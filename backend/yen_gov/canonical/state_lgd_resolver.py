"""state_lgd (LGD numeric state/UT code) -> ECI state code resolver.

The ramSeraph LGD-keyed boundary releases (Subdistricts, Villages,
Districts) carry every feature's parent state in a numeric ``state_lgd``
property (e.g. ``2`` for Himachal Pradesh, ``33`` for Tamil Nadu).
yen-gov's canonical state addressing uses ECI state codes (``S08``,
``S22``, ``U05``, etc.) for Hive partition keys and entity ids; the
mapping between the two lives implicitly in
``datasets/taxonomy/entities.json`` where every current state/UT row
carries both ``entity_code`` (ECI) and ``lgd_code`` (LGD as
zero-padded string).

This module makes the mapping explicit and testable for the boundary
lift orchestrators (Phase B subdistrict national lift, Phase C village
national lift). The orchestrator reads features once, calls
``build_state_lgd_to_eci_map(entities)`` once, and groups by the
integer LGD key with a fast dict lookup.

Pure stdlib. No fetch, no I/O outside the explicit ``Path.open`` in
``load_state_lgd_to_eci_map``.

Why not a DuckDB query against ``entities.parquet``: a one-shot lift
runs once per phase and the entire mapping fits in 36 dict entries —
the JSON loader avoids pulling DuckDB into the orchestrator's import
graph for a 36-row lookup. Tests can build the dict directly without
needing a parquet fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

__all__ = [
    "STATE_LIKE_ENTITY_TYPES",
    "build_state_lgd_to_eci_map",
    "load_state_lgd_to_eci_map",
]


# State + UT rows participate in the LGD-to-ECI mapping. Historical
# states (e.g. composite J&K pre-2019, IN-S09) carry ``entity_valid_to``
# set and are filtered out — their LGD code is overloaded by the
# successor entity (IN-U08 J&K UT post-2019, lgd 01) and the upstream
# LGD-keyed release always carries the CURRENT layout.
STATE_LIKE_ENTITY_TYPES: Final[frozenset[str]] = frozenset({"state", "ut"})


def build_state_lgd_to_eci_map(
    entities: list[dict[str, Any]],
) -> dict[int, str]:
    """Project a parsed ``entities`` list to ``{lgd_int: ECI_code}``.

    Filters to ``entity_type in {"state", "ut"}`` AND
    ``entity_valid_to is None`` (only currently-valid rows). Raises
    ``ValueError`` on duplicate LGD codes (two currently-valid entities
    sharing one LGD value indicates a taxonomy data bug; the lift
    orchestrator would silently misroute features otherwise).

    Args:
        entities: the ``entities`` array from ``entities.json`` (or any
            equivalently-shaped list of dicts with at least
            ``entity_type``, ``entity_valid_to``, ``entity_code``, and
            ``lgd_code`` keys).

    Returns:
        ``{lgd_int: ECI_code}`` — e.g. ``{2: "S08", 33: "S22"}``.
        Rows missing ``lgd_code`` are skipped silently (legitimate
        absence: some entities pre-date LGD adoption).
    """
    mapping: dict[int, str] = {}
    for row in entities:
        if row.get("entity_type") not in STATE_LIKE_ENTITY_TYPES:
            continue
        if row.get("entity_valid_to") is not None:
            continue
        lgd_str = row.get("lgd_code")
        if lgd_str is None:
            continue
        lgd_int = int(lgd_str)
        eci = row["entity_code"]
        if lgd_int in mapping and mapping[lgd_int] != eci:
            raise ValueError(
                f"duplicate state_lgd {lgd_int}: already mapped to "
                f"{mapping[lgd_int]!r}, new claimant {eci!r}. "
                "Two currently-valid entities cannot share one LGD code; "
                "fix entities.json or set entity_valid_to on the historic row."
            )
        mapping[lgd_int] = eci
    return mapping


def load_state_lgd_to_eci_map(entities_path: Path) -> dict[int, str]:
    """Convenience wrapper: read ``entities.json`` then project.

    Equivalent to::

        with entities_path.open(encoding="utf-8") as fh:
            doc = json.load(fh)
        return build_state_lgd_to_eci_map(doc["entities"])
    """
    with entities_path.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    return build_state_lgd_to_eci_map(doc["entities"])
