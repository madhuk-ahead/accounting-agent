# AP Invoice Triage (LangGraph)

This template runs the **AP Invoice Triage + Coding Copilot** using **LangGraph** as the orchestrator. LangGraph and its dependencies are bundled in the chat Lambda zip.

## Quick start

### Local development

```bash
export OPENAI_API_KEY=sk-...
export ORCHESTRATOR_TYPE=langraph
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/app.

### AWS Lambda deployment

1. Ensure `requirements-lambda.txt` includes:

   ```
   langgraph>=0.2.0
   langchain-openai>=0.2.0
   langchain-core>=0.3.0
   ```

2. Build the chat Lambda:

   ```bash
   python3 scripts/build_lambda_chat.py
   ```

3. Apply Terraform:

   ```bash
   cd infra && terraform apply
   ```

## Features

- AP triage: Extract → 3-Way Match → GL Coding → Artifact Generation
- DynamoDB: Vendors, POs, Receipts, InvoiceStatus
- S3: invoices/, policies/, outputs/
- LangGraph workflow export: `graph = workflow.compile()` for LangGraph Studio
