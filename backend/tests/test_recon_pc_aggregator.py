"""Tier-A tests for the per-PC Compare-Aggregator (PR-PC-LS2024).

Covers:

  - ``compare_per_pc`` groups by ``(state_code, constituency_no)``
    and applies the Fowler machine-decidable verdict rule.
  - Single-oracle PC -> ``UNVERIFIED`` (n_oracles_present < 2).
  - All-oracles-agree -> ``VERIFIED`` (n_agreeing == n_present and
    n_present >= 2).
  - Mixed-oracles -> ``DISPUTED`` (modal party id, agreeing set
    surfaced for curator).
  - Malformed rows (empty state_code or constituency_no) are
    skipped silently (the adapter should not emit them; the
    aggregator's invariant).
  - ``write_pc_verdict_csv`` round-trip header + None-as-empty.
  - ``_modal_party`` tie-break is deterministic (alpha-min wins).

Per CLAUDE.md section 14 the aggregator is exercised against
in-memory fixtures (NOT the real corpus). All fixtures are
hand-built; no real-CSV writes.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.recon.pc_aggregator import (
    PcVerdictRow,
    _modal_party,
    compare_per_pc,
    pc_verdict_csv_header,
    write_pc_verdict_csv,
)
from yen_gov.canonical.recon.shape_a import ShapeARow


def _pc_shape_a(
    *,
    scope: str,
    state: str,
    cno: str,
    cname: str,
    party_id: str,
    candidate: str = "X CANDIDATE",
    votes: int | None = 100000,
) -> ShapeARow:
    """Tiny per-PC ShapeARow factory."""
    return ShapeARow(
        external_key=f"{state}:{cno}:{cname}",
        external_short=party_id.rsplit(".", 1)[-1],
        external_full=candidate,
        external_scope=scope,
        external_vintage="2024",
        proposed_party_id=party_id,
        proposed_action="match",
        notes=None,
        constituency_no=cno,
        constituency_name=cname,
        state_code=state,
        winner_candidate=candidate,
        winner_votes=votes,
    )


# --- VERDICT RULE: VERIFIED / UNVERIFIED / DISPUTED -----------------------


def test_compare_per_pc_verified_when_2_oracles_agree():
    """Both oracles vote BJP -> VERIFIED, agreeing list = both scopes."""
    rows = [
        _pc_shape_a(
            scope="bhukyavenkatamahesh-pc",
            state="andhra-pradesh",
            cno="411",
            cname="AMALAPURAM",
            party_id="parties.IN.TDP",
        ),
        _pc_shape_a(
            scope="yen-gov-canonical-pc",
            state="andhra-pradesh",
            cno="411",
            cname="AMALAPURAM",
            party_id="parties.IN.TDP",
        ),
    ]
    canonical = {"parties.IN.TDP": {"party_id": "parties.IN.TDP"}}
    verdicts = compare_per_pc(rows, canonical)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.state_code == "andhra-pradesh"
    assert v.constituency_no == "411"
    assert v.constituency_name == "AMALAPURAM"
    assert v.verdict == "VERIFIED"
    assert v.n_oracles_present == 2
    assert v.n_oracles_agreeing == 2
    assert v.winner_party_id_consensus == "parties.IN.TDP"
    assert v.oracles_disagreeing == ""
    assert v.curator_note is None


def test_compare_per_pc_unverified_when_single_oracle():
    """Only bhuky has the PC (Surat 2024) -> UNVERIFIED + 1 oracle."""
    rows = [
        _pc_shape_a(
            scope="bhukyavenkatamahesh-pc",
            state="gujarat",
            cno="?",
            cname="SURAT",
            party_id="parties.IN.BJP",
            votes=None,
        ),
    ]
    canonical = {"parties.IN.BJP": {"party_id": "parties.IN.BJP"}}
    verdicts = compare_per_pc(rows, canonical)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.verdict == "UNVERIFIED"
    assert v.n_oracles_present == 1
    assert v.n_oracles_agreeing == 1
    assert v.winner_party_id_consensus == "parties.IN.BJP"


def test_compare_per_pc_disputed_when_oracles_disagree():
    """bhuky says JSP, canonical says JP -> DISPUTED + curator_note."""
    rows = [
        _pc_shape_a(
            scope="bhukyavenkatamahesh-pc",
            state="andhra-pradesh",
            cno="424",
            cname="KAKINADA",
            party_id="parties.IN.JSP",
        ),
        _pc_shape_a(
            scope="yen-gov-canonical-pc",
            state="andhra-pradesh",
            cno="424",
            cname="KAKINADA",
            party_id="parties.IN.JP",
        ),
    ]
    canonical = {
        "parties.IN.JSP": {"party_id": "parties.IN.JSP"},
        "parties.IN.JP": {"party_id": "parties.IN.JP"},
    }
    verdicts = compare_per_pc(rows, canonical)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.verdict == "DISPUTED"
    assert v.n_oracles_present == 2
    assert v.n_oracles_agreeing == 1
    # Tie-break: parties.IN.JP < parties.IN.JSP alpha-sort, so JP wins
    # the modal tie. The agreeing set is then yen-gov-canonical-pc.
    assert v.winner_party_id_consensus == "parties.IN.JP"
    assert v.oracles_agreeing == "yen-gov-canonical-pc"
    assert v.oracles_disagreeing == "bhukyavenkatamahesh-pc"
    assert v.curator_note is not None
    assert "disagreeing" in v.curator_note


def test_compare_per_pc_2_of_3_majority_wins_when_third_disagrees():
    """3 oracles, 2 vote AAP, 1 votes UNK -> DISPUTED, AAP consensus."""
    rows = [
        _pc_shape_a(
            scope="bhukyavenkatamahesh-pc",
            state="punjab",
            cno="12",
            cname="ANANDPUR SAHIB",
            party_id="parties.IN.AAP",
        ),
        _pc_shape_a(
            scope="tcpd-pc",
            state="punjab",
            cno="12",
            cname="ANANDPUR SAHIB",
            party_id="parties.IN.AAP",
        ),
        _pc_shape_a(
            scope="yen-gov-canonical-pc",
            state="punjab",
            cno="12",
            cname="ANANDPUR SAHIB",
            party_id="parties.IN.UNK",
        ),
    ]
    canonical = {"parties.IN.AAP": {"party_id": "parties.IN.AAP"}}
    verdicts = compare_per_pc(rows, canonical)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.verdict == "DISPUTED"
    assert v.n_oracles_present == 3
    assert v.n_oracles_agreeing == 2
    assert v.winner_party_id_consensus == "parties.IN.AAP"
    assert v.oracles_agreeing == "bhukyavenkatamahesh-pc|tcpd-pc"


def test_compare_per_pc_verified_when_3_of_3_agree():
    """3 oracles all vote BJP -> VERIFIED with 3 agreeing."""
    rows = [
        _pc_shape_a(
            scope="bhukyavenkatamahesh-pc",
            state="uttar-pradesh",
            cno="50",
            cname="VARANASI",
            party_id="parties.IN.BJP",
        ),
        _pc_shape_a(
            scope="tcpd-pc",
            state="uttar-pradesh",
            cno="50",
            cname="VARANASI",
            party_id="parties.IN.BJP",
        ),
        _pc_shape_a(
            scope="yen-gov-canonical-pc",
            state="uttar-pradesh",
            cno="50",
            cname="VARANASI",
            party_id="parties.IN.BJP",
        ),
    ]
    canonical = {"parties.IN.BJP": {"party_id": "parties.IN.BJP"}}
    verdicts = compare_per_pc(rows, canonical)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.verdict == "VERIFIED"
    assert v.n_oracles_present == 3
    assert v.n_oracles_agreeing == 3


def test_compare_per_pc_consensus_party_id_not_in_canonical_surfaces_note():
    """Consensus party_id absent from canonical -> curator_note flag."""
    rows = [
        _pc_shape_a(
            scope="bhukyavenkatamahesh-pc",
            state="meghalaya",
            cno="201",
            cname="SHILLONG",
            party_id="parties.IN.VPP",
        ),
        _pc_shape_a(
            scope="yen-gov-canonical-pc",
            state="meghalaya",
            cno="201",
            cname="SHILLONG",
            party_id="parties.IN.VPP",
        ),
    ]
    # parties.IN.VPP intentionally absent from canonical.
    canonical: dict[str, dict[str, object]] = {}
    verdicts = compare_per_pc(rows, canonical)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.verdict == "VERIFIED"  # both oracles agree
    assert v.winner_party_id_consensus == "parties.IN.VPP"
    assert v.curator_note is not None
    assert "not in parties.csv" in v.curator_note


def test_compare_per_pc_sentinel_party_id_not_surfaced_as_missing():
    """Consensus = parties.IN.UNK / IND / NOTA: no curator_note about FK."""
    rows = [
        _pc_shape_a(
            scope="bhukyavenkatamahesh-pc",
            state="andhra-pradesh",
            cno="999",
            cname="TEST",
            party_id="parties.IN.UNK",
        ),
        _pc_shape_a(
            scope="yen-gov-canonical-pc",
            state="andhra-pradesh",
            cno="999",
            cname="TEST",
            party_id="parties.IN.UNK",
        ),
    ]
    # Even with parties.IN.UNK absent from canonical, sentinel suppresses
    # the curator_note. (The PR-0 sentinel rows guarantee UNK / IND /
    # NOTA exist in parties.csv anyway; the test exercises the guard.)
    canonical: dict[str, dict[str, object]] = {}
    verdicts = compare_per_pc(rows, canonical)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.verdict == "VERIFIED"
    assert v.winner_party_id_consensus == "parties.IN.UNK"
    assert v.curator_note is None


def test_compare_per_pc_skips_rows_with_empty_state_code():
    """Malformed shape-A rows missing state_code are skipped silently."""
    rows = [
        _pc_shape_a(
            scope="x",
            state="",  # empty
            cno="1",
            cname="X",
            party_id="parties.IN.X",
        ),
        _pc_shape_a(
            scope="x",
            state="ok",
            cno="",  # empty
            cname="X",
            party_id="parties.IN.X",
        ),
    ]
    verdicts = compare_per_pc(rows, {})
    assert verdicts == []


def test_compare_per_pc_orders_by_state_then_cno_int():
    """Verdict rows sort by (state_code, int(constituency_no))."""
    rows = [
        _pc_shape_a(
            scope="a",
            state="zzz",
            cno="2",
            cname="z2",
            party_id="parties.IN.X",
        ),
        _pc_shape_a(
            scope="b",
            state="zzz",
            cno="2",
            cname="z2",
            party_id="parties.IN.X",
        ),
        _pc_shape_a(
            scope="a",
            state="zzz",
            cno="10",
            cname="z10",
            party_id="parties.IN.X",
        ),
        _pc_shape_a(
            scope="b",
            state="zzz",
            cno="10",
            cname="z10",
            party_id="parties.IN.X",
        ),
        _pc_shape_a(
            scope="a",
            state="aaa",
            cno="1",
            cname="a1",
            party_id="parties.IN.X",
        ),
        _pc_shape_a(
            scope="b",
            state="aaa",
            cno="1",
            cname="a1",
            party_id="parties.IN.X",
        ),
    ]
    verdicts = compare_per_pc(rows, {"parties.IN.X": {}})
    assert [(v.state_code, v.constituency_no) for v in verdicts] == [
        ("aaa", "1"),
        ("zzz", "2"),  # numerically 2 < 10
        ("zzz", "10"),
    ]


# --- _modal_party: deterministic tie-break --------------------------------


def test_modal_party_ties_break_by_alpha_smaller():
    """Tied counts -> alphabetically-smaller party_id wins."""
    pid, count = _modal_party(
        ["parties.IN.JSP", "parties.IN.JP", "parties.IN.JSP", "parties.IN.JP"]
    )
    assert count == 2
    # JP < JSP alpha-sort, so JP wins on tie.
    assert pid == "parties.IN.JP"


def test_modal_party_empty_returns_empty_zero():
    """Empty input -> ('', 0) for safe verdict surface."""
    assert _modal_party([]) == ("", 0)


def test_modal_party_unanimous():
    """All-same input -> that party + count."""
    assert _modal_party(["a", "a", "a"]) == ("a", 3)


# --- WRITE VERDICT CSV ----------------------------------------------------


def test_write_pc_verdict_csv_header_and_none_serialisation(tmp_path: Path):
    """write_pc_verdict_csv emits the expected header + None as empty."""
    verdicts = [
        PcVerdictRow(
            state_code="punjab",
            constituency_no="12",
            constituency_name="ANANDPUR SAHIB",
            n_oracles_present=2,
            n_oracles_agreeing=2,
            oracles_agreeing="bhukyavenkatamahesh-pc|yen-gov-canonical-pc",
            oracles_disagreeing="",
            winner_party_id_consensus="parties.IN.AAP",
            winner_party_id_per_oracle="bhukyavenkatamahesh-pc=parties.IN.AAP|yen-gov-canonical-pc=parties.IN.AAP",
            winner_candidate_per_oracle="",
            verdict="VERIFIED",
            curator_note=None,
            curator_source_id=None,
        )
    ]
    out = tmp_path / "verdict.csv"
    n = write_pc_verdict_csv(verdicts, out)
    assert n == 1
    text = out.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == ",".join(pc_verdict_csv_header())
    # curator_note + curator_source_id both None -> trailing ",,"
    assert lines[1].endswith(",,")


def test_pc_verdict_csv_header_is_field_order():
    """pc_verdict_csv_header() is the single source of truth for header."""
    assert pc_verdict_csv_header() == (
        "state_code",
        "constituency_no",
        "constituency_name",
        "n_oracles_present",
        "n_oracles_agreeing",
        "oracles_agreeing",
        "oracles_disagreeing",
        "winner_party_id_consensus",
        "winner_party_id_per_oracle",
        "winner_candidate_per_oracle",
        "verdict",
        "curator_note",
        "curator_source_id",
    )
