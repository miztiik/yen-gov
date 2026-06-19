"""Deterministic fixtures shared by the run_pipeline byte-identity oracle.

This module is import-safe (it pulls only ``openpyxl`` + the adapter spec
types, never the refactored ``run_pipeline`` symbols), so the golden-capture
script (run BEFORE the extraction) and ``test_ingest_run_pipeline`` (run AFTER)
both build the EXACT same staged inputs. The oracle proves the two existing
single-series callers emit byte-identical CSV across the extraction.
"""
from __future__ import annotations

import io
from pathlib import Path

from openpyxl import Workbook

from yen_gov.canonical.adapters.rbi_handbook.parser import (
    TIME_CALENDAR_YEAR,
    HbsTableSpec,
)

# States the fixtures reference; mirrors the real geo.csv alias columns so the
# rbi_handbook + rbi_hbs_health resolvers map every label deterministically.
GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "kerala,Kerala,IN,state,IN-KL|S11|lgd:32,32,32\n"
    "odisha,Odisha,IN,state,IN-OD|S18|lgd:21,21,21\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
)


def write_geo(repo_root: Path) -> Path:
    """Write the shared ``geo.csv`` resolver source under ``repo_root``."""
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(GEO_CSV, encoding="utf-8")
    return geo


# --- rbi_handbook (full-workbook REPLACE single-series caller) -------------- #

_TFR_ROWS: list[list[object]] = [
    ["Table 6: State-Wise Total Fertility Rate", None, None, None],
    ["State", 2016, 2017, 2018],
    ["1. Andhra Pradesh", 1.7, 1.6, 1.6],
    ["2. Kerala", 1.8, 1.7, 1.7],
    ["Orissa", 2.1, 2.0, 1.9],
    ["All India", 2.3, 2.2, 2.0],
    ["Source: SRS Statistical Report 2024", None, None, None],
]

#: Distinct test-only indicator_id so the emitted golden never collides with a
#: real corpus file; the citation triple is fixed so source_id is deterministic.
RBI_HANDBOOK_INDICATOR_ID = "test-runpipe-tfr"
RBI_HANDBOOK_STAGING_FILENAME = "test-runpipe-tfr.xlsx"


def rbi_handbook_spec() -> HbsTableSpec:
    """A single-value calendar-year RBI Handbook spec (TFR-shaped)."""
    return HbsTableSpec(
        indicator_id=RBI_HANDBOOK_INDICATOR_ID,
        name="Total fertility rate (run_pipeline oracle)",
        concept_id="total-fertility-rate-runpipe",
        concept_noun="Total fertility rate",
        concept_description="Run-pipeline byte-identity oracle fixture concept.",
        unit="children per woman",
        unit_canonical="children per woman",
        normalisation="ratio",
        topic="health",
        entity_kinds="country state",
        update_period_days=365,
        source_producer="Office of the Registrar General & Census Commissioner, India",
        source_title="Sample Registration System (run_pipeline oracle fixture)",
        source_vintage="2024-25",
        source_url="https://censusindia.gov.in/census.website/data/SRSSTAT",
        staging_filename=RBI_HANDBOOK_STAGING_FILENAME,
        time_kind=TIME_CALENDAR_YEAR,
        skip_labels=("Source",),
        all_india_labels=("All India", "All-India", "India"),
    )


def rbi_handbook_workbook_bytes() -> bytes:
    """XLSX bytes for the TFR-shaped single-value Handbook table."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for row in _TFR_ROWS:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def stage_rbi_handbook(staging_dir: Path) -> Path:
    """Drop the staged workbook under ``staging_dir`` and return its path."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    path = staging_dir / RBI_HANDBOOK_STAGING_FILENAME
    path.write_bytes(rbi_handbook_workbook_bytes())
    return path


# --- rbi_hbs_health (per-year UPSERT single-series caller) ------------------ #

RBI_HBS_HEALTH_YEARS: tuple[int, ...] = (2019, 2020)

#: state -> (government_hospitals, hospital_beds) per year. Deterministic small
#: cohort; the per-year file carries BOTH columns (the shared-cache-unit shape).
_HEALTH_BY_YEAR: dict[int, list[tuple[str, int, int]]] = {
    2019: [
        ("Andhra Pradesh", 1900, 52000),
        ("Kerala", 1280, 39000),
        ("Tamil Nadu", 2700, 78000),
        ("All India", 25700, 713000),
    ],
    2020: [
        ("Andhra Pradesh", 1950, 53000),
        ("Kerala", 1300, 39500),
        ("Tamil Nadu", 2750, 79000),
        ("All India", 26000, 720000),
    ],
}


def rbi_hbs_health_year_csv(year: int) -> bytes:
    """``health-<year>.csv`` bytes (state + the two health columns)."""
    lines = ["state,government_hospitals,hospital_beds"]
    for state, gov, beds in _HEALTH_BY_YEAR[year]:
        lines.append(f"{state},{gov},{beds}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def stage_rbi_hbs_health(staging_dir: Path) -> Path:
    """Stage every per-year health CSV under ``staging_dir``."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    for year in RBI_HBS_HEALTH_YEARS:
        (staging_dir / f"health-{year}.csv").write_bytes(
            rbi_hbs_health_year_csv(year)
        )
    return staging_dir


# --- scenario runners (stable public API; identical before/after the rip) --- #

#: Repo-relative emitted files the rbi_handbook oracle compares byte-for-byte.
RBI_HANDBOOK_EMITTED: tuple[str, ...] = (
    f"datasets/data/datapoints/geo/{RBI_HANDBOOK_INDICATOR_ID}.csv",
    "datasets/data/variables.csv",
    "datasets/data/concepts.csv",
    "datasets/data/entities/source.csv",
)

#: Repo-relative emitted files the rbi_hbs_health oracle compares byte-for-byte.
RBI_HBS_HEALTH_EMITTED: tuple[str, ...] = (
    "datasets/data/datapoints/geo/government-hospitals.csv",
    "datasets/data/datapoints/geo/hospital-beds.csv",
    "datasets/data/entities/source.csv",
)


def run_rbi_handbook(repo_root: Path) -> None:
    """Drive the rbi_handbook single-series caller into ``repo_root``.

    Uses only the package's stable ``ingest`` entry point, so the call is
    identical before and after the run_pipeline extraction.
    """
    from yen_gov.canonical.adapters.rbi_handbook import ingest

    write_geo(repo_root)
    staging = repo_root / "_staging"
    stage_rbi_handbook(staging)
    ingest(
        repo_root=repo_root,
        staging_dir=staging,
        specs=(rbi_handbook_spec(),),
    )


def run_rbi_hbs_health(repo_root: Path) -> None:
    """Drive the rbi_hbs_health single-series caller into ``repo_root``.

    Uses only the adapter's stable ``run_indicator`` entry point for BOTH
    indicators (they share each per-year cache unit), so the call is identical
    before and after the run_pipeline extraction.
    """
    from yen_gov.canonical.adapters.rbi_hbs_health import RbiHbsHealthAdapter
    from yen_gov.canonical.ingest.registry import OrchestrateConfig

    write_geo(repo_root)
    staging = repo_root / "_staging"
    stage_rbi_hbs_health(staging)
    adapter = RbiHbsHealthAdapter(years=RBI_HBS_HEALTH_YEARS)
    config = OrchestrateConfig(staging_dir=staging)
    for indicator_id in ("government-hospitals", "hospital-beds"):
        adapter.run_indicator(indicator_id, repo_root=repo_root, config=config)
