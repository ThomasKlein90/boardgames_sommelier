# Athena Configuration for querying BGG data
# Cost: $5 per TB of data scanned (partioning dramatically reduces costs)

# Athena Workgroup = Configure query execution
resource "aws_athena_workgroup" "bgg" {
  name = "${var.project_name}-bgg-workgroup"
  description = "Workgroup for BGG data queries"

  configuration {
    enforce_workgroup_configuration = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/athena-results/" # change to gold bucket?

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    # Limit query data scanned to control costs
    bytes_scanned_cutoff_per_query = 100000000 # 100 MB limit pr query
  }

  tags = var.common_tags
}

# Outputs
output "athena_workgroup_name" {
  value = aws_athena_workgroup.bgg.name
  description = "Name of the Athena workgroup"
}

