"""Derived national reference series (G31a, parent plan section 20.11).

Computes two derived datapoints per (indicator, year):

- ``IN-pop-weighted``: population-weighted national average across all
  states that have BOTH a value AND a population denominator that year.
- ``IN-median``: median of state values that year (across whichever
  states have a value, regardless of population availability).

Both pseudo-entities live in ``datasets/data/entities/geo.csv`` with
``entity_kind=country`` and ``parent=IN`` (the IN-prefix namespace is
reserved for derived aggregates per parent plan section 20.11). The
output rows share the long-format 4-column shape declared at
``datasets/data/_schema/columns.json`` for ``data/datapoints/geo/*.csv``
and are written to a sibling file ``<indicator_id>-national.csv``.

Direction hard gate (parent plan section 20.11 -- Max + Hans verdict):
ONLY indicators with ``direction in {higher_is_better, lower_is_better}``
get a derived series. ``neutral`` indicators get NO national row (the
recessive grey reference line would mislead -- "higher" / "lower" has
no agreed-good direction). The gate is enforced by the caller (the CLI
sub-command checks the allowlist descriptor before invoking the
compute function); this module is pure compute and does not read the
allowlist itself.

Population denominator rules:

- Population is joined by ``(entity_id, time)``.
- For years OUTSIDE the population coverage window, the closest in-window
  year is used (back-fill from the earliest available year for queries
  before it; carry-forward from the latest available year for queries
  after it). The pilot indicator
  ``outstanding-liabilities-pct-gsdp`` spans 2007-2023; population
  ``state-population-lakhs.csv`` spans 2015-2025, so years 2007-2014 use
  the 2015 population.
- States missing from population for a given year (after the closest-year
  back-fill) are EXCLUDED from the pop-weighted sum for that year, NOT
  imputed. They are STILL included in the median calculation -- median
  uses state-row presence regardless of denominator availability.

Median rule: ``statistics.median`` of state values for the year (excludes
``IN-*`` rows by construction since the function is called only with
per-state values). Even-N tie: average of middle two (standard
statistical convention).

Provenance: every emitted row carries the caller-supplied
``derived_source_id`` (a deterministic ``src-...`` id derived via
``backend.yen_gov.canonical.citation.derive_source_id`` from the triple
``("yen-gov (derived)", <citation title>, <vintage>)``). The
corresponding row in ``datasets/data/entities/source.csv`` is the
"yen-gov (derived)" owner; one row covers all derived national-reference
indicators (one citation triple, one ``src-...`` id).

This module is stdlib-only -- no pandas, no duckdb. Pure functions for
unit testability.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping

POP_WEIGHTED_ENTITY_ID = "IN-pop-weighted"
MEDIAN_ENTITY_ID = "IN-median"

# Decimal precision for the derived value column. The two underlying
# inputs carry 1-2 decimals (the pilot's per-state values are 1-decimal
# percentage points; population is 1-2 decimal lakhs); 2 decimals on
# the derived output preserves the higher input precision without
# leaking spurious computation noise (e.g. 27.534816... -> 27.53).
_VALUE_DECIMALS = 2


def compute_national_reference_rows(
    state_rows: Iterable[Mapping[str, object]],
    population_rows: Iterable[Mapping[str, object]],
    derived_source_id: str,
) -> list[dict[str, object]]:
    """Compute pop-weighted + median-of-states derived rows.

    Args:
        state_rows: per-state observation rows, each at least carrying
            ``entity_id`` (string), ``time`` (int), ``value``
            (numeric or None). Rows with ``value is None`` are skipped
            entirely (no value means no contribution).
        population_rows: state population rows, same 4-column shape;
            ``value`` is the population denominator (units irrelevant
            for a weighted average as long as the unit is consistent
            across states). Rows with ``value is None`` are skipped.
        derived_source_id: ``src-...`` id of the citation ledger row
            covering this derivation (caller resolves via
            ``derive_source_id("yen-gov (derived)", title, vintage)``).

    Returns:
        A list of 4-column rows ``{entity_id, time, value, source_id}``
        with ``entity_id`` in ``{"IN-pop-weighted", "IN-median"}`` and
        ``source_id`` equal to ``derived_source_id`` on every row.
        Returned unsorted (caller's ``write_csv`` re-sorts by PK).
        Per (time) up to 2 rows are emitted; if both pop-weighted and
        median are uncomputable for a year (no states with values),
        zero rows are emitted for that year.

    Raises:
        ValueError: ``derived_source_id`` is empty.
    """
    if not derived_source_id:
        raise ValueError("derived_source_id must be non-empty")

    state_by_year: dict[int, dict[str, float]] = {}
    for row in state_rows:
        if row.get("entity_id") is None:
            continue
        if row.get("time") is None:
            continue
        value = row.get("value")
        if value is None:
            continue
        time = int(row["time"])  # type: ignore[arg-type]
        entity_id = str(row["entity_id"])
        state_by_year.setdefault(time, {})[entity_id] = float(value)  # type: ignore[arg-type]

    pop_by_year: dict[int, dict[str, float]] = {}
    for row in population_rows:
        if row.get("entity_id") is None:
            continue
        if row.get("time") is None:
            continue
        value = row.get("value")
        if value is None:
            continue
        time = int(row["time"])  # type: ignore[arg-type]
        entity_id = str(row["entity_id"])
        pop_by_year.setdefault(time, {})[entity_id] = float(value)  # type: ignore[arg-type]

    out: list[dict[str, object]] = []
    for year in sorted(state_by_year):
        per_state = state_by_year[year]
        if not per_state:
            continue

        # Median uses every state with a value (no population dependency).
        median_value = statistics.median(per_state.values())
        out.append(
            {
                "entity_id": MEDIAN_ENTITY_ID,
                "time": year,
                "value": round(median_value, _VALUE_DECIMALS),
                "source_id": derived_source_id,
            }
        )

        # Pop-weighted uses states that have BOTH a value and a population.
        pop_lookup = _population_lookup_for_year(pop_by_year, year)
        weighted_numerator = 0.0
        weight_denominator = 0.0
        for entity_id, state_value in per_state.items():
            pop = pop_lookup.get(entity_id)
            if pop is None:
                continue
            weighted_numerator += state_value * pop
            weight_denominator += pop
        if weight_denominator > 0:
            pw_value = weighted_numerator / weight_denominator
            out.append(
                {
                    "entity_id": POP_WEIGHTED_ENTITY_ID,
                    "time": year,
                    "value": round(pw_value, _VALUE_DECIMALS),
                    "source_id": derived_source_id,
                }
            )

    return out


def _population_lookup_for_year(
    pop_by_year: Mapping[int, Mapping[str, float]],
    year: int,
) -> Mapping[str, float]:
    """Resolve the population lookup for ``year`` with closest-year fallback.

    If ``year`` is within the population coverage window, the exact-year
    lookup is returned. Otherwise the closest in-window year is used --
    earliest year for queries before the window, latest for queries
    after it. Empty mapping returned only if ``pop_by_year`` itself is
    empty (no population data at all).
    """
    if not pop_by_year:
        return {}
    if year in pop_by_year:
        return pop_by_year[year]
    available = sorted(pop_by_year.keys())
    if year < available[0]:
        return pop_by_year[available[0]]
    if year > available[-1]:
        return pop_by_year[available[-1]]
    # In-range but missing year: use the nearest available year, ties
    # broken by the earlier one (deterministic, no in-between
    # interpolation -- population data is annual; gaps are not
    # synthesised).
    nearest = min(available, key=lambda y: (abs(y - year), y))
    return pop_by_year[nearest]
