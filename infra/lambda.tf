# Lambda: WebSocket connect, disconnect, and chat (default route)

resource "aws_lambda_function" "connect" {
  filename      = "${path.module}/../dist/connect_lambda.zip"
  function_name = "${local.name_prefix}-connect"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "connect.lambda_handler"
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

resource "aws_lambda_function" "disconnect" {
  filename      = "${path.module}/../dist/disconnect_lambda.zip"
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

resource "aws_lambda_function" "chat" {
  filename      = "${path.module}/../dist/chat_lambda.zip"
  function_name = "${local.name_prefix}-chat"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "chat.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  layers = []

  environment {
    variables = {
      DYNAMODB_SESSIONS_TABLE  = aws_dynamodb_table.sessions.name
      DYNAMODB_KNOWLEDGE_TABLE = aws_dynamodb_table.knowledge.name
      S3_PRESS_KIT_BUCKET      = aws_s3_bucket.press_kit.id
      OPENAI_API_KEY_SECRET    = var.openai_api_key_secret_name
    }
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
