"""Catalogue-level invariants for ``iced_common.endpoints.ENDPOINT_CATALOGUE``.

These are not parser tests — there is no decryption or response shape
involved. They guard the *catalogue* itself: names are unique, the
``_ep`` helper correctly classifies templated paths, and the air-quality
endpoints registered on 2026-05-15 are all present and parameter-free
(so they can be bulk-mirrored without per-endpoint setup).
"""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_common.endpoints import (
    ENDPOINT_CATALOGUE,
    by_name,
    parameter_free,
)


def test_endpoint_names_are_unique():
    names = [ep.name for ep in ENDPOINT_CATALOGUE]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"duplicate endpoint name(s): {sorted(duplicates)}"


def test_endpoint_paths_are_unique():
    paths = [ep.path for ep in ENDPOINT_CATALOGUE]
    duplicates = {p for p in paths if paths.count(p) > 1}
    assert not duplicates, f"duplicate endpoint path(s): {sorted(duplicates)}"


def test_by_name_round_trip():
    for ep in ENDPOINT_CATALOGUE:
        assert by_name(ep.name) is ep


def test_by_name_raises_for_unknown():
    with pytest.raises(KeyError, match="unknown ICED endpoint"):
        by_name("nope_not_a_real_endpoint")


# ---------------------------------------------------------------------------
# Air-quality registration (2026-05-15)
# ---------------------------------------------------------------------------
# The eight endpoints registered after the 2026-05-15 live recon. Pinned
# here so an accidental rename or path edit fails loudly.

AIR_QUALITY_ENDPOINTS: dict[str, str] = {
    "aq_aqi_map_markers":   "/climate-environment/environment/air-quality/aqi-map-markers",
    "aq_aqm_cities":        "/climate-environment/aqmCityWise/aqm-cities",
    "aq_fgd":               "/climate-environment/environment/air-quality/fgd",
    "aq_co2_emission":      "/climate-environment/environment/air-quality/co2Emission",
    "aq_cpcb_dates":        "/climate-environment/environment/air-quality/cpbc-dates",
    "aq_sentinel_dates":    "/climate-environment/environment/air-quality/sentinel-dates",
    "aq_power_plant_list":  "/climate-environment/environment/air-quality/power-plant-list",
    "aq_coal_plant_impact": "/analytics/aqi-impact-due-to-coal-plants-list",
}


@pytest.mark.parametrize("name,path", sorted(AIR_QUALITY_ENDPOINTS.items()))
def test_air_quality_endpoint_registered(name: str, path: str):
    ep = by_name(name)
    assert ep.path == path
    # All AQ endpoints are GET with no path/query placeholders — bulk-mirror safe.
    assert ep.method == "GET"
    assert ep.path_params == ()
    assert ep.query_params == ()


def test_air_quality_endpoints_in_parameter_free_set():
    free_names = {ep.name for ep in parameter_free()}
    missing = set(AIR_QUALITY_ENDPOINTS) - free_names
    assert not missing, f"AQ endpoints missing from parameter_free(): {sorted(missing)}"
