# SNS topic for pipeline alerts
# Free tier: first 1,000 email notifications per month are free
# After that: 2$ per 100,000 email notifications

resource "aws_sns_topic" "pipeline_alerts" {
  name = "${local.project_name}-alerts-${local.environment}"
  
  tags = merge(local.common_tags, {
    Purpose = "Pipeline errors and status notifications"
  })
}

# Email subscription
resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# SNS Topic Policy to allow publishing from CloudWatch
resource "aws_sns_topic_policy" "pipeline_alerts_policy" {
  arn    = aws_sns_topic.pipeline_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudWatchPublish"
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action = "SNS:Publish"
        Resource = aws_sns_topic.pipeline_alerts.arn
      },
      {
        Sid    = "AllowLambdaPublish"
        Effect = "Allow"
        Principal = {
            Service = "lambda.amazonaws.com"
        }
        Action = "SNS:Publish"
        Resource = aws_sns_topic.pipeline_alerts.arn
      }
    ]
  })
}

# Output the SNS topic ARN
output "sns_topic_arn" {
    description = "ARN of the SNS topic for pipeline alerts"
    value       = aws_sns_topic.pipeline_alerts.arn
}