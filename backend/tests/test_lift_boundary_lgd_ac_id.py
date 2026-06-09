"""Tests for ``tools/boundaries/lift_boundary_lgd_ac_id.py`` (Row B1).

End-to-end with a tiny inline crosswalk parquet + AC shard fixtures (no
network). Validates:

* crosswalk-covered ``AC_ID`` features get ``lgd_ac_id`` stamped
* features without ``AC_ID`` (S03 district-fallback / U08 seat_id) untouched
* spillover features whose ``AC_ID`` is NOT crosswalk-covered untouched
* the B1 subset gate: every stamped ``lgd_ac_id`` is in crosswalk-covered
* ``ac_no`` retained beside the new ``lgd_ac_id``
* byte-determinism: a second run over the stamped tree is a no-op
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import duckdb
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


def _feature(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        },
    }


def _write_shard(root: Path, state: str, features: list[dict]) -> Path:
    d = (
        root
        / "boundaries"
        / "electoral"
        / "delim=2008"
        / "ac"
        / f"state=in_{state}"
    )
    d.mkdir(parents=True, exist_ok=True)
    p = d / "all.geojson"
    with p.open("w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, ensure_ascii=False)
    return p


def _write_crosswalk(root: Path, covered: list[int]) -> None:
    tax = root / "taxonomy"
    tax.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        con.execute("CREATE TABLE cx (lgd_ac_id INTEGER, eci_no INTEGER)")
        for i, lgd in enumerate(covered, start=1):
            con.execute("INSERT INTO cx VALUES (?, ?)", [lgd, i])
        # add an unmapped (NULL lgd_ac_id) row to exercise the IS NOT NULL filter
        con.execute("INSERT INTO cx VALUES (NULL, 999)")
        con.execute(
            "COPY cx TO ? (FORMAT PARQUET)",
            [(tax / "ac_crosswalk.parquet").as_posix()],
        )
    finally:
        con.close()


@pytest.fixture()
def datasets_root(tmp_path: Path) -> Path:
    root = tmp_path / "datasets"
    root.mkdir()
    _write_crosswalk(root, covered=[33001, 33002, 28001])
    # s22: one covered (33002), one spillover-uncovered (34001)
    _write_shard(
        root,
        "s22",
        [
            _feature({"ac_no": 1, "AC_ID": "33001"}),
            _feature({"ac_no": 2, "AC_ID": "33002"}),
            _feature({"ac_no": 9, "AC_ID": "34001"}),  # uncovered spillover
        ],
    )
    # s03: district-fallback, no AC_ID -> never stamped
    _write_shard(root, "s03", [_feature({"ac_no": 5})])
    # u08: seat_id, no AC_ID -> never stamped
    _write_shard(root, "u08", [_feature({"seat_id": 7})])
    return root


def test_covered_features_get_lgd_ac_id(lift_module: Any, datasets_root: Path) -> None:
    report = lift_module.lift_all(datasets_root)
    assert report["state=in_s22"] == (3, 2)  # 3 features, 2 stamped
    data = json.loads(
        (datasets_root / "boundaries/electoral/delim=2008/ac/state=in_s22/all.geojson").read_text()
    )
    by_acno = {f["properties"]["ac_no"]: f["properties"] for f in data["features"]}
    assert by_acno[1]["lgd_ac_id"] == 33001
    assert by_acno[2]["lgd_ac_id"] == 33002
    # ac_no retained beside lgd_ac_id
    assert by_acno[2]["ac_no"] == 2


def test_uncovered_spillover_untouched(lift_module: Any, datasets_root: Path) -> None:
    lift_module.lift_all(datasets_root)
    data = json.loads(
        (datasets_root / "boundaries/electoral/delim=2008/ac/state=in_s22/all.geojson").read_text()
    )
    spill = next(f for f in data["features"] if f["properties"]["ac_no"] == 9)
    assert "lgd_ac_id" not in spill["properties"]


def test_shards_without_ac_id_untouched(lift_module: Any, datasets_root: Path) -> None:
    report = lift_module.lift_all(datasets_root)
    assert report["state=in_s03"] == (1, 0)
    assert report["state=in_u08"] == (1, 0)
    for state in ("s03", "u08"):
        data = json.loads(
            (datasets_root / f"boundaries/electoral/delim=2008/ac/state=in_{state}/all.geojson").read_text()
        )
        for f in data["features"]:
            assert "lgd_ac_id" not in f["properties"]


def test_subset_gate(lift_module: Any, datasets_root: Path) -> None:
    """Every stamped lgd_ac_id must be in the crosswalk-covered set."""
    covered = lift_module.load_covered_lgd_ac_ids(datasets_root)
    lift_module.lift_all(datasets_root)
    stamped: set[int] = set()
    for sd in (datasets_root / "boundaries/electoral/delim=2008/ac").glob("state=in_*"):
        data = json.loads((sd / "all.geojson").read_text())
        for f in data["features"]:
            v = f["properties"].get("lgd_ac_id")
            if v is not None:
                stamped.add(int(v))
    assert stamped <= covered
    assert stamped == {33001, 33002}


def test_load_excludes_null_lgd_ac_id(lift_module: Any, datasets_root: Path) -> None:
    covered = lift_module.load_covered_lgd_ac_ids(datasets_root)
    assert covered == {33001, 33002, 28001}


def test_missing_crosswalk_returns_empty(lift_module: Any, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert lift_module.load_covered_lgd_ac_ids(empty) == set()
    assert lift_module.lift_all(empty) == {}


def test_idempotent_byte_stable(lift_module: Any, datasets_root: Path) -> None:
    shard = datasets_root / "boundaries/electoral/delim=2008/ac/state=in_s22/all.geojson"
    lift_module.lift_all(datasets_root)
    first = shard.read_bytes()
    lift_module.lift_all(datasets_root)
    assert shard.read_bytes() == first
