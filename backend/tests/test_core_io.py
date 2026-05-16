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


# --------------------------------------------------------------------- #
# Folded-block maintenance for indicator artifacts (schema v2.0)         #
# --------------------------------------------------------------------- #


def _indicator_payload(rows: list[dict] | None = None) -> dict:
    """Composer-style payload (no folded blocks; caller doesn't know about them)."""
    if rows is None:
        rows = [
            {"entity_id": "S01", "time": "2023", "value": 100.0},
            {"entity_id": "S02", "time": "2023", "value": 200.0},
        ]
    return {
        "license": {"id": "GoI-Open", "name": "GoI", "redistributable": True},
        "coverage": {"spatial": "All-India", "temporal": "2023..2024"},
        "indicator": {
            "id": "fiscal/write_artifact_smoke",
            "title": "write_artifact smoke indicator",
            "description": "Synthetic indicator used to exercise the folded-block maintenance in write_artifact (schema v2.0).",
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": "count",
            "direction": "neutral",
            "unit": "INR crore",
        },
        "rows": rows,
    }


def _write_universes_into(repo_root: Path) -> None:
    """Place a minimal universes.json at the conventional location so the
    write_artifact loader can find it from the test's tmp tree."""
    target = repo_root / "datasets" / "reference" / "in" / "universes.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "$schema": "https://yen-gov.github.io/schemas/universes.schema.json",
                "$schema_version": "1.0",
                "sources": [],
                "universes": {
                    "states_only_no_ut": {
                        "description": "Synthetic test universe with two states.",
                        "geo_codes": ["S01", "S02"],
                        "expected_count": 2,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_write_artifact_derives_folded_blocks_when_payload_omits_them(tmp_path: Path) -> None:
    """Composer that emits a v1.5-shape payload (no series_spec / methodology /
    collection_inventory / divergence) still produces a valid v2.0 artifact —
    write_artifact derives stubs and validates."""
    schema = _load_schema("indicator.schema.json")
    _write_universes_into(tmp_path)
    target = tmp_path / "datasets" / "indicators" / "in" / "fiscal" / "write_artifact_smoke.json"

    write_artifact(
        path=target,
        schema_id=schema["$id"],
        schema_version=schema["x-version"],
        payload=_indicator_payload(),
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 17, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )

    written = json.loads(target.read_text(encoding="utf-8"))
    # All four required v2.0 blocks present.
    for block in ("series_spec", "methodology", "collection_inventory", "divergence"):
        assert block in written, f"missing {block}"
    # Stub markers visible — /data-completeness can surface these as 'stub'.
    assert written["methodology"]["documentation_status"] == "stub"
    assert written["series_spec"]["expected_periods_inference"]["basis"] == "seeded_from_observed_rows"
    # collection_inventory derived from rows: 2 entities x 1 period, all observed.
    assert written["collection_inventory"]["status"] == "complete"


def test_write_artifact_preserves_operator_set_inventory_fields(tmp_path: Path) -> None:
    """On a re-write of an existing artifact, operator-set fields on
    collection_inventory (frozen / refetch_requested / unavailable_periods)
    survive the auto-rederivation. This is the real regression target:
    if the merge logic regressed, every refresh would silently clear an
    operator's `frozen: true` flag."""
    schema = _load_schema("indicator.schema.json")
    _write_universes_into(tmp_path)
    target = tmp_path / "datasets" / "indicators" / "in" / "fiscal" / "write_artifact_smoke.json"

    write_artifact(
        path=target,
        schema_id=schema["$id"], schema_version=schema["x-version"],
        payload=_indicator_payload(),
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 17, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )

    # Operator edits the artifact: marks frozen, declares an unavailable period.
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    on_disk["collection_inventory"]["frozen"] = True
    on_disk["collection_inventory"]["unavailable_periods"] = [
        {
            "period": {"key": "2099", "label": "FY2099", "frequency": "annual_fy"},
            "reason": "future period, not yet published",
        }
    ]
    target.write_text(json.dumps(on_disk, indent=2) + "\n", encoding="utf-8")

    # Adapter re-emits with fresh rows; operator flags must survive.
    write_artifact(
        path=target,
        schema_id=schema["$id"], schema_version=schema["x-version"],
        payload=_indicator_payload([
            {"entity_id": "S01", "time": "2023", "value": 100.0},
            {"entity_id": "S01", "time": "2024", "value": 110.0},
            {"entity_id": "S02", "time": "2023", "value": 200.0},
            {"entity_id": "S02", "time": "2024", "value": 210.0},
        ]),
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 18, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )

    after = json.loads(target.read_text(encoding="utf-8"))
    assert after["collection_inventory"]["frozen"] is True
    assert after["collection_inventory"]["unavailable_periods"][0]["period"]["key"] == "2099"


def test_write_artifact_caller_provided_methodology_wins_over_prior(tmp_path: Path) -> None:
    """Composer that knows what it's doing can pass methodology
    explicitly; that value wins over both the prior on-disk methodology
    and the stub. Catches a regression where the carry-forward logic
    accidentally overwrote a caller-supplied block."""
    schema = _load_schema("indicator.schema.json")
    _write_universes_into(tmp_path)
    target = tmp_path / "datasets" / "indicators" / "in" / "fiscal" / "write_artifact_smoke.json"

    write_artifact(
        path=target,
        schema_id=schema["$id"], schema_version=schema["x-version"],
        payload=_indicator_payload(),
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 17, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )

    explicit_methodology = {
        "definition": "An authored definition, supplied verbatim by the composer.",
        "publisher": "Explicit Publisher Co.",
        "publisher_methodology_url": "https://example.gov.in/methodology",
        "documentation_status": "authored",
        "methodology_breaks": [],
        "known_caveats": ["Caveat from the composer."],
        "notes": [],
    }
    payload = _indicator_payload()
    payload["methodology"] = explicit_methodology

    write_artifact(
        path=target,
        schema_id=schema["$id"], schema_version=schema["x-version"],
        payload=payload,
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 18, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )

    after = json.loads(target.read_text(encoding="utf-8"))
    assert after["methodology"] == explicit_methodology
