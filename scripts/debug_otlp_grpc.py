#!/usr/bin/env python3
"""Send a minimal OTLP metrics batch via gRPC (HTTP/2) — use when HTTP/protobuf gets Cloudflare 400.

Env (same as Grafana Cloud OTLP tile):
  export OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp-gateway-....grafana.net/otlp"
  export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $(echo -n 'ID:TOKEN' | base64)"

Optional:
  export OTEL_EXPORTER_OTLP_GRPC_ENDPOINT="https://otlp-gateway-....grafana.net:443"
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _etc_hosts_has_ipv4_for(hostname: str) -> bool:
    try:
        with open("/etc/hosts", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                if hostname not in parts[1:]:
                    continue
                try:
                    socket.inet_pton(socket.AF_INET, parts[0])
                    return True
                except OSError:
                    continue
    except OSError:
        pass
    return False


def _grpc_target(http_base: str) -> str:
    explicit = (os.getenv("OTEL_EXPORTER_OTLP_GRPC_ENDPOINT") or "").strip()
    if explicit:
        from urllib.parse import urlparse

        u = urlparse(explicit)
        return u.netloc or explicit.replace("https://", "").replace("http://", "")
    b = http_base.strip().rstrip("/")
    if "/otlp" in b:
        from urllib.parse import urlparse

        u = urlparse(b if "://" in b else f"https://{b}")
        if u.hostname:
            return f"{u.hostname}:443"
    from urllib.parse import urlparse

    u = urlparse(b if "://" in b else f"https://{b}")
    return u.netloc or b


def main() -> int:
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass

    import grpc
    from opentelemetry import metrics as metrics_api
    from opentelemetry.exporter.otlp.proto.common.metrics_encoder import encode_metrics
    from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2_grpc
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.util.re import parse_env_headers

    base = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip().rstrip("/")
    if not base or "/v1/" in base:
        print("Set OTEL_EXPORTER_OTLP_ENDPOINT to the HTTPS …/otlp base.", file=sys.stderr)
        return 1

    hdrs = parse_env_headers(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""), liberal=True)
    if not hdrs:
        print("Set OTEL_EXPORTER_OTLP_HEADERS.", file=sys.stderr)
        return 1
    auth = (hdrs.get("Authorization") or hdrs.get("authorization") or "").strip()
    if len(auth) < 24 or auth in ("Basic", "Basic%20", "Basic "):
        print(
            "OTEL_EXPORTER_OTLP_HEADERS must include a real Basic token. In bash use:\n"
            '  export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $(echo -n \'INSTANCE_ID:TOKEN\' | base64)"\n'
            "Do not use only Basic%20 (that is for .env URL-encoding, not a substitute for credentials).",
            file=sys.stderr,
        )
        return 1

    reader = InMemoryMetricReader()
    mp = MeterProvider(
        resource=Resource.create({"service.name": "otlp-grpc-debug"}),
        metric_readers=[reader],
    )
    metrics_api.set_meter_provider(mp)
    metrics_api.get_meter("debug_otlp_grpc").create_counter("debug.probe").add(1)
    req = encode_metrics(reader.get_metrics_data())

    from core.otlp_grpc_target import ensure_ipv4_dns_resolution

    ensure_ipv4_dns_resolution()
    target = _grpc_target(base)
    _ipv4_hint: str | None = None
    if ":" in target:
        _h, _, _p = target.rpartition(":")
        try:
            _infos = socket.getaddrinfo(_h, int(_p), socket.AF_INET, socket.SOCK_STREAM)
            _ip = _infos[0][4][0]
            _ipv4_hint = f'{_ip} {_h}'
            if not _etc_hosts_has_ipv4_for(_h):
                print(
                    "gRPC uses its own DNS (not Python). On many networks IPv6 to Grafana times out.\n"
                    "Add this line to /etc/hosts, then flush DNS (commands require sudo):\n"
                    f"  sudo sh -c 'echo \"{_ip} {_h}\" >> /etc/hosts'\n"
                    "  sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder\n",
                    file=sys.stderr,
                )
        except OSError:
            pass
    metadata = tuple((k.lower(), v) for k, v in hdrs.items())

    from core.otlp_grpc_ssl import channel_credentials

    creds = channel_credentials()
    channel = grpc.secure_channel(target, creds)
    try:
        stub = metrics_service_pb2_grpc.MetricsServiceStub(channel)
        stub.Export(req, metadata=metadata, timeout=60)
    except grpc.RpcError as e:
        print(f"gRPC Export to {target} -> {e.code()} {e.details()}")
        det = (e.details() or "").lower()
        if e.code() == grpc.StatusCode.UNAVAILABLE and (
            "ipv6" in det or "2600:" in det or "fd shutdown" in det or "timeout" in det
        ):
            if _ipv4_hint:
                print(
                    "\nIPv6 dial failed. gRPC ignores Python DNS settings — use /etc/hosts:\n"
                    f"  sudo sh -c 'echo \"{_ipv4_hint}\" >> /etc/hosts'\n"
                    "  sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder\n"
                    "Then run this script again.",
                    file=sys.stderr,
                )
        return 1
    finally:
        channel.close()

    print(f"gRPC Export to {target} -> OK (HTTP/2 path; use OTEL_EXPORTER_OTLP_PROTOCOL=grpc in the app)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
