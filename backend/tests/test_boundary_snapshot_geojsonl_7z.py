"""Unit tests for tools.boundaries.snapshot — focus on the geojsonl_7z handler.

Per CLAUDE.md §15 (DoD: "tests ship with the feature") and Holy Law #7
(no mocks). Builds a real .geojsonl, packs it with py7zr, and asserts that
fetch_geojsonl_7z extracts + wraps it correctly. The "download" step is
the one place we substitute a real local file for an HTTP URL — via
file:// URI which urllib.request handles natively (still a real fetch,
just over the local filesystem).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "boundaries"))

import snapshot  # noqa: E402  (after sys.path manipulation)

py7zr = pytest.importorskip("py7zr")


def _build_archive(dest_dir: Path, features: list[dict]) -> Path:
    """Write features as .geojsonl, pack to .geojsonl.7z, return the archive path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    payload = dest_dir / "fixture.geojsonl"
    payload.write_text(
        "\n".join(json.dumps(f) for f in features) + "\n",
        encoding="utf-8",
    )
    archive = dest_dir / "fixture.geojsonl.7z"
    with py7zr.SevenZipFile(archive, mode="w") as zf:
        zf.write(payload, arcname=payload.name)
    return archive


def _file_url(path: Path) -> str:
    return path.resolve().as_uri()


@pytest.fixture
def two_district_features() -> list[dict]:
    return [
        {
            "type": "Feature",
            "properties": {"dist_lgd": 673, "dtname": "Morbi", "stname": "GUJARAT"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[70.123456, 22.654321], [70.789012, 22.654321],
                                 [70.789012, 22.123456], [70.123456, 22.123456],
                                 [70.123456, 22.654321]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"dist_lgd": 100, "dtname": "Test District", "stname": "TESTLAND"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[80.0, 13.0], [80.5, 13.0], [80.5, 12.5],
                                 [80.0, 12.5], [80.0, 13.0]]],
            },
        },
    ]


def test_extracts_and_wraps_features(tmp_path: Path, two_district_features: list[dict]) -> None:
    archive = _build_archive(tmp_path / "src", two_district_features)
    out_path = tmp_path / "out" / "test-districts.geojson"
    raw_dir = tmp_path / "raw"

    sources = snapshot.fetch_geojsonl_7z([_file_url(archive)], out_path, raw_dir)

    assert out_path.is_file()
    fc = json.loads(out_path.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2
    # Property pass-through verbatim — no allowlist filtering at this layer.
    assert fc["features"][0]["properties"]["dist_lgd"] == 673
    assert fc["features"][1]["properties"]["dtname"] == "Test District"
    # Provenance: one source row per URL with fetched_at populated.
    assert len(sources) == 1
    assert sources[0]["url"] == _file_url(archive)
    assert sources[0]["fetched_at"].endswith("Z")


def test_coord_precision_rounds_and_dedups(tmp_path: Path, two_district_features: list[dict]) -> None:
    archive = _build_archive(tmp_path / "src", two_district_features)
    out_path = tmp_path / "out" / "rounded.geojson"
    raw_dir = tmp_path / "raw"

    snapshot.fetch_geojsonl_7z([_file_url(archive)], out_path, raw_dir, coord_precision=2)

    fc = json.loads(out_path.read_text(encoding="utf-8"))
    coords = fc["features"][0]["geometry"]["coordinates"][0]
    # 70.123456 -> 70.12 at precision=2.
    assert coords[0] == [70.12, 22.65]
    # All coordinate components have at most 2 decimal places.
    for ring in fc["features"][0]["geometry"]["coordinates"]:
        for x, y in ring:
            assert round(x, 2) == x
            assert round(y, 2) == y


def test_rejects_multi_url(tmp_path: Path, two_district_features: list[dict]) -> None:
    archive = _build_archive(tmp_path / "src", two_district_features)
    with pytest.raises(ValueError, match="exactly 1 url"):
        snapshot.fetch_geojsonl_7z(
            [_file_url(archive), _file_url(archive)],
            tmp_path / "out.geojson",
            tmp_path / "raw",
        )


def test_rejects_archive_without_geojsonl(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    txt = src / "not_a_layer.txt"
    txt.write_text("hello", encoding="utf-8")
    archive = src / "junk.7z"
    with py7zr.SevenZipFile(archive, mode="w") as zf:
        zf.write(txt, arcname=txt.name)

    with pytest.raises(ValueError, match="no .geojsonl file"):
        snapshot.fetch_geojsonl_7z([_file_url(archive)], tmp_path / "out.geojson", tmp_path / "raw")


def test_districts_basename_routing() -> None:
    """derive_output_basename knows the new kind=districts shape."""
    assert (
        snapshot.derive_output_basename({"kind": "districts", "country": "IN"})
        == "india-districts.geojson"
    )
    # Per-state district carve-outs are not yet supported; fail loudly.
    with pytest.raises(ValueError):
        snapshot.derive_output_basename({"kind": "districts", "state": "S03"})
