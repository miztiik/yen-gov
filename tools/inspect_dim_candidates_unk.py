"""Verify the new dim_candidates.parquet has party_short_raw populated.

Reads ``datasets/elections/dim_candidates.parquet`` and reports:
1. Column list (must include ``party_short_raw``).
2. UNK count by ``party_id``.
3. For UNK rows, how many have a non-NULL ``party_short_raw`` (those will
   display the verbatim short in the UI fallback — no "UNK" chip).
4. Top-N distinct ``party_short_raw`` values where ``party_id == parties.IN.UNK``
   (these are the long-tail parties not yet in canonical taxonomy).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import duckdb

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
PARQUET = REPO / "datasets" / "elections" / "dim_candidates.parquet"


def main() -> int:
    if not PARQUET.is_file():
        print(f"NOT FOUND: {PARQUET}", file=sys.stderr)
        return 2
    con = duckdb.connect(":memory:")
    cols = [c[0] for c in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{PARQUET.as_posix()}')"
    ).fetchall()]
    print("columns:", cols)
    assert "party_short_raw" in cols, "MISSING party_short_raw column!"

    total = con.execute(
        f"SELECT count(*) FROM read_parquet('{PARQUET.as_posix()}')"
    ).fetchone()[0]
    print(f"total candidate rows: {total}")

    unk = con.execute(f"""
        SELECT count(*) FROM read_parquet('{PARQUET.as_posix()}')
        WHERE party_id = 'parties.IN.UNK'
    """).fetchone()[0]
    print(f"UNK candidate rows: {unk} ({100 * unk / total:.2f}%)")

    unk_with_raw = con.execute(f"""
        SELECT count(*) FROM read_parquet('{PARQUET.as_posix()}')
        WHERE party_id = 'parties.IN.UNK' AND party_short_raw IS NOT NULL
    """).fetchone()[0]
    print(f"UNK rows with party_short_raw populated (fallback-displayable): {unk_with_raw}")
    unk_without_raw = unk - unk_with_raw
    print(f"UNK rows WITHOUT party_short_raw (truly 'UNK' in UI):            {unk_without_raw}")

    print("\nTop 20 long-tail UNK shorts:")
    rows = con.execute(f"""
        SELECT party_short_raw, count(*) AS n
        FROM read_parquet('{PARQUET.as_posix()}')
        WHERE party_id = 'parties.IN.UNK' AND party_short_raw IS NOT NULL
        GROUP BY party_short_raw
        ORDER BY n DESC
        LIMIT 20
    """).fetchall()
    for short, n in rows:
        print(f"  {short:24s} {n}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
