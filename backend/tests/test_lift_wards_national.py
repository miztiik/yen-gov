"""Tests for ``tools/boundaries/lift_wards_national.py``.

End-to-end with a tiny inline geojsonl fixture (no real network, no
real upstream archive). Validates:

* feature grouping by ``(state_lgd, ulb_lgd)`` (well-keyed + missing-
  either-key unkeyed + unknown state)
* per-(state, ulb) shard emission with byte-determinism across two
  runs
* ``BoundaryLayerRow`` shape (level='ward', partition_path carries
  ulb= segment, layer_id, source_id, entity_state + entity_city,
  denominator invariants)
* ``remove_stale_shards`` cleanup behaviour (nested two-level dirs)
* C.1.c inherited auto-fallback path from blocks (PR #443) +
  panchayats (PR #446): bucket exceeding budget at default precision
  re-emits at coarser precision before SKIP; the row carries the
  fallback tolerance.

Note: C.3.b live-lift first-snapshot revealed SBM_Wards uses
``statecode`` / ``ulbcode`` / ``wardcode`` / ``wardname`` (concatenated
lowercase per MoHUA's SBM Urban release format) — a third distinct
convention beyond the C.1.c blocks long-form (``state_lgd`` /
``dist_lgd``) and the C.2.b panchayats short-form (``st_lgd`` /
``dt_lgd``). The ``wardcode`` field is heterogeneous: mostly numeric
strings ("4", "7") plus a non-trivial minority of free-text labels
("Ward No 5", "WARD 12") — the sort helper handles both shapes via
a (numeric-first, text-second) two-cohort key. Fixtures + assertions
below mirror the discovered shape; both move together if a future
upstream release renames any property.
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
    spec_path = tools_dir / "lift_wards_national.py"
    spec = importlib.util.spec_from_file_location(
        "lift_wards_national",
        spec_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _feature(
    state_lgd: int | None,
    ulb_lgd: int | None,
    ward_code: int | str,
    ward_name: str,
    lon: float = 78.0,
    lat: float = 12.0,
) -> dict[str, Any]:
    """Minimal ward feature (1x1 degree square polygon)."""
    props: dict[str, Any] = {
        "wardcode": ward_code,
        "wardname": ward_name,
        "statename": "TEST",
        "ulbname": "TestULB",
    }
    if state_lgd is not None:
        props["statecode"] = state_lgd
    if ulb_lgd is not None:
        props["ulbcode"] = ulb_lgd
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


def test_group_features_by_state_and_ulb_partitions_and_collects_unkeyed(
    lift_module: Any,
) -> None:
    feats = [
        _feature(2, 802743, 1, "Ward 1"),     # HP / ulb=802743
        _feature(33, 800001, 1, "Ward 1"),    # TN / ulb=800001
        _feature(33, 800001, 2, "Ward 2"),    # TN / ulb=800001 (same bucket)
        _feature(33, 800002, 1, "Ward 1"),    # TN / ulb=800002 (different ULB)
        _feature(None, 802743, 99, "U1"),     # unkeyed (missing state_lgd)
        _feature(2, None, 99, "U2"),          # unkeyed (missing ulb_lgd)
        _feature(2, 802743, 2, "Ward 2"),     # HP / ulb=802743
    ]
    groups, unkeyed = lift_module.group_features_by_state_and_ulb(feats)
    assert set(groups) == {(2, 802743), (33, 800001), (33, 800002)}
    assert len(groups[(2, 802743)]) == 2
    assert len(groups[(33, 800001)]) == 2
    assert len(groups[(33, 800002)]) == 1
    assert len(unkeyed) == 2


def test_group_features_treats_empty_string_keys_as_unkeyed(lift_module: Any) -> None:
    feats = [
        _feature(2, 802743, 1, "A"),
        {
            "type": "Feature",
            "properties": {
                "statecode": "",
                "ulbcode": 802743,
                "wardcode": 1,
                "wardname": "x",
            },
            "geometry": None,
        },
        {
            "type": "Feature",
            "properties": {
                "statecode": 2,
                "ulbcode": "",
                "wardcode": 2,
                "wardname": "y",
            },
            "geometry": None,
        },
    ]
    groups, unkeyed = lift_module.group_features_by_state_and_ulb(feats)
    assert set(groups) == {(2, 802743)}
    assert len(unkeyed) == 2


def test_group_features_coerces_string_keys_to_int(lift_module: Any) -> None:
    """Upstream sometimes serialises both keys as numeric strings; we
    accept both and key the dict by int tuple so the resolver lookup works.
    """
    feats = [
        {
            "type": "Feature",
            "properties": {
                "statecode": "33",
                "ulbcode": "800001",
                "wardcode": 1,
                "wardname": "x",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            },
        },
        _feature(33, 800001, 2, "y"),
    ]
    groups, unkeyed = lift_module.group_features_by_state_and_ulb(feats)
    assert set(groups) == {(33, 800001)}
    assert len(groups[(33, 800001)]) == 2
    assert unkeyed == []


def test_sort_features_deterministic_by_ward_code_then_name(lift_module: Any) -> None:
    feats = [
        _feature(2, 802743, 3, "C"),
        _feature(2, 802743, 1, "A"),
        _feature(2, 802743, 2, "B"),
        _feature(2, 802743, 1, "A2"),  # tie on wardcode, sort by wardname
    ]
    out = lift_module.sort_features_deterministically(feats)
    keys = [(f["properties"]["wardcode"], f["properties"]["wardname"]) for f in out]
    assert keys == [(1, "A"), (1, "A2"), (2, "B"), (3, "C")]


def test_sort_features_handles_heterogeneous_wardcode(lift_module: Any) -> None:
    """SBM_Wards ``wardcode`` is heterogeneous (C.3.b first-snapshot
    finding): mostly numeric strings ("4", "7") but a non-trivial
    minority are free-text labels ("Ward No 5", "WARD 12"). The sort
    helper splits into two cohorts — numeric-castable codes first
    (sorted by int value), free-text codes second (sorted by str value)
    — so byte-determinism survives the heterogeneity.
    """
    feats = [
        _feature(2, 802743, "Ward No 5", "Z"),  # free-text cohort
        _feature(2, 802743, "3", "C"),  # numeric cohort (string)
        _feature(2, 802743, 1, "A"),  # numeric cohort (int)
        _feature(2, 802743, "WARD 12", "Y"),  # free-text cohort
        _feature(2, 802743, 2, "B"),  # numeric cohort
    ]
    out = lift_module.sort_features_deterministically(feats)
    keys = [f["properties"]["wardcode"] for f in out]
    # numeric cohort first (1, 2, 3); free-text cohort second ("WARD 12", "Ward No 5")
    assert keys == [1, 2, "3", "WARD 12", "Ward No 5"]


def test_lift_emits_per_ulb_shards_and_returns_rows(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "SBM_Wards.geojsonl"
    feats = [
        # TN/ULB=800001 — 2 wards
        _feature(33, 800001, 1, "Ward-1-Chennai", lon=80.0, lat=13.0),
        _feature(33, 800001, 2, "Ward-2-Chennai", lon=80.2, lat=13.1),
        # TN/ULB=800002 — 1 ward
        _feature(33, 800002, 1, "Ward-1-Vellore", lon=79.0, lat=12.9),
        # HP/ULB=802743 — 1 ward
        _feature(2, 802743, 1, "Ward-1-Shimla", lon=76.0, lat=32.5),
        # Delhi/ULB=801234 — 1 ward
        _feature(7, 801234, 1, "Ward-1-NDMC", lon=77.2, lat=28.6),
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {2: "S08", 33: "S22", 7: "U05"}

    rows = lift_module.lift_wards_to_per_ulb_shards(
        geojsonl, mapping, datasets_root,
    )
    # 4 shards: TN/800001 + TN/800002 + HP/802743 + Delhi/801234
    assert len(rows) == 4

    by_partition = {r.partition_path: r for r in rows}
    expected_paths = {
        "boundaries/in/wards/state=in_s22/ulb=800001/all.geojson",
        "boundaries/in/wards/state=in_s22/ulb=800002/all.geojson",
        "boundaries/in/wards/state=in_s08/ulb=802743/all.geojson",
        "boundaries/in/wards/state=in_u05/ulb=801234/all.geojson",
    }
    assert set(by_partition) == expected_paths

    chennai_row = by_partition[
        "boundaries/in/wards/state=in_s22/ulb=800001/all.geojson"
    ]
    assert chennai_row.retained_feature_count == 2
    assert chennai_row.original_feature_count == 2
    assert chennai_row.unkeyed_count == 0
    assert chennai_row.level == "ward"
    assert chennai_row.layer_id == "boundaries.in.wards.state=in_s22.ulb=800001"
    assert chennai_row.entity_state == "S22"
    assert chennai_row.entity_city == "800001"
    # entity_district MUST be None for ward rows — wards are ULB-keyed
    # not district-keyed (a ULB can span multiple districts per LGD).
    assert chennai_row.entity_district is None
    assert chennai_row.simplification_algorithm == "coord-precision-round"
    assert chennai_row.simplification_tolerance_deg == 10**-4

    # shards actually exist on disk
    for r in rows:
        assert (datasets_root / r.partition_path).is_file()
        assert (datasets_root / r.partition_path).stat().st_size == r.size_bytes


def test_lift_is_byte_deterministic(tmp_path: Path, lift_module: Any) -> None:
    """Two consecutive lifts of the same fixture produce byte-identical shards."""
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "SBM_Wards.geojsonl"
    feats = [
        _feature(33, 800001, 2, "B"),
        _feature(33, 800001, 1, "A"),
        _feature(33, 800001, 3, "C"),
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    lift_module.lift_wards_to_per_ulb_shards(geojsonl, mapping, datasets_root)
    shard = (
        datasets_root
        / "boundaries"
        / "in"
        / "wards"
        / "state=in_s22"
        / "ulb=800001"
        / "all.geojson"
    )
    sha1 = hashlib.sha256(shard.read_bytes()).hexdigest()

    # rerun against fresh datasets_root
    datasets_root2 = tmp_path / "datasets_v2"
    lift_module.lift_wards_to_per_ulb_shards(geojsonl, mapping, datasets_root2)
    shard2 = (
        datasets_root2
        / "boundaries"
        / "in"
        / "wards"
        / "state=in_s22"
        / "ulb=800001"
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
    geojsonl = tmp_path / "raw" / "SBM_Wards.geojsonl"
    feats = [
        _feature(33, 800001, 1, "Ward-1-Chennai"),
        _feature(999, 999999, 1, "MysteryWard"),  # unknown state_lgd
    ]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    rows = lift_module.lift_wards_to_per_ulb_shards(
        geojsonl, mapping, datasets_root
    )
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "999" in captured.out
    # only S22/800001 shard emitted
    assert {r.entity_state for r in rows} == {"S22"}


def test_remove_stale_shards_deletes_only_non_keep_paths(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    """Verify the cleanup helper deletes a shard whose partition_path is
    not in the keep-set. Mirrors test coverage of the panchayats lift's
    equivalent helper (with the additional ulb= dir cleanup).
    """
    wards = tmp_path / "datasets" / "boundaries" / "in" / "wards"
    (wards / "state=in_s22" / "ulb=800001").mkdir(parents=True)
    (wards / "state=in_s22" / "ulb=800001" / "all.geojson").write_text(
        "{}", encoding="utf-8"
    )
    (wards / "state=in_s22" / "ulb=800002").mkdir(parents=True)
    (wards / "state=in_s22" / "ulb=800002" / "all.geojson").write_text(
        "{}", encoding="utf-8"
    )
    (wards / "state=in_s08" / "ulb=802743").mkdir(parents=True)
    (wards / "state=in_s08" / "ulb=802743" / "all.geojson").write_text(
        "{}", encoding="utf-8"
    )

    # Keep only TN/800001; TN/800002 and HP/802743 are stale.
    deleted = lift_module.remove_stale_shards(
        wards,
        {"boundaries/in/wards/state=in_s22/ulb=800001/all.geojson"},
    )
    assert deleted == 2
    assert (wards / "state=in_s22" / "ulb=800001" / "all.geojson").is_file()
    assert not (wards / "state=in_s22" / "ulb=800002").exists()
    assert not (wards / "state=in_s08").exists()


def test_remove_stale_shards_handles_missing_dir(tmp_path: Path, lift_module: Any) -> None:
    """No-op when the directory doesn't exist."""
    assert lift_module.remove_stale_shards(tmp_path / "nope", set()) == 0


# ---------------------------------------------------------------------
# C.1.c auto-fallback path inherited verbatim (PR #443 + #446): over-
# budget bucket re-emits at coarser precision before SKIP. Asserts (a)
# the row's simplification_tolerance_deg reflects the fallback precision,
# (b) the shard size is smaller after fallback than at default precision,
# (c) the fallback log line names the (state, ulb).
# ---------------------------------------------------------------------


def test_lift_auto_fallback_when_bucket_exceeds_budget(
    tmp_path: Path,
    lift_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When a per-(state, ulb) shard exceeds SNAPSHOT_BYTE_BUDGET at
    the default coord_precision, the lift script must re-emit the
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
            "wardcode": 1,
            "wardname": "BigWard",
            "statecode": 33,
            "ulbcode": 800001,
            "statename": "TEST",
            "ulbname": "TestULB",
        },
        "geometry": {"type": "Polygon", "coordinates": [long_ring]},
    }

    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "SBM_Wards.geojsonl"
    _write_geojsonl(geojsonl, [feat])
    mapping = {33: "S22"}

    # First lift at default precision to measure the byte size.
    rows_p4 = lift_module.lift_wards_to_per_ulb_shards(
        geojsonl, mapping, datasets_root, coord_precision=4,
    )
    p4_size = rows_p4[0].size_bytes

    # Second lift at fallback precision to measure that size.
    rows_p3 = lift_module.lift_wards_to_per_ulb_shards(
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

    rows = lift_module.lift_wards_to_per_ulb_shards(
        geojsonl, mapping, tmp_path / "datasets_fb", coord_precision=4,
    )

    # Exactly one row emitted (fallback succeeded; no SKIP).
    assert len(rows) == 1
    row = rows[0]
    assert row.entity_state == "S22"
    assert row.entity_city == "800001"
    # Fallback precision = 4 - 1 = 3; tolerance = 10**-3 = 0.001.
    assert row.simplification_tolerance_deg == 10**-3
    # Shard exists on disk.
    assert (tmp_path / "datasets_fb" / row.partition_path).is_file()

    # Log line names the fallback transition AND the (state, ulb).
    captured = capsys.readouterr()
    assert "fallback to precision=3" in captured.out
    assert "S22" in captured.out
    assert "800001" in captured.out


def test_lift_skips_when_even_fallback_precision_exceeds_budget(
    tmp_path: Path,
    lift_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When even coord_precision=3 (one step coarser than default=4)
    fails the budget gate, the lift falls through to the existing SKIP
    branch: no row emitted, shard unlinked, parent ulb=<N>/ dir
    rmdir'd.
    """
    # Budget = 1 byte; even an empty-ish FeatureCollection exceeds it.
    monkeypatch.setattr(lift_module, "SNAPSHOT_BYTE_BUDGET", 1)

    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "SBM_Wards.geojsonl"
    feats = [_feature(33, 800001, 1, "Ward-1-Chennai")]
    _write_geojsonl(geojsonl, feats)
    mapping = {33: "S22"}

    rows = lift_module.lift_wards_to_per_ulb_shards(
        geojsonl, mapping, datasets_root, coord_precision=4,
    )

    # No row emitted; shard + empty ulb= dir cleaned up.
    assert rows == []
    shard = (
        datasets_root
        / "boundaries"
        / "in"
        / "wards"
        / "state=in_s22"
        / "ulb=800001"
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


def test_derive_hive_ulb_segment_in_partition_path(lift_module: Any) -> None:
    """The wards-kind partition path MUST carry both state=<slug>/ and
    ulb=<lgd>/ Hive segments. Regression test for the C.3.a derive_hive
    extension that added the ``ulb_lgd`` parameter alongside the
    existing ``district_lgd`` parameter (mutually exclusive per the
    ULB-keyed partition rationale).

    Slug-only partition contract (2026-06-09, Hans+Max+Gregor verdict):
    ``state_slug=`` carries the LGD-name slug verbatim
    (``"tamil-nadu"``, not ``"S22"``); the legacy ``state=in_<lc>``
    pre-2026-06-09 form is no longer produced.
    """
    from _paths import derive_hive  # noqa: PLC0415

    partition_path, layer_id = derive_hive(
        kind="wards",
        state_slug="tamil-nadu",
        ulb_lgd="800001",
    )
    assert partition_path == "boundaries/in/wards/state=tamil-nadu/ulb=800001/all.geojson"
    assert layer_id == "boundaries.in.wards.state=tamil-nadu.ulb=800001"
