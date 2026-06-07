"""X1a-fu2-C transcode: dim_party_alliances.parquet -> party_alliances.csv.

Reads the retiring ``datasets/elections/dim_party_alliances.parquet`` and
projects it 1:1 to the canonical long-format CSV at
``datasets/data/entities/party_alliances.csv`` per the column contract in
``datasets/data/_schema/columns.json``.

Columns are unchanged from the parquet (5 cols, composite PK on
``(party_id, period_label)``):

- ``party_id``     VARCHAR  (not null, FK -> entities/parties.csv.party_id)
- ``short_name``   VARCHAR  (nullable)
- ``period_label`` VARCHAR  (not null)
- ``alliance``     VARCHAR  (nullable; null means "no declared alliance")
- ``source_id``    VARCHAR  (not null, FK -> entities/source.csv.source_id)

Lifecycle:

- During X1a-fu2-C this module bootstraps the CSV from the parquet so
  the citizen-facing CSV becomes the source of truth.
- The parquet is ``git rm``-d in the same PR; subsequent ``emit-taxonomy``
  runs find no parquet and the emit becomes a silent skip (the committed
  CSV stays authoritative).
- The legacy ECI ingest adapters (``adapters/eci_ls.py``,
  ``adapters/eci_ae_panel.py``, ``pipeline/canonical_eci_backfill.py``)
  still produce ``party_alliance_dim_rows`` envelopes and writer.py
  still has the ``_write_dimensions`` path that would re-emit a
  parquet if those adapters ran. That writer path is preserved
  pending B4 retirement of the adapters; this CSV emit will be
  rewired to read from the envelope rows directly when that lands.

No mocks (Holy Law #7); duckdb reads the real parquet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from yen_gov.canonical.csv_writer import write_csv

__all__ = [
    "FILE_CLASS",
    "emit",
]


FILE_CLASS = "datasets/data/entities/party_alliances.csv"


def _project_rows(parquet_path: Path) -> list[dict[str, Any]]:
    rel = duckdb.sql(
        "SELECT party_id, short_name, period_label, alliance, source_id "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY party_id, period_label"
    )
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, tup, strict=True)) for tup in rel.fetchall()]


def emit(*, parquet_path: Path, out_csv_path: Path) -> Path | None:
    """Project ``dim_party_alliances.parquet`` to ``party_alliances.csv``.

    Args:
        parquet_path: source ``datasets/elections/dim_party_alliances.parquet``.
        out_csv_path: target ``datasets/data/entities/party_alliances.csv``.

    Returns:
        The resolved ``out_csv_path`` when the CSV was (re-)emitted, or
        ``None`` when ``parquet_path`` is missing (the post-retirement
        steady state; the existing committed CSV stays authoritative).
    """
    if not parquet_path.is_file():
        return None
    rows = _project_rows(parquet_path)
    write_csv(path=out_csv_path, file_class=FILE_CLASS, rows=rows)
    return out_csv_path
