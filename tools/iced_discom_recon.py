"""Recon the v0 DISCOM-family ICED endpoints (Tier-2 ingest candidates).

Probes 4 v0 AES-decrypt endpoints, dumps payloads to
.runtime/iced_recon/discom_*.json, prints shape + sample row + facet
inventory for each.

Endpoints (all v0, decrypt=True default):
  - /energy/electricity/distribution/operationalPerformanceStates
  - /energy/electricity/distribution/rpo
  - /all-data-power-purchase-quantum-and-cost
  - /discomDemandsCategoryAndHighestTotal
"""
from __future__ import annotations

import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_common import IcedClient  # noqa: E402

OUT_DIR = REPO_ROOT / ".runtime" / "iced_recon"

ENDPOINTS: list[tuple[str, str]] = [
    ("opperf", "/energy/electricity/distribution/operationalPerformanceStates"),
    ("rpo", "/energy/electricity/distribution/rpo"),
    ("pp_alldata", "/all-data-power-purchase-quantum-and-cost"),
    ("demand_cat", "/discomDemandsCategoryAndHighestTotal"),
]


def _rows_of(decoded):
    if isinstance(decoded, list):
        return decoded
    if isinstance(decoded, dict):
        for k in ("data", "rows", "result"):
            v = decoded.get(k)
            if isinstance(v, list):
                return v
    return []


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = IcedClient(host="https://icedapi.niti.gov.in", polite_delay=0.5)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for label, path in ENDPOINTS:
        print(f"\n=== {label}  GET {path}")
        try:
            resp = client.get(path)
        except Exception as exc:
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            continue
        decoded = resp.decrypted
        out_file = OUT_DIR / f"discom_{label}_{ts}.json"
        out_file.write_text(json.dumps(decoded, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  shape: {type(decoded).__name__}")
        if isinstance(decoded, dict):
            print(f"  top keys: {sorted(decoded)[:15]}")
        rows = _rows_of(decoded)
        print(f"  rows: {len(rows)}")
        if rows and isinstance(rows[0], dict):
            print(f"  field keys: {sorted(rows[0].keys())}")
            print(f"  sample row:")
            print("    " + json.dumps(rows[0], ensure_ascii=False))
            # Facet enumerations
            for fk in ("state", "source", "category", "type", "fyear", "year",
                       "fy", "param", "subcategory", "discom", "fuel"):
                vals = Counter(str(r.get(fk)) for r in rows if isinstance(r, dict) and r.get(fk) is not None)
                if vals:
                    top = vals.most_common(8)
                    print(f"  facet {fk!r}: n={len(vals)} top={top}")
        print(f"  saved -> {out_file.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
