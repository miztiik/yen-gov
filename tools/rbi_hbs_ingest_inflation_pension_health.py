"""Ingest RBI Handbook tables (HBS-IE 2024-25 + HBS-IS 2024-25) for inflation,
state pension, and state vital-stats / health indicators.

Emits 13 artifacts under datasets/indicators/in/{prices,fiscal,health}/.

This script is intentionally self-contained (no backend imports) — same
pragmatic pattern as ``rbi_hbs_ingest_state_gdp.py`` (the prior NSDP ingest).
Promote to ``backend/yen_gov/sources/rbi_hbs/`` once the second ingest pass
confirms the parser shape is stable.
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

ECON_CACHE = Path(".runtime/raw/rbi/handbook_economy_2024_25")
STATES_CACHE = Path(".runtime/raw/rbi/handbook_states_2024_25")
OUT = Path("datasets/indicators/in")

HBS_IE_LANDING = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy"
HBS_IS_LANDING = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States"
FETCHED_AT = datetime(2026, 5, 14, 19, 0, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

# State-name -> ECI-code map. RBI uses "&" not "and"; our reference uses "and".
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
    "Puducherry": "U07",
    "NCT of Delhi": "U05",
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
_CY_RX = re.compile(r"^\d{4}$")


def _year_label_to_time(label: object, calendar: bool) -> str | None:
    """Map an Excel year-label cell to our `time` string.

    Fiscal year '2014-15' -> '2014-04'.
    Calendar year 2014 (int or str) -> '2014'.
    Pension table suffixes '(A)' / '(RE)' / '(BE)' are stripped.
    """
    if isinstance(label, int) and 1900 <= label <= 2100:
        return str(label) if calendar else f"{label}-04"
    if not isinstance(label, str):
        return None
    s = label.strip()
    m = _FY_RX.match(s)
    if m:
        return f"{m.group(1)}-04"
    if _CY_RX.match(s):
        return s if calendar else f"{s}-04"
    return None


# ---------------------------------------------------------------------------
# Pattern A — National multi-base series (HBS-IE Tables 36 / 37)
# ---------------------------------------------------------------------------


def parse_national_multibase(
    xlsx: Path, sub_series_col_idx: int, sub_series_label: str
) -> dict[str, dict[str, float]]:
    """Read a national time-series workbook where rows are years (with
    interspersed '(Base : YYYY-YY = 100)' marker rows) and columns are
    sub-series. Returns ``{time: {base: value}}`` for the given column.
    """
    out: dict[str, dict[str, float]] = {}
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    current_base: str | None = None
    base_marker_rx = re.compile(r"\(Base\s*:?\s*(\d{4}(?:-\d{2,4})?)\s*=\s*100\)")
    for row in rows:
        c1 = row[1] if len(row) > 1 else None
        if isinstance(c1, str):
            m = base_marker_rx.search(c1)
            if m:
                current_base = m.group(1)
                continue
        if current_base is None:
            continue
        time = _year_label_to_time(c1, calendar=False)
        if time is None:
            continue
        v = _coerce(row[sub_series_col_idx]) if sub_series_col_idx < len(row) else None
        if v is None:
            continue
        out.setdefault(time, {})[current_base] = v
    wb.close()
    return out


def collapse_national(
    parsed: dict[str, dict[str, float]], base_priority: list[str]
) -> list[dict]:
    rows: list[dict] = []
    for time in sorted(parsed):
        by_base = parsed[time]
        chosen = next((b for b in base_priority if b in by_base), None)
        if chosen is None:
            continue
        rows.append({
            "entity_id": "IN",
            "time": time,
            "value": by_base[chosen],
            "vintage": f"Base {chosen} = 100",
        })
    return rows


def parse_national_simple(xlsx: Path, sub_series_col_idx: int) -> list[dict]:
    """Simpler walker for workbooks where base-marker rows are per-sub-series
    (e.g. T37 CPI, where '(Base : 2012 = 100 for New CPI)' applies only to
    cols 5-7 while '(Base : 2016 = 100 for CPI - IW)' applies only to col 2).
    We ignore markers entirely, walk every year row, and emit one (time,
    value) per non-null cell in the requested column. Splice/break metadata
    is conveyed via the indicator's ``series_breaks`` array instead.
    """
    out: list[dict] = []
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    for row in ws.iter_rows(values_only=True):
        c1 = row[1] if len(row) > 1 else None
        time = _year_label_to_time(c1, calendar=False)
        if time is None:
            continue
        v = _coerce(row[sub_series_col_idx]) if sub_series_col_idx < len(row) else None
        if v is None:
            continue
        out.append({"entity_id": "IN", "time": time, "value": v})
    wb.close()
    out.sort(key=lambda r: r["time"])
    return out


# ---------------------------------------------------------------------------
# Pattern B — State × year (rows = state, cols = years), one or two sheets.
# ---------------------------------------------------------------------------


def parse_state_year_table(
    xlsx: Path, header_row: int = 3, calendar: bool = False
) -> list[dict]:
    """Walk every sheet. Header row N is at index ``header_row`` (0-based);
    cells in cols 2+ are year labels. Subsequent rows have state name in col 1
    and value cells in cols 2+. Returns long-form ``[{entity_id, time, value}]``.

    For tables with two range-split sheets (e.g. T_171(i) + T_171(ii)), the
    same state appears in each sheet under disjoint year ranges; we union them
    in one output stream.
    """
    out: list[dict] = []
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    seen: set[tuple[str, str]] = set()  # de-dup if a year repeats across sheets
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
            t = _year_label_to_time(cell, calendar=calendar)
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


# ---------------------------------------------------------------------------
# Spec table — one entry per artifact
# ---------------------------------------------------------------------------

WPI_BASES = ["2011-12", "2004-05", "1993-94", "1981-82", "1970-71"]
CPI_IW_BASES = ["2016", "2001", "1982", "1960-61"]

SOURCE_RBI = "Reserve Bank of India (compiled from Office of the Economic Adviser, MoCI; or Labour Bureau, MoLE; per table)"
LICENSE_RBI = {
    "id": "RBI-publication",
    "name": "Reserve Bank of India publication (open for non-commercial use with attribution)",
    "url": "https://www.rbi.org.in/Scripts/Disclaimer.aspx",
    "redistributable": True,
}

# --- National inflation specs (driven by parse_national_multibase) ---

NATIONAL_SPECS = [
    {
        "out_path": "prices/national_wpi_all_commodities_index_annual.json",
        "id": "prices/national_wpi_all_commodities_index_annual",
        "title": "Wholesale Price Index — All Commodities (annual average, spliced)",
        "xlsx": ECON_CACHE / "T36_NationalWPI_AnnualAverage.xlsx",
        "table_label": "Table 36: Wholesale Price Index - Annual Average",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/36T_29082025046481C533F84F82AFDF9EA32C8176A1.XLSX",
        "landing": HBS_IE_LANDING,
        "sub_col_idx": 2,  # col B = year label, col C = AC (All Commodities)
        "sub_label": "All Commodities",
        "base_priority": WPI_BASES,
        "value_kind": "index",
        "unit": "index (rebased)",
        "time_grain": "fiscal_year",
        "description": (
            "Wholesale Price Index (All Commodities) — annual average, FY 1974-75 onwards, "
            "spliced across MoCI's five base-year revisions (1970-71 / 1981-82 / 1993-94 / "
            "2004-05 / 2011-12). Index level (rebased to most-recent base where overlap "
            "exists); convert to year-on-year inflation in the renderer rather than baking "
            "it into the artifact. WPI tracks producer-stage prices and excludes most "
            "services. It is shown here for the deep historical perspective only — RBI's "
            "official inflation anchor since the 2014 monetary-policy framework switch is "
            "CPI-Combined (see `prices/national_cpi_combined_index_annual`)."
        ),
        "notes": (
            "Source: RBI Handbook of Statistics on Indian Economy 2024-25 edition, Table 36. "
            "Each row's `vintage` records the WPI base year that produced the value. The "
            "WPI basket and methodology change at every rebase (commodity composition, "
            "weights, services treatment), so growth rates spanning a `series_breaks` "
            "transition should be read as directional, not exact."
        ),
    },
    {
        "out_path": "prices/national_cpi_iw_index_annual.json",
        "id": "prices/national_cpi_iw_index_annual",
        "title": "Consumer Price Index — Industrial Workers (annual average, spliced)",
        "xlsx": ECON_CACHE / "T37_NationalCPI_AnnualAverage.xlsx",
        "table_label": "Table 37: Consumer Price Index - Annual Average",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/37T_29082025B6355D5BDE984665BD7120E3C3596086.XLSX",
        "landing": HBS_IE_LANDING,
        "sub_col_idx": 2,  # col C = IW
        "sub_label": "Industrial Workers (CPI-IW)",
        "base_priority": CPI_IW_BASES,
        "value_kind": "index",
        "unit": "index (rebased)",
        "time_grain": "fiscal_year",
        "description": (
            "CPI for Industrial Workers (CPI-IW) — annual average from FY 1993-94 onwards "
            "in this series, the deepest continuous CPI India publishes. Compiled by the "
            "Labour Bureau (Ministry of Labour & Employment) from a basket of goods and "
            "services consumed by industrial-worker households across 88 centres, then "
            "national-averaged. Index level; convert to year-on-year inflation in the "
            "renderer. Compositionally urban-industrial, so it understates rural food-price "
            "experience — for the citizen 'cost of living' headline since 2012, prefer "
            "`prices/national_cpi_combined_index_annual` (RBI's monetary-policy anchor)."
        ),
        "notes": (
            "Source: RBI Handbook of Statistics on Indian Economy 2024-25 edition, Table 37, "
            "column 'IW'. Multiple base years stacked in the same column; the renderer "
            "should not compute growth rates that span a `series_breaks` rebase entry."
        ),
    },
    {
        "out_path": "prices/national_cpi_combined_index_annual.json",
        "id": "prices/national_cpi_combined_index_annual",
        "title": "Consumer Price Index — Combined (Rural+Urban), annual average",
        "xlsx": ECON_CACHE / "T37_NationalCPI_AnnualAverage.xlsx",
        "table_label": "Table 37: Consumer Price Index - Annual Average",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/37T_29082025B6355D5BDE984665BD7120E3C3596086.XLSX",
        "landing": HBS_IE_LANDING,
        "sub_col_idx": 7,  # col H = New CPI Combined (Rural+Urban)
        "sub_label": "CPI-Combined (Base 2012=100)",
        "base_priority": ["2012"],  # single base — the only one published
        "value_kind": "index",
        "unit": "index (Base 2012=100)",
        "time_grain": "fiscal_year",
        "description": (
            "All-India CPI-Combined (Rural+Urban) — annual average, base 2012=100, "
            "from FY 2014-15 onwards. This is the official cost-of-living benchmark "
            "the Reserve Bank of India is legally mandated to keep near 4% (within a "
            "2-6% band) under the 2016 monetary-policy framework. Citizen-relevant "
            "headline: roughly 46% food and beverages, 10% fuel and light, 10% housing, "
            "with the rest in clothing, transport, education, health, and other services. "
            "Convert to year-on-year inflation in the renderer; level is shipped here so "
            "future revisions remain traceable."
        ),
        "notes": (
            "Source: RBI Handbook of Statistics on Indian Economy 2024-25 edition, Table 37, "
            "column 'New CPI Combined (Rural+Urban)'. Single base (2012=100) — no splice "
            "needed within this artifact. For deeper history splice to `cpi_iw_index_annual` "
            "with explicit ratio-link in the renderer."
        ),
    },
]

INFLATION_SERIES_BREAKS_WPI = [
    {"at_time": "1981-04", "kind": "rebase", "note": "WPI rebase: 1970-71 → 1981-82 base. Basket and weights revised."},
    {"at_time": "1993-04", "kind": "rebase", "note": "WPI rebase: 1981-82 → 1993-94 base."},
    {"at_time": "2004-04", "kind": "rebase", "note": "WPI rebase: 1993-94 → 2004-05 base. Commodity basket modernised; services treatment expanded."},
    {"at_time": "2011-04", "kind": "rebase", "note": "WPI rebase: 2004-05 → 2011-12 base (current). Excise duty exclusion introduced; 'Combined' index dropped in favour of 'All Commodities'."},
]

INFLATION_SERIES_BREAKS_CPI_IW = [
    {"at_time": "1982-04", "kind": "rebase", "note": "CPI-IW rebase: 1960-61 → 1982 base. Basket of goods and centre coverage updated."},
    {"at_time": "2001-04", "kind": "rebase", "note": "CPI-IW rebase: 1982 → 2001 base."},
    {"at_time": "2016-04", "kind": "rebase", "note": "CPI-IW rebase: 2001 → 2016 base (current). Centres expanded from 78 to 88; basket reweighted post-2010 services consumption survey."},
]

# --- State indicator specs (driven by parse_state_year_table) ---

STATE_SPECS = [
    # ---- State CPI inflation (T108-T111) ----
    {
        "out_path": "prices/state_cpi_general_inflation_pct.json",
        "id": "prices/state_cpi_general_inflation_pct",
        "title": "State-wise CPI inflation (General) — annual average",
        "xlsx": STATES_CACHE / "T108_StateCpiGeneral.xlsx",
        "table_label": "Table 108: State-wise Average Inflation (CPI) - General",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/108T_111220251942D16B3BED4D73BE851D15D2329168.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": False,
        "value_kind": "rate",
        "unit": "% YoY",
        "time_grain": "fiscal_year",
        "direction": "neutral",
        "description": (
            "State-wise headline CPI inflation (General sub-index), year-on-year %, "
            "annual average per fiscal year. Sub-national sibling of the national "
            "`prices/national_cpi_combined_index_annual`. Tamil Nadu inflation can "
            "diverge meaningfully from Bihar inflation in any given year because of "
            "local food, fuel, and housing dynamics — citizens experience their own "
            "state's number, not the national average."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 108. RBI publishes already as YoY % inflation (not index level), so no further computation needed.",
    },
    {
        "out_path": "prices/state_cpi_food_inflation_pct.json",
        "id": "prices/state_cpi_food_inflation_pct",
        "title": "State-wise CPI inflation (Food and Beverages)",
        "xlsx": STATES_CACHE / "T109_StateCpiFood.xlsx",
        "table_label": "Table 109: State-wise Average Inflation (CPI) - Food and Beverages",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/109T_111220250E067E49350B48659E5A50C3D357BB46.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": False,
        "value_kind": "rate",
        "unit": "% YoY",
        "time_grain": "fiscal_year",
        "direction": "neutral",
        "description": (
            "State-wise CPI inflation in the Food and Beverages sub-basket — the "
            "single biggest household expenditure category (~46% of CPI-Combined). "
            "Food inflation is what citizens actually feel; it is also the most "
            "monsoon- and global-commodity-shock-driven sub-index, so swings here "
            "are largely supply-side, not policy-attributable."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 109.",
    },
    {
        "out_path": "prices/state_cpi_fuel_inflation_pct.json",
        "id": "prices/state_cpi_fuel_inflation_pct",
        "title": "State-wise CPI inflation (Fuel and Light)",
        "xlsx": STATES_CACHE / "T110_StateCpiFuel.xlsx",
        "table_label": "Table 110: State-wise Average Inflation (CPI) - Fuel and Light",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/110T_11122025784C1BDC2482496B9E25DA1BA4B38A3D.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": False,
        "value_kind": "rate",
        "unit": "% YoY",
        "time_grain": "fiscal_year",
        "direction": "neutral",
        "description": (
            "State-wise CPI inflation in the Fuel and Light sub-basket (LPG, kerosene, "
            "electricity tariffs, firewood). Driven by a mix of central petroleum "
            "policy, state electricity-tariff orders, and global crude. State variation "
            "reflects state-specific subsidy regimes (e.g. free electricity up to N "
            "units) and ESC-tariff slabs as much as supply shocks."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 110.",
    },
    {
        "out_path": "prices/state_cpi_housing_urban_inflation_pct.json",
        "id": "prices/state_cpi_housing_urban_inflation_pct",
        "title": "State-wise CPI inflation (Housing — Urban only)",
        "xlsx": STATES_CACHE / "T111_StateCpiHousingUrban.xlsx",
        "table_label": "Table 111: State-wise Average Inflation (CPI) - Housing (Urban)",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/111T_111220252F7D9704AB664C35A58770BAC73518DE.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": False,
        "value_kind": "rate",
        "unit": "% YoY",
        "time_grain": "fiscal_year",
        "direction": "neutral",
        "description": (
            "State-wise CPI Housing inflation, URBAN ONLY — NSO does not publish a "
            "rural housing CPI because rural housing in the CPI methodology is "
            "imputed from owner-occupied dwellings differently. Use this as the "
            "rent / urban housing-cost signal; it is structurally smoother than "
            "Food or Fuel and reflects mostly base-rent revisions in the surveyed "
            "centres."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 111. Coverage is urban centres only by methodology — not a yen-gov omission.",
    },
    # ---- State pension expenditure (T171) ----
    {
        "out_path": "fiscal/state_pension_expenditure_inr_crore.json",
        "id": "fiscal/state_pension_expenditure_inr_crore",
        "title": "State pension expenditure (revenue account)",
        "xlsx": STATES_CACHE / "T171_StatePension.xlsx",
        "table_label": "Table 171: State-wise Pension",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/171T_1112202558897643693142228AC6C769081FB16B.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": False,
        "value_kind": "currency",
        "unit": "INR (crore)",
        "time_grain": "fiscal_year",
        "direction": "neutral",
        "description": (
            "Annual state-government pension expenditure (revenue account, ₹ Crore) "
            "from FY 2004-05 onwards. Covers retirement and family pensions paid to "
            "state-government employees and pre-NPS hires; does NOT include the "
            "centrally-sponsored social-pension schemes (IGNOAPS, IGNWPS) or the "
            "National Pension System (NPS) contribution flows. Rapidly-growing line "
            "item in most state budgets — relevant to fiscal-sustainability and the "
            "Old Pension Scheme (OPS) restoration debate."
        ),
        "notes": (
            "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, "
            "Table 171. Suffix codes in column headers — '(A)' = Actuals, '(RE)' = "
            "Revised Estimates, '(BE)' = Budget Estimates — are stripped at parse "
            "time but the underlying revision tier should be considered when "
            "comparing FY24/FY25 with earlier years."
        ),
    },
    # ---- State health / vital statistics (T02, T03, T04, T06, T18) ----
    {
        "out_path": "health/state_birth_rate_per_1000.json",
        "id": "health/state_birth_rate_per_1000",
        "title": "Crude Birth Rate (per 1,000 population)",
        "xlsx": STATES_CACHE / "T02_BirthRate.xlsx",
        "table_label": "Table 2: State-wise Birth Rate",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/2T_11122025382C4BD8859E47A2B510B8A332E7A589.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": True,
        "value_kind": "rate",
        "unit": "per 1,000 population",
        "time_grain": "year",
        "direction": "neutral",
        "description": (
            "Crude Birth Rate — number of live births per 1,000 mid-year population, "
            "calendar-year. Sourced via SRS (Sample Registration System), Office of "
            "the Registrar General of India. Trending downward across all states "
            "(India's demographic transition); compare with TFR for the policy-"
            "relevant fertility lens. NEUTRAL direction — neither high nor low is "
            "intrinsically 'good' (high CBR may reflect poverty + low female "
            "agency; very low CBR plus long life expectancy = ageing-population "
            "fiscal stress)."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 2 (SRS, Registrar General).",
    },
    {
        "out_path": "health/state_death_rate_per_1000.json",
        "id": "health/state_death_rate_per_1000",
        "title": "Crude Death Rate (per 1,000 population)",
        "xlsx": STATES_CACHE / "T03_DeathRate.xlsx",
        "table_label": "Table 3: State-wise Death Rate",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/3T_111220254D0C628610584647A785A4DC76884B04.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": True,
        "value_kind": "rate",
        "unit": "per 1,000 population",
        "time_grain": "year",
        "direction": "neutral",
        "description": (
            "Crude Death Rate — deaths per 1,000 mid-year population, calendar-year. "
            "Crude in the sense that it is unadjusted for age structure: states with "
            "older populations (Kerala, Tamil Nadu) will show structurally higher CDR "
            "than states with younger populations (Bihar, UP), without that meaning "
            "they are 'less healthy'. Pair with Life Expectancy and Infant Mortality "
            "for a properly age-controlled mortality picture."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 3 (SRS, Registrar General).",
    },
    {
        "out_path": "health/state_infant_mortality_rate_per_1000.json",
        "id": "health/state_infant_mortality_rate_per_1000",
        "title": "Infant Mortality Rate (per 1,000 live births)",
        "xlsx": STATES_CACHE / "T04_InfantMortalityRate.xlsx",
        "table_label": "Table 4: State-wise Infant Mortality Rate",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/4T_11122025025F203A250E46CAB963946C776ADBAF.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": True,
        "value_kind": "rate",
        "unit": "per 1,000 live births",
        "time_grain": "year",
        "direction": "lower_is_better",
        "description": (
            "Infant Mortality Rate — deaths of children under one year of age per "
            "1,000 live births, calendar-year. The single most cited summary of a "
            "state's public-health performance, because it integrates antenatal care, "
            "institutional delivery quality, neonatal nutrition, and immunisation "
            "coverage. India's IMR has fallen from ~58 in 2004 to under 30 in 2023, "
            "but the inter-state spread is still wide (Kerala under 7; MP/UP near 30)."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 4 (SRS, Registrar General).",
    },
    {
        "out_path": "health/state_total_fertility_rate.json",
        "id": "health/state_total_fertility_rate",
        "title": "Total Fertility Rate (children per woman)",
        "xlsx": STATES_CACHE / "T06_TotalFertilityRate.xlsx",
        "table_label": "Table 6: State-wise Total Fertility Rate",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/6T_11122025339F4339AA23421F863E7B21428C8460.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 2,
        "calendar": True,
        "value_kind": "rate",
        "unit": "births per woman (lifetime)",
        "time_grain": "year",
        "direction": "neutral",
        "description": (
            "Total Fertility Rate — average number of children a woman would bear "
            "over her lifetime at current age-specific fertility rates. Replacement "
            "level is conventionally 2.1; India's national TFR fell below replacement "
            "around 2020. Below-replacement TFR has direct downstream consequences "
            "for school-age population, working-age share, dependency ratio, and "
            "long-run fiscal pension sustainability — relevant context for "
            "`fiscal/state_pension_expenditure_inr_crore`."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 6 (SRS, Registrar General).",
    },
    {
        "out_path": "health/state_public_health_expenditure_inr_crore.json",
        "id": "health/state_public_health_expenditure_inr_crore",
        "title": "State public expenditure on health",
        "xlsx": STATES_CACHE / "T18_PublicHealthExpenditure.xlsx",
        "table_label": "Table 18: State-wise Public Expenditure on Health",
        "snapshot_url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/18T_11122025768C98BEB7A5493EA2E2EFFFEDDA7C46.XLSX",
        "landing": HBS_IS_LANDING,
        "header_row": 3,
        "calendar": False,
        "value_kind": "currency",
        "unit": "INR (crore)",
        "time_grain": "fiscal_year",
        "direction": "neutral",
        "description": (
            "Annual public expenditure on health, by state, ₹ Crore — captures "
            "Medical & Public Health, Family Welfare, and Water Supply & Sanitation "
            "heads of the state revenue + capital accounts. Coverage is FY 2012-13 "
            "to FY 2019-20 in this RBI edition; for citizen-relevant comparisons "
            "normalise by population (per-capita) or by GSDP (% of GSDP). Direction "
            "is `neutral` not `higher_is_better` because spending is an INPUT, not "
            "an OUTCOME — pair with Infant Mortality / Life Expectancy for the "
            "value-for-money story."
        ),
        "notes": "Source: RBI Handbook of Statistics on Indian States 2024-25 edition, Table 18.",
    },
]


def _build_artifact(spec: dict, rows: list[dict], series_breaks: list[dict] | None = None) -> dict:
    times = sorted({r["time"] for r in rows})
    entities = sorted({r["entity_id"] for r in rows})
    indicator = {
        "id": spec["id"],
        "title": spec["title"],
        "description": spec["description"],
        "entity_kind": "country" if entities == ["IN"] else "state",
        "time_grain": spec["time_grain"],
        "value_kind": spec["value_kind"],
        "direction": spec.get("direction", "neutral"),
        "scale_hint": "linear",
        "unit": spec["unit"],
        "icon": spec.get("icon", "trending-up"),
        "attribution_geography": spec.get("attribution_geography", "where_resident"),
        "comparability": spec.get("comparability", "comparable_with_normalisation"),
        "implementing_authority": spec.get("implementing_authority", "centre"),
        "methodology_vintage": spec.get("methodology_vintage", "RBI Handbook 2024-25 edition"),
        "notes": spec["notes"],
    }
    if series_breaks:
        indicator["series_breaks"] = series_breaks
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
                "url": spec["landing"],
                "fetched_at": FETCHED_AT,
                "name": "RBI Handbook landing page",
                "authority": "Reserve Bank of India",
            },
        ],
        "license": LICENSE_RBI,
        "coverage": {
            "spatial": "India" if entities == ["IN"] else f"India (states + UTs); {len(entities)} entities",
            "temporal": f"{times[0]}..{times[-1]}",
            "admin_level": "country" if entities == ["IN"] else "state",
        },
        "indicator": indicator,
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
    print("\n=== National inflation (HBS-IE Tables 36, 37) ===")
    for spec in NATIONAL_SPECS:
        is_wpi = spec["id"].endswith("national_wpi_all_commodities_index_annual")
        if is_wpi:
            parsed = parse_national_multibase(spec["xlsx"], spec["sub_col_idx"], spec["sub_label"])
            rows = collapse_national(parsed, spec["base_priority"])
        else:
            # T37 CPI: per-sub-series base markers — use simple walker.
            rows = parse_national_simple(spec["xlsx"], spec["sub_col_idx"])
        if not rows:
            print(f"  WARN no rows for {spec['id']}")
            continue
        breaks = None
        if is_wpi:
            breaks = INFLATION_SERIES_BREAKS_WPI
        elif spec["id"].endswith("national_cpi_iw_index_annual"):
            breaks = INFLATION_SERIES_BREAKS_CPI_IW
        art = _build_artifact(spec, rows, series_breaks=breaks)
        _write(spec, art)

    print("\n=== State indicators (HBS-IS) ===")
    for spec in STATE_SPECS:
        rows = parse_state_year_table(spec["xlsx"], spec["header_row"], spec["calendar"])
        if not rows:
            print(f"  WARN no rows for {spec['id']}")
            continue
        art = _build_artifact(spec, rows)
        _write(spec, art)


if __name__ == "__main__":
    main()
