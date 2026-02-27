# S3 bucket for press-kit documents and generated press release exports

resource "aws_s3_bucket" "press_kit" {
  bucket = "${local.name_prefix}-press-kit-${local.account_id}"

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "press_kit" {
  bucket = aws_s3_bucket.press_kit.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_public_access_block" "press_kit" {
  bucket = aws_s3_bucket.press_kit.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
