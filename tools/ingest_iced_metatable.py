"""Operator entry — `python tools/ingest_iced_metatable.py`.

Fetches the three ICED v1 ``*-metatable-data`` endpoints (gen, plf,
co-emission) and writes the corresponding state-scope indicator artifacts.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_metatable import ingest_iced_metatable  # noqa: E402


def main() -> None:
    summary = ingest_iced_metatable(repo_root=REPO_ROOT)
    print(f"ingest finished at {summary.fetched_at.isoformat()}")
    for r in summary.results:
        rel = r.artifact_path.relative_to(REPO_ROOT).as_posix()
        skip = f"  (skipped {r.skipped_unmapped} unmapped)" if r.skipped_unmapped else ""
        print(f"  {r.indicator_id:70s}  {r.row_count:>5d} rows  "
              f"{r.time_min}..{r.time_max}  -> {rel}{skip}")


if __name__ == "__main__":
    main()
