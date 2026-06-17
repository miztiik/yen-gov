"""Orchestrator for CEA Installed Capacity ingest -> faceted geo_by_fuel CSV.

No network. Reads the workbook from
``.runtime/raw/cea/installed_capacity_<YYYY>_<MM>.xlsx`` (or an explicit
path / ``CEA_INSTALLED_CAPACITY_PATH`` override), runs the pure parser,
and writes ONE faceted canonical file
``datasets/data/datapoints/geo_by_fuel/installed-capacity-snapshot-mw.csv``
(``entity_id, time, fuel_type, value, source_id``; composite PK
``(entity_id, time, fuel_type)``; closed ``fuel_type`` enum).

Shape history (plan TODO/20260617-cea-iced-faceted-ingestion-plan.md, Row 2):
the legacy emit fanned each fuel column out into a per-fuel single-value
``geo/*.csv`` file; PR #1097 consolidated those into the faceted
``geo_by_fuel/*.csv`` class. This adapter now emits that faceted shape
DIRECTLY in a single pass: parse -> map workbook fuel columns to the
canonical ``fuel_type`` enum -> ECI st_code -> LGD slug -> faceted CSV.

Why no network in this adapter: CEA's TLS chain is not in the standard
CA bundle on Windows / many CI images, so direct httpx fetches fail
with CERTIFICATE_VERIFY_FAILED. The operator runs the one-line
``Invoke-WebRequest`` (or ``curl --insecure`` on Linux) once per month
to refill the cache; the adapter is then trivially re-runnable in any
environment.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

from .parsers import (
    ParsedWorkbook,
    parse_workbook,
)

# Canonical CSV citation triple for the CEA monthly Installed Capacity
# report. All fuel columns share one publication (Executive Summary on
# Power Sector, monthly edition). Vintage per ADR-0042 is the publisher
# edition string (YYYY-MM from the workbook snapshot period). derive_source_id
# hashes the triple at write time.
_CSV_SOURCE_PRODUCER = "Central Electricity Authority"
_CSV_SOURCE_TITLE = "Executive Summary on Power Sector"

# Faceted target (PR #1097 dimension-column branch). One file per measure;
# the fuel members live in the `fuel_type` column, not in the filename.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo_by_fuel/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo_by_fuel"
_FACETED_VARIABLE_ID = "installed-capacity-snapshot-mw"

# Workbook fuel column (its parser indicator_id) -> canonical `fuel_type`
# enum member. The CEA columns map 1:1 to the 5-bucket axis; the published
# Grand Total is the `all` aggregate member (NOT a render-time sum). The
# "Total Thermal" composite (coal + lignite + gas + diesel) is NOT a
# canonical fuel_type bucket and is intentionally DROPPED from the facet
# axis per plan ruling R-C (it is derivable + unconsumed; a separate
# single-value "total thermal" indicator is deferred).
_INDICATOR_TO_FUEL_TYPE: dict[str, str] = {
    "energy/installed_capacity_total_mw": "all",
    "energy/installed_capacity_coal_mw": "coal",
    "energy/installed_capacity_gas_mw": "gas",
    "energy/installed_capacity_nuclear_mw": "nuclear",
    "energy/installed_capacity_hydro_mw": "hydro",
    "energy/installed_capacity_renewable_mw": "renewable",
}
_DROPPED_INDICATOR = "energy/installed_capacity_thermal_mw"


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
class FacetedIngestResult:
    """Receipt for the single faceted CSV emit."""

    variable_id: str
    csv_path: Path
    workbook_fetched_at: datetime
    snapshot_period: str
    time: int
    row_count: int
    fuel_types: tuple[str, ...]


def _resolve_workbook(
    *, repo_root: Path, workbook_path: Path | None = None
) -> tuple[bytes, datetime, str]:
    """Read the CEA workbook, returning ``(content, mtime, url)``.

    Resolution order: explicit ``workbook_path`` arg ->
    ``$CEA_INSTALLED_CAPACITY_PATH`` -> latest cached
    ``installed_capacity_YYYY_MM.xlsx`` under ``.runtime/raw/cea/``.
    """
    if workbook_path is not None:
        path = workbook_path
        if not path.exists():
            raise CEACacheMissing(f"workbook path {path} does not exist.")
    else:
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
        f"Or pass the workbook path explicitly (CLI --xlsx) or override with "
        f"$CEA_INSTALLED_CAPACITY_PATH=<absolute path>."
    )


def _snapshot_to_year(snapshot_period: str) -> int:
    """Encode the snapshot ``YYYY-MM`` into the canonical integer ``time``.

    The ``geo_by_fuel`` datapoints class declares ``time`` as integer and the
    consolidated CEA snapshot keys on the report YEAR (the March FY-end
    snapshot is the canonical edition), matching the on-disk faceted file.
    Raises ``ValueError`` on shape drift -- fail fast at the boundary.
    """
    year_str, _, month_str = snapshot_period.partition("-")
    if not (year_str.isdigit() and month_str.isdigit()):
        raise ValueError(
            f"unexpected snapshot period {snapshot_period!r}; expected 'YYYY-MM'"
        )
    return int(year_str)


def _to_slug(eci_st_code: str) -> str:
    """ECI st_code -> LGD slug, with the country rollup passed through."""
    if eci_st_code == "IN":
        return "IN"
    return eci_to_lgd_slug(eci_st_code)


def build_faceted_rows(
    parsed: ParsedWorkbook,
    *,
    source_id: str,
) -> list[dict[str, object]]:
    """Build the faceted ``geo_by_fuel`` row list for one workbook.

    One row per ``(state, fuel_type)``: the workbook fuel columns map to the
    canonical ``fuel_type`` enum via ``_INDICATOR_TO_FUEL_TYPE`` (Grand Total
    -> ``all``; Total Thermal dropped), the ECI st_code translates to the LGD
    slug, and the snapshot reduces to the integer report year. write_csv sorts
    by the composite PK.
    """
    time_int = _snapshot_to_year(parsed.snapshot_period)
    rows: list[dict[str, object]] = []
    for indicator_id, fuel_type in _INDICATOR_TO_FUEL_TYPE.items():
        for r in parsed.rows_by_indicator[indicator_id]:
            rows.append(
                {
                    "entity_id": _to_slug(r.entity_id),
                    "time": time_int,
                    "fuel_type": fuel_type,
                    "value": r.value,
                    "source_id": source_id,
                }
            )
    return rows


def emit_faceted(*, repo_root: Path, rows: list[dict[str, object]]) -> Path:
    """Write the single faceted ``geo_by_fuel/<variable_id>.csv`` file."""
    out_path = repo_root / _CSV_OUT_REL_DIR / f"{_FACETED_VARIABLE_ID}.csv"
    return write_csv(path=out_path, file_class=_CSV_FILE_CLASS, rows=rows)


def ingest(
    *, repo_root: Path, workbook_path: Path | None = None
) -> FacetedIngestResult:
    """Read the workbook, parse all fuel columns, emit the faceted CSV.

    Emits ONE faceted file
    ``datasets/data/datapoints/geo_by_fuel/installed-capacity-snapshot-mw.csv``.
    ``workbook_path`` overrides the cache resolution (used by the CLI).
    """
    content, mtime, _url = _resolve_workbook(
        repo_root=repo_root, workbook_path=workbook_path
    )
    parsed: ParsedWorkbook = parse_workbook(content)

    # One citation-ledger source_id shared across all fuel facets (same
    # Executive Summary monthly publication). Vintage = workbook snapshot
    # period (YYYY-MM) per ADR-0042.
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, parsed.snapshot_period
    )

    rows = build_faceted_rows(parsed, source_id=source_id)
    csv_path = emit_faceted(repo_root=repo_root, rows=rows)

    return FacetedIngestResult(
        variable_id=_FACETED_VARIABLE_ID,
        csv_path=csv_path,
        workbook_fetched_at=mtime,
        snapshot_period=parsed.snapshot_period,
        time=_snapshot_to_year(parsed.snapshot_period),
        row_count=len(rows),
        fuel_types=tuple(sorted({str(r["fuel_type"]) for r in rows})),
    )
