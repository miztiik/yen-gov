"""Fetch + meadow-emit helper for the ICED ``plantPipelineInfo`` endpoint.

Layers 1 (fetch) + 2 (parse-to-meadow) of the four-layer ingest doctrine
([docs/concepts/ingest-fetch-enrich-separation.md]). Pulls one decrypted
snapshot of ``/v1/plantPipelineInfo`` and persists it under
``datasets/energy/_meadow/iced/<vintage>/plant_pipeline_info.json``
([ADR-0041](../../../../docs/architecture/decisions/0041-meadow-tier.md)),
where ``<vintage>`` is the upstream ``Last-Modified`` date (per the
CLAUDE.md anti-pattern that bars ``datetime.now()`` in data-row content).

The meadow file is schema-compliant per
``datasets/schemas/indicator.schema.json`` v6.0: ``$schema`` +
``$schema_version`` + ``sources[]`` + ``license`` + ``coverage`` +
``indicator{...}`` + ``rows[{entity_id, time, value, facet}]``. The rows
are produced by the pure parser
:func:`yen_gov.sources.iced_power.parsers.parse_plant_pipeline_info`
(layer 2). The enrich + emit pass (layer 3 + 4) lives in
``backend/yen_gov/canonical/adapters/energy/capacity_pipeline.py``.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from yen_gov.sources.iced_common.client import API_HOST_DEFAULT, IcedClient
from yen_gov.sources.iced_power.parsers import parse_plant_pipeline_info


API_PATH = "/plantPipelineInfo"


def _build_meadow_payload(
    *,
    rows: list[dict[str, Any]],
    fetched_at_iso: str,
) -> dict[str, Any]:
    """Wrap parsed rows into the meadow-tier indicator.schema v6.0 shape."""
    times = sorted({r["time"] for r in rows}) if rows else []
    temporal = f"{times[0]}..{times[-1]}" if times else ""
    description = (
        "ICED plantPipelineInfo: national under-construction generation "
        "capacity by expected commissioning calendar-year and status "
        "(likely-to-be-commissioned vs on-hold). Values are GW per year "
        "(not cumulative). Publisher 2022 gap preserved verbatim."
    )
    return {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "6.0",
        "sources": [
            {
                "url": "https://iced.niti.gov.in/energy/electricity/capacity/upcoming",
                "fetched_at": fetched_at_iso,
            }
        ],
        "license": {
            "id": "GoI-OpenData",
            "name": "Government of India Open Data License",
            "url": "https://www.data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": "India (national)",
            "temporal": temporal,
            "admin_level": None,
        },
        "indicator": {
            "id": "energy/plant_pipeline_info",
            "title": "India under-construction generation capacity, by year and status (GW)",
            "description": description,
            "entity_kind": "country",
            "time_grain": "year",
            "value_kind": "count",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "GW",
            "short_unit": "GW",
            "icon": "bolt",
            "attribution_geography": "where_produced",
            "comparability": "comparable_across_states_and_time",
            "implementing_authority": "joint",
            "methodology_vintage": (
                f"NITI Aayog ICED plantPipelineInfo endpoint; payload fetched "
                f"{fetched_at_iso}; calendar-year expected-commissioning grain; "
                "two status facets verbatim."
            ),
            "notes": (
                "Source: NITI Aayog ICED dashboard (https://iced.niti.gov.in/"
                "energy/electricity/capacity/upcoming). AES-encrypted API "
                "envelope; IcedClient.get(..., decrypt=True). Originating data: "
                "Central Electricity Authority station-level pipeline records; "
                "ICED is the federal aggregator (silver / not-authority)."
            ),
        },
        "series_spec": {"description": description},
        "methodology": {
            "definition": description,
            "publisher": "joint",
            "publisher_methodology_url": None,
            "documentation_status": "stub",
            "methodology_breaks": [],
            "known_caveats": [],
            "notes": [],
        },
        "divergence": None,
        "rows": rows,
    }


def fetch_plant_pipeline_info(
    *,
    repo_root: Path,
    client: IcedClient | None = None,
) -> tuple[Path, datetime, dict[str, Any]]:
    """Fetch + parse + persist one snapshot.

    Returns ``(meadow_path, vintage_dt, meadow_payload)``.

    ``vintage_dt`` is the upstream ``Last-Modified`` (UTC) carried by the
    HTTP response -- never a wall-clock ``datetime.now()``. The meadow
    file path encodes the vintage as ``YYYY-MM-DD`` per the
    ``_meadow/<source>/<vintage>/<endpoint>.json`` grammar.

    Passing an explicit ``client`` enables tests + offline replay; the
    default constructs an :class:`IcedClient` pointing at the v1 host.
    """
    if client is None:
        client = IcedClient(host=f"{API_HOST_DEFAULT}/v1", runtime_root=repo_root)
    response = client.get(API_PATH, decrypt=True)

    vintage_dt = response.fetched_at
    vintage_str = vintage_dt.strftime("%Y-%m-%d")
    rows = parse_plant_pipeline_info(response.decrypted)
    meadow_payload = _build_meadow_payload(
        rows=rows,
        fetched_at_iso=vintage_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    meadow_dir = repo_root / "datasets" / "energy" / "_meadow" / "iced" / vintage_str
    meadow_dir.mkdir(parents=True, exist_ok=True)
    meadow_path = meadow_dir / "plant_pipeline_info.json"
    meadow_path.write_text(
        json.dumps(meadow_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return meadow_path, vintage_dt, meadow_payload
