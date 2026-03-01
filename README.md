# AP Invoice Triage + Coding Copilot

24/7 Agentic AP Assistant: Extract → 3-Way Match → GL Coding → Artifact Generation. LangGraph-based workflow with WebSocket chat frontend, Lambda, DynamoDB and S3.

## What's included

- **Terraform**: VPC, ALB, ECS Fargate (frontend), Lambda (connect, disconnect, chat), API Gateway WebSocket, DynamoDB (sessions + Vendors, POs, Receipts, InvoiceStatus), S3 (invoices/, policies/, outputs/), IAM
- **Lambda**: WebSocket connect/disconnect and a chat handler that runs the AP Invoice orchestrator (LangGraph)
- **Frontend**: FastAPI app with invoice path input, chat, and right-side panel for GL coding and ERP packet

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
   export S3_AP_BUCKET=$(terraform -chdir=infra output -raw s3_ap_bucket)
   export DYNAMODB_VENDORS_TABLE=$(terraform -chdir=infra output -raw dynamodb_vendor_master_table)
   export DYNAMODB_POS_TABLE=$(terraform -chdir=infra output -raw dynamodb_po_ledger_table)
   export DYNAMODB_RECEIPTS_TABLE=$(terraform -chdir=infra output -raw dynamodb_receipts_table)
   export DYNAMODB_INVOICE_STATUS_TABLE=$(terraform -chdir=infra output -raw dynamodb_invoice_status_table)
   export AWS_REGION=us-east-1
   python scripts/seed_ap_invoice.py
   ```

3. **Frontend image**
   - Build: `docker build --platform linux/amd64 -t agent-template-frontend .`
   - Tag and push to the ECR repository output by Terraform; update ECS service.

4. Open the frontend at `{path_prefix}/app` and run AP triage.

## Local development

```bash
export OPENAI_API_KEY=sk-...
export S3_AP_BUCKET=your-bucket   # optional
export ORCHESTRATOR_TYPE=ap       # or langraph
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/app.

## Orchestrator type

Set `ORCHESTRATOR_TYPE` to `ap` or `langraph` (default: `ap`). Both use the AP Invoice LangGraph workflow.

## Project layout

- `app/` – FastAPI app (health, static, chat page, WebSocket for local dev)
- `core/` – Config, agent manager, state, AP Invoice orchestrator (LangGraph), tools
- `frontend/` – Templates and static (JS/CSS) for AP triage UI
- `lambda/` – WebSocket connect, disconnect, and chat handlers
- `infra/` – Terraform (ALB, ECS, Lambda, API Gateway, DynamoDB, S3, IAM)
- `scripts/` – Build Lambda zips, seed AP data
