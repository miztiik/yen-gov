"""Unit tests for ``yen_gov.canonical.reingest.indicator_topic_tags`` (B2b.4.5).

Stages a miniature fixture parquet under ``tmp_path`` and asserts the
emitter's 1:1 projection semantics. The real-corpus cross-format-parity
gate lives in ``test_csv_parquet_parity.py::test_indicator_topic_tags``.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.indicator_topic_tags import FILE_CLASS, emit


def _stage_parquet(
    path: Path,
    rows: list[
        tuple[
            str,
            str,
            str | None,
            str | None,
            bool,
            bool,
            str,
            str | None,
            int,
        ]
    ],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        "("
        + ", ".join(
            "NULL"
            if v is None
            else (
                ("TRUE" if v else "FALSE")
                if isinstance(v, bool)
                else (
                    str(v)
                    if isinstance(v, int)
                    else "'" + v.replace("'", "''") + "'"
                )
            )
            for v in r
        )
        + ")"
        for r in rows
    )
    duckdb.sql(
        "COPY (SELECT topic_id, artifact_kind, artifact_id, display, "
        "is_default, featured, scope, peer_set_default_override, "
        "in_topic_order FROM (VALUES "
        + values
        + ") AS t(topic_id, artifact_kind, artifact_id, display, "
        "is_default, featured, scope, peer_set_default_override, "
        f"in_topic_order)) TO '{path.as_posix()}' (FORMAT PARQUET)"
    )


def test_emit_projects_all_nine_columns_and_sorts(tmp_path: Path) -> None:
    parquet_path = tmp_path / "indicator_topic_tags.parquet"
    out_path = tmp_path / "data" / "indicator_topic_tags.csv"
    _stage_parquet(
        parquet_path,
        [
            (
                "z-topic",
                "indicator",
                "z/ind",
                None,
                False,
                False,
                "national",
                None,
                9,
            ),
            (
                "a-topic",
                "election",
                None,
                "Latest assembly election",
                False,
                False,
                "state",
                None,
                1,
            ),
            (
                "a-topic",
                "indicator",
                "a/ind_two",
                None,
                True,
                False,
                "state",
                "override",
                3,
            ),
            (
                "a-topic",
                "indicator",
                "a/ind_one",
                None,
                False,
                True,
                "national",
                None,
                2,
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
        "topic_id,artifact_kind,artifact_id,display,is_default,featured,"
        "scope,peer_set_default_override,in_topic_order"
    )
    # PK sort order: a-topic/election/NULL, a-topic/indicator/a/ind_one,
    # a-topic/indicator/a/ind_two, z-topic/indicator/z/ind.
    assert lines[1].startswith(
        "a-topic,election,,Latest assembly election,false,false,state,,1"
    )
    assert lines[2].startswith(
        "a-topic,indicator,a/ind_one,,false,true,national,,2"
    )
    assert lines[3].startswith(
        "a-topic,indicator,a/ind_two,,true,false,state,override,3"
    )
    assert lines[4].startswith(
        "z-topic,indicator,z/ind,,false,false,national,,9"
    )


def test_emit_round_trips_through_validator(tmp_path: Path) -> None:
    parquet_path = tmp_path / "indicator_topic_tags.parquet"
    out_path = tmp_path / "data" / "indicator_topic_tags.csv"
    _stage_parquet(
        parquet_path,
        [
            (
                "agriculture",
                "indicator",
                "ag/ind1",
                None,
                False,
                False,
                "national",
                None,
                1,
            ),
        ],
    )
    emit(parquet_path=parquet_path, out_path=out_path)
    # Stage a minimal repo_root with the schema + FK target the validator needs.
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
    topics = repo_root / "datasets" / "data" / "topics.csv"
    topics.parent.mkdir(parents=True, exist_ok=True)
    topics.write_text(
        "topic,name,parent\nagriculture,Agriculture,\n",
        encoding="utf-8",
    )
    target_in_repo = (
        repo_root / "datasets" / "data" / "indicator_topic_tags.csv"
    )
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
