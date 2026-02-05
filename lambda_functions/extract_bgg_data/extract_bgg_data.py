# lambda_functions/extract_bgg_data/extract_bgg_data.py
# VERSION: v1.2.0 - Fixed BGG API endpoint to https://boardgamegeek.com/xmlapi2
import json
import boto3
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import logging
from typing import Dict, List, Optional, Any
import socket
import hashlib

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Intialize AWS clients
s3_client = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')
dynamodb = boto3.resource('dynamodb')
state_table = dynamodb.Table(os.environ['STATE_TABLE_NAME'])

def get_secret(secret_name: str, region: str) -> str:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        return secret.get('token', '')
    except Exception as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise

def parse_input_event(event: Dict) -> List[str]:
    """
    Parse various input formats for game IDs
    """
    # Direct game_id
    if 'game_id' in event:
        return [str(event['game_id'])]
    
    # List of game_ids
    if 'game_ids' in event:
        return [str(gid) for gid in event['game_ids']]
    
    # S3 Reference
    if 's3_key' in event:
        s3_data = s3_client.get_object(
            Bucket=event['bucket'],
            Key=event['s3_key']
        )
        data = json.loads(s3_data['Body'].read())
        return [str(gid) for gid in data.get('game_ids',[])]
    
    return []

def should_skip_game(game_id: str) -> bool:
    """Check if game should be skipped (DISABLED for testing - DynamoDB queries too slow)"""
    # TODO: Re-enable after optimizing with batch queries or caching
    return False
    
def update_game_state(game_id: str, status: str, game_data: Optional[Dict] = None, error: Optional[str] = None):
    """Update game processing state in DynamoDB"""
    item = {
        'game_id': game_id,
        'processing_status': status,
        'last_updated': datetime.utcnow().isoformat()
    }
    if game_data:
        # Store data hash to detect changes
        data_hash = hashlib.md5(json.dumps(game_data, sort_keys=True).encode()).hexdigest()
        item['data_hash'] = data_hash
        item['year_published'] = game_data.get('year_published')
        item['name'] = game_data.get('primary_name','')

    if error:
        item['error_message'] = error

    #Set TTL for 90 days
    item['ttl'] = int((datetime.utcnow().timestamp()) + 90*24*3600)

    state_table.put_item(Item=item)

def fetch_game_data(game_id: str, bearer_token: str) -> Optional[Dict]:
    """
    Fetch game data from BoardGameGeek XML API2 with retry logic.

    Args:
        game_id (int): The BGG ID of the game to fetch.
        bearer_token (str, optional): Bearer token for authentication. Defaults to None.

    Returns:
        Dictionary containing parsed game data.
    """
    url = f"https://boardgamegeek.com/xmlapi2/thing?id={game_id}&stats=1&type=boardgame"
    
    headers = {
        'Authorization': f'Bearer {bearer_token}',
        'User-Agent': 'BoardGames Sommelier/1.0',
        'Accept': 'application/xml',
        'Accept-Encoding': 'gzip, deflate'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse XML response
        root = ET.fromstring(response.content)
        item = root.find('.//item[@type="boardgame"]')

        if item is None:
            logger.warning(f'No boardgame item found for game ID {game_id}.')
            return None

        # Extract game data
        game_data = extract_game_details(item)
        game_data['api_response_raw'] = response.text
        game_data['extraction_timestamp'] = datetime.utcnow().isoformat()

        return game_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for game {game_id}: {str(e)}")
        return None
        
    except ET.ParseError as e:
        logger.error(f"XML parsing failed for game {game_id}: {str(e)}")
        return None


def extract_game_details(item: ET.Element) -> Dict:
    """Extract structured data from XML item"""

    game_id = item.get('id')
        
    # Basic info
    primary_name = item.find(".//name[@type='primary']")
    year_published = item.find('.//yearpublished')
    description = item.find('.//description')

    # Player counts
    min_players= item.find('.//minplayers')
    max_players= item.find('.//maxplayers')
    # Playing time
    min_playtime= item.find('.//minplaytime')
    max_playtime= item.find('.//maxplaytime')
    playing_time= item.find('.//playingtime')
    # Age
    min_age= item.find('.//minage')

    # Statistics
    stats = item.find('.//statistics/ratings')

    # Links (categories, mechanics, designers, artists, publishers)
    categories = [link.get('value') for link in item.findall(".//link[@type='boardgamecategory']")]
    mechanics = [link.get('value') for link in item.findall(".//link[@type='boardgamemechanic']")]
    families = [link.get('value') for link in item.findall(".//link[@type='boardgamefamily']")]
    designers = [link.get('value') for link in item.findall(".//link[@type='boardgamedesigner']")]
    artists = [link.get('value') for link in item.findall(".//link[@type='boardgameartist']")]
    publishers = [link.get('value') for link in item.findall(".//link[@type='boardgamepublisher']")]

    # Polls
    suggested_players = extract_poll_data(item, 'suggested_numplayers')
    suggested_age = extract_poll_data(item, 'suggested_playerage')
    language_dependence = extract_poll_data(item, 'language_dependence')

    return {
        'game_id': game_id,
        'primary_name': primary_name.get('value') if primary_name is not None else None,
        'year_published': int(year_published.get('value')) if year_published is not None else None,
        'description': description.text if description is not None else None,
        'min_players': int(min_players.get('value')) if min_players is not None else None,
        'max_players': int(max_players.get('value')) if max_players is not None else None,
        'min_playtime': int(min_playtime.get('value')) if min_playtime is not None else None,
        'max_playtime': int(max_playtime.get('value')) if max_playtime is not None else None,
        'playing_time': int(playing_time.get('value')) if playing_time is not None else None,
        'min_age': int(min_age.get('value')) if min_age is not None else None,
        'categories': categories,
        'mechanics': mechanics,
        'families': families,
        'designers': designers,
        'artists': artists,
        'publishers': publishers,
        'statistics': extract_statistics(stats) if stats is not None else {},
        'polls': {
            'suggested_players': suggested_players,
            'suggested_age': suggested_age,
            'language_dependence': language_dependence
        }
    }

def extract_statistics(stats: ET.Element) -> Dict:
    """Extract statistic from ratings element"""
    
    return {
        'users_rated': int(stats.find('usersrated').get('value')) if stats.find('usersrated') is not None else 0,
        'average_rating': float(stats.find('average').get('value')) if stats.find('average') is not None else 0.0,
        'bayes_average_rating': float(stats.find('bayesaverage').get('value')) if stats.find('bayesaverage') is not None else 0.0,
        'stddev': float(stats.find('stddev').get('value')) if stats.find('stddev') is not None else 0.0,
        'owned': int(stats.find('owned').get('value')) if stats.find('owned') is not None else 0,
        'trading': int(stats.find('trading').get('value')) if stats.find('trading') is not None else 0,
        'wanting': int(stats.find('wanting').get('value')) if stats.find('wanting') is not None else 0,
        'wishing': int(stats.find('wishing').get('value')) if stats.find('wishing') is not None else 0,
        'num_comments': int(stats.find('numcomments').get('value')) if stats.find('numcomments') is not None else 0,
        'num_weights': int(stats.find('numweights').get('value')) if stats.find('numweights') is not None else 0,
        'average_weight': float(stats.find('averageweight').get('value')) if stats.find('averageweight') is not None else 0.0
    }

def extract_poll_data(item: ET.Element, poll_name: str) -> Dict:
    """Extract poll data from XML item"""

    poll = item.find(f".//poll[@name='{poll_name}']")
    if poll is None:
        return {}
    
    poll_data = {
        'total_votes': int(poll.get('totalvotes', '0'))
    }

    results = []
    for result_group in poll.findall('.//results'):
        num_players = result_group.get('numplayers')

        for result in result_group.findall('.//result'):
            results.append({
                'num_players': num_players,
                'value': result.get('value'),
                'num_votes': int(result.get('numvotes', '0'))
            })

    poll_data['results'] = results

    return poll_data

def store_raw_data(bucket: str, game_id: str, game_data: Dict):
    """Store raw XML data in S3"""

    # Partition by year for better organization
    year = game_data.get('year_published', 'unknown')
    date = datetime.utcnow().strftime('%Y%m%d')

    s3_key = f"bgg/raw_games/year={year}/date={date}/game_{game_id}.json"

    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=json.dumps(game_data, indent=2),
        ContentType='application/json'
    )

def lambda_handler(event, context):
    """
    Extract game data from BGG API with state tracking

    Input event can be:
    - Single game_id
    - List of game_ids
    - S3 reference to JSON file with game_ids   
    """

    # Get configuration from environment
    BRONZE_BUCKET = os.environ['BRONZE_BUCKET']
    SECRET_NAME = os.environ['SECRET_NAME']
    REGION = os.environ['REGION']

    # Get BGG token from Secrets Manager
    bearer_token = get_secret(SECRET_NAME, REGION)

    # Parse input event
    game_ids = parse_input_event(event)

    results = {
        'processed': 0,
        'failed': 0,
        'skipped': 0,
        'errors': []
    }

    for game_id in game_ids:
        try:
            # Skip if we've already processed this game in this invocation
            if game_id in [r.get('game_id') for r in results.get('processed_ids', [])]:
                logger.info(f"Game {game_id} already processed in this invocation, skipping")
                results['skipped'] += 1
                continue

            # Update state as IN_PROGRESS
            update_game_state(game_id, 'IN_PROGRESS')

            # Rate limiting: Wait before making API call to respect BGG rate limits
            # This ensures we don't burst after skipping multiple games
            time.sleep(3)

            # Fetch game data
            game_data = fetch_game_data(game_id, bearer_token)
            
            logger.info(f"Successfully fetched game {game_id}")

            if game_data:
                # Store raw data in S3
                store_raw_data(BRONZE_BUCKET, game_id, game_data)

                # Update state as COMPLETED
                update_game_state(game_id, 'COMPLETED', game_data=game_data)

                results['processed'] += 1
                if 'processed_ids' not in results:
                    results['processed_ids'] = []
                results['processed_ids'].append({'game_id': game_id})
            else:
                # Update state as FAILED
                update_game_state(game_id, 'FAILED', error='Failed to fetch or parse game data.')
                results['failed'] += 1

        except Exception as e:
            logger.error(f"Error processing game ID {game_id}: {str(e)}")
            results['failed'] += 1
            results['errors'].append({'game_id': game_id, 'error': str(e)})
            update_game_state(game_id, 'FAILED', error=str(e))

    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }