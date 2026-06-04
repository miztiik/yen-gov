"""B2b.4.2 facet_axes parquet -> long-format CSV reingest.

Transcodes ``datasets/taxonomy/facet-axes.parquet`` (127 rows; facet axis
register) into ``datasets/data/facet_axes.csv`` (parent plan section 21.6 /
22.4; sub-sub-plan B2b.4 row B2b.4.2).

Source + target share the same eight columns 1:1
(``axis_id, axis_label, axis_description, allow_compute_on_read_total,
value_id, value_label, value_description, deprecated``). No re-keys; no
FKs. PK ``(axis_id, value_id)``. Filename loses the hyphen per parent
plan 21.6 underscore-in-filename convention.

Public surface:

    from yen_gov.canonical.reingest.facet_axes import emit
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


FILE_CLASS = "datasets/data/facet_axes.csv"

_COLUMNS = (
    "axis_id",
    "axis_label",
    "axis_description",
    "allow_compute_on_read_total",
    "value_id",
    "value_label",
    "value_description",
    "deprecated",
)


def _project_parquet(parquet_path: Path) -> list[dict[str, Any]]:
    sql = (
        "SELECT axis_id, axis_label, axis_description, "
        "allow_compute_on_read_total, value_id, value_label, "
        "value_description, deprecated "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY axis_id, value_id"
    )
    rel = duckdb.sql(sql)
    rows: list[dict[str, Any]] = []
    for tup in rel.fetchall():
        rows.append(dict(zip(_COLUMNS, tup, strict=True)))
    return rows


def emit(*, parquet_path: Path, out_path: Path) -> Path:
    """Transcode the facet-axes parquet into the long-format CSV.

    Args:
        parquet_path: path to ``datasets/taxonomy/facet-axes.parquet``.
        out_path: target CSV path (``datasets/data/facet_axes.csv``).

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
