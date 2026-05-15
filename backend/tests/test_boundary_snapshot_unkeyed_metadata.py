"""Unit tests for tools.boundaries.snapshot — unkeyed + simplification sidecars.

Phase 1b commit 4. Per CLAUDE.md §15 + Holy Law #7: real fixtures, no mocks.
No py7zr dependency — these helpers operate on in-memory feature dicts and the
local filesystem. Sidecar payloads are validated against their schemas so a
future schema bump faces the test as well.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "boundaries"))

import snapshot  # noqa: E402

jsonschema = pytest.importorskip("jsonschema")

SCHEMAS = REPO / "datasets" / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _feat(props: dict) -> dict:
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Point", "coordinates": [80.0, 13.0]},
    }


# --- _make_drop_record -----------------------------------------------------


def test_make_drop_record_uses_name_property() -> None:
    feat = _feat({"vlgname": "Adyar", "village_lgd": 12345, "stname": "TAMIL NADU"})
    rec = snapshot._make_drop_record(feat, "outside_state_filter", name_property="vlgname")
    assert rec["source_feature_name"] == "Adyar"
    assert rec["reason"] == "outside_state_filter"
    assert rec["dropped_at"].endswith("Z")


def test_make_drop_record_falls_back_to_common_name_keys() -> None:
    feat = _feat({"stname": "KARNATAKA"})
    rec = snapshot._make_drop_record(feat, "outside_state_filter")
    assert rec["source_feature_name"] == "KARNATAKA"


def test_make_drop_record_unnamed_when_no_name_field() -> None:
    rec = snapshot._make_drop_record(_feat({"foo": "bar"}), "geometry_invalid")
    assert rec["source_feature_name"] == "(unnamed)"
    # Schema requires minLength 1 — verify literally.
    assert len(rec["source_feature_name"]) >= 1


# --- _write_unkeyed_sidecar -----------------------------------------------


_SOURCES_FIXTURE = [
    {
        "url": "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/villages/LGD_Villages.geojsonl.7z",
        "fetched_at": "2026-05-15T12:00:00Z",
    },
]


def test_unkeyed_sidecar_validates_and_records_totals(tmp_path: Path) -> None:
    sidecar = tmp_path / "S22-villages-603.geojson.unkeyed.json"
    drops = [
        snapshot._make_drop_record(_feat({"vlgname": "X"}), "no_lgd_code_in_source"),
        snapshot._make_drop_record(_feat({"vlgname": "Y"}), "outside_state_filter"),
    ]
    snapshot._write_unkeyed_sidecar(
        sidecar,
        basename="S22-villages-603.geojson",
        original=10,
        retained=8,
        dropped_records=drops,
        sources=_SOURCES_FIXTURE,
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    jsonschema.validate(payload, _load("boundary.unkeyed.schema.json"))
    assert payload["totals"] == {"original": 10, "retained": 8, "dropped": 2}
    assert payload["for"] == "S22-villages-603.geojson"
    assert payload["$schema_version"] == "2.0"
    assert payload["sources"] == _SOURCES_FIXTURE


def test_unkeyed_sidecar_empty_dropped_emitted_explicitly(tmp_path: Path) -> None:
    """Hans v2 nit: 'perfect snapshot' must be written, not omitted."""
    sidecar = tmp_path / "india-districts.geojson.unkeyed.json"
    snapshot._write_unkeyed_sidecar(
        sidecar,
        basename="india-districts.geojson",
        original=800,
        retained=800,
        dropped_records=[],
        sources=_SOURCES_FIXTURE,
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    jsonschema.validate(payload, _load("boundary.unkeyed.schema.json"))
    assert payload["totals"]["dropped"] == 0
    assert payload["dropped"] == []


def test_unkeyed_sidecar_denominator_mismatch_raises(tmp_path: Path) -> None:
    """Writer-side guard: original != retained + dropped is a logic error."""
    sidecar = tmp_path / "x.unkeyed.json"
    with pytest.raises(ValueError, match="denominator mismatch"):
        snapshot._write_unkeyed_sidecar(
            sidecar, "x.geojson", original=10, retained=8, dropped_records=[],
            sources=_SOURCES_FIXTURE,
        )


# --- _write_simplification_metadata_sidecar --------------------------------


def _entry_metadata() -> dict:
    return {
        "title": "Tamil Nadu villages (LGD)",
        "description": "Per-village polygons for TN, keyed by village_lgd.",
        "category": "boundaries",
        "license": {
            "id": "CC0-1.0",
            "name": "Creative Commons Zero v1.0",
            "url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "redistributable": True,
        },
        "coverage": {
            "spatial": "Tamil Nadu",
            "temporal": "snapshot 2026-05-15",
            "admin_level": "village",
        },
        "coordinate_system": "EPSG:4326",
    }


def _sources() -> list[dict[str, str]]:
    return [
        {
            "url": "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/villages/LGD_Villages.geojsonl.7z",
            "fetched_at": "2026-05-15T12:00:00Z",
        },
    ]


def test_simplification_metadata_sidecar_validates(tmp_path: Path) -> None:
    metadata = tmp_path / "S22-villages-603.geojson.metadata.json"
    snapshot._write_simplification_metadata_sidecar(
        metadata,
        basename="S22-villages-603.geojson",
        entry_metadata=_entry_metadata(),
        sources=_sources(),
        coord_precision=4,
        original_feature_count=120,
        retained_feature_count=120,
    )
    payload = json.loads(metadata.read_text(encoding="utf-8"))
    jsonschema.validate(payload, _load("feature_collection.metadata.schema.json"))
    assert payload["$schema_version"] == "1.2"
    assert payload["simplification"]["algorithm"] == "coord-precision-round"
    # 10 ** -4 — let pytest.approx tolerate float repr.
    assert payload["simplification"]["tolerance_deg"] == pytest.approx(1e-4)
    assert payload["simplification"]["original_feature_count"] == 120
    assert payload["coverage"]["admin_level"] == "village"
    assert payload["title"] == "Tamil Nadu villages (LGD)"


def test_simplification_metadata_passes_through_optional_fields(tmp_path: Path) -> None:
    """Optional pass-through fields (title/description/category/coordinate_system)
    are copied verbatim from the entry's metadata block; absent fields stay absent."""
    metadata = tmp_path / "x.metadata.json"
    minimal_entry = {
        "license": _entry_metadata()["license"],
        "coverage": _entry_metadata()["coverage"],
    }
    snapshot._write_simplification_metadata_sidecar(
        metadata,
        basename="x.geojson",
        entry_metadata=minimal_entry,
        sources=_sources(),
        coord_precision=3,
        original_feature_count=5,
        retained_feature_count=5,
    )
    payload = json.loads(metadata.read_text(encoding="utf-8"))
    jsonschema.validate(payload, _load("feature_collection.metadata.schema.json"))
    assert "title" not in payload
    assert "description" not in payload
    assert payload["simplification"]["tolerance_deg"] == pytest.approx(1e-3)
