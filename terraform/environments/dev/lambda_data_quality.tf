# Data Quality Lambda Function
locals {
  data_quality_zip  = "${path.module}/../../../lambda_functions/data_quality.zip"
  data_quality_hash = fileexists(local.data_quality_zip) ? filebase64sha256(local.data_quality_zip) : base64sha256("placeholder")
}

resource "aws_lambda_function" "data_quality" {
    filename = local.data_quality_zip
    function_name = "${var.project_name}-data-quality-${var.environment}"
    role = aws_iam_role.lambda_execution.arn
    handler = "data_quality.lambda_handler"
    source_code_hash = local.data_quality_hash
    runtime = "python3.11"
    timeout = 900
    memory_size = 1024

    environment {
      variables = {
        GLUE_DATABASE = aws_glue_catalog_database.bgg.name
        DQ_METRICS_TABLE = aws_dynamodb_table.data_quality_metrics.name
        ATHENA_OUTPUT_LOCATION = "s3://${aws_s3_bucket.athena_results.id}/"
        ATHENA_WORKGROUP = aws_athena_workgroup.bgg.name
        SNS_TOPIC_ARN = aws_sns_topic.dq_alerts.arn
      }
    }

    tags = {
        Name = "${var.project_name}-data-quality"
        Environment = var.environment
    }
}

# SNS Topic for Data Quality Alerts
resource "aws_sns_topic" "dq_alerts" {
    name = "${var.project_name}-dq-alerts-${var.environment}"

    tags = {
        Name = "${var.project_name}-dq-alerts"
        Environment = var.environment
    }
}

resource "aws_sns_topic_subscription" "dq_email" {
    topic_arn = aws_sns_topic.dq_alerts.arn
    protocol = "email"
    endpoint = var.alert_email
}

# Cloudwatch Log Group
resource "aws_cloudwatch_log_group" "data_quality_logs" {
    name = "/aws/lambda/${aws_lambda_function.data_quality.function_name}"
    retention_in_days = 30

    tags = {
        Name = "${var.project_name}-data-quality-logs"
        Environment = var.environment
    }
}