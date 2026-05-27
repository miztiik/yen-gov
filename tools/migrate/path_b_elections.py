"""Path-B elections rename — strip the `state-` grain prefix on 8 indicator_ids
in the canonical `datasets/elections/state=*/election_results.parquet` shards.

Scope: PR-B2 of docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md
(row 32 of the standing reference table). Rewrites the 8 state-scope rollup
indicator_ids in-place across all per-state shards; recomputes
`observation_id` since it is sha256(entity_id|year|period_label|indicator_id).
Idempotent: re-running on already-migrated shards is a no-op.

Why a one-shot script (not a writer migration): the rename is a pure data
op on already-emitted canonical Parquet; no schema change, no adapter logic
change beyond the literal rename in `adapters/eci/rollups.py`. After this
runs the rollups adapter and the on-disk shards agree on the new ids and
future `canonical-backfill-eci` runs UPSERT against the post-rename
observation_ids.

Usage:
  PYTHONPATH=backend python -m tools.migrate.path_b_elections \\
      [--root <repo-root>] [--dry-run]

Per repo policy: relative paths only in any emitted artifact; this script
edits binary parquet via DuckDB CTAS to a sibling temp path + os.replace.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb


RENAMES: dict[str, str] = {
    "state-electors-total": "electors-total",
    "state-votes-polled": "votes-polled",
    "state-turnout-pct": "turnout-pct",
    "state-nota-pct": "nota-pct",
    "state-effective-parties-laakso": "effective-parties-laakso",
    "state-winning-party-id": "winning-party-id",
    "state-winning-party-seats": "winning-party-seats",
    "state-majority-threshold-acs": "majority-threshold-acs",
}


def _build_case_expr(column: str, mapping: dict[str, str]) -> str:
    parts = ["CASE " + column]
    for old, new in mapping.items():
        parts.append(f"WHEN '{old}' THEN '{new}'")
    parts.append(f"ELSE {column} END")
    return " ".join(parts)


def migrate_shard(shard: Path, *, dry_run: bool) -> tuple[int, int]:
    """Rewrite indicator_id + observation_id in `shard`. Returns (rows, renames)."""
    con = duckdb.connect()
    try:
        total = con.execute(
            "SELECT count(*) FROM read_parquet(?)",
            [shard.as_posix()],
        ).fetchone()[0]
        affected = con.execute(
            f"SELECT count(*) FROM read_parquet(?) WHERE indicator_id IN ({','.join('?' * len(RENAMES))})",
            [shard.as_posix(), *RENAMES.keys()],
        ).fetchone()[0]
        if affected == 0:
            return total, 0

        new_indicator = _build_case_expr("indicator_id", RENAMES)
        # observation_id = sha256(entity_id|year|period_label|<new_indicator_id>)
        new_obs_id = (
            "lower(hex(sha256("
            "concat(entity_id, '|', cast(year as VARCHAR), '|', "
            f"period_label, '|', {new_indicator}))))"
        )

        if dry_run:
            print(f"  DRY-RUN would rewrite {affected}/{total} rows in {shard.as_posix()}")
            return total, affected

        tmp = shard.with_suffix(".parquet.tmp")
        # Preserve column order from the existing schema.
        con.execute(
            f"""
            COPY (
                SELECT
                    {new_obs_id} AS observation_id,
                    entity_id, year, period_label, period_seq,
                    {new_indicator} AS indicator_id,
                    value_numeric, value_text, source_id, derivation, state
                FROM read_parquet(?)
            )
            TO '{tmp.as_posix()}' (FORMAT PARQUET)
            """,
            [shard.as_posix()],
        )
        os.replace(tmp, shard)
        return total, affected
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repo root (default: cwd)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    elections = root / "datasets" / "elections"
    shards = sorted(elections.glob("state=*/election_results.parquet"))
    if not shards:
        print(f"No shards under {elections.as_posix()}", file=sys.stderr)
        return 1

    print(f"Path-B elections rename — {len(shards)} shards, {len(RENAMES)} renames"
          + (" [DRY-RUN]" if args.dry_run else ""))
    total_rows = 0
    total_affected = 0
    for shard in shards:
        rel = shard.relative_to(root).as_posix()
        rows, affected = migrate_shard(shard, dry_run=args.dry_run)
        total_rows += rows
        total_affected += affected
        status = "UNCHANGED" if affected == 0 else f"{affected:>6}/{rows} renamed"
        print(f"  {status:>20}  {rel}")

    print(f"\nTotal: {total_affected}/{total_rows} rows renamed across {len(shards)} shards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
