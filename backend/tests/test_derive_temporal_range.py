"""Tests for `yen_gov.inventory.derive.derive_temporal_range`.

Pure-function tests against fixtures. No real-corpus walks, no I/O — the
unit/contract separation per CLAUDE.md §15 (the corpus walk lives in
`tools/spike_derive_temporal_range_all_indicators.py`, run locally
before each schema bump, NOT in CI).

Each test pins one regression a future reviewer could plausibly ship:
- vocabulary fail-loud (debate consensus 2026-05-17),
- gap math at each grain (year, fiscal_year, month, quarter),
- snapshot collapse (min == max → gap_count = 0),
- empty rows → None (no fabrication),
- date grain → gap_count omitted (cadence undefined),
- label fallback to time token,
- determinism across row-order shuffling.
"""

from __future__ import annotations

import pytest

from yen_gov.inventory import derive_temporal_range


def _ind(grain: str, rows: list[dict], ind_id: str = "topic/test_id", cadence: str | None = None) -> dict:
    indicator: dict = {"id": ind_id, "time_grain": grain}
    if cadence is not None:
        indicator["cadence"] = cadence
    return {
        "indicator": indicator,
        "rows": rows,
    }


def _row(time: str, label: str | None = None, value: float = 1.0) -> dict:
    r: dict = {"entity_id": "S22", "time": time, "value": value}
    if label is not None:
        r["period_label"] = label
    return r


# --- shape: year ------------------------------------------------------ #

def test_year_grain_continuous_range_zero_gaps() -> None:
    rows = [_row(str(y), label=str(y)) for y in (2018, 2019, 2020, 2021, 2022, 2023)]
    out = derive_temporal_range(_ind("year", rows))
    assert out is not None
    assert out["min_time"] == "2018"
    assert out["max_time"] == "2023"
    assert out["min_period_label"] == "2018"
    assert out["max_period_label"] == "2023"
    assert out["observed_periods_within_range"] == 6
    assert out["gap_count_within_range"] == 0
    assert out["time_grain"] == "year"


def test_year_grain_with_pm25_shaped_gap() -> None:
    """PM2.5-shaped fixture: range 2018..2023 with 2020 missing → gap_count=1.

    This is the load-bearing AQ honesty case the plan was written for.
    """
    rows = [_row(str(y)) for y in (2018, 2019, 2021, 2022, 2023)]
    out = derive_temporal_range(_ind("year", rows))
    assert out is not None
    assert out["min_time"] == "2018"
    assert out["max_time"] == "2023"
    assert out["observed_periods_within_range"] == 5
    assert out["gap_count_within_range"] == 1


# --- shape: year_month / fiscal_year --------------------------------- #

def test_fiscal_year_grain_continuous_FY_range() -> None:
    """FY tokens emit as YYYY-04 (April-anchored). FY2015-16..FY2024-25 = 10 FYs."""
    rows = [_row(f"{y}-04", label=f"FY {y}-{(y + 1) % 100:02d}") for y in range(2015, 2025)]
    out = derive_temporal_range(_ind("fiscal_year", rows))
    assert out is not None
    assert out["min_time"] == "2015-04"
    assert out["max_time"] == "2024-04"
    assert out["min_period_label"] == "FY 2015-16"
    assert out["max_period_label"] == "FY 2024-25"
    assert out["observed_periods_within_range"] == 10
    assert out["gap_count_within_range"] == 0


def test_fiscal_year_grain_with_gap() -> None:
    rows = [_row(f"{y}-04") for y in (2015, 2016, 2018, 2019)]  # 2017 missing
    out = derive_temporal_range(_ind("fiscal_year", rows))
    assert out is not None
    assert out["observed_periods_within_range"] == 4
    assert out["gap_count_within_range"] == 1  # 2017-04 is the missing FY


# --- shape: year_month / month --------------------------------------- #

def test_month_grain_continuous() -> None:
    rows = [_row(f"2024-{m:02d}") for m in range(1, 13)]
    out = derive_temporal_range(_ind("month", rows))
    assert out is not None
    assert out["min_time"] == "2024-01"
    assert out["max_time"] == "2024-12"
    assert out["observed_periods_within_range"] == 12
    assert out["gap_count_within_range"] == 0


def test_month_grain_with_gap_spans_year_boundary() -> None:
    # 2024-11, 2024-12, 2025-01, [2025-02 missing], 2025-03 → 5 expected, 4 observed
    rows = [_row(t) for t in ("2024-11", "2024-12", "2025-01", "2025-03")]
    out = derive_temporal_range(_ind("month", rows))
    assert out is not None
    assert out["observed_periods_within_range"] == 4
    assert out["gap_count_within_range"] == 1


# --- shape: quarter --------------------------------------------------- #

def test_quarter_grain_aligned_strides() -> None:
    # Q1 FY24-25 (Apr), Q2 (Jul), Q3 (Oct), Q4 (Jan) → 4 quarters across April..January
    rows = [_row(t) for t in ("2024-04", "2024-07", "2024-10", "2025-01")]
    out = derive_temporal_range(_ind("quarter", rows))
    assert out is not None
    assert out["min_time"] == "2024-04"
    assert out["max_time"] == "2025-01"
    assert out["observed_periods_within_range"] == 4
    assert out["gap_count_within_range"] == 0


# --- shape: date (snapshot) ------------------------------------------ #

def test_date_grain_omits_gap_count() -> None:
    """Snapshot dates have no cadence; gap_count is meaningless and absent."""
    rows = [_row("2026-05-14")]
    out = derive_temporal_range(_ind("date", rows))
    assert out is not None
    assert out["min_time"] == "2026-05-14"
    assert out["max_time"] == "2026-05-14"
    assert out["observed_periods_within_range"] == 1
    assert "gap_count_within_range" not in out


def test_date_grain_multi_snapshot_still_omits_gap_count() -> None:
    rows = [_row(t) for t in ("2024-01-15", "2025-06-30", "2026-05-14")]
    out = derive_temporal_range(_ind("date", rows))
    assert out is not None
    assert out["observed_periods_within_range"] == 3
    assert "gap_count_within_range" not in out


# --- snapshot collapse ------------------------------------------------ #

def test_snapshot_min_eq_max_gap_zero() -> None:
    rows = [_row("2026-03"), _row("2026-03", value=2.0)]  # 2 rows, 1 distinct time
    out = derive_temporal_range(_ind("month", rows))
    assert out is not None
    assert out["min_time"] == out["max_time"] == "2026-03"
    assert out["observed_periods_within_range"] == 1
    assert out["gap_count_within_range"] == 0


# --- empty rows ------------------------------------------------------- #

def test_empty_rows_returns_none() -> None:
    assert derive_temporal_range(_ind("year", [])) is None


def test_rows_without_time_field_returns_none() -> None:
    rows = [{"entity_id": "S22", "value": 1.0}]
    assert derive_temporal_range(_ind("year", rows)) is None


# --- fail-loud: mixed vocabulary ------------------------------------- #

def test_mixed_vocabulary_raises_value_error() -> None:
    """Heterogeneous rows[].time is an adapter bug. Fail at the boundary.

    Debate consensus 2026-05-17: silent omit would overload the null
    signal — operator cannot distinguish "no rows" from "emitter gave up
    on mixed vocab". CLAUDE.md §10.
    """
    rows = [_row("2024-04"), _row("2025")]  # year_month + year mixed
    with pytest.raises(ValueError, match="heterogeneous"):
        derive_temporal_range(_ind("fiscal_year", rows))


# --- label fallback --------------------------------------------------- #

def test_period_label_missing_falls_back_to_time_token() -> None:
    rows = [_row("2018"), _row("2023")]  # no period_label
    out = derive_temporal_range(_ind("year", rows))
    assert out is not None
    assert out["min_period_label"] == "2018"
    assert out["max_period_label"] == "2023"


def test_period_label_preserved_when_present() -> None:
    rows = [_row("2018", label="2018"), _row("2023", label="2023")]
    out = derive_temporal_range(_ind("year", rows))
    assert out is not None
    assert out["min_period_label"] == "2018"
    assert out["max_period_label"] == "2023"


# --- determinism ------------------------------------------------------ #

def test_row_order_does_not_affect_output() -> None:
    """Determinism contract: shuffling rows[] must not change derived output.

    Pins the §16 #13 / fetched_at-smear lesson at the function boundary —
    if this fails, the emitter's byte-stability test will fail too.
    """
    times = ["2018", "2019", "2021", "2022", "2023"]
    rows_a = [_row(t) for t in times]
    rows_b = [_row(t) for t in reversed(times)]
    assert derive_temporal_range(_ind("year", rows_a)) == derive_temporal_range(_ind("year", rows_b))


# --- time_grain mirror ------------------------------------------------ #

def test_time_grain_mirrored_into_output() -> None:
    rows = [_row("2024")]
    out = derive_temporal_range(_ind("year", rows))
    assert out is not None
    assert out["time_grain"] == "year"


def test_missing_time_grain_omits_key() -> None:
    """When the indicator carries no `time_grain`, the derivation OMITS
    the key rather than writing the empty string. Mirrors the TS
    derivation; conflating "no grain" with `""` would drift between
    Python and TS and could mislead consumers checking
    `"time_grain" in row`. Per Fowler review 2026-05-17.
    """
    rows = [_row("2024")]
    doc = {"indicator": {"id": "x/y"}, "rows": rows}
    out = derive_temporal_range(doc)
    assert out is not None
    assert "time_grain" not in out


# --- cadence (ADR-0027) ---------------------------------------------- #

def test_cadence_decennial_omits_both_observed_and_gap() -> None:
    """Census-shaped: cadence=decennial, time_grain=year, 6 obs over 50 years.

    Per ADR-0027: decennial series have no defined inter-observation
    interval, so framing them as "6 of 51 expected" or "45 gaps" would
    mislead the citizen into reading patchiness into a complete record.
    Both fields must be absent.
    """
    rows = [_row(str(y)) for y in (1961, 1971, 1981, 1991, 2001, 2011)]
    out = derive_temporal_range(_ind("year", rows, cadence="decennial"))
    assert out is not None
    assert out["min_time"] == "1961"
    assert out["max_time"] == "2011"
    assert out["cadence"] == "decennial"
    assert "observed_periods_within_range" not in out
    assert "gap_count_within_range" not in out


def test_cadence_ad_hoc_omits_both_observed_and_gap() -> None:
    """UNFCCC BUR-shaped: cadence=ad_hoc, time_grain=year, irregular years."""
    rows = [_row(str(y)) for y in (1994, 2000, 2010, 2014, 2016, 2020)]
    out = derive_temporal_range(_ind("year", rows, cadence="ad_hoc"))
    assert out is not None
    assert out["min_time"] == "1994"
    assert out["max_time"] == "2020"
    assert out["cadence"] == "ad_hoc"
    assert "observed_periods_within_range" not in out
    assert "gap_count_within_range" not in out


def test_cadence_annual_cy_keeps_gap_math() -> None:
    """When cadence IS defined as annual, gap_count remains computed."""
    rows = [_row(str(y)) for y in (2018, 2019, 2021, 2022, 2023)]  # 2020 missing
    out = derive_temporal_range(_ind("year", rows, cadence="annual_cy"))
    assert out is not None
    assert out["cadence"] == "annual_cy"
    assert out["observed_periods_within_range"] == 5
    assert out["gap_count_within_range"] == 1


def test_cadence_absent_falls_back_to_time_grain_inference() -> None:
    """Back-compat: artifacts without cadence behave exactly as v4.0."""
    rows = [_row(str(y)) for y in (2018, 2019, 2021)]
    out = derive_temporal_range(_ind("year", rows))  # no cadence
    assert out is not None
    assert "cadence" not in out
    assert out["observed_periods_within_range"] == 3
    assert out["gap_count_within_range"] == 1


def test_cadence_mirror_present_when_set() -> None:
    rows = [_row("2024")]
    out = derive_temporal_range(_ind("year", rows, cadence="annual_cy"))
    assert out is not None
    assert out["cadence"] == "annual_cy"

# --- shared-fixture parity with TS mirror ----------------------------- #
#
# Same JSON file is consumed by frontend/src/lib/indicators.test.ts. Any
# rule drift between this Python derivation and the TS
# `deriveTemporalRange` mirror fails BOTH suites at once. Per
# TODO/20260517-coverage-temporal-range-plan.md Phase #3.

import json as _json  # noqa: E402  (intentionally below the main block)
from pathlib import Path as _Path  # noqa: E402

_FIXTURES_PATH = (
    _Path(__file__).resolve().parents[2]
    / "datasets" / "_test" / "temporal-range-fixtures" / "cases.json"
)


def _load_fixture_cases() -> list[dict]:
    with _FIXTURES_PATH.open(encoding="utf-8") as fh:
        payload = _json.load(fh)
    return list(payload["cases"])


@pytest.mark.parametrize("case", _load_fixture_cases(), ids=lambda c: c["name"])
def test_shared_fixture_parity_with_ts_mirror(case: dict) -> None:
    doc = {"indicator": case["indicator"], "rows": case["rows"]}
    got = derive_temporal_range(doc)
    assert got == case["expected"]