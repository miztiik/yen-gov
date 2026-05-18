"""Contract tests for yen_gov.canonical.adapters.eci.observations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.eci.identity import Period
from yen_gov.canonical.adapters.eci.observations import (
    observations_from_constituency,
)
from yen_gov.canonical.adapters.eci.party_lookup import load_party_lookup
from yen_gov.core.models import (
    CandidateResult,
    ConstituencyResult,
    NotaResult,
    ResultTotals,
    SourceRef,
    WinnerInfo,
)

import json


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
            {"party_id": "parties.IN.NOTA", "short_name": "NOTA",
             "full_name": "None of the Above", "aliases": [], "eci_codes": [],
             "state_scope": ["IN"]},
            {"party_id": "parties.IN.DMK", "short_name": "DMK",
             "full_name": "Dravida Munnetra Kazhagam", "aliases": [],
             "eci_codes": ["1234"], "state_scope": ["S22"]},
            {"party_id": "parties.IN.BJP", "short_name": "BJP",
             "full_name": "Bharatiya Janata Party", "aliases": [],
             "eci_codes": ["742"], "state_scope": ["IN"]},
        ],
    }
    (tax / "parties.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp


SOURCE = "src-abc12345"


def _result(
    *,
    nota_votes: int = 800,
    nota_pct: float = 0.8,
    electors: int | None = 100_000,
) -> ConstituencyResult:
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
        totals=ResultTotals(electors=electors, votes_polled=100_000, turnout_pct=100.0),
        candidates=cands,
        nota=NotaResult(votes=nota_votes, vote_share_pct=nota_pct),
        top_n_cutoff=5,
        winner=WinnerInfo(
            name="A. Alpha", party_short="DMK", party_eci_code="1234",
            votes=60_000, margin_votes=30_000, margin_pct=30.0,
        ),
    )


@pytest.fixture()
def lookup(tmp_path: Path):
    return load_party_lookup(_write_parties(tmp_path))


def _by_indicator(rows, ind: str):
    return [r for r in rows if r.indicator_id == ind]


class TestObservationsFromConstituency:
    def test_emits_candidate_rows_for_every_candidate(self, lookup):
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        assert len(_by_indicator(rows, "candidate-votes-polled")) == 3
        assert len(_by_indicator(rows, "candidate-vote-share-pct")) == 3
        assert len(_by_indicator(rows, "candidate-rank")) == 3

    def test_candidate_entity_id_per_contest(self, lookup):
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        ids = {r.entity_id for r in _by_indicator(rows, "candidate-votes-polled")}
        assert ids == {
            "IN-S22-AC-2008-167-AcGenMay2026-C01",
            "IN-S22-AC-2008-167-AcGenMay2026-C02",
            "IN-S22-AC-2008-167-AcGenMay2026-C03",
        }

    def test_ac_winner_party_id_resolves(self, lookup):
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        [r] = _by_indicator(rows, "ac-winner-party-id")
        assert r.value_text == "parties.IN.DMK"
        assert r.value_numeric is None

    def test_ac_winner_candidate_id_derives_from_rank_1(self, lookup):
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        [r] = _by_indicator(rows, "ac-winner-candidate-id")
        assert r.value_text.endswith("-C01")

    def test_independent_winner_routes_to_ind(self, lookup):
        r = _result()
        r = r.model_copy(update={
            "winner": WinnerInfo(
                name="C. Charlie", party_short="IND",
                votes=9_200, margin_votes=1, margin_pct=0.01,
            )
        })
        rows = observations_from_constituency(
            result=r, period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        [w] = _by_indicator(rows, "ac-winner-party-id")
        assert w.value_text == "parties.IN.IND"

    def test_nota_null_pre_2013(self, lookup):
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenApr2011", 2011, 4),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        assert _by_indicator(rows, "ac-nota-votes") == []
        assert _by_indicator(rows, "ac-nota-pct") == []

    def test_nota_present_post_2013(self, lookup):
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        [v] = _by_indicator(rows, "ac-nota-votes")
        assert v.value_numeric == 800.0
        assert v.derivation == "raw"

    def test_ac_total_electors_omitted_when_null(self, lookup):
        rows = observations_from_constituency(
            result=_result(electors=None),
            period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        assert _by_indicator(rows, "ac-total-electors") == []
        assert _by_indicator(rows, "ac-turnout-pct") == []

    def test_margin_votes_and_pct(self, lookup):
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        [mv] = _by_indicator(rows, "ac-margin-votes")
        [mp] = _by_indicator(rows, "ac-margin-pct")
        assert mv.value_numeric == 30_000.0
        assert mp.value_numeric == pytest.approx(30.0)

    def test_effective_candidates_laakso(self, lookup):
        # shares: 0.60, 0.30, 0.092, 0.008 (NOTA) -> ssq = 0.36+0.09+0.008464+0.000064
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        [r] = _by_indicator(rows, "ac-effective-candidates-laakso")
        ssq = 0.6**2 + 0.3**2 + 0.092**2 + 0.008**2
        assert r.value_numeric == pytest.approx(1.0 / ssq, rel=1e-9)
        assert r.derivation == "laakso_taagepera"

    def test_every_row_carries_source_id(self, lookup):
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        assert all(r.source_id == SOURCE for r in rows)
        assert all(r.period_label == "AcGenMay2026" for r in rows)
        assert all(r.year == 2026 for r in rows)

    def test_candidates_total_equals_kept_when_no_others(self, lookup):
        # Phase 1.6: field-size disclosure. With no `others` bucket the total
        # equals the number of CandidateResult rows on the artifact.
        rows = observations_from_constituency(
            result=_result(), period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        [r] = _by_indicator(rows, "ac-candidates-total")
        assert r.value_numeric == 3.0
        assert _by_indicator(rows, "ac-others-votes") == []
        assert _by_indicator(rows, "ac-others-pct") == []

    def test_candidates_total_includes_others_bucket(self, lookup):
        from yen_gov.core.models import OthersBucket
        r = _result().model_copy(update={
            "others": OthersBucket(candidate_count=7, votes=4_000, vote_share_pct=4.0),
        })
        rows = observations_from_constituency(
            result=r, period=Period("AcGenMay2026", 2026, 5),
            delim_year=2008, party_lookup=lookup, source_id=SOURCE,
        )
        [total] = _by_indicator(rows, "ac-candidates-total")
        [ov] = _by_indicator(rows, "ac-others-votes")
        [op] = _by_indicator(rows, "ac-others-pct")
        assert total.value_numeric == 10.0
        assert ov.value_numeric == 4_000.0
        assert op.value_numeric == pytest.approx(4.0)
