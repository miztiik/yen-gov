"""Tier-A tests for the per-event Compare-Aggregator (PR-S-TN-AE2026).

Covers:

  - The Fowler machine-decidable verdict rule for per-constituency
    parity (recon/event_aggregator.py): VERIFIED iff n_oracles_present
    >= 2 AND all present oracles agree on (winner_party_id,
    winner_candidate_name); DISPUTED iff disagreement on either dim;
    UNVERIFIED iff < 2 oracles present.
  - Candidate-name normalisation: punctuation + whitespace + case
    collapse across publisher conventions (event_aggregator._normalise_name).
  - Primary-row selection: yen-gov-elections wins when present; else
    first-alphabetic scope.
  - other_sources column formatting: pipe-delim, scope-sorted, primary
    excluded.
  - party_id_alliance lookup: looked up via (winner_party_id, event)
    against the party_alliances map; empty when not curated (the Q6
    "alliance not yet curated" badge signal).
  - Pure function: no I/O, no clock, no random; same inputs -> same
    outputs.

Tests author ConstituencyParityRow inputs directly; no adapter
dependency. The aggregator is the boundary tested here.
"""

from __future__ import annotations

from yen_gov.canonical.recon.event_aggregator import (
    ConstituencyVerdictRow,
    _normalise_name,
    compare_event,
    verdict_event_csv_header,
    write_event_verdict_csv,
)
from yen_gov.canonical.recon.shape_b import ConstituencyParityRow


def _row(
    *,
    scope: str = "yen-gov-elections",
    state: str = "tamil-nadu",
    event: str = "AcGenMay2026",
    ac_no: int = 1,
    ac_name: str = "TESTAC",
    party_id: str = "parties.IN.DMK",
    party_raw: str = "DMK",
    candidate: str = "Test Winner",
    votes: int | None = 1000,
    vintage: str = "AcGenMay2026",
) -> ConstituencyParityRow:
    return ConstituencyParityRow(
        external_scope=scope,
        external_vintage=vintage,
        state=state,
        event=event,
        constituency_no=ac_no,
        constituency_name=ac_name,
        winner_party_id=party_id,
        winner_party_short_raw=party_raw,
        winner_candidate_name=candidate,
        winner_votes=votes,
    )


# --- _normalise_name ----------------------------------------------------


def test_normalise_name_uppercases_and_collapses_punctuation() -> None:
    # The three publisher conventions for the same candidate should
    # normalise to the same key.
    assert (
        _normalise_name("S.vijayakumar")
        == _normalise_name("S.VIJAYAKUMAR")
        == _normalise_name("S VIJAYAKUMAR")
    )


def test_normalise_name_handles_empty_and_whitespace() -> None:
    assert _normalise_name("") == ""
    assert _normalise_name("  Spacious   Name  ") == "SPACIOUS NAME"


def test_normalise_name_strips_dots_dashes_commas() -> None:
    assert _normalise_name("Dr.J. Abubakkar Sithick") == (
        "DR J ABUBAKKAR SITHICK"
    )
    assert _normalise_name("M.K.STALIN") == "M K STALIN"


# --- verdict logic ------------------------------------------------------


def test_verdict_verified_when_two_oracles_agree() -> None:
    rows = [
        _row(scope="yen-gov-elections"),
        _row(scope="thecont1-state"),
    ]
    verdicts = compare_event(rows)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.verdict == "VERIFIED"
    assert v.verdict_party == "VERIFIED"
    assert v.verdict_candidate == "VERIFIED"
    assert v.n_oracles_present == 2
    assert v.n_oracles_agreeing_party == 2
    assert v.n_oracles_agreeing_candidate == 2


def test_verdict_verified_when_three_oracles_agree() -> None:
    rows = [
        _row(scope="yen-gov-elections"),
        _row(scope="thecont1-state"),
        _row(scope="tcpd-state"),
    ]
    verdicts = compare_event(rows)
    assert verdicts[0].verdict == "VERIFIED"
    assert verdicts[0].n_oracles_present == 3
    assert verdicts[0].n_oracles_agreeing_party == 3


def test_verdict_disputed_when_party_disagrees() -> None:
    rows = [
        _row(scope="yen-gov-elections", party_id="parties.IN.DMK"),
        _row(scope="thecont1-state", party_id="parties.IN.AIADMK"),
    ]
    verdicts = compare_event(rows)
    v = verdicts[0]
    assert v.verdict_party == "DISPUTED"
    assert v.verdict_candidate == "VERIFIED"  # candidate same
    assert v.verdict == "DISPUTED"  # combined = DISPUTED


def test_verdict_disputed_when_candidate_disagrees() -> None:
    rows = [
        _row(scope="yen-gov-elections", candidate="Alice"),
        _row(scope="thecont1-state", candidate="Bob"),
    ]
    verdicts = compare_event(rows)
    v = verdicts[0]
    assert v.verdict_party == "VERIFIED"
    assert v.verdict_candidate == "DISPUTED"
    assert v.verdict == "DISPUTED"


def test_verdict_disputed_when_both_disagree() -> None:
    rows = [
        _row(scope="yen-gov-elections", party_id="parties.IN.DMK",
             candidate="Alice"),
        _row(scope="thecont1-state", party_id="parties.IN.AIADMK",
             candidate="Bob"),
    ]
    verdicts = compare_event(rows)
    v = verdicts[0]
    assert v.verdict == "DISPUTED"


def test_verdict_unverified_when_only_one_oracle() -> None:
    rows = [
        _row(scope="yen-gov-elections"),
    ]
    verdicts = compare_event(rows)
    v = verdicts[0]
    assert v.verdict == "UNVERIFIED"
    assert v.verdict_party == "UNVERIFIED"
    assert v.verdict_candidate == "UNVERIFIED"
    assert v.n_oracles_present == 1


def test_verdict_combined_unverified_dominates_party_verified() -> None:
    # When one dim is UNVERIFIED, combined verdict MUST also be
    # UNVERIFIED - never silently upgrade.
    rows = [_row(scope="yen-gov-elections")]
    verdicts = compare_event(rows)
    assert verdicts[0].verdict == "UNVERIFIED"


# --- candidate normalisation in the verdict path ------------------------


def test_verdict_verified_when_publishers_disagree_only_on_capitalisation() -> None:
    # yen-gov: "S.vijayakumar"; thecont1: "S.VIJAYAKUMAR" - same after
    # _normalise_name. Should NOT trigger DISPUTED.
    rows = [
        _row(scope="yen-gov-elections", candidate="S.vijayakumar"),
        _row(scope="thecont1-state", candidate="S.VIJAYAKUMAR"),
    ]
    verdicts = compare_event(rows)
    assert verdicts[0].verdict == "VERIFIED"


# --- primary-row selection + other_sources formatting -------------------


def test_primary_row_picks_yen_gov_when_present() -> None:
    rows = [
        _row(scope="thecont1-state", candidate="External", party_id="parties.IN.AIADMK"),
        _row(scope="yen-gov-elections", candidate="Canonical", party_id="parties.IN.DMK"),
        _row(scope="tcpd-state", candidate="External", party_id="parties.IN.AIADMK"),
    ]
    verdicts = compare_event(rows)
    v = verdicts[0]
    assert v.yen_gov_winner_candidate_name == "Canonical"
    assert v.yen_gov_winner_party_id == "parties.IN.DMK"


def test_primary_row_falls_back_to_alphabetic_when_yen_gov_absent() -> None:
    # No yen-gov; first-alphabetic-scope wins ('tcpd-state' < 'thecont1-state'
    # because the 3rd char 'c' (99) < 'h' (104) - so tcpd-state is primary).
    rows = [
        _row(scope="tcpd-state", candidate="TCPD"),
        _row(scope="thecont1-state", candidate="TheCont1"),
    ]
    verdicts = compare_event(rows)
    assert verdicts[0].yen_gov_winner_candidate_name == "TCPD"


def test_other_sources_format_pipe_delim_scope_sorted() -> None:
    rows = [
        _row(scope="yen-gov-elections", party_id="parties.IN.DMK",
             candidate="X", votes=1000),
        _row(scope="thecont1-state", party_id="parties.IN.DMK",
             candidate="X", votes=2000),
        _row(scope="tcpd-state", party_id="parties.IN.DMK",
             candidate="X", votes=3000),
    ]
    verdicts = compare_event(rows)
    other = verdicts[0].other_sources
    # Alphabetic ordering: tcpd-state then thecont1-state.
    assert other == (
        "tcpd-state:parties.IN.DMK:X:3000|"
        "thecont1-state:parties.IN.DMK:X:2000"
    )


def test_other_sources_empty_when_only_primary() -> None:
    rows = [_row(scope="yen-gov-elections")]
    verdicts = compare_event(rows)
    assert verdicts[0].other_sources == ""


def test_other_sources_handles_null_votes() -> None:
    rows = [
        _row(scope="yen-gov-elections"),
        _row(scope="thecont1-state", votes=None),
    ]
    verdicts = compare_event(rows)
    # Empty votes field at end is fine.
    assert verdicts[0].other_sources.endswith(":")


# --- alliance lookup ----------------------------------------------------


def test_alliance_surfaces_when_curated() -> None:
    rows = [
        _row(scope="yen-gov-elections", party_id="parties.IN.AIADMK"),
        _row(scope="thecont1-state", party_id="parties.IN.AIADMK"),
    ]
    alliances = {("parties.IN.AIADMK", "AcGenMay2026"): "AIADMK+"}
    verdicts = compare_event(rows, party_alliances=alliances)
    assert verdicts[0].party_id_alliance == "AIADMK+"


def test_alliance_empty_when_not_curated() -> None:
    # The Q6 default: empty cell signals "alliance not yet curated for
    # this event" (the citizen-UI badge signal).
    rows = [
        _row(scope="yen-gov-elections", party_id="parties.IN.DMK"),
        _row(scope="thecont1-state", party_id="parties.IN.DMK"),
    ]
    verdicts = compare_event(rows, party_alliances={})
    assert verdicts[0].party_id_alliance == ""


def test_alliance_none_default_is_safe() -> None:
    # party_alliances kwarg defaults to None - aggregator must not
    # raise. Same shape as fully-empty map.
    rows = [_row(scope="yen-gov-elections")]
    verdicts = compare_event(rows)
    assert verdicts[0].party_id_alliance == ""


# --- multi-AC + sorting -------------------------------------------------


def test_verdicts_sorted_by_constituency_no() -> None:
    rows = [
        _row(scope="yen-gov-elections", ac_no=3),
        _row(scope="yen-gov-elections", ac_no=1),
        _row(scope="yen-gov-elections", ac_no=2),
        _row(scope="thecont1-state", ac_no=1),
        _row(scope="thecont1-state", ac_no=2),
        _row(scope="thecont1-state", ac_no=3),
    ]
    verdicts = compare_event(rows)
    assert [v.constituency_no for v in verdicts] == [1, 2, 3]


def test_compare_event_pure_function_same_input_same_output() -> None:
    rows = [
        _row(scope="yen-gov-elections", ac_no=1),
        _row(scope="thecont1-state", ac_no=1),
        _row(scope="yen-gov-elections", ac_no=2, candidate="Other"),
    ]
    v1 = compare_event(rows)
    v2 = compare_event(rows)
    assert v1 == v2


# --- shape contract -----------------------------------------------------


def test_verdict_csv_header_matches_row_fields() -> None:
    header = verdict_event_csv_header()
    # Header order matches ConstituencyVerdictRow field declaration
    # order; this is the EMISSION-order contract.
    expected = (
        "state", "event", "constituency_no", "constituency_name",
        "n_oracles_present", "n_oracles_agreeing_party",
        "n_oracles_agreeing_candidate", "yen_gov_winner_party_id",
        "yen_gov_winner_candidate_name", "yen_gov_winner_votes",
        "other_sources", "party_id_alliance",
        "verdict_party", "verdict_candidate", "verdict",
        "curator_note", "curator_source_id",
    )
    assert header == expected


def test_write_event_verdict_csv_roundtrips(tmp_path) -> None:  # type: ignore[no-untyped-def]
    rows = [
        _row(scope="yen-gov-elections"),
        _row(scope="thecont1-state"),
    ]
    verdicts = compare_event(rows)
    path = tmp_path / "verdict.csv"
    n = write_event_verdict_csv(verdicts, path)
    assert n == 1
    assert path.exists()
    # File header matches schema contract.
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",")[0] == "state"


def test_constituency_no_zero_or_negative_rejected() -> None:
    import pytest
    # ConstituencyParityRow itself doesn't reject - the aggregator does.
    bad = _row(ac_no=0)
    with pytest.raises(ValueError, match="invalid constituency_no"):
        compare_event([bad])
