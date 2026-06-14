"""Indicators inventory endpoint — read-only listing of every indicator's
folded v3.0 completeness summary.

This primarily wraps ``datasets/_ops/indicators-completeness.json``, the
static index emitted by ``tools/emit_indicators_completeness_index.py``.
During the canonical long-CSV migration that legacy folded-indicator
artifact tree can be empty; in that case the endpoint falls back to the
canonical ``datasets/taxonomy/indicators.json`` catalogue so the operator
panel still lists the indicator registry instead of rendering an empty
table.

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
INDEX_PATH = REPO_ROOT / "datasets" / "_ops" / "indicators-completeness.json"
CATALOGUE_PATH = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"


def _catalogue_fallback_rows() -> list[dict[str, Any]]:
    if not CATALOGUE_PATH.exists():
        return []
    try:
        doc = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    rows: list[dict[str, Any]] = []
    for row in doc.get("indicators") or []:
        if not isinstance(row, dict):
            continue
        indicator_id = row.get("indicator_id")
        if not isinstance(indicator_id, str) or not indicator_id:
            continue
        family = row.get("family")
        topic = family if isinstance(family, str) and family else "catalogue"
        label = row.get("label_long") or row.get("label_short") or indicator_id
        rows.append(
            {
                "id": indicator_id,
                "topic": topic,
                "path": CATALOGUE_PATH.relative_to(REPO_ROOT).as_posix(),
                "title": label,
                "documentation_status": "authored",
                "inventory_status": "empty",
                "frozen": False,
                "last_polled_at": None,
                "observed_count": 0,
                "pending_count": 0,
                "unavailable_count": 0,
            }
        )
    return sorted(rows, key=lambda r: (r["topic"], r["id"]))


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
    if not rows:
        rows = _catalogue_fallback_rows()
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
