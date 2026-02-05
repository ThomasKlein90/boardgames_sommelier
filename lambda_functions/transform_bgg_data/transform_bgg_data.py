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
logger = logging.getLogger()
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
    if df_game.empty:
        logger.warning("No dim_game data found in silver; bridge tables will be empty.")
        return bridge_tables
    game_id_map = dict(zip(df_game['bgg_game_id'], df_game['game_id']))

    # Create bridge tables for each dimension
    bridges = {
        'categories': ('category_id', 'category_name', 'br_game_category'),
        'mechanics': ('mechanic_id', 'mechanic_name', 'br_game_mechanic'),
        'families': ('theme_id', 'theme_name', 'br_game_theme'),
        'publishers': ('publisher_id', 'publisher_name', 'br_game_publisher'),
        'artists': ('artist_id', 'artist_name', 'br_game_artist')
    }

    for source_field, (id_field, name_field, table_name) in bridges.items():
        bridge_data = []
        # Track unique dimension values to assign IDs
        dim_values = set()

        for game in raw_games_bronze:
            bgg_game_id = game.get('bgg_game_id') or game.get('game_id')
            # Convert to int if it's a string
            if isinstance(bgg_game_id, str):
                try:
                    bgg_game_id = int(bgg_game_id)
                except (ValueError, TypeError):
                    continue
            
            game_id_sk = game_id_map.get(bgg_game_id)

            if not game_id_sk:
                continue

            items = game.get(source_field, [])
            if not isinstance(items, list):
                continue

            for item in items:
                # Items are strings (e.g., "Abstract Strategy", "Dice Rolling")
                if isinstance(item, str) and item.strip():
                    item_name = item.strip()
                    dim_values.add(item_name)
                    bridge_data.append({
                        'game_id': game_id_sk,
                        name_field: item_name
                    })

        if bridge_data:
            # Create dimension ID mapping (assign sequential IDs)
            dim_id_map = {name: idx + 1 for idx, name in enumerate(sorted(dim_values))}
            
            # Add IDs to bridge data
            for record in bridge_data:
                record[id_field] = dim_id_map[record[name_field]]
            
            df_bridge = pd.DataFrame(bridge_data).drop_duplicates()
            # Keep only game_id and id_field for bridge table
            df_bridge = df_bridge[['game_id', id_field]]
            
            bridge_tables[table_name] = df_bridge
            logger.info(f"Created {table_name} with {len(df_bridge)} records from {len(dim_values)} unique {source_field}")

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
        bgg_game_id = game.get('bgg_game_id') or game.get('game_id')
        # Convert to int if it's a string
        if isinstance(bgg_game_id, str):
            try:
                bgg_game_id = int(bgg_game_id)
            except (ValueError, TypeError):
                continue
        
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
        logger.info(f"Gold bucket: {gold_bucket}")

        # Read dim_game
        df_game = read_parquet_from_s3(silver_bucket, 'bgg/dim_game/')
        logger.info(f"Loaded dim_game rows: {len(df_game)}")
        if df_game.empty:
            logger.warning("No dim_game data found in silver. Exiting gold transform.")
            return {
                'statusCode': 204,
                'body': json.dumps('No dim_game data found. Skipping gold layer transformation.')
            }
        game_id_map = dict(zip(df_game['bgg_game_id'], df_game['game_id']))

        # For bridge tables, we need the raw data
        # This is a simplified approach - in production, store relationships separately
        bronze_bucket = os.environ['BRONZE_BUCKET']

        # Load today's bronze files (multiple games)
        today = datetime.utcnow().strftime('%Y%m%d')
        raw_games = []
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bronze_bucket, Prefix='bgg/raw_games/')

        loaded_files = 0
        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                key = obj['Key']
                if f"date={today}" not in key:
                    continue

                obj_response = s3_client.get_object(
                    Bucket=bronze_bucket,
                    Key=key
                )
                raw_game = json.loads(obj_response['Body'].read().decode('utf-8'))
                if isinstance(raw_game, dict):
                    raw_games.append(raw_game)
                elif isinstance(raw_game, list):
                    raw_games.extend(raw_game)

                loaded_files += 1

        logger.info(f"Loaded {len(raw_games)} raw games from {loaded_files} bronze files for date={today}")
        if not raw_games:
            logger.warning("No bronze games found for today. Exiting gold transform.")
            return {
                'statusCode': 204,
                'body': json.dumps('No bronze games found for today. Skipping gold layer transformation.')
            }

        # Create bridge tables
        bridge_tables = create_bridge_tables(silver_bucket, raw_games)
        if not bridge_tables:
            logger.warning("No bridge tables created. Check raw game data and dim_game mappings.")

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

                # Drop year column and reset index before saving
                year_df = year_df.drop('year', axis=1).reset_index(drop=True)

                table = pa.Table.from_pandas(year_df, preserve_index=False)

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
        logger.info(f"Fact user rating rows: {len(df_fact)}")

        if len(df_fact) > 0:
            # Partition by extraction_date
            df_fact['extraction_date_parsed'] = pd.to_datetime(df_fact['extraction_date']).dt.date

            for date, date_df in df_fact.groupby('extraction_date_parsed'):
                # Drop both the parsed date and original extraction_date, then reset index
                date_df = date_df.drop(['extraction_date_parsed', 'extraction_date'], axis=1).reset_index(drop=True)

                table = pa.Table.from_pandas(date_df, preserve_index=False)

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