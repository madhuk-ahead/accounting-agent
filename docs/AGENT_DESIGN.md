# Empty Agent Template — Agent Design

This document describes how the agent works in `empty_agent_template` so you can build tooling that automatically adapts the template (e.g., new persona, new tools, new datasource).

---

## 1. High-level architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────────────────────────────┐
│  Frontend       │ ◄─────────────────►│  API Gateway WebSocket API                │
│  (ECS / Fargate)│   wss://...        │  Routes: $connect, $disconnect, $default  │
│  Serves /app    │                    └───────────────┬──────────────────────────┘
└─────────────────┘                                   │
       │                                               │
       │ AGENT_WS_URL (env)                            │
       │ (injected at render)                          ▼
       │                                    ┌─────────────────────────────────────┐
       │                                    │  Lambda: connect → session in DDB    │
       │                                    │  Lambda: disconnect → (cleanup)     │
       │                                    │  Lambda: chat → AgentManager →       │
       │                                    │            StrandsOrchestrator       │
       │                                    └─────────────────┬───────────────────┘
       │                                                      │
       │                                                      │ reads
       │                                                      ▼
       │                                            ┌─────────────────┐
       │                                            │  DynamoDB        │
       │                                            │  - sessions      │
       │                                            │  - knowledge     │
       │                                            └─────────────────┘
       │
       │  (OpenAI key from Secrets Manager; chat Lambda only)
```

- **Frontend**: Single-page chat UI. Connects to WebSocket URL, sends `{ action: "message", text, conversation }`, receives `{ type: "status"|"final"|"error", content }`.
- **WebSocket API**: Three routes; only the **$default** route carries chat messages and invokes the **chat** Lambda.
- **Chat Lambda**: Resolves session from connection, loads OpenAI key from Secrets Manager, calls **AgentManager**, streams status/final/error back over the same connection.
- **AgentManager**: Thin wrapper: parses transcript, calls **get_orchestrator()**, runs **orchestrator.run_turn()**, returns **RunResult** (message, buttons, conversation_id).
- **Orchestrator**: Single implementation today — **StrandsOrchestrator**. It builds a Strands **Agent** with a **system prompt**, **tools**, and **OpenAI model**, then runs one turn (streaming) and returns the final text.

---

## 2. End-to-end request flow

### 2.1 User sends a message

1. **Browser** sends over WebSocket:
   - `JSON.stringify({ action: "message", text: "Please recall the weather record", conversation: "USER: ...\nAGENT: ..." })`
2. **API Gateway** routes to **chat** Lambda (`$default`).
3. **Chat Lambda** (`lambda/chat.py`):
   - Reads `connectionId` from `event.requestContext`.
   - Looks up **session_id** from DynamoDB **sessions** table (GSI on `connection_id`).
   - Parses body → `user_text`, `conversation`.
   - Optionally loads **OPENAI_API_KEY** from Secrets Manager (if not set), then calls `get_agent_manager().run(conversation_id=session_id, user_text=..., transcript=conversation, on_stream_message=...)`.
4. **AgentManager** (`core/agent.py`):
   - Calls `get_orchestrator(settings, session_id)` → returns **StrandsOrchestrator**.
   - Converts `transcript` to `conversation_history`: list of `{ "role": "user"|"assistant", "content": "..." }` (lines starting with `USER:` / `AGENT:`).
   - Calls `orchestrator.run_turn(task_input=user_text, conversation_history=..., session_id=..., on_stream_message=...)`.
5. **StrandsOrchestrator** (`core/orchestrators/strands_orchestrator.py`):
   - If Strands not available (ImportError): returns fallback message.
   - Builds Strands **Agent** on first use: **system prompt** (constant `AGENT_SYSTEM_PROMPT`), **tools** from `_create_recall_tool(settings)` (single tool: `recall_weather_record`), **model** = OpenAI via `OpenAIModel(model_id=settings.openai_model)`.
   - Runs `agent.stream_async(user_message)`; for each event, calls `on_stream_message` and accumulates text via `_extract_text_from_event`.
   - Returns **OrchestratorResult(content=final_text)**.
6. **AgentManager** wraps that in **RunResult(message=..., buttons=[], conversation_id=...)**.
7. **Chat Lambda** sends over WebSocket:
   - During stream: `{ type: "status", content: "..." }`.
   - At end: `{ type: "final", content: result.message, buttons: [], conversation_id }`.
   - On error: `{ type: "error", content: "..." }`.

### 2.2 Session lifecycle

- **$connect** → **connect** Lambda: creates a new **session_id** (UUID), writes to DynamoDB **sessions** (`session_id`, `connection_id`, `created_at`, `last_activity`, `ttl`). Returns 200 with optional `X-Session-Id`.
- **$disconnect** → **disconnect** Lambda: can log or clean up; session row remains until TTL.
- **Chat** uses **session_id** only as `conversation_id`; the **orchestrator** does not persist conversation history to DynamoDB. History is sent from the client each time as `conversation` (transcript string).

---

## 3. Key components and where behavior is defined

| Component | File(s) | What it does | What is fixed vs adaptable |
|-----------|--------|---------------|-----------------------------|
| **System prompt** | `core/orchestrators/strands_orchestrator.py` | `AGENT_SYSTEM_PROMPT` constant | **Fixed** text; defines persona and when to use the tool. |
| **Tools** | Same file | `_create_recall_tool(settings)` → one `@tool` function `recall_weather_record()` | **Fixed**: one tool; reads DynamoDB **knowledge** table, item `id="polar-vortex-chicago"`. |
| **Knowledge schema** | DynamoDB table `knowledge` (hash `id`); seed in `scripts/seed_knowledge.py` | Single item: `id`, `title`, `content`, `updated_at`. | **Fixed** key `id` and demo item id; table name from env. |
| **Orchestrator choice** | `core/orchestrators/factory.py` | `get_orchestrator()` always returns `StrandsOrchestrator(settings, session_id)`. | **Fixed** (single implementation). |
| **Settings** | `core/config.py` | `Settings`: `openai_api_key`, `openai_model`, `aws_region`, `dynamodb_sessions_table`, `dynamodb_knowledge_table`, `templates_dir`, `static_dir`. | **Adaptable** via env vars (and optional tfvars for table names). |
| **Transcript format** | `core/agent.py` | `_parse_transcript()`: lines `USER: ...` → `role: user`, `AGENT: ...` → `role: assistant`. | **Fixed** format. |
| **WebSocket message contract** | `lambda/chat.py`, `frontend/static/js/app.js` | Body: `{ action, text, conversation }`. Response: `{ type: "status"|"final"|"error", content, ... }`. | **Fixed**; frontend and Lambda must stay in sync. |
| **Frontend copy** | `frontend/templates/base.html`, `app.js` | Title, placeholder, “recall the weather record”, etc. | **Fixed** in HTML/JS. |

---

## 4. Data flow summary

- **Sessions table**: `session_id` (PK), `connection_id` (GSI), `created_at`, `last_activity`, `ttl`. Used only to map WebSocket `connection_id` → `session_id` for the chat Lambda.
- **Knowledge table**: `id` (PK). Single use today: item `polar-vortex-chicago` with `title`, `content`, `updated_at`. The **recall_weather_record** tool does a `get_item(Key={"id": "polar-vortex-chicago"})` and returns that content.
- **Conversation history**: Not stored server-side. The client sends the full `conversation` string each time; the orchestrator receives it as `conversation_history` but the Strands agent is built with no persistent memory—each turn is effectively the latest user message plus whatever context the client sent.

---

## 5. Extension points for auto-adaptation

To build something that “automatically adapts” the template, these are the levers.

### 5.1 Persona and behavior (no new tools)

- **System prompt**: Replace `AGENT_SYSTEM_PROMPT` in `strands_orchestrator.py` (or load from config/file). This changes tone, topic, and instructions.
- **Frontend**: Update `frontend/templates/base.html` and any strings in `app.js` (title, placeholder, hints) to match the new persona.

### 5.2 Same pattern, different “knowledge” item

- **Knowledge table**: Keep schema `id`, `title`, `content` (and optional fields). Seed different items (e.g. different `id` and content).
- **Tool**: In `_create_recall_tool`, the DynamoDB key is hardcoded to `"polar-vortex-chicago"`. To adapt:
  - Make the **item id** configurable (env var or settings, e.g. `KNOWLEDGE_ITEM_ID`), or
  - Support multiple items (e.g. pass `id` as tool argument or from prompt/settings).
- **Seed script**: Parameterize `scripts/seed_knowledge.py` (e.g. accept `--id`, `--title`, `--content` or a JSON file) so the same script can seed different content.

### 5.3 New or additional tools

- **Tool definitions**: Today there is one tool in `strands_orchestrator.py`: `recall_weather_record`. To add tools:
  - Define new `@tool` functions (same file or a separate module).
  - Return a list of callables from a “tool factory” (e.g. `_create_tools(settings)`) and pass that list to `Agent(..., tools=...)`.
- **Strands** expects tools to be decorated with `@tool` and passed as a list; each can take arguments (and optionally context). The orchestrator’s `_build_agent()` must be updated to include the new tools.
- **System prompt** must be updated so the model knows when and how to call the new tools.

### 5.4 Different datasource (not DynamoDB knowledge table)

- **New tool**: Implement a different function that reads from another store (e.g. S3, RDS, API). Same pattern: `@tool`, return a dict (or structure the LLM can use).
- **Settings**: Add any needed config (bucket name, endpoint, etc.) to `Settings` and env.

### 5.5 Multiple agents or orchestrator types

- **Factory**: Today `get_orchestrator()` in `core/orchestrators/factory.py` always returns `StrandsOrchestrator`. To support multiple types:
  - Add a setting (e.g. `orchestrator_type` or `agent_type`) and branch in `get_orchestrator()` to return different orchestrator classes.
  - Each orchestrator implements `AgentOrchestrator`: `run_turn(task_input, conversation_history, session_id, on_stream_message, **kwargs)` returning `OrchestratorResult`.
- **AgentManager** does not need to change; it only uses `get_orchestrator()` and `run_turn()`.

### 5.6 Frontend and WebSocket contract

- **Contract**: Keep `action: "message"`, `text`, `conversation` on the wire; and `type: "status"|"final"|"error"`, `content` in responses. Then you can change only copy and styling.
- **WebSocket URL**: In production, frontend gets `ws_url` from the server; server gets it from `AGENT_WS_URL` (set by Terraform in ECS). So the URL is already environment-driven.
- For a new persona/domain, update the HTML/JS text and, if needed, add minimal UI (e.g. buttons) that still send the same `{ action, text, conversation }` and handle `status`/`final`/`error`.

### 5.7 Infrastructure and env

- **Terraform**: `project_name`, `environment`, `service_path`, `aws_region`, etc. Table names and Lambda env (e.g. `DYNAMODB_KNOWLEDGE_TABLE`, `OPENAI_API_KEY_SECRET`) are already parameterized.
- **Secrets**: OpenAI key in Secrets Manager; name from env. No code change needed for a new deploy if the secret name is the same or passed via env.

---

## 6. What an “auto-adapt” system could do

A tool that adapts the template could:

1. **Inputs**: Persona description, optional list of tools (e.g. “recall one knowledge item”, “search knowledge by query”), optional datasource config (e.g. one DynamoDB item id, or “same table, multiple items”).
2. **Prompt**: Generate or replace `AGENT_SYSTEM_PROMPT` from the persona (and tool descriptions).
3. **Tools**:  
   - Keep “recall one record” but parameterize the item id (and optionally table name) from config.  
   - Or generate a small set of tools (e.g. recall by id, list ids) with descriptions and wire them into `_create_tools` / `_build_agent`.
4. **Knowledge**: Generate or parameterize the seed script (or a one-off script) to populate the knowledge table with the right `id`/`title`/`content`.
5. **Frontend**: Replace or parameterize the title, subtitle, placeholder, and any “example” text in `base.html` and `app.js` to match the persona.
6. **Config**: Ensure `Settings` and env (or tfvars) carry any new keys (e.g. `KNOWLEDGE_ITEM_ID`, optional table name). No need to change the WebSocket or Lambda handler if the contract stays the same.

The design is already “one orchestrator, one agent per turn, tools + system prompt + OpenAI”; adaptation is mostly **replacing or parameterizing** the prompt, the tool set (and their backing data), and the frontend copy, plus optional factory branching for multiple orchestrator types.

---

## 7. File reference (agent-related)

| Purpose | File |
|--------|------|
| Entry from Lambda | `lambda/chat.py` |
| Agent entrypoint | `core/agent.py` (AgentManager, get_agent_manager, RunResult) |
| Orchestrator abstraction | `core/orchestrators/base.py` (AgentOrchestrator, OrchestratorResult) |
| Orchestrator factory | `core/orchestrators/factory.py` (get_orchestrator) |
| Strands implementation | `core/orchestrators/strands_orchestrator.py` (prompt, tools, run_turn) |
| Config | `core/config.py` (Settings, get_settings) |
| Session lookup | `lambda/chat.py` (_get_session_id_from_connection) |
| Session create | `lambda/connect.py` |
| Knowledge seed | `scripts/seed_knowledge.py` |
| Frontend UI | `frontend/templates/base.html`, `frontend/static/js/app.js` |
| WebSocket URL injection | `app/main.py` (AGENT_WS_URL), ECS task def in `infra/ecs.tf` |

This should be enough to implement an adapter that rewrites or generates the prompt, tools, seed data, and frontend text while leaving the rest of the stack unchanged.
