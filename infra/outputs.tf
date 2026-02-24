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
  description = "WebSocket API endpoint URL (wss://)"
  value       = replace(aws_apigatewayv2_api.websocket.api_endpoint, "https://", "wss://")
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

output "dynamodb_knowledge_table" {
  description = "Knowledge DynamoDB table name"
  value       = aws_dynamodb_table.knowledge.name
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

output "strands_ahead_layer_arn" {
  description = "Strands-AHEAD Lambda layer ARN"
  value       = local.strands_ahead_layer_arn != null ? local.strands_ahead_layer_arn : (length(aws_lambda_layer_version.strands_ahead) > 0 ? aws_lambda_layer_version.strands_ahead[0].arn : "not_created")
}

output "openai_layer_arn" {
  description = "OpenAI Lambda layer ARN"
  value       = local.openai_layer_arn != null ? local.openai_layer_arn : (length(aws_lambda_layer_version.openai) > 0 ? aws_lambda_layer_version.openai[0].arn : "not_created")
}
