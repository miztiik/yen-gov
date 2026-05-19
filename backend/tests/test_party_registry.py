"""Tests for the eci_code party registry + Section-3-driven parties.json emit.

PR-R.3 (1.8e closure) retired the prior 3-layer registry
(per-event parties.json + ``reference/in/parties-discovered.json``
overlay + ``reference/in/parties.json`` master). The single source of
truth is now ``datasets/taxonomy/parties.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.core.models import SourceRef
from yen_gov.pipeline.compose import (
    PartyRegistryEntry,
    load_eci_party_registry,
    parties_snapshot_from_section3,
)
from yen_gov.sources.eci.section3 import ParticipatingParty


def _write_taxonomy(path: Path, *, parties: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "$schema": "../schemas/taxonomy-parties.schema.json",
            "$schema_version": "2.1",
            "sources": [{
                "url": "https://en.wikipedia.org/wiki/List_of_political_parties_in_India",
                "fetched_at": "2026-05-19T00:00:00Z",
                "name": "Reference parties roster",
                "authority": "yen-gov editorial",
            }],
            "parties": parties,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_registry_loads_from_taxonomy(tmp_path: Path) -> None:
    """A registry built from the canonical taxonomy resolves short_names."""
    datasets = tmp_path / "datasets"
    _write_taxonomy(
        datasets / "taxonomy" / "parties.json",
        parties=[
            {
                "party_id": "parties.IN.INC",
                "short_name": "INC",
                "full_name": "Indian National Congress",
                "aliases": [],
                "eci_codes": ["742"],
            },
            {
                "party_id": "parties.IN.DMK",
                "short_name": "DMK",
                "full_name": "Dravida Munnetra Kazhagam",
                "aliases": [],
                "eci_codes": ["582"],
            },
        ],
    )

    # Caller passes elections_root; registry reads ../taxonomy/parties.json.
    registry = load_eci_party_registry(datasets / "elections")

    assert "INC" in registry and "DMK" in registry
    assert registry["INC"].eci_code == "742"
    assert registry["INC"].full_name == "Indian National Congress"
    assert any("wikipedia.org" in u for u in registry["INC"].source_urls)


def test_registry_resolves_aliases_to_same_entry(tmp_path: Path) -> None:
    """``aliases[]`` entries point at the same PartyRegistryEntry as the canonical short."""
    datasets = tmp_path / "datasets"
    _write_taxonomy(
        datasets / "taxonomy" / "parties.json",
        parties=[{
            "party_id": "parties.IN.AIADMK",
            "short_name": "AIADMK",
            "full_name": "All India Anna Dravida Munnetra Kazhagam",
            "aliases": ["ADMK", "AIADMK(JR)"],
            "eci_codes": ["201"],
        }],
    )
    registry = load_eci_party_registry(datasets / "elections")

    assert "AIADMK" in registry
    assert "ADMK" in registry
    assert "AIADMK(JR)" in registry
    assert registry["AIADMK"] is registry["ADMK"]
    assert registry["ADMK"].eci_code == "201"


def test_registry_eci_code_none_for_taxonomy_entries_without_codes(tmp_path: Path) -> None:
    """A roster entry without observed ECI codes carries ``eci_code=None``."""
    datasets = tmp_path / "datasets"
    _write_taxonomy(
        datasets / "taxonomy" / "parties.json",
        parties=[{
            "party_id": "parties.IN.NEWP",
            "short_name": "NEWP",
            "full_name": "Newly Registered Party",
            "aliases": [],
            "eci_codes": [],
        }],
    )
    registry = load_eci_party_registry(datasets / "elections")

    assert "NEWP" in registry
    assert registry["NEWP"].eci_code is None


def test_registry_returns_empty_when_taxonomy_absent(tmp_path: Path) -> None:
    """Fresh checkout with no taxonomy file → empty dict (caller skips emit)."""
    registry = load_eci_party_registry(tmp_path / "datasets" / "elections")
    assert registry == {}


def test_section3_snapshot_resolves_against_registry() -> None:
    """``parties_snapshot_from_section3`` keeps only registry-resolved entries
    and reports the rest as unresolved."""
    section_3 = [
        ParticipatingParty(party_type="NATIONAL PARTIES", short_name="INC", full_name="Indian National Congress"),
        ParticipatingParty(party_type="NATIONAL PARTIES", short_name="BJP", full_name="Bharatiya Janata Party"),
        ParticipatingParty(party_type="STATE PARTIES", short_name="ZPM", full_name="Zoram People's Movement"),
    ]
    registry = {
        "INC": PartyRegistryEntry(
            eci_code="742", full_name="Indian National Congress",
            source_urls=("https://en.wikipedia.org/wiki/List_of_political_parties_in_India",),
        ),
        "BJP": PartyRegistryEntry(
            eci_code="1924", full_name="Bharatiya Janata Party",
            source_urls=("https://en.wikipedia.org/wiki/List_of_political_parties_in_India",),
        ),
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
    urls = {s.url for s in snapshot.sources}
    assert any("List_Of_Political_Parties_Participated" in u for u in urls)
    assert any("wikipedia.org" in u for u in urls)


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
