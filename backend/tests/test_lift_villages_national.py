"""Tests for ``tools/boundaries/lift_villages_national.py``.

End-to-end with a tiny inline geojsonl fixture (no real network, no
real upstream archive). Validates:

* feature grouping by ``(state_lgd, dist_lgd)`` (well-keyed + unkeyed)
* per-(state, district) shard emission with byte-determinism across two runs
* ``BoundaryLayerRow`` shape (level, partition_path, layer_id,
  source_id, entity_state, entity_district, denominator invariants)
* stale-shard cleanup honours the keep-set
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(scope="module")
def lift_module() -> Any:
    """Import the lift script via its absolute path so pytest discovery
    works regardless of cwd. Side-effect: adds tools/boundaries/ +
    backend/ to sys.path (idempotent across tests).
    """
    repo_root = Path(__file__).resolve().parents[2]
    tools_dir = repo_root / "tools" / "boundaries"
    backend_dir = repo_root / "backend"
    for p in (tools_dir, backend_dir):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec_path = tools_dir / "lift_villages_national.py"
    spec = importlib.util.spec_from_file_location(
        "lift_villages_national",
        spec_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _feature(
    state_lgd: int | None,
    dist_lgd: int | None,
    village_lgd: int,
    vlgname: str,
    lon: float = 80.0,
    lat: float = 13.0,
) -> dict[str, Any]:
    """Minimal village feature (tiny 0.01×0.01 degree square polygon)."""
    props: dict[str, Any] = {
        "village_lgd": village_lgd,
        "vlgname": vlgname,
        "stname": "TEST",
        "dtname": "TestDist",
    }
    if state_lgd is not None:
        props["state_lgd"] = state_lgd
    if dist_lgd is not None:
        props["dist_lgd"] = dist_lgd
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [lon, lat],
                [lon + 0.01, lat],
                [lon + 0.01, lat + 0.01],
                [lon, lat + 0.01],
                [lon, lat],
            ]],
        },
    }


def _write_geojsonl(path: Path, features: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for f in features:
            fh.write(json.dumps(f, ensure_ascii=False))
            fh.write("\n")


def test_group_features_partitions_by_state_and_district(lift_module: Any) -> None:
    feats = [
        _feature(2, 50, 100, "A"),     # HP, district 50
        _feature(33, 568, 200, "B"),   # TN, district 568
        _feature(33, 568, 201, "C"),   # TN, district 568
        _feature(33, 569, 202, "D"),   # TN, district 569 (different)
        _feature(2, 50, 101, "E"),     # HP, district 50
    ]
    groups, unkeyed = lift_module.group_features_by_state_and_district(feats)
    assert set(groups) == {(2, 50), (33, 568), (33, 569)}
    assert len(groups[(2, 50)]) == 2
    assert len(groups[(33, 568)]) == 2
    assert len(groups[(33, 569)]) == 1
    assert unkeyed == []


def test_group_features_treats_missing_either_key_as_unkeyed(lift_module: Any) -> None:
    feats = [
        _feature(2, 50, 100, "A"),
        _feature(None, 50, 101, "B"),   # missing state_lgd
        _feature(2, None, 102, "C"),    # missing dist_lgd
        _feature(2, "", 103, "D"),      # empty string dist_lgd
    ]
    # _feature with empty-string dist_lgd isn't actually possible via
    # the helper (it sets ints), so build inline.
    feats.append({
        "type": "Feature",
        "properties": {"state_lgd": "", "dist_lgd": 50, "village_lgd": 999, "vlgname": "E"},
        "geometry": None,
    })
    groups, unkeyed = lift_module.group_features_by_state_and_district(feats)
    assert set(groups) == {(2, 50)}
    assert len(unkeyed) == 4


def test_group_features_coerces_string_state_and_district_to_int(lift_module: Any) -> None:
    """Upstream sometimes serialises lgd codes as numeric strings; we
    accept both and key the dict by int so the resolver lookup works.
    """
    feats = [
        {
            "type": "Feature",
            "properties": {
                "state_lgd": "33",
                "dist_lgd": "568",
                "village_lgd": 1,
                "vlgname": "x",
            },
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        },
        _feature(33, 568, 2, "y"),
    ]
    groups, unkeyed = lift_module.group_features_by_state_and_district(feats)
    assert set(groups) == {(33, 568)}
    assert len(groups[(33, 568)]) == 2
    assert unkeyed == []


def test_sort_features_deterministic_by_village_lgd_then_name(lift_module: Any) -> None:
    feats = [
        _feature(33, 568, 300, "C"),
        _feature(33, 568, 100, "A"),
        _feature(33, 568, 200, "B"),
        _feature(33, 568, 100, "A2"),  # tie on village_lgd, sort by vlgname
    ]
    out = lift_module.sort_features_deterministically(feats)
    keys = [(f["properties"]["village_lgd"], f["properties"]["vlgname"]) for f in out]
    assert keys == [(100, "A"), (100, "A2"), (200, "B"), (300, "C")]


def test_lift_emits_per_district_shards_and_returns_rows(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_Villages.geojsonl"
    feats = [
        _feature(33, 568, 100, "Adyar", lon=80.0, lat=13.0),
        _feature(33, 568, 101, "Mylapore", lon=80.2, lat=13.0),
        _feature(33, 569, 102, "Tambaram", lon=80.1, lat=12.9),
        _feature(2, 50, 200, "Bhattiyat", lon=76.0, lat=32.5),
        _feature(7, 10, 300, "ConnaughtPlace", lon=77.2, lat=28.6),  # Delhi
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {2: "S08", 33: "S22", 7: "U05"}

    rows = lift_module.lift_villages_to_per_district_shards(
        geojsonl, mapping, datasets_root,
    )
    # 1 row for HP-50, 2 rows for TN (568, 569), 1 for Delhi-10
    assert len(rows) == 4

    # rows in deterministic (state_lgd-int, district_lgd) order:
    # state_lgd 2 → S08/d=50, state_lgd 7 → U05/d=10,
    # state_lgd 33 → S22/d=568, S22/d=569.
    # The orchestrator iterates ``sorted(state_lgd_to_eci)`` (i.e. numeric
    # LGD order) so the U05 row precedes S22 even though ECI sort would
    # put S22 before U05.
    ordered = [(r.entity_state, r.entity_district) for r in rows]
    assert ordered == [
        ("S08", "50"),
        ("U05", "10"),
        ("S22", "568"),
        ("S22", "569"),
    ]

    tn_568 = next(r for r in rows if r.entity_state == "S22" and r.entity_district == "568")
    assert tn_568.retained_feature_count == 2
    assert tn_568.unkeyed_count == 0
    assert tn_568.original_feature_count == 2
    assert tn_568.level == "village"
    assert tn_568.partition_path == "boundaries/in/villages/state=in_s22/district=568/all.geojson"
    assert tn_568.layer_id == "boundaries.in.villages.state=in_s22.district=568"
    assert tn_568.simplification_algorithm == "coord-precision-round"
    assert tn_568.simplification_tolerance_deg == 10**-4

    # shards actually exist on disk
    for r in rows:
        assert (datasets_root / r.partition_path).is_file()
        assert (datasets_root / r.partition_path).stat().st_size == r.size_bytes


def test_lift_is_byte_deterministic(tmp_path: Path, lift_module: Any) -> None:
    """Two consecutive lifts of the same fixture produce byte-identical shards."""
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_Villages.geojsonl"
    feats = [
        _feature(33, 568, 100, "B"),
        _feature(33, 568, 99, "A"),
        _feature(33, 568, 101, "C"),
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    lift_module.lift_villages_to_per_district_shards(geojsonl, mapping, datasets_root)
    shard = datasets_root / "boundaries" / "in" / "villages" / "state=in_s22" / "district=568" / "all.geojson"
    sha1 = hashlib.sha256(shard.read_bytes()).hexdigest()

    # rerun against fresh datasets_root
    datasets_root2 = tmp_path / "datasets_v2"
    lift_module.lift_villages_to_per_district_shards(geojsonl, mapping, datasets_root2)
    shard2 = datasets_root2 / "boundaries" / "in" / "villages" / "state=in_s22" / "district=568" / "all.geojson"
    sha2 = hashlib.sha256(shard2.read_bytes()).hexdigest()

    assert sha1 == sha2, "byte-determinism broken — features must sort identically across runs"


def test_lift_warns_on_unknown_state_lgd(
    tmp_path: Path,
    lift_module: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Features with a state_lgd not in the ECI map are reported but do
    NOT crash the lift; they're not emitted as a shard.
    """
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_Villages.geojsonl"
    feats = [
        _feature(33, 568, 100, "Chennai-Vill"),
        _feature(999, 50, 200, "MysteryVill"),  # unknown state_lgd
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    rows = lift_module.lift_villages_to_per_district_shards(
        geojsonl, mapping, datasets_root,
    )
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "999" in captured.out
    # only TN shard emitted
    assert {r.entity_state for r in rows} == {"S22"}


def test_remove_stale_shards_deletes_only_non_keep_paths(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    """Verify the cleanup helper deletes shards not in the keep-set and
    opportunistically removes now-empty district= + state= parent dirs.
    """
    villages = tmp_path / "datasets" / "boundaries" / "in" / "villages"
    keep_dir = villages / "state=in_s22" / "district=568"
    keep_dir.mkdir(parents=True)
    (keep_dir / "all.geojson").write_text("{}", encoding="utf-8")

    stale_district = villages / "state=in_s22" / "district=999"
    stale_district.mkdir(parents=True)
    (stale_district / "all.geojson").write_text("{}", encoding="utf-8")

    stale_state = villages / "state=in_s08" / "district=50"
    stale_state.mkdir(parents=True)
    (stale_state / "all.geojson").write_text("{}", encoding="utf-8")

    deleted = lift_module.remove_stale_shards(
        villages,
        {"boundaries/in/villages/state=in_s22/district=568/all.geojson"},
    )
    assert deleted == 2
    assert (keep_dir / "all.geojson").is_file()
    assert not stale_district.exists()
    # state=in_s08 dir should be gone since it had only the one stale district
    assert not (villages / "state=in_s08").exists()


def test_remove_stale_shards_handles_missing_dir(tmp_path: Path, lift_module: Any) -> None:
    """No-op when the directory doesn't exist."""
    assert lift_module.remove_stale_shards(tmp_path / "nope", set()) == 0
