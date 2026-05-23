"""Quick inventory of canonical energy fact-tables — for the re-acquisition plan."""
from __future__ import annotations
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "datasets/energy/energy_installed_capacity.parquet",
    "datasets/energy/energy_generation.parquet",
    "datasets/energy/energy_demand_supply.parquet",
    "datasets/energy/energy_distribution_performance.parquet",
]


def main() -> None:
    con = duckdb.connect()
    for rel in FILES:
        path = ROOT / rel
        if not path.exists():
            print(f"MISSING {rel}")
            continue
        print(f"\n=== {rel} ===")
        rows = con.execute(
            "SELECT indicator_id, COUNT(*) AS n, MIN(period_label) AS p_min, "
            "MAX(period_label) AS p_max, COUNT(DISTINCT entity_id) AS n_e "
            f"FROM read_parquet('{path.as_posix()}') GROUP BY indicator_id "
            "ORDER BY indicator_id"
        ).fetchall()
        for r in rows:
            print(f"  {r[0]:55s}  rows={r[1]:5d}  entities={r[4]:3d}  range={r[2]}..{r[3]}")


if __name__ == "__main__":
    main()
