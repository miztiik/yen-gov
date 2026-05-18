"""Contract tests for yen_gov.canonical.adapters.eci.rollups."""

from __future__ import annotations

import pytest

from yen_gov.canonical.adapters.eci.identity import Period
from yen_gov.canonical.adapters.eci.rollups import (
    ACContestSummary,
    state_rollup_observations,
)


PERIOD = Period("AcGenMay2026", 2026, 5)


def _summary(
    *,
    eci_no: int,
    winner: str,
    votes_by_party: dict[str, int],
    source_id: str | None = None,
    total_electors: int | None = 100_000,
    votes_polled: int | None = None,
    nota_votes: int = 500,
    party_on_ballot: set[str] | None = None,
    forfeitures: dict[str, int] | None = None,
) -> ACContestSummary:
    vp = votes_polled if votes_polled is not None else sum(votes_by_party.values()) + nota_votes
    return ACContestSummary(
        state_code="S22", eci_no=eci_no, delim_year=2008, period=PERIOD,
        total_electors=total_electors, votes_polled=vp, nota_votes=nota_votes,
        winner_party_id=winner,
        source_id=source_id or f"src-eci{eci_no:04d}",
        votes_by_party=votes_by_party,
        party_was_on_ballot=party_on_ballot if party_on_ballot is not None
            else set(votes_by_party.keys()),
        forfeitures_by_party=forfeitures or {},
    )


def _by_ind(rows, ind: str):
    return [r for r in rows if r.indicator_id == ind]


class TestEmptyAndInvariants:
    def test_empty_returns_empty(self):
        assert state_rollup_observations(summaries=[]) == []

    def test_mismatched_state_raises(self):
        a = _summary(eci_no=1, winner="parties.IN.DMK", votes_by_party={"parties.IN.DMK": 100})
        b = _summary(eci_no=2, winner="parties.IN.BJP", votes_by_party={"parties.IN.BJP": 100})
        b = ACContestSummary(**{**b.__dict__, "state_code": "S30"})
        with pytest.raises(ValueError):
            state_rollup_observations(summaries=[a, b])


class TestStateLevel:
    def test_totals_and_turnout(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 60_000, "parties.IN.BJP": 39_500},
                     total_electors=100_000),
            _summary(eci_no=2, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 70_000, "parties.IN.BJP": 29_500},
                     total_electors=100_000),
        ])
        [el] = _by_ind(rows, "state-electors-total")
        assert el.value_numeric == 200_000.0
        [vp] = _by_ind(rows, "state-votes-polled")
        assert vp.value_numeric == 200_000.0
        [tp] = _by_ind(rows, "state-turnout-pct")
        assert tp.value_numeric == pytest.approx(100.0)
        [mt] = _by_ind(rows, "state-majority-threshold-acs")
        assert mt.value_numeric == 2.0  # 2 // 2 + 1

    def test_electors_omitted_if_any_missing(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100},
                     total_electors=None),
        ])
        assert _by_ind(rows, "state-electors-total") == []
        assert _by_ind(rows, "state-turnout-pct") == []

    def test_nota_pct_present_post_2013(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 9_500},
                     nota_votes=500, votes_polled=10_000),
        ])
        [n] = _by_ind(rows, "state-nota-pct")
        assert n.value_numeric == pytest.approx(5.0)

    def test_nota_absent_pre_2013(self):
        s = _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100}, nota_votes=0)
        s = ACContestSummary(**{**s.__dict__, "period": Period("AcGenApr2011", 2011, 4)})
        rows = state_rollup_observations(summaries=[s])
        assert _by_ind(rows, "state-nota-pct") == []


class TestPartyLevel:
    def test_seats_won_and_contested(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100, "parties.IN.BJP": 50}),
            _summary(eci_no=2, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100, "parties.IN.BJP": 50}),
            _summary(eci_no=3, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100, "parties.IN.DMK": 50}),
        ])
        seats = {r.entity_id: r.value_numeric for r in _by_ind(rows, "party-seats-won")}
        contested = {r.entity_id: r.value_numeric for r in _by_ind(rows, "party-contested-acs")}
        dmk_id = "IN-S22-AcGenMay2026-PARTY-DMK"
        bjp_id = "IN-S22-AcGenMay2026-PARTY-BJP"
        assert seats[dmk_id] == 2.0
        assert seats[bjp_id] == 1.0
        assert contested[dmk_id] == 3.0
        assert contested[bjp_id] == 3.0

    def test_strike_rate(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100, "parties.IN.BJP": 50}),
            _summary(eci_no=2, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.DMK": 50, "parties.IN.BJP": 100}),
        ])
        sr = {r.entity_id: r.value_numeric for r in _by_ind(rows, "party-strike-rate-pct")}
        assert sr["IN-S22-AcGenMay2026-PARTY-DMK"] == pytest.approx(50.0)
        assert sr["IN-S22-AcGenMay2026-PARTY-BJP"] == pytest.approx(50.0)

    def test_nota_excluded_from_party_rollups(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100, "parties.IN.NOTA": 5}),
        ])
        entity_ids = {r.entity_id for r in _by_ind(rows, "party-votes-polled")}
        assert all("PARTY-NOTA" not in e for e in entity_ids)

    def test_forfeitures_aggregated(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100, "parties.IN.BJP": 5},
                     forfeitures={"parties.IN.BJP": 1}),
            _summary(eci_no=2, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100, "parties.IN.BJP": 3},
                     forfeitures={"parties.IN.BJP": 1}),
        ])
        f = {r.entity_id: r.value_numeric for r in _by_ind(rows, "party-forfeitures-count")}
        assert f["IN-S22-AcGenMay2026-PARTY-BJP"] == 2.0


class TestWinningPartyAndEffective:
    def test_winning_party_max_seats(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100}),
            _summary(eci_no=2, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100}),
            _summary(eci_no=3, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100}),
        ])
        [w] = _by_ind(rows, "state-winning-party-id")
        assert w.value_text == "parties.IN.DMK"
        [ws] = _by_ind(rows, "state-winning-party-seats")
        assert ws.value_numeric == 2.0

    def test_tie_break_is_lex_on_pid(self):
        # BJP and DMK each take 1 seat. Lex tie-break on pid → BJP wins.
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100}),
            _summary(eci_no=2, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100}),
        ])
        [w] = _by_ind(rows, "state-winning-party-id")
        assert w.value_text == "parties.IN.BJP"

    def test_effective_parties_laakso(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=i, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100})
            for i in range(1, 5)
        ])
        [r] = _by_ind(rows, "state-effective-parties-laakso")
        # All 4 seats to one party → ENP = 1.0
        assert r.value_numeric == pytest.approx(1.0)


class TestDeterministicSourcePicking:
    def test_rollup_source_is_first_eci_no(self):
        rows = state_rollup_observations(summaries=[
            _summary(eci_no=42, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100},
                     source_id="src-zzz99999"),
            _summary(eci_no=7, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100},
                     source_id="src-aaa11111"),
            _summary(eci_no=100, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100},
                     source_id="src-mmm55555"),
        ])
        # eci_no=7 is the smallest → its source wins.
        assert all(r.source_id == "src-aaa11111" for r in rows)
