# output
output "instance_public_ip" {
  description = "Public IP of the Airflow EC2 instance"
  value       = aws_instance.airflow.public_ip

}

output "instance_id" {
  description = "ID of the Airflow EC2 instance"
  value       = aws_instance.airflow.id
}

output "ssh_connection_command" {
  description = "SSH command to connect to the Airflow EC2 instance"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_instance.airflow.public_ip}"
}

output "airflow_webserver_url" {
  description = "URL to access the Airflow webserver"
  value       = "http://${aws_instance.airflow.public_ip}:8080"
}