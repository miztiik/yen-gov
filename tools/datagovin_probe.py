"""Probe data.gov.in DMS API for a resource UUID."""
from __future__ import annotations

import io
import sys

import httpx


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


CANDIDATES = [
    "https://www.data.gov.in/backend/dms/v1/resource/{uuid}",
    "https://www.data.gov.in/backend/dms/v1/ogdp/resource/{uuid}",
    "https://www.data.gov.in/backend/dms/v1/ogdp/resource/download/{uuid}",
    "https://www.data.gov.in/backend/dms/v1/ogdp/resource/preview/{uuid}",
    "https://www.data.gov.in/backend/dms/v1/resource/download/{uuid}",
    "https://www.data.gov.in/backend/dms/v1/resource/preview/{uuid}",
]


def main() -> int:
    uuid = sys.argv[1]
    for tpl in CANDIDATES:
        url = tpl.format(uuid=uuid)
        try:
            r = httpx.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 yen-gov-recon"},
                timeout=20,
                follow_redirects=True,
            )
            ct = r.headers.get("content-type", "")
            n = len(r.content)
            preview = r.text[:200] if "json" in ct or "text" in ct else f"<{n} bytes>"
            print(f"{r.status_code} {ct} {n} {url}")
            print(f"   {preview!r}")
        except Exception as e:
            print(f"ERR {url} -> {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
