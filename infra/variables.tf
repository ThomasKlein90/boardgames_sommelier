# input
variable "region"{
    description = "region for aws services"
    type = string
    default = "ap-southeast-2"
}

variable "airflow_server_name" {
    description = "name of the server running airflow"
    type = string
}

variable "project"{
    description = "name of the project"
    type = string
}

variable "env" {
    description = "name of the deployment environment (eg. dev, staging, prod)"
    type = string
}

variable "allowed_cidr" { 
    type = string 
    default = "YOUR.IP.ADDR.0/32" 
    }

variable "ec2_key_name" {
    description = "Key name of the Key Pair to use for the instance; which can be managed using the aws_key_pair resource."
    type = string 
    }

variable "raw_bucket" {
    description = "name of the s3 bucket for raw data"
    type = string
}

variable "staged_bucket" {
    description = "name of the s3 bucket for staged data"
    type = string
}

variable "logs_bucket" {
    description = "name of the s3 bucket for cloudwatch logs"
    type = string
}
