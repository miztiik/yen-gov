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


def test_write_artifact_derives_folded_blocks_when_payload_omits_them(tmp_path: Path) -> None:
    """Composer that emits a v1.5-shape payload (no series_spec / methodology /
    divergence) still produces a valid v4.0 artifact —
    write_artifact derives stubs and validates. v4.0 dropped
    `collection_inventory` (lifted to external completeness index per
    ADR-0026) and shrunk `series_spec` to `{description}` only."""
    schema = _load_schema("indicator.schema.json")
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
    # All three required v4.0 folded blocks present.
    for block in ("series_spec", "methodology", "divergence"):
        assert block in written, f"missing {block}"
    # v4.0: collection_inventory MUST NOT be in the artifact.
    assert "collection_inventory" not in written
    # v4.0: series_spec is `{description}` only — no expected_* keys.
    assert set(written["series_spec"].keys()) == {"description"}
    # Stub markers visible — /data-completeness can surface these as 'stub'.
    assert written["methodology"]["documentation_status"] == "stub"


def test_write_artifact_v4_strips_no_inventory_carried_in_caller_payload(tmp_path: Path) -> None:
    """v4.0: if a caller (e.g. unpatched old composer) still passes a
    `collection_inventory` block in the payload, validation MUST reject
    it — the schema has `additionalProperties: false`. This catches a
    composer that didn't get the v4 memo."""
    import jsonschema
    schema = _load_schema("indicator.schema.json")
    target = tmp_path / "datasets" / "indicators" / "in" / "fiscal" / "write_artifact_smoke.json"

    payload = _indicator_payload()
    payload["collection_inventory"] = {
        "status": "complete", "frozen": False,
        "last_collected_at": None, "refetch_requested": False,
        "pending_periods": [], "observed_periods": [], "unavailable_periods": [],
    }

    with pytest.raises(jsonschema.ValidationError):
        write_artifact(
            path=target,
            schema_id=schema["$id"], schema_version=schema["x-version"],
            payload=payload,
            sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 17, tzinfo=timezone.utc))],
            schema_for_validation=schema,
        )


def test_write_artifact_caller_provided_methodology_wins_over_prior(tmp_path: Path) -> None:
    """Composer that knows what it's doing can pass methodology
    explicitly; that value wins over both the prior on-disk methodology
    and the stub. Catches a regression where the carry-forward logic
    accidentally overwrote a caller-supplied block."""
    schema = _load_schema("indicator.schema.json")
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


# --------------------------------------------------------------------- #
# Write-skip gate (dict-equal, operational-field-stripped)               #
# --------------------------------------------------------------------- #


def test_write_artifact_skips_write_when_only_fetched_at_changed(tmp_path: Path) -> None:
    """The headline bug fix: re-emitting the same indicator with only
    `sources[].fetched_at` changing MUST NOT advance the file's bytes or
    mtime. This is the test that would have caught the multi-day arc of
    `fetched_at` smearing across unrelated artifacts (per 2026-05-16
    user-memory lesson)."""
    schema = _load_schema("indicator.schema.json")
    target = tmp_path / "datasets" / "indicators" / "in" / "fiscal" / "write_artifact_smoke.json"

    # First write.
    write_artifact(
        path=target,
        schema_id=schema["$id"], schema_version=schema["x-version"],
        payload=_indicator_payload(),
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 17, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )
    first_bytes = target.read_bytes()
    first_mtime_ns = target.stat().st_mtime_ns

    # Re-emit with identical rows but a different fetched_at — the bug case.
    write_artifact(
        path=target,
        schema_id=schema["$id"], schema_version=schema["x-version"],
        payload=_indicator_payload(),
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 18, 9, 0, 0, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )

    assert target.read_bytes() == first_bytes, "fetched_at-only change must not rewrite bytes"
    assert target.stat().st_mtime_ns == first_mtime_ns, "fetched_at-only change must not advance mtime"


def test_write_artifact_writes_when_rows_change(tmp_path: Path) -> None:
    """Sanity counterpart: a real row change DOES rewrite the file."""
    schema = _load_schema("indicator.schema.json")
    target = tmp_path / "datasets" / "indicators" / "in" / "fiscal" / "write_artifact_smoke.json"

    write_artifact(
        path=target,
        schema_id=schema["$id"], schema_version=schema["x-version"],
        payload=_indicator_payload(),
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 17, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )
    first_bytes = target.read_bytes()

    write_artifact(
        path=target,
        schema_id=schema["$id"], schema_version=schema["x-version"],
        payload=_indicator_payload(rows=[
            {"entity_id": "S01", "time": "2024", "value": 999.0},  # value changed
            {"entity_id": "S02", "time": "2023", "value": 200.0},
        ]),
        sources=[Source(url="https://example.gov.in/data.csv", fetched_at=datetime(2026, 5, 17, tzinfo=timezone.utc))],
        schema_for_validation=schema,
    )

    assert target.read_bytes() != first_bytes, "real row change must rewrite bytes"


def test_write_artifact_strip_operational_idempotent() -> None:
    """`_strip_operational` is pure; running it twice produces the same dict."""
    from yen_gov.core.io import _strip_operational

    doc = {
        "sources": [
            {"url": "https://x", "fetched_at": "2026-05-17T00:00:00Z"},
            {"url": "https://y", "fetched_at": "2026-05-18T00:00:00Z"},
        ],
        "collection_inventory": {
            "status": "complete",
            "last_collected_at": "2026-05-18T00:00:00Z",
            "frozen": False,
        },
        "rows": [{"entity_id": "S01", "time": "2023", "value": 1.0}],
    }
    once = _strip_operational(doc)
    twice = _strip_operational(once)
    assert once == twice
    assert "fetched_at" not in once["sources"][0]
    assert "last_collected_at" not in once["collection_inventory"]
    # Non-stripped content intact.
    assert once["sources"][0]["url"] == "https://x"
    assert once["collection_inventory"]["status"] == "complete"
    assert once["rows"][0]["value"] == 1.0

