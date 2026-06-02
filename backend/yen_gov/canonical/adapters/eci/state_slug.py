"""ECI st_code -> LGD-name slug bridge for backend inventory writers.

Per ADR-0050, on-disk artifacts (Hive partitions, inventory entries, etc.)
identify states by their LGD-name slug (e.g. ``tamil-nadu``) rather than the
legacy ECI st_code (``S22``). The internal join-key model in
``dim_acs.parquet`` / ``dim_pcs.parquet`` keeps ECI codes as the relational
identifier — this helper translates ONLY at the write boundary.

The map is loaded once from ``datasets/taxonomy/lgd_states.json`` and cached
for the process lifetime.
"""

from __future__ import annotations

import json
from pathlib import Path

_STATES_PATH = (
    Path(__file__).resolve().parents[5] / "datasets" / "taxonomy" / "lgd_states.json"
)

_CACHE: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _CACHE
    if _CACHE is None:
        doc = json.loads(_STATES_PATH.read_text(encoding="utf-8"))
        _CACHE = {s["eci_st_code"]: s["slug"] for s in doc["states"]}
    return _CACHE


def eci_to_lgd_slug(eci_st_code: str) -> str:
    """Return the LGD-name slug for an ECI st_code (uppercase, e.g. ``S22``).

    Raises ``KeyError`` if the code is unknown — callers should pass a
    validated st_code (S01..S29 / U01..U09) from the canonical states seed.
    """
    return _load()[eci_st_code]
