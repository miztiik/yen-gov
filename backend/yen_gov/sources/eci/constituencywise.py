"""Parse ECI Constituencywise<state><n>.htm.

The constituencywise page is the atomic election artifact: one row per
candidate (plus NOTA), votes split into EVM/postal/total/share, plus a
tfoot "Total" row giving the polled-vote sum.

Two-step design (kept separate for testability):

  - parse_constituencywise(bytes) -> ConstituencywiseRaw
      Pure HTML→data. No knowledge of the schema, the election context, or
      the top-N cutoff. Easy to test against a saved or live page.
  - to_constituency_result(raw, ...) -> ConstituencyResult
      Adds election/state/body/eci_no (from the URL/config — not the page),
      applies the top_n_candidates / collapse_others knobs from
      processing.json, derives winner+margin, and emits the schema-bound
      pydantic model. Pure transformation; no I/O, no parsing.

The page does NOT carry party short codes or ECI numeric party codes —
only full party names. Schema requires `party_short` to be non-empty, so
without an external party lookup we put the full name into party_short and
leave party_eci_code as None. This is a known data-quality compromise; the
pipeline can fill both from a partywise snapshot when one is available.
See docs/architecture/backend/sources-eci.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import html as lxml_html

from yen_gov.core.models import (
    CandidateResult,
    ConstituencyResult,
    NotaResult,
    OthersBucket,
    ResultTotals,
    SourceRef,
    WinnerInfo,
)


_HEADER_RE = re.compile(
    r"^\s*(?P<no>\d+)\s*-\s*(?P<name>.+?)\s*$",
    re.IGNORECASE,
)
_NOTA_PARTY_NAMES = {"none of the above", "nota"}
_INDEPENDENT_PARTY_NAMES = {"independent", "ind"}


@dataclass(frozen=True)
class CandidateRow:
    rank: int  # 1-based, descending by votes
    name: str
    party_full: str  # raw party text from the page
    is_independent: bool
    votes: int
    vote_share_pct: float


@dataclass(frozen=True)
class ConstituencywiseRaw:
    """Raw structured form of a Constituencywise<state><n>.htm page.

    Coordinates that the URL/config supplies (election, state code, body,
    eci_no) are NOT carried here — the to_constituency_result mapper merges
    them with the page-derived data.
    """

    constituency_no: int  # from page header (sanity-check vs URL)
    constituency_name: str  # uppercase per ECI convention; left as-is
    state_name: str  # human-readable from header, e.g. "Tamil Nadu"
    candidates: list[CandidateRow]  # excludes NOTA, sorted by votes desc
    nota: CandidateRow | None
    votes_polled: int  # tfoot grand total


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def parse_constituencywise(content: bytes) -> ConstituencywiseRaw:
    doc = lxml_html.fromstring(content)
    no, name, state = _parse_header(doc)
    table = _find_results_table(doc)
    rows, nota_row = _parse_rows(table)
    votes_polled = _parse_total_polled(table)
    if not rows and nota_row is None:
        raise ValueError("constituencywise page contained no candidate rows")
    return ConstituencywiseRaw(
        constituency_no=no,
        constituency_name=name,
        state_name=state,
        candidates=rows,
        nota=nota_row,
        votes_polled=votes_polled,
    )


def _parse_header(doc) -> tuple[int, str, str]:
    # <h2>Assembly Constituency <span> N - NAME<Strong> (State)</Strong></span></h2>
    h2s = doc.xpath("//h2[.//span]")
    for h2 in h2s:
        span = h2.xpath(".//span")[0]
        # The state lives inside an inner <strong> as "(State)". Pull it out
        # before reading the rest of the span text.
        strong_text = ""
        strongs = span.xpath(".//strong | .//Strong")
        if strongs:
            strong_text = strongs[0].text_content().strip()
        # Remove the strong subtree from a copy so " N - NAME" remains.
        span_copy = lxml_html.fromstring(lxml_html.tostring(span))
        for s in span_copy.xpath(".//strong | .//Strong"):
            s.getparent().remove(s)
        head_text = " ".join(span_copy.text_content().split())
        m = _HEADER_RE.match(head_text)
        if not m:
            continue
        state_name = strong_text.strip("()").strip()
        if not state_name:
            continue
        return int(m.group("no")), m.group("name").strip(), state_name
    raise ValueError("constituencywise page header (N - NAME (State)) not found")


def _find_results_table(doc):
    for table in doc.xpath("//table"):
        headers = [th.text_content().strip().lower() for th in table.xpath(".//thead//th")]
        # Expected: S.N. | Candidate | Party | EVM Votes | Postal Votes | Total Votes | % of Votes
        if (
            len(headers) >= 7
            and "candidate" in headers[1]
            and "party" in headers[2]
            and "total" in headers[5]
        ):
            return table
    raise ValueError(
        "could not find constituencywise results table "
        "(expected S.N.|Candidate|Party|EVM|Postal|Total|%)"
    )


def _parse_rows(table) -> tuple[list[CandidateRow], CandidateRow | None]:
    candidates: list[tuple[int, str, str, int, float]] = []  # (votes, name, party, total, pct)
    nota: CandidateRow | None = None
    for tr in table.xpath(".//tbody/tr"):
        tds = tr.xpath("./td")
        if len(tds) < 7:
            continue
        name = tds[1].text_content().strip()
        party = tds[2].text_content().strip()
        total = _parse_int(tds[5].text_content())
        pct = _parse_float(tds[6].text_content())
        if party.lower() in _NOTA_PARTY_NAMES or name.lower() in _NOTA_PARTY_NAMES:
            nota = CandidateRow(
                rank=0, name="NOTA", party_full=party,
                is_independent=False, votes=total, vote_share_pct=pct,
            )
            continue
        candidates.append((total, name, party, total, pct))
    candidates.sort(key=lambda r: r[0], reverse=True)
    out: list[CandidateRow] = []
    for rank, (_, name, party, total, pct) in enumerate(candidates, start=1):
        out.append(CandidateRow(
            rank=rank,
            name=name,
            party_full=party,
            is_independent=party.lower() in _INDEPENDENT_PARTY_NAMES,
            votes=total,
            vote_share_pct=pct,
        ))
    return out, nota


def _parse_total_polled(table) -> int:
    # Footer row layout: blank | "Total" | blank | EVM total | Postal total | Grand total | blank
    for tr in table.xpath(".//tfoot/tr"):
        cells = tr.xpath("./th | ./td")
        if len(cells) < 6:
            continue
        labels = [c.text_content().strip().lower() for c in cells]
        if "total" in labels:
            return _parse_int(cells[5].text_content())
    raise ValueError("constituencywise tfoot Total row not found")


def _parse_int(text: str) -> int:
    s = text.strip().replace(",", "")
    if not s or s == "\u00a0":
        return 0
    return int(s)


def _parse_float(text: str) -> float:
    s = text.strip().replace(",", "").rstrip("%").strip()
    if not s:
        return 0.0
    return float(s)


# ---------------------------------------------------------------------------
# raw → schema-bound model
# ---------------------------------------------------------------------------

def to_constituency_result(
    raw: ConstituencywiseRaw,
    *,
    election: str,
    state: str,
    body: str,
    eci_no: int,
    top_n: int,
    collapse_others: bool,
    sources: list[SourceRef],
    party_lookup: dict[str, tuple[str, str]] | None = None,
) -> ConstituencyResult:
    """Build a ConstituencyResult from a parsed page + caller-supplied context.

    Args:
        raw: the parsed page.
        election, state, body, eci_no: identity coordinates not present in the
            page itself (see docs/architecture/backend/sources-eci.md). `eci_no` is sanity-checked against
            raw.constituency_no.
        top_n: processing.results.top_n_candidates.
        collapse_others: processing.results.collapse_others.
        sources: provenance entries to stamp.
        party_lookup: optional mapping from full party name to (short, eci_code).
            When absent, party_short = full name and party_eci_code = None.

    Raises ValueError on schema-violating inputs (mismatched eci_no, empty
    candidate list, NOTA missing).
    """
    if raw.constituency_no != eci_no:
        raise ValueError(
            f"page header constituency #{raw.constituency_no} does not match URL eci_no={eci_no}"
        )
    if not raw.candidates:
        raise ValueError("no candidates parsed; cannot build ConstituencyResult")
    if raw.nota is None:
        raise ValueError("no NOTA row parsed; ConstituencyResult schema requires nota")

    kept = raw.candidates[:top_n]
    rest = raw.candidates[top_n:]
    candidates_model = [
        _to_candidate_model(row, party_lookup, is_winner=(row.rank == 1))
        for row in kept
    ]
    others_model: OthersBucket | None = None
    if collapse_others and rest:
        others_model = OthersBucket(
            candidate_count=len(rest),
            votes=sum(r.votes for r in rest),
            vote_share_pct=round(sum(r.vote_share_pct for r in rest), 2),
        )

    winner_row = raw.candidates[0]
    runner_up_votes = raw.candidates[1].votes if len(raw.candidates) >= 2 else 0
    margin_votes = winner_row.votes - runner_up_votes
    margin_pct = (margin_votes / raw.votes_polled * 100.0) if raw.votes_polled > 0 else 0.0
    winner_short, winner_code = _resolve_party(winner_row, party_lookup)

    return ConstituencyResult(
        sources=sources,
        election=election,
        state=state,
        body=body,
        eci_no=eci_no,
        constituency_name=raw.constituency_name,
        totals=ResultTotals(votes_polled=raw.votes_polled),
        candidates=candidates_model,
        nota=NotaResult(votes=raw.nota.votes, vote_share_pct=raw.nota.vote_share_pct),
        others=others_model,
        top_n_cutoff=top_n,
        winner=WinnerInfo(
            name=winner_row.name,
            party_eci_code=winner_code,
            party_short=winner_short,
            votes=winner_row.votes,
            margin_votes=margin_votes,
            margin_pct=round(margin_pct, 2),
        ),
    )


def _to_candidate_model(
    row: CandidateRow,
    party_lookup: dict[str, tuple[str, str]] | None,
    *,
    is_winner: bool,
) -> CandidateResult:
    short, code = _resolve_party(row, party_lookup)
    return CandidateResult(
        rank=row.rank,
        name=row.name,
        party_eci_code=code,
        party_short=short,
        votes=row.votes,
        vote_share_pct=row.vote_share_pct,
        is_winner=is_winner if is_winner else None,
    )


def _resolve_party(
    row: CandidateRow,
    party_lookup: dict[str, tuple[str, str]] | None,
) -> tuple[str, str | None]:
    if row.is_independent:
        return "IND", None
    if party_lookup is not None:
        hit = party_lookup.get(row.party_full)
        if hit is not None:
            return hit
    # Fallback: use the full name as the short. Schema only requires non-empty.
    return row.party_full, None
