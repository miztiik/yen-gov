"""Private fixture builders for the emit-* test modules.

Builds small but realistic in-memory PartiesSnapshot + ConstituencyResult
objects, then returns their body_payload() dicts. The dicts match exactly
what `cli.py::run` would thread into the in-memory emitters, so tests
exercise the same shape as production.

Why not walk the real corpus (`datasets/elections/AcGenMay2026/S22/`)?
Per CLAUDE.md §10 anti-pattern: pytest tests CODE, not DATA. Walking real
on-disk artifacts inside pytest crosses that line — the data may legitimately
be absent or in a stale shape on a teammate's machine, and the test then fails
for "missing fixture" reasons that have nothing to do with the emitter. The
canonical-store conformance tests (test_canonical_eci_*) cover real-shape
coverage at a different tier.
"""

from __future__ import annotations

from yen_gov.core.models import (
    CandidateResult,
    ConstituencyResult,
    NotaResult,
    OthersBucket,
    PartiesSnapshot,
    PartyEntry,
    ResultTotals,
    SourceRef,
    WinnerInfo,
)


def parties_doc() -> dict:
    """A 3-party snapshot dict matching parties.json shape on disk."""
    snapshot = PartiesSnapshot(
        sources=[SourceRef(url="https://example.invalid/parties", fetched_at="2026-05-19T00:00:00Z")],
        election="AcGenMay2026",
        parties=[
            PartyEntry(eci_code="0136", short_name="AIADMK", full_name="All India Anna Dravida Munnetra Kazhagam"),
            PartyEntry(eci_code="0143", short_name="DMK", full_name="Dravida Munnetra Kazhagam"),
            PartyEntry(eci_code="0742", short_name="INC", full_name="Indian National Congress"),
        ],
    )
    return snapshot.body_payload()


def _constituency(eci_no: int, name: str, winner_party_short: str, winner_party_code: str) -> dict:
    """Build one ConstituencyResult dict with 5 candidates + NOTA + winner.

    Deterministic: same args produce identical dicts each call.
    """
    # Vote totals chosen so vote_share_pct values are clean decimals and
    # the winner / runner-up margin is large enough to be unambiguous.
    candidates = [
        CandidateResult(
            rank=1, name=f"Cand-1-AC{eci_no}", party_eci_code=winner_party_code,
            party_short=winner_party_short, votes=60_000, vote_share_pct=60.0, is_winner=True,
        ),
        CandidateResult(
            rank=2, name=f"Cand-2-AC{eci_no}", party_eci_code="0136" if winner_party_short != "AIADMK" else "0143",
            party_short="AIADMK" if winner_party_short != "AIADMK" else "DMK",
            votes=25_000, vote_share_pct=25.0, is_winner=False,
        ),
        CandidateResult(
            rank=3, name=f"Cand-3-AC{eci_no}", party_eci_code="0742",
            party_short="INC", votes=10_000, vote_share_pct=10.0, is_winner=False,
        ),
        CandidateResult(
            rank=4, name=f"Cand-4-AC{eci_no}", party_eci_code=None,
            party_short="IND", votes=3_000, vote_share_pct=3.0, is_winner=False,
        ),
        CandidateResult(
            rank=5, name=f"Cand-5-AC{eci_no}", party_eci_code=None,
            party_short="IND", votes=1_000, vote_share_pct=1.0, is_winner=False,
        ),
    ]
    cr = ConstituencyResult(
        sources=[SourceRef(url=f"https://example.invalid/ac/{eci_no}", fetched_at="2026-05-19T00:00:00Z")],
        election="AcGenMay2026",
        state="S22",
        body="AC",
        eci_no=eci_no,
        constituency_name=name,
        totals=ResultTotals(electors=150_000, votes_polled=100_000, turnout_pct=66.67),
        candidates=candidates,
        nota=NotaResult(votes=500, vote_share_pct=0.5),
        others=OthersBucket(candidate_count=2, votes=500, vote_share_pct=0.5),
        top_n_cutoff=5,
        winner=WinnerInfo(
            name=f"Cand-1-AC{eci_no}", party_eci_code=winner_party_code,
            party_short=winner_party_short, votes=60_000,
            margin_votes=35_000, margin_pct=35.0,
        ),
    )
    return cr.body_payload()


def constituencies() -> list[dict]:
    """A 3-AC slice of ConstituencyResult body dicts, two DMK wins + one AIADMK."""
    return [
        _constituency(eci_no=1, name="AC One", winner_party_short="DMK", winner_party_code="0143"),
        _constituency(eci_no=2, name="AC Two", winner_party_short="AIADMK", winner_party_code="0136"),
        _constituency(eci_no=3, name="AC Three", winner_party_short="DMK", winner_party_code="0143"),
    ]
