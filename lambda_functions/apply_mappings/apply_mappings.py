import json
import boto3
import os
from typing import Dict, List, Set

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Apply category/mechanic/theme mappings to enriched data.
    Reads from silver layer and writes to gold layer.
    """

    reference_bucket = os.environ['REFERENCE_BUCKET']
    silver_bucket = os.environ['SILVER_BUCKET']
    gold_bucket = os.environ['GOLD_BUCKET']

    # Load the mapping files from S3
    category_mapping = load_mapping(reference_bucket, Key='mappings/category_mapping.json')
    mechanic_mapping = load_mapping(reference_bucket, Key='mappings/mechanic_mapping.json')
    theme_mapping = load_mapping(reference_bucket, Key='mappings/theme_mapping.json')

    # Process games from silver layer
    games = load_games_from_silver(silver_bucket)

    enriched_games = []
    for game in games:
        enriched_game = game.copy()

        # Apply category mappings
        enriched_game['grouped_categories'] = apply_category_mapping(
            game.get('categories', []),
            category_mapping
        )

        # Apply mechanic mappings
        enriched_game['grouped_mechanics'] = apply_mechanic_mapping(
            game.get('mechanics', []),
            mechanic_mapping
        )

        # Apply theme mappings
        enriched_game['grouped_themes'] = apply_theme_mapping(
            game.get('themes', []),
            theme_mapping
        )

        enriched_games.append(enriched_game)
    
    # Store enriched games to gold layer
    store_enriched_games(gold_bucket, enriched_games)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed_games': len(enriched_games)
        })
    }

def load_mapping(bucket: str, Key: str) -> Dict:
    """Load mapping from S3"""

    response = s3_client.get_object(Bucket=bucket, Key=Key)
    return json.loads(response['Body'].read())

def apply_category_mapping(original_categories: List[str], mapping: Dict) -> List[str]:
    """Apply category mappings to original categories"""

    grouped = set()
    mapping_dict = mapping['mappings']

    for original_cat in original_categories:
        for grouped_cat, config in mapping_dict.items():
            if original_cat in config['original_categories']:
                grouped.add(grouped_cat)
                break

    return sorted(list(grouped))

def apply_mechanic_mapping(original_mechanics: List[str], mapping: Dict) -> List[str]:
    """Map original mechanics to grouped mechanics"""

    grouped = set()
    mapping_dict = mapping['mappings']

    for original_mech in original_mechanics:
        for grouped_mech, config in mapping_dict.items():
            if original_mech in config['original_mechanics']:
                grouped.add(grouped_mech)
                break
    
    return sorted(list(grouped))

def apply_theme_mapping(original_themes: List[str], mapping: Dict) -> List[str]:
    """Apply theme mappings to original themes"""

    grouped = set()
    mapping_dict = mapping['mappings']

    for original_theme in original_themes:
        for grouped_theme, config in mapping_dict.items():
            if original_theme in config['original_themes']:
                grouped.add(grouped_theme)
                break

    return sorted(list(grouped))

def load_games_from_silver(bucket: str) -> List[Dict]:
    """Load games from silver layer in S3"""

    games = []
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix='games/')

    for page in pages:
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            if obj['Key'].endswith('.json'):
                game_data = s3_client.get_object(Bucket=bucket, Key=obj['Key'])
                game = json.loads(game_data['Body'].read())
                games.append(game)

    return games

def store_enriched_games(bucket: str, games: List[Dict]):
    """Store enriched games to gold layer in S3"""

    for game in games:
        key = f"games/game_{game['game_id']}.json"
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(game, indent=2),
            ContentType='application/json'
        )