"""ICED transmission-substation list - ingest orchestrator.

Pipeline for the national transmission-substation feed::

    stage encrypted JSON  ->  decrypt + classify by voltage + aggregate (parser)
                          ->  emit ONE faceted datapoints CSV
                              (datasets/data/datapoints/geo_by_voltage/<id>.csv)
                          ->  upsert variables / concepts / source catalogue rows

The operator stages the raw ICED response under a local staging directory;
this module reads it - NO network (parent plan section 21.4). Each run is
idempotent: the canonical writer skip-writes byte-identical output, so
re-running leaves a clean ``git status``.

Catalogue rows are upserted directly into the live CSV catalogue
(``datasets/data/{variables,concepts}.csv`` + ``entities/source.csv``) - the
same surface the RBI Handbook + renewable-potential ingests write - so one
command produces a corpus the canonical validator accepts (datapoint filename
== ``indicator_id`` in ``variables.csv``; every ``source_id`` FK closes; the
country ``entity_id`` FK-closes against ``entities/geo.csv``).
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.csv_writer import write_csv

from .parser import TransmissionSubstationSpec, parse_substation_feed
from .registry import SHIPPED_SPEC

__all__ = ["IngestResult", "ingest"]

_DATAPOINTS_FILE_CLASS = "datasets/data/datapoints/geo_by_voltage/*.csv"
_DATAPOINTS_REL_DIR = "datasets/data/datapoints/geo_by_voltage"
_VARIABLES_REL = "datasets/data/variables.csv"
_CONCEPTS_REL = "datasets/data/concepts.csv"
_SOURCE_REL = "datasets/data/entities/source.csv"


@dataclass(frozen=True)
class IngestResult:
    """Outcome of one ``ingest`` run, reported to the CLI."""

    indicator_id: str
    output_path: Path
    row_count: int
    time_min: int
    time_max: int
    source_id: str
    total_assets: int
    dropped_null_capacity: int
    dropped_unparseable_year: int
    class_row_counts: tuple[tuple[str, int], ...]


def ingest(
    *,
    repo_root: Path,
    staging_dir: Path,
    spec: TransmissionSubstationSpec | None = None,
) -> IngestResult:
    """Ingest the staged ICED transmission-substation feed.

    Args:
        repo_root: repo root; anchors the faceted datapoint output dir and the
            catalogue CSVs.
        staging_dir: directory the operator dropped the ICED JSON response into.
            ``spec.staging_filename`` is resolved inside it. Never a committed
            contract surface (operator input).
        spec: the feed spec; defaults to :data:`SHIPPED_SPEC`.

    Returns:
        :class:`IngestResult` summarising the faceted file written.

    Raises:
        FileNotFoundError: the staged feed is missing.
        TransmissionSubstationShapeError: the feed no longer matches its spec.
    """
    spec = spec if spec is not None else SHIPPED_SPEC
    feed_path = staging_dir / spec.staging_filename
    if not feed_path.exists():
        raise FileNotFoundError(
            f"{spec.indicator_id}: staged feed not found at {feed_path}. "
            f"Stage the ICED response there (no network ingest)."
        )

    contract = load_columns()
    rows, stats = parse_substation_feed(feed_path.read_bytes(), spec)
    source_id = derive_source_id(
        spec.source_producer, spec.source_title, spec.source_vintage
    )

    datapoint_rows = [
        {
            "entity_id": r.entity_id,
            "time": r.time,
            spec.facet_column: r.voltage_class,
            "value": r.value,
            "source_id": source_id,
        }
        for r in rows
    ]
    out_path = write_csv(
        path=repo_root / _DATAPOINTS_REL_DIR / f"{spec.indicator_id}.csv",
        file_class=_DATAPOINTS_FILE_CLASS,
        rows=datapoint_rows,
        contract=contract,
    )

    times = [r.time for r in rows]
    time_min, time_max = min(times), max(times)

    variable_rows = [
        {
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
    ]
    concept_rows = [
        {
            "concept_id": spec.concept_id,
            "noun": spec.concept_noun,
            "unit_canonical": spec.unit_canonical,
            "normalisation": spec.normalisation,
            "entity_kinds": spec.entity_kinds,
            "description": spec.concept_description,
        }
    ]
    source_rows = [
        {
            "source_id": source_id,
            "producer": spec.source_producer,
            "title": spec.source_title,
            "vintage": spec.source_vintage,
            "url": spec.source_url,
        }
    ]
    _upsert_rows(repo_root, _VARIABLES_REL, variable_rows, contract=contract)
    _upsert_rows(repo_root, _CONCEPTS_REL, concept_rows, contract=contract)
    _upsert_rows(repo_root, _SOURCE_REL, source_rows, contract=contract)

    class_counts = Counter(r.voltage_class for r in rows)
    class_row_counts = tuple(
        (cls, class_counts[cls]) for cls in spec.voltage_classes if class_counts[cls]
    )

    return IngestResult(
        indicator_id=spec.indicator_id,
        output_path=out_path,
        row_count=len(datapoint_rows),
        time_min=time_min,
        time_max=time_max,
        source_id=source_id,
        total_assets=stats.total_assets,
        dropped_null_capacity=stats.dropped_null_capacity,
        dropped_unparseable_year=stats.dropped_unparseable_year,
        class_row_counts=class_row_counts,
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

    A self-contained copy of the renewable-potential / rbi_handbook
    catalogue-merge helper: keeping it local makes this adapter purely additive
    (no edit to a sibling adapter, no cross-adapter private import). It is a
    generic PK merge - distinct from ``csv_writer.upsert_source_scoped`` (which
    is source-scoped and replaces an incoming source's rows wholesale).
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
