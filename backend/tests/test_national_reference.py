"""Tests for ``yen_gov.canonical.national_reference`` (G31a).

Pure-function unit tests for ``compute_national_reference_rows``. No
mocks (CLAUDE.md Holy Law #7); no on-disk corpus walk (anti-pattern in
CLAUDE.md section 10 -- pytest must not walk the real ``datasets/``
tree).
"""

from __future__ import annotations

import math
import statistics

import pytest

from yen_gov.canonical.national_reference import (
    MEDIAN_ENTITY_ID,
    POP_WEIGHTED_ENTITY_ID,
    compute_national_reference_rows,
)

_SRC = "src-deadbeef0001"


def _row(entity_id: str, time: int, value: float | None, source_id: str = "src-x") -> dict[str, object]:
    return {"entity_id": entity_id, "time": time, "value": value, "source_id": source_id}


def test_pop_weighted_matches_hand_calc_three_states_three_years() -> None:
    """3 states x 3 years x 3 populations: assert hand-calculated weighted average."""
    state_rows = [
        # (entity_id, time, value, ...)
        _row("a", 2020, 10.0),
        _row("b", 2020, 20.0),
        _row("c", 2020, 30.0),
        _row("a", 2021, 15.0),
        _row("b", 2021, 25.0),
        _row("c", 2021, 35.0),
        _row("a", 2022, 11.0),
        _row("b", 2022, 22.0),
        _row("c", 2022, 33.0),
    ]
    population_rows = [
        # equal populations -> pop-weighted == simple mean
        _row("a", 2020, 100.0),
        _row("b", 2020, 100.0),
        _row("c", 2020, 100.0),
        # 2021: skewed weights -- b weighted heavy
        _row("a", 2021, 10.0),
        _row("b", 2021, 70.0),
        _row("c", 2021, 20.0),
        # 2022: skewed weights -- c weighted heavy
        _row("a", 2022, 20.0),
        _row("b", 2022, 20.0),
        _row("c", 2022, 60.0),
    ]
    rows = compute_national_reference_rows(state_rows, population_rows, _SRC)

    by_key = {(r["entity_id"], r["time"]): r["value"] for r in rows}

    # 2020 pop-weighted: (10*100 + 20*100 + 30*100) / 300 = 6000/300 = 20.00
    assert by_key[(POP_WEIGHTED_ENTITY_ID, 2020)] == 20.00
    # 2021 pop-weighted: (15*10 + 25*70 + 35*20) / 100 = (150+1750+700)/100 = 2600/100 = 26.00
    assert by_key[(POP_WEIGHTED_ENTITY_ID, 2021)] == 26.00
    # 2022 pop-weighted: (11*20 + 22*20 + 33*60) / 100 = (220+440+1980)/100 = 2640/100 = 26.40
    assert by_key[(POP_WEIGHTED_ENTITY_ID, 2022)] == 26.40


def test_median_matches_sorted_middle_three_states_one_year() -> None:
    """3 states x 1 year: assert median equals the middle of sorted values."""
    state_rows = [
        _row("a", 2020, 10.0),
        _row("b", 2020, 20.0),
        _row("c", 2020, 30.0),
    ]
    rows = compute_national_reference_rows(state_rows, [], _SRC)
    median_rows = [r for r in rows if r["entity_id"] == MEDIAN_ENTITY_ID]
    assert len(median_rows) == 1
    assert median_rows[0]["time"] == 2020
    assert median_rows[0]["value"] == 20.00


def test_median_even_n_averages_middle_two() -> None:
    """2 states x 1 year: assert median is the mean of the two values."""
    state_rows = [
        _row("a", 2020, 12.0),
        _row("b", 2020, 18.0),
    ]
    rows = compute_national_reference_rows(state_rows, [], _SRC)
    median_rows = [r for r in rows if r["entity_id"] == MEDIAN_ENTITY_ID]
    assert len(median_rows) == 1
    # standard statistical convention: (12 + 18) / 2 = 15.00
    assert median_rows[0]["value"] == 15.00
    assert median_rows[0]["value"] == round(statistics.median([12.0, 18.0]), 2)


def test_state_missing_population_excluded_from_pop_weighted_included_in_median() -> None:
    """State with no population row that year: excluded from pop-weighted, kept in median.

    Verifies the documented split: median uses STATE-row presence
    (regardless of denominator availability); pop-weighted excludes any
    state without a usable denominator.
    """
    state_rows = [
        _row("a", 2020, 10.0),
        _row("b", 2020, 20.0),
        _row("c", 2020, 30.0),
    ]
    # Only a + b carry population; c is excluded from pop-weighted.
    population_rows = [
        _row("a", 2020, 100.0),
        _row("b", 2020, 100.0),
    ]
    rows = compute_national_reference_rows(state_rows, population_rows, _SRC)
    by_key = {(r["entity_id"], r["time"]): r["value"] for r in rows}

    # pop-weighted: (10*100 + 20*100) / 200 = 15.00  (c excluded)
    assert by_key[(POP_WEIGHTED_ENTITY_ID, 2020)] == 15.00
    # median: still uses all 3 state values -> middle = 20.00
    assert by_key[(MEDIAN_ENTITY_ID, 2020)] == 20.00


def test_every_row_carries_source_id_and_namespaced_entity_id() -> None:
    """All emitted rows carry ``derived_source_id`` and IN-* entity_ids."""
    state_rows = [
        _row("a", 2020, 10.0),
        _row("b", 2020, 20.0),
    ]
    population_rows = [
        _row("a", 2020, 50.0),
        _row("b", 2020, 50.0),
    ]
    rows = compute_national_reference_rows(state_rows, population_rows, _SRC)
    assert rows, "expected at least one derived row"
    for r in rows:
        assert r["source_id"] == _SRC
        assert r["entity_id"] in {POP_WEIGHTED_ENTITY_ID, MEDIAN_ENTITY_ID}


def test_year_outside_population_window_uses_closest_year() -> None:
    """For indicator years outside the pop coverage, use closest in-window year."""
    state_rows = [
        # 2010 is BEFORE pop coverage (which only has 2015-2017)
        _row("a", 2010, 10.0),
        _row("b", 2010, 20.0),
        # 2020 is AFTER pop coverage
        _row("a", 2020, 30.0),
        _row("b", 2020, 40.0),
    ]
    # Population only covers 2015-2017; weights skewed each year.
    population_rows = [
        _row("a", 2015, 10.0),  # earliest year -- back-fill source for 2010
        _row("b", 2015, 90.0),
        _row("a", 2016, 50.0),
        _row("b", 2016, 50.0),
        _row("a", 2017, 80.0),  # latest year -- carry-forward source for 2020
        _row("b", 2017, 20.0),
    ]
    rows = compute_national_reference_rows(state_rows, population_rows, _SRC)
    by_key = {(r["entity_id"], r["time"]): r["value"] for r in rows}

    # 2010 uses 2015 weights (10 + 90 = 100); (10*10 + 20*90) / 100 = 19.00
    assert by_key[(POP_WEIGHTED_ENTITY_ID, 2010)] == 19.00
    # 2020 uses 2017 weights (80 + 20 = 100); (30*80 + 40*20) / 100 = 32.00
    assert by_key[(POP_WEIGHTED_ENTITY_ID, 2020)] == 32.00


def test_no_population_data_at_all_emits_median_only() -> None:
    """If no population data is provided, only median rows are emitted."""
    state_rows = [
        _row("a", 2020, 10.0),
        _row("b", 2020, 20.0),
        _row("c", 2020, 30.0),
    ]
    rows = compute_national_reference_rows(state_rows, [], _SRC)
    assert all(r["entity_id"] == MEDIAN_ENTITY_ID for r in rows)
    assert len(rows) == 1
    assert rows[0]["value"] == 20.00


def test_state_value_none_is_skipped_in_both_metrics() -> None:
    """``value is None`` rows do not contribute to median or pop-weighted."""
    state_rows = [
        _row("a", 2020, 10.0),
        _row("b", 2020, None),  # missing -- excluded from both
        _row("c", 2020, 30.0),
    ]
    population_rows = [
        _row("a", 2020, 50.0),
        _row("b", 2020, 50.0),
        _row("c", 2020, 50.0),
    ]
    rows = compute_national_reference_rows(state_rows, population_rows, _SRC)
    by_key = {(r["entity_id"], r["time"]): r["value"] for r in rows}

    # Only a + c contribute; pop-weighted: (10*50 + 30*50) / 100 = 20.00
    assert by_key[(POP_WEIGHTED_ENTITY_ID, 2020)] == 20.00
    # median of {10, 30} = (10+30)/2 = 20.00
    assert by_key[(MEDIAN_ENTITY_ID, 2020)] == 20.00


def test_empty_state_rows_emits_nothing() -> None:
    """No state rows at all -> empty output (no median, no pop-weighted)."""
    rows = compute_national_reference_rows([], [_row("a", 2020, 100.0)], _SRC)
    assert rows == []


def test_empty_source_id_rejected() -> None:
    """``derived_source_id`` must be non-empty (fail fast at the boundary)."""
    with pytest.raises(ValueError, match="non-empty"):
        compute_national_reference_rows([_row("a", 2020, 10.0)], [], "")


def test_no_unexpected_extra_rows_per_year() -> None:
    """At most 2 rows per (year): one pop-weighted, one median."""
    state_rows = [
        _row("a", 2020, 10.0),
        _row("b", 2020, 20.0),
        _row("a", 2021, 30.0),
        _row("b", 2021, 40.0),
    ]
    population_rows = [
        _row("a", 2020, 50.0),
        _row("b", 2020, 50.0),
        _row("a", 2021, 50.0),
        _row("b", 2021, 50.0),
    ]
    rows = compute_national_reference_rows(state_rows, population_rows, _SRC)
    by_year: dict[int, list[str]] = {}
    for r in rows:
        by_year.setdefault(int(r["time"]), []).append(str(r["entity_id"]))  # type: ignore[arg-type]
    for year, ids in by_year.items():
        assert len(ids) <= 2, f"year {year} emitted {len(ids)} rows: {ids}"
        assert sorted(ids) == sorted(set(ids)), f"year {year} duplicate entity_id"


def test_pop_weighted_with_pop_zero_excluded() -> None:
    """A state with population 0 contributes nothing to pop-weighted (no NaN)."""
    state_rows = [
        _row("a", 2020, 10.0),
        _row("b", 2020, 20.0),
    ]
    population_rows = [
        _row("a", 2020, 100.0),
        _row("b", 2020, 0.0),  # zero weight -> b contributes nothing
    ]
    rows = compute_national_reference_rows(state_rows, population_rows, _SRC)
    by_key = {(r["entity_id"], r["time"]): r["value"] for r in rows}
    # numerator: 10*100 + 20*0 = 1000; denominator: 100 + 0 = 100 -> 10.00
    assert by_key[(POP_WEIGHTED_ENTITY_ID, 2020)] == 10.00
    assert not math.isnan(float(by_key[(POP_WEIGHTED_ENTITY_ID, 2020)]))  # type: ignore[arg-type]
