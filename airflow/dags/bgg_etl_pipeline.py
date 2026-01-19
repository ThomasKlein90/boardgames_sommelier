# airflow/dags/bgg_etl_pipeline.py

from airflow import DAG
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.providers.amazon.aws.operators.glue_crawler import GlueCrawlerOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import json

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
    function_name='bgg-pipeline-extract-bgg-data',
    payload=json.dumps({
        'game_ids': "{{ task_instance.xcom_pull(task_ids='generate_game_ids')['game_ids'] }}",
        'batch_name': "{{ task_instance.xcom_pull(task_ids='generate_game_ids')['batch_name'] }}"
    }),
    aws_conn_id='aws_default',
    dag=dag
)

# Task 3: Wait for bronze file
wait_for_bronze = S3KeySensor(
    task_id='wait_for_bronze_file',
    bucket_name='{{ var.value.bronze_bucket_name }}',
    bucket_key='bgg/raw_games/extraction_date={{ ds }}/*.json',
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
    bucket_key='bgg/dim_game/**/*.parquet',
    aws_conn_id='aws_default',
    timeout=900,
    poke_interval=60,
    dag=dag
)

# Task 5: Transform data (Gold layer) - triggered automatically by S3 even
# We just need to wait for it
wait_for_gold = S3KeySensor(
    task_id='wait_for_gold_file',
    bucket_name='{{ var.value.gold_bucket_name }}',
    bucket_key='bgg/br_game_category/**/*.parquet',
    aws_conn_id='aws_default',
    timeout=900,
    poke_interval=60,
    dag=dag
)

# Task 6: Run Glue Crawler for Silver layer
crawl_silver = GlueCrawlerOperator(
    task_id='crawl_silver_layer',
    crawler_name='bgg-pipeline-silver-dimensions-crawler',
    aws_conn_id='aws_default',
    dag=dag
)

# Task 7: Run Glue Crawler for Gold layer
crawl_gold = GlueCrawlerOperator(
    task_id='crawl_gold_layer',
    crawler_name='bgg-pipeline-gold-fact-crawler',
    aws_conn_id='aws_default',
    dag=dag
)

# Define task dependencies
generate_ids_task >> extract_task >> wait_for_bronze >> wait_for_silver >> wait_for_gold
wait_for_silver >> crawl_silver
wait_for_gold >> crawl_gold