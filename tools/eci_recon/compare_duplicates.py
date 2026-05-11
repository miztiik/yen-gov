"""Compare ECI category_id batches for the May-2026 cohort.

Recon found two clusters with identical cat_name strings:
  - ids 18-22: Assam/Kerala/Puducherry/TN/WB 2026 (batch A)
  - ids 23-27: same five states (batch B)

This script fetches each, dumps index_url + index_name + any list-shape
payload counts, and writes a side-by-side comparison.
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import httpx

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

PAIRS = [
    ("Assam", 18, 23),
    ("Kerala", 19, 24),
    ("Puducherry", 20, 25),
    ("Tamil Nadu", 21, 26),
    ("West Bengal", 22, 27),
]

OUT = Path(__file__).parent / "categories.duplication_compare.json"


def fetch(client: httpx.Client, cid: int) -> dict:
    r = client.get(API, params={"category_id": cid}, timeout=20.0)
    r.raise_for_status()
    body = r.json()
    # Summarise structure: top-level scalar fields + lengths of list fields.
    summary: dict[str, object] = {
        "id": cid,
        "cat_name": body.get("cat_name"),
        "index_name": body.get("index_name"),
        "index_url": body.get("index_url"),
        "title_headline": body.get("title_headline"),
    }
    for k, v in body.items():
        if isinstance(v, list):
            summary[f"len:{k}"] = len(v)
        elif isinstance(v, dict):
            summary[f"keys:{k}"] = sorted(v.keys())[:10]
    # Also keep the first ~10 keys of any nested 'message'/'data' for shape.
    return summary


def main() -> None:
    rows: list[dict] = []
    with httpx.Client(headers=HEADERS) as client:
        for state, a, b in PAIRS:
            print(f"\n=== {state} ===")
            ra = fetch(client, a)
            time.sleep(0.4)
            rb = fetch(client, b)
            time.sleep(0.4)
            print(f"  {a:3d} index_name={ra['index_name']!r}")
            print(f"      index_url ={ra['index_url']}")
            print(f"  {b:3d} index_name={rb['index_name']!r}")
            print(f"      index_url ={rb['index_url']}")
            rows.append({"state": state, "a": ra, "b": rb})

    OUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
