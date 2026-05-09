"""Tests for core.models — Pydantic v2 mirrors of datasets/schemas/.

Each top-level model is round-tripped through core.io.write_artifact +
the real schema file to confirm the model produces a payload that the schema
validator accepts. This is the contract: model in, validated artifact out.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from yen_gov.core.io import write_artifact
from yen_gov.core.models import (
    AllianceDistribution,
    CandidateResult,
    ConstituenciesCollection,
    ConstituencyEntry,
    ConstituencyResult,
    DistrictEntry,
    DistrictsCollection,
    Election,
    FetchKnobs,
    NotaResult,
    OthersBucket,
    PartiesSnapshot,
    PartyEntry,
    PartyTotals,
    ProcessingConfig,
    ResultSummary,
    ResultsKnobs,
    ResultTotals,
    SourceRef,
    StateEntry,
    StatesCollection,
    SummaryTotals,
    WinnerInfo,
)

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "datasets" / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _round_trip(tmp_path: Path, model, schema_name: str) -> dict:
    schema = _load_schema(schema_name)
    target = tmp_path / "out.json"
    write_artifact(
        path=target,
        schema_id=model._schema_id,
        schema_version=model._schema_version,
        payload=model.body_payload(),
        sources=model.sources_payload(),
        schema_for_validation=schema,
    )
    return json.loads(target.read_text(encoding="utf-8"))


# --- SourceRef --------------------------------------------------------------

def test_sourceref_rejects_naive_timestamp():
    with pytest.raises(ValidationError, match="timezone-aware"):
        SourceRef(url="https://x/y", fetched_at=datetime(2026, 5, 8, 14, 0))


def test_sourceref_rejects_non_http():
    with pytest.raises(ValidationError):
        SourceRef(url="ftp://x/y", fetched_at=datetime(2026, 5, 8, tzinfo=timezone.utc))


# --- Election ---------------------------------------------------------------

def test_election_round_trip(tmp_path: Path):
    m = Election(
        sources=[],
        eci_event_id="AcGenMay2026",
        scope="state",
        body="AC",
        year=2026,
        month=5,
        states=["S22"],
    )
    out = _round_trip(tmp_path, m, "election.schema.json")
    assert out["eci_event_id"] == "AcGenMay2026"
    assert out["sources"] == []


def test_election_rejects_bad_state_code():
    with pytest.raises(ValidationError):
        Election(
            sources=[], eci_event_id="x", scope="state", body="AC",
            year=2026, states=["XX22"],
        )


# --- StatesCollection -------------------------------------------------------

def test_states_collection_round_trip(tmp_path: Path):
    m = StatesCollection(
        sources=[SourceRef(
            url="https://en.wikipedia.org/wiki/States_and_union_territories_of_India",
            fetched_at=datetime(2026, 5, 8, 14, 0, tzinfo=timezone.utc),
        )],
        country="IN",
        states=[StateEntry(eci_code="S22", iso_3166_2="IN-TN", name="Tamil Nadu", kind="state")],
    )
    out = _round_trip(tmp_path, m, "state.schema.json")
    assert out["country"] == "IN"
    assert out["states"][0]["eci_code"] == "S22"
    assert out["sources"][0]["fetched_at"].endswith("Z")


# --- DistrictsCollection ---------------------------------------------------

def test_districts_collection_round_trip(tmp_path: Path):
    m = DistrictsCollection(
        sources=[],
        state="S22",
        districts=[DistrictEntry(id="603", id_source="lgd", name="Chennai")],
    )
    out = _round_trip(tmp_path, m, "district.schema.json")
    assert out["state"] == "S22"
    assert "headquarters" not in out["districts"][0]  # exclude_none works


# --- ConstituenciesCollection ----------------------------------------------

def test_constituencies_round_trip(tmp_path: Path):
    m = ConstituenciesCollection(
        sources=[],
        state="S22",
        body="AC",
        status="provisional",
        constituencies=[ConstituencyEntry(eci_no=1, name="Gummidipoondi", reservation="GEN")],
    )
    out = _round_trip(tmp_path, m, "constituency.schema.json")
    assert out["constituencies"][0]["eci_no"] == 1
    assert out["status"] == "provisional"


# --- PartiesSnapshot --------------------------------------------------------

def test_parties_round_trip(tmp_path: Path):
    m = PartiesSnapshot(
        sources=[],
        election="AcGenMay2026",
        parties=[PartyEntry(eci_code="803", short_name="DMK", full_name="Dravida Munnetra Kazhagam")],
    )
    out = _round_trip(tmp_path, m, "party.schema.json")
    assert out["parties"][0]["short_name"] == "DMK"


def test_party_rejects_non_numeric_eci_code():
    with pytest.raises(ValidationError):
        PartyEntry(eci_code="DMK", short_name="DMK", full_name="x")


# --- ConstituencyResult -----------------------------------------------------

def test_constituency_result_with_others_bucket(tmp_path: Path):
    m = ConstituencyResult(
        sources=[SourceRef(
            url="https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22167.htm",
            fetched_at=datetime(2026, 5, 8, 14, 30, tzinfo=timezone.utc),
        )],
        election="AcGenMay2026", state="S22", body="AC", eci_no=167,
        totals=ResultTotals(electors=300000, votes_polled=210000, turnout_pct=70.0),
        candidates=[CandidateResult(
            rank=1, name="A", party_eci_code="803", party_short="DMK",
            votes=100000, vote_share_pct=47.6, is_winner=True,
        )],
        nota=NotaResult(votes=2000, vote_share_pct=0.95),
        others=OthersBucket(candidate_count=8, votes=15000, vote_share_pct=7.1),
        top_n_cutoff=5,
        winner=WinnerInfo(
            name="A", party_eci_code="803", party_short="DMK",
            votes=100000, margin_votes=20000, margin_pct=9.5,
        ),
    )
    out = _round_trip(tmp_path, m, "result.constituency.schema.json")
    assert out["others"]["candidate_count"] == 8


def test_constituency_result_without_others_keeps_null(tmp_path: Path):
    """`others` is required AND nullable — model must emit null when absent."""
    m = ConstituencyResult(
        sources=[],
        election="AcGenMay2026", state="S22", body="AC", eci_no=1,
        totals=ResultTotals(votes_polled=100),
        candidates=[CandidateResult(
            rank=1, name="A", party_short="IND", votes=100, vote_share_pct=100.0,
        )],
        nota=NotaResult(votes=0, vote_share_pct=0.0),
        top_n_cutoff=5,
        winner=WinnerInfo(name="A", party_short="IND", votes=100, margin_votes=100, margin_pct=100.0),
    )
    out = _round_trip(tmp_path, m, "result.constituency.schema.json")
    assert out["others"] is None  # explicit null, not omitted


# --- ResultSummary ---------------------------------------------------------

def test_result_summary_round_trip(tmp_path: Path):
    m = ResultSummary(
        sources=[],
        election="AcGenMay2026", state="S22", body="AC",
        total_seats=234,
        totals=SummaryTotals(electors=60_000_000, votes_polled=42_000_000, turnout_pct=70.0),
        party_totals=[PartyTotals(party_eci_code="803", party_short="DMK", seats_won=130, votes=20_000_000, vote_share_pct=47.6)],
        alliance_distribution=[AllianceDistribution(alliance="SPA", seats_won=160, vote_share_pct=55.0)],
    )
    out = _round_trip(tmp_path, m, "result.summary.schema.json")
    assert out["total_seats"] == 234
    assert out["alliance_distribution"][0]["alliance"] == "SPA"


# --- ProcessingConfig ------------------------------------------------------

def test_processing_config_round_trip(tmp_path: Path):
    m = ProcessingConfig(
        sources=[],
        fetch=FetchKnobs(concurrency=4, retry_attempts=3, timeout_seconds=30.0, user_agent="yen-gov/0.0"),
        results=ResultsKnobs(top_n_candidates=5, collapse_others=True),
    )
    out = _round_trip(tmp_path, m, "processing.schema.json")
    assert out["fetch"]["concurrency"] == 4
    assert out["sources"] == []


def test_processing_rejects_concurrency_above_max():
    with pytest.raises(ValidationError):
        FetchKnobs(concurrency=99, retry_attempts=0, timeout_seconds=1.0, user_agent="x")
