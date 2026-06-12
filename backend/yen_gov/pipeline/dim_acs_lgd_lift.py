"""Join ``ac_crosswalk.lgd_ac_id`` onto ``dim_acs.parquet`` (Row A3).

Two responsibilities backed by the canonical crosswalk:

* :func:`load_lgd_lookup` returns the ``(state_code, eci_no) -> lgd_ac_id``
  map over the covered subset, sourced from
  ``datasets/data/entities/ac_crosswalk.csv`` (the canonical home after the
  parquet retirement in X1b). The live/backfill envelope builders
  (:func:`pipeline.canonical_eci_backfill.build_slice_envelope`) call this so
  EVERY future ``dim_acs`` write carries ``lgd_ac_id``. Without it the
  writer's DELETE+INSERT UPSERT would null the column on the next re-run.

* :func:`relift_dim_acs` is the one-shot that materialises the new column on
  the existing on-disk ``dim_acs.parquet`` for this PR. It re-emits the
  parquet through the canonical writer's :func:`_emit_table` so the KV
  metadata and the manifest ``schema_version`` advance to ``dim-acs`` v1.1,
  then regenerates ``manifest.json``.

``lgd_ac_id`` is the canonical INTERNAL join key per ADR-0049; ``eci_no``
stays the citizen-facing display + URL label. The crosswalk covers only the
2008 delimitation cycle, so 1976 rows (and ACs with no LGD code yet, e.g.
U08/J&K, S03/Assam) keep ``lgd_ac_id = NULL``.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import duckdb

from yen_gov.canonical.writer import _DIM_SPECS, _emit_table, _regenerate_manifest

#: The crosswalk binds only the post-delimitation cycle. A 1976 ``(state, eci)``
#: must never inherit a 2008 LGD code, hence the explicit guard on the join.
CROSSWALK_DELIM_YEAR = 2008


def load_lgd_lookup(datasets_root: Path) -> dict[tuple[str, int], int]:
    """Map ``(state_code, eci_no) -> lgd_ac_id`` over covered crosswalk rows.

    Only rows with a non-null ``lgd_ac_id`` appear; a missing key means the AC
    is not yet bound to an LGD code and the caller leaves ``lgd_ac_id`` NULL.
    Returns an empty map when the crosswalk CSV is absent.

    Reads ``datasets/data/entities/ac_crosswalk.csv`` via typed
    ``read_csv(columns=...)`` per the CSV column contract at
    ``datasets/data/_schema/columns.json``. The CSV does not carry the
    ``S01``-style ECI state code directly; it is derived in-SQL from the
    leading ``IN-([SU][0-9]{2})-`` segment of ``ac_id`` (every covered row
    in the on-disk corpus matches this pattern).
    """
    cx_path = datasets_root / "data" / "entities" / "ac_crosswalk.csv"
    if not cx_path.is_file():
        return {}
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            """
            SELECT regexp_extract(ac_id, '^IN-([SU][0-9]{2})-', 1) AS state_code,
                   eci_no,
                   lgd_ac_id
            FROM read_csv(
                ?,
                header = true,
                columns = {
                    'state_entity_id': 'VARCHAR',
                    'delim_year': 'INTEGER',
                    'eci_no': 'INTEGER',
                    'lgd_ac_id': 'INTEGER',
                    'ac_id': 'VARCHAR',
                    'ac_name': 'VARCHAR',
                    'match_method': 'VARCHAR',
                    'source_id': 'VARCHAR'
                },
                nullstr = '',
                auto_detect = false
            )
            WHERE lgd_ac_id IS NOT NULL
            """,
            [cx_path.as_posix()],
        ).fetchall()
    finally:
        con.close()
    return {(str(s), int(e)): int(lgd) for s, e, lgd in rows}


def relift_dim_acs(datasets_root: Path, *, dry_run: bool = False) -> int:
    """Re-emit ``dim_acs.parquet`` with ``lgd_ac_id`` joined from the crosswalk.

    Reads the existing dim into an in-memory table (BY NAME fills the new
    column with NULL), sets ``lgd_ac_id`` for delim_year=2008 ACs from the
    crosswalk, and writes back through :func:`_emit_table` so the parquet
    metadata + manifest advance to dim-acs v1.1. Returns the row count.
    """
    dim_path = datasets_root / "elections" / "dim_acs.parquet"
    cx_path = datasets_root / "taxonomy" / "ac_crosswalk.parquet"
    if not dim_path.is_file():
        raise SystemExit(f"dim_acs.parquet not found: {dim_path}")
    if not cx_path.is_file():
        raise SystemExit(f"ac_crosswalk.parquet not found: {cx_path}")

    spec = _DIM_SPECS["ac"]
    con = duckdb.connect(":memory:")
    try:
        col_defs = ", ".join(f"{name} {typ}" for name, typ in spec["columns"])
        con.execute(f"CREATE TABLE dim ({col_defs})")
        con.execute(
            "INSERT INTO dim BY NAME SELECT * FROM read_parquet(?)",
            [dim_path.as_posix()],
        )
        con.execute(
            """
            UPDATE dim
            SET lgd_ac_id = cx.lgd_ac_id
            FROM (
                SELECT state_code, eci_no, lgd_ac_id
                FROM read_parquet(?)
                WHERE lgd_ac_id IS NOT NULL
            ) AS cx
            WHERE dim.state_code = cx.state_code
              AND dim.eci_no = cx.eci_no
              AND dim.delim_year = ?
            """,
            [cx_path.as_posix(), CROSSWALK_DELIM_YEAR],
        )
        select_sql = "SELECT * FROM dim ORDER BY " + ", ".join(spec["sort_cols"])
        count = _emit_table(
            con=con,
            select_sql=select_sql,
            out_path=dim_path,
            table_id="elections.dim_acs",
            row_schema_file=spec["schema_file"],
            sort_cols=spec["sort_cols"],
            dry_run=dry_run,
        )
    finally:
        con.close()

    _regenerate_manifest(datasets_root, dry_run=dry_run)
    return count


def _distribution(datasets_root: Path) -> tuple[int, int]:
    """Return ``(total_rows, covered_rows)`` for the on-disk dim_acs."""
    dim_path = datasets_root / "elections" / "dim_acs.parquet"
    con = duckdb.connect(":memory:")
    try:
        [(total, covered)] = con.execute(
            "SELECT count(*), count(lgd_ac_id) FROM read_parquet(?)",
            [dim_path.as_posix()],
        ).fetchall()
    finally:
        con.close()
    return int(total), int(covered)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Lift lgd_ac_id onto dim_acs (Row A3)")
    ap.add_argument("--datasets-root", default="datasets")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.datasets_root)
    count = relift_dim_acs(root, dry_run=args.dry_run)
    if not args.dry_run:
        total, covered = _distribution(root)
        pct = (100.0 * covered / total) if total else 0.0
        print(
            f"dim_acs rows: {count} / lgd_ac_id covered {covered}/{total} "
            f"({pct:.1f}%)"
        )
    else:
        print(f"dry-run: dim_acs would emit {count} rows")


if __name__ == "__main__":
    main()


# Re-export for the envelope builders that populate lgd_ac_id on live writes.
__all__ = ["load_lgd_lookup", "relift_dim_acs", "CROSSWALK_DELIM_YEAR"]


# Type alias kept inline to avoid a runtime import where only annotations need it.
LgdLookup = Mapping[tuple[str, int], int]
