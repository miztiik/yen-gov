"""Tests for `yen_gov.inventory.derive.derive_collection_inventory`.

Per CLAUDE.md anti-ceremony: each test below either catches a real
regression a future reviewer could plausibly ship (status enum mis-derived,
operator-set flags clobbered by re-derivation, or list-ordering
non-determinism that would silently churn 110 artifact files in CI) or
is the byte-stability contract the wiring in commit 8 relies on. No
`f(x) == f(x)` ceremonies.
"""

from __future__ import annotations

import json

from yen_gov.inventory import derive_collection_inventory


def _periods(*specs: tuple[str, str, str]) -> list[dict[str, str]]:
    return [{"key": k, "label": label, "frequency": freq} for k, label, freq in specs]


def _row(entity_id: str, time: str, value: float | None = 1.0) -> dict[str, object]:
    return {"entity_id": entity_id, "time": time, "value": value}


def _indicator(*, geographies: list[str], periods: list[dict[str, str]], rows: list[dict[str, object]], prior: dict[str, object] | None = None) -> dict[str, object]:
    doc: dict[str, object] = {
        "sources": [{"url": "https://example/x", "fetched_at": "2026-01-01T00:00:00Z"}],
        "series_spec": {
            "description": "synthetic series for tests",
            "expected_geographies": geographies,
            "expected_periods": periods,
            "expected_periods_inference": {"basis": "authored_from_source_schedule", "confidence": "clear", "series": None},
        },
        "rows": rows,
    }
    if prior is not None:
        doc["collection_inventory"] = prior
    return doc


# --------------------------------------------------------------------- #
# core algorithm                                                        #
# --------------------------------------------------------------------- #


def test_complete_series_inline_geographies() -> None:
    """Every expected (geography, period) cell collected -> status 'complete', no pending."""
    inv = derive_collection_inventory(
        _indicator(
            geographies=["S01", "S02"],
            periods=_periods(("2024", "FY 2024-25", "annual_fy"), ("2025", "FY 2025-26", "annual_fy")),
            rows=[_row("S01", "2024"), _row("S01", "2025"), _row("S02", "2024"), _row("S02", "2025")],
        ),
    )
    assert inv["status"] == "complete"
    assert inv["pending_periods"] == []
    assert {p["key"] for p in inv["observed_periods"]} == {"2024", "2025"}


def test_partial_series_lists_only_missing_periods() -> None:
    """Period 2025 is missing 1 of 3 expected geographies -> appears in pending; 2024 fully collected does not."""
    inv = derive_collection_inventory(
        _indicator(
            geographies=["S01", "S02", "S03"],
            periods=_periods(("2024", "FY 2024-25", "annual_fy"), ("2025", "FY 2025-26", "annual_fy")),
            rows=[
                _row("S01", "2024"), _row("S02", "2024"), _row("S03", "2024"),
                _row("S01", "2025"), _row("S02", "2025"),  # S03 missing
            ],
        ),
    )
    assert inv["status"] == "partial"
    assert [p["key"] for p in inv["pending_periods"]] == ["2025"]


def test_empty_series_has_status_empty() -> None:
    inv = derive_collection_inventory(
        _indicator(
            geographies=["S01"],
            periods=_periods(("2024", "FY 2024-25", "annual_fy")),
            rows=[_row("S01", "2024", value=None)],
        ),
    )
    assert inv["status"] == "empty"


def test_unavailable_periods_excluded_from_pending() -> None:
    """A whole-period unavailable entry takes the period out of pending; status flips to complete."""
    inv = derive_collection_inventory(
        _indicator(
            geographies=["S01", "S02"],
            periods=_periods(("2024", "FY 2024-25", "annual_fy"), ("2025", "FY 2025-26", "annual_fy")),
            rows=[_row("S01", "2024"), _row("S02", "2024")],
            prior={
                "unavailable_periods": [{
                    "period": {"key": "2025", "label": "FY 2025-26", "frequency": "annual_fy"},
                    "geographies": ["S01", "S02"],
                    "reason": "publisher has not released FY 2025-26 yet (synthetic test fixture)",
                }],
            },
        ),
    )
    assert inv["status"] == "complete"
    assert inv["pending_periods"] == []
    assert len(inv["unavailable_periods"]) == 1


# --------------------------------------------------------------------- #
# operator-set field preservation                                       #
# --------------------------------------------------------------------- #


def test_operator_set_flags_preserved_across_redivation() -> None:
    """`frozen`, `refetch_requested`, `unavailable_periods` survive a re-derive even though the derived fields recompute."""
    prior = {
        "status": "stale-junk",        # derived; must be ignored
        "frozen": True,
        "refetch_requested": True,
        "unavailable_periods": [{
            "period": {"key": "2024", "label": "FY 2024-25", "frequency": "annual_fy"},
            "reason": "operator-set test fixture for preservation contract",
        }],
        "pending_periods": [{"key": "GARBAGE", "label": "x", "frequency": "annual_fy"}],  # derived; must be ignored
    }
    inv = derive_collection_inventory(
        _indicator(
            geographies=["S01"],
            periods=_periods(("2025", "FY 2025-26", "annual_fy")),
            rows=[_row("S01", "2025")],
            prior=prior,
        ),
    )
    assert inv["frozen"] is True
    assert inv["refetch_requested"] is True
    assert len(inv["unavailable_periods"]) == 1
    assert all(p["key"] != "GARBAGE" for p in inv["pending_periods"])


# --------------------------------------------------------------------- #
# determinism (the contract the commit-8 wiring depends on)             #
# --------------------------------------------------------------------- #


def test_byte_identical_re_derivation() -> None:
    """Calling twice on the same input produces byte-identical JSON.

    Real regression target: any future `set()`-ordering leak into the
    pending or observed lists would silently churn 110 artifact files
    every backend refresh. The wiring in commit 8 re-derives on every
    coverage run; if this assertion ever fails, that wiring will
    produce a noisy `git status` after every operator pull.
    """
    doc = _indicator(
        geographies=["S03", "S01", "S02"],  # deliberately unsorted
        periods=_periods(
            ("2025", "FY 2025-26", "annual_fy"),
            ("2023", "FY 2023-24", "annual_fy"),
            ("2024", "FY 2024-25", "annual_fy"),
        ),
        rows=[_row("S02", "2023"), _row("S01", "2024"), _row("S03", "2025")],
    )
    a = json.dumps(derive_collection_inventory(doc), sort_keys=False)
    b = json.dumps(derive_collection_inventory(doc), sort_keys=False)
    assert a == b
