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
    # State path: accounting-agent/<workspace>/terraform.tfstate
    # Use workspaces for dev/prod: terraform workspace select dev (or prod)
    workspace_key_prefix = "accounting-agent"
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

}
