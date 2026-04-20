# Production deployment tfvars for accounting-agent
# Apply with: terraform workspace select prod && terraform apply -var-file=prod.tfvars

project_name = "acct-agent"
environment  = "prod"
aws_region   = "us-east-1"
service_path = "/accounting_agent"

# OpenTelemetry → Grafana Cloud (shared AHEAD dashboard; Secrets Manager secret = OTLP auth header)
otel_endpoint            = "https://otlp-gateway-prod-us-east-3.grafana.net/otlp"
grafana_otel_secret_name = "grafana-otel-token"

# Production: real LLM triage (ensure async/long-running design if runs exceed ~29s API GW limit).
ap_triage_use_llm = true

# Optional: use existing Lambda layer ARNs
# strands_layer_arn = "arn:aws:lambda:us-east-1:ACCOUNT:layer:layer-name:VERSION"
# openai_layer_arn  = "arn:aws:lambda:us-east-1:ACCOUNT:layer:openai:VERSION"
