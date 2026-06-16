"""Regression lock for tools/topojson/build_country.py (Row 2 of the
2026-06-16 map-geometry rip-and-replace plan).

C1: the combined country topojson carries `objects.states` (~36) +
`objects.districts` (~785); every state feature has an integer
`State_LGD`, every district an integer `dist_lgd`. A renamed / dropped
join key would blank every map (Gregor G1).

C2 (NON-NEGOTIABLE): a Lakshadweep feature survives BY NAME into BOTH the
`states` and `districts` objects of the freshly built output. This is the
standing guard for the exact island regression this plan exists to fix.

Two tiers:
  - `test_build_country_*` build into tmp_path with the real mapshaper
    binary (skipped when mapshaper is absent, per Holy Law #7 - no mocks).
  - `test_built_artifact_*` read the already-shipped
    datasets/boundaries/in/country/all.topojson (read-only, ONE known
    file - NOT a corpus walk) so the lock holds even in a mapshaper-less
    shell.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.topojson import build_country  # noqa: E402

BUILT_ARTIFACT = (
    REPO_ROOT / "datasets" / "boundaries" / "in" / "country" / "all.topojson"
)

MAPSHAPER_BIN = REPO_ROOT / "frontend" / "node_modules" / ".bin" / "mapshaper.exe"
if not MAPSHAPER_BIN.exists():
    alt = (
        REPO_ROOT / "frontend" / "node_modules" / ".bin" / "mapshaper.cmd",
        REPO_ROOT / "frontend" / "node_modules" / ".bin" / "mapshaper",
    )
    MAPSHAPER_BIN = next((p for p in alt if p.exists()), MAPSHAPER_BIN)

_mapshaper_available = (
    MAPSHAPER_BIN.exists()
    or bool(shutil.which("bunx"))
    or bool(shutil.which("mapshaper"))
)
requires_mapshaper = pytest.mark.skipif(
    not _mapshaper_available,
    reason="mapshaper not installed (run `cd frontend && bun install`)",
)


def _load_objects(topojson_path: Path) -> tuple[list, list]:
    topo = json.loads(topojson_path.read_text(encoding="utf-8"))
    objects = topo.get("objects", {})
    assert "states" in objects, "country topojson missing 'states' object"
    assert "districts" in objects, "country topojson missing 'districts' object"
    return objects["states"]["geometries"], objects["districts"]["geometries"]


def _assert_shape(states: list, districts: list) -> None:
    # C1: feature counts + integer join keys.
    assert len(states) >= 30, f"expected ~36 states, got {len(states)}"
    assert len(districts) >= 700, f"expected ~785 districts, got {len(districts)}"
    for g in states:
        lgd = (g.get("properties") or {}).get("State_LGD")
        assert isinstance(lgd, int), f"a states feature lacks an int State_LGD: {lgd!r}"
    for g in districts:
        lgd = (g.get("properties") or {}).get("dist_lgd")
        assert isinstance(lgd, int), f"a districts feature lacks an int dist_lgd: {lgd!r}"


def _assert_lakshadweep(states: list, districts: list) -> None:
    # C2 (NON-NEGOTIABLE): Lakshadweep survives BY NAME into BOTH objects.
    for name, geoms in (("states", states), ("districts", districts)):
        hit = any(
            "laksh" in json.dumps(g.get("properties") or {}).lower() for g in geoms
        )
        assert hit, f"C2 regression: Lakshadweep absent from {name!r} object"


@requires_mapshaper
def test_build_country_shape_and_islands(tmp_path: Path) -> None:
    """C1 + C2 against a freshly built output (real mapshaper, tmp_path)."""
    out = build_country.build_country(output_path=tmp_path / "all.topojson")
    states, districts = _load_objects(out)
    _assert_shape(states, districts)
    _assert_lakshadweep(states, districts)


@requires_mapshaper
def test_build_country_returns_output_path(tmp_path: Path) -> None:
    out = build_country.build_country(output_path=tmp_path / "nested" / "all.topojson")
    assert out == tmp_path / "nested" / "all.topojson"
    assert out.exists()


@pytest.mark.skipif(
    not BUILT_ARTIFACT.exists(),
    reason="built country topojson not present on disk",
)
def test_built_artifact_shape_and_islands() -> None:
    """C1 + C2 against the already-shipped artifact (read-only, ONE file)."""
    states, districts = _load_objects(BUILT_ARTIFACT)
    _assert_shape(states, districts)
    _assert_lakshadweep(states, districts)
