"""Unit tests for the pure people-panel adapter (no I/O)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from yen_gov.sources.eci.people_panel import (
    ADAPTER_ID,
    is_nota,
    normalise_constituency_type,
    normalise_education,
    normalise_profession,
    normalise_sex,
    parse_panel,
    slugify,
    to_people_payload,
)


def test_slugify_lowercases_and_ascii_folds():
    assert slugify("GOVINDARAJAN T.J") == "govindarajan-t-j"
    assert slugify("José Ñoño") == "jose-nono"
    assert slugify("USHA") == "usha"


def test_slugify_collapses_whitespace_and_punctuation():
    assert slugify("Dr. A. P. J. Abdul Kalam") == "dr-a-p-j-abdul-kalam"


def test_slugify_rejects_empty_or_whitespace_only():
    with pytest.raises(ValueError):
        slugify("")
    with pytest.raises(ValueError):
        slugify("   ")


def test_slugify_rejects_punctuation_only():
    with pytest.raises(ValueError):
        slugify("---")


def test_is_nota_recognises_variants():
    assert is_nota("NOTA")
    assert is_nota("nota")
    assert is_nota("None of the Above")
    assert not is_nota("GOVINDARAJAN T.J")


def test_normalise_sex_collapses_variants():
    assert normalise_sex("M") == "Male"
    assert normalise_sex("MALE") == "Male"
    assert normalise_sex("F") == "Female"
    assert normalise_sex("FEMALE") == "Female"
    assert normalise_sex("O") == "Other"
    assert normalise_sex("") is None
    with pytest.raises(ValueError):
        normalise_sex("X")


def test_normalise_constituency_type():
    assert normalise_constituency_type("GEN") == "GEN"
    assert normalise_constituency_type("SC") == "SC"
    assert normalise_constituency_type("ST") == "ST"
    assert normalise_constituency_type("") is None
    with pytest.raises(ValueError):
        normalise_constituency_type("OBC")


def test_normalise_education_accepts_blank_and_known():
    assert normalise_education("") is None
    assert normalise_education("10th Pass") == "10th Pass"
    assert normalise_education("Doctorate") == "Doctorate"
    with pytest.raises(ValueError):
        normalise_education("Some Mystery Degree")


def test_normalise_profession_preserves_class_distinctions():
    assert normalise_profession("Agriculture") == "Agriculture"
    assert normalise_profession("Agricultural Labour") == "Agricultural Labour"
    assert normalise_profession("") is None
    with pytest.raises(ValueError):
        normalise_profession("Free-form text Hans warned about")


def _write_fixture(tmp_path: Path) -> Path:
    """Minimal panel CSV with two ACs, NOTA, one blank-sex row."""
    csv_text = dedent(
        """\
        State_Name,Assembly_No,Constituency_No,Year,month,DelimID,Poll_No,Position,Candidate,Sex,Party,Votes,Age,Candidate_Type,Valid_Votes,Electors,Constituency_Name,Constituency_Type,District_Name,Sub_Region,N_Cand,Turnout_Percentage,Vote_Share_Percentage,Deposit_Lost,Margin,Margin_Percentage,ENOP,pid,Party_Type_TCPD,Party_ID,last_poll,Contested,Last_Party,Last_Party_ID,Last_Constituency_Name,Same_Constituency,Same_Party,No_Terms,Turncoat,Incumbent,Recontest,MyNeta_education,TCPD_Prof_Main,TCPD_Prof_Main_Desc,TCPD_Prof_Second,TCPD_Prof_Second_Desc,Election_Type
        Tamil_Nadu,16,1,2021,4,,,1,WINNER A,M,DMK,126000,60,,,,Gummidipoondi,GEN,,,,,,,,,,,,,,,,,,,,,,,,10th Pass,Business,,,,State Assembly Election (AE)
        Tamil_Nadu,16,1,2021,4,,,2,RUNNERUP B,F,PMK,75000,50,,,,Gummidipoondi,GEN,,,,,,,,,,,,,,,,,,,,,,,,Graduate,Agriculture,,,,State Assembly Election (AE)
        Tamil_Nadu,16,1,2021,4,,,3,NOTA,,,1700,,,,,Gummidipoondi,GEN,,,,,,,,,,,,,,,,,,,,,,,,,,,,,State Assembly Election (AE)
        Tamil_Nadu,16,2,2021,4,,,1,NOSEX C,,IND,40000,45,,,,Tiruttani,GEN,,,,,,,,,,,,,,,,,,,,,,,,,,,,,State Assembly Election (AE)
        Tamil_Nadu,15,1,2016,5,,,1,OLD CANDIDATE,M,DMK,90000,55,,,,Gummidipoondi,GEN,,,,,,,,,,,,,,,,,,,,,,,,8th Pass,,,,,State Assembly Election (AE)
        """
    )
    path = tmp_path / "panel.csv"
    path.write_text(csv_text, encoding="utf-8")
    return path


def test_parse_panel_filters_by_year_and_state(tmp_path: Path):
    csv_path = _write_fixture(tmp_path)
    rows = parse_panel(csv_path, election_id="AcGenApr2021", state_code="S22", year=2021)
    # 4 source rows for 2021 TN; NOTA dropped -> 3 people rows.
    assert len(rows) == 3
    assert {r.ac_code for r in rows} == {1, 2}
    assert all(r.election_id == "AcGenApr2021" for r in rows)
    assert all(r.state == "S22" for r in rows)


def test_parse_panel_handles_blank_sex_as_null(tmp_path: Path):
    csv_path = _write_fixture(tmp_path)
    rows = parse_panel(csv_path, election_id="AcGenApr2021", state_code="S22", year=2021)
    nosex = next(r for r in rows if r.name == "NOSEX C")
    assert nosex.sex is None


def test_parse_panel_unknown_state_raises(tmp_path: Path):
    csv_path = _write_fixture(tmp_path)
    with pytest.raises(ValueError):
        parse_panel(csv_path, election_id="AcGenApr2021", state_code="S99", year=2021)


def test_to_people_payload_omits_null_biographics_and_attaches_grades(tmp_path: Path):
    csv_path = _write_fixture(tmp_path)
    rows = parse_panel(csv_path, election_id="AcGenApr2021", state_code="S22", year=2021)
    nosex = next(r for r in rows if r.name == "NOSEX C")
    payload = to_people_payload(nosex)
    # Null biographics are omitted entirely (no "Unknown" sentinel).
    assert "sex" not in payload
    assert "education" not in payload
    assert "profession" not in payload
    # Constituency_type=GEN survives.
    assert payload["constituency_type"] == "GEN"
    # field_provenance only carries entries for populated fields.
    assert "sex" not in payload["field_provenance"]
    assert payload["field_provenance"]["constituency_type"] == {
        "grade": "issuing_authority",
        "source_id": ADAPTER_ID,
    }
    assert payload["field_provenance"]["age"]["grade"] == "sworn_declaration"


def test_to_people_payload_includes_identity_fields(tmp_path: Path):
    csv_path = _write_fixture(tmp_path)
    rows = parse_panel(csv_path, election_id="AcGenApr2021", state_code="S22", year=2021)
    winner = next(r for r in rows if r.name == "WINNER A")
    payload = to_people_payload(winner)
    assert payload["election_id"] == "AcGenApr2021"
    assert payload["state"] == "S22"
    assert payload["ac_code"] == 1
    assert payload["candidate_slug"] == "winner-a"
    assert payload["education"] == "10th Pass"
    assert payload["profession"] == "Business"
