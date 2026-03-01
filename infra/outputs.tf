output "ecr_repository_url" {
  description = "ECR repository URL for the frontend container"
  value       = aws_ecr_repository.frontend.repository_url
}

output "origin_hostname" {
  description = "ALB DNS name (e.g. for CloudFront origin)"
  value       = aws_lb.frontend.dns_name
}

output "path_prefix" {
  description = "Path prefix for the service"
  value       = var.service_path
}

output "websocket_api_url" {
  description = "WebSocket API endpoint URL (wss://). Append /$default for connections."
  value       = "${replace(aws_apigatewayv2_api.websocket.api_endpoint, "https://", "wss://")}/${aws_apigatewayv2_stage.websocket.name}"
}

output "websocket_api_id" {
  description = "WebSocket API ID"
  value       = aws_apigatewayv2_api.websocket.id
}

output "lambda_connect_function_name" {
  description = "Connect Lambda function name"
  value       = aws_lambda_function.connect.function_name
}

output "lambda_disconnect_function_name" {
  description = "Disconnect Lambda function name"
  value       = aws_lambda_function.disconnect.function_name
}

output "lambda_chat_function_name" {
  description = "Chat Lambda function name"
  value       = aws_lambda_function.chat.function_name
}

output "dynamodb_sessions_table" {
  description = "Sessions DynamoDB table name"
  value       = aws_dynamodb_table.sessions.name
}

output "dynamodb_vendor_master_table" {
  description = "Vendor master DynamoDB table name"
  value       = aws_dynamodb_table.vendor_master.name
}

output "dynamodb_po_ledger_table" {
  description = "PO ledger DynamoDB table name"
  value       = aws_dynamodb_table.po_ledger.name
}

output "dynamodb_receipts_table" {
  description = "Receipts DynamoDB table name"
  value       = aws_dynamodb_table.receipts.name
}

output "dynamodb_invoice_status_table" {
  description = "Invoice status DynamoDB table name"
  value       = aws_dynamodb_table.invoice_status.name
}

output "alb_arn" {
  description = "ALB ARN"
  value       = aws_lb.frontend.arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.frontend.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.frontend.name
}

output "s3_ap_bucket" {
  description = "S3 bucket for AP invoice inbox (invoices/, policies/, outputs/)"
  value       = aws_s3_bucket.invoice_inbox.id
}
