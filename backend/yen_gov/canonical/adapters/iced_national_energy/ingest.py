"""NITI ICED national energy-balance - ingest orchestrator.

Two national feeds, one pipeline each:

    stage encrypted JSON  ->  decrypt + map to closed enums (parser)
                          ->  emit faceted datapoints CSV
                          ->  upsert variables / concepts / source catalogue rows

Primary supply emits the single-axis faceted class
``datasets/data/datapoints/geo_by_primary_source/<id>.csv`` (primary_source
dimension); final consumption emits the two-axis class
``datasets/data/datapoints/geo_by_sector_fuel/<id>.csv`` (sector + fuel
dimensions). Every row is national (entity_id ``IN``); the entity FK closes
against geo.csv, which already carries the country row.

The operator stages the raw ICED response under the spec's staging filename;
this module reads it - NO network (parent plan section 21.4). Each run is
idempotent: the canonical writer skip-writes byte-identical output, so
re-running leaves a clean ``git status`` (and the two source rows reproduce the
on-disk ``src-170d3536d908`` / ``src-29ecbb6dce9d`` exactly).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.csv_writer import write_csv

from .parser import (
    NATIONAL_ENTITY_ID,
    FinalEnergySpec,
    PrimaryEnergySpec,
    parse_sector_wise_consumption,
    parse_source_wise_supply,
)
from .registry import FINAL_ENERGY_SPEC, PRIMARY_ENERGY_SPEC

__all__ = ["IngestResult", "ingest_final", "ingest_primary"]

_DATAPOINTS_REL_DIR = "datasets/data/datapoints"
_VARIABLES_REL = "datasets/data/variables.csv"
_CONCEPTS_REL = "datasets/data/concepts.csv"
_SOURCE_REL = "datasets/data/entities/source.csv"


@dataclass(frozen=True)
class IngestResult:
    """Per-feed outcome reported to the CLI."""

    indicator_id: str
    output_path: Path
    row_count: int
    time_min: int
    time_max: int
    source_id: str
    facet_summary: str


def ingest_primary(
    *,
    repo_root: Path,
    staging_dir: Path,
    spec: PrimaryEnergySpec = PRIMARY_ENERGY_SPEC,
) -> IngestResult:
    """Ingest the ICED Source-wise Energy Supply national feed.

    Emits ``datasets/data/datapoints/geo_by_primary_source/<id>.csv`` (one row
    per (year, primary_source); entity IN) and upserts the catalogue rows.
    """
    rows = parse_source_wise_supply(_read_feed(staging_dir, spec), spec)
    source_id = derive_source_id(
        spec.source_producer, spec.source_title, spec.source_vintage
    )
    datapoint_rows = [
        {
            "entity_id": NATIONAL_ENTITY_ID,
            "time": r.time,
            "primary_source": r.primary_source,
            "value": r.value,
            "source_id": source_id,
        }
        for r in rows
    ]
    times = [r.time for r in rows]
    facet_summary = (
        f"{len({r.primary_source for r in rows})} primary_source members"
    )
    return _emit(
        repo_root=repo_root,
        spec=spec,
        datapoint_rows=datapoint_rows,
        source_id=source_id,
        time_min=min(times),
        time_max=max(times),
        facet_summary=facet_summary,
    )


def ingest_final(
    *,
    repo_root: Path,
    staging_dir: Path,
    spec: FinalEnergySpec = FINAL_ENERGY_SPEC,
) -> IngestResult:
    """Ingest the ICED Sector-wise Energy Consumption national feed.

    Emits ``datasets/data/datapoints/geo_by_sector_fuel/<id>.csv`` (one row per
    (year, sector, fuel); entity IN) and upserts the catalogue rows.
    """
    rows = parse_sector_wise_consumption(_read_feed(staging_dir, spec), spec)
    source_id = derive_source_id(
        spec.source_producer, spec.source_title, spec.source_vintage
    )
    datapoint_rows = [
        {
            "entity_id": NATIONAL_ENTITY_ID,
            "time": r.time,
            "sector": r.sector,
            "fuel": r.fuel,
            "value": r.value,
            "source_id": source_id,
        }
        for r in rows
    ]
    times = [r.time for r in rows]
    facet_summary = (
        f"{len({r.sector for r in rows})} sector x "
        f"{len({r.fuel for r in rows})} fuel members"
    )
    return _emit(
        repo_root=repo_root,
        spec=spec,
        datapoint_rows=datapoint_rows,
        source_id=source_id,
        time_min=min(times),
        time_max=max(times),
        facet_summary=facet_summary,
    )


def _read_feed(staging_dir: Path, spec: PrimaryEnergySpec | FinalEnergySpec) -> bytes:
    feed_path = staging_dir / spec.staging_filename
    if not feed_path.exists():
        raise FileNotFoundError(
            f"{spec.indicator_id}: staged feed not found at {feed_path}. "
            f"Stage the ICED response there (no network ingest)."
        )
    return feed_path.read_bytes()


def _emit(
    *,
    repo_root: Path,
    spec: PrimaryEnergySpec | FinalEnergySpec,
    datapoint_rows: list[dict[str, Any]],
    source_id: str,
    time_min: int,
    time_max: int,
    facet_summary: str,
) -> IngestResult:
    """Write the faceted datapoints file and upsert the catalogue rows."""
    contract = load_columns()
    out_path = write_csv(
        path=repo_root / _DATAPOINTS_REL_DIR
        / spec.file_class.split("/")[-2]
        / f"{spec.indicator_id}.csv",
        file_class=spec.file_class,
        rows=datapoint_rows,
        contract=contract,
    )

    variable_row = {
        "indicator_id": spec.indicator_id,
        "name": spec.name,
        "concept_id": spec.concept_id,
        "unit": spec.unit,
        "derivation": spec.derivation,
        "topic": spec.topic,
        "source_id": source_id,
        "update_period_days": spec.update_period_days,
        "time_min": time_min,
        "time_max": time_max,
        "entity_kinds": spec.entity_kinds,
    }
    concept_row = {
        "concept_id": spec.concept_id,
        "noun": spec.concept_noun,
        "unit_canonical": spec.unit_canonical,
        "normalisation": spec.normalisation,
        "entity_kinds": spec.entity_kinds,
        "description": spec.concept_description,
    }
    source_row = {
        "source_id": source_id,
        "producer": spec.source_producer,
        "title": spec.source_title,
        "vintage": spec.source_vintage,
        "url": spec.source_url,
    }
    _upsert_rows(repo_root, _VARIABLES_REL, [variable_row], contract=contract)
    _upsert_rows(repo_root, _CONCEPTS_REL, [concept_row], contract=contract)
    _upsert_rows(repo_root, _SOURCE_REL, [source_row], contract=contract)

    return IngestResult(
        indicator_id=spec.indicator_id,
        output_path=out_path,
        row_count=len(datapoint_rows),
        time_min=time_min,
        time_max=time_max,
        source_id=source_id,
        facet_summary=facet_summary,
    )


def _upsert_rows(
    repo_root: Path,
    rel_path: str,
    new_rows: list[dict[str, Any]],
    *,
    contract: Any,
) -> Path:
    """Merge ``new_rows`` into the catalogue CSV at ``rel_path`` by PK.

    Reads the existing file (if any), overlays the new rows keyed by the file
    class's primary key, and rewrites via the canonical writer (which sorts by
    PK and skip-writes when nothing changed). Existing rows are preserved
    verbatim; a re-ingest of the same edition is a no-op.

    A self-contained copy of the rbi_handbook / iced_renewable_potential
    catalogue-merge helper: keeping it local makes this adapter purely additive
    (no edit to a sibling adapter, no cross-adapter private import).
    """
    path = repo_root / rel_path
    file_class = rel_path  # literal-path file classes key on the path itself
    fc = contract.for_glob(file_class)
    names = [c.name for c in fc.columns]
    pk_names = [c.name for c in fc.pk_columns]

    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            for raw in csv.DictReader(fh):
                row = {
                    name: (raw.get(name) if (raw.get(name) or "") != "" else None)
                    for name in names
                }
                merged[tuple(_pk_value(row[k]) for k in pk_names)] = row
    for row in new_rows:
        key = tuple(_pk_value(row.get(k)) for k in pk_names)
        merged[key] = {name: row.get(name) for name in names}

    return write_csv(
        path=path,
        file_class=file_class,
        rows=list(merged.values()),
        contract=contract,
    )


def _pk_value(value: Any) -> Any:
    """Normalise a PK value for keying (stringify so int/str match)."""
    return str(value) if value is not None else None
