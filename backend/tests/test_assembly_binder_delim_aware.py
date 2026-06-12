"""PR-Q7a tests for the delim-aware assembly binder.

The binder (``backend/yen_gov/canonical/reingest/assembly_results.py``) was
previously hardcoded to bind TCPD ``DelimID=4`` rows against electoral.csv
without filtering the lookup by ``delim_year``. That was safe only because
every on-disk ``electoral.csv`` row carried ``delim_year=2008`` (the
in-force cycle); the moment PR-Q7b mints historical AC entities (delim
1962 / 1967 / 1976), an unfiltered lookup would collide eci_no's across
delim eras because a state's ``Constituency_No`` numbering re-uses
values across delimitations.

These tests pin the new shape:
  (1) the lookup is delim-aware: same eci_no in different delim eras
      yields different entity_ids;
  (2) the default call path is byte-stable (delim_id=4 -> delim_year=2008
      filter is a no-op for current production electoral.csv);
  (3) the delim_id parameter threads through correctly when historical
      entities exist;
  (4) when delim_id selects a cohort that does not yet exist on disk,
      every row lands in the unbound set and the year is skipped, which
      is the documented pre-PR-Q7b state for delim_id in {1, 2, 3}.

No real-corpus walk (CLAUDE.md anti-pattern). All fixtures are synthetic
under ``tmp_path``.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.reingest import assembly_results
from yen_gov.canonical.reingest.assembly_results import (
    TCPD_DELIM_ID_TO_DELIM_YEAR,
    _electoral_eci_to_entity,
    build_candidacy_rows,
    emit_state_assembly,
)

SOURCE_ID = "src-tcpd-ae-q7a-test"

_AE_HEADER = [
    "State_Name", "Assembly_No", "Constituency_No", "Year", "DelimID",
    "Poll_No", "Position", "Candidate", "Sex", "Party", "Votes", "Age",
    "Deposit_Lost", "Valid_Votes", "Electors", "Constituency_Name",
    "Turnout_Percentage", "Vote_Share_Percentage", "Incumbent", "Turncoat",
    "MyNeta_education", "TCPD_Prof_Main_Desc",
]


def _ae_row(**over) -> dict[str, str]:
    base = {
        "State_Name": "Tamil_Nadu", "Assembly_No": "12", "Constituency_No": "1",
        "Year": "2021", "DelimID": "4", "Poll_No": "0", "Position": "1",
        "Candidate": "A", "Sex": "MALE", "Party": "DMK", "Votes": "100",
        "Age": "50", "Deposit_Lost": "no", "Valid_Votes": "180",
        "Electors": "250", "Constituency_Name": "Ichapuram",
        "Turnout_Percentage": "72.0", "Vote_Share_Percentage": "55.5",
        "Incumbent": "FALSE", "Turncoat": "FALSE",
        "MyNeta_education": "Graduate", "TCPD_Prof_Main_Desc": "Doctor",
    }
    base.update({k: str(v) for k, v in over.items()})
    return base


def _write_ae(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=_AE_HEADER, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in _AE_HEADER})
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")
    return path


def _stage_catalogue(
    root: Path,
    *,
    eci_nos_2008: list[int] = (),  # type: ignore[assignment]
    eci_nos_1976: list[int] = (),  # type: ignore[assignment]
) -> Path:
    """Stage electoral.csv with a mix of delim_year=2008 + delim_year=1976 ACs.

    A real on-disk fixture so the writer reads through ``_read_csv_rows``
    (CSV-shape round-trip is part of the contract under test). ``eci_nos_2008``
    + ``eci_nos_1976`` are the per-cohort ECI ballot serials; entity_ids are
    derived as ``IN-AC-<delim_year>-tamil-nadu-<1000 + eci_no>``.
    """
    entities = root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)

    el_lines = ["entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"]
    for n in eci_nos_2008:
        eid = f"IN-AC-2008-tamil-nadu-{1000 + n}"
        el_lines.append(f"{eid},AC 2008 {n},ac,2008,tamil-nadu,,{n},,GEN")
    for n in eci_nos_1976:
        eid = f"IN-AC-1976-tamil-nadu-{2000 + n}"
        el_lines.append(f"{eid},AC 1976 {n},ac,1976,tamil-nadu,,{n},,GEN")
    (entities / "electoral.csv").write_text("\n".join(el_lines) + "\n", encoding="utf-8")

    (entities / "parties.csv").write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n"
        "parties.IN.UNK,UNK,Unresolved Party,,,,\n",
        encoding="utf-8",
    )
    (entities / "source.csv").write_text(
        "source_id,owner,title,vintage,url\n"
        f"{SOURCE_ID},TCPD,Indian Assembly Elections,2026-06-05,\n",
        encoding="utf-8",
    )
    return entities / "electoral.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- Test 1: lookup helper filters by delim_year ----------------------------


def test_eci_to_entity_filters_by_delim_year(tmp_path):
    """``_electoral_eci_to_entity`` MUST partition by ``delim_year``.

    Same state, same eci_no, two delim eras -> two different entity_ids.
    The lookup returns ONLY the cohort matching the caller's ``delim_year``;
    without this filter, the second-seen row would silently shadow the first
    and the binder would mis-route historical results to the in-force entity.
    """
    electoral = _stage_catalogue(
        tmp_path, eci_nos_2008=[1, 2], eci_nos_1976=[1, 2]
    )
    rows = _read_csv(electoral)
    # Sanity: the fixture really does carry both cohorts for the same eci_no.
    assert len(rows) == 4
    assert {(r["delim_year"], r["eci_no"]) for r in rows} == {
        ("2008", "1"), ("2008", "2"), ("1976", "1"), ("1976", "2"),
    }

    out_2008 = _electoral_eci_to_entity(rows, "tamil-nadu", 2008)
    assert out_2008 == {
        1: "IN-AC-2008-tamil-nadu-1001",
        2: "IN-AC-2008-tamil-nadu-1002",
    }

    out_1976 = _electoral_eci_to_entity(rows, "tamil-nadu", 1976)
    assert out_1976 == {
        1: "IN-AC-1976-tamil-nadu-2001",
        2: "IN-AC-1976-tamil-nadu-2002",
    }

    # A cohort the fixture does NOT carry -> empty (no collision, no fallback).
    out_1967 = _electoral_eci_to_entity(rows, "tamil-nadu", 1967)
    assert out_1967 == {}


# --- Test 2: existing default call path is byte-stable ----------------------


def test_emit_state_assembly_default_delim_unchanged(tmp_path):
    """Default ``delim_id`` (the in-force 2008 cycle) preserves prior behaviour.

    For the current on-disk electoral.csv (every AC row is ``delim_year=2008``),
    adding a ``delim_year=2008`` filter to the lookup is a no-op: same entity
    set, same bind. This test pins that callers that pass NO ``delim_id``
    (every production call-site as of PR-Q7a) get byte-identical output.
    """
    ae_rows = [
        _ae_row(Constituency_No=1, Year=2021, DelimID=4, Position=1,
                Candidate="W", Party="DMK", Votes=100,
                Vote_Share_Percentage=55.5, Deposit_Lost="no"),
        _ae_row(Constituency_No=1, Year=2021, DelimID=4, Position=2,
                Candidate="R", Party="DMK", Votes=80,
                Vote_Share_Percentage=44.5, Deposit_Lost="no"),
    ]
    ae = _write_ae(tmp_path / "datasets" / "ephemeral" / "All_States_AE.csv", ae_rows)
    electoral = _stage_catalogue(tmp_path, eci_nos_2008=[1])

    emitted = emit_state_assembly(
        ae_csv=ae,
        electoral_csv=electoral,
        out_root=tmp_path,
        state_name_tcpd="Tamil_Nadu",
        state_slug="tamil-nadu",
        source_id=SOURCE_ID,
        # NO delim_id kwarg - exercise the default path
    )
    assert set(emitted) == {2021}
    cand = _read_csv(emitted[2021]["candidacies"])
    assert len(cand) == 2
    # Every row binds to the delim-2008 entity, exactly as pre-PR-Q7a.
    assert {r["entity_id"] for r in cand} == {"IN-AC-2008-tamil-nadu-1001"}
    assert emitted[2021]["unbound_eci_nos"] == []


# --- Test 3: delim_id=3 binds against the delim_year=1976 cohort ------------


def test_emit_state_assembly_delim_3_routes_to_1976_entities(tmp_path):
    """When ``delim_id='3'`` AND the 1976 cohort exists, rows bind to it.

    Pins the thread-through: ``delim_id`` -> ``TCPD_DELIM_ID_TO_DELIM_YEAR``
    -> ``_electoral_eci_to_entity`` filter -> ``IN-AC-1976-*`` entity. This
    is the call shape PR-Q7b will use once historical AC entities exist on
    disk.
    """
    ae_rows = [
        _ae_row(Constituency_No=1, Year=1980, DelimID=3, Position=1,
                Candidate="W", Party="DMK", Votes=100,
                Vote_Share_Percentage=55.5, Deposit_Lost="no"),
        _ae_row(Constituency_No=1, Year=1980, DelimID=3, Position=2,
                Candidate="R", Party="DMK", Votes=80,
                Vote_Share_Percentage=44.5, Deposit_Lost="no"),
    ]
    ae = _write_ae(tmp_path / "datasets" / "ephemeral" / "All_States_AE.csv", ae_rows)
    # ONLY the delim_year=1976 entity exists for eci_no=1.
    electoral = _stage_catalogue(tmp_path, eci_nos_1976=[1])

    emitted = emit_state_assembly(
        ae_csv=ae,
        electoral_csv=electoral,
        out_root=tmp_path,
        state_name_tcpd="Tamil_Nadu",
        state_slug="tamil-nadu",
        source_id=SOURCE_ID,
        delim_id="3",  # historical cycle - PR-Q7b call shape
    )
    assert set(emitted) == {1980}
    cand = _read_csv(emitted[1980]["candidacies"])
    assert len(cand) == 2
    # All bind to the 1976 cohort - NOT the 2008 cohort (which does not exist
    # in this fixture; the assertion would also catch an off-by-one in the
    # mapping like DelimID=3 -> delim_year=2008).
    assert {r["entity_id"] for r in cand} == {"IN-AC-1976-tamil-nadu-2001"}
    assert emitted[1980]["unbound_eci_nos"] == []


# --- Test 4: pre-PR-Q7b state (delim_id=3 but no 1976 entities) -------------


def test_emit_state_assembly_delim_mismatch_emits_unbound(tmp_path):
    """Pre-PR-Q7b shape: ``delim_id='3'`` against a delim_year=2008-only catalogue.

    With the new filter the lookup returns an empty cohort, so every
    DelimID=3 AE row's ``Constituency_No`` lands in the ``unbound`` set
    inside ``build_candidacy_rows`` and the year is skipped (the ``if not
    candidacy_rows: continue`` guard fires). No candidacies / summary CSV
    is written. This documents the dependency on PR-Q7b: until historical
    AC entities exist, a ``delim_id`` in {1, 2, 3} call produces an empty
    ``emitted`` dict deterministically rather than silently mis-binding to
    the in-force entity (the pre-PR-Q7a failure mode the filter prevents).
    """
    ae_rows = [
        _ae_row(Constituency_No=1, Year=1980, DelimID=3, Position=1,
                Candidate="W", Party="DMK", Votes=100,
                Vote_Share_Percentage=55.5, Deposit_Lost="no"),
        _ae_row(Constituency_No=1, Year=1980, DelimID=3, Position=2,
                Candidate="R", Party="DMK", Votes=80,
                Vote_Share_Percentage=44.5, Deposit_Lost="no"),
    ]
    ae = _write_ae(tmp_path / "datasets" / "ephemeral" / "All_States_AE.csv", ae_rows)
    # Only delim_year=2008 entities - the current production shape.
    electoral = _stage_catalogue(tmp_path, eci_nos_2008=[1])

    emitted = emit_state_assembly(
        ae_csv=ae,
        electoral_csv=electoral,
        out_root=tmp_path,
        state_name_tcpd="Tamil_Nadu",
        state_slug="tamil-nadu",
        source_id=SOURCE_ID,
        delim_id="3",
    )
    # No year emitted - every row was unbound, so the year was skipped.
    assert emitted == {}
    # No on-disk artefact written for the would-be 1980 election.
    assert not (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=1980" / "candidacies.csv"
    ).exists()

    # And the lower-layer mechanism: build_candidacy_rows surfaces the eci
    # in unbound directly, even though emit_state_assembly drops the year.
    # Exercising it here pins the per-row contract that the surrounding
    # emit layer relies on.
    electoral_rows = _read_csv(electoral)
    eci_to_entity = _electoral_eci_to_entity(electoral_rows, "tamil-nadu", 1976)
    assert eci_to_entity == {}, "delim_year=1976 cohort is empty in this fixture"
    rows, unbound = build_candidacy_rows(
        source_rows=ae_rows,
        eci_to_entity=eci_to_entity,
        state_slug="tamil-nadu",
        election_year=1980,
        source_id=SOURCE_ID,
    )
    assert rows == []
    assert unbound == {1}


# --- Public-surface sanity --------------------------------------------------


def test_delim_id_to_year_mapping_covers_known_tcpd_delim_ids():
    """The mapping covers every TCPD DelimID value observed on All_States_AE.csv.

    TCPD AE.csv year-ranges (established by the PR-Q7a diagnostic):
      DelimID 1: 1961-1965 -> 1962
      DelimID 2: 1964-1972 -> 1967
      DelimID 3: 1974-2012 -> 1976
      DelimID 4: 2008-2023 -> 2008
    Future delim cycles (post-2023 elections under a new delimitation
    commission) add a new entry - the constant is exhaustive over the
    publisher's current vocabulary; new entries require a doctrine edit.
    """
    assert TCPD_DELIM_ID_TO_DELIM_YEAR == {
        "1": 1962,
        "2": 1967,
        "3": 1976,
        "4": 2008,
    }
    # Default delim_id in emit_state_assembly resolves to delim_year=2008.
    assert TCPD_DELIM_ID_TO_DELIM_YEAR[assembly_results.DELIM_ID_2008] == 2008
