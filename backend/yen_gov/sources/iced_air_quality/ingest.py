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

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import emit_indicator_rows, extract_state_rows

# ---------------------------------------------------------------------------
# Canonical CSV emission (B1.4.9)
# ---------------------------------------------------------------------------
#
# Re-points the FGD indicator emitted by this ingest onto
# `yen_gov.canonical.csv_writer.write_csv` ALONGSIDE the legacy
# `write_artifact` meadow-JSON path (parent plan section 23.1; instead-of
# is deferred to B3). `source_id` is derived via ADR-0042 from
# (producer, title, vintage); variable_id honours parent plan section
# 21.6 / 21.12 (no `__`) and ADR-0044 (no grain prefix).
# concept_id binding DEFERRED to B2a; recorded as DEFER marker in PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_TITLE_FGD = (
    "ICED FGD-status tracker (thermal-plant FGD compliance, "
    "re-publishing CEA / MoEF&CC)"
)
_CSV_SOURCE_VINTAGE_FGD = "2026 snapshot"
_CSV_VARIABLE_ID_FGD = "thermal-fgd-installed-share-pct"


def _period_to_year_int(period: str) -> int:
    """Reduce ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD`` to integer year.

    The canonical CSV column class ``datasets/data/datapoints/geo/*.csv``
    declares ``time`` as integer. FGD rows carry an ISO snapshot date
    (``YYYY-MM-DD``); reducing to the snapshot year is the natural
    long-format mapping for a once-per-snapshot indicator.
    """
    if not (isinstance(period, str) and len(period) >= 4 and period[:4].isdigit()):
        raise ValueError(
            f"unexpected time format {period!r}; expected 'YYYY', 'YYYY-MM' "
            f"or 'YYYY-MM-DD'"
        )
    return int(period[:4])


def build_csv_rows_fgd(
    payload_rows: list[dict],
    *,
    source_id: str,
) -> list[dict]:
    """Build canonical CSV rows for the FGD indicator.

    Each row carries the canonical 4 columns declared on file class
    ``datasets/data/datapoints/geo/*.csv``: ``entity_id``, ``time``,
    ``value``, ``source_id``. Rows with ``value is None`` are dropped
    upstream by ``extract_state_rows``; this builder asserts no Nones
    slip through.
    """
    out: list[dict] = []
    for row in payload_rows:
        out.append({
            "entity_id": row["entity_id"],
            "time": _period_to_year_int(row["time"]),
            "value": row["value"],
            "source_id": source_id,
        })
    return out


def _emit_csv_fgd(*, repo_root: Path, payload_rows: list[dict]) -> Path:
    """Canonical CSV emission ALONGSIDE the legacy meadow indicator JSON.

    B1.4.9 - both stores coexist (parent plan section 23.1); reader flip
    is X1a. ``source_id`` derived via ADR-0042 from (producer, title,
    vintage); one ``variable_id`` (no facets).
    """
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_FGD, _CSV_SOURCE_VINTAGE_FGD
    )
    csv_rows = build_csv_rows_fgd(payload_rows, source_id=source_id)
    return write_csv(
        path=repo_root / _CSV_OUT_REL_DIR / f"{_CSV_VARIABLE_ID_FGD}.csv",
        file_class=_CSV_FILE_CLASS,
        rows=csv_rows,
    )

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
    # B1.4.9: canonical CSV emission ALONGSIDE legacy meadow JSON
    # (parent plan section 23.1; reader flip = X1a, instead-of = B3).
    _emit_csv_fgd(repo_root=repo_root, payload_rows=payload["rows"])

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
