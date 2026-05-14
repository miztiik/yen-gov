"""Recon helper for data.gov.in resource pages.

Fetches a resource page and extracts the underlying CSV/XLSX/API URLs
+ resource UUIDs (data.gov.in builds the page client-side so the
download buttons reference the canonical asset URLs in inline JS / data
attributes).

Usage:
    python tools/datagovin_recon.py <resource-slug>
"""
from __future__ import annotations

import io
import re
import sys

import httpx


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main(slug: str) -> int:
    url = f"https://www.data.gov.in/resource/{slug}"
    r = httpx.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 yen-gov-recon"},
        timeout=30,
        follow_redirects=True,
    )
    print(f"GET {url} -> {r.status_code} ({len(r.text)} bytes)")
    t = r.text

    print("\n== CSV/XLSX/JSON URLs ==")
    for m in sorted(set(re.findall(r"https?://[^\s\"'<>]+\.(?:csv|xlsx|json|CSV|XLSX|JSON)", t))):
        print(f"  {m}")

    print("\n== UUIDs ==")
    for m in sorted(set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", t))):
        print(f"  {m}")

    print("\n== api.data.gov.in references ==")
    for m in sorted(set(re.findall(r"https?://api\.data\.gov\.in/[^\s\"'<>]+", t))):
        print(f"  {m}")

    print("\n== sites/default/files references ==")
    for m in sorted(set(re.findall(r"https?://[^\s\"'<>]*sites/default/files/[^\s\"'<>]+", t))):
        print(f"  {m}")

    print("\n== /backend/dms references ==")
    for m in sorted(set(re.findall(r"/backend/dms/[^\s\"'<>]+", t))):
        print(f"  {m}")

    print("\n== resource/.../download references ==")
    for m in sorted(set(re.findall(r"/resource/[^\s\"'<>]+download[^\s\"'<>]*", t))):
        print(f"  {m}")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/datagovin_recon.py <resource-slug>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
