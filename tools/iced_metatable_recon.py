"""Recon the three ICED *_metatable-data endpoints (v1, plain JSON).

Saves raw payloads under .runtime/iced_recon/ and prints shape, facets,
year coverage, state coverage, and aggregate-row detection.
"""
from __future__ import annotations

import io
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_common import IcedClient  # noqa: E402

ENDPOINTS = [
    ("co_emission", "/co-emission-metatable-data"),
    ("gen", "/gen-metatable-data"),
    ("plf", "/plf-metatable-data"),
]


def summarise(name: str, path: str, data) -> None:
    print(f"\n{'=' * 78}\n### {name}  {path}\n{'=' * 78}")
    if isinstance(data, dict):
        print(f"  top-level: dict, keys={sorted(data.keys())}")
        rows = data.get("data") or data.get("rows") or data.get("result")
    elif isinstance(data, list):
        rows = data
        print("  top-level: list")
    else:
        print(f"  unexpected: {type(data).__name__}")
        return
    if not isinstance(rows, list) or not rows:
        print("  no rows extracted")
        return
    print(f"  rows: {len(rows)}")
    first = rows[0]
    print(f"  first-row fields: {sorted(first.keys()) if isinstance(first, dict) else type(first).__name__}")
    print(f"  first row: {json.dumps(first, ensure_ascii=False)}")

    if not isinstance(first, dict):
        return

    # Facet enumerations
    for key in sorted(first.keys()):
        vals = [r.get(key) for r in rows if isinstance(r, dict)]
        nonnull = [str(v).strip() for v in vals if v is not None and str(v).strip() != ""]
        nulls = len(vals) - len(nonnull)
        unique = sorted(set(nonnull), key=str)
        # short report only for low-cardinality columns; show all years explicitly
        if len(unique) <= 60 or key.lower() in ("year", "fy", "yearmonth"):
            print(f"  - {key}: {len(unique)} unique, nulls={nulls}")
            print(f"      values: {unique}")
        else:
            print(f"  - {key}: {len(unique)} unique, nulls={nulls}, sample={unique[:8]}")

    # Aggregate detection on `state`
    if "state" in first:
        sc = Counter(str(r.get("state") or "").strip() for r in rows)
        agg = {k: v for k, v in sc.items() if k.lower() in {"all india", "india", "national", "total", "all states", "grand total", ""}}
        if agg:
            print(f"  [!] aggregate-state rows: {agg}")
        print(f"  state cardinality: {len(sc)} (top-3 by row count: {sc.most_common(3)})")


def main() -> int:
    out_dir = REPO_ROOT / ".runtime" / "iced_recon"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = IcedClient(host="https://icedapi.niti.gov.in/v1", polite_delay=0.2, retries=2)
    for name, path in ENDPOINTS:
        print(f"\n[*] fetching {path} ...", flush=True)
        try:
            resp = client.get(path, decrypt=False, timeout=30)
        except Exception as exc:
            print(f"  ERROR: {exc!r}")
            continue
        out_path = out_dir / f"metatable_{name}.json"
        out_path.write_text(json.dumps(resp.decrypted, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  saved {out_path.relative_to(REPO_ROOT).as_posix()}")
        summarise(name, path, resp.decrypted)
    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
