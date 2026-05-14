"""Run the iced_socio adapter against the live ICED API."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent

from yen_gov.sources.iced_socio import ingest_iced_socio

summary = ingest_iced_socio(repo_root=REPO_ROOT)

print(f"fetched_at: {summary.fetched_at.isoformat()}")
print(f"emitted {len(summary.results)} indicator artifacts:")
for r in summary.results:
    print(
        f"  - {r.indicator_id}",
        f"rows={r.row_count}",
        f"span={r.time_min}..{r.time_max}",
        f"path={r.artifact_path.relative_to(REPO_ROOT).as_posix()}",
    )
