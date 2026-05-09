"""Parse ECI Statistical Report Section 10 — "Detailed Results" XLSX.

Section 10 is the per-AC per-candidate vote breakdown — the richest single
sheet in the Statistical Report family. Layout (header row at index 3):

    STATE/UT NAME | AC NO. | AC NAME | CANDIDATE NAME | GENDER | AGE |
    CATEGORY | PARTY | SYMBOL | GENERAL | POSTAL | TOTAL |
    %_OVER_VALID_NOTA | %_OVER_TOTAL_ELECTORS | TOTAL_ELECTORS

Rows after the header alternate between:

  - Candidate rows (one per contesting candidate, plus a NOTA row), with
    party SHORT codes (TVK, ADMK, INC, IND, NOTA, ...). Vote share columns
    are pre-computed by ECI; we use them as-authoritative per the authority
    hierarchy (sources-eci.md).
  - A "TURN OUT" sentinel row at the end of each AC, carrying the totals
    used elsewhere in the report (general + postal polled, turnout %).
  - A final "GRAND TOTAL:" row + Disclaimer rows at the bottom of the
    sheet — both ignored by the parser.

Two-step convention (mirrors HTML parsers in this package):

  - parse_detailed_results(xlsx_bytes) -> DetailedResultsRaw
        Pure XLSX -> data. Knows nothing about the schema, the election
        coordinates, or processing knobs.
  - to_constituency_results(raw, *, election, state, top_n, collapse_others,
                             sources)
        Emits one ConstituencyResult per AC, applying top_n / others
        collapsing the same way the HTML mapper does.

Party codes: Section 10 carries SHORT codes only (no numeric ECI code).
The parser leaves `party_eci_code` empty; the mapper (`to_constituency_results`)
optionally backfills it from a `{short_name → eci_code}` lookup, typically
built from the live-results partywise.htm snapshot via
`pipeline.compose.eci_code_by_short_from_partywise`. Without the lookup,
`party_eci_code` is None — the schema permits it.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from openpyxl import load_workbook

from yen_gov.core.models import (
    CandidateResult,
    ConstituencyResult,
    NotaResult,
    OthersBucket,
    ResultTotals,
    SourceRef,
    WinnerInfo,
)


_NOTA_TOKENS = {"nota", "none of the above"}
_INDEPENDENT_TOKENS = {"ind", "independent"}


@dataclass(frozen=True)
class CandidateRow:
    rank: int  # filled by mapper, not the parser
    name: str
    party_short: str  # raw text from the PARTY column (already short)
    is_nota: bool
    is_independent: bool
    votes_general: int
    votes_postal: int
    votes_total: int
    vote_share_pct: float  # over valid + NOTA, per ECI's own column


@dataclass(frozen=True)
class AcSection:
    state_name: str  # e.g. "Tamil Nadu"
    eci_no: int
    constituency_name: str  # uppercase per ECI; reservation suffix kept
    candidates: list[CandidateRow]  # includes NOTA, in sheet order
    polled_general: int  # from TURN OUT row (col 10)
    polled_postal: int  # from TURN OUT row (col 11)
    polled_total: int  # from TURN OUT row (col 12); == sum of candidate totals
    turnout_pct: float | None  # from TURN OUT row (col 14); None if "-"
    total_electors: int | None  # from any candidate row (col 15); constant per AC


@dataclass(frozen=True)
class DetailedResultsRaw:
    state_name: str
    sections: list[AcSection]


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def parse_detailed_results(content: bytes) -> DetailedResultsRaw:
    """Parse Section 10 XLSX bytes into AC sections.

    Raises ValueError on structural surprises (header missing, AC section
    without a TURN OUT row, no sections at all). Same fail-loud posture as
    the HTML parsers — silent partials would let a sheet-shape change go
    unnoticed.
    """
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    header_idx = _find_header_row(rows)
    sections: list[AcSection] = []
    state_name: str | None = None
    current: list[CandidateRow] = []
    current_eci_no: int | None = None
    current_ac_name: str | None = None
    current_state: str | None = None
    current_electors: int | None = None

    for raw_row in rows[header_idx + 1:]:
        if raw_row is None or all(c is None for c in raw_row):
            continue
        first = raw_row[0]

        # End-of-AC sentinel
        if isinstance(first, str) and first.strip().upper() == "TURN OUT":
            if current_eci_no is None or not current:
                raise ValueError(
                    f"TURN OUT row with no preceding candidates "
                    f"(eci_no={current_eci_no})"
                )
            polled_general = _to_int(raw_row[9])
            polled_postal = _to_int(raw_row[10])
            polled_total = _to_int(raw_row[11])
            turnout_pct = _to_float_or_none(raw_row[13])
            sections.append(
                AcSection(
                    state_name=current_state or "",
                    eci_no=current_eci_no,
                    constituency_name=current_ac_name or "",
                    candidates=current,
                    polled_general=polled_general,
                    polled_postal=polled_postal,
                    polled_total=polled_total,
                    turnout_pct=turnout_pct,
                    total_electors=current_electors,
                )
            )
            current = []
            current_eci_no = None
            current_ac_name = None
            current_state = None
            current_electors = None
            continue

        # State-level grand total or disclaimer at the bottom — stop.
        if isinstance(first, str) and (
            first.strip().upper().startswith("GRAND TOTAL")
            or first.strip().lower().startswith("disclaimer")
            or first.strip().lower().startswith("this report is based on")
        ):
            break

        # Candidate row
        ac_no = raw_row[1]
        if not isinstance(ac_no, int):
            continue  # skip stray header repeats / spacer rows
        if state_name is None:
            state_name = str(first).strip() if first else ""
        if current_eci_no is None:
            current_eci_no = ac_no
            current_ac_name = str(raw_row[2]).strip() if raw_row[2] else ""
            current_state = str(first).strip() if first else state_name
        elif current_eci_no != ac_no:
            raise ValueError(
                f"AC #{ac_no} starts before the previous TURN OUT row "
                f"(was building #{current_eci_no})"
            )

        cand = _row_to_candidate(raw_row)
        current.append(cand)
        if current_electors is None and isinstance(raw_row[14], (int, float)):
            current_electors = int(raw_row[14])

    if current:
        raise ValueError(
            f"trailing AC #{current_eci_no} has no TURN OUT row"
        )
    if not sections:
        raise ValueError("no AC sections parsed from Section 10 XLSX")

    return DetailedResultsRaw(
        state_name=state_name or sections[0].state_name,
        sections=sections,
    )


def _find_header_row(rows: list[tuple]) -> int:
    for i, r in enumerate(rows):
        if r and isinstance(r[0], str) and r[0].strip().upper().startswith("STATE"):
            if r[1] and "AC" in str(r[1]).upper():
                return i
    raise ValueError(
        "Section 10 header row (STATE/UT NAME | AC NO. | ...) not found"
    )


def _row_to_candidate(raw_row: tuple) -> CandidateRow:
    name = str(raw_row[3]).strip() if raw_row[3] else ""
    party = str(raw_row[7]).strip() if raw_row[7] else ""
    party_lower = party.lower()
    is_nota = party_lower in _NOTA_TOKENS
    is_ind = party_lower in _INDEPENDENT_TOKENS
    return CandidateRow(
        rank=0,
        name=_strip_leading_serial(name),
        party_short=party if party else "IND",
        is_nota=is_nota,
        is_independent=is_ind,
        votes_general=_to_int(raw_row[9]),
        votes_postal=_to_int(raw_row[10]),
        votes_total=_to_int(raw_row[11]),
        vote_share_pct=_to_float(raw_row[12]),
    )


def _strip_leading_serial(name: str) -> str:
    """ECI prefixes the row's serial (e.g. '1 S.vijayakumar'). Strip it."""
    parts = name.split(" ", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1].strip()
    return name


def _to_int(value: object) -> int:
    if value is None or value == "" or value == "-":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().replace(",", "")
    if not s or s == "-":
        return 0
    return int(float(s))


def _to_float(value: object) -> float:
    if value is None or value == "" or value == "-":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().rstrip("%").replace(",", "")
    if not s or s == "-":
        return 0.0
    return float(s)


def _to_float_or_none(value: object) -> float | None:
    if value is None or value == "" or value == "-":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().rstrip("%").replace(",", "")
    if not s or s == "-":
        return None
    return float(s)


# ---------------------------------------------------------------------------
# raw -> schema-bound model
# ---------------------------------------------------------------------------

def to_constituency_results(
    raw: DetailedResultsRaw,
    *,
    election: str,
    state: str,
    top_n: int,
    collapse_others: bool,
    sources: list[SourceRef],
    party_eci_codes: dict[str, str] | None = None,
) -> list[ConstituencyResult]:
    """Build one ConstituencyResult per AC section.

    Mirrors `constituencywise.to_constituency_result` semantics: rank by
    total votes desc, take top_n as candidates, NOTA broken out, optional
    collapsed `others` bucket, winner derived from rank-1 row with margin
    over runner-up.

    Optional `party_eci_codes` is a {short_name → numeric_code} lookup used
    to backfill `party_eci_code` (Section 10 carries short codes only).
    Independents and unmapped shorts get `None`.

    **Countermanded ACs are skipped silently.** ECI publishes Section 10
    rows for postponed/countermanded constituencies as a single NOTA row
    with all-zero votes and polled_total=0 (e.g. WB 2026 AC #144 FALTA).
    The schema requires `candidates: minItems: 1` and a non-zero winner —
    representing "no result" with a stub would be misleading. Skipping
    leaves a gap in the per-AC file sequence that consumers can detect.
    Caller can compare `len(out)` to `len(raw.sections)` to count skips.
    """
    codes = party_eci_codes or {}
    def _code_for(short: str, is_ind: bool) -> str | None:
        if is_ind:
            return None
        return codes.get(short)
    out: list[ConstituencyResult] = []
    for sec in raw.sections:
        if sec.polled_total == 0:
            continue  # countermanded / postponed — no result to emit
        nota_row = next((c for c in sec.candidates if c.is_nota), None)
        contestants = [c for c in sec.candidates if not c.is_nota]
        contestants.sort(key=lambda c: c.votes_total, reverse=True)
        if not contestants:
            raise ValueError(f"AC #{sec.eci_no} has no non-NOTA candidates")
        if nota_row is None:
            raise ValueError(f"AC #{sec.eci_no} has no NOTA row")

        ranked = [
            CandidateRow(
                rank=i + 1,
                name=c.name, party_short=c.party_short, is_nota=False,
                is_independent=c.is_independent,
                votes_general=c.votes_general, votes_postal=c.votes_postal,
                votes_total=c.votes_total, vote_share_pct=c.vote_share_pct,
            )
            for i, c in enumerate(contestants)
        ]
        kept, rest = ranked[:top_n], ranked[top_n:]

        candidates_model = [
            CandidateResult(
                rank=row.rank,
                name=row.name,
                party_eci_code=_code_for(row.party_short, row.is_independent),
                party_short="IND" if row.is_independent else row.party_short,
                votes=row.votes_total,
                vote_share_pct=row.vote_share_pct,
                is_winner=(row.rank == 1) or None,
            )
            for row in kept
        ]
        others_model: OthersBucket | None = None
        if collapse_others and rest:
            others_model = OthersBucket(
                candidate_count=len(rest),
                votes=sum(r.votes_total for r in rest),
                vote_share_pct=round(sum(r.vote_share_pct for r in rest), 2),
            )

        winner = ranked[0]
        runner_up_votes = ranked[1].votes_total if len(ranked) >= 2 else 0
        margin_votes = winner.votes_total - runner_up_votes
        margin_pct = (
            (margin_votes / sec.polled_total * 100.0)
            if sec.polled_total > 0 else 0.0
        )

        out.append(ConstituencyResult(
            sources=sources,
            election=election,
            state=state,
            body="AC",
            eci_no=sec.eci_no,
            constituency_name=sec.constituency_name,
            totals=ResultTotals(
                electors=sec.total_electors,
                votes_polled=sec.polled_total,
                turnout_pct=sec.turnout_pct,
            ),
            candidates=candidates_model,
            nota=NotaResult(
                votes=nota_row.votes_total,
                vote_share_pct=nota_row.vote_share_pct,
            ),
            others=others_model,
            top_n_cutoff=top_n,
            winner=WinnerInfo(
                name=winner.name,
                party_eci_code=_code_for(winner.party_short, winner.is_independent),
                party_short="IND" if winner.is_independent else winner.party_short,
                votes=winner.votes_total,
                margin_votes=margin_votes,
                margin_pct=round(margin_pct, 2),
            ),
        ))
    return out
