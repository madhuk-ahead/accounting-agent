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

