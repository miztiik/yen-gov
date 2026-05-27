"""Fetch helper for the ICED ``plantPipelineInfo`` endpoint.

Layer 1 (fetch) of the four-layer ingest doctrine
([docs/concepts/ingest-fetch-enrich-separation.md](../../../../docs/concepts/ingest-fetch-enrich-separation.md)).
Pulls one decrypted snapshot of ``/v1/plantPipelineInfo`` and persists it
under ``datasets/energy/_meadow/iced/<vintage>/plant_pipeline_info.json``
([ADR-0041](../../../../docs/architecture/decisions/0041-meadow-tier.md)),
where ``<vintage>`` is the upstream ``Last-Modified`` date (per the
CLAUDE.md anti-pattern that bars ``datetime.now()`` in data-row content).

The fetcher is intentionally thin: no parsing, no entity resolution, no
unit conversion. Those layers live in
:func:`yen_gov.sources.iced_power.parsers.parse_plant_pipeline_info`
(layer 2 — pure parser) and the as-yet-unwritten ``ingest.py`` enricher
that will UPSERT the parsed rows into the canonical store (layer 3 + 4,
deferred to a follow-up PR — see
``TODO/20260527-iced-plant-pipeline-ingest/handover.md`` §5).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from yen_gov.sources.iced_common.client import API_HOST_DEFAULT, IcedClient


API_PATH = "/plantPipelineInfo"


def fetch_plant_pipeline_info(
    *,
    repo_root: Path,
    client: IcedClient | None = None,
) -> tuple[Path, datetime, dict[str, Any]]:
    """Fetch + persist one snapshot. Returns ``(meadow_path, vintage_dt, payload)``.

    ``vintage_dt`` is the upstream ``Last-Modified`` (UTC) carried by the
    HTTP response — never a wall-clock ``datetime.now()``. The meadow
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
    meadow_dir = repo_root / "datasets" / "energy" / "_meadow" / "iced" / vintage_str
    meadow_dir.mkdir(parents=True, exist_ok=True)
    meadow_path = meadow_dir / "plant_pipeline_info.json"

    payload: dict[str, Any] = response.decrypted  # type: ignore[assignment]
    meadow_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return meadow_path, vintage_dt, payload
