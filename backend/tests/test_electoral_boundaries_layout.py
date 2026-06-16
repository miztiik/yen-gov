"""Layout gate for the electoral boundary subtree (G10).

Per G10 of TODO/20260603-data-and-charting-platform-reset-plan.md section 4
EL2 (2026-06-09), electoral constituency geometry was moved out of the admin
spine at ``datasets/boundaries/in/{ac,pc}/...`` into a peer subtree at
``datasets/boundaries/electoral/delim=<year>/<grain>/...`` so each ECI
Delimitation Commission Order publishes its own coexisting boundary set.

The grammar is asymmetric on purpose:

* **AC** uses ``delim=<year>/ac/state=<slug>/all.{geojson,topojson}`` -- a
  per-state shard tree because Assembly Constituencies are defined within
  state legislatures and the per-state shards keep the citizen-facing page
  load bounded.
* **PC** uses ``delim=<year>/pc/all.{geojson,topojson}`` -- a single
  country-wide file because Parliamentary Constituencies span the whole
  Union and are not state-partitioned in the canonical store.

This module asserts the on-disk layout matches the locked grammar so a
future PR cannot silently demote either subtree back into the admin spine
without test signal, and so the ``delim=2026`` reservation stays committed
(both ``.gitkeep`` files in place, awaiting the next ECI Delimitation
Order ingest).

Layout snapshot at G10 closing (2026-06-09):

* ``delim=2008/ac/state=<slug>/all.{geojson,topojson}`` -- 31 state subtrees
  (62 files) covering the post-2008 Delim baseline that 30 of 31 states use.
* ``delim=2024/pc/all.{geojson,topojson}`` -- the national 2024-Delim PC
  layer (1 country-wide file pair).
* ``delim=2026/{ac,pc}/.gitkeep`` -- reserved for the next ECI Delimitation
  Order; placeholders prove the directory shape is intentional.

The symmetric inverse upstream gaps (delim=2008 PC, delim=2024 AC) are
out of G10 scope; new electoral ingests land alongside the existing
subtrees by appending fresh ``delim=<year>/{ac,pc}/`` rows under the same
grammar.

RIP UPDATE (Row 3, TODO/20260616-map-geometry-rip-and-palette-plan.md,
2026-06-16): the multi-vintage layout above was RIPPED to a SINGLE 2024
vintage. AC is now ONE national TopoJSON ``delim=2024/ac/all.topojson``
(object ``ac``, each feature stamped ``state_ut_code``; the 31 per-state
delim=2008 shards were consolidated + deleted). PC stays ONE national
GeoJSON ``delim=2024/pc/all.geojson``. The ``delim=2008`` + ``delim=2026``
trees were DELETED - the single 2024 snapshot carries every delimitation
era via the dual-key join + the ``delim_year`` baked into each unit_id.
The tests below assert the post-rip single-vintage grammar.
"""

from __future__ import annotations

from pathlib import Path


# Repository-root resolution mirrors the pattern used by the other
# layout-gate tests (e.g. ``test_lift_boundary_lgd_ac_id.py``): walk
# two ``parents`` from this file (``backend/tests/<file>.py`` -> repo
# root) so the gate runs without env-var injection in the standard
# ``cd backend; pytest`` invocation.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATASETS = _REPO_ROOT / "datasets"
_ELECTORAL = _DATASETS / "boundaries" / "electoral"


def test_delim_2024_ac_national_topojson_present() -> None:
    """The consolidated national AC layer ships as ONE TopoJSON."""
    ac_topojson = _ELECTORAL / "delim=2024" / "ac" / "all.topojson"
    assert ac_topojson.is_file(), (
        f"missing national AC TopoJSON: {ac_topojson}. Row 3 consolidated the "
        "31 per-state shards into this one file; produce it via "
        "tools/boundaries/consolidate_ac_2024.py."
    )


def test_delim_2024_ac_is_topojson_object_ac() -> None:
    """The national AC TopoJSON is a Topology whose object is named ``ac``."""
    import json

    ac_topojson = _ELECTORAL / "delim=2024" / "ac" / "all.topojson"
    topo = json.loads(ac_topojson.read_text(encoding="utf-8"))
    assert topo.get("type") == "Topology", "AC file must be a TopoJSON Topology"
    objects = topo.get("objects") or {}
    assert "ac" in objects, (
        f"national AC TopoJSON must expose object 'ac'; got {sorted(objects)}"
    )
    geoms = objects["ac"].get("geometries")
    assert isinstance(geoms, list) and len(geoms) > 3000, (
        "AC object must be a non-trivial GeometryCollection (~4149 ACs)"
    )


def test_delim_2024_ac_features_carry_state_ut_code() -> None:
    """Every AC feature is stamped with ``state_ut_code`` (the per-state filter
    key the frontend + tile generator slice on)."""
    import json

    ac_topojson = _ELECTORAL / "delim=2024" / "ac" / "all.topojson"
    topo = json.loads(ac_topojson.read_text(encoding="utf-8"))
    geoms = topo["objects"]["ac"]["geometries"]
    missing = [
        i
        for i, g in enumerate(geoms)
        if not str((g.get("properties") or {}).get("state_ut_code") or "")
    ]
    assert not missing, (
        f"{len(missing)} AC features missing state_ut_code (first few: {missing[:5]})"
    )


def test_delim_2024_pc_country_geojson_present() -> None:
    """The national delim=2024 PC layer ships as ONE GeoJSON."""
    pc_geojson = _ELECTORAL / "delim=2024" / "pc" / "all.geojson"
    assert pc_geojson.is_file(), f"missing national PC GeoJSON: {pc_geojson}"


def test_no_legacy_delimitation_trees_survive() -> None:
    """The pre-rip ``delim=2008`` + ``delim=2026`` trees are gone.

    Row 3 deleted both: the single 2024 snapshot carries every delimitation
    era via the dual-key join + the ``delim_year`` baked into each unit_id.
    A regression that re-creates either tree would re-introduce the 24x wire
    regression (national AC geojson) or a stale second vintage.
    """
    survivors = [
        str(p)
        for p in (
            _ELECTORAL / "delim=2008",
            _ELECTORAL / "delim=2026",
        )
        if p.exists()
    ]
    assert not survivors, (
        f"legacy electoral delimitation trees survive: {survivors}; Row 3 of "
        "the map-geometry plan deleted delim=2008 + delim=2026."
    )


def test_electoral_subtree_holds_only_delim_2024() -> None:
    """The only ``delim=`` tree under boundaries/electoral is ``delim=2024``."""
    delim_dirs = sorted(
        d.name
        for d in _ELECTORAL.iterdir()
        if d.is_dir() and d.name.startswith("delim=")
    )
    assert delim_dirs == ["delim=2024"], (
        f"electoral subtree should hold only delim=2024 after the Row 3 rip; "
        f"found {delim_dirs}"
    )


def test_legacy_in_ac_and_in_pc_subtrees_gone() -> None:
    """The pre-G10 electoral paths under boundaries/in/{ac,pc} are gone.

    A regression that re-creates ``boundaries/in/ac/state=*/...`` or
    ``boundaries/in/pc/delim=*/...`` would defeat the G10 separation
    (the admin spine and the electoral spine are now peers under
    ``datasets/boundaries/``).
    """
    legacy_paths = [
        _DATASETS / "boundaries" / "in" / "ac",
        _DATASETS / "boundaries" / "in" / "pc",
    ]
    survivors = [str(p) for p in legacy_paths if p.exists()]
    assert not survivors, (
        f"legacy electoral subtrees survive under boundaries/in/: "
        f"{survivors}; the G10 rip moved them to boundaries/electoral/"
    )


def test_electoral_readme_documents_single_vintage_grammar() -> None:
    """The README must spell out the single-2024-vintage AC + PC grammar.

    Readers and future ingest tools must be able to grep the README and
    find the on-disk grammar (one national AC TopoJSON, one national PC
    GeoJSON) without re-reading the plan-doc.
    """
    readme = _ELECTORAL / "README.md"
    assert readme.is_file(), f"missing electoral README: {readme}"
    text = readme.read_text(encoding="utf-8")
    assert "delim=2024/ac/all.topojson" in text, (
        "electoral README must document the national AC TopoJSON path "
        "(delim=2024/ac/all.topojson)"
    )
    assert "delim=2024/pc/all.geojson" in text, (
        "electoral README must document the national PC GeoJSON path "
        "(delim=2024/pc/all.geojson)"
    )
