"""The splice break-row gate (Row 6, plan section 3 honesty preconditions).

Plain English (the doctrine the plan spells out): some indicators take their
EARLY years from one publisher and their RECENT years from another, stitched
into one continuous series -- a "splice". The year where the publisher changes
is a "seam", and numbers can JUMP there because the measurement method changed,
not because the world did. ``state-installed-capacity-allocated-mw`` is the
live example: RBI Handbook Table 140 supplies FY05-FY14, NITI Aayog ICED
supplies FY15+, with a real basis change at the FY15 seam.

The gate (Gregor = contracts, Hans + Max = data shape, Row 6 debate):

* A **seam** is a point INSIDE one ``(entity_id, indicator_id)`` time series
  where the time-ordered rows change ``source_id`` mid-series. The seam YEAR is
  the first year of the new source.
* The FIRST time a seam appears the writer REFUSES to publish unless BOTH hold:
  (1) a ``methodology_breaks`` row exists at the seam year, and (2) the
  indicator's ``methodology_break_ids`` FK resolves to that row. So the chart
  shows a visible break marker and never computes a growth rate across the seam
  (the Bhattacharya rule the methodology-break schema cites).
* **Disjoint-entity multi-source does NOT trigger it.** When each entity
  contributes its OWN rows from a single source (state A from publisher P, state
  B from publisher Q) there is no seam on any single line, so :func:`find_seams`
  returns nothing and the gate passes. The gate is per-entity precisely so a
  legitimate multi-publisher *panel* is never mistaken for a *spliced* series.

There is NO ``splice`` verb (plan section 7): the splice is an EMERGENT property
of the rows, and the only affordance is the break-row precondition this gate
enforces. The escape hatch is to AUTHOR the break row, never to suppress the
check.

Reads are injectable (``breaks`` rows or a ``breaks_path``) so tests never walk
the real corpus (CLAUDE.md section 10); the default reads the compiled
long-format CSV ``datasets/data/methodology_breaks.csv`` (the Parquet form was
retired in the long-format rip; the JSON under ``datasets/taxonomy/`` is the
authoring tier, the CSV is the canonical data tier).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

# ``ingest/`` is at backend/yen_gov/canonical/ingest/; the compiled breaks CSV
# lives at the repo root under datasets/data/ (parents[4] = repo root).
_REPO_ROOT: Path = Path(__file__).resolve().parents[4]
DEFAULT_BREAKS_PATH: Path = _REPO_ROOT / "datasets" / "data" / "methodology_breaks.csv"


class SpliceError(Exception):
    """Base for splice-gate violations."""


class SpliceBreakRowError(SpliceError):
    """A mid-series ``source_id`` change has no covering ``methodology_breaks`` row."""


class MethodologyBreak(BaseModel):
    """One compiled ``methodology_breaks`` row, narrowed to the seam coordinate.

    The gate only needs the PK (``methodology_version``) and the seam year +
    intra-year sequence; the citizen-readable ``note`` / ``kind`` live in the
    full row and are not the gate's concern (the gate enforces EXISTENCE at the
    seam, the renderer surfaces the prose).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    methodology_version: str = Field(min_length=1)
    at_year: int = Field(ge=1850, le=2100)
    at_period_seq: int = Field(ge=1, default=1)


class SeriesRow(BaseModel):
    """The minimal provenance projection the splice gate reasons over.

    One ``(entity_id, time, source_id)`` triple -- the columns of a geo
    datapoints row that decide whether a series is spliced. ``value`` is
    irrelevant to the seam test, so it is deliberately absent: the gate is a
    PROVENANCE check, not a value check (that is the divergence gate's job).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    time: int = Field(ge=1850, le=2100)
    source_id: str = Field(min_length=1)


def load_methodology_breaks(
    *,
    breaks: Iterable[Mapping[str, object]] | None = None,
    breaks_path: Path | None = None,
) -> dict[str, MethodologyBreak]:
    """Return ``{methodology_version -> MethodologyBreak}`` from the breaks table.

    Pass ``breaks`` (an iterable of row mappings) to inject synthetic fixtures;
    pass ``breaks_path`` to read a fixture CSV; the default reads the canonical
    ``datasets/data/methodology_breaks.csv``. Only ``methodology_version`` +
    ``at_year`` (+ optional ``at_period_seq``) are consumed; other columns are
    ignored so the loader does not couple to the full break-row schema.
    """
    if breaks is not None:
        rows: Iterable[Mapping[str, object]] = breaks
    else:
        path = breaks_path or DEFAULT_BREAKS_PATH
        if not path.is_file():
            return {}
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))

    out: dict[str, MethodologyBreak] = {}
    for row in rows:
        version = str(row.get("methodology_version") or "").strip()
        raw_year = row.get("at_year")
        if not version or raw_year in (None, ""):
            continue
        seq_raw = row.get("at_period_seq")
        out[version] = MethodologyBreak(
            methodology_version=version,
            at_year=int(raw_year),  # type: ignore[arg-type]
            at_period_seq=int(seq_raw) if seq_raw not in (None, "") else 1,  # type: ignore[arg-type]
        )
    return out


def _as_series_rows(rows: Iterable[object]) -> list[SeriesRow]:
    """Coerce heterogeneous row objects to :class:`SeriesRow`.

    Accepts anything exposing ``entity_id`` / ``time`` / ``source_id`` as
    attributes (e.g. ``CanonicalObservationRow``) or as mapping keys (a parsed
    CSV ``dict``), so the same gate serves the in-memory PUBLISH batch and the
    on-disk verification read.
    """
    out: list[SeriesRow] = []
    for row in rows:
        if isinstance(row, SeriesRow):
            out.append(row)
            continue
        if isinstance(row, Mapping):
            entity_id = str(row.get("entity_id") or "").strip()
            time = row.get("time")
            source_id = str(row.get("source_id") or "").strip()
        else:
            entity_id = str(getattr(row, "entity_id", "") or "").strip()
            time = getattr(row, "time", None)
            source_id = str(getattr(row, "source_id", "") or "").strip()
        if not entity_id or time in (None, "") or not source_id:
            # A row missing any provenance coordinate cannot be reasoned about;
            # skip it rather than guess (fail-fast belongs at the writer, which
            # already rejects such a row -- this gate trusts validated rows).
            continue
        out.append(SeriesRow(entity_id=entity_id, time=int(time), source_id=source_id))
    return out


def find_seams(rows: Iterable[object]) -> dict[str, list[int]]:
    """Return ``{entity_id -> [seam_year, ...]}`` for every mid-series source change.

    For each entity the rows are sorted by ``time``; a seam is recorded at a
    year whose ``source_id`` differs from the immediately preceding year's. A
    single-source entity (or a disjoint-entity panel) yields an empty list, so
    the returned mapping is empty when nothing is spliced. Interleaved sources
    (A, B, A) record EVERY boundary -- each is a real discontinuity needing a
    break.
    """
    by_entity: dict[str, list[SeriesRow]] = {}
    for row in _as_series_rows(rows):
        by_entity.setdefault(row.entity_id, []).append(row)

    seams: dict[str, list[int]] = {}
    for entity_id, entity_rows in by_entity.items():
        ordered = sorted(entity_rows, key=lambda r: r.time)
        entity_seams: list[int] = []
        prev_source: str | None = None
        for row in ordered:
            if prev_source is not None and row.source_id != prev_source:
                entity_seams.append(row.time)
            prev_source = row.source_id
        if entity_seams:
            seams[entity_id] = entity_seams
    return seams


def check_splice(
    rows: Iterable[object],
    *,
    indicator_id: str,
    methodology_break_ids: Sequence[str] | None,
    breaks: Mapping[str, MethodologyBreak],
) -> tuple[int, ...]:
    """Raise unless every mid-series ``source_id`` seam is covered by a break row.

    A seam at year ``Y`` is COVERED iff the indicator declares a
    ``methodology_break_ids`` entry whose break row resolves (the FK exists in
    ``breaks``) AND that row's ``at_year`` equals ``Y``. Both conditions are the
    plan's requirement: "a ``methodology_breaks`` row exists at the seam year
    AND the indicator's ``methodology_version`` FK resolves to it".

    Returns the sorted tuple of seam years (empty when the series is not
    spliced) so a caller can surface them in ``status``. Raises
    :class:`SpliceBreakRowError` listing the uncovered seam years otherwise.
    """
    seams = find_seams(rows)
    seam_years = sorted({year for years in seams.values() for year in years})
    if not seam_years:
        return ()

    declared = tuple(methodology_break_ids or ())
    covered_years = {
        breaks[version].at_year for version in declared if version in breaks
    }
    uncovered = [year for year in seam_years if year not in covered_years]
    if uncovered:
        dangling = [v for v in declared if v not in breaks]
        detail = (
            f"indicator {indicator_id!r} splices sources at year(s) "
            f"{uncovered} but no methodology_breaks row covers them. The "
            "time-ordered rows change source_id mid-series (a splice seam); "
            "publishing would draw a smooth line across a methodology break. "
            "Author a methodology_breaks row at each seam year and add its "
            "methodology_version to the indicator's methodology_break_ids."
        )
        if declared:
            resolved = {v: breaks[v].at_year for v in declared if v in breaks}
            detail += (
                f" Declared methodology_break_ids={list(declared)}; "
                f"resolved seam years={resolved}"
            )
            if dangling:
                detail += f"; UNRESOLVED (dangling FK)={dangling}"
        else:
            detail += " The indicator declares no methodology_break_ids."
        raise SpliceBreakRowError(detail)

    return tuple(seam_years)


__all__ = [
    "DEFAULT_BREAKS_PATH",
    "MethodologyBreak",
    "SeriesRow",
    "SpliceBreakRowError",
    "SpliceError",
    "check_splice",
    "find_seams",
    "load_methodology_breaks",
]
