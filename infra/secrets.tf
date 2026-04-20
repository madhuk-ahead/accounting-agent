# Reference to existing Secrets Manager secret for OpenAI API key
# Create the secret manually if needed:
#   aws secretsmanager create-secret --name openai_api_key --secret-string "your-api-key" --region us-east-1

data "aws_secretsmanager_secret" "openai_api_key" {
  name = var.openai_api_key_secret_name
}

data "aws_secretsmanager_secret" "grafana_otel" {
  count = var.grafana_otel_secret_name != "" ? 1 : 0
  name  = var.grafana_otel_secret_name
}
