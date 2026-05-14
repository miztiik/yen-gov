"""Ingest RBI Handbook of Statistics on Indian States (HBS-IS) 2024-25 Power
section — Tables 138, 139, 140, 141.

Emits 4 state × fiscal-year artifacts under datasets/indicators/in/energy/:

  - state_per_capita_availability_kwh.json  (T138)
  - state_power_availability_mu.json        (T139)
  - state_installed_capacity_total_mw.json  (T140)
  - state_power_requirement_mu.json         (T141)

Coverage span FY 2004-05 .. FY 2024-25 (21 fiscal years). Aggregate values
only — RBI's HBS-IS does NOT publish a state × fuel-source breakdown in the
Power section. For source-mix data see the CEA monthly archive (separate
adapter, planned).

Why a sibling tool instead of extending rbi_hbs_ingest_inflation_pension_health.py:
keeping each thematic pull (inflation, health, power) in its own script keeps
the spec table short and the run-time tractable when re-emitting just one
artifact during iteration. Promote all three to backend/yen_gov/sources/rbi_hbs/
once the parser shape stays stable across one more edition.
"""
from __future__ import annotations

import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

STATES_CACHE = Path(".runtime/raw/rbi/handbook_states_2024_25")
OUT = Path("datasets/indicators/in")

HBS_IS_LANDING = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States"
FETCHED_AT = datetime(2026, 5, 14, 19, 30, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

# Same map used by the inflation/health ingest. Kept inline to keep this script
# self-contained (no shared module yet — promote when patterns settle).
NAME_TO_ECI = {
    "Andhra Pradesh": "S01",
    "Arunachal Pradesh": "S02",
    "Assam": "S03",
    "Bihar": "S04",
    "Chhattisgarh": "S26",
    "Goa": "S05",
    "Gujarat": "S06",
    "Haryana": "S07",
    "Himachal Pradesh": "S08",
    "Jammu & Kashmir": "U08",
    "Jharkhand": "S27",
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
    "Telangana": "S29",
    "Tripura": "S23",
    "Uttar Pradesh": "S24",
    "Uttarakhand": "S28",
    "West Bengal": "S25",
    "Andaman & Nicobar Islands": "U01",
    "Chandigarh": "U02",
    "Delhi": "U05",
    "NCT of Delhi": "U05",
    "Puducherry": "U07",
    "Lakshadweep": "U04",
    "Dadra & Nagar Haveli": "U03",
    "Dadra and Nagar Haveli and Daman and Diu": "U03",
    "Daman & Diu": "U03",
}


def _coerce(v: object) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s in ("-", ".", "", "*", "NA", "n.a.", "—"):
            return None
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return None
    return None


_FY_RX = re.compile(r"^(\d{4})-(\d{2,4})(?:\s*\([A-Z]+\))?$")


def _fy_label_to_time(label: object) -> str | None:
    if isinstance(label, int) and 1900 <= label <= 2100:
        return f"{label}-04"
    if not isinstance(label, str):
        return None
    s = label.strip()
    m = _FY_RX.match(s)
    if m:
        return f"{m.group(1)}-04"
    return None


def parse_state_year_table(xlsx: Path, header_row: int = 3) -> list[dict]:
    """Walk every sheet. Header row is at index ``header_row`` (0-based);
    cells in cols 2+ are FY labels like '2004-05'. Subsequent rows have the
    state name in col 1. The two-sheet split (T_NNN(i) FY05-FY13 +
    T_NNN(ii) FY14-FY25) is unioned automatically.
    """
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    for sname in wb.sheetnames:
        ws = wb[sname]
        rows = list(ws.iter_rows(values_only=True))
        if header_row >= len(rows):
            continue
        header = rows[header_row]
        col_to_time: dict[int, str] = {}
        for ci, cell in enumerate(header):
            if ci < 2:
                continue
            t = _fy_label_to_time(cell)
            if t:
                col_to_time[ci] = t
        if not col_to_time:
            continue
        for row in rows[header_row + 1:]:
            label = row[1] if len(row) > 1 else None
            if not isinstance(label, str):
                continue
            name = label.strip()
            eid = NAME_TO_ECI.get(name)
            if eid is None:
                continue
            for ci, time in col_to_time.items():
                v = _coerce(row[ci]) if ci < len(row) else None
                if v is None:
                    continue
                key = (eid, time)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"entity_id": eid, "time": time, "value": v})
    wb.close()
    out.sort(key=lambda r: (r["entity_id"], r["time"]))
    return out


SOURCE_RBI = "Reserve Bank of India (compiled from Central Electricity Authority, Ministry of Power)"
LICENSE_RBI = {
    "id": "RBI-publication",
    "name": "Reserve Bank of India publication (open for non-commercial use with attribution)",
    "url": "https://www.rbi.org.in/Scripts/Disclaimer.aspx",
    "redistributable": True,
}

SPECS = [
    {
        "out_path": "energy/state_per_capita_availability_kwh.json",
        "id": "energy/state_per_capita_availability_kwh",
        "title": "State-wise per-capita availability of power",
        "xlsx": STATES_CACHE / "T138_PerCapitaAvailabilityOfPower.xlsx",
        "table_label": "Table 138: State-wise Per Capita Availability of Power",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/138T_111220252D21BC51E5A842E4B25E954391C10A41.XLSX",
        "value_kind": "raw",
        "unit": "kWh per person per year",
        "icon": "zap",
        "direction": "higher_is_better",
        "description": (
            "Annual per-capita electricity availability (kWh / person / year), by "
            "state and Union Territory, fiscal year. Computed by CEA as state "
            "energy availability (MU) ÷ state mid-year population. The most "
            "citizen-relevant single number for 'how much power do people in this "
            "state actually get to use' — captures both supply expansion and "
            "transmission losses. The all-India figure roughly tripled from "
            "~600 kWh in FY05 to ~1300 kWh in FY24, but the inter-state spread "
            "is wide (Goa / Punjab / Gujarat above 2,000; Bihar / Manipur / "
            "Nagaland still below 400)."
        ),
        "notes": (
            "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, "
            "Table 138. Originating data: Central Electricity Authority, Ministry "
            "of Power. Per-capita is on geographical-area population (resident), "
            "not consumption-weighted — large industrial-export states (e.g. "
            "Chhattisgarh, Sikkim) post inflated numbers because the power they "
            "generate is consumed elsewhere."
        ),
    },
    {
        "out_path": "energy/state_power_availability_mu.json",
        "id": "energy/state_power_availability_mu",
        "title": "State-wise availability of power (MU)",
        "xlsx": STATES_CACHE / "T139_AvailabilityOfPower.xlsx",
        "table_label": "Table 139: State-wise Availability of Power",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/139T_111220256569FF1C11E248B7A8ED64D31C999776.XLSX",
        "value_kind": "raw",
        "unit": "MU (million units = GWh)",
        "icon": "zap",
        "direction": "higher_is_better",
        "description": (
            "Annual availability of energy in the state (MU = million units = GWh), "
            "fiscal year. 'Availability' is the energy actually supplied to the "
            "state grid after accounting for inter-state imports / exports and "
            "transmission losses — i.e. what was put on the bus for distribution "
            "companies to sell to consumers. Read alongside Power Requirement "
            "(T141) — the gap between requirement and availability is the "
            "'energy not supplied' (deficit), which CEA tracks separately."
        ),
        "notes": (
            "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, "
            "Table 139. Originating data: Central Electricity Authority. Note that "
            "'availability' is a transmission-side metric, not consumption — "
            "for actual electricity sold to end users see ICED-derived "
            "`energy/state_electricity_sales_mu.json`."
        ),
    },
    {
        "out_path": "energy/state_installed_capacity_total_mw.json",
        "id": "energy/state_installed_capacity_total_mw",
        "title": "State-wise installed capacity of power (MW)",
        "xlsx": STATES_CACHE / "T140_InstalledCapacityOfPower.xlsx",
        "table_label": "Table 140: State-wise Installed Capacity of Power",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/140T_111220254D8DA0B69B444492B6E9BAF30F3395C8.XLSX",
        "value_kind": "raw",
        "unit": "MW",
        "icon": "zap",
        "direction": "higher_is_better",
        "description": (
            "Total installed electricity-generation capacity located in the state "
            "(MW), end-of-fiscal-year. Aggregate of all fuel sources (coal, gas, "
            "diesel, nuclear, hydro, renewable). For the state × source breakdown "
            "RBI's Handbook does not publish — see CEA monthly Executive Summary "
            "for that. This RBI series gives the deepest continuous all-source "
            "total: 21 fiscal years (FY05 → FY25) versus 10 years from the "
            "ICED-derived sibling `energy/state_installed_capacity_geographical_mw`. "
            "Prefer this RBI series for long-history charts; ICED for the most "
            "recent year's sub-aggregates."
        ),
        "notes": (
            "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, "
            "Table 140. Originating data: Central Electricity Authority. "
            "Capacity is geographically located — power-trading states "
            "(e.g. Chhattisgarh exports much of its thermal output) appear "
            "with capacity disproportionate to their consumption. Compare "
            "with `state_per_capita_availability_kwh` for the consumption-side "
            "view."
        ),
    },
    {
        "out_path": "energy/state_power_requirement_mu.json",
        "id": "energy/state_power_requirement_mu",
        "title": "State-wise power requirement (MU)",
        "xlsx": STATES_CACHE / "T141_PowerRequirement.xlsx",
        "table_label": "Table 141: State-wise Power Requirement",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/141T_11122025615E98A72EA6475CAACFFD12FFC83057.XLSX",
        "value_kind": "raw",
        "unit": "MU (million units = GWh)",
        "icon": "zap",
        "direction": "neutral",
        "description": (
            "Annual energy requirement assessed by the state (MU = million units "
            "= GWh), fiscal year — the demand-side counterpart to Availability "
            "(T139). Requirement minus availability gives the 'energy not "
            "supplied' deficit; the percentage gap (deficit / requirement) is "
            "the headline 'power deficit %' India tracked closely through the "
            "2000s. The all-India deficit shrank from ~10% in FY05 to under "
            "0.5% from FY18 onwards as supply caught up; persistent state-level "
            "deficits today flag distribution / scheduling issues, not "
            "generation shortage."
        ),
        "notes": (
            "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, "
            "Table 141. Originating data: Central Electricity Authority. "
            "Direction is neutral because higher requirement reflects "
            "industrial activity (good) and / or inefficient consumption "
            "(not good) — interpret in conjunction with per-capita GSDP and "
            "T-and-D loss series."
        ),
    },
]


def _build_artifact(spec: dict, rows: list[dict]) -> dict:
    times = sorted({r["time"] for r in rows})
    entities = sorted({r["entity_id"] for r in rows})
    return {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "1.3",
        "sources": [
            {
                "url": spec["snapshot_url"],
                "fetched_at": FETCHED_AT,
                "name": f"RBI Handbook 2024-25 — {spec['table_label']}",
                "authority": SOURCE_RBI,
            },
            {
                "url": HBS_IS_LANDING,
                "fetched_at": FETCHED_AT,
                "name": "RBI Handbook of Statistics on Indian States — landing page",
                "authority": "Reserve Bank of India",
            },
        ],
        "license": LICENSE_RBI,
        "coverage": {
            "spatial": f"India (states + UTs); {len(entities)} entities",
            "temporal": f"{times[0]}..{times[-1]}",
            "admin_level": "state",
        },
        "indicator": {
            "id": spec["id"],
            "title": spec["title"],
            "description": spec["description"],
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": spec["value_kind"],
            "direction": spec.get("direction", "neutral"),
            "scale_hint": "linear",
            "unit": spec["unit"],
            "icon": spec.get("icon", "zap"),
            "attribution_geography": "where_administered",
            "comparability": "comparable_with_normalisation",
            "implementing_authority": "centre",
            "methodology_vintage": (
                "RBI Handbook of Statistics on Indian States 2024-25 edition; "
                "originating data Central Electricity Authority, Ministry of Power."
            ),
            "notes": spec["notes"],
        },
        "rows": rows,
    }


def _write(spec: dict, art: dict) -> None:
    path = OUT / spec["out_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(art, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = art["rows"]
    times = sorted({r["time"] for r in rows})
    entities = sorted({r["entity_id"] for r in rows})
    print(f"  wrote {path}  rows={len(rows)} entities={len(entities)} span={times[0]}..{times[-1]}")


def main() -> None:
    print("=== HBS-IS Power section (T138-T141) ===")
    for spec in SPECS:
        rows = parse_state_year_table(spec["xlsx"], header_row=3)
        if not rows:
            print(f"  WARN no rows for {spec['id']}")
            continue
        art = _build_artifact(spec, rows)
        _write(spec, art)


if __name__ == "__main__":
    main()
