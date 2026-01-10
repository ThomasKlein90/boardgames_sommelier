# input
variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "ap-southeast-2"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "m7i-flex.large" # t3.small better for airflow
}

variable "project_name" {
  description = "name of the project"
  type        = string
  default     = "boardgames_sommelier"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "my_ip" {
  description = "Your IP address for SSH access (CIDR notation)"
  type        = string
  # We'll set this when running terraform
}

variable "bgg_bearer_token" {
  description = "BGG API Bearer Token"
  type        = string
  # defined in terraform.tfvars
}

variable "alert_email" {
  description = "Email address for pipeline alerts"
  type        = string
  # defined in terraform.tfvars
}