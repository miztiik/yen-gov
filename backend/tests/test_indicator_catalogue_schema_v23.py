"""Schema-shape assertions for indicator-catalogue.schema.json v2.3
(PR-Zjust -- meta.justification backfill + Tier-B chained live).

Per TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #15: minting a second indicator that shares ``concept_id`` with
an existing one (only ``entity_kinds`` differing) is permitted only when
the catalogue row carries non-empty ``meta.justification`` naming the
structural difference (different concept / unit / normalisation /
sampling frame / attribution facet). PR-Zjust additively adds the
optional ``meta`` object with the ``justification`` sub-property and
backfills the 26 existing cross-grain twin rows.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "indicator-catalogue.schema.json"
CATALOGUE_PATH = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _catalogue() -> dict:
    return json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))


def test_schema_x_version_is_2_3():
    assert _schema()["x-version"] == "2.3"


def test_catalogue_schema_version_stamp_is_2_3():
    assert _catalogue()["$schema_version"] == "2.3"


def test_x_changelog_tail_entry_is_2_3():
    tail = _schema()["x-changelog"][-1]
    assert tail["version"] == "2.3"
    assert tail["date"] == "2026-05-26"
    assert "meta.justification" in tail["description"]
    assert "PR-Zjust" in tail["description"]


def test_schema_declares_meta_object_with_justification():
    props = _schema()["properties"]["indicators"]["items"]["properties"]
    assert "meta" in props
    meta = props["meta"]
    assert meta["type"] == "object"
    assert meta["additionalProperties"] is False
    just = meta["properties"]["justification"]
    assert just["type"] == "string"
    assert just["minLength"] == 20


def test_meta_is_optional_in_required_list():
    required = _schema()["properties"]["indicators"]["items"]["required"]
    assert "meta" not in required


def test_v22_concept_id_still_present():
    """v2.3 is purely additive on top of v2.2; the v2.2 field must remain."""
    props = _schema()["properties"]["indicators"]["items"]["properties"]
    assert "concept_id" in props


def test_all_cross_grain_twins_carry_meta_justification():
    """All 26 known cross-grain twins (5x coal/gas/hydro/nuclear/renewable
    installed-capacity attribution facets + 2x vote-share + 2x winning-party)
    MUST carry non-empty ``meta.justification`` post PR-Zjust backfill.
    """
    rows = _catalogue()["indicators"]
    by_concept: dict[str, list[dict]] = {}
    for r in rows:
        cid = r.get("concept_id")
        if isinstance(cid, str) and cid:
            by_concept.setdefault(cid, []).append(r)
    twin_misses: list[str] = []
    for cid, group in by_concept.items():
        ek_tuples = {tuple(sorted(r["entity_kinds"])) for r in group}
        if len(ek_tuples) < 2:
            continue
        for r in group:
            meta = r.get("meta") or {}
            j = meta.get("justification", "")
            if not (isinstance(j, str) and j.strip()):
                twin_misses.append(f"{r['indicator_id']} (concept={cid})")
    assert twin_misses == [], (
        f"{len(twin_misses)} cross-grain twin(s) missing meta.justification: "
        + ", ".join(twin_misses[:6])
    )
