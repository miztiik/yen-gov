"""Unit tests for the admin Inventory endpoint.

Per CLAUDE.md §10, pytest tests MUST NOT walk the real on-disk corpus.
We seed a controlled fixture corpus under ``tmp_path`` and point the
inventory module at it via ``YEN_GOV_REPO_ROOT`` (same pattern as
``schemas.py`` / ``validator.py``). The endpoint resolves the root at
call time, so a module-level ``TestClient`` is fine — the env var
flip per-test is enough.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

# Skip the whole module gracefully if FastAPI/admin extras aren't installed.
fastapi = pytest.importorskip("fastapi")  # noqa: F841
from fastapi.testclient import TestClient

from yen_gov.admin import app


client = TestClient(app)


def _write_observations(path: Path, rows: list[tuple]) -> None:
    """Write an ``observations.parquet`` with the canonical columns."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.execute(
            """
            CREATE TABLE obs (
                observation_id VARCHAR,
                entity_id      VARCHAR,
                year           INTEGER,
                period_label   VARCHAR,
                period_seq     INTEGER,
                indicator_id   VARCHAR,
                value_numeric  DOUBLE,
                value_text     VARCHAR,
                source_id      VARCHAR,
                derivation     VARCHAR
            )
            """
        )
        con.executemany(
            "INSERT INTO obs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.execute(f"COPY obs TO '{path.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()


def _write_dim(path: Path, n_rows: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.execute("CREATE TABLE d (id VARCHAR, name VARCHAR)")
        con.executemany(
            "INSERT INTO d VALUES (?, ?)",
            [(f"id-{i}", f"name-{i}") for i in range(n_rows)],
        )
        con.execute(f"COPY d TO '{path.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()


@pytest.fixture()
def fixture_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Seed a tiny, family-agnostic Parquet corpus and pin the env var.

    Writes a minimal ``datasets/manifest.json`` alongside the parquet files
    so the inventory's manifest-driven classifier resolves the fact-table
    kind authoritatively (PR-O.1 / TODO row 1.8b-i — the legacy
    ``observations.parquet`` filename fallback was retired because per-family
    fact-table stems break it).
    """
    datasets = tmp_path / "datasets"
    obs_path = datasets / "elections" / "election_results.parquet"
    _write_observations(
        obs_path,
        rows=[
            ("o1", "AC-S22-001", 2026, "AcGenMay2026", 1, "ac-winner-party-id", None, "DMK", "src-1", "primary"),
            ("o2", "AC-S22-002", 2026, "AcGenMay2026", 1, "ac-winner-party-id", None, "BJP", "src-1", "primary"),
            ("o3", "AC-S22-001", 2026, "AcGenMay2026", 1, "ac-margin-pct", 12.5, None, "src-1", "derived"),
            ("o4", "AC-S22-002", 2021, "AcGenApr2021", 1, "ac-winner-party-id", None, "AIADMK", "src-2", "primary"),
        ],
    )
    _write_dim(datasets / "elections" / "dim_parties.parquet", n_rows=5)
    _write_dim(datasets / "taxonomy" / "sources.parquet", n_rows=2)
    # Sentinel dirs that MUST be skipped.
    _write_dim(datasets / "_old" / "ignored.parquet", n_rows=99)
    _write_dim(datasets / "_test" / "ignored.parquet", n_rows=99)

    # Minimal manifest so the manifest-driven classifier (admin/inventory.py
    # _classify) recognises the fact-table by table_id + kind. Only fields
    # the classifier reads (family, kind, files[].path) are populated.
    manifest = {
        "$schema": "./schemas/manifest.schema.json",
        "$schema_version": "1.1",
        "manifest_version": "1.0",
        "generated_at": "2026-05-18T00:00:00Z",
        "tables": [
            {
                "table_id": "elections.election_results",
                "family": "elections",
                "table_name": "election_results",
                "kind": "observations",
                "format": "parquet",
                "schema_version": "1.1",
                "partition_columns": [],
                "files": [{"path": "elections/election_results.parquet",
                           "size_bytes": 0, "row_count": 4}],
                "row_count_total": 4,
            },
            {
                "table_id": "elections.dim_parties",
                "family": "elections",
                "table_name": "dim_parties",
                "kind": "dim",
                "format": "parquet",
                "schema_version": "1.0",
                "partition_columns": [],
                "files": [{"path": "elections/dim_parties.parquet",
                           "size_bytes": 0, "row_count": 5}],
                "row_count_total": 5,
            },
            {
                "table_id": "taxonomy.sources",
                "family": "taxonomy",
                "table_name": "sources",
                "kind": "taxonomy",
                "format": "parquet",
                "schema_version": "1.0",
                "partition_columns": [],
                "files": [{"path": "taxonomy/sources.parquet",
                           "size_bytes": 0, "row_count": 2}],
                "row_count_total": 2,
            },
        ],
    }
    (datasets / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    monkeypatch.setenv("YEN_GOV_REPO_ROOT", str(tmp_path))
    return tmp_path


def test_health_ok() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_inventory_shape(fixture_corpus: Path) -> None:
    r = client.get("/api/inventory")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"generated_at", "stores", "indicators"}
    assert isinstance(body["stores"], list)
    assert isinstance(body["indicators"], list)


def test_inventory_classifies_observations_dim_taxonomy(fixture_corpus: Path) -> None:
    body = client.get("/api/inventory").json()
    kinds = {(s["family"], s["kind"]) for s in body["stores"]}
    assert ("elections", "observations") in kinds
    assert ("elections", "dim") in kinds
    assert ("taxonomy", "taxonomy") in kinds


def test_inventory_skips_sentinel_dirs(fixture_corpus: Path) -> None:
    body = client.get("/api/inventory").json()
    paths = [s["path"] for s in body["stores"]]
    assert not any(p.startswith("datasets/_old/") for p in paths)
    assert not any(p.startswith("datasets/_test/") for p in paths)


def test_observations_carries_stats(fixture_corpus: Path) -> None:
    body = client.get("/api/inventory").json()
    obs = next(s for s in body["stores"] if s["kind"] == "observations")
    assert obs["row_count"] == 4
    assert obs["stats"] is not None
    assert obs["stats"]["indicators"] == 2  # ac-winner-party-id + ac-margin-pct
    assert obs["stats"]["entities"] == 2  # AC-S22-001, AC-S22-002
    assert obs["stats"]["periods"] == 2  # AcGenMay2026, AcGenApr2021
    assert obs["stats"]["min_year"] == 2021
    assert obs["stats"]["max_year"] == 2026
    assert obs["stats"]["sources"] == 2  # src-1, src-2


def test_dim_and_taxonomy_have_row_count_no_stats(fixture_corpus: Path) -> None:
    body = client.get("/api/inventory").json()
    dim = next(s for s in body["stores"] if s["kind"] == "dim")
    assert dim["row_count"] == 5
    assert dim["stats"] is None
    tax = next(s for s in body["stores"] if s["kind"] == "taxonomy")
    assert tax["row_count"] == 2
    assert tax["stats"] is None


def test_indicators_rollup_per_indicator_id(fixture_corpus: Path) -> None:
    body = client.get("/api/inventory").json()
    by_id = {(i["family"], i["indicator_id"]): i for i in body["indicators"]}
    winner = by_id[("elections", "ac-winner-party-id")]
    assert winner["obs_count"] == 3
    assert winner["entity_count"] == 2
    assert winner["period_count"] == 2
    assert winner["min_year"] == 2021
    assert winner["max_year"] == 2026
    margin = by_id[("elections", "ac-margin-pct")]
    assert margin["obs_count"] == 1
