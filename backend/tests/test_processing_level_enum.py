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
