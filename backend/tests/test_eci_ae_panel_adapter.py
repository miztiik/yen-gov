from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from yen_gov.canonical.adapters.eci_ae_panel import (
    PanelFilters,
    build_envelope,
    event_id_for,
    inspect_panel,
    parse_panel_csv,
)


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
                "party_id": "parties.IN.UNK",
                "short_name": "UNK",
                "full_name": "Unknown party",
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
            State_Name,Assembly_No,Constituency_No,Year,month,DelimID,Poll_No,Position,Candidate,Sex,Party,Votes,Age,Candidate_Type,Valid_Votes,Electors,Constituency_Name,Constituency_Type,District_Name,Sub_Region,N_Cand,Turnout_Percentage,Vote_Share_Percentage,Deposit_Lost,Margin,Margin_Percentage,ENOP,pid,Party_Type_TCPD,Party_ID,last_poll,Contested,Last_Party,Last_Party_ID,Last_Constituency_Name,Same_Constituency,Same_Party,No_Terms,Turncoat,Incumbent,Recontest,MyNeta_education,TCPD_Prof_Main,TCPD_Prof_Main_Desc,TCPD_Prof_Second,TCPD_Prof_Second_Desc,Election_Type
            Tamil_Nadu,5,1,1971,3,2,0,1,A Alpha,M,DMK,600,45,,1000,1000,ONE,GEN,,,,80,,,,,,,State Party,,TRUE,,,,,,,,,,Graduate,Agriculture,,,,State Assembly Election (AE)
            Tamil_Nadu,5,1,1971,3,2,0,2,B Bravo,F,INC,400,39,,1000,1000,ONE,GEN,,,,80,,,,,,,National Party,,TRUE,,,,,,,,,,12th Pass,Business,,,,State Assembly Election (AE)
            Tamil_Nadu,5,1,1971,,2,1,1,By Poll,M,DMK,10,45,,1000,1000,ONE,GEN,,,,80,,,,,,,State Party,,TRUE,,,,,,,,,,Graduate,Agriculture,,,,State Assembly Election (AE)
            Tamil_Nadu,15,1,2021,5,4,0,1,A Alpha,M,DMK,600,45,,1010,1000,ONE,GEN,,,,81,,,,,,,State Party,,TRUE,,,,,,,,,,Graduate,Agriculture,,,,State Assembly Election (AE)
            Tamil_Nadu,15,1,2021,5,4,0,2,B Bravo,F,INC,400,39,,1010,1000,ONE,GEN,,,,81,,,,,,,National Party,,TRUE,,,,,,,,,,12th Pass,Business,,,,State Assembly Election (AE)
            Tamil_Nadu,15,1,2021,5,4,0,3,None Of The Above,,NOTA,10,,,,1010,1000,ONE,GEN,,,,81,,,,,,,NOTA,,TRUE,,,,,,,,,,,,,,State Assembly Election (AE)
            Tamil_Nadu,15,2,2021,5,4,0,1,C Charlie,M,FRINGE,90,41,,100,200,TWO,GEN,,,,50,,,,,,,Local Party,,TRUE,,,,,,,,,,Graduate,Other,,,,State Assembly Election (AE)
            Tamil_Nadu,15,2,2021,5,4,0,2,D Delta,F,INC,110,40,,100,200,TWO,GEN,,,,50,,,,,,,National Party,,TRUE,,,,,,,,,,Graduate,Other,,,,State Assembly Election (AE)
            """
        ),
        encoding="utf-8",
    )


def test_parse_panel_filters_general_election_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    rows = parse_panel_csv(csv_path, state_code="S22")

    assert len(rows) == 7
    assert {row.year for row in rows} == {1971, 2021}
    assert any(row.is_nota for row in rows)
    assert all(row.name != "By Poll" for row in rows)


def test_parse_panel_supports_delim_id_filters(tmp_path: Path) -> None:
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    rows = parse_panel_csv(
        csv_path,
        state_code="S22",
        filters=PanelFilters(delim_ids=frozenset({"4"})),
    )

    assert len(rows) == 5
    assert {row.year for row in rows} == {2021}
    assert {row.delim_year for row in rows} == {2008}


def test_build_envelope_emits_nota_only_after_2013(tmp_path: Path) -> None:
    _write_parties(tmp_path)
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    envelope, events, report = build_envelope(
        datasets_root=tmp_path,
        csv_path=csv_path,
        state_code="S22",
        allow_unknown_parties=True,
    )

    assert events == ("AcGenApr2021", "AcGenMar1971")
    indicators_by_period = {}
    for row in envelope.observation_rows:
        indicators_by_period.setdefault(row.period_label, set()).add(row.indicator_id)
    assert "ac-nota-votes" not in indicators_by_period["AcGenMar1971"]
    assert "ac-nota-votes" in indicators_by_period["AcGenApr2021"]
    assert len(envelope.person_dim_rows) == 6
    assert len(envelope.candidacy_rows) == 6
    assert len(envelope.source_rows) == 2
    assert report["unresolved_parties"] == {"FRINGE": 1}
    assert any(row.party_id == "parties.IN.UNK" and row.party_short_raw == "FRINGE" for row in envelope.candidacy_rows)
    assert report["events"][0]["halted"] is False


def test_inspect_panel_reports_events_and_unresolved_parties(tmp_path: Path) -> None:
    _write_parties(tmp_path)
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    report = inspect_panel(
        datasets_root=tmp_path,
        csv_path=csv_path,
        state_code="S22",
        filters=PanelFilters(delim_ids=frozenset({"3", "4"})),
    )

    assert report["rows_included"] == 5
    assert report["rows_by_delim_id"] == {"4": 5}
    assert report["missing_events"] == []
    assert report["unresolved_party_rows"] == 1
    assert report["unresolved_parties"] == [{"party": "FRINGE", "rows": 1}]


def test_event_lookup_uses_month_for_duplicate_state_year() -> None:
    assert event_id_for("S04", 2005, 2) == "AcGenFeb2005"
    assert event_id_for("S04", 2005, 11) == "AcGenNov2005"
