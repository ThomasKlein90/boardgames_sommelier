import json
import boto3
import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Set
import xml.etree.ElementTree as ET

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')
state_table = dynamodb.Table(os.environ['STATE_TABLE_NAME'])

def get_bearer_token():
    """Retrieve BGG bearer token from AWS Secrets Manager using env var name"""
    secret_name = os.environ.get('BGG_SECRET_NAME')
    if not secret_name:
        raise ValueError("BGG_SECRET_NAME environment variable is not set")
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
            return secret.get('token') or secret.get('bearer_token')
        raise ValueError("Bearer token not found in secret")
    except Exception as e:
        raise ValueError(f"Failed to retrieve bearer token from Secrets Manager: {e}")

def lambda_handler(event, context):
    """ 
    Discovers new and updated game IDs from BGG API

    Strategies:
    1. Check BGG's "hot" games list for new popular games.
    2. Scan IDS ranges incrementally.
    3. Check for games updated in last N days.
    """
    bucket_name = os.environ['RAW_BUCKET_NAME']
    bearer_token = get_bearer_token()

    discovered_games = set()

    # Strategy 1: Check BGG's "hot" games list
    hot_games = get_hot_games(bearer_token)
    discovered_games.update(hot_games)

    # Strategy 2: Scan ID ranges incrementally
    last_scanned_id = get_last_scanned_id()
    new_games = scan_id_range(bearer_token, last_scanned_id, last_scanned_id + 1000)
    discovered_games.update(new_games)

    # Strategy 3: Check for games updated in last N days
    games_to_refresh = get_games_needing_refresh()
    discovered_games.update(games_to_refresh)

    # Store discovered game IDs for processing
    game_list = list(discovered_games)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    s3_client.put_object(
        Bucket=bucket_name,
        Key=f'game_ids/discovered_{timestamp}.json',
        Body=json.dumps({
            'timestamp': timestamp,
            'game_ids': game_list,
            'total_count': len(game_list),
            'discovery_methods': {
                'hot_games': len(hot_games),
                'id_scan': len(new_games),
                'refresh': len(games_to_refresh)
            }
        }, indent=2)
    )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'discovered_games': len(game_list),
            'timestamp': timestamp
        })
    }

def get_hot_games(bearer_token: str) -> Set[str]:
    """Fetch currently trending games from BGG API"""
    headers = {
        'Authorization': f'Bearer {bearer_token}',
        'User-Agent': 'BGG-Data-Pipeline/1.0'
    }

    try:
        response = requests.get(
            'https://boardgamegeek.com/xmlapi2/hot?type=boardgame',
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)
        game_ids = {item.get('id') for item in root.findall('.//item[@type="boardgame"]')}

        return game_ids
    except Exception as e:
        print(f"Error fetching hot games: {e}")
        return set()
    
def scan_id_range(bearer_token: str, start_id: int, end_id: int) -> Set[str]:
    """Scan a range of game IDs to find valid games"""
    headers = {
        'Authorization': f'Bearer {bearer_token}',
        'User-Agent': 'BGG-Data-Pipeline/1.0'
    }

    valid_games = set()

    # Batch IDs for efficiency (BGG API supports up to 20 IDs per request)
    for batch_start in range(start_id, end_id, 20):
        batch_end = min(batch_start + 20, end_id)
        ids_param = ','.join(str(i) for i in range(batch_start, batch_end))

        try:
            response = requests.get(
                f'https://boardgamegeek.com/xmlapi2/thing?id={ids_param}&type=boardgame',
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                root = ET.fromstring(response.content)
                game_ids = {item.get('id') for item in root.findall('.//item[@type="boardgame"]')}
                valid_games.update(game_ids)
            
            # Be respectful to BGG API
            import time
            time.sleep(1)

        except Exception as e:
            print(f"Error scanning ID range {batch_start}-{batch_end}: {e}")

    # Update last scanned ID in DynamoDB
    state_table.put_item(
        Item={
            'game_id': 'LAST_SCANNED_ID',
            'last_updated': datetime.utcnow().isoformat(),
            'value': str(end_id)
        }
    )

    return valid_games

def get_last_scanned_id() -> int:
    """Retrieve the last scanned game ID from DynamoDB"""
    try:
        response = state_table.get_item(
            Key={'game_id': 'LAST_SCANNED_ID','last_updated': 'CURRENT'}
        )
        return int(response.get('Item', {}).get('value', '1'))
    except:
        return 1
    
def get_games_needing_refresh() -> Set[str]:
    """Get game IDs that need refreshing (older than 30 days)"""
    cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()

    try:
        response = state_table.query(
            IndexName='StatusIndex',
            KeyConditionExpression='processing_status = :status AND last_updated < :cutoff',
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':cutoff': cutoff_date
            },
            Limit=100 # Limit refresh batch size
        )

        return {item['game_id'] for item in response.get('Items', [])}
    except Exception as e:
        print(f"Error querying games needing refresh: {e}")
        return set()