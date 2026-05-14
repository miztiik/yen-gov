"""Orchestrator for CEA Installed Capacity ingest.

No network. Reads the workbook from
``.runtime/raw/cea/installed_capacity_<YYYY>_<MM>.xlsx`` (or operator-
overridden via ``CEA_INSTALLED_CAPACITY_PATH``), runs the pure parser,
and writes one canonical state-level indicator artifact per fuel
column under ``datasets/indicators/in/energy/<leaf>.json``.

Why no network in this adapter: CEA's TLS chain is not in the standard
CA bundle on Windows / many CI images, so direct httpx fetches fail
with CERTIFICATE_VERIFY_FAILED. The operator runs the one-line
``Invoke-WebRequest`` (or ``curl --insecure`` on Linux) once per month
to refill the cache; the adapter is then trivially re-runnable in any
environment.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.io import Source, write_artifact

from .parsers import (
    SHIPPED_COLUMNS,
    FuelColumn,
    ParsedRow,
    ParsedWorkbook,
    parse_workbook,
)


CACHE_DIR_RELPATH = ".runtime/raw/cea"
"""Where the operator caches the downloaded XLSX."""

LISTING_PAGE = "https://cea.nic.in/installed-capacity-report/?lang=en"
"""Stable landing page for monthly Installed Capacity reports."""

# Filename pattern the operator is asked to use:
#   installed_capacity_YYYY_MM.xlsx
# We pick the lexicographically-largest match so the latest snapshot
# wins when multiple months are cached.
_CACHE_FILE_RE = re.compile(r"^installed_capacity_(\d{4})_(\d{2})\.xlsx$")


class CEACacheMissing(RuntimeError):
    """No cached CEA Installed Capacity workbook to read."""


@dataclass(frozen=True)
class IndicatorMeta:
    indicator_id: str
    title: str
    description: str
    icon: str
    notes: str


# Notes shared across all CEA installed-capacity indicators.
_COMMON_NOTES_TAIL = (
    " Source: CEA monthly Executive Summary, 'IC' sheet, per-state Sub-Total "
    "row (sum of State + Private + Central ownership tiers, including "
    "allocated shares from joint and central-sector utilities). Snapshot "
    "is point-in-time as of the last day of the report month — NOT a "
    "year-average. Capacity is **nameplate** MW, not generation; a state "
    "with high coal capacity isn't necessarily a high coal-generation "
    "state if those plants run at low PLF. Two CEA-reported entities are "
    "intentionally dropped: 'NLC' (a central PSU on the Tamil Nadu list) "
    "and 'DVC' (a central corporation on the West Bengal list) — their "
    "capacity is not state-attributable. 'Central - Unallocated' shares "
    "are also dropped for the same reason. CEA bundles 'Jammu & Kashmir "
    "and Ladakh' into a single row; the combined capacity is attributed "
    "to U08 (J&K UT) — the alternative would require a fabrication "
    "split. The Andaman & Nicobar (U01) and Lakshadweep (U04) entries "
    "in the Islands region are tiny but real."
)


INDICATOR_META: dict[str, IndicatorMeta] = {
    "energy/installed_capacity_total_mw": IndicatorMeta(
        indicator_id="energy/installed_capacity_total_mw",
        title="Installed power-generation capacity (all fuels)",
        description=(
            "Total nameplate generation capacity physically located in (or "
            "allocated to) each state, in megawatts, from CEA's monthly "
            "Installed Capacity report. Sum of thermal + nuclear + hydro + "
            "renewable across all ownership tiers (state, private, central, "
            "and allocated shares from joint / central-sector utilities). "
            "Read this as 'how much grid-connected generation gets billed "
            "to this state', not 'how much electricity citizens here "
            "consume' — a state can have large central-sector plants whose "
            "output flows to the regional grid."
        ),
        icon="zap",
        notes=(
            "The headline 'how big is each state's power footprint' "
            "indicator." + _COMMON_NOTES_TAIL
        ),
    ),
    "energy/installed_capacity_thermal_mw": IndicatorMeta(
        indicator_id="energy/installed_capacity_thermal_mw",
        title="Installed thermal capacity (coal + lignite + gas + diesel)",
        description=(
            "Total fossil-fuel thermal generation capacity (coal + lignite "
            "+ gas + diesel), in megawatts, per state. The 'IC' sheet's "
            "Total Thermal column. Useful for the 'how dependent is each "
            "state on fossil-fuel plants' question."
        ),
        icon="flame",
        notes=(
            "Includes lignite and diesel alongside coal and gas. Lignite "
            "is concentrated in Tamil Nadu (Neyveli) and Gujarat / "
            "Rajasthan; diesel is mostly small island / off-grid plants."
            + _COMMON_NOTES_TAIL
        ),
    ),
    "energy/installed_capacity_coal_mw": IndicatorMeta(
        indicator_id="energy/installed_capacity_coal_mw",
        title="Installed coal-fired capacity",
        description=(
            "Coal-fired thermal generation capacity in megawatts, per "
            "state. The single largest fuel category nationally — about "
            "42% of all-India installed capacity as of FY26. States with "
            "captive coal (Chhattisgarh, Odisha, Jharkhand, MP) and the "
            "central-sector NTPC plants in UP / Bihar / WB dominate."
        ),
        icon="flame",
        notes=(
            "Excludes lignite (which CEA lists as a separate column — "
            "see energy/installed_capacity_thermal_mw for coal+lignite "
            "combined)." + _COMMON_NOTES_TAIL
        ),
    ),
    "energy/installed_capacity_gas_mw": IndicatorMeta(
        indicator_id="energy/installed_capacity_gas_mw",
        title="Installed gas-based capacity",
        description=(
            "Natural-gas-based thermal capacity in megawatts, per state. "
            "Largely concentrated in gas-producing / pipeline-connected "
            "states (Gujarat, Maharashtra, AP) and a few central-sector "
            "stations. Many gas plants run at very low utilisation due "
            "to tight gas supply, so this number overstates real "
            "contribution to generation."
        ),
        icon="flame",
        notes=(
            "About 4% of all-India installed capacity but a much smaller "
            "share of generation due to low PLF." + _COMMON_NOTES_TAIL
        ),
    ),
    "energy/installed_capacity_nuclear_mw": IndicatorMeta(
        indicator_id="energy/installed_capacity_nuclear_mw",
        title="Installed nuclear capacity",
        description=(
            "Nuclear generation capacity in megawatts, per state. Eight "
            "operating sites: Tarapur (Maharashtra), Kaiga (Karnataka), "
            "Madras / Kalpakkam (Tamil Nadu), Kudankulam (Tamil Nadu), "
            "RAPS (Rajasthan), NAPS (Uttar Pradesh), KAPS (Gujarat), "
            "Kakrapar (Gujarat). All capacity is centrally allocated by "
            "NPCIL across the regional grid; CEA reports the SHARE that "
            "flows back to each state, which is why the values look "
            "small relative to nameplate at each plant."
        ),
        icon="atom",
        notes=(
            "About 1.6% of all-India installed capacity. The state-level "
            "split here is the central-sector ALLOCATION, not the "
            "physical site of the plant — most states have a small "
            "nuclear allocation even without a reactor in their "
            "boundary." + _COMMON_NOTES_TAIL
        ),
    ),
    "energy/installed_capacity_hydro_mw": IndicatorMeta(
        indicator_id="energy/installed_capacity_hydro_mw",
        title="Installed hydro capacity",
        description=(
            "Conventional hydro generation capacity in megawatts, per "
            "state, including pumped-storage projects (PSPs) but "
            "EXCLUDING small-hydro (SHP) which CEA classifies under RES. "
            "Concentrated in the Himalayan states (Himachal Pradesh, "
            "Uttarakhand, J&K) and the central / southern hill states "
            "(Karnataka, AP, Telangana via Srisailam etc.)."
        ),
        icon="droplet",
        notes=(
            "Small hydro (≤25 MW) lives in the renewable category, not "
            "here. PSPs ARE included." + _COMMON_NOTES_TAIL
        ),
    ),
    "energy/installed_capacity_renewable_mw": IndicatorMeta(
        indicator_id="energy/installed_capacity_renewable_mw",
        title="Installed renewable capacity (RES MNRE)",
        description=(
            "Renewable capacity reported by MNRE (Ministry of New & "
            "Renewable Energy) and republished by CEA in the IC sheet's "
            "RES* (MNRE) column: solar (ground-mounted + rooftop + "
            "hybrid + off-grid + KUSUM) + wind + small hydro + biomass "
            "+ waste-to-energy, in megawatts per state. The fastest-"
            "growing capacity category in India — about 42% of all-India "
            "installed capacity as of FY26 (vs ~27% a decade ago)."
        ),
        icon="sun",
        notes=(
            "Excludes large hydro (which has its own column / "
            "indicator). Includes small hydro (≤25 MW). "
            "From August 2021 onwards CEA also includes off-grid "
            "RES capacity in this column." + _COMMON_NOTES_TAIL
        ),
    ),
}


def _resolve_workbook(*, repo_root: Path) -> tuple[bytes, datetime, str]:
    """Read latest cached CEA workbook, returning ``(content, mtime, url)``."""
    env_path = os.environ.get("CEA_INSTALLED_CAPACITY_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise CEACacheMissing(
                f"$CEA_INSTALLED_CAPACITY_PATH points to {path}, but that "
                f"file does not exist."
            )
    else:
        cache_dir = repo_root / CACHE_DIR_RELPATH
        if not cache_dir.exists():
            raise CEACacheMissing(_missing_cache_recipe(cache_dir))
        candidates = sorted(
            (
                p
                for p in cache_dir.iterdir()
                if p.is_file() and _CACHE_FILE_RE.match(p.name)
            ),
            key=lambda p: p.name,
        )
        if not candidates:
            raise CEACacheMissing(_missing_cache_recipe(cache_dir))
        path = candidates[-1]  # latest YYYY_MM
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(
        microsecond=0
    )
    return path.read_bytes(), mtime, LISTING_PAGE


def _missing_cache_recipe(cache_dir: Path) -> str:
    return (
        f"No cached CEA Installed Capacity workbook in {CACHE_DIR_RELPATH}/.\n"
        f"  (a) Open {LISTING_PAGE}\n"
        f"  (b) Download the latest month's Excel report (e.g. 'Website-1.xlsx')\n"
        f"  (c) Save it as {CACHE_DIR_RELPATH}/installed_capacity_YYYY_MM.xlsx\n"
        f"      where YYYY_MM is the report month\n"
        f"  (d) Re-run this command\n"
        f"On Windows the one-liner is:\n"
        f"  Invoke-WebRequest "
        f"'https://cea.nic.in/wp-content/uploads/installed/<YYYY>/<MM>/Website-1.xlsx' "
        f"-OutFile '{cache_dir}/installed_capacity_<YYYY>_<MM>.xlsx'\n"
        f"Or override the source file entirely with "
        f"$CEA_INSTALLED_CAPACITY_PATH=<absolute path>."
    )


def _build_payload(
    *,
    column: FuelColumn,
    rows: list[ParsedRow],
    snapshot_period: str,
    workbook_fetched_at: datetime,
    state_count: int,
) -> dict[str, Any]:
    meta = INDICATOR_META[column.indicator_id]
    return {
        "license": {
            "id": "GoI-Open",
            "name": "Government of India open publication",
            "url": "https://data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": f"{state_count} states/UTs (all CEA-reported per-state entities)",
            "temporal": snapshot_period,
            "admin_level": "state",
        },
        "indicator": {
            "id": column.indicator_id,
            "title": meta.title,
            "description": meta.description,
            "entity_kind": "state",
            "time_grain": "month",
            "value_kind": "raw",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "MW",
            "icon": meta.icon,
            "attribution_geography": "where_produced",
            # Capacity is comparable across states only AFTER you
            # normalise by population or load — a fair comparison.
            "comparability": "comparable_with_normalisation",
            "implementing_authority": "joint",
            "methodology_vintage": (
                f"CEA Monthly Executive Summary, IC sheet, snapshot "
                f"{snapshot_period}; cached file mtime "
                f"{workbook_fetched_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}"
            ),
            "notes": meta.notes,
        },
        "rows": [
            {"entity_id": r.entity_id, "time": r.time, "value": r.value}
            for r in rows
        ],
    }


@dataclass(frozen=True)
class IndicatorIngestResult:
    indicator_id: str
    artifact_path: Path
    workbook_fetched_at: datetime
    snapshot_period: str
    row_count: int


@dataclass(frozen=True)
class IngestResult:
    indicators: tuple[IndicatorIngestResult, ...]


def ingest(*, repo_root: Path, schema_dir: Path) -> IngestResult:
    """Read cached workbook, parse all fuel columns, write artifacts."""
    indicator_schema_path = schema_dir / "indicator.schema.json"
    indicator_schema = json.loads(indicator_schema_path.read_text(encoding="utf-8"))

    out_dir = repo_root / "datasets" / "indicators" / "in" / "energy"
    out_dir.mkdir(parents=True, exist_ok=True)

    content, mtime, url = _resolve_workbook(repo_root=repo_root)
    parsed: ParsedWorkbook = parse_workbook(content)

    results: list[IndicatorIngestResult] = []
    for column in SHIPPED_COLUMNS:
        rows = parsed.rows_by_indicator[column.indicator_id]
        payload = _build_payload(
            column=column,
            rows=rows,
            snapshot_period=parsed.snapshot_period,
            workbook_fetched_at=mtime,
            state_count=parsed.state_count,
        )
        leaf = column.indicator_id.split("/")[-1] + ".json"
        path = out_dir / leaf
        write_artifact(
            path=path,
            schema_id=indicator_schema["$id"],
            schema_version=indicator_schema["x-version"],
            payload=payload,
            sources=[Source(url=url, fetched_at=mtime)],
            schema_for_validation=indicator_schema,
        )
        results.append(
            IndicatorIngestResult(
                indicator_id=column.indicator_id,
                artifact_path=path,
                workbook_fetched_at=mtime,
                snapshot_period=parsed.snapshot_period,
                row_count=len(rows),
            )
        )

    return IngestResult(indicators=tuple(results))
