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

STATE_PARTITION_KEY = '__STATE__'
LAST_SCANNED_SORT_KEY = 'LAST_SCANNED_ID'

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
    2. Scan IDs ranges incrementally for unseen games.
    3. Refresh games last updated beyond a cutoff.
    """
    bucket_name = os.environ['RAW_BUCKET_NAME']
    bearer_token = get_bearer_token()

    scan_range_size = int(os.environ.get('SCAN_RANGE_SIZE', '1000'))
    refresh_days = int(os.environ.get('REFRESH_DAYS', '30'))
    refresh_limit = int(os.environ.get('REFRESH_LIMIT', '100'))
    hot_limit = int(os.environ.get('HOT_LIMIT', '50'))
    new_ids_limit = int(os.environ.get('NEW_IDS_LIMIT', '1000'))

    discovered_new_games = set()

    # Strategy 1: Check BGG's "hot" games list
    hot_games = list(get_hot_games(bearer_token))
    hot_games = hot_games[:hot_limit]
    discovered_new_games.update(hot_games)

    # Strategy 2: Scan ID ranges incrementally
    last_scanned_id = get_last_scanned_id()
    new_games = scan_id_range(bearer_token, last_scanned_id, last_scanned_id + scan_range_size)
    discovered_new_games.update(new_games)

    # Strategy 3: Refresh games beyond cutoff
    cutoff_date = datetime.utcnow() - timedelta(days=refresh_days)
    recent_games = get_recently_processed_games(cutoff_date)
    games_to_refresh = get_games_needing_refresh(cutoff_date, refresh_limit)

    # Avoid reprocessing recently completed games
    discovered_new_games = discovered_new_games - recent_games

    # Avoid duplicates between new and refresh
    discovered_new_games = discovered_new_games - games_to_refresh

    # Cap new discovery batch size
    if len(discovered_new_games) > new_ids_limit:
        discovered_new_games = set(list(discovered_new_games)[:new_ids_limit])

    # Final list combines new discovery + stale refresh
    discovered_games = list(discovered_new_games.union(games_to_refresh))

    # Store discovered game IDs for processing
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    s3_client.put_object(
        Bucket=bucket_name,
        Key=f'game_ids/discovered_{timestamp}.json',
        Body=json.dumps({
            'timestamp': timestamp,
            'game_ids': discovered_games,
            'total_count': len(discovered_games),
            'discovery_methods': {
                'hot_games': len(hot_games),
                'id_scan': len(new_games),
                'refresh': len(games_to_refresh)
            },
            'limits': {
                'scan_range_size': scan_range_size,
                'refresh_days': refresh_days,
                'refresh_limit': refresh_limit,
                'hot_limit': hot_limit,
                'new_ids_limit': new_ids_limit
            }
        }, indent=2)
    )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'discovered_games': len(discovered_games),
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
    batch_size = int(os.environ.get('SCAN_BATCH_SIZE', '20'))
    for batch_start in range(start_id, end_id, batch_size):
        batch_end = min(batch_start + batch_size, end_id)
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

    set_last_scanned_id(end_id)

    return valid_games

def get_last_scanned_id() -> int:
    """Retrieve the last scanned game ID from DynamoDB"""
    try:
        response = state_table.get_item(
            Key={'game_id': STATE_PARTITION_KEY, 'last_updated': LAST_SCANNED_SORT_KEY}
        )
        return int(response.get('Item', {}).get('value', '1'))
    except Exception:
        return 1

def set_last_scanned_id(last_scanned_id: int) -> None:
    """Persist last scanned game ID to DynamoDB"""
    state_table.put_item(
        Item={
            'game_id': STATE_PARTITION_KEY,
            'last_updated': LAST_SCANNED_SORT_KEY,
            'value': str(last_scanned_id),
            'processing_status': 'STATE'
        }
    )
    
def get_games_needing_refresh(cutoff_date: datetime, limit: int) -> Set[str]:
    """Get game IDs that need refreshing (older than cutoff)"""
    cutoff_iso = cutoff_date.isoformat()
    results: Dict[str, str] = {}

    try:
        response = state_table.query(
            IndexName='StatusIndex',
            KeyConditionExpression='processing_status = :status AND last_updated < :cutoff',
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':cutoff': cutoff_iso
            },
            Limit=limit
        )

        for item in response.get('Items', []):
            game_id = item.get('game_id')
            last_updated = item.get('last_updated')
            if game_id and last_updated:
                current = results.get(game_id)
                if current is None or last_updated > current:
                    results[game_id] = last_updated

        return set(results.keys())
    except Exception as e:
        print(f"Error querying games needing refresh: {e}")
        return set()

def get_recently_processed_games(cutoff_date: datetime) -> Set[str]:
    """Get game IDs processed on/after cutoff to avoid reprocessing"""
    cutoff_iso = cutoff_date.isoformat()
    results: Dict[str, str] = {}

    try:
        paginator_key = None
        while True:
            response = state_table.query(
                IndexName='StatusIndex',
                KeyConditionExpression='processing_status = :status AND last_updated >= :cutoff',
                ExpressionAttributeValues={
                    ':status': 'COMPLETED',
                    ':cutoff': cutoff_iso
                },
                ExclusiveStartKey=paginator_key
            )

            for item in response.get('Items', []):
                game_id = item.get('game_id')
                last_updated = item.get('last_updated')
                if game_id and last_updated:
                    current = results.get(game_id)
                    if current is None or last_updated > current:
                        results[game_id] = last_updated

            paginator_key = response.get('LastEvaluatedKey')
            if not paginator_key:
                break

        return set(results.keys())
    except Exception as e:
        print(f"Error querying recently processed games: {e}")
        return set()