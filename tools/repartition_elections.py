"""One-shot: convert datasets/elections/election_results.parquet to Hive-partitioned layout.

Reads the existing monolith, derives the ``state`` partition value from
each row's ``entity_id`` (first two hyphen-separated segments, lower-cased,
``-`` swapped for ``_``), and emits one ``state=<val>/election_results.parquet``
per distinct state. The monolith is removed once all partition files land.
The manifest is regenerated last so consumers see the new shape atomically.

This is a Phase 0 closeout tool (TODO 20260517-canonical-long-format-pivot
§0e.10 lock B). The canonical writer's ``_emit_observations`` was updated
in the same PR to emit partitioned output natively on every subsequent
``write_batch``; this tool is the one-time migration of the on-disk
monolith. Safe to delete from the tree once the migration ships.

Usage::

    cd <repo-root>
    python tools/repartition_elections.py

Re-running with the monolith already absent is a no-op.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parent.parent
MONOLITH = ROOT / "datasets" / "elections" / "election_results.parquet"
FAMILY_DIR = ROOT / "datasets" / "elections"
STEM = "election_results"

# Mirror the writer's derivation expression verbatim — any divergence here
# would silently produce a different partition grammar on the migration
# than on subsequent write_batch emits.
_STATE_PARTITION_SQL = (
    "replace("
    "lower("
    "CASE WHEN entity_id LIKE '%-%' "
    "THEN regexp_extract(entity_id, '^([A-Z]+-[A-Z0-9]+)', 1) "
    "ELSE entity_id "
    "END"
    "), '-', '_')"
)


def main() -> int:
    if not MONOLITH.is_file():
        print(f"[skip] No monolith at {MONOLITH.relative_to(ROOT).as_posix()}; nothing to do.")
        return 0

    print(f"[plan] Read monolith: {MONOLITH.relative_to(ROOT).as_posix()}")
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            f"CREATE TABLE obs AS SELECT * FROM read_parquet('{MONOLITH.as_posix()}')"
        )
        [(total_rows,)] = con.execute("SELECT count(*) FROM obs").fetchall()
        partition_values = [
            r[0]
            for r in con.execute(
                f"SELECT DISTINCT {_STATE_PARTITION_SQL} AS pv FROM obs ORDER BY pv"
            ).fetchall()
        ]
        print(f"[plan] {total_rows:,} rows -> {len(partition_values)} partitions: {partition_values}")

        written_rows = 0
        for pv in partition_values:
            partition_dir = FAMILY_DIR / f"state={pv}"
            partition_dir.mkdir(parents=True, exist_ok=True)
            out_path = partition_dir / f"{STEM}.parquet"
            tmp_path = out_path.with_suffix(".parquet.tmp")
            con.execute(
                f"""
                COPY (
                  SELECT observation_id, entity_id, year, period_label, period_seq,
                         indicator_id, value_numeric, value_text, source_id, derivation
                  FROM obs
                  WHERE {_STATE_PARTITION_SQL} = ?
                  ORDER BY indicator_id, entity_id, year, period_seq
                ) TO '{tmp_path.as_posix()}'
                (FORMAT PARQUET, ROW_GROUP_SIZE 100000)
                """,
                [pv],
            )
            os.replace(tmp_path, out_path)
            [(rc,)] = con.execute(
                f"SELECT count(*) FROM read_parquet('{out_path.as_posix()}')"
            ).fetchall()
            print(
                f"  wrote {out_path.relative_to(ROOT).as_posix()} "
                f"({rc:,} rows, {out_path.stat().st_size / 1024:.1f} KiB)"
            )
            written_rows += int(rc)

        if written_rows != int(total_rows):
            print(
                f"[ERROR] row count mismatch: monolith={total_rows} written={written_rows}",
                file=sys.stderr,
            )
            return 2

        MONOLITH.unlink()
        print(f"[ok] Removed monolith {MONOLITH.relative_to(ROOT).as_posix()}")
    finally:
        con.close()

    # Regenerate manifest so the new partitioned shape is registered.
    from yen_gov.canonical.writer import _regenerate_manifest  # noqa: PLC0415

    manifest_path = _regenerate_manifest(ROOT / "datasets")
    print(f"[ok] Regenerated manifest {manifest_path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
