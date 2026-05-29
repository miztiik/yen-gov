"""Tests for ``tools/boundaries/lift_blocks_national.py``.

End-to-end with a tiny inline geojsonl fixture (no real network, no
real upstream archive). Validates:

* feature grouping by ``state_lgd`` (well-keyed + unkeyed + unknown)
* per-state shard emission with byte-determinism across two runs
* ``BoundaryLayerRow`` shape (level='block', partition_path,
  layer_id, source_id, entity_state, denominator invariants)
* ``remove_stale_shards`` cleanup behaviour
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
    spec_path = tools_dir / "lift_blocks_national.py"
    spec = importlib.util.spec_from_file_location(
        "lift_blocks_national",
        spec_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _feature(
    state_lgd: int | None,
    block_lgd: int,
    block_name: str,
    lon: float = 78.0,
    lat: float = 12.0,
) -> dict[str, Any]:
    """Minimal block feature (1x1 degree square polygon)."""
    props: dict[str, Any] = {
        "block_lgd": block_lgd,
        "block_name": block_name,
        "stname": "TEST",
        "dist_lgd": 999,
        "dtname": "TestDist",
        "sdname": "TestSubdist",
        "sd_lgd": 998,
    }
    if state_lgd is not None:
        props["state_lgd"] = state_lgd
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [lon, lat],
                [lon + 1, lat],
                [lon + 1, lat + 1],
                [lon, lat + 1],
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


def test_group_features_by_state_lgd_partitions_and_collects_unkeyed(lift_module: Any) -> None:
    feats = [
        _feature(2, 100, "A"),     # HP
        _feature(33, 200, "B"),    # TN
        _feature(33, 201, "C"),    # TN
        _feature(None, 300, "U"),  # unkeyed
        _feature(2, 101, "D"),     # HP
    ]
    groups, unkeyed = lift_module.group_features_by_state_lgd(feats)
    assert set(groups) == {2, 33}
    assert len(groups[2]) == 2
    assert len(groups[33]) == 2
    assert len(unkeyed) == 1


def test_group_features_treats_empty_string_state_lgd_as_unkeyed(lift_module: Any) -> None:
    feats = [
        _feature(2, 100, "A"),
        {
            "type": "Feature",
            "properties": {"state_lgd": "", "block_lgd": 1, "block_name": "x"},
            "geometry": None,
        },
    ]
    groups, unkeyed = lift_module.group_features_by_state_lgd(feats)
    assert set(groups) == {2}
    assert len(unkeyed) == 1


def test_group_features_coerces_string_state_lgd_to_int(lift_module: Any) -> None:
    """Upstream sometimes serialises state_lgd as a numeric string; we
    accept both and key the dict by int so the resolver lookup works.
    """
    feats = [
        {
            "type": "Feature",
            "properties": {"state_lgd": "33", "block_lgd": 1, "block_name": "x"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            },
        },
        _feature(33, 2, "y"),
    ]
    groups, unkeyed = lift_module.group_features_by_state_lgd(feats)
    assert set(groups) == {33}
    assert len(groups[33]) == 2
    assert unkeyed == []


def test_sort_features_deterministic_by_block_lgd_then_name(lift_module: Any) -> None:
    feats = [
        _feature(2, 300, "C"),
        _feature(2, 100, "A"),
        _feature(2, 200, "B"),
        _feature(2, 100, "A2"),  # tie on block_lgd, sort by block_name
    ]
    out = lift_module.sort_features_deterministically(feats)
    keys = [(f["properties"]["block_lgd"], f["properties"]["block_name"]) for f in out]
    assert keys == [(100, "A"), (100, "A2"), (200, "B"), (300, "C")]


def test_lift_emits_per_state_shards_and_returns_rows(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_Blocks.geojsonl"
    feats = [
        _feature(33, 100, "Chennai-Block", lon=80.0, lat=13.0),
        _feature(33, 101, "Mylapore-Block", lon=80.2, lat=13.1),
        _feature(2, 50, "Bhattiyat-Block", lon=76.0, lat=32.5),
        _feature(7, 10, "Connaught-Block", lon=77.2, lat=28.6),  # Delhi
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {2: "S08", 33: "S22", 7: "U05"}

    rows = lift_module.lift_blocks_to_per_state_shards(
        geojsonl, mapping, datasets_root,
    )
    assert len(rows) == 3

    # one shard per state, in deterministic ECI order (S08, S22, U05)
    by_state = {r.entity_state: r for r in rows}
    assert set(by_state) == {"S08", "S22", "U05"}

    tn_row = by_state["S22"]
    assert tn_row.retained_feature_count == 2
    assert tn_row.unkeyed_count == 0
    assert tn_row.original_feature_count == 2
    assert tn_row.level == "block"
    assert tn_row.partition_path == "boundaries/in/blocks/state=in_s22/all.geojson"
    assert tn_row.layer_id == "boundaries.in.blocks.state=in_s22"
    assert tn_row.simplification_algorithm == "coord-precision-round"
    assert tn_row.simplification_tolerance_deg == 10**-3

    # shards actually exist on disk
    for r in rows:
        assert (datasets_root / r.partition_path).is_file()
        assert (datasets_root / r.partition_path).stat().st_size == r.size_bytes


def test_lift_is_byte_deterministic(tmp_path: Path, lift_module: Any) -> None:
    """Two consecutive lifts of the same fixture produce byte-identical shards."""
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_Blocks.geojsonl"
    feats = [
        _feature(33, 100, "B"),
        _feature(33, 99, "A"),
        _feature(33, 101, "C"),
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    lift_module.lift_blocks_to_per_state_shards(geojsonl, mapping, datasets_root)
    shard = datasets_root / "boundaries" / "in" / "blocks" / "state=in_s22" / "all.geojson"
    sha1 = hashlib.sha256(shard.read_bytes()).hexdigest()

    # rerun against fresh datasets_root
    datasets_root2 = tmp_path / "datasets_v2"
    lift_module.lift_blocks_to_per_state_shards(geojsonl, mapping, datasets_root2)
    shard2 = datasets_root2 / "boundaries" / "in" / "blocks" / "state=in_s22" / "all.geojson"
    sha2 = hashlib.sha256(shard2.read_bytes()).hexdigest()

    assert sha1 == sha2, "byte-determinism broken - features must sort identically across runs"


def test_lift_warns_on_unknown_state_lgd(
    tmp_path: Path,
    lift_module: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Features with a state_lgd that's not in the ECI map are reported
    but do NOT crash the lift; they're not emitted as a shard.
    """
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_Blocks.geojsonl"
    feats = [
        _feature(33, 100, "Chennai-Block"),
        _feature(999, 200, "MysteryBlock"),  # unknown state_lgd
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    rows = lift_module.lift_blocks_to_per_state_shards(geojsonl, mapping, datasets_root)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "999" in captured.out
    # only S22 shard emitted
    assert {r.entity_state for r in rows} == {"S22"}


def test_remove_stale_shards_deletes_only_non_keep_paths(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    """Verify the cleanup helper deletes a shard whose partition_path is
    not in the keep-set. Mirrors test coverage of the subdistricts lift's
    equivalent helper.
    """
    blocks = tmp_path / "datasets" / "boundaries" / "in" / "blocks"
    (blocks / "state=in_s22").mkdir(parents=True)
    (blocks / "state=in_s22" / "all.geojson").write_text("{}", encoding="utf-8")
    (blocks / "state=in_s08").mkdir(parents=True)
    (blocks / "state=in_s08" / "all.geojson").write_text("{}", encoding="utf-8")

    # Keep only S22; S08 is stale.
    deleted = lift_module.remove_stale_shards(
        blocks,
        {"boundaries/in/blocks/state=in_s22/all.geojson"},
    )
    assert deleted == 1
    assert (blocks / "state=in_s22" / "all.geojson").is_file()
    assert not (blocks / "state=in_s08").exists()


def test_remove_stale_shards_handles_missing_dir(tmp_path: Path, lift_module: Any) -> None:
    """No-op when the directory doesn't exist."""
    assert lift_module.remove_stale_shards(tmp_path / "nope", set()) == 0
