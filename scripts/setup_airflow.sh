#!/bin/bash
set -ex
exec > >(tee /var/log/airflow-setup.log)
exec 2>&1

# Install Python dependencies
apt-get update
apt-get install -y python3-pip python3-venv python3-dev libpq-dev git

# Create Airflow directory
mkdir -p /home/ubuntu/airflow
cd /home/ubuntu/airflow

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Airflow and dependencies
pip install --upgrade pip
pip install apache-airflow==2.7.0
pip install apache-airflow-providers-amazon
pip install apache-airflow-providers-postgres
pip install boto3 pandas psycopg2-binary

# Initialize Airflow
export AIRFLOW_HOME=/home/ubuntu/airflow
airflow db init

# Create admin user
airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com 2>/dev/null || echo "User may already exist"

# Create DAG directory
mkdir -p /home/ubuntu/airflow/dags

# Fix permissions
chown -R ubuntu:ubuntu /home/ubuntu/airflow

# Create systemd service for scheduler
cat > /etc/systemd/system/airflow-scheduler.service <<'EOF'
[Unit]
Description=Airflow Scheduler
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/airflow
Environment="PATH=/home/ubuntu/airflow/venv/bin"
Environment="AIRFLOW_HOME=/home/ubuntu/airflow"
ExecStart=/home/ubuntu/airflow/venv/bin/airflow scheduler
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for webserver
cat > /etc/systemd/system/airflow-webserver.service <<'EOF'
[Unit]
Description=Airflow Webserver
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/airflow
Environment="PATH=/home/ubuntu/airflow/venv/bin"
Environment="AIRFLOW_HOME=/home/ubuntu/airflow"
ExecStart=/home/ubuntu/airflow/venv/bin/airflow webserver -p 8080
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
systemctl daemon-reload
systemctl enable airflow-scheduler.service
systemctl enable airflow-webserver.service
systemctl start airflow-scheduler.service
systemctl start airflow-webserver.service

echo "Airflow installation complete!"
systemctl status airflow-scheduler.service
systemctl status airflow-webserver.service
