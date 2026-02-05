# lambda_functions/clean_bgg_data/clean_bgg_data.py

import json
import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
import logging
from typing import Dict, List, Any
import io
import os
import uuid
from urllib.parse import unquote_plus

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')

# Define schema for dim_game
DIM_GAME_SCHEMA = {
    'game_id': 'string',
    'bgg_game_id': 'int64',
    'year': 'int32',            # for partitioning
    'weight': 'float64',
    'min_players': 'int32',
    'max_players': 'int32',
    'min_players_best': 'int32',
    'max_players_best': 'int32',
    'min_age_rec': 'int32',
    'min_time': 'int32',
    'max_time': 'int32',
    'cooperative': 'boolean',
    'rank_bgg': 'int32',
    'num_votes_bgg': 'int32',
    'avg_rating_bgg': 'float64',
    'stddev_rating_bgg': 'float64',
    'bayes_rating_bgg': 'float64',
    'complexity_bgg': 'float64',
    'reddit_game_id': 'string',     # for future use
    'bgstats_game_id': 'string',    # for future use
    'bga_game_id': 'string',        # for future use
    'primary_name': 'string',
    'description': 'string',
    'thumbnail_url': 'string',
    'image_url': 'string',
    'extraction_date': 'string'
}

def validate_and_clean_game_data(raw_games: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Validate and clean raw game data into dim_game schema

    Args:    
        raw_games: List of raw game dictionaries from bronze layer
    
    Returns:
        Pandas DataFrame conforming to dim_game schema
    """
    cleaned_games = []

    for game in raw_games:
        try:
            # Use bgg_game_id if present, otherwise fall back to game_id from bronze
            source_id = game.get('bgg_game_id') or game.get('game_id')
            if source_id is None:
                logger.warning("Missing bgg_game_id/game_id in raw game payload")
            # Generate game_id_sk (surrogate key)
            game_id_sk = f"bggg_{source_id or 0}"

            # Check if cooperative (simple heuristic: check if cooperative in mechanics)
            mechanics = game.get('mechanics',[])
            is_cooperative = any(
                'cooperative' in (m.get('name','') if isinstance(m, dict) else str(m)).lower()
                for m in mechanics
            )

            stats = game.get('statistics', {}) if isinstance(game.get('statistics', {}), dict) else {}

            cleaned_game = {
                'game_id': game_id_sk,
                'bgg_game_id': source_id,
                'year': game.get('year_published'),    
                'weight': game.get('average_weight'),
                'min_players': game.get('min_players'),
                'max_players': game.get('max_players'),
                'min_players_best': game.get('min_players_best'),
                'max_players_best': game.get('max_players_best'),
                'min_age_rec': game.get('min_age_rec') or game.get('min_age'),
                'min_time': game.get('min_playtime'),
                'max_time': game.get('max_playtime'),
                'cooperative': is_cooperative,                          # to update
                'rank_bgg': game.get('rank_boardgame'),
                'num_votes_bgg': stats.get('users_rated'),
                'avg_rating_bgg': stats.get('average_rating'),
                'stddev_rating_bgg': stats.get('stddev'),
                'bayes_rating_bgg': stats.get('bayes_average_rating'),
                'complexity_bgg': stats.get('average_weight'),
                'reddit_game_id': None,
                'bgstats_game_id': None,
                'bga_game_id': None,
                'primary_name': game.get('primary_name',''),
                'description': game.get('description',''),
                'thumbnail_url': game.get('thumbnail',''),
                'image_url': game.get('image',''),
                'extraction_date': game.get('extraction_date', datetime.utcnow().isoformat())
            }

            cleaned_games.append(cleaned_game)

        except Exception as e:
            logger.error(f"Error cleaning game {game.get('bgg_game_id')}: {str(e)}")
            continue

    # Convert to DataFrame
    df = pd.DataFrame(cleaned_games)

    # Apply schema types
    for col, dtype in DIM_GAME_SCHEMA.items():
        if col in df.columns:
            try:
                if dtype == 'int32' or dtype == 'int64':
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                elif dtype == 'float64':
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                elif dtype == 'boolean':
                    df[col] = df[col].astype('boolean')
                elif dtype == 'string':
                    df[col] = df[col].astype('string')
            except Exception as e:
                logger.warning(f"Error converting column {col} to {dtype}: {str(e)}")

    # Normalize zero min/max players to 1
    if 'min_players' in df.columns:
        df['min_players'] = df['min_players'].where(df['min_players'] != 0, 1)
    if 'max_players' in df.columns:
        df['max_players'] = df['max_players'].where(df['max_players'] != 0, 1)

    return df

def extract_dimension_data(raw_games: List[Dict[str, Any]], dimension: str, id_column: str, name_column: str, description_column: str, grouped_column: str = None) -> pd.DataFrame:
    """
    Extract dimension table data (category, mechanic, theme, publisher, artist)
    
    Args:
        raw_games: List of raw game dictionaries
        dimension: Name of dimension ('categories', 'mechanics', 'themes', 'publishers', 'artists')

    Returns:
        Pandas DataFrame with unique dimension records
    """

    dimension_data = []

    next_id = 1

    for game in raw_games:
        items = game.get(dimension, [])

        for item in items:
            if isinstance(item, dict):
                item_id = item.get('id')
                item_name = item.get('name', '')
            else:
                item_id = next_id
                item_name = str(item)
                next_id += 1

            dimension_data.append({
                id_column: item_id,
                name_column: item_name
            })
    
    # Remove duplicates
    df = pd.DataFrame(dimension_data).drop_duplicates(subset=[id_column])

    # Add description column (empty for now)
    df[description_column] = ''

    # For categories and mechanics, add grouped column
    if grouped_column:
        df[grouped_column] = df[id_column]

    return df

def lambda_handler(event, context):
    """
    Lambda handler for cleaning and validating BGG data
    Triggered by S3 even when new file lands in bronze layer
    """
    try:
        bronze_bucket = os.environ['BRONZE_BUCKET']
        silver_bucket = os.environ['SILVER_BUCKET']

        # Parse S3 event
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = unquote_plus(record['s3']['object']['key'])

            logger.info(f"Processing file: s3://{bucket}/{key}")

            # Read raw data from bronze
            response = s3_client.get_object(Bucket=bucket, Key=key)
            raw_game = json.loads(response['Body'].read().decode('utf-8'))

            # Convert single game dict to list for validation function
            raw_games = [raw_game] if isinstance(raw_game, dict) else raw_game

            logger.info(f"Loaded {len(raw_games)} raw games")

            # Clean dim_game data
            df_game = validate_and_clean_game_data(raw_games)

            # Group by year for paritioning
            for year, year_df in df_game.groupby('year'):
                if pd.isna(year):
                    year = 0  # unknown year
                
                year = int(year)

                # Convert to Parquet
                table = pa.Table.from_pandas(year_df)

                # Write to S3 silver layer (partitioned by year)
                s3_key = f"bgg/dim_game/year_published={year}/data.parquet"

                parquet_buffer = io.BytesIO()
                pq.write_table(table, parquet_buffer, compression='snappy')
                parquet_buffer.seek(0)

                # Validate parquet buffer before upload
                try:
                    pq.ParquetFile(parquet_buffer)
                except Exception as e:
                    logger.error(f"Invalid parquet buffer for {s3_key}: {str(e)}")
                    continue
                finally:
                    parquet_buffer.seek(0)

                # Atomic write: upload to temp key in separate prefix then copy to final key
                temp_key = f"bgg/_tmp/{uuid.uuid4()}-data.parquet"
                s3_client.put_object(
                    Bucket=silver_bucket,
                    Key=temp_key,
                    Body=parquet_buffer.getvalue(),
                    ContentType='application/parquet'
                )
                s3_client.copy_object(
                    Bucket=silver_bucket,
                    CopySource={'Bucket': silver_bucket, 'Key': temp_key},
                    Key=s3_key,
                    ContentType='application/parquet'
                )
                s3_client.delete_object(Bucket=silver_bucket, Key=temp_key)

                logger.info(f"Wrote {len(year_df)} games to {s3_key}")

            # Extract and save dimension tables (no partitioning)
            dimensions = {
                'categories': ('dim_category', 'category_id', 'category_name', 'category_description', 'grouped_category_name'),
                'mechanics': ('dim_mechanic', 'mechanic_id', 'mechanic_name', 'mechanic_description', 'grouped_mechanic_name'),
                'families': ('dim_theme', 'theme_id', 'theme_name', 'theme_description', None),
                'publishers': ('dim_publisher', 'publisher_id', 'publisher_name', 'publisher_description', None),
                'artists': ('dim_artist', 'artist_id', 'artist_name', 'artist_description', None)
            }

            for dim_source, (dim_table, id_column, name_column, description_column, grouped_column) in dimensions.items():
                df_dim = extract_dimension_data(raw_games, dim_source, id_column, name_column, description_column, grouped_column)

                if len(df_dim) > 0:
                    # Reset index and convert to Parquet
                    df_dim = df_dim.reset_index(drop=True)
                    table = pa.Table.from_pandas(df_dim, preserve_index=False)

                    # Write to S3 (no partitioning for dimension tables)
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    s3_key = f"bgg/{dim_table}/data_{timestamp}.parquet"

                    parquet_buffer = io.BytesIO()
                    pq.write_table(table, parquet_buffer, compression='snappy')
                    parquet_buffer.seek(0)

                    # Validate parquet buffer before upload
                    try:
                        pq.ParquetFile(parquet_buffer)
                    except Exception as e:
                        logger.error(f"Invalid parquet buffer for {s3_key}: {str(e)}")
                        continue
                    finally:
                        parquet_buffer.seek(0)

                    # Atomic write: upload to temp key in separate prefix then copy to final key
                    temp_key = f"bgg/_tmp/{uuid.uuid4()}-data.parquet"
                    s3_client.put_object(
                        Bucket=silver_bucket,
                        Key=temp_key,
                        Body=parquet_buffer.getvalue(),
                        ContentType='application/parquet'
                    )
                    s3_client.copy_object(
                        Bucket=silver_bucket,
                        CopySource={'Bucket': silver_bucket, 'Key': temp_key},
                        Key=s3_key,
                        ContentType='application/parquet'
                    )
                    s3_client.delete_object(Bucket=silver_bucket, Key=temp_key)

                    logger.info(f"Wrote {len(df_dim)} {dim_table} records to {s3_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Data cleaning completed successfully')
        }
    
    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        raise