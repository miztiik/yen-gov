"""Tier-A tests for ``yen_gov.canonical.energy_sources_seed``.

Per CLAUDE.md §15: operates on ``tmp_path`` (or builds in-memory DuckDB).
Asserts the 18 source_id hashes (7 P.1.A + 5 P.1.B + 1 P.1.C PR-Q + 1 P.1.C
PR-R + 1 P.1.C PR-S + 1 P.1.C PR-T + 1 P.1.C PR-U + 1 P.1.C PR-V) match the
values baked into ``datasets/taxonomy/indicators.json`` and the UPSERT
idempotency.
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


def test_twelve_sources_built():
    """Exactly 18 sources: 7 P.1.A (1 CEA + 3 ICED + 3 RBI) +
    5 P.1.B (2 ICED distribution + 3 RBI Handbook) + 1 P.1.C PR-Q
    (1 ICED coal-consumption) + 1 P.1.C PR-R (1 ICED rooftop-solar) +
    1 P.1.C PR-S (1 ICED thermal-retired) + 1 P.1.C PR-T (1 ICED
    oil-product-consumption) + 1 P.1.C PR-U (1 ICED primary-energy-supply) +
    1 P.1.C PR-V (1 ICED plant-load-factor).

    Test name preserved for git-blame continuity even though count is now 18;
    the canonical assertion is the count-vs-NICKNAMES match below, not the
    literal 12.
    """
    assert len(ENERGY_SOURCES) == 18
    assert len(SOURCE_NICKNAMES) == 18
    assert set(ENERGY_SOURCE_ID_BY_NICKNAME) == set(SOURCE_NICKNAMES)


def test_source_id_hashes_match_catalogue_fks():
    """The 18 derive_source_id outputs MUST match the values baked into
    indicators.json as the per-child source_id FKs. If a triple drifts
    here, every energy catalogue row's FK goes dangling."""
    expected = {
        # P.1.A (7)
        "cea_monthly_ic": "src-092a5dc7af3f",
        # 3 ICED P.1.A ids rotated under ADR-0042 (vintage "" → "2024-25").
        "iced_capacity_metatable": "src-1240f07df0ac",
        "iced_deep_dive": "src-bb1d7bec8b34",
        "iced_gen_metatable": "src-ddbfadd51428",
        "rbi_hbk_142_peak_demand": "src-99ac1fee8a50",
        "rbi_hbk_142_peak_met": "src-9c02616a7166",
        "rbi_hbk_140_installed_capacity": "src-3d1d55f8a94b",
        # P.1.B (5) — DISCOM finance + demand/supply lift.
        # 2 ICED P.1.B ids rotated under ADR-0042 (vintage "" → "2024-25").
        "iced_distribution_perf": "src-650b1c25d1f7",
        "iced_distribution_rpo": "src-0ea63ed47704",
        "rbi_hbk_141_power_requirement": "src-f7ce9960caba",
        "rbi_hbk_139_power_availability": "src-97a3c47d092f",
        "rbi_hbk_138_per_capita_availability": "src-9a38005d8713",
        # P.1.C PR-Q (1) — ICED coal-consumption endpoint.
        "iced_consumption_coal": "src-c222a8e2cd61",
        # P.1.C PR-R (1) — ICED rooftop-solar capacity endpoint.
        "iced_rooftop_solar": "src-018bb42f9519",
        # P.1.C PR-S (1) — ICED retired-thermal-capacity endpoint.
        "iced_thermal_retired": "src-fd152bd3c6c6",
        # P.1.C PR-T (1) — ICED oil-product-consumption endpoint.
        "iced_consumption_oil": "src-cba8334fedc5",
        # P.1.C PR-U (1) — ICED primary-energy-supply national endpoint.
        "iced_primary_energy_supply": "src-170d3536d908",
        # P.1.C PR-V (1) — ICED plant-load-factor state-wise endpoint.
        "iced_plant_load_factor": "src-7eb929cbf2d8",
    }
    for nickname, src_id in expected.items():
        assert ENERGY_SOURCE_ID_BY_NICKNAME[nickname] == src_id, (
            f"source_id drift for {nickname!r}: producer/title/vintage triple "
            f"changed since seed. Either roll back the triple change or "
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
        # P.1.B ICED endpoints — same silver / not-authority / live-fetch
        # classification as the P.1.A ICED rows. The distribution-perf +
        # RPO-compliance APIs republish state-regulator data, not the
        # issuing authority's primary record.
        "iced_distribution_perf",
        "iced_distribution_rpo",
        # P.1.C PR-Q ICED endpoint — coal-consumption republishes Coal
        # Controller's Office / Ministry of Coal data; same silver /
        # not-authority / live-fetch classification.
        "iced_consumption_coal",
        # P.1.C PR-R ICED endpoint — rooftop-solar republishes MNRE /
        # state nodal agency data; same silver / not-authority /
        # live-fetch classification.
        "iced_rooftop_solar",
        # P.1.C PR-S ICED endpoint — retired-thermal-capacity republishes
        # CEA station-level retirement records; same silver / not-authority /
        # live-fetch classification.
        "iced_thermal_retired",
        # P.1.C PR-T ICED endpoint — oil-product-consumption republishes
        # PPAC / Ministry of Petroleum & Natural Gas state-wise consumption;
        # same silver / not-authority / live-fetch classification.
        "iced_consumption_oil",
        # P.1.C PR-U ICED endpoint — primary-energy-supply (TPES) republishes
        # MoSPI Energy Statistics India (annual edition);
        # same silver / not-authority / live-fetch classification.
        "iced_primary_energy_supply",
        # P.1.C PR-V ICED endpoint — plant-load-factor state-wise republishes
        # CEA station-level daily generation aggregated to PLF; same silver
        # / not-authority / live-fetch classification.
        "iced_plant_load_factor",
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
        # P.1.B RBI Handbook tables — same silver / not-authority /
        # archived-snapshot classification as the P.1.A RBI rows. Tables
        # 138 / 139 / 141 republish CEA originating data ("Originating
        # data: Central Electricity Authority, Ministry of Power"
        # verbatim on every affected file).
        "rbi_hbk_138_per_capita_availability",
        "rbi_hbk_139_power_availability",
        "rbi_hbk_141_power_requirement",
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


def test_upsert_into_empty_table_writes_twelve_rows():
    con = duckdb.connect(":memory:")
    try:
        _create_sources_table(con)
        n = upsert_energy_sources(con)
        assert n == 18
        count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        assert count == 18
    finally:
        con.close()


def test_upsert_is_idempotent():
    """Running twice yields the same 18 rows (not 34)."""
    con = duckdb.connect(":memory:")
    try:
        _create_sources_table(con)
        upsert_energy_sources(con)
        upsert_energy_sources(con)
        count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        assert count == 18
    finally:
        con.close()


def test_upsert_to_parquet_creates_file_when_absent(tmp_path: Path):
    target = tmp_path / "sources.parquet"
    assert not target.exists()
    n = upsert_energy_sources_to_parquet(target)
    assert n == 18
    assert target.is_file()
    con = duckdb.connect()
    try:
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{target.as_posix()}')"
        ).fetchone()[0]
    finally:
        con.close()
    assert count == 18


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
    assert n == 18

    con = duckdb.connect()
    try:
        rows = con.execute(
            f"SELECT source_id FROM read_parquet('{target.as_posix()}') ORDER BY source_id"
        ).fetchall()
    finally:
        con.close()

    src_ids = [r[0] for r in rows]
    assert "src-aaaaaaaaaaaa" in src_ids
    assert len(src_ids) == 19  # 1 pre-existing + 18 energy


def test_upsert_to_parquet_is_idempotent(tmp_path: Path):
    """Two consecutive calls yield the same 18-row parquet (byte-identical)."""
    target = tmp_path / "sources.parquet"
    upsert_energy_sources_to_parquet(target)
    bytes_a = target.read_bytes()
    upsert_energy_sources_to_parquet(target)
    bytes_b = target.read_bytes()
    assert bytes_a == bytes_b
