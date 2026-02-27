# Adapt Before Deploy

To avoid collisions with other deployments and to get a working stack, do the following before running `terraform apply`.

## 1. Set a unique project name

In `variables.tf` or via `-var` / `.tfvars`, set `project_name` to a value unique to your team or agent (e.g. `my-pr-agent`). The default may cause resource name clashes in the same account/region.

## 2. Set environment

Set `environment` to `dev` or `prod` (required). Use a `.tfvars` file or workspace:

- Example: `terraform apply -var="environment=dev" -var="project_name=my-pr-agent"`

## 3. Backend (state)

The default backend uses:

- Bucket: `aheadailabs-terraform-state`
- DynamoDB table: `aheadailabs-terraform-locks`

If you use a different AWS account or state bucket, edit the `backend "s3"` block in `main.tf` and run `terraform init -reconfigure`.

## 4. OpenAI API key secret

Ensure the secret referenced by `openai_api_key_secret_name` (default: `openai_api_key`) exists in AWS Secrets Manager in the same region:

```bash
aws secretsmanager create-secret --name openai_api_key --secret-string "sk-..." --region us-east-1
```

## 5. Lambda zip artifacts

Before first apply, the Lambda functions expect these zips:

- `dist/connect_lambda.zip`
- `dist/disconnect_lambda.zip`
- `dist/chat_lambda.zip`

Run the build scripts (see README) to generate them. The chat zip includes LangGraph and its dependencies from `requirements-lambda.txt`.

## 6. Seed data (after first apply)

After the first successful `terraform apply`, seed DynamoDB and S3 with press release assets:

```bash
export DYNAMODB_KNOWLEDGE_TABLE=$(terraform -chdir=infra output -raw dynamodb_knowledge_table)
export S3_PRESS_KIT_BUCKET=$(terraform -chdir=infra output -raw s3_press_kit_bucket)
export AWS_REGION=us-east-1
python scripts/seed_press_release.py
```

## 7. WebSocket URL

When configuring the frontend, use the full WebSocket URL including the stage:

```bash
terraform -chdir=infra output websocket_api_url
# Returns: wss://xxx.execute-api.region.amazonaws.com/$default
```
