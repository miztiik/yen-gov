"""Unit tests for the ICED sub-fuel -> canonical 5-bucket collapse.

Row 1 of the CEA+ICED faceted-ingestion plan. Pins every upstream label
mapping and that the codomain is exactly the closed 5-bucket fuel axis,
so a future edit cannot quietly add a sixth bucket or re-route a fuel.
"""

from __future__ import annotations

import pytest

from yen_gov.canonical.adapters.iced_common.fuel_collapse import (
    CANONICAL_FUELS,
    SUB_FUEL_TO_CANONICAL,
    UnknownFuelLabelError,
    collapse_fuel,
)

_EXPECTED: dict[str, str] = {
    "coal": "coal",
    "gas": "gas",
    "oil-gas": "gas",
    "hydro": "hydro",
    "nuclear": "nuclear",
    "renewable": "renewable",
    "wind": "renewable",
    "solar": "renewable",
    "small-hydro": "renewable",
    "bio-power": "renewable",
    "biomass": "renewable",
    "waste-to-energy": "renewable",
}


def test_map_matches_expected_exactly():
    assert SUB_FUEL_TO_CANONICAL == _EXPECTED


@pytest.mark.parametrize("label,bucket", sorted(_EXPECTED.items()))
def test_collapse_each_label(label: str, bucket: str):
    assert collapse_fuel(label) == bucket


def test_codomain_is_exactly_the_five_buckets():
    assert set(SUB_FUEL_TO_CANONICAL.values()) == set(CANONICAL_FUELS)
    assert set(CANONICAL_FUELS) == {"coal", "gas", "hydro", "nuclear", "renewable"}


def test_all_is_not_a_collapse_target():
    # `all` is the published-aggregate enum member, never a collapse codomain.
    assert "all" not in SUB_FUEL_TO_CANONICAL.values()
    assert "all" not in CANONICAL_FUELS


def test_unknown_label_raises():
    with pytest.raises(UnknownFuelLabelError):
        collapse_fuel("thermal")
    with pytest.raises(UnknownFuelLabelError):
        collapse_fuel("diesel")
