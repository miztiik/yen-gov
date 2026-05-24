"""Tier-A tests for ``yen_gov.canonical.energy_sources_seed``.

Per CLAUDE.md §15: operates on ``tmp_path`` (or builds in-memory DuckDB).
Asserts the 7 source_id hashes match the values baked into
``datasets/taxonomy/indicators.json`` at C1 commit (6 rows) + the C4.6
long-arc splice commit (7th, RBI Table 140) + the UPSERT idempotency.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from yen_gov.canonical.energy_sources_seed import (
    ENERGY_SOURCE_ID_BY_NICKNAME,
    ENERGY_SOURCES,
    SOURCE_NICKNAMES,
    upsert_energy_sources,
    upsert_energy_sources_to_parquet,
)


def test_seven_sources_built():
    """Exactly 7 sources: 1 CEA + 3 ICED + 3 RBI (peak-demand + peak-met +
    installed-capacity long-arc added at C4.6)."""
    assert len(ENERGY_SOURCES) == 7
    assert len(SOURCE_NICKNAMES) == 7
    assert set(ENERGY_SOURCE_ID_BY_NICKNAME) == set(SOURCE_NICKNAMES)


def test_source_id_hashes_match_catalogue_fks():
    """The 7 derive_source_id outputs MUST match the values C1 + C4.6 baked
    into indicators.json as the per-child source_id FKs. If a triple
    drifts here, every energy catalogue row's FK goes dangling."""
    expected = {
        "cea_monthly_ic": "src-092a5dc7af3f",
        "iced_capacity_metatable": "src-ba5c6fa6acfe",
        "iced_deep_dive": "src-be6a6d5d6493",
        "iced_gen_metatable": "src-b60ed70f19d8",
        "rbi_hbk_142_peak_demand": "src-99ac1fee8a50",
        "rbi_hbk_142_peak_met": "src-9c02616a7166",
        "rbi_hbk_140_installed_capacity": "src-3d1d55f8a94b",
    }
    for nickname, src_id in expected.items():
        assert ENERGY_SOURCE_ID_BY_NICKNAME[nickname] == src_id, (
            f"source_id drift for {nickname!r}: producer/title/vintage triple "
            f"changed since C1 commit. Either roll back the triple change or "
            f"re-derive and update indicators.json source_id FKs same-commit."
        )


def test_license_tier_authority_invariants():
    """CEA is the gold issuing authority for installed capacity; ICED + RBI
    Handbook are silver republishers per plan-doc §3 Q-d (Hans verdict,
    2026-05-22): RBI republishes CEA peak-demand/peak-met series in its
    longitudinal Handbook ("Originating data: Central Electricity
    Authority, Ministry of Power" verbatim on every affected file), so
    it is NOT the issuing authority for the underlying fact. Promoting
    longitudinal republishers to gold would silently inflate every
    aggregator in the future corpus and the tier loses signal. All
    publish under OGL-IN-1.0.
    """
    by_nick = {nick: row for nick, row in zip(SOURCE_NICKNAMES, ENERGY_SOURCES)}
    cea = by_nick["cea_monthly_ic"]
    assert cea.confidence_tier == "gold"
    assert cea.is_issuing_authority is True
    assert cea.verification_method == "live-fetch"

    for nick in (
        "iced_capacity_metatable",
        "iced_deep_dive",
        "iced_gen_metatable",
    ):
        row = by_nick[nick]
        assert row.confidence_tier == "silver", nick
        assert row.is_issuing_authority is False, nick
        assert row.verification_method == "live-fetch", nick

    # RBI Handbook entries: silver / not-authority / archived-snapshot per
    # plan-doc §3 Q-d (Hans verdict 2026-05-22, REJECTING Max's gold
    # recommendation). Underlying fact published by CEA; RBI is the
    # longitudinal republisher with annual PDF archival cadence.
    # Extended at C4.6 to include the Table 140 installed-capacity
    # long-arc citation (same Hans verdict applies: RBI republishes CEA
    # state-wise installed-capacity history annually in the Handbook).
    for nick in (
        "rbi_hbk_142_peak_demand",
        "rbi_hbk_142_peak_met",
        "rbi_hbk_140_installed_capacity",
    ):
        row = by_nick[nick]
        assert row.confidence_tier == "silver", nick
        assert row.is_issuing_authority is False, nick
        assert row.verification_method == "archived-snapshot", nick

    # All energy upstreams publish under OGL-IN-1.0.
    for row in ENERGY_SOURCES:
        assert row.license == "OGL-IN-1.0", row.source_id


def _create_sources_table(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE sources (
            source_id VARCHAR PRIMARY KEY,
            producer VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            vintage VARCHAR NOT NULL,
            license VARCHAR NOT NULL,
            confidence_tier VARCHAR NOT NULL,
            is_issuing_authority BOOLEAN NOT NULL,
            verification_method VARCHAR NOT NULL,
            url_main VARCHAR,
            citation_full VARCHAR,
            notes VARCHAR
        )
        """
    )


def test_upsert_into_empty_table_writes_seven_rows():
    con = duckdb.connect(":memory:")
    try:
        _create_sources_table(con)
        n = upsert_energy_sources(con)
        assert n == 7
        count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        assert count == 7
    finally:
        con.close()


def test_upsert_is_idempotent():
    """Running twice yields the same 7 rows (not 14)."""
    con = duckdb.connect(":memory:")
    try:
        _create_sources_table(con)
        upsert_energy_sources(con)
        upsert_energy_sources(con)
        count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        assert count == 7
    finally:
        con.close()


def test_upsert_to_parquet_creates_file_when_absent(tmp_path: Path):
    target = tmp_path / "sources.parquet"
    assert not target.exists()
    n = upsert_energy_sources_to_parquet(target)
    assert n == 7
    assert target.is_file()
    con = duckdb.connect()
    try:
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{target.as_posix()}')"
        ).fetchone()[0]
    finally:
        con.close()
    assert count == 7


def test_upsert_to_parquet_preserves_existing_rows(tmp_path: Path):
    """Existing (non-energy) source rows survive the UPSERT."""
    target = tmp_path / "sources.parquet"

    # Pre-seed one unrelated row.
    pre = duckdb.connect(":memory:")
    try:
        _create_sources_table(pre)
        pre.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "src-aaaaaaaaaaaa",
                "Some Publisher",
                "Some Title",
                "",
                "CC-BY-4.0",
                "silver",
                False,
                "transcribed",
                None,
                None,
                None,
            ],
        )
        pre.execute(
            f"COPY (SELECT * FROM sources) TO '{target.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        pre.close()

    n = upsert_energy_sources_to_parquet(target)
    assert n == 7

    con = duckdb.connect()
    try:
        rows = con.execute(
            f"SELECT source_id FROM read_parquet('{target.as_posix()}') ORDER BY source_id"
        ).fetchall()
    finally:
        con.close()

    src_ids = [r[0] for r in rows]
    assert "src-aaaaaaaaaaaa" in src_ids
    assert len(src_ids) == 8  # 1 pre-existing + 7 energy


def test_upsert_to_parquet_is_idempotent(tmp_path: Path):
    """Two consecutive calls yield the same 7-row parquet (byte-identical)."""
    target = tmp_path / "sources.parquet"
    upsert_energy_sources_to_parquet(target)
    bytes_a = target.read_bytes()
    upsert_energy_sources_to_parquet(target)
    bytes_b = target.read_bytes()
    assert bytes_a == bytes_b
