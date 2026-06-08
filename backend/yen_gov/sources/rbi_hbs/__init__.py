"""Shared building blocks for RBI Handbook of Statistics ingest scripts.

This package factors out the *low-level primitives* that the legacy RBI
HBS ingest scripts under ``tools/`` previously duplicated verbatim. Those
scripts (``tools/rbi_hbs_ingest_*.py``) were retired in the G6 tools/
prune 2026-06-08 alongside the broader fetch-code rip per plan section
21.4. The primitives below are still consumed by the in-repo backend
adapter ``backend/yen_gov/sources/rbi_hbs_ie_state_sdp/ingest.py``:

- the state-name → ECI-code map (``name_map``),
- the cell-value coercion + year-label parsing helpers (``parsers``),
- the Handbook landing-page URLs, RBI license block, UTF-8 stdout shim, and a thin
  artifact-write helper (``emit``).

It deliberately does NOT abstract the per-table-shape parsers (state-as-row × FY-as-col,
multi-base time series, peak-paired sub-columns, etc.) — those varied enough between RBI
publications and section pages that a single "universal walker" would need a flag for
every quirk. Each historical ingest tool kept its own walker against its own SPECS table;
the duplication that mattered (~80 lines × 3 files) lived at the primitive layer, and that
is what this package owns.

Two RBI publications are in scope today:

- **HBS-IE** — *Handbook of Statistics on Indian Economy* (national time series,
  state SDP, prices/inflation indices). Imported by the backend
  ``rbi_hbs_ie_state_sdp`` adapter.
- **HBS-IS** — *Handbook of Statistics on Indian States* (per-state series:
  power, vital stats, state pension expenditure). The dedicated tools/ ingest
  scripts were retired in G6; future re-ingest paths land under
  ``backend/yen_gov/sources/`` per the platform-reset plan.

Use ``HBS_IE_LANDING`` / ``HBS_IS_LANDING`` to populate ``sources[].url`` correctly
per publication; pass the publication-specific snapshot URL alongside.
"""
from .name_map import ALL_INDIA_NAMES, NAME_TO_ECI
from .parsers import coerce_value, cy_label_to_time, fy_label_to_time, year_label_to_time
from .emit import HBS_IE_LANDING, HBS_IS_LANDING, LICENSE_RBI, setup_utf8_stdout, write_artifact

__all__ = [
    "ALL_INDIA_NAMES",
    "NAME_TO_ECI",
    "coerce_value",
    "cy_label_to_time",
    "fy_label_to_time",
    "year_label_to_time",
    "HBS_IE_LANDING",
    "HBS_IS_LANDING",
    "LICENSE_RBI",
    "setup_utf8_stdout",
    "write_artifact",
]
