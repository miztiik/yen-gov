"""Tests for ``yen_gov.canonical.citation.lookup_source_id`` (PR-A6).

The data-driven counterpart to ``derive_source_id``. These tests use a
``tmp_path``-built fixture parquet (no real-corpus walk, per CLAUDE.md
§10 anti-patterns).
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.citation import derive_source_id, lookup_source_id


def _build_fixture_parquet(tmp_path: Path, rows: list[tuple[str, str, str, str]]) -> Path:
    """Write a minimal sources-shaped parquet at ``tmp_path/sources.parquet``.

    ``rows`` = list of ``(source_id, producer, title, vintage)`` tuples.
    Only the 4 columns ``lookup_source_id`` queries are populated; the
    full schema is irrelevant for this helper's contract.
    """
    out = tmp_path / "sources.parquet"
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE s (source_id VARCHAR, producer VARCHAR, "
            "title VARCHAR, vintage VARCHAR)"
        )
        con.executemany("INSERT INTO s VALUES (?, ?, ?, ?)", rows)
        con.execute(f"COPY s TO '{out.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()
    return out


def test_lookup_returns_source_id_on_exact_triple_match(tmp_path: Path) -> None:
    sid = derive_source_id("Reserve Bank of India", "Handbook 2024-25", "2024-25")
    pq = _build_fixture_parquet(
        tmp_path,
        [(sid, "Reserve Bank of India", "Handbook 2024-25", "2024-25")],
    )
    got = lookup_source_id(
        "Reserve Bank of India",
        "Handbook 2024-25",
        "2024-25",
        sources_path=pq,
    )
    assert got == sid


def test_lookup_raises_lookup_error_on_no_match(tmp_path: Path) -> None:
    sid = derive_source_id("Producer A", "Title A", "2024")
    pq = _build_fixture_parquet(tmp_path, [(sid, "Producer A", "Title A", "2024")])
    with pytest.raises(LookupError) as exc:
        lookup_source_id("Producer B", "Title A", "2024", sources_path=pq)
    msg = str(exc.value)
    assert "Producer B" in msg
    assert "Title A" in msg


def test_lookup_is_case_sensitive(tmp_path: Path) -> None:
    # Triples that differ only in case must NOT match - identity is
    # the verbatim publisher string per ADR-0032 / ADR-0042.
    sid = derive_source_id("Producer X", "Title X", "2024")
    pq = _build_fixture_parquet(tmp_path, [(sid, "Producer X", "Title X", "2024")])
    with pytest.raises(LookupError):
        lookup_source_id("producer x", "Title X", "2024", sources_path=pq)


def test_lookup_raises_file_not_found_when_parquet_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.parquet"
    with pytest.raises(FileNotFoundError):
        lookup_source_id("P", "T", "2024", sources_path=missing)


def test_lookup_rejects_empty_triple_fields(tmp_path: Path) -> None:
    # Symmetric with derive_source_id: empty inputs are caller errors,
    # not "no match" lookups - fail fast at the boundary.
    pq = _build_fixture_parquet(
        tmp_path,
        [(derive_source_id("P", "T", "2024"), "P", "T", "2024")],
    )
    with pytest.raises(ValueError):
        lookup_source_id("", "T", "2024", sources_path=pq)
    with pytest.raises(ValueError):
        lookup_source_id("P", "", "2024", sources_path=pq)
    with pytest.raises(ValueError):
        lookup_source_id("P", "T", "", sources_path=pq)


def test_lookup_picks_correct_row_among_many(tmp_path: Path) -> None:
    sid_a = derive_source_id("P", "T", "2023")
    sid_b = derive_source_id("P", "T", "2024")
    sid_c = derive_source_id("P", "T", "2025")
    pq = _build_fixture_parquet(
        tmp_path,
        [
            (sid_a, "P", "T", "2023"),
            (sid_b, "P", "T", "2024"),
            (sid_c, "P", "T", "2025"),
        ],
    )
    assert lookup_source_id("P", "T", "2024", sources_path=pq) == sid_b
    assert lookup_source_id("P", "T", "2025", sources_path=pq) == sid_c
