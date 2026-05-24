from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from yen_gov.canonical.adapters.eci_ae_panel import build_envelope, parse_panel_csv


def _write_parties(root: Path) -> None:
    taxonomy = root / "taxonomy"
    taxonomy.mkdir(parents=True)
    payload = {
        "$schema": "../schemas/taxonomy-parties.schema.json",
        "$schema_version": "2.1",
        "sources": [],
        "parties": [
            {
                "party_id": "parties.IN.IND",
                "short_name": "IND",
                "full_name": "Independent",
                "aliases": ["Independent"],
                "eci_codes": [],
                "state_scope": ["IN"],
            },
            {
                "party_id": "parties.IN.NOTA",
                "short_name": "NOTA",
                "full_name": "None of the Above",
                "aliases": [],
                "eci_codes": [],
                "state_scope": ["IN"],
            },
            {
                "party_id": "parties.IN.DMK",
                "short_name": "DMK",
                "full_name": "Dravida Munnetra Kazhagam",
                "aliases": [],
                "eci_codes": [],
                "state_scope": ["S22"],
            },
            {
                "party_id": "parties.IN.INC",
                "short_name": "INC",
                "full_name": "Indian National Congress",
                "aliases": [],
                "eci_codes": [],
                "state_scope": ["IN"],
            },
        ],
    }
    (taxonomy / "parties.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path) -> None:
    path.write_text(
        dedent(
            """\
            State_Name,Year,month,DelimID,Constituency_No,Constituency_Name,Candidate,Party,Votes,Electors,Valid_Votes,Turnout_Percentage,Sex,Age,Constituency_Type,MyNeta_education,ECI_Prof_Main,Party_Type_ECI
            Tamil_Nadu,1971,3,2,1,ONE,A Alpha,DMK,600,1000,1000,80,M,45,GEN,Graduate,Agriculture,State Party
            Tamil_Nadu,1971,3,2,1,ONE,B Bravo,INC,400,1000,1000,80,F,39,GEN,12th Pass,Business,National Party
            Tamil_Nadu,1971,,2,1,ONE,By Poll,DMK,10,1000,1000,80,M,45,GEN,Graduate,Agriculture,State Party
            Tamil_Nadu,2021,5,4,1,ONE,A Alpha,DMK,600,1000,1010,81,M,45,GEN,Graduate,Agriculture,State Party
            Tamil_Nadu,2021,5,4,1,ONE,B Bravo,INC,400,1000,1010,81,F,39,GEN,12th Pass,Business,National Party
            Tamil_Nadu,2021,5,4,1,ONE,None Of The Above,NOTA,10,1000,1010,81,,,,,,
            """
        ),
        encoding="utf-8",
    )


def test_parse_panel_filters_general_election_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    rows = parse_panel_csv(csv_path, state_code="S22")

    assert len(rows) == 5
    assert {row.year for row in rows} == {1971, 2021}
    assert any(row.is_nota for row in rows)
    assert all(row.name != "By Poll" for row in rows)


def test_build_envelope_emits_nota_only_after_2013(tmp_path: Path) -> None:
    _write_parties(tmp_path)
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    envelope, events, report = build_envelope(
        datasets_root=tmp_path,
        csv_path=csv_path,
        state_code="S22",
    )

    assert events == ("AcGenApr2021", "AcGenMar1971")
    indicators_by_period = {}
    for row in envelope.observation_rows:
        indicators_by_period.setdefault(row.period_label, set()).add(row.indicator_id)
    assert "ac-nota-votes" not in indicators_by_period["AcGenMar1971"]
    assert "ac-nota-votes" in indicators_by_period["AcGenApr2021"]
    assert len(envelope.person_dim_rows) == 4
    assert len(envelope.candidacy_rows) == 4
    assert len(envelope.source_rows) == 2
    assert report["events"][0]["halted"] is False
