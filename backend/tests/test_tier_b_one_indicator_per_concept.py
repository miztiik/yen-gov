"""Tier-B tests for ``tier_b_one_indicator_per_concept`` (PR-Z3b-tail3 dark).

Per TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #13, identity is what is MEASURED, not who published it. Two
indicators sharing ``(concept_id, entity_kinds)`` is a proliferation bug.
The check ships dark in PR-Z3b-tail3 (function present, NOT chained into
``run()``) and enforces post-PR-Z3b-tail-actionC once the 183 existing
rows have been backfilled with ``concept_id``.

Per CLAUDE.md anti-pattern (pytest never walks the real corpus) these
tests use ``tmp_path`` fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.validate import tier_b_one_indicator_per_concept


_BASE = {
    "label_short": "X",
    "label_long": "X long",
    "description_short": "X.",
    "unit": "MW",
    "cadence": "annual",
    "family": "energy",
    "pillar": "infrastructure",
    "value_kind": "stock",
    "direction": "neutral",
    "attribution_geography": "where_administered",
    "comparability": "comparable_across_states_and_time",
    "parent_indicator_id": None,
}


def _row(indicator_id: str, *, concept_id: str | None = None,
         entity_kinds: list[str] | None = None) -> dict:
    r = {**_BASE, "indicator_id": indicator_id,
         "entity_kinds": entity_kinds or ["state"],
         "default_entity_kind": (entity_kinds or ["state"])[0]}
    if concept_id is not None:
        r["concept_id"] = concept_id
    return r


def _write(root: Path, rows: list[dict]) -> None:
    p = root / "datasets" / "taxonomy"
    p.mkdir(parents=True, exist_ok=True)
    (p / "indicators.json").write_text(
        json.dumps(
            {
                "$schema": "../schemas/indicator-catalogue.schema.json",
                "$schema_version": "2.0",
                "indicators": rows,
            }
        ),
        encoding="utf-8",
    )


def test_no_op_when_catalogue_missing(tmp_path):
    assert tier_b_one_indicator_per_concept(tmp_path) == []


def test_no_op_when_no_row_has_concept_id(tmp_path):
    # Mirrors today's catalogue: no row carries concept_id yet (backfill pending).
    _write(tmp_path, [_row("a"), _row("b"), _row("c")])
    assert tier_b_one_indicator_per_concept(tmp_path) == []


def test_passes_when_each_concept_has_one_indicator(tmp_path):
    _write(tmp_path, [
        _row("coal-mw-absolute", concept_id="coal-mw-absolute"),
        _row("gas-mw-absolute", concept_id="gas-mw-absolute"),
    ])
    assert tier_b_one_indicator_per_concept(tmp_path) == []


def test_passes_when_same_concept_distinct_entity_kinds(tmp_path):
    # country-grain and state-grain of the same concept are legitimate twins
    # until cross-grain merge ships (separate concepts row could also model it).
    _write(tmp_path, [
        _row("coal-mw-country", concept_id="coal-mw-absolute", entity_kinds=["country"]),
        _row("coal-mw-state", concept_id="coal-mw-absolute", entity_kinds=["state"]),
    ])
    assert tier_b_one_indicator_per_concept(tmp_path) == []


def test_rejects_two_indicators_sharing_concept_and_entity_kinds(tmp_path):
    _write(tmp_path, [
        _row("installed-capacity-coal-mw", concept_id="coal-mw-absolute"),
        _row("coal-installed-capacity-mw", concept_id="coal-mw-absolute"),
    ])
    failures = tier_b_one_indicator_per_concept(tmp_path)
    assert len(failures) == 1
    msg = failures[0].message
    assert "coal-mw-absolute" in msg
    assert "installed-capacity-coal-mw" in msg
    assert "coal-installed-capacity-mw" in msg
    assert "guardrail #13" in msg


def test_rejects_five_way_coal_mw_cluster_oracle(tmp_path):
    # Mirrors the 5xcoal-MW duplicate cluster surfaced by Z3a clustering.
    ids = [
        "coal-installed-capacity-mw",
        "installed-capacity-coal-mw",
        "thermal-coal-mw",
        "coal-capacity-mw-state",
        "coal-mw-installed",
    ]
    _write(tmp_path, [_row(i, concept_id="coal-mw-absolute") for i in ids])
    failures = tier_b_one_indicator_per_concept(tmp_path)
    assert len(failures) == 1
    msg = failures[0].message
    assert "5 rows" in msg
    for i in ids:
        assert i in msg


def test_reports_each_distinct_proliferation_cluster(tmp_path):
    _write(tmp_path, [
        _row("a1", concept_id="coal-mw-absolute"),
        _row("a2", concept_id="coal-mw-absolute"),
        _row("b1", concept_id="gas-mw-absolute"),
        _row("b2", concept_id="gas-mw-absolute"),
        _row("ok", concept_id="solo-concept"),
    ])
    failures = tier_b_one_indicator_per_concept(tmp_path)
    assert len(failures) == 2
    msgs = "\n".join(f.message for f in failures)
    assert "coal-mw-absolute" in msgs and "gas-mw-absolute" in msgs


def test_check_is_dark_not_chained_into_run():
    """PR-Z3b-tail3 ships the check DARK -- NOT in run(). Enforced post-tail."""
    from yen_gov import validate as v

    src = Path(v.__file__).read_text(encoding="utf-8")
    assert "tier_b_one_indicator_per_concept" in src  # function present
    assert "+ tier_b_one_indicator_per_concept" not in src  # not chained
