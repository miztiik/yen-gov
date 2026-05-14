"""Probe data.gov.in OGD API for a resource UUID with sample/demo key."""
from __future__ import annotations

import io
import os
import sys

import httpx


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# data.gov.in's documented sample/demo API key (rate-limited, public).
DEMO_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"


def main() -> int:
    uuid = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else "json"
    api_key = os.environ.get("DATAGOVIN_API_KEY", DEMO_KEY)
    url = f"https://api.data.gov.in/resource/{uuid}"
    params = {"api-key": api_key, "format": fmt, "limit": "5"}
    r = httpx.get(
        url,
        params=params,
        headers={"User-Agent": "Mozilla/5.0 yen-gov-recon"},
        timeout=30,
        follow_redirects=True,
    )
    print(f"GET {r.request.url}")
    print(f"status={r.status_code} ct={r.headers.get('content-type', '')} bytes={len(r.content)}")
    print("---")
    print(r.text[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
