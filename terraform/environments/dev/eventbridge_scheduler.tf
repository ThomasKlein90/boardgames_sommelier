# EventBridge Scheduler resources to control Airflow EC2 runtime window

resource "aws_iam_role" "eventbridge_scheduler" {
  name = "${var.project_name}_ec2_scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })

  lifecycle {
    ignore_changes = [tags_all]
  }

}

resource "aws_iam_role_policy" "eventbridge_scheduler_ec2" {
  name = "${var.project_name}_ec2_start_stop"
  role = aws_iam_role.eventbridge_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:StartInstances",
          "ec2:StopInstances"
        ]
        Resource = aws_instance.airflow.arn
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.eventbridge_scheduler.arn
      }
    ]
  })

}

resource "aws_scheduler_schedule" "airflow_start" {
  name                         = "${var.project_name}_airflow_start"
  group_name                   = "default"
  schedule_expression          = "rate(3 days)"
  schedule_expression_timezone = "Australia/Sydney"
  start_date                   = "2026-03-18T14:55:00Z"
  state                        = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ec2:startInstances"
    role_arn = aws_iam_role.eventbridge_scheduler.arn
    input = jsonencode({
      InstanceIds = [aws_instance.airflow.id]
    })

    retry_policy {
      maximum_event_age_in_seconds = 86400
      maximum_retry_attempts       = 0
    }
  }
}

resource "aws_scheduler_schedule" "airflow_stop" {
  name                         = "${var.project_name}_airflow_stop"
  group_name                   = "default"
  schedule_expression          = "rate(3 days)"
  schedule_expression_timezone = "Australia/Sydney"
  start_date                   = "2026-03-18T15:40:00Z"
  state                        = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ec2:stopInstances"
    role_arn = aws_iam_role.eventbridge_scheduler.arn
    input = jsonencode({
      InstanceIds = [aws_instance.airflow.id]
    })

    retry_policy {
      maximum_event_age_in_seconds = 86400
      maximum_retry_attempts       = 0
    }
  }
}