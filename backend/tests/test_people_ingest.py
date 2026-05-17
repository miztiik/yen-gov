"""Integration test for the people-ingest orchestrator.

Uses a tmp_path-rooted fake corpus (CLAUDE.md §10 — never walk the real
on-disk corpus from a pytest test). Asserts:

  - people artifacts land at the right paths and validate against schema
  - inventory entry is upserted with discrepancy summary
  - discrepancy report is written under .runtime/reports/
  - re-running with the same inputs is a no-op (inventory short-circuit)
  - --force re-runs but write_artifact's dict-equal gate keeps files
    untouched on disk (mtimes survive)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from textwrap import dedent

import pytest

from yen_gov.pipeline.people_ingest import (
    IngestHalted,
    run_people_ingest,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _seed_corpus(tmp_path: Path) -> Path:
    """Copy the schemas, config, and one ECI result.constituency artifact
    into a tmp_path-rooted fake corpus."""
    root = tmp_path / "repo"
    (root / "datasets" / "schemas").mkdir(parents=True)
    (root / "config").mkdir(parents=True)
    (root / "datasets" / "elections" / "AcGenApr2021" / "S22" / "results").mkdir(
        parents=True
    )

    # Schemas the orchestrator touches.
    for name in (
        "people.entity.schema.json",
        "elections-inventory.schema.json",
        "elections-config.schema.json",
    ):
        shutil.copy(
            REPO_ROOT / "datasets" / "schemas" / name,
            root / "datasets" / "schemas" / name,
        )
    shutil.copy(
        REPO_ROOT / "config" / "elections.json",
        root / "config" / "elections.json",
    )

    # One ECI result.constituency.json with winner votes matching the
    # fixture CSV exactly — no discrepancies, no halt.
    eci_artifact = {
        "$schema": "https://yen-gov.github.io/schemas/result.constituency.schema.json",
        "$schema_version": "3.2",
        "sources": [],
        "election": "AcGenApr2021",
        "state": "S22",
        "body": "AC",
        "eci_no": 1,
        "constituency_name": "Gummidipoondi",
        "totals": {"electors": 281688, "votes_polled": 222069, "turnout_pct": 78.84},
        "candidates": [
            {"rank": 1, "name": "WINNER A", "party_short": "DMK", "votes": 126000, "vote_share_pct": 56.7, "is_winner": True}
        ],
        "nota": {"votes": 1700, "vote_share_pct": 0.8},
        "top_n_cutoff": 5,
        "winner": {
            "name": "WINNER A", "party_short": "DMK", "votes": 126000,
            "margin_votes": 51000, "margin_pct": 22.9,
        },
    }
    (root / "datasets" / "elections" / "AcGenApr2021" / "S22" / "results" / "1.json").write_text(
        json.dumps(eci_artifact, indent=2) + "\n", encoding="utf-8"
    )
    return root


def _write_panel_csv(path: Path, *, winner_votes: int = 126000) -> None:
    """Two AC fixture with WINNER A votes parametrisable for discrepancy tests."""
    csv_text = dedent(
        f"""\
        State_Name,Assembly_No,Constituency_No,Year,month,DelimID,Poll_No,Position,Candidate,Sex,Party,Votes,Age,Candidate_Type,Valid_Votes,Electors,Constituency_Name,Constituency_Type,District_Name,Sub_Region,N_Cand,Turnout_Percentage,Vote_Share_Percentage,Deposit_Lost,Margin,Margin_Percentage,ENOP,pid,Party_Type_TCPD,Party_ID,last_poll,Contested,Last_Party,Last_Party_ID,Last_Constituency_Name,Same_Constituency,Same_Party,No_Terms,Turncoat,Incumbent,Recontest,MyNeta_education,TCPD_Prof_Main,TCPD_Prof_Main_Desc,TCPD_Prof_Second,TCPD_Prof_Second_Desc,Election_Type
        Tamil_Nadu,16,1,2021,4,,,1,WINNER A,M,DMK,{winner_votes},60,,,,Gummidipoondi,GEN,,,,,,,,,,,,,,,,,,,,,,,,10th Pass,Business,,,,State Assembly Election (AE)
        Tamil_Nadu,16,1,2021,4,,,2,RUNNERUP B,F,PMK,75000,50,,,,Gummidipoondi,GEN,,,,,,,,,,,,,,,,,,,,,,,,Graduate,Agriculture,,,,State Assembly Election (AE)
        """
    )
    path.write_text(csv_text, encoding="utf-8")


def test_run_people_ingest_writes_files_inventory_and_report(tmp_path: Path):
    root = _seed_corpus(tmp_path)
    csv_path = tmp_path / "panel.csv"
    _write_panel_csv(csv_path)

    result = run_people_ingest(
        repo_root=root,
        csv_path=csv_path,
        election_id="AcGenApr2021",
        state="S22",
        year=2021,
        source_input="tn_ae_panel_test",
        source_url="https://eci.gov.in/statistical-report/tn-2021",
        run_id="fixture",
    )

    assert result.people_written == 2
    assert result.report.halted is False
    assert result.report.acs_with_mismatch == 0

    winner_path = root / "datasets" / "people" / "AcGenApr2021" / "1" / "winner-a.json"
    assert winner_path.is_file()
    doc = json.loads(winner_path.read_text(encoding="utf-8"))
    assert doc["election_id"] == "AcGenApr2021"
    assert doc["state"] == "S22"
    assert doc["sex"] == "Male"
    assert doc["education"] == "10th Pass"

    inv_path = root / "datasets" / "elections" / "_inventory.json"
    assert inv_path.is_file()
    inv = json.loads(inv_path.read_text(encoding="utf-8"))
    assert len(inv["ingested"]) == 1
    assert inv["ingested"][0]["election_id"] == "AcGenApr2021"
    assert inv["ingested"][0]["discrepancy_summary"]["acs_with_mismatch"] == 0

    report_path = root / ".runtime" / "reports" / "ingest-discrepancies-fixture.json"
    assert report_path.is_file()


def test_inventory_short_circuits_rerun(tmp_path: Path):
    root = _seed_corpus(tmp_path)
    csv_path = tmp_path / "panel.csv"
    _write_panel_csv(csv_path)

    run_people_ingest(
        repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
        state="S22", year=2021, source_input="tn_ae_panel_test",
        source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="r1",
    )
    winner_path = root / "datasets" / "people" / "AcGenApr2021" / "1" / "winner-a.json"
    mtime_before = winner_path.stat().st_mtime_ns

    # Re-run without --force: inventory short-circuit, no work done.
    second = run_people_ingest(
        repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
        state="S22", year=2021, source_input="tn_ae_panel_test",
        source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="r2",
    )
    assert second.people_written == 0
    assert winner_path.stat().st_mtime_ns == mtime_before


def test_force_rerun_is_byte_idempotent(tmp_path: Path):
    root = _seed_corpus(tmp_path)
    csv_path = tmp_path / "panel.csv"
    _write_panel_csv(csv_path)

    run_people_ingest(
        repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
        state="S22", year=2021, source_input="tn_ae_panel_test",
        source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="r1",
    )
    winner_path = root / "datasets" / "people" / "AcGenApr2021" / "1" / "winner-a.json"
    mtime_before = winner_path.stat().st_mtime_ns
    bytes_before = winner_path.read_bytes()

    # --force re-runs the adapter, but write_artifact's dict-equal gate
    # must keep file bytes AND mtime untouched (operational fetched_at
    # stripped before compare).
    run_people_ingest(
        repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
        state="S22", year=2021, source_input="tn_ae_panel_test",
        source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="r2",
        force=True,
    )
    assert winner_path.stat().st_mtime_ns == mtime_before
    assert winner_path.read_bytes() == bytes_before


def test_halt_threshold_aborts_and_writes_no_artifacts(tmp_path: Path):
    root = _seed_corpus(tmp_path)
    csv_path = tmp_path / "panel.csv"
    # 60k vote delta on 222k votes_polled = 27pp; halt threshold is 0.5pp.
    _write_panel_csv(csv_path, winner_votes=66000)

    with pytest.raises(IngestHalted):
        run_people_ingest(
            repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
            state="S22", year=2021, source_input="tn_ae_panel_test",
            source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="halt",
        )

    # No people written, no inventory entry.
    assert not (root / "datasets" / "people").exists() or not any(
        (root / "datasets" / "people").rglob("*.json")
    )
    assert not (root / "datasets" / "elections" / "_inventory.json").exists()
    # The discrepancy report IS written so the operator can inspect.
    assert (root / ".runtime" / "reports" / "ingest-discrepancies-halt.json").is_file()
