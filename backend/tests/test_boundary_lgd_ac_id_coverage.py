"""Tier-A guard: the consolidated AC TopoJSON stamps lgd_ac_id for the full crosswalk.

ADR-0049: ``lgd_ac_id`` is the canonical INTERNAL AC join key; the frontend AC
choropleth (``StateAcMapD3.svelte``) greys any feature missing it. This gate
fails loudly if the consolidated AC TopoJSON drifts out of sync with the
canonical crosswalk - e.g. a future state whose crosswalk coverage lands but
whose topojson was never re-stamped via
``tools/boundaries/lift_boundary_lgd_ac_id.py``. That is exactly the
"tomorrow it will be X state" regression that made every standard AC grey
before this gate existed (the stamp tool used to read a retired parquet + walk
deleted ``delim=2008`` shards, so it stamped nothing).

Reads two specific known files once (the crosswalk CSV via the tool loader +
the one national AC TopoJSON) - NOT a corpus-walk (no globbing / discovery),
permitted per the CLAUDE.md anti-pattern carve-out, same as
``test_ac_parity_per_state.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "boundaries"))

import lift_boundary_lgd_ac_id as lift  # noqa: E402  (after sys.path manipulation)

DATASETS = REPO / "datasets"
AC_TOPOJSON = (
    DATASETS / "boundaries" / "electoral" / "delim=2024" / "ac" / "all.topojson"
)


def _ac_geometries() -> list[dict]:
    topo = json.loads(AC_TOPOJSON.read_bytes())
    return topo["objects"]["ac"]["geometries"]


def _ac_id_int(props: dict) -> int | None:
    ac_id = props.get("AC_ID")
    if ac_id is None:
        return None
    try:
        return int(ac_id)
    except (TypeError, ValueError):
        return None


def test_crosswalk_covered_set_non_empty() -> None:
    """The crosswalk read must yield a non-empty covered set.

    Guards the exact regression this gate exists for: if the loader is
    repointed at a missing/retired file it returns an empty set and the stamp
    tool silently stamps nothing, greying every AC choropleth.
    """
    covered = lift.load_covered_lgd_ac_ids(DATASETS)
    assert len(covered) >= 3000, (
        f"covered lgd_ac_id set is {len(covered)}; expected the full AC "
        "crosswalk (~3986 today). An empty/short set means the crosswalk read "
        "is broken and the AC choropleth will grey on every state."
    )


def test_every_covered_ac_id_feature_is_stamped() -> None:
    """Completeness: every AC feature whose AC_ID is a covered lgd_ac_id carries it.

    Documented exclusions (NOT required to carry lgd_ac_id):
      - features with no parseable AC_ID (U08 J&K ``seat_id``, S03 Assam
        district-fallback);
      - cross-state spillover slivers whose AC_ID is outside the covered set
        (each AC's main polygon is stamped; only tiny duplicate slivers stay
        unstamped).
    """
    covered = lift.load_covered_lgd_ac_ids(DATASETS)
    missing: list[dict] = []
    for g in _ac_geometries():
        props = g.get("properties") or {}
        ac_id = _ac_id_int(props)
        if ac_id is None or ac_id not in covered:
            continue  # documented exclusion (no AC_ID / sliver outside crosswalk)
        if props.get("lgd_ac_id") is None:
            missing.append(
                {
                    "state_ut_code": props.get("state_ut_code"),
                    "AC_ID": props.get("AC_ID"),
                    "ac_name": props.get("ac_name"),
                }
            )
    assert not missing, (
        f"{len(missing)} AC feature(s) have a covered AC_ID but no lgd_ac_id "
        "stamp -> they will grey on the choropleth. Re-run "
        "tools/boundaries/lift_boundary_lgd_ac_id.py and commit the topojson. "
        f"First few: {missing[:5]}"
    )
