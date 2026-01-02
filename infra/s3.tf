resource "aws_s3_bucket" "raw"   { 
    bucket = var.raw_bucket  
}

resource "aws_s3_bucket" "staged"{
    bucket = var.staged_bucket 
}

resource "aws_s3_bucket" "logs"  { 
    bucket = var.logs_bucket 
}

resource "aws_s3_bucket_versioning" "raw"   { 
    bucket = aws_s3_bucket.raw.id    
    versioning_configuration { 
        status = "Enabled" 
    } 
}

resource "aws_s3_bucket_versioning" "stg"   { 
    bucket = aws_s3_bucket.staged.id 
    versioning_configuration { 
        status = "Enabled" 
    } 
}

resource "aws_s3_bucket_versioning" "logs"  { 
    bucket = aws_s3_bucket.logs.id   
    versioning_configuration { 
        status = "Enabled" 
    } 
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw"  { 
    bucket = aws_s3_bucket.raw.id  
    rule { 
        apply_server_side_encryption_by_default { 
            sse_algorithm = "AES256" 
        } 
    } 
}

resource "aws_s3_bucket_server_side_encryption_configuration" "stg"  { 
    bucket = aws_s3_bucket.staged.id 
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

resource "aws_s3_bucket_public_access_block" "raw"  { 
    bucket = aws_s3_bucket.raw.id  
    block_public_acls=true 
    block_public_policy=true 
    ignore_public_acls=true 
    restrict_public_buckets=true 
}

resource "aws_s3_bucket_public_access_block" "stg"  { 
    bucket = aws_s3_bucket.staged.id 
    block_public_acls=true 
    block_public_policy=true 
    ignore_public_acls=true 
    restrict_public_buckets=true 
}

resource "aws_s3_bucket_public_access_block" "logs" { 
    bucket = aws_s3_bucket.logs.id 
    block_public_acls=true 
    block_public_policy=true 
    ignore_public_acls=true 
    restrict_public_buckets=true 
}