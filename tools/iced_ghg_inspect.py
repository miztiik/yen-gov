"""Inspect the cached ghg_energy_full payload more deeply to understand
sector/subSector/category/subCategory hierarchy.
"""
from __future__ import annotations

import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_common.client import IcedClient  # noqa: E402

c = IcedClient(host="https://icedapi.niti.gov.in", polite_delay=0.5)
r = c.get("/climate-environment/ghg-emissions/energy")
rows = r.decrypted["data"]

print(f"total rows: {len(rows)}")
print(f"years: {sorted({r['year'] for r in rows})}")

# Hierarchy buckets
levels = defaultdict(set)
for row in rows:
    sec = row.get("sector") or ""
    sub = row.get("subSector") or ""
    cat = row.get("category") or ""
    subcat = row.get("subCategory") or ""
    levels["sector"].add(sec)
    levels[(sec, "subSector")].add(sub)
    if cat:
        levels[(sec, sub, "category")].add(cat)
    if subcat:
        levels[(sec, sub, cat, "subCategory")].add(subcat)

print("\n=== Sectors ===")
for s in sorted(levels["sector"]):
    print(f"  {s!r}")

print("\n=== SubSectors per Sector ===")
for s in sorted(levels["sector"]):
    subs = sorted(levels.get((s, "subSector"), set()))
    print(f"  {s}: {subs}")

print("\n=== Sample rows where category != '' ===")
shown = 0
for row in rows:
    if row.get("category"):
        print(json.dumps(row))
        shown += 1
        if shown >= 8:
            break

print("\n=== Sample rows where subCategory != '' ===")
shown = 0
for row in rows:
    if row.get("subCategory"):
        print(json.dumps(row))
        shown += 1
        if shown >= 8:
            break

# Coverage matrix: subSector × year non-zero
print("\n=== Year-coverage per (sector, subSector) ===")
yc = defaultdict(Counter)
for row in rows:
    yc[(row["sector"], row["subSector"])][row["year"]] += 1
for k in sorted(yc):
    years = sorted(yc[k])
    print(f"  {k}: {len(years)} years, {min(years)}..{max(years)}")
