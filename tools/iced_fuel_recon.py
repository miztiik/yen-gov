"""Recon Tier-3 ICED v0 fuel + power-purchase endpoints.

Probes 3 v0 AES-decrypt endpoints, dumps payloads to
.runtime/iced_recon/fuel_*.json, prints shape + sample row + facet
inventory for each.
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
    ("coal_state", "/energy/fuel-sources/coal/consumption-domestic-state"),
    ("oil_state", "/energy/fuel-sources/oil/consumptionStateProductTrend"),
    ("ppa_state", "/statelevel-power-purchase-quantum-and-cost"),
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
        out_file = OUT_DIR / f"fuel_{label}_{ts}.json"
        out_file.write_text(json.dumps(decoded, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  shape: {type(decoded).__name__}")
        if isinstance(decoded, dict):
            print(f"  top keys: {sorted(decoded)[:15]}")
        rows = _rows_of(decoded)
        print(f"  rows: {len(rows)}")
        if rows and isinstance(rows[0], dict):
            print(f"  field keys: {sorted(rows[0].keys())}")
            print(f"  samples:")
            for r in rows[:3]:
                print("    " + json.dumps(r, ensure_ascii=False))
            for fk in ("state", "source", "category", "type", "fyear", "year",
                       "fy", "sector", "region", "subType", "subType_name", "unit"):
                vals = Counter(str(r.get(fk)) for r in rows if isinstance(r, dict) and r.get(fk) is not None)
                if vals:
                    top = vals.most_common(8)
                    print(f"  facet {fk!r}: n={len(vals)} top={top}")
        print(f"  saved -> {out_file.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
