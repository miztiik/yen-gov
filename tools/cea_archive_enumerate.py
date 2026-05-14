"""Enumerate the CEA Installed Capacity monthly archive.

Using browser-verified URL pattern:
   https://cea.nic.in/wp-content/uploads/installed/<YYYY>/<MM>/<leaf>

Earlier recon failed because it tried only ``Website-1.xlsx``. The
current-month leaf is actually ``Website.xlsx``; older months use
varying leaves. We probe a small set of plausible leaves per month and
record the FIRST one that returns 200.

Output: ``.runtime/raw/cea/_archive_index.json`` — a manifest mapping
``YYYY-MM`` -> direct XLSX URL, used by the downloader to fetch only
months that exist.
"""
from __future__ import annotations

import asyncio
import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "https://cea.nic.in/wp-content/uploads/installed"
LEAVES = (
    "Website.xlsx",
    "Website-1.xlsx",
    "Website-2.xlsx",
    "Website-3.xlsx",
    "website.xlsx",  # older folders sometimes lower-case
)

# CEA browser date picker shows months back to ~2009; data starts later.
START = date(2010, 1, 1)
END = date(2026, 5, 1)

OUT = Path(".runtime/raw/cea/_archive_index.json")

# Browser User-Agent + Referer to dodge naive bot rejection.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Referer": "https://cea.nic.in/installed-capacity-report/?lang=en",
    "Accept": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/octet-stream;q=0.9,*/*;q=0.8"
    ),
}


def _months(start: date, end: date) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    cur = date(start.year, start.month, 1)
    end_first = date(end.year, end.month, 1)
    while cur <= end_first:
        out.append((cur.year, cur.month))
        # Advance one month.
        cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


async def _probe_one(
    client: httpx.AsyncClient, year: int, month: int
) -> tuple[str, str | None, int | None]:
    """Return ``(YYYY-MM, url_or_None, status_or_None)``."""
    key = f"{year:04d}-{month:02d}"
    for leaf in LEAVES:
        url = f"{BASE}/{year:04d}/{month:02d}/{leaf}"
        try:
            r = await client.head(url, follow_redirects=True, timeout=12.0)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            continue
        if r.status_code == 200:
            return key, url, 200
    return key, None, None


async def main() -> None:
    months = _months(START, END)
    print(f"probing {len(months)} months (from {START} to {END})...", flush=True)

    sem = asyncio.Semaphore(8)  # be polite

    async with httpx.AsyncClient(headers=HEADERS) as client:
        async def _bounded(y: int, m: int):
            async with sem:
                return await _probe_one(client, y, m)

        results = await asyncio.gather(*(_bounded(y, m) for (y, m) in months))

    found = {key: url for (key, url, _) in results if url is not None}
    missing = [key for (key, url, _) in results if url is None]

    print(f"\nfound: {len(found)} months  ({len(found) / len(months) * 100:.1f}%)")
    if missing:
        print(f"missing: {len(missing)} months -- first 12: {missing[:12]}")
        print(f"       -- last 12:  {missing[-12:]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "probed_months": [f"{y:04d}-{m:02d}" for (y, m) in months],
                "leaves_tried": list(LEAVES),
                "found_count": len(found),
                "missing_count": len(missing),
                "missing": missing,
                "manifest": dict(sorted(found.items())),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT.as_posix()}")


if __name__ == "__main__":
    asyncio.run(main())
