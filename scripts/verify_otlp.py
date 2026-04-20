#!/usr/bin/env python3
"""Quick check that OTLP env vars can reach Grafana Cloud (auth + TLS).

Does not send real telemetry — POSTs an empty body to provoke a non-auth error
(400) instead of 401, proving the gateway accepted your credentials.

Usage (same vars as the app):
  export OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp-gateway-REGION.grafana.net/otlp"
  export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $(echo -n 'INSTANCE_ID:API_TOKEN' | base64)"
  python scripts/verify_otlp.py

Uses truststore for TLS (Zscaler-friendly on macOS).
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass

    import requests
    from opentelemetry.util.re import parse_env_headers

    base = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip().rstrip("/")
    if not base:
        print("Set OTEL_EXPORTER_OTLP_ENDPOINT (base URL ending in /otlp).", file=sys.stderr)
        return 1

    if "/v1/" in base:
        print(
            "OTEL_EXPORTER_OTLP_ENDPOINT should NOT include /v1/... — use the base …/otlp only.",
            file=sys.stderr,
        )
        return 1

    hdrs = parse_env_headers(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""), liberal=True)
    if not hdrs:
        print(
            "Set OTEL_EXPORTER_OTLP_HEADERS (Grafana Cloud → stack → OpenTelemetry / API keys).",
            file=sys.stderr,
        )
        return 1

    url = f"{base}/v1/traces"
    r = requests.post(
        url,
        headers={**hdrs, "Content-Type": "application/x-protobuf"},
        data=b"",
        timeout=30,
    )

    print(f"POST {url} -> HTTP {r.status_code}")
    if r.status_code == 401:
        print("401 Unauthorized: fix OTEL_EXPORTER_OTLP_HEADERS (wrong token or format).", file=sys.stderr)
        return 1
    if r.status_code == 403:
        print("403 Forbidden: token may lack OTLP write scope.", file=sys.stderr)
        return 1
    if r.status_code in (400, 415, 422, 500):
        print("Gateway responded (auth likely OK). Empty body often yields 400 — that is expected.")
        return 0
    if 200 <= r.status_code < 300:
        print("Success response (unexpected for empty body but OK).")
        return 0

    print(r.text[:500], file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
