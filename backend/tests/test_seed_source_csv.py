"""Tests for B2a.1 source.csv emitter (sub-plan).

Stages a fixture ``sources.parquet`` under ``tmp_path`` (CLAUDE.md
anti-pattern: never walk the real on-disk corpus from pytest), runs the
emitter, asserts the CSV shape + that ``source_id`` is re-derived (not
hand-copied from the parquet column).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.source_csv import FILE_CLASS, emit


def _stage_parquet(path: Path, rows: list[dict[str, str | bool | None]]) -> None:
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE s ("
            "source_id VARCHAR, producer VARCHAR, title VARCHAR, vintage VARCHAR, "
            "license VARCHAR, confidence_tier VARCHAR, is_issuing_authority BOOLEAN, "
            "verification_method VARCHAR, url_main VARCHAR, citation_full VARCHAR, "
            "notes VARCHAR)"
        )
        for row in rows:
            con.execute(
                "INSERT INTO s VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [
                    row.get("source_id"),
                    row.get("producer"),
                    row.get("title"),
                    row.get("vintage"),
                    row.get("license"),
                    row.get("confidence_tier"),
                    row.get("is_issuing_authority"),
                    row.get("verification_method"),
                    row.get("url_main"),
                    row.get("citation_full"),
                    row.get("notes"),
                ],
            )
        con.execute(f"COPY s TO '{path.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()


def test_emit_projects_five_columns_and_rederives_source_id(tmp_path):
    parquet = tmp_path / "sources.parquet"
    _stage_parquet(
        parquet,
        [
            {
                "source_id": "src-IGNORED-1",
                "producer": "Election Commission of India",
                "title": "General Election to Lok Sabha 2009",
                "vintage": "2009",
                "url_main": "https://eci.gov.in/",
            },
            {
                "source_id": "src-IGNORED-2",
                "producer": "Wikipedia",
                "title": "List of Chief Ministers of Tripura",
                "vintage": "",
                "url_main": "https://en.wikipedia.org/wiki/...",
            },
        ],
    )
    out = tmp_path / "datasets" / "data" / "entities" / "source.csv"

    emit(sources_parquet=parquet, out_path=out)

    text = out.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "source_id,owner,title,vintage,url"
    assert len(lines) == 3, lines

    expected_id_eci = derive_source_id(
        "Election Commission of India",
        "General Election to Lok Sabha 2009",
        "2009",
    )
    expected_id_wiki = derive_source_id(
        "Wikipedia", "List of Chief Ministers of Tripura", ""
    )
    body = "\n".join(lines[1:])
    assert expected_id_eci in body
    assert expected_id_wiki in body
    # Hand-copied parquet source_ids must not appear.
    assert "src-IGNORED" not in text


def test_emit_rejects_duplicate_identity_triple(tmp_path):
    parquet = tmp_path / "sources.parquet"
    triple = {
        "producer": "X",
        "title": "Y",
        "vintage": "2024",
        "url_main": None,
    }
    _stage_parquet(parquet, [dict(triple), dict(triple)])
    out = tmp_path / "source.csv"
    with pytest.raises(ValueError, match="duplicate source_id"):
        emit(sources_parquet=parquet, out_path=out)


def test_emit_rejects_missing_producer(tmp_path):
    parquet = tmp_path / "sources.parquet"
    _stage_parquet(
        parquet,
        [{"producer": None, "title": "Y", "vintage": "2024", "url_main": None}],
    )
    with pytest.raises(ValueError, match="missing producer/title"):
        emit(sources_parquet=parquet, out_path=tmp_path / "source.csv")


def test_emitted_csv_passes_validator(tmp_path):
    parquet = tmp_path / "sources.parquet"
    _stage_parquet(
        parquet,
        [
            {
                "producer": "A",
                "title": "Alpha report",
                "vintage": "2020",
                "url_main": "https://example.org/a",
            },
            {
                "producer": "B",
                "title": "Beta report",
                "vintage": "2021",
                "url_main": None,
            },
        ],
    )
    repo_root = tmp_path
    out = repo_root / "datasets" / "data" / "entities" / "source.csv"
    emit(sources_parquet=parquet, out_path=out)
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)
