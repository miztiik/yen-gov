"""india-geodata energy/power-plants source adapter.

The legacy network-fetch + GeoJSON + sidecar emit path (``ingest`` +
``IngestPaths`` + ``_write_geojson_payload`` + Fetcher import + write_artifact
import) was retired in B4-pt2.3 per parent plan section 21.4 ("network-fetch
code is deleted; ingest reads local TCPD / source CSV"). What remains is
the B1.6.3 canonical CSV emission helpers (``build_csv_variables`` +
``emit_csv_variables``) exercised by
``backend/tests/test_power_plants_csv_repoint.py``.

Per docs/research/energy-power-plants.md (v1 plan):
    upstream  = india-geodata raw GeoJSON (CC BY 4.0, attribution surfaced)
    authority = Central Electricity Authority, Ministry of Power
    license   = "Unspecified" verbatim per D9 (CLAUDE.md does not let us
                upgrade a license claim without written permission upstream).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

# B1.6.3 - canonical CSV citation triple for the india-geodata power-plants
# ingest (sub-plan `TODO/20260604-b1.6-misc-repoint-subplan.md`).
# Producer / title / vintage match the per-family convention declared in
# sub-plan section B1.6.1..7 point 8 (upstream cartographer / dataset
# title / release year). Vintage per ADR-0042 is the publisher edition;
# the sidecar metadata's `coverage.temporal` field declares "2019".
# The fk-validator gate is dark on this hash until `entities/source.csv`
# lands (B2a), by design per sub-plan section "Pre-flight - source-id +
# concept-id readiness". Concept binding is DEFER-to-B2a (concepts.csv
# does not yet ship the installed-capacity-by-fuel concept).
_CSV_PRODUCER = "yashveeeeeeer/india-geodata (CEA-derived)"
_CSV_TITLE = "INDIA_ENERGY_PLANTS"
_CSV_VINTAGE = "2019"
_CSV_NATIONAL_ENTITY_ID = "IN"
_CSV_SNAPSHOT_TIME = 2019
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"

# Upstream `type` token -> kebab-case facet for variable_id suffix.
# variable_id honours parent plan section 21.6 / 21.12 (no `__`) and
# ADR-0044 (no grain prefix; kebab-case `<measure>-<unit>-<facet>`).
# One variable_id per facet until csv_writer supports facet columns
# (sub-plan section B1.6.1..7 point 7).
_FUEL_FACET: dict[str, str] = {
    "coal_power_plant": "coal",
    "hydro_power_plant": "hydro",
    "natural_gas_power_plant": "natural-gas",
    "small_hydro_power_plant": "small-hydro",
    "diesel_power_plant": "diesel",
    "pumped_storage_hydro_power_plant": "pumped-storage-hydro",
}

UPSTREAM_GEOJSON_URL = (
    "https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/"
    "main/data/energy/power-plants/INDIA_ENERGY_PLANTS.geojson"
)
UPSTREAM_METADATA_URL = (
    "https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/"
    "main/data/energy/power-plants/metadata.json"
)
UPSTREAM_AUTHORITY_URL = "https://cea.nic.in/"


def build_csv_variables(
    geojson: dict,
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Aggregate point features to national installed capacity by fuel facet.

    Each fuel `type` maps to one `variable_id`
    `installed-capacity-mw-<facet>`; rows carry the four canonical columns
    declared on file class ``datasets/data/datapoints/geo/*.csv``
    (``entity_id``, ``time``, ``value``, ``source_id``). Features whose
    upstream ``type`` is not in the known fuel-facet map are skipped
    fail-loud-on-shape would over-fit to a Wikipedia-derived upstream
    that occasionally adds new tokens; the legacy GeoJSON path retains
    them verbatim and is the source of truth for the map renderer.
    Per ADR-0044 grain lives on the row's entity_id (``IN`` = national),
    not on the variable_id.
    """
    totals: dict[str, float] = {}
    for feat in geojson.get("features", []):
        props = feat.get("properties") or {}
        fuel_token = props.get("type")
        facet = _FUEL_FACET.get(fuel_token)
        if facet is None:
            continue
        raw_cap = props.get("inst_cap")
        if raw_cap in (None, ""):
            continue
        try:
            cap_mw = float(raw_cap)
        except (TypeError, ValueError):
            continue
        totals[facet] = totals.get(facet, 0.0) + cap_mw
    by_variable: dict[str, list[dict[str, Any]]] = {}
    for facet, total_mw in totals.items():
        variable_id = f"installed-capacity-mw-{facet}"
        by_variable[variable_id] = [{
            "entity_id": _CSV_NATIONAL_ENTITY_ID,
            "time": _CSV_SNAPSHOT_TIME,
            "value": total_mw,
            "source_id": source_id,
        }]
    return by_variable


def emit_csv_variables(
    *, repo_root: Path, by_variable: dict[str, list[dict[str, Any]]]
) -> tuple[Path, ...]:
    """Write each `variable_id` to `datasets/data/datapoints/geo/<id>.csv`."""
    written: list[Path] = []
    out_dir = repo_root / _CSV_OUT_REL_DIR
    for variable_id, rows in sorted(by_variable.items()):
        path = write_csv(
            path=out_dir / f"{variable_id}.csv",
            file_class=_CSV_FILE_CLASS,
            rows=rows,
        )
        written.append(path)
    return tuple(written)
