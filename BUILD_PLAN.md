# Step-by-Step Plan: Building the Empty Agent Template

This document is the master plan for filling `empty_agent_template` with a **generalized, deployment-safe** agent deployment template. The template pulls patterns from **secunit_agent** and **data_auto_engineer**, with these goals:

- **Terraform**: Agnostic naming and state so multiple teams can deploy without collisions.
- **Strands-AHEAD orchestrator**: Runs in Lambda; one tool only (recall from a single DynamoDB table).
- **Lambda WebSocket**: Connect, disconnect, and default (chat) routes.
- **Fargate**: Frontend container behind ALB (same serving pattern as secunit).
- **Frontend**: Same FastAPI + static + Jinja + WebSocket client pattern.
- **Single datasource**: One DynamoDB table with one dummy record (campy Chicago polar vortex weather); user can ask to “recall” it; agent otherwise chats and annoyingly focuses on weather.

Each step below follows: **Investigate → Write temp step plan → Execute → Test (if possible) → Clean up → Next step.**

---

## Pre-requisites and Conventions

- **Source repos**: `secunit_agent` (primary for Terraform/Fargate/Lambda/WebSocket/frontend), `data_auto_engineer` (reference for Strands orchestrator and Lambda chat flow).
- **Template repo**: `empty_agent_template`. All new files go here.
- **Collision avoidance**: Every Terraform resource uses a **project name** and **environment** (e.g. `project_name = "my-agent"`, `environment = "dev"`). Default `project_name` is `empty-agent-template`; users **must** change it (or set a unique value) before deploying their own agent. Backend state key is parameterized so each deployment has its own state.
- **Naming**: Use generic env vars in the template (e.g. `AGENT_WS_URL`, `APP_ROOT_PATH`); avoid `SECUNIT_*` or `AUTOENGINEER_*` in the template.

---

## Step 1: Terraform foundation (agnostic, no collisions)

### 1.1 Investigate

- **Secunit**: `infra/main.tf`, `variables.tf`, backend uses `workspace_key_prefix = "secunit-agent"` and key `secunit-agent/terraform.tfstate` (workspace prepends). `locals.project_name`, `environment`, `name_prefix = "${project_name}-${environment}"` drive all names.
- **Data_auto_engineer**: No S3 backend in `main.tf`; `project_name = "autoengineer"`. Uses `local.project_name` and `environment`.
- **Collision**: If two repos use same `project_name` + `environment` in same account/region, resource names (e.g. Lambda, DynamoDB, API Gateway) will clash. Template must document: “Set `project_name` (and optionally `tf_state_key`) to a unique value before first deploy.”

### 1.2 Temp step plan (Step 1)

1. Create `empty_agent_template/infra/` and copy Terraform layout from secunit: `main.tf`, `variables.tf`, `outputs.tf`, `vpc.tf`, `security_groups.tf`, `secrets.tf`, `iam.tf`, `ecr.tf`, `ecs.tf`, `alb.tf`, `lambda.tf`, `layers.tf`, `dynamodb.tf`, `apigw_websocket.tf`.
2. In `main.tf`: Set default or variable for backend; use `project_name` and `environment` in `locals`; add optional `tf_state_key_prefix` (e.g. `empty-agent-template`) so state key is `{prefix}/{project_name}-{environment}/terraform.tfstate` or similar—document that users can override.
3. In `variables.tf`: `project_name` default `"empty-agent-template"` with description “**Change this before deploying to avoid collisions.**”; `environment` (dev/prod); `service_path` (e.g. `/agent`); `aws_region`, `openai_api_key_secret_name`, optional `strands_layer_arn` and `openai_layer_arn`.
4. Replace all secunit-specific names with `local.name_prefix` or `var.project_name`/`var.environment` so no literal `secunit` remains. Remove references to secunit-only tables (incidents, topology, oncall) in IAM and DynamoDB—Step 2 will define the minimal tables (sessions + one knowledge table).
5. Add `infra/README.md` (or ADAPT_BEFORE_DEPLOY.md) that states: (a) set `project_name` to a unique value; (b) ensure backend bucket/prefix exist or adapt backend block; (c) create OpenAI secret if needed; (d) optional: use existing Lambda layer ARNs.

### 1.3 Execute

- Create each `.tf` and the README/ADAPT doc under `empty_agent_template/infra/`.
- In `dynamodb.tf`: Define only **sessions** (same schema as secunit: `session_id` PK, `connection_id` GSI, TTL) and **one** table for the agent datasource (e.g. `knowledge` or `agent_recall`): hash_key `id` (string). No incidents, topology, oncall, chat table for now (chat can be added later if needed for transcript persistence; for template minimalism, only sessions + knowledge).
- In `iam.tf`: Lambda and ECS task policies reference only `aws_dynamodb_table.sessions` and the one knowledge table. Remove policy references to incidents, topology, oncall, chat if present.
- In `lambda.tf`: Connect and disconnect Lambdas get only `DYNAMODB_SESSIONS_TABLE`; chat Lambda gets `DYNAMODB_SESSIONS_TABLE` and `DYNAMODB_KNOWLEDGE_TABLE` (or chosen name). Layers: strands-ahead + openai (same as secunit).
- In `ecs.tf`: Frontend task env vars: `APP_ROOT_PATH`, `AGENT_WS_URL` (not `SECUNIT_WS_URL`), `USE_DYNAMODB`, `AWS_REGION`, `DYNAMODB_SESSIONS_TABLE` only (frontend in template may not need knowledge table; only Lambda chat does).

### 1.4 Test

- Run `terraform init` and `terraform validate` in `empty_agent_template/infra/` (no need to apply yet). Fix any variable or reference errors.

### 1.5 Clean up

- Remove any copied comments that say “secunit” or “SecUnit”. Ensure all resource names use `local.name_prefix` or `var.*` only.

---

## Step 2: Single DynamoDB knowledge table and seed data

### 2.1 Investigate

- Secunit has no “knowledge” table; data_auto_engineer has `datasets`, `transformed`, `activity`, `chat`. For template we need one table with one item: a dummy “weather / polar vortex Chicago” record, campy and scary, so the agent’s only tool can “recall” it.
- DynamoDB table: simple PK `id` (e.g. `"polar-vortex-chicago"`). Attributes: e.g. `content` (string or map), `title`, `updated_at`. Terraform can create the table; seed data can be a separate script or a Terraform `null_resource` + local-exec that runs `aws dynamodb put-item` once.

### 2.2 Temp step plan (Step 2)

1. In `infra/dynamodb.tf`: Add resource `aws_dynamodb_table.knowledge` with `name = "${local.name_prefix}-knowledge"`, `hash_key = "id"` (S), PAY_PER_REQUEST.
2. Add a seed script `scripts/seed_knowledge.py` (or `terraform null_resource` with local-exec) that inserts one item: id `polar-vortex-chicago`, with body text that is campy/scary Chicago polar vortex weather. Script reads table name from env or CLI arg.
3. Document in README: “After first deploy, run `scripts/seed_knowledge.py` to insert the demo record (or use AWS console).”
4. Ensure Lambda chat and IAM have access to this table (already done in Step 1 if we added `DYNAMODB_KNOWLEDGE_TABLE` and IAM for it).

### 2.3 Execute

- Add `knowledge` table in `dynamodb.tf`. Create `scripts/seed_knowledge.py` that uses boto3 to put one item; table name from env `DYNAMODB_KNOWLEDGE_TABLE` or `--table`.
- Write the single record content (campy polar vortex Chicago weather) into the script as a constant.

### 2.4 Test

- Run script locally against a table (or run after first apply) and verify GetItem returns the record.

### 2.5 Clean up

- No secunit/autoengineer-specific names in script; use generic “knowledge” and “recall” terminology.

---

## Step 3: Lambda WebSocket handlers (connect, disconnect, default)

### 3.1 Investigate

- Secunit: `lambda/connect.py`, `lambda/disconnect.py`, `lambda/chat.py`. Connect writes session_id + connection_id to DynamoDB sessions; disconnect deletes by connection_id (query GSI then delete); chat resolves session_id from connection_id, then calls agent/orchestrator and sends replies via ApiGatewayManagementApi.
- Handler paths: connect/disconnect use `connect.lambda_handler` and `disconnect.lambda_handler` (file at repo root `lambda/`). Chat uses `chat.lambda_handler` and imports from `core.agent`, `core.session_storage` (secunit). Package layout: at deploy time, `lambda/` and `core/` are at zip root.
- Data_auto_engineer: Similar layout; `lambda/chat.py` uses `core.agent.get_agent_manager`, `core.config.Settings`, and passes DynamoDB table names via env.

### 3.2 Temp step plan (Step 3)

1. Create `empty_agent_template/lambda/connect.py` and `disconnect.py` from secunit, replacing `secunit_sessions` default table name with `empty_agent_template_sessions` or env `DYNAMODB_SESSIONS_TABLE` (no default that matches secunit).
2. Create `empty_agent_template/lambda/chat.py`: same structure as secunit/data_auto_engineer—get `connection_id`, `domain_name`, `stage`; look up `session_id` from DynamoDB sessions; parse body; call agent manager run (with streaming callback that posts to WebSocket); send final message. Use env: `DYNAMODB_SESSIONS_TABLE`, `DYNAMODB_KNOWLEDGE_TABLE`, `OPENAI_API_KEY_SECRET`, `AWS_REGION`. Do not reference secunit-specific tables or env vars.
3. Ensure `core/agent.py` and `core/orchestrators` exist (Step 4 will add them); chat.py can assume `get_agent_manager()` and `agent_manager.run(...)` with session_id and message and streaming callback.

### 3.3 Execute

- Add `lambda/connect.py`, `lambda/disconnect.py`, `lambda/chat.py` with generic table names and no secunit/autoengineer branding.
- If `core` does not exist yet, add minimal stubs so `terraform validate` and Lambda package build (Step 5) can run; implement core in Step 4.

### 3.4 Test

- Unit test or local test: mock event with `requestContext.connectionId`, `body`, and optionally mock DynamoDB; assert handler calls agent and sends one or more WebSocket messages. Optional: run connect in AWS, then chat, then disconnect and verify table state.

### 3.5 Clean up

- Remove debug print statements that reference “secunit” or “autoengineer”. Use generic log messages.

---

## Step 4: Strands-AHEAD orchestrator with one tool (recall) and weather-focused agent

### 4.1 Investigate

- Secunit: `core/orchestrators/strands_orchestrator.py` builds Strands `Agent` with multiple tools (triage_hash, execute_action, seed_demo_dataset, get_topology, contain_ticket, close_ticket, investigate_ticket); each tool is a `@tool` that calls into a core orchestrator or settings.
- Data_auto_engineer: `core/orchestrators/strands_orchestrator.py` has tools: list_datasets, get_dataset_info, recommend_models, transform_data, get_activity_history, delete_transformed_data; uses `FeatureEngineeringTools` and `@tool` from strands.
- For template: one tool only—e.g. `recall_weather_record` or `get_weather_info`—that reads from the single DynamoDB knowledge table (item id `polar-vortex-chicago`) and returns the content to the agent. Agent system prompt: you are a helpful but annoyingly weather-obsessed assistant; when the user asks to recall or fetch the weather record, use the recall tool and report it; otherwise keep steering conversation to weather in a campy way.

### 4.2 Temp step plan (Step 4)

1. Add `core/config.py`: Settings with `openai_api_key`, `openai_model`, `aws_region`, `dynamodb_sessions_table`, `dynamodb_knowledge_table` (from env).
2. Add `core/orchestrators/base.py`: Abstract `AgentOrchestrator` with `run_turn(conversation, session_id, ...)` and `reset()`; `OrchestratorResult` with `content`, `tool_results`, etc. (minimal, matching what Strands returns.)
3. Add `core/orchestrators/strands_orchestrator.py`: Import `strands.Agent` and `strands.tool` (from Lambda layer); define one tool `recall_weather_record()` that uses boto3 to get item `polar-vortex-chicago` from `DYNAMODB_KNOWLEDGE_TABLE` and return it; build Agent with this tool and system prompt that emphasizes weather and the single recall capability; implement `run_turn` (sync or async as in existing repos) and `reset()`.
4. Add `core/agent.py`: `AgentManager` that holds settings and gets orchestrator (Strands); `run(session_id, message, on_stream_message)` that builds conversation from message, calls `orchestrator.run_turn`, and returns content + optional tool_results. Session storage: in-memory or DynamoDB for transcript (minimal—can be in-memory for template).
5. System prompt text: instruct the agent to be chatty, focus on weather, and when the user asks to “recall” or “get the weather record” or similar, call the recall tool and deliver the campy polar vortex Chicago message.

### 4.3 Execute

- Implement `core/config.py`, `core/orchestrators/base.py`, `core/orchestrators/strands_orchestrator.py`, `core/agent.py`. Create `core/orchestrators/__init__.py` exporting `get_orchestrator` and `StrandsOrchestrator` (or single implementation).
- In strands_orchestrator: single tool that does DynamoDB GetItem and returns the record; wrap in Strands `@tool(description="...")`. System prompt: weather-obsessed, campy, and use the recall tool when user asks for the stored weather info.

### 4.4 Test

- Local test: mock DynamoDB or use real table; instantiate orchestrator, call `run_turn` with a message like “Can you recall the weather record?” and assert response contains the polar vortex content. Optional: test without Strands (mock Agent) to verify tool and config wiring.

### 4.5 Clean up

- No references to triage, containment, datasets, or feature engineering. Single tool and single table only.

---

## Step 5: Lambda packaging and layers

### 5.1 Investigate

- Secunit: `scripts/build_lambda_connect.py`, `build_lambda_disconnect.py`, `build_lambda_chat.py` (or `build_chat_lambda_zip.py`) produce zips under `dist/`. Chat zip includes `core/`, `lambda/` (or `lambdas/chat_handler`); excludes strands and openai (provided by layers). requirements-lambda.txt for Lambda deps; layers built separately (e.g. `infra/layers/strands_ahead/build_layer.sh`, openai layer).
- Data_auto_engineer: Makefile `build-layers`; Terraform expects `infra/layers/artifacts/strands-ahead-layer.zip` and `openai-layer.zip`. Lambda code from `lambda/` and `core/`.

### 5.2 Temp step plan (Step 5)

1. Add `empty_agent_template/requirements.txt` and `requirements-lambda.txt`: minimal (e.g. boto3 for Lambda; no strands/openai in requirements-lambda if using layers).
2. Add build scripts: e.g. `scripts/build_lambda_connect.py`, `build_lambda_disconnect.py`, `build_lambda_chat.py` that copy `lambda/*.py` and `core/` into a build dir, install requirements-lambda.txt, zip to `dist/connect_lambda.zip`, `dist/disconnect_lambda.zip`, `dist/chat_lambda.zip`. Chat build must exclude strands and openai when using layers.
3. Document layer build: either (a) copy layer build from secunit (`infra/layers/strands_ahead/build_layer.sh`, openai) and document “run before terraform apply”, or (b) document that users can pass existing layer ARNs via `strands_layer_arn` and `openai_layer_arn` (as in secunit prod.tfvars).
4. Terraform `lambda.tf`: point connect/disconnect to `dist/connect_lambda.zip`, `dist/disconnect_lambda.zip`, and chat to `dist/chat_lambda.zip` (or path.module relative paths). Attach layers to chat Lambda only.

### 5.3 Execute

- Add requirements files and build scripts. Ensure chat zip does not include strands/openai when layers are used. Add README or DEPLOYMENT.md: “Build Lambda zips: run scripts/build_lambda_*.py; build layers or set layer ARN variables; then terraform apply.”

### 5.4 Test

- Run build scripts; verify zips exist and chat zip size is reasonable. Run `terraform plan` and ensure Lambda source paths are correct.

### 5.5 Clean up

- Remove any hardcoded paths to secunit or data_auto_engineer. Use paths relative to `empty_agent_template`.

---

## Step 6: Frontend app (FastAPI + static + WebSocket client)

### 6.1 Investigate

- Secunit: `app/main.py` creates FastAPI app, mounts static and Jinja templates, sets `root_path` from `APP_ROOT_PATH`, defines `/api/health`, `/`, and `/app` (renders base.html with `ws_url` and `root_path`). Frontend: `frontend/templates/base.html`, `frontend/static/js/app.js`, `frontend/static/css/app.css`. JS connects to `ws_url` (e.g. from template or config) and sends/receives JSON messages (e.g. type + content).
- Data_auto_engineer: Similar; simpler templates. WebSocket URL from env in backend and passed to template.

### 6.2 Temp step plan (Step 6)

1. Add `empty_agent_template/app/main.py`: FastAPI app with `root_path` from `APP_ROOT_PATH`; mount static at `/static`, Jinja templates from `frontend/templates`; routes: `GET /api/health`, `GET /`, `GET /app` (or `/`) that render a single page with WebSocket client. Inject `AGENT_WS_URL` (not SECUNIT_WS_URL) and `root_path` into template.
2. Add `frontend/templates/base.html`: minimal page with a chat box and area for messages; include `app.js` and pass WebSocket URL from server (e.g. global var or data attribute).
3. Add `frontend/static/js/app.js`: connect to WebSocket URL; on open, allow user to type and send messages; on message, display agent response (and optional status). Same message contract as Lambda chat (e.g. `{ type: "message"|"status"|"error", content: "..." }`).
4. Add `frontend/static/css/app.css`: minimal styling for chat UI.
5. Add `core/config.py` (if not already) so app can use `get_settings()` for templates_dir and static_dir (paths to frontend/templates and frontend/static).

### 6.3 Execute

- Implement app/main.py, base.html, app.js, app.css. Use generic title “Agent” or “Template Agent” and env `AGENT_WS_URL`.

### 6.4 Test

- Run FastAPI locally with `AGENT_WS_URL=ws://localhost:8000/...` or a placeholder; open /app and confirm page loads and JS runs. If WebSocket is not yet deployed, at least verify no JS errors and that send/receive structure matches what Lambda chat will send.

### 6.5 Clean up

- No “SecUnit” or “AutoEngineer” in UI or env var names. Use “Agent” or “Template Agent” in titles.

---

## Step 7: Fargate frontend container (Dockerfile + ECS)

### 7.1 Investigate

- Secunit: Dockerfile copies `app/`, `core/`, `frontend/`, `routers/`, `data/`; CMD gunicorn with uvicorn workers on 8080. ECS task definition uses ECR image, env vars (APP_ROOT_PATH, SECUNIT_WS_URL, DynamoDB tables, etc.), health check on `APP_ROOT_PATH/api/health`. ALB forwards to target group on port 8080.

### 7.2 Temp step plan (Step 7)

1. Add `empty_agent_template/Dockerfile`: same pattern—Python 3.11, copy `app/`, `core/`, `frontend/` (and `routers/` if any); expose 8080; CMD gunicorn with uvicorn. No `data/` unless template needs it.
2. ECS task env (in Terraform): `APP_ROOT_PATH`, `AGENT_WS_URL` (from API Gateway WebSocket invoke URL), `USE_DYNAMODB`, `AWS_REGION`, `DYNAMODB_SESSIONS_TABLE`. No need for knowledge table in frontend.
3. Health check path: `${var.service_path}/api/health` (already in Step 1 if ALB/ECS were copied). Ensure app serves health at that path with root_path applied.

### 7.3 Execute

- Add Dockerfile. Ensure Terraform ECS task definition and ALB target group use port 8080 and health path. Document: “Build image, push to ECR (terraform output ecr_repository_url), then deploy/update ECS service.”

### 7.4 Test

- Build image: `docker build --platform linux/amd64 -t empty-agent-frontend .` and run locally; curl `http://localhost:8080/api/health` and `http://localhost:8080/app` (or with APP_ROOT_PATH). Fix any import or path errors.

### 7.5 Clean up

- Comments in Dockerfile say “Agent template” not “SecUnit”. Remove unused `data/` or `routers/` if not needed.

---

## Step 8: Documentation for users (adapt before deploy)

### 8.1 Investigate

- What a clone-and-deploy user must change: project_name, backend state key/bucket, OpenAI secret, optional layer ARNs, and any account/region specifics.

### 8.2 Temp step plan (Step 8)

1. Add `empty_agent_template/README.md`: overview (Terraform + Lambda WebSocket + Fargate frontend + one-tool agent); prerequisites (AWS CLI, Terraform, Docker, Python 3.11); **Adapt before deploy**: set `project_name` in tfvars or variables to a unique value; create OpenAI secret; optionally build or reference Lambda layers; backend S3 bucket and key.
2. Add `empty_agent_template/ADAPT_BEFORE_DEPLOY.md` or section in README: checklist—project_name, environment, service_path, backend, secrets, layers, run seed_knowledge after first apply.
3. Add `empty_agent_template/infra/README.md` or tfvars example: `dev.tfvars` / `prod.tfvars` with placeholder project_name and comments.

### 8.3 Execute

- Write README and ADAPT doc; add example tfvars.

### 8.4 Test

- N/A (docs only).

### 8.5 Clean up

- Ensure no internal repo names (secunit_agent, data_auto_engineer) in user-facing docs except in “Based on patterns from …” if desired.

---

## Step 9: End-to-end and cleanup

### 9.1 Investigate

- Full flow: user opens frontend → WebSocket connect → Lambda connect stores session → user sends message → Lambda chat gets session, calls agent, agent uses Strands with one tool (recall), streams back → user sees reply; user can ask to “recall the weather record” and get the campy polar vortex text. Disconnect cleans up session.

### 9.2 Temp step plan (Step 9)

1. Apply Terraform (dev) in a test account; build and push frontend image; build Lambda zips and layers; run seed_knowledge. Open frontend URL; connect and send “What’s the weather?” and “Recall the weather record” and verify behavior.
2. Fix any missing env vars, IAM, or table names. Remove debug logging that shouldn’t ship.
3. Final pass: grep for “secunit”, “autoengineer”, “SecUnit”, “AutoEngineer” in template repo and replace or remove.

### 9.3 Execute

- Run through deploy and smoke test; fix issues; do final naming cleanup.

### 9.4 Test

- Manual E2E as above.

### 9.5 Clean up

- Archive or delete any temporary step plans (e.g. TEMP_STEP_*.md) if created during execution. Leave BUILD_PLAN.md (this file) as the master plan.

---

## Summary: What the template contains

| Area | Content |
|------|--------|
| **Terraform** | Agnostic project_name + environment; backend state parameterized; VPC (default), security groups, ALB, ECS Fargate, ECR, Lambda (connect, disconnect, chat), API Gateway WebSocket, DynamoDB (sessions + knowledge), IAM, layers (strands-ahead, openai), secrets reference. |
| **Lambda** | connect, disconnect, chat handlers; chat invokes Strands orchestrator with one tool (recall from knowledge table). |
| **Orchestrator** | Strands-AHEAD; one tool `recall_weather_record`; system prompt: weather-obsessed, campy; when user asks to recall, return Chicago polar vortex record. |
| **Data** | Sessions table (WebSocket); one knowledge table with one seeded item (polar vortex Chicago, campy/scary). |
| **Frontend** | FastAPI app, static + Jinja, one chat page; WebSocket client using AGENT_WS_URL. |
| **Container** | Dockerfile → ECR → ECS Fargate behind ALB; health at service_path/api/health. |
| **Docs** | README, ADAPT_BEFORE_DEPLOY (or section), example tfvars; clear “change project_name and backend to avoid collisions.” |

---

## Execution order

Execute steps in order: **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9**. Steps 3 and 4 can be partially parallelized (Lambda handlers and core/orchestrator) but the chat Lambda depends on core/agent and orchestrator, so complete Step 4 before finalizing Step 3 and Step 5.
