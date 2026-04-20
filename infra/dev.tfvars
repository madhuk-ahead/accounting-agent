# Dev deployment tfvars for accounting-agent
# Apply with: terraform workspace select dev && terraform apply -var-file=dev.tfvars

project_name = "acct-agent"
environment  = "dev"
aws_region   = "us-east-1"
service_path = "/accounting_agent"

# OpenTelemetry → Grafana Cloud (shared AHEAD dashboard; Secrets Manager secret = OTLP auth header)
otel_endpoint            = "https://otlp-gateway-prod-us-east-3.grafana.net/otlp"
grafana_otel_secret_name = "grafana-otel-token"

# Real LLM extraction in ingest. Note: API Gateway WebSocket → Lambda is ~29s max; long runs may time out (UI stuck) until async architecture exists.
ap_triage_use_llm = true

# Optional: use existing Lambda layer ARNs to avoid building layers
# strands_layer_arn = "arn:aws:lambda:us-east-1:ACCOUNT:layer:layer-name:VERSION"
# openai_layer_arn  = "arn:aws:lambda:us-east-1:ACCOUNT:layer:openai:VERSION"
