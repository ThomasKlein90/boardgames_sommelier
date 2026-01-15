# Glue Database - Metadata catalog for Athena
resource "aws_glue_catalog_database" "bgg" {
  name = "${var.project_name}_bgg_database"
  description = "BGG daboardgames data warehouse"

  tags = var.common_tags
}

# Glue Crawlers for Silver layer
resource "aws_glue_crawler" "silver_dimensions" {
  name         = "${var.project_name}_silver_dimensions_crawler"
  database_name = aws_glue_catalog_database.bgg.name
  role     = aws_iam_role.glue_crawler.arn

  s3_target {
    path = "s3://${aws_s3_bucket.silver.id}/bgg/dim_game/"
  }

  s3_target {
    path = "s3://${aws_s3_bucker.silver.id/bgg/dim_category}"
  }

  s3_target {
    path = "s3://${aws_s3_bucker.silver.id/bgg/dim_mechanic}"
  }
  
  s3_target {
    path = "s3://${aws_s3_bucker.silver.id/bgg/dim_theme}"
  }
  
  s3_target {
    path = "s3://${aws_s3_bucker.silver.id/bgg/dim_publisher}"
  }
  
  s3_target {
    path = "s3://${aws_s3_bucker.silver.id/bgg/dim_artist}"
  }

  configuration = jsonencode({
    "Version" = 1.0,
    Grouping = {
        "TableGroupingPolicy" = "CombineCompatibleSchemas"
    }
  })

  schedule = "cron(0 2 * * ? *)" # Daily at 2AM UTC

  tags = var.common_tags
}

# Glue Crawlers for Gold layer
resource "aws_glue_crawler" "gold_facts" {
  name         = "${var.project_name}_gold_facts_crawler"
  database_name = aws_glue_catalog_database.bgg.name
  role     = aws_iam_role.glue_crawler.arn

  s3_target {
    path = "s3://${aws_s3_bucket.gold.id}/bgg/br_game_category/"
  }

  s3_target {
    path = "s3://${aws_s3_bucket.gold.id}/bgg/br_game_mechanic/"
  }
  
    s3_target {
        path = "s3://${aws_s3_bucket.gold.id}/bgg/br_game_theme/"
    }

    s3_target {
        path = "s3://${aws_s3_bucket.gold.id}/bgg/br_game_publisher/"
    }

    s3_target {
        path = "s3://${aws_s3_bucket.gold.id}/bgg/br_game_artist/"
    }

    s3_target {
      path = "s3://${aws_s3_bucket_gold.id}/bgg/fct_user_rating"
    }

  configuration = jsonencode({
    "Version" = 1.0,
    Grouping = {
        "TableGroupingPolicy" = "CombineCompatibleSchemas"
    }
  })

  schedule = "cron(0 3 * * ? *)" # Daily at 3AM UTC

  tags = var.common_tags
  
}

output "glue_database_name" {
  value = aws_glue_catalog_database.bgg.name
  description = "Name of the Glue database"
}
