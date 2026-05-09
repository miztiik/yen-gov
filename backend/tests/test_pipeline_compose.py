"""Tests for pipeline.compose.party_lookup_from_partywise."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from yen_gov.core.models import (
    CandidateResult,
    ConstituencyResult,
    NotaResult,
    ResultTotals,
    SourceRef,
    WinnerInfo,
)
from yen_gov.pipeline.compose import (
    compose_result_summary,
    party_lookup_from_partywise,
    reconcile_winners_against_partywise,
)
from yen_gov.sources.eci.partywise import PartyRow, PartywiseSnapshot


def _src(url: str = "https://results.eci.gov.in/x.htm") -> SourceRef:
    return SourceRef(url=url, fetched_at=datetime(2026, 5, 8, 14, 0, tzinfo=timezone.utc))


def _snap(*rows: PartyRow, total_seats: int = 234) -> PartywiseSnapshot:
    return PartywiseSnapshot(state_name="Tamil Nadu", total_seats=total_seats, parties=list(rows))


def test_builds_full_to_short_and_code_map():
    snap = _snap(
        PartyRow(full_name="Dravida Munnetra Kazhagam", short_name="DMK",
                 eci_code="742", seats_won=130, leading=0, total=130),
        PartyRow(full_name="Indian National Congress", short_name="INC",
                 eci_code="1142", seats_won=20, leading=0, total=20),
    )
    lookup = party_lookup_from_partywise(snap)
    assert lookup["Dravida Munnetra Kazhagam"] == ("DMK", "742")
    assert lookup["Indian National Congress"] == ("INC", "1142")


def test_preserves_none_eci_code():
    snap = _snap(
        PartyRow(full_name="Tiny Party", short_name="TP",
                 eci_code=None, seats_won=0, leading=0, total=0),
    )
    assert party_lookup_from_partywise(snap)["Tiny Party"] == ("TP", None)


def test_rejects_duplicate_full_name():
    snap = _snap(
        PartyRow(full_name="Same Name", short_name="A",
                 eci_code="1", seats_won=1, leading=0, total=1),
        PartyRow(full_name="Same Name", short_name="B",
                 eci_code="2", seats_won=2, leading=0, total=2),
    )
    with pytest.raises(ValueError, match="duplicate party full_name"):
        party_lookup_from_partywise(snap)


# --- compose_result_summary -------------------------------------------------

def _cr(eci_no: int, *, polled: int, candidates: list[tuple[str, str, int, float]]) -> ConstituencyResult:
    """Build a minimal ConstituencyResult. candidates = [(name, party_short, votes, pct), ...]"""
    cands = [
        CandidateResult(
            rank=i + 1, name=n, party_eci_code=None, party_short=ps,
            votes=v, vote_share_pct=pct, is_winner=(i == 0) or None,
        )
        for i, (n, ps, v, pct) in enumerate(candidates)
    ]
    winner_n, winner_ps, winner_v, _ = candidates[0]
    runner = candidates[1][2] if len(candidates) > 1 else 0
    margin = winner_v - runner
    return ConstituencyResult(
        sources=[_src()],
        election="AcGenMay2026", state="S22", body="AC", eci_no=eci_no,
        constituency_name=f"AC{eci_no}",
        totals=ResultTotals(votes_polled=polled),
        candidates=cands,
        nota=NotaResult(votes=0, vote_share_pct=0.0),
        others=None,
        top_n_cutoff=10,
        winner=WinnerInfo(
            name=winner_n, party_eci_code=None, party_short=winner_ps,
            votes=winner_v, margin_votes=margin,
            margin_pct=round(margin / polled * 100, 2),
        ),
    )


def test_summary_aggregates_votes_and_seats_from_partywise():
    snap = _snap(
        PartyRow(full_name="Dravida Munnetra Kazhagam", short_name="DMK",
                 eci_code="742", seats_won=2, leading=0, total=2),
        PartyRow(full_name="All India Anna Dravida Munnetra Kazhagam", short_name="AIADMK",
                 eci_code="2110", seats_won=0, leading=0, total=0),
        total_seats=2,
    )
    cr1 = _cr(1, polled=100, candidates=[("A", "DMK", 60, 60.0), ("B", "AIADMK", 40, 40.0)])
    cr2 = _cr(2, polled=200, candidates=[("C", "DMK", 120, 60.0), ("D", "AIADMK", 80, 40.0)])
    summary = compose_result_summary(
        election="AcGenMay2026", state="S22", body="AC",
        partywise=snap, constituencies=[cr1, cr2], sources=[_src()],
    )
    assert summary.total_seats == 2
    assert summary.totals.votes_polled == 300
    by_short = {p.party_short: p for p in summary.party_totals}
    assert by_short["DMK"].seats_won == 2
    assert by_short["DMK"].votes == 180
    assert by_short["DMK"].vote_share_pct == 60.0
    assert by_short["DMK"].seats_contested == 2
    assert by_short["AIADMK"].seats_won == 0
    assert by_short["AIADMK"].votes == 120
    assert by_short["AIADMK"].vote_share_pct == 40.0


def test_summary_surfaces_party_present_in_acs_but_absent_from_partywise():
    snap = _snap(
        PartyRow(full_name="Dravida Munnetra Kazhagam", short_name="DMK",
                 eci_code="742", seats_won=1, leading=0, total=1),
        total_seats=1,
    )
    cr = _cr(1, polled=100, candidates=[("A", "DMK", 60, 60.0), ("B", "FRINGE", 40, 40.0)])
    summary = compose_result_summary(
        election="AcGenMay2026", state="S22", body="AC",
        partywise=snap, constituencies=[cr], sources=[_src()],
    )
    by_short = {p.party_short: p for p in summary.party_totals}
    assert "FRINGE" in by_short
    assert by_short["FRINGE"].seats_won == 0
    assert by_short["FRINGE"].votes == 40
    assert by_short["FRINGE"].party_eci_code is None


def test_summary_rejects_empty_constituencies():
    snap = _snap(PartyRow(full_name="X", short_name="X", eci_code="1",
                          seats_won=0, leading=0, total=0))
    with pytest.raises(ValueError, match="at least one"):
        compose_result_summary(
            election="e", state="S22", body="AC",
            partywise=snap, constituencies=[], sources=[_src()],
        )


# --- reconcile_winners_against_partywise -----------------------------------

def test_reconcile_passes_when_winners_match_partywise():
    snap = _snap(
        PartyRow(full_name="DMK Full", short_name="DMK", eci_code="742",
                 seats_won=2, leading=0, total=2),
        PartyRow(full_name="AIADMK Full", short_name="AIADMK", eci_code="2110",
                 seats_won=1, leading=0, total=1),
        total_seats=3,
    )
    crs = [
        _cr(1, polled=100, candidates=[("A", "DMK", 60, 60.0), ("B", "AIADMK", 40, 40.0)]),
        _cr(2, polled=100, candidates=[("C", "DMK", 60, 60.0), ("D", "AIADMK", 40, 40.0)]),
        _cr(3, polled=100, candidates=[("E", "AIADMK", 60, 60.0), ("F", "DMK", 40, 40.0)]),
    ]
    reconcile_winners_against_partywise(partywise=snap, constituencies=crs)


def test_reconcile_raises_on_count_mismatch():
    snap = _snap(
        PartyRow(full_name="DMK Full", short_name="DMK", eci_code="742",
                 seats_won=1, leading=0, total=1),
        total_seats=1,
    )
    crs = [_cr(1, polled=100, candidates=[("A", "AIADMK", 60, 60.0), ("B", "DMK", 40, 40.0)])]
    with pytest.raises(ValueError, match="reconciliation failed"):
        reconcile_winners_against_partywise(partywise=snap, constituencies=crs)


def test_reconcile_raises_when_winning_party_absent_from_partywise():
    snap = _snap(
        PartyRow(full_name="DMK Full", short_name="DMK", eci_code="742",
                 seats_won=0, leading=0, total=0),
        total_seats=1,
    )
    crs = [_cr(1, polled=100, candidates=[("A", "FRINGE", 60, 60.0), ("B", "DMK", 40, 40.0)])]
    with pytest.raises(ValueError, match="FRINGE.*absent from partywise"):
        reconcile_winners_against_partywise(partywise=snap, constituencies=crs)
