"""NITI Aayog SDG India Index - parse a staged composite-score CSV.

The greenfield single-series proof source (plan Row 11). NITI Aayog publishes
the SDG India Index as a state/UT composite score (0-100) per edition; the
operator stages one CSV (``state,year,score``) which this module melts to
long-format observations, resolving every state label (and the ``All India``
row) to its LGD ``entity_id`` via the shared ``geo.csv`` resolver (Holy Law #6:
no hardcoded state map). NO network: the raw CSV is operator-staged locally
(plan D1 + the parent rip's local-only Fetch rule).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

from yen_gov.canonical.ingest.run_pipeline import Observation

if TYPE_CHECKING:  # pragma: no cover - typing only
    from yen_gov.canonical.adapters.rbi_handbook.resolver import StateResolver

__all__ = ["SdgIndexSpec", "SdgParseError", "parse_sdg_index_csv"]

# CSV cell contents that mean "no observation" -> dropped (sparse-safe). NITI
# scores every state, so this is a guard, not an expected path.
_NA_MARKERS: frozenset[str] = frozenset({"", "-", "--", "n.a.", "na", "nr", "..."})

# Required header columns of the staged CSV.
_COL_STATE = "state"
_COL_YEAR = "year"
_COL_SCORE = "score"


class SdgParseError(ValueError):
    """The staged SDG India Index CSV does not match the expected shape."""


@dataclass(frozen=True)
class SdgIndexSpec:
    """One SDG India Index single-series indicator + its citation triple.

    Mirrors the ``rbi_handbook`` spec shape (catalogue + citation in one place)
    so the adapter stays a thin parse -> ``run_pipeline`` driver.
    """

    indicator_id: str
    name: str
    concept_id: str
    concept_noun: str
    concept_description: str
    unit: str
    unit_canonical: str
    normalisation: str
    topic: str | None
    entity_kinds: str
    update_period_days: int
    source_producer: str
    source_title: str
    source_vintage: str
    source_url: str
    staging_filename: str


def parse_sdg_index_csv(
    raw_bytes: bytes,
    spec: SdgIndexSpec,
    resolver: "StateResolver",
) -> list[Observation]:
    """Melt a staged ``state,year,score`` CSV into long-format observations.

    Args:
        raw_bytes: the operator-staged CSV bytes.
        spec: the indicator spec being ingested (for error context).
        resolver: a ``geo.csv``-backed state resolver (``All India`` -> ``IN``).

    Returns:
        Sorted (by ``entity_id``, ``time``) list of :class:`Observation`.

    Raises:
        SdgParseError: a missing header, an unresolved state label, a
            non-integer year, or an unparseable score (fail loud; never
            silently drop a real row).
    """
    reader = csv.DictReader(io.StringIO(raw_bytes.decode("utf-8")))
    header = reader.fieldnames
    if header is None or not {_COL_STATE, _COL_YEAR, _COL_SCORE} <= set(header):
        raise SdgParseError(
            f"{spec.indicator_id}: staged CSV header {header!r} must contain "
            f"{_COL_STATE!r}, {_COL_YEAR!r}, {_COL_SCORE!r}"
        )

    observations: list[Observation] = []
    for line_no, row in enumerate(reader, start=2):
        cell = (row.get(_COL_SCORE) or "").strip()
        if cell.lower() in _NA_MARKERS:
            continue
        label = (row.get(_COL_STATE) or "").strip()
        entity_id = resolver.resolve(label)
        if entity_id is None:
            raise SdgParseError(
                f"{spec.indicator_id}: unresolved state label {label!r} on line "
                f"{line_no} (no geo.csv match; fail loud, never silently drop)"
            )
        year_raw = (row.get(_COL_YEAR) or "").strip()
        try:
            year = int(year_raw)
        except ValueError as exc:
            raise SdgParseError(
                f"{spec.indicator_id}: non-integer year {year_raw!r} on line "
                f"{line_no}"
            ) from exc
        try:
            value = float(cell)
        except ValueError as exc:
            raise SdgParseError(
                f"{spec.indicator_id}: unparseable score {cell!r} on line "
                f"{line_no}"
            ) from exc
        observations.append(Observation(entity_id, year, value))

    if not observations:
        raise SdgParseError(
            f"{spec.indicator_id}: staged CSV produced no observations "
            "(every row blank/NA?); refusing an empty emit"
        )
    observations.sort(key=lambda o: (o.entity_id, o.time))
    return observations
