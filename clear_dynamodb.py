import boto3
import time

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
table = dynamodb.Table('boardgames_sommelier-bgg-api-state-dev')

deleted_count = 0
try:
    response = table.scan()
    items = response['Items']
    total = len(items)
    
    print(f'Found {total} items to delete...')
    
    # Use batch write for efficiency
    with table.batch_writer() as batch:
        for i, item in enumerate(items, 1):
            batch.delete_item(Key={
                'game_id': item['game_id'],
                'last_updated': item['last_updated']
            })
            deleted_count += 1
            if i % 100 == 0:
                print(f'Deleted {i}/{total} items...')
    
    print(f'Successfully deleted {deleted_count} items!')
    
except Exception as e:
    print(f'Error after deleting {deleted_count} items: {e}')
    print('You may need to run the script again to delete remaining items.')
