# Press Release Drafting Assistant

This document describes the Press Release Drafting Assistant, a LangGraph-based agent that helps users turn rough drafts and key topics into polished, publication-ready press releases.

## Features

- **Form-driven inputs**: Rough draft, key topics, tone (professional, conversational, bold, formal), and optional constraints (audience, length, CTA, exclusions)
- **Internal data enrichment**: DynamoDB (company boilerplate, product facts, quotes, partner info, metrics) and S3 press-kit documents
- **Standard PR structure**: Headline, subhead, dateline, body, quotes, boilerplate, media contact
- **Right-side file panel**: Generated press release displayed as a file with download support
- **Iteration via chat**: Follow-up messages to revise tone, length, or content

## Quick Start

### 1. Local development

```bash
export ORCHESTRATOR_TYPE=press_release
export OPENAI_API_KEY=sk-...
export DYNAMODB_KNOWLEDGE_TABLE=your-knowledge-table    # optional if seeding
export S3_PRESS_KIT_BUCKET=your-press-kit-bucket       # optional if seeding

# Seed spoofed data (requires AWS credentials and deployed resources)
python scripts/seed_press_release.py --table $DYNAMODB_KNOWLEDGE_TABLE --bucket $S3_PRESS_KIT_BUCKET

uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/app (or http://localhost:8000/agent/app if `APP_ROOT_PATH=/agent`).

### 2. AWS deployment

Set `orchestrator_type = "press_release"` (default) and deploy:

```bash
cd infra
terraform apply -var="project_name=my-pr-agent" -var="environment=dev"
```

After deployment, seed the DynamoDB and S3 resources:

```bash
export DYNAMODB_KNOWLEDGE_TABLE=$(terraform -chdir=infra output -raw dynamodb_knowledge_table)
export S3_PRESS_KIT_BUCKET=$(terraform -chdir=infra output -raw s3_press_kit_bucket)
python scripts/seed_press_release.py
```

Rebuild the chat Lambda (includes LangGraph):

```bash
python3 scripts/build_lambda_chat.py
```

## Data sources (spoofed)

### DynamoDB knowledge table

| id | Description |
|----|-------------|
| company:acme | Company boilerplate and media contact |
| product:skyline-2 | Product facts and differentiators |
| quote:ceo, quote:cmo | Approved executive quotes |
| partner:globex | Partner blurb and announcement facts |
| metrics:q1-2026 | Q1 2026 metrics |

### S3 press-kit documents

- `docs/press-kit/company_overview.md`
- `docs/press-kit/product_one_pager.md`
- `docs/press-kit/partner_blurb.md`
- `docs/press-kit/metrics_summary.json`

### Exports

Generated press releases are saved to:
`exports/press-releases/{session_id}/PressRelease.md`

## WebSocket message contract

**Request** (unchanged, extended):
```json
{
  "action": "message",
  "text": "Draft a press release",
  "conversation": "USER: ...\nAGENT: ...",
  "form_data": {
    "rough_draft": "...",
    "key_topics": "...",
    "tone": "professional",
    "audience": "...",
    "length": "...",
    "cta": "...",
    "exclusions": "..."
  }
}
```

**Response** (extended):
```json
{
  "type": "final",
  "content": "...",
  "file_content": "..."  // Present for press releases; display in file panel
}
```

## Tools available to the agent

- `lookup_company_boilerplate(company_id)` – Company description and boilerplate
- `lookup_product_facts(product_id)` – Product features and differentiators
- `lookup_quotes(quote_id)` – Approved executive quotes
- `lookup_partner_info(partner_id)` – Partner blurbs and facts
- `lookup_metrics(metrics_id)` – Metrics (growth, dates, etc.)
- `fetch_press_kit_document(doc_key)` – Fetch S3 press-kit documents
- `save_press_release(content, filename)` – Save generated draft to S3
