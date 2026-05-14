"""Pure parser for the ICED GHG energy-full endpoint.

Endpoint: ``GET /climate-environment/ghg-emissions/energy`` (despite
the name, returns the ENTIRE GHG dataset across all sectors with a
sector / subSector / category / subCategory hierarchy). We extract the
sub-sector level (one level deeper than the existing
``india_ghg_emissions_mtco2e_by_sector`` artifact) so analysts can
see, e.g., "Energy/Transport" vs "Energy/Energy Industries" trends.
"""
from __future__ import annotations

from typing import Any

from yen_gov.sources.iced_common import ICEDShapeError, coerce_numeric


def parse_ghg_subsector(decrypted: Any) -> list[dict[str, Any]]:
    """Return canonical rows for the by-subsector indicator.

    Filters:
      * Drop rows where ``subSector == "Total"`` (already covered by the
        parent sector indicator).
      * Drop rows where ``category`` is non-empty and not "Total" — those
        are deeper drill-downs (sub-category granularity is sparse and
        inconsistent across years; we publish only the clean sub-sector
        roll-ups in this artifact).
      * Drop rows with missing/non-numeric emission.

    Facet: ``"{sector}|{subSector}"`` so the renderer can group by parent.
    Time: ``str(year)`` (calendar-year integers — UNFCCC BUR convention).
    """
    if not isinstance(decrypted, dict):
        raise ICEDShapeError(
            f"expected the GHG energy-full endpoint to return a dict, "
            f"got {type(decrypted).__name__}"
        )
    data = decrypted.get("data")
    if not isinstance(data, list):
        raise ICEDShapeError(
            "expected the GHG energy-full endpoint to carry a 'data' list, "
            f"got {type(data).__name__}"
        )

    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in data:
        if not isinstance(raw, dict):
            continue
        sector = (raw.get("sector") or "").strip()
        sub = (raw.get("subSector") or "").strip()
        category = (raw.get("category") or "").strip()
        if not sector or not sub:
            continue
        if sub.lower() == "total":
            continue
        # Keep only the cleanest level: subSector roll-up. A non-empty
        # category that isn't "Total" means this row is a deeper drill
        # (e.g. Fugitive emissions/Oil and natural gas system) — skip.
        if category and category.lower() != "total":
            continue

        year = raw.get("year")
        try:
            year_str = str(int(year))
        except (TypeError, ValueError):
            continue

        emission = coerce_numeric(raw.get("emission"))
        if emission is None:
            continue

        facet = f"{sector}|{sub}"
        key = ("IN", year_str, facet)
        rows[key] = {
            "entity_id": "IN",
            "time": year_str,
            "value": emission,
            "facet": facet,
        }

    return sorted(rows.values(), key=lambda r: (r["entity_id"], r["time"], r["facet"]))
