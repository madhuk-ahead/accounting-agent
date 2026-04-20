variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming. Keep short (e.g. acct-agent): ALB and target group names have a 32-character limit."
  type        = string
  default     = "acct-agent"
}

variable "environment" {
  description = "Environment name (e.g., prod, dev)"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}

variable "service_path" {
  description = "Path prefix for the service (e.g., /accounting_agent). Must match aheadailabs-infra CloudFront path."
  type        = string
  default     = "/accounting_agent"
  validation {
    condition     = startswith(var.service_path, "/")
    error_message = "service_path must start with '/'."
  }
}

variable "openai_api_key_secret_name" {
  description = "Name of the AWS Secrets Manager secret containing OPENAI_API_KEY"
  type        = string
  default     = "openai_api_key"
}

variable "otel_endpoint" {
  description = "OTLP HTTP endpoint (no trailing path). Empty = telemetry disabled."
  type        = string
  default     = ""
}

variable "grafana_otel_secret_name" {
  description = "Secrets Manager secret name whose value is OTEL auth header (e.g. Authorization=Basic ...). Empty = no OTLP auth / no extra IAM."
  type        = string
  default     = ""
}

variable "ap_triage_use_llm" {
  description = "If false, chat Lambda sets AP_TRIAGE_USE_LLM=false so ingest skips LLM extraction (mock) and usually finishes under API Gateway's 29s WebSocket limit. Set true for full LLM triage (needs async architecture or expect timeouts)."
  type        = bool
  default     = true
}

