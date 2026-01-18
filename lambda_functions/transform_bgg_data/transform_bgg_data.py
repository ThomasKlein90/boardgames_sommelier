# lambda_functions/transform_bgg_data/transform_bgg_data.py

import json
import os
import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
import logging
from typing import Dict, List
import io
from urllib.parse import unquote_plus

# Configure logging
logger = logging.getLoggger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')

def read_parquet_from_s3 (bucket: str, prefix: str) -> pd.DataFrame:
    """
    Read all parquet files from s3 prefix into single DataFrame

    Args:
        bucket: S3 bucket name
        prefix: S3 prefix (folder path)

    Returns:
        Combined pandas DataFrame
    """
    dfs = []

    # List all objects with prefix
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    for page in pages:
        if 'Contents' not in page:
            continue

        for obj in page['Contents']:
            key = obj['Key']

            if not key.endswith('.parquet'):
                continue

            try:
                response = s3_client.get_object(Bucket=bucket, Key=key)
                df = pd.read_parquet(io.BytesIO(response['Body'].read()))
                dfs.append(df)
            except Exception as e:
                logger.error(f"Error reading {key}: {str(e)}")
                continue

    if not dfs:
        return pd.DataFrame()
    
    return pd.concat(dfs, ignore_index=True)

def create_bridge_tables(silver_bucket: str, raw_games_bronze: List[Dict]) -> Dict[str, pd.DataFrame]:
    """
    Create bridge tables linking games to dimensions

    Args:
        silver_bucket: Silver S3 bucket name
        raw_games_bronze: Raw game data (needed for many-to-many relationships)

    Returns:
        Dictionary of bridge table DataFrames
    """
    bridge_tables = {}

    # Read dim_game to get game_id mappings
    df_game = read_parquet_from_s3(silver_bucket, 'bgg/dim_game/')
    game_id_map = dict(zip(df_game['bgg_game_id'], df_game['game_id']))

    # Create bridge tables for each dimension
    bridges = {
        'categories': ('category_id', 'br_game_category'),
        'mechanics': ('mechanic_id', 'br_game_mechanic'),
        'themes': ('theme_id', 'br_game_theme'),
        'publishers': ('publisher_id', 'br_game_publisher'),
        'artists': ('artist_id', 'br_game_artist')
    }

    for source_field, (id_field, table_name) in bridges.items():
        bridge_data = []

        for game in raw_games_bronze:
            bgg_game_id = game.get('bgg_game_id')
            game_id_sk = game_id_map.get(bgg_game_id)

            if not game_id_sk:
                continue

            items = game.get(source_field, [])
            for item in items:
                bridge_data.append({
                    'game_id':game_id_sk,
                    id_field: item.get('id')
                })

        if bridge_data:
            df_bridge = pd.DataFrame(bridge_data).drop_duplicates()
            bridge_tables[table_name] = df_bridge
            logger.info(f"Create {table_name} with {len(df_bridge)} records")

    return bridge_tables

def create_fact_user_rating(raw_games_bronze: List[Dict], game_id_map: Dict[int, str]) -> pd.DataFrame:
    """
    Create fact table for user ratings

    Args:
        raw_games_bronze: Raw game data
        game_id_map: Mapping of the bgg_game_id to game_id_sk

    Returns:
        DataFrame for fct_user_rating
    """

    # For BGG data we don't have individual user rating from the XML API
    # We will choose the grain of the fact table to be the aggregate record instad

    fact_data = []

    for game in raw_games_bronze:
        bgg_game_id = game.get('bgg_game_id')
        game_id_sk = game_id_map.get(bgg_game_id)

        if not game_id_sk:
            continue
    
        # Create a single aggregate record per game
        fact_data.append({
            'user_id_sk': 'bgg_aggregate',
            'game_id_sk': game_id_sk,
            'bgg_latest_rating': game.get('average_rating'),
            'extraction_date': game.get('extraction_date', datetime.utcnow().isoformat())
        })

    return pd.DataFrame(fact_data)

def lambda_handler(event, context):
    """
    Lambda handler for transforming data into star schema (Gold layer)
    Triggered by S3 event when new dim_game data lands in silver
    """
    try:
        silver_bucket = os.environ['SILVER_BUCKET']
        gold_bucket = os.environ['GOLD_BUCKET']

        # We need to read the original bronze data to create bridge tables
        # this should be passed in the event or we need to track it

        # For this implementation we'll read from bronze based on extraction date
        # In production you'd want better better coordination

        logger.info("Starting gold layer transformation")

        # Read dim_game
        df_game = read_parquet_from_s3(silver_bucket, 'bgg/dim_game/')
        game_id_map = dict(zip(df_game['bgg_game_id'], df_game['game_id']))

        # For bridge tables, we need the raw data
        # This is a simplified approach - in production, store relationships separately
        bronze_bucket = os.environ('BRONZE_BUCKET')

        # List recent bronze files
        response = s3_client.list_objects_v2(
            Bucket=bronze_bucket,
            Prefix='bgg/raw_games/',
            MaxKeys=10
        )

        raw_games = []
        if 'Contents' in response:
            # Get most recent file
            latest_file = sorted(response['Contents'],
                                 key=lambda x: x['LastModified'],
                                 reverse=True)[0]
            
            obj_response = s3_client.get_object(
                Bucket=bronze_bucket,
                Key=latest_file['key']
            )
            raw_games = json.loads(obj_response['Body'].read().decode('utf-8'))

        # Create bridge tables
        bridge_tables = create_bridge_tables(silver_bucket, raw_games)

        # Save bridge tables to gold layer (partitioned by year)
        for table_name, df_bridge in bridge_tables.items():
            # Add year from game
            df_bridge_with_year = df_bridge.merge(
                df_game[['game_id','year']],
                on='game_id',
                how='left'
            )

            # Partition by year
            for year, year_df in df_bridge_with_year.groupby('year'):
                if pd.isna(year):
                    year = 0

                year = int(year)

                # Drop year column before saving
                year_df = year_df.drop('year', axis=1)

                table = pa.Table.from_pandas(year_df)

                s3_key = f"bgg/{table_name}/year_published={year}/data.parquet"

                parquet_buffer = io.BytesIO()
                pq.write_table(table, parquet_buffer, compression='snappy')
                parquet_buffer.seek(0)

                s3_client.put_object(
                    Bucket=gold_bucket,
                    Key=s3_key,
                    Body=parquet_buffer.getvalue(),
                    ContentType='application/parquet'
                )

                logger.info(f"Wrote {len(year_df)} records to {s3_key}")

        # Create fact_user_rating
        df_fact = create_fact_user_rating(raw_games, game_id_map)

        if len(df_fact) > 0:
            # Partition by extraction_date
            df_fact['extraction_date_parsed'] = pd.to_datetime(df_fact['extraction_date']).dt.date

            for date, date_df in df_fact.groupby('extraction_date_parsed'):
                date_df = date_df.drop('extraction_date_parsed', axis=1)

                table = pa.Table.from_pandas(date_df)

                s3_key = f"bgg/fct_user_rating/extraction_date={date}/data.parquet"

                parquet_buffer = io.BytesIO()
                pq.write_table(table, parquet_buffer, compression='snappy')
                parquet_buffer.seek(0)

                s3_client.put_object(
                    Bucket=gold_bucket,
                    Key=s3_key,
                    Body=parquet_buffer.getvalue(),
                    ContentType='application/parquet'
                )

                logger.info(f"Wrote {len(date_df)} fact records to {s3_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Gold layer transformation completed successfully')
        }
    
    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        raise