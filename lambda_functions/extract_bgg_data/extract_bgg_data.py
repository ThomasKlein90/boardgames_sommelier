# lambda_functions/extract_bgg_data/extract_bgg_data.py
# VERSION: v1.1.0 - Fixed BGG API endpoint to https://boardgamegeek.com/xmlapi2
import json
import boto3
import os
import requests
import xml
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import logging
from typing import Dict, List, Any
import socket

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Intialize AWS clients
s3_client = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')

def get_secret(secret_name: str, region: str) -> str:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        return secret.get('token', '')
    except Exception as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise

def fetch_game_data(game_id: int, bearer_token: str = None, max_retries: int = 3) -> Dict[str, Any]:
    """
    Fetch game data from BoardGameGeek XML API2 with retry logic.

    Args:
        game_id (int): The BGG ID of the game to fetch.
        bearer_token (str, optional): Bearer token for authentication. Defaults to None.
        max_retries (int): Number of retry attempts for transient errors.

    Returns:
        Dictionary containing parsed game data.
    """
    url = f"https://boardgamegeek.com/xmlapi2/thing?id={game_id}&stats=1"
    
    headers = {
        'User-Agent': 'BoardGames Sommelier/1.0',
        'Accept': 'application/xml',
        'Accept-Encoding': 'gzip, deflate'
    }

    if bearer_token:
        headers['Authorization'] = f'Bearer {bearer_token}'

    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching data for game ID: {game_id} (attempt {attempt + 1}/{max_retries})")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # BGG API rate limiting
            time.sleep(2)

            return parse_game_xml(response.text, game_id)
        
        except (socket.gaierror, socket.timeout) as e:
            # DNS resolution or socket timeout errors - these may be transient
            logger.warning(f"Network error for game ID {game_id} (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                logger.info(f"Retrying after {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to fetch game ID {game_id} after {max_retries} attempts: {str(e)}")
                return None
        
        except requests.RequestException as e:
            logger.error(f"HTTP error while fetching game ID {game_id}: {str(e)}")
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error while fetching game ID {game_id}: {type(e).__name__}: {str(e)}")
            return None
    
def parse_game_xml(xml_content: str, game_id: int) -> Dict[str, Any]:
    """
    Parse BGG XML response into structure dictionary

    Args:
        xml_content: XML string from BGG API
        game_id: Game ID being parsed
    
    Returns:
        Structured dictionary of game data
    """
    try:
        root = ET.fromstring(xml_content)
        item = root.find('item')

        if item is None:
            logger.warning(f'No item found for game {game_id}. XML content: {xml_content[:500]}')
            return None
        
        # Helper function to safely get element text
        def get_text(element, default=''):
            return element.text if element is not None else default
        
        # Helper function to safely get attribute
        def get_attr(element, attr, default=''):
            return element.get(attr, default) if element is not None else default
        
        # Parse basic game information
        game_data = {
            'game_id': game_id,
            'bgg_game_id': int(item.get('id')),
            'extraction_date': datetime.utcnow().isoformat(),

            # Names
            'primary_name': '',
            'alternate_names': [],

            # Basic info
            'year_published': None,
            'description': '',
            'thumbnail': '',
            'image': '',

            # Player counts
            'min_players': None,
            'max_players': None,
            'min_players_best': None,
            'max_players_best': None,

            # Playing time
            'min_playtime': None,
            'max_playtime': None,
            'playing_time': None,

            # Age
            'min_age': None,
            'min_age_rec': None,

            # Poll data
            'suggested_numplayers': {},
            'suggested_playerage': {},
            'language_dependence': {},

            # Designers, Artists, Publishers
            'designers': [],
            'artists': [],
            'publishers': [],

            # Categories, Mechanics, Themes
            'categories': [],
            'mechanics': [],
            'themes': [],

            # Statistics:
            'users_rated': None,
            'average_rating': None,
            'bayes_average': None,
            'stddev': None,
            'median': None,
            'owned': None,
            'trading': None,
            'wanting': None,
            'wishing': None,
            'num_comments': None,
            'num_weights': None,
            'average_weight': None,
            'rank_boardgame': None,
            'rank_strategy': None,
            'rank_family': None,

            # Raw XML for reference
            'raw_xml': xml_content
        }

        # Parse names
        for name in item.findall('name'):
            name_type = name.get('type')
            name_value = name.get('value','')

            if name_type == 'primary':
                game_data['primary_name'] = name_value
            elif name_type == 'alternate':
                game_data['alternate_names'].append(name_value)
        
        # Parse basic info
        year_elem = item.find('yearpublished')
        if year_elem is not None:
            try:
                game_data['year_published'] = int(year_elem.get('value',0))
            except (ValueError, TypeError):
                game_data['year_published'] = None

        desc_elem = item.find('description')
        game_data['description'] = get_text(desc_elem)

        thumb_elem = item.find('thumbnail')
        game_data['thumbnail'] = get_text(thumb_elem)

        image_elem = item.find('image')
        game_data['image'] = get_text(image_elem)

        # Parse player counts
        minplayers = item.find('minplayers')
        if minplayers is not None:
            try:
                game_data['min_players'] = int(minplayers.get('value',0))
            except (ValueError, TypeError):
                pass
            
        maxplayers = item.find('maxplayers')
        if maxplayers is not None:
            try:
                game_data['max_players'] = int(maxplayers.get('value',0))
            except (ValueError, TypeError):
                pass

        # Parse suggested player count poll
        numplayers_poll = item.find(".//poll[@name='suggested_numplayers']")
        if numplayers_poll is not None:
            for results in numplayers_poll.findall('results'):
                num = results.get('numplayers')
                best = 0
                recommended = 0
                not_recommended = 0

                for result in results.findall('result'):
                    value = result.get('value')
                    numvotes = int(result.get('numvotes',0))

                    if value == 'Best':
                        best = numvotes
                    elif value == 'Recommended':
                        recommended = numvotes
                    elif value == 'Not Recommended':
                        not_recommended = numvotes
                
                game_data['suggested_numplayers'][num] = {
                    'best': best,
                    'recommended': recommended,
                    'not_recommended': not_recommended
                }

            # Determine best player count
            if game_data['suggested_numplayers']:
                best_count = max(game_data['suggested_numplayers'].items(), key=lambda x: x[1]['best'])
                if best_count[1]['best'] > 0:
                    try:
                        if '+' not in best_count[0]:
                            game_data['min_players_best'] = int(best_count[0])
                            game_data['max_players_best'] = int(best_count[0])
                    except ValueError:
                        pass

        # Parse playing time
        minplaytime = item.find('minplaytime')
        if minplaytime is not None:
            try:
                game_data['min_playtime'] = int(minplaytime.get('value',0))
            except (ValueError, TypeError):
                pass

        maxplaytime = item.find('maxplaytime')
        if maxplaytime is not None:
            try:
                game_data['max_playtime'] = int(maxplaytime.get('value',0))
            except (ValueError, TypeError):
                pass
            
        playingtime = item.find('playingtime')
        if playingtime is not None:
            try:
                game_data['playing_time'] = int(playingtime.get('value',0))
            except (ValueError, TypeError):
                pass

        # Parse minimum age
        minage = item.find('minage')
        if minage is not None:
            try:
                game_data['min_age'] = int(minage.get('value',0))
            except (ValueError, TypeError):
                pass

        # Parse suggested age poll
        age_poll = item.find(".//poll[@name='suggested_playerage']")
        if age_poll is not None:
            age_votes = {}
            for results in age_poll.findall('results'):
                for result in results.findall('result'):
                    age = result.get('value')
                    numvotes = int(result.get('numvotes',0))
                    age_votes[age] = numvotes

            game_data['suggested_playerage'] = age_votes

            # Determine recommended age
            if age_votes:
                max_age = max(age_votes.items(), key=lambda x: x[1])
                try:
                    game_data['min_age_rec'] = int(max_age[0])
                except (ValueError, TypeError):
                    pass
        
        # Parse language dependence poll
        lang_poll = item.find(".//poll[@name='language_dependence']")
        if lang_poll is not None:
            lang_votes = {}
            for results in lang_poll.findall('results'):
                for result in results.findall('result'):
                    level = result.get('level')
                    value = result.get('value')
                    numvotes = int(result.get('numvotes',0))
                    lang_votes[f"level_{level}"] = {
                        'description': value,
                        'votes': numvotes
                    }
            game_data['language_dependence'] = lang_votes

        
        # Parse categories
        for link in item.findall(".//link[@type='boardgamecategory']"):
            game_data['categories'].append({
                'id': int(link.get('id')),
                'name': link.get('value','')
            })

        # Parse mechanics
        for link in item.findall(".//link[@type='boardgamemechanic']"):
            game_data['mechanics'].append({
                'id': int(link.get('id')),
                'name': link.get('value','')
            })

        # Parse families (to derive themes)
        for link in item.findall(".//link[@type='boardgamefamily']"):
            family_name = link.get('value','')
            # Simple heuristic: families starting with "Theme:" are themes
            if family_name.startswith('Theme:'):
                game_data['themes'].append({
                    'id': int(link.get('id')),
                    'name': family_name.replace('Theme:','').strip()
                })
                
        # Parse designers
        for link in item.findall(".//link[@type='boardgamedesigner']"):
            game_data['designers'].append({
                'id': int(link.get('id')),
                'name': link.get('value','')
            })
            
        # Parse artists
        for link in item.findall(".//link[@type='boardgameartist']"):
            game_data['artists'].append({
                'id': int(link.get('id')),
                'name': link.get('value','')
            })

        # Parse publishers
        for link in item.findall(".//link[@type='boardgamepublisher']"):
            game_data['publishers'].append({
                'id': int(link.get('id')),
                'name': link.get('value','')
            })

        # Parse statistics
        stats = item.find('statistics/ratings')
        if stats is not None:
            try:
                game_data['users_rated'] = int(get_attr(stats.find('usersrated'),'value', 0))
                game_data['average_rating'] = float(get_attr(stats.find('average'),'value', 0))
                game_data['bayes_average'] = float(get_attr(stats.find('bayesaverage'),'value', 0))
                game_data['stddev'] = float(get_attr(stats.find('stddev'),'value', 0))
                game_data['median'] = float(get_attr(stats.find('median'),'value', 0))
                game_data['owned'] = int(get_attr(stats.find('owned'),'value', 0))
                game_data['trading'] = int(get_attr(stats.find('trading'),'value', 0))
                game_data['wanting'] = int(get_attr(stats.find('wanting'),'value', 0))
                game_data['wishing'] = int(get_attr(stats.find('wishing'),'value', 0))
                game_data['num_comments'] = int(get_attr(stats.find('numcomments'),'value', 0))
                game_data['num_weights'] = int(get_attr(stats.find('numweights'),'value', 0))
                game_data['average_weight'] = float(get_attr(stats.find('averageweight'),'value', 0))
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsong statistics: {str(e)}")

            # Parse ranks
            ranks = stats.find('ranks')
            if ranks is not None:
                for rank in ranks.findall('rank'):
                    rank_type = rank.get('type')
                    rank_name = rank.get('name')
                    rank_value = rank.get('value')

                    try:
                        rank_int = int(rank_value) if rank_value and rank_value != 'Not Ranked' else None
                    except ValueError:
                        rank_int = None

                    if rank_name == 'boardgame':
                        game_data['rank_boardgame'] = rank_int
                    elif rank_name == 'strategygames':
                        game_data['rank_strategy'] = rank_int
                    elif rank_name == 'familygames':
                        game_data['rank_family'] = rank_int
                
        return game_data

    except ET.ParseError as e:
        logger.error(f"XML parsing error for game {game_id}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing game {game_id}: {str(e)}")
        return None

def lambda_handler(event, context):
    """
    Lambda handler for extracting BGG data

    Expected event structure:
    {
        "game_ids": [421, 217372,...],
        "batch_name"; "batch_1"         # optional
    }
   
    """
    try:
        # Get configuration from environment
        bronze_bucket = os.environ['BRONZE_BUCKET']
        secret_name = os.environ['SECRET_NAME']
        region = os.environ['REGION']

        # Get BGG token from Secrets Manager
        bearer_token = get_secret(secret_name, region)

        # Parse event
        game_ids = event.get('game_ids',[])
        batch_name = event.get('batch_name', f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")

        if not game_ids:
            logger.error("No game IDs provided")
            return {
                'statusCode': 400,
                'body': json.dumps('No game IDs provided')
            }
        
        logger.info(f"Processing {len(game_ids)} games in batch: {batch_name}")

        # Fetch and parse games
        games_data = []
        failed_ids = []
        extraction_date = datetime.utcnow().strftime('%Y-%m-%d')

        for game_id in game_ids:
            game_data = fetch_game_data(game_id, bearer_token, max_retries=1)

            if game_data:
                games_data.append(game_data)
            else:
                failed_ids.append(game_id)

        # Save to S3 Bronze layer
        if games_data:
            s3_key = f"bgg/raw_games/extraction_date={extraction_date}/{batch_name}.json"

            s3_client.put_object(
                Bucket=bronze_bucket,
                Key=s3_key,
                Body=json.dumps(games_data, indent=2),
                ContentType='application/json'
            )

            logger.info(f"Successfully saved {len(games_data)} games to {s3_key}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {len(games_data)} games',
                'batch_name': batch_name,
                'games_processed': len(games_data),
                'games_failed': len(failed_ids),
                'failed_ids': failed_ids,
                's3_location': f"s3://{bronze_bucket}/bgg/raw_games/extraction_date={extraction_date}/{batch_name}.json"
            })
        }
    
    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
