"""Operator entry-point: ingest the ICED v0 fuel + power-purchase endpoints."""
from __future__ import annotations

import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_fuel import ingest_iced_fuel  # noqa: E402


def main() -> None:
    summary = ingest_iced_fuel(repo_root=REPO_ROOT)
    print(f"\nfetched_at: {summary.fetched_at.isoformat()}\n")
    print(f"{'indicator':<60s}  {'rows':>6s}  {'time_min':>9s}  {'time_max':>9s}  {'unmapped':>8s}")
    print("-" * 100)
    for r in summary.results:
        print(f"{r.indicator_id:<60s}  {r.row_count:>6d}  {r.time_min:>9s}  {r.time_max:>9s}  {r.skipped_unmapped:>8d}")


if __name__ == "__main__":
    main()
