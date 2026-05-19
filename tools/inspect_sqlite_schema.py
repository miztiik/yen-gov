"""Inspect the schema of a results.sqlite file (one-off for parity oracle work)."""

from __future__ import annotations

import io
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
SQLITE = REPO / "datasets" / "elections" / "AcGenApr2021" / "S22" / "results.sqlite"

con = sqlite3.connect(SQLITE)
con.row_factory = sqlite3.Row
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
print(f"tables in {SQLITE.name}: {tables}\n")
for t in tables:
    cols = [(r[1], r[2]) for r in con.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"  {t}({', '.join(f'{n}:{ty}' for n, ty in cols)})")
    row = con.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
    if row is not None:
        print(f"    sample: {dict(row)}")
    print()
