"""Integration test for the people-ingest orchestrator.

Uses a tmp_path-rooted fake corpus (CLAUDE.md §10 — never walk the real
on-disk corpus from a pytest test). Asserts:

  - panel rows UPSERT into datasets/elections/dim_candidates.parquet
    (biographic columns sex/age/education/profession/constituency_type
    populated for matched rows; party_type stays NULL)
  - inventory entry is upserted with discrepancy summary
  - discrepancy report is written under .runtime/reports/
  - re-running with the same inputs is a no-op (inventory short-circuit;
    dim_candidates parquet mtime unchanged)
  - --force re-runs but _upsert_dim's sorted-COPY emit keeps the parquet
    bytes AND mtime untouched (idempotent on identical inputs)
  - halt threshold aborts BEFORE the bio UPSERT runs (dim_candidates
    parquet stays at its pre-ingest mtime; no inventory entry written)

PR-S.2 (canonical pivot 1.8f) replaced the per-candidate JSON sidecar
emit with this UPSERT path. The discrepancy QA gate (compare_winner_votes)
is preserved verbatim — it already reads the canonical Parquet.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from textwrap import dedent

import duckdb
import pytest

from yen_gov.pipeline.people_ingest import (
    IngestHalted,
    run_people_ingest,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _seed_canonical_winner(
    *,
    root: Path,
    election_id: str,
    state_code: str,
    delim_year: int,
    eci_no: int,
    winner_votes: int,
    votes_polled: int,
) -> None:
    """Seed datasets/elections/election_results.parquet with the three rows
    compare_winner_votes reads via DuckDB (PR-O.3b-main canonical reroute):
    ac-winner-candidate-id, candidate-votes-polled (winner), ac-votes-polled.
    Uses duckdb directly so the test doesn't need to import the full writer
    + party_lookup machinery."""
    parquet_path = root / "datasets" / "elections" / "election_results.parquet"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    ac_id = f"IN-{state_code}-AC-{delim_year}-{eci_no}"
    winner_id = f"{ac_id}-{election_id}-C01"
    rows = [
        # entity_id, year, period_label, period_seq, indicator_id,
        # value_numeric, value_text, source_id, derivation
        (ac_id, 2021, election_id, 4, "ac-winner-candidate-id",
         None, winner_id, "src-fixture", "argmax"),
        (winner_id, 2021, election_id, 4, "candidate-votes-polled",
         float(winner_votes), None, "src-fixture", "raw"),
        (ac_id, 2021, election_id, 4, "ac-votes-polled",
         float(votes_polled), None, "src-fixture", "sum"),
    ]
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE staging (
                entity_id VARCHAR, year INTEGER, period_label VARCHAR,
                period_seq INTEGER, indicator_id VARCHAR,
                value_numeric DOUBLE, value_text VARCHAR,
                source_id VARCHAR, derivation VARCHAR
            )
            """
        )
        con.executemany(
            "INSERT INTO staging VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows,
        )
        # POSIX path for the COPY (DuckDB on Windows accepts forward slashes).
        con.execute(
            f"COPY staging TO '{parquet_path.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        con.close()


def _seed_canonical_dim_candidates(
    *,
    root: Path,
    election_id: str,
    state_code: str,
    delim_year: int,
    eci_no: int,
) -> None:
    """Seed datasets/elections/dim_candidates.parquet with the two
    candidates the panel CSV ships. The bio UPSERT joins on
    (state, period_label, ac_eci_no, slugify(name)); we pre-seed
    name='WINNER A' / 'RUNNERUP B' so slugify yields the panel's
    candidate_slug values. All v1.2 bio columns are NULL on seed;
    upsert_candidate_bios will populate them post-run."""
    parquet_path = root / "datasets" / "elections" / "dim_candidates.parquet"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    ac_id = f"IN-{state_code}-AC-{delim_year}-{eci_no}"
    rows = [
        # All 15 v1.2 columns in _DIM_SPECS['candidate']['columns'] order.
        (
            f"{ac_id}-{election_id}-C01", ac_id, election_id, 1,
            "WINNER A", "parties.IN.DMK", 1, "src-fixture",
            "DMK", None, None, None, None, None, None,
        ),
        (
            f"{ac_id}-{election_id}-C02", ac_id, election_id, 2,
            "RUNNERUP B", "parties.IN.PMK", 2, "src-fixture",
            "PMK", None, None, None, None, None, None,
        ),
    ]
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE dim (
                candidate_id VARCHAR, ac_id VARCHAR, period_label VARCHAR,
                ballot_serial INTEGER, name VARCHAR, party_id VARCHAR,
                rank INTEGER, source_id VARCHAR, party_short_raw VARCHAR,
                sex VARCHAR, age INTEGER, education VARCHAR, profession VARCHAR,
                constituency_type VARCHAR, party_type VARCHAR
            )
            """
        )
        con.executemany(
            "INSERT INTO dim VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.execute(
            f"COPY (SELECT * FROM dim ORDER BY candidate_id) TO "
            f"'{parquet_path.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        con.close()


def _seed_corpus(tmp_path: Path) -> Path:
    """Copy the schemas, config, and seed canonical fact + dim parquets
    into a tmp_path-rooted fake corpus."""
    root = tmp_path / "repo"
    (root / "datasets" / "schemas").mkdir(parents=True)
    (root / "config").mkdir(parents=True)

    # Schemas the orchestrator touches. (people.entity.schema.json is gone
    # in PR-S.2 — bio rides on dim_candidates v1.2 columns.)
    for name in (
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

    # One canonical election_results.parquet row trio (winner-id +
    # candidate-votes + ac-votes) matching the panel CSV's winner total
    # exactly — no discrepancies, no halt. PR-O.3b-main: the discrepancy
    # gate reads the canonical store, not per-AC JSON shards.
    _seed_canonical_winner(
        root=root, election_id="AcGenApr2021", state_code="S22",
        delim_year=2008, eci_no=1, winner_votes=126000, votes_polled=222069,
    )
    # Pre-seed dim_candidates with the two candidate rows the panel CSV
    # will enrich. PR-S.2: upsert_candidate_bios only enriches existing
    # dim rows (it never creates new ones — top-N + NOTA cutoff is the
    # canonical roster).
    _seed_canonical_dim_candidates(
        root=root, election_id="AcGenApr2021", state_code="S22",
        delim_year=2008, eci_no=1,
    )
    return root


def _read_dim_candidates(root: Path) -> list[dict]:
    """Read all dim_candidates rows as dicts (ordered by candidate_id)."""
    parquet_path = root / "datasets" / "elections" / "dim_candidates.parquet"
    con = duckdb.connect(":memory:")
    try:
        rel = con.execute(
            f"SELECT * FROM read_parquet('{parquet_path.as_posix()}') "
            f"ORDER BY candidate_id"
        )
        cols = [d[0] for d in rel.description]
        return [dict(zip(cols, r)) for r in rel.fetchall()]
    finally:
        con.close()


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


def test_run_people_ingest_upserts_bios_inventory_and_report(tmp_path: Path):
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

    assert result.bios_upserted == 2
    assert result.report.halted is False
    assert result.report.acs_with_mismatch == 0

    # No JSON sidecar tree exists (PR-S.2: datasets/people/ is dead).
    assert not (root / "datasets" / "people").exists()

    # dim_candidates.parquet now carries bio for both rows.
    dim_rows = _read_dim_candidates(root)
    assert len(dim_rows) == 2
    winner = next(r for r in dim_rows if r["candidate_id"].endswith("C01"))
    runnerup = next(r for r in dim_rows if r["candidate_id"].endswith("C02"))
    assert winner["name"] == "WINNER A"
    assert winner["sex"] == "Male"
    assert winner["age"] == 60
    assert winner["education"] == "10th Pass"
    assert winner["profession"] == "Business"
    assert winner["constituency_type"] == "GEN"
    # party_type is not derived from the panel CSV; stays NULL.
    assert winner["party_type"] is None
    assert runnerup["sex"] == "Female"
    assert runnerup["age"] == 50

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
    dim_parquet = root / "datasets" / "elections" / "dim_candidates.parquet"
    mtime_before = dim_parquet.stat().st_mtime_ns

    # Re-run without --force: inventory short-circuit, no work done.
    second = run_people_ingest(
        repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
        state="S22", year=2021, source_input="tn_ae_panel_test",
        source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="r2",
    )
    assert second.bios_upserted == 0
    assert dim_parquet.stat().st_mtime_ns == mtime_before


def test_force_rerun_is_byte_idempotent(tmp_path: Path):
    root = _seed_corpus(tmp_path)
    csv_path = tmp_path / "panel.csv"
    _write_panel_csv(csv_path)

    run_people_ingest(
        repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
        state="S22", year=2021, source_input="tn_ae_panel_test",
        source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="r1",
    )
    dim_parquet = root / "datasets" / "elections" / "dim_candidates.parquet"
    bytes_before = dim_parquet.read_bytes()

    # --force re-runs the adapter. _upsert_dim emits sorted COPY output
    # keyed by candidate_id; identical inputs MUST produce byte-identical
    # parquet (this is the canonical-store equivalent of the legacy
    # write_artifact dict-equal idempotency check).
    run_people_ingest(
        repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
        state="S22", year=2021, source_input="tn_ae_panel_test",
        source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="r2",
        force=True,
    )
    assert dim_parquet.read_bytes() == bytes_before


def test_halt_threshold_aborts_and_writes_no_artifacts(tmp_path: Path):
    root = _seed_corpus(tmp_path)
    csv_path = tmp_path / "panel.csv"
    # 60k vote delta on 222k votes_polled = 27pp; halt threshold is 0.5pp.
    _write_panel_csv(csv_path, winner_votes=66000)

    dim_parquet = root / "datasets" / "elections" / "dim_candidates.parquet"
    mtime_before = dim_parquet.stat().st_mtime_ns
    bytes_before = dim_parquet.read_bytes()

    with pytest.raises(IngestHalted):
        run_people_ingest(
            repo_root=root, csv_path=csv_path, election_id="AcGenApr2021",
            state="S22", year=2021, source_input="tn_ae_panel_test",
            source_url="https://eci.gov.in/statistical-report/tn-2021", run_id="halt",
        )

    # No JSON sidecar tree (PR-S.2: datasets/people/ is dead) and no
    # bio UPSERT happened (parquet unchanged).
    assert not (root / "datasets" / "people").exists()
    assert dim_parquet.stat().st_mtime_ns == mtime_before
    assert dim_parquet.read_bytes() == bytes_before
    # No inventory entry written; the run was rejected upstream of it.
    assert not (root / "datasets" / "elections" / "_inventory.json").exists()
    # The discrepancy report IS written so the operator can inspect.
    assert (root / ".runtime" / "reports" / "ingest-discrepancies-halt.json").is_file()
