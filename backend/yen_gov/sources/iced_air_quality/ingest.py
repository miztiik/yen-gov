"""Fetch, parse, and write the FGD-installed-share artifact.

Network boundary: :class:`yen_gov.sources.iced_common.IcedClient` (which
handles AES-256-CBC decryption and on-disk caching of the raw encrypted
body under ``.runtime/raw/iced/``). This module composes the client
with the pure parser and writes the schema-stamped indicator artifact.

Run via :mod:`yen_gov.cli` or the admin pipeline panel; the standalone
entry point is :func:`ingest_fgd`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import emit_indicator_rows, extract_state_rows

# Endpoint catalogue name (see iced_common.endpoints.aq_fgd).
FGD_API_PATH = "/climate-environment/environment/air-quality/fgd"
FGD_API_URL = f"https://icedapi.niti.gov.in{FGD_API_PATH}"

# Public ICED dashboard page that surfaces this data — useful as the
# human-readable landing reference, but NOT the data URL.
FGD_DASHBOARD_URL = (
    "https://iced.niti.gov.in/climate-and-environment/environment/air-quality"
)

# Upstream policy URL — the December 2015 MoEF&CC notification that
# created the FGD-compliance obligation in the first place. Listed in
# the artifact's `sources` array per the dual-provenance rule (Hans
# 2026-05-15, docs/architecture/backend/sources-iced-api.md): ICED is
# the re-publisher; MoEF&CC owns the directive.
MOEFCC_NOTIFICATION_URL = (
    "https://moef.gov.in/wp-content/uploads/2018/04/"
    "Final-Notification-7-12-2015.pdf"
)

INDICATOR_ID = "environment/state_thermal_fgd_installed_share_pct"
INDICATOR_TITLE = "Thermal-plant FGD compliance (share of state capacity)"

# Citizen-facing description. Kept short — the chart's source card
# expands on caveats from `notes`.
INDICATOR_DESCRIPTION = (
    "Share of each state's coal thermal-plant capacity (MW) that has "
    "actually installed flue-gas desulphurisation (FGD) equipment, "
    "against the MoEF&CC's December-2015 directive. Numerator: capacity "
    "(MW) of plant-units whose FGD status is recorded as 'installed'. "
    "Denominator: total capacity of all plant-units in the tracker."
)

INDICATOR_NOTES = (
    "Snapshot. The MoEF&CC's December 2015 notification mandated FGD "
    "installation at coal/lignite thermal plants by 2017; the deadline "
    "has been extended repeatedly (currently 2027 for many categories). "
    "States not appearing in this map have no major coal thermal "
    "capacity in the CEA tracker. ICED is a re-publisher of the CEA "
    "tracker; the underlying status list is maintained by CEA against "
    "the MoEF&CC notification — both URLs appear in `sources`."
)


@dataclass(frozen=True)
class FGDIngestResult:
    """One-line result summary for the CLI / admin pipeline panel."""

    indicator_id: str
    artifact_path: Path
    state_count: int
    plant_unit_count_total: int
    plant_unit_count_installed: int
    capacity_total_mw: float
    capacity_installed_mw: float
    fetched_at: datetime


def ingest_fgd(
    *,
    repo_root: Path,
    schema_dir: Path | None = None,
    refresh: bool = False,
) -> FGDIngestResult:
    """Fetch (or load cached) FGD response, aggregate, write artifact.

    Args:
        repo_root: workspace root; ``datasets/indicators/in/environment/``
            sits under this.
        schema_dir: override the schema_registry's default location.
            Pass ``repo_root / "datasets" / "schemas"`` from CLI; tests
            can pass a fixture dir.
        refresh: if True, bypass the on-disk cache and re-fetch.
    """
    runtime_root = repo_root / ".runtime"
    client = IcedClient(host="https://icedapi.niti.gov.in", runtime_root=runtime_root)
    response = client.get(FGD_API_PATH)
    fetched_at = response.fetched_at

    parsed = extract_state_rows(response.decrypted)
    if not parsed:
        from yen_gov.sources.iced_common import ICEDShapeError
        raise ICEDShapeError(
            "FGD parser returned zero state rows — refusing to ship empty artifact."
        )

    snapshot_date = fetched_at.astimezone(timezone.utc).date().isoformat()
    payload = _build_payload(
        parsed=parsed,
        snapshot_date=snapshot_date,
        fetched_at=fetched_at,
    )

    indicator_schema = schema_doc("indicator.schema.json")
    out_path = (
        repo_root
        / "datasets"
        / "indicators"
        / "in"
        / "environment"
        / "state_thermal_fgd_installed_share_pct.json"
    )
    write_artifact(
        path=out_path,
        schema_id=schema_id("indicator.schema.json"),
        schema_version=schema_version("indicator.schema.json"),
        payload=payload,
        sources=[
            Source(url=FGD_API_URL, fetched_at=fetched_at),
            Source(url=MOEFCC_NOTIFICATION_URL, fetched_at=fetched_at),
        ],
        schema_for_validation=indicator_schema,
    )

    return FGDIngestResult(
        indicator_id=INDICATOR_ID,
        artifact_path=out_path,
        state_count=len(parsed),
        plant_unit_count_total=sum(r.units_total for r in parsed),
        plant_unit_count_installed=sum(r.units_installed for r in parsed),
        capacity_total_mw=sum(r.capacity_total_mw for r in parsed),
        capacity_installed_mw=sum(r.capacity_installed_mw for r in parsed),
        fetched_at=fetched_at,
    )


def _build_payload(
    *,
    parsed: list,
    snapshot_date: str,
    fetched_at: datetime,
) -> dict:
    """Compose the schema-required payload (everything except $schema/sources)."""
    rows = [{**r, "time": snapshot_date} for r in emit_indicator_rows(parsed)]

    return {
        "license": {
            "id": "GoI-Open",
            "name": (
                "Government of India open publication "
                "(NITI Aayog ICED, re-publishing CEA / MoEF&CC tracker)"
            ),
            "url": "https://data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": (
                f"{len(parsed)} states with coal thermal capacity in the "
                "CEA FGD tracker"
            ),
            "temporal": f"snapshot {snapshot_date}",
            "admin_level": "state",
        },
        "indicator": {
            "id": INDICATOR_ID,
            "title": INDICATOR_TITLE,
            "description": INDICATOR_DESCRIPTION,
            "entity_kind": "state",
            "time_grain": "date",
            "value_kind": "share",
            "direction": "higher_is_better",
            "scale_hint": "linear",
            "unit": "%",
            "icon": "factory",
            "notes": INDICATOR_NOTES,
            "attribution_geography": "where_produced",
            "comparability": "comparable_with_normalisation",
            "implementing_authority": "joint",
            "methodology_vintage": (
                "ICED FGD-status tracker (re-publishing CEA's plant-unit "
                f"status list); snapshot {snapshot_date}; numerator = "
                "capacity (MW) of plant-units with fgdStatus == "
                "'FGD installed'; denominator = total capacity (MW) of "
                "all plant-units in the response."
            ),
            "chart_type": "choropleth",
        },
        "rows": rows,
    }
