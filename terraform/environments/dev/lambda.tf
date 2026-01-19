locals {
  dependencies_zip     = "${path.root}/../../lambda_layers/dependencies.zip"
  extract_zip          = "${path.root}/../../lambda_functions/extract_bgg_data.zip"
  clean_zip            = "${path.root}/../../lambda_functions/clean_bgg_data.zip"
  transform_zip        = "${path.root}/../../lambda_functions/transform_bgg_data.zip"
  
  # Generate hash only if file exists, otherwise use empty string
  dependencies_hash    = fileexists(local.dependencies_zip) ? filebase64sha256(local.dependencies_zip) : base64sha256("placeholder")
  extract_hash         = fileexists(local.extract_zip) ? filebase64sha256(local.extract_zip) : base64sha256("placeholder")
  clean_hash           = fileexists(local.clean_zip) ? filebase64sha256(local.clean_zip) : base64sha256("placeholder")
  transform_hash       = fileexists(local.transform_zip) ? filebase64sha256(local.transform_zip) : base64sha256("placeholder")
}

# Lambda Layer for dependencies (requests, boto3, etc.)
resource "aws_lambda_layer_version" "dependencies" {
  filename         = local.dependencies_zip
  layer_name       = "${var.project_name}_dependencies"

  compatible_runtimes = ["python3.11"]
  source_code_hash = local.dependencies_hash
}

# Lambda Function: Bronze - Extract BGG Data
resource "aws_lambda_function" "extract_bgg_data" {
  function_name = "${var.project_name}_extract_bgg_data"
  filename      = local.extract_zip
  handler       = "extract_bgg_data.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_execution.arn
  memory_size   = 512
  timeout       = 900 # 15 minutes

  source_code_hash = local.extract_hash

  layers = [
    aws_lambda_layer_version.dependencies.arn
  ]

  environment {
    variables = {
      BRONZE_BUCKET = aws_s3_bucket.bronze.id
      SECRET_NAME = aws_secretsmanager_secret.bgg_token.name
      REGION = var.aws_region
    }
  }
  tags = var.common_tags
}

# Lambda Function: Silver - Clean and validate BGG Data
resource "aws_lambda_function" "clean_bgg_data" {
  function_name = "${var.project_name}_clean_bgg_data"
  filename      = local.clean_zip
  handler       = "clean_bgg_data.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_execution.arn
  memory_size   = 1024
  timeout       = 900 # 15 minutes

  source_code_hash = local.clean_hash

  layers = [
    aws_lambda_layer_version.dependencies.arn
  ]

  environment {
    variables = {
      BRONZE_BUCKET = aws_s3_bucket.bronze.id
      SILVER_BUCKET = aws_s3_bucket.silver.id
      REGION = var.aws_region
    }
  }
  tags = var.common_tags
}

# Lambda Function: Gold - Transform to star schema
resource "aws_lambda_function" "transform_bgg_data" {
  function_name = "${var.project_name}_transform_bgg_data"
  filename      = local.transform_zip
  handler       = "transform_bgg_data.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_execution.arn
  memory_size   = 2048
  timeout       = 900 # 15 minutes

  source_code_hash = local.transform_hash

  layers = [
    aws_lambda_layer_version.dependencies.arn
  ]

  environment {
    variables = {
      SILVER_BUCKET = aws_s3_bucket.silver.id
      GOLD_BUCKET   = aws_s3_bucket.gold.id
      REGION        = var.aws_region
    }
  }
  tags = var.common_tags
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "extract_bgg_data" {
  name = "/aws/lambda/${aws_lambda_function.extract_bgg_data.function_name}"
  retention_in_days = 14

  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "clean_bgg_data" {
  name = "/aws/lambda/${aws_lambda_function.clean_bgg_data.function_name}"
  retention_in_days = 14

  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "transform_bgg_data" {
  name = "/aws/lambda/${aws_lambda_function.transform_bgg_data.function_name}"
  retention_in_days = 14

  tags = var.common_tags
}

# S3 Event Notification to trigger clean_bgg_data Lambda
resource "aws_s3_bucket_notification" "bronze_trigger" {
  bucket = aws_s3_bucket.bronze.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.clean_bgg_data.arn
    events = ["s3:ObjectCreated:*"]
    filter_prefix = "bgg/raw_games/"
    filter_suffix = ".json"
  }

  depends_on = [ aws_lambda_permission.allow_bronze_bucket ]
}

# Lambda Permission for S3 to invoke clean_bgg_data
resource "aws_lambda_permission" "allow_bronze_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.clean_bgg_data.arn
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.bronze.arn
}

# S3 Event Notification to trigger transform_bgg_data Lambda
resource "aws_s3_bucket_notification" "silver_trigger" {
  bucket = aws_s3_bucket.silver.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.transform_bgg_data.arn
    events = ["s3:ObjectCreated:*"]
    filter_prefix = "bgg/dim_game/"
    filter_suffix = ".parquet"
  }

  depends_on = [ aws_lambda_permission.allow_silver_bucket ]
}

resource "aws_lambda_permission" "allow_silver_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.transform_bgg_data.arn
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.silver.arn
}

# Outputs
output "extract_lambda_arn" {
  value = aws_lambda_function.extract_bgg_data.arn
}

output "clean_lambda_arn" {
  value = aws_lambda_function.clean_bgg_data.arn
}

output "transform_lambda_arn" {
  value = aws_lambda_function.transform_bgg_data.arn
}