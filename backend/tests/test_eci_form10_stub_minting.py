"""Tier-A contract test for the ECI Form 10 writer's electoral.csv stub-minting.

Verifies the structural fix landed in PR R1 (2026-06-15) per the Hans + Max +
Fowler persona-debate verdict. The writer auto-mints stub
``IN-AC-2008-<state>-eci<N>`` rows in electoral.csv when the XLSX carries
an AC NO. that has no matching row for (state, delim_year=2008).

Tests are pure-function level (no XLSX I/O) for speed + reviewability.
The full end-to-end smoke (288 ACs landing) is verified by the operator
running ``python -m yen_gov ingest-eci-ae-form10 --root .`` and the
existing form10 + assembly_results pytest suite.
"""

from __future__ import annotations

from yen_gov.canonical.adapters.eci_form10_ae import (
    _mint_stub_entities,
)


def _by_ac(entries: list[tuple[int, str]]) -> dict[int, list[dict]]:
    """Helper: shape the test fixture into _ingest_one's by_ac dict."""
    return {
        eci_no: [{"publisher_ac_name": name}]
        for eci_no, name in entries
    }


class TestStubMintingShape:
    """Verify _mint_stub_entities() output shape matches electoral.csv schema."""

    def test_mints_general_seat(self) -> None:
        stubs = _mint_stub_entities(
            missing_eci_nos=[107],
            by_ac=_by_ac([(107, "AURANGABAD CENTRAL")]),
            state_slug="maharashtra",
            delim_year="2008",
        )
        assert len(stubs) == 1
        s = stubs[0]
        assert s["entity_id"] == "IN-AC-2008-maharashtra-eci107"
        assert s["name"] == "AURANGABAD CENTRAL"
        assert s["entity_kind"] == "ac"
        assert s["delim_year"] == "2008"
        assert s["state"] == "maharashtra"
        assert s["parent"] == ""
        assert s["eci_no"] == "107"
        assert s["aliases"] == ""
        assert s["reservation"] == "GEN"

    def test_strips_sc_suffix_and_sets_reservation(self) -> None:
        stubs = _mint_stub_entities(
            missing_eci_nos=[178],
            by_ac=_by_ac([(178, "DHARAVI (SC)")]),
            state_slug="maharashtra",
            delim_year="2008",
        )
        assert stubs[0]["name"] == "DHARAVI"
        assert stubs[0]["reservation"] == "SC"

    def test_strips_st_suffix_and_sets_reservation(self) -> None:
        stubs = _mint_stub_entities(
            missing_eci_nos=[42],
            by_ac=_by_ac([(42, "FAKE ST AC (ST)")]),
            state_slug="madhya-pradesh",
            delim_year="2008",
        )
        assert stubs[0]["name"] == "FAKE ST AC"
        assert stubs[0]["reservation"] == "ST"

    def test_lowercase_reservation_suffix_still_works(self) -> None:
        """The (SC)/(ST) regex is case-insensitive."""
        stubs = _mint_stub_entities(
            missing_eci_nos=[1],
            by_ac=_by_ac([(1, "Some Constituency (sc)")]),
            state_slug="test",
            delim_year="2008",
        )
        assert stubs[0]["name"] == "Some Constituency"
        assert stubs[0]["reservation"] == "SC"

    def test_no_paren_suffix_yields_GEN(self) -> None:
        stubs = _mint_stub_entities(
            missing_eci_nos=[5],
            by_ac=_by_ac([(5, "PLAIN NAME")]),
            state_slug="test",
            delim_year="2008",
        )
        assert stubs[0]["reservation"] == "GEN"
        assert stubs[0]["name"] == "PLAIN NAME"

    def test_empty_missing_list_returns_empty(self) -> None:
        stubs = _mint_stub_entities(
            missing_eci_nos=[],
            by_ac={},
            state_slug="test",
            delim_year="2008",
        )
        assert stubs == []

    def test_multiple_stubs_sorted_by_eci_no(self) -> None:
        """Stub list returned sorted ascending so the on-disk append order
        is deterministic across runs."""
        stubs = _mint_stub_entities(
            missing_eci_nos=[182, 7, 107],  # intentionally out of order
            by_ac=_by_ac([(7, "DHULE CITY"), (107, "AURANGABAD CENTRAL"), (182, "WORLI")]),
            state_slug="maharashtra",
            delim_year="2008",
        )
        assert [s["eci_no"] for s in stubs] == ["7", "107", "182"]
        assert [s["name"] for s in stubs] == ["DHULE CITY", "AURANGABAD CENTRAL", "WORLI"]

    def test_eci_no_with_no_xlsx_row_is_skipped(self) -> None:
        """Defensive: if missing_eci_nos contains an eci_no with no by_ac
        entry, skip it rather than crashing."""
        stubs = _mint_stub_entities(
            missing_eci_nos=[107, 999],  # 999 not in by_ac
            by_ac=_by_ac([(107, "AURANGABAD CENTRAL")]),
            state_slug="maharashtra",
            delim_year="2008",
        )
        assert len(stubs) == 1
        assert stubs[0]["eci_no"] == "107"

    def test_state_slug_and_delim_propagate(self) -> None:
        """Verifies the entity_id template uses both parameters correctly."""
        stubs = _mint_stub_entities(
            missing_eci_nos=[13],
            by_ac=_by_ac([(13, "JALGAON CITY")]),
            state_slug="jammu-and-kashmir",
            delim_year="2019",
        )
        assert stubs[0]["entity_id"] == "IN-AC-2019-jammu-and-kashmir-eci13"
        assert stubs[0]["state"] == "jammu-and-kashmir"
        assert stubs[0]["delim_year"] == "2019"


class TestStubMintingMatchesProductionConvention:
    """Verify the eci<N>-stub format matches the convention already in
    production at electoral.csv for AP/Assam/Karnataka rows."""

    def test_matches_andhra_pradesh_eci107_shape(self) -> None:
        """The pre-existing IN-AC-2008-andhra-pradesh-eci107 row (electoral.csv
        line ~184) carries name='SANTHANUTHALAPADU', reservation='SC',
        parent=''. Our stub-minter must produce a structurally identical
        row when given the same inputs."""
        stubs = _mint_stub_entities(
            missing_eci_nos=[107],
            by_ac=_by_ac([(107, "SANTHANUTHALAPADU (SC)")]),
            state_slug="andhra-pradesh",
            delim_year="2008",
        )
        s = stubs[0]
        assert s["entity_id"] == "IN-AC-2008-andhra-pradesh-eci107"
        assert s["name"] == "SANTHANUTHALAPADU"
        assert s["entity_kind"] == "ac"
        assert s["delim_year"] == "2008"
        assert s["state"] == "andhra-pradesh"
        assert s["parent"] == ""
        assert s["eci_no"] == "107"
        assert s["aliases"] == ""
        assert s["reservation"] == "SC"
