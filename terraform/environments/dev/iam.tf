# IAM Roles for different pipeline components
# Each component gets only the permissions it needs

# 1. Lambda Execution Role - for data processing functions
resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-lambda-execution-role"

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
  
  tags = var.common_tags
}

# Lambda policy for s3, cloudwatch and secrets manager
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.bronze.arn}/*",
          "${aws_s3_bucket.silver.arn}/*",
          "${aws_s3_bucket.gold.arn}/*",
          aws_s3_bucket.bronze.arn,
          aws_s3_bucket.silver.arn,
          aws_s3_bucket.gold.arn
        ]
      },
      {
        Effect   = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.bgg_token.arn
      },
      {
        Effect   = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action = [
          "glue:GetTable",
          "glue:GetDatabase",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:BatchCreatePartition",
          "glue:CreatePartition",
          "glue:GetPartition",
          "glue:GetPartitions"
        ]
        Resource = "*"
      }
    ]
  })
}

# 2. Airflow EC2 Role - for orchestrating the pipeline
resource "aws_iam_role" "airflow_ec2" {
  name = "${var.project_name}-airflow-ec2-${var.environment}"

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
  
  tags = var.common_tags
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
          aws_s3_bucket.bronze.arn,
          "${aws_s3_bucket.bronze.arn}/*",
          aws_s3_bucket.silver.arn,
          "${aws_s3_bucket.silver.arn}/*",
          aws_s3_bucket.gold.arn,
          "${aws_s3_bucket.gold.arn}/*",
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
          "glue:CreateCrawler",
          "glue:UpdateCrawler",
          "glue:StartCrawler",
          "glue:GetCrawler",
          "glue:GetCrawlerMetrics",
          "glue:ListCrawlers"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.glue_crawler.arn
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
  name = "${var.project_name}-athena-query-${var.environment}"

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
          aws_s3_bucket.gold.arn,
          "${aws_s3_bucket.gold.arn}/*",
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
  name = "${var.project_name}-developer-access-${var.environment}"
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
            aws_s3_bucket.bronze.arn,
            "${aws_s3_bucket.bronze.arn}/*",
            aws_s3_bucket.silver.arn,
            "${aws_s3_bucket.silver.arn}/*",
            aws_s3_bucket.gold.arn,
            "${aws_s3_bucket.gold.arn}/*",
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
  # NOTE: Tags removed because terraform-user lacks iam:TagPolicy permission
  # Tags can be added manually via AWS Console if needed
}

# Glue Crawler Role
resource "aws_iam_role" "glue_crawler" {
  name = "${var.project_name}-glue-crawler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

# Instance Profile for Airflow EC2
resource "aws_iam_instance_profile" "airflow" {
  name = "${var.project_name}-airflow-instance-profile"
  role = aws_iam_role.airflow_ec2.name
}

# Attach AWS managed policy for Glue service role
resource "aws_iam_role_policy_attachment" "glue_service_role_attachment" {
  role       = aws_iam_role.glue_crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Glue S3 Access Policy
resource "aws_iam_role_policy" "glue_s3_policy" {
  name = "${var.project_name}-glue-s3-policy"
  role = aws_iam_role.glue_crawler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.silver.arn}/*",
          "${aws_s3_bucket.gold.arn}/*",
          aws_s3_bucket.silver.arn,
          aws_s3_bucket.gold.arn
        ]
      }
    ]
  })
}

# Secrets Manager for BGG Token
resource "aws_secretsmanager_secret" "bgg_token" {
  name                    = "${var.project_name}-bgg-token"
  description             = "BGG API Bearer Token"
  recovery_window_in_days = 0  # Force immediate deletion when destroyed to avoid "scheduled for deletion" state
  
  tags = var.common_tags

  lifecycle {
    ignore_changes = [policy]
  }
}

resource "aws_secretsmanager_secret_version" "bgg_token" {
  secret_id = aws_secretsmanager_secret.bgg_token.id
  secret_string = jsonencode({
    token = var.bgg_bearer_token
  })
}

# Outputs
output "lambda_execution_role_arn" {
  value = aws_iam_role.lambda_execution.arn
  description = "ARN of the Lambda execution role"
}

output "glue_crawler_role_arn" {
  value = aws_iam_role.glue_crawler.arn
  description = "ARN of the Glue Crawler role"
}

output "airflow_instance_profile_name" {
  value = aws_iam_instance_profile.airflow.name
  description = "Name of the Airflow EC2 Instance profile"
}

output "developer_policy_arn" {
  value = aws_iam_policy.developer_access.arn
  description = "ARN of the developer access policy (attach this to your IAM user)"
}