"""Pinned (state, year) -> ECI Statistical Report category_id map.

The new ECI portal serves Statistical Reports for 2024+ events through
`/eci-backend/public/api/election-result?category_id=<int>`. The category_id
per (state, year) is harvested manually from Phase A reconnaissance
(see notes/eci-recon-2026-05-09.md and tools/eci_recon/recon.py) and pinned
here. Extending the map requires a code change with the upstream URL the
value was confirmed against.

Per docs/architecture/backend/sources-eci.md (Phase B): we deliberately do
NOT auto-discover category_ids at ingestion time — the pipeline must be
deterministic. Recon is the discovery mechanism; ingestion uses pinned ids.
A drift between the pinned id and the next recon run is the early-warning
signal.

Two id families exist per (state, year) — Phase A discovered both:

  - "Index Cards" (cleartext per-AC pages, totalResults == #ACs).
  - "Copy of Index Cards [Digital]" (Statistical Report, 14 sectioned
    XLSX/PDF documents). This is the canonical Phase B target.

We pin only the Statistical Report family. Confirmed 2026-05-09 against
https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=<id>
(`cat_name` and `index_name == "Copy of Index Cards [Digital]"`).
"""

from __future__ import annotations

# Keys are (state_code, year) pairs. Values are the int category_id ECI
# expects on the cleartext /api/election-result query string.
STATISTICAL_REPORT_CATEGORY_ID: dict[tuple[str, int], int] = {
    ("S03", 2026): 23,  # Assam — confirmed via /api/election-result?category_id=23
    ("S11", 2026): 24,  # Kerala — confirmed via /api/election-result?category_id=24
    ("S22", 2026): 26,  # Tamil Nadu — confirmed via /api/election-result?category_id=26
    ("S25", 2026): 27,  # West Bengal — confirmed via /api/election-result?category_id=27
}


def category_id_for(state_code: str, year: int) -> int:
    """Look up the pinned Statistical Report category_id for one (state, year).

    Raises KeyError with a directive message: extending the map is a code
    change, not a config edit (see module docstring).
    """
    try:
        return STATISTICAL_REPORT_CATEGORY_ID[(state_code, year)]
    except KeyError as exc:
        raise KeyError(
            f"no pinned ECI Statistical Report category_id for "
            f"({state_code!r}, {year}); extend "
            f"STATISTICAL_REPORT_CATEGORY_ID after re-running tools/eci_recon"
        ) from exc
