"""Tests for ``tools/boundaries/lift_boundary_lgd_ac_id.py`` (ADR-0049).

End-to-end unit coverage with a tiny inline crosswalk CSV + consolidated AC
TopoJSON fixture under ``tmp_path`` (no network, no real corpus). Validates:

* crosswalk-covered ``AC_ID`` geometries get ``lgd_ac_id`` stamped
* geometries without ``AC_ID`` (S03 district-fallback / U08 ``seat_id``) untouched
* spillover geometries whose ``AC_ID`` is NOT crosswalk-covered untouched
* an already-stamped geometry is skipped (idempotent) and its value preserved
* every stamped ``lgd_ac_id`` is in the crosswalk-covered set
* ``ac_no`` retained beside the new ``lgd_ac_id``
* the loader reads the canonical CSV (not the retired parquet) and excludes NULLs
* byte-determinism: a second run over the stamped tree is a no-op

The companion ``test_boundary_lgd_ac_id_coverage.py`` is the integration
guard against the REAL committed topojson drifting out of sync with the
crosswalk; this file unit-tests the stamping LOGIC with synthetic fixtures.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(scope="module")
def lift_module() -> Any:
    repo_root = Path(__file__).resolve().parents[2]
    tools_dir = repo_root / "tools" / "boundaries"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    spec_path = tools_dir / "lift_boundary_lgd_ac_id.py"
    spec = importlib.util.spec_from_file_location(
        "lift_boundary_lgd_ac_id", spec_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _geom(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Polygon", "arcs": [[0]], "properties": props}


def _write_topojson(root: Path, geometries: list[dict]) -> Path:
    d = root / "boundaries" / "electoral" / "delim=2024" / "ac"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "all.topojson"
    topo = {
        "type": "Topology",
        "objects": {
            "ac": {"type": "GeometryCollection", "geometries": geometries}
        },
        "arcs": [[[0, 0], [1, 1]]],
    }
    # Match the mapshaper output byte-style (compact, no trailing newline).
    p.write_bytes(
        json.dumps(topo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return p


def _write_crosswalk(root: Path, covered: list[int]) -> None:
    d = root / "data" / "entities"
    d.mkdir(parents=True, exist_ok=True)
    lines = ["state_entity_id,delim_year,eci_no,lgd_ac_id"]
    for i, lgd in enumerate(covered, start=1):
        lines.append(f"tamil-nadu,2024,{i},{lgd}")
    # an unmapped (empty lgd_ac_id) row to exercise the IS NOT NULL filter
    lines.append("jammu-and-kashmir,2024,999,")
    (d / "ac_crosswalk.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ac_topojson(root: Path) -> Path:
    return root / "boundaries/electoral/delim=2024/ac/all.topojson"


def _geometries(root: Path) -> list[dict]:
    return json.loads(_ac_topojson(root).read_bytes())["objects"]["ac"]["geometries"]


@pytest.fixture()
def datasets_root(tmp_path: Path) -> Path:
    root = tmp_path / "datasets"
    root.mkdir()
    _write_crosswalk(root, covered=[33001, 33002, 28001])
    _write_topojson(
        root,
        [
            _geom({"ac_no": 1, "AC_ID": "33001"}),  # covered -> stamp 33001
            _geom({"ac_no": 2, "AC_ID": "33002"}),  # covered -> stamp 33002
            _geom({"ac_no": 9, "AC_ID": "34001"}),  # uncovered spillover -> skip
            _geom({"ac_no": 5}),  # no AC_ID (S03 district-fallback) -> skip
            _geom({"seat_id": 7}),  # no AC_ID (U08 seat_id) -> skip
            _geom(
                {"ac_no": 3, "AC_ID": "28001", "lgd_ac_id": 28001}
            ),  # already stamped -> skip, counted as "already"
        ],
    )
    return root


def test_covered_features_get_lgd_ac_id(
    lift_module: Any, datasets_root: Path
) -> None:
    report = lift_module.stamp_consolidated_topojson(datasets_root)
    assert report == {"total": 6, "stamped": 2, "already": 1, "covered": 3}
    by_acno = {
        g["properties"].get("ac_no"): g["properties"]
        for g in _geometries(datasets_root)
    }
    assert by_acno[1]["lgd_ac_id"] == 33001
    assert by_acno[2]["lgd_ac_id"] == 33002
    # ac_no retained beside the new lgd_ac_id
    assert by_acno[2]["ac_no"] == 2


def test_uncovered_spillover_untouched(
    lift_module: Any, datasets_root: Path
) -> None:
    lift_module.stamp_consolidated_topojson(datasets_root)
    spill = next(
        g for g in _geometries(datasets_root) if g["properties"].get("ac_no") == 9
    )
    assert "lgd_ac_id" not in spill["properties"]


def test_features_without_ac_id_untouched(
    lift_module: Any, datasets_root: Path
) -> None:
    lift_module.stamp_consolidated_topojson(datasets_root)
    for g in _geometries(datasets_root):
        props = g["properties"]
        if "AC_ID" not in props:
            assert "lgd_ac_id" not in props


def test_already_stamped_geometry_preserved(
    lift_module: Any, datasets_root: Path
) -> None:
    """A geometry that already carries lgd_ac_id is skipped, value unchanged."""
    report = lift_module.stamp_consolidated_topojson(datasets_root)
    assert report["already"] == 1
    pre = next(
        g for g in _geometries(datasets_root) if g["properties"].get("ac_no") == 3
    )
    assert pre["properties"]["lgd_ac_id"] == 28001


def test_subset_gate(lift_module: Any, datasets_root: Path) -> None:
    """Every stamped lgd_ac_id must be in the crosswalk-covered set."""
    covered = lift_module.load_covered_lgd_ac_ids(datasets_root)
    lift_module.stamp_consolidated_topojson(datasets_root)
    stamped: set[int] = set()
    for g in _geometries(datasets_root):
        v = g["properties"].get("lgd_ac_id")
        if v is not None:
            stamped.add(int(v))
    assert stamped <= covered
    assert stamped == {33001, 33002, 28001}


def test_load_excludes_null_lgd_ac_id(
    lift_module: Any, datasets_root: Path
) -> None:
    covered = lift_module.load_covered_lgd_ac_ids(datasets_root)
    assert covered == {33001, 33002, 28001}


def test_missing_crosswalk_returns_empty(lift_module: Any, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert lift_module.load_covered_lgd_ac_ids(empty) == set()
    report = lift_module.stamp_consolidated_topojson(empty)
    assert report["stamped"] == 0
    assert report["covered"] == 0


def test_dry_run_does_not_write(lift_module: Any, datasets_root: Path) -> None:
    before = _ac_topojson(datasets_root).read_bytes()
    report = lift_module.stamp_consolidated_topojson(datasets_root, dry_run=True)
    assert report["stamped"] == 2
    assert _ac_topojson(datasets_root).read_bytes() == before


def test_idempotent_byte_stable(lift_module: Any, datasets_root: Path) -> None:
    topo = _ac_topojson(datasets_root)
    lift_module.stamp_consolidated_topojson(datasets_root)
    first = topo.read_bytes()
    second_report = lift_module.stamp_consolidated_topojson(datasets_root)
    assert second_report["stamped"] == 0
    assert topo.read_bytes() == first
