"""Tests for the eci_code party registry + Section-3-driven parties.json emit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.core.models import SourceRef
from yen_gov.pipeline.compose import (
    PartyRegistryEntry,
    load_eci_party_registry,
    parties_snapshot_from_section3,
)
from yen_gov.sources.eci.section3 import ParticipatingParty


def _write_parties_json(path: Path, *, sources: list[dict], parties: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "$schema": "https://yen-gov.github.io/schemas/party.schema.json",
            "$schema_version": "3.1",
            "sources": sources,
            "election": "AcGenMay2026",
            "parties": parties,
        }),
        encoding="utf-8",
    )


def test_registry_aggregates_from_existing_parties_files(tmp_path: Path) -> None:
    """A registry built from two cohorts merges shorts and dedupes URLs."""
    _write_parties_json(
        tmp_path / "AcGenMay2026/S22/parties.json",
        sources=[{"url": "https://results.eci.gov.in/A/partywiseresult-S22.htm",
                  "fetched_at": "2026-05-09T12:00:00Z"}],
        parties=[
            {"eci_code": "742", "short_name": "INC", "full_name": "Indian National Congress"},
            {"eci_code": "582", "short_name": "DMK", "full_name": "Dravida Munnetra Kazhagam"},
        ],
    )
    _write_parties_json(
        tmp_path / "AcGenMay2026/S25/parties.json",
        sources=[{"url": "https://results.eci.gov.in/A/partywiseresult-S25.htm",
                  "fetched_at": "2026-05-09T12:00:00Z"}],
        parties=[
            {"eci_code": "742", "short_name": "INC", "full_name": "Indian National Congress"},
            {"eci_code": "300", "short_name": "AITC", "full_name": "All India Trinamool Congress"},
        ],
    )
    registry = load_eci_party_registry(tmp_path)

    assert set(registry) == {"INC", "DMK", "AITC"}
    inc = registry["INC"]
    assert inc.eci_code == "742"
    # INC appears in both files, so both partywise URLs contribute.
    assert "partywiseresult-S22.htm" in " ".join(inc.source_urls)
    assert "partywiseresult-S25.htm" in " ".join(inc.source_urls)


def test_registry_raises_on_eci_code_conflict(tmp_path: Path) -> None:
    """Same short → two different eci_codes is a data-integrity error, not silent overwrite."""
    _write_parties_json(
        tmp_path / "AcGenMay2026/S22/parties.json",
        sources=[{"url": "https://x/p.htm", "fetched_at": "2026-05-09T12:00:00Z"}],
        parties=[{"eci_code": "742", "short_name": "INC", "full_name": "Indian National Congress"}],
    )
    _write_parties_json(
        tmp_path / "AcGenMay2026/S25/parties.json",
        sources=[{"url": "https://y/p.htm", "fetched_at": "2026-05-09T12:00:00Z"}],
        parties=[{"eci_code": "999", "short_name": "INC", "full_name": "Indian National Congress"}],
    )
    with pytest.raises(ValueError, match="eci_code conflict for short 'INC'"):
        load_eci_party_registry(tmp_path)


def test_section3_snapshot_resolves_against_registry() -> None:
    """parties_snapshot_from_section3 keeps only registry-resolved entries
    and reports the rest as unresolved."""
    section_3 = [
        ParticipatingParty(party_type="NATIONAL PARTIES", short_name="INC", full_name="Indian National Congress"),
        ParticipatingParty(party_type="NATIONAL PARTIES", short_name="BJP", full_name="Bharatiya Janata Party"),
        ParticipatingParty(party_type="STATE PARTIES", short_name="ZPM", full_name="Zoram People's Movement"),
    ]
    registry = {
        "INC": PartyRegistryEntry(eci_code="742", full_name="Indian National Congress",
                                   source_urls=("https://results.eci.gov.in/A/partywiseresult-S22.htm",)),
        "BJP": PartyRegistryEntry(eci_code="1924", full_name="Bharatiya Janata Party",
                                   source_urls=("https://results.eci.gov.in/A/partywiseresult-S22.htm",)),
    }
    snapshot, unresolved = parties_snapshot_from_section3(
        section_3,
        election="AcGenNov2023",
        section_3_source=SourceRef(
            url="https://www.eci.gov.in/eci-backend/public/all_files/full-statistical-reports/mizoram/2023/List_Of_Political_Parties_Participated.xlsx",
            fetched_at="2026-05-12T10:00:00Z",
        ),
        registry=registry,
        fetched_at="2026-05-12T10:00:00Z",
    )

    assert snapshot is not None
    assert {p.short_name for p in snapshot.parties} == {"INC", "BJP"}
    assert unresolved == ["ZPM"]
    # sources[]: Section 3 URL + the partywise URL that minted the codes.
    urls = {s.url for s in snapshot.sources}
    assert any("List_Of_Political_Parties_Participated" in u for u in urls)
    assert any("partywiseresult-S22.htm" in u for u in urls)


def test_section3_snapshot_returns_none_when_nothing_resolves() -> None:
    """Zero resolved → caller skips parties.json (schema requires minItems: 1)."""
    section_3 = [
        ParticipatingParty(party_type="STATE PARTIES", short_name="OBSCURE", full_name="Obscure Party"),
    ]
    snapshot, unresolved = parties_snapshot_from_section3(
        section_3,
        election="AcGenNov2023",
        section_3_source=SourceRef(url="https://x/s3.xlsx", fetched_at="2026-05-12T10:00:00Z"),
        registry={},
        fetched_at="2026-05-12T10:00:00Z",
    )
    assert snapshot is None
    assert unresolved == ["OBSCURE"]
