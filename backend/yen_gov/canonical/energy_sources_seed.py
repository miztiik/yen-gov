"""Seed the 6 energy citation rows into ``taxonomy/sources.parquet``.

P.1.A consumes 6 distinct upstreams (1 CEA + 3 ICED endpoints + 2 RBI
Handbook tables). Each gets a citation row in the sources ledger so
every emitted observation in P.1.A can FK to a real ``source_id`` per
Holy Law #9 + ADR-0032.

Pattern mirrors ``boundary_layers_seed.upsert_boundary_sources`` (T.0d):
INSERT-OR-REPLACE keyed on ``source_id`` so multiple subsystems can
upsert their rows into the same in-memory ``sources`` table before the
final COPY to parquet.

``derive_source_id(producer, title, vintage)`` is the only way to compute
``source_id`` -- NEVER hand-author (CLAUDE.md §10 + ADR-0032). The 6
expected hashes are baked into ``datasets/taxonomy/indicators.json`` at
C1 commit; if a triple is edited here, those FKs go dangling and the
catalogue compile fails closed.

P.1.A C3 seed (2026-05-22).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.envelope import SourceRow

__all__ = [
    "ENERGY_SOURCE_ID_BY_NICKNAME",
    "ENERGY_SOURCES",
    "SOURCE_NICKNAMES",
    "upsert_energy_sources",
    "upsert_energy_sources_to_parquet",
]


# Operator nicknames for the 6 energy P.1.A sources. Adapters look up
# the materialised source_id by nickname rather than rebuilding the
# triple-hash each time.
SOURCE_NICKNAMES: tuple[str, ...] = (
    "cea_monthly_ic",
    "iced_capacity_metatable",
    "iced_deep_dive",
    "iced_gen_metatable",
    "rbi_hbk_142_peak_demand",
    "rbi_hbk_142_peak_met",
)


# (producer, title, vintage) triples. Vintage="" is permitted per
# source.schema.json when the publisher publishes no vintage (ICED APIs
# are continuously-updated; the RBI Handbook table-142 explicitly carries
# the 2024-25 edition tag; CEA Monthly is the March-2026 snapshot).
_TRIPLES: dict[str, tuple[str, str, str]] = {
    "cea_monthly_ic": (
        "Central Electricity Authority",
        "Monthly Executive Summary \u2014 Installed Capacity (IC) sheet",
        "2026-03",
    ),
    "iced_capacity_metatable": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Capacity Metatable API (state-wise installed capacity, by fuel)",
        "",
    ),
    "iced_deep_dive": (
        "NITI Aayog India Climate & Energy Dashboard",
        "State-wise Deep Dive API",
        "",
    ),
    "iced_gen_metatable": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Generation Metatable API (state-wise electricity generation, by fuel)",
        "",
    ),
    "rbi_hbk_142_peak_demand": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 142: State-wise Actual Power Supply Position \u2014 Peak Demand",
        "2024-25",
    ),
    "rbi_hbk_142_peak_met": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 142: State-wise Actual Power Supply Position \u2014 Peak Met",
        "2024-25",
    ),
}


# Per-source license / confidence_tier / verification_method / authority /
# url_main / notes. CEA + RBI are issuing authorities (gold tier); ICED
# is the federal aggregator over CEA-published station-level data
# (silver tier -- republisher). All energy upstreams publish under
# OGL-IN-1.0 (Open Government Licence India).
_BY_NICKNAME: dict[str, tuple[str, str, str, bool, str, str | None]] = {
    "cea_monthly_ic": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://cea.nic.in/monthly-installed-capacity-report/",
        "Monthly all-India + state-wise installed capacity by fuel; primary publisher for the canonical installed-capacity series.",
    ),
    "iced_capacity_metatable": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://iced.niti.gov.in/energy/electricity/generation/capacity/state-wise",
        "Federal aggregator over CEA station-level data; harmonised across fiscal years.",
    ),
    "iced_deep_dive": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://iced.niti.gov.in/energy/electricity",
        "Per-state deep-dive API; provides allocated-capacity series + per-capita consumption.",
    ),
    "iced_gen_metatable": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://iced.niti.gov.in/energy/electricity/generation",
        "Federal aggregator for state-wise electricity generation by fuel.",
    ),
    "rbi_hbk_142_peak_demand": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 142: 12-year state-wise peak demand series.",
    ),
    "rbi_hbk_142_peak_met": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 142: 12-year state-wise peak-supplied series.",
    ),
}


def _build_energy_source_rows() -> tuple[SourceRow, ...]:
    rows: list[SourceRow] = []
    for nickname in SOURCE_NICKNAMES:
        producer, title, vintage = _TRIPLES[nickname]
        license_, tier, method, is_authority, url_main, notes = _BY_NICKNAME[nickname]
        rows.append(
            SourceRow(
                source_id=derive_source_id(producer, title, vintage),
                producer=producer,
                title=title,
                vintage=vintage,
                license=license_,  # type: ignore[arg-type]
                confidence_tier=tier,  # type: ignore[arg-type]
                is_issuing_authority=is_authority,
                verification_method=method,  # type: ignore[arg-type]
                url_main=url_main,
                citation_full=None,
                notes=notes,
            )
        )
    return tuple(rows)


ENERGY_SOURCES: tuple[SourceRow, ...] = _build_energy_source_rows()
ENERGY_SOURCE_ID_BY_NICKNAME: dict[str, str] = {
    nickname: row.source_id
    for nickname, row in zip(SOURCE_NICKNAMES, ENERGY_SOURCES, strict=True)
}


def upsert_energy_sources(con: duckdb.DuckDBPyConnection) -> int:
    """Idempotent INSERT-OR-REPLACE of the 6 energy citation rows into the
    in-memory ``sources`` DuckDB table.

    Caller is responsible for creating the ``sources`` table first and
    for emitting the table back to ``taxonomy/sources.parquet`` after.
    Returns the number of rows upserted (always 6 today).
    """
    upserted = 0
    for row in ENERGY_SOURCES:
        con.execute(
            """
            INSERT OR REPLACE INTO sources (
                source_id, producer, title, vintage,
                license, confidence_tier, is_issuing_authority,
                verification_method, url_main, citation_full, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row.source_id,
                row.producer,
                row.title,
                row.vintage,
                row.license,
                row.confidence_tier,
                row.is_issuing_authority,
                row.verification_method,
                row.url_main,
                row.citation_full,
                row.notes,
            ],
        )
        upserted += 1
    return upserted


# DDL identical to boundary_layers_seed.py's `sources` shape (mirrors
# source.schema.json). PRIMARY KEY on source_id makes INSERT OR REPLACE
# work cleanly across re-runs.
_SOURCES_DDL = """
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


def upsert_energy_sources_to_parquet(sources_parquet: Path) -> int:
    """Read-modify-write wrapper around :func:`upsert_energy_sources`.

    Opens an in-memory DuckDB, loads the existing
    ``taxonomy/sources.parquet`` (if any), upserts the 6 energy
    citation rows, writes the parquet back. Used by the
    ``emit-taxonomy`` orchestrator after office_holdings_seed has
    already written the wiki citation rows for the CM offices.

    Returns the number of rows upserted (always 6 today). Idempotent --
    re-running yields byte-identical output.
    """
    sources_parquet = Path(sources_parquet)
    sources_parquet.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")
    try:
        con.execute(_SOURCES_DDL)
        if sources_parquet.is_file():
            con.execute(
                f"INSERT INTO sources SELECT * FROM read_parquet('{sources_parquet.as_posix()}')"
            )
        n = upsert_energy_sources(con)
        con.execute(
            f"""
            COPY (
                SELECT * FROM sources ORDER BY source_id
            ) TO '{sources_parquet.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()

    return n
