"""B2b.4.1 methodology_breaks parquet -> long-format CSV reingest.

Transcodes ``datasets/taxonomy/methodology_breaks.parquet`` (5 rows; F6
Rosling-rule register) into ``datasets/data/methodology_breaks.csv``
(parent plan section 21.6 / 22.4; sub-sub-plan B2b.4 row B2b.4.1).

Source + target share the same seven columns 1:1
(``methodology_version, at_year, at_period_seq, kind, note, publisher_url,
supersedes_methodology_version``). No re-keys; no FKs. PK
``(methodology_version, at_year, at_period_seq)``.

Public surface:

    from yen_gov.canonical.reingest.methodology_breaks import emit
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


FILE_CLASS = "datasets/data/methodology_breaks.csv"

_COLUMNS = (
    "methodology_version",
    "at_year",
    "at_period_seq",
    "kind",
    "note",
    "publisher_url",
    "supersedes_methodology_version",
)


def _project_parquet(parquet_path: Path) -> list[dict[str, Any]]:
    sql = (
        "SELECT methodology_version, at_year, at_period_seq, kind, note, "
        "publisher_url, supersedes_methodology_version "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY methodology_version, at_year, at_period_seq"
    )
    rel = duckdb.sql(sql)
    rows: list[dict[str, Any]] = []
    for tup in rel.fetchall():
        rows.append(dict(zip(_COLUMNS, tup, strict=True)))
    return rows


def emit(*, parquet_path: Path, out_path: Path) -> Path:
    """Transcode the methodology_breaks parquet into the long-format CSV.

    Args:
        parquet_path: path to ``datasets/taxonomy/methodology_breaks.parquet``.
        out_path: target CSV path
            (``datasets/data/methodology_breaks.csv``).

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
