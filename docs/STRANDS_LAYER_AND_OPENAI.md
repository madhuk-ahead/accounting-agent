# Strands Layer and OpenAI: How It Works (Same or Different)

This document explains how the **Strands layer** (“strands-ahead”) and **OpenAI API key / calls** work in **empty_agent_template** compared to **secunit_agent** and **data_auto_engineer**, and why they are the same or different.

---

## 1. What “Strands-AHEAD” Means

- **Strands** (upstream): The public [strands-agents](https://pypi.org/project/strands-agents/) Python SDK. Same API everywhere: `from strands import Agent, tool`, `strands.models.openai.OpenAIModel`, `agent.stream_async(...)`.
- **Strands-AHEAD**: An internal AHEAD fork of Strands. It is **API-compatible** with upstream (same `strands` import and usage) but removes or no-ops OpenTelemetry/telemetry. Used in production where you want the same agent behavior without OTEL.

So “implementing strands-ahead through the strands layer” can mean either:

- **Option A**: Use the **Strands-AHEAD fork** in the Lambda layer (like secunit_agent).
- **Option B**: Use **upstream strands-agents** from PyPI in the layer (like data_auto_engineer). Behavior is the same except telemetry is still present (unless Strands makes it optional). The empty_agent_template now uses Strands-AHEAD by default (Option A).

---

## 2. How Each Project Builds the Strands Layer

| Project               | Layer build source                    | How layer is produced                                                                 |
|-----------------------|----------------------------------------|----------------------------------------------------------------------------------------|
| **secunit_agent**     | **Strands-AHEAD** (local package)     | `infra/layers/strands_ahead/build_layer.sh` installs `strands_ahead-*.whl` from `strands-ahead-package/` into a `python/` dir, zips it. Layer exposes `strands` (drop-in). |
| **data_auto_engineer** | **PyPI strands-agents** (upstream)     | `make build-layers` runs Docker + `pip install strands-agents -t python/`, then zips.  |
| **empty_agent_template** | **Strands-AHEAD** (local wheel) or PyPI fallback | Place `strands_ahead-*.whl` in `strands-ahead-package/`, run `./infra/layers/strands_ahead/build_layer.sh` (or `./scripts/build_layers.sh`). Or set `strands_layer_arn` to use an existing layer. Template defaults to Strands-AHEAD so the chat Lambda avoids OpenTelemetry import errors. |

So:

- **secunit_agent** uses the **AHEAD fork** in the layer (Strands-AHEAD).
- **data_auto_engineer** may use **upstream strands-agents** from PyPI or a shared layer.
- **empty_agent_template** uses **Strands-AHEAD** in the layer (from `strands-ahead-package/` wheel or `strands_layer_arn`), so the chat Lambda avoids OpenTelemetry import errors.

If we want the template to use Strands-AHEAD “in the same way as” secunit_agent, we would need to:

- Add (or reference) **strands-ahead-package** and build the layer from the `strands_ahead-*.whl` wheel, similar to `secunit_agent/infra/layers/strands_ahead/build_layer.sh`, **or**
- Use a **shared Lambda layer** ARN that already contains Strands-AHEAD (e.g. the same layer secunit uses), and set `strands_layer_arn` in Terraform.

---

## 3. Why It Works the Same or Differently

- **API and code**: All three use the same **imports and usage**: `from strands import Agent, tool`, `from strands.models.openai import OpenAIModel`, `OpenAIModel(model_id=...)`, `agent.stream_async(prompt)`. So application code is the same.
- **Runtime behavior**: With **upstream strands-agents** (template + data_auto_engineer), the SDK may still pull in or reference OpenTelemetry. With **Strands-AHEAD** (secunit), that is removed or no-op’d. So the only behavioral difference is telemetry, not how the agent or OpenAI is called.
- **Lambda path**: Lambda loads layers into `/opt/python`. All three attach a “strands-ahead” (or equivalent) layer plus an openai layer. The function code does **not** bundle `strands` or `openai`; they come from the layers. So the **mechanism** (layers providing Strands + OpenAI) is the same; only the **content** of the Strands layer differs (fork vs PyPI).

---

## 4. OpenAI API Key: Flow and Comparison

### 4.1 Terraform / infrastructure (same idea everywhere)

- **Secret**: Stored in AWS Secrets Manager. Terraform does **not** create the secret; it only references it.
- **Variable**: `openai_api_key_secret_name` (default `"openai_api_key"`).
- **Lambda env**: Chat Lambda gets `OPENAI_API_KEY_SECRET = <secret name>` and has IAM permission to read that secret.

### 4.2 Where and when the key is loaded

| Project               | Where key is loaded                    | When                                      |
|-----------------------|----------------------------------------|-------------------------------------------|
| **secunit_agent**     | In **chat Lambda** before any agent code | If `OPENAI_API_KEY` not set: get secret, parse JSON or use plain string, set `os.environ["OPENAI_API_KEY"]`, then `get_settings.cache_clear()` so config sees it. |
| **data_auto_engineer** | In **chat Lambda** before running agent | `_get_openai_api_key()` returns secret string; Lambda passes it into `Settings(openai_api_key=api_key)`. (If secret is JSON, that helper should parse and extract `OPENAI_API_KEY`; see docs/operations.) |
| **empty_agent_template** | In **chat Lambda** before get_settings / agent | If `OPENAI_API_KEY` not set: get secret, parse JSON (`OPENAI_API_KEY` key) or use plain string, set `os.environ["OPENAI_API_KEY"]`, then optionally `get_settings.cache_clear()`. |

So:

- **secunit** and **empty_agent_template**: Key is loaded in Lambda, written to **env**, and config (e.g. `get_settings()`) reads `OPENAI_API_KEY` from env. Same pattern.
- **data_auto_engineer**: Key is loaded in Lambda and passed **explicitly** into `Settings(openai_api_key=api_key)`. No need to rely on env for the first run, but orchestrator still uses env when building `OpenAIModel` (see below).

### 4.3 How the orchestrator gets the key and calls OpenAI

All three do the same thing in the **orchestrator**:

- **Config**: `Settings` has `openai_api_key` (from env in template/secunit, or from constructor in data_auto_engineer).
- **Before creating the agent**: They set `os.environ["OPENAI_API_KEY"] = self.settings.openai_api_key` (if present).
- **Model**: `OpenAIModel(model_id=self.settings.openai_model)` (e.g. `gpt-4o`). Strands’ `OpenAIModel` uses the **environment variable** `OPENAI_API_KEY` when making HTTP calls to the OpenAI API.
- **Calls**: The actual OpenAI API calls are made **inside the Strands SDK** when the agent runs (e.g. `stream_async`). The application code does not call the OpenAI client directly; it just configures the model and runs the agent.

So: **API key and OpenAI usage are the same in practice** — key in env (or in settings then copied to env), OpenAIModel reads env, same model ID, same streaming flow.

---

## 5. Summary Table

| Aspect                    | secunit_agent              | data_auto_engineer           | empty_agent_template        |
|---------------------------|----------------------------|------------------------------|-----------------------------|
| **Strands layer source**  | Strands-AHEAD (local wheel)| PyPI strands-agents         | Strands-AHEAD (local wheel or shared ARN)        |
| **Import**                | `from strands import Agent`| Same                         | Same                        |
| **OpenAI model**          | `OpenAIModel(model_id=…)`  | Same                         | Same                        |
| **Key from Secrets Manager** | Yes, in Lambda          | Yes, in Lambda               | Yes, in Lambda             |
| **Key set in env**        | Yes                        | Via Settings → env in orchestrator | Yes                        |
| **Secret format**         | JSON or plain; extract `OPENAI_API_KEY` | Plain or JSON (should extract) | JSON or plain; extract `OPENAI_API_KEY` |

---

## 6. Recommendation: Aligning Template With “Strands-AHEAD” Like the Other Agents

- **data_auto_engineer** uses **PyPI strands-agents** in the layer (same as the template today). So for “same as data_auto_engineer,” no layer change is needed; only streaming/error handling and event extraction were aligned earlier.
- **secunit_agent** uses the **Strands-AHEAD fork** in the layer. To match that:
  1. **Option A**: Add a strands-ahead-package (or path to it) and a build script that installs `strands_ahead-*.whl` into `python/` and zips it, like secunit’s `infra/layers/strands_ahead/build_layer.sh`; **or**
  2. **Option B**: Use an existing shared layer that already contains Strands-AHEAD (e.g. the same ARN secunit uses) and set `strands_layer_arn` in Terraform so the template does not build its own Strands layer.

After that, **API key and OpenAI usage** can stay as they are: same secret name, same env, same `OpenAIModel(model_id=...)`, same `stream_async` flow. The only change is *what* is inside the Strands layer (fork vs PyPI).

---

## 7. References

- **secunit_agent**: `infra/layers/strands_ahead/build_layer.sh`, `lambda/chat.py` (key load), `core/orchestrators/strands_orchestrator.py` (OpenAIModel, env).
- **data_auto_engineer**: `Makefile` (build-layers), `lambda/chat.py` (`_get_openai_api_key`, Settings), `core/orchestrators/strands_orchestrator.py` (OpenAIModel, env).
- **empty_agent_template**: `scripts/build_layers.sh`, `lambda/chat.py` (key load), `core/orchestrators/strands_orchestrator.py` (OpenAIModel, env).
- **Strands-AHEAD**: `secunit_agent/docs/deployment/strands-ahead-layers.md`, `docs/implementation/strands-ahead-implementation.txt`.
