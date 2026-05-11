"""Enumerate ECI Statistical Report category_id space.

Sweeps integers 1..MAX against
``https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=<N>``
and records (id, cat_name, index_url, state-hint, year-hint) for every hit.

Akamai filters non-browser UAs; the recipe in
docs/architecture/admin/eci-statistical-report-fetcher.md (browser UA +
Referer/Origin + Sec-Fetch-* + ``secret: ECI@MAIN825``) bypasses the 403.

Writes ``tools/eci_recon/categories.enumeration.json``:

  {
    "ts": "2026-05-11T...",
    "range": [1, 50],
    "hits": [
      {"id": 25, "cat_name": "General Election to the Legislative
       Assembly of Puducherry 2026", "index_url": ".../ae/2026/20",
       "title_headline": "..."}
    ],
    "misses": [3, 4, ...]
  }

Run:
  python tools/eci_recon/enumerate_categories.py --start 1 --end 50
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

# UTF-8 stdout (lesson: Windows cp1252 chokes on ₹/—).
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API = "https://www.eci.gov.in/eci-backend/public/api/election-result"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "secret": "ECI@MAIN825",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.eci.gov.in/statistical-reports",
    "Origin": "https://www.eci.gov.in",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

OUT = Path(__file__).parent / "categories.enumeration.json"


def probe(client: httpx.Client, cid: int) -> dict | None:
    try:
        r = client.get(API, params={"category_id": cid}, timeout=15.0)
    except httpx.RequestError as exc:
        return {"id": cid, "error": f"request: {exc.__class__.__name__}"}
    if r.status_code != 200:
        return {"id": cid, "error": f"http {r.status_code}"}
    try:
        body = r.json()
    except ValueError:
        return {"id": cid, "error": "non-json"}
    if not body.get("success"):
        return {"id": cid, "error": "success=false"}
    cat_name = body.get("cat_name") or ""
    if not cat_name:
        return {"id": cid, "error": "empty cat_name"}
    return {
        "id": cid,
        "cat_name": cat_name,
        "index_url": body.get("index_url"),
        "index_name": body.get("index_name"),
        "title_headline": body.get("title_headline"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=50)
    ap.add_argument("--sleep", type=float, default=0.4,
                    help="Seconds between requests (be polite).")
    args = ap.parse_args()

    hits: list[dict] = []
    misses: list[int] = []
    errors: list[dict] = []

    with httpx.Client(headers=HEADERS) as client:
        for cid in range(args.start, args.end + 1):
            result = probe(client, cid)
            if result is None:
                misses.append(cid)
                print(f"  {cid:3d} miss")
            elif "error" in result:
                errors.append(result)
                print(f"  {cid:3d} ERR  {result['error']}")
            else:
                hits.append(result)
                print(f"  {cid:3d} HIT  {result['cat_name'][:80]}")
            time.sleep(args.sleep)

    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "range": [args.start, args.end],
        "hits": hits,
        "misses": misses,
        "errors": errors,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUT}")
    print(f"hits={len(hits)} errors={len(errors)} misses={len(misses)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
