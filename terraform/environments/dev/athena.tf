# Athena Configuration for querying BGG data
# Cost: $5 per TB of data scanned (partioning dramatically reduces costs)

# Athena Workgroup = Configure query execution
resource "aws_athena_workgroup" "bgg_pipeline" {
  name = "${local.project_name}-workgroup${local.environment}"

  configuration {
    enforce_workgroup_configuration = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/query-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    # Limit query data scanned to control costs
    bytes_scanned_cutoff_per_query = 100000000 # 100 MB limit pr query
  }

  tags = local.common_tags
}

# Glue Database - Metadata catalog for Athena
resource "aws_glue_catalog_database" "bgg_data" {
  name = "${local.project_name}_bgg_data_${local.environment}"
  description = "BGG data lake database"

  tags = local.common_tags
}

# Glue table - BoardGames (will be created by crawler or manually)
resource "aws_glue_catalog_table" "bgg_boardgames" {
  database_name = aws_glue_catalog_database.bgg_data.name
  name          = "bgg_boardgames"
  description = "BGG boardgame data with partitions"

  table_type = "EXTERNAL_TABLE"

  partition_keys {  # to review
    name = "year"
    type = "string"
  }
  
  partition_keys {  # to review
    name = "month"
    type = "string"
  }
  
  partition_keys {  # to review
    name = "day"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.enriched_data.bucket}/boardgames/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    
    ser_de_info {
      name = "json-serde"
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    # Schema to be defined based on cleaned data structure - this is a placeholder
    columns {
      name = "game_id"
      type = "bigint"
    }
    columns {
      name = "name"
      type = "string"
    }
    columns {
      name = "year_published"
      type = "int"
    }
    # Add additional columns as needed
  }  
}

# Glue Crawler - To automatically discover schema and partitions (optional, costs ~$0.44/DPU-hour)
# Commented out to save costs - can add paritions manually
# resource "aws_glue_crawler" "boardgames" {
#   name         = "${local.project_name}-boardgames-crawler${local.environment}"
#   database_name = aws_glue_catalog_database.bgg_data.name
#   role     = aws_iam_role.glue_crawler_role.arn
#
#  s3_target {
#    path = "s3://${aws_s3_bucket.enriched_data.bucket}/boardgames/"
#  }
#
#   schedule = "cron(0 2 * * ? *)" # Daily at 2AM
# }

# Outputs
output "athena_workgroup_name" {
  value = aws_athena_workgroup.bgg_pipeline.name
  description = "Name of the Athena workgroup"
}

output "glue_database_name" {
  value = aws_glue_catalog_database.bgg_data.name
  description = "Name of the Glue database"
}
