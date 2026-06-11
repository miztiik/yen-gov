"""Tier-A tests for the bhukyavenkatamahesh per-PC parity adapter (PR-PC-LS2024).

Covers:

  - ADAPTER is registered in REGISTRY['bhukyavenkatamahesh-pc'].
  - Adapter rejects ``kind != 'parliament'``; CLI vintage is ignored.
  - ``_slugify`` + ``_resolve_state_slug`` mappings.
  - ``_parse_votes`` handles the 'Unconteste' truncation + other
    placeholders.
  - ``_resolve_party_id`` priority: sentinel -> by_full -> by_alias.
  - ``_read_bhuky_winners`` derives the per-PC modal winner from
    the per-candidate snapshot CSV.
  - End-to-end: ``BhukyavenkatamaheshPcAdapter()`` against a minimal
    fixture yields the expected per-PC shape-A row set.

No real-corpus walking (CLAUDE.md section 14 carve-out: tmp_path
fixtures only). Pure-function tests; the adapter holds no I/O
state beyond reading the snapshot path.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.recon.adapters import REGISTRY
from yen_gov.canonical.recon.adapters.bhukyavenkatamahesh_pc import (
    ADAPTER,
    BHUKY_SCOPE,
    BHUKY_VINTAGE,
    DEFAULT_BHUKY_CSV,
    BhukyavenkatamaheshPcAdapter,
    _BHUKY_CONSTITUENCY_NAME_REMAP,
    _BHUKY_STATE_SLUG_REMAP,
    _load_parties_index,
    _load_state_index,
    _normalise_party_name,
    _parse_votes,
    _read_bhuky_winners,
    _resolve_party_id,
    _resolve_state_slug,
    _slugify,
    _yen_gov_pc_no_index,
)
from yen_gov.canonical.recon.shape_a import ShapeARow


_BHUKY_COLS: tuple[str, ...] = (
    "State", "Constituency", "Party", "Candidate", "Votes",
    "State ID", "Constituency ID",
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


def _write_bhuky_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    """Write a bhuky-style semicolon-delimited CSV to the expected path."""
    path = tmp_path / DEFAULT_BHUKY_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=_BHUKY_COLS, delimiter=";", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _BHUKY_COLS})
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


def _write_summary_csv(
    tmp_path: Path, year: int, rows: list[dict[str, str]]
) -> Path:
    path = (
        tmp_path
        / "datasets"
        / "elections"
        / "parliament"
        / f"election={year}"
        / "summary.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ("entity_id", "state", "election_year", "constituency_name",
            "winner_party_id", "winner_candidate")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in cols})
    return path


# --- REGISTRATION ---------------------------------------------------------


def test_adapter_registered_in_registry() -> None:
    """The PR-PC-LS2024 adapter is registered under bhukyavenkatamahesh-pc."""
    assert "bhukyavenkatamahesh-pc" in REGISTRY
    assert REGISTRY["bhukyavenkatamahesh-pc"] is ADAPTER


def test_adapter_rejects_wrong_kind(tmp_path: Path) -> None:
    adapter = BhukyavenkatamaheshPcAdapter()
    with pytest.raises(ValueError, match="parliament"):
        list(adapter(root=tmp_path, vintage=BHUKY_VINTAGE, kind="assembly"))


def test_adapter_accepts_any_vintage_uses_own_pin(tmp_path: Path) -> None:
    """CLI vintage is ignored - adapter always emits with BHUKY_VINTAGE."""
    _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.X", "short": "X", "full": "X"},
    ])
    _write_bhuky_csv(tmp_path, [
        {"State": "Andhra Pradesh", "Constituency": "X",
         "Party": "X", "Candidate": "X", "Votes": "100",
         "State ID": "S01", "Constituency ID": "1"},
    ])
    adapter = BhukyavenkatamaheshPcAdapter()
    # Passing a different CLI vintage MUST NOT raise; pin is internal.
    rows = list(adapter(root=tmp_path, vintage="2030", event="LsGenJun2024"))
    assert len(rows) == 1
    assert rows[0].external_vintage == BHUKY_VINTAGE


def test_adapter_raises_when_snapshot_missing(tmp_path: Path) -> None:
    adapter = BhukyavenkatamaheshPcAdapter()
    _write_state_codes_csv(tmp_path, [])
    _write_parties_csv(tmp_path, [])
    with pytest.raises(FileNotFoundError, match="bhukyavenkatamahesh"):
        list(adapter(root=tmp_path, vintage=BHUKY_VINTAGE))


# --- SLUGIFY + STATE RESOLUTION -------------------------------------------


def test_slugify_basic() -> None:
    assert _slugify("Andhra Pradesh") == "andhra-pradesh"
    assert _slugify("NCT OF Delhi") == "nct-of-delhi"
    assert _slugify("Jammu & Kashmir") == "jammu-and-kashmir"
    assert _slugify("") == ""


def test_resolve_state_slug_remap_wins(tmp_path: Path) -> None:
    """Remap 'NCT OF Delhi' -> 'delhi' fires even if state_codes has Delhi."""
    state_codes_csv = _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Delhi", "iso_3166_2": "IN-DL",
         "census_2001_code": "7", "census_2011_code": "7",
         "kind": "ut", "slug": "delhi", "aliases": ""},
    ])
    ix = _load_state_index(state_codes_csv)
    assert _resolve_state_slug("NCT OF Delhi", ix) == "delhi"


def test_resolve_state_slug_by_lgd_name(tmp_path: Path) -> None:
    state_codes_csv = _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    ix = _load_state_index(state_codes_csv)
    assert _resolve_state_slug("Andhra Pradesh", ix) == "andhra-pradesh"
    assert _resolve_state_slug("ANDHRA PRADESH", ix) == "andhra-pradesh"


def test_resolve_state_slug_miss_returns_none(tmp_path: Path) -> None:
    state_codes_csv = _write_state_codes_csv(tmp_path, [])
    ix = _load_state_index(state_codes_csv)
    assert _resolve_state_slug("Fictional Land", ix) is None
    assert _resolve_state_slug("", ix) is None


# --- VOTES PARSER ---------------------------------------------------------


def test_parse_votes_handles_truncated_unopposed() -> None:
    """The 'Unconteste' truncation in the Surat 2024 row -> None."""
    assert _parse_votes("Unconteste") is None
    assert _parse_votes("Uncontested") is None
    assert _parse_votes("-") is None
    assert _parse_votes("NA") is None
    assert _parse_votes("") is None


def test_parse_votes_parses_int() -> None:
    assert _parse_votes("100000") == 100000
    assert _parse_votes("0") == 0


def test_parse_votes_non_numeric_returns_none() -> None:
    """An unparseable non-placeholder string also degrades to None."""
    assert _parse_votes("garbage") is None


# --- PARTY RESOLUTION -----------------------------------------------------


def test_normalise_party_name() -> None:
    assert _normalise_party_name("Bharatiya Janata Party") == (
        "BHARATIYA JANATA PARTY"
    )
    assert _normalise_party_name("Communist Party of India (Marxist)") == (
        "COMMUNIST PARTY OF INDIA MARXIST"
    )


def test_resolve_party_id_full_name_match(tmp_path: Path) -> None:
    parties_csv = _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.BJP", "short": "BJP",
         "full": "Bharatiya Janata Party"},
    ])
    ix = _load_parties_index(parties_csv)
    assert _resolve_party_id("Bharatiya Janata Party", ix) == "parties.IN.BJP"


def test_resolve_party_id_sentinel_nota(tmp_path: Path) -> None:
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_parties_index(parties_csv)
    assert _resolve_party_id("NOTA", ix) == "parties.IN.NOTA"
    assert _resolve_party_id("None of the Above", ix) == "parties.IN.NOTA"


def test_resolve_party_id_sentinel_independent(tmp_path: Path) -> None:
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_parties_index(parties_csv)
    assert _resolve_party_id("Independent", ix) == "parties.IN.IND"


def test_resolve_party_id_fallback_to_short_alias(tmp_path: Path) -> None:
    """Publisher uses short instead of full -> by_alias hits."""
    parties_csv = _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.BJP", "short": "BJP",
         "full": "Bharatiya Janata Party", "aliases": "BJP|B.J.P."},
    ])
    ix = _load_parties_index(parties_csv)
    assert _resolve_party_id("B.J.P.", ix) == "parties.IN.BJP"


def test_resolve_party_id_miss_returns_unk(tmp_path: Path) -> None:
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_parties_index(parties_csv)
    assert _resolve_party_id("Some Fictional Party", ix) == "parties.IN.UNK"
    assert _resolve_party_id("", ix) == "parties.IN.UNK"


# --- WINNER DERIVATION ----------------------------------------------------


def test_read_bhuky_winners_picks_max_votes(tmp_path: Path) -> None:
    state_codes_csv = _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    bhuky_csv = _write_bhuky_csv(tmp_path, [
        # Same PC, 3 candidates - max votes wins.
        {"State": "Andhra Pradesh", "Constituency": "Araku",
         "Party": "Bharatiya Janata Party", "Candidate": "B",
         "Votes": "400000", "State ID": "S01", "Constituency ID": "1"},
        {"State": "Andhra Pradesh", "Constituency": "Araku",
         "Party": "Indian National Congress", "Candidate": "C",
         "Votes": "100000", "State ID": "S01", "Constituency ID": "1"},
        {"State": "Andhra Pradesh", "Constituency": "Araku",
         "Party": "YSR Congress", "Candidate": "Y",
         "Votes": "500000", "State ID": "S01", "Constituency ID": "1"},
    ])
    state_ix = _load_state_index(state_codes_csv)
    winners = _read_bhuky_winners(bhuky_csv, state_ix)
    assert len(winners) == 1
    w = winners[0]
    assert w.state_slug == "andhra-pradesh"
    assert w.constituency_name_upper == "ARAKU"
    assert w.party_full == "YSR Congress"
    assert w.candidate == "Y"
    assert w.votes == 500000


def test_read_bhuky_winners_handles_uncontested(tmp_path: Path) -> None:
    """Surat 2024-style row (single candidate, Votes='Unconteste')."""
    state_codes_csv = _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "6", "lgd_name": "Gujarat",
         "iso_3166_2": "IN-GJ", "census_2001_code": "24",
         "census_2011_code": "24", "kind": "state",
         "slug": "gujarat", "aliases": ""},
    ])
    bhuky_csv = _write_bhuky_csv(tmp_path, [
        {"State": "Gujarat", "Constituency": "Surat",
         "Party": "Bharatiya Janata Party", "Candidate": "Mukesh Dalal",
         "Votes": "Unconteste", "State ID": "S06", "Constituency ID": "2"},
    ])
    state_ix = _load_state_index(state_codes_csv)
    winners = _read_bhuky_winners(bhuky_csv, state_ix)
    assert len(winners) == 1
    assert winners[0].votes is None  # placeholder -> None
    assert winners[0].party_full == "Bharatiya Janata Party"


def test_read_bhuky_winners_applies_constituency_name_remap(tmp_path: Path) -> None:
    """jharkhand/PALAMAU (bhuky) -> jharkhand/PALAMU (yen-gov canonical)."""
    state_codes_csv = _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Jharkhand",
         "iso_3166_2": "IN-JH", "census_2001_code": "20",
         "census_2011_code": "20", "kind": "state",
         "slug": "jharkhand", "aliases": ""},
    ])
    bhuky_csv = _write_bhuky_csv(tmp_path, [
        {"State": "Jharkhand", "Constituency": "Palamau",
         "Party": "Bharatiya Janata Party", "Candidate": "X",
         "Votes": "100000", "State ID": "S20", "Constituency ID": "1"},
    ])
    state_ix = _load_state_index(state_codes_csv)
    winners = _read_bhuky_winners(bhuky_csv, state_ix)
    assert len(winners) == 1
    # Bhuky's PALAMAU is canonicalised to PALAMU per the 4-case remap.
    assert winners[0].constituency_name_upper == "PALAMU"


def test_read_bhuky_winners_skips_unknown_state(tmp_path: Path) -> None:
    state_codes_csv = _write_state_codes_csv(tmp_path, [])
    bhuky_csv = _write_bhuky_csv(tmp_path, [
        {"State": "Fictional Land", "Constituency": "X",
         "Party": "X", "Candidate": "X", "Votes": "100",
         "State ID": "?", "Constituency ID": "1"},
    ])
    state_ix = _load_state_index(state_codes_csv)
    winners = _read_bhuky_winners(bhuky_csv, state_ix)
    assert winners == []


# --- YEN-GOV PC NO INDEX --------------------------------------------------


def test_yen_gov_pc_no_index_extracts_from_entity_id(tmp_path: Path) -> None:
    """entity_id 'IN-PC-2008-tamil-nadu-503' -> constituency_no '503'."""
    _write_summary_csv(tmp_path, 2024, [
        {"entity_id": "IN-PC-2008-tamil-nadu-503", "state": "tamil-nadu",
         "constituency_name": "ARAKKONAM", "winner_party_id": "parties.IN.DMK"},
        {"entity_id": "IN-PC-2008-uttar-pradesh-50", "state": "uttar-pradesh",
         "constituency_name": "VARANASI", "winner_party_id": "parties.IN.BJP"},
    ])
    ix = _yen_gov_pc_no_index(tmp_path / "datasets", 2024)
    assert ix[("tamil-nadu", "ARAKKONAM")] == "503"
    assert ix[("uttar-pradesh", "VARANASI")] == "50"


def test_yen_gov_pc_no_index_missing_summary_returns_empty(tmp_path: Path) -> None:
    """No summary.csv on disk -> empty map (adapter emits cno='?')."""
    ix = _yen_gov_pc_no_index(tmp_path / "datasets", 2024)
    assert ix == {}


# --- END-TO-END ADAPTER ---------------------------------------------------


def test_adapter_end_to_end_minimal_fixture(tmp_path: Path) -> None:
    """Full adapter pass on a 3-PC fixture -> 3 per-PC shape-A rows."""
    _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
        {"lgd_state_id": "2", "lgd_name": "Gujarat",
         "iso_3166_2": "IN-GJ", "census_2001_code": "24",
         "census_2011_code": "24", "kind": "state",
         "slug": "gujarat", "aliases": ""},
    ])
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.BJP", "short": "BJP",
         "full": "Bharatiya Janata Party"},
        {"party_id": "parties.IN.INC", "short": "INC",
         "full": "Indian National Congress"},
    ])
    _write_bhuky_csv(tmp_path, [
        # Araku - INC wins.
        {"State": "Andhra Pradesh", "Constituency": "Araku",
         "Party": "Indian National Congress", "Candidate": "X",
         "Votes": "500000", "State ID": "S01", "Constituency ID": "1"},
        # Anantapur - BJP wins.
        {"State": "Andhra Pradesh", "Constituency": "Anantapur",
         "Party": "Bharatiya Janata Party", "Candidate": "B",
         "Votes": "400000", "State ID": "S01", "Constituency ID": "2"},
        # Surat - BJP unopposed.
        {"State": "Gujarat", "Constituency": "Surat",
         "Party": "Bharatiya Janata Party", "Candidate": "M",
         "Votes": "Unconteste", "State ID": "S06", "Constituency ID": "2"},
    ])
    # Summary has only 2 of the 3 PCs (Surat missing - canonical's known gap).
    _write_summary_csv(tmp_path, 2024, [
        {"entity_id": "IN-PC-2008-andhra-pradesh-1", "state": "andhra-pradesh",
         "constituency_name": "ARAKU", "winner_party_id": "parties.IN.INC"},
        {"entity_id": "IN-PC-2008-andhra-pradesh-2", "state": "andhra-pradesh",
         "constituency_name": "ANANTAPUR", "winner_party_id": "parties.IN.BJP"},
    ])

    adapter = BhukyavenkatamaheshPcAdapter()
    rows = list(adapter(
        root=tmp_path, vintage="2024", event="LsGenJun2024",
        kind="parliament",
    ))
    assert len(rows) == 3
    by_pc = {(r.state_code, r.constituency_no, r.constituency_name): r for r in rows}
    araku = by_pc[("andhra-pradesh", "1", "ARAKU")]
    assert araku.proposed_party_id == "parties.IN.INC"
    assert araku.winner_votes == 500000
    anantapur = by_pc[("andhra-pradesh", "2", "ANANTAPUR")]
    assert anantapur.proposed_party_id == "parties.IN.BJP"
    surat = by_pc[("gujarat", "?", "SURAT")]  # missing from canonical summary
    assert surat.proposed_party_id == "parties.IN.BJP"
    assert surat.winner_votes is None
    # All rows carry the adapter's scope + pin.
    for r in rows:
        assert r.external_scope == BHUKY_SCOPE
        assert r.external_vintage == BHUKY_VINTAGE


def test_adapter_emits_stable_order_across_runs(tmp_path: Path) -> None:
    """Same snapshot -> same per-PC emission order (sort by (slug, cname))."""
    _write_state_codes_csv(tmp_path, [
        {"lgd_state_id": "1", "lgd_name": "Andhra Pradesh",
         "iso_3166_2": "IN-AP", "census_2001_code": "1",
         "census_2011_code": "1", "kind": "state",
         "slug": "andhra-pradesh", "aliases": ""},
    ])
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.BJP", "short": "BJP", "full": "X"},
    ])
    _write_bhuky_csv(tmp_path, [
        {"State": "Andhra Pradesh", "Constituency": "Z", "Party": "X",
         "Candidate": "X", "Votes": "100", "State ID": "S01", "Constituency ID": "1"},
        {"State": "Andhra Pradesh", "Constituency": "A", "Party": "X",
         "Candidate": "X", "Votes": "100", "State ID": "S01", "Constituency ID": "2"},
        {"State": "Andhra Pradesh", "Constituency": "M", "Party": "X",
         "Candidate": "X", "Votes": "100", "State ID": "S01", "Constituency ID": "3"},
    ])
    adapter = BhukyavenkatamaheshPcAdapter()
    rows1 = list(adapter(root=tmp_path, vintage="2024", event="LsGenJun2024"))
    rows2 = list(adapter(root=tmp_path, vintage="2024", event="LsGenJun2024"))
    cnames1 = [r.constituency_name for r in rows1]
    cnames2 = [r.constituency_name for r in rows2]
    assert cnames1 == cnames2
    assert cnames1 == ["A", "M", "Z"]
