"""Tests for ``tools/boundaries/lift_villages_jk_bhuvan.py``.

End-to-end with a tiny inline geojsonl fixture (no real network, no
real upstream archive). Validates:

* feature grouping by Census-2011 ``DIST_NAME``
* Census-2011 -> modern (eci_state, slug) mapping (incl. U08/U09 split)
* per-(state, district-slug) shard emission with byte-determinism
* ``BoundaryLayerRow`` shape (level=village, slug-keyed entity_district,
  ramseraph_bhuvan_jk_villages source_id, denominator invariants)
* unkeyed-warning + skip behaviour for unknown DIST_NAME values
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
    spec_path = tools_dir / "lift_villages_jk_bhuvan.py"
    spec = importlib.util.spec_from_file_location(
        "lift_villages_jk_bhuvan",
        spec_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _feature(
    dist_name: str | None,
    vid: str,
    name: str,
    lon: float = 75.0,
    lat: float = 33.5,
) -> dict[str, Any]:
    """Minimal Bhuvan-J&K-style village feature (tiny 0.01x0.01 square)."""
    props: dict[str, Any] = {
        "STAT_NAME": "JK",
        "VID": vid,
        "NAME": name,
        "VILL_CODE": vid[-8:],
    }
    if dist_name is not None:
        props["DIST_NAME"] = dist_name
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


def test_census2011_district_mapping_has_14_entries(lift_module: Any) -> None:
    """Lock the Census-2011 district name list — adding/removing keys
    must be a deliberate code change reviewed against upstream.
    """
    mapping = lift_module.CENSUS2011_DISTRICT_TO_MODERN
    assert len(mapping) == 14
    # All keys are the literal Census-2011 names observed in the
    # 2026-05-30 probe of Bhuvan_JK_Villages.geojsonl.
    expected = {
        "Anantnag", "Badgam", "Baramula", "Doda", "Jammu", "Kargil",
        "Kathua", "Kupwara", "Ladakh (leh)", "Pulwama", "Punch",
        "Rajauri", "Srinagar", "Udhampur",
    }
    assert set(mapping) == expected


def test_census2011_district_mapping_routes_ladakh_pair_to_u09(lift_module: Any) -> None:
    """The 2019 J&K Reorganisation Act split Ladakh out as U09.
    Census-2011 ``Kargil`` + ``Ladakh (leh)`` must route to U09.
    """
    mapping = lift_module.CENSUS2011_DISTRICT_TO_MODERN
    assert mapping["Kargil"] == ("U09", "kargil")
    assert mapping["Ladakh (leh)"] == ("U09", "ladakh_leh")
    # All others route to U08 J&K UT.
    u08_count = sum(1 for state, _slug in mapping.values() if state == "U08")
    u09_count = sum(1 for state, _slug in mapping.values() if state == "U09")
    assert u08_count == 12
    assert u09_count == 2


def test_census2011_slugs_satisfy_layer_id_regex(lift_module: Any) -> None:
    """Slugs go into ``district=<slug>`` which must match the
    boundary-layers.schema.json layer_id regex ``[a-z0-9_]+``.
    """
    import re
    pat = re.compile(r"^[a-z0-9_]+$")
    for _name, (_state, slug) in lift_module.CENSUS2011_DISTRICT_TO_MODERN.items():
        assert pat.match(slug), f"slug {slug!r} does not match [a-z0-9_]+"


def test_group_features_buckets_by_dist_name(lift_module: Any) -> None:
    feats = [
        _feature("Anantnag", "010600040001000A", "Vill A1"),
        _feature("Anantnag", "010600040001000B", "Vill A2"),
        _feature("Kargil", "010700010001000A", "Vill K1"),
        _feature("Srinagar", "010500010001000A", "Vill S1"),
    ]
    groups, unkeyed = lift_module.group_features_by_district(feats)
    assert set(groups) == {"Anantnag", "Kargil", "Srinagar"}
    assert len(groups["Anantnag"]) == 2
    assert unkeyed == []


def test_group_features_treats_missing_or_unknown_dist_name_as_unkeyed(
    lift_module: Any,
) -> None:
    feats = [
        _feature("Anantnag", "AAA", "vill"),
        _feature(None, "BBB", "missing-dist"),
        _feature("Atlantis", "CCC", "unknown-dist"),  # not in mapping
        _feature("", "DDD", "empty-dist"),
    ]
    groups, unkeyed = lift_module.group_features_by_district(feats)
    assert set(groups) == {"Anantnag"}
    assert len(unkeyed) == 3


def test_sort_features_deterministic_by_vid_then_name(lift_module: Any) -> None:
    feats = [
        _feature("Anantnag", "0106000400251400", "Cherry"),
        _feature("Anantnag", "0106000400251000", "Apple"),
        _feature("Anantnag", "0106000400251200", "Banana"),
        _feature("Anantnag", "0106000400251000", "Apple2"),  # tie on VID
    ]
    out = lift_module.sort_features_deterministically(feats)
    vids = [f["properties"]["VID"] for f in out]
    names = [f["properties"]["NAME"] for f in out]
    assert vids == [
        "0106000400251000",
        "0106000400251000",
        "0106000400251200",
        "0106000400251400",
    ]
    assert names[:2] == ["Apple", "Apple2"]  # secondary key by NAME on VID tie


def test_lift_emits_per_district_shards_for_u08_and_u09(
    tmp_path: Path,
    lift_module: Any,
) -> None:
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "Bhuvan_JK_Villages.geojsonl"
    feats = [
        _feature("Anantnag", "0106000400000001", "Vill A1", lon=75.1, lat=33.7),
        _feature("Anantnag", "0106000400000002", "Vill A2", lon=75.2, lat=33.7),
        _feature("Srinagar", "0105000100000001", "Vill S1", lon=74.8, lat=34.0),
        _feature("Kargil", "0107000100000001", "Vill K1", lon=76.0, lat=34.5),
        _feature("Ladakh (leh)", "0108000100000001", "Vill L1", lon=77.5, lat=34.1),
    ]
    _write_geojsonl(geojsonl, feats)

    rows = lift_module.lift_jk_villages_to_per_district_shards(
        geojsonl, datasets_root,
    )
    # 2 U08 districts (Anantnag, Srinagar) + 2 U09 districts (Kargil, Ladakh (leh)) = 4 shards
    assert len(rows) == 4

    # rows in deterministic (state, slug) order: U08 first, then U09.
    ordered = [(r.entity_state, r.entity_district) for r in rows]
    assert ordered == [
        ("U08", "anantnag"),
        ("U08", "srinagar"),
        ("U09", "kargil"),
        ("U09", "ladakh_leh"),
    ]

    anantnag = next(r for r in rows if r.entity_district == "anantnag")
    assert anantnag.retained_feature_count == 2
    assert anantnag.unkeyed_count == 0
    assert anantnag.original_feature_count == 2
    assert anantnag.level == "village"
    assert anantnag.entity_state == "U08"
    assert anantnag.partition_path == "boundaries/in/villages/state=in_u08/district=anantnag/all.geojson"
    assert anantnag.layer_id == "boundaries.in.villages.state=in_u08.district=anantnag"
    assert anantnag.simplification_algorithm == "coord-precision-round"
    assert anantnag.simplification_tolerance_deg == 10**-4

    ladakh = next(r for r in rows if r.entity_district == "ladakh_leh")
    assert ladakh.entity_state == "U09"
    assert ladakh.partition_path == "boundaries/in/villages/state=in_u09/district=ladakh_leh/all.geojson"

    # All rows carry the new ramseraph_bhuvan_jk_villages source_id.
    expected_source_id = lift_module.BOUNDARY_SOURCE_ID_BY_NICKNAME[
        lift_module.SOURCE_NICKNAME
    ]
    assert all(r.source_id == expected_source_id for r in rows)

    # shards actually exist on disk
    for r in rows:
        assert (datasets_root / r.partition_path).is_file()
        assert (datasets_root / r.partition_path).stat().st_size == r.size_bytes


def test_lift_is_byte_deterministic(tmp_path: Path, lift_module: Any) -> None:
    """Two consecutive lifts of the same fixture produce byte-identical shards."""
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "Bhuvan_JK_Villages.geojsonl"
    feats = [
        _feature("Anantnag", "0106000400000003", "Cherry"),
        _feature("Anantnag", "0106000400000001", "Apple"),
        _feature("Anantnag", "0106000400000002", "Banana"),
    ]
    _write_geojsonl(geojsonl, feats)

    lift_module.lift_jk_villages_to_per_district_shards(geojsonl, datasets_root)
    shard = datasets_root / "boundaries" / "in" / "villages" / "state=in_u08" / "district=anantnag" / "all.geojson"
    sha1 = hashlib.sha256(shard.read_bytes()).hexdigest()

    # rerun against fresh datasets_root
    datasets_root2 = tmp_path / "datasets_v2"
    lift_module.lift_jk_villages_to_per_district_shards(geojsonl, datasets_root2)
    shard2 = datasets_root2 / "boundaries" / "in" / "villages" / "state=in_u08" / "district=anantnag" / "all.geojson"
    sha2 = hashlib.sha256(shard2.read_bytes()).hexdigest()

    assert sha1 == sha2, "byte-determinism broken — features must sort identically across runs"


def test_lift_warns_on_unknown_dist_name(
    tmp_path: Path,
    lift_module: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Features with a DIST_NAME not in CENSUS2011_DISTRICT_TO_MODERN
    are reported but do NOT crash the lift; they're not emitted as a shard.
    """
    datasets_root = tmp_path / "datasets"
    geojsonl = tmp_path / "raw" / "Bhuvan_JK_Villages.geojsonl"
    feats = [
        _feature("Anantnag", "AAA", "real"),
        _feature("Atlantis", "BBB", "mystery"),  # unknown dist
    ]
    _write_geojsonl(geojsonl, feats)

    rows = lift_module.lift_jk_villages_to_per_district_shards(
        geojsonl, datasets_root,
    )
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "Atlantis" in captured.out
    # only Anantnag shard emitted
    assert {r.entity_district for r in rows} == {"anantnag"}


def test_source_id_is_registered_in_seed(lift_module: Any) -> None:
    """The SOURCE_NICKNAME constant must resolve to a real source_id via
    the canonical seed — fail loudly if the seed entry got pruned.
    """
    nick = lift_module.SOURCE_NICKNAME
    assert nick == "ramseraph_bhuvan_jk_villages"
    assert nick in lift_module.BOUNDARY_SOURCE_ID_BY_NICKNAME
    sid = lift_module.BOUNDARY_SOURCE_ID_BY_NICKNAME[nick]
    # source_ids follow the pattern src-<12 hex chars>
    import re
    assert re.match(r"^src-[a-z0-9]{12}$", sid), f"unexpected source_id shape: {sid}"
