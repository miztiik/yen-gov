"""Operator entry point — run the ICED power-sector ingest end-to-end.

Run from repo root::

    python tools/ingest_iced_power.py

Fetches every endpoint, writes five new indicator artifacts under
``datasets/indicators/in/energy/``, prints a one-line summary per
artifact (path, row count, temporal span).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_power import ingest_iced_power  # noqa: E402


def main() -> None:
    summary = ingest_iced_power(repo_root=REPO_ROOT)
    print(f"ingest finished at {summary.fetched_at.isoformat()}")
    for r in summary.results:
        rel = r.artifact_path.relative_to(REPO_ROOT).as_posix()
        print(
            f"  {r.indicator_id:60s}  "
            f"{r.row_count:>5d} rows  {r.time_min}..{r.time_max}  -> {rel}"
        )


if __name__ == "__main__":
    main()
