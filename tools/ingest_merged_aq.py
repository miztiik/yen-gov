"""Ingest MoSPI National Accounts Statistics (annual + quarterly) from
``datasets/ephemeral_datasets/Merged_Annually_Quarterly.csv``.

Decisions locked 2026-05-14 (per Governance Strategist consult + user direction):

* **Constant-price as canonical.** Constant-price (base 2011-12) matches every
  international tracker (IMF WEO, World Bank WDI ``NY.GDP.MKTP.KD``, OECD SNA,
  RBI Annual Report Statement 1, MoSPI press notes lead with constant-price
  growth). We do NOT ship the current-price column at all in v1; nominal-vs-real
  citizen confusion is the larger risk.
* **Drop subindustry rows.** 17-industry (NIC-1 digit) tier is the citizen-front
  story; subindustry (Crops vs Livestock, etc.) is a sectoral-policy researcher's
  lens that earns its keep only behind an explicit deep-dive toggle.
* **Drop pre-computed growth-rate rows.** MoSPI uses fixed-base accounts (no
  chain-weighting), so naive ``(Y_t - Y_{t-1}) / Y_{t-1}`` on the constant-price
  level series matches MoSPI's published growth to the last decimal. One source
  of truth — the level series — at build time.
* **Latest-final revision per (indicator, year).** Multiple revision tiers
  collapse to one canonical row; the chosen vintage is stamped per row via the
  schema 1.3 ``vintage`` field so the chart can disclose "FY 2025-26 may
  still revise".
* **Use 2011-12 base only.** The 2022-23 rebased series is sparse (~5 years)
  and not yet splice-able with the long history; revisit when MoSPI publishes
  the official link factor (FY27).

Emits three artifacts under ``datasets/indicators/in/economy/``:

  1. ``national_macro_aggregates_constant_2011_12_inr_crore.json`` — long-format
     headline aggregates (GDP, GVA, NDP, GFCF, Gross Saving, PFCE, GFCE,
     Imports/Exports, Change in Stock, Valuables, Net Taxes, Consumption of
     Fixed Capital, GNI, GNDI), faceted by indicator name.
  2. ``national_gva_by_industry_constant_2011_12_inr_crore.json`` — annual
     GVA by 17-industry, faceted by industry.
  3. ``national_gva_by_industry_quarterly_constant_2011_12_inr_crore.json`` —
     quarterly GVA by industry; ``time_grain: quarter``, time as ``YYYY-MM``
     (Q1 -> YYYY-04, Q2 -> YYYY-07, Q3 -> YYYY-10, Q4 -> (Y+1)-01).

Source: data.gov.in mirror of MoSPI National Accounts Statistics consolidated
across press-note vintages. Per the user-approved domain-level provenance
policy, ``url`` is the data.gov.in domain root.
"""
from __future__ import annotations
import csv
import io
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "datasets" / "ephemeral_datasets" / "Merged_Annually_Quarterly.csv"
OUT_DIR = ROOT / "datasets" / "indicators" / "in" / "economy"
SCHEMA_REL = "https://yen-gov.github.io/schemas/indicator.schema.json"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

# Revision rank: higher = more final. Picked per (indicator, year, facet).
REVISION_RANK = {
    "First Advance Estimates": 1,
    "Second Advance Estimates": 2,
    "Provisional Estimates": 3,
    "First Revised Estimates": 4,
    "Second Revised Estimates": 5,
    "Third Revised Estimates": 6,
    "Final Estimates": 7,
    "Additional Revision": 8,
}

# Indicators to keep in the headline-aggregates artifact (#1). All national,
# no industry/sector facet.
HEADLINE_INDICATORS = {
    "Gross Domestic Product",
    "Gross Value Added",
    "Net Domestic Product",
    "Gross National Income",
    "Gross National Disposable Income",
    "Gross Fixed Capital Formation",
    "Gross Saving",
    "Consumption of Fixed Capital",
    "Private Final Consumption Expenditure",
    "Government Final Consumption Expenditure",
    "Change in Stock",
    "Valuables",
    "Export of Goods and Services",
    "Import of Goods and Services",
    "Net Taxes on Products",
    "Taxes on Products",
    "Subsidies on Products",
    "Primary Income Receivable Net From Row",
    "Other Current Transfers Net From Row",
}

# 17-industry NIC-1 tier for artifacts #2 and #3. Excludes subindustry rows
# and the rolled-up "Total Gross Value Added" line.
INDUSTRY_TIER_1 = {
    "Agriculture, Livestock, Forestry and Fishing",
    "Mining and Quarrying",
    "Manufacturing",
    "Electricity, Gas, Water Supply & Other Utility Services",
    "Construction",
    "Trade, Repair, Hotels and Restaurants",
    "Trade, Hotels, Transport, Communication & Services Related to Broadcasting",
    "Transport, Storage, Communication & Services Related to Broadcasting",
    "Financial, Real Estate & Professional Services",
    "Financial Services",
    "Real Estate, Ownership of Dwelling & Professional Services",
    "Public Administration, Defence & Other Services",
    "Public Administration and Defence",
    "Other Services",
}

SOURCES = [{
    "url": "https://www.data.gov.in/",
    "fetched_at": NOW,
    "name": "MoSPI National Accounts Statistics — consolidated annual + quarterly NAS series (data.gov.in mirror)",
    "authority": "Ministry of Statistics and Programme Implementation (National Statistical Office)",
}]
LICENSE = {
    "id": "GoI-OpenData",
    "name": "Government of India Open Data License",
    "url": "https://www.data.gov.in/government-open-data-license-india",
    "redistributable": True,
}


def parse_year_to_fy(y: str) -> str | None:
    """Map a `year` cell to fiscal_year time `YYYY-04`.

    `1999`        -> `1999-04`  (FY 1999-2000)
    `2008-09`     -> `2008-04`
    `2025-26`     -> `2025-04`
    """
    y = (y or "").strip()
    if not y:
        return None
    if len(y) == 4 and y.isdigit():
        return f"{y}-04"
    if len(y) >= 7 and y[4] == "-":
        try:
            return f"{int(y[:4]):04d}-04"
        except ValueError:
            return None
    return None


QUARTER_TO_MONTH = {"Q1": "04", "Q2": "07", "Q3": "10", "Q4": "01"}


def parse_year_quarter_to_time(y: str, q: str) -> str | None:
    """Map (year, quarter) to a `YYYY-MM` time at the quarter's start month.

    Q4 spans Jan-Mar of the FY's CALENDAR-end year, so e.g. `2024-25` Q4
    maps to `2025-01`, not `2024-01`.
    """
    yfy = parse_year_to_fy(y)
    if not yfy or q not in QUARTER_TO_MONTH:
        return None
    yi = int(yfy[:4])
    mm = QUARTER_TO_MONTH[q]
    if q == "Q4":
        yi += 1
    return f"{yi:04d}-{mm}"


def safe_float(s: str) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Read CSV
# ---------------------------------------------------------------------------
with SRC.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
print(f"loaded {len(rows)} rows")


# Filter: base_year=2011-12, unit=₹ Crore (drop growth-rate rows), drop subindustry
def keep_base(r):
    return r["base_year"] == "2011-12"


def is_currency_row(r):
    return r["unit"].endswith("Crore")  # handles "₹ Crore" w/ any encoding


# ---------------------------------------------------------------------------
# Artifact 1: headline aggregates (annual, faceted by indicator)
# ---------------------------------------------------------------------------
# Group by (indicator, time) with subindustry blank and institutional_sector
# blank (we want pure national totals, not the sector-decomposition rows
# that share indicator names like "Gross Fixed Capital Formation").
agg_keep: dict[tuple[str, str], dict] = {}
for r in rows:
    if not keep_base(r) or not is_currency_row(r):
        continue
    if r["frequency"] != "Annual":
        continue
    if r["indicator"] not in HEADLINE_INDICATORS:
        continue
    if r["industry"] or r["subindustry"] or r["institutional_sector"]:
        # Skip industry/sector decomposition rows; we want the pure national
        # total per indicator. Industry-faceted GVA goes to artifact #2.
        continue
    t = parse_year_to_fy(r["year"])
    if not t:
        continue
    v = safe_float(r["constant_price"])
    if v is None:
        continue
    rev_rank = REVISION_RANK.get(r["revision"], 0)
    key = (r["indicator"], t)
    cur = agg_keep.get(key)
    if cur is None or rev_rank > cur["_rev_rank"]:
        agg_keep[key] = {
            "_rev_rank": rev_rank,
            "facet": r["indicator"],
            "time": t,
            "value": v,
            "vintage": r["revision"] or None,
        }

agg_rows = sorted(
    ({"entity_id": "IN", "time": d["time"], "value": d["value"], "facet": d["facet"], "vintage": d["vintage"]}
     for d in agg_keep.values()),
    key=lambda r: (r["facet"], r["time"]),
)
print(f"\nartifact 1 (macro aggregates annual): {len(agg_rows)} rows; "
      f"{len({r['facet'] for r in agg_rows})} indicators; "
      f"{len({r['time'] for r in agg_rows})} fiscal years")


# ---------------------------------------------------------------------------
# Artifact 2: national GVA by industry (annual)
# ---------------------------------------------------------------------------
gva_a_keep: dict[tuple[str, str], dict] = {}
for r in rows:
    if not keep_base(r) or not is_currency_row(r):
        continue
    if r["frequency"] != "Annual":
        continue
    if r["indicator"] != "Gross Value Added":
        continue
    if r["industry"] not in INDUSTRY_TIER_1 or r["subindustry"]:
        continue
    t = parse_year_to_fy(r["year"])
    if not t:
        continue
    v = safe_float(r["constant_price"])
    if v is None:
        continue
    rev_rank = REVISION_RANK.get(r["revision"], 0)
    key = (r["industry"], t)
    cur = gva_a_keep.get(key)
    if cur is None or rev_rank > cur["_rev_rank"]:
        gva_a_keep[key] = {
            "_rev_rank": rev_rank,
            "facet": r["industry"],
            "time": t,
            "value": v,
            "vintage": r["revision"] or None,
        }

gva_a_rows = sorted(
    ({"entity_id": "IN", "time": d["time"], "value": d["value"], "facet": d["facet"], "vintage": d["vintage"]}
     for d in gva_a_keep.values()),
    key=lambda r: (r["facet"], r["time"]),
)
print(f"artifact 2 (gva by industry annual): {len(gva_a_rows)} rows; "
      f"{len({r['facet'] for r in gva_a_rows})} industries; "
      f"{len({r['time'] for r in gva_a_rows})} fiscal years")


# ---------------------------------------------------------------------------
# Artifact 3: national GVA by industry (quarterly)
# ---------------------------------------------------------------------------
gva_q_keep: dict[tuple[str, str], dict] = {}
for r in rows:
    if not keep_base(r) or not is_currency_row(r):
        continue
    if r["frequency"] != "Quarterly":
        continue
    if r["indicator"] != "Gross Value Added":
        continue
    if r["industry"] not in INDUSTRY_TIER_1 or r["subindustry"]:
        continue
    t = parse_year_quarter_to_time(r["year"], r["quarter"])
    if not t:
        continue
    v = safe_float(r["constant_price"])
    if v is None:
        continue
    key = (r["industry"], t)
    if key in gva_q_keep:
        continue  # quarterly has no revision tiers in this dump
    gva_q_keep[key] = {
        "facet": r["industry"],
        "time": t,
        "value": v,
        "vintage": None,
    }

gva_q_rows = sorted(
    ({"entity_id": "IN", "time": d["time"], "value": d["value"], "facet": d["facet"], "vintage": d["vintage"]}
     for d in gva_q_keep.values()),
    key=lambda r: (r["facet"], r["time"]),
)
print(f"artifact 3 (gva by industry quarterly): {len(gva_q_rows)} rows; "
      f"{len({r['facet'] for r in gva_q_rows})} industries; "
      f"{len({r['time'] for r in gva_q_rows})} quarters")


# ---------------------------------------------------------------------------
# Build envelopes
# ---------------------------------------------------------------------------
def build(payload_id, title, description, time_grain, rows_, facet_kind):
    times = sorted({r["time"] for r in rows_})
    return {
        "$schema": SCHEMA_REL,
        "$schema_version": "1.3",
        "sources": SOURCES,
        "license": LICENSE,
        "coverage": {
            "spatial": "India (national aggregate)",
            "temporal": f"{times[0]}..{times[-1]}",
            "admin_level": "national",
        },
        "indicator": {
            "id": payload_id,
            "title": title,
            "description": description,
            "entity_kind": "country",
            "time_grain": time_grain,
            "value_kind": "currency",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "INR (crore)",
            "icon": "trending-up",
            "attribution_geography": "where_resident",
            "comparability": "comparable_across_states",
            "implementing_authority": "centre",
            "methodology_vintage": (
                "MoSPI National Accounts Statistics, base 2011-12, constant prices. "
                f"Consolidated CSV ingested {NOW[:10]}; per (indicator{', industry' if facet_kind=='industry' else ''}"
                f"{', quarter' if time_grain=='quarter' else ', year'}) the most-final published revision tier was "
                "selected (rank order: First Advance < Second Advance < Provisional < First Revised < Second "
                "Revised < Third Revised < Final < Additional Revision) and stamped on each row via the v1.3 "
                "`vintage` field. Source CSV included a parallel current-price series and a 2022-23 "
                "rebased series; both were intentionally dropped — constant-price 2011-12 is yen-gov's canonical "
                "real-GDP/GVA basis (matches IMF WEO, World Bank WDI NY.GDP.MKTP.KD, OECD SNA, MoSPI press notes). "
                "Pre-computed growth-rate rows were also dropped: MoSPI uses fixed-base accounts so naive "
                "(Y_t - Y_{t-1}) / Y_{t-1} on this constant-price level series reproduces the published growth "
                "rate to the last decimal. Subindustry rows (Crops, Livestock, Air Transport, etc.) were also "
                "dropped — citizen front door uses the 17-industry NIC-1 tier; subindustry returns in a Phase F "
                "deep-dive."
            ),
            "notes": (
                "Values are in ₹ crore at 2011-12 prices — comparable across years (real growth is meaningful) "
                "but NOT directly comparable to today's market value. For 'size of the economy in today's money' "
                "use the current-price series (not yet shipped at the national level)."
            ),
            "chart_type": "stacked-trend" if facet_kind in ("indicator", "industry") else "ranked",
            "default_mode": "absolute",
        },
        "rows": rows_,
    }


payloads = [
    (OUT_DIR / "national_macro_aggregates_constant_2011_12_inr_crore.json",
     build(
        "economy/national_macro_aggregates_constant_2011_12_inr_crore",
        "National macro aggregates at constant 2011-12 prices (annual)",
        "MoSPI National Accounts Statistics headline aggregates — GDP, GVA, NDP, "
        "Gross National Income, Gross National Disposable Income, Gross Fixed "
        "Capital Formation, Gross Saving, Consumption of Fixed Capital, Private "
        "and Government Final Consumption Expenditure, Change in Stock, Valuables, "
        "Exports and Imports of Goods and Services, Net Taxes / Taxes / Subsidies "
        "on Products, and external transfers — at constant 2011-12 prices, faceted "
        "by indicator. The 'real-economy' lens IMF WEO, World Bank WDI, OECD SNA, "
        "and MoSPI press notes all default to.",
        "fiscal_year", agg_rows, "indicator")),
    (OUT_DIR / "national_gva_by_industry_constant_2011_12_inr_crore.json",
     build(
        "economy/national_gva_by_industry_constant_2011_12_inr_crore",
        "National Gross Value Added by industry, constant 2011-12 prices (annual)",
        "Annual Gross Value Added by 17-industry NIC-1-digit tier (Agriculture / "
        "Mining / Manufacturing / Electricity-Gas-Water / Construction / Trade-Hotels-"
        "Transport-Communication / Financial-Real-Estate-Professional / Public Admin / "
        "Other Services and their published variants), at constant 2011-12 prices. "
        "Drives the 'structure-of-the-economy' citizen story: how shares shift across "
        "CM terms and policy waves.",
        "fiscal_year", gva_a_rows, "industry")),
    (OUT_DIR / "national_gva_by_industry_quarterly_constant_2011_12_inr_crore.json",
     build(
        "economy/national_gva_by_industry_quarterly_constant_2011_12_inr_crore",
        "National Gross Value Added by industry, constant 2011-12 prices (quarterly)",
        "Quarterly Gross Value Added by 17-industry tier at constant 2011-12 prices. "
        "Time field is YYYY-MM at the quarter's start month (Q1 = YYYY-04, Q2 = YYYY-07, "
        "Q3 = YYYY-10, Q4 = (Y+1)-01). The high-frequency companion to the annual series; "
        "useful for monsoon / supply-shock narratives.",
        "quarter", gva_q_rows, "industry")),
]

for path, payload in payloads:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWROTE {path.relative_to(ROOT).as_posix()}  ({len(payload['rows'])} rows)")


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
import jsonschema
schema = json.loads((ROOT / "datasets/schemas/indicator.schema.json").read_text(encoding="utf-8"))
v = jsonschema.Draft202012Validator(schema)
ok = True
for path, _ in payloads:
    obj = json.loads(path.read_text(encoding="utf-8"))
    errs = list(v.iter_errors(obj))
    if errs:
        ok = False
        print(f"\nINVALID {path.relative_to(ROOT).as_posix()}")
        for e in errs[:5]:
            print(f"  - {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message[:160]}")
    else:
        print(f"VALID   {path.relative_to(ROOT).as_posix()}")

if ok:
    SRC.unlink()
    print(f"\nDELETED {SRC.relative_to(ROOT).as_posix()}")
