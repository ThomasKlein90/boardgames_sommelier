# Lambda function for applying category/mechanic/theme mappings to enriched data
# Reads from silver layer and writes to gold layer

locals {
  apply_mappings_zip = "${path.module}/../../../lambda_functions/apply_mappings.zip"
  apply_mappings_hash = fileexists(local.apply_mappings_zip) ? filebase64sha256(local.apply_mappings_zip) : base64sha256("placeholder")
}

# Lambda Function: Apply Mappings - Gold layer enrichment
resource "aws_lambda_function" "apply_mappings" {
  function_name = "${var.project_name}_apply_mappings"
  filename      = local.apply_mappings_zip
  handler       = "apply_mappings.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_execution.arn
  memory_size   = 512
  timeout       = 900 # 15 minutes

  source_code_hash = local.apply_mappings_hash

  environment {
    variables = {
      REFERENCE_BUCKET = aws_s3_bucket.reference_data.id
      SILVER_BUCKET    = aws_s3_bucket.silver.id
      GOLD_BUCKET      = aws_s3_bucket.gold.id
      REGION           = var.aws_region
    }
  }

  tags = var.common_tags
}

# CloudWatch Log Group for Lambda function
resource "aws_cloudwatch_log_group" "apply_mappings_logs" {
  name              = "/aws/lambda/${aws_lambda_function.apply_mappings.function_name}"
  retention_in_days = 30

  tags = var.common_tags
}
