"""X1a-fu2-C transcode: dim_party_alliances.parquet -> party_alliances.csv.

Bootstraps the canonical long-format CSV at
``datasets/data/entities/party_alliances.csv`` from the retired
``datasets/elections/dim_party_alliances.parquet`` per the column
contract in ``datasets/data/_schema/columns.json``.

Schema v2.0 (2026-06-12, plan TODO/20260612-alliance-phase-1-structural-fix-plan.md):
the canonical CSV's column shape is now (party_id, event_id, state,
alliance, source_id). The retired parquet carried the v1 shape
(party_id, short_name, period_label, alliance, source_id) -- no
``state`` column, no canonical ``event_id``. Resurrecting the parquet
and projecting it to the v2.0 CSV is therefore IMPOSSIBLE without
manual state-column backfill + period_label -> event_id mapping. The
guard in :func:`_project_rows` raises ``RuntimeError`` if the parquet
ever returns rows so the agent / operator surfaces the v2.0 gap
before any v1-shaped data corrupts the CSV.

Lifecycle:

- During X1a-fu2-C this module bootstrapped the CSV from the parquet
  (v1 shape). The CSV was then migrated to v2.0 by the alliance
  phase-1 fix (2026-06-12), at which point this transcoder became
  defensive scaffolding.
- The parquet is ``git rm``-d; subsequent ``emit-taxonomy`` runs find
  no parquet and ``emit`` returns None (silent skip) -- the committed
  CSV stays authoritative.
- The legacy ECI ingest adapters (``adapters/eci_ls.py``,
  ``adapters/eci_ae_panel.py``, ``pipeline/canonical_eci_backfill.py``)
  still produce ``party_alliance_dim_rows`` envelopes and writer.py
  still has the ``_write_dimensions`` path that would re-emit a
  parquet if those adapters ran. That writer path is preserved
  pending B4 retirement of the adapters; this CSV emit will be
  rewired to read from the envelope rows directly when that lands,
  and at that point the rewire MUST author both ``event_id`` and
  ``state`` columns -- not blindly project the parquet shape.

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
    rows = [dict(zip(cols, tup, strict=True)) for tup in rel.fetchall()]
    if rows:
        # v2.0 schema (2026-06-12) requires event_id + state on the CSV;
        # the v1 parquet shape cannot supply them. Surface loudly so the
        # operator does the manual backfill rather than corrupt the CSV.
        raise RuntimeError(
            "party_alliances_csv: refused to project "
            f"{parquet_path.as_posix()} ({len(rows)} rows) to "
            "datasets/data/entities/party_alliances.csv. The CSV is v2.0 "
            "(party_id, event_id, state, alliance, source_id) per plan "
            "TODO/20260612-alliance-phase-1-structural-fix-plan.md; the "
            "v1 parquet shape (party_id, short_name, period_label, "
            "alliance, source_id) lacks the event_id mapping + state "
            "column. Rewire this module to read from "
            "party_alliance_dim_rows envelopes and author both columns, "
            "or delete the parquet."
        )
    return rows


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
