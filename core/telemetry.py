"""OpenTelemetry bootstrap — call init_telemetry() before the app starts.

If OTEL_EXPORTER_OTLP_ENDPOINT is not set, telemetry is silently disabled
and the app runs with zero overhead.  All helper functions (get_tracer,
get_meter) return no-op implementations when telemetry is off.

Grafana Cloud auth is handled automatically by the OTel SDK, which reads
the OTEL_EXPORTER_OTLP_HEADERS environment variable
(e.g. "Authorization=Basic <base64>").
"""

from __future__ import annotations

import logging
import os
import sys


def _patch_otel_context_entrypoints_for_lambda() -> None:
    """OpenTelemetry resolves ``opentelemetry_context`` via importlib metadata entry points.
    Lambda zip bundles often omit ``*.dist-info``, so ``entry_points()`` returns empty and
    ``opentelemetry.context`` raises ``StopIteration`` at import time. Inject the default
    contextvars implementation when the registry is empty (only on Lambda).
    """
    if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return
    try:
        import opentelemetry.util._importlib_metadata as oim
    except Exception:
        return
    _orig = oim.entry_points

    def _patched(**params: object) -> object:
        if not params:
            return _orig()
        eps = _orig(**params)
        if len(eps) > 0:
            return eps
        group = params.get("group")
        name = params.get("name")
        if group == "opentelemetry_context" and name == "contextvars_context":
            try:
                from importlib_metadata import EntryPoint, EntryPoints
            except ImportError:
                from importlib.metadata import EntryPoint, EntryPoints

            ep = EntryPoint(
                name="contextvars_context",
                value="opentelemetry.context.contextvars_context:ContextVarsRuntimeContext",
                group="opentelemetry_context",
            )
            return EntryPoints([ep])
        return eps

    oim.entry_points = _patched  # type: ignore[assignment]
    if hasattr(oim, "_original_entry_points_cached"):
        oim._original_entry_points_cached.cache_clear()


_patch_otel_context_entrypoints_for_lambda()

from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

logger = logging.getLogger(__name__)

_initialized = False


def _ensure_otlp_headers_from_secrets_manager() -> None:
    """Lambda: Terraform sets GRAFANA_OTEL_SECRET_NAME; ECS injects OTEL_EXPORTER_OTLP_HEADERS directly."""
    if (os.getenv("OTEL_EXPORTER_OTLP_HEADERS") or "").strip():
        return
    secret_id = (os.getenv("GRAFANA_OTEL_SECRET_NAME") or "").strip()
    if not secret_id:
        return
    try:
        import boto3

        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("secretsmanager", region_name=region)
        resp = client.get_secret_value(SecretId=secret_id)
        raw = (resp.get("SecretString") or "").strip()
        if not raw:
            return
        if raw.startswith("{"):
            import json

            try:
                obj = json.loads(raw)
                if isinstance(obj, dict) and obj.get("OTEL_EXPORTER_OTLP_HEADERS"):
                    raw = str(obj["OTEL_EXPORTER_OTLP_HEADERS"])
            except json.JSONDecodeError:
                pass
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = raw
        logger.info("[OTEL] Loaded OTEL_EXPORTER_OTLP_HEADERS from Secrets Manager secret %s", secret_id)
        print(f"[OTEL] Loaded OTLP auth from Secrets Manager: {secret_id}", file=sys.stderr)
    except Exception as e:
        logger.warning("[OTEL] Could not load OTLP headers from %s: %s", secret_id, e)
        print(f"[OTEL] ERROR: could not load OTLP headers from {secret_id}: {e}", file=sys.stderr)


def init_telemetry() -> None:
    """One-time OTel SDK setup.  Safe to call multiple times."""
    global _initialized
    if _initialized:
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "unnamed-agent")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    if not otlp_endpoint:
        logger.info("[OTEL] No OTEL_EXPORTER_OTLP_ENDPOINT set — telemetry disabled")
        print("[OTEL] OTLP disabled: OTEL_EXPORTER_OTLP_ENDPOINT not set", file=sys.stderr)
        _initialized = True
        return

    _ensure_otlp_headers_from_secrets_manager()
    if not (os.getenv("OTEL_EXPORTER_OTLP_HEADERS") or "").strip():
        logger.warning(
            "[OTEL] OTEL_EXPORTER_OTLP_HEADERS empty — OTLP exports will fail. "
            "Set env or GRAFANA_OTEL_SECRET_NAME (Lambda) / ECS secret."
        )
        print(
            "[OTEL] WARNING: OTEL_EXPORTER_OTLP_HEADERS is empty; Grafana will reject exports (401).",
            file=sys.stderr,
        )

    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            "deployment.environment": os.getenv("ENVIRONMENT", "dev"),
            "service.version": os.getenv("SERVICE_VERSION", "0.1.0"),
        }
    )

    # --- Traces (OTLP/HTTP for Grafana Cloud compatibility) ---
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(tracer_provider)

    # --- Metrics (OTLP/HTTP) ---
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

    # Lambda: shorter interval + flush at end of handler; ECS can use default interval.
    _export_ms = 3_000 if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else 15_000
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{otlp_endpoint}/v1/metrics"),
        export_interval_millis=_export_ms,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    # --- Auto-instrumentation (FastAPI only where an app exists; Lambda handlers are not FastAPI) ---
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

    if not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
    BotocoreInstrumentor().instrument()

    _initialized = True
    logger.info("[OTEL] Telemetry initialized — service=%s endpoint=%s", service_name, otlp_endpoint)
    print(
        f"[OTEL] initialized service_name={service_name!r} deployment.environment={os.getenv('ENVIRONMENT', 'dev')!r} "
        f"endpoint={otlp_endpoint!r} headers={'set' if (os.getenv('OTEL_EXPORTER_OTLP_HEADERS') or '').strip() else 'MISSING'}",
        file=sys.stderr,
    )


def flush_telemetry(timeout_millis: int = 10_000) -> None:
    """Export pending OTLP metrics and traces. Call at the end of short-lived workers (e.g. AWS Lambda)."""
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
        return
    try:
        mp = metrics.get_meter_provider()
        if hasattr(mp, "force_flush"):
            mp.force_flush(timeout_millis=timeout_millis)
        tp = trace.get_tracer_provider()
        if hasattr(tp, "force_flush"):
            tp.force_flush(timeout_millis=timeout_millis)
        print(
            f"[OTEL] flush ok service_name={os.getenv('OTEL_SERVICE_NAME', '')!r}",
            file=sys.stderr,
        )
    except Exception as e:
        logger.warning("[OTEL] flush failed: %s", e)
        print(f"[OTEL] ERROR flush failed: {e!r}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Convenience helpers — safe to call even when telemetry is disabled
# (the global providers return no-op tracers / meters by default).
# ---------------------------------------------------------------------------


def get_tracer(name: str = __name__) -> trace.Tracer:
    """Return a tracer from the global TracerProvider."""
    return trace.get_tracer(name)


def get_meter(name: str = __name__) -> metrics.Meter:
    """Return a meter from the global MeterProvider."""
    return metrics.get_meter(name)
