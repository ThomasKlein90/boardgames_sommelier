# airflow/dags/bgg_etl_pipeline.py

from airflow import DAG
from airflow.models import Variable
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.amazon.aws.operators.glue_crawler import GlueCrawlerOperator
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from botocore.config import Config
from datetime import datetime, timedelta
import json
import os
import boto3

# Get region from environment or use default
REGION = os.environ.get('AWS_REGION', 'ap-southeast-2')

# Get Airflow Variables (fetched at DAG parse time)
GLUE_CRAWLER_ROLE_ARN = Variable.get('glue_crawler_role_arn', default_var='arn:aws:iam::021406833830:role/boardgames_sommelier-glue-crawler-role')
BRONZE_BUCKET = Variable.get('bronze_bucket_name', default_var='boardgames-sommelier-bronze-dev-021406833830')
SILVER_BUCKET = Variable.get('silver_bucket_name', default_var='boardgames-sommelier-silver-dev-021406833830')
GOLD_BUCKET = Variable.get('gold_bucket_name', default_var='boardgames-sommelier-gold-dev-021406833830')
SILVER_CRAWLER_NAME = Variable.get('silver_crawler_name', default_var='bgg-pipeline-silver-dimensions-crawler')
GOLD_CRAWLER_NAME = Variable.get('gold_crawler_name', default_var='bgg-pipeline-gold-fact-crawler')
GLUE_DATABASE_NAME = Variable.get('glue_database_name', default_var='boardgames_sommelier_bgg_database')
GAME_ID_DISCOVERY_LAMBDA = Variable.get('game_id_discovery_lambda_name', default_var='boardgames_sommelier-game-id-discovery-dev')
APPLY_MAPPINGS_LAMBDA = Variable.get('apply_mappings_lambda_name', default_var='boardgames_sommelier_apply_mappings')
DATA_QUALITY_LAMBDA = Variable.get('data_quality_lambda_name', default_var='boardgames_sommelier-data-quality-dev')

# Default arguments
default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2026, 2, 26, 2, 0, 0),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 5,
    'retry_delay': timedelta(minutes=2),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=15)
}

# Create DAG
dag = DAG(
    'bgg_etl_pipeline',
    default_args=default_args,
    description='ETL pipeline for BoardGameGeek data',
    schedule_interval=timedelta(days=3),  # Run every 3 days
    timezone='Australia/Sydney',
    catchup=False,
    tags=['bgg','boardgames','etl']
)

# Botocore config to handle Lambda throttling with adaptive retries
lambda_botocore_config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'
    }
)

def get_latest_discovered_ids_key(**context):
    """
    Find the latest discovered game IDs file in S3.
    """
    s3_client = boto3.client('s3', region_name=REGION)
    response = s3_client.list_objects_v2(
        Bucket=BRONZE_BUCKET,
        Prefix='game_ids/discovered_'
    )

    contents = response.get('Contents', [])
    if not contents:
        raise ValueError('No discovered game IDs file found in S3.')

    latest = max(contents, key=lambda obj: obj['LastModified'])
    return {
        'bucket': BRONZE_BUCKET,
        's3_key': latest['Key']
    }

# Task 1: Discover game IDs (Lambda)
game_id_discovery_task = LambdaInvokeFunctionOperator(
    task_id='game_id_discovery',
    function_name=GAME_ID_DISCOVERY_LAMBDA,
    payload=json.dumps({}),
    invocation_type='Event',
    region_name=REGION,
    execution_timeout=timedelta(minutes=30),
    dag=dag
)

# Task 2: Wait for discovery output file in bronze bucket
wait_for_game_id_file = S3KeySensor(
    task_id='wait_for_game_id_file',
    bucket_name='{{ var.value.bronze_bucket_name }}',
    bucket_key='game_ids/discovered_*.json',
    wildcard_match=True,
    aws_conn_id='aws_default',
    timeout=600,
    poke_interval=30,
    dag=dag
)

# Task 3: Get latest discovered file key
get_latest_game_id_file = PythonOperator(
    task_id='get_latest_game_id_file',
    python_callable=get_latest_discovered_ids_key,
    dag=dag
)

# Task 4: Extract data from BGG API (Bronze layer)
extract_task = LambdaInvokeFunctionOperator(
    task_id='extract_bgg_data',
    function_name='boardgames_sommelier_extract_bgg_data',
    payload='{{ task_instance.xcom_pull(task_ids="get_latest_game_id_file") | tojson }}',
    invocation_type='Event',  # fire-and-forget; downstream S3 sensor waits for output
    region_name=REGION,
    execution_timeout=timedelta(minutes=30),
    dag=dag
)

# Task 5: Wait for bronze file
wait_for_bronze = S3KeySensor(
    task_id='wait_for_bronze_file',
    bucket_name='{{ var.value.bronze_bucket_name }}',
    bucket_key='bgg/raw_games/year=*/date=*/game_*.json',
    wildcard_match=True,
    aws_conn_id='aws_default',
    timeout=1200,  # Increased to 20 minutes to account for Lambda runtime + DynamoDB checks
    poke_interval=30,
    dag=dag
)

# Task 6: Clean data (Silver layer) - triggered automatically by S3 event
# We just need to wait for it
wait_for_silver = S3KeySensor(
    task_id='wait_for_silver_file',
    bucket_name='{{ var.value.silver_bucket_name }}',
    aws_conn_id='aws_default',
    bucket_key='bgg/dim_game/**/*.parquet',
    wildcard_match=True,
    timeout=900,
    poke_interval=60,
    dag=dag
)

# Task 7: Apply mappings (Gold enrichment) - new Lambda
apply_mappings_task = LambdaInvokeFunctionOperator(
    task_id='apply_mappings',
    function_name=APPLY_MAPPINGS_LAMBDA,
    payload=json.dumps({}),
    invocation_type='RequestResponse',
    botocore_config=lambda_botocore_config,
    retries=5,
    retry_delay=timedelta(minutes=5),
    region_name=REGION,
    execution_timeout=timedelta(minutes=30),
    dag=dag
)

# Task 8: Transform data (Gold layer) - triggered automatically by S3 even
# We just need to wait for it
wait_for_gold = S3KeySensor(
    task_id='wait_for_gold_file',
    aws_conn_id='aws_default',
    bucket_name='{{ var.value.gold_bucket_name }}',
    bucket_key='bgg/br_game_category/**/*.parquet',
    wildcard_match=True,
    timeout=900,
    poke_interval=60,
    dag=dag
)

# Task 9: Run dbt transformations (Gold layer)
dbt_run = BashOperator(
    task_id='dbt_run',
    bash_command='cd /opt/airflow/bgg_analytics && /home/airflow/.local/bin/dbt run --profiles-dir /home/airflow/.dbt',
    dag=dag
)

# Task 10: Run Glue Crawler for Silver layer
crawl_silver = GlueCrawlerOperator(
    task_id='crawl_silver_layer',
    config={
        'Name': SILVER_CRAWLER_NAME,
        'Role': GLUE_CRAWLER_ROLE_ARN,
        'DatabaseName': GLUE_DATABASE_NAME,
        'Targets': {
            'S3Targets': [{'Path': f's3://{SILVER_BUCKET}/bgg/'}]
        }
    },
    region_name=REGION,
    dag=dag
)

# Task 11: Run Glue Crawler for Gold layer
crawl_gold = GlueCrawlerOperator(
    task_id='crawl_gold_layer',
    config={
        'Name': GOLD_CRAWLER_NAME,
        'Role': GLUE_CRAWLER_ROLE_ARN,
        'DatabaseName': GLUE_DATABASE_NAME,
        'Targets': {
            'S3Targets': [{'Path': f's3://{GOLD_BUCKET}/bgg/'}]
        }
    },
    region_name=REGION,
    dag=dag
)

# Task 12: Data quality checks
data_quality_task = LambdaInvokeFunctionOperator(
    task_id='data_quality',
    function_name=DATA_QUALITY_LAMBDA,
    payload=json.dumps({'table_name': 'dim_game'}),
    invocation_type='RequestResponse',
    region_name=REGION,
    execution_timeout=timedelta(minutes=30),
    dag=dag
)

# Define task dependencies
game_id_discovery_task >> wait_for_game_id_file >> get_latest_game_id_file >> extract_task >> wait_for_bronze >> wait_for_silver >> apply_mappings_task >> wait_for_gold >> dbt_run
wait_for_silver >> crawl_silver
dbt_run >> crawl_gold >> data_quality_task