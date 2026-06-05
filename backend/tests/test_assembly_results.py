"""Tests for B2b.5.2 assembly election-results emitter.

No real-corpus walk (CLAUDE.md anti-pattern): every test stages a synthetic
TCPD-shaped ``All_States_AE`` slice + a minimal electoral/parties/source catalogue
under ``tmp_path`` and asserts the emitted candidacies/summary CSVs against the
real ``columns.json`` contract (via ``validate_csv``) + the parity invariant
``summary == recompute(candidacies)``.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest import assembly_results
from yen_gov.canonical.reingest.elections import (
    ASSEMBLY_CANDIDACIES_FC,
    ASSEMBLY_SUMMARY_FC,
)

SOURCE_ID = "src-tcpd-ae-test"

# The subset of TCPD All_States_AE columns the emitter reads.
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


def _stage_catalogue(root: Path, eci_nos: list[int]) -> Path:
    """Stage electoral.csv (TN ACs for eci_nos) + parties.csv + source.csv."""
    entities = root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)

    el_lines = ["entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"]
    for n in eci_nos:
        eid = f"IN-AC-2008-tamil-nadu-{1000 + n}"
        el_lines.append(f"{eid},AC {n},ac,2008,tamil-nadu,,{n},,GEN")
    (entities / "electoral.csv").write_text("\n".join(el_lines) + "\n", encoding="utf-8")

    (entities / "parties.csv").write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n",
        encoding="utf-8",
    )
    (entities / "source.csv").write_text(
        "source_id,owner,title,vintage,url\n"
        f"{SOURCE_ID},TCPD,Indian Assembly Elections,2026-06-05,\n",
        encoding="utf-8",
    )
    return entities / "electoral.csv"


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _emit(root: Path, ae_rows: list[dict[str, str]], eci_nos: list[int]):
    ae = _write_ae(root / "datasets" / "ephemeral" / "All_States_AE.csv", ae_rows)
    electoral = _stage_catalogue(root, eci_nos)
    return assembly_results.emit_state_assembly(
        ae_csv=ae,
        electoral_csv=electoral,
        out_root=root,
        state_name_tcpd="Tamil_Nadu",
        state_slug="tamil-nadu",
        source_id=SOURCE_ID,
    )


def _three_way(cno: int, year: int = 2021) -> list[dict[str, str]]:
    """A clean three-candidate + NOTA contest in one constituency."""
    return [
        _ae_row(Constituency_No=cno, Year=year, Position=1, Candidate="Winner",
                Party="DMK", Votes=100, Vote_Share_Percentage=50.0, Deposit_Lost="no"),
        _ae_row(Constituency_No=cno, Year=year, Position=2, Candidate="Runner",
                Party="ADMK", Votes=80, Vote_Share_Percentage=40.0, Deposit_Lost="no"),
        _ae_row(Constituency_No=cno, Year=year, Position=3, Candidate="Third",
                Party="BJP", Votes=15, Vote_Share_Percentage=7.5, Deposit_Lost="yes"),
        _ae_row(Constituency_No=cno, Year=year, Position=4, Candidate="None of the Above",
                Party="NOTA", Votes=5, Vote_Share_Percentage=2.5, Deposit_Lost="no"),
    ]


# --- happy path + validator -------------------------------------------------


def test_emit_produces_validatable_candidacies_and_summary(tmp_path):
    emitted = _emit(tmp_path, _three_way(1), [1])
    assert set(emitted) == {2021}
    info = emitted[2021]
    validate_csv(path=info["candidacies"], file_class=ASSEMBLY_CANDIDACIES_FC, repo_root=tmp_path)
    validate_csv(path=info["summary"], file_class=ASSEMBLY_SUMMARY_FC, repo_root=tmp_path)
    assert info["candidacies"].relative_to(tmp_path).as_posix() == (
        "datasets/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv"
    )


def test_nota_excluded_from_candidacies(tmp_path):
    emitted = _emit(tmp_path, _three_way(1), [1])
    cand = _read(emitted[2021]["candidacies"])
    names = {r["candidate_name"] for r in cand}
    assert "None of the Above" not in names
    assert len(cand) == 3  # winner + runner + third, NOTA dropped


# --- parity oracle: summary == recompute(candidacies) -----------------------


def test_summary_is_recompute_of_candidacies(tmp_path):
    emitted = _emit(tmp_path, _three_way(1) + _three_way(2), [1, 2])
    cand = _read(emitted[2021]["candidacies"])
    summ = {r["entity_id"]: r for r in _read(emitted[2021]["summary"])}

    by_ac: dict[str, list[dict[str, str]]] = {}
    for r in cand:
        by_ac.setdefault(r["entity_id"], []).append(r)

    for entity_id, rows in by_ac.items():
        ranked = sorted(rows, key=lambda r: int(r["votes"]), reverse=True)
        winner, runner = ranked[0], ranked[1]
        s = summ[entity_id]
        assert s["winner_candidate"] == winner["candidate_name"]
        assert int(s["winner_votes"]) == int(winner["votes"])
        assert s["runnerup_candidate"] == runner["candidate_name"]
        assert int(s["runnerup_votes"]) == int(runner["votes"])
        assert int(s["margin_votes"]) == int(winner["votes"]) - int(runner["votes"])


def test_winner_is_argmax_ex_nota(tmp_path):
    # NOTA with the MOST votes must never become the winner.
    rows = [
        _ae_row(Constituency_No=1, Position=2, Candidate="Real", Party="DMK", Votes=90),
        _ae_row(Constituency_No=1, Position=1, Candidate="NOTA", Party="NOTA", Votes=120),
    ]
    emitted = _emit(tmp_path, rows, [1])
    summ = _read(emitted[2021]["summary"])[0]
    assert summ["winner_candidate"] == "Real"
    assert int(summ["winner_votes"]) == 90


# --- entity bind + skip -----------------------------------------------------


def test_unbound_constituency_is_skipped_and_surfaced(tmp_path):
    # eci_no 2 is NOT staged in electoral.csv -> skipped, surfaced in unbound.
    emitted = _emit(tmp_path, _three_way(1) + _three_way(2), [1])
    cand = _read(emitted[2021]["candidacies"])
    assert {r["constituency_no"] for r in cand} == {"1"}
    assert emitted[2021]["unbound_eci_nos"] == [2]


def test_entity_id_resolves_through_electoral(tmp_path):
    emitted = _emit(tmp_path, _three_way(7), [7])
    cand = _read(emitted[2021]["candidacies"])
    assert all(r["entity_id"] == "IN-AC-2008-tamil-nadu-1007" for r in cand)


# --- enum + field mapping ---------------------------------------------------


def test_result_enum_mapping(tmp_path):
    emitted = _emit(tmp_path, _three_way(1), [1])
    cand = {r["candidate_name"]: r for r in _read(emitted[2021]["candidacies"])}
    assert cand["Winner"]["result"] == "won"
    assert cand["Runner"]["result"] == "lost"
    assert cand["Third"]["result"] == "forfeit"  # Deposit_Lost=yes


def test_sex_and_candidate_type_mapping(tmp_path):
    rows = [
        _ae_row(Constituency_No=1, Position=1, Candidate="W", Sex="FEMALE",
                Incumbent="TRUE", Votes=100),
        _ae_row(Constituency_No=1, Position=2, Candidate="X", Sex="OTHERS",
                Turncoat="TRUE", Votes=50),
        _ae_row(Constituency_No=1, Position=3, Candidate="Y", Sex="",
                Votes=10, Deposit_Lost="yes"),
    ]
    emitted = _emit(tmp_path, rows, [1])
    cand = {r["candidate_name"]: r for r in _read(emitted[2021]["candidacies"])}
    assert cand["W"]["sex"] == "F" and cand["W"]["candidate_type"] == "incumbent"
    assert cand["X"]["sex"] == "O" and cand["X"]["candidate_type"] == "crossover"
    assert cand["Y"]["sex"] == "U" and cand["Y"]["candidate_type"] == "challenger"


def test_party_id_is_null_v1(tmp_path):
    emitted = _emit(tmp_path, _three_way(1), [1])
    cand = _read(emitted[2021]["candidacies"])
    assert all(r["party_id"] == "" for r in cand)


# --- delimitation + year scoping --------------------------------------------


def test_other_delimitation_excluded(tmp_path):
    rows = _three_way(1, year=2021) + [
        _ae_row(Constituency_No=1, Year=2006, DelimID=3, Position=1,
                Candidate="OldWinner", Party="DMK", Votes=100),
    ]
    emitted = _emit(tmp_path, rows, [1])
    assert set(emitted) == {2021}  # the DelimID=3 (2006) row is excluded


def test_distinct_years_emit_distinct_directories(tmp_path):
    rows = _three_way(1, year=2016) + _three_way(1, year=2021)
    emitted = _emit(tmp_path, rows, [1])
    assert set(emitted) == {2016, 2021}
    assert emitted[2016]["candidacies"].parent.name == "election=2016"
    assert emitted[2021]["candidacies"].parent.name == "election=2021"


# --- re-poll handling -------------------------------------------------------


def test_latest_poll_supersedes_earlier(tmp_path):
    rows = [
        _ae_row(Constituency_No=1, Poll_No=0, Position=1, Candidate="Countermanded",
                Party="DMK", Votes=999),
        _ae_row(Constituency_No=1, Poll_No=1, Position=1, Candidate="FinalWinner",
                Party="ADMK", Votes=100),
        _ae_row(Constituency_No=1, Poll_No=1, Position=2, Candidate="FinalRunner",
                Party="DMK", Votes=80),
    ]
    emitted = _emit(tmp_path, rows, [1])
    cand = _read(emitted[2021]["candidacies"])
    names = {r["candidate_name"] for r in cand}
    assert names == {"FinalWinner", "FinalRunner"}  # Poll_No=0 generation dropped


# --- determinism ------------------------------------------------------------


def test_emit_is_deterministic(tmp_path):
    rows = _three_way(2) + _three_way(1)
    e1 = _emit(tmp_path, rows, [1, 2])
    first = e1[2021]["candidacies"].read_text(encoding="utf-8")
    # Re-emit into a fresh root with the same input.
    e2 = _emit(tmp_path / "again", rows, [1, 2])
    second = e2[2021]["candidacies"].read_text(encoding="utf-8")
    assert first == second
