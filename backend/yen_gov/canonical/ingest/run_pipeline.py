"""The shared single-series publish pipeline (plan Row 11).

``run_pipeline`` factors the common *one-series-per-file* publish flow -- derive
the citation ``source_id``, emit the long-format ``datapoints/geo/<id>.csv``,
upsert the ``source.csv`` citation row, and (optionally) upsert the
``variables.csv`` + ``concepts.csv`` catalogue rows -- shared by the three
single-series callers: ``rbi_handbook`` (full-workbook REPLACE), the
``rbi_hbs_health`` cohort (per-year UPSERT), and the greenfield
``niti_sdg_index`` adapter.

It is the SINGLE-SERIES strategy ONLY. The faceted
``yen_gov.sources.iced_power`` ``ingest_pipeline`` (per-fuel / per-sector
dimension columns) is a SEPARATE strategy and is deliberately NOT folded in
here (plan section 3: "``run_pipeline`` is scoped single-series ... the existing
faceted ``iced_power.ingest_pipeline`` stays a separate strategy").

Two write modes:

* ``replace`` -- the datapoints file is written wholesale from the observations
  the caller parsed (a full-workbook caller that owns every year of the series
  in one pass, e.g. ``rbi_handbook``);
* ``upsert`` -- the observations are merged into any existing file by the file
  class's primary key ``(entity_id, time)`` (a per-year caller that emits one
  year at a time and must leave the others intact, e.g. ``rbi_hbs_health``).

The optional catalogue rows are upserted by the file class's PK, so a re-ingest
of the same edition is a byte-for-byte no-op (the canonical writer skip-writes
unchanged output). ``variable_row`` is supplied as a builder callback because
its ``source_id`` / ``time_min`` / ``time_max`` fields are only known after the
pipeline derives them; ``concept_row`` carries no such dependency, so it is a
plain dict.
"""
from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.csv_writer import write_csv

__all__ = [
    "Citation",
    "DatapointsMode",
    "Observation",
    "PublishOutcome",
    "run_pipeline",
    "upsert_csv",
]

_DATAPOINTS_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_DATAPOINTS_REL_DIR = "datasets/data/datapoints/geo"
_VARIABLES_REL = "datasets/data/variables.csv"
_CONCEPTS_REL = "datasets/data/concepts.csv"
_SOURCE_REL = "datasets/data/entities/source.csv"

#: How the datapoints file is written. ``replace`` = full wholesale write (the
#: caller owns every row); ``upsert`` = merge by the (entity_id, time) PK.
DatapointsMode = Literal["replace", "upsert"]


@dataclass(frozen=True)
class Observation:
    """One long-format observation: the (entity, time) -> value spine cell."""

    entity_id: str
    time: int
    value: float | None


@dataclass(frozen=True)
class Citation:
    """The OWID-shaped citation triple (+ optional landing url) the row cites.

    ``source_id`` is DERIVED from ``(producer, title, vintage)`` inside the
    pipeline (Holy Law #9; never hand-written).
    """

    producer: str
    title: str
    vintage: str
    url: str | None = None


@dataclass(frozen=True)
class PublishOutcome:
    """The typed result of one ``run_pipeline`` publish."""

    indicator_id: str
    source_id: str
    output_path: Path
    row_count: int
    entity_count: int
    time_min: int
    time_max: int


def _pk_value(value: Any) -> Any:
    """Normalise a PK value for keying (stringify so int/str compare equal)."""
    return str(value) if value is not None else None


def upsert_csv(
    path: Path,
    file_class: str,
    new_rows: Iterable[dict[str, Any]],
    *,
    contract: Any,
) -> Path:
    """Merge ``new_rows`` into the CSV at ``path`` by the file class's PK.

    Reads any existing file, overlays the new rows keyed by the file class's PK,
    and rewrites through the canonical writer (which sorts by PK and skip-writes
    when nothing changed, so an unchanged re-ingest leaves a clean ``git
    status``). Existing rows not touched by ``new_rows`` are preserved verbatim.

    This is the single shared merge-by-PK helper the three single-series callers
    previously each duplicated (``rbi_handbook._upsert_rows`` +
    ``rbi_hbs_health._upsert``); they now route through it.
    """
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


def run_pipeline(
    *,
    repo_root: Path,
    indicator_id: str,
    observations: Iterable[Observation],
    citation: Citation,
    datapoints_mode: DatapointsMode = "upsert",
    variable_row_builder: Callable[[str, int, int], dict[str, Any]] | None = None,
    concept_row: dict[str, Any] | None = None,
    contract: Any | None = None,
) -> PublishOutcome:
    """Publish ONE single-series indicator into the canonical store.

    Args:
        repo_root: repo root; anchors the datapoint output dir + catalogue CSVs.
        indicator_id: the series being published (the datapoints filename stem).
        observations: the parsed/enriched long-format rows.
        citation: the ``(producer, title, vintage[, url])`` the rows cite;
            ``source_id`` is derived from the triple.
        datapoints_mode: ``replace`` (wholesale write) or ``upsert`` (merge by
            ``(entity_id, time)``).
        variable_row_builder: optional ``(source_id, time_min, time_max) ->
            dict`` callback building the ``variables.csv`` row (its ``source_id``
            + time bounds are only known after the pipeline derives them). Pass
            ``None`` to skip the variables upsert (e.g. the health cohort whose
            taxonomy registration is deferred).
        concept_row: optional ``concepts.csv`` row (no derived dependency, so a
            plain dict). Pass ``None`` to skip the concepts upsert.
        contract: optional pre-loaded columns contract (defaults to
            ``load_columns()``; passed in by a multi-series caller to load once).

    Returns:
        :class:`PublishOutcome` summarising the emitted series.

    Raises:
        ValueError: ``observations`` is empty (a series with no rows is a parse
            failure, never a silent empty emit).
    """
    rows = list(observations)
    if not rows:
        raise ValueError(
            f"run_pipeline: no observations for indicator {indicator_id!r} "
            "(refusing to emit an empty series; fix the parse upstream)"
        )
    contract = contract if contract is not None else load_columns()
    source_id = derive_source_id(
        citation.producer, citation.title, citation.vintage
    )

    datapoint_rows = [
        {
            "entity_id": o.entity_id,
            "time": o.time,
            "value": o.value,
            "source_id": source_id,
        }
        for o in rows
    ]
    out_path = repo_root / _DATAPOINTS_REL_DIR / f"{indicator_id}.csv"
    if datapoints_mode == "replace":
        out_path = write_csv(
            path=out_path,
            file_class=_DATAPOINTS_FILE_CLASS,
            rows=datapoint_rows,
            contract=contract,
        )
    else:
        out_path = upsert_csv(
            out_path, _DATAPOINTS_FILE_CLASS, datapoint_rows, contract=contract
        )

    upsert_csv(
        repo_root / _SOURCE_REL,
        _SOURCE_REL,
        [
            {
                "source_id": source_id,
                "producer": citation.producer,
                "title": citation.title,
                "vintage": citation.vintage,
                "url": citation.url,
            }
        ],
        contract=contract,
    )

    times = [o.time for o in rows]
    time_min, time_max = min(times), max(times)

    if variable_row_builder is not None:
        upsert_csv(
            repo_root / _VARIABLES_REL,
            _VARIABLES_REL,
            [variable_row_builder(source_id, time_min, time_max)],
            contract=contract,
        )
    if concept_row is not None:
        upsert_csv(
            repo_root / _CONCEPTS_REL,
            _CONCEPTS_REL,
            [concept_row],
            contract=contract,
        )

    return PublishOutcome(
        indicator_id=indicator_id,
        source_id=source_id,
        output_path=out_path,
        row_count=len(datapoint_rows),
        entity_count=len({o.entity_id for o in rows}),
        time_min=time_min,
        time_max=time_max,
    )
