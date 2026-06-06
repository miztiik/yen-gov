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
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.entities_seed import (
    compile_to_parquet as _compile_entities,
)


def _write_entities_parquet(
    tmp_path: Path,
    include_office: bool = True,
    include_national_offices: bool = False,
) -> Path:
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
    if include_national_offices:
        entities.extend(
            [
                {
                    "entity_id": "IN-PRES",
                    "entity_type": "office_bearer",
                    "entity_level": "fiscal_actor",
                    "entity_code": "PRES",
                    "display_name": "President of India",
                    "parent_entity_id": "IN",
                    "entity_valid_from": 1950,
                },
                {
                    "entity_id": "IN-VPRES",
                    "entity_type": "office_bearer",
                    "entity_level": "fiscal_actor",
                    "entity_code": "VPRES",
                    "display_name": "Vice President of India",
                    "parent_entity_id": "IN",
                    "entity_valid_from": 1952,
                },
            ]
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
    citation_groups: dict[str, dict] | None = None,
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
        "$schema_version": "1.1",
        "office_citations": office_citations,
        "holdings": holdings,
    }
    if citation_groups is not None:
        payload["citation_groups"] = citation_groups
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


def _official_president_group() -> dict:
    return {
        "producer": "President's Secretariat",
        "title": "Profile",
        "vintage": "Page Last Updated on: 24/05/2026",
        "license": "unknown-public",
        "confidence_tier": "gold",
        "is_issuing_authority": True,
        "verification_method": "transcribed",
        "url_main": "https://www.presidentofindia.gov.in/profile",
        "citation_full": None,
        "notes": "Official President of India profile fixture.",
    }


def _official_vp_group() -> dict:
    return {
        "producer": "Vice President Office, Government of India",
        "title": "Former Vice Presidents",
        "vintage": "Last Updated: 20 May 2026",
        "license": "unknown-public",
        "confidence_tier": "gold",
        "is_issuing_authority": True,
        "verification_method": "transcribed",
        "url_main": "https://vicepresidentofindia.nic.in/former-vice-presidents/",
        "citation_full": None,
        "notes": "Official former Vice Presidents list fixture.",
    }


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
    dim_offices = tmp_path / "dim_offices.parquet"
    holdings = tmp_path / "holdings.parquet"
    office_count, holdings_count = compile_to_parquet(
        holdings_json,
        entities_parquet,
        dim_offices,
        holdings,
    )
    assert office_count == 1
    assert holdings_count == 2
    # Post-B3-pt2: sources.parquet sibling is NOT emitted.
    assert not (tmp_path / "sources.parquet").exists()
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
    assert pr[4] is None  # selection_method
    assert pr[5] is None  # tenure_status
    assert pr[6] is None  # person_slug
    assert pr[7] is None  # person_name
    # elected row
    elected = hold[1]
    assert elected[3] == "elected"
    assert elected[4] is None  # selection_method remains optional for legacy CM rows
    assert elected[5] is None  # tenure_status remains optional for legacy CM rows
    assert elected[6] == "m-k-stalin"  # person_slug
    assert elected[7] == "M. K. Stalin"
    # source FK: both holdings cite the same wiki source per office.
    assert pr[-1] == elected[-1]
    # The derived source_id matches the Wikipedia CM citation triple.
    expected_wiki_sid = derive_source_id(
        "Wikipedia",
        "List of Chief Ministers of Tamil Nadu",
        "operator-snapshot-2026-05",
    )
    assert elected[-1] == expected_wiki_sid


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
    o1 = tmp_path / "o1.parquet"
    o2 = tmp_path / "o2.parquet"
    h1 = tmp_path / "h1.parquet"
    h2 = tmp_path / "h2.parquet"
    compile_to_parquet(holdings_json, entities_parquet, o1, h1)
    compile_to_parquet(holdings_json, entities_parquet, o2, h2)
    assert o1.read_bytes() == o2.read_bytes()
    assert h1.read_bytes() == h2.read_bytes()


def test_schema_version_constants():
    assert DIM_OFFICES_ROW_SCHEMA_VERSION == "1.0"
    assert GOVERNMENTS_OFFICE_HOLDINGS_ROW_SCHEMA_VERSION == "1.1"


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
            tmp_path / "dim_offices.parquet",
            tmp_path / "holdings.parquet",
        )


def test_holding_without_citation_raises(tmp_path):
    """If holdings[] references an office_id not in office_citations,
    fail loudly. Every office_id in holdings[] must have a citation row
    -- the seed can't compose a source_id without one.
    """
    entities_parquet = _write_entities_parquet(
        tmp_path, include_national_offices=True
    )
    payload = {
        "$schema": "../schemas/office-holdings.schema.json",
        "$schema_version": "1.1",
        "office_citations": {},
        "holdings": [
            {
                "office_id": "IN-PRES",
                "start_date": "2022-07-25",
                "regime": None,
                "person_name": "Smt. Droupadi Murmu",
                "party_eci_code": None,
            },
        ],
    }
    holdings_json = tmp_path / "office_holdings.json"
    holdings_json.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="non-legacy office holdings"):
        compile_to_parquet(
            holdings_json,
            entities_parquet,
            tmp_path / "dim_offices.parquet",
            tmp_path / "holdings.parquet",
        )


def test_non_cm_office_uses_official_citation_group(tmp_path):
    entities_parquet = _write_entities_parquet(
        tmp_path, include_national_offices=True
    )
    group = _official_president_group()
    holdings_json = _write_office_holdings(
        tmp_path,
        office_citations={},
        citation_groups={"president-profile": group},
        holdings=[
            {
                "office_id": "IN-PRES",
                "start_date": "2022-07-25",
                "end_date": None,
                "regime": None,
                "citation_group_id": "president-profile",
                "selection_method": "electoral_college",
                "tenure_status": "substantive",
                "person_name": "Smt. Droupadi Murmu",
                "party_eci_code": None,
                "alliance": None,
            }
        ],
    )
    dim_offices = tmp_path / "dim_offices.parquet"
    holdings = tmp_path / "holdings.parquet"

    office_count, holdings_count = compile_to_parquet(
        holdings_json,
        entities_parquet,
        dim_offices,
        holdings,
    )

    assert office_count == 1
    assert holdings_count == 1
    expected_source_id = derive_source_id(
        group["producer"], group["title"], group["vintage"]
    )
    hold = _rows(holdings)[0]
    assert hold[0] == "IN-PRES"
    assert hold[3] is None  # regime
    assert hold[4] == "electoral_college"
    assert hold[5] == "substantive"
    assert hold[6] == "smt-droupadi-murmu"
    assert hold[-1] == expected_source_id
    # Post-B3-pt2: no sources.parquet sibling. The citation row
    # (President's Secretariat / Profile / ...) lives in source.csv
    # seeded via B2a; here we only assert the derived source_id FK.
    assert not (tmp_path / "sources.parquet").exists()


def test_missing_referenced_citation_group_raises(tmp_path):
    entities_parquet = _write_entities_parquet(
        tmp_path, include_national_offices=True
    )
    holdings_json = _write_office_holdings(
        tmp_path,
        office_citations={},
        citation_groups={},
        holdings=[
            {
                "office_id": "IN-PRES",
                "start_date": "2022-07-25",
                "end_date": None,
                "regime": None,
                "citation_group_id": "missing-official-page",
                "selection_method": "electoral_college",
                "tenure_status": "substantive",
                "person_name": "Smt. Droupadi Murmu",
                "party_eci_code": None,
                "alliance": None,
            }
        ],
    )
    with pytest.raises(ValueError, match="citation_groups has no such key"):
        compile_to_parquet(
            holdings_json,
            entities_parquet,
            tmp_path / "dim_offices.parquet",
            tmp_path / "holdings.parquet",
        )


def test_legacy_office_citations_and_citation_groups_coexist(tmp_path):
    entities_parquet = _write_entities_parquet(
        tmp_path, include_national_offices=True
    )
    pres_group = _official_president_group()
    holdings_json = _write_office_holdings(
        tmp_path,
        citation_groups={"president-profile": pres_group},
        holdings=[
            {
                "office_id": "IN-S22-CM",
                "start_date": "2021-05-07",
                "regime": "elected",
                "person_name": "M. K. Stalin",
                "party_eci_code": "582",
            },
            {
                "office_id": "IN-PRES",
                "start_date": "2022-07-25",
                "end_date": None,
                "regime": None,
                "citation_group_id": "president-profile",
                "selection_method": "electoral_college",
                "tenure_status": "substantive",
                "person_name": "Smt. Droupadi Murmu",
                "party_eci_code": None,
                "alliance": None,
            },
        ],
    )
    holdings = tmp_path / "holdings.parquet"
    compile_to_parquet(
        holdings_json,
        entities_parquet,
        tmp_path / "dim_offices.parquet",
        holdings,
    )
    # Post-B3-pt2: the seed no longer emits sources.parquet, so the
    # legacy/group coexistence assertion shifts from "both producers
    # appear in the sources sibling" to "each holding gets the
    # correct derived source_id FK".
    wiki_sid = derive_source_id(
        "Wikipedia",
        "List of Chief Ministers of Tamil Nadu",
        "operator-snapshot-2026-05",
    )
    pres_sid = derive_source_id(
        pres_group["producer"], pres_group["title"], pres_group["vintage"]
    )
    hold_rows = _rows(holdings)
    by_office = {row[0]: row[-1] for row in hold_rows}
    assert by_office["IN-S22-CM"] == wiki_sid
    assert by_office["IN-PRES"] == pres_sid


def test_official_president_vp_rows_do_not_use_tcpd_or_wikipedia(tmp_path):
    entities_parquet = _write_entities_parquet(
        tmp_path, include_national_offices=True
    )
    pres_group = _official_president_group()
    vp_group = _official_vp_group()
    holdings_json = _write_office_holdings(
        tmp_path,
        office_citations={},
        citation_groups={
            "president-profile": pres_group,
            "vp-former-list": vp_group,
        },
        holdings=[
            {
                "office_id": "IN-PRES",
                "start_date": "2022-07-25",
                "end_date": None,
                "regime": None,
                "citation_group_id": "president-profile",
                "selection_method": "electoral_college",
                "tenure_status": "substantive",
                "person_name": "Smt. Droupadi Murmu",
                "party_eci_code": None,
                "alliance": None,
            },
            {
                "office_id": "IN-VPRES",
                "start_date": "2022-08-11",
                "end_date": "2025-07-21",
                "regime": None,
                "citation_group_id": "vp-former-list",
                "selection_method": "electoral_college",
                "tenure_status": "substantive",
                "person_name": "Shri Jagdeep Dhankhar",
                "party_eci_code": None,
                "alliance": None,
            },
        ],
    )
    holdings_path = tmp_path / "holdings.parquet"
    compile_to_parquet(
        holdings_json,
        entities_parquet,
        tmp_path / "dim_offices.parquet",
        holdings_path,
    )
    # Post-B3-pt2: the source.parquet sibling is gone; we assert FK
    # source_id closure by computing the expected source_ids and
    # checking each holding's FK column points at the matching
    # official citation-group source, not at any Wikipedia / TCPD
    # derived source_id.
    pres_sid = derive_source_id(
        pres_group["producer"], pres_group["title"], pres_group["vintage"]
    )
    vp_sid = derive_source_id(
        vp_group["producer"], vp_group["title"], vp_group["vintage"]
    )
    # Per-state Wikipedia CM citation triple does NOT show up here.
    # IN-S22 is not in the entities fixture, but we can still assert
    # a few canonical Wikipedia/TCPD triples are NOT the source_id.
    forbidden = {
        derive_source_id(
            "Wikipedia",
            "List of Chief Ministers of Tamil Nadu",
            "operator-snapshot-2026-05",
        ),
        derive_source_id(
            "TCPD",
            "office-bearers",
            "operator-snapshot-2026-05",
        ),
    }
    by_office = {row[0]: row[-1] for row in _rows(holdings_path)}
    assert by_office["IN-PRES"] == pres_sid
    assert by_office["IN-VPRES"] == vp_sid
    assert set(by_office.values()).isdisjoint(forbidden)
