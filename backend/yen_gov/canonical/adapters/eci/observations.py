"""Per-AC observation builder — ConstituencyResult → ObservationRow[].

Emits both the raw candidate-* rows and the materialised ac-* rollup rows
per docs/architecture/data/elections-indicators.md. The state-* and party-*
rollups need ALL AC results for the state and live in ``rollups.py``.

Per canonical-store.md §11.4 materialisation rule: each materialised row
carries the source_id of the per-AC contest it was computed from.
"""

from __future__ import annotations

from yen_gov.canonical.adapters.eci.identity import (
    Period,
    ac_entity_id,
    candidate_entity_id,
)
from yen_gov.canonical.adapters.eci.party_lookup import PartyLookup
from yen_gov.canonical.envelope import ObservationRow
from yen_gov.core.models import ConstituencyResult


def observations_from_constituency(
    *,
    result: ConstituencyResult,
    period: Period,
    delim_year: int,
    party_lookup: PartyLookup,
    source_id: str,
    nota_introduced_year: int = 2013,
) -> list[ObservationRow]:
    """Emit candidate-* + ac-* rows for one AC contest.

    Args:
        result: parsed ConstituencyResult from the ECI page.
        period: decoded period (year, period_seq, period_label).
        delim_year: the delimitation cycle the AC belongs to (typically 2008
            for post-delimitation results; 1976 for pre-delimitation backfill).
        party_lookup: resolves party strings to canonical party_ids.
        source_id: FK to taxonomy/sources.parquet for the underlying ECI page.
        nota_introduced_year: year before which ac-nota-* must be null.

    Returns:
        Flat list of ObservationRow instances (observation_id auto-derived
        when the row is added to a BatchEnvelope).
    """
    rows: list[ObservationRow] = []
    ac_id = ac_entity_id(result.state, delim_year, result.eci_no)

    # ---------------- candidate-scope (raw) ----------------
    # Candidate ballot serial = result.candidates.rank for now. The ECI ballot
    # serial is the order of appearance, not vote rank; per §3a we record the
    # serial in entity_id. Phase 1.1 uses rank as a stand-in until the per-AC
    # Section-10 parser surfaces the ballot serial explicitly.
    for cand in result.candidates:
        cand_id = candidate_entity_id(ac_id, period.period_label, cand.rank)
        rows.append(_obs(
            entity_id=cand_id,
            period=period,
            indicator_id="candidate-votes-polled",
            value_numeric=float(cand.votes),
            source_id=source_id,
            derivation="raw",
        ))
        rows.append(_obs(
            entity_id=cand_id,
            period=period,
            indicator_id="candidate-vote-share-pct",
            value_numeric=float(cand.vote_share_pct),
            source_id=source_id,
            derivation="raw",
        ))
        rows.append(_obs(
            entity_id=cand_id,
            period=period,
            indicator_id="candidate-rank",
            value_numeric=float(cand.rank),
            source_id=source_id,
            derivation="raw",
        ))

    # ---------------- ac-scope (materialised) ----------------
    if result.totals.electors is not None:
        rows.append(_obs(
            entity_id=ac_id,
            period=period,
            indicator_id="ac-total-electors",
            value_numeric=float(result.totals.electors),
            source_id=source_id,
            derivation="raw",
        ))
    rows.append(_obs(
        entity_id=ac_id,
        period=period,
        indicator_id="ac-votes-polled",
        value_numeric=float(result.totals.votes_polled),
        source_id=source_id,
        derivation="sum",
    ))
    if result.totals.electors and result.totals.turnout_pct is not None:
        rows.append(_obs(
            entity_id=ac_id,
            period=period,
            indicator_id="ac-turnout-pct",
            value_numeric=float(result.totals.turnout_pct),
            source_id=source_id,
            derivation="ratio_pct",
        ))

    # NOTA — null pre-introduction, NOT zero (per §3a comparability trap).
    if period.year >= nota_introduced_year:
        rows.append(_obs(
            entity_id=ac_id,
            period=period,
            indicator_id="ac-nota-votes",
            value_numeric=float(result.nota.votes),
            source_id=source_id,
            derivation="raw",
        ))
        rows.append(_obs(
            entity_id=ac_id,
            period=period,
            indicator_id="ac-nota-pct",
            value_numeric=float(result.nota.vote_share_pct),
            source_id=source_id,
            derivation="ratio_pct",
        ))

    # Winner identity (value_text, not numeric).
    winner_candidate_id = candidate_entity_id(
        ac_id, period.period_label, _winner_rank(result),
    )
    rows.append(_obs(
        entity_id=ac_id,
        period=period,
        indicator_id="ac-winner-candidate-id",
        value_text=winner_candidate_id,
        source_id=source_id,
        derivation="argmax",
    ))
    winner_party_id = party_lookup.resolve(
        party_short=result.winner.party_short,
        eci_code=str(result.winner.party_eci_code) if result.winner.party_eci_code else None,
        is_independent=_winner_is_independent(result),
    )
    rows.append(_obs(
        entity_id=ac_id,
        period=period,
        indicator_id="ac-winner-party-id",
        value_text=winner_party_id,
        source_id=source_id,
        derivation="join",
    ))

    # Margin
    rows.append(_obs(
        entity_id=ac_id,
        period=period,
        indicator_id="ac-margin-votes",
        value_numeric=float(result.winner.margin_votes),
        source_id=source_id,
        derivation="diff",
    ))
    rows.append(_obs(
        entity_id=ac_id,
        period=period,
        indicator_id="ac-margin-pct",
        value_numeric=float(result.winner.margin_pct),
        source_id=source_id,
        derivation="ratio_pct",
    ))

    # Effective candidates (Laakso-Taagepera). Computed from candidate shares
    # plus the NOTA share when present.
    shares = [c.vote_share_pct / 100.0 for c in result.candidates]
    if period.year >= nota_introduced_year:
        shares.append(result.nota.vote_share_pct / 100.0)
    ssq = sum(s * s for s in shares)
    if ssq > 0:
        rows.append(_obs(
            entity_id=ac_id,
            period=period,
            indicator_id="ac-effective-candidates-laakso",
            value_numeric=float(1.0 / ssq),
            source_id=source_id,
            derivation="laakso_taagepera",
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


def _winner_rank(result: ConstituencyResult) -> int:
    # The winner is rank 1 by construction in ConstituencyResult, but the
    # explicit lookup keeps us honest if the model ever loosens that invariant.
    for cand in result.candidates:
        if cand.name == result.winner.name and cand.party_short == result.winner.party_short:
            return cand.rank
    raise ValueError(
        f"Winner {result.winner.name!r} not found among candidates of "
        f"{result.state} AC {result.eci_no}"
    )


def _winner_is_independent(result: ConstituencyResult) -> bool:
    return result.winner.party_short.strip().lower() in {"ind", "independent"}
