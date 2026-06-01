"""Build datasets/taxonomy/lgd_states.json from datasets/taxonomy/lgd/states-latest.csv.

PR L1a per docs/archive/plans/20260601-lgd-execution-handover.md row L1a.

Joins three inputs (all in-repo, deterministic):
  1. datasets/taxonomy/lgd/states-latest.csv         (LGD authority: 36 rows)
  2. ECI st_code map                                  (from backend/yen_gov/sources/wikipedia/urls.py)
  3. ISO 3166-2:IN subdivision codes                  (hand table; standardized; stable)

Output: datasets/taxonomy/lgd_states.json (validated by datasets/schemas/lgd-states.schema.json).

Schema columns per execution-handover L1a:
  lgd_state_id, lgd_name, lgd_name_short, iso_alpha, slug, eci_st_code,
  census_2001_code, census_2011_code, kind (S=state, U=ut)
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "datasets/taxonomy/lgd/states-latest.csv"
OUT_PATH = REPO / "datasets/taxonomy/lgd_states.json"
SCHEMA_REL = "../schemas/lgd-states.schema.json"

# ECI st_code -> canonical LGD English name (mirrors
# backend/yen_gov/sources/wikipedia/urls.py:_ECI_TO_WIKI_STATE)
ECI_BY_NAME: dict[str, str] = {
    "Andhra Pradesh": "S01",
    "Arunachal Pradesh": "S02",
    "Assam": "S03",
    "Bihar": "S04",
    "Goa": "S05",
    "Gujarat": "S06",
    "Haryana": "S07",
    "Himachal Pradesh": "S08",
    "Karnataka": "S10",
    "Kerala": "S11",
    "Madhya Pradesh": "S12",
    "Maharashtra": "S13",
    "Manipur": "S14",
    "Meghalaya": "S15",
    "Mizoram": "S16",
    "Nagaland": "S17",
    "Odisha": "S18",
    "Punjab": "S19",
    "Rajasthan": "S20",
    "Sikkim": "S21",
    "Tamil Nadu": "S22",
    "Tripura": "S23",
    "Uttar Pradesh": "S24",
    "West Bengal": "S25",
    "Chhattisgarh": "S26",
    "Jharkhand": "S27",
    "Uttarakhand": "S28",
    "Telangana": "S29",
    "Andaman And Nicobar Islands": "U01",
    "Chandigarh": "U02",
    "The Dadra And Nagar Haveli And Daman And Diu": "U03",
    "Lakshadweep": "U04",
    "Delhi": "U05",
    "Puducherry": "U07",
    "Jammu And Kashmir": "U08",
    "Ladakh": "U09",
}

# ISO 3166-2:IN subdivision codes (https://www.iso.org/obp/ui/#iso:code:3166:IN).
# Stable; hand-curated against the published ISO list.
ISO_BY_NAME: dict[str, str] = {
    "Andhra Pradesh": "IN-AP",
    "Arunachal Pradesh": "IN-AR",
    "Assam": "IN-AS",
    "Bihar": "IN-BR",
    "Chhattisgarh": "IN-CT",
    "Goa": "IN-GA",
    "Gujarat": "IN-GJ",
    "Haryana": "IN-HR",
    "Himachal Pradesh": "IN-HP",
    "Jharkhand": "IN-JH",
    "Karnataka": "IN-KA",
    "Kerala": "IN-KL",
    "Madhya Pradesh": "IN-MP",
    "Maharashtra": "IN-MH",
    "Manipur": "IN-MN",
    "Meghalaya": "IN-ML",
    "Mizoram": "IN-MZ",
    "Nagaland": "IN-NL",
    "Odisha": "IN-OR",
    "Punjab": "IN-PB",
    "Rajasthan": "IN-RJ",
    "Sikkim": "IN-SK",
    "Tamil Nadu": "IN-TN",
    "Telangana": "IN-TG",
    "Tripura": "IN-TR",
    "Uttar Pradesh": "IN-UP",
    "Uttarakhand": "IN-UT",
    "West Bengal": "IN-WB",
    "Andaman And Nicobar Islands": "IN-AN",
    "Chandigarh": "IN-CH",
    "The Dadra And Nagar Haveli And Daman And Diu": "IN-DH",
    "Delhi": "IN-DL",
    "Jammu And Kashmir": "IN-JK",
    "Ladakh": "IN-LA",
    "Lakshadweep": "IN-LD",
    "Puducherry": "IN-PY",
}

# Short names for display (e.g. URL slugs sometimes prefer shorter forms).
SHORT_BY_NAME: dict[str, str] = {
    "The Dadra And Nagar Haveli And Daman And Diu": "Dadra And Nagar Haveli And Daman And Diu",
    "Andaman And Nicobar Islands": "Andaman & Nicobar",
    "Jammu And Kashmir": "Jammu & Kashmir",
}


def _slug(name: str) -> str:
    s = name.lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def main() -> None:
    rows: list[dict] = []
    seen_lgd: set[int] = set()
    seen_eci: set[str] = set()
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            name = r["State Name (In English)"].strip()
            lgd_id = int(r["State Code"])
            kind = r["State or UT"].strip()
            eci = ECI_BY_NAME.get(name)
            iso = ISO_BY_NAME.get(name)
            if eci is None:
                raise SystemExit(f"missing ECI st_code for LGD name {name!r}")
            if iso is None:
                raise SystemExit(f"missing ISO 3166-2 code for LGD name {name!r}")
            if lgd_id in seen_lgd:
                raise SystemExit(f"duplicate lgd_state_id {lgd_id}")
            if eci in seen_eci:
                raise SystemExit(f"duplicate eci_st_code {eci}")
            seen_lgd.add(lgd_id)
            seen_eci.add(eci)
            display_name = SHORT_BY_NAME.get(name, name)
            census_2001 = int(r["Census 2001 Code"]) or None
            census_2011 = int(r["Census 2011 Code"]) or None
            rows.append({
                "lgd_state_id": lgd_id,
                "lgd_name": name,
                "lgd_name_short": display_name,
                "iso_alpha": iso,
                "slug": _slug(display_name),
                "eci_st_code": eci,
                "census_2001_code": census_2001,
                "census_2011_code": census_2011,
                "kind": "ut" if kind.upper() == "U" else "state",
            })
    rows.sort(key=lambda x: x["lgd_state_id"])
    doc = {
        "$schema": SCHEMA_REL,
        "$schema_version": "1.0",
        "$comment": (
            "Authoritative LGD state/UT register. Sourced from "
            "datasets/taxonomy/lgd/states-latest.csv (LGD portal snapshot via "
            "Ministry of Panchayati Raj). Joined with ECI st_code (the in-repo "
            "wikipedia.urls map) and ISO 3166-2:IN. See ADR-0050 + "
            "docs/concepts/lgd-authority.md. Builder: "
            "tools/migrate/build_lgd_states.py."
        ),
        "sources": [
            {
                "url": "https://lgdirectory.gov.in/",
                "fetched_at": "2026-05-24T20:25:59Z",
                "name": "Local Government Directory (LGD) - States register",
                "authority": "Ministry of Panchayati Raj, Government of India",
            }
        ],
        "states": rows,
    }
    OUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(REPO)} with {len(rows)} rows")


if __name__ == "__main__":
    main()
