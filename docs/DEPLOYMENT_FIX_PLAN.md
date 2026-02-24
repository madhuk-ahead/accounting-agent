# Plan to Fix Current Deployment (StopIteration / OpenTelemetry in Lambda)

**Implemented:** The template now uses a **Strands-AHEAD** Lambda layer (built from `strands-ahead-package/` wheel or via `strands_layer_arn`). See [STRANDS_AHEAD_STEP_BY_STEP_PLAN.md](STRANDS_AHEAD_STEP_BY_STEP_PLAN.md) for the execution steps.

This plan is based on **CloudWatch log analysis** for the chat Lambda and the **package/layer comparison** in [STRANDS_LAYER_AND_OPENAI.md](STRANDS_LAYER_AND_OPENAI.md).

---

## 1. What the Logs Show

### 1.1 Failure is at import time, not during streaming

CloudWatch logs for `/aws/lambda/agent-tmpl-dev-chat` show:

- **First error line**: `Failed to load context: contextvars_context, fallback to contextvars_context` in **`/opt/python/opentelemetry/context/__init__.py`**, line 46: `return next(...)` → **StopIteration**.
- **Stack trace** (simplified):
  1. `chat.py` → `agent_manager.run(...)`
  2. `core/agent.py` → `get_orchestrator(self.settings, session_id=...)`
  3. `core/orchestrators/factory.py` → `from .strands_orchestrator import StrandsOrchestrator`
  4. `core/orchestrators/strands_orchestrator.py` line 13 → **`from strands import Agent, tool`**
  5. `/opt/python/strands/__init__.py` → `from . import agent, models, telemetry, types`
  6. `/opt/python/strands/agent/__init__.py` → imports event_loop
  7. `/opt/python/strands/event_loop/event_loop.py` line 16 → **`from opentelemetry import trace as trace_api`**
  8. `/opt/python/opentelemetry/context/__init__.py` → `_RUNTIME_CONTEXT = _load_runtime_context()` → `return next(...)` → **StopIteration**

So the agent **never runs**. The failure happens as soon as the Lambda tries to load the Strands orchestrator, which imports `strands`, which imports **OpenTelemetry**. In the Lambda runtime (Python 3.11, constrained context), OpenTelemetry’s context loader raises **StopIteration**, which then propagates up and is reported as `[CHAT] ERROR: StopIteration()`.

### 1.2 Why this matches “different packages”

From [STRANDS_LAYER_AND_OPENAI.md](STRANDS_LAYER_AND_OPENAI.md):

- **empty_agent_template** (current): Lambda layer is built from **PyPI `strands-agents`**. That package **depends on and imports OpenTelemetry** (e.g. `opentelemetry-api`, `opentelemetry-context`). So `/opt/python` contains full `opentelemetry`, which fails in Lambda when loading context.
- **secunit_agent**: Lambda layer is built from **Strands-AHEAD** (local `strands-ahead-package` wheel). Strands-AHEAD is **API-compatible** with Strands but **removes or no-ops OpenTelemetry**. So in secunit, importing `strands` does **not** trigger the opentelemetry context code path, and the Lambda runs successfully.

So the deployment issue is **not** streaming logic or StopIteration inside our code; it is **which Strands package is in the layer**. PyPI Strands + OpenTelemetry in Lambda → import-time StopIteration. Strands-AHEAD (no active OTEL) → no failure.

---

## 2. Root cause summary

| Item | Detail |
|------|--------|
| **Symptom** | User sees "Error: StopIteration()" for every chat message. |
| **Where** | During **import** of `strands` in the chat Lambda, before any agent run. |
| **Technical cause** | PyPI `strands-agents` pulls in `opentelemetry`; `opentelemetry/context/__init__.py` raises StopIteration in Lambda’s runtime when loading context. |
| **Why other agents work** | secunit_agent uses **Strands-AHEAD** in the layer (no active OpenTelemetry). data_auto_engineer may use the same shared layer or a PyPI layer in an environment where this OTEL bug does not manifest. |

---

## 3. Fix strategy: use Strands-AHEAD in the layer

To fix the current deployment we should **provide the chat Lambda with a Strands layer that does not pull in active OpenTelemetry** — i.e. use **Strands-AHEAD** in the same way as secunit_agent.

Two concrete options:

- **Option A – Use existing shared layer (fastest)**  
  If there is already a Lambda layer in the account that contains Strands-AHEAD (e.g. the one secunit or data_auto_engineer use), use it:
  - Set **`strands_layer_arn`** in Terraform (e.g. in a tfvars file or variable) to that layer’s ARN.
  - Run `terraform apply` so the chat Lambda uses that layer instead of the current PyPI-based one.
  - No need to build or copy strands-ahead-package in this repo.

- **Option B – Build Strands-AHEAD layer in this repo**  
  If no shared layer is available or we want this repo to be self-contained:
  - Add (or reference) the **strands-ahead-package** (e.g. as submodule, copy, or path) and ensure a built wheel `strands_ahead-*.whl` is present.
  - Add a layer build script (e.g. under `infra/layers/strands_ahead/`) that:
    - Uses Docker (Python 3.11, linux/amd64) to install the Strands-AHEAD wheel into a `python/` directory.
    - Zips that directory and produces `infra/layers/artifacts/strands-ahead-layer.zip`.
  - Keep Terraform creating the layer from that zip (or optionally publish and reference by ARN).
  - Ensure the **chat Lambda** (and any other Lambda that imports Strands) uses this new layer and **does not** use the current PyPI-based strands layer.

Recommendation: prefer **Option A** if a suitable shared layer exists; otherwise implement **Option B**.

---

## 4. Step-by-step plan

### Phase 1: Confirm and choose layer source

1. **Confirm shared layer availability**
   - Check with the team or in the AWS account for an existing Lambda layer that contains Strands-AHEAD (e.g. same ARN as in secunit’s `strands_layer_arn` in prod/dev tfvars).
   - If yes → use **Option A** (steps 4.2–4.4 below).
   - If no → use **Option B** (steps 4.5–4.8 below).

2. **Optional: Re-check logs after any future deploy**
   - Log group: `/aws/lambda/agent-tmpl-dev-chat` (or the actual chat function name).
   - Confirm that after the fix there are no more import-time errors from `opentelemetry/context/__init__.py` and that chat requests complete (or fail for different reasons, e.g. API key).

### Phase 2: Apply Option A (use existing Strands-AHEAD layer)

3. **Set `strands_layer_arn` in Terraform**
   - In `infra/variables.tf`, `strands_layer_arn` already exists and is optional.
   - Set it (e.g. in `infra/dev.tfvars` or via CLI) to the ARN of the shared Strands-AHEAD layer.
   - Example (from secunit):  
     `strands_layer_arn = "arn:aws:lambda:us-east-1:740315635748:layer:data-engineering-agent-strands-ahead:8"`  
     (Use the correct account/region/name/version for your environment.)

4. **Apply Terraform**
   - Run `terraform init` and `terraform plan` in `infra/` to confirm the chat Lambda’s layers change to use the provided ARN (and no new layer is created from the local zip).
   - Run `terraform apply` so the chat Lambda uses the Strands-AHEAD layer.

5. **Smoke test**
   - Open the frontend, connect, send a message (e.g. “Test” or “recall the weather record”).
   - Expect no “Error: StopIteration()”. If the rest of the stack is correct, expect a normal agent reply or a clear error (e.g. missing key) that can be fixed separately.

### Phase 2 (alternative): Apply Option B (build Strands-AHEAD layer in repo)

6. **Obtain strands-ahead-package**
   - Get the Strands-AHEAD package (e.g. clone/copy the same repo or directory secunit uses: `strands-ahead-package`).
   - Place it so the build script can find it (e.g. `empty_agent_template/strands-ahead-package/` or a path referenced by the script).
   - Build the wheel: e.g. `pip wheel .` or the package’s build instructions, so that `strands_ahead-*.whl` exists.

7. **Add layer build script**
   - Create a script (e.g. `infra/layers/strands_ahead/build_layer.sh`) modeled on secunit’s:
     - Use Docker with Python 3.11, linux/amd64 (Lambda runtime).
     - Install the Strands-AHEAD wheel into a `python/` directory (e.g. `pip install strands_ahead-*.whl --target python`).
     - Zip that directory and output to `infra/layers/artifacts/strands-ahead-layer.zip`.
   - Ensure the zip layout is correct for Lambda (packages under `python/` so they appear under `/opt/python`).
   - Do **not** install PyPI `strands-agents` in this layer; only Strands-AHEAD.

8. **Build and deploy**
   - Run the new build script to produce `infra/layers/artifacts/strands-ahead-layer.zip`.
   - Leave `strands_layer_arn` unset (or null) so Terraform creates/updates the layer from this zip.
   - Run `terraform apply` so the chat Lambda uses the new layer.
   - Smoke test as in step 5.

### Phase 3: Align streaming/error handling (already planned)

9. **Optional but recommended: align orchestrator with secunit/data_auto_engineer**
   - Wrap the full `async for event in self._agent.stream_async(prompt):` loop in `try/except Exception`, use `collected_events`, and use the same event extraction (including `"data"` accumulation and fallback from last events) as in secunit and data_auto_engineer.
   - This avoids leaking other runtime or SDK exceptions to the user as generic errors and improves robustness. It does **not** fix the current import-time StopIteration; that is fixed only by using the Strands-AHEAD layer.

### Phase 4: Documentation and operations

10. **Update docs**
    - In [STRANDS_LAYER_AND_OPENAI.md](STRANDS_LAYER_AND_OPENAI.md), add a short “Current deployment” note: template uses Strands-AHEAD layer (shared or self-built) to avoid OpenTelemetry StopIteration in Lambda.
    - In [ADAPT_BEFORE_DEPLOY.md](../infra/ADAPT_BEFORE_DEPLOY.md) (or equivalent), state that the Strands layer **must** be Strands-AHEAD (or a layer that does not pull in active OpenTelemetry), and reference either the shared layer ARN or the local build steps.

11. **Runbook**
    - Add a one-line runbook: “Chat returns StopIteration → confirm chat Lambda uses Strands-AHEAD layer (not PyPI strands-agents with OTEL). Check CloudWatch for traceback in `opentelemetry/context/__init__.py`.”

---

## 5. What not to do

- **Do not** try to fix this only by catching StopIteration in our orchestrator or chat handler. The exception happens during **import**, before any of our turn logic runs. Catching it later would only hide the symptom; the Lambda would still fail on the first import.
- **Do not** rely on “fixing” OpenTelemetry inside the current layer (e.g. patching context) unless you own and maintain that layer; it is fragile and version-dependent.
- **Do not** remove the OpenAI or other layers; only replace the **Strands** layer content (PyPI strands-agents → Strands-AHEAD). API key and OpenAI usage stay as documented in [STRANDS_LAYER_AND_OPENAI.md](STRANDS_LAYER_AND_OPENAI.md).

---

## 6. Success criteria

- Chat Lambda starts and imports `strands` without raising StopIteration.
- CloudWatch logs for the chat Lambda show no traceback in `opentelemetry/context/__init__.py`.
- User can send a message and receive either an agent reply or a clear, non-StopIteration error (e.g. missing API key, DynamoDB, etc.).
- Template doc and runbook state that the Strands layer must be Strands-AHEAD (or equivalent) for Lambda.

---

## 7. References

- **Logs**: CloudWatch log group `/aws/lambda/agent-tmpl-dev-chat`, streams `2026/02/24/[$LATEST]...` (and newer).
- **Package/layer comparison**: [STRANDS_LAYER_AND_OPENAI.md](STRANDS_LAYER_AND_OPENAI.md).
- **secunit layer build**: `secunit_agent/infra/layers/strands_ahead/build_layer.sh`.
- **secunit tfvars**: `secunit_agent/infra/dev.tfvars` (example `strands_layer_arn`).
