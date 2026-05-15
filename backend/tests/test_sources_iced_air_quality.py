"""Pure-parser tests for ``yen_gov.sources.iced_air_quality.parsers``.

No network, no mocks — backed by the real decrypted ICED response
captured live on 2026-05-15 and committed under
``backend/tests/fixtures/iced_air_quality/aq_fgd_2026-05-15.json``. The
fixture IS the parser's contract; pin the bytes and the parser cannot
silently regress against the real shape.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.sources.iced_air_quality.parsers import (
    FGD_INSTALLED_STATUS,
    ParsedRow,
    emit_indicator_rows,
    extract_state_rows,
)
from yen_gov.sources.iced_common import ICEDShapeError, ENTITY_MAP


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "iced_air_quality"
FGD_FIXTURE = FIXTURE_DIR / "aq_fgd_2026-05-15.json"


@pytest.fixture(scope="module")
def fgd_response() -> dict:
    return json.loads(FGD_FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Shape sanity (the fixture itself, not the parser)
# ---------------------------------------------------------------------------


def test_fixture_outer_envelope(fgd_response):
    assert fgd_response["status"] == "success"
    assert set(fgd_response["data"].keys()) == {"fgdGroups", "data", "graphData"}
    assert len(fgd_response["data"]["data"]) == 602  # plant-units, 2026-05-15 vintage


# ---------------------------------------------------------------------------
# extract_state_rows
# ---------------------------------------------------------------------------


def test_extract_state_rows_returns_one_row_per_state(fgd_response):
    rows = extract_state_rows(fgd_response)
    # 17 states have coal thermal capacity in the 2026-05-15 snapshot.
    assert len(rows) == 17
    # Every row resolves to a known ECI state code.
    assert all(r.entity_id in set(ENTITY_MAP.values()) for r in rows)
    # No duplicate states.
    assert len({r.entity_id for r in rows}) == len(rows)


def test_extract_state_rows_sorted_by_entity_id(fgd_response):
    rows = extract_state_rows(fgd_response)
    assert [r.entity_id for r in rows] == sorted(r.entity_id for r in rows)


def test_extract_state_rows_aggregates_capacity_correctly(fgd_response):
    """Independent re-aggregation: parser must match a hand-rolled groupby."""
    rows = extract_state_rows(fgd_response)
    by_state = {r.entity_id: r for r in rows}

    # Hand-roll the same aggregation from the raw response.
    expected: dict[str, dict[str, float]] = {}
    for plant in fgd_response["data"]["data"]:
        state = plant["state"]
        if state not in ENTITY_MAP:
            continue
        eid = ENTITY_MAP[state]
        cap = plant["capacity"]
        if cap is None:
            continue
        b = expected.setdefault(eid, {"tot": 0.0, "inst": 0.0})
        b["tot"] += cap
        if plant["fgdStatus"] == FGD_INSTALLED_STATUS:
            b["inst"] += cap

    for eid, b in expected.items():
        assert by_state[eid].capacity_total_mw == pytest.approx(b["tot"])
        assert by_state[eid].capacity_installed_mw == pytest.approx(b["inst"])


def test_chhatisgarh_typo_resolves_to_s26(fgd_response):
    """The ICED feed spells Chhattisgarh as 'Chhatisgarh' (single 't').

    The alias was added to ENTITY_MAP in the same commit as this adapter.
    Asserting it here so the fix can't silently regress.
    """
    rows = {r.entity_id: r for r in extract_state_rows(fgd_response)}
    assert "S26" in rows
    assert rows["S26"].state_name == "Chhatisgarh"
    assert rows["S26"].units_total > 0


def test_unknown_state_spelling_raises_loudly():
    """A new state spelling must fail in CI, not silently drop the rows."""
    bad = {
        "status": "success",
        "data": {
            "fgdGroups": [],
            "data": [
                {"state": "Atlantis", "capacity": 100, "fgdStatus": "FGD installed"},
            ],
            "graphData": None,
        },
    }
    with pytest.raises(ICEDShapeError, match="Atlantis"):
        extract_state_rows(bad)


def test_missing_capacity_is_dropped_not_zeroed():
    """Capacity=None means 'unknown', not 'zero MW' — must not pollute either side."""
    response = {
        "status": "success",
        "data": {
            "fgdGroups": [],
            "data": [
                {"state": "Tamil Nadu", "capacity": 1000, "fgdStatus": "FGD installed"},
                {"state": "Tamil Nadu", "capacity": None, "fgdStatus": "FGD installed"},
                {"state": "Tamil Nadu", "capacity": 4000, "fgdStatus": "Bid Awarded"},
            ],
            "graphData": None,
        },
    }
    [row] = extract_state_rows(response)
    assert row.entity_id == "S22"
    assert row.capacity_total_mw == 5000.0
    assert row.capacity_installed_mw == 1000.0
    # Units count: only the rows with valid capacity (None is dropped wholesale).
    assert row.units_total == 2
    assert row.units_installed == 1


def test_share_property_safe_for_zero_total():
    row = ParsedRow(
        entity_id="S99",
        state_name="Nowhere",
        capacity_total_mw=0.0,
        capacity_installed_mw=0.0,
        units_total=0,
        units_installed=0,
    )
    assert row.installed_share_pct == 0.0


# ---------------------------------------------------------------------------
# Headline-claim tests — would catch a methodology silently changing on us
# ---------------------------------------------------------------------------


def test_national_installed_share_is_under_5_percent(fgd_response):
    """As of 2026-05-15, national FGD installation is ~4.5 % of capacity.

    If the parser ever silently double-counts or skips, this assertion
    will move sharply. Wide bound (1 % - 15 %) so it tolerates real
    quarterly drift but flags algorithmic regressions.
    """
    rows = extract_state_rows(fgd_response)
    total = sum(r.capacity_total_mw for r in rows)
    inst = sum(r.capacity_installed_mw for r in rows)
    assert total > 200_000  # ~215 GW expected
    national_share = inst / total * 100
    assert 1.0 < national_share < 15.0, f"national FGD share = {national_share:.2f}%"


def test_haryana_leads_states_2026_05_15(fgd_response):
    """Hard-coded ranking pin against the 2026-05-15 snapshot.

    Haryana (S07) was the leader at 24.8% in the captured fixture. If
    the parser changes the ranking against unchanged input, that's a
    bug; if the input changes in a future fixture, this test moves with
    it. Pinning the headline claim ensures the chart we ship matches
    what the parser computes.
    """
    rows = extract_state_rows(fgd_response)
    leader = max(rows, key=lambda r: r.installed_share_pct)
    assert leader.entity_id == "S07"
    assert 20.0 < leader.installed_share_pct < 30.0


# ---------------------------------------------------------------------------
# emit_indicator_rows
# ---------------------------------------------------------------------------


def test_emit_indicator_rows_one_per_state(fgd_response):
    parsed = extract_state_rows(fgd_response)
    emitted = emit_indicator_rows(parsed)
    assert len(emitted) == len(parsed)
    # Schema requires entity_id and value; time is added by the ingest layer.
    assert all(set(r.keys()) == {"entity_id", "value"} for r in emitted)
    # Value is the percent-share, rounded to 2dp.
    assert all(isinstance(r["value"], float) for r in emitted)
    assert all(0.0 <= r["value"] <= 100.0 for r in emitted)
