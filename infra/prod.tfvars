# Production deployment tfvars for accounting-agent
# Apply with: terraform workspace select prod && terraform apply -var-file=prod.tfvars

project_name = "acct-agent"
environment  = "prod"
aws_region   = "us-east-1"
service_path = "/accounting_agent"

# Optional: use existing Lambda layer ARNs
# strands_layer_arn = "arn:aws:lambda:us-east-1:ACCOUNT:layer:layer-name:VERSION"
# openai_layer_arn  = "arn:aws:lambda:us-east-1:ACCOUNT:layer:openai:VERSION"
