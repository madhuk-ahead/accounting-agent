terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "aheadailabs-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "aheadailabs-terraform-locks"
    # State path: empty-agent-template/<workspace>/terraform.tfstate
    # Use workspaces for multiple deployments: terraform workspace new my-agent-dev
    workspace_key_prefix = "empty-agent-template"
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  project_name = var.project_name
  environment  = var.environment
  name_prefix  = "${local.project_name}-${local.environment}"
  account_id   = data.aws_caller_identity.current.account_id
  common_tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "Terraform"
  }

  strands_ahead_layer_arn = var.strands_layer_arn != null ? var.strands_layer_arn : try(aws_lambda_layer_version.strands_ahead[0].arn, null)
  openai_layer_arn        = var.openai_layer_arn != null ? var.openai_layer_arn : try(aws_lambda_layer_version.openai[0].arn, null)
}
