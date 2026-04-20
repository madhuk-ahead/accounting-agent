# Temporary plan: OpenTelemetry for accounts_payable_agent

Reference: [docs/ADDING_TELEMETRY_TO_ANY_AGENT.md](ADDING_TELEMETRY_TO_ANY_AGENT.md) (same content as the observability guide). Dashboard metric names match [docs/agent-overview-dashboard.json](agent-overview-dashboard.json) (`ws_sessions_total`, `ws_turns_total`, `llm_calls_total`, `tool_calls_total`, histograms).

## Repo snapshot

- **FastAPI** (`app/main.py`): sub-app with `/ws`, static UI, `/api/health`, `/api/upload-invoice`. `create_app()` mounts the sub-app at `APP_ROOT_PATH`.
- **Agent**: `core/agent.py` → LangGraph (`APInvoiceOrchestrator`) or Strands (`StrandsOrchestrator`). Default path uses **LangGraph** + `core/tools/ap_invoice_tools.py` for extraction and ERP helpers.
- **LLM calls**: LangChain `ChatOpenAI` in `_extract_with_llm`, `_extract_from_images`, `_extract_from_image` (invoice extraction). `assign_coding` in LangGraph is rule-based (no LLM).
- **AWS**: WebSocket **connect** (sessions in DynamoDB), **chat** (one Lambda invocation per user message), **ECS Fargate** for the frontend container.

## Steps (investigate → plan → implement → test → cleanup)

### Step 1 — Dependencies

- **Investigate**: `requirements.txt` and `requirements-lambda.txt` had no OTel packages.
- **Plan**: Add the five packages from the guide to both files so ECS and Lambda zips include exporters and FastAPI/botocore instrumentors.
- **Done**: Added OpenTelemetry API/SDK, OTLP HTTP exporter, FastAPI and botocore instrumentations.

### Step 2 — `core/telemetry.py`

- **Investigate**: No prior telemetry module.
- **Plan**: Copy the shared `init_telemetry()`, `get_tracer()`, `get_meter()` pattern; add optional `GRAFANA_OTEL_SECRET_NAME` → load `OTEL_EXPORTER_OTLP_HEADERS` via boto3 so **Lambda** can authenticate without ECS-style secret injection.
- **Done**: `core/telemetry.py` with `_load_otlp_headers_from_secrets_if_needed()`.

### Step 3 — Instrumentation helpers

- **Investigate**: Dashboard expects `llm.*` and `tool.*` spans and counters with consistent names.
- **Plan**: `core/telemetry_instrumentation.py` with `trace_llm_langchain()` and `trace_tool()` for `llm.invoke` / `tool.<name>` and histograms/counters.
- **Done**: Implemented; LangChain `AIMessage` usage via `usage_metadata` / `response_metadata`.

### Step 4 — FastAPI

- **Investigate**: `create_app()` had no OTel init; WebSocket was not traced.
- **Plan**: Call `init_telemetry()` first in `create_app()`; add `ws.sessions.total`, `ws.turns.total`, `ws.session`, `ws.turn` on `sub` WebSocket (local dev parity with guide).
- **Done**: `app/main.py` updated.

### Step 5 — Tools and LLM

- **Investigate**: `extract_invoice` is the main tool; LLM calls live in private helpers.
- **Plan**: Wrap `extract_invoice` with `trace_tool("extract_invoice", ...)`, wrap each LangChain invoke with `trace_llm_langchain`.
- **Done**: `core/tools/ap_invoice_tools.py` (`extract_invoice` → `_extract_invoice_impl`).

### Step 6 — Lambda (`chat`, `connect`)

- **Investigate**: Production traffic uses API Gateway WebSocket: connect creates sessions; **chat** runs one turn per invocation (no long-lived `ws` span in one process).
- **Plan**: `init_telemetry()` + `ws.turn` + `ws.turns.total` in `lambda/chat.py`; `ws.sessions.total` in `lambda/connect.py` when a session row is created. Extend `build_lambda_connect.py` to bundle `core/` (telemetry + boto3 secret bootstrap).
- **Done**: `lambda/chat.py`, `lambda/connect.py`, `scripts/build_lambda_connect.py`.

### Step 7 — Terraform

- **Investigate**: `infra/ecs.tf` had no OTel env; IAM had OpenAI secret only.
- **Plan**: Variables `otel_endpoint`, `grafana_otel_secret_name`; conditional `data.aws_secretsmanager_secret.grafana_otel`; ECS env + optional `secrets` for OTEL headers; Lambda `merge` env with OTEL + `GRAFANA_OTEL_SECRET_NAME`; IAM `GetSecretValue` for Grafana secret on Lambda execution role and ECS execution role (conditional).
- **Done**: `infra/variables.tf`, `infra/secrets.tf`, `infra/ecs.tf`, `infra/lambda.tf`, `infra/iam.tf`.

### Step 8 — Test and deploy

- **Test**: Local venv: `python -c "from app.main import app"` after `pip install -r requirements.txt`.
- **Deploy**: Build/push Docker image; rebuild Lambda zips (`scripts/build_lambda_chat.py`, `scripts/build_lambda_connect.py`); `terraform apply` with `-var='otel_endpoint=...' -var='grafana_otel_secret_name=grafana-otel-token'` (or your secret name); verify **Explore → Tempo** and **Prometheus** in Grafana; confirm the **AHEAD Agent Overview** panel shows `service_name` = `${project_name}-${environment}` (e.g. `acct-agent-dev`).

### Step 9 — Cleanup

- Remove this file when the team is satisfied, or keep as runbook.

## Notes

- **Strands** orchestrator uses the Strands runtime for LLM calls; extraction still goes through `extract_invoice` (instrumented). Extra Strands-only LLM spans may appear if you add OpenAI SDK instrumentation later.
- **Dashboard JSON** lives at `docs/agent-overview-dashboard.json` (not under `docs/observability/` in this repo). Import into Grafana if not already present.
