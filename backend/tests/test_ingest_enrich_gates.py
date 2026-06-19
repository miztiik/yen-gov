"""Unit tests for the six India-discontinuity ENRICH gates (Row 6).

Each gate RAISES a typed error on bad input and passes on good input -- the
Row-6 gate requirement. Pure functions, no corpus walk, no fixtures on disk.
"""
from __future__ import annotations

import pytest

from yen_gov.canonical.ingest.enrich_gates import (
    BifurcationError,
    CodeAuthorityError,
    EntityObservation,
    EntityResolution,
    EstimateStatusError,
    FiscalCalendarError,
    PriceBasisError,
    PublisherBoundedUniverseError,
    check_bifurcation,
    check_code_authority,
    check_estimate_status,
    check_fiscal_calendar,
    check_price_basis,
    check_publisher_bounded_universe,
    fiscal_year_start,
)
from yen_gov.canonical.ingest.spec import PriceBasis


# --------------------------------------------------------------------------- #
# (1) bifurcation
# --------------------------------------------------------------------------- #


class TestBifurcation:
    def test_andhra_pradesh_is_id_reuse_valid_either_side_of_2014(self):
        # IN-S01 stays valid across the 2014 split (the plan's id-REUSE rule).
        check_bifurcation(
            [
                EntityObservation(entity_id="andhra-pradesh", time=2010),
                EntityObservation(entity_id="andhra-pradesh", time=2016),
            ]
        )

    def test_pre_2014_telangana_row_fails(self):
        with pytest.raises(BifurcationError):
            check_bifurcation([EntityObservation(entity_id="telangana", time=2010)])

    def test_post_2014_telangana_row_passes(self):
        check_bifurcation([EntityObservation(entity_id="telangana", time=2016)])

    def test_post_2019_jk_state_row_fails(self):
        with pytest.raises(BifurcationError):
            check_bifurcation(
                [
                    EntityObservation(
                        entity_id="jammu-and-kashmir", time=2021, entity_kind="state"
                    )
                ]
            )

    def test_jk_as_union_territory_after_2019_passes(self):
        check_bifurcation(
            [
                EntityObservation(
                    entity_id="jammu-and-kashmir",
                    time=2021,
                    entity_kind="union_territory",
                )
            ]
        )

    def test_jk_state_before_2019_passes(self):
        check_bifurcation(
            [
                EntityObservation(
                    entity_id="jammu-and-kashmir", time=2018, entity_kind="state"
                )
            ]
        )

    def test_pre_2019_ladakh_fails_post_passes(self):
        with pytest.raises(BifurcationError):
            check_bifurcation([EntityObservation(entity_id="ladakh", time=2018)])
        check_bifurcation([EntityObservation(entity_id="ladakh", time=2020)])

    def test_force_tag_permits_an_otherwise_illegal_row(self):
        check_bifurcation(
            [EntityObservation(entity_id="telangana", time=2010)],
            force_tagged=[("telangana", 2010)],
        )


# --------------------------------------------------------------------------- #
# (2) code-authority
# --------------------------------------------------------------------------- #


class TestCodeAuthority:
    def test_single_unambiguous_resolution_passes(self):
        check_code_authority(
            [
                EntityResolution(
                    raw_label="Kerala",
                    resolved_entity_id="kerala",
                    candidates=("kerala",),
                    authority="lgd",
                )
            ]
        )

    def test_unmapped_label_fails(self):
        with pytest.raises(CodeAuthorityError):
            check_code_authority(
                [
                    EntityResolution(
                        raw_label="Atlantis",
                        resolved_entity_id=None,
                        candidates=(),
                        authority="lgd",
                    )
                ]
            )

    def test_ambiguous_label_fails(self):
        with pytest.raises(CodeAuthorityError):
            check_code_authority(
                [
                    EntityResolution(
                        raw_label="Aurangabad",
                        resolved_entity_id="aurangabad-mh",
                        candidates=("aurangabad-mh", "aurangabad-bihar"),
                        authority="lgd",
                    )
                ]
            )

    def test_unknown_authority_fails(self):
        with pytest.raises(CodeAuthorityError):
            check_code_authority(
                [
                    EntityResolution(
                        raw_label="Kerala",
                        resolved_entity_id="kerala",
                        candidates=("kerala",),
                        authority="wikipedia",
                    )
                ]
            )

    def test_resolution_outside_candidate_set_fails(self):
        with pytest.raises(CodeAuthorityError):
            check_code_authority(
                [
                    EntityResolution(
                        raw_label="Kerala",
                        resolved_entity_id="goa",
                        candidates=("kerala",),
                        authority="census",
                    )
                ]
            )


# --------------------------------------------------------------------------- #
# (3) fiscal-year != calendar-year
# --------------------------------------------------------------------------- #


class TestFiscalCalendar:
    def test_fiscal_span_anchors_to_start_year(self):
        check_fiscal_calendar("2015-16", 2015, basis="fiscal_year_start")
        check_fiscal_calendar("2015-2016", 2015, basis="fiscal_year_start")

    def test_fiscal_span_anchored_to_end_year_fails(self):
        with pytest.raises(FiscalCalendarError):
            check_fiscal_calendar("2015-16", 2016, basis="fiscal_year_start")

    def test_bare_year_is_not_a_fiscal_span(self):
        with pytest.raises(FiscalCalendarError):
            check_fiscal_calendar("2015", 2015, basis="fiscal_year_start")

    def test_calendar_basis_with_fiscal_label_fails(self):
        with pytest.raises(FiscalCalendarError):
            check_fiscal_calendar("2015-16", 2015, basis="calendar_year")

    def test_calendar_basis_matches_year(self):
        check_fiscal_calendar("2015", 2015, basis="calendar_year")
        with pytest.raises(FiscalCalendarError):
            check_fiscal_calendar("2015", 2016, basis="calendar_year")

    def test_non_consecutive_span_fails(self):
        with pytest.raises(FiscalCalendarError):
            fiscal_year_start("2015-17")

    def test_unknown_basis_fails(self):
        with pytest.raises(FiscalCalendarError):
            check_fiscal_calendar("2015", 2015, basis="lunar")


# --------------------------------------------------------------------------- #
# (4) provisional-vs-revised
# --------------------------------------------------------------------------- #


class TestEstimateStatus:
    def test_downgrade_final_to_provisional_fails(self):
        with pytest.raises(EstimateStatusError):
            check_estimate_status("provisional", "final")

    def test_upgrade_provisional_to_final_passes(self):
        check_estimate_status("final", "provisional")

    def test_no_incumbent_passes(self):
        check_estimate_status("provisional", None)

    def test_same_rank_passes(self):
        check_estimate_status("revised", "mixed")

    def test_unknown_status_fails(self):
        with pytest.raises(EstimateStatusError):
            check_estimate_status("guess", "final")
        with pytest.raises(EstimateStatusError):
            check_estimate_status("final", "guess")


# --------------------------------------------------------------------------- #
# (5) price-basis
# --------------------------------------------------------------------------- #


class TestPriceBasis:
    def test_matching_current_basis_passes(self):
        check_price_basis(PriceBasis(basis="current"), PriceBasis(basis="current"))

    def test_constant_into_current_fails(self):
        with pytest.raises(PriceBasisError):
            check_price_basis(
                PriceBasis(basis="constant", base_year=2011),
                PriceBasis(basis="current"),
            )

    def test_non_monetary_none_pair_passes(self):
        check_price_basis(None, None)

    def test_constant_base_year_mismatch_fails(self):
        with pytest.raises(PriceBasisError):
            check_price_basis(
                PriceBasis(basis="constant", base_year=2011),
                PriceBasis(basis="constant", base_year=2004),
            )


# --------------------------------------------------------------------------- #
# (6) publisher-bounded-universe
# --------------------------------------------------------------------------- #


class TestPublisherBoundedUniverse:
    def test_open_universe_is_a_noop(self):
        check_publisher_bounded_universe(
            ["kerala", "made-up-state"], allowed_entities=None
        )

    def test_entity_inside_universe_passes(self):
        check_publisher_bounded_universe(
            ["kerala", "goa"], allowed_entities=["kerala", "goa", "bihar"]
        )

    def test_phantom_entity_fails(self):
        with pytest.raises(PublisherBoundedUniverseError):
            check_publisher_bounded_universe(
                ["kerala", "atlantis"], allowed_entities=["kerala", "goa"]
            )
