# Cloudwatch Log Groups and Monitoring
# Free tier: 5GB ingestion, 5GB storage per month

# Log group for Airflow DAGs
resource "aws_cloudwatch_log_group" "airflow_dags" {
  name              = "/aws/boardgames_sommelier/airflow/dags"
  retention_in_days = 30 # Adjust based on needs, longer = more cost

  tags = merge(local.common_tags, {
    Component = "Airflow"
  })
}

# Local group for API extraction
resource "aws_cloudwatch_log_group" "api_extraction" {
    name = "/aws/boardgames_sommelier/extraction"
    retention_in_days = 30

  tags = merge(local.common_tags, {
    Component = "Extraction"
  })
}

# Local group for data cleaning
resource "aws_cloudwatch_log_group" "data_cleaning" {
    name = "/aws/boardgames_sommelier/data_cleaning"
    retention_in_days = 30

  tags = merge(local.common_tags, {
    Component = "Cleaning"
  })
}

# Local group for data enrichment
resource "aws_cloudwatch_log_group" "data_enrichment" {
    name = "/aws/boardgames_sommelier/data_enrichment"
    retention_in_days = 30

  tags = merge(local.common_tags, {
    Component = "Enrichment"
  })
}   

# Cloudwatch metric filter - Track API failures
resource "aws_cloudwatch_log_metric_filter" "api_errors" {
  name           = "api-extraction-errors"
  log_group_name = aws_cloudwatch_log_group.api_extraction.name
  pattern        = "[ERROR]"

  metric_transformation {
    name = "APIExtractionErrors"
    namespace = "BGGPipeline"
    value = "1"
  }
}

# Cloudwatch metric filter - Track cleaning features
resource "aws_cloudwatch_log_metric_filter" "cleaning_errors" {
  name           = "data-cleaning-errors"
  log_group_name = aws_cloudwatch_log_group.data_cleaning.name
  pattern        = "[ERROR]"

  metric_transformation {
    name = "DataCleaningErrors"
    namespace = "BGGPipeline"
    value = "1"
  }
}

# Cloudwatch Alarm - Alert on API extraction errors
resource "aws_cloudwatch_metric_alarm" "api_error_alarm" {
  alarm_name          = "bgg-api-extraction-error"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BGGAPIExtractionErrors"
  namespace = "BGGPipeline"
    period              = "300" # 5 minutes
    statistic = "Sum"
    threshold = "5" # Alert if more than 5 errors in 5 minutes
    alarm_description = "This metric monitors BGG API extraction errors"
    alarm_actions = [aws_sns_topic.pipeline_alerts.arn]

    tags = local.common_tags
}

# Cloudwatch Alarm - Alert on Data Cleaning errors
resource "aws_cloudwatch_metric_alarm" "cleaning_error_alarm" {
  alarm_name          = "bgg-data-cleaning-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DataCleaningErrors"
  namespace = "BGGPipeline"
    period              = "300" # 5 minutes
    statistic = "Sum"
    threshold = "10" # Alert if more than 10 errors in 5 minutes
    alarm_description = "This metric monitors data cleaning errors"
    alarm_actions = [aws_sns_topic.pipeline_alerts.arn]

    tags = local.common_tags
}

# Alerts on Lambda errors and duration
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name = "${var.project_name}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "LambdaErrors"
  namespace = "AWS/Lambda"
  period              = "300" # 5 minutes
  statistic = "Sum"
  threshold = "5" # Alert if more than 5 errors in 5 minutes
  alarm_description = "Alert when Lambda functions have errors"
  treat_missing_data = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.extract_bgg_data.function_name
  }

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name = "${var.project_name}-lambda-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace = "AWS/Lambda"
  period              = "300" # 5 minutes
  statistic = "Average"
  threshold = "300000" # Alert if average duration exceeds 5 seconds
  alarm_description = "Alert when Lambda duration is too high"

  dimensions = {
    FunctionName = aws_lambda_function.extract_bgg_data.function_name
  }

  tags = var.common_tags
}



# Cloudwatch Dashboard for monitoring (Free!)
resource "aws_cloudwatch_dashboard" "pipeline_dashboard" {
  dashboard_name = "bgg-pipeline-${local.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            [ "BGGPipeline", "BGGAPIExtractionErrors", { "stat" = "Sum" } ],
            [ ".", "DataCleaningErrors", { "stat"= "Sum" } ]
          ]
          period = 300
          stat = "Sum"
          title = "Pipeline Errors"
          region = var.aws_region
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type = "log"
        properties = {
          query = "SOURCE '${aws_cloudwatch_log_group.api_extraction.name}' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20"
          title = "Recent API Errors"
          region = var.aws_region
        }
      },
      {
        type = "log"
        properties = {
          query = "SOURCE '${aws_cloudwatch_log_group.data_cleaning.name}' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20"
          title = "Recent Data Cleaning Errors"
          region = var.aws_region
        }
      }
    ]
  })
}

# Outputs
output "aws_cloudwatch_log_groups" {
  value = {
    airflow = aws_cloudwatch_log_group.airflow_dags.name
    api_extraction = aws_cloudwatch_log_group.api_extraction.name
    data_cleaning = aws_cloudwatch_log_group.data_cleaning.name
    data_enrichment = aws_cloudwatch_log_group.data_enrichment.name
  }
    description = "Cloudwatch log group names"
}