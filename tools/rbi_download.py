"""Download an RBI XLSX with a real-browser UA + referer header.

Usage:
    python tools/rbi_download.py <url> <output_path>
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.ms-excel,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": (
        "https://www.rbi.org.in/Scripts/AnnualPublications.aspx"
        "?head=State+Finances+%3A+A+Study+of+Budgets"
    ),
}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    url, out = sys.argv[1], Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as c:
        # Touch the listing page first to establish session/cookies.
        c.get(HEADERS["Referer"])
        r = c.get(url)
    print(f"status={r.status_code} bytes={len(r.content)} ct={r.headers.get('content-type')}", file=sys.stderr)
    if r.status_code != 200:
        print(f"!! non-200; first 200 chars:\n{r.text[:200]}", file=sys.stderr)
        return 3

    head = r.content[:8]
    if head[:2] != b"PK":
        print(f"!! not a zip/xlsx (head={head!r}); first 200 chars:\n{r.text[:200]}", file=sys.stderr)
        # Save anyway for inspection
        out.write_bytes(r.content)
        return 4

    out.write_bytes(r.content)
    print(f"wrote {out} ({len(r.content)} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
