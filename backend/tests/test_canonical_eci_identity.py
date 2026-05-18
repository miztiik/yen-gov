"""Contract tests for yen_gov.canonical.adapters.eci.identity."""

from __future__ import annotations

import pytest

from yen_gov.canonical.adapters.eci.identity import (
    Period,
    ac_entity_id,
    candidate_entity_id,
    parse_period_label,
    party_rollup_entity_id,
    state_rollup_entity_id,
)


class TestParsePeriodLabel:
    def test_acgen_decodes_year_and_month(self):
        p = parse_period_label("AcGenMay2026")
        assert p == Period(period_label="AcGenMay2026", year=2026, period_seq=5)

    def test_lsgen_april(self):
        p = parse_period_label("LsGenApr2024")
        assert p.year == 2024
        assert p.period_seq == 4

    def test_lsbye_and_acbye_supported(self):
        assert parse_period_label("LsByeJan2021").period_seq == 1
        assert parse_period_label("AcByeDec2019").period_seq == 12

    @pytest.mark.parametrize(
        "bad",
        ["", "GenMay2026", "AcGen2026", "AcGenMay26", "AcGenMAY2026", "AcGenMay20260"],
    )
    def test_rejects_malformed(self, bad: str):
        with pytest.raises(ValueError):
            parse_period_label(bad)


class TestAcEntityId:
    def test_canonical_form(self):
        assert ac_entity_id("S22", 2008, 167) == "IN-S22-AC-2008-167"

    def test_ut_supported(self):
        assert ac_entity_id("U07", 2008, 70) == "IN-U07-AC-2008-70"

    @pytest.mark.parametrize("bad", ["s22", "S2", "SS22", "22", "S222"])
    def test_rejects_bad_state(self, bad: str):
        with pytest.raises(ValueError):
            ac_entity_id(bad, 2008, 1)

    def test_rejects_bad_delim_year(self):
        with pytest.raises(ValueError):
            ac_entity_id("S22", 1500, 1)
        with pytest.raises(ValueError):
            ac_entity_id("S22", 2200, 1)

    def test_rejects_nonpositive_eci_no(self):
        with pytest.raises(ValueError):
            ac_entity_id("S22", 2008, 0)


class TestCandidateEntityId:
    def test_zero_padded_serial(self):
        cid = candidate_entity_id("IN-S22-AC-2008-167", "AcGenMay2026", 3)
        assert cid == "IN-S22-AC-2008-167-AcGenMay2026-C03"

    def test_two_digit_serial(self):
        cid = candidate_entity_id("IN-S22-AC-2008-167", "AcGenMay2026", 27)
        assert cid.endswith("-C27")

    @pytest.mark.parametrize("bad", [0, -1, 100, 999])
    def test_rejects_out_of_range_serial(self, bad: int):
        with pytest.raises(ValueError):
            candidate_entity_id("IN-S22-AC-2008-167", "AcGenMay2026", bad)


class TestStateRollupEntityId:
    def test_canonical(self):
        assert state_rollup_entity_id("S22", "AcGenMay2026") == "IN-S22-AcGenMay2026"

    def test_rejects_bad_state(self):
        with pytest.raises(ValueError):
            state_rollup_entity_id("XX", "AcGenMay2026")


class TestPartyRollupEntityId:
    def test_canonical(self):
        assert (
            party_rollup_entity_id("S22", "AcGenMay2026", "DMK")
            == "IN-S22-AcGenMay2026-PARTY-DMK"
        )

    def test_allows_digits_and_underscore(self):
        # Pattern is [A-Z][A-Z0-9_]*
        assert party_rollup_entity_id("S22", "AcGenMay2026", "AIADMK_M") .endswith(
            "PARTY-AIADMK_M"
        )

    @pytest.mark.parametrize("bad", ["dmk", "DMK-X", "1DMK", "", "D MK"])
    def test_rejects_bad_slug(self, bad: str):
        with pytest.raises(ValueError):
            party_rollup_entity_id("S22", "AcGenMay2026", bad)
