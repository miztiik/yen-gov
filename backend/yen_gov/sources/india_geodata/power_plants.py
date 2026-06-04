"""india-geodata energy/power-plants source adapter.

Fetches the upstream GeoJSON + metadata.json from
yashveeeeeeer/india-geodata and emits one yen-gov artifact pair:

  datasets/features/in/energy/power-plants.geojson  (raw points, all India)
  + power-plants.geojson.metadata.json  (sidecar per
    feature_collection.metadata.schema.json — sources, license, coverage,
    coordinate_system).

Consumer: the frontend energy-hub map. This module is the sole writer for
both files; provenance lives in the sidecar.

Per docs/research/energy-power-plants.md (v1 plan):
    upstream  = india-geodata raw GeoJSON (CC BY 4.0, attribution surfaced)
    authority = Central Electricity Authority, Ministry of Power
    license   = "Unspecified" verbatim per D9 (CLAUDE.md does not let us
                upgrade a license claim without written permission upstream).

History: this adapter also emitted a derived indicator artifact
``datasets/indicators/in/energy/installed_mw_by_state.json`` (state-level
rollup of installed MW by fuel, restricted to the TN/KL/AS/WB subset
where ECI codes resolved). Retired in PR-A of the energy-residue triage
(2026-05-25) — the indicator was widely cited as a *cautionary tale* in
the indicators system (Wikipedia-derived, 4-state-only subset, ECI-code
gated) but never grew beyond that subset; the canonical
``energy/state_installed_capacity_by_source_mw`` series (ICED, 36 states,
FY16-FY26) is the right successor. The state-name normaliser + the
ECI-lookup helper that supported the rollup were removed alongside the
indicator emission.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.core.http import Fetcher
from yen_gov.core.io import Source, write_artifact

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


@dataclass(frozen=True)
class IngestPaths:
    """POSIX-relative paths the ingest will write."""
    geojson: Path
    sidecar: Path


def _write_geojson_payload(path: Path, geojson: dict) -> None:
    """Write the raw GeoJSON FeatureCollection verbatim.

    GeoJSON has no $schema/$schema_version stamping — it's an RFC 7946 file,
    not a yen-gov schema artifact. Provenance lives in the sibling
    `<file>.metadata.json` sidecar (see write_artifact below).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(geojson, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def ingest(
    *,
    fetcher: Fetcher,
    repo_root: Path,
    schema_dir: Path,
) -> IngestPaths:
    """Fetch india-geodata energy/power-plants and emit geojson + sidecar.

    Network-bound. Idempotent: re-runs overwrite the artifacts (and re-stamp
    fetched_at timestamps in the sidecar).
    """

    # 1. Fetch upstream GeoJSON + metadata.
    geo_res = fetcher.fetch(UPSTREAM_GEOJSON_URL)
    meta_res = fetcher.fetch(UPSTREAM_METADATA_URL)
    geojson = json.loads(geo_res.content)
    upstream_meta = json.loads(meta_res.content)

    # 2. Plan paths.
    paths = IngestPaths(
        geojson=repo_root / "datasets" / "features" / "in" / "energy" / "power-plants.geojson",
        sidecar=repo_root / "datasets" / "features" / "in" / "energy" / "power-plants.geojson.metadata.json",
    )

    # 3. Write the GeoJSON verbatim.
    _write_geojson_payload(paths.geojson, geojson)

    # 4. Build the metadata sidecar.
    sidecar_schema_path = schema_dir / "feature_collection.metadata.schema.json"
    sidecar_schema = json.loads(sidecar_schema_path.read_text(encoding="utf-8"))
    sidecar_payload: dict[str, Any] = {
        "for": "power-plants.geojson",
        "title": upstream_meta.get("title") or "Power Plants",
        "description": upstream_meta.get("description") or "",
        "category": upstream_meta.get("category") or "energy",
        "license": {
            "id": "Unspecified",
            "name": upstream_meta.get("license", {}).get("name") or "Unspecified",
            "url": upstream_meta.get("license", {}).get("url"),
            # Unknown license: bundling allowed but flagged in UI per D9.
            "redistributable": None,
        },
        "coverage": {
            "spatial": (upstream_meta.get("coverage") or {}).get("spatial") or "India (national)",
            "temporal": (upstream_meta.get("coverage") or {}).get("temporal") or "unknown",
            "admin_level": (upstream_meta.get("coverage") or {}).get("admin_level"),
        },
        "coordinate_system": upstream_meta.get("coordinate_system") or "EPSG:4326",
    }
    write_artifact(
        path=paths.sidecar,
        schema_id=sidecar_schema["$id"],
        schema_version=sidecar_schema["x-version"],
        payload=sidecar_payload,
        sources=[
            Source(url=geo_res.url, fetched_at=geo_res.fetched_at),
            Source(url=meta_res.url, fetched_at=meta_res.fetched_at),
            Source(url=UPSTREAM_AUTHORITY_URL, fetched_at=meta_res.fetched_at),
        ],
        schema_for_validation=sidecar_schema,
    )

    # 5. B1.6.3 - canonical long-format CSV emission ALONGSIDE the
    # legacy GeoJSON + sidecar write. Existing GeoJSON output stays in
    # place; instead-of deletion is deferred to B3 per parent plan
    # section 23.1 and sub-plan section B1.6.1..7 point 6.
    csv_source_id = derive_source_id(_CSV_PRODUCER, _CSV_TITLE, _CSV_VINTAGE)
    by_variable = build_csv_variables(geojson, source_id=csv_source_id)
    emit_csv_variables(repo_root=repo_root, by_variable=by_variable)

    return paths


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
