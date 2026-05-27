"""Carve 1 backfill assertions (PR-Z3b-tail-conceptFK Carve 1).

Per docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #13: every indicator MUST FK to one row in
``datasets/taxonomy/concepts.json``. Carve 0a (#373) added the optional
schema field; Carve 1 (this PR) backfills the FK on every row via the
PR-Z3a ``find_overlap`` helper (confidence >=0.95 -> use match;
otherwise auto-mint a stub concept and FK to it).

These tests walk the canonical catalogue files (same pattern as the
existing v2.0/v2.1/v2.2 schema-shape tests). They guard the invariant
that the FK is fully populated and that every FK resolves.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOGUE_PATH = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"
CONCEPTS_PATH = REPO_ROOT / "datasets" / "taxonomy" / "concepts.json"
CONCEPT_ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _catalogue() -> dict:
    return json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))


def _concepts() -> dict:
    return json.loads(CONCEPTS_PATH.read_text(encoding="utf-8"))


def test_all_indicators_carry_concept_id():
    rows = _catalogue()["indicators"]
    missing = [r["indicator_id"] for r in rows if not r.get("concept_id")]
    assert not missing, (
        f"Carve 1 backfilled all 183 rows; missing on: {missing[:10]} "
        f"(total {len(missing)})."
    )


def test_every_concept_id_is_valid_kebab():
    rows = _catalogue()["indicators"]
    bad = [
        (r["indicator_id"], r.get("concept_id"))
        for r in rows
        if not (r.get("concept_id") and CONCEPT_ID_RE.match(r["concept_id"]))
        or (r.get("concept_id") and len(r["concept_id"]) > 40)
    ]
    assert not bad, f"Invalid kebab concept_id slug on: {bad[:10]}"


def test_every_concept_id_resolves_to_a_concepts_row():
    rows = _catalogue()["indicators"]
    available = {c["concept_id"] for c in _concepts()["concepts"]}
    unresolved = sorted(
        {r["concept_id"] for r in rows if r.get("concept_id") not in available}
    )
    assert not unresolved, (
        f"Dangling FK on indicators.json -> concepts.json: {unresolved[:10]}"
    )


def test_carve1_seeded_at_least_one_stub_concept():
    # Carve 1's auto-mint stub concepts carry the well-known description
    # prefix; sanity that the seeder ran. (3 stubs at backfill time:
    # per-capita-consumption-2, per-capita-availability-2,
    # capacity-allocated-to-state-2.)
    stubs = [
        c
        for c in _concepts()["concepts"]
        if c["description_short"].startswith("Auto-minted stub for indicator ")
    ]
    assert stubs, "Carve 1 should have minted at least one stub concept."
