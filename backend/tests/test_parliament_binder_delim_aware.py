"""PR-Q7c tests for the delim-aware parliament binder.

The parliament binder (``backend/yen_gov/canonical/reingest/
parliament_results.py``) was previously safe to call across delims only
because every on-disk ``electoral.csv`` PC row carried ``delim_year=2008``
(the in-force cycle); the moment PR-Q7c mints historical PC entities
(delim 1962 / 1967 / 1976), an unfiltered lookup would collide eci_no's
across delim eras because a state's ``Constituency_No`` numbering re-uses
values across delimitations.

These tests pin the new shape (mirror of PR-Q7a's
test_assembly_binder_delim_aware for the parliament axis):

  (1) ``_pc_eci_to_entity`` is delim-aware: same eci_no in different
      delim eras yields different entity_ids;
  (2) the default call path is byte-stable (delim_id=4 -> delim_year=2008
      filter is a no-op for current production electoral.csv);
  (3) the delim_id parameter threads through emit_parliament correctly
      when historical entities exist;
  (4) when delim_id selects a cohort that does not yet exist on disk,
      every row lands in the unbound set and the year is skipped, which
      is the documented pre-PR-Q7c state for delim_id in {1, 2, 3};
  (5) cross-delim entity_id stability: an electoral.csv carrying BOTH
      delim_year=1976 + delim_year=2008 PCs for the same (state, eci_no)
      resolves to the cohort matching the binder's delim_id.

No real-corpus walk (CLAUDE.md anti-pattern). All fixtures synthetic
under ``tmp_path``.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.reingest import parliament_results
from yen_gov.canonical.reingest.parliament_results import (
    _pc_eci_to_entity,
    emit_parliament,
)

SOURCE_ID = "src-tcpd-ge-q7c-test"

_GE_HEADER = [
    "State_Name", "Constituency_No", "Year", "DelimID", "Poll_No", "Position",
    "Candidate", "Sex", "Party", "Votes", "Age", "Deposit_Lost", "Valid_Votes",
    "Electors", "Constituency_Name", "Turnout_Percentage",
    "Vote_Share_Percentage", "Incumbent", "Turncoat", "MyNeta_education",
    "TCPD_Prof_Main_Desc",
]


def _ge_row(**over) -> dict[str, str]:
    base = {
        "State_Name": "Bihar", "Constituency_No": "1", "Year": "1999",
        "DelimID": "3", "Poll_No": "0", "Position": "1", "Candidate": "A",
        "Sex": "M", "Party": "INC", "Votes": "100", "Age": "50",
        "Deposit_Lost": "no", "Valid_Votes": "180", "Electors": "250",
        "Constituency_Name": "Patliputra", "Turnout_Percentage": "72.0",
        "Vote_Share_Percentage": "55.5", "Incumbent": "FALSE",
        "Turncoat": "FALSE", "MyNeta_education": "Graduate",
        "TCPD_Prof_Main_Desc": "Lawyer",
    }
    base.update({k: str(v) for k, v in over.items()})
    return base


def _write_ge(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=_GE_HEADER, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in _GE_HEADER})
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")
    return path


def _stage_catalogue(
    root: Path,
    *,
    eci_nos_2008: list[tuple[str, int]] = (),  # type: ignore[assignment]
    eci_nos_1976: list[tuple[str, int]] = (),  # type: ignore[assignment]
) -> Path:
    """Stage electoral.csv with a mix of delim_year=2008 + delim_year=1976 PCs.

    ``eci_nos_2008`` + ``eci_nos_1976`` are lists of ``(state_slug, eci_no)``
    tuples; entity_ids are derived as
    ``IN-PC-<delim_year>-<state>-<eci_no>`` for the historical cohort and
    ``IN-PC-2008-<state>-<2000+eci_no>`` (national LGD-style) for the 2008
    cohort to match the in-force cohort's actual suffix shape.
    """
    entities = root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)

    el_lines = ["entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"]
    for state, n in eci_nos_2008:
        eid = f"IN-PC-2008-{state}-{2000 + n}"
        el_lines.append(f"{eid},PC 2008 {n},pc,2008,{state},,{n},,GEN")
    for state, n in eci_nos_1976:
        eid = f"IN-PC-1976-{state}-{n}"
        el_lines.append(f"{eid},PC 1976 {n},pc,1976,{state},,{n},,GEN")
    (entities / "electoral.csv").write_text("\n".join(el_lines) + "\n", encoding="utf-8")

    (entities / "parties.csv").write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.INC,INC,Indian National Congress,,,,\n"
        "parties.IN.UNK,UNK,Unresolved Party,,,,\n",
        encoding="utf-8",
    )
    (entities / "source.csv").write_text(
        "source_id,owner,title,vintage,url\n"
        f"{SOURCE_ID},TCPD,Indian General Elections,2026-06-05,\n",
        encoding="utf-8",
    )
    return entities / "electoral.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- Test 1: _pc_eci_to_entity filters by delim_year -----------------------


def test_pc_eci_to_entity_filters_by_delim_year(tmp_path):
    """Same (state, eci_no) in different delim eras yields different entity_ids.

    A pre-PR-Q7c unfiltered lookup would resolve the second row to the
    first row's entity_id (silent shadow); the new contract picks the
    cohort matching the requested delim_year.
    """
    electoral = _stage_catalogue(
        tmp_path,
        eci_nos_2008=[("bihar", 1)],
        eci_nos_1976=[("bihar", 1)],
    )
    rows = list(csv.DictReader(electoral.open(encoding="utf-8", newline="")))

    map_2008 = _pc_eci_to_entity(rows, delim_year=2008)
    map_1976 = _pc_eci_to_entity(rows, delim_year=1976)

    assert map_2008[("bihar", 1)] == "IN-PC-2008-bihar-2001"
    assert map_1976[("bihar", 1)] == "IN-PC-1976-bihar-1"
    # The maps are disjoint by construction (different entity_id per cohort).
    assert set(map_2008.values()).isdisjoint(set(map_1976.values()))


# --- Test 2: byte-stable default (delim_id=4 path unchanged) ----------------


def test_emit_parliament_default_delim_id_4_byte_stable(tmp_path):
    """Calling ``emit_parliament`` with the default delim is byte-stable.

    The default ``delim_id=DELIM_ID_2008`` (= 4) selects ``delim_year=2008``;
    a production-shape electoral.csv that ONLY carries delim_year=2008 PCs
    resolves identically pre- and post-PR-Q7c (the new ``delim_year`` filter
    is a no-op for the in-force cohort).
    """
    ge = _write_ge(
        tmp_path / "datasets" / "ephemeral" / "All_States_GE.csv",
        [
            _ge_row(State_Name="Bihar", DelimID=4, Year=2014,
                    Constituency_No=1, Position=1, Candidate="W"),
            _ge_row(State_Name="Bihar", DelimID=4, Year=2014,
                    Constituency_No=1, Position=2, Candidate="R", Votes=50),
        ],
    )
    electoral = _stage_catalogue(tmp_path, eci_nos_2008=[("bihar", 1)])
    entities = electoral.parent

    emitted = emit_parliament(
        ge_csv=ge,
        electoral_csv=electoral,
        out_root=tmp_path,
        source_id=SOURCE_ID,
        parties_csv=entities / "parties.csv",
    )
    assert set(emitted) == {2014}
    cand = _read_csv(emitted[2014]["candidacies"])
    assert {r["entity_id"] for r in cand} == {"IN-PC-2008-bihar-2001"}


# --- Test 3: delim_id threads through correctly when historical exists ------


def test_emit_parliament_delim_id_3_binds_against_1976(tmp_path):
    """``emit_parliament(delim_id='3')`` binds against the 1976 PC cohort."""
    ge = _write_ge(
        tmp_path / "datasets" / "ephemeral" / "All_States_GE.csv",
        [
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=1, Position=1, Candidate="W"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=1, Position=2, Candidate="R", Votes=50),
        ],
    )
    electoral = _stage_catalogue(
        tmp_path,
        eci_nos_2008=[("bihar", 1)],
        eci_nos_1976=[("bihar", 1)],
    )
    entities = electoral.parent

    emitted = emit_parliament(
        ge_csv=ge,
        electoral_csv=electoral,
        out_root=tmp_path,
        source_id=SOURCE_ID,
        delim_id="3",
        parties_csv=entities / "parties.csv",
    )
    assert set(emitted) == {1999}
    cand = _read_csv(emitted[1999]["candidacies"])
    # The DelimID 3 emit picked the 1976 cohort entity_id, NOT the 2008
    # cohort's entity_id (which uses national LGD numbering).
    assert {r["entity_id"] for r in cand} == {"IN-PC-1976-bihar-1"}


# --- Test 4: missing-cohort path lands every row in unbound -----------------


def test_emit_parliament_unbound_when_cohort_missing(tmp_path):
    """``delim_id='3'`` against an electoral.csv carrying ONLY delim_year=2008
    leaves every row unbound and the year is skipped from the emitted map.
    """
    ge = _write_ge(
        tmp_path / "datasets" / "ephemeral" / "All_States_GE.csv",
        [
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=1, Position=1, Candidate="W"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=2, Position=1, Candidate="X"),
        ],
    )
    # Only the in-force cohort on disk (mirror of pre-PR-Q7c state).
    electoral = _stage_catalogue(tmp_path, eci_nos_2008=[("bihar", 1), ("bihar", 2)])
    entities = electoral.parent

    emitted = emit_parliament(
        ge_csv=ge,
        electoral_csv=electoral,
        out_root=tmp_path,
        source_id=SOURCE_ID,
        delim_id="3",
        parties_csv=entities / "parties.csv",
    )
    # Year 1999 has no bound rows -> the emitter SKIPS the year entirely
    # (build_parliament_year returns empty candidacies, the caller's
    # ``if not candidacies: continue`` filter drops it).
    assert emitted == {}


# --- Test 5: cross-delim entity_id stability --------------------------------


def test_emit_parliament_cross_delim_entity_id_stability(tmp_path):
    """Sequential delim calls produce distinct entity_ids for same (state, eci_no).

    Two separate ``emit_parliament`` calls (delim 3 then delim 4) over a
    GE file that has rows in BOTH cycles for the same state+eci_no
    resolve to delim-matching entity_ids each time. This is the binding
    invariant that prevents the cross-cohort silent-shadow bug.
    """
    ge = _write_ge(
        tmp_path / "datasets" / "ephemeral" / "All_States_GE.csv",
        [
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=1, Position=1, Candidate="A"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=1, Position=2, Candidate="B", Votes=50),
            _ge_row(State_Name="Bihar", DelimID=4, Year=2014,
                    Constituency_No=1, Position=1, Candidate="C"),
            _ge_row(State_Name="Bihar", DelimID=4, Year=2014,
                    Constituency_No=1, Position=2, Candidate="D", Votes=50),
        ],
    )
    electoral = _stage_catalogue(
        tmp_path,
        eci_nos_2008=[("bihar", 1)],
        eci_nos_1976=[("bihar", 1)],
    )
    entities = electoral.parent

    emitted_3 = emit_parliament(
        ge_csv=ge, electoral_csv=electoral, out_root=tmp_path,
        source_id=SOURCE_ID, delim_id="3",
        parties_csv=entities / "parties.csv",
    )
    emitted_4 = emit_parliament(
        ge_csv=ge, electoral_csv=electoral, out_root=tmp_path,
        source_id=SOURCE_ID, delim_id="4",
        parties_csv=entities / "parties.csv",
    )

    cand_1999 = _read_csv(emitted_3[1999]["candidacies"])
    cand_2014 = _read_csv(emitted_4[2014]["candidacies"])

    # 1999 binds against 1976 cohort; 2014 binds against 2008 cohort.
    assert {r["entity_id"] for r in cand_1999} == {"IN-PC-1976-bihar-1"}
    assert {r["entity_id"] for r in cand_2014} == {"IN-PC-2008-bihar-2001"}


# --- Sanity: TCPD_DELIM_ID_TO_DELIM_YEAR import works through binder --------


def test_parliament_binder_imports_delim_year_mapping():
    """parliament_results re-uses assembly_results.TCPD_DELIM_ID_TO_DELIM_YEAR.

    The shared mapping (single source of truth for delim_id -> delim_year)
    must be importable through the parliament binder's module namespace so
    the binder's delim_year derivation stays in lockstep with the assembly
    binder's PR-Q7a behaviour.
    """
    from yen_gov.canonical.reingest.assembly_results import (
        TCPD_DELIM_ID_TO_DELIM_YEAR,
    )
    # Sanity: same mapping the parliament binder threads through emit_parliament.
    assert TCPD_DELIM_ID_TO_DELIM_YEAR["3"] == 1976
    assert TCPD_DELIM_ID_TO_DELIM_YEAR["4"] == 2008
    # Verify the binder module imported it for its own use (PR-Q7c).
    assert (
        parliament_results.TCPD_DELIM_ID_TO_DELIM_YEAR is TCPD_DELIM_ID_TO_DELIM_YEAR
    )
