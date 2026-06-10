"""Tests for B2b.5.4 parliament (Parliament) election-results emitter.

No real-corpus walk: each test stages a synthetic TCPD-GE slice + a minimal
electoral (PC) / parties / source catalogue under tmp_path and asserts the
emitted parliament candidacies/summary CSVs against the real columns.json
contract + the parity invariant summary == recompute(candidacies). The
parliament-specific surface (country-wide one-file-per-cycle, mandatory state
column, per-state constituency_no restart, PC binding) is exercised here; the
shared mapping helpers are covered by test_assembly_results.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest import parliament_results
from yen_gov.canonical.reingest.elections import (
    PARLIAMENT_CANDIDACIES_FC,
    PARLIAMENT_SUMMARY_FC,
)

SOURCE_ID = "src-tcpd-ge-test"

_GE_HEADER = [
    "State_Name", "Constituency_No", "Year", "DelimID", "Poll_No", "Position",
    "Candidate", "Sex", "Party", "Votes", "Age", "Deposit_Lost", "Valid_Votes",
    "Electors", "Constituency_Name", "Turnout_Percentage",
    "Vote_Share_Percentage", "Incumbent", "Turncoat", "MyNeta_education",
    "TCPD_Prof_Main_Desc",
]


def _ge_row(**over) -> dict[str, str]:
    base = {
        "State_Name": "Tamil_Nadu", "Constituency_No": "1", "Year": "2019",
        "DelimID": "4", "Poll_No": "0", "Position": "1", "Candidate": "A",
        "Sex": "M", "Party": "DMK", "Votes": "100", "Age": "50",
        "Deposit_Lost": "no", "Valid_Votes": "180", "Electors": "250",
        "Constituency_Name": "Chennai North", "Turnout_Percentage": "72.0",
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


def _stage_catalogue(root: Path, pcs: list[tuple[str, int]]) -> Path:
    """Stage electoral.csv (PC rows for (state_slug, eci_no)) + parties + source."""
    entities = root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    lines = ["entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"]
    for state_slug, n in pcs:
        eid = f"IN-PC-2008-{state_slug}-{2000 + n}"
        lines.append(f"{eid},PC {n},pc,2008,{state_slug},,{n},,GEN")
    (entities / "electoral.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (entities / "parties.csv").write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n",
        encoding="utf-8",
    )
    (entities / "source.csv").write_text(
        "source_id,owner,title,vintage,url\n"
        f"{SOURCE_ID},TCPD,Indian General Elections,2026-06-05,\n",
        encoding="utf-8",
    )
    return entities / "electoral.csv"


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _emit(root: Path, ge_rows, pcs):
    ge = _write_ge(root / "datasets" / "ephemeral" / "All_States_GE.csv", ge_rows)
    electoral = _stage_catalogue(root, pcs)
    return parliament_results.emit_parliament(
        ge_csv=ge, electoral_csv=electoral, out_root=root, source_id=SOURCE_ID
    )


def _contest(state, cno, year=2019):
    return [
        _ge_row(State_Name=state, Constituency_No=cno, Year=year, Position=1,
                Candidate=f"{state}-W", Party="DMK", Votes=100, Vote_Share_Percentage=55.0),
        _ge_row(State_Name=state, Constituency_No=cno, Year=year, Position=2,
                Candidate=f"{state}-R", Party="BJP", Votes=70, Vote_Share_Percentage=38.0),
        _ge_row(State_Name=state, Constituency_No=cno, Year=year, Position=3,
                Candidate="NOTA", Party="NOTA", Votes=5, Vote_Share_Percentage=2.5),
    ]


# --- happy path + path layout -----------------------------------------------


def test_emit_country_wide_single_file_per_cycle(tmp_path):
    rows = _contest("Tamil_Nadu", 1) + _contest("Kerala", 1)
    emitted = _emit(tmp_path, rows, [("tamil-nadu", 1), ("kerala", 1)])
    assert set(emitted) == {2019}
    info = emitted[2019]
    # ONE country-wide file (no state= partition); both states inside it.
    rel = info["candidacies"].relative_to(tmp_path).as_posix()
    assert rel == "datasets/elections/parliament/election=2019/candidacies.csv"
    assert info["states"] == 2
    validate_csv(path=info["candidacies"], file_class=PARLIAMENT_CANDIDACIES_FC, repo_root=tmp_path)
    validate_csv(path=info["summary"], file_class=PARLIAMENT_SUMMARY_FC, repo_root=tmp_path)


def test_state_column_mandatory_and_populated(tmp_path):
    rows = _contest("Tamil_Nadu", 1) + _contest("Kerala", 1)
    emitted = _emit(tmp_path, rows, [("tamil-nadu", 1), ("kerala", 1)])
    cand = _read(emitted[2019]["candidacies"])
    assert all(r["state"] in {"tamil-nadu", "kerala"} for r in cand)
    assert {r["state"] for r in cand} == {"tamil-nadu", "kerala"}


def test_per_state_constituency_no_restart(tmp_path):
    # Both states have a PC numbered 1; they must remain distinct.
    rows = _contest("Tamil_Nadu", 1) + _contest("Kerala", 1)
    emitted = _emit(tmp_path, rows, [("tamil-nadu", 1), ("kerala", 1)])
    # candidacies carry constituency_no + state; (state, constituency_no) is unique.
    cand = _read(emitted[2019]["candidacies"])
    pairs = {(r["state"], r["constituency_no"]) for r in cand}
    assert ("tamil-nadu", "1") in pairs
    assert ("kerala", "1") in pairs
    # summary rows are keyed by entity_id (one per PC) + carry state.
    summ = {r["entity_id"]: r for r in _read(emitted[2019]["summary"])}
    by_state = {r["state"] for r in summ.values()}
    assert by_state == {"tamil-nadu", "kerala"}
    assert len(summ) == 2  # two distinct PCs despite both being constituency_no 1


def test_entity_id_binds_to_pc(tmp_path):
    emitted = _emit(tmp_path, _contest("Tamil_Nadu", 3), [("tamil-nadu", 3)])
    cand = _read(emitted[2019]["candidacies"])
    assert all(r["entity_id"] == "IN-PC-2008-tamil-nadu-2003" for r in cand)


# --- parity oracle ----------------------------------------------------------


def test_summary_is_recompute_of_candidacies(tmp_path):
    rows = _contest("Tamil_Nadu", 1) + _contest("Kerala", 2)
    emitted = _emit(tmp_path, rows, [("tamil-nadu", 1), ("kerala", 2)])
    cand = _read(emitted[2019]["candidacies"])
    summ = {r["entity_id"]: r for r in _read(emitted[2019]["summary"])}
    by = {}
    for r in cand:
        by.setdefault(r["entity_id"], []).append(r)
    for eid, group in by.items():
        ranked = sorted(group, key=lambda r: int(r["votes"]), reverse=True)
        w, ru = ranked[0], ranked[1]
        s = summ[eid]
        assert s["winner_candidate"] == w["candidate_name"]
        assert int(s["winner_votes"]) == int(w["votes"])
        assert int(s["margin_votes"]) == int(w["votes"]) - int(ru["votes"])


def test_nota_excluded(tmp_path):
    emitted = _emit(tmp_path, _contest("Tamil_Nadu", 1), [("tamil-nadu", 1)])
    cand = _read(emitted[2019]["candidacies"])
    assert "NOTA" not in {r["candidate_name"] for r in cand}
    assert len(cand) == 2


# --- bind skip + delim scoping ----------------------------------------------


def test_unbound_pc_skipped(tmp_path):
    # Kerala PC 1 not staged -> skipped, surfaced.
    rows = _contest("Tamil_Nadu", 1) + _contest("Kerala", 1)
    emitted = _emit(tmp_path, rows, [("tamil-nadu", 1)])
    cand = _read(emitted[2019]["candidacies"])
    assert {r["state"] for r in cand} == {"tamil-nadu"}
    assert ("kerala", 1) in emitted[2019]["unbound"]


def test_other_delimitation_excluded(tmp_path):
    rows = _contest("Tamil_Nadu", 1, year=2019) + [
        _ge_row(State_Name="Tamil_Nadu", Constituency_No=1, Year=2004, DelimID=3,
                Position=1, Candidate="Old", Party="DMK", Votes=100),
    ]
    emitted = _emit(tmp_path, rows, [("tamil-nadu", 1)])
    assert set(emitted) == {2019}


def test_distinct_cycles_emit_distinct_directories(tmp_path):
    rows = _contest("Tamil_Nadu", 1, year=2014) + _contest("Tamil_Nadu", 1, year=2019)
    emitted = _emit(tmp_path, rows, [("tamil-nadu", 1)])
    assert set(emitted) == {2014, 2019}
    assert emitted[2014]["candidacies"].parent.name == "election=2014"
