"""Tier-A pins for the installed-capacity concept model AFTER the geo-facet collapse.

Supersedes the per-fuel cluster tests test_concept_resolve_c2..c6 (deleted in
the same PR). Those files pinned a workaround: because the geo datapoint
file-class had no facet column, each (fuel x attribution) pair had to be its
own indicator + concept to satisfy tier_b_one_indicator_per_concept, which
fragmented one measure into N concepts (e.g. coal-mw-geographical,
coal-mw-snapshot, coal-mw-absolute).

The geo-facet PR (TODO/20260616-geo-facet-dimension-column-plan.md) removes
that workaround: fuel_type is a dimension column on the faceted
datasets/data/datapoints/geo_by_fuel/*.csv file-class, so the geographical +
snapshot + all-India families each collapse to ONE faceted measure
(installed-capacity-{geographical-mw,snapshot-mw,mw}) carrying a single
concept. Only the ALLOCATED family stays single-value (no fuel children on
disk -> fails the four-gate facet test), so its per-fuel concepts survive.

These pins guard the post-collapse model against accidental re-fragmentation.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDICATORS = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"
CONCEPTS = REPO_ROOT / "datasets" / "taxonomy" / "concepts.json"
GEO_BY_FUEL = REPO_ROOT / "datasets" / "data" / "datapoints" / "geo_by_fuel"

_FUELS = ("coal", "gas", "hydro", "nuclear", "renewable")
# The all-India family's per-fuel concepts use an irregular -absolute suffix
# (gas + renewable drop the -mw infix); pin the exact names.
_ABSOLUTE_CONCEPTS = {
    "coal": "coal-mw-absolute",
    "gas": "gas-absolute",
    "hydro": "hydro-mw-absolute",
    "nuclear": "nuclear-mw-absolute",
    "renewable": "renewable-absolute",
}


def _rows() -> list[dict]:
    return json.loads(INDICATORS.read_text(encoding="utf-8"))["indicators"]


def _indicator_ids() -> set[str]:
    return {r["indicator_id"] for r in _rows()}


def _concept_ids() -> set[str]:
    return {
        c["concept_id"]
        for c in json.loads(CONCEPTS.read_text(encoding="utf-8"))["concepts"]
    }


def test_allocated_family_stays_split_per_fuel():
    """allocated-mw is single-value (no fuel children on disk), so each fuel
    keeps its own indicator + concept - the four-gate test correctly excludes
    it from the dimension-column collapse."""
    rows = {r["indicator_id"]: r for r in _rows()}
    for fuel in _FUELS:
        ind = f"installed-capacity-allocated-mw-{fuel}"
        assert ind in rows, f"{ind} should survive the collapse"
        assert rows[ind]["concept_id"] == f"{fuel}-mw-allocated"


def test_allocated_concepts_survive():
    cids = _concept_ids()
    for fuel in _FUELS:
        assert f"{fuel}-mw-allocated" in cids


def test_geographical_snapshot_absolute_concepts_removed():
    """The geographical + snapshot + all-India per-fuel concepts existed ONLY
    as the no-facet-column workaround; fuel is now a dimension, so they are
    gone."""
    cids = _concept_ids()
    for fuel in _FUELS:
        assert f"{fuel}-mw-geographical" not in cids
        assert f"{fuel}-mw-snapshot" not in cids
        assert _ABSOLUTE_CONCEPTS[fuel] not in cids


def test_per_fuel_child_indicators_removed():
    ids = _indicator_ids()
    for fuel in _FUELS:
        for family in ("geographical-mw", "snapshot-mw", "mw"):
            child = f"installed-capacity-{family}-{fuel}"
            assert child not in ids, f"{child} should be collapsed into the faceted file"


def test_faceted_parents_survive_with_single_concept():
    rows = {r["indicator_id"]: r for r in _rows()}
    expected = {
        "installed-capacity-geographical-mw": "capacity-sited-in-state",
        "installed-capacity-snapshot-mw": "capacity-snapshot-cea",
        "installed-capacity-mw": "all-india-installed-capacity",
    }
    for parent_id, concept_id in expected.items():
        assert parent_id in rows, f"faceted parent {parent_id} must survive"
        assert rows[parent_id]["concept_id"] == concept_id


def test_faceted_files_exist_on_disk():
    for parent_id in (
        "installed-capacity-geographical-mw",
        "installed-capacity-snapshot-mw",
        "installed-capacity-mw",
    ):
        assert (GEO_BY_FUEL / f"{parent_id}.csv").is_file()
