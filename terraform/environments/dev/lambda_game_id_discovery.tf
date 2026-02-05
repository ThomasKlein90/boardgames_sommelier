# Lambda function for game ID discovery
locals {
  game_id_discovery_zip = "${path.module}/../../../lambda_functions/lambda_game_id_discovery.zip"
  game_id_discovery_hash = fileexists(local.game_id_discovery_zip) ? filebase64sha256(local.game_id_discovery_zip) : base64sha256("placeholder")
}

resource "aws_lambda_function" "lambda_game_id_discovery" {
  filename      = local.game_id_discovery_zip
  function_name = "${var.project_name}-game-id-discovery-${var.environment}"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "game_id_discovery.lambda_handler"
  runtime       = "python3.11"
  source_code_hash = local.game_id_discovery_hash
  timeout = 900 # 15 minutes
  memory_size = 512

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      BGG_SECRET_NAME  = aws_secretsmanager_secret.bgg_token.name
      RAW_BUCKET_NAME  = aws_s3_bucket.bronze.id
      STATE_TABLE_NAME = aws_dynamodb_table.bgg_api_state.name
      SCAN_RANGE_SIZE  = "1000"
      SCAN_BATCH_SIZE  = "20"
      REFRESH_DAYS     = "30"
      REFRESH_LIMIT    = "100"
      HOT_LIMIT        = "50"
      NEW_IDS_LIMIT    = "1000"
    }
  }

  tags = {
    Environment = "dev"
    Name     = "${var.project_name}-game-id-discovery"
  }
}

# CloudWatch Log Group for Lambda function
resource "aws_cloudwatch_log_group" "game_id_discovery_logs" {
  name              = "/aws/lambda/${aws_lambda_function.lambda_game_id_discovery.function_name}"
  retention_in_days = 30

  tags = local.common_tags
}
