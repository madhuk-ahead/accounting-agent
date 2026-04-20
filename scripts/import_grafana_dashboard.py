#!/usr/bin/env python3
"""Create or update the AHEAD Agent Overview dashboard in Grafana via HTTP API.

Environment:
  GRAFANA_URL   — Base URL (e.g. https://myorg.grafana.net)
  GRAFANA_API_KEY — Service account token or API key with dashboard write scope
  GRAFANA_SSL_VERIFY — Set to 0 to skip TLS verification (only if you must; not recommended).
  GRAFANA_CA_BUNDLE — Path to a PEM file of trusted CAs (overrides automatic trust).

TLS verification:
  By default this script calls ``truststore.inject_into_ssl()`` so HTTPS uses the **system
  trust store** (macOS Keychain, Windows, etc.). That fixes **Zscaler and other TLS
  inspection** cases where ``certifi`` alone fails with "unable to get local issuer certificate".
  If you prefer a specific PEM bundle, set GRAFANA_CA_BUNDLE.

The dashboard JSON path defaults to docs/agent-overview-dashboard.json next to repo root.

Example:
  export GRAFANA_URL=https://myorg.grafana.net
  export GRAFANA_API_KEY=glsa_...
  python scripts/import_grafana_dashboard.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DASHBOARD = REPO_ROOT / "docs" / "agent-overview-dashboard.json"


def _configure_tls() -> bool | str:
    """Return ``verify`` argument for ``requests`` (bool or path to CA bundle)."""
    if os.environ.get("GRAFANA_SSL_VERIFY", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        print(
            "WARNING: GRAFANA_SSL_VERIFY disables TLS certificate checks.",
            file=sys.stderr,
        )
        return False

    custom = os.environ.get("GRAFANA_CA_BUNDLE", "").strip()
    if custom:
        return custom

    import truststore

    truststore.inject_into_ssl()
    return True


def main() -> int:
    base = (os.environ.get("GRAFANA_URL") or "").strip().rstrip("/")
    token = (os.environ.get("GRAFANA_API_KEY") or "").strip()
    if not base or not token:
        print("Set GRAFANA_URL and GRAFANA_API_KEY.", file=sys.stderr)
        return 1

    path = Path(os.environ.get("GRAFANA_DASHBOARD_JSON", str(DEFAULT_DASHBOARD)))
    body = json.loads(path.read_text(encoding="utf-8"))
    uid = body.get("uid") or "ahead-agent-overview"

    payload = {"dashboard": body, "overwrite": True, "message": "Import AHEAD Agent Overview"}
    url = f"{base}/api/dashboards/db"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    verify = _configure_tls()
    try:
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60,
            verify=verify,
        )
    except requests.exceptions.SSLError as e:
        print(f"SSL error: {e}", file=sys.stderr)
        print(
            "If you use Zscaler or similar TLS inspection, ensure truststore is installed "
            "(pip install -r requirements.txt) so the system trust store is used.",
            file=sys.stderr,
        )
        print(
            "Or set GRAFANA_CA_BUNDLE=/path/to/your-org-root-ca.pem",
            file=sys.stderr,
        )
        print("Last resort (insecure): GRAFANA_SSL_VERIFY=0", file=sys.stderr)
        return 1
    except requests.exceptions.RequestException as e:
        print(str(e), file=sys.stderr)
        return 1

    if resp.status_code >= 400:
        print(f"HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        return 1

    try:
        out = resp.json()
    except json.JSONDecodeError:
        print(resp.text, file=sys.stderr)
        return 1

    meta = out.get("url") or out.get("uid", uid)
    print(f"OK: dashboard uid={uid} url={base}{meta if str(meta).startswith('/') else '/' + str(meta)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
