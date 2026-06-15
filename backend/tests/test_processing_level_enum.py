"""Per-row processing_level / processing_note vocabulary contract.

Uses ``tmp_path`` fixtures per CLAUDE.md section 10 anti-pattern (no pytest
test may walk the real on-disk corpus; that is the Tier-B validator's job
via ``python -m yen_gov validate --root .``). These unit tests pin the
``derive_processing`` helper's enum + note-shape contract; the parity
oracle in ``test_summary_equals_recompute_candidacies.py`` already exercises
the field on every real (state, election) slice indirectly.

Doctrine: docs/concepts/data-quality.md.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.processing_quality import (
    UNK_PARTY_ID,
    derive_processing,
    derive_processing_for_party_founded_year_backfill,
)


_VALID_LEVELS = frozenset({"minor", "major"})


def test_derive_processing_minor_default() -> None:
    """A resolved party_id (anything except UNK) -> minor + empty note."""
    level, note = derive_processing("parties.IN.INC", "INC")
    assert level == "minor"
    assert note == ""


def test_derive_processing_major_on_unk() -> None:
    """UNK fall-through is the only fresh-write trigger for major; the
    note quotes the publisher label so the curator follow-up has the
    raw upstream string verbatim."""
    level, note = derive_processing(UNK_PARTY_ID, "MYSTERY_PARTY")
    assert level == "major"
    assert "MYSTERY_PARTY" in note
    assert "unk-ledger" in note


def test_derive_processing_major_on_unk_empty_label() -> None:
    """UNK with an empty publisher label still emits a non-empty note
    (the bookkeeping pointer survives even without a label hint)."""
    level, note = derive_processing(UNK_PARTY_ID, "")
    assert level == "major"
    assert note != ""

    level_none, note_none = derive_processing(UNK_PARTY_ID, None)
    assert level_none == "major"
    assert note_none != ""


def test_processing_note_non_empty_iff_major() -> None:
    """Contract: processing_note is empty iff processing_level == minor.
    Asserted on a tmp_path-written fixture CSV (no real corpus walk)."""
    rows = [
        {"party_id": "parties.IN.INC", "party_short_raw": "INC"},
        {"party_id": "parties.IN.BJP", "party_short_raw": "BJP"},
        {"party_id": UNK_PARTY_ID, "party_short_raw": "RANDOM"},
        {"party_id": UNK_PARTY_ID, "party_short_raw": ""},
    ]
    derived = [derive_processing(r["party_id"], r["party_short_raw"]) for r in rows]
    for level, note in derived:
        assert level in _VALID_LEVELS
        if level == "major":
            assert note != ""
        else:
            assert note == ""


def test_unk_rows_all_get_major(tmp_path: Path) -> None:
    """Write a small candidacies-shape CSV with mixed party_ids under
    tmp_path; assert every UNK row would carry major + non-empty note,
    every non-UNK row carries minor + empty note. Mirrors the runtime
    invariant the writers + backfill both honour."""
    cand_csv = tmp_path / "candidacies.csv"
    fieldnames = [
        "entity_id", "party_id", "party_short_raw",
        "processing_level", "processing_note",
    ]
    with cand_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for i, (pid, short) in enumerate([
            ("parties.IN.INC", "INC"),
            (UNK_PARTY_ID, "FOO"),
            ("parties.IN.BJP", "BJP"),
            (UNK_PARTY_ID, "BAR"),
        ]):
            level, note = derive_processing(pid, short)
            writer.writerow({
                "entity_id": f"IN-AC-2008-fixture-{i}",
                "party_id": pid,
                "party_short_raw": short,
                "processing_level": level,
                "processing_note": note,
            })

    with cand_csv.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 4
    for row in rows:
        assert row["processing_level"] in _VALID_LEVELS
        if row["party_id"] == UNK_PARTY_ID:
            assert row["processing_level"] == "major"
            assert row["processing_note"] != ""
        else:
            assert row["processing_level"] == "minor"
            assert row["processing_note"] == ""


@pytest.mark.parametrize(
    "party_id,short_raw,expected_level",
    [
        ("parties.IN.INC", "INC", "minor"),
        ("parties.IN.BJP", "BJP", "minor"),
        ("parties.IN.NOTA", "NOTA", "minor"),
        ("parties.IN.IND", "IND", "minor"),
        (UNK_PARTY_ID, "OFP", "major"),
        (UNK_PARTY_ID, None, "major"),
    ],
)
def test_derive_processing_enum_membership(
    party_id: str, short_raw: str | None, expected_level: str,
) -> None:
    """Spot-check enum membership: every output level is in the closed
    vocabulary; the level matches the UNK-vs-not asymmetry."""
    level, _ = derive_processing(party_id, short_raw)
    assert level in _VALID_LEVELS
    assert level == expected_level


def _load_backfill_summary_tags():
    """Import the segment-aware summary classifier from
    ``tools/backfill_processing_level.py`` without making ``tools``
    importable globally. Stays inside ``tmp_path``-style discipline by
    importing through a local path lookup."""
    import importlib.util

    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "tools" / "backfill_processing_level.py"
    spec = importlib.util.spec_from_file_location(
        "_backfill_processing_level_under_test", module_path,
    )
    assert spec is not None and spec.loader is not None, (
        f"could not load module spec from {module_path}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tcpd_sourced_ls_summary_rows_tag_major(tmp_path: Path) -> None:
    """Parliament-chamber summary rows for the TCPD-sourced LS years
    (1999, 2004, 2009, 2014, 2019) flip from ``minor`` to ``major`` with
    the segment-aggregation note. Assembly chamber AND parliament 2024+
    stay ``minor``. UNK rows still win over the segment override.

    Exercised via the backfill helper's ``_expected_summary_tags`` directly
    (no real-corpus walk per CLAUDE.md section 10 anti-pattern; the Tier-B
    validator + the parity oracle in
    ``test_summary_equals_recompute_candidacies.py`` cover the on-disk
    cross-product)."""

    backfill = _load_backfill_summary_tags()
    inc_row = {"winner_party_id": "parties.IN.INC", "winner_party_short_raw": "INC"}
    unk_row = {"winner_party_id": UNK_PARTY_ID, "winner_party_short_raw": "MYSTERY"}

    # All five TCPD LS years -> major + segment note.
    for year in ("1999", "2004", "2009", "2014", "2019"):
        level, note = backfill._expected_summary_tags(
            inc_row, chamber="parliament", election_year=year,
        )
        assert level == "major", f"parliament {year} INC should flip to major"
        assert "TCPD All_States_GA.csv" in note
        assert "AC-segment aggregation" in note

    # 2024 onward stays minor (direct-PC TCPD CSV is published).
    level_2024, note_2024 = backfill._expected_summary_tags(
        inc_row, chamber="parliament", election_year="2024",
    )
    assert level_2024 == "minor"
    assert note_2024 == ""

    # Assembly chamber never flips, even for TCPD LS years.
    for year in ("1999", "2004", "2009", "2014", "2019"):
        level, note = backfill._expected_summary_tags(
            inc_row, chamber="assembly", election_year=year,
        )
        assert level == "minor", f"assembly {year} INC must NOT flip to major"
        assert note == ""

    # UNK winner gate still wins over the segment override.
    level_unk, note_unk = backfill._expected_summary_tags(
        unk_row, chamber="parliament", election_year="2009",
    )
    assert level_unk == "major"
    assert "MYSTERY" in note_unk
    assert "unk-ledger" in note_unk
    assert "TCPD All_States_GA.csv" not in note_unk


# ---------------------------------------------------------------------------
# PR-1 of TODO/20260615-party-page-citizen-fixes-plan.md: parties.csv
# founded_year backfill helper. Sibling to derive_processing (NOT a
# replacement); pins L-1 doctrine for the catalogue surface.
# ---------------------------------------------------------------------------


def test_party_founded_year_backfill_helper_returns_major_plus_note() -> None:
    """The parties.csv founded_year backfill always returns major + the L-1
    note verbatim. processing_level is in the closed vocabulary; note is
    non-empty (matches the processing_note non-empty iff major contract)."""
    level, note = derive_processing_for_party_founded_year_backfill("parties.IN.BSP")
    assert level == "major"
    assert level in _VALID_LEVELS
    assert note != ""
    # L-1 verbatim phrasing: operational receipt for the discretionary call.
    assert "third-party party-catalogue website" in note
    assert "2026-06-15" in note
    assert "cross-checked against publisher records" in note


def test_party_founded_year_backfill_helper_does_not_name_third_party_site() -> None:
    """L-2 doctrine extension to L-1: the note text MUST NOT name the
    acquisition site. Forbidden tokens (wikipedia, .com, .org, http) are
    operational knowledge in the curator's notebook, not row content."""
    _level, note = derive_processing_for_party_founded_year_backfill("parties.IN.CPIM")
    lowered = note.lower()
    assert "wikipedia" not in lowered
    assert ".com" not in lowered
    assert ".org" not in lowered
    assert "http://" not in lowered
    assert "https://" not in lowered


def test_party_founded_year_backfill_helper_is_party_id_agnostic() -> None:
    """The party_id argument is accepted (reserved for future per-party
    divergence) but does not change the return value today. Every backfilled
    row receives the same (major, L-1 note) pair so the data writer can call
    the helper inline without branching."""
    bsp = derive_processing_for_party_founded_year_backfill("parties.IN.BSP")
    cpim = derive_processing_for_party_founded_year_backfill("parties.IN.CPIM")
    npp = derive_processing_for_party_founded_year_backfill("parties.IN.NPP")
    ajsu = derive_processing_for_party_founded_year_backfill("parties.IN.AJSU")
    assert bsp == cpim == npp == ajsu


def test_party_founded_year_backfill_helper_is_sibling_not_replacement() -> None:
    """The candidacy/summary derive_processing helper keeps its UNK-only
    major trigger; the parties.csv helper does NOT disturb that contract.
    A non-UNK candidacy row still resolves to (minor, '')."""
    cand_level, cand_note = derive_processing("parties.IN.INC", "INC")
    assert cand_level == "minor"
    assert cand_note == ""
    # The two helpers are independent surfaces.
    party_level, party_note = derive_processing_for_party_founded_year_backfill(
        "parties.IN.INC",
    )
    assert party_level == "major"
    assert party_note != ""
