# Adapt Before Deploy

To avoid collisions with other deployments and to get a working stack, do the following before running `terraform apply`.

## 1. Set a unique project name

In `variables.tf` or via `-var` / `.tfvars`, set `project_name` to a value unique to your team or agent (e.g. `my-weather-agent`). The default `empty-agent-template` is for the template only; reusing it across deployments will cause resource name clashes in the same account/region.

## 2. Set environment

Set `environment` to `dev` or `prod` (required; no default). Use a `.tfvars` file or workspace:

- Example: `terraform apply -var="environment=dev" -var="project_name=my-agent"`
- Or: `terraform workspace new my-agent-dev` then use a tfvars that sets `environment = "dev"` and `project_name = "my-agent"`

## 3. Backend (state)

The default backend uses:

- Bucket: `aheadailabs-terraform-state`
- DynamoDB table: `aheadailabs-terraform-locks`
- State key: `empty-agent-template/<workspace>/terraform.tfstate`

If you use a different AWS account or state bucket, edit the `backend "s3"` block in `main.tf` and run `terraform init -reconfigure`. Use Terraform workspaces so each deployment (e.g. `my-agent-dev`, `my-agent-prod`) has its own state file.

## 4. OpenAI API key secret

Ensure the secret referenced by `openai_api_key_secret_name` (default: `openai_api_key`) exists in AWS Secrets Manager in the same region:

```bash
aws secretsmanager create-secret --name openai_api_key --secret-string "sk-..." --region us-east-1
```

Or set the variable to an existing secret name.

## 5. Lambda layers (optional)

- To use **existing** layers: set `strands_layer_arn` and `openai_layer_arn` in your tfvars so Terraform does not create new layers.
- To **create** layers: before apply, build the layer zips and place them at:
  - `infra/layers/artifacts/strands-ahead-layer.zip` – **Strands-AHEAD** (no OpenTelemetry): place `strands_ahead-*.whl` in repo root `strands-ahead-package/`, then run `./infra/layers/strands_ahead/build_layer.sh` from repo root. Or run `./scripts/build_layers.sh` (builds both strands and openai).
  - `infra/layers/artifacts/openai-layer.zip` – built by `./scripts/build_layers.sh`.  
  The template uses **Strands-AHEAD** in the layer (not PyPI strands-agents) so the chat Lambda does not hit OpenTelemetry import errors in AWS Lambda.

## 6. Lambda zip artifacts

Before first apply, the Lambda functions expect these zips to exist (or Terraform will fail on the file reference):

- `dist/connect_lambda.zip`
- `dist/disconnect_lambda.zip`
- `dist/chat_lambda.zip`

Run the build scripts (see README) to generate them. You can use a placeholder (e.g. empty zip) for initial `terraform plan` if needed.

## 7. Seed the knowledge table (after first apply)

After the first successful `terraform apply`, seed the single demo record (Chicago polar vortex weather) so the agent’s recall tool can return it:

```bash
export DYNAMODB_KNOWLEDGE_TABLE=$(terraform -chdir=infra output -raw dynamodb_knowledge_table)
export AWS_REGION=us-east-1
python scripts/seed_knowledge.py
```

Or: `python scripts/seed_knowledge.py --table <table-name> --region us-east-1`

## 8. Secure connection (HTTPS)

- **WebSocket** is already **WSS** (secure) via API Gateway; the frontend uses this URL and it works from both HTTP and HTTPS pages.
- **Frontend** is served over **HTTP** (port 80) by default. Browsers allow this with WSS for testing.
- For **production**, serve the app over **HTTPS** (e.g. add an ACM certificate and an HTTPS listener on the ALB, or put the ALB behind CloudFront with a custom domain and ACM). Use a custom domain; ACM cannot issue certs for the default ALB hostname.
