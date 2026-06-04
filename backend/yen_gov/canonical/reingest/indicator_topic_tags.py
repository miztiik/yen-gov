"""B2b.4.5 indicator_topic_tags parquet -> long-format CSV reingest.

Transcodes ``datasets/taxonomy/indicator_topic_tags.parquet`` (45 rows;
M:N tag enrichment) into ``datasets/data/indicator_topic_tags.csv``
(parent plan section 21.6 / 22.4; sub-sub-plan B2b.4 row B2b.4.5).

Verbatim 1:1 projection across all nine columns; no re-keys; no FKs to
re-construct on the way in (the FK on ``topic_id`` -> ``topics.csv.topic``
is enforced at read time by ``csv_validator``).

Public surface:

    from yen_gov.canonical.reingest.indicator_topic_tags import emit
    emit(parquet_path=..., out_path=...)

No mocks (Holy Law #7); duckdb reads the real parquet file. Tests stage a
miniature fixture parquet under ``tmp_path`` to exercise the path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from yen_gov.canonical.csv_writer import write_csv

__all__ = ["FILE_CLASS", "emit"]


FILE_CLASS = "datasets/data/indicator_topic_tags.csv"

_COLUMNS = (
    "topic_id",
    "artifact_kind",
    "artifact_id",
    "display",
    "is_default",
    "featured",
    "scope",
    "peer_set_default_override",
    "in_topic_order",
)


def _project_parquet(parquet_path: Path) -> list[dict[str, Any]]:
    sql = (
        "SELECT topic_id, artifact_kind, artifact_id, display, is_default, "
        "featured, scope, peer_set_default_override, in_topic_order "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY topic_id, artifact_kind, artifact_id"
    )
    rows: list[dict[str, Any]] = []
    for tup in duckdb.sql(sql).fetchall():
        rows.append(dict(zip(_COLUMNS, tup, strict=True)))
    return rows


def emit(*, parquet_path: Path, out_path: Path) -> Path:
    """Transcode the indicator_topic_tags parquet into the long-format CSV.

    Args:
        parquet_path: path to ``datasets/taxonomy/indicator_topic_tags.parquet``.
        out_path: target CSV path (``datasets/data/indicator_topic_tags.csv``).

    Returns:
        The resolved CSV path.

    Raises:
        FileNotFoundError: ``parquet_path`` does not exist.
    """
    if not parquet_path.exists():
        raise FileNotFoundError(parquet_path)
    rows = _project_parquet(parquet_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
