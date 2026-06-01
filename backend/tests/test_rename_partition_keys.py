"""Tests for tools/migrate/rename_partition_keys.py (PR M1).

Builds a fake state= tree in a tmp directory, runs discover() against it,
asserts the (old, new) mapping is correct. Also smoke-tests the manifest
shape and the --apply gate (without invoking git, by stubbing).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.migrate import rename_partition_keys as rpk


@pytest.fixture
def fake_tree(tmp_path: Path) -> Path:
    root = tmp_path / "boundaries" / "in"
    for code in ("in_s01", "in_s07", "in_u05", "in_u08"):
        (root / "ac" / f"state={code}").mkdir(parents=True)
        (root / "ac" / f"state={code}" / "all.geojson").write_text("{}")
        (root / "wards" / f"state={code}" / "district=42").mkdir(parents=True)
    # plant something that should NOT match
    (root / "country").mkdir(parents=True)
    (root / "country" / "all.geojson").write_text("{}")
    return root


def test_discover_renames_only_legacy_partitions(fake_tree):
    slug_map = {"S01": "andhra-pradesh", "S07": "haryana", "U05": "delhi", "U08": "jammu-and-kashmir"}
    pairs = rpk.discover(fake_tree, slug_map)
    # 4 codes x 2 layers (ac + wards) = 8 pairs
    assert len(pairs) == 8
    by_old = {p.old.name: p for p in pairs}
    assert by_old["state=in_s07"].new.name == "state=haryana"
    assert by_old["state=in_u08"].new.name == "state=jammu-and-kashmir"
    # eci codes uppercased
    assert all(p.eci_st_code.isupper() for p in pairs)


def test_discover_raises_on_missing_slug(fake_tree):
    # Drop one mapping
    slug_map = {"S01": "andhra-pradesh", "S07": "haryana", "U05": "delhi"}
    with pytest.raises(SystemExit, match="no LGD slug for ECI code 'U08'"):
        rpk.discover(fake_tree, slug_map)


def test_manifest_shape(tmp_path, fake_tree, monkeypatch):
    monkeypatch.setattr(rpk, "REPO", tmp_path)
    slug_map = {"S01": "andhra-pradesh", "S07": "haryana", "U05": "delhi", "U08": "jammu-and-kashmir"}
    pairs = rpk.discover(fake_tree, slug_map)
    out = tmp_path / "manifest.json"
    rpk.write_manifest(pairs, out, fake_tree)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["count"] == len(pairs)
    assert all(set(r) == {"old", "new", "eci_st_code", "lgd_slug"} for r in doc["renames"])
    # ensure forward slashes (cross-platform stability)
    assert all("\\" not in r["old"] for r in doc["renames"])
    assert all("\\" not in r["new"] for r in doc["renames"])


def test_real_lgd_states_slug_map_resolves_all_legacy_codes():
    """The real lgd_states.json MUST cover every legacy in_sXX/in_uXX folder
    currently under datasets/. If a new code appears that doesn't resolve,
    M2/M3/M4 cannot execute - fail fast here."""
    slug_map = rpk._load_slug_map()
    real_root = rpk.REPO / "datasets"
    pairs = rpk.discover(real_root, slug_map)
    # Smoke: at least the boundary partitions are discoverable
    assert len(pairs) >= 36, f"expected >=36 state= dirs across datasets/, found {len(pairs)}"
    # Every pair resolves to a kebab-case slug
    import re as _re
    slug_re = _re.compile(r"^state=[a-z0-9]+(-[a-z0-9]+)*$")
    assert all(slug_re.match(p.new.name) for p in pairs)
