"""Tier-A tests for the TCPD per-PC parity adapter (PR-PC-LS2024).

Covers:

  - ADAPTER is registered in REGISTRY['tcpd-pc'].
  - Adapter rejects ``kind != 'parliament'``; CLI vintage is ignored.
  - ``_resolve_state_slug`` honours the TCPD underscore convention +
    the legacy state-name remap (PONDICHERRY -> puducherry, etc.).
  - ``_resolve_party_id`` priority: sentinel -> by_alias -> by_full.
  - ``_read_tcpd_winners`` filters to a year + picks Position == 1
    rows; rows outside the year are skipped.
  - Year beyond TCPD_GE_LAST_COVERED_YEAR (2019) returns an empty
    shape-A list with a stderr notice; no exception.
  - End-to-end: ``TcpdPcAdapter()`` against a minimal fixture
    yields the expected per-PC shape-A row set.

No real-corpus walking (CLAUDE.md section 14 carve-out: tmp_path
fixtures only). Pure-function tests.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.recon.adapters import REGISTRY
from yen_gov.canonical.recon.adapters.tcpd_pc import (
    ADAPTER,
    DEFAULT_TCPD_GE_CSV,
    TCPD_GE_LAST_COVERED_YEAR,
    TCPD_GE_VINTAGE,
    TCPD_PC_SCOPE,
    TcpdPcAdapter,
    _TCPD_STATE_SLUG_REMAP,
    _load_parties_index,
    _load_state_index,
    _normalise_party_name,
    _parse_votes,
    _read_tcpd_winners,
    _resolve_party_id,
    _resolve_state_slug,
    _slugify,
)


_TCPD_COLS: tuple[str, ...] = (
    "State_Name", "Assembly_No", "Constituency_No", "Year", "month",
    "Poll_No", "DelimID", "Position", "Candidate", "Sex", "Party",
    "Votes", "Constituency_Name", "Party_Type_TCPD",
)

_PARTIES_COLS: tuple[str, ...] = (
    "party_id", "short", "full", "eci_codes", "brand_colour",
    "symbol_asset", "wikipedia", "aliases", "recognition_scope",
    "home_state_codes", "founded_year", "dissolved_year",
    "predecessor_party_ids", "successor_party_ids", "name_history",
    "claims_to_parent_name", "name_native_script", "is_sentinel",
)

_STATE_CODES_COLS: tuple[str, ...] = (
    "lgd_state_id", "lgd_name", "iso_3166_2", "census_2001_code",
    "census_2011_code", "kind", "slug", "aliases",
)


def _write_tcpd_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    """Write a TCPD-style CSV to the expected default path."""
    path = tmp_path / DEFAULT_TCPD_GE_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=_TCPD_COLS, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _TCPD_COLS})
    return path


def _write_parties_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "datasets" / "data" / "entities" / "parties.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=_PARTIES_COLS, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _PARTIES_COLS})
    return path


def _write_state_codes_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "datasets" / "data" / "entities" / "state_codes.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=_STATE_CODES_COLS, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _STATE_CODES_COLS})
    return path


# --- REGISTRATION ---------------------------------------------------------


def test_adapter_registered_in_registry() -> None:
    """The PR-PC-LS2024 adapter is registered under tcpd-pc."""
    assert "tcpd-pc" in REGISTRY
    assert REGISTRY["tcpd-pc"] is ADAPTER


def test_adapter_rejects_wrong_kind(tmp_path: Path) -> None:
    adapter = TcpdPcAdapter()
    with pytest.raises(ValueError, match="parliament"):
        list(
            adapter(root=tmp_path, vintage=TCPD_GE_VINTAGE, kind="assembly")
        )


def test_adapter_accepts_any_vintage_uses_own_pin(tmp_path: Path) -> None:
    """CLI vintage is ignored - adapter always emits with TCPD_GE_VINTAGE."""
    _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.INC", "short": "INC", "full": "INC"},
    ])
    _write_tcpd_csv(tmp_path, [
        {"State_Name": "Andhra_Pradesh", "Assembly_No": "17",
         "Constituency_No": "1", "Year": "2019", "month": "4",
         "Poll_No": "0", "DelimID": "4", "Position": "1",
         "Candidate": "X", "Sex": "M", "Party": "INC",
         "Votes": "100000", "Constituency_Name": "ARAKU",
         "Party_Type_TCPD": "National Party"},
    ])
    adapter = TcpdPcAdapter()
    rows = list(adapter(
        root=tmp_path, vintage="anything", event="LsGen2019",
    ))
    assert len(rows) == 1
    assert rows[0].external_vintage == TCPD_GE_VINTAGE


def test_adapter_raises_when_csv_missing(tmp_path: Path) -> None:
    """In-window year + missing file -> FileNotFoundError."""
    _write_state_codes_csv(tmp_path, [])
    _write_parties_csv(tmp_path, [])
    adapter = TcpdPcAdapter()
    with pytest.raises(FileNotFoundError, match="TCPD"):
        list(adapter(root=tmp_path, vintage=TCPD_GE_VINTAGE, event="LsGen2019"))


def test_adapter_year_beyond_cutoff_returns_empty(tmp_path: Path) -> None:
    """LS-2024 > 2019 cutoff -> empty list (no exception)."""
    _write_state_codes_csv(tmp_path, [])
    _write_parties_csv(tmp_path, [])
    # Note: no TCPD CSV needed; year guard short-circuits BEFORE the
    # file existence check.
    adapter = TcpdPcAdapter()
    rows = list(adapter(
        root=tmp_path, vintage=TCPD_GE_VINTAGE, event="LsGenJun2024",
    ))
    assert rows == []
    # Confirm the year sentinel constant is still 2019 (regression
    # guard: bumping the cutoff is a deliberate operator act).
    assert TCPD_GE_LAST_COVERED_YEAR == 2019


# --- STATE RESOLUTION -----------------------------------------------------


def test_slugify_underscored_state() -> None:
    assert _slugify("Andhra_Pradesh") == "andhra-pradesh"
    assert _slugify("Tamil_Nadu") == "tamil-nadu"
    assert _slugify("Andaman_&_Nicobar_Islands") == (
        "andaman-and-nicobar-islands"
    )


def test_resolve_state_slug_remap_legacy_names(tmp_path: Path) -> None:
    """ORISSA -> odisha; PONDICHERRY -> puducherry."""
    state_codes_csv = _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Odisha", "iso_3166_2": "IN-OD",
         "census_2001_code": "21", "census_2011_code": "21",
         "kind": "state", "slug": "odisha", "aliases": "Orissa"},
        {"lgd_state_id": "2", "lgd_name": "Puducherry",
         "iso_3166_2": "IN-PY", "census_2001_code": "34",
         "census_2011_code": "34", "kind": "ut", "slug": "puducherry",
         "aliases": "Pondicherry"},
    ])
    ix = _load_state_index(state_codes_csv)
    assert _resolve_state_slug("ORISSA", ix) == "odisha"
    assert _resolve_state_slug("PONDICHERRY", ix) == "puducherry"


def test_resolve_state_slug_handles_underscore_to_space(tmp_path: Path) -> None:
    """TCPD 'Andhra_Pradesh' -> by_upper_name match after _ -> space."""
    state_codes_csv = _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    ix = _load_state_index(state_codes_csv)
    assert _resolve_state_slug("Andhra_Pradesh", ix) == "andhra-pradesh"


# --- VOTES + PARTY RESOLUTION ---------------------------------------------


def test_parse_votes_basic() -> None:
    assert _parse_votes("100000") == 100000
    assert _parse_votes("0") == 0
    assert _parse_votes("") is None
    assert _parse_votes("garbage") is None


def test_resolve_party_id_short_alias(tmp_path: Path) -> None:
    """TCPD uses short codes (INC, BJP); by_alias_upper resolves them."""
    parties_csv = _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.INC", "short": "INC",
         "full": "Indian National Congress"},
    ])
    ix = _load_parties_index(parties_csv)
    assert _resolve_party_id("INC", ix) == "parties.IN.INC"


def test_resolve_party_id_sentinel(tmp_path: Path) -> None:
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_parties_index(parties_csv)
    assert _resolve_party_id("NOTA", ix) == "parties.IN.NOTA"
    assert _resolve_party_id("IND", ix) == "parties.IN.IND"
    assert _resolve_party_id("Independent", ix) == "parties.IN.IND"


def test_resolve_party_id_miss_returns_unk(tmp_path: Path) -> None:
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_parties_index(parties_csv)
    assert _resolve_party_id("Fictional", ix) == "parties.IN.UNK"


def test_normalise_party_name_collapses_punctuation() -> None:
    assert _normalise_party_name("CPI (M)") == "CPI M"
    assert _normalise_party_name("Bharatiya Janata Party") == (
        "BHARATIYA JANATA PARTY"
    )


# --- WINNER DERIVATION ----------------------------------------------------


def test_read_tcpd_winners_filters_by_year_and_position(tmp_path: Path) -> None:
    """Only Year==filter AND Position==1 rows survive."""
    state_codes_csv = _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    tcpd_csv = _write_tcpd_csv(tmp_path, [
        # 2019 P1 - WINNER.
        {"State_Name": "Andhra_Pradesh", "Year": "2019", "Position": "1",
         "Candidate": "W1", "Party": "INC", "Votes": "100000",
         "Constituency_No": "1", "Constituency_Name": "Araku",
         "Party_Type_TCPD": "National Party"},
        # 2019 P2 - SKIP (not winner).
        {"State_Name": "Andhra_Pradesh", "Year": "2019", "Position": "2",
         "Candidate": "R1", "Party": "BJP", "Votes": "50000",
         "Constituency_No": "1", "Constituency_Name": "Araku",
         "Party_Type_TCPD": "National Party"},
        # 2014 P1 - SKIP (different year).
        {"State_Name": "Andhra_Pradesh", "Year": "2014", "Position": "1",
         "Candidate": "X", "Party": "TDP", "Votes": "200000",
         "Constituency_No": "1", "Constituency_Name": "Araku",
         "Party_Type_TCPD": "State-based Party"},
    ])
    state_ix = _load_state_index(state_codes_csv)
    winners = _read_tcpd_winners(tcpd_csv, 2019, state_ix)
    assert len(winners) == 1
    w = winners[0]
    assert w.state_slug == "andhra-pradesh"
    assert w.candidate == "W1"
    assert w.party_short == "INC"
    assert w.votes == 100000


def test_read_tcpd_winners_skips_unknown_state(tmp_path: Path) -> None:
    state_codes_csv = _write_state_codes_csv(tmp_path, [])
    tcpd_csv = _write_tcpd_csv(tmp_path, [
        {"State_Name": "Fictional", "Year": "2019", "Position": "1",
         "Candidate": "X", "Party": "INC", "Votes": "100",
         "Constituency_No": "1", "Constituency_Name": "X",
         "Party_Type_TCPD": "National Party"},
    ])
    state_ix = _load_state_index(state_codes_csv)
    assert _read_tcpd_winners(tcpd_csv, 2019, state_ix) == []


# --- END-TO-END ADAPTER ---------------------------------------------------


def test_adapter_end_to_end_minimal_fixture(tmp_path: Path) -> None:
    """Full adapter pass on a 2-PC LS-2019 fixture."""
    _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.INC", "short": "INC",
         "full": "Indian National Congress"},
        {"party_id": "parties.IN.BJP", "short": "BJP",
         "full": "Bharatiya Janata Party"},
    ])
    _write_tcpd_csv(tmp_path, [
        {"State_Name": "Andhra_Pradesh", "Year": "2019", "Position": "1",
         "Candidate": "INC Winner", "Party": "INC", "Votes": "100000",
         "Constituency_No": "1", "Constituency_Name": "ARAKU",
         "Party_Type_TCPD": "National Party"},
        {"State_Name": "Andhra_Pradesh", "Year": "2019", "Position": "1",
         "Candidate": "BJP Winner", "Party": "BJP", "Votes": "200000",
         "Constituency_No": "2", "Constituency_Name": "ANANTAPUR",
         "Party_Type_TCPD": "National Party"},
    ])
    adapter = TcpdPcAdapter()
    rows = list(adapter(
        root=tmp_path, vintage=TCPD_GE_VINTAGE, event="LsGen2019",
    ))
    assert len(rows) == 2
    by_cno = {r.constituency_no: r for r in rows}
    assert by_cno["1"].proposed_party_id == "parties.IN.INC"
    assert by_cno["1"].external_scope == TCPD_PC_SCOPE
    assert by_cno["1"].external_vintage == TCPD_GE_VINTAGE
    assert by_cno["2"].proposed_party_id == "parties.IN.BJP"
    assert by_cno["2"].winner_candidate == "BJP Winner"
    assert by_cno["2"].winner_votes == 200000


def test_adapter_emits_stable_order_across_runs(tmp_path: Path) -> None:
    """Same snapshot -> same per-PC emission order."""
    _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.INC", "short": "INC", "full": "INC"},
    ])
    _write_tcpd_csv(tmp_path, [
        {"State_Name": "Andhra_Pradesh", "Year": "2019", "Position": "1",
         "Candidate": "X", "Party": "INC", "Votes": "100",
         "Constituency_No": "3", "Constituency_Name": "Z",
         "Party_Type_TCPD": "National Party"},
        {"State_Name": "Andhra_Pradesh", "Year": "2019", "Position": "1",
         "Candidate": "X", "Party": "INC", "Votes": "100",
         "Constituency_No": "1", "Constituency_Name": "A",
         "Party_Type_TCPD": "National Party"},
        {"State_Name": "Andhra_Pradesh", "Year": "2019", "Position": "1",
         "Candidate": "X", "Party": "INC", "Votes": "100",
         "Constituency_No": "2", "Constituency_Name": "M",
         "Party_Type_TCPD": "National Party"},
    ])
    adapter = TcpdPcAdapter()
    rows1 = list(adapter(root=tmp_path, vintage=TCPD_GE_VINTAGE, event="LsGen2019"))
    rows2 = list(adapter(root=tmp_path, vintage=TCPD_GE_VINTAGE, event="LsGen2019"))
    cnos1 = [r.constituency_no for r in rows1]
    cnos2 = [r.constituency_no for r in rows2]
    assert cnos1 == cnos2
    assert cnos1 == ["1", "2", "3"]
