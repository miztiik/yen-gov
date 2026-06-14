"""Contract tests for :func:`parliament_rollup_observations`.

Mirror of :mod:`test_canonical_eci_rollups` for the PC grain — added in the
LS-aggregate-ingest PR (2026-06-13) to close the
``ls_history.vote_share_pct == null`` honest-degradation from
``docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md``
PR-4 closure-ledger known-degradation #1.

State-scoped per Hans's locked design verdict — entity_id is
``IN-S22-LsGenMay2024-PARTY-BJP`` (the frontend SUMs across states in SQL
for any national LS view).
"""

from __future__ import annotations

import pytest

from yen_gov.canonical.adapters.eci.identity import Period
from yen_gov.canonical.adapters.eci.rollups import (
    PCContestSummary,
    parliament_rollup_observations,
)


LS_PERIOD = Period("LsGenMay2024", 2024, 5)
LS_PERIOD_PRE_NOTA = Period("LsGenOct1999", 1999, 1)


def _summary(
    *,
    pc_no: int,
    winner: str,
    votes_by_party: dict[str, int],
    source_id: str | None = None,
    total_electors: int | None = 1_000_000,
    votes_polled: int | None = None,
    nota_votes: int = 5_000,
    party_on_ballot: set[str] | None = None,
    forfeitures: dict[str, int] | None = None,
    period: Period = LS_PERIOD,
    delim_year: int = 2008,
    state_code: str = "S22",
) -> PCContestSummary:
    vp = (
        votes_polled
        if votes_polled is not None
        else sum(votes_by_party.values()) + nota_votes
    )
    return PCContestSummary(
        state_code=state_code,
        eci_no=pc_no,
        delim_year=delim_year,
        period=period,
        total_electors=total_electors,
        votes_polled=vp,
        nota_votes=nota_votes,
        winner_party_id=winner,
        source_id=source_id or f"src-pc{pc_no:04d}",
        votes_by_party=votes_by_party,
        party_was_on_ballot=(
            party_on_ballot
            if party_on_ballot is not None
            else set(votes_by_party.keys())
        ),
        forfeitures_by_party=forfeitures or {},
    )


def _by_ind(rows, ind: str):
    return [r for r in rows if r.indicator_id == ind]


class TestEmptyAndInvariants:
    def test_parliament_rollup_empty_returns_empty(self):
        assert parliament_rollup_observations(summaries=[]) == []

    def test_mismatched_state_raises(self):
        a = _summary(pc_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100})
        b = _summary(pc_no=2, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100})
        b = PCContestSummary(**{**b.__dict__, "state_code": "S30"})
        with pytest.raises(ValueError):
            parliament_rollup_observations(summaries=[a, b])

    def test_parliament_rollup_only_for_ls_periods(self):
        """Defensive guard: AC periods must be rejected.

        Prevents a caller from accidentally producing ``party-contested-pcs``
        rows under an ``AcGen*`` period_label, which would mis-classify the
        contested grain.
        """
        ac_period = Period("AcGenMay2026", 2026, 5)
        s = _summary(pc_no=1, winner="parties.IN.DMK",
                     votes_by_party={"parties.IN.DMK": 100},
                     period=ac_period)
        with pytest.raises(ValueError, match="period_label must start with 'Ls'"):
            parliament_rollup_observations(summaries=[s])


class TestPartyLevel:
    def test_parliament_seats_won_aggregation(self):
        rows = parliament_rollup_observations(summaries=[
            _summary(pc_no=1, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 600_000, "parties.IN.INC": 350_000}),
            _summary(pc_no=2, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 550_000, "parties.IN.INC": 400_000}),
            _summary(pc_no=3, winner="parties.IN.INC",
                     votes_by_party={"parties.IN.INC": 700_000, "parties.IN.BJP": 200_000}),
        ])
        seats = {r.entity_id: r.value_numeric for r in _by_ind(rows, "party-seats-won")}
        bjp_id = "IN-S22-LsGenMay2024-PARTY-BJP"
        inc_id = "IN-S22-LsGenMay2024-PARTY-INC"
        assert seats[bjp_id] == 2.0
        assert seats[inc_id] == 1.0

    def test_parliament_contested_pcs_indicator(self):
        """party_was_on_ballot drives party-contested-pcs accurately.

        Verifies (a) the NEW indicator id ``party-contested-pcs`` is emitted
        (not the AC sibling ``party-contested-acs``), and (b) the count
        matches the number of PCs where the party fielded a candidate.
        """
        rows = parliament_rollup_observations(summaries=[
            _summary(pc_no=1, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100, "parties.IN.INC": 50}),
            _summary(pc_no=2, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100, "parties.IN.INC": 50}),
            _summary(pc_no=3, winner="parties.IN.INC",
                     votes_by_party={"parties.IN.INC": 100, "parties.IN.BJP": 50}),
        ])
        # NEW indicator surface — not the AC sibling.
        contested = {r.entity_id: r.value_numeric
                     for r in _by_ind(rows, "party-contested-pcs")}
        # The AC sibling MUST NOT leak into the LS rollup output.
        assert _by_ind(rows, "party-contested-acs") == []

        bjp_id = "IN-S22-LsGenMay2024-PARTY-BJP"
        inc_id = "IN-S22-LsGenMay2024-PARTY-INC"
        assert contested[bjp_id] == 3.0
        assert contested[inc_id] == 3.0

    def test_parliament_vote_share_pct(self):
        """votes_by_party sums correctly relative to total state votes."""
        rows = parliament_rollup_observations(summaries=[
            _summary(pc_no=1, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 600_000, "parties.IN.INC": 395_000},
                     nota_votes=5_000),
            _summary(pc_no=2, winner="parties.IN.INC",
                     votes_by_party={"parties.IN.BJP": 400_000, "parties.IN.INC": 595_000},
                     nota_votes=5_000),
        ])
        # Total state votes = 1_000_000 + 1_000_000 = 2_000_000
        # BJP total = 1_000_000; INC total = 990_000
        share = {r.entity_id: r.value_numeric
                 for r in _by_ind(rows, "party-vote-share-pct")}
        bjp_id = "IN-S22-LsGenMay2024-PARTY-BJP"
        inc_id = "IN-S22-LsGenMay2024-PARTY-INC"
        assert share[bjp_id] == pytest.approx(50.0)
        assert share[inc_id] == pytest.approx(49.5)

    def test_parliament_rollup_nota_excluded(self):
        """NOTA pid never appears in party_rollup_entity_id outputs."""
        rows = parliament_rollup_observations(summaries=[
            _summary(pc_no=1, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100, "parties.IN.NOTA": 5}),
        ])
        entity_ids = {r.entity_id for r in _by_ind(rows, "party-votes-polled")}
        assert all("PARTY-NOTA" not in e for e in entity_ids)


class TestStateLevel:
    def test_turnout_and_totals(self):
        rows = parliament_rollup_observations(summaries=[
            _summary(pc_no=1, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 600_000, "parties.IN.INC": 395_000},
                     nota_votes=5_000, total_electors=1_500_000),
            _summary(pc_no=2, winner="parties.IN.INC",
                     votes_by_party={"parties.IN.BJP": 400_000, "parties.IN.INC": 595_000},
                     nota_votes=5_000, total_electors=1_500_000),
        ])
        [el] = _by_ind(rows, "electors-total")
        assert el.value_numeric == 3_000_000.0
        [vp] = _by_ind(rows, "votes-polled")
        assert vp.value_numeric == 2_000_000.0
        [tp] = _by_ind(rows, "turnout-pct")
        assert tp.value_numeric == pytest.approx(2_000_000 / 3_000_000 * 100, rel=1e-4)
        [mt] = _by_ind(rows, "majority-threshold-acs")
        assert mt.value_numeric == 2.0  # 2 // 2 + 1

    def test_nota_absent_pre_2013(self):
        """LS1999 cycle has no NOTA observation (pre-introduction)."""
        s = _summary(pc_no=1, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100},
                     nota_votes=0, period=LS_PERIOD_PRE_NOTA)
        rows = parliament_rollup_observations(summaries=[s])
        assert _by_ind(rows, "nota-pct") == []


class TestDeterministicSourcePicking:
    def test_parliament_rollup_source_is_first_eci_no(self):
        """Same deterministic ordering as AC: smallest pc_no source wins."""
        rows = parliament_rollup_observations(summaries=[
            _summary(pc_no=42, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100},
                     source_id="src-zzz99999"),
            _summary(pc_no=7, winner="parties.IN.BJP",
                     votes_by_party={"parties.IN.BJP": 100},
                     source_id="src-aaa11111"),
            _summary(pc_no=100, winner="parties.IN.INC",
                     votes_by_party={"parties.IN.INC": 100},
                     source_id="src-mmm55555"),
        ])
        # pc_no=7 is the smallest → its source wins.
        assert all(r.source_id == "src-aaa11111" for r in rows)
