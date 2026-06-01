"""Tier-A FK + schema tests for LGD taxonomy seeds (L1d).

Covers PR L1a (lgd_states.json), PR L1b (lgd_districts.json), and PR L1c
(lgd_acs.json + lgd_pcs.json + lgd_ac_pc_district_map.json).

Asserts:
  - every JSON validates against its schema
  - no duplicate primary keys
  - cross-FK closure: districts/acs/pcs/map all FK-resolve into their parents
  - documented gaps (Delhi ACs+PCs; Lakshadweep+Ladakh PCs) are still gaps
    until the source LGD report is re-pulled
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO = Path(__file__).resolve().parents[2]
TAX = REPO / "datasets/taxonomy"
SCH = REPO / "datasets/schemas"


def _load(name: str, key: str) -> list[dict]:
    doc = json.loads((TAX / f"{name}.json").read_text(encoding="utf-8"))
    schema_stem = name.replace("_", "-")
    schema = json.loads((SCH / f"{schema_stem}.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    return doc[key]


@pytest.fixture(scope="module")
def states() -> list[dict]:
    return _load("lgd_states", "states")


@pytest.fixture(scope="module")
def districts() -> list[dict]:
    return _load("lgd_districts", "districts")


@pytest.fixture(scope="module")
def acs() -> list[dict]:
    return _load("lgd_acs", "acs")


@pytest.fixture(scope="module")
def pcs() -> list[dict]:
    return _load("lgd_pcs", "pcs")


@pytest.fixture(scope="module")
def ac_district_map() -> list[dict]:
    return _load("lgd_ac_pc_district_map", "rows")


def test_states_count_and_unique_pks(states):
    assert len(states) == 36
    assert len({s["lgd_state_id"] for s in states}) == 36
    assert len({s["eci_st_code"] for s in states}) == 36
    assert len({s["slug"] for s in states}) == 36


def test_districts_fk_state(states, districts):
    sids = {s["lgd_state_id"] for s in states}
    assert all(d["lgd_state_id"] in sids for d in districts)
    assert len({d["lgd_district_id"] for d in districts}) == len(districts)


def test_acs_fk_state(states, acs):
    sids = {s["lgd_state_id"] for s in states}
    assert all(a["lgd_state_id"] in sids for a in acs)
    assert len({a["lgd_ac_id"] for a in acs}) == len(acs)


def test_acs_fk_pc(pcs, acs):
    pc_ids = {p["lgd_pc_id"] for p in pcs}
    for a in acs:
        if a["lgd_pc_id"] is not None:
            assert a["lgd_pc_id"] in pc_ids, f"AC {a['lgd_ac_id']} references unknown PC {a['lgd_pc_id']}"


def test_pcs_fk_state(states, pcs):
    sids = {s["lgd_state_id"] for s in states}
    assert all(p["lgd_state_id"] in sids for p in pcs)
    assert len({p["lgd_pc_id"] for p in pcs}) == len(pcs)


def test_ac_district_map_fk(acs, districts, ac_district_map):
    acids = {a["lgd_ac_id"] for a in acs}
    dids = {d["lgd_district_id"] for d in districts}
    for r in ac_district_map:
        assert r["lgd_ac_id"] in acids
        for d in r["lgd_district_ids"]:
            assert d in dids


def test_documented_gaps_still_present(acs, pcs):
    """When the source LGD report is re-pulled with Delhi + Lakshadweep + Ladakh
    included, this test is the canary - it MUST fail (forcing a doc update +
    schema bump). Until then, the gaps stand."""
    ac_states = {a["lgd_state_id"] for a in acs}
    pc_states = {p["lgd_state_id"] for p in pcs}
    # Delhi (LGD 7): currently absent from both
    assert 7 not in ac_states, "Delhi ACs now present - update lgd_acs $comment + drop this guard"
    assert 7 not in pc_states, "Delhi PCs now present - update lgd_pcs $comment + drop this guard"
    # Lakshadweep (31) + Ladakh (37): PCs absent (no ACs expected)
    assert 31 not in pc_states, "Lakshadweep PC now present - update lgd_pcs $comment"
    assert 37 not in pc_states, "Ladakh PC now present - update lgd_pcs $comment"
