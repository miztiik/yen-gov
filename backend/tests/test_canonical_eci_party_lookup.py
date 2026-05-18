"""Contract tests for yen_gov.canonical.adapters.eci.party_lookup.

No real-corpus walks (CLAUDE.md §10) — every test seeds a tmp_path/parties.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.eci.party_lookup import (
    PartyLookup,
    UnknownPartyError,
    load_party_lookup,
)


def _write_parties(tmp: Path) -> Path:
    """Seed a tmp datasets/ root with a minimal parties.json."""
    tax = tmp / "taxonomy"
    tax.mkdir(parents=True)
    payload = {
        "$schema": "../schemas/taxonomy-parties.schema.json",
        "$schema_version": "1.0",
        "sources": [],
        "parties": [
            {
                "party_id": "parties.IN.IND",
                "short_name": "IND",
                "full_name": "Independent",
                "aliases": ["INDEPENDENT"],
                "eci_codes": [],
                "state_scope": ["IN"],
            },
            {
                "party_id": "parties.IN.NOTA",
                "short_name": "NOTA",
                "full_name": "None of the Above",
                "aliases": [],
                "eci_codes": [],
                "state_scope": ["IN"],
            },
            {
                "party_id": "parties.IN.DMK",
                "short_name": "DMK",
                "full_name": "Dravida Munnetra Kazhagam",
                "aliases": ["D.M.K."],
                "eci_codes": ["1234"],
                "state_scope": ["S22"],
            },
            {
                "party_id": "parties.IN.BJP",
                "short_name": "BJP",
                "full_name": "Bharatiya Janata Party",
                "aliases": [],
                "eci_codes": ["742"],
                "state_scope": ["IN"],
            },
        ],
    }
    (tax / "parties.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp


@pytest.fixture()
def lookup(tmp_path: Path) -> PartyLookup:
    return load_party_lookup(_write_parties(tmp_path))


class TestResolve:
    def test_nota_flag_wins(self, lookup: PartyLookup):
        assert lookup.resolve(is_nota=True) == "parties.IN.NOTA"

    def test_independent_flag(self, lookup: PartyLookup):
        assert lookup.resolve(is_independent=True) == "parties.IN.IND"

    def test_independent_flag_beats_alias(self, lookup: PartyLookup):
        # Even if a misleading short string comes in, IND flag overrides.
        assert (
            lookup.resolve(is_independent=True, party_short="BJP")
            == "parties.IN.IND"
        )

    def test_eci_code_priority_over_alias(self, lookup: PartyLookup):
        # Code points at DMK; alias "BJP" would resolve elsewhere — code wins.
        assert (
            lookup.resolve(eci_code="1234", party_short="BJP")
            == "parties.IN.DMK"
        )

    def test_short_alias_case_insensitive(self, lookup: PartyLookup):
        assert lookup.resolve(party_short="dmk") == "parties.IN.DMK"

    def test_full_alias_fallback(self, lookup: PartyLookup):
        assert (
            lookup.resolve(party_full="Bharatiya Janata Party")
            == "parties.IN.BJP"
        )

    def test_explicit_alias_resolves(self, lookup: PartyLookup):
        assert lookup.resolve(party_short="D.M.K.") == "parties.IN.DMK"

    def test_unknown_raises(self, lookup: PartyLookup):
        with pytest.raises(UnknownPartyError):
            lookup.resolve(party_short="ZZZ")

    def test_all_none_raises(self, lookup: PartyLookup):
        with pytest.raises(UnknownPartyError):
            lookup.resolve()


class TestLoad:
    def test_indexes_both_alias_and_code(self, tmp_path: Path):
        lkp = load_party_lookup(_write_parties(tmp_path))
        assert lkp.by_alias["dmk"] == "parties.IN.DMK"
        assert lkp.by_alias["d.m.k."] == "parties.IN.DMK"
        assert lkp.by_eci_code["1234"] == "parties.IN.DMK"
        assert lkp.by_eci_code["742"] == "parties.IN.BJP"
