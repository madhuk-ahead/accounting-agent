#!/usr/bin/env python3
"""POST a minimal but non-empty OTLP metrics payload (like the real SDK).

The first version sent an empty protobuf (body length 0). Cloudflare often
returns a generic HTML 400 for empty POSTs — that is not the same error as
your app, which sends real batches.

Use the same env as the app (OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS).

Usage:
  export OTEL_EXPORTER_OTLP_ENDPOINT=\"https://otlp-gateway-....grafana.net/otlp\"
  export OTEL_EXPORTER_OTLP_HEADERS=\"Authorization=Basic $(echo -n 'ID:TOKEN' | base64)\"
  python scripts/debug_otlp_http_response.py

If you still get generic Cloudflare HTML 400, try HTTP/2 (Python OTLP uses HTTP/1.1 by default):
  pip install 'urllib3-future>=2.0'
Then run this script again.
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
    from opentelemetry import metrics as metrics_api
    from opentelemetry.exporter.otlp.proto.common.metrics_encoder import encode_metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.util.re import parse_env_headers

    base = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip().rstrip("/")
    if not base or "/v1/" in base:
        print("Set OTEL_EXPORTER_OTLP_ENDPOINT to base URL ending in /otlp only.", file=sys.stderr)
        return 1

    hdrs = parse_env_headers(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""), liberal=True)
    if not hdrs:
        print("Set OTEL_EXPORTER_OTLP_HEADERS.", file=sys.stderr)
        return 1

    reader = InMemoryMetricReader()
    mp = MeterProvider(
        resource=Resource.create({"service.name": "otlp-debug-probe"}),
        metric_readers=[reader],
    )
    metrics_api.set_meter_provider(mp)
    meter = metrics_api.get_meter("debug_otlp_http_response")
    meter.create_counter("debug.probe").add(1)
    metrics_data = reader.get_metrics_data()
    body = encode_metrics(metrics_data).SerializeToString()

    url = f"{base}/v1/metrics"
    r = requests.post(
        url,
        data=body,
        headers={
            **hdrs,
            "Content-Type": "application/x-protobuf",
            "User-Agent": "debug_otlp_http_response/2",
        },
        timeout=60,
    )
    print(f"POST {url}\nBody size: {len(body)} bytes\nHTTP {r.status_code} {r.reason}")
    if r.text:
        print("Body:", r.text[:4000])
    if r.status_code == 400 and "cloudflare" in r.text.lower() and len(body) > 0:
        print(
            "\nStill a generic Cloudflare 400 with a non-empty OTLP body — often HTTP/1.1 vs HTTP/2. Try:\n"
            "  pip install 'urllib3-future>=2.0'\n"
            "Restart your app and re-run this script.",
            file=sys.stderr,
        )
    if r.status_code == 400 and "HTTP/1" in r.text and "HTTP/2" in r.text:
        print(
            "\nGateway requires HTTP/2 for OTLP. Install urllib3-future (see above).",
            file=sys.stderr,
        )
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
