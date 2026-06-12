"""PR-Q7b tests for the event-data-status flipper tool.

Pin the behaviour of ``tools/flip_event_data_status``:

  (1) An event with ``data_status: pending_upstream`` flips to
      ``complete`` when ``candidacies.csv`` exists on disk with non-empty
      content.
  (2) An event with ``data_status: pending_upstream`` is NOT flipped
      when no disk file exists (or the file is header-only).
  (3) Other event fields (``notes``, ``event_id_aliases``, ``polled_on``,
      ``term_end_estimated``) are preserved byte-stably across the flip.

All fixtures synthetic under ``tmp_path``; no real-corpus walk.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.flip_event_data_status.__main__ import main


GEO_CSV_HEADER = "entity_id,name,parent,entity_kind,aliases,lgd_id,state_iso\n"
GEO_TAMIL_NADU = "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"


def _write_geo(root: Path) -> Path:
    geo = root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(GEO_CSV_HEADER + GEO_TAMIL_NADU, encoding="utf-8")
    return geo


def _write_event_catalogue(root: Path, payload: dict) -> Path:
    path = root / "datasets" / "taxonomy" / "election_events.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _write_candidacies(
    root: Path,
    state_slug: str,
    year: int,
    n_data_rows: int = 1,
) -> Path:
    """Write a minimal candidacies.csv with ``n_data_rows`` data lines."""
    path = (
        root / "datasets" / "elections" / "assembly"
        / f"state={state_slug}" / f"election={year}" / "candidacies.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "entity_id,state,election_year,constituency_no,constituency_name\n"
    body = ""
    for i in range(n_data_rows):
        body += f"IN-AC-1976-{state_slug}-{i+1},{state_slug},{year},{i+1},AC-{i+1}\n"
    path.write_text(header + body, encoding="utf-8")
    return path


# --- Test 1: flip pending -> complete when disk is present ------------------


def test_flip_pending_to_complete_when_disk_present(tmp_path):
    """One event, on-disk candidacies present -> data_status flipped."""
    _write_geo(tmp_path)
    catalogue_path = _write_event_catalogue(
        tmp_path,
        {
            "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
            "$schema_version": "1.3",
            "sources": [],
            "states": {
                "S22": [
                    {
                        "event_id": "assembly-1980",
                        "kind": "assembly",
                        "display": "Tamil Nadu Assembly - 1980",
                        "polled_on": "1980-05-01",
                        "term_end_estimated": "1985-05-01",
                        "data_status": "pending_upstream",
                        "notes": "Synthetic test event.",
                        "event_id_aliases": ["AcGenMay1980"],
                    }
                ]
            },
        },
    )
    _write_candidacies(tmp_path, "tamil-nadu", 1980, n_data_rows=2)

    rc = main(["--apply", "--root", str(tmp_path)])
    assert rc == 0

    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    event = updated["states"]["S22"][0]
    assert event["data_status"] == "complete"
    # Other fields preserved exactly.
    assert event["notes"] == "Synthetic test event."
    assert event["event_id_aliases"] == ["AcGenMay1980"]
    assert event["polled_on"] == "1980-05-01"
    assert event["term_end_estimated"] == "1985-05-01"


# --- Test 2: no flip when disk is absent or header-only ---------------------


def test_no_flip_when_disk_empty(tmp_path):
    """No on-disk candidacies file -> data_status STAYS pending_upstream.

    Also asserts that a HEADER-ONLY candidacies.csv (zero data rows) is
    treated as empty and does not advance the flip.
    """
    _write_geo(tmp_path)
    catalogue_path = _write_event_catalogue(
        tmp_path,
        {
            "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
            "$schema_version": "1.3",
            "sources": [],
            "states": {
                "S22": [
                    {
                        "event_id": "assembly-1980",
                        "kind": "assembly",
                        "display": "Tamil Nadu Assembly - 1980",
                        "polled_on": "1980-05-01",
                        "term_end_estimated": None,
                        "data_status": "pending_upstream",
                        "notes": "Missing disk.",
                        "event_id_aliases": ["AcGenMay1980"],
                    },
                    {
                        "event_id": "assembly-1985",
                        "kind": "assembly",
                        "display": "Tamil Nadu Assembly - 1985",
                        "polled_on": "1985-05-01",
                        "term_end_estimated": None,
                        "data_status": "pending_upstream",
                        "notes": "Empty disk file.",
                        "event_id_aliases": ["AcGenMay1985"],
                    },
                ]
            },
        },
    )
    # Note: NO file for 1980. Header-only file for 1985.
    empty_path = (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=1985" / "candidacies.csv"
    )
    empty_path.parent.mkdir(parents=True, exist_ok=True)
    empty_path.write_text(
        "entity_id,state,election_year,constituency_no,constituency_name\n",
        encoding="utf-8",
    )

    rc = main(["--apply", "--root", str(tmp_path)])
    assert rc == 0

    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    events = {e["event_id"]: e for e in updated["states"]["S22"]}
    assert events["assembly-1980"]["data_status"] == "pending_upstream"
    assert events["assembly-1985"]["data_status"] == "pending_upstream"


# --- Test 3: preserves other event fields ----------------------------------


def test_preserves_other_fields(tmp_path):
    """Notes / event_id_aliases / polled_on / etc. survive the flip unchanged.

    Same byte-identical shape as Test 1's assertion but parametrised over
    more fields to make the invariant explicit -- if a future refactor of
    ``apply_flips`` accidentally drops a key, this fails loudly.
    """
    _write_geo(tmp_path)
    rich_event = {
        "event_id": "assembly-1980",
        "kind": "assembly",
        "display": "Tamil Nadu Assembly - 1980",
        "polled_on": "1980-05-01",
        "term_end_estimated": "1985-05-01",
        "data_status": "pending_upstream",
        "notes": "Multi-phase poll 1-3 May 1980. Source: TCPD compilation.",
        "event_id_aliases": ["AcGenMay1980", "TN-AE-1980"],
    }
    catalogue_path = _write_event_catalogue(
        tmp_path,
        {
            "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
            "$schema_version": "1.3",
            "sources": [],
            "states": {"S22": [dict(rich_event)]},
        },
    )
    _write_candidacies(tmp_path, "tamil-nadu", 1980, n_data_rows=1)

    rc = main(["--apply", "--root", str(tmp_path)])
    assert rc == 0

    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    event = updated["states"]["S22"][0]
    # Only data_status changed.
    expected = dict(rich_event)
    expected["data_status"] = "complete"
    assert event == expected


# --- Dry-run safety ---------------------------------------------------------


def test_dry_run_does_not_write(tmp_path):
    """Default invocation (no ``--apply``) leaves the file byte-stable."""
    _write_geo(tmp_path)
    payload = {
        "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
        "$schema_version": "1.3",
        "sources": [],
        "states": {
            "S22": [
                {
                    "event_id": "assembly-1980",
                    "kind": "assembly",
                    "display": "Tamil Nadu Assembly - 1980",
                    "polled_on": "1980-05-01",
                    "term_end_estimated": None,
                    "data_status": "pending_upstream",
                    "notes": "x",
                    "event_id_aliases": ["AcGenMay1980"],
                }
            ]
        },
    }
    catalogue_path = _write_event_catalogue(tmp_path, payload)
    before = catalogue_path.read_text(encoding="utf-8")
    _write_candidacies(tmp_path, "tamil-nadu", 1980, n_data_rows=1)

    rc = main(["--root", str(tmp_path)])  # no --apply
    assert rc == 0
    assert catalogue_path.read_text(encoding="utf-8") == before


def test_no_double_flip_on_complete_events(tmp_path):
    """Events ALREADY ``complete`` are left alone (even on disk-empty).

    This is the inverse of Test 2 -- the tool never moves an event
    BACKWARDS from ``complete`` to ``pending_upstream``.
    """
    _write_geo(tmp_path)
    catalogue_path = _write_event_catalogue(
        tmp_path,
        {
            "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
            "$schema_version": "1.3",
            "sources": [],
            "states": {
                "S22": [
                    {
                        "event_id": "assembly-2021",
                        "kind": "assembly",
                        "display": "Tamil Nadu Assembly - 2021",
                        "polled_on": "2021-04-06",
                        "term_end_estimated": "2026-04-05",
                        "data_status": "complete",
                        "notes": "Already complete; should stay complete.",
                        "event_id_aliases": ["AcGenApr2021"],
                    }
                ]
            },
        },
    )
    # Deliberately no disk file for this event.
    rc = main(["--apply", "--root", str(tmp_path)])
    assert rc == 0

    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    event = updated["states"]["S22"][0]
    assert event["data_status"] == "complete"
