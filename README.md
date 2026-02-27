# Press Release Drafting Assistant

AI-powered Press Release Drafting Assistant with a WebSocket chat frontend, Lambda-backed chat (LangGraph), DynamoDB and S3 datasources. The agent turns rough drafts and key topics into polished, publication-ready press releases using internal facts and approved assets.

## What's included

- **Terraform**: VPC (default), ALB, ECS Fargate (frontend), Lambda (connect, disconnect, chat), API Gateway WebSocket, DynamoDB (sessions + knowledge), S3 (press-kit documents), IAM
- **Lambda**: WebSocket connect/disconnect and a chat handler that runs the Press Release orchestrator (LangGraph) with tools for DynamoDB lookups and S3 press-kit documents
- **Frontend**: FastAPI app with form-driven inputs, chat, and right-side file panel for generated press releases

## Prerequisites

- AWS CLI, Terraform, Docker, Python 3.11+
- An AWS account and (for remote state) an S3 bucket and DynamoDB table for Terraform state

## Adapt before deploy

See **[infra/ADAPT_BEFORE_DEPLOY.md](infra/ADAPT_BEFORE_DEPLOY.md)** for:

- Setting `project_name` and `environment`
- Backend (state) configuration
- Creating the OpenAI API key secret in Secrets Manager
- Building Lambda zips after first apply

## Quick start

1. **Terraform**
   - Set variables (e.g. `project_name`, `environment`) via tfvars or CLI.
   - Build Lambda zips:
     ```bash
     python scripts/build_lambda_connect.py
     python scripts/build_lambda_disconnect.py
     python scripts/build_lambda_chat.py
     ```
   - From repo root: `cd infra && terraform init && terraform apply`.

2. **Seed data** (after first apply):
   ```bash
   export DYNAMODB_KNOWLEDGE_TABLE=$(terraform -chdir=infra output -raw dynamodb_knowledge_table)
   export S3_PRESS_KIT_BUCKET=$(terraform -chdir=infra output -raw s3_press_kit_bucket)
   export AWS_REGION=us-east-1
   python scripts/seed_press_release.py
   ```

3. **Frontend image**
   - Build: `docker build --platform linux/amd64 -t agent-template-frontend .`
   - Tag and push to the ECR repository output by Terraform; update ECS service (e.g. force new deployment).

4. Open the frontend at `{path_prefix}/app` and use the form to draft a press release.

## Local development

```bash
export OPENAI_API_KEY=sk-...
export DYNAMODB_KNOWLEDGE_TABLE=your-table  # optional
export S3_PRESS_KIT_BUCKET=your-bucket      # optional (after deploy)
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/app. For local dev the WebSocket connects to `/ws` on the same server.

## WebSocket URL

When using the deployed frontend, set `AGENT_WS_URL` to the full WebSocket URL including the stage:

```bash
terraform -chdir=infra output websocket_api_url
# Returns: wss://xxx.execute-api.region.amazonaws.com/$default
```

## Project layout

- `app/` – FastAPI app (health, static, chat page, WebSocket for local dev)
- `core/` – Config, agent manager, Press Release orchestrator (LangGraph), tools
- `frontend/` – Templates and static (JS/CSS) for the Press Release UI
- `lambda/` – WebSocket connect, disconnect, and chat handlers
- `infra/` – Terraform (ALB, ECS, Lambda, API Gateway, DynamoDB, S3, IAM)
- `scripts/` – Build Lambda zips, seed press release data

## Further reading

- **[PRESS_RELEASE_SETUP.md](PRESS_RELEASE_SETUP.md)** – Press release features, data sources, WebSocket contract
