"""State-level rollups — party-* and state-* observations.

Computed AFTER every AC or PC contest for a state has been ingested. Inputs
are the candidate-* + ac-* / pc-* ObservationRows already emitted by
``observations.py`` / ``pc_observations.py``.

Per canonical-store.md §11.4: each rollup row carries the source_id of the
**contest-scoping source**. The writer needs deterministic source-picking so
re-runs produce byte-identical Parquet; here we pick the first contest's
source_id in (eci_no) order, which is stable as long as the input list is
sorted.

Two analogous entry-points:

- :func:`state_rollup_observations` — AC rollup (party-contested-acs).
- :func:`parliament_rollup_observations` — PC rollup (party-contested-pcs).
  Added in the LS-aggregate-ingest PR (2026-06-13) to close the
  ``ls_history.vote_share_pct == null`` honest-degradation from
  ``docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md``
  PR-4 closure-ledger known-degradation #1. The two functions share the same
  party_rollup_entity_id grammar (``IN-S22-LsGenMay2024-PARTY-BJP`` mirrors
  ``IN-S22-AcGenMay2026-PARTY-BJP``); only the ``-contested-`` indicator id
  differs (``-acs`` vs ``-pcs``) so a downstream consumer can dispatch on
  the period_label prefix without changing the rollup shape.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from yen_gov.canonical.adapters.eci.identity import (
    Period,
    candidate_entity_id,
    party_rollup_entity_id,
    state_rollup_entity_id,
)
from yen_gov.canonical.row_models import ObservationRow


@dataclass(frozen=True)
class ACContestSummary:
    """Compact summary of one AC's contest, used as rollup input.

    Built by the caller from the same parsed ConstituencyResult used by
    ``observations_from_constituency`` — kept as a separate input shape so
    the rollup code is testable without re-running the full per-AC adapter.
    """

    state_code: str
    eci_no: int
    delim_year: int
    period: Period
    total_electors: int | None
    votes_polled: int
    nota_votes: int
    winner_party_id: str
    source_id: str
    # candidate_party_id -> total votes that party got in this AC
    votes_by_party: dict[str, int]
    # candidate_party_id -> True if any candidate of that party was on the ballot
    # (used for party-contested-acs)
    party_was_on_ballot: set[str]
    # candidate_party_id -> count of candidates of that party who forfeited
    # deposit (< 16.67% vote share)
    forfeitures_by_party: dict[str, int]


def state_rollup_observations(
    *,
    summaries: list[ACContestSummary],
    nota_introduced_year: int = 2013,
) -> list[ObservationRow]:
    """Compute party-* and state-* ObservationRows from a list of AC summaries.

    All summaries MUST share the same (state_code, period). The function
    sorts internally and picks a deterministic source_id for rollup rows.
    """
    if not summaries:
        return []
    state_code = summaries[0].state_code
    period = summaries[0].period
    if any(s.state_code != state_code or s.period != period for s in summaries):
        raise ValueError(
            "state_rollup_observations: all summaries must share (state, period)"
        )

    # Deterministic contest-scoping source per §11.4: first source_id in
    # eci_no order.
    summaries_sorted = sorted(summaries, key=lambda s: s.eci_no)
    rollup_source = summaries_sorted[0].source_id

    state_id = state_rollup_entity_id(state_code, period.period_label)
    rows: list[ObservationRow] = []

    # ---------- state-* ----------
    total_electors = sum((s.total_electors or 0) for s in summaries_sorted)
    any_electors_missing = any(s.total_electors is None for s in summaries_sorted)
    total_votes = sum(s.votes_polled for s in summaries_sorted)
    total_nota = sum(s.nota_votes for s in summaries_sorted)
    total_acs = len(summaries_sorted)

    if not any_electors_missing:
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="electors-total",
            value_numeric=float(total_electors),
            source_id=rollup_source, derivation="sum",
        ))
    rows.append(_obs(
        entity_id=state_id, period=period,
        indicator_id="votes-polled",
        value_numeric=float(total_votes),
        source_id=rollup_source, derivation="sum",
    ))
    if not any_electors_missing and total_electors > 0:
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="turnout-pct",
            value_numeric=round(total_votes / total_electors * 100, 4),
            source_id=rollup_source, derivation="ratio_pct",
        ))
    if period.year >= nota_introduced_year and total_votes > 0:
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="nota-pct",
            value_numeric=round(total_nota / total_votes * 100, 4),
            source_id=rollup_source, derivation="ratio_pct",
        ))

    rows.append(_obs(
        entity_id=state_id, period=period,
        indicator_id="majority-threshold-acs",
        value_numeric=float(total_acs // 2 + 1),
        source_id=rollup_source, derivation="constant",
    ))

    # ---------- party-* per party ----------
    seats_won: dict[str, int] = defaultdict(int)
    for s in summaries_sorted:
        seats_won[s.winner_party_id] += 1

    contested: dict[str, int] = defaultdict(int)
    party_votes: dict[str, int] = defaultdict(int)
    forfeitures: dict[str, int] = defaultdict(int)
    for s in summaries_sorted:
        for pid in s.party_was_on_ballot:
            contested[pid] += 1
        for pid, votes in s.votes_by_party.items():
            party_votes[pid] += votes
        for pid, count in s.forfeitures_by_party.items():
            forfeitures[pid] += count

    all_parties = sorted(set(contested) | set(seats_won) | set(party_votes))
    for pid in all_parties:
        if not pid.startswith("parties.IN.") or pid == "parties.IN.NOTA":
            # NOTA is not a party — exclude from party rollups even if a caller
            # accidentally surfaced it in votes_by_party.
            continue
        slug = pid.removeprefix("parties.IN.")
        prty_id = party_rollup_entity_id(state_code, period.period_label, slug)
        p_contested = contested.get(pid, 0)
        p_seats = seats_won.get(pid, 0)
        p_votes = party_votes.get(pid, 0)
        p_forfeit = forfeitures.get(pid, 0)

        rows.append(_obs(
            entity_id=prty_id, period=period,
            indicator_id="party-contested-acs",
            value_numeric=float(p_contested),
            source_id=rollup_source, derivation="count_where",
        ))
        rows.append(_obs(
            entity_id=prty_id, period=period,
            indicator_id="party-seats-won",
            value_numeric=float(p_seats),
            source_id=rollup_source, derivation="count_where",
        ))
        if p_contested > 0:
            rows.append(_obs(
                entity_id=prty_id, period=period,
                indicator_id="party-strike-rate-pct",
                value_numeric=round(p_seats / p_contested * 100, 4),
                source_id=rollup_source, derivation="ratio_pct",
            ))
        rows.append(_obs(
            entity_id=prty_id, period=period,
            indicator_id="party-votes-polled",
            value_numeric=float(p_votes),
            source_id=rollup_source, derivation="sum",
        ))
        if total_votes > 0:
            rows.append(_obs(
                entity_id=prty_id, period=period,
                indicator_id="party-vote-share-pct",
                value_numeric=round(p_votes / total_votes * 100, 4),
                source_id=rollup_source, derivation="ratio_pct",
            ))
        rows.append(_obs(
            entity_id=prty_id, period=period,
            indicator_id="party-forfeitures-count",
            value_numeric=float(p_forfeit),
            source_id=rollup_source, derivation="count_where",
        ))

    # ---------- state-winning-party-* + effective parties ----------
    # Highest-seat party (deterministic tie-break: lex order on slug).
    if seats_won:
        winning_pid = sorted(seats_won.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        winning_seats = seats_won[winning_pid]
        # "Hung" sentinel: no party crosses majority threshold AND no party
        # has the largest seat count > runner-up by >= 2 — we still report
        # the largest-bloc party; null is reserved for genuinely tied legislatures.
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="winning-party-id",
            value_text=winning_pid,
            source_id=rollup_source, derivation="argmax",
        ))
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="winning-party-seats",
            value_numeric=float(winning_seats),
            source_id=rollup_source, derivation="argmax",
        ))

        # Laakso-Taagepera on seat shares
        seat_shares = [v / total_acs for v in seats_won.values() if v > 0]
        ssq = sum(s * s for s in seat_shares)
        if ssq > 0:
            rows.append(_obs(
                entity_id=state_id, period=period,
                indicator_id="effective-parties-laakso",
                value_numeric=round(1.0 / ssq, 4),
                source_id=rollup_source, derivation="laakso_taagepera",
            ))

    return rows


def _obs(
    *,
    entity_id: str,
    period: Period,
    indicator_id: str,
    source_id: str,
    derivation: str,
    value_numeric: float | None = None,
    value_text: str | None = None,
) -> ObservationRow:
    return ObservationRow(
        entity_id=entity_id,
        year=period.year,
        period_label=period.period_label,
        period_seq=period.period_seq,
        indicator_id=indicator_id,
        value_numeric=value_numeric,
        value_text=value_text,
        source_id=source_id,
        derivation=derivation,
    )


# ---------------------------------------------------------------------------
# Parliament (PC) rollup — sibling of state_rollup_observations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PCContestSummary:
    """Compact summary of one PC's contest, used as parliament rollup input.

    Mirror of :class:`ACContestSummary`; ``eci_no`` holds the PC's pc_no,
    ``delim_year`` holds the PC's delim cohort (1976 for pre-2008 cycles,
    2008 for the in-force boundaries). The party shape is identical so the
    rollup function can share most of its code path with the AC rollup.

    Built by the caller (currently :mod:`yen_gov.canonical.adapters.eci_ls`
    ``_envelope_from_results``) from the same parsed PcResultRaw used by
    :func:`observations_from_pc`, so the rollup is testable without re-
    running the full per-PC adapter.
    """

    state_code: str
    eci_no: int
    delim_year: int
    period: Period
    total_electors: int | None
    votes_polled: int
    nota_votes: int
    winner_party_id: str
    source_id: str
    # candidate_party_id -> total votes that party got in this PC
    votes_by_party: dict[str, int]
    # candidate_party_id -> True if any candidate of that party was on the
    # ballot (used for party-contested-pcs)
    party_was_on_ballot: set[str]
    # candidate_party_id -> count of candidates of that party who forfeited
    # deposit (< 16.67% vote share — ECI Section 158 RPA)
    forfeitures_by_party: dict[str, int]


def parliament_rollup_observations(
    *,
    summaries: list[PCContestSummary],
    nota_introduced_year: int = 2013,
) -> list[ObservationRow]:
    """Compute party-* and state-* ObservationRows from PC summaries.

    All summaries MUST share the same (state_code, period) AND the period MUST
    be an LS event (``period_label`` starts with ``Ls``). The defensive guard
    on the period prefix exists so a caller who accidentally passes AC
    summaries gets a fail-fast rather than minting ``IN-S22-AcGen...-PARTY-X``
    rows with a PC-specific ``party-contested-pcs`` indicator (which would be
    structurally invalid).

    Emits per-(state, period, party) rows for:
      - party-seats-won
      - party-vote-share-pct (state-scoped denominator = state turnout)
      - party-votes-polled
      - party-contested-pcs (NEW; analogous to party-contested-acs)
      - party-strike-rate-pct (seats / contested * 100)
      - party-forfeitures-count (PC forfeitures, < 16.67% of valid votes)

    Plus per-state state-* indicators (electors-total, votes-polled,
    turnout-pct, nota-pct, majority-threshold-acs [shape preserved despite
    the "-acs" suffix — Hans's "extra rows are harmless" decision; the
    citizen-facing label dispatches on period_label, not indicator_id],
    winning-party-id, winning-party-seats, effective-parties-laakso).

    NOTA is excluded from party rollups (it is a ballot option, not a party).
    Source rows pick the deterministic first source_id by eci_no order per
    canonical-store.md §11.4.
    """
    if not summaries:
        return []
    state_code = summaries[0].state_code
    period = summaries[0].period
    if any(s.state_code != state_code or s.period != period for s in summaries):
        raise ValueError(
            "parliament_rollup_observations: all summaries must share (state, period)"
        )
    if not period.period_label.startswith("Ls"):
        # Defensive: prevent an AC caller from accidentally producing
        # party-contested-pcs rows under an AcGen* period_label.
        raise ValueError(
            "parliament_rollup_observations: period_label must start with 'Ls'; "
            f"got {period.period_label!r}"
        )

    summaries_sorted = sorted(summaries, key=lambda s: s.eci_no)
    rollup_source = summaries_sorted[0].source_id

    state_id = state_rollup_entity_id(state_code, period.period_label)
    rows: list[ObservationRow] = []

    # ---------- state-* ----------
    total_electors = sum((s.total_electors or 0) for s in summaries_sorted)
    any_electors_missing = any(s.total_electors is None for s in summaries_sorted)
    total_votes = sum(s.votes_polled for s in summaries_sorted)
    total_nota = sum(s.nota_votes for s in summaries_sorted)
    total_pcs = len(summaries_sorted)

    if not any_electors_missing:
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="electors-total",
            value_numeric=float(total_electors),
            source_id=rollup_source, derivation="sum",
        ))
    rows.append(_obs(
        entity_id=state_id, period=period,
        indicator_id="votes-polled",
        value_numeric=float(total_votes),
        source_id=rollup_source, derivation="sum",
    ))
    if not any_electors_missing and total_electors > 0:
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="turnout-pct",
            value_numeric=round(total_votes / total_electors * 100, 4),
            source_id=rollup_source, derivation="ratio_pct",
        ))
    if period.year >= nota_introduced_year and total_votes > 0:
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="nota-pct",
            value_numeric=round(total_nota / total_votes * 100, 4),
            source_id=rollup_source, derivation="ratio_pct",
        ))

    rows.append(_obs(
        entity_id=state_id, period=period,
        indicator_id="majority-threshold-acs",
        value_numeric=float(total_pcs // 2 + 1),
        source_id=rollup_source, derivation="constant",
    ))

    # ---------- party-* per party ----------
    seats_won: dict[str, int] = defaultdict(int)
    for s in summaries_sorted:
        seats_won[s.winner_party_id] += 1

    contested: dict[str, int] = defaultdict(int)
    party_votes: dict[str, int] = defaultdict(int)
    forfeitures: dict[str, int] = defaultdict(int)
    for s in summaries_sorted:
        for pid in s.party_was_on_ballot:
            contested[pid] += 1
        for pid, votes in s.votes_by_party.items():
            party_votes[pid] += votes
        for pid, count in s.forfeitures_by_party.items():
            forfeitures[pid] += count

    all_parties = sorted(set(contested) | set(seats_won) | set(party_votes))
    for pid in all_parties:
        if not pid.startswith("parties.IN.") or pid == "parties.IN.NOTA":
            # NOTA is not a party — exclude from party rollups even if a caller
            # accidentally surfaced it in votes_by_party.
            continue
        slug = pid.removeprefix("parties.IN.")
        prty_id = party_rollup_entity_id(state_code, period.period_label, slug)
        p_contested = contested.get(pid, 0)
        p_seats = seats_won.get(pid, 0)
        p_votes = party_votes.get(pid, 0)
        p_forfeit = forfeitures.get(pid, 0)

        rows.append(_obs(
            entity_id=prty_id, period=period,
            indicator_id="party-contested-pcs",
            value_numeric=float(p_contested),
            source_id=rollup_source, derivation="count_where",
        ))
        rows.append(_obs(
            entity_id=prty_id, period=period,
            indicator_id="party-seats-won",
            value_numeric=float(p_seats),
            source_id=rollup_source, derivation="count_where",
        ))
        if p_contested > 0:
            rows.append(_obs(
                entity_id=prty_id, period=period,
                indicator_id="party-strike-rate-pct",
                value_numeric=round(p_seats / p_contested * 100, 4),
                source_id=rollup_source, derivation="ratio_pct",
            ))
        rows.append(_obs(
            entity_id=prty_id, period=period,
            indicator_id="party-votes-polled",
            value_numeric=float(p_votes),
            source_id=rollup_source, derivation="sum",
        ))
        if total_votes > 0:
            rows.append(_obs(
                entity_id=prty_id, period=period,
                indicator_id="party-vote-share-pct",
                value_numeric=round(p_votes / total_votes * 100, 4),
                source_id=rollup_source, derivation="ratio_pct",
            ))
        rows.append(_obs(
            entity_id=prty_id, period=period,
            indicator_id="party-forfeitures-count",
            value_numeric=float(p_forfeit),
            source_id=rollup_source, derivation="count_where",
        ))

    # ---------- state-winning-party-* + effective parties ----------
    if seats_won:
        winning_pid = sorted(seats_won.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        winning_seats = seats_won[winning_pid]
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="winning-party-id",
            value_text=winning_pid,
            source_id=rollup_source, derivation="argmax",
        ))
        rows.append(_obs(
            entity_id=state_id, period=period,
            indicator_id="winning-party-seats",
            value_numeric=float(winning_seats),
            source_id=rollup_source, derivation="argmax",
        ))

        # Laakso-Taagepera on seat shares
        seat_shares = [v / total_pcs for v in seats_won.values() if v > 0]
        ssq = sum(s * s for s in seat_shares)
        if ssq > 0:
            rows.append(_obs(
                entity_id=state_id, period=period,
                indicator_id="effective-parties-laakso",
                value_numeric=round(1.0 / ssq, 4),
                source_id=rollup_source, derivation="laakso_taagepera",
            ))

    return rows
