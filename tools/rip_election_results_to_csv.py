"""One-shot transcode: datasets/elections/state=<slug>/election_results.parquet
-> datasets/data/datapoints/electoral/<slug>_election_results.csv.

Per X1a-fu2-D rip-and-replace (user directive 2026-06-07): mechanical
9-column SELECT. Drops observation_id (content-hash, unused by readers)
and the Hive partition `state` column (already encoded in filename).

Output columns (mirrors the 9 the user named in the brief):
  entity_id, year, period_label, period_seq, indicator_id,
  value_numeric, value_text, source_id, derivation
"""

from __future__ import annotations

import pathlib
import duckdb


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    src_glob = "datasets/elections/state=*/election_results.parquet"
    out_dir = repo_root / "datasets" / "data" / "datapoints" / "electoral"
    out_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")
    parquets = sorted((repo_root).glob(src_glob))
    if not parquets:
        raise SystemExit(f"no parquets matched {src_glob} under {repo_root}")

    total_rows = 0
    for parquet in parquets:
        state_slug = parquet.parent.name.removeprefix("state=")
        out_csv = out_dir / f"{state_slug}_election_results.csv"
        sql = (
            "COPY (SELECT entity_id, year, period_label, period_seq, "
            "indicator_id, value_numeric, value_text, source_id, derivation "
            f"FROM read_parquet('{parquet.as_posix()}') "
            "ORDER BY entity_id, period_seq, indicator_id) "
            f"TO '{out_csv.as_posix()}' (HEADER, DELIMITER ',')"
        )
        con.execute(sql)
        n = con.execute(
            f"SELECT COUNT(*) FROM read_csv('{out_csv.as_posix()}', AUTO_DETECT=TRUE)"
        ).fetchone()[0]
        total_rows += n
        rel_in = parquet.relative_to(repo_root).as_posix()
        rel_out = out_csv.relative_to(repo_root).as_posix()
        print(f"  {rel_in} -> {rel_out}  ({n} rows)")

    print(f"\nemitted {len(parquets)} CSVs ({total_rows} rows total) under "
          f"{out_dir.relative_to(repo_root).as_posix()}/")


if __name__ == "__main__":
    main()
