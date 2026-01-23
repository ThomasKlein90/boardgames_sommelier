# airflow/dags/bgg_etl_pipeline.py

from airflow import DAG
from airflow.models import Variable
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.amazon.aws.operators.glue_crawler import GlueCrawlerOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import json
import os

# Get region from environment or use default
REGION = os.environ.get('AWS_REGION', 'ap-southeast-2')

# Get Airflow Variables (fetched at DAG parse time)
GLUE_CRAWLER_ROLE_ARN = Variable.get('glue_crawler_role_arn', default_var='arn:aws:iam::021406833830:role/boardgames_sommelier-glue-crawler-role')
SILVER_BUCKET = Variable.get('silver_bucket_name', default_var='boardgames-sommelier-silver-dev-021406833830')
GOLD_BUCKET = Variable.get('gold_bucket_name', default_var='boardgames-sommelier-gold-dev-021406833830')
SILVER_CRAWLER_NAME = Variable.get('silver_crawler_name', default_var='bgg-pipeline-silver-dimensions-crawler')
GOLD_CRAWLER_NAME = Variable.get('gold_crawler_name', default_var='bgg-pipeline-gold-fact-crawler')
GLUE_DATABASE_NAME = Variable.get('glue_database_name', default_var='boardgames_sommelier_bgg_database')

# Default arguments
default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2026,1,1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries':2,
    'retry_delay': timedelta(minutes=5)
}

# Create DAG
dag = DAG(
    'bgg_etl_pipeline',
    default_args=default_args,
    description='ETL pipeline for BoardGameGeek data',
    schedule_interval='@daily', # Run daily
    catchup=False,
    tags=['bgg','boardgames','etl']
)

def generate_game_ids(**context):
    """
    Generate list of game IDs to process
    In production, this would query BGG or use a more sophisticated method
    """
    # For demo: process games 1-100
    # In production: query BGG rankings, use incremental loading,etc.
    execution_date = context['execution_date']

    # Example: process 50 games per day
    start_id = 1
    end_id = 50

    game_ids = list(range(start_id, end_id+1))

    return {
        'game_ids': game_ids,
        'batch_name': f"batch_{execution_date.strftime('%Y%m%d')}"
    }

# Task 1: Generate game IDs to process
generate_ids_task = PythonOperator(
    task_id='generate_game_ids',
    python_callable=generate_game_ids,
    dag=dag
)

# Task 2: Extract data from BGG API (Bronze layer)
extract_task = LambdaInvokeFunctionOperator(
    task_id='extract_bgg_data',
    function_name='boardgames_sommelier_extract_bgg_data',
    payload='{{ task_instance.xcom_pull(task_ids="generate_game_ids") | tojson }}',
    invocation_type='Event',  # fire-and-forget; downstream S3 sensor waits for output
    region_name=REGION,
    execution_timeout=timedelta(minutes=30),
    dag=dag
)

# Task 3: Wait for bronze file
wait_for_bronze = S3KeySensor(
    task_id='wait_for_bronze_file',
    bucket_name='{{ var.value.bronze_bucket_name }}',
    bucket_key='bgg/raw_games/extraction_date={{ ds }}/*.json',
    wildcard_match=True,
    aws_conn_id='aws_default',
    timeout=600,
    poke_interval=30,
    dag=dag
)

# Task 4: Clean data (Silver layer) - triggered automatically by S3 event
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

# Task 5: Transform data (Gold layer) - triggered automatically by S3 even
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

# Task 6: Run Glue Crawler for Silver layer
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

# Task 7: Run Glue Crawler for Gold layer
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

# Define task dependencies
generate_ids_task >> extract_task >> wait_for_bronze >> wait_for_silver >> wait_for_gold
wait_for_silver >> crawl_silver
wait_for_gold >> crawl_gold