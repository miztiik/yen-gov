"""Tests for the india-geodata energy/power-plants source adapter."""

from __future__ import annotations

from yen_gov.sources.india_geodata.power_plants import (
    _normalise_state,
    _rollup_by_state_fuel,
    _to_mw,
    _temporal_to_year,
)


def test_normalise_state_handles_messy_upstream_strings() -> None:
    """Upstream uses 'AP', 'ANDHRA PRADESH', 'Arunachal Pradesh', etc. interchangeably."""
    assert _normalise_state("TN") == "Tamil Nadu"
    assert _normalise_state("Tamil Nadu") == "Tamil Nadu"
    assert _normalise_state("  tamil nadu  ") == "Tamil Nadu"
    assert _normalise_state("ANDHRA PRADESH") == "Andhra Pradesh"
    assert _normalise_state("AP") == "Andhra Pradesh"
    assert _normalise_state("AR.  PRADESH") == "Arunachal Pradesh"
    assert _normalise_state("ar. pradesh") == "Arunachal Pradesh"
    # Unknown / empty:
    assert _normalise_state(None) is None
    assert _normalise_state("") is None
    assert _normalise_state("Atlantis") is None


def test_to_mw_coerces_strings_and_drops_garbage() -> None:
    """Upstream stores inst_cap as a string; some entries are blank or non-numeric."""
    assert _to_mw("1040") == 1040.0
    assert _to_mw("12.5") == 12.5
    assert _to_mw(40) == 40.0
    assert _to_mw("") is None
    assert _to_mw(None) is None
    assert _to_mw("n/a") is None
    # Zero or negative is treated as missing — power capacity cannot be 0.
    assert _to_mw("0") is None
    assert _to_mw("-5") is None


def test_temporal_to_year_extracts_year_or_falls_back() -> None:
    """Upstream's coverage.temporal is free-form ('2019', 'snapshot 2026-03-15')."""
    assert _temporal_to_year("2019") == "2019"
    assert _temporal_to_year("snapshot 2026-03-15") == "2026"
    # Unknown / missing falls through to current year (which we don't pin in
    # the test — just assert it parses to a 4-digit YYYY string).
    out = _temporal_to_year(None)
    assert len(out) == 4 and out.isdigit()


def test_rollup_by_state_fuel_aggregates_and_reports_unresolved() -> None:
    """Plants in unknown states accumulate into the unresolved list."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            # Resolved (TN):
            {"properties": {"state": "TN", "type": "coal_power_plant", "inst_cap": "1000"}},
            {"properties": {"state": "Tamil Nadu", "type": "coal_power_plant", "inst_cap": "500"}},
            # Resolved (TN), different fuel:
            {"properties": {"state": "TN", "type": "hydro_power_plant", "inst_cap": "300"}},
            # Unresolved upstream label:
            {"properties": {"state": "Atlantis", "type": "coal_power_plant", "inst_cap": "777"}},
            # Garbage capacity — dropped.
            {"properties": {"state": "TN", "type": "diesel_power_plant", "inst_cap": ""}},
        ],
    }
    state_to_eci = {"Tamil Nadu": "S22"}

    rows, unresolved = _rollup_by_state_fuel(geojson, state_to_eci)

    fuels = {(r.eci, r.fuel): r.mw for r in rows}
    assert fuels[("S22", "coal_power_plant")] == 1500.0
    assert fuels[("S22", "hydro_power_plant")] == 300.0
    assert ("S22", "diesel_power_plant") not in fuels  # garbage capacity skipped
    assert unresolved == ["Atlantis"]
