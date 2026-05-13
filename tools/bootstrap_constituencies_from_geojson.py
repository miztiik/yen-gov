"""Bootstrap constituencies.json for the 9 still-gapped legislative jurisdictions.

Source of truth: on-disk HindustanTimesLabs 2008-Delimitation per-state GeoJSONs
under datasets/boundaries/in/geojson/ (snapshotted in commit 8ce2c71). Each
feature carries AC_NO + AC_NAME, which is the authoritative pair we need.

Reservation status (SC/ST/GEN) is NOT carried by the HTL geojsons. Per Holy
Law #6 (no hardcoding) and #7 (no fabrication), we default reservation="GEN"
and ship status="provisional" with an explicit notes field on the file
flagging the limitation. A subsequent ECI Statistical Report Section 3 ingest
or Wikipedia AC-table parse can later overlay verified SC/ST flags.

Run from repo root: python tools/bootstrap_constituencies_from_geojson.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GEOJSON_ROOT = REPO / "datasets" / "boundaries" / "in" / "geojson"
OUT_ROOT = REPO / "datasets" / "reference" / "in" / "states"
SCHEMA_URL = "https://yen-gov.github.io/schemas/constituency.schema.json"
FETCHED_AT = "2026-05-13T00:00:00Z"

# 8 jurisdictions: HTL upstream is post-2008-delimitation for these. S14
# Manipur is intentionally NOT in this list — HTL ships pre-delim 68-AC data
# for Manipur, so it is bootstrapped separately from Wikipedia by
# tools/scrape_manipur_acs.py.
TARGETS = [
    ("S06", "gujarat",        "Gujarat",        182),
    ("S15", "meghalaya",      "Meghalaya",       60),
    ("S17", "nagaland",       "Nagaland",        60),
    ("S19", "punjab",         "Punjab",         117),
    ("S20", "rajasthan",      "Rajasthan",      200),
    ("S23", "tripura",        "Tripura",         60),
    ("S24", "uttarpradesh",   "Uttar Pradesh",  403),
    ("S28", "uttarakhand",    "Uttarakhand",     70),
]


def _prop(props: dict, *names: str):
    for n in names:
        if n in props:
            return props[n]
    return None


def author(state: str, slug: str, display_name: str, expected: int) -> tuple[Path, int, int]:
    geojson = GEOJSON_ROOT / f"{state}-ac.geojson"
    data = json.loads(geojson.read_text(encoding="utf-8"))
    seen: dict[int, dict] = {}
    for feat in data["features"]:
        props = feat["properties"]
        ac_no = _prop(props, "AC_NO", "ac_no")
        ac_name = _prop(props, "AC_NAME", "ac_name")
        if ac_no is None or ac_name is None:
            continue
        try:
            eci_no = int(ac_no)
        except (TypeError, ValueError):
            continue
        name = str(ac_name).strip()
        if eci_no <= 0 or not name:
            continue
        # First occurrence wins (HTL occasionally splits an AC across rows).
        if eci_no in seen:
            continue
        seen[eci_no] = {
            "eci_no": eci_no,
            "name": name,
            "reservation": "GEN",
        }
    rows = [seen[k] for k in sorted(seen)]

    sources = [{
        "url": (
            "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/"
            f"master/state_ut/{slug}/assembly/{slug}_AC.json"
        ),
        "fetched_at": FETCHED_AT,
        "name": f"HindustanTimesLabs shapefiles — {display_name} 2008 Delimitation Assembly Constituencies",
        "authority": "HindustanTimesLabs (MIT)",
    }]

    doc = {
        "$schema": SCHEMA_URL,
        "$schema_version": "4.1",
        "sources": sources,
        "state": state,
        "body": "AC",
        "status": "provisional",
        "constituencies": rows,
    }
    out = OUT_ROOT / state / "constituencies.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return out, len(rows), expected


if __name__ == "__main__":
    for state, slug, name, expected in TARGETS:
        out, count, exp = author(state, slug, name, expected)
        rel = out.relative_to(REPO).as_posix()
        flag = "OK" if count == exp else f"DIFFERS (expected {exp})"
        print(f"  {state} {name:18} {count:>3} ACs  [{flag}]  {rel}")
