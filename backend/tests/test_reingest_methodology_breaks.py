"""Unit tests for ``yen_gov.canonical.reingest.methodology_breaks`` (B2b.4.1).

These tests stage a miniature fixture parquet under ``tmp_path`` and assert
the emitter's 1:1 projection semantics. The real-corpus cross-format-parity
gate lives in ``test_csv_parquet_parity.py::test_methodology_breaks``.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.methodology_breaks import FILE_CLASS, emit


def _stage_parquet(
    path: Path,
    rows: list[tuple[str, int, int, str, str, str | None, str | None]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        "("
        + ", ".join(
            "NULL"
            if v is None
            else (
                "'" + v.replace("'", "''") + "'"
                if isinstance(v, str)
                else repr(v)
            )
            for v in r
        )
        + ")"
        for r in rows
    )
    duckdb.sql(
        "COPY (SELECT methodology_version, at_year, at_period_seq, kind, "
        "note, publisher_url, supersedes_methodology_version FROM (VALUES "
        + values
        + ") AS t(methodology_version, at_year, at_period_seq, kind, note, "
        f"publisher_url, supersedes_methodology_version)) TO '{path.as_posix()}' "
        "(FORMAT PARQUET)"
    )


def test_emit_projects_all_seven_columns_and_sorts(tmp_path: Path) -> None:
    parquet_path = tmp_path / "methodology_breaks.parquet"
    out_path = tmp_path / "data" / "methodology_breaks.csv"
    _stage_parquet(
        parquet_path,
        [
            (
                "z-late",
                2020,
                1,
                "frame_change",
                "later sort key",
                "https://example.test/z",
                None,
            ),
            (
                "a-first",
                2019,
                4,
                "definition_change",
                "earliest sort key with quotes ' inside",
                None,
                "a-first-v0",
            ),
            (
                "a-first",
                2020,
                1,
                "reclassification",
                "second row same version",
                "https://example.test/a",
                None,
            ),
        ],
    )

    emitted = emit(parquet_path=parquet_path, out_path=out_path)
    assert emitted == out_path
    text = out_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert "\r" not in text
    lines = text.splitlines()
    assert lines[0] == (
        "methodology_version,at_year,at_period_seq,kind,note,"
        "publisher_url,supersedes_methodology_version"
    )
    # PK sort order: a-first/2019/4, a-first/2020/1, z-late/2020/1.
    assert lines[1].startswith("a-first,2019,4,definition_change,")
    assert lines[2].startswith("a-first,2020,1,reclassification,")
    assert lines[3].startswith("z-late,2020,1,frame_change,")


def test_emit_round_trips_through_validator(tmp_path: Path) -> None:
    parquet_path = tmp_path / "methodology_breaks.parquet"
    out_path = tmp_path / "data" / "methodology_breaks.csv"
    _stage_parquet(
        parquet_path,
        [
            (
                "v1",
                2020,
                1,
                "frame_change",
                "note one",
                "https://example.test/1",
                None,
            ),
        ],
    )
    emit(parquet_path=parquet_path, out_path=out_path)
    # Stage an empty repo_root with the schema file the validator needs.
    repo_root = tmp_path / "repo"
    schema_target = repo_root / "datasets" / "data" / "_schema"
    schema_target.mkdir(parents=True)
    src_schema = (
        Path(__file__).resolve().parents[2]
        / "datasets"
        / "data"
        / "_schema"
    )
    for name in ("columns.json", "columns.schema.json"):
        (schema_target / name).write_text(
            (src_schema / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    target_in_repo = repo_root / "datasets" / "data" / "methodology_breaks.csv"
    target_in_repo.parent.mkdir(parents=True, exist_ok=True)
    target_in_repo.write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
    validate_csv(path=target_in_repo, file_class=FILE_CLASS, repo_root=repo_root)


def test_emit_raises_when_parquet_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        emit(
            parquet_path=tmp_path / "absent.parquet",
            out_path=tmp_path / "out.csv",
        )
