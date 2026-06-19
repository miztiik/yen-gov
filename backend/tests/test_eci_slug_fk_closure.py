"""Row 0 gate: the ECI->LGD-slug bridge FK-closes against entities/geo.csv.

The CEA + ICED energy adapters key their parsed rows by ECI st_code
(``S22`` / ``U05`` / ``IN``) and translate to the canonical LGD slug
(``tamil-nadu``) at the write boundary via
``yen_gov.canonical.adapters.eci.state_slug.eci_to_lgd_slug``. That slug
is the ``entity_id`` FK target for every faceted ``geo_by_fuel/*.csv`` and
single-value ``geo/*.csv`` row the adapters emit.

This contract test proves the bridge's slug codomain is FK-closed: every
ECI code in the union of ``datasets/taxonomy/lgd_states.json`` and the
ICED ``ENTITY_MAP`` codomain maps (via the shared helper, with ``IN`` the
country passthrough) to an ``entity_id`` that exists in
``datasets/data/entities/geo.csv``. If a future seed edit drops a slug or
renames a state, this row goes red before any adapter can emit an
orphaned FK.

It reads two bounded reference files (``lgd_states.json`` = 36 rows;
``geo.csv`` = bounded entity register) -- NOT the cardinality-scaling
datapoint corpus -- so it does not trip the CLAUDE.md "no pytest walks the
real corpus" anti-pattern (same bounded-canary pattern as
``test_ac_parity_per_state.py``).
"""

from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.adapters.eci.state_slug import _load, eci_to_lgd_slug
from yen_gov.canonical.adapters.iced_common import ENTITY_MAP

REPO_ROOT = Path(__file__).resolve().parents[2]

# The country rollup is not a state in the ECI->slug seed; CEA/ICED national
# rows ("IN") pass through unchanged and FK-close against the geo.csv country
# row directly.
_COUNTRY_PASSTHROUGH = "IN"


def _geo_entity_ids() -> set[str]:
    path = REPO_ROOT / "datasets" / "data" / "entities" / "geo.csv"
    with path.open(encoding="utf-8") as f:
        return {row["entity_id"] for row in csv.DictReader(f)}


def _candidate_eci_codes() -> set[str]:
    """Union of the lgd_states seed keys and the ICED ENTITY_MAP codomain."""
    return set(_load().keys()) | {code for code in ENTITY_MAP.values()}


def test_every_eci_code_maps_to_a_known_geo_entity():
    geo_ids = _geo_entity_ids()
    unmapped: list[str] = []
    orphaned: list[tuple[str, str]] = []

    for code in sorted(_candidate_eci_codes()):
        if code == _COUNTRY_PASSTHROUGH:
            if code not in geo_ids:
                orphaned.append((code, code))
            continue
        try:
            slug = eci_to_lgd_slug(code)
        except KeyError:
            unmapped.append(code)
            continue
        if slug not in geo_ids:
            orphaned.append((code, slug))

    assert unmapped == [], f"ECI codes the bridge cannot map: {unmapped}"
    assert orphaned == [], f"slugs missing from geo.csv: {orphaned}"


def test_country_passthrough_present_in_geo():
    assert _COUNTRY_PASSTHROUGH in _geo_entity_ids()
