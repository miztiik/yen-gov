"""Tier-A tests for the Pincode Directory ingest (Phase A.1.b).

CLAUDE.md §10 anti-pattern: NO real-corpus walks from pytest. All tests
use ``tmp_path`` fixtures with hand-built CSVs.

Coverage:
  - smoke: ingest writes the canonical CSV + sources.parquet with the
    expected row count and source_id.
  - idempotency: re-running against byte-identical input yields
    byte-identical CSV bytes (the determinism guarantee).
  - sort ordering: rows in the emitted CSV are ordered by
    (pincode, officename) regardless of input order.
  - sources row UPSERT: the citation row carries the right
    producer/title/vintage/source_id triple and FK-resolves.
  - sources idempotency: re-running over a pre-existing sources
    parquet leaves the row count unchanged (UPSERT, not INSERT).
  - missing input file: raises a descriptive ``FileNotFoundError``.

G8-finish (2026-06-08): the writer body was rewritten parquet -> direct
CSV emit per plan-doc section 21.2; the 9 assertions in this module that
previously decoded the output via ``read_parquet`` now decode it via
``read_csv_auto`` / :mod:`csv`. The sources.parquet ledger remains a
separate ADR-0032 scope: those assertions still use ``read_parquet``
until the source-table migration (post-X1b) flips them.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.datagovin_ogd.ingest_pincode import (
    PINCODE_OUTPUT_COLUMNS,
    PINCODE_SOURCE_ID,
    PRODUCER,
    TITLE,
    VINTAGE,
    build_pincode_source_row,
    ingest_pincode_directory,
    upsert_pincode_source_to_parquet,
)


def _fixture_csv(*lines: str) -> bytes:
    """Mimics the inline-CSV helper from test_sources_datagovin_ogd_pincode."""
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write_csv(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


_CSV_BODY = _fixture_csv(
    "circlename,regionname,divisionname,officename,pincode,"
    "officetype,delivery,district,statename,latitude,longitude",
    # Intentionally OUT of (pincode, officename) order — the ingest
    # sorts before writing so the assertion exercises that path.
    "Karnataka Circle,Bengaluru Region,Bengaluru East Division,"
    "Indiranagar SO,560038,SO,Delivery,BANGALORE URBAN,KARNATAKA,12.97,77.64",
    "Telangana Circle,Hyderabad Region,Adilabad Division,"
    "Kothimir B.O,504273,BO,Delivery,KB ASIFABAD,TELANGANA,19.36,79.53",
    "Tamilnadu Circle,Chennai Region,Chennai South Division,"
    "T Nagar SO,600017,SO,Delivery,CHENNAI,TAMIL NADU,13.04,80.24",
)


# ---------------------------------------------------------------------------
# Smoke + structural assertions
# ---------------------------------------------------------------------------


def test_ingest_writes_csv_and_sources_row(tmp_path: Path) -> None:
    csv_in = tmp_path / "in" / "pincodes.csv"
    out_csv = tmp_path / "out" / "pincode.csv"
    sources_parquet = tmp_path / "tax" / "sources.parquet"
    _write_csv(csv_in, _CSV_BODY)

    result = ingest_pincode_directory(
        input_csv=csv_in,
        output_csv=out_csv,
        sources_parquet=sources_parquet,
    )

    assert result.row_count == 3
    assert result.parsed.record_count == 3
    assert result.parsed.invalid_pincode_count == 0
    assert result.source_id == PINCODE_SOURCE_ID
    assert out_csv.is_file()
    assert sources_parquet.is_file()


def test_emitted_csv_columns_match_canonical_order(tmp_path: Path) -> None:
    csv_in = tmp_path / "in.csv"
    out_csv = tmp_path / "out.csv"
    sources_parquet = tmp_path / "sources.parquet"
    _write_csv(csv_in, _CSV_BODY)

    ingest_pincode_directory(
        input_csv=csv_in,
        output_csv=out_csv,
        sources_parquet=sources_parquet,
    )

    # First line of the CSV is the header; split on the standard ',' so the
    # assertion is independent of any DuckDB type-detection behaviour.
    with out_csv.open(encoding="utf-8", newline="") as fp:
        header = next(csv.reader(fp))
    assert tuple(header) == PINCODE_OUTPUT_COLUMNS


def test_rows_sorted_by_pincode_then_officename(tmp_path: Path) -> None:
    csv_in = tmp_path / "in.csv"
    out_csv = tmp_path / "out.csv"
    sources_parquet = tmp_path / "sources.parquet"
    _write_csv(csv_in, _CSV_BODY)

    ingest_pincode_directory(
        input_csv=csv_in,
        output_csv=out_csv,
        sources_parquet=sources_parquet,
    )

    with out_csv.open(encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp))

    # Expected order is by pincode ascending.
    assert [r["pincode"] for r in rows] == ["504273", "560038", "600017"]


def test_source_id_fk_present_on_every_row(tmp_path: Path) -> None:
    csv_in = tmp_path / "in.csv"
    out_csv = tmp_path / "out.csv"
    sources_parquet = tmp_path / "sources.parquet"
    _write_csv(csv_in, _CSV_BODY)

    ingest_pincode_directory(
        input_csv=csv_in,
        output_csv=out_csv,
        sources_parquet=sources_parquet,
    )

    with out_csv.open(encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp))

    distinct = {r["source_id"] for r in rows}
    assert distinct == {PINCODE_SOURCE_ID}


def test_sources_row_carries_correct_citation_triple(tmp_path: Path) -> None:
    csv_in = tmp_path / "in.csv"
    out_csv = tmp_path / "out.csv"
    sources_parquet = tmp_path / "sources.parquet"
    _write_csv(csv_in, _CSV_BODY)

    ingest_pincode_directory(
        input_csv=csv_in,
        output_csv=out_csv,
        sources_parquet=sources_parquet,
    )

    con = duckdb.connect(":memory:")
    try:
        row = con.execute(
            f"""
            SELECT source_id, producer, title, vintage, license,
                   confidence_tier, is_issuing_authority, verification_method
            FROM read_parquet('{sources_parquet.as_posix()}')
            WHERE source_id = ?
            """,
            [PINCODE_SOURCE_ID],
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    sid, prod, title, vint, lic, tier, auth, method = row
    assert sid == derive_source_id(PRODUCER, TITLE, VINTAGE)
    assert prod == PRODUCER
    assert title == TITLE
    assert vint == VINTAGE
    assert lic == "OGL-IN-1.0"
    assert tier == "gold"
    assert auth is True
    assert method == "transcribed"


# ---------------------------------------------------------------------------
# Determinism + idempotency
# ---------------------------------------------------------------------------


def test_reingest_produces_byte_identical_csv(tmp_path: Path) -> None:
    """Re-running ingest against the same input yields byte-identical
    output bytes — required for the citation-ledger invariant
    (Holy Law #10) that re-runs against byte-identical upstream
    leave observation bytes unchanged.
    """
    csv_in = tmp_path / "in.csv"
    out_csv = tmp_path / "out.csv"
    sources_parquet = tmp_path / "sources.parquet"
    _write_csv(csv_in, _CSV_BODY)

    ingest_pincode_directory(
        input_csv=csv_in,
        output_csv=out_csv,
        sources_parquet=sources_parquet,
    )
    sha1 = _sha256(out_csv)
    src_sha1 = _sha256(sources_parquet)

    ingest_pincode_directory(
        input_csv=csv_in,
        output_csv=out_csv,
        sources_parquet=sources_parquet,
    )
    sha2 = _sha256(out_csv)
    src_sha2 = _sha256(sources_parquet)

    assert sha1 == sha2, "pincode.csv bytes drifted across re-runs"
    assert src_sha1 == src_sha2, "sources.parquet bytes drifted across re-runs"


def test_sources_upsert_preserves_unrelated_rows(tmp_path: Path) -> None:
    """A pre-existing sources.parquet with rows from a different adapter
    must survive the pincode UPSERT untouched — the pincode citation row
    is added ALONGSIDE, not replacing them.
    """
    sources_parquet = tmp_path / "sources.parquet"

    # Seed an unrelated citation row first.
    unrelated_id = derive_source_id("Bureau of Other Things", "Some Report", "2024")
    con = duckdb.connect(":memory:")
    try:
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
        con.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                unrelated_id,
                "Bureau of Other Things",
                "Some Report",
                "2024",
                "CC-BY-4.0",
                "silver",
                False,
                "live-fetch",
                "https://example.org/report",
                None,
                None,
            ],
        )
        con.execute(
            f"COPY sources TO '{sources_parquet.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        con.close()

    n = upsert_pincode_source_to_parquet(sources_parquet)
    assert n == 1

    con = duckdb.connect(":memory:")
    try:
        ids = sorted(
            r[0]
            for r in con.execute(
                f"SELECT source_id FROM read_parquet('{sources_parquet.as_posix()}')"
            ).fetchall()
        )
    finally:
        con.close()

    assert unrelated_id in ids
    assert PINCODE_SOURCE_ID in ids


def test_re_upsert_does_not_duplicate_pincode_row(tmp_path: Path) -> None:
    """Two consecutive upserts MUST leave exactly one pincode row."""
    sources_parquet = tmp_path / "sources.parquet"

    upsert_pincode_source_to_parquet(sources_parquet)
    upsert_pincode_source_to_parquet(sources_parquet)

    con = duckdb.connect(":memory:")
    try:
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{sources_parquet.as_posix()}') "
            f"WHERE source_id = ?",
            [PINCODE_SOURCE_ID],
        ).fetchone()
    finally:
        con.close()

    assert count == (1,)


# ---------------------------------------------------------------------------
# Boundary error cases
# ---------------------------------------------------------------------------


def test_missing_input_file_raises_descriptive(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.csv"
    out_csv = tmp_path / "out.csv"
    sources_parquet = tmp_path / "sources.parquet"

    with pytest.raises(FileNotFoundError, match="pincode directory input"):
        ingest_pincode_directory(
            input_csv=missing,
            output_csv=out_csv,
            sources_parquet=sources_parquet,
        )

    # No CSV should have been written.
    assert not out_csv.exists()
    assert not sources_parquet.exists()


def test_source_row_builder_matches_module_constant() -> None:
    """The SourceRow constructed from the module's identity triple
    MUST carry the same source_id as :data:`PINCODE_SOURCE_ID`.
    Guards against an accidental drift between the triple constants
    and the materialised id at module-import time.
    """
    row = build_pincode_source_row()
    assert row.source_id == PINCODE_SOURCE_ID
    assert row.source_id == derive_source_id(PRODUCER, TITLE, VINTAGE)
    assert row.producer == PRODUCER
    assert row.title == TITLE
    assert row.vintage == VINTAGE
