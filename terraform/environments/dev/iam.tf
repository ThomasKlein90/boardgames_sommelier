# IAM Roles for different pipeline components
# Each component gets only the permissions it needs

# 1. Lambda Execution Role - for data processing functions
resource "aws_iam_role" "lambda_execution" {
  name = "${local.project_name}-lambda-execution-${local.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# Lambsa policy - Read from one bucket, write to another, log to CloudWatch
resource "aws_iam_role_policy" "lambda_s3_access" {
  name = "s3-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.raw_data.arn,
          "${aws_s3_bucket.raw_data.arn}/*",
          aws_s3_bucket.cleaned_data.arn,
          "${aws_s3_bucket.cleaned_data.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action = [
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.cleaned_data.arn}/*",
          "${aws_s3_bucket.enriched_data.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# 2. Airflow EC2 Role - for orchestrating the pipeline
resource "aws_iam_role" "airflow_ec2" {
  name = "${local.project_name}-airflow-ec2-${local.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# Airflow policy - Can invoke Lambda, write to s3, and read from s3
resource "aws_iam_role_policy" "airflow_permissions" {
  name = "airflow-permissions"
  role = aws_iam_role.airflow_ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
          "lambda:InvokeFunction",
          "lambda:InvokeAsync"
        ]
        Resource = "*" # to restrict after Lambda functions are created
      },
      {
        Effect   = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.raw_data.arn,
          "${aws_s3_bucket.raw_data.arn}/*",
          aws_s3_bucket.cleaned_data.arn,
          "${aws_s3_bucket.cleaned_data.arn}/*",
          aws_s3_bucket.enriched_data.arn,
          "${aws_s3_bucket.enriched_data.arn}/*",
          aws_s3_bucket.logs.arn,
          "${aws_s3_bucket.logs.arn}/*",
        ]
      },
      {
        Effect   = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.pipeline_alerts.arn
      },
      {
        Effect   = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# 3. Athena Query Role - for analyzing data
resource "aws_iam_role" "athena_query" {
  name = "${local.project_name}-athena-query-${local.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "athena.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# Athena policy - Read-only access to enriched data
resource "aws_iam_role_policy" "athena_s3_access" {
  name = "athena-s3-access"
  role = aws_iam_role.athena_query.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.enriched_data.arn,
          "${aws_s3_bucket.enriched_data.arn}/*",
          aws_s3_bucket.athena_results.arn,
          "${aws_s3_bucket.athena_results.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = [
            "${aws_s3_bucket.athena_results.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions"
        ]
        Resource = "*"
      }
    ]
  })
}

# 4. Personal IAM User Policy (attack to existing user)
# This gives full access for development
resource "aws_iam_policy" "developer_access" {
  name = "${local.project_name}-developer-access-${local.environment}"
  description = "Full access to BGG pipeline resources for development"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
            "s3:*"
        ]
        Resource = [
            aws_s3_bucket.raw_data.arn,
            "${aws_s3_bucket.raw_data.arn}/*",
            aws_s3_bucket.cleaned_data.arn,
            "${aws_s3_bucket.cleaned_data.arn}/*",
            aws_s3_bucket.enriched_data.arn,
            "${aws_s3_bucket.enriched_data.arn}/*",
            aws_s3_bucket.logs.arn,
            "${aws_s3_bucket.logs.arn}/*",
            aws_s3_bucket.scripts.arn,
            "${aws_s3_bucket.scripts.arn}/*",
            aws_s3_bucket.athena_results.arn,
            "${aws_s3_bucket.athena_results.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action = [
            "lambda:*",
            "athena:*",
            "glue:*",
            "sns:*",
            "cloudwatch:*",
            "logs:*"
        ]
        Resource = "*"
      }
    ]
  })
  tags = local.common_tags
}

# Outputs
output "lambda_role_arn" {
  value = aws_iam_role.lambda_execution.arn
  description = "ARN of the Lambda execution role"
}

output "airflow_instance_profile_name" {
  value = aws_iam_instance_profile.airflow.name
  description = "Name of the Airflow EC2 Instance profile"
}

output "developer_policy_arn" {
  value = aws_iam_policy.developer_access.arn
  description = "ARN of the developer access policy (attach this to your IAM user)"
}