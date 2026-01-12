# S3 buckets for data lake
# Following the medallion architecture: raw -> cleaned -> enriched

locals {
  project_name = "boardgames_sommelier"
  environment = var.environment # change to "prod" when ready

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "Thomas"
  }
}

# Raw data bucket = stores data exactly as received from API
resource "aws_s3_bucket" "raw_data" {
  bucket = "${local.project_name}-raw${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      DataLayer = "raw"
      Purpose   = "Store raw BGG API responses"
    })
}

# Cleaned data bucket = stores data after basic cleaning and validation
resource "aws_s3_bucket" "cleaned_data" {
  bucket = "${local.project_name}-cleaned${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      DataLayer = "cleaned"
      Purpose   = "Store cleaned and validated BGG data"
    })
}

# Enriched data bucket = stores data after enrichment and transformations, ready for ML/analytics
resource "aws_s3_bucket" "enriched_data" {
  bucket = "${local.project_name}-enriched${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      DataLayer = "enriched"
      Purpose   = "Store enriched BGG data for analytics and ML"
    })
}

# Logs bucket - stores application and access logs
resource "aws_s3_bucket" "logs" {
  bucket = "${local.project_name}-logs${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      Purpose = "Store application and access logs"
    })
}

# Scripts bucket - stores ETL and utility scripts
resource "aws_s3_bucket" "scripts" {
  bucket = "${local.project_name}-scripts${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      Purpose = "Store ETL and utility scripts"
    })
}   

resource "aws_s3_bucket" "athena_results" {
  bucket = "${local.project_name}-athena-results${local.environment}-${data.aws_caller_identity.current.account_id}"

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
resource "aws_s3_bucket_versioning" "raw_data" {
    bucket = aws_s3_bucket.raw_data.id

    versioning_configuration {
      status = "Enabled"
    }
}

resource "aws_s3_bucket_versioning" "cleaned_data" {
    bucket = aws_s3_bucket.cleaned_data.id

    versioning_configuration {
      status = "Enabled"
    }
}

resource "aws_s3_bucket_versioning" "enriched_data" {
    bucket = aws_s3_bucket.enriched_data.id

    versioning_configuration {
      status = "Enabled"
    }
}

# Encryption = Enable server-side encryption for all buckets
resource "aws_s3_bucket_server_side_encryption_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cleaned_data" {
  bucket = aws_s3_bucket.cleaned_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "enriched_data" {
  bucket = aws_s3_bucket.enriched_data.id

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
resource "aws_s3_bucket_public_access_block" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "cleaned_data" {
  bucket = aws_s3_bucket.cleaned_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "enriched_data" {
  bucket = aws_s3_bucket.enriched_data.id

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
resource "aws_s3_bucket_lifecycle_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    id     = "transition-old-data"
    status = "Enabled"

    # Move to Intelligent-Tiering after 30 days (automatically optimizes costs)
    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }

    # Move to Glacier after 90 days (very cheap, retrieval takes hours)
    transition {
        days =  90
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

resource "aws_s3_bucket_lifecycle_configuration" "cleaned_data" {
  bucket = aws_s3_bucket.cleaned_data.id

  rule {
    id     = "transition-old-data"
    status = "Enabled"

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

    # Delete Athena query results after 30 days
    expiration {
      days = 7 # Query results are temporary
    }
  }
}

# Logging configuration - track access to data buckets
resource "aws_s3_bucket_logging" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/raw_data/"
}

resource "aws_s3_bucket_logging" "cleaned_data" {
  bucket = aws_s3_bucket.cleaned_data.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/cleaned_data/"
}

resource "aws_s3_bucket_logging" "enriched_data" {
  bucket = aws_s3_bucket.enriched_data.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/enriched_data/"
}

# Outputs for use in other modules
output "raw_bucket_name" {
  value = aws_s3_bucket.raw_data.id
  description = "Name of the raw data S3 bucket"
}

output "cleaned_bucket_name" {
  value = aws_s3_bucket.cleaned_data.id
  description = "Name of the cleaned data S3 bucket"
}

output "enriched_bucket_name" {
  value = aws_s3_bucket.enriched_data.id
  description = "Name of the enriched data S3 bucket"
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