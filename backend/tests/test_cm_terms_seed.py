"""Tier-A tests for ``yen_gov.canonical.cm_terms_seed``.

Per CLAUDE.md §15, ``tmp_path`` fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from yen_gov.canonical.cm_terms_seed import (
    DIM_OFFICES_ROW_SCHEMA_VERSION,
    GOVERNMENTS_OFFICE_HOLDINGS_ROW_SCHEMA_VERSION,
    compile_to_parquet,
)


def _write_entities(tmp_path: Path) -> Path:
    payload = {
        "$schema": "./entity.schema.json",
        "$schema_version": "1.1",
        "entities": [
            {
                "entity_id": "IN-S22",
                "entity_type": "state",
                "entity_level": "state",
                "entity_code": "S22",
                "display_name": "Tamil Nadu",
                "entity_valid_from": 1969,
            },
        ],
    }
    p = tmp_path / "entities.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _write_cm_terms(tmp_path: Path, state: str, terms: list[dict]) -> Path:
    payload = {
        "$schema": "./state_government.schema.json",
        "$schema_version": "1.0",
        "sources": [
            {
                "url": f"https://en.wikipedia.org/wiki/List_of_chief_ministers_of_{state}",
                "fetched_at": "2026-05-20T00:00:00Z",
                "name": f"List of CMs of {state}",
                "authority": "Wikipedia",
            }
        ],
        "state": "S22",
        "terms": terms,
    }
    d = tmp_path / state
    d.mkdir(parents=True, exist_ok=True)
    p = d / "cm_terms.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _rows(parquet: Path) -> list[tuple]:
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_parquet('{parquet.as_posix()}') ORDER BY 1, 2"
        ).fetchall()
    finally:
        con.close()


def test_emits_offices_and_holdings_with_presidents_rule_null(tmp_path):
    entities_json = _write_entities(tmp_path)
    cm_file = _write_cm_terms(
        tmp_path,
        "Tamil_Nadu",
        [
            {
                "start": "2021-05-07",
                "end": None,
                "regime": "elected",
                "party_code": "582",
                "alliance": "DMK+INC",
                "cm_name": "M. K. Stalin",
            },
            {
                "start": "1991-01-30",
                "end": "1991-06-24",
                "regime": "presidents_rule",
                "party_code": None,
                "alliance": None,
                "cm_name": None,
            },
        ],
    )
    sources_parquet = tmp_path / "sources.parquet"
    dim_offices = tmp_path / "dim_offices.parquet"
    holdings = tmp_path / "holdings.parquet"
    office_count, holdings_count = compile_to_parquet(
        [cm_file],
        entities_json,
        sources_parquet,
        dim_offices,
        holdings,
    )
    assert office_count == 1
    assert holdings_count == 2
    # office row
    offices = _rows(dim_offices)
    assert offices[0][0] == "IN-S22-CM"
    assert offices[0][1] == "IN-S22"  # entity_id
    assert offices[0][2] == "CM"  # role
    # holdings rows — sorted by office_id, start_date
    hold = _rows(holdings)
    # presidents_rule comes first (older start_date)
    pr = hold[0]
    assert pr[3] == "presidents_rule"
    assert pr[4] is None  # person_slug
    assert pr[5] is None  # person_name
    # elected row
    elected = hold[1]
    assert elected[3] == "elected"
    assert elected[4] == "m-k-stalin"  # person_slug
    assert elected[5] == "M. K. Stalin"
    # source FK
    assert pr[-1] == elected[-1]  # both cite same wiki source per file
    # sources.parquet upserted with the wiki citation
    sources = _rows(sources_parquet)
    assert len(sources) == 1
    src = sources[0]
    assert src[1] == "Wikipedia"
    assert src[2] == "List of Chief Ministers of Tamil Nadu"
    assert src[5] == "silver"  # confidence_tier
    assert src[6] is False  # is_issuing_authority
    assert src[7] == "transcribed"  # verification_method


def test_upsert_preserves_existing_sources(tmp_path):
    """If sources.parquet already has unrelated rows, they're preserved
    on UPSERT — the seed only adds/replaces its own Wikipedia rows.
    """
    entities_json = _write_entities(tmp_path)
    cm_file = _write_cm_terms(
        tmp_path,
        "Tamil_Nadu",
        [
            {"start": "2021-05-07", "regime": "elected", "cm_name": "M. K. Stalin", "party_code": "582"},
        ],
    )
    # Pre-seed sources.parquet with one unrelated row (mimic ECI report)
    sources_parquet = tmp_path / "sources.parquet"
    con = duckdb.connect()
    try:
        con.execute(
            """
            CREATE TABLE s (
                source_id VARCHAR NOT NULL, producer VARCHAR NOT NULL,
                title VARCHAR NOT NULL, vintage VARCHAR NOT NULL,
                license VARCHAR NOT NULL, confidence_tier VARCHAR NOT NULL,
                is_issuing_authority BOOLEAN NOT NULL,
                verification_method VARCHAR NOT NULL,
                url_main VARCHAR, citation_full VARCHAR, notes VARCHAR
            )
            """
        )
        con.execute(
            """INSERT INTO s VALUES
            ('src-existingone', 'Election Commission of India',
             'ECI Statistical Report S22', 'AcGenMay2021',
             'OGL-IN-1.0', 'gold', TRUE, 'live-fetch',
             'https://example.com', NULL, NULL)"""
        )
        con.execute(
            f"COPY s TO '{sources_parquet.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        con.close()
    compile_to_parquet(
        [cm_file],
        entities_json,
        sources_parquet,
        tmp_path / "dim_offices.parquet",
        tmp_path / "holdings.parquet",
    )
    sources = _rows(sources_parquet)
    assert len(sources) == 2
    sids = {r[0] for r in sources}
    assert "src-existingone" in sids


def test_compile_is_deterministic(tmp_path):
    entities_json = _write_entities(tmp_path)
    cm_file = _write_cm_terms(
        tmp_path,
        "Tamil_Nadu",
        [
            {"start": "2021-05-07", "regime": "elected", "cm_name": "M. K. Stalin", "party_code": "582"},
        ],
    )
    s1 = tmp_path / "s1.parquet"
    s2 = tmp_path / "s2.parquet"
    o1 = tmp_path / "o1.parquet"
    o2 = tmp_path / "o2.parquet"
    h1 = tmp_path / "h1.parquet"
    h2 = tmp_path / "h2.parquet"
    compile_to_parquet([cm_file], entities_json, s1, o1, h1)
    compile_to_parquet([cm_file], entities_json, s2, o2, h2)
    assert o1.read_bytes() == o2.read_bytes()
    assert h1.read_bytes() == h2.read_bytes()
    assert s1.read_bytes() == s2.read_bytes()


def test_schema_version_constants():
    assert DIM_OFFICES_ROW_SCHEMA_VERSION == "1.0"
    assert GOVERNMENTS_OFFICE_HOLDINGS_ROW_SCHEMA_VERSION == "1.0"
