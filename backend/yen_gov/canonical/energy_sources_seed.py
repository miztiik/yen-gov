"""Seed the 13 energy citation rows into ``taxonomy/sources.parquet``.

P.1.A (7 sources) + P.1.B (5 sources) + P.1.C PR-Q (1 source) = 13
distinct upstreams.

P.1.A: 1 CEA + 3 ICED endpoints + 3 RBI Handbook tables (Table 142
peak-demand + Table 142 peak-met + Table 140 installed-capacity long-arc
added at C4.6).

P.1.B: 2 ICED distribution-dashboard endpoints (operational performance
and RPO compliance) + 3 RBI Handbook tables (141 power requirement,
139 power availability, 138 per-capita availability).

P.1.C PR-Q: 1 ICED state-coal-consumption-mt endpoint (first canonical
fuel-consumption lift; originating data: Coal Controller's Office /
Ministry of Coal; ICED is the federal aggregator, not issuing authority).

Each gets a citation row in the sources ledger so every emitted
observation in P.1.A, P.1.B, and P.1.C PR-Q can FK to a real
``source_id`` per Holy Law #9 + ADR-0032.

Pattern mirrors ``boundary_layers_seed.upsert_boundary_sources`` (T.0d):
INSERT-OR-REPLACE keyed on ``source_id`` so multiple subsystems can
upsert their rows into the same in-memory ``sources`` table before the
final COPY to parquet.

``derive_source_id(producer, title, vintage)`` is the only way to compute
``source_id`` -- NEVER hand-author (CLAUDE.md §10 + ADR-0032). The 12
expected hashes are baked into ``datasets/taxonomy/indicators.json`` at
C1 commit (6 rows) + C4.6 commit (7th, RBI Table 140) + P.1.B commit
(8th-12th); if a triple is edited here, those FKs go dangling and the
catalogue compile fails closed.

P.1.A C3 seed (2026-05-22); RBI Table 140 long-arc citation added at
P.1.A C4.6 (2026-05-24); P.1.B 5-row extension (2026-05-25).
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


# Operator nicknames for the 13 energy sources (7 P.1.A + 5 P.1.B + 1 P.1.C PR-Q).
# Adapters look up the materialised source_id by nickname rather than
# rebuilding the triple-hash each time.
SOURCE_NICKNAMES: tuple[str, ...] = (
    # --- P.1.A (7) -------------------------------------------------
    "cea_monthly_ic",
    "iced_capacity_metatable",
    "iced_deep_dive",
    "iced_gen_metatable",
    "rbi_hbk_142_peak_demand",
    "rbi_hbk_142_peak_met",
    "rbi_hbk_140_installed_capacity",
    # --- P.1.B (5) -------------------------------------------------
    # 2 ICED distribution-dashboard endpoints (distinct upstream
    # products from the analytics deep-dive surface; earn their own
    # ledger rows per ADR-0032 citation identity = (producer, title,
    # vintage)).
    "iced_distribution_perf",
    "iced_distribution_rpo",
    # 3 RBI Handbook tables not previously cited (state-level demand /
    # supply / per-capita-availability long-arc — CEA-originated,
    # RBI-republished, archived snapshot).
    "rbi_hbk_141_power_requirement",
    "rbi_hbk_139_power_availability",
    "rbi_hbk_138_per_capita_availability",
    # --- P.1.C PR-Q (1; first canonical fuel-consumption lift) ----
    # ICED state-coal-consumption-mt endpoint (4-grade SUM lift:
    # raw + washed + middlings + lignite; FY06-FY25; TOTAL COAL rows
    # dropped to avoid double-counting). Originating data: Coal
    # Controller's Office / Ministry of Coal. ICED is the federal
    # aggregator; not the issuing authority for the underlying fact
    # (plan-doc §3 Q-d). Same silver / not-authority / live-fetch
    # classification as other ICED endpoints.
    "iced_consumption_coal",
)


# (producer, title, vintage) triples. Per ADR-0042 (source schema v3.0),
# vintage MUST be non-empty ("strongest period anchor available"):
# publisher edition when published, operator snapshot window when not.
# CEA Monthly is the March-2026 snapshot; ICED APIs are continuously
# updated by NITI Aayog so we tag the federal fiscal-year snapshot
# window ("2024-25") of when this corpus was harvested; RBI Handbook
# tables carry their explicit 2024-25 edition tag.
_TRIPLES: dict[str, tuple[str, str, str]] = {
    "cea_monthly_ic": (
        "Central Electricity Authority",
        "Monthly Executive Summary \u2014 Installed Capacity (IC) sheet",
        "2026-03",
    ),
    "iced_capacity_metatable": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Capacity Metatable API (state-wise installed capacity, by fuel)",
        "2024-25",
    ),
    "iced_deep_dive": (
        "NITI Aayog India Climate & Energy Dashboard",
        "State-wise Deep Dive API",
        "2024-25",
    ),
    "iced_gen_metatable": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Generation Metatable API (state-wise electricity generation, by fuel)",
        "2024-25",
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
    "rbi_hbk_140_installed_capacity": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 140: State-wise Installed Capacity of Power",
        "2024-25",
    ),
    # --- P.1.B (5) -----------------------------------------------------
    "iced_distribution_perf": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Distribution Operational Performance API (state-wise billing efficiency, collection efficiency, T&D losses)",
        "2024-25",
    ),
    "iced_distribution_rpo": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Distribution RPO Compliance API (state-wise Renewable Purchase Obligation compliance, by segment)",
        "2024-25",
    ),
    "rbi_hbk_141_power_requirement": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 141: State-wise Power Requirement",
        "2024-25",
    ),
    "rbi_hbk_139_power_availability": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 139: State-wise Availability of Power",
        "2024-25",
    ),
    "rbi_hbk_138_per_capita_availability": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 138: State-wise Per Capita Availability of Power",
        "2024-25",
    ),
    # --- P.1.C PR-Q (1) ------------------------------------------------
    "iced_consumption_coal": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Coal Consumption (Domestic) State-wise API (per-state fiscal-year coal consumption, by grade)",
        "2024-25",
    ),
}


# Per-source license / confidence_tier / verification_method / authority /
# url_main / notes. CEA is the issuing authority for installed-capacity
# data (gold tier). ICED is the federal aggregator over CEA-published
# station-level data (silver tier -- republisher). RBI Handbook is the
# silver-tier longitudinal republisher of CEA peak-demand series per
# plan-doc §3 Q-d (Hans 2026-05-22): "RBI is the issuing authority for
# its own analytical Handbook but NOT for the underlying electricity
# capacity numbers -- every affected file under datasets/indicators/in/
# energy/ carries the disclosure 'Originating data: Central Electricity
# Authority, Ministry of Power' verbatim. Promoting longitudinal
# republishers to gold would silently inflate every aggregator in the
# future corpus and the tier loses signal." verification_method is
# archived-snapshot because the RBI Handbook is published as a PDF
# annually; we extract the table and archive it, not poll a live API.
# All energy upstreams publish under OGL-IN-1.0 (Open Government Licence
# India).
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
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 142: 12-year state-wise peak demand series. Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_142_peak_met": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 142: 12-year state-wise peak-supplied series. Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_140_installed_capacity": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 140: long-arc state-wise installed-capacity series (FY05 onwards). Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d). Used at P.1.A C4.6 to splice FY05-FY14 history onto state-installed-capacity-allocated-mw, whose ICED source (`iced_deep_dive`) only covers FY15-FY25.",
    ),
    # --- P.1.B (5) -----------------------------------------------------
    "iced_distribution_perf": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/energy/electricity/distribution/operationalPerformanceStates",
        "ICED distribution-dashboard endpoint covering three operational-performance series: billing efficiency, collection efficiency, T&D loss (state-wise FY09-FY24). Originating data: PFC State Distribution Utilities reports. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "iced_distribution_rpo": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/energy/electricity/distribution/rpo",
        "ICED distribution-dashboard endpoint covering state-wise Renewable Purchase Obligation compliance (three facets: solar, non-solar, total; FY19-FY21). Originating data: MNRE / state regulators. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_141_power_requirement": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 141: state-wise annual energy requirement (MU = GWh, FY05-FY25). Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_139_power_availability": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 139: state-wise annual energy availability (MU = GWh, FY05-FY25). Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). Companion to Table 141 -- requirement minus availability gives the energy-not-supplied deficit. RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_138_per_capita_availability": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 138: state-wise per-capita electricity availability (kWh per person per year, FY05-FY25). Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). Population denominator from Census 2011 + linear projection. RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    # --- P.1.C PR-Q (1) ------------------------------------------------
    "iced_consumption_coal": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/energy/fuel-sources/coal/consumption-domestic-state",
        "ICED fuel-sources endpoint for state-wise domestic coal consumption (4 grades: raw + washed + middlings + lignite; FY06-FY25). Originating data: Coal Controller's Office / Ministry of Coal. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
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
    """Idempotent scope-authoritative emit of the 13 energy citation rows
    into the in-memory ``sources`` DuckDB table.

    First DELETEs every row whose ``(producer, title)`` pair is owned by
    this seed (i.e. one of the 13 ``_TRIPLES`` keys); then INSERTs the
    13 current rows. This makes the seed structurally authoritative for
    its 13 ``(producer, title)`` slots: when a vintage rotates (as in
    ADR-0042 + the 5 ICED rotations of PR-B Commit 2), the previous
    ``source_id`` (derived from the previous vintage) is purged rather
    than orphaned. INSERT-OR-REPLACE alone would NOT achieve this
    because the new ``source_id`` hash differs from the old one.

    Caller is responsible for creating the ``sources`` table first and
    for emitting the table back to ``taxonomy/sources.parquet`` after.
    Returns the number of rows upserted (always 13 today: 7 P.1.A + 5 P.1.B + 1 P.1.C PR-Q).
    """
    owned_keys = sorted({(producer, title) for producer, title, _ in _TRIPLES.values()})
    for producer, title in owned_keys:
        con.execute(
            "DELETE FROM sources WHERE producer = ? AND title = ?",
            [producer, title],
        )
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
    ``taxonomy/sources.parquet`` (if any), upserts the 13 energy
    citation rows, writes the parquet back. Used by the
    ``emit-taxonomy`` orchestrator after office_holdings_seed has
    already written the wiki citation rows for the CM offices.

    Returns the number of rows upserted (always 13 today: 7 P.1.A +
    5 P.1.B + 1 P.1.C PR-Q). Idempotent -- re-running yields byte-identical
    output.
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
