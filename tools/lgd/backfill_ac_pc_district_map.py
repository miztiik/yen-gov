"""tools/lgd/backfill_ac_pc_district_map.py — harvest (lgd_ac_id, lgd_district_id) edges from boundary features.

Closes R3a-pre of TODO/20260602-eci-sot-rip-and-replace-plan.md.

The map at ``datasets/taxonomy/lgd_ac_pc_district_map.json`` covers
5.6% of ACs (232 of ~4113) before this script runs — almost entirely
J&K, harvested earlier from the LGD Constituency Coverage Report
portal. The remaining 26 states have no per-AC district coverage,
which would break district-grouping in
``frontend/src/lib/view-models/districts.ts`` once the
ECI-SoT-shard reader is retired (R3a of the plan-doc).

Per the §0d audit, every AC boundary geojson except U08 J&K already
carries the canonical LGD numeric district code on each feature:

- 29 generic state shards: ``Dist_LGD`` per feature
- S03 Assam: ``parent_district_lgd`` per feature (different
  schema, same fact)
- U08 J&K: only ``seat_district_en`` (district name string). Resolved
  by name-match against ``datasets/taxonomy/lgd_districts.json`` rows
  with ``lgd_state_id=1``.

The harvest produces 4000+ ``(lgd_state_id, lgd_ac_id,
[lgd_district_ids])`` triples. Merged with the existing 232 manual
rows (which may cover multi-district ACs the boundary harvest does
not see), the map grows to ~4100+ rows.

Pure stdlib; idempotent; deterministic (sorts rows by ``(lgd_state_id,
lgd_ac_id)`` for byte-stable output). Per CLAUDE.md §4 ``tools/`` MUST
NOT import ``backend/yen_gov`` runtime modules.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOUNDARIES = ROOT / "datasets" / "boundaries" / "in" / "ac"
MAP_FILE = ROOT / "datasets" / "taxonomy" / "lgd_ac_pc_district_map.json"
DISTRICTS_FILE = ROOT / "datasets" / "taxonomy" / "lgd_districts.json"
ACS_FILE = ROOT / "datasets" / "taxonomy" / "lgd_acs.json"


def _norm_int(v: object) -> int | None:
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _norm_name(s: str) -> str:
    # Strip punctuation noise + lowercase for fuzzy district name match.
    out = "".join(c.lower() for c in s if c.isalnum())
    # Common abbreviations seen in U08 seat_district_en vs LGD lgd_name:
    return out.replace("and", "")


def _harvest_generic(features: list[dict]) -> list[tuple[int, int, int]]:
    """Read ``State_LGD`` + ``lgd_ac_id`` + ``Dist_LGD`` per feature."""
    out: list[tuple[int, int, int]] = []
    for ft in features:
        p = ft.get("properties", {}) or {}
        state = _norm_int(p.get("State_LGD") or p.get("state_lgd"))
        ac = _norm_int(p.get("lgd_ac_id") or p.get("AC_ID"))
        dist = _norm_int(p.get("Dist_LGD") or p.get("parent_district_lgd"))
        if state is not None and ac is not None and dist is not None:
            out.append((state, ac, dist))
    return out


def _harvest_jk(features: list[dict], jk_districts: dict[str, int]) -> tuple[list[tuple[int, int, int]], list[str]]:
    """U08 J&K: name-match ``seat_district_en`` against lgd_districts.json.

    Returns (harvested rows, list of unmatched names for the operator).
    """
    out: list[tuple[int, int, int]] = []
    unmatched: list[str] = []
    for ft in features:
        p = ft.get("properties", {}) or {}
        ac = _norm_int(p.get("seat_id") or p.get("lgd_ac_id") or p.get("AC_ID"))
        name = p.get("seat_district_en") or p.get("dist_name")
        if ac is None or not isinstance(name, str):
            continue
        key = _norm_name(name)
        dist = jk_districts.get(key)
        if dist is None:
            unmatched.append(name)
            continue
        out.append((1, ac, dist))
    return out, unmatched


def main() -> int:
    # Load existing map (preserves manual multi-district rows).
    existing = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    existing_rows = existing["rows"]
    merged: dict[tuple[int, int], set[int]] = {
        (r["lgd_state_id"], r["lgd_ac_id"]): set(r["lgd_district_ids"])
        for r in existing_rows
    }
    print(f"existing map: {len(merged)} (state,ac) keys")

    # J&K district name -> lgd_district_id (for U08 reconciliation).
    districts = json.loads(DISTRICTS_FILE.read_text(encoding="utf-8"))["districts"]
    jk_districts = {
        _norm_name(d["lgd_name"]): d["lgd_district_id"]
        for d in districts
        if d["lgd_state_id"] == 1
    }
    # Common JK name aliases (operator-curated; small allowlist).
    jk_aliases = {
        "bandipore": "bandipora",
        "shopia": "shopian",
        "shupiyan": "shopian",
        "leh": "lehladakh",  # Ladakh seats under U09; should not hit here, but safe
    }
    for alias, canonical in jk_aliases.items():
        key = _norm_name(alias)
        if canonical in jk_districts:
            jk_districts[key] = jk_districts[canonical]

    # Sweep state shards.
    per_state: dict[str, tuple[int, int]] = {}  # slug -> (with_dist, total)
    all_unmatched: list[tuple[str, str]] = []  # (state, name)
    for state_dir in sorted(BOUNDARIES.glob("state=*")):
        f = state_dir / "all.geojson"
        if not f.is_file():
            continue
        slug = state_dir.name.replace("state=", "")
        data = json.loads(f.read_text(encoding="utf-8"))
        feats = data.get("features", [])
        if slug == "jammu-and-kashmir":
            triples, unmatched = _harvest_jk(feats, jk_districts)
            all_unmatched.extend((slug, n) for n in unmatched)
        else:
            triples = _harvest_generic(feats)
        per_state[slug] = (len(triples), len(feats))
        for state_lgd, ac_lgd, dist_lgd in triples:
            merged.setdefault((state_lgd, ac_lgd), set()).add(dist_lgd)

    # Print coverage report.
    print()
    print(f"{'state':<33} with_dist/total")
    for s in sorted(per_state):
        wd, tot = per_state[s]
        marker = "  " if wd == tot else " !"
        print(f"  {s:<31}{marker} {wd}/{tot}")
    if all_unmatched:
        print()
        print(f"!! {len(all_unmatched)} unmatched district names (need alias):")
        for st, n in all_unmatched[:30]:
            print(f"   {st}: {n!r}")

    print()
    print(f"merged map: {len(merged)} (state,ac) keys")

    # Emit: sort for byte-stability.
    new_rows = [
        {
            "lgd_state_id": st,
            "lgd_ac_id": ac,
            "lgd_district_ids": sorted(merged[(st, ac)]),
        }
        for st, ac in sorted(merged.keys())
    ]
    existing["rows"] = new_rows
    out_text = json.dumps(existing, indent=2, ensure_ascii=False) + "\n"
    MAP_FILE.write_text(out_text, encoding="utf-8")
    print(f"wrote {MAP_FILE.relative_to(ROOT)} ({len(new_rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
