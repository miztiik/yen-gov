"""Tier-A tests for ``yen_gov.canonical.office_holdings_seed``.

Per CLAUDE.md §15, ``tmp_path`` fixtures only.

G.1.c shape (2026-05-22): the compile function takes ONE consolidated
``office_holdings_json`` (was: list of 31 cm_terms.json files). Office
IDENTITY still comes from ``entity_type='office_bearer'`` rows in
entities.parquet (G.1.b reader-switch, unchanged). Fixtures below
compile a small entities.json to parquet via
``yen_gov.canonical.entities_seed.compile_to_parquet`` so the test
inputs mirror the real production data flow.

Forked from the retired test_cm_terms_seed.py; behavioural invariants
identical except for the input-file shape switch (1 file vs 31).
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.office_holdings_seed import (
    DIM_OFFICES_ROW_SCHEMA_VERSION,
    GOVERNMENTS_OFFICE_HOLDINGS_ROW_SCHEMA_VERSION,
    compile_to_parquet,
)
from yen_gov.canonical.entities_seed import (
    compile_to_parquet as _compile_entities,
)


def _write_entities_parquet(tmp_path: Path, include_office: bool = True) -> Path:
    """Write a minimal entities.json containing IN-S22 (+ IN-S22-CM if
    requested) and compile to entities.parquet. Returns the parquet path.
    """
    entities = [
        {
            "entity_id": "IN-S22",
            "entity_type": "state",
            "entity_level": "state",
            "entity_code": "S22",
            "display_name": "Tamil Nadu",
            "entity_valid_from": 1969,
        },
    ]
    if include_office:
        entities.append(
            {
                "entity_id": "IN-S22-CM",
                "entity_type": "office_bearer",
                "entity_level": "fiscal_actor",
                "entity_code": "CM",
                "display_name": "Chief Minister of Tamil Nadu",
                "parent_entity_id": "IN-S22",
                "entity_valid_from": 1969,
            }
        )
    payload = {
        "$schema": "./entity.schema.json",
        "$schema_version": "1.2",
        "entities": entities,
    }
    json_path = tmp_path / "entities.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    parquet_path = tmp_path / "entities.parquet"
    _compile_entities(json_path, parquet_path)
    return parquet_path


def _write_office_holdings(
    tmp_path: Path,
    holdings: list[dict],
    office_citations: dict[str, dict] | None = None,
) -> Path:
    """Write a minimal office_holdings.json fixture and return its path.

    Defaults to a single IN-S22-CM citation if office_citations is None.
    """
    if office_citations is None:
        office_citations = {
            "IN-S22-CM": {
                "url_main": "https://en.wikipedia.org/wiki/List_of_chief_ministers_of_Tamil_Nadu"
            }
        }
    payload = {
        "$schema": "../schemas/office-holdings.schema.json",
        "$schema_version": "1.0",
        "office_citations": office_citations,
        "holdings": holdings,
    }
    p = tmp_path / "office_holdings.json"
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
    """elected + presidents_rule rows; PR carries person_slug/name NULL."""
    entities_parquet = _write_entities_parquet(tmp_path)
    holdings_json = _write_office_holdings(
        tmp_path,
        holdings=[
            {
                "office_id": "IN-S22-CM",
                "start_date": "2021-05-07",
                "end_date": None,
                "regime": "elected",
                "party_eci_code": "582",
                "alliance": "DMK+INC",
                "person_name": "M. K. Stalin",
            },
            {
                "office_id": "IN-S22-CM",
                "start_date": "1991-01-30",
                "end_date": "1991-06-24",
                "regime": "presidents_rule",
                "party_eci_code": None,
                "alliance": None,
                "person_name": None,
            },
        ],
    )
    sources_parquet = tmp_path / "sources.parquet"
    dim_offices = tmp_path / "dim_offices.parquet"
    holdings = tmp_path / "holdings.parquet"
    office_count, holdings_count = compile_to_parquet(
        holdings_json,
        entities_parquet,
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
    # holdings rows -- sorted by office_id, start_date
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
    assert pr[-1] == elected[-1]  # both cite same wiki source per office
    # sources.parquet upserted with the wiki citation
    sources = _rows(sources_parquet)
    assert len(sources) == 1
    src = sources[0]
    assert src[1] == "Wikipedia"
    assert src[2] == "List of Chief Ministers of Tamil Nadu"
    assert src[5] == "silver"  # confidence_tier
    assert src[6] is False  # is_issuing_authority
    assert src[7] == "transcribed"  # verification_method
    assert src[8] == "https://en.wikipedia.org/wiki/List_of_chief_ministers_of_Tamil_Nadu"


def test_upsert_preserves_existing_sources(tmp_path):
    """If sources.parquet already has unrelated rows, they're preserved
    on UPSERT -- the seed only adds/replaces its own Wikipedia rows.
    """
    entities_parquet = _write_entities_parquet(tmp_path)
    holdings_json = _write_office_holdings(
        tmp_path,
        holdings=[
            {
                "office_id": "IN-S22-CM",
                "start_date": "2021-05-07",
                "regime": "elected",
                "person_name": "M. K. Stalin",
                "party_eci_code": "582",
            },
        ],
    )
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
        holdings_json,
        entities_parquet,
        sources_parquet,
        tmp_path / "dim_offices.parquet",
        tmp_path / "holdings.parquet",
    )
    sources = _rows(sources_parquet)
    assert len(sources) == 2
    sids = {r[0] for r in sources}
    assert "src-existingone" in sids


def test_compile_is_deterministic(tmp_path):
    """Two runs over the same inputs produce byte-identical parquet."""
    entities_parquet = _write_entities_parquet(tmp_path)
    holdings_json = _write_office_holdings(
        tmp_path,
        holdings=[
            {
                "office_id": "IN-S22-CM",
                "start_date": "2021-05-07",
                "regime": "elected",
                "person_name": "M. K. Stalin",
                "party_eci_code": "582",
            },
        ],
    )
    s1 = tmp_path / "s1.parquet"
    s2 = tmp_path / "s2.parquet"
    o1 = tmp_path / "o1.parquet"
    o2 = tmp_path / "o2.parquet"
    h1 = tmp_path / "h1.parquet"
    h2 = tmp_path / "h2.parquet"
    compile_to_parquet(holdings_json, entities_parquet, s1, o1, h1)
    compile_to_parquet(holdings_json, entities_parquet, s2, o2, h2)
    assert o1.read_bytes() == o2.read_bytes()
    assert h1.read_bytes() == h2.read_bytes()
    assert s1.read_bytes() == s2.read_bytes()


def test_schema_version_constants():
    assert DIM_OFFICES_ROW_SCHEMA_VERSION == "1.0"
    assert GOVERNMENTS_OFFICE_HOLDINGS_ROW_SCHEMA_VERSION == "1.0"


def test_missing_office_bearer_raises(tmp_path):
    """If office_citations names an office_id with no office_bearer in
    entities.parquet, the seed must fail loudly. G.1.b reader-switch
    contract: office identity MUST exist canonically before citations
    reference it.
    """
    entities_parquet = _write_entities_parquet(tmp_path, include_office=False)
    holdings_json = _write_office_holdings(
        tmp_path,
        holdings=[
            {
                "office_id": "IN-S22-CM",
                "start_date": "2021-05-07",
                "regime": "elected",
                "person_name": "M. K. Stalin",
                "party_eci_code": "582",
            },
        ],
    )
    with pytest.raises(ValueError, match="entities.parquet has no office_bearer"):
        compile_to_parquet(
            holdings_json,
            entities_parquet,
            tmp_path / "sources.parquet",
            tmp_path / "dim_offices.parquet",
            tmp_path / "holdings.parquet",
        )


def test_holding_without_citation_raises(tmp_path):
    """If holdings[] references an office_id not in office_citations,
    fail loudly. Every office_id in holdings[] must have a citation row
    -- the seed can't compose a source_id without one.
    """
    entities_parquet = _write_entities_parquet(tmp_path)
    # Citation only for a different office_id than the one we hold under
    payload = {
        "$schema": "../schemas/office-holdings.schema.json",
        "$schema_version": "1.0",
        "office_citations": {
            "IN-S22-CM": {
                "url_main": "https://en.wikipedia.org/wiki/List_of_chief_ministers_of_Tamil_Nadu"
            },
        },
        "holdings": [
            {
                "office_id": "IN-S99-CM",  # not in office_citations
                "start_date": "2021-05-07",
                "regime": "elected",
                "person_name": "Someone",
                "party_eci_code": "1",
            },
        ],
    }
    holdings_json = tmp_path / "office_holdings.json"
    holdings_json.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="no entry in office_citations"):
        compile_to_parquet(
            holdings_json,
            entities_parquet,
            tmp_path / "sources.parquet",
            tmp_path / "dim_offices.parquet",
            tmp_path / "holdings.parquet",
        )
