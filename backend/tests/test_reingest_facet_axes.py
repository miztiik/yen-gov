"""Unit tests for ``yen_gov.canonical.reingest.facet_axes`` (B2b.4.2).

Stages a miniature fixture parquet under ``tmp_path`` and asserts the
emitter's 1:1 projection semantics. The real-corpus cross-format-parity
gate lives in ``test_csv_parquet_parity.py::test_facet_axes``.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.facet_axes import FILE_CLASS, emit


def _stage_parquet(
    path: Path,
    rows: list[
        tuple[str, str, str | None, bool, str, str, str | None, bool]
    ],
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
                else ("TRUE" if v else "FALSE")
                if isinstance(v, bool)
                else repr(v)
            )
            for v in r
        )
        + ")"
        for r in rows
    )
    duckdb.sql(
        "COPY (SELECT axis_id, axis_label, axis_description, "
        "allow_compute_on_read_total, value_id, value_label, "
        "value_description, deprecated FROM (VALUES "
        + values
        + ") AS t(axis_id, axis_label, axis_description, "
        "allow_compute_on_read_total, value_id, value_label, "
        f"value_description, deprecated)) TO '{path.as_posix()}' "
        "(FORMAT PARQUET)"
    )


def test_emit_projects_all_eight_columns_and_sorts(tmp_path: Path) -> None:
    parquet_path = tmp_path / "facet-axes.parquet"
    out_path = tmp_path / "data" / "facet_axes.csv"
    _stage_parquet(
        parquet_path,
        [
            (
                "z-axis",
                "Z label",
                "later sort key",
                False,
                "v1",
                "Value one",
                None,
                False,
            ),
            (
                "a-axis",
                "A label",
                None,
                True,
                "v2",
                "Second value",
                "with quote ' inside",
                True,
            ),
            (
                "a-axis",
                "A label",
                None,
                True,
                "v1",
                "First value",
                "earliest",
                False,
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
        "axis_id,axis_label,axis_description,allow_compute_on_read_total,"
        "value_id,value_label,value_description,deprecated"
    )
    # PK sort order: a-axis/v1, a-axis/v2, z-axis/v1.
    assert lines[1].startswith("a-axis,A label,,true,v1,First value,")
    assert lines[2].startswith("a-axis,A label,,true,v2,Second value,")
    assert lines[3].startswith("z-axis,Z label,later sort key,false,v1,")


def test_emit_round_trips_through_validator(tmp_path: Path) -> None:
    parquet_path = tmp_path / "facet-axes.parquet"
    out_path = tmp_path / "data" / "facet_axes.csv"
    _stage_parquet(
        parquet_path,
        [
            (
                "a1",
                "Axis one",
                "describes axis one",
                False,
                "v1",
                "Value one",
                "describes value one",
                False,
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
    target_in_repo = repo_root / "datasets" / "data" / "facet_axes.csv"
    target_in_repo.parent.mkdir(parents=True, exist_ok=True)
    target_in_repo.write_text(
        out_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    validate_csv(
        path=target_in_repo, file_class=FILE_CLASS, repo_root=repo_root
    )


def test_emit_raises_when_parquet_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        emit(
            parquet_path=tmp_path / "absent.parquet",
            out_path=tmp_path / "out.csv",
        )
