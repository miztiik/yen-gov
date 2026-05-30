"""Tests for ``tools/boundaries/lift_panchayats_national.py``.

End-to-end with a tiny inline geojsonl fixture (no real network, no
real upstream archive). Validates:

* feature grouping by ``(st_lgd, dt_lgd)`` (well-keyed + missing-
  either-key unkeyed + unknown state)
* per-(state, district) shard emission with byte-determinism across
  two runs
* ``BoundaryLayerRow`` shape (level='panchayat', partition_path
  carries district= segment, layer_id, source_id, entity_state +
  entity_district, denominator invariants)
* ``remove_stale_shards`` cleanup behaviour (nested two-level dirs)
* C.2.b inherited auto-fallback path from C.1.c (PR #443): bucket
  exceeding budget at default precision re-emits at coarser precision
  before SKIP; the row carries the fallback tolerance.

Note: upstream LGD_Panchayats uses LGD short codes ``st_lgd`` / ``dt_lgd``
/ ``gp_code`` / ``gp_name`` rather than the longer convention used by
the blocks layer (``state_lgd`` / ``dist_lgd`` / ``block_lgd`` /
``block_name``). Fixtures + assertions below mirror the actual wire
schema confirmed in the C.2.b first-snapshot inspection (2026-05-30).
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
    spec_path = tools_dir / "lift_panchayats_national.py"
    spec = importlib.util.spec_from_file_location(
        "lift_panchayats_national",
        spec_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _feature(
    st_lgd: int | None,
    dt_lgd: int | None,
    gp_code: int,
    gp_name: str,
    lon: float = 78.0,
    lat: float = 12.0,
) -> dict[str, Any]:
    """Minimal panchayat feature (1x1 degree square polygon)."""
    props: dict[str, Any] = {
        "gp_code": gp_code,
        "gp_name": gp_name,
        "stname": "TEST",
        "dtname": "TestDist",
        "blklgdcode": "998",
        "blkname": "TestBlock",
    }
    if st_lgd is not None:
        props["st_lgd"] = st_lgd
    if dt_lgd is not None:
        props["dt_lgd"] = dt_lgd
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


def test_group_features_by_state_and_district_partitions_and_collects_unkeyed(
    lift_module: Any,
) -> None:
    feats = [
        _feature(2, 50, 100, "A"),       # HP / d=50
        _feature(33, 603, 200, "B"),     # TN / d=603
        _feature(33, 603, 201, "C"),     # TN / d=603 (same bucket as B)
        _feature(33, 604, 202, "D"),     # TN / d=604 (different district)
        _feature(None, 50, 300, "U1"),   # unkeyed (missing st_lgd)
        _feature(2, None, 301, "U2"),    # unkeyed (missing dt_lgd)
        _feature(2, 50, 101, "E"),       # HP / d=50
    ]
    groups, unkeyed = lift_module.group_features_by_state_and_district(feats)
    assert set(groups) == {(2, 50), (33, 603), (33, 604)}
    assert len(groups[(2, 50)]) == 2
    assert len(groups[(33, 603)]) == 2
    assert len(groups[(33, 604)]) == 1
    assert len(unkeyed) == 2


def test_group_features_treats_empty_string_keys_as_unkeyed(lift_module: Any) -> None:
    feats = [
        _feature(2, 50, 100, "A"),
        {
            "type": "Feature",
            "properties": {
                "st_lgd": "",
                "dt_lgd": 50,
                "gp_code": 1,
                "gp_name": "x",
            },
            "geometry": None,
        },
        {
            "type": "Feature",
            "properties": {
                "st_lgd": 2,
                "dt_lgd": "",
                "gp_code": 2,
                "gp_name": "y",
            },
            "geometry": None,
        },
    ]
    groups, unkeyed = lift_module.group_features_by_state_and_district(feats)
    assert set(groups) == {(2, 50)}
    assert len(unkeyed) == 2


def test_group_features_coerces_string_keys_to_int(lift_module: Any) -> None:
    """Upstream sometimes serialises both keys as numeric strings; we
    accept both and key the dict by int tuple so the resolver lookup works.
    """
    feats = [
        {
            "type": "Feature",
            "properties": {
                "st_lgd": "33",
                "dt_lgd": "603",
                "gp_code": 1,
                "gp_name": "x",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            },
        },
        _feature(33, 603, 2, "y"),
    ]
    groups, unkeyed = lift_module.group_features_by_state_and_district(feats)
    assert set(groups) == {(33, 603)}
    assert len(groups[(33, 603)]) == 2
    assert unkeyed == []


def test_sort_features_deterministic_by_panchayat_lgd_then_name(lift_module: Any) -> None:
    feats = [
        _feature(2, 50, 300, "C"),
        _feature(2, 50, 100, "A"),
        _feature(2, 50, 200, "B"),
        _feature(2, 50, 100, "A2"),  # tie on gp_code, sort by gp_name
    ]
    out = lift_module.sort_features_deterministically(feats)
    keys = [(f["properties"]["gp_code"], f["properties"]["gp_name"]) for f in out]
    assert keys == [(100, "A"), (100, "A2"), (200, "B"), (300, "C")]


def test_lift_emits_per_district_shards_and_returns_rows(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_panchayats.geojsonl"
    feats = [
        # TN/Chennai (d=603) — 2 GPs
        _feature(33, 603, 100, "Tiruvottiyur-GP", lon=80.0, lat=13.0),
        _feature(33, 603, 101, "Manali-GP", lon=80.2, lat=13.1),
        # TN/Vellore (d=604) — 1 GP
        _feature(33, 604, 102, "Katpadi-GP", lon=79.0, lat=12.9),
        # HP/Chamba (d=50) — 1 GP
        _feature(2, 50, 50, "Bhattiyat-GP", lon=76.0, lat=32.5),
        # Delhi/CentralDelhi (d=70) — 1 GP (note: Delhi has no GPs IRL;
        # fixture is synthetic for shard-emission test)
        _feature(7, 70, 10, "Connaught-GP", lon=77.2, lat=28.6),
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {2: "S08", 33: "S22", 7: "U05"}

    rows = lift_module.lift_panchayats_to_per_district_shards(
        geojsonl, mapping, datasets_root,
    )
    # 4 shards: TN/603 + TN/604 + HP/50 + Delhi/70
    assert len(rows) == 4

    by_partition = {r.partition_path: r for r in rows}
    expected_paths = {
        "boundaries/in/panchayats/state=in_s22/district=603/all.geojson",
        "boundaries/in/panchayats/state=in_s22/district=604/all.geojson",
        "boundaries/in/panchayats/state=in_s08/district=50/all.geojson",
        "boundaries/in/panchayats/state=in_u05/district=70/all.geojson",
    }
    assert set(by_partition) == expected_paths

    chennai_row = by_partition[
        "boundaries/in/panchayats/state=in_s22/district=603/all.geojson"
    ]
    assert chennai_row.retained_feature_count == 2
    assert chennai_row.original_feature_count == 2
    assert chennai_row.unkeyed_count == 0
    assert chennai_row.level == "panchayat"
    assert chennai_row.layer_id == "boundaries.in.panchayats.state=in_s22.district=603"
    assert chennai_row.entity_state == "S22"
    assert chennai_row.entity_district == "603"
    assert chennai_row.simplification_algorithm == "coord-precision-round"
    assert chennai_row.simplification_tolerance_deg == 10**-4

    # shards actually exist on disk
    for r in rows:
        assert (datasets_root / r.partition_path).is_file()
        assert (datasets_root / r.partition_path).stat().st_size == r.size_bytes


def test_lift_is_byte_deterministic(tmp_path: Path, lift_module: Any) -> None:
    """Two consecutive lifts of the same fixture produce byte-identical shards."""
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_panchayats.geojsonl"
    feats = [
        _feature(33, 603, 100, "B"),
        _feature(33, 603, 99, "A"),
        _feature(33, 603, 101, "C"),
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    lift_module.lift_panchayats_to_per_district_shards(geojsonl, mapping, datasets_root)
    shard = (
        datasets_root
        / "boundaries"
        / "in"
        / "panchayats"
        / "state=in_s22"
        / "district=603"
        / "all.geojson"
    )
    sha1 = hashlib.sha256(shard.read_bytes()).hexdigest()

    # rerun against fresh datasets_root
    datasets_root2 = tmp_path / "datasets_v2"
    lift_module.lift_panchayats_to_per_district_shards(geojsonl, mapping, datasets_root2)
    shard2 = (
        datasets_root2
        / "boundaries"
        / "in"
        / "panchayats"
        / "state=in_s22"
        / "district=603"
        / "all.geojson"
    )
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
    geojsonl = tmp_path / "raw" / "LGD_panchayats.geojsonl"
    feats = [
        _feature(33, 603, 100, "Tiruvottiyur-GP"),
        _feature(999, 999, 200, "MysteryGP"),  # unknown state_lgd
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    rows = lift_module.lift_panchayats_to_per_district_shards(
        geojsonl, mapping, datasets_root
    )
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "999" in captured.out
    # only S22/603 shard emitted
    assert {r.entity_state for r in rows} == {"S22"}


def test_remove_stale_shards_deletes_only_non_keep_paths(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    """Verify the cleanup helper deletes a shard whose partition_path is
    not in the keep-set. Mirrors test coverage of the villages lift's
    equivalent helper (with the additional district= dir cleanup).
    """
    panchayats = tmp_path / "datasets" / "boundaries" / "in" / "panchayats"
    (panchayats / "state=in_s22" / "district=603").mkdir(parents=True)
    (panchayats / "state=in_s22" / "district=603" / "all.geojson").write_text(
        "{}", encoding="utf-8"
    )
    (panchayats / "state=in_s22" / "district=604").mkdir(parents=True)
    (panchayats / "state=in_s22" / "district=604" / "all.geojson").write_text(
        "{}", encoding="utf-8"
    )
    (panchayats / "state=in_s08" / "district=50").mkdir(parents=True)
    (panchayats / "state=in_s08" / "district=50" / "all.geojson").write_text(
        "{}", encoding="utf-8"
    )

    # Keep only TN/603; TN/604 and HP/50 are stale.
    deleted = lift_module.remove_stale_shards(
        panchayats,
        {"boundaries/in/panchayats/state=in_s22/district=603/all.geojson"},
    )
    assert deleted == 2
    assert (panchayats / "state=in_s22" / "district=603" / "all.geojson").is_file()
    assert not (panchayats / "state=in_s22" / "district=604").exists()
    assert not (panchayats / "state=in_s08").exists()


def test_remove_stale_shards_handles_missing_dir(tmp_path: Path, lift_module: Any) -> None:
    """No-op when the directory doesn't exist."""
    assert lift_module.remove_stale_shards(tmp_path / "nope", set()) == 0


# ---------------------------------------------------------------------
# C.1.c auto-fallback path inherited verbatim (PR #443): over-budget
# bucket re-emits at coarser precision before SKIP. Asserts (a) the
# row's simplification_tolerance_deg reflects the fallback precision,
# (b) the shard size is smaller after fallback than at default
# precision, (c) the fallback log line names the (state, district).
# ---------------------------------------------------------------------


def test_lift_auto_fallback_when_bucket_exceeds_budget(
    tmp_path: Path,
    lift_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When a per-(state, district) shard exceeds SNAPSHOT_BYTE_BUDGET
    at the default coord_precision, the lift script must re-emit the
    bucket at the next coarser precision (coord_precision - 1) before
    falling through to SKIP. The resulting BoundaryLayerRow carries
    the fallback tolerance and the shard exists on disk.
    """
    # Build a many-vertex polygon with long-decimal coordinates so
    # precision=4 -> precision=3 rounding produces a meaningful byte-
    # size delta.
    long_ring = [[80.12345678 + i * 0.00001, 13.12345678 + i * 0.00001] for i in range(300)]
    long_ring.append(long_ring[0])  # close ring
    feat = {
        "type": "Feature",
        "properties": {
            "gp_code": 100,
            "gp_name": "BigGP",
            "st_lgd": 33,
            "dt_lgd": 603,
            "stname": "TEST",
            "dtname": "TestDist",
            "blklgdcode": "998",
            "blkname": "TestBlock",
        },
        "geometry": {"type": "Polygon", "coordinates": [long_ring]},
    }

    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_panchayats.geojsonl"
    _write_geojsonl(geojsonl, [feat])
    mapping = {33: "S22"}

    # First lift at default precision to measure the byte size.
    rows_p4 = lift_module.lift_panchayats_to_per_district_shards(
        geojsonl, mapping, datasets_root, coord_precision=4,
    )
    p4_size = rows_p4[0].size_bytes

    # Second lift at fallback precision to measure that size.
    rows_p3 = lift_module.lift_panchayats_to_per_district_shards(
        geojsonl, mapping, tmp_path / "datasets_p3", coord_precision=3,
    )
    p3_size = rows_p3[0].size_bytes
    # Sanity: precision=3 must produce a strictly smaller shard than
    # precision=4 for this fixture.
    assert p3_size < p4_size, (
        f"fixture too small to exercise fallback: p4={p4_size}, p3={p3_size}"
    )

    # Set budget to a value strictly between p3 and p4 sizes so:
    #   - default precision=4 emit trips the breach,
    #   - fallback precision=3 emit fits and ships.
    monkeypatch.setattr(
        lift_module, "SNAPSHOT_BYTE_BUDGET", (p4_size + p3_size) // 2,
    )

    rows = lift_module.lift_panchayats_to_per_district_shards(
        geojsonl, mapping, tmp_path / "datasets_fb", coord_precision=4,
    )

    # Exactly one row emitted (fallback succeeded; no SKIP).
    assert len(rows) == 1
    row = rows[0]
    assert row.entity_state == "S22"
    assert row.entity_district == "603"
    # Fallback precision = 4 - 1 = 3; tolerance = 10**-3 = 0.001.
    assert row.simplification_tolerance_deg == 10**-3
    # Shard exists on disk.
    assert (tmp_path / "datasets_fb" / row.partition_path).is_file()

    # Log line names the fallback transition AND the (state, district).
    captured = capsys.readouterr()
    assert "fallback to precision=3" in captured.out
    assert "S22" in captured.out
    assert "603" in captured.out


def test_lift_skips_when_even_fallback_precision_exceeds_budget(
    tmp_path: Path,
    lift_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When even coord_precision=3 (one step coarser than default=4)
    fails the budget gate, the lift falls through to the existing SKIP
    branch: no row emitted, shard unlinked, parent district=<N>/ dir
    rmdir'd.
    """
    # Budget = 1 byte; even an empty-ish FeatureCollection exceeds it.
    monkeypatch.setattr(lift_module, "SNAPSHOT_BYTE_BUDGET", 1)

    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "LGD_panchayats.geojsonl"
    feats = [_feature(33, 603, 100, "Tiruvottiyur-GP")]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    rows = lift_module.lift_panchayats_to_per_district_shards(
        geojsonl, mapping, datasets_root, coord_precision=4,
    )

    # No row emitted; shard + empty district= dir cleaned up.
    assert rows == []
    shard = (
        datasets_root
        / "boundaries"
        / "in"
        / "panchayats"
        / "state=in_s22"
        / "district=603"
        / "all.geojson"
    )
    assert not shard.exists()
    assert not shard.parent.exists()

    captured = capsys.readouterr()
    # Both the fallback-attempt line AND the eventual SKIP line should
    # appear, in that order, so a future operator reading logs sees the
    # full escalation trail.
    assert "fallback to precision=3" in captured.out
    assert "even at precision=3" in captured.out
