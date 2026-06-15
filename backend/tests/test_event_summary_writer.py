"""Tests for the event_summary derived mart writer (PR-E2 of elections-redesign-plan).

Bounded canaries per CLAUDE.md anti-pattern: synthetic fixtures, no corpus
scans. The shipped-data contract test lives in the frontend Tier-A suite
(PR-E3); this module tests the WRITER's shape + aggregation + idempotence
on tiny fixtures.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.derived.event_summary import (
    EVENT_SUMMARY_REL,
    refresh_event_summary_mart,
)


SUMMARY_HEADER = (
    "entity_id,state,election_year,constituency_name,electors,votes_polled,"
    "turnout_pct,winner_candidate,winner_party_id,winner_party_short_raw,"
    "winner_votes,winner_share_pct,runnerup_candidate,runnerup_party_id,"
    "runnerup_party_short_raw,runnerup_votes,margin_votes,margin_pct,"
    "source_id,processing_level,processing_note\n"
)


def _write_min_schema(root: Path) -> None:
    """Ship the minimum columns.json the write_csv contract needs."""
    schema_dir = root / "datasets" / "data" / "_schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "columns.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "./columns.schema.json",
                "x-version": "2.2",
                "type": "object",
                "additionalProperties": False,
                "required": ["$schema", "$schema_version", "file_classes"],
                "properties": {
                    "$schema": {"const": "./columns.schema.json"},
                    "$schema_version": {"type": "string", "pattern": r"^\d+\.\d+$"},
                    "file_classes": {
                        "type": "object",
                        "minProperties": 1,
                        "propertyNames": {"type": "string"},
                        "additionalProperties": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["columns"],
                            "properties": {
                                "notes": {"type": "string"},
                                "columns": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["name", "dtype", "nullable"],
                                        "properties": {
                                            "name": {"type": "string"},
                                            "dtype": {"enum": ["string", "integer", "number", "boolean", "date", "datetime"]},
                                            "nullable": {"type": "boolean"},
                                            "pk": {"type": "boolean"},
                                            "fk": {"type": "string"},
                                            "enum": {"type": "array", "items": {"type": "string"}},
                                            "derived": {"type": "boolean"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (schema_dir / "columns.json").write_text(
        json.dumps(
            {
                "$schema": "./columns.schema.json",
                "$schema_version": "2.2",
                "file_classes": {
                    "datasets/data/marts/elections/event_summary.csv": {
                        "columns": [
                            {"name": "event_id", "dtype": "string", "nullable": False, "pk": True},
                            {"name": "state_code", "dtype": "string", "nullable": True, "pk": True},
                            {"name": "scope", "dtype": "string", "nullable": False, "enum": ["national", "state"]},
                            {"name": "kind", "dtype": "string", "nullable": False, "enum": ["parliament", "assembly", "assembly_bye", "general_bye", "by_election"]},
                            {"name": "polled_on", "dtype": "string", "nullable": False},
                            {"name": "leading_party_id", "dtype": "string", "nullable": True},
                            {"name": "seats_won", "dtype": "integer", "nullable": False},
                            {"name": "seats_contested", "dtype": "integer", "nullable": False},
                            {"name": "turnout_pct", "dtype": "number", "nullable": True, "derived": True},
                            {"name": "runner_up_party_id", "dtype": "string", "nullable": True},
                            {"name": "runner_up_seats", "dtype": "integer", "nullable": True},
                            {"name": "source_id", "dtype": "string", "nullable": False},
                        ],
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_state_codes(root: Path) -> None:
    path = root / "datasets" / "data" / "entities" / "state_codes.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "lgd_state_id,lgd_name,iso_3166_2,census_2001_code,census_2011_code,kind,slug,aliases\n"
        "10,Bihar,IN-BR,,,state,bihar,\n"
        "22,Tamil Nadu,IN-TN,,,state,tamil-nadu,\n"
        "07,Delhi,IN-DL,,,ut,delhi,\n",
        encoding="utf-8",
    )


def _write_source(root: Path) -> None:
    path = root / "datasets" / "data" / "entities" / "source.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "source_id,producer,title,vintage,url\n"
        "src-existing0001,SeedProducer,Seed Source,2026-01-01,https://example.com/seed\n",
        encoding="utf-8",
    )


def _write_catalogue(root: Path) -> None:
    """Three states, three events: TN-assembly-2026, BR-assembly-2020, parliament-2024."""
    path = root / "datasets" / "taxonomy" / "election_events.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "$schema_version": "1.3",
                "states": {
                    "S22": [
                        {"event_id": "assembly-2026", "kind": "assembly", "polled_on": "2026-05-08", "display": "Tamil Nadu Assembly . May 2026"},
                        {"event_id": "general-2024", "kind": "parliament", "polled_on": "2024-06-01", "display": "Tamil Nadu . Parliament 2024"},
                    ],
                    "S04": [
                        {"event_id": "assembly-2020", "kind": "assembly", "polled_on": "2020-11-10", "display": "Bihar Assembly . November 2020"},
                        {"event_id": "general-2024", "kind": "parliament", "polled_on": "2024-06-01", "display": "Bihar . Parliament 2024"},
                    ],
                    "U05": [
                        {"event_id": "assembly-2025", "kind": "assembly", "polled_on": "2025-02-08", "display": "NCT of Delhi Assembly . February 2025"},
                        {"event_id": "general-2024", "kind": "parliament", "polled_on": "2024-06-01", "display": "NCT of Delhi . Parliament 2024"},
                    ],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_summary(
    path: Path,
    *,
    winners: list[tuple[str, int, int]],
    state_slug: str,
    year: int,
) -> None:
    """Write a minimal summary.csv with N winner rows.

    winners: list of (winner_party_id, electors, votes_polled)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [SUMMARY_HEADER.rstrip()]
    for idx, (party_id, electors, votes_polled) in enumerate(winners, start=1):
        # The writer only consults: winner_party_id, electors, votes_polled.
        # All other columns are blank/zero for the fixture.
        lines.append(
            f"IN-FIX-{idx},{state_slug},{year},FIX-{idx},{electors},{votes_polled},"
            f"0.0,WINNER,{party_id},WP,1000,50.0,RUNNER,parties.IN.RU,RU,500,500,5.0,"
            "src-existing0001,minor,"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    _write_min_schema(tmp_path)
    _write_state_codes(tmp_path)
    _write_source(tmp_path)
    _write_catalogue(tmp_path)
    return tmp_path


def test_writer_emits_rows_for_matched_events(repo_root: Path) -> None:
    """Catalogue-matched events produce one row per (event_id, state_code)."""
    # TN assembly 2026: BJP 60, DMK 80, AIADMK 60 -> DMK leads
    _write_summary(
        repo_root / "datasets/elections/assembly/state=tamil-nadu/election=2026/summary.csv",
        winners=[("parties.IN.DMK", 1000, 800)] * 80
        + [("parties.IN.BJP", 1000, 700)] * 60
        + [("parties.IN.AIADMK", 1000, 750)] * 60,
        state_slug="tamil-nadu",
        year=2026,
    )
    # Parliament 2024: 2 states each contribute a few PCs
    _write_summary(
        repo_root / "datasets/elections/parliament/election=2024/summary.csv",
        winners=[("parties.IN.BJP", 1000, 700)] * 20
        + [("parties.IN.INC", 1000, 650)] * 10,
        state_slug="all-india",
        year=2024,
    )
    result = refresh_event_summary_mart(repo_root)
    assert result.row_count == 2  # 1 national + 1 state (TN); BR + Delhi have no summary
    assert result.national_row_count == 1
    assert result.state_row_count == 1

    rows = list(csv.DictReader((repo_root / EVENT_SUMMARY_REL).open(encoding="utf-8")))
    # National parliament-2024 row
    nat = next(r for r in rows if r["scope"] == "national")
    assert nat["event_id"] == "general-2024"
    assert nat["state_code"] == ""  # NULL serialised as empty
    assert nat["kind"] == "parliament"
    assert nat["polled_on"] == "2024-06-01"
    assert nat["leading_party_id"] == "parties.IN.BJP"
    assert nat["seats_won"] == "20"
    assert nat["seats_contested"] == "30"
    assert nat["runner_up_party_id"] == "parties.IN.INC"
    assert nat["runner_up_seats"] == "10"

    # State assembly-2026 row
    st = next(r for r in rows if r["scope"] == "state")
    assert st["event_id"] == "assembly-2026"
    assert st["state_code"] == "S22"
    assert st["kind"] == "assembly"
    assert st["leading_party_id"] == "parties.IN.DMK"
    assert st["seats_won"] == "80"
    assert st["seats_contested"] == "200"
    # Runner-up between BJP and AIADMK (tied at 60); deterministic alphabetical
    # tie-break inside the writer picks parties.IN.AIADMK first (sorted asc).
    assert st["runner_up_party_id"] == "parties.IN.AIADMK"
    assert st["runner_up_seats"] == "60"


def test_writer_is_idempotent(repo_root: Path) -> None:
    """Two consecutive runs on unchanged input yield byte-identical CSV."""
    _write_summary(
        repo_root / "datasets/elections/assembly/state=tamil-nadu/election=2026/summary.csv",
        winners=[("parties.IN.DMK", 1000, 800)] * 5,
        state_slug="tamil-nadu",
        year=2026,
    )
    refresh_event_summary_mart(repo_root)
    out_path = repo_root / EVENT_SUMMARY_REL
    first_bytes = out_path.read_bytes()

    refresh_event_summary_mart(repo_root)
    second_bytes = out_path.read_bytes()
    assert first_bytes == second_bytes


def test_writer_upserts_source_row_once(repo_root: Path) -> None:
    """source.csv gains exactly one row across multiple writer runs."""
    _write_summary(
        repo_root / "datasets/elections/assembly/state=tamil-nadu/election=2026/summary.csv",
        winners=[("parties.IN.DMK", 1000, 800)] * 5,
        state_slug="tamil-nadu",
        year=2026,
    )
    source_path = repo_root / "datasets/data/entities/source.csv"
    rows_before = list(csv.DictReader(source_path.open(encoding="utf-8")))
    refresh_event_summary_mart(repo_root)
    rows_after_1 = list(csv.DictReader(source_path.open(encoding="utf-8")))
    refresh_event_summary_mart(repo_root)
    rows_after_2 = list(csv.DictReader(source_path.open(encoding="utf-8")))

    assert len(rows_after_1) == len(rows_before) + 1
    assert len(rows_after_2) == len(rows_after_1)
    # The appended row carries the deterministic mart source_id.
    new_row = rows_after_1[-1]
    assert new_row["producer"] == "yen-gov"
    assert new_row["title"] == "Per-event election summary aggregate (event_summary.csv)"
    assert new_row["source_id"].startswith("src-")


def test_writer_turnout_is_event_scope_average(repo_root: Path) -> None:
    """turnout_pct = SUM(votes_polled) / SUM(electors) * 100 across the event."""
    # TN assembly 2026: 2 ACs, total electors 3000, total votes_polled 2400 -> 80.0%
    _write_summary(
        repo_root / "datasets/elections/assembly/state=tamil-nadu/election=2026/summary.csv",
        winners=[("parties.IN.DMK", 1000, 800), ("parties.IN.DMK", 2000, 1600)],
        state_slug="tamil-nadu",
        year=2026,
    )
    refresh_event_summary_mart(repo_root)
    rows = list(csv.DictReader((repo_root / EVENT_SUMMARY_REL).open(encoding="utf-8")))
    st = next(r for r in rows if r["scope"] == "state")
    assert float(st["turnout_pct"]) == pytest.approx(80.0, abs=0.01)


def test_writer_skips_files_without_catalogue_match(repo_root: Path) -> None:
    """Folders whose year doesn't match any catalogue event are skipped + counted."""
    # 1999 is not in the catalogue -> skipped
    _write_summary(
        repo_root / "datasets/elections/assembly/state=tamil-nadu/election=1999/summary.csv",
        winners=[("parties.IN.DMK", 1000, 800)] * 5,
        state_slug="tamil-nadu",
        year=1999,
    )
    result = refresh_event_summary_mart(repo_root)
    assert result.skipped_files == 1
    assert result.row_count == 0


def test_writer_handles_delhi_via_nct_alias(repo_root: Path) -> None:
    """The slug->ECI bridge resolves `delhi` -> `U05` via the NCT-of alias."""
    _write_summary(
        repo_root / "datasets/elections/assembly/state=delhi/election=2025/summary.csv",
        winners=[("parties.IN.BJP", 1000, 700)] * 48,
        state_slug="delhi",
        year=2025,
    )
    result = refresh_event_summary_mart(repo_root)
    assert result.state_row_count == 1
    rows = list(csv.DictReader((repo_root / EVENT_SUMMARY_REL).open(encoding="utf-8")))
    st = next(r for r in rows if r["scope"] == "state")
    assert st["state_code"] == "U05"
    assert st["event_id"] == "assembly-2025"
