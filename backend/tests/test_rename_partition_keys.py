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
    """Forward-guard against accidental re-introduction of legacy
    ``state=in_sXX`` / ``state=in_uXX`` partitions under ``datasets/``.

    Historically (pre-2026-06 boundary slug rename) this test asserted
    ``len(pairs) >= 36`` to prove every legacy partition resolved via
    ``lgd_states.json``. The rename completed across PR #856 (G31
    derive_hive universal state_slug) + PR #562 (M2 LGD-name slug
    rename, ADR-0050), so ``discover()`` against the real corpus now
    returns zero pairs. The assertion is inverted to ``len(pairs) == 0``
    so any future PR that accidentally writes a legacy-shaped
    partition under ``datasets/`` fails this test loudly.

    The slug_re check below stays in place as a defensive sanity gate:
    if a legacy partition IS re-introduced and discover() finds it, the
    derived ``new.name`` should still be a kebab-case slug
    (``state=tamil-nadu`` etc.), not a malformed value.
    """
    slug_map = rpk._load_slug_map()
    real_root = rpk.REPO / "datasets"
    pairs = rpk.discover(real_root, slug_map)
    # Rename complete as of 2026-06 sweep; forward guard.
    assert len(pairs) == 0, (
        f"found {len(pairs)} legacy state=in_sXX/in_uXX partitions under "
        "datasets/; rename completed at PR #856 + PR #562 (ADR-0050) so "
        "this should be zero. A non-zero result means a PR accidentally "
        "re-introduced a legacy-shaped partition."
    )
    # Every pair (if any future regression occurs) resolves to kebab-case
    import re as _re
    slug_re = _re.compile(r"^state=[a-z0-9]+(-[a-z0-9]+)*$")
    assert all(slug_re.match(p.new.name) for p in pairs)
