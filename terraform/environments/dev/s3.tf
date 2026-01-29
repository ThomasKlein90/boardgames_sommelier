# S3 buckets for data lake
# Following the medallion architecture: raw -> cleaned -> enriched

locals {
  project_name = lower(replace("boardgames_sommelier", "_", "-")) # S3 bucket names cannot have underscores
  environment = lower(var.environment) # S3 bucket names must be lowercase

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "Thomas"
  }
}

# Raw data bucket = stores data exactly as received from API
resource "aws_s3_bucket" "bronze" {
  bucket = "${local.project_name}-bronze-${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "Bronze Layer - Raw Data"
      Layer   = "bronze"
    })
}

# Cleaned data bucket = stores data after basic cleaning and validation
resource "aws_s3_bucket" "silver" {
  bucket = "${local.project_name}-silver-${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "Silver Layer - Cleaned Data"
      Layer   = "silver"
    })
}

# Enriched data bucket = stores data after enrichment and transformations, ready for ML/analytics
resource "aws_s3_bucket" "gold" {
  bucket = "${local.project_name}-gold-${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "Gold Layer - Enriched Data"
      Layer   = "gold"
    })
}

# Logs bucket - stores application and access logs
resource "aws_s3_bucket" "logs" {
  bucket = "${local.project_name}-logs-${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      Purpose = "Store application and access logs"
    })
}

# Scripts bucket - stores ETL and utility scripts
resource "aws_s3_bucket" "scripts" {
  bucket = "${local.project_name}-scripts-${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      Purpose = "Store ETL and utility scripts"
    })
}   

resource "aws_s3_bucket" "athena_results" {
  bucket = "${local.project_name}-athena-results-${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      Purpose = "Store Athena query results"
    }
  )
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Versioning = Enable for all buckets except logs and scripts
resource "aws_s3_bucket_versioning" "bronze" {
    bucket = aws_s3_bucket.bronze.id

    versioning_configuration {
      status = "Enabled"
    }
}

resource "aws_s3_bucket_versioning" "silver" {
    bucket = aws_s3_bucket.silver.id

    versioning_configuration {
      status = "Enabled"
    }
}

resource "aws_s3_bucket_versioning" "gold" {
    bucket = aws_s3_bucket.gold.id

    versioning_configuration {
      status = "Enabled"
    }
}

# Encryption = Enable server-side encryption for all buckets
resource "aws_s3_bucket_server_side_encryption_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "silver" {
  bucket = aws_s3_bucket.silver.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "gold" {
  bucket = aws_s3_bucket.gold.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "scripts" {
  bucket = aws_s3_bucket.scripts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


# Block public access for all buckets - essential security best practice
resource "aws_s3_bucket_public_access_block" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "silver" {
  bucket = aws_s3_bucket.silver.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "gold" {
  bucket = aws_s3_bucket.gold.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "scripts" {
  bucket = aws_s3_bucket.scripts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle policies - move old data to cheaper storage (Glacier) after 30 days, delete after 365 days
resource "aws_s3_bucket_lifecycle_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"
    filter {}

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    # Move to Glacier after 180 days (very cheap, retrieval takes hours)
    transition {
        days =  180
        storage_class = "GLACIER"
    }

    # Delete after 365 days (adjust based on retention needs)
    expiration {
      days = 365
    }

    # Clean up old versions
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "silver" {
  bucket = aws_s3_bucket.silver.id

  rule {
    id     = "transition-old-data"
    status = "Enabled"
    filter {}

    transition {
      days          = 90
      storage_class = "INTELLIGENT_TIERING"
    }

    # Keep cleaned data longer than raw data
    expiration {
      days = 730 # 2 years
    }

    noncurrent_version_expiration {
      noncurrent_days = 180
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"
    filter {}

    # Delete logs after 90 days to save costs
    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "delete-old-results"
    status = "Enabled"
    filter {}

    # Delete Athena query results after 30 days
    expiration {
      days = 7 # Query results are temporary
    }
  }
}

# Logging configuration - track access to data buckets
resource "aws_s3_bucket_logging" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/bronze/"
}

resource "aws_s3_bucket_logging" "silver" {
  bucket = aws_s3_bucket.silver.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/silver/"
}

resource "aws_s3_bucket_logging" "gold" {
  bucket = aws_s3_bucket.gold.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/gold/"
}

# Outputs for use in other modules
output "bronze_bucket_name" {
  value = aws_s3_bucket.bronze.id
  description = "Name of the bronze data S3 bucket"
}

output "silver_bucket_name" {
  value = aws_s3_bucket.silver.id
  description = "Name of the silver data S3 bucket"
}

output "gold_bucket_name" {
  value = aws_s3_bucket.gold.id
  description = "Name of the gold data S3 bucket"
}

output "bronze_bucket_arn" {
  value = aws_s3_bucket.bronze.arn
  description = "ARN of the bronze data S3 bucket"
}

output "silver_bucket_arn" {
  value = aws_s3_bucket.silver.arn
  description = "ARN of the silver data S3 bucket"
}

output "gold_bucket_arn" {
  value = aws_s3_bucket.gold.arn
  description = "ARN of the gold data S3 bucket"
}

output "logs_bucket_name" {
  value = aws_s3_bucket.logs.id
  description = "Name of the logs bucket"
}

output "scripts_bucket_name" {
  value = aws_s3_bucket.scripts.id
  description = "Name of the scripts S3 bucket"
}

output "athena_results_bucket" {
  value = aws_s3_bucket.athena_results.bucket
  description = "Name of the Athena query results S3 bucket"
}


# Additional S3 bucket for reference data and mappings
resource "aws_s3_bucket" "reference_data" {
  bucket = "${var.project_name}-reference-data-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-reference-data"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_versioning" "reference_data_versioning" {
    bucket = aws_s3_bucket.reference_data.id

    versioning_configuration {
      status = "Enabled"
    }
}

# Upload initial reference data mapping files (e.g., game categories, mechanics)
resource "aws_s3_object" "category_mapping" {
  bucket = aws_s3_bucket.reference_data.id
  key    = "mappings/category_mapping.json"
  source = "${path.module}/../../data/mappings/category_mapping.json"
  etag   = filemd5("${path.module}/../../data/mappings/category_mapping.json")

  tags = {
    Name = "category-mapping"
  }
}

resource "aws_s3_object" "mechanic_mapping" {
  bucket = aws_s3_bucket.reference_data.id
  key    = "mappings/mechanic_mapping.json"
  source = "${path.module}/../../data/mappings/mechanic_mapping.json"
  etag   = filemd5("${path.module}/../../data/mappings/mechanic_mapping.json") 

  tags = {
    Name = "mechanic-mapping"
  }
}

resource "aws_s3_object" "theme_mapping" {
  bucket = aws_s3_bucket.reference_data.id
  key    = "mappings/theme_mapping.json"
  source = "${path.module}/../../data/mappings/theme_mapping.json"
  etag   = filemd5("${path.module}/../../data/mappings/theme_mapping.json")

  tags = {
    Name = "theme-mapping"
  }
}