"""Tests for the Section 3 (List of Political Parties Participated) parser.

Uses the live-fetched Assam-2026 XLSX under `.runtime/raw/eci/...` when
present (skipped on CI / fresh checkouts).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.sources.eci.section3 import parse_section3_parties

ASSAM_2026_XLSX = (
    Path(__file__).resolve().parents[2]
    / ".runtime" / "raw" / "eci" / "eci-backend" / "public" / "all_files"
    / "election_report"
    / "General_Election_to_the_Legislative_Assembly_of_Assam_2026_2026"
    / "3-List_Of_Political_Parties_Participated_1778163955.xlsx"
)


@pytest.mark.skipif(
    not ASSAM_2026_XLSX.exists(),
    reason="raw Assam-2026 Section 3 fixture not downloaded; run "
           "eci-statreport S03 2026 --download --skip-pdf to populate",
)
def test_parses_assam_2026_groups_and_rows() -> None:
    parties = parse_section3_parties(ASSAM_2026_XLSX.read_bytes())

    # Header + four group labels in the source: NATIONAL / STATE / STATE
    # PARTIES - OTHER STATES / REGISTERED(Unrecognised). Every data row
    # should be tagged with one of them.
    types = {p.party_type for p in parties}
    assert "NATIONAL PARTIES" in types
    assert "STATE PARTIES" in types
    assert any("REGISTERED" in t for t in types)

    # Every parsed row has both short and full names. No row inherits the
    # group-header text in the short_name slot (that was the off-by-one
    # bug class we want to guard against).
    assert all(p.short_name and p.full_name for p in parties)
    assert "PARTIES" not in {p.short_name for p in parties}

    # Spot-check a known entry — BJP appears under NATIONAL PARTIES with
    # the canonical full name.
    bjp = next((p for p in parties if p.short_name == "BJP"), None)
    assert bjp is not None
    assert bjp.party_type == "NATIONAL PARTIES"
    assert "Bharatiya Janata Party" in bjp.full_name
