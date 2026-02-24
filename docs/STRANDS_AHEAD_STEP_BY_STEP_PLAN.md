# Step-by-Step Plan: Use Strands-AHEAD Layer (Copy Package from Secunit)

This plan updates the empty_agent_template codebase to use the **Strands-AHEAD** Lambda layer (instead of PyPI strands-agents) so the chat Lambda no longer hits the OpenTelemetry StopIteration at import time. Each step follows: **Investigate** → **Write temp step plan** → **Execute** → **Test** → **Clean up**.

**Reference:** [DEPLOYMENT_FIX_PLAN.md](DEPLOYMENT_FIX_PLAN.md), [STRANDS_LAYER_AND_OPENAI.md](STRANDS_LAYER_AND_OPENAI.md).

---

## Quick path (same AWS account as secunit)

If you can use the **existing Strands-AHEAD layer** from secunit/data_auto_engineer:

1. Set **`strands_layer_arn`** in Terraform (e.g. in `infra/dev.tfvars`) to the shared layer ARN (see secunit’s `infra/dev.tfvars`).
2. Build only the **openai** layer and the **chat Lambda** zip; run **terraform apply**. The chat Lambda will use the existing strands layer; no need to copy strands-ahead-package or build a wheel.

You can still do Steps 1–2 (copy package, add build script) so the repo is ready to build the Strands-AHEAD layer locally later (e.g. when a wheel is available).

---

## Overview of steps

| Step | Goal |
|------|------|
| 1 | Copy strands-ahead-package from secunit_agent and document wheel requirement |
| 2 | Add Strands-AHEAD layer build script (from secunit) and adapt for template |
| 3 | Update layer build entry point and ensure Terraform uses built layer |
| 4 | Build Strands-AHEAD layer, (re)build OpenAI layer, build chat Lambda, deploy |
| 5 | Test deployment (frontend chat, no StopIteration) |
| 6 | Optional: Align orchestrator streaming with secunit/data_auto_engineer |
| 7 | Final docs and cleanup |

---

## Step 1: Copy strands-ahead-package from secunit and document wheel

### 1.1 Investigate

- **secunit_agent:** Locate `strands-ahead-package` (repo root). Contents: `README.md`, `install.sh`; README references `strands_ahead-*.whl` (built wheel). No `.whl` is committed in the repo; the wheel is built or obtained elsewhere and placed there before running `build_layer.sh`.
- **empty_agent_template:** No `strands-ahead-package` today. Layer build is `scripts/build_layers.sh`, which uses PyPI `strands-agents` only.
- **Conclusion:** Copy the package directory for structure and docs; we will need a way to get a Strands-AHEAD wheel (build from Strands SDK fork, team artifact, or use shared layer ARN and skip building the strands layer).

### 1.2 Temp step plan (write to `docs/_step01_temp_plan.md`)

```markdown
# Step 01 temp plan
- Copy secunit_agent/strands-ahead-package/ to empty_agent_template/strands-ahead-package/
- Add docs/_step01_notes.md: where wheel comes from (secunit build, artifact, or use shared layer ARN).
- Do NOT add .whl to repo; add .gitignore entry for strands_ahead-*.whl if we later add wheel.
```

### 1.3 Execute

- Copy directory: `cp -r ../secunit_agent/strands-ahead-package ./strands-ahead-package` from empty_agent_template root (or equivalent).
- Add `strands-ahead-package/strands_ahead-*.whl` to `.gitignore` (so when a wheel is placed there it is not committed).
- Create `docs/_step01_notes.md`: "Strands-AHEAD wheel: obtain from secunit build or team artifact, or use Terraform variable strands_layer_arn to point to existing layer and skip building."

### 1.4 Test

- List `empty_agent_template/strands-ahead-package/`: should contain at least README.md, install.sh.
- Optional: if you have a wheel, place it there and run `pip install strands-ahead-package/strands_ahead-*.whl` locally to confirm it installs `strands`.

### 1.5 Clean up

- Delete `docs/_step01_temp_plan.md` after step is done.
- Keep `docs/_step01_notes.md` or merge into a single "Strands-AHEAD package" section in ADAPT or README; remove temp note once merged.

---

## Step 2: Add Strands-AHEAD layer build script (from secunit)

### 2.1 Investigate

- **secunit:** `infra/layers/strands_ahead/build_layer.sh`: expects `PROJECT_ROOT/strands-ahead-package` and `strands_ahead-*.whl` inside it; uses Docker (python:3.11, linux/amd64) to `pip install strands_ahead-*.whl --target python`; zips to `infra/layers/artifacts/strands-ahead-layer.zip`; verifies `python/strands` exists.
- **empty_agent_template:** `infra/layers/` exists; no `strands_ahead` subdir. `layers.tf` expects `layers/artifacts/strands-ahead-layer.zip` when `strands_layer_arn` is null. PROJECT_ROOT in secunit script is `SCRIPT_DIR/../../..` (three levels up from `infra/layers/strands_ahead`); in empty_agent_template the same path from `infra/layers/strands_ahead` would be repo root. So paths match if we use the same script layout.

### 2.2 Temp step plan (write to `docs/_step02_temp_plan.md`)

```markdown
# Step 02 temp plan
- Create empty_agent_template/infra/layers/strands_ahead/build_layer.sh.
- Copy from secunit and set PROJECT_ROOT to SCRIPT_DIR/../../.. (repo root).
- Keep STRANDS_AHEAD_PACKAGE_DIR="$PROJECT_ROOT/strands-ahead-package".
- Ensure script is executable.
- Document in infra/layers/README.md or ADAPT: run this script to produce strands-ahead-layer.zip when not using strands_layer_arn.
```

### 2.3 Execute

- Create `infra/layers/strands_ahead/` directory.
- Copy `secunit_agent/infra/layers/strands_ahead/build_layer.sh` to `empty_agent_template/infra/layers/strands_ahead/build_layer.sh`.
- Fix PROJECT_ROOT if needed: in template, `SCRIPT_DIR` = `infra/layers/strands_ahead`, so `SCRIPT_DIR/../../..` = repo root. Same as secunit. No change needed.
- `chmod +x infra/layers/strands_ahead/build_layer.sh`.
- Update `infra/layers/README.md` (or create it) to state: "To build Strands-AHEAD layer: place strands_ahead-*.whl in strands-ahead-package/ then run infra/layers/strands_ahead/build_layer.sh. Output: layers/artifacts/strands-ahead-layer.zip."

### 2.4 Test

- If a wheel is present in `strands-ahead-package/`: run `./infra/layers/strands_ahead/build_layer.sh` and confirm `infra/layers/artifacts/strands-ahead-layer.zip` exists and contains `python/strands/` (e.g. `unzip -l infra/layers/artifacts/strands-ahead-layer.zip | head -30`).
- If no wheel: script will fail with "No strands_ahead wheel file found"; that is expected. Document that user must obtain wheel or set strands_layer_arn.

### 2.5 Clean up

- Delete `docs/_step02_temp_plan.md`.

---

## Step 3: Update layer build entry point and Terraform

### 3.1 Investigate

- **empty_agent_template:** `scripts/build_layers.sh` builds both strands and openai from PyPI; writes to `infra/layers/artifacts/`. Terraform `layers.tf` uses `var.strands_layer_arn == null` to create layer from `layers/artifacts/strands-ahead-layer.zip`.
- **Goal:** When building locally, strands layer should come from the new build script (Strands-AHEAD wheel), not from PyPI. OpenAI layer can stay as-is (current script). So: either (a) change `build_layers.sh` to call the Strands-AHEAD build script for the strands layer and keep openai as-is, or (b) document two flows: "build strands: run infra/layers/strands_ahead/build_layer.sh; build openai: run scripts/build_layers.sh (openai only) or a dedicated openai build." Option (a) is simpler: build_layers.sh runs the Strands-AHEAD script first (if wheel present) then builds openai; if no wheel, print instructions to use strands_layer_arn or add wheel.

### 3.2 Temp step plan (write to `docs/_step03_temp_plan.md`)

```markdown
# Step 03 temp plan
- Update scripts/build_layers.sh: for strands, run infra/layers/strands_ahead/build_layer.sh instead of pip install strands-agents. If that script fails (e.g. no wheel), print a message and optionally skip strands zip (user must set strands_layer_arn).
- Keep openai build as-is in build_layers.sh.
- Ensure infra/layers/artifacts/ is created and both zips can coexist.
- Terraform: no change if layers.tf already uses artifacts/strands-ahead-layer.zip when strands_layer_arn is null.
```

### 3.3 Execute

- Edit `scripts/build_layers.sh`:
  - Replace the "Building strands-ahead layer" block with: run `infra/layers/strands_ahead/build_layer.sh` from repo root; if it fails, echo "Strands-AHEAD layer build failed (missing wheel?). Set strands_layer_arn in Terraform to use an existing layer, or add strands_ahead-*.whl to strands-ahead-package/ and re-run." Do **not** exit the script on strands failure so the openai build still runs.
  - Keep the openai layer build unchanged (always run it so openai-layer.zip exists).
- Ensure `infra/layers/artifacts` exists (script or mkdir in build_layer.sh already does this).
- Confirm `infra/layers.tf` still references `layers/artifacts/strands-ahead-layer.zip` when `var.strands_layer_arn == null`.

### 3.4 Test

- If wheel present: run `./scripts/build_layers.sh` and confirm both `strands-ahead-layer.zip` and `openai-layer.zip` exist under `infra/layers/artifacts/`.
- If no wheel: run script and confirm clear message; openai zip should still be built if that part runs after strands or if we run strands script and it fails we still run openai. (Adjust order so openai always builds; strands is optional when wheel missing.)

### 3.5 Clean up

- Delete `docs/_step03_temp_plan.md`.

---

## Step 4: Build layers, Lambda, and deploy

### 4.1 Investigate

- **Current build order:** Layers first (strands-ahead, openai), then Lambda zips (connect, disconnect, chat). Terraform apply uploads layer zips and chat zip.
- **Deploy:** terraform apply (with project_name, environment); then optionally force Lambda update if only code changed; ECS if frontend changed.
- **Wheel:** If no wheel in repo, use shared layer: set `strands_layer_arn` in tfvars to secunit’s layer ARN (e.g. from secunit infra/dev.tfvars), then only openai layer needs to be built; Terraform will not create a new strands layer.

### 4.2 Temp step plan (write to `docs/_step04_temp_plan.md`)

```markdown
# Step 04 temp plan
- Option A (shared layer): Set strands_layer_arn in infra/dev.tfvars (or equivalent). Build only openai layer (run build_layers.sh and let strands fail, or add a build-openai-only path). Build chat Lambda zip. terraform apply. Update Lambda code if needed (aws lambda update-function-code).
- Option B (self-built): Ensure wheel in strands-ahead-package. Run scripts/build_layers.sh. Build chat Lambda (python scripts/build_lambda_chat.py). cd infra && terraform apply. Update Lambda code if needed.
- After apply: smoke test frontend (open /agent/app, send message).
```

### 4.3 Execute

- **If using shared layer (recommended if same AWS account as secunit):**
  - Set in `infra/dev.tfvars`: `strands_layer_arn = "arn:aws:lambda:us-east-1:740315635748:layer:data-engineering-agent-strands-ahead:8"` (or correct ARN for your account/region).
  - Build openai layer only: run the openai section of `build_layers.sh` manually or add a target; ensure `openai-layer.zip` is in `infra/layers/artifacts/`.
  - Build chat Lambda: `python scripts/build_lambda_chat.py`.
  - `cd infra && terraform apply -var="project_name=agent-tmpl" -var="environment=dev" -auto-approve` (or use tfvars).
  - If Terraform does not update the chat Lambda (zip unchanged in its view), run `aws lambda update-function-code --function-name agent-tmpl-dev-chat --zip-file fileb://../dist/chat_lambda.zip`.
- **If building Strands-AHEAD locally:** Place wheel in strands-ahead-package, run `scripts/build_layers.sh`, then build chat Lambda, then terraform apply as above.

### 4.4 Test

- Open frontend URL (e.g. http://agent-tmpl-dev-frontend-alb-..../agent/app).
- Connect, send "Test" or "recall the weather record".
- Expect no "Error: StopIteration()". Expect agent reply or a different clear error (e.g. API key).
- Check CloudWatch log group for chat Lambda: no traceback in `opentelemetry/context/__init__.py`.

### 4.5 Clean up

- Delete `docs/_step04_temp_plan.md`.

---

## Step 5: Test deployment and verify logs

### 5.1 Investigate

- Log group: `/aws/lambda/<project>-<env>-chat` (e.g. `/aws/lambda/agent-tmpl-dev-chat`).
- Success: log stream shows "[CHAT] Invoked" and no StopIteration; may show agent run and final response or streaming.

### 5.2 Temp step plan (write to `docs/_step05_temp_plan.md`)

```markdown
# Step 05 temp plan
- Run through frontend test again; capture any error message.
- In AWS Console (or CLI): get recent log events for chat Lambda; confirm no opentelemetry/context in traceback.
- If still failing: capture full traceback and error message for next fix.
```

### 5.3 Execute

- Perform frontend test (connect, send message).
- Run: `aws logs get-log-events --log-group-name /aws/lambda/agent-tmpl-dev-chat --log-stream-name <latest> --limit 50` (or use Console).
- Confirm no `opentelemetry/context/__init__.py` in stack trace.

### 5.4 Test

- Same as 4.4; treat as pass when chat returns a reply or a non-StopIteration error.

### 5.5 Clean up

- Delete `docs/_step05_temp_plan.md`.

---

## Step 6: Optional — Align orchestrator streaming with secunit/data_auto_engineer

### 6.1 Investigate

- **secunit / data_auto_engineer:** Full `async for event in self._agent.stream_async(prompt):` wrapped in `try/except Exception`; use `collected_events`; extract final text from events (including `"data"` accumulation); on exception return OrchestratorResult with error message.
- **empty_agent_template:** Already has StopIteration handling and a simpler event loop; no collected_events, no broad Exception catch in _run_async_turn.

### 6.2 Temp step plan (write to `docs/_step06_temp_plan.md`)

```markdown
# Step 06 temp plan (optional)
- In strands_orchestrator.py: wrap async for loop in try/except Exception; accumulate events in collected_events; if final_text empty, scan collected_events (reversed) to extract text; on exception return OrchestratorResult(content=f"Error during streaming: {exc}").
- Add "data" handling in _extract_text_from_event and accumulate chunks (final_text += extracted) for streamed response.
- Keep OrchestratorResult(content=...) (no change to base class).
```

### 6.3 Execute

- Implement the try/except and collected_events logic in `core/orchestrators/strands_orchestrator.py` (see secunit/data_auto_engineer implementations).
- Add "data" key handling in `_extract_text_from_event` and accumulation in the loop.

### 6.4 Test

- Rebuild chat Lambda, update Lambda code, send messages; confirm no regression and that streaming/error messages are clearer if applicable.

### 6.5 Clean up

- Delete `docs/_step06_temp_plan.md`.

---

## Step 7: Final docs and cleanup

### 7.1 Investigate

- **Docs to update:** README (layer build instructions), ADAPT_BEFORE_DEPLOY (strands-ahead wheel or shared layer), DEPLOYMENT_FIX_PLAN (mark as implemented), STRANDS_LAYER_AND_OPENAI (note template now uses Strands-AHEAD).
- **Temp files:** Remove any remaining `docs/_step*_temp_plan.md` and `docs/_step*_notes.md` or merge into main docs.

### 7.2 Temp step plan (write to `docs/_step07_temp_plan.md`)

```markdown
# Step 07 temp plan
- Update README: layer build = run infra/layers/strands_ahead/build_layer.sh (with wheel) or set strands_layer_arn.
- Update infra/ADAPT_BEFORE_DEPLOY: Strands-AHEAD layer from wheel or shared ARN.
- Update DEPLOYMENT_FIX_PLAN: add "Implemented: template now uses Strands-AHEAD layer (see STRANDS_AHEAD_STEP_BY_STEP_PLAN)."
- Update STRANDS_LAYER_AND_OPENAI: empty_agent_template now uses Strands-AHEAD (built or shared).
- Delete all docs/_step*_temp_plan.md and docs/_step*_notes.md.
```

### 7.3 Execute

- Edit README, ADAPT_BEFORE_DEPLOY, DEPLOYMENT_FIX_PLAN, STRANDS_LAYER_AND_OPENAI as above.
- Delete temp step docs.

### 7.4 Test

- Quick read-through of README and ADAPT to ensure a new deployer can follow them.

### 7.5 Clean up

- Delete `docs/_step07_temp_plan.md`. Step 7 complete.

---

## Checklist summary

- [ ] Step 1: Copy strands-ahead-package; add .gitignore; document wheel/source.
- [ ] Step 2: Add infra/layers/strands_ahead/build_layer.sh; update layers README.
- [ ] Step 3: Update scripts/build_layers.sh to use Strands-AHEAD script for strands layer.
- [ ] Step 4: Build layers (+ chat Lambda), deploy (Terraform; use shared layer ARN or local wheel).
- [ ] Step 5: Test frontend and CloudWatch logs (no StopIteration).
- [ ] Step 6 (optional): Align orchestrator streaming with secunit/data_auto_engineer.
- [ ] Step 7: Update main docs; remove temp step docs.

---

## References

- secunit_agent: `strands-ahead-package/`, `infra/layers/strands_ahead/build_layer.sh`, `infra/dev.tfvars` (strands_layer_arn).
- empty_agent_template: `scripts/build_layers.sh`, `infra/layers.tf`, `docs/DEPLOYMENT_FIX_PLAN.md`, `docs/STRANDS_LAYER_AND_OPENAI.md`.
