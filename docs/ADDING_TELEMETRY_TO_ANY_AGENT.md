# Adding OpenTelemetry to Any AHEAD Agent

A general-purpose guide for adding tracing and metrics to any Python/FastAPI agent repo, exporting to Grafana Cloud. Written so that any agent built from our templates gets consistent telemetry that rolls up into the shared **AHEAD Agent Overview** dashboard.

---

## What You Get

After following this guide, your agent will emit:

| Signal | What's captured | Where it lands |
|---|---|---|
| **Traces** | Every HTTP request, WebSocket session, conversation turn, LLM call (with token counts), tool invocation, and AWS SDK call | Grafana Tempo |
| **Metrics** | Session count, turn count, LLM call count, LLM latency histogram, token usage histogram, tool call count | Grafana Mimir (PromQL-queryable) |

All agents share the same metric names and span conventions, so they show up side-by-side on the shared dashboard filtered by `service_name`.

---

## Prerequisites (One-Time Setup)

These only need to be done once across all agents:

1. **Grafana Cloud account** — Free tier at `grafana.com/auth/sign-up`
2. **OTLP gateway URL** — Found in your Grafana Cloud stack settings (e.g. `https://otlp-gateway-prod-us-east-3.grafana.net/otlp`)
3. **API token** — Generate in Grafana Cloud with scopes `traces:write`, `metrics:write`, `logs:write`
4. **Secrets Manager secret** — Store the auth header as a secret:

```bash
INSTANCE_ID="your-instance-id"
TOKEN="your-api-token"
AUTH=$(echo -n "${INSTANCE_ID}:${TOKEN}" | base64)
aws secretsmanager create-secret \
  --name grafana-otel-token \
  --secret-string "Authorization=Basic ${AUTH}" \
  --region us-east-1
```

If you already did this for another agent, reuse the same secret — all agents can share it.

---

## Transport: minimal template vs. difficult networks

The steps below use **OTLP/HTTP** (`http/protobuf`) and the **five OpenTelemetry packages** only. That is the right default for **ECS Fargate / Linux** in AWS: TLS and DNS behave predictably.

**Local macOS**, **VPN**, or **TLS inspection** (e.g. Zscaler) often need extra pieces:

| Topic | What to add |
|--------|-------------|
| TLS to OTLP on Mac / custom roots | `truststore`, `certifi`; HTTP exporters use the OS trust store after `truststore.inject_into_ssl()` (see this repo’s `core/telemetry.py`). |
| Cloudflare / HTTP 400 on OTLP POST | Try `urllib3-future` (HTTP/2 for `requests`) or switch to **gRPC** (below). |
| OTLP over **gRPC** | `opentelemetry-exporter-otlp-proto-grpc`, `grpcio`; set `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`. This repo maps `…/otlp` to `https://host:443` and merges **certifi** (+ optional macOS / extra PEM) for gRPC TLS in `core/otlp_grpc_ssl.py`. |
| gRPC **IPv6** timeout on laptop | Python’s DNS patch does **not** affect gRPC’s C++ resolver. Map the OTLP **hostname** to its **IPv4 A record** in `/etc/hosts` (see `scripts/debug_otlp_grpc.py` output). Do **not** dial OTLP by raw IP (breaks ALPN/HTTP2). |
| Corporate CA | `OTEL_EXPORTER_OTLP_CERTIFICATE` or `OTEL_EXTRA_CA_CERTS` pointing at a PEM bundle. |

**Scripts in this repo:** `scripts/verify_otlp.py` (HTTP auth), `scripts/debug_otlp_grpc.py` (gRPC probe).

For **AWS Lambda**, keep the same env vars; headers can be loaded from Secrets Manager via `GRAFANA_OTEL_SECRET_NAME` (implemented in this repo’s `core/telemetry.py`).

---

## Step-by-Step Implementation

### Step 1: Add Dependencies

Append to your `requirements.txt`:

```
# OpenTelemetry
opentelemetry-api>=1.25.0
opentelemetry-sdk>=1.25.0
opentelemetry-exporter-otlp-proto-http>=1.25.0
opentelemetry-instrumentation-fastapi>=0.46b0
opentelemetry-instrumentation-botocore>=0.46b0
```

These are the same five packages for every agent in the **baseline** template. The FastAPI instrumentor handles HTTP routes; the botocore instrumentor handles AWS SDK calls. If you hit the networking issues above, add the optional packages from the **Transport** section (this repo’s `requirements.txt` includes them).

---

### Step 2: Create `core/telemetry.py`

Copy this file into your `core/` directory. It should stay **functionally the same** across agents (same exporters, instrumentors, resource attributes). The **minimal** version below is enough for ECS + `http/protobuf`.

**This repository** ships an extended `core/telemetry.py` (truststore, optional gRPC, Secrets Manager header bootstrap, OTLP timeout default, `OTEL_EXPORTER_OTLP_HEADERS` warnings). New agents can start from the snippet below and port those extras only if needed.

---

```python
"""OpenTelemetry bootstrap — call init_telemetry() before the app starts.

If OTEL_EXPORTER_OTLP_ENDPOINT is not set, telemetry is silently disabled
and the app runs with zero overhead.
"""

from __future__ import annotations

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

logger = logging.getLogger(__name__)

_initialized = False


def init_telemetry() -> None:
    """One-time OTel SDK setup. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "unknown-agent")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    if not otlp_endpoint:
        logger.info("[OTEL] No OTEL_EXPORTER_OTLP_ENDPOINT set — telemetry disabled")
        _initialized = True
        return

    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            "deployment.environment": os.getenv("ENVIRONMENT", "dev"),
            "service.version": os.getenv("SERVICE_VERSION", "0.1.0"),
        }
    )

    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(tracer_provider)

    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{otlp_endpoint}/v1/metrics"),
        export_interval_millis=15_000,
    )
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[metric_reader])
    )

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

    FastAPIInstrumentor().instrument()
    BotocoreInstrumentor().instrument()

    _initialized = True
    logger.info("[OTEL] Telemetry initialized — service=%s endpoint=%s",
                service_name, otlp_endpoint)


def get_tracer(name: str = __name__) -> trace.Tracer:
    """Return a tracer from the global TracerProvider."""
    return trace.get_tracer(name)


def get_meter(name: str = __name__) -> metrics.Meter:
    """Return a meter from the global MeterProvider."""
    return metrics.get_meter(name)
```

**Key design**: When `OTEL_EXPORTER_OTLP_ENDPOINT` is not set, the entire module is a no-op. `get_tracer()` and `get_meter()` return no-op implementations. Your app runs identically with zero overhead. This means local development, tests, and any environment without Grafana configured works without changes.

---

### Step 3: Wire into `app/main.py`

Add two lines to your FastAPI app creation:

```python
from core.telemetry import init_telemetry

def create_app() -> FastAPI:
    init_telemetry()          # Must be before FastAPI() creation
    # ... rest of your app setup ...
```

Or if your `main.py` creates the app at module level:

```python
from core.telemetry import init_telemetry
init_telemetry()

app = FastAPI(...)
```

The auto-instrumentors (FastAPI + botocore) take effect immediately. Every HTTP route gets a span. Every `boto3` call (Secrets Manager, DynamoDB, S3, etc.) gets a span. No manual code needed for those.

---

### Step 4: Add Manual Spans to WebSocket Handlers

WebSocket connections are NOT auto-instrumented. Add manual spans:

```python
from opentelemetry import trace
from core.telemetry import get_tracer, get_meter

tracer = get_tracer("app.websocket")
meter = get_meter("app.websocket")

_sessions_counter = meter.create_counter("ws.sessions.total",
    description="Total WebSocket sessions")
_turns_counter = meter.create_counter("ws.turns.total",
    description="Total conversation turns")

async def your_websocket_handler(websocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    _sessions_counter.add(1)

    with tracer.start_as_current_span("ws.session",
            attributes={"session.id": session_id}) as session_span:
        try:
            # ... your greeting logic ...
            with tracer.start_as_current_span("ws.greeting",
                    attributes={"session.id": session_id}):
                greeting = await get_greeting(session_id)

            # ... your message loop ...
            turn = 0
            while True:
                user_msg = await websocket.receive_text()
                turn += 1
                _turns_counter.add(1)

                with tracer.start_as_current_span("ws.turn",
                        attributes={
                            "session.id": session_id,
                            "turn.number": turn,
                            "user.message_length": len(user_msg),
                        }):
                    response = await process_message(session_id, user_msg)

        except WebSocketDisconnect:
            session_span.set_attribute("disconnect.reason", "client")
        except Exception as e:
            session_span.set_status(trace.StatusCode.ERROR, str(e))
            session_span.record_exception(e)
```

Adapt this pattern to your specific WebSocket handler. The span names (`ws.session`, `ws.greeting`, `ws.turn`) and metric names (`ws.sessions.total`, `ws.turns.total`) must stay the same across all agents for the shared dashboard to work.

---

### Step 5: Add Spans Around LLM Calls

Wherever your code calls an LLM, wrap it:

```python
import time
from core.telemetry import get_tracer, get_meter

tracer = get_tracer("your.module")
meter = get_meter("your.module")

_llm_calls = meter.create_counter("llm.calls.total",
    description="Total LLM invocations")
_llm_latency = meter.create_histogram("llm.latency_ms",
    description="LLM call latency in milliseconds", unit="ms")
_llm_tokens = meter.create_histogram("llm.tokens.total",
    description="Total tokens per LLM call")

def call_llm_with_telemetry(client, messages, model="gpt-4o", temperature=0.7):
    """Wrap any LLM call with tracing and metrics."""
    with tracer.start_as_current_span("llm.invoke",
            attributes={"llm.model": model, "llm.temperature": temperature}
    ) as span:
        _llm_calls.add(1, {"llm.model": model})
        t0 = time.perf_counter()

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        _llm_latency.record(elapsed_ms, {"llm.model": model})

        usage = response.usage
        if usage:
            span.set_attribute("llm.prompt_tokens", usage.prompt_tokens)
            span.set_attribute("llm.completion_tokens", usage.completion_tokens)
            total = usage.prompt_tokens + usage.completion_tokens
            span.set_attribute("llm.total_tokens", total)
            _llm_tokens.record(total, {"llm.model": model})

        span.set_attribute("llm.latency_ms", round(elapsed_ms, 1))
        return response
```

**For the whiteboarding_agent specifically**, there are two patterns:

1. **Chat completions** (in `routers/writeup.py`, `rules.py`, `build_plan.py`, `cursor_prompt.py`, `diagram.py`): Each calls `openai.chat.completions.create()`. Wrap each with the pattern above.

2. **Realtime API** (in `openai_realtime_client.py`): This is a persistent WebSocket to OpenAI. Add a parent span for the entire realtime session and child spans for each audio chunk / response received. Token tracking may not be available via the Realtime API — record what you can (session duration, message count).

---

### Step 6: Add Spans Around Tool Calls

```python
from opentelemetry import trace
from core.telemetry import get_tracer, get_meter

tracer = get_tracer("your.tools")
meter = get_meter("your.tools")
_tool_calls = meter.create_counter("tool.calls.total",
    description="Total tool invocations")

def your_tool_function(**kwargs):
    with tracer.start_as_current_span("tool.your_tool_name",
            attributes={"tool.name": "your_tool_name"}
    ) as span:
        _tool_calls.add(1, {"tool.name": "your_tool_name"})
        try:
            result = do_the_work(**kwargs)
            span.set_attribute("tool.result_length", len(str(result)))
            return result
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise
```

---

### Step 7: Update Terraform

Add these variables to `infra/variables.tf`:

```hcl
variable "otel_endpoint" {
  description = "OTLP HTTP endpoint. Empty = telemetry disabled."
  type        = string
  default     = ""
}

variable "grafana_otel_secret_name" {
  description = "Secrets Manager secret with Grafana OTLP auth header."
  type        = string
  default     = ""
}
```

Add a conditional data source to `infra/secrets.tf`:

```hcl
data "aws_secretsmanager_secret" "grafana_otel" {
  count = var.grafana_otel_secret_name != "" ? 1 : 0
  name  = var.grafana_otel_secret_name
}
```

Update the container definition in `infra/ecs.tf` — add env vars and secrets:

```hcl
environment = concat([
  # ... your existing env vars ...
  { name = "ENVIRONMENT",                  value = var.environment },
  { name = "OTEL_SERVICE_NAME",            value = "${var.project_name}-${var.environment}" },
  { name = "OTEL_EXPORTER_OTLP_PROTOCOL", value = "http/protobuf" },
], var.otel_endpoint != "" ? [
  { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = var.otel_endpoint },
] : [])

secrets = var.grafana_otel_secret_name != "" ? [
  {
    name      = "OTEL_EXPORTER_OTLP_HEADERS"
    valueFrom = data.aws_secretsmanager_secret.grafana_otel[0].arn
  },
] : []
```

Update the ECS **execution role** in `infra/iam.tf` to allow reading the Grafana secret:

```hcl
{
  Effect   = "Allow"
  Action   = ["secretsmanager:GetSecretValue"]
  Resource = concat(
    [your_existing_secret_arns],
    var.grafana_otel_secret_name != "" ?
      [data.aws_secretsmanager_secret.grafana_otel[0].arn] : []
  )
}
```

---

### Step 8: Deploy

```bash
# Build and push
docker build --platform linux/amd64 -t $ECR_URL:latest .
docker push $ECR_URL:latest

# Apply Terraform with OTel enabled
terraform apply \
  -var="environment=dev" \
  -var="otel_endpoint=https://otlp-gateway-prod-us-east-3.grafana.net/otlp" \
  -var="grafana_otel_secret_name=grafana-otel-token"

# Force new deployment
aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment
```

---

## Standard Metric and Span Names

Use these exact names in every agent. The shared dashboard depends on them.

### Metrics (counters and histograms)

| Metric name | Type | Labels | Description |
|---|---|---|---|
| `ws.sessions.total` | Counter | — | WebSocket sessions opened |
| `ws.turns.total` | Counter | — | Conversation turns (user→agent round trips) |
| `llm.calls.total` | Counter | `llm.model` | LLM API invocations |
| `llm.latency_ms` | Histogram | `llm.model` | LLM call latency in ms |
| `llm.tokens.total` | Histogram | `llm.model` | Total tokens per LLM call |
| `tool.calls.total` | Counter | `tool.name` | Tool/function invocations |

### Span names

| Span name | Where | Attributes |
|---|---|---|
| `ws.session` | WebSocket handler | `session.id` |
| `ws.greeting` | Initial agent message | `session.id` |
| `ws.turn` | Each user→agent turn | `session.id`, `turn.number`, `user.message_length` |
| `llm.invoke` | Each LLM call | `llm.model`, `llm.temperature`, `llm.prompt_tokens`, `llm.completion_tokens`, `llm.total_tokens`, `llm.latency_ms` |
| `tool.<name>` | Each tool execution | `tool.name`, `tool.result_length` |

### Resource attributes (set via env vars)

| Env var | Maps to | Example |
|---|---|---|
| `OTEL_SERVICE_NAME` | `service.name` / `service_name` | `whiteboarding-dev` |
| `ENVIRONMENT` | `deployment.environment` / `deployment_environment` | `dev` |

The `service_name` label is what the dashboard uses to distinguish agents. Each agent gets a unique `OTEL_SERVICE_NAME` via Terraform: `${var.project_name}-${var.environment}`.

---

## Shared Dashboard

Import `dashboards/agent-overview.json` from the `empty_agent_template_langgraph` repo into Grafana Cloud. It has:

- **Top row**: Total sessions, turns, LLM calls, tool calls (big number stats)
- **Sessions & Turns**: Over time by agent (stacked bars), pie charts, avg turns per session
- **LLM Usage**: Calls over time, by model, latency percentiles (p50/p95/p99), avg tokens per call
- **Tool Calls**: Over time by agent, by tool name

All panels filter by the **Agent** and **Environment** dropdowns at the top. As you add more agents, they automatically appear in the dropdown.

The dashboard data source is `grafanacloud-kurtboden-prom`. If your Grafana Cloud Prometheus data source has a different UID, update the `"uid": "${ds}"` references and the `ds` template variable default.

---

## Applying to whiteboarding_agent

The whiteboarding_agent has the same FastAPI + ECS Fargate architecture, so the pattern is identical. Specific notes:

| Component | What to do |
|---|---|
| `requirements.txt` | Add the same 5 OTel packages |
| `core/telemetry.py` | Copy the file as-is |
| `app/main.py` | Add `init_telemetry()` at the top of `create_app()` |
| `app/whisper_ws.py` | Add `ws.session` and `ws.turn` spans around the WebSocket handler. The Whisper handler proxies to OpenAI Realtime — wrap the outer session and each response-back-to-user in spans. |
| `app/openai_realtime_client.py` | Optional: add a span for the Realtime API WebSocket session duration |
| `app/routers/writeup.py` | Wrap the `openai.chat.completions.create()` call with `llm.invoke` span and metrics |
| `app/routers/rules.py` | Same pattern |
| `app/routers/build_plan.py` | Same pattern |
| `app/routers/cursor_prompt.py` | Same pattern |
| `app/routers/diagram.py` | Wrap the GPT-4o call with `llm.invoke` span; add a separate `tool.eraser_diagram` span for the Eraser.io API call |
| `infra/variables.tf` | Add `otel_endpoint` and `grafana_otel_secret_name` |
| `infra/ecs.tf` | Add OTel env vars and secrets block |
| `infra/iam.tf` | Add Grafana secret to execution role |

The `OTEL_SERVICE_NAME` for the whiteboarding agent would be set to something like `whiteboarding-${var.environment}` so it appears as a separate entry in the dashboard.

---

## Checklist for Adding Telemetry to a New Repo

- [ ] Add 5 OTel packages to `requirements.txt`
- [ ] Copy `core/telemetry.py` (identical across all repos)
- [ ] Add `init_telemetry()` call in `app/main.py` before app creation
- [ ] Add `ws.session`, `ws.greeting`, `ws.turn` spans to WebSocket handler(s)
- [ ] Add `ws.sessions.total` and `ws.turns.total` counter metrics
- [ ] Add `llm.invoke` spans around every LLM call with token tracking
- [ ] Add `llm.calls.total`, `llm.latency_ms`, `llm.tokens.total` metrics
- [ ] Add `tool.<name>` spans around tool/function calls
- [ ] Add `tool.calls.total` counter metric
- [ ] Add `otel_endpoint` and `grafana_otel_secret_name` to Terraform variables
- [ ] Add OTel env vars and secrets block to ECS container definition
- [ ] Add Grafana secret access to ECS execution role IAM policy
- [ ] Deploy with `otel_endpoint` and `grafana_otel_secret_name` set
- [ ] Verify traces in Grafana Cloud Explore → Tempo
- [ ] Verify metrics in Grafana Cloud Explore → Prometheus
- [ ] Confirm agent appears in the shared dashboard dropdown
