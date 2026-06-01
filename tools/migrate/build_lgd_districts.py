"""Build datasets/taxonomy/lgd_districts.json from datasets/taxonomy/lgd/districts-latest.csv.

PR L1b per docs/archive/plans/20260601-lgd-execution-handover.md row L1b.

Joins:
  1. datasets/taxonomy/lgd/districts-latest.csv   (LGD authority: 784 rows)
  2. datasets/taxonomy/lgd_states.json            (FK target for lgd_state_id)

Output: datasets/taxonomy/lgd_districts.json (validated by datasets/schemas/lgd-districts.schema.json).

Schema columns:
  lgd_district_id, lgd_state_id, lgd_name, slug, census_2001_code, census_2011_code

The handover spec also asked for parent_district_lgd (bifurcation lineage). The source LGD CSV
does not carry that column; bifurcation lineage will be added via a follow-up ingest from the
LGD portal's district-history page once a separate plan-doc commissions it. Field absent from
this seed; not nullable absent — simply not present in v1.0.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "datasets/taxonomy/lgd/districts-latest.csv"
STATES_PATH = REPO / "datasets/taxonomy/lgd_states.json"
OUT_PATH = REPO / "datasets/taxonomy/lgd_districts.json"
SCHEMA_REL = "../schemas/lgd-districts.schema.json"


def _slug(name: str) -> str:
    s = name.lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def main() -> None:
    states = json.loads(STATES_PATH.read_text(encoding="utf-8"))["states"]
    state_lgd_set = {s["lgd_state_id"] for s in states}
    state_by_lgd = {s["lgd_state_id"]: s for s in states}

    rows: list[dict] = []
    seen_district: set[int] = set()
    # district slugs need to be unique within a state (not nationally) - some
    # district names repeat across states (e.g. 'Hamirpur' in HP and UP).
    seen_slug_per_state: dict[int, set[str]] = {}
    for r in csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")):
        lgd_state_id = int(r["State Code"])
        if lgd_state_id not in state_lgd_set:
            raise SystemExit(
                f"district row references unknown lgd_state_id {lgd_state_id} "
                f"(district {r['District Name(In English)']!r})"
            )
        lgd_district_id = int(r["District Code"])
        if lgd_district_id in seen_district:
            raise SystemExit(f"duplicate lgd_district_id {lgd_district_id}")
        seen_district.add(lgd_district_id)
        name = r["District Name(In English)"].strip()
        slug = _slug(name)
        state_slugs = seen_slug_per_state.setdefault(lgd_state_id, set())
        if slug in state_slugs:
            # Salt with the district id to keep uniqueness; rare (<5 cases).
            slug = f"{slug}-{lgd_district_id}"
        state_slugs.add(slug)
        c01 = int(r["Census 2001 Code"]) or None
        c11 = int(r["Census 2011 Code"]) or None
        rows.append({
            "lgd_district_id": lgd_district_id,
            "lgd_state_id": lgd_state_id,
            "lgd_name": name,
            "slug": slug,
            "census_2001_code": c01,
            "census_2011_code": c11,
        })

    rows.sort(key=lambda x: (x["lgd_state_id"], x["lgd_district_id"]))

    # Cross-check: every state has >= 1 district (else the CSV is broken).
    states_with_districts = {r["lgd_state_id"] for r in rows}
    missing = state_lgd_set - states_with_districts
    if missing:
        names = [state_by_lgd[m]["lgd_name"] for m in sorted(missing)]
        raise SystemExit(f"states with zero districts in CSV: {names}")

    doc = {
        "$schema": SCHEMA_REL,
        "$schema_version": "1.0",
        "$comment": (
            "Authoritative LGD district register. Every row FK-joins to "
            "datasets/taxonomy/lgd_states.json on lgd_state_id. Sourced from "
            "datasets/taxonomy/lgd/districts-latest.csv (LGD portal snapshot "
            "via Ministry of Panchayati Raj). Bifurcation lineage "
            "(parent_district_lgd) is NOT in this seed; will arrive in a "
            "follow-up ingest from the LGD district-history page. Builder: "
            "tools/migrate/build_lgd_districts.py."
        ),
        "sources": [
            {
                "url": "https://lgdirectory.gov.in/",
                "fetched_at": "2026-05-24T20:25:59Z",
                "name": "Local Government Directory (LGD) - Districts register",
                "authority": "Ministry of Panchayati Raj, Government of India",
            }
        ],
        "districts": rows,
    }
    OUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(REPO)} with {len(rows)} districts across {len(states_with_districts)} states/UTs")


if __name__ == "__main__":
    main()
