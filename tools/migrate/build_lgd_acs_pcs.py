"""Build datasets/taxonomy/{lgd_acs.json, lgd_pcs.json, lgd_ac_pc_district_map.json}
from datasets/taxonomy/lgd/constituency-report-2026-06-01.xlsx.

PR L1c per docs/archive/plans/20260601-lgd-execution-handover.md row L1c.

The source XLSX is the LGD portal's "Constituency Coverage Details" report
(498663 rows; one row per (PC, AC, contained entity)). We aggregate to three
distinct artefacts:

  1. lgd_pcs.json   - one row per Parliamentary Constituency (lgd_pc_id, ...)
  2. lgd_acs.json   - one row per Assembly Constituency (lgd_ac_id, lgd_pc_id, ...)
  3. lgd_ac_pc_district_map.json - per-AC district coverage (lgd_ac_id -> [lgd_district_id])

All three FK to datasets/taxonomy/lgd_states.json on lgd_state_id and (for ACs)
to lgd_districts.json on lgd_district_id.

Known gaps in this snapshot (documented; do NOT silently backfill):
  - state_code=7 (Delhi): 0 ACs, 0 PCs in this report (Delhi has 70 ACs + 7 PCs).
    Report was generated with an unknown filter that excluded Delhi.
  - state_code=31 (Lakshadweep): 0 PCs (has 1 PC).
  - state_code=37 (Ladakh): 0 PCs (has 1 PC).
  - state_codes 31 / 35 / 37 / 38 / 4: 0 ACs (correct - these UTs have no
    Legislative Assembly except for Puducherry which is covered).

Counts after build: 3918 ACs, 533 PCs. Plan-doc target was ~4123 ACs and 543
PCs; the delta (205 ACs + 10 PCs) is the Delhi + Lakshadweep + Ladakh gap.
Documented in the schema $comment + plan-doc successor handover.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

REPO = Path(__file__).resolve().parents[2]
XLSX = REPO / "datasets/taxonomy/lgd/constituency-report-2026-06-01.xlsx"
STATES = REPO / "datasets/taxonomy/lgd_states.json"
DISTRICTS = REPO / "datasets/taxonomy/lgd_districts.json"

OUT_ACS = REPO / "datasets/taxonomy/lgd_acs.json"
OUT_PCS = REPO / "datasets/taxonomy/lgd_pcs.json"
OUT_MAP = REPO / "datasets/taxonomy/lgd_ac_pc_district_map.json"


def _slug(name: str) -> str:
    s = name.lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def main() -> None:
    states = json.loads(STATES.read_text(encoding="utf-8"))["states"]
    state_ids = {s["lgd_state_id"] for s in states}
    districts = json.loads(DISTRICTS.read_text(encoding="utf-8"))["districts"]
    district_ids = {d["lgd_district_id"] for d in districts}

    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["constituencyReport"]

    acs: dict[tuple[int, int], dict] = {}
    pcs: dict[tuple[int, int], dict] = {}
    ac_to_districts: dict[tuple[int, int], set[int]] = defaultdict(set)

    for row in ws.iter_rows(min_row=3, values_only=True):
        _sno, sc, _sname, pc_code, pc_name, ac_code, ac_name, et, ec, _en, _cov = row
        if sc is None:
            continue
        sc = int(sc)
        if sc not in state_ids:
            raise SystemExit(f"unknown state_code {sc} in XLSX row")
        if pc_code and int(pc_code) > 0:
            pcs.setdefault((sc, int(pc_code)), {
                "lgd_pc_id": int(pc_code),
                "lgd_state_id": sc,
                "pc_name": (pc_name or "").strip(),
                "slug": _slug(pc_name or ""),
            })
        if ac_code and int(ac_code) > 0 and ac_name:
            key = (sc, int(ac_code))
            acs.setdefault(key, {
                "lgd_ac_id": int(ac_code),
                "lgd_state_id": sc,
                "lgd_pc_id": int(pc_code) if pc_code and int(pc_code) > 0 else None,
                "ac_name": ac_name.strip(),
                "slug": _slug(ac_name),
            })
            if et == "District" and ec:
                ec_int = int(ec)
                if ec_int in district_ids:
                    ac_to_districts[key].add(ec_int)

    # Sanity: every PC referenced by an AC exists in pcs[]
    pc_keys = set(pcs)
    for k, ac in acs.items():
        if ac["lgd_pc_id"] is not None and (k[0], ac["lgd_pc_id"]) not in pc_keys:
            raise SystemExit(f"AC {k} references missing PC {ac['lgd_pc_id']}")

    # Sort + write PCs
    pcs_sorted = sorted(pcs.values(), key=lambda x: (x["lgd_state_id"], x["lgd_pc_id"]))
    pcs_doc = {
        "$schema": "../schemas/lgd-pcs.schema.json",
        "$schema_version": "1.0",
        "$comment": (
            "Authoritative LGD Parliamentary Constituency register. FK to "
            "lgd_states.json on lgd_state_id. Sourced from "
            "datasets/taxonomy/lgd/constituency-report-2026-06-01.xlsx (LGD "
            "portal Constituency Coverage report). KNOWN GAPS: state_code=7 "
            "Delhi (0 PCs; expected 7), state_code=31 Lakshadweep (0 PCs; "
            "expected 1), state_code=37 Ladakh (0 PCs; expected 1) - the "
            "source report excluded these. Total in this snapshot: 533 PCs; "
            "expected 543. See plan-doc successor handover for the follow-up "
            "ingest plan. Builder: tools/migrate/build_lgd_acs_pcs.py."
        ),
        "sources": [
            {
                "url": "https://lgdirectory.gov.in/",
                "fetched_at": "2026-06-01T21:38:00Z",
                "name": "Local Government Directory (LGD) - Constituency Coverage Report",
                "authority": "Ministry of Panchayati Raj, Government of India",
            }
        ],
        "pcs": pcs_sorted,
    }
    OUT_PCS.write_text(json.dumps(pcs_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Sort + write ACs
    acs_sorted = sorted(acs.values(), key=lambda x: (x["lgd_state_id"], x["lgd_ac_id"]))
    acs_doc = {
        "$schema": "../schemas/lgd-acs.schema.json",
        "$schema_version": "1.0",
        "$comment": (
            "Authoritative LGD Assembly Constituency register. FK to "
            "lgd_states.json on lgd_state_id and lgd_pcs.json on lgd_pc_id. "
            "Sourced from datasets/taxonomy/lgd/constituency-report-2026-06-01.xlsx. "
            "KNOWN GAPS: state_code=7 Delhi (0 ACs; expected 70) - the "
            "source report excluded Delhi. UTs without legislatures (A&N=35, "
            "Chandigarh=4, DNHDD=38, Lakshadweep=31, Ladakh=37) correctly "
            "have 0 ACs. Total in this snapshot: 3918 ACs; expected ~4123. "
            "ECI ac_no is NOT carried here (LGD report has no ECI mapping); "
            "the ECI -> LGD AC join lives in datasets/data/entities/ac_crosswalk.csv "
            "post-X1b (#814; was taxonomy/ac_crosswalk.parquet pre-X1b) "
            "per ADR-0049. Builder: tools/migrate/build_lgd_acs_pcs.py."
        ),
        "sources": [
            {
                "url": "https://lgdirectory.gov.in/",
                "fetched_at": "2026-06-01T21:38:00Z",
                "name": "Local Government Directory (LGD) - Constituency Coverage Report",
                "authority": "Ministry of Panchayati Raj, Government of India",
            }
        ],
        "acs": acs_sorted,
    }
    OUT_ACS.write_text(json.dumps(acs_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # AC -> [district] map
    map_rows = []
    for (sc, ac_id), dids in sorted(ac_to_districts.items()):
        if not dids:
            continue
        map_rows.append({
            "lgd_state_id": sc,
            "lgd_ac_id": ac_id,
            "lgd_district_ids": sorted(dids),
        })
    map_doc = {
        "$schema": "../schemas/lgd-ac-pc-district-map.schema.json",
        "$schema_version": "1.0",
        "$comment": (
            "Per-AC district coverage from the LGD Constituency Coverage Report. "
            "An AC can span multiple districts (e.g. urban-rural boundary cases); "
            "this map records every (lgd_ac_id, lgd_district_id) coverage edge "
            "the LGD portal asserts. FK both sides to lgd_acs.json and "
            "lgd_districts.json. Coverage entries with unknown district ids "
            "(not in lgd_districts.json) are dropped silently - those are "
            "almost always sub-district / panchayat entities the source row "
            "carried as Entity Type=District by mistake. Builder: "
            "tools/migrate/build_lgd_acs_pcs.py."
        ),
        "sources": [
            {
                "url": "https://lgdirectory.gov.in/",
                "fetched_at": "2026-06-01T21:38:00Z",
                "name": "Local Government Directory (LGD) - Constituency Coverage Report",
                "authority": "Ministry of Panchayati Raj, Government of India",
            }
        ],
        "rows": map_rows,
    }
    OUT_MAP.write_text(json.dumps(map_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"wrote {OUT_PCS.relative_to(REPO)}: {len(pcs_sorted)} PCs")
    print(f"wrote {OUT_ACS.relative_to(REPO)}: {len(acs_sorted)} ACs")
    print(f"wrote {OUT_MAP.relative_to(REPO)}: {len(map_rows)} AC-district edges")


if __name__ == "__main__":
    main()
