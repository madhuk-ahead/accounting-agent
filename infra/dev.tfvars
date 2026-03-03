# Dev deployment tfvars for accounting-agent
# Apply with: terraform workspace select dev && terraform apply -var-file=dev.tfvars

project_name = "acct-agent"
environment  = "dev"
aws_region   = "us-east-1"
service_path = "/accounting_agent"

# Optional: use existing Lambda layer ARNs to avoid building layers
# strands_layer_arn = "arn:aws:lambda:us-east-1:ACCOUNT:layer:layer-name:VERSION"
# openai_layer_arn  = "arn:aws:lambda:us-east-1:ACCOUNT:layer:openai:VERSION"
