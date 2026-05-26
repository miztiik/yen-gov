"""Tier-A tests for ``yen_gov.canonical.livestock_sources_seed``.

Per CLAUDE.md section 15: operates on ``tmp_path`` (or builds in-memory
DuckDB). Asserts the 5 source_id hashes (Owner Reg + Pashu Aadhaar +
NADCP + Breeding + NAIP IV) are deterministic, the UPSERT is
idempotent, and the gold-tier / live-fetch / OGL-IN-1.0 invariants
hold (DAHD is the issuing authority for each Bharat Pashudhan series
per Hans + Max pin, plan-doc section 2).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from yen_gov.canonical.livestock_sources_seed import (
    LIVESTOCK_SOURCE_ID_BY_NICKNAME,
    LIVESTOCK_SOURCES,
    SOURCE_NICKNAMES,
    upsert_livestock_sources,
    upsert_livestock_sources_to_parquet,
)


def test_five_sources_built():
    """Exactly 5 sources: Owner Reg + Pashu Aadhaar + NADCP +
    Breeding ABIP+RGM + NAIP IV (one row per NDLM upstream endpoint,
    per ADR-0032 citation identity = (producer, title, vintage)).
    The CY / FY duality is carried at the observation row via
    ``period_label`` per CLAUDE.md section 12, not at the citation row.
    """
    assert len(LIVESTOCK_SOURCES) == 5
    assert len(SOURCE_NICKNAMES) == 5
    assert set(LIVESTOCK_SOURCE_ID_BY_NICKNAME) == set(SOURCE_NICKNAMES)


def test_source_id_hashes_are_deterministic():
    """The 5 derive_source_id outputs MUST be stable across runs. If a
    triple is edited in livestock_sources_seed.py, the hash changes and
    every downstream FK on observation rows in datasets/livestock/*.parquet
    goes dangling. The expected hashes were captured at PR 1 seed time
    (2026-05-25) from the verbatim DAHD producer + title + vintage triples.
    """
    expected = {
        "ndlm_owner_registration": "src-d98dc531ef7e",
        "ndlm_pashu_aadhaar": "src-7e5d4aac4995",
        "ndlm_nadcp_vaccination": "src-1d0c0fbf96e3",
        "ndlm_breeding_abip_rgm": "src-fb1694ab6a11",
        "ndlm_naip_iv": "src-93a2a72db482",
    }
    for nickname, src_id in expected.items():
        assert LIVESTOCK_SOURCE_ID_BY_NICKNAME[nickname] == src_id, (
            f"source_id drift for {nickname!r}: producer/title/vintage triple "
            f"changed since PR 1 seed. Either roll back the triple change or "
            f"re-derive AND update any datasets/livestock/*.parquet source_id "
            f"FKs in the SAME commit (per ADR-0032 + CLAUDE.md Holy Law #9)."
        )


def test_license_tier_authority_invariants():
    """DAHD is the gold issuing authority for every Bharat Pashudhan
    series (the portal is the official data product of the Department
    of Animal Husbandry & Dairying). All 5 rows must be:

    - confidence_tier = "gold"
    - is_issuing_authority = True
    - verification_method = "live-fetch" (continuously-updated JSON APIs)
    - license = "OGL-IN-1.0" (Open Government Licence India)
    """
    by_nick = {nick: row for nick, row in zip(SOURCE_NICKNAMES, LIVESTOCK_SOURCES)}
    for nick in SOURCE_NICKNAMES:
        row = by_nick[nick]
        assert row.confidence_tier == "gold", nick
        assert row.is_issuing_authority is True, nick
        assert row.verification_method == "live-fetch", nick
        assert row.license == "OGL-IN-1.0", nick
        assert row.vintage == "2024-25", nick
        assert "Animal Husbandry" in row.producer, nick
        assert row.notes is not None and len(row.notes) > 0, nick


def test_pashu_aadhaar_carries_honest_renderer_caveat():
    """Hans pin (plan-doc-pashu-aadhaar section 2): the Pashu Aadhaar
    registry counts TAGGED animals, not the underlying livestock
    population; the curve is monotone-non-decreasing because there is
    no de-registration event. The honest-renderer caveat must be
    surfaced in the source row's notes so any downstream FK on this
    source can carry that framing into the citizen surface (PR 3 wires
    the indicator-row comparability=directional_only + renderer_rules).
    """
    by_nick = {nick: row for nick, row in zip(SOURCE_NICKNAMES, LIVESTOCK_SOURCES)}
    notes = by_nick["ndlm_pashu_aadhaar"].notes
    assert notes is not None
    assert "tagged" in notes.lower() or "TAGGED" in notes
    assert "population" in notes.lower()
    assert "directional_only" in notes or "no_rank_table" in notes


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


def test_upsert_into_empty_table_writes_five_rows():
    con = duckdb.connect(":memory:")
    try:
        _create_sources_table(con)
        n = upsert_livestock_sources(con)
        assert n == 5
        count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        assert count == 5
    finally:
        con.close()


def test_upsert_is_idempotent():
    """Running twice yields the same 5 rows (not 10)."""
    con = duckdb.connect(":memory:")
    try:
        _create_sources_table(con)
        upsert_livestock_sources(con)
        upsert_livestock_sources(con)
        count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        assert count == 5
    finally:
        con.close()


def test_upsert_to_parquet_creates_file_when_absent(tmp_path: Path):
    target = tmp_path / "sources.parquet"
    assert not target.exists()
    n = upsert_livestock_sources_to_parquet(target)
    assert n == 5
    assert target.is_file()
    con = duckdb.connect()
    try:
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{target.as_posix()}')"
        ).fetchone()[0]
    finally:
        con.close()
    assert count == 5


def test_upsert_to_parquet_preserves_existing_rows(tmp_path: Path):
    """Existing (non-livestock) source rows survive the UPSERT. This
    mirrors how the live emit-taxonomy CLI step runs AFTER
    energy_sources_seed has already upserted its 21 rows -- the
    livestock upsert must not clobber the energy rows.
    """
    target = tmp_path / "sources.parquet"

    pre = duckdb.connect(":memory:")
    try:
        _create_sources_table(pre)
        pre.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "src-bbbbbbbbbbbb",
                "Some Other Publisher",
                "Some Other Title",
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

    n = upsert_livestock_sources_to_parquet(target)
    assert n == 5

    con = duckdb.connect()
    try:
        rows = con.execute(
            f"SELECT source_id FROM read_parquet('{target.as_posix()}') ORDER BY source_id"
        ).fetchall()
    finally:
        con.close()

    src_ids = [r[0] for r in rows]
    assert "src-bbbbbbbbbbbb" in src_ids
    assert len(src_ids) == 6  # 1 pre-existing + 5 livestock


def test_upsert_to_parquet_is_idempotent(tmp_path: Path):
    """Two consecutive calls yield the same 5-row parquet (byte-identical)."""
    target = tmp_path / "sources.parquet"
    upsert_livestock_sources_to_parquet(target)
    bytes_a = target.read_bytes()
    upsert_livestock_sources_to_parquet(target)
    bytes_b = target.read_bytes()
    assert bytes_a == bytes_b
