# S3 bucket for AP Invoice Triage: invoice-inbox with prefixes
# invoices/ - uploaded invoices
# policies/ - AP policy docs (match rules, approval matrix, exception SOP)
# outputs/ - generated artifacts (ERP import packet, exception summaries)

resource "aws_s3_bucket" "invoice_inbox" {
  bucket = "${local.name_prefix}-invoice-inbox-${local.account_id}"

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "invoice_inbox" {
  bucket = aws_s3_bucket.invoice_inbox.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_public_access_block" "invoice_inbox" {
  bucket = aws_s3_bucket.invoice_inbox.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
