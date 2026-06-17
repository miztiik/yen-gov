"""RBI Handbook of Statistics on Indian States - ingest orchestrator.

One reusable pipeline for every ``state x period`` Handbook table:

    stage XLSX  ->  parse (parser)  ->  resolve entity (resolver)
                ->  emit datapoints CSV  +  upsert variables / concepts
                    / source catalogue rows  (canonical csv_writer)

The operator stages the workbook(s) the RBI website serves (one XLSX per
table) under a local staging directory; this module reads them - NO
network (parent plan section 21.4: the network fetcher was deleted in the
rip; ingest reads local source files only). Each run is idempotent: the
canonical writer skip-writes byte-identical output, so re-running leaves a
clean ``git status``.

Catalogue rows are upserted directly into the live CSV catalogue
(``datasets/data/{variables,concepts}.csv`` + ``entities/source.csv``) -
the same surface the TN-CEO electors ingest writes - so one command
produces a corpus the canonical validator accepts (datapoint filename ==
``indicator_id`` in ``variables.csv``; every ``source_id`` FK closes).
"""
from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.csv_writer import write_csv

from .parser import HbsTableSpec, parse_hbs_workbook
from .registry import SHIPPED_SPECS
from .resolver import build_state_resolver

__all__ = ["IngestResult", "IngestedTable", "ingest"]

_DATAPOINTS_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_DATAPOINTS_REL_DIR = "datasets/data/datapoints/geo"
_VARIABLES_REL = "datasets/data/variables.csv"
_CONCEPTS_REL = "datasets/data/concepts.csv"
_SOURCE_REL = "datasets/data/entities/source.csv"
_GEO_REL = "datasets/data/entities/geo.csv"


@dataclass(frozen=True)
class IngestedTable:
    """Per-table outcome reported to the CLI."""

    indicator_id: str
    output_path: Path
    row_count: int
    entity_count: int
    time_min: int
    time_max: int
    source_id: str


@dataclass(frozen=True)
class IngestResult:
    """Aggregate outcome of one ``ingest`` run."""

    tables: tuple[IngestedTable, ...]

    @property
    def total_rows(self) -> int:
        return sum(t.row_count for t in self.tables)


def ingest(
    *,
    repo_root: Path,
    staging_dir: Path,
    specs: Iterable[HbsTableSpec] | None = None,
) -> IngestResult:
    """Ingest one or more staged RBI Handbook tables into the canonical store.

    Args:
        repo_root: repo root; anchors the datapoint output dir, the
            catalogue CSVs, and the geo.csv resolver source.
        staging_dir: directory the operator dropped the Handbook XLSX
            file(s) into. Each spec's ``staging_filename`` is resolved
            inside it. Never a committed contract surface (operator input).
        specs: the tables to ingest; defaults to :data:`SHIPPED_SPECS`.

    Returns:
        :class:`IngestResult` summarising every table written.

    Raises:
        FileNotFoundError: ``geo.csv`` or a staged workbook is missing.
        RbiHbsShapeError: a workbook no longer matches its spec.
    """
    specs = tuple(specs) if specs is not None else SHIPPED_SPECS
    geo_csv = repo_root / _GEO_REL
    resolver = build_state_resolver(geo_csv)

    contract = load_columns()
    out_dir = repo_root / _DATAPOINTS_REL_DIR

    tables: list[IngestedTable] = []
    variable_rows: list[dict[str, Any]] = []
    concept_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []

    for spec in specs:
        workbook_path = staging_dir / spec.staging_filename
        if not workbook_path.exists():
            raise FileNotFoundError(
                f"{spec.indicator_id}: staged workbook not found at "
                f"{workbook_path}. Download the RBI Handbook table and save "
                f"it there (no network ingest)."
            )
        long_rows = parse_hbs_workbook(
            workbook_path.read_bytes(), spec, resolver
        )
        source_id = derive_source_id(
            spec.source_producer, spec.source_title, spec.source_vintage
        )
        datapoint_rows = [
            {
                "entity_id": r.entity_id,
                "time": r.time,
                "value": r.value,
                "source_id": source_id,
            }
            for r in long_rows
        ]
        out_path = write_csv(
            path=out_dir / f"{spec.indicator_id}.csv",
            file_class=_DATAPOINTS_FILE_CLASS,
            rows=datapoint_rows,
            contract=contract,
        )

        times = [r.time for r in long_rows]
        time_min, time_max = min(times), max(times)
        entity_count = len({r.entity_id for r in long_rows})

        variable_rows.append(
            {
                "indicator_id": spec.indicator_id,
                "name": spec.name,
                "concept_id": spec.concept_id,
                "unit": spec.unit,
                "derivation": None,
                "topic": spec.topic,
                "source_id": source_id,
                "update_period_days": spec.update_period_days,
                "time_min": time_min,
                "time_max": time_max,
                "entity_kinds": spec.entity_kinds,
            }
        )
        concept_rows.append(
            {
                "concept_id": spec.concept_id,
                "noun": spec.concept_noun,
                "unit_canonical": spec.unit_canonical,
                "normalisation": spec.normalisation,
                "entity_kinds": spec.entity_kinds,
                "description": spec.concept_description,
            }
        )
        source_rows.append(
            {
                "source_id": source_id,
                "producer": spec.source_producer,
                "title": spec.source_title,
                "vintage": spec.source_vintage,
                "url": spec.source_url,
            }
        )
        tables.append(
            IngestedTable(
                indicator_id=spec.indicator_id,
                output_path=out_path,
                row_count=len(datapoint_rows),
                entity_count=entity_count,
                time_min=time_min,
                time_max=time_max,
                source_id=source_id,
            )
        )

    _upsert_rows(repo_root, _VARIABLES_REL, variable_rows, contract=contract)
    _upsert_rows(repo_root, _CONCEPTS_REL, concept_rows, contract=contract)
    _upsert_rows(repo_root, _SOURCE_REL, source_rows, contract=contract)

    return IngestResult(tables=tuple(tables))


def _upsert_rows(
    repo_root: Path,
    rel_path: str,
    new_rows: list[dict[str, Any]],
    *,
    contract: Any,
) -> Path:
    """Merge ``new_rows`` into the catalogue CSV at ``rel_path`` by PK.

    Reads the existing file (if any), overlays the new rows keyed by the
    file class's primary key, and rewrites via the canonical writer
    (which sorts by PK and skip-writes when nothing changed). Existing
    rows are preserved verbatim; a re-ingest of the same edition is a
    no-op.
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
                merged[tuple(row[k] for k in pk_names)] = row
    for row in new_rows:
        key = tuple(_pk_value(row[k]) for k in pk_names)
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
