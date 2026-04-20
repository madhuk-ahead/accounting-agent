"""Optional IPv4-only DNS hint for Python (does **not** change gRPC’s C++ resolver).

gRPC uses its own DNS (not Python’s ``getaddrinfo``). On networks where **IPv6
to Grafana times out**, add a line to ``/etc/hosts`` mapping the OTLP hostname
to its **IPv4 A record** (see ``scripts/debug_otlp_grpc.py`` output).

Dialing ``hostname`` as an IPv4 literal breaks ALPN — do not do that.

Set OTEL_GRPC_FORCE_IPV4=false to disable the Python ``getaddrinfo`` patch.
"""

from __future__ import annotations

import os
import socket

_gai_patch_installed = False


def ensure_ipv4_dns_resolution() -> bool:
    """Return True if the process-wide getaddrinfo IPv4-only patch is active."""
    global _gai_patch_installed
    if os.getenv("OTEL_GRPC_FORCE_IPV4", "true").lower() in ("0", "false", "no"):
        return False
    if _gai_patch_installed:
        return True

    _orig = socket.getaddrinfo

    def _gai(
        host,
        port,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ):
        if family in (0, socket.AF_UNSPEC):
            family = socket.AF_INET
        return _orig(host, port, family, type, proto, flags)

    socket.getaddrinfo = _gai
    _gai_patch_installed = True
    return True
