"""Pinned (state, year) -> ECI Statistical Report category_id map.

The new ECI portal serves Statistical Reports for 2024+ events through
``/eci-backend/public/api/election-result?category_id=<int>``. The
category_id per (state, year) is harvested through reconnaissance (see
``tools/eci_recon/``) and pinned in **config/eci-pins.json**.

Why a JSON config and not a Python dict? Adding a pin used to require a
code edit; the admin GUI Recon panel (Phase 4) needs to manage the pin
set without touching code. The file is loaded once at import, validated
by the two-tier validator (CLAUDE.md §11) against
``datasets/schemas/eci_pins.schema.json``, and kept in lock-step with the
pipeline through provenance (CLAUDE.md §12).

Per docs/architecture/backend/sources-eci.md (Phase B): we deliberately
do NOT auto-discover category_ids at ingestion time — the pipeline must
be deterministic. Recon is the discovery mechanism; ingestion uses the
pinned ids loaded here. Drift between pin and a fresh recon run is the
early-warning signal.

Two id families exist per (state, year) — Phase A discovered both:

  - "Index Cards" (cleartext per-AC pages, totalResults == #ACs).
  - "Copy of Index Cards [Digital]" (Statistical Report, 14 sectioned
    XLSX/PDF documents). This is the canonical Phase B target.

We pin only the Statistical Report family (``index_name == "Copy of
Index Cards [Digital]"``).
"""

from __future__ import annotations

import json
from pathlib import Path

# config/eci-pins.json sits at <repo>/config/. This file is at
# backend/yen_gov/sources/eci/categories.py — four parents up to repo.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PINS_PATH = _REPO_ROOT / "config" / "eci-pins.json"


def _load_pins() -> dict[tuple[str, int], int]:
    """Read config/eci-pins.json into the (state, year) -> category_id map.

    Returns an empty dict if the file is missing — callers will then hit
    the directive KeyError in :func:`category_id_for`. We deliberately
    do NOT fail-fast at import time so unrelated unit tests (which don't
    touch ECI) can still run when the config file isn't present.
    """
    if not _PINS_PATH.is_file():
        return {}
    payload = json.loads(_PINS_PATH.read_text(encoding="utf-8"))
    out: dict[tuple[str, int], int] = {}
    for entry in payload.get("pins", []):
        out[(entry["state"], int(entry["year"]))] = int(entry["category_id"])
    return out


# Loaded once at import. The admin Recon panel writes the file then calls
# :func:`reload` to pick up changes without restarting uvicorn.
STATISTICAL_REPORT_CATEGORY_ID: dict[tuple[str, int], int] = _load_pins()


def reload() -> dict[tuple[str, int], int]:
    """Re-read the pins file. Used by the admin API after a write."""
    global STATISTICAL_REPORT_CATEGORY_ID
    STATISTICAL_REPORT_CATEGORY_ID = _load_pins()
    return STATISTICAL_REPORT_CATEGORY_ID


def category_id_for(state_code: str, year: int) -> int:
    """Look up the pinned Statistical Report category_id for one (state, year).

    Raises KeyError with a directive message: extending the map is now a
    config edit (config/eci-pins.json) — typically through the admin GUI
    Recon panel after a fresh sweep confirms a new id.
    """
    try:
        return STATISTICAL_REPORT_CATEGORY_ID[(state_code, year)]
    except KeyError as exc:
        raise KeyError(
            f"no pinned ECI Statistical Report category_id for "
            f"({state_code!r}, {year}); add a pin to config/eci-pins.json "
            f"after re-running tools/eci_recon"
        ) from exc
