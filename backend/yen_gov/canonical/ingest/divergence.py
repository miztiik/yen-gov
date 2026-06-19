"""The UPSERT-seam divergence gate (Row 6, plan section 3 honesty preconditions).

When a SECOND ``source_id`` overwrites a cell ``(entity_id, time)`` an existing
``source_id`` already wrote, the two publishers DISAGREE about the same fact.
Silent last-writer-wins would hide that disagreement behind whichever source ran
last. This gate makes a MATERIAL disagreement FAIL LOUD: a value beyond a
per-concept tolerance raises; a within-tolerance difference (rounding, a minor
revision) passes; an over-tolerance difference is only allowed when the operator
records an explicit precedence decision (the audit row).

Per-concept tolerance ruling (Hans + Max = data shape, Gregor = contracts; Row 6)
---------------------------------------------------------------------------------
* **Relative, not absolute.** An absolute tolerance is meaningless across a
  corpus whose values span rates (~2 children/woman) to crores (~10^6): 0.1 is
  noise for GSDP and a category error for TFR. The tolerance is a FRACTION of
  the cell value.
* **Symmetric with an absolute floor.** The threshold is
  ``max(tolerance * max(|existing|, |incoming|), ABS_FLOOR)`` so a near-zero
  cell (a share or index close to 0) does not make every non-equal value
  "infinitely divergent".
* **Sourced from a concept field, with a default.** The tolerance is read from
  an OPTIONAL ``divergence_tolerance`` float on the concept row (the per-concept
  override seam), defaulting to :data:`DEFAULT_DIVERGENCE_TOLERANCE` (1%) when
  absent. 1% is the band two honest publishers of the same fact stay inside
  through rounding and routine revision; a wider gap is a methodology
  disagreement, not noise. A hand-authored table across all ~164 concepts was
  rejected as YAGNI (the plan forbids a reconciliation framework); the override
  field handles the rare concept that needs a tighter or looser band, and it is
  read DEFENSIVELY (no ``concepts.json`` schema bump -- zero rows carry it
  today, it is the forward-compatible seam).
* **Same-source re-emit is never a divergence.** A revision from the SAME
  ``source_id`` legitimately replaces its own prior value (the year re-opened on
  a raw-hash change); the gate only fires when the ``source_id`` DIFFERS.
* **A null carries no claim.** When one side is ``None`` (the publisher reports
  no value for the cell) there is nothing to disagree with; the numeric side
  stands and the gate does not fire.

The gate is declare-and-compare on data in hand -- there is no reconciliation
engine, no audit.jsonl subsystem (both explicit YAGNI in the plan). The
"recorded precedence + audit row" escape is a caller-supplied
:class:`DivergenceResolution` returned for the caller to log/persist.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

#: Default relative tolerance when a concept declares no ``divergence_tolerance``.
DEFAULT_DIVERGENCE_TOLERANCE: float = 0.01

#: Absolute floor so near-zero cells do not divide by ~0 (see module docstring).
ABS_FLOOR: float = 1e-9


class DivergenceError(Exception):
    """Two sources disagree about a cell beyond the concept's tolerance."""


class DivergentCell(BaseModel):
    """One ``(entity_id, time)`` cell two sources disagree about, with the gap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    time: int = Field(ge=1850, le=2100)
    existing_source_id: str = Field(min_length=1)
    incoming_source_id: str = Field(min_length=1)
    existing_value: float
    incoming_value: float
    tolerance: float = Field(ge=0.0)


class DivergenceResolution(BaseModel):
    """An operator's recorded precedence decision for one over-tolerance cell.

    This IS the audit row the plan calls for: it names which ``source_id`` wins
    the contested cell and WHY, so an over-tolerance overwrite is never silent.
    Supplied by the caller; the gate validates it covers a real contested cell
    and returns it for the caller to persist/log.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    time: int = Field(ge=1850, le=2100)
    winning_source_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


def concept_tolerance(concept: Mapping[str, object] | None) -> float:
    """Return the per-concept relative tolerance (the override or the default).

    Reads an optional ``divergence_tolerance`` float off the concept row; falls
    back to :data:`DEFAULT_DIVERGENCE_TOLERANCE`. A negative or non-numeric
    override is rejected (a tolerance is a non-negative fraction).
    """
    if concept is None:
        return DEFAULT_DIVERGENCE_TOLERANCE
    raw = concept.get("divergence_tolerance")
    if raw is None:
        return DEFAULT_DIVERGENCE_TOLERANCE
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise DivergenceError(
            f"concept divergence_tolerance {raw!r} is not a number"
        ) from exc
    if value < 0.0:
        raise DivergenceError(
            f"concept divergence_tolerance {value!r} is negative"
        )
    return value


def _cell_value(row: object) -> tuple[str, int, str, float | None] | None:
    """Project a row to ``(entity_id, time, source_id, value)`` or ``None``."""
    if isinstance(row, Mapping):
        entity_id = str(row.get("entity_id") or "").strip()
        time = row.get("time")
        source_id = str(row.get("source_id") or "").strip()
        value = row.get("value")
    else:
        entity_id = str(getattr(row, "entity_id", "") or "").strip()
        time = getattr(row, "time", None)
        source_id = str(getattr(row, "source_id", "") or "").strip()
        value = getattr(row, "value", None)
    if not entity_id or time in (None, "") or not source_id:
        return None
    if value in (None, ""):
        numeric: float | None = None
    else:
        numeric = float(value)  # type: ignore[arg-type]
    return entity_id, int(time), source_id, numeric


def _diverges(existing: float, incoming: float, tolerance: float) -> bool:
    """Return True iff ``incoming`` is beyond ``tolerance`` of ``existing``."""
    threshold = max(tolerance * max(abs(existing), abs(incoming)), ABS_FLOOR)
    return abs(incoming - existing) > threshold


def check_divergence(
    incoming_rows: Iterable[object],
    existing_rows: Iterable[object],
    *,
    concept: Mapping[str, object] | None = None,
    resolutions: Iterable[DivergenceResolution] = (),
) -> tuple[DivergenceResolution, ...]:
    """Raise on any unresolved over-tolerance cross-source cell disagreement.

    For each cell ``(entity_id, time)`` present in BOTH ``incoming_rows`` (the
    PUBLISH batch) and ``existing_rows`` (what is on disk) whose ``source_id``
    DIFFERS and whose numeric values disagree beyond the concept tolerance, the
    cell is contested. A contested cell with no matching
    :class:`DivergenceResolution` raises :class:`DivergenceError`; a contested
    cell that IS resolved is permitted and the resolution returned (the recorded
    audit). Within-tolerance, same-source, and null-vs-value cells never fire.

    Returns the tuple of applied resolutions (the audit rows the caller logs).
    """
    tolerance = concept_tolerance(concept)
    resolution_index = {(r.entity_id, r.time): r for r in resolutions}

    existing_index: dict[tuple[str, int], tuple[str, float | None]] = {}
    for row in existing_rows:
        cell = _cell_value(row)
        if cell is None:
            continue
        entity_id, time, source_id, value = cell
        existing_index[(entity_id, time)] = (source_id, value)

    contested: list[DivergentCell] = []
    applied: list[DivergenceResolution] = []
    for row in incoming_rows:
        cell = _cell_value(row)
        if cell is None:
            continue
        entity_id, time, inc_source, inc_value = cell
        prior = existing_index.get((entity_id, time))
        if prior is None:
            continue  # a brand-new cell: no incumbent to disagree with
        ex_source, ex_value = prior
        if inc_source == ex_source:
            continue  # same source revising its own value is not a divergence
        if inc_value is None or ex_value is None:
            continue  # a null carries no claim; the numeric side stands
        if not _diverges(ex_value, inc_value, tolerance):
            continue  # the two publishers agree within tolerance
        key = (entity_id, time)
        if key in resolution_index:
            applied.append(resolution_index[key])
            continue
        contested.append(
            DivergentCell(
                entity_id=entity_id,
                time=time,
                existing_source_id=ex_source,
                incoming_source_id=inc_source,
                existing_value=ex_value,
                incoming_value=inc_value,
                tolerance=tolerance,
            )
        )

    if contested:
        lines = ", ".join(
            f"{c.entity_id}@{c.time}: {c.existing_source_id}={c.existing_value} "
            f"vs {c.incoming_source_id}={c.incoming_value} "
            f"(>{c.tolerance:.4g} rel)"
            for c in contested
        )
        raise DivergenceError(
            "cross-source value disagreement beyond the per-concept tolerance "
            f"on {len(contested)} cell(s): {lines}. Resolve by recording a "
            "DivergenceResolution (which source wins + why) or by authoring a "
            "methodology break -- never silent last-writer-wins."
        )

    return tuple(applied)


__all__ = [
    "ABS_FLOOR",
    "DEFAULT_DIVERGENCE_TOLERANCE",
    "DivergenceError",
    "DivergenceResolution",
    "DivergentCell",
    "check_divergence",
    "concept_tolerance",
]
