variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming. Change before deploy to avoid collisions. Keep short (e.g. agent-tmpl): ALB and target group names have a 32-character limit."
  type        = string
  default     = "empty-agent-template"
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
  description = "Path prefix for the service (e.g., /agent)"
  type        = string
  default     = "/agent"
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

variable "strands_layer_arn" {
  description = "Optional ARN of existing Strands-AHEAD Lambda layer. If not provided, a new layer will be created (requires layers/artifacts/strands-ahead-layer.zip)."
  type        = string
  default     = null
}

variable "openai_layer_arn" {
  description = "Optional ARN of existing OpenAI Lambda layer. If not provided, a new layer will be created (requires layers/artifacts/openai-layer.zip)."
  type        = string
  default     = null
}
