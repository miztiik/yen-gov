"""Indicators inventory endpoint — read-only listing of every indicator's
folded v3.0 completeness summary.

This wraps ``datasets/reference/in/indicators-completeness.json``, the
static index emitted by ``tools/emit_indicators_completeness_index.py``
and consumed by the citizen-facing ``/data-completeness`` route. The
admin panel re-uses the same on-disk artifact so the operator and the
citizen are always looking at the same numbers; this prevents a class of
"why does my dashboard disagree with the public site" drift.

The endpoint reads the file fresh on every request. The index is small
(~110 rows today, capped at the number of published indicators) so the
cost is negligible and it lets the operator regenerate the index
externally (``python tools/emit_indicators_completeness_index.py --write``)
and immediately see the result without restarting the admin server.

Path convention: every path emitted here is **POSIX-relative to the
repo root** (CLAUDE.md §2) — the underlying index already complies, so
we pass values through untouched.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = REPO_ROOT / "datasets" / "reference" / "in" / "indicators-completeness.json"


@router.get("/inventory/indicators")
def list_indicators() -> dict[str, Any]:
    """Return the indicators-completeness index, enriched with operator
    freshness metadata.

    Response shape::

        {
          "$schema": "...",
          "$schema_version": "...",
          "generated_at": "YYYY-MM-DD",      # from the on-disk index
          "index_mtime": "ISO-8601 UTC",     # filesystem mtime of the index
          "count": <int>,
          "indicators": [<index row>, ...],
        }
    """
    if not INDEX_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "indicators-completeness.json not found; run "
                "`python tools/emit_indicators_completeness_index.py --write`"
            ),
        )

    try:
        doc = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"index parse error: {exc}") from exc

    rows = doc.get("indicators") or []
    return {
        "$schema": doc.get("$schema"),
        "$schema_version": doc.get("$schema_version"),
        "generated_at": doc.get("generated_at"),
        "index_mtime": datetime.fromtimestamp(
            INDEX_PATH.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
        "count": len(rows),
        "indicators": rows,
    }
