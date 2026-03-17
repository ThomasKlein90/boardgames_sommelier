#!/bin/bash
set -euo pipefail
set -x

AIRFLOW_VERSION="2.11.0"
PYTHON_VERSION="3.10"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

rm -rf /home/ubuntu/airflow/venv
python3 -m venv /home/ubuntu/airflow/venv
source /home/ubuntu/airflow/venv/bin/activate

pip install --upgrade pip
pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
pip install apache-airflow-providers-amazon apache-airflow-providers-postgres --constraint "${CONSTRAINT_URL}"
pip install boto3 pandas psycopg2-binary --constraint "${CONSTRAINT_URL}"

export AIRFLOW_HOME=/home/ubuntu/airflow

airflow db init

airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com || true

mkdir -p /home/ubuntu/airflow/dags
chown -R ubuntu:ubuntu /home/ubuntu/airflow
