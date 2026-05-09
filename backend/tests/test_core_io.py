"""Tests for core.io.write_artifact."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from yen_gov.core.io import Source, write_artifact

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "datasets" / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_write_artifact_stamps_schema_version_and_sources(tmp_path: Path):
    schema = _load_schema("processing.schema.json")
    target = tmp_path / "config" / "processing.json"

    write_artifact(
        path=target,
        schema_id=schema["$id"],
        schema_version=schema["x-version"],
        payload={
            "fetch": {
                "concurrency": 4, "retry_attempts": 3,
                "timeout_seconds": 30.0, "user_agent": "x",
            },
            "results": {"top_n_candidates": 5, "collapse_others": True},
        },
        sources=[],  # hand-authored
        schema_for_validation=schema,
    )

    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["$schema"] == schema["$id"]
    assert written["$schema_version"] == schema["x-version"]
    assert written["sources"] == []
    assert written["fetch"]["concurrency"] == 4


def test_write_artifact_serialises_sources(tmp_path: Path):
    schema = _load_schema("election.schema.json")
    target = tmp_path / "election.json"

    write_artifact(
        path=target,
        schema_id=schema["$id"],
        schema_version=schema["x-version"],
        payload={
            "eci_event_id": "AcGenMay2026", "scope": "state",
            "body": "AC", "year": 2026, "month": 5, "states": ["S22"],
        },
        sources=[Source(
            url="https://results.eci.gov.in/ResultAcGenMay2026/",
            fetched_at=datetime(2026, 5, 8, 14, 30, 0, tzinfo=timezone.utc),
        )],
        schema_for_validation=schema,
    )

    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["sources"] == [{
        "url": "https://results.eci.gov.in/ResultAcGenMay2026/",
        "fetched_at": "2026-05-08T14:30:00Z",
    }]


def test_write_artifact_rejects_payload_with_reserved_keys(tmp_path: Path):
    schema = _load_schema("processing.schema.json")
    with pytest.raises(ValueError, match="reserved keys"):
        write_artifact(
            path=tmp_path / "x.json",
            schema_id=schema["$id"],
            schema_version=schema["x-version"],
            payload={"$schema": "leaked"},
            sources=[],
            schema_for_validation=schema,
        )


def test_write_artifact_rejects_version_mismatch(tmp_path: Path):
    schema = _load_schema("processing.schema.json")
    with pytest.raises(ValueError, match="does not match schema x-version"):
        write_artifact(
            path=tmp_path / "x.json",
            schema_id=schema["$id"],
            schema_version="9.9",
            payload={
                "fetch": {
                    "concurrency": 1, "retry_attempts": 0,
                    "timeout_seconds": 1.0, "user_agent": "x",
                },
                "results": {"top_n_candidates": 1, "collapse_others": False},
            },
            sources=[],
            schema_for_validation=schema,
        )


def test_write_artifact_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        Source(url="https://x", fetched_at=datetime(2026, 5, 8, 14, 30)).to_dict()


def test_write_artifact_runs_schema_validation(tmp_path: Path):
    """Payload missing a required field is rejected before write."""
    schema = _load_schema("processing.schema.json")
    with pytest.raises(Exception):  # jsonschema.ValidationError
        write_artifact(
            path=tmp_path / "x.json",
            schema_id=schema["$id"],
            schema_version=schema["x-version"],
            payload={"fetch": {
                "concurrency": 1, "retry_attempts": 0,
                "timeout_seconds": 1.0, "user_agent": "x",
            }},  # missing 'results'
            sources=[],
            schema_for_validation=schema,
        )
    assert not (tmp_path / "x.json").exists(), "must not write on validation failure"
