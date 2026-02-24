# Empty Agent Template

Generalized deployment template for an AI agent with a single WebSocket chat frontend, Lambda-backed chat (Strands-AHEAD), and one datasource: a DynamoDB knowledge table with a demo “Chicago polar vortex” weather record. The agent can **recall** that record when asked and otherwise chats while steering the conversation toward weather.

## What’s included

- **Terraform**: VPC (default), ALB, ECS Fargate (frontend), Lambda (connect, disconnect, chat), API Gateway WebSocket, DynamoDB (sessions + knowledge), IAM, optional Lambda layers (Strands-AHEAD, OpenAI).
- **Lambda**: WebSocket connect/disconnect and a chat handler that runs the Strands orchestrator with one tool: `recall_weather_record` (reads from the knowledge table).
- **Frontend**: FastAPI app serving a single chat page; WebSocket client uses `AGENT_WS_URL`.
- **Container**: Dockerfile for the frontend (Fargate); health check at `{service_path}/api/health`.

## Prerequisites

- AWS CLI, Terraform, Docker, Python 3.11+
- An AWS account and (for remote state) an S3 bucket and DynamoDB table for Terraform state

## Adapt before deploy

**Important:** To avoid name collisions with other deployments, set a **unique `project_name`** (and optionally use a separate Terraform workspace or state key). See **[infra/ADAPT_BEFORE_DEPLOY.md](infra/ADAPT_BEFORE_DEPLOY.md)** for:

- Setting `project_name` and `environment`
- Backend (state) configuration
- Creating the OpenAI API key secret in Secrets Manager
- Lambda layers (use existing ARNs or build and place zips in `infra/layers/artifacts/`)
- Building Lambda zips and seeding the knowledge table after first apply

## Quick start (after adapting)

1. **Terraform**
   - Set variables (e.g. `project_name`, `environment`) via tfvars or CLI.
   - **Lambda layers**: Either set `strands_layer_arn` (and optionally `openai_layer_arn`) in tfvars to use existing layers, or build locally: place `strands_ahead-*.whl` in `strands-ahead-package/`, then run `./scripts/build_layers.sh` to produce `infra/layers/artifacts/strands-ahead-layer.zip` and `openai-layer.zip`.
   - Build Lambda zips:
     ```bash
     python scripts/build_lambda_connect.py
     python scripts/build_lambda_disconnect.py
     python scripts/build_lambda_chat.py
     ```
   - From repo root: `cd infra && terraform init && terraform apply`.

2. **Seed knowledge table** (after first apply):
   ```bash
   export DYNAMODB_KNOWLEDGE_TABLE=$(terraform -chdir=infra output -raw dynamodb_knowledge_table)
   export AWS_REGION=us-east-1
   python scripts/seed_knowledge.py
   ```

3. **Frontend image**
   - Build: `docker build --platform linux/amd64 -t agent-template-frontend .`
   - Tag and push to the ECR repository output by Terraform; update ECS service (e.g. force new deployment).

4. Open the frontend (ALB DNS or CloudFront) at `{path_prefix}/app` and chat; ask to **recall the weather record** to get the Chicago polar vortex message.

**If you see "Error: Unknown error" or "Error: StopIteration()"** when sending messages: see **[docs/DEPLOYMENT_FIX_PLAN.md](docs/DEPLOYMENT_FIX_PLAN.md)**. The StopIteration case is caused by OpenTelemetry in the PyPI Strands layer failing in Lambda; the fix is to use a Strands-AHEAD layer (see the plan and [STRANDS_LAYER_AND_OPENAI.md](docs/STRANDS_LAYER_AND_OPENAI.md)).

## Strands layer and OpenAI

See **[docs/STRANDS_LAYER_AND_OPENAI.md](docs/STRANDS_LAYER_AND_OPENAI.md)** for how the Strands layer (strands-ahead vs PyPI) and OpenAI API key/calls work in this template compared to secunit_agent and data_auto_engineer.

## Project layout

- `app/` – FastAPI app (health, static, chat page).
- `core/` – Config, agent manager, orchestrator (Strands with one tool).
- `frontend/` – Templates and static (JS/CSS) for the chat UI.
- `lambda/` – WebSocket connect, disconnect, and chat handlers.
- `infra/` – Terraform (ALB, ECS, Lambda, API Gateway, DynamoDB, IAM, layers).
- `scripts/` – Build Lambda zips, seed knowledge table.

## License / use

Use and adapt as needed for your own agents. Ensure `project_name` and backend/state are unique per deployment to avoid collisions.
