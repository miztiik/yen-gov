"""Tests for tools/topojson/convert_layer.py (P2.1).

Uses a tiny 3-feature GeoJSON fixture in tmp_path; asserts mapshaper is
invoked, the output parses as TopoJSON, and two consecutive runs are
byte-identical (idempotency via the sidecar).

Per CLAUDE.md Holy Law #7 there are no mocks: the real mapshaper binary
(installed under frontend/node_modules/.bin/ via bun install) is exec'd.
The test is skipped if mapshaper is absent (e.g. minimal CI shell).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.topojson import convert_layer  # noqa: E402

MAPSHAPER_BIN = REPO_ROOT / "frontend" / "node_modules" / ".bin" / "mapshaper.exe"
if not MAPSHAPER_BIN.exists():
    # Allow .cmd / .sh / direct binary on non-Windows
    alt = (
        (REPO_ROOT / "frontend" / "node_modules" / ".bin" / "mapshaper.cmd"),
        (REPO_ROOT / "frontend" / "node_modules" / ".bin" / "mapshaper"),
    )
    MAPSHAPER_BIN = next((p for p in alt if p.exists()), MAPSHAPER_BIN)

pytestmark = pytest.mark.skipif(
    not MAPSHAPER_BIN.exists() and not shutil.which("bunx") and not shutil.which("mapshaper"),
    reason="mapshaper not installed (run `cd frontend && bun install`)",
)


def _tiny_geojson() -> dict:
    """Three small triangles with distinct join-key properties."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": i, "name": f"poly{i}"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [i, i],
                            [i + 1, i],
                            [i + 1, i + 1],
                            [i, i + 1],
                            [i, i],
                        ]
                    ],
                },
            }
            for i in range(3)
        ],
    }


def _write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "topojson.json"
    config_path.write_text(
        json.dumps(
            {
                "$schema_version": "1.0",
                "default_quantization": 1000,
                "simplification": "5% weighted",
                "per_layer": {},
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_convert_produces_valid_topojson(tmp_path: Path) -> None:
    input_path = tmp_path / "tiny.geojson"
    input_path.write_text(json.dumps(_tiny_geojson()), encoding="utf-8")
    output_path = tmp_path / "tiny.topojson"
    config_path = _write_config(tmp_path)

    key = convert_layer.convert(input_path, output_path, "tiny", config_path)

    assert output_path.exists()
    assert key["quantization"] == 1000
    assert key["clean"] is False

    parsed = json.loads(output_path.read_text(encoding="utf-8"))
    assert parsed["type"] == "Topology"
    assert "tiny" in parsed["objects"]
    geometries = parsed["objects"]["tiny"]["geometries"]
    assert len(geometries) == 3
    # Property names preserved
    for i, g in enumerate(sorted(geometries, key=lambda g: g["properties"]["id"])):
        assert g["properties"]["id"] == i
        assert g["properties"]["name"] == f"poly{i}"


def test_convert_writes_sidecar_with_key(tmp_path: Path) -> None:
    input_path = tmp_path / "tiny.geojson"
    input_path.write_text(json.dumps(_tiny_geojson()), encoding="utf-8")
    output_path = tmp_path / "tiny.topojson"
    config_path = _write_config(tmp_path)

    convert_layer.convert(input_path, output_path, "tiny", config_path)

    sidecar = convert_layer._sidecar_path(output_path)
    assert sidecar.exists()
    recorded = json.loads(sidecar.read_text(encoding="utf-8"))
    expected_sha = hashlib.sha256(input_path.read_bytes()).hexdigest()
    assert recorded["input_sha256"] == expected_sha
    assert recorded["quantization"] == 1000
    assert recorded["simplification"] == "5% weighted"
    assert recorded["clean"] is False


def test_convert_is_idempotent_byte_equal(tmp_path: Path) -> None:
    input_path = tmp_path / "tiny.geojson"
    input_path.write_text(json.dumps(_tiny_geojson()), encoding="utf-8")
    output_path = tmp_path / "tiny.topojson"
    config_path = _write_config(tmp_path)

    convert_layer.convert(input_path, output_path, "tiny", config_path)
    first_bytes = output_path.read_bytes()
    first_mtime = output_path.stat().st_mtime_ns

    # Second run should short-circuit via sidecar; output bytes unchanged.
    convert_layer.convert(input_path, output_path, "tiny", config_path)
    second_bytes = output_path.read_bytes()
    second_mtime = output_path.stat().st_mtime_ns

    assert first_bytes == second_bytes
    # Sidecar short-circuit means mapshaper was not re-invoked; mtime is
    # unchanged. (Even on a re-run, mapshaper's output is deterministic
    # under the locale-pinned env, so a re-emit would also be byte-equal;
    # but the mtime guard proves the short-circuit fired.)
    assert first_mtime == second_mtime


def test_convert_re_runs_when_input_changes(tmp_path: Path) -> None:
    input_path = tmp_path / "tiny.geojson"
    input_path.write_text(json.dumps(_tiny_geojson()), encoding="utf-8")
    output_path = tmp_path / "tiny.topojson"
    config_path = _write_config(tmp_path)

    convert_layer.convert(input_path, output_path, "tiny", config_path)
    first_bytes = output_path.read_bytes()

    # Mutate the input: drop one feature, rewrite.
    payload = _tiny_geojson()
    payload["features"] = payload["features"][:2]
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    convert_layer.convert(input_path, output_path, "tiny", config_path)
    second_bytes = output_path.read_bytes()
    assert first_bytes != second_bytes

    parsed = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(parsed["objects"]["tiny"]["geometries"]) == 2


def test_convert_missing_input_raises(tmp_path: Path) -> None:
    output_path = tmp_path / "out.topojson"
    config_path = _write_config(tmp_path)
    with pytest.raises(FileNotFoundError):
        convert_layer.convert(tmp_path / "nope.geojson", output_path, "x", config_path)


def test_layer_settings_per_layer_override(tmp_path: Path) -> None:
    config_path = tmp_path / "topojson.json"
    config_path.write_text(
        json.dumps(
            {
                "$schema_version": "1.0",
                "default_quantization": 100000,
                "simplification": "5% weighted",
                "per_layer": {"states": {"quantization": 50000, "clean": True}},
            }
        ),
        encoding="utf-8",
    )
    config = convert_layer._load_config(config_path)
    s = convert_layer._layer_settings(config, "states")
    assert s["quantization"] == 50000
    assert s["clean"] is True
    d = convert_layer._layer_settings(config, "anything_else")
    assert d["quantization"] == 100000
    assert d["clean"] is False
