"""Meadow envelope tests for the ICED plant-pipeline fetch helper."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common.client import IcedResponse
from yen_gov.sources.iced_power.fetch_pipeline import (
    _build_meadow_payload,
    fetch_plant_pipeline_info,
)


def _sample_decrypted() -> dict[str, Any]:
    return {
        "category": ["2024", "2025"],
        "seriesData": [
            {
                "name": "Under Construction and likely to be commissioned",
                "data": [6.5, 3.5],
            },
            {"name": "Under Construction but on Hold", "data": [0.0, 0.5]},
        ],
    }


def _sample_rows() -> list[dict[str, Any]]:
    return [
        {
            "entity_id": "IN",
            "time": "2024",
            "value": 6.5,
            "facet": "Under Construction and likely to be commissioned",
        },
        {
            "entity_id": "IN",
            "time": "2024",
            "value": 0.0,
            "facet": "Under Construction but on Hold",
        },
    ]


def test_build_meadow_payload_uses_current_indicator_schema() -> None:
    payload = _build_meadow_payload(
        rows=_sample_rows(),
        fetched_at_iso="2026-05-27T00:00:00Z",
    )

    assert payload["$schema"] == schema_id("indicator.schema.json")
    assert payload["$schema_version"] == schema_version("indicator.schema.json")
    assert "default_mode" not in payload["indicator"]
    assert "facet_labels" not in payload["indicator"]
    assert "renderer_rules" not in payload["indicator"]
    Draft202012Validator(schema_doc("indicator.schema.json")).validate(payload)


def test_fetch_plant_pipeline_info_writes_current_schema_payload(tmp_path: Path) -> None:
    fetched_at = datetime(2026, 5, 27, tzinfo=timezone.utc)

    class FakeClient:
        def get(self, api_path: str, *, decrypt: bool) -> IcedResponse:
            assert api_path == "/plantPipelineInfo"
            assert decrypt is True
            return IcedResponse(
                url="https://icedapi.niti.gov.in/v1/plantPipelineInfo",
                fetched_at=fetched_at,
                decrypted=_sample_decrypted(),
                raw_body=b"{}",
                raw_path=tmp_path / ".runtime" / "raw" / "iced" / "sample.b64",
            )

    meadow_path, vintage_dt, payload = fetch_plant_pipeline_info(
        repo_root=tmp_path,
        client=FakeClient(),
    )

    assert vintage_dt == fetched_at
    assert meadow_path == tmp_path / "datasets" / "energy" / "_meadow" / "iced" / "2026-05-27" / "plant_pipeline_info.json"
    on_disk = json.loads(meadow_path.read_text(encoding="utf-8"))
    assert on_disk["$schema"] == schema_id("indicator.schema.json")
    assert on_disk["$schema_version"] == schema_version("indicator.schema.json")
    assert on_disk == payload