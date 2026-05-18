"""Unit tests for dim_rows_from_constituency + PartyLookup.registry().

Sub-phase 1.2b — proves the adapter emits the denormalised strings citizen
view-models need (candidate name, AC name, party labels), and that the PKs it
produces are byte-equal to the per-contest entity_ids the observations adapter
already emits. JOINing on those PKs is what unblocks the route swap (PR-E).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.eci.identity import (
    Period,
    ac_entity_id,
    candidate_entity_id,
)
from yen_gov.canonical.adapters.eci.observations import (
    dim_rows_from_constituency,
    observations_from_constituency,
)
from yen_gov.canonical.adapters.eci.party_lookup import (
    load_party_lookup,
    party_dim_rows,
)
from yen_gov.core.models import (
    CandidateResult,
    ConstituencyResult,
    NotaResult,
    ResultTotals,
    SourceRef,
    WinnerInfo,
)


SOURCE = "src-abc12345"


def _write_parties(tmp: Path) -> Path:
    tax = tmp / "taxonomy"
    tax.mkdir(parents=True)
    payload = {
        "$schema": "../schemas/taxonomy-parties.schema.json",
        "$schema_version": "1.0",
        "sources": [],
        "parties": [
            {"party_id": "parties.IN.IND", "short_name": "IND",
             "full_name": "Independent", "aliases": [], "eci_codes": [],
             "state_scope": ["IN"]},
            {"party_id": "parties.IN.DMK", "short_name": "DMK",
             "full_name": "Dravida Munnetra Kazhagam", "aliases": [],
             "eci_codes": ["1234"], "state_scope": ["S22"],
             "recognition": "state"},
            {"party_id": "parties.IN.BJP", "short_name": "BJP",
             "full_name": "Bharatiya Janata Party", "aliases": [],
             "eci_codes": ["742"], "state_scope": ["IN"],
             "recognition": "national"},
        ],
    }
    (tax / "parties.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp


def _result() -> ConstituencyResult:
    cands = [
        CandidateResult(
            rank=1, name="A. Alpha", party_short="DMK", party_eci_code="1234",
            votes=60_000, vote_share_pct=60.0,
        ),
        CandidateResult(
            rank=2, name="B. Bravo", party_short="BJP", party_eci_code="742",
            votes=30_000, vote_share_pct=30.0,
        ),
        CandidateResult(
            rank=3, name="C. Charlie", party_short="IND",
            votes=9_200, vote_share_pct=9.2,
        ),
    ]
    return ConstituencyResult(
        sources=[SourceRef(url="https://example/eci/page",
                           fetched_at=datetime(2026, 5, 1, tzinfo=timezone.utc))],
        election="AcGenMay2026",
        state="S22",
        body="AC",
        eci_no=167,
        constituency_name="Mylapore",
        totals=ResultTotals(electors=100_000, votes_polled=100_000, turnout_pct=100.0),
        candidates=cands,
        nota=NotaResult(votes=800, vote_share_pct=0.8),
        top_n_cutoff=5,
        winner=WinnerInfo(
            name="A. Alpha", party_short="DMK", party_eci_code="1234",
            votes=60_000, margin_votes=30_000, margin_pct=30.0,
        ),
    )


@pytest.fixture()
def lookup(tmp_path: Path):
    return load_party_lookup(_write_parties(tmp_path))


@pytest.fixture()
def period():
    return Period("AcGenMay2026", 2026, 5)


class TestCandidateDims:
    def test_one_row_per_candidate(self, lookup, period):
        dims = dim_rows_from_constituency(
            result=_result(), period=period, delim_year=2008,
            party_lookup=lookup, source_id=SOURCE,
        )
        assert len(dims["candidate"]) == 3

    def test_candidate_pk_matches_observations_entity_id(self, lookup, period):
        """The JOIN that unblocks PR-E rides on this equality."""
        dims = dim_rows_from_constituency(
            result=_result(), period=period, delim_year=2008,
            party_lookup=lookup, source_id=SOURCE,
        )
        obs = observations_from_constituency(
            result=_result(), period=period, delim_year=2008,
            party_lookup=lookup, source_id=SOURCE,
        )
        cand_pks = {d["candidate_id"] for d in dims["candidate"]}
        obs_entity_ids = {
            r.entity_id for r in obs if r.indicator_id == "candidate-votes-polled"
        }
        assert cand_pks == obs_entity_ids

    def test_candidate_carries_name_party_rank(self, lookup, period):
        dims = dim_rows_from_constituency(
            result=_result(), period=period, delim_year=2008,
            party_lookup=lookup, source_id=SOURCE,
        )
        rows = sorted(dims["candidate"], key=lambda r: r["rank"])
        assert rows[0]["name"] == "A. Alpha"
        assert rows[0]["party_id"] == "parties.IN.DMK"
        assert rows[0]["rank"] == 1
        assert rows[0]["ballot_serial"] == 1
        assert rows[2]["party_id"] == "parties.IN.IND"

    def test_every_dim_carries_source_id(self, lookup, period):
        dims = dim_rows_from_constituency(
            result=_result(), period=period, delim_year=2008,
            party_lookup=lookup, source_id=SOURCE,
        )
        assert all(r["source_id"] == SOURCE for r in dims["candidate"])
        assert all(r["source_id"] == SOURCE for r in dims["ac"])


class TestAcDim:
    def test_one_ac_row(self, lookup, period):
        dims = dim_rows_from_constituency(
            result=_result(), period=period, delim_year=2008,
            party_lookup=lookup, source_id=SOURCE,
        )
        assert len(dims["ac"]) == 1
        row = dims["ac"][0]
        assert row["ac_id"] == ac_entity_id("S22", 2008, 167)
        assert row["state_code"] == "S22"
        assert row["delim_year"] == 2008
        assert row["eci_no"] == 167
        assert row["name"] == "Mylapore"


class TestPartyRegistry:
    def test_party_dim_rows_one_per_party(self, lookup):
        rows = party_dim_rows(lookup, source_id=SOURCE)
        pids = {r["party_id"] for r in rows}
        assert pids == {"parties.IN.IND", "parties.IN.DMK", "parties.IN.BJP"}

    def test_party_dim_carries_full_name_and_recognition(self, lookup):
        rows = party_dim_rows(lookup, source_id=SOURCE)
        by_id = {r["party_id"]: r for r in rows}
        assert by_id["parties.IN.DMK"]["full_name"] == "Dravida Munnetra Kazhagam"
        assert by_id["parties.IN.DMK"]["short_name"] == "DMK"
        assert by_id["parties.IN.DMK"]["recognition"] == "state"
        assert by_id["parties.IN.DMK"]["eci_code"] == "1234"
        assert by_id["parties.IN.IND"]["eci_code"] is None
