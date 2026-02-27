# Press Release Agent (LangGraph)

This template runs the **Press Release Drafting Assistant** using **LangGraph** as the orchestrator. There are no Strands or Lambda layers; LangGraph and its dependencies are bundled in the chat Lambda zip.

## Quick start

### Local development

```bash
export OPENAI_API_KEY=sk-...
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

- Press release drafting with form-driven inputs (rough draft, key topics, tone)
- DynamoDB tools: company boilerplate, product facts, quotes, partner info, metrics
- S3 tools: press-kit documents, save generated press releases
- Streaming responses and right-side file panel with download

See **[PRESS_RELEASE_SETUP.md](PRESS_RELEASE_SETUP.md)** for full details.
