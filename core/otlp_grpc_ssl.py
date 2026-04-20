"""TLS roots for OTLP/gRPC.

Python gRPC does not use ``truststore`` or the macOS keychain. We merge:

- **certifi** (public CAs)
- On **macOS**, optional roots from the **System Roots** keychain (helps when the
  default bundle is incomplete for your Python build)
- Optional extra PEM from **OTEL_EXTRA_CA_CERTS** (e.g. Zscaler / corporate root)

If you still see ``CERTIFICATE_VERIFY_FAILED``, set **OTEL_EXPORTER_OTLP_CERTIFICATE**
to a single PEM file: ``cat $(python -c "import certifi; print(certifi.where())") ~/corp-root.pem > /tmp/otel-ca.pem``
"""

from __future__ import annotations

import os
import subprocess
import sys

import grpc


def _certifi_pem() -> bytes:
    import certifi

    with open(certifi.where(), "rb") as f:
        return f.read()


def _read_file_if_exists(path: str) -> bytes:
    path = path.strip()
    if not path or not os.path.isfile(path):
        return b""
    with open(path, "rb") as f:
        return f.read()


def _darwin_system_root_pem() -> bytes:
    """Apple system root CAs as PEM (helps gRPC + Homebrew Python on macOS)."""
    if sys.platform != "darwin":
        return b""
    if os.getenv("OTEL_GRPC_USE_MACOS_KEYCHAIN", "true").lower() in (
        "0",
        "false",
        "no",
    ):
        return b""
    try:
        return subprocess.check_output(
            [
                "security",
                "find-certificate",
                "-a",
                "-p",
                "/System/Library/Keychains/SystemRootCertificates.keychain",
            ],
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
        OSError,
    ):
        return b""


def _merged_roots_default() -> bytes:
    parts: list[bytes] = [_certifi_pem(), _darwin_system_root_pem()]

    extra = (
        os.getenv("OTEL_EXTRA_CA_CERTS")
        or os.getenv("OTEL_GRPC_EXTRA_CA_CERTS")
        or ""
    ).strip()
    if extra:
        parts.append(_read_file_if_exists(extra))

    # Common Homebrew OpenSSL bundle (often has more intermediates than certifi alone)
    for p in ("/etc/ssl/cert.pem", "/opt/homebrew/etc/openssl@3/cert.pem"):
        parts.append(_read_file_if_exists(p))

    return b"\n".join(p for p in parts if p)


def channel_credentials() -> grpc.ChannelCredentials:
    """Roots for ``grpc.secure_channel`` / OTLP gRPC exporters."""
    path = (os.getenv("OTEL_EXPORTER_OTLP_CERTIFICATE") or "").strip()
    if path:
        with open(path, "rb") as f:
            roots = f.read()
    else:
        roots = _merged_roots_default()
    return grpc.ssl_channel_credentials(root_certificates=roots)
