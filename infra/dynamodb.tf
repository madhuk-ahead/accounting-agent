# DynamoDB: sessions (WebSocket) and knowledge (single datasource for agent recall)

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

resource "aws_dynamodb_table" "knowledge" {
  name         = "${local.name_prefix}-knowledge"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = local.common_tags
}
