# Lambda: WebSocket connect, disconnect, and chat (default route)

locals {
  lambda_otel_env = var.otel_endpoint != "" ? merge(
    {
      ENVIRONMENT                 = var.environment
      OTEL_SERVICE_NAME           = "${var.project_name}-${var.environment}"
      OTEL_EXPORTER_OTLP_PROTOCOL = "http/protobuf"
      OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint
    },
    var.grafana_otel_secret_name != "" ? { GRAFANA_OTEL_SECRET_NAME = var.grafana_otel_secret_name } : {}
  ) : {}
}

resource "aws_s3_object" "connect_lambda" {
  bucket = aws_s3_bucket.invoice_inbox.id
  key    = "lambda-deployments/connect_lambda.zip"
  source = "${path.module}/../dist/connect_lambda.zip"
  etag   = filemd5("${path.module}/../dist/connect_lambda.zip")
}

resource "aws_lambda_function" "connect" {
  s3_bucket        = aws_s3_object.connect_lambda.bucket
  s3_key           = aws_s3_object.connect_lambda.key
  source_code_hash = filebase64sha256("${path.module}/../dist/connect_lambda.zip")
  function_name = "${local.name_prefix}-connect"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "connect.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  environment {
    variables = merge(
      { DYNAMODB_SESSIONS_TABLE = aws_dynamodb_table.sessions.name },
      local.lambda_otel_env,
    )
  }

  tags = local.common_tags
}

resource "aws_s3_object" "disconnect_lambda" {
  bucket = aws_s3_bucket.invoice_inbox.id
  key    = "lambda-deployments/disconnect_lambda.zip"
  source = "${path.module}/../dist/disconnect_lambda.zip"
  etag   = filemd5("${path.module}/../dist/disconnect_lambda.zip")
}

resource "aws_lambda_function" "disconnect" {
  s3_bucket        = aws_s3_object.disconnect_lambda.bucket
  s3_key           = aws_s3_object.disconnect_lambda.key
  source_code_hash = filebase64sha256("${path.module}/../dist/disconnect_lambda.zip")
  function_name = "${local.name_prefix}-disconnect"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "disconnect.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  environment {
    variables = {
      DYNAMODB_SESSIONS_TABLE = aws_dynamodb_table.sessions.name
    }
  }

  tags = local.common_tags
}

# Chat Lambda zip exceeds 50MB; deploy via S3
resource "aws_s3_object" "chat_lambda" {
  bucket = aws_s3_bucket.invoice_inbox.id
  key    = "lambda-deployments/chat_lambda.zip"
  source = "${path.module}/../dist/chat_lambda.zip"
  etag   = filemd5("${path.module}/../dist/chat_lambda.zip")
}

resource "aws_lambda_function" "chat" {
  s3_bucket        = aws_s3_object.chat_lambda.bucket
  s3_key           = aws_s3_object.chat_lambda.key
  source_code_hash = filebase64sha256("${path.module}/../dist/chat_lambda.zip")
  function_name    = "${local.name_prefix}-chat"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "chat.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  layers = []

  environment {
    variables = merge(
      {
        DYNAMODB_SESSIONS_TABLE       = aws_dynamodb_table.sessions.name
        DYNAMODB_VENDORS_TABLE        = aws_dynamodb_table.vendor_master.name
        DYNAMODB_POS_TABLE            = aws_dynamodb_table.po_ledger.name
        DYNAMODB_RECEIPTS_TABLE       = aws_dynamodb_table.receipts.name
        DYNAMODB_INVOICE_STATUS_TABLE = aws_dynamodb_table.invoice_status.name
        S3_AP_BUCKET                  = aws_s3_bucket.invoice_inbox.id
        OPENAI_API_KEY_SECRET         = var.openai_api_key_secret_name
        AP_TRIAGE_USE_LLM             = var.ap_triage_use_llm ? "true" : "false"
      },
      local.lambda_otel_env,
    )
  }

  tags = local.common_tags
}

resource "aws_lambda_permission" "connect" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket.execution_arn}/*/$connect"
}

resource "aws_lambda_permission" "disconnect" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.disconnect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket.execution_arn}/*/$disconnect"
}

resource "aws_lambda_permission" "chat" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chat.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket.execution_arn}/*/$default"
}
