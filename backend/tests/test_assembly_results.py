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
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n"
        # PR-0 sentinel; PR-3 writers emit this on lookup miss.
        "parties.IN.UNK,UNK,Unresolved Party,,,,\n",
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


def test_nota_excluded_when_only_candidate_field_marks_it(tmp_path):
    """TCPD vintage >= 2017 shape: Candidate='NOTA', Party='' (empty cell).

    Pre-2017 TCPD: Party='NOTA' (the column the original filter checked).
    2017+: Candidate='NOTA' with blank Party. Both shapes are ballot
    options. The 2017+ shape escaped the original filter and was the
    72-slice writer-bug class identified 2026-06-11 (Karnataka 2019 +
    Madhya Pradesh 2020 + 70 more); regression test for is_nota_row().
    """
    rows = [
        _ae_row(Constituency_No=1, Year=2021, Position=1, Candidate="Real",
                Party="DMK", Votes=100, Vote_Share_Percentage=80.0,
                Deposit_Lost="no"),
        _ae_row(Constituency_No=1, Year=2021, Position=2, Candidate="Other",
                Party="ADMK", Votes=20, Vote_Share_Percentage=16.0,
                Deposit_Lost="no"),
        # The 2017+ NOTA shape: blank Party, Candidate='NOTA'.
        _ae_row(Constituency_No=1, Year=2021, Position=3, Candidate="NOTA",
                Party="", Votes=5, Vote_Share_Percentage=4.0,
                Deposit_Lost="no"),
    ]
    emitted = _emit(tmp_path, rows, [1])
    cand = _read(emitted[2021]["candidacies"])
    names = {r["candidate_name"] for r in cand}
    assert "NOTA" not in names, f"NOTA leaked into candidacies: {names}"
    assert len(cand) == 2  # NOTA dropped, two real candidates retained
    # And every emitted row carries a non-empty party_short_raw (the defensive
    # contract assertion guards this; explicit check here for the contract).
    assert all(r["party_short_raw"] for r in cand)


def test_writer_raises_on_blank_party_short_raw_for_non_nota_row(tmp_path):
    """Defensive contract: an emitted row MUST have non-empty party_short_raw.

    Synthesises a non-NOTA candidate with an empty Party cell (a hypothetical
    publisher contract regression). The writer's structural-fix contract
    (CLAUDE.md section 5: 'structural fixes only, no band-aids') raises on
    emit so the regression is caught at write time, not by a downstream
    consumer with a silent default.
    """
    rows = [
        _ae_row(Constituency_No=1, Year=2021, Position=1, Candidate="Real",
                Party="DMK", Votes=100, Vote_Share_Percentage=80.0,
                Deposit_Lost="no"),
        # Real candidate name but no Party value and not the NOTA token.
        _ae_row(Constituency_No=1, Year=2021, Position=2, Candidate="Mystery",
                Party="", Votes=20, Vote_Share_Percentage=16.0,
                Deposit_Lost="no"),
    ]
    with pytest.raises(ValueError, match="writer regression"):
        _emit(tmp_path, rows, [1])


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


def test_party_id_falls_back_to_unk_when_no_parties_csv(tmp_path):
    """PR-3 v1.2: empty/missing lookup -> parties.IN.UNK (not null).

    The v1 writer left party_id null when ``parties_csv=None``; PR-3 closes
    the empty-party_id bug class by uniformly substituting the
    ``parties.IN.UNK`` sentinel (CLAUDE.md section 10 "no silent demotion";
    publisher label survives on ``party_short_raw``).
    """
    emitted = _emit(tmp_path, _three_way(1), [1])
    cand = _read(emitted[2021]["candidacies"])
    assert all(r["party_id"] == "parties.IN.UNK" for r in cand)


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


# --- uncontested seat (B2b.5.3): single candidate, nan share -----------------


def test_uncontested_seat_emits_null_runnerup_and_margin(tmp_path):
    # TCPD shape for an unopposed return: winner votes=0, share=nan, + a NOTA row.
    rows = [
        _ae_row(Constituency_No=1, Position=1, Candidate="Unopposed", Party="BJP",
                Votes=0, Vote_Share_Percentage="nan", Valid_Votes=0,
                Turnout_Percentage=0),
        _ae_row(Constituency_No=1, Position=2, Candidate="NOTA", Party="NOTA",
                Votes=0, Vote_Share_Percentage="nan"),
    ]
    emitted = _emit(tmp_path, rows, [1])
    validate_csv(path=emitted[2021]["summary"], file_class=ASSEMBLY_SUMMARY_FC, repo_root=tmp_path)
    validate_csv(path=emitted[2021]["candidacies"], file_class=ASSEMBLY_CANDIDACIES_FC, repo_root=tmp_path)
    summ = _read(emitted[2021]["summary"])[0]
    assert summ["winner_candidate"] == "Unopposed"
    assert summ["runnerup_candidate"] == ""      # null -> empty cell
    assert summ["runnerup_votes"] == ""
    assert summ["margin_votes"] == ""
    assert summ["margin_pct"] == ""
    assert summ["winner_share_pct"] == ""        # nan share -> null


def test_nan_vote_share_becomes_null_not_literal_nan(tmp_path):
    rows = [
        _ae_row(Constituency_No=1, Position=1, Candidate="W", Party="DMK",
                Votes=100, Vote_Share_Percentage="nan"),
        _ae_row(Constituency_No=1, Position=2, Candidate="R", Party="ADMK",
                Votes=80, Vote_Share_Percentage=40.0),
    ]
    emitted = _emit(tmp_path, rows, [1])
    cand = {r["candidate_name"]: r for r in _read(emitted[2021]["candidacies"])}
    assert cand["W"]["vote_share_pct"] == ""     # nan -> empty, never the string "nan"
    assert float(cand["R"]["vote_share_pct"]) == 40.0


# --- F1.3a v1.1: party_lookup_from_parties_csv + parties_csv kwarg ---------


def test_party_lookup_from_parties_csv_round_trip(tmp_path):
    """``party_lookup_from_parties_csv`` returns ``{upper(short): party_id}``."""
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.BJP,BJP,Bharatiya Janata Party,,,,\n"
        "parties.IN.INC,INC,Indian National Congress,,,,\n"
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n",
        encoding="utf-8",
    )

    lookup = assembly_results.party_lookup_from_parties_csv(parties)
    # PR-Q1 commit 2 (2026-06-12): load_resolver now indexes ``full``
    # values as a conditional fallback (when not a sentinel placeholder, not
    # a multi-row collision, and not already an explicit alias). All 3 rows
    # in this fixture satisfy the rules, so the upper-cased fulls land in
    # by_alias alongside the shorts.
    assert lookup == {
        "BJP": "parties.IN.BJP",
        "INC": "parties.IN.INC",
        "DMK": "parties.IN.DMK",
        "BHARATIYA JANATA PARTY": "parties.IN.BJP",
        "INDIAN NATIONAL CONGRESS": "parties.IN.INC",
        "DRAVIDA MUNNETRA KAZHAGAM": "parties.IN.DMK",
    }


def test_party_lookup_from_parties_csv_uppercases_key(tmp_path):
    """Lookup keys are upper-cased so case-mismatched TCPD shorts still hit."""
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.AIADMK,aiadmk,All India Anna DMK,,,,\n"
        "parties.IN.MIXED,mIxEd,Mixed-case Party,,,,\n",
        encoding="utf-8",
    )

    lookup = assembly_results.party_lookup_from_parties_csv(parties)
    assert lookup["AIADMK"] == "parties.IN.AIADMK"
    assert lookup["MIXED"] == "parties.IN.MIXED"


def test_party_lookup_skips_rows_missing_short_or_party_id(tmp_path):
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.OK,OK,OK Party,,,,\n"
        ",NOID,No party_id row,,,,\n"
        "parties.IN.NOSHORT,,No short row,,,,\n",
        encoding="utf-8",
    )

    lookup = assembly_results.party_lookup_from_parties_csv(parties)
    # PR-Q1 commit 2 (2026-06-12): the OK row contributes BOTH ``OK`` (short)
    # and ``OK PARTY`` (full-name fallback). The NOID + NOSHORT rows are
    # still skipped (empty pid / empty short), so their fulls (``No party_id
    # row`` / ``No short row``) do NOT enter the index even though they
    # would otherwise pass the three full-fallback skip rules.
    assert lookup == {
        "OK": "parties.IN.OK",
        "OK PARTY": "parties.IN.OK",
    }


def test_party_lookup_missing_file_returns_empty(tmp_path):
    missing = tmp_path / "does-not-exist.csv"
    assert assembly_results.party_lookup_from_parties_csv(missing) == {}


def _emit_with_parties(
    root: Path,
    ae_rows: list[dict[str, str]],
    eci_nos: list[int],
    parties_csv: Path,
):
    ae = _write_ae(root / "datasets" / "ephemeral" / "All_States_AE.csv", ae_rows)
    electoral = _stage_catalogue(root, eci_nos)
    return assembly_results.emit_state_assembly(
        ae_csv=ae,
        electoral_csv=electoral,
        out_root=root,
        state_name_tcpd="Tamil_Nadu",
        state_slug="tamil-nadu",
        source_id=SOURCE_ID,
        parties_csv=parties_csv,
    )


def test_emit_with_parties_csv_populates_party_id(tmp_path):
    """``parties_csv=`` kwarg resolves TCPD ``Party`` shortcode to ``parties.IN.*``."""
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n"
        "parties.IN.ADMK,ADMK,All India Anna DMK,,,,\n"
        "parties.IN.BJP,BJP,Bharatiya Janata Party,,,,\n",
        encoding="utf-8",
    )
    emitted = _emit_with_parties(tmp_path, _three_way(1), [1], parties)
    cand = {r["candidate_name"]: r for r in _read(emitted[2021]["candidacies"])}
    assert cand["Winner"]["party_id"] == "parties.IN.DMK"
    assert cand["Runner"]["party_id"] == "parties.IN.ADMK"
    assert cand["Third"]["party_id"] == "parties.IN.BJP"

    summ = _read(emitted[2021]["summary"])[0]
    assert summ["winner_party_id"] == "parties.IN.DMK"
    assert summ["runnerup_party_id"] == "parties.IN.ADMK"


def test_emit_with_parties_csv_falls_back_to_unk_for_long_tail(tmp_path):
    """PR-3 v1.2: shorts absent from parties.csv become parties.IN.UNK.

    The v1.1 writer left long-tail party_id null on a lookup miss; PR-3
    flips the miss path to the explicit ``parties.IN.UNK`` sentinel so the
    FK closure invariant holds (Holy Law #9 is preserved: no fabrication;
    ``parties.IN.UNK`` is a first-class catalogue row added in PR-0).
    """
    parties = tmp_path / "parties.csv"
    parties.write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n",
        encoding="utf-8",
    )
    emitted = _emit_with_parties(tmp_path, _three_way(1), [1], parties)
    cand = {r["candidate_name"]: r for r in _read(emitted[2021]["candidacies"])}
    assert cand["Winner"]["party_id"] == "parties.IN.DMK"
    assert cand["Runner"]["party_id"] == "parties.IN.UNK"  # ADMK not in parties.csv
    assert cand["Runner"]["party_short_raw"] == "ADMK"     # but raw label survives
    assert cand["Third"]["party_id"] == "parties.IN.UNK"   # BJP not in parties.csv
    assert cand["Third"]["party_short_raw"] == "BJP"

    summ = _read(emitted[2021]["summary"])[0]
    assert summ["winner_party_id"] == "parties.IN.DMK"
    assert summ["runnerup_party_id"] == "parties.IN.UNK"  # runnerup ADMK -> UNK
    assert summ["runnerup_party_short_raw"] == "ADMK"


def test_emit_without_parties_csv_uses_unk_sentinel(tmp_path):
    """PR-3 v1.2: ``parties_csv=None`` -> every party_id is parties.IN.UNK.

    The v1 "back-compat" contract was "party_id stays null" - PR-3 retires
    that contract because empty party_id was the TN-2026 AIADMK bug class.
    The new uniform sentinel keeps the FK closure invariant true regardless
    of whether the caller wired a parties.csv lookup.
    """
    emitted = _emit(tmp_path, _three_way(1), [1])  # _emit() omits parties_csv
    cand = _read(emitted[2021]["candidacies"])
    assert all(r["party_id"] == "parties.IN.UNK" for r in cand)
    summ = _read(emitted[2021]["summary"])[0]
    assert summ["winner_party_id"] == "parties.IN.UNK"
    assert summ["runnerup_party_id"] == "parties.IN.UNK"


def test_party_lookup_threading_into_build_candidacy_rows():
    """``build_candidacy_rows`` accepts ``party_lookup=`` and resolves at row build time."""
    src_rows = [
        {"Constituency_No": "1", "Position": "1", "Candidate": "Winner",
         "Party": "DMK", "Votes": "100", "Vote_Share_Percentage": "55.5",
         "Sex": "MALE", "Age": "50", "Deposit_Lost": "no",
         "Constituency_Name": "AC1", "Incumbent": "FALSE", "Turncoat": "FALSE",
         "MyNeta_education": "", "TCPD_Prof_Main_Desc": ""},
        {"Constituency_No": "1", "Position": "2", "Candidate": "Other",
         "Party": "LONGTAIL_PARTY", "Votes": "80", "Vote_Share_Percentage": "44.5",
         "Sex": "FEMALE", "Age": "45", "Deposit_Lost": "no",
         "Constituency_Name": "AC1", "Incumbent": "FALSE", "Turncoat": "FALSE",
         "MyNeta_education": "", "TCPD_Prof_Main_Desc": ""},
    ]
    eci_to_entity = {1: "IN-AC-2008-tamil-nadu-1001"}
    lookup = {"DMK": "parties.IN.DMK"}  # LONGTAIL_PARTY absent

    rows, unbound = assembly_results.build_candidacy_rows(
        source_rows=src_rows,
        eci_to_entity=eci_to_entity,
        state_slug="tamil-nadu",
        election_year=2021,
        source_id=SOURCE_ID,
        party_lookup=lookup,
    )
    by_name = {r["candidate_name"]: r for r in rows}
    assert by_name["Winner"]["party_id"] == "parties.IN.DMK"
    # PR-3 v1.2: long-tail lookup miss -> parties.IN.UNK sentinel (was None
    # at v1.1; the TN-2026 AIADMK empty-party_id bug class is closed by
    # uniformly substituting the canonical UNK sentinel on miss).
    assert by_name["Other"]["party_id"] == "parties.IN.UNK"
    assert by_name["Other"]["party_short_raw"] == "LONGTAIL_PARTY"  # raw label survives
    assert unbound == set()
