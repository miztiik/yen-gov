"""Tier-B tests for ``tier_b_indicator_has_justification`` (PR-Z3b-tail-actionD dark).

Per docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #15, default action for new data is UPSERT into the existing
indicator. Minting a SECOND indicator that shares a ``concept_id`` with
an existing one (only entity_kinds differing) is permitted only when
the catalogue row carries a non-empty ``meta.justification``. The check
ships dark in PR-Z3b-tail-actionD (function present, NOT chained into
``run()``) and enforces post-PR-Z3b-tail-actionC.

Per CLAUDE.md anti-pattern (pytest never walks the real corpus) these
tests use ``tmp_path`` fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.validate import tier_b_indicator_has_justification


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
         entity_kinds: list[str] | None = None,
         justification: str | None = None) -> dict:
    ek = entity_kinds or ["state"]
    r = {**_BASE, "indicator_id": indicator_id,
         "entity_kinds": ek, "default_entity_kind": ek[0]}
    if concept_id is not None:
        r["concept_id"] = concept_id
    if justification is not None:
        r["meta"] = {"justification": justification}
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
    assert tier_b_indicator_has_justification(tmp_path) == []


def test_no_op_when_no_row_has_concept_id(tmp_path):
    # Mirrors today's catalogue: no row carries concept_id yet (backfill pending).
    _write(tmp_path, [_row("a"), _row("b")])
    assert tier_b_indicator_has_justification(tmp_path) == []


def test_single_grain_cluster_does_not_require_justification(tmp_path):
    # Both rows same concept_id AND same entity_kinds -- proliferation
    # case caught by tier_b_one_indicator_per_concept, not this check.
    _write(tmp_path, [
        _row("a", concept_id="coal-mw-absolute"),
        _row("b", concept_id="coal-mw-absolute"),
    ])
    assert tier_b_indicator_has_justification(tmp_path) == []


def test_rejects_cross_grain_twin_missing_justification(tmp_path):
    _write(tmp_path, [
        _row("coal-mw-country", concept_id="coal-mw-absolute",
             entity_kinds=["country"]),
        _row("coal-mw-state", concept_id="coal-mw-absolute",
             entity_kinds=["state"]),
    ])
    failures = tier_b_indicator_has_justification(tmp_path)
    # Both twins lack justification -> both fail.
    assert len(failures) == 2
    msgs = [f.message for f in failures]
    assert any("coal-mw-country" in m for m in msgs)
    assert any("coal-mw-state" in m for m in msgs)
    assert all("guardrail #15" in m for m in msgs)


def test_passes_when_each_cross_grain_twin_has_justification(tmp_path):
    _write(tmp_path, [
        _row("coal-mw-country", concept_id="coal-mw-absolute",
             entity_kinds=["country"],
             justification="CEA all-India totals from monthly capacity report; "
                          "state allocations not published at this grain."),
        _row("coal-mw-state", concept_id="coal-mw-absolute",
             entity_kinds=["state"],
             justification="ICED state-wise series; different vintage from CEA."),
    ])
    assert tier_b_indicator_has_justification(tmp_path) == []


def test_rejects_only_the_missing_one_when_partial(tmp_path):
    _write(tmp_path, [
        _row("ok", concept_id="coal-mw-absolute", entity_kinds=["country"],
             justification="documented"),
        _row("bad", concept_id="coal-mw-absolute", entity_kinds=["state"]),
    ])
    failures = tier_b_indicator_has_justification(tmp_path)
    assert len(failures) == 1
    assert "bad" in failures[0].message


def test_empty_string_justification_counts_as_missing(tmp_path):
    _write(tmp_path, [
        _row("a", concept_id="c", entity_kinds=["country"], justification="   "),
        _row("b", concept_id="c", entity_kinds=["state"], justification="real"),
    ])
    failures = tier_b_indicator_has_justification(tmp_path)
    assert len(failures) == 1
    assert "'a'" in failures[0].message


def test_check_is_chained_live_into_run():
    """PR-Zjust flips the check LIVE -- chained into run() post meta.justification backfill."""
    from yen_gov import validate as v

    src = Path(v.__file__).read_text(encoding="utf-8")
    assert "tier_b_indicator_has_justification" in src  # function present
    assert "+ tier_b_indicator_has_justification" in src  # chained live


def test_passes_against_repo_indicators_catalogue():
    """Live sentinel: real datasets/taxonomy/indicators.json must produce zero failures.

    Guards against any future indicator-catalogue PR introducing a new cross-grain
    twin without ``meta.justification``. The 26 existing twins (5x coal/gas/hydro/
    nuclear/renewable installed-capacity attribution facets + 2x vote-share +
    2x winning-party) all carry justifications per PR-Zjust backfill.
    """
    from yen_gov import validate as v

    repo_root = Path(v.__file__).resolve().parents[2]
    failures = tier_b_indicator_has_justification(repo_root)
    assert failures == [], (
        f"{len(failures)} cross-grain twin(s) missing meta.justification: "
        + "; ".join(f.message[:200] for f in failures[:3])
    )
