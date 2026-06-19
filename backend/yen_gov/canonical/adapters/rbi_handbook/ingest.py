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

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.ingest.run_pipeline import (
    Citation,
    Observation,
    run_pipeline,
)

from .parser import HbsTableSpec, parse_hbs_workbook
from .registry import SHIPPED_SPECS
from .resolver import build_state_resolver

__all__ = ["IngestResult", "IngestedTable", "ingest"]

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

    tables: list[IngestedTable] = []
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
        outcome = run_pipeline(
            repo_root=repo_root,
            indicator_id=spec.indicator_id,
            observations=[
                Observation(r.entity_id, r.time, r.value) for r in long_rows
            ],
            citation=Citation(
                producer=spec.source_producer,
                title=spec.source_title,
                vintage=spec.source_vintage,
                url=spec.source_url,
            ),
            datapoints_mode="replace",
            variable_row_builder=_variable_row_builder(spec),
            concept_row=_concept_row(spec),
            contract=contract,
        )
        tables.append(
            IngestedTable(
                indicator_id=spec.indicator_id,
                output_path=outcome.output_path,
                row_count=outcome.row_count,
                entity_count=outcome.entity_count,
                time_min=outcome.time_min,
                time_max=outcome.time_max,
                source_id=outcome.source_id,
            )
        )

    return IngestResult(tables=tuple(tables))


def _variable_row_builder(
    spec: HbsTableSpec,
) -> Any:
    """Return a ``(source_id, time_min, time_max) -> variables.csv row`` builder.

    The ``source_id`` + time bounds are only known after ``run_pipeline``
    derives them, so the variables row is built lazily from the spec metadata.
    """

    def build(source_id: str, time_min: int, time_max: int) -> dict[str, Any]:
        return {
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

    return build


def _concept_row(spec: HbsTableSpec) -> dict[str, Any]:
    """Build the ``concepts.csv`` row from the spec (no derived dependency)."""
    return {
        "concept_id": spec.concept_id,
        "noun": spec.concept_noun,
        "unit_canonical": spec.unit_canonical,
        "normalisation": spec.normalisation,
        "entity_kinds": spec.entity_kinds,
        "description": spec.concept_description,
    }
