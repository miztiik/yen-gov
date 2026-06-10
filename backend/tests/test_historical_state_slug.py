"""Unit tests for backend.yen_gov.canonical.historical_state_slug.

Covers the 5 formation events seeded in
``datasets/taxonomy/state_formation_events.json`` plus the
no-formation pass-through (Tamil Nadu) and the parse-failure branch.

ECI codes pinned against the on-disk taxonomy
``datasets/taxonomy/entities.json`` (Holy Law #3):
  - S12 = Madhya Pradesh (current)
  - S26 = Chhattisgarh (carved 2000-11-01 from S12)
  - S24 = Uttar Pradesh
  - S28 = Uttarakhand (carved 2000-11-09 from S24)
  - S04 = Bihar
  - S27 = Jharkhand (carved 2000-11-15 from S04)
  - S01 = Andhra Pradesh
  - S29 = Telangana (carved 2014-06-02 from S01)
  - U06 = Goa-Daman-Diu (historical, pre-1987 UT)
  - S05 = Goa (current)
  - U03 = Dadra and Nagar Haveli and Daman and Diu (current; D&D lineage)
"""

from __future__ import annotations

import pytest

from yen_gov.canonical.historical_state_slug import (
    DEFAULT_CATALOGUE_PATH,
    MODERN_STATE_SLUG_BY_ECI_CODE,
    historical_state_slug,
)


# ---------------------------------------------------------------------------
# Oracle (plan-doc PR-W1b row line 25): the load-bearing two-line proof
# that the temporal crosswalk works.
# ---------------------------------------------------------------------------


def test_oracle_chhattisgarh_pc_pre_bifurcation_returns_historical_mp():
    """1952 << 2000-11-01: CG PC was inside undivided MP."""
    assert (
        historical_state_slug("IN-PC-2008-S26-1", 1952)
        == "madhya-pradesh-1947-1999"
    )


def test_oracle_chhattisgarh_pc_post_bifurcation_returns_modern_cg():
    """2024 >> 2000-11-01: CG PC sits in modern Chhattisgarh."""
    assert historical_state_slug("IN-PC-2008-S26-1", 2024) == "chhattisgarh"


# ---------------------------------------------------------------------------
# MP-CG (2000-11-01): both sides of the bifurcation
# ---------------------------------------------------------------------------


def test_mp_pc_pre_bifurcation_returns_historical_mp():
    """MP PC in 1952: still inside undivided MP (parent code S12)."""
    assert (
        historical_state_slug("IN-PC-2008-S12-1", 1952)
        == "madhya-pradesh-1947-1999"
    )


def test_mp_pc_post_bifurcation_returns_modern_mp():
    """MP PC in 2024: modern MP (S12, post-2000 carve)."""
    assert historical_state_slug("IN-PC-2008-S12-1", 2024) == "madhya-pradesh"


# ---------------------------------------------------------------------------
# UP-UK (2000-11-09): Uttarakhand pre/post
# ---------------------------------------------------------------------------


def test_uk_ac_pre_bifurcation_returns_historical_up():
    """Uttarakhand AC in 1999: pre-bifurcation, historical UP window."""
    assert (
        historical_state_slug("IN-AC-2008-S28-1", 1999)
        == "uttar-pradesh-1947-1999"
    )


def test_uk_ac_post_bifurcation_returns_modern_uk():
    """Uttarakhand AC in 2024: modern UK."""
    assert historical_state_slug("IN-AC-2008-S28-1", 2024) == "uttarakhand"


# ---------------------------------------------------------------------------
# Bihar-Jharkhand (2000-11-15): Jharkhand pre/post
# ---------------------------------------------------------------------------


def test_jh_pc_pre_bifurcation_returns_historical_bihar():
    assert (
        historical_state_slug("IN-PC-2008-S27-1", 1999)
        == "bihar-1947-1999"
    )


def test_jh_pc_post_bifurcation_returns_modern_jh():
    assert historical_state_slug("IN-PC-2008-S27-1", 2024) == "jharkhand"


# ---------------------------------------------------------------------------
# AP-Telangana (2014-06-02): the brief's other oracle case
# ---------------------------------------------------------------------------


def test_telangana_pc_pre_bifurcation_returns_historical_ap():
    """Telangana PC in 2009: held under undivided AP (2014 carve)."""
    assert (
        historical_state_slug("IN-PC-2008-S29-3", 2009)
        == "andhra-pradesh-1956-2013"
    )


def test_telangana_pc_post_bifurcation_returns_modern_telangana():
    assert historical_state_slug("IN-PC-2008-S29-3", 2024) == "telangana"


# ---------------------------------------------------------------------------
# Goa-Daman-Diu (1987-05-30): the historical-parent (U06) branch
# ---------------------------------------------------------------------------


def test_goa_pc_pre_1987_returns_historical_gdd():
    """Modern Goa (S05) PC in 1984: still inside the pre-1987 UT."""
    assert (
        historical_state_slug("IN-PC-2008-S05-1", 1984)
        == "goa-daman-and-diu-1962-1986"
    )


def test_goa_pc_post_1987_returns_modern_goa():
    assert historical_state_slug("IN-PC-2008-S05-1", 2024) == "goa"


# ---------------------------------------------------------------------------
# Tamil Nadu (no formation event): always returns modern slug
# ---------------------------------------------------------------------------


def test_tn_ac_modern_year_returns_tamil_nadu():
    assert historical_state_slug("IN-AC-2008-S22-1", 2024) == "tamil-nadu"


def test_tn_ac_pre_1987_returns_tamil_nadu():
    """TN was never bifurcated; even 1952 returns the modern slug."""
    assert historical_state_slug("IN-AC-2008-S22-1", 1952) == "tamil-nadu"


# ---------------------------------------------------------------------------
# Parse failures
# ---------------------------------------------------------------------------


def test_parse_failure_on_malformed_entity_id():
    with pytest.raises(ValueError, match="does not match"):
        historical_state_slug("not-a-constituency", 2024)


def test_parse_failure_on_non_conforming_state_code():
    with pytest.raises(ValueError, match="non-conforming state code"):
        # 4th segment is "XYZ", not ^[SU]\d{2}$
        historical_state_slug("IN-PC-2008-XYZ-1", 2024)


# ---------------------------------------------------------------------------
# Catalogue parity (lightweight sanity)
# ---------------------------------------------------------------------------


def test_catalogue_path_exists_and_is_readable():
    """The default catalogue ships with the repo and is loadable."""
    assert DEFAULT_CATALOGUE_PATH.is_file(), (
        f"missing canonical catalogue {DEFAULT_CATALOGUE_PATH}"
    )


def test_modern_slug_table_covers_current_state_and_ut_rows():
    """One row per current state (28) + UT (8) on entities.json, plus the
    historical S09 J&K state code (mapped to the same `jammu-and-kashmir`
    slug as the post-2019 U08 UT). 37 entries today; >= 36 is the floor
    so a future spine addition does not flake this test before the table
    is updated."""
    assert len(MODERN_STATE_SLUG_BY_ECI_CODE) >= 36
