# DynamoDB table to track processed games and API state
resource "aws_dynamodb_table" "bgg_api_state" {
  name           = "${var.project_name}-bgg-api-state-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "game_id"
  range_key      = "last_updated"

  attribute {
    name = "game_id"
    type = "S"
  }

  attribute {
    name = "last_updated"
    type = "S"
  }

  attribute {
    name = "processing_status"
    type = "S"
  }

  global_secondary_index {
    name = "StatusIndex"
    hash_key = "processing_status"
    range_key = "last_updated"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name = "${var.project_name}-bgg-api-state"
    Environment = "${var.environment}"
    ManagedBy = "Terraform"
  }
}

# DynamoDB table for data quality metrics
resource "aws_dynamodb_table" "data_quality_metrics" {
    name = "${var.project_name}-dq-metrics-${var.environment}"
    billing_mode = "PAY_PER_REQUEST"
    hash_key = "check_id"
    range_key = "timestamp"

    attribute {
      name = "check_id"
      type = "S"
    }

    attribute {
      name = "timestamp"
      type = "S"
    }

    attribute {
      name = "table_name"
      type = "S"
    }

    global_secondary_index {
      name = "TableIndex"
      hash_key = "table_name"
      range_key = "timestamp"
      projection_type = "ALL"
    }

    tags = {
      Name = "${var.project_name}-dq-metrics"
      Environment = "${var.environment}"
      ManagedBy = "Terraform"
    }
}
