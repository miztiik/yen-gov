"""Per-PC observation builder — PcResultRaw → ObservationRow[].

Emits the candidate-* raw rows plus the 13 materialised ``pc-*`` aggregate
rows per ``TODO/20260531-uk-style-elections-experience-plan.md`` (Model C —
the pc-grain measures are SIBLING concepts of the ac-grain ones, sharing one
``concept_id`` whose ``entity_kinds`` lists both ``ac`` and ``pc``).

PC person/candidacy dim rows are deliberately NOT emitted here: the
``CandidacyRow``/``PersonDimRow`` schemas are AC-pattern-locked
(``IN-<state>-AC-...``) and extending them to PC is a separate schema bump
out of scope for this row. ``dim_rows_from_pc`` therefore returns only the
``PcDimRow`` payloads, mirroring the plan's PR-A3 deliverable.
"""

from __future__ import annotations

from yen_gov.canonical.adapters.eci.identity import (
    Period,
    candidate_entity_id,
    pc_entity_id,
)
from yen_gov.canonical.adapters.eci.party_lookup import PartyLookup
from yen_gov.canonical.envelope import ObservationRow
from yen_gov.sources.eci.ls_constituencywise import PcCandidateRaw, PcResultRaw

_INDEPENDENT_ALIASES = {"independent", "ind", "ind.", "independents"}


def _is_independent(party_name: str) -> bool:
    return party_name.strip().lower() in _INDEPENDENT_ALIASES


def _ranked_non_nota(result: PcResultRaw) -> list[PcCandidateRaw]:
    """Candidates excluding NOTA, sorted by total votes descending.

    The ECI Report-33 row order is ballot order, not vote rank, so we sort
    explicitly. Ties break by candidate name for determinism.
    """
    contestants = [c for c in result.candidates if not c.is_nota]
    return sorted(contestants, key=lambda c: (-c.total_votes, c.name))


def _nota_candidate(result: PcResultRaw) -> PcCandidateRaw | None:
    for cand in result.candidates:
        if cand.is_nota:
            return cand
    return None


def observations_from_pc(
    *,
    result: PcResultRaw,
    period: Period,
    delim_year: int,
    party_lookup: PartyLookup,
    source_id: str,
    nota_introduced_year: int = 2013,
) -> list[ObservationRow]:
    """Emit candidate-* + pc-* rows for one Lok Sabha (PC) contest.

    Args:
        result: parsed PcResultRaw from ECI Report 33.
        period: decoded period (year, period_seq, period_label).
        delim_year: the delimitation cycle the PC belongs to (2008 for the
            current Lok Sabha boundaries).
        party_lookup: resolves party strings to canonical party_ids.
        source_id: FK to taxonomy/sources.parquet for the underlying ECI report.
        nota_introduced_year: year before which pc-nota-* must be null.

    Returns:
        Flat list of ObservationRow instances (observation_id auto-derived
        when the row is added to a BatchEnvelope).
    """
    rows: list[ObservationRow] = []
    pc_id = pc_entity_id(result.state_code, delim_year, result.pc_no)
    ranked = _ranked_non_nota(result)
    if not ranked:
        raise ValueError(
            f"PC {result.pc_name} ({result.state_code}) has no non-NOTA "
            f"candidates — cannot derive a winner"
        )

    valid = float(result.valid_votes) if result.valid_votes else None
    polled = float(result.total_votes_polled)

    # ---------------- candidate-scope (raw) ----------------
    for rank, cand in enumerate(ranked, start=1):
        cand_id = candidate_entity_id(pc_id, period.period_label, rank)
        rows.append(_obs(
            entity_id=cand_id, period=period,
            indicator_id="candidate-votes-polled",
            value_numeric=float(cand.total_votes),
            source_id=source_id, derivation="raw",
        ))
        if valid:
            rows.append(_obs(
                entity_id=cand_id, period=period,
                indicator_id="candidate-vote-share-pct",
                value_numeric=float(cand.total_votes) / valid * 100.0,
                source_id=source_id, derivation="ratio_pct",
            ))
        rows.append(_obs(
            entity_id=cand_id, period=period,
            indicator_id="candidate-rank",
            value_numeric=float(rank),
            source_id=source_id, derivation="raw",
        ))

    # ---------------- pc-scope (materialised) ----------------
    if result.total_electors is not None:
        rows.append(_obs(
            entity_id=pc_id, period=period,
            indicator_id="pc-total-electors",
            value_numeric=float(result.total_electors),
            source_id=source_id, derivation="raw",
        ))
    rows.append(_obs(
        entity_id=pc_id, period=period,
        indicator_id="pc-votes-polled",
        value_numeric=polled,
        source_id=source_id, derivation="raw",
    ))
    if result.total_electors:
        rows.append(_obs(
            entity_id=pc_id, period=period,
            indicator_id="pc-turnout-pct",
            value_numeric=polled / float(result.total_electors) * 100.0,
            source_id=source_id, derivation="ratio_pct",
        ))

    # NOTA — null pre-introduction, NOT zero (comparability trap). 2024 always
    # has NOTA since it was introduced in 2013.
    nota = _nota_candidate(result)
    if period.year >= nota_introduced_year and nota is not None:
        rows.append(_obs(
            entity_id=pc_id, period=period,
            indicator_id="pc-nota-votes",
            value_numeric=float(nota.total_votes),
            source_id=source_id, derivation="raw",
        ))
        rows.append(_obs(
            entity_id=pc_id, period=period,
            indicator_id="pc-nota-pct",
            value_numeric=float(nota.total_votes) / polled * 100.0,
            source_id=source_id, derivation="ratio_pct",
        ))

    # Winner identity (value_text, not numeric). Winner is rank 1 by sort.
    winner = ranked[0]
    winner_candidate_id = candidate_entity_id(pc_id, period.period_label, 1)
    rows.append(_obs(
        entity_id=pc_id, period=period,
        indicator_id="pc-winner-candidate-id",
        value_text=winner_candidate_id,
        source_id=source_id, derivation="argmax",
    ))
    winner_party_id = party_lookup.resolve(
        party_full=winner.party_name,
        is_independent=_is_independent(winner.party_name),
    )
    rows.append(_obs(
        entity_id=pc_id, period=period,
        indicator_id="pc-winner-party-id",
        value_text=winner_party_id,
        source_id=source_id, derivation="join",
    ))

    # Margin (winner − runner-up). A one-candidate field has no runner-up;
    # the contested-PC corpus (542 of 543) always has ≥2 contestants.
    if len(ranked) >= 2:
        margin_votes = winner.total_votes - ranked[1].total_votes
        rows.append(_obs(
            entity_id=pc_id, period=period,
            indicator_id="pc-margin-votes",
            value_numeric=float(margin_votes),
            source_id=source_id, derivation="diff",
        ))
        rows.append(_obs(
            entity_id=pc_id, period=period,
            indicator_id="pc-margin-pct",
            value_numeric=float(margin_votes) / polled * 100.0,
            source_id=source_id, derivation="ratio_pct",
        ))

    # Field size. ECI Report 33 ships the FULL field (no collapsed tail), so
    # pc-others-votes / pc-others-pct have no observations for this slice —
    # those indicators exist for sources that truncate to a top-N.
    rows.append(_obs(
        entity_id=pc_id, period=period,
        indicator_id="pc-candidates-total",
        value_numeric=float(len(ranked)),
        source_id=source_id, derivation="count",
    ))

    # Effective candidates (Laakso-Taagepera) from vote shares incl. NOTA.
    if valid:
        shares = [c.total_votes / valid for c in ranked]
        if nota is not None and period.year >= nota_introduced_year:
            shares.append(nota.total_votes / valid)
        ssq = sum(s * s for s in shares)
        if ssq > 0:
            rows.append(_obs(
                entity_id=pc_id, period=period,
                indicator_id="pc-effective-candidates-laakso",
                value_numeric=float(1.0 / ssq),
                source_id=source_id, derivation="laakso_taagepera",
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


def dim_rows_from_pc(
    *,
    result: PcResultRaw,
    delim_year: int,
    source_id: str,
) -> list[dict]:
    """Emit the PcDimRow payload for one PC contest.

    Returns plain dicts (not PcDimRow) so the driver wraps them in PcDimRow
    before envelope construction, matching the party_dim_rows convention.
    """
    pc_id = pc_entity_id(result.state_code, delim_year, result.pc_no)
    return [{
        "pc_id": pc_id,
        "state_code": result.state_code,
        "delim_year": delim_year,
        "pc_no": result.pc_no,
        "name": result.pc_name,
        "source_id": source_id,
    }]
