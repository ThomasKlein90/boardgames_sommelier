# output
output "instance_public_ip" {
  description = "Static Elastic IP of the Airflow EC2 instance"
  value       = aws_eip.airflow.public_ip

}

output "instance_id" {
  description = "ID of the Airflow EC2 instance"
  value       = aws_instance.airflow.id
}

output "ssh_connection_command" {
  description = "SSH command to connect to the Airflow EC2 instance"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.airflow.public_ip}"
}

output "airflow_webserver_url" {
  description = "URL to access the Airflow webserver"
  value       = "http://${aws_eip.airflow.public_ip}:8080"
}

output "eventbridge_scheduler_role_arn" {
  description = "IAM role ARN used by EventBridge Scheduler for EC2 start/stop"
  value       = aws_iam_role.eventbridge_scheduler.arn
}

output "airflow_start_schedule_name" {
  description = "EventBridge Scheduler name that starts Airflow EC2"
  value       = aws_scheduler_schedule.airflow_start.name
}

output "airflow_stop_schedule_name" {
  description = "EventBridge Scheduler name that stops Airflow EC2"
  value       = aws_scheduler_schedule.airflow_stop.name
}