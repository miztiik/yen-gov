"""Tier-A tests for the TCPD All_States_AE per-state parity adapter (PR-S-TN-AE2026).

Covers:

  - End-to-end: ``TcpdStateAdapter()`` against a minimal fixture yields
    one ``ConstituencyParityRow`` per AC with ``Position=1`` for the
    requested (state, year) tuple.
  - Multi-state fixture: adapter filters by ``State_Name`` correctly
    (rows from other states do NOT leak into the per-state result).
  - Multi-year fixture: adapter filters by ``Year`` correctly (rows
    from other years for the same state do NOT leak).
  - Empty-oracle behaviour: when the TCPD compilation has no
    (state, year) rows (the typical post-2021 cutoff scenario for
    events like AcGenMay2026), the adapter returns an empty list and
    the CLI continues with the remaining sources per the brief.
  - Data-integrity guard: multiple ``Position=1`` rows for the same
    (state, year, constituency_no) are TCPD bypoll-conflation per the
    PR-S-WB-AE2021 finding (2026-06-11) - keep first-seen row
    (original polling-cycle winner), skip subsequent rows, log a
    stderr warning naming the conflated AC count.
  - Vintage validation: adapter rejects any vintage value other than
    the TCPD compilation cutoff (TCPD_VINTAGE).
  - Resolver dispatch via TCPD's short / alias labels (the typical
    TCPD ``Party`` column carries the short, not full).
  - NOTA / IND surface via the resolver's sentinel flags.
  - Adapter is registered in ``EVENT_REGISTRY["tcpd-state"]``.

Pure ``tmp_path`` fixtures only - CLAUDE.md section 14 carve-out: no
real-corpus walking from pytest.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.party_resolver import load_resolver
from yen_gov.canonical.recon.adapters import EVENT_REGISTRY
from yen_gov.canonical.recon.adapters.tcpd_state import (
    ADAPTER,
    DEFAULT_TCPD_AE_CSV,
    TCPD_STATE_SCOPE,
    TCPD_VINTAGE,
    TcpdStateAdapter,
)
from yen_gov.canonical.recon.shape_b import ConstituencyParityRow


_PARTIES_COLS: tuple[str, ...] = (
    "party_id",
    "short",
    "full",
    "eci_codes",
    "brand_colour",
    "symbol_asset",
    "wikipedia",
    "aliases",
    "recognition_scope",
    "home_state_codes",
    "founded_year",
    "dissolved_year",
    "predecessor_party_ids",
    "successor_party_ids",
    "name_history",
    "claims_to_parent_name",
    "name_native_script",
    "is_sentinel",
)


# Subset of TCPD All_States_AE.csv columns the adapter consumes. Full
# upstream has 47 columns; the adapter reads only these 8.
_TCPD_AE_COLS: tuple[str, ...] = (
    "State_Name",
    "Year",
    "Constituency_No",
    "Position",
    "Candidate",
    "Party",
    "Votes",
    "Constituency_Name",
)


def _write_parties_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "datasets" / "data" / "entities" / "parties.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_PARTIES_COLS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _PARTIES_COLS})
    return path


def _write_tcpd_ae_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / DEFAULT_TCPD_AE_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_TCPD_AE_COLS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _TCPD_AE_COLS})
    return path


@pytest.fixture(autouse=True)
def _reset_resolver_cache() -> None:
    load_resolver.cache_clear()


# --- ADAPTER REGISTRATION -----------------------------------------------


def test_adapter_registered_in_event_registry() -> None:
    assert "tcpd-state" in EVENT_REGISTRY
    assert EVENT_REGISTRY["tcpd-state"] is ADAPTER


def test_adapter_rejects_missing_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tcpd-state adapter requires --state"):
        list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                     state=None, event="AcGenMay2021", kind="assembly"))


def test_adapter_rejects_missing_event(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tcpd-state adapter requires --event"):
        list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                     state="tamil-nadu", event=None, kind="assembly"))


def test_adapter_rejects_kind_parliament(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--kind 'assembly' only"):
        list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                     state="tamil-nadu", event="LsGenJun2024",
                     kind="parliament"))


def test_adapter_rejects_unmapped_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no TCPD-token mapping"):
        list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                     state="unknown-state", event="AcGenMay2021",
                     kind="assembly"))


def test_adapter_rejects_wrong_vintage(tmp_path: Path) -> None:
    # The compilation cutoff is fixed at TCPD_VINTAGE; any other
    # vintage is a publisher-edition spoof.
    with pytest.raises(ValueError, match="only supports vintage"):
        list(ADAPTER(root=tmp_path, vintage="2026",
                     state="tamil-nadu", event="AcGenMay2026",
                     kind="assembly"))


def test_adapter_raises_when_tcpd_csv_missing(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [])
    # TCPD CSV not created.
    with pytest.raises(FileNotFoundError, match="All_States_AE.csv not found"):
        list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                     state="tamil-nadu", event="AcGenMay2021",
                     kind="assembly"))


# --- end-to-end: winner extraction --------------------------------------


def test_adapter_emits_one_row_per_position_one(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.AIADMK", "short": "AIADMK",
         "full": "All India Anna Dravida Munnetra Kazhagam",
         "aliases": "ADMK"},
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        # AC 1: DMK winner.
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "DMK Winner", "Party": "DMK",
         "Votes": "100000", "Constituency_Name": "AC1"},
        # AC 1: AIADMK runner-up (Position != 1; should be skipped).
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "2",
         "Candidate": "AIADMK Loser", "Party": "AIADMK",
         "Votes": "80000", "Constituency_Name": "AC1"},
        # AC 2: AIADMK winner.
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "2", "Position": "1",
         "Candidate": "AIADMK Winner", "Party": "AIADMK",
         "Votes": "70000", "Constituency_Name": "AC2"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenApr2021",
                       kind="assembly"))
    assert len(out) == 2
    by_ac = {r.constituency_no: r for r in out}
    assert by_ac[1].winner_party_id == "parties.IN.DMK"
    assert by_ac[1].winner_candidate_name == "DMK Winner"
    assert by_ac[1].winner_votes == 100000
    assert by_ac[2].winner_party_id == "parties.IN.AIADMK"


def test_adapter_filters_by_state(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
        {"party_id": "parties.IN.TDP", "short": "TDP",
         "full": "Telugu Desam Party", "aliases": "TDP"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        # TN row that should be returned.
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "TN Winner", "Party": "DMK",
         "Votes": "100000", "Constituency_Name": "AC1"},
        # AP row that should NOT be returned for state=tamil-nadu.
        {"State_Name": "Andhra_Pradesh", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "AP Winner", "Party": "TDP",
         "Votes": "50000", "Constituency_Name": "Some AC"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenApr2021",
                       kind="assembly"))
    assert len(out) == 1
    assert out[0].winner_candidate_name == "TN Winner"


def test_adapter_filters_by_year(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        # 2016 TN row - should NOT be returned for AcGenApr2021.
        {"State_Name": "Tamil_Nadu", "Year": "2016",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "2016 Winner", "Party": "DMK",
         "Votes": "100000", "Constituency_Name": "AC1"},
        # 2021 TN row - SHOULD be returned.
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "2021 Winner", "Party": "DMK",
         "Votes": "120000", "Constituency_Name": "AC1"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenApr2021",
                       kind="assembly"))
    assert len(out) == 1
    assert out[0].winner_candidate_name == "2021 Winner"


def test_adapter_empty_oracle_for_post_cutoff_year(tmp_path: Path) -> None:
    # The brief's flagship case: TCPD compilation cutoff is 2021; for
    # an event in 2026 the adapter returns an empty list and the CLI
    # logs '(EMPTY ORACLE)' + continues with the other sources.
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        # 2021 row exists but the requested event is 2026.
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "X", "Party": "DMK",
         "Votes": "100000", "Constituency_Name": "AC1"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenMay2026",
                       kind="assembly"))
    assert out == []


def test_adapter_keeps_first_position_one_on_bypoll_conflation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TCPD bypoll-conflation: two Position=1 rows for the same AC =
    original polling-cycle winner FIRST, bypoll winner SECOND. The
    adapter keeps the first-seen row and logs a warning to stderr.

    Verified at scale on WB 2021 (PR-S-WB-AE2021 finding 2026-06-11):
    5 ACs (#7 DINHATA, #86 SANTIPUR, #109 KHARDAHA, #127 GOSABA, #159
    BHABANIPUR) have bypoll re-elections within the 2021 cycle. The
    parity oracle compares against yen-gov's original-cycle results,
    so the first-seen row is the right one to keep.
    """
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        # TWO Position=1 rows for the same (state, year, AC) =
        # original FIRST (X1, 100k), bypoll SECOND (X2, 90k).
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "X1", "Party": "DMK",
         "Votes": "100000", "Constituency_Name": "AC1"},
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "X2", "Party": "DMK",
         "Votes": "90000", "Constituency_Name": "AC1"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenApr2021",
                       kind="assembly"))
    # First-seen (X1, original cycle winner) is kept.
    assert len(out) == 1
    assert out[0].constituency_no == 1
    assert out[0].winner_candidate_name == "X1"
    assert out[0].winner_votes == 100000
    # Stderr warning surfaces the conflation count for the operator.
    captured = capsys.readouterr()
    assert "tcpd-state adapter [warning]" in captured.err
    assert "multiple Position=1 rows" in captured.err


def test_adapter_preserves_unk_when_resolver_misses(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        # Party 'FOO' not in parties.csv -> resolver returns UNK; TCPD
        # adapter does NOT consult by_full (per design - TCPD publishes
        # SHORTS, not full names, so the resolver's by_alias path is
        # the only resolution route).
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "X", "Party": "FOO",
         "Votes": "100000", "Constituency_Name": "AC1"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenApr2021",
                       kind="assembly"))
    assert len(out) == 1
    assert out[0].winner_party_id == "parties.IN.UNK"
    # Raw label preserved per CLAUDE.md section 10.
    assert out[0].winner_party_short_raw == "FOO"


def test_adapter_resolves_nota(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.NOTA", "short": "NOTA",
         "full": "None of the Above"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "", "Party": "NOTA",
         "Votes": "5000", "Constituency_Name": "AC1"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenApr2021",
                       kind="assembly"))
    assert out[0].winner_party_id == "parties.IN.NOTA"


def test_adapter_resolves_independent(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.IND", "short": "IND",
         "full": "Independent"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "Joe", "Party": "IND",
         "Votes": "3000", "Constituency_Name": "AC1"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenApr2021",
                       kind="assembly"))
    assert out[0].winner_party_id == "parties.IN.IND"


def test_adapter_emits_shape_b_rows_with_tcpd_vintage(tmp_path: Path) -> None:
    # ConstituencyParityRow.external_vintage is pinned to TCPD_VINTAGE
    # (the compilation edition; per ADR-0042 publisher edition anchor)
    # - distinct from the event id (which is the per-event-publisher
    # anchor used by other event adapters).
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_tcpd_ae_csv(tmp_path, [
        {"State_Name": "Tamil_Nadu", "Year": "2021",
         "Constituency_No": "1", "Position": "1",
         "Candidate": "X", "Party": "DMK",
         "Votes": "100000", "Constituency_Name": "AC1"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage=TCPD_VINTAGE,
                       state="tamil-nadu", event="AcGenApr2021",
                       kind="assembly"))
    assert len(out) == 1
    row = out[0]
    assert isinstance(row, ConstituencyParityRow)
    assert row.external_scope == TCPD_STATE_SCOPE
    assert row.external_vintage == TCPD_VINTAGE
    assert row.state == "tamil-nadu"
    assert row.event == "AcGenApr2021"
