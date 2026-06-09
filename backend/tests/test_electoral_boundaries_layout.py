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


# Snapshot of the 31 AC state slugs captured BEFORE the G10 git mv
# (via ``git ls-files datasets/boundaries/in/ac/`` on origin/main
# ``c3c9639d``). Frozen as a tuple constant so the gate fails closed if
# any slug silently disappears post-mv; adding a new state slug is a
# deliberate edit to this tuple plus the matching on-disk fixture.
_EXPECTED_AC_STATE_SLUGS: tuple[str, ...] = (
    "state=andhra-pradesh",
    "state=arunachal-pradesh",
    "state=assam",
    "state=bihar",
    "state=chhattisgarh",
    "state=delhi",
    "state=goa",
    "state=gujarat",
    "state=haryana",
    "state=himachal-pradesh",
    "state=jammu-and-kashmir",
    "state=jharkhand",
    "state=karnataka",
    "state=kerala",
    "state=madhya-pradesh",
    "state=maharashtra",
    "state=manipur",
    "state=meghalaya",
    "state=mizoram",
    "state=nagaland",
    "state=odisha",
    "state=puducherry",
    "state=punjab",
    "state=rajasthan",
    "state=sikkim",
    "state=tamil-nadu",
    "state=telangana",
    "state=tripura",
    "state=uttar-pradesh",
    "state=uttarakhand",
    "state=west-bengal",
)


def test_delim_2008_ac_state_geojsons_present() -> None:
    """Every expected delim=2008 AC state slug ships a geojson shard."""
    ac_root = _ELECTORAL / "delim=2008" / "ac"
    assert ac_root.is_dir(), f"missing electoral AC root: {ac_root}"
    missing: list[str] = []
    for slug in _EXPECTED_AC_STATE_SLUGS:
        shard = ac_root / slug / "all.geojson"
        if not shard.is_file():
            missing.append(slug)
    assert not missing, (
        "delim=2008 AC state geojson shards missing: "
        f"{missing} (expected {len(_EXPECTED_AC_STATE_SLUGS)} slugs)"
    )
    on_disk = sorted(
        d.name
        for d in ac_root.iterdir()
        if d.is_dir() and d.name.startswith("state=")
    )
    assert on_disk == list(_EXPECTED_AC_STATE_SLUGS), (
        f"delim=2008 AC state slug set drifted from frozen snapshot; "
        f"on disk: {on_disk}; expected: {list(_EXPECTED_AC_STATE_SLUGS)}"
    )


def test_delim_2008_ac_state_dirs_carry_both_extensions() -> None:
    """Every delim=2008 AC state dir ships BOTH geojson AND topojson."""
    ac_root = _ELECTORAL / "delim=2008" / "ac"
    missing: list[str] = []
    for slug in _EXPECTED_AC_STATE_SLUGS:
        state_dir = ac_root / slug
        for ext in ("geojson", "topojson"):
            shard = state_dir / f"all.{ext}"
            if not shard.is_file():
                missing.append(f"{slug}/all.{ext}")
    assert not missing, (
        "delim=2008 AC state dirs missing extension companions: "
        f"{missing}"
    )


def test_delim_2024_pc_country_files_present() -> None:
    """The national delim=2024 PC pair ships both extensions."""
    pc_root = _ELECTORAL / "delim=2024" / "pc"
    assert pc_root.is_dir(), f"missing electoral PC root: {pc_root}"
    missing: list[str] = []
    for ext in ("geojson", "topojson"):
        shard = pc_root / f"all.{ext}"
        if not shard.is_file():
            missing.append(f"all.{ext}")
    assert not missing, (
        f"delim=2024 PC country files missing: {missing}"
    )


def test_delim_2026_placeholders_present() -> None:
    """Reserved delim=2026 ac+pc dirs carry .gitkeep placeholders.

    Per plan section 4 EL2 the next ECI Delimitation Commission Order
    lands as ``delim=2026/{ac,pc}/...``; reserving the dirs upfront
    means the first ingest does not need to mint a new top-level
    ``delim=`` peer in the same PR as its first data shard.
    """
    for grain in ("ac", "pc"):
        keep = _ELECTORAL / "delim=2026" / grain / ".gitkeep"
        assert keep.is_file(), f"missing delim=2026 placeholder: {keep}"


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


def test_electoral_readme_documents_asymmetric_grammar() -> None:
    """The README must spell out both the AC and PC grammars verbatim.

    The asymmetry (per-state AC, country-wide PC) is the Gregor-locked
    contract for the subtree; readers and future ingest tools must be
    able to grep the README and find the grammar without re-reading
    the plan-doc.
    """
    readme = _ELECTORAL / "README.md"
    assert readme.is_file(), f"missing electoral README: {readme}"
    text = readme.read_text(encoding="utf-8")
    assert "delim=<year>/ac/state=<slug>" in text, (
        "electoral README must document the AC grammar literally "
        "(delim=<year>/ac/state=<slug>)"
    )
    assert "delim=<year>/pc" in text, (
        "electoral README must document the PC grammar literally "
        "(delim=<year>/pc)"
    )
