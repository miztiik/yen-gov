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


# --- PR-Q7c parliament-event tests ------------------------------------------


_GEO_HEADER = "entity_id,name,parent,entity_kind,aliases,lgd_id,state_iso\n"
_GEO_ROWS_FOR_PARLIAMENT = (
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
    "bihar,Bihar,IN,state,IN-BR|S04|lgd:10,10,10\n"
    "andaman-and-nicobar,Andaman and Nicobar,IN,ut,IN-AN|U01|lgd:35,35,35\n"
    "dadra-and-nagar-haveli-and-daman-and-diu,Dadra and Nagar Haveli and Daman"
    " and Diu,IN,ut,IN-DH|U03|lgd:38,38,38\n"
)


def _write_geo_for_parliament(root: Path) -> Path:
    geo = root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_HEADER + _GEO_ROWS_FOR_PARLIAMENT, encoding="utf-8")
    return geo


def _write_parliament_candidacies(
    root: Path,
    year: int,
    state_slugs: list[str],
) -> Path:
    """Write a parliament candidacies.csv with one row per state slug.

    Parliament data is COUNTRY-WIDE one file per year, not per-state, so
    the file path lacks the ``state=`` partition.
    """
    path = (
        root / "datasets" / "elections" / "parliament"
        / f"election={year}" / "candidacies.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "entity_id,state,election_year,constituency_no,constituency_name\n"
    body = ""
    for i, slug in enumerate(state_slugs):
        body += f"IN-PC-1976-{slug}-{i+1},{slug},{year},{i+1},PC-{i+1}\n"
    path.write_text(header + body, encoding="utf-8")
    return path


def test_flip_parliament_general_event_when_disk_present(tmp_path):
    """Parliament event ``general-1999`` flips when a non-empty file exists.

    Stage one state's parliament event as pending_upstream + write the
    matching parliament candidacies.csv with a row for that state slug.
    The flipper recognises the parliament path and flips the event to
    complete.
    """
    _write_geo_for_parliament(tmp_path)
    catalogue_path = _write_event_catalogue(
        tmp_path,
        {
            "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
            "$schema_version": "1.3",
            "sources": [],
            "states": {
                "S04": [
                    {
                        "event_id": "general-1999",
                        "kind": "parliament",
                        "display": "Bihar - Parliament 1999",
                        "polled_on": "1999-09-05",
                        "term_end_estimated": "2004-02-06",
                        "data_status": "pending_upstream",
                        "notes": "13th Lok Sabha; pending TCPD GE reingest.",
                    }
                ]
            },
        },
    )
    _write_parliament_candidacies(tmp_path, 1999, ["bihar"])

    rc = main(["--apply", "--root", str(tmp_path)])
    assert rc == 0

    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    event = updated["states"]["S04"][0]
    assert event["data_status"] == "complete"
    assert event["notes"] == "13th Lok Sabha; pending TCPD GE reingest."


def test_flip_parliament_state_slug_divergence_mapping(tmp_path):
    """``PARLIAMENT_TCPD_TO_GEO_SLUG`` normalises U01 + U03 slug divergences.

    The parliament binder emits ``andaman-and-nicobar-islands`` for U01
    (TCPD State_Name slugifies that way) but geo.csv carries the
    canonical ``andaman-and-nicobar``. The map normalises so the flip
    succeeds for the U01 event.

    Likewise the pre-2020 ``dadra-and-nagar-haveli`` and ``daman-and-diu``
    both map to U03 (post-2020 merged form on geo.csv).
    """
    _write_geo_for_parliament(tmp_path)
    catalogue_path = _write_event_catalogue(
        tmp_path,
        {
            "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
            "$schema_version": "1.3",
            "sources": [],
            "states": {
                "U01": [
                    {
                        "event_id": "general-1999",
                        "kind": "parliament",
                        "display": "Andaman and Nicobar - Parliament 1999",
                        "polled_on": "1999-09-05",
                        "term_end_estimated": "2004-02-06",
                        "data_status": "pending_upstream",
                    }
                ],
                "U03": [
                    {
                        "event_id": "general-1999",
                        "kind": "parliament",
                        "display": "Dadra Nagar Haveli Daman Diu - Parliament 1999",
                        "polled_on": "1999-09-05",
                        "term_end_estimated": "2004-02-06",
                        "data_status": "pending_upstream",
                    }
                ],
            },
        },
    )
    # Parliament file carries the TCPD-binder slugs (NOT geo.csv slugs).
    _write_parliament_candidacies(
        tmp_path, 1999,
        ["andaman-and-nicobar-islands", "dadra-and-nagar-haveli", "daman-and-diu"],
    )

    rc = main(["--apply", "--root", str(tmp_path)])
    assert rc == 0

    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    assert updated["states"]["U01"][0]["data_status"] == "complete"
    assert updated["states"]["U03"][0]["data_status"] == "complete"


def test_no_flip_when_parliament_disk_empty(tmp_path):
    """No parliament file on disk -> pending_upstream stays."""
    _write_geo_for_parliament(tmp_path)
    catalogue_path = _write_event_catalogue(
        tmp_path,
        {
            "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
            "$schema_version": "1.3",
            "sources": [],
            "states": {
                "S22": [
                    {
                        "event_id": "general-1999",
                        "kind": "parliament",
                        "display": "Tamil Nadu - Parliament 1999",
                        "polled_on": "1999-09-05",
                        "term_end_estimated": "2004-02-06",
                        "data_status": "pending_upstream",
                    }
                ]
            },
        },
    )
    # No disk file for parliament 1999.
    rc = main(["--apply", "--root", str(tmp_path)])
    assert rc == 0

    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    assert updated["states"]["S22"][0]["data_status"] == "pending_upstream"


def test_parliament_disk_state_not_in_catalogue_is_silent(tmp_path):
    """A state present on disk but absent from catalogue is silently ignored.

    The flipper only acts on events DECLARED in election_events.json; a
    parliament candidacies row for a state whose ECI code is not in the
    catalogue is a no-op (NOT a hard fail). This matches the assembly
    flipper's permissive contract.
    """
    _write_geo_for_parliament(tmp_path)
    catalogue_path = _write_event_catalogue(
        tmp_path,
        {
            "$schema": "https://yen-gov.github.io/schemas/election-events.schema.json",
            "$schema_version": "1.3",
            "sources": [],
            "states": {},  # No events declared.
        },
    )
    _write_parliament_candidacies(tmp_path, 1999, ["bihar"])

    rc = main(["--apply", "--root", str(tmp_path)])
    assert rc == 0

    # File unchanged (no flips applied).
    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    assert updated["states"] == {}
