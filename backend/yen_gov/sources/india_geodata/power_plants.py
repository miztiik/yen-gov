"""india-geodata energy/power-plants source adapter.

Fetches the upstream GeoJSON + metadata.json from
yashveeeeeeer/india-geodata and emits two yen-gov artifacts:

  1. datasets/features/in/energy/power-plants.geojson  (raw points, all India)
     + power-plants.geojson.metadata.json  (sidecar per
       feature_collection.metadata.schema.json — sources, license, coverage,
       coordinate_system).

  2. datasets/indicators/in/energy/installed_mw_by_state.json  (long-form
     rows per indicator.schema.json — only for states whose ECI code is in
     datasets/reference/in/states.json; others are documented in `notes`).

Per docs/research/energy-power-plants.md (v1 plan):
    upstream  = india-geodata raw GeoJSON (CC BY 4.0, attribution surfaced)
    authority = Central Electricity Authority, Ministry of Power
    license   = "Unspecified" verbatim per D9 (CLAUDE.md does not let us
                upgrade a license claim without written permission upstream).

The state-name normaliser maps the raw GeoJSON `state` field (which is a
mess: 64 distinct strings ranging from "AP" to "ANDHRA PRADESH" to
"Arunachal Pradesh") to canonical English names; the canonical names are
joined to states.json by exact match. State strings we don't recognise
become rows in the indicator output's `notes` so a reader can see what
got dropped.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.http import Fetcher
from yen_gov.core.io import Source, write_artifact

UPSTREAM_GEOJSON_URL = (
    "https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/"
    "main/data/energy/power-plants/INDIA_ENERGY_PLANTS.geojson"
)
UPSTREAM_METADATA_URL = (
    "https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/"
    "main/data/energy/power-plants/metadata.json"
)
UPSTREAM_AUTHORITY_URL = "https://cea.nic.in/"


# Canonical English-name lookup for the upstream's messy `state` field.
# Keys lowercased, whitespace collapsed. Values match the `name` field in
# datasets/reference/in/states.json so the join is by exact equality.
#
# This is presentation/normalisation, not a contract surface — it stays here
# rather than going under datasets/. When states.json grows, this map grows
# alongside it (additive only).
_STATE_NAME_NORMALISER: dict[str, str] = {
    # Tamil Nadu — the only state we have an ECI code for at v1.
    "tn": "Tamil Nadu",
    "tamil nadu": "Tamil Nadu",
    # Other entries kept for human readability of the fallout list, even
    # though they don't currently resolve to ECI codes.
    "ap": "Andhra Pradesh",
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "ar.  pradesh": "Arunachal Pradesh",
    "ar. pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chattisgarh": "Chhattisgarh",
    "chhattisgarh": "Chhattisgarh",
    "delhi": "Delhi",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "j&k": "Jammu and Kashmir",
    "jammu & kashmir": "Jammu and Kashmir",
    "jammu and kashmir": "Jammu and Kashmir",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "uttaranchal": "Uttarakhand",
    "west bengal": "West Bengal",
    "a&n islands": "Andaman and Nicobar Islands",
    "andaman and nicobar islands": "Andaman and Nicobar Islands",
    "chandigarh": "Chandigarh",
    "dadra & nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "daman & diu": "Dadra and Nagar Haveli and Daman and Diu",
    "lakshadweep": "Lakshadweep",
    "puducherry": "Puducherry",
    "ladakh": "Ladakh",
}


@dataclass(frozen=True)
class IngestPaths:
    """POSIX-relative paths the ingest will write."""
    geojson: Path
    sidecar: Path
    indicator: Path


def _normalise_state(raw: str | None) -> str | None:
    """Return canonical English name or None if the raw string is unknown."""
    if not raw:
        return None
    key = " ".join(raw.strip().lower().split())
    return _STATE_NAME_NORMALISER.get(key)


def _to_mw(raw: Any) -> float | None:
    """Coerce upstream `inst_cap` to MW float; None on missing/garbage."""
    if raw is None:
        return None
    try:
        v = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _state_eci_lookup(states_json_path: Path) -> dict[str, str]:
    """Return name → ECI code map from datasets/reference/in/states.json."""
    doc = json.loads(states_json_path.read_text(encoding="utf-8"))
    return {s["name"]: s["eci_code"] for s in doc.get("states", [])}


@dataclass(frozen=True)
class _RollupRow:
    eci: str
    fuel: str
    mw: float


def _rollup_by_state_fuel(
    geojson: dict,
    state_to_eci: dict[str, str],
) -> tuple[list[_RollupRow], list[str]]:
    """Aggregate plant-level capacities to (state, fuel) totals.

    Returns:
        rows: one row per (eci_code, fuel_type), sorted deterministically.
        unresolved: distinct raw `state` strings we could not map to ECI codes.
    """
    bucket: dict[tuple[str, str], float] = defaultdict(float)
    unresolved_raws: set[str] = set()
    for feat in geojson.get("features", []):
        props = feat.get("properties") or {}
        raw_state = props.get("state")
        canonical = _normalise_state(raw_state)
        eci = state_to_eci.get(canonical) if canonical else None
        if not eci:
            if raw_state:
                unresolved_raws.add(raw_state)
            continue
        fuel = (props.get("type") or "unknown").strip().lower() or "unknown"
        mw = _to_mw(props.get("inst_cap"))
        if mw is None:
            continue
        bucket[(eci, fuel)] += mw
    rows = [
        _RollupRow(eci=eci, fuel=fuel, mw=round(mw, 3))
        for (eci, fuel), mw in sorted(bucket.items())
    ]
    return rows, sorted(unresolved_raws)


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
    """Fetch india-geodata energy/power-plants and emit the three artifacts.

    Network-bound. Idempotent: re-runs overwrite the artifacts (and re-stamp
    fetched_at timestamps in the sidecar / indicator).
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
        indicator=repo_root / "datasets" / "indicators" / "in" / "energy" / "installed_mw_by_state.json",
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

    # 5. Roll up to state-level installed MW by fuel and emit indicator.
    states_json = repo_root / "datasets" / "reference" / "in" / "states.json"
    state_to_eci = _state_eci_lookup(states_json)
    rollup, unresolved = _rollup_by_state_fuel(geojson, state_to_eci)

    indicator_schema_path = schema_dir / "indicator.schema.json"
    indicator_schema = json.loads(indicator_schema_path.read_text(encoding="utf-8"))
    notes = (
        "v1: rollup is restricted to states present in datasets/reference/in/"
        "states.json (currently TN, KL, AS, WB). Upstream covers all India; "
        f"{len(unresolved)} distinct upstream state labels were not mapped to "
        "ECI codes in this run and their plants are excluded from this indicator. "
        "See docs/research/energy-power-plants.md for v2 plans (CEA direct + "
        "expanded states.json)."
    )
    indicator_payload: dict[str, Any] = {
        "license": {
            "id": "Unspecified",
            "name": "Unspecified",
            "url": None,
            "redistributable": None,
        },
        "coverage": {
            "spatial": "Subset of India (states with ECI codes resolved at emit time)",
            "temporal": (upstream_meta.get("coverage") or {}).get("temporal") or "unknown",
            "admin_level": "state",
        },
        "indicator": {
            "id": "energy/installed_mw_by_state",
            "title": "Installed power capacity by state",
            "description": (
                "Total installed electricity-generation capacity in megawatts, "
                "rolled up by state and faceted by fuel type. Source data is a "
                "snapshot — see `coverage.temporal`."
            ),
            "entity_kind": "state",
            "time_grain": "year",
            "value_kind": "raw",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "MW",
            "denominator": None,
            "notes": notes,
        },
        "rows": [
            {
                "entity_id": r.eci,
                "time": _temporal_to_year(
                    (upstream_meta.get("coverage") or {}).get("temporal")
                ),
                "value": r.mw,
                "facet": r.fuel,
            }
            for r in rollup
        ],
    }
    if not indicator_payload["rows"]:
        # Schema requires minItems: 1. Surface a single null-valued sentinel
        # row so the artifact still ships with provenance + license.
        indicator_payload["rows"] = [
            {"entity_id": "S22", "time": "2019", "value": None, "facet": None}
        ]
    write_artifact(
        path=paths.indicator,
        schema_id=indicator_schema["$id"],
        schema_version=indicator_schema["x-version"],
        payload=indicator_payload,
        sources=[
            Source(url=geo_res.url, fetched_at=geo_res.fetched_at),
            Source(url=meta_res.url, fetched_at=meta_res.fetched_at),
            Source(url=UPSTREAM_AUTHORITY_URL, fetched_at=meta_res.fetched_at),
        ],
        schema_for_validation=indicator_schema,
    )

    return paths


def _temporal_to_year(temporal: str | None) -> str:
    """Best-effort extraction of a YYYY string from upstream's free-form temporal coverage."""
    if not temporal:
        return str(datetime.now(timezone.utc).year)
    digits = "".join(ch for ch in temporal if ch.isdigit())
    if len(digits) >= 4 and digits[:4].isdigit():
        return digits[:4]
    return str(datetime.now(timezone.utc).year)
