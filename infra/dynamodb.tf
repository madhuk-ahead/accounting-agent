# DynamoDB: sessions (WebSocket) + AP data tables (mock)
# Sessions: unchanged
# AP tables: vendor_master, po_ledger, receipts, invoice_status

resource "aws_dynamodb_table" "sessions" {
  name         = "${local.name_prefix}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "connection_id"
    type = "S"
  }

  global_secondary_index {
    name            = "connection_id-index"
    hash_key        = "connection_id"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.common_tags
}

# vendor_master: remit-to, payment terms, tax IDs, default GL/cost center hints
resource "aws_dynamodb_table" "vendor_master" {
  name         = "${local.name_prefix}-vendor-master"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = local.common_tags
}

# po_ledger: PO number, vendor, line items, amounts, cost center
resource "aws_dynamodb_table" "po_ledger" {
  name         = "${local.name_prefix}-po-ledger"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "po_id"

  attribute {
    name = "po_id"
    type = "S"
  }

  tags = local.common_tags
}

# receipts: received quantities (optional for 3-way match)
resource "aws_dynamodb_table" "receipts" {
  name         = "${local.name_prefix}-receipts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "po_id"
  range_key    = "receipt_id"

  attribute {
    name = "po_id"
    type = "S"
  }

  attribute {
    name = "receipt_id"
    type = "S"
  }

  tags = local.common_tags
}

# invoice_status: state machine + duplicate heuristics
resource "aws_dynamodb_table" "invoice_status" {
  name         = "${local.name_prefix}-invoice-status"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "vendor_id"
  range_key    = "invoice_no"

  attribute {
    name = "vendor_id"
    type = "S"
  }

  attribute {
    name = "invoice_no"
    type = "S"
  }

  tags = local.common_tags
}
