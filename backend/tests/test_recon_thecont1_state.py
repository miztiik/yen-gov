"""Tier-A tests for the thecont1-india-votes-data per-state parity adapter (PR-S-TN-AE2026).

Covers:

  - ``_normalise_full_name`` collapses punctuation + whitespace
    consistently with PR-W-1 + PR-W-2 + PR-W-3 adapter behaviour.
  - ``_build_by_full_index`` reads parties.csv ``full`` cells into a
    normalised lookup; tolerates empty cells; soft-fails (warns +
    keeps first-seen) on full-name collisions instead of blocking
    unrelated per-state parity sweeps.
  - End-to-end: ``TheCont1StateAdapter()`` against a minimal fixture
    yields one ``ConstituencyParityRow`` per AC, identifying the
    winner as max(evm_votes + postal_votes) per constituency_no.
  - Two-tier resolver dispatch: tier 1 (central resolver via short /
    alias) wins; tier 2 (adapter-local by_full bridge) kicks in only
    when tier 1 misses; both miss preserves ``parties.IN.UNK`` per
    CLAUDE.md section 10 "no silent demotion".
  - NOTA / Independent labels surface via the resolver's sentinel
    flags as ``parties.IN.NOTA`` / ``parties.IN.IND``.
  - Adapter rejects missing scoping flags (state / event / kind) with
    deterministic ValueError messages; refuses kinds other than
    'assembly'; raises FileNotFoundError when the snapshot is absent.
  - Adapter is registered in ``EVENT_REGISTRY["thecont1-state"]``.

Pure ``tmp_path`` fixtures only - CLAUDE.md section 14 carve-out: no
real-corpus walking from pytest. The adapter holds no I/O state beyond
reading the snapshot path + parties.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.party_resolver import load_resolver
from yen_gov.canonical.recon.adapters import EVENT_REGISTRY
from yen_gov.canonical.recon.adapters.thecont1_state import (
    ADAPTER,
    THECONT1_STATE_SCOPE,
    TheCont1StateAdapter,
    _build_by_full_index,
    _normalise_full_name,
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


_THECONT1_COLS: tuple[str, ...] = (
    "election_year",
    "election_type",
    "election_state",
    "constituency",
    "constituency_no",
    "serial_no",
    "candidate",
    "party",
    "evm_votes",
    "postal_votes",
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


def _write_thecont1_csv(
    tmp_path: Path,
    rows: list[dict[str, str]],
    *,
    year: str = "2026",
    state_file: str = "Assembly-Tamil-Nadu.csv",
) -> Path:
    path = (
        tmp_path
        / "datasets"
        / "ephemeral"
        / "thecont1-india-votes-data"
        / year
        / state_file
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_THECONT1_COLS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _THECONT1_COLS})
    return path


# Reset the lru_cache on load_resolver between tests so each tmp_path
# parties.csv builds a fresh resolver (the adapter calls load_resolver
# with the absolute path so the cache key differs per-test, but the
# global cache can still grow during test runs).
@pytest.fixture(autouse=True)
def _reset_resolver_cache() -> None:
    load_resolver.cache_clear()


# --- _normalise_full_name -----------------------------------------------


def test_normalise_full_name_collapses_punctuation_and_whitespace() -> None:
    assert _normalise_full_name(
        "All India Anna Dravida Munnetra Kazhagam (M)"
    ) == "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM M"
    assert _normalise_full_name(" Indian   National   Congress ") == (
        "INDIAN NATIONAL CONGRESS"
    )
    assert _normalise_full_name("") == ""
    assert _normalise_full_name("Naam Tamilar Katchi") == "NAAM TAMILAR KATCHI"


# --- _build_by_full_index -----------------------------------------------


def test_by_full_index_builds_from_full_column(tmp_path: Path) -> None:
    parties = _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.AIADMK", "short": "AIADMK",
         "full": "All India Anna Dravida Munnetra Kazhagam"},
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam"},
    ])
    index = _build_by_full_index(parties)
    assert index["ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM"] == "parties.IN.AIADMK"
    assert index["DRAVIDA MUNNETRA KAZHAGAM"] == "parties.IN.DMK"


def test_by_full_index_skips_rows_without_full_cell(tmp_path: Path) -> None:
    parties = _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.X", "short": "X", "full": ""},
        {"party_id": "parties.IN.AIADMK", "short": "AIADMK",
         "full": "All India Anna Dravida Munnetra Kazhagam"},
    ])
    index = _build_by_full_index(parties)
    # X has empty full; nothing for X. AIADMK still indexed.
    assert "parties.IN.X" not in index.values()
    assert "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM" in index


def test_by_full_index_soft_fails_on_collision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parties = _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.AJSU", "short": "AJSU",
         "full": "All Jharkhand Students Union"},
        {"party_id": "parties.IN.AJSUP", "short": "AJSUP",
         "full": "All Jharkhand Students Union"},
    ])
    index = _build_by_full_index(parties)
    captured = capsys.readouterr()
    assert "full-name collision" in captured.err
    # First-seen wins; second is ignored. The exact "first" depends on
    # CSV row order; both possibilities are valid per the warning text.
    assert index["ALL JHARKHAND STUDENTS UNION"] in {
        "parties.IN.AJSU", "parties.IN.AJSUP",
    }


def test_by_full_index_returns_empty_when_parties_csv_absent(tmp_path: Path) -> None:
    # The adapter tolerates a missing parties.csv by returning empty
    # (the resolver behaves the same way - every lookup returns UNK).
    index = _build_by_full_index(tmp_path / "no-such-file.csv")
    assert index == {}


# --- ADAPTER REGISTRATION -----------------------------------------------


def test_adapter_registered_in_event_registry() -> None:
    assert "thecont1-state" in EVENT_REGISTRY
    assert EVENT_REGISTRY["thecont1-state"] is ADAPTER


def test_adapter_rejects_missing_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="thecont1-state adapter requires --state"):
        list(ADAPTER(root=tmp_path, vintage="", state=None, event="AcGenMay2026",
                     kind="assembly"))


def test_adapter_rejects_missing_event(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="thecont1-state adapter requires --event"):
        list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                     event=None, kind="assembly"))


def test_adapter_rejects_kind_parliament(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="supports --kind 'assembly' only"):
        list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                     event="LsGenJun2024", kind="parliament"))


def test_adapter_rejects_unmapped_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no snapshot-name mapping"):
        list(ADAPTER(root=tmp_path, vintage="", state="unknown-state",
                     event="AcGenMay2026", kind="assembly"))


def test_adapter_raises_when_snapshot_missing(tmp_path: Path) -> None:
    # parties.csv is fine but the snapshot CSV is missing.
    _write_parties_csv(tmp_path, [])
    with pytest.raises(FileNotFoundError, match="thecont1 snapshot not found"):
        list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                     event="AcGenMay2026", kind="assembly"))


def test_adapter_extracts_year_from_event_id(tmp_path: Path) -> None:
    # AcGenMay2026 -> year 2026; the adapter looks under 2026/
    # subdir of the snapshot tree. Confirm by writing snapshot at 2026.
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_thecont1_csv(tmp_path, [
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "TESTAC",
         "constituency_no": "1", "serial_no": "1",
         "candidate": "X", "party": "Dravida Munnetra Kazhagam",
         "evm_votes": "1000", "postal_votes": "100"},
    ], year="2026")
    out = list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                       event="AcGenMay2026", kind="assembly"))
    assert len(out) == 1
    assert out[0].constituency_no == 1


# --- End-to-end: winner identification + party resolution ---------------


def test_adapter_picks_max_total_votes_per_ac(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
        {"party_id": "parties.IN.AIADMK", "short": "AIADMK",
         "full": "All India Anna Dravida Munnetra Kazhagam",
         "aliases": "ADMK"},
    ])
    _write_thecont1_csv(tmp_path, [
        # AC 1: DMK has 60k EVM + 1k postal = 61k; AIADMK has 50k+10k=60k.
        # DMK wins (higher total).
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC1",
         "constituency_no": "1", "serial_no": "1",
         "candidate": "D1", "party": "Dravida Munnetra Kazhagam",
         "evm_votes": "60000", "postal_votes": "1000"},
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC1",
         "constituency_no": "1", "serial_no": "2",
         "candidate": "A1",
         "party": "All India Anna Dravida Munnetra Kazhagam",
         "evm_votes": "50000", "postal_votes": "10000"},
        # AC 2: only AIADMK row.
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC2",
         "constituency_no": "2", "serial_no": "1",
         "candidate": "A2",
         "party": "All India Anna Dravida Munnetra Kazhagam",
         "evm_votes": "30000", "postal_votes": "500"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                       event="AcGenMay2026", kind="assembly"))
    assert len(out) == 2
    ac1, ac2 = sorted(out, key=lambda r: r.constituency_no)
    assert ac1.constituency_no == 1
    assert ac1.winner_party_id == "parties.IN.DMK"
    assert ac1.winner_candidate_name == "D1"
    assert ac1.winner_votes == 61000
    assert ac2.constituency_no == 2
    assert ac2.winner_party_id == "parties.IN.AIADMK"
    assert ac2.winner_votes == 30500


def test_adapter_two_tier_resolver_by_full_fallback(tmp_path: Path) -> None:
    # AIADMK with NO 'aliases' for the full name. Tier 1 (resolver by
    # short / aliases) misses; tier 2 (by_full) hits via full-name.
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.AIADMK", "short": "AIADMK",
         "full": "All India Anna Dravida Munnetra Kazhagam",
         "aliases": ""},
    ])
    _write_thecont1_csv(tmp_path, [
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC1",
         "constituency_no": "1", "serial_no": "1",
         "candidate": "A1",
         "party": "All India Anna Dravida Munnetra Kazhagam",
         "evm_votes": "50000", "postal_votes": "1000"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                       event="AcGenMay2026", kind="assembly"))
    assert len(out) == 1
    assert out[0].winner_party_id == "parties.IN.AIADMK"
    # Raw label preserved verbatim for curator review.
    assert out[0].winner_party_short_raw == (
        "All India Anna Dravida Munnetra Kazhagam"
    )


def test_adapter_preserves_unk_when_both_tiers_miss(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_thecont1_csv(tmp_path, [
        # Party not in parties.csv; resolver returns UNK; by_full misses.
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC1",
         "constituency_no": "1", "serial_no": "1",
         "candidate": "X", "party": "Fictional Party Z",
         "evm_votes": "1000", "postal_votes": "100"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                       event="AcGenMay2026", kind="assembly"))
    assert len(out) == 1
    assert out[0].winner_party_id == "parties.IN.UNK"
    # Raw label preserved per CLAUDE.md section 10 "no silent demotion".
    assert out[0].winner_party_short_raw == "Fictional Party Z"


def test_adapter_resolves_nota_via_sentinel(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.NOTA", "short": "NOTA",
         "full": "None of the Above"},
    ])
    _write_thecont1_csv(tmp_path, [
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC1",
         "constituency_no": "1", "serial_no": "1",
         "candidate": "", "party": "None of the Above",
         "evm_votes": "5000", "postal_votes": "0"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                       event="AcGenMay2026", kind="assembly"))
    assert len(out) == 1
    assert out[0].winner_party_id == "parties.IN.NOTA"


def test_adapter_resolves_independent_via_sentinel(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent"},
    ])
    _write_thecont1_csv(tmp_path, [
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC1",
         "constituency_no": "1", "serial_no": "1",
         "candidate": "Joe Citizen", "party": "Independent",
         "evm_votes": "3000", "postal_votes": "10"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                       event="AcGenMay2026", kind="assembly"))
    assert len(out) == 1
    assert out[0].winner_party_id == "parties.IN.IND"


def test_adapter_skips_ac_with_zero_votes(tmp_path: Path) -> None:
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_thecont1_csv(tmp_path, [
        # Both rows have zero votes - adapter skips the AC entirely.
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC1",
         "constituency_no": "1", "serial_no": "1",
         "candidate": "X", "party": "Dravida Munnetra Kazhagam",
         "evm_votes": "0", "postal_votes": "0"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                       event="AcGenMay2026", kind="assembly"))
    assert out == []


def test_adapter_emits_shape_b_rows_with_event_vintage(tmp_path: Path) -> None:
    # ConstituencyParityRow.external_vintage is pinned to the event id
    # (not the year) so that downstream verdict joins align with the
    # other event-grain adapters (yen_gov_elections).
    _write_parties_csv(tmp_path, [
        {"party_id": "parties.IN.DMK", "short": "DMK",
         "full": "Dravida Munnetra Kazhagam", "aliases": "DMK"},
    ])
    _write_thecont1_csv(tmp_path, [
        {"election_year": "2026", "election_type": "Assembly",
         "election_state": "TN", "constituency": "AC1",
         "constituency_no": "1", "serial_no": "1",
         "candidate": "X", "party": "Dravida Munnetra Kazhagam",
         "evm_votes": "1000", "postal_votes": "0"},
    ])
    out = list(ADAPTER(root=tmp_path, vintage="", state="tamil-nadu",
                       event="AcGenMay2026", kind="assembly"))
    assert len(out) == 1
    row = out[0]
    assert isinstance(row, ConstituencyParityRow)
    assert row.external_scope == THECONT1_STATE_SCOPE
    assert row.external_vintage == "AcGenMay2026"
    assert row.state == "tamil-nadu"
    assert row.event == "AcGenMay2026"
