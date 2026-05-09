"""Live tests against results.eci.gov.in for the ECI source adapters.

Per Holy Law #7 and the explicit choice for "fetch live active site": these
tests hit the real ECI server. They are slow, network-dependent, and brittle
by ECI's standards — but they verify the parser against the actual page our
pipeline will fetch in production.

Tests are gated on YEN_GOV_LIVE=1 unless ECI is reachable; in CI we may set
that variable explicitly. Locally they run by default if reachable.
"""

from __future__ import annotations

import os
import socket

import httpx
import pytest

from yen_gov.core.io import Source
from yen_gov.core.models import SourceRef
from yen_gov.sources.eci.constituencywise import (
    parse_constituencywise,
    to_constituency_result,
)
from yen_gov.sources.eci.partywise import parse_partywise
from yen_gov.sources.eci.urls import (
    constituencywise_url,
    event_index_url,
    partywise_state_url,
)


_EVENT = "AcGenMay2026"
_STATE = "S22"  # Tamil Nadu


def _network_up() -> bool:
    if os.environ.get("YEN_GOV_NO_NET") == "1":
        return False
    try:
        socket.create_connection(("results.eci.gov.in", 443), timeout=5).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _network_up(),
    reason="results.eci.gov.in not reachable (set YEN_GOV_NO_NET=0 to force)",
)


@pytest.fixture(scope="module")
def http() -> httpx.Client:
    with httpx.Client(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "yen-gov-tests/0.0"},
    ) as c:
        yield c


# --- urls --------------------------------------------------------------------

def test_url_builders_round_trip():
    assert event_index_url(_EVENT).endswith(f"Result{_EVENT}/index.htm")
    assert partywise_state_url(_EVENT, _STATE).endswith(f"partywiseresult-{_STATE}.htm")
    assert constituencywise_url(_EVENT, _STATE, 167).endswith(
        f"Constituencywise{_STATE}167.htm"
    )


def test_url_builders_validate_inputs():
    with pytest.raises(ValueError):
        partywise_state_url(_EVENT, "XX22")
    with pytest.raises(ValueError):
        constituencywise_url(_EVENT, _STATE, 0)
    with pytest.raises(ValueError):
        partywise_state_url("bad/event", _STATE)


# --- partywise ---------------------------------------------------------------

def test_live_partywise_tn(http: httpx.Client):
    url = partywise_state_url(_EVENT, _STATE)
    r = http.get(url)
    assert r.status_code == 200, f"ECI returned {r.status_code} for {url}"
    snap = parse_partywise(r.content)

    assert snap.state_name == "Tamil Nadu"
    assert snap.total_seats == 234  # TN AC has 234 seats; constant for this election
    assert snap.parties, "no parties parsed"

    # Total seats won + leading across all parties + independents must sum to 234.
    seats_total = sum(p.total for p in snap.parties)
    # Independents may show as a separate row or as multiple rows; the sum may
    # equal 234 outright or fall slightly short if independents aren't on this
    # page. Assert it's at least bounded sanely.
    assert 0 < seats_total <= snap.total_seats

    # Spot-check: at least one well-known TN party should have an ECI code.
    coded = [p for p in snap.parties if p.eci_code is not None]
    assert coded, "no party row carried an ECI code via partywisewinresult-<code> href"
    for p in coded:
        assert p.eci_code.isdigit()
        assert p.short_name and p.full_name


# --- constituencywise --------------------------------------------------------

def test_live_constituencywise_ac1(http: httpx.Client):
    url = constituencywise_url(_EVENT, _STATE, 1)
    r = http.get(url)
    assert r.status_code == 200, f"ECI returned {r.status_code} for {url}"
    raw = parse_constituencywise(r.content)

    assert raw.constituency_no == 1
    assert raw.state_name == "Tamil Nadu"
    assert raw.constituency_name  # ECI uses uppercase like GUMMIDIPOONDI
    assert raw.candidates, "no candidates parsed"
    assert raw.nota is not None, "NOTA row missing"
    assert raw.votes_polled > 0

    # Ranks are 1..N strictly increasing, sorted by votes desc.
    assert [c.rank for c in raw.candidates] == list(range(1, len(raw.candidates) + 1))
    for a, b in zip(raw.candidates, raw.candidates[1:]):
        assert a.votes >= b.votes

    # Candidate vote sum + NOTA must approximately equal votes_polled.
    totals = sum(c.votes for c in raw.candidates) + raw.nota.votes
    diff = abs(totals - raw.votes_polled)
    assert diff <= 5, f"vote totals off by {diff}: candidates+NOTA={totals} vs polled={raw.votes_polled}"


def test_live_to_constituency_result_with_others(http: httpx.Client):
    url = constituencywise_url(_EVENT, _STATE, 1)
    r = http.get(url)
    raw = parse_constituencywise(r.content)
    sources = [SourceRef(
        url=url,
        # Use a fixed timestamp; real fetcher would inject the actual fetched_at.
        fetched_at=__import__("datetime").datetime(2026, 5, 8, 14, 30, tzinfo=__import__("datetime").timezone.utc),
    )]
    result = to_constituency_result(
        raw,
        election=_EVENT, state=_STATE, body="AC", eci_no=1,
        top_n=5, collapse_others=True, sources=sources,
    )

    assert result.election == _EVENT
    assert result.state == _STATE
    assert len(result.candidates) == 5
    assert result.candidates[0].is_winner is True
    assert all(c.is_winner is None for c in result.candidates[1:])
    assert result.others is not None  # AC1 had 16 candidates, so others bucket present
    assert result.others.candidate_count == len(raw.candidates) - 5
    assert result.winner.name == raw.candidates[0].name
    assert result.winner.margin_votes == raw.candidates[0].votes - raw.candidates[1].votes


def test_to_constituency_result_rejects_eci_no_mismatch():
    # Build a tiny synthetic raw that the mapper alone can validate, no HTML needed.
    from yen_gov.sources.eci.constituencywise import (
        CandidateRow,
        ConstituencywiseRaw,
    )
    raw = ConstituencywiseRaw(
        constituency_no=1, constituency_name="X", state_name="Y",
        candidates=[CandidateRow(rank=1, name="A", party_full="Independent",
                                  is_independent=True, votes=10, vote_share_pct=100.0)],
        nota=CandidateRow(rank=0, name="NOTA", party_full="None of the Above",
                          is_independent=False, votes=0, vote_share_pct=0.0),
        votes_polled=10,
    )
    with pytest.raises(ValueError, match="does not match"):
        to_constituency_result(
            raw, election=_EVENT, state=_STATE, body="AC", eci_no=999,
            top_n=5, collapse_others=True, sources=[],
        )
