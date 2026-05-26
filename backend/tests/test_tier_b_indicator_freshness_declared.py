"""Tier-B tests for ``tier_b_indicator_freshness_declared`` (PR-Z3b-cli dark).

Per TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #18, every indicator MUST declare ``update_period_days`` as a
positive int. The check ships dark in PR-Z3b-cli (function present, NOT
chained into ``run()``) and enforces post-PR-Z3b-tail once the 183
existing rows have been backfilled.

Per CLAUDE.md anti-pattern (pytest never walks the real corpus) these
tests use ``tmp_path`` fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.validate import tier_b_indicator_freshness_declared


_BASE = {
    "indicator_id": "electors-total",
    "label_short": "Electors",
    "label_long": "Total electors",
    "description_short": "Total registered electors at the contest grain.",
    "unit": "count",
    "cadence": "ad_hoc",
    "family": "elections",
    "pillar": "politics",
    "value_kind": "count",
    "direction": "neutral",
    "attribution_geography": "where_administered",
    "comparability": "comparable_across_states_and_time",
    "parent_indicator_id": None,
    "entity_kinds": ["state"],
    "default_entity_kind": "state",
}


def _write_catalogue(root: Path, indicators: list[dict]) -> None:
    p = root / "datasets" / "taxonomy"
    p.mkdir(parents=True, exist_ok=True)
    (p / "indicators.json").write_text(
        json.dumps(
            {
                "$schema": "../schemas/indicator-catalogue.schema.json",
                "$schema_version": "2.0",
                "indicators": indicators,
            }
        ),
        encoding="utf-8",
    )


def test_passes_when_update_period_days_is_positive_int(tmp_path):
    row = {**_BASE, "update_period_days": 365}
    _write_catalogue(tmp_path, [row])
    assert tier_b_indicator_freshness_declared(tmp_path) == []


def test_rejects_missing_update_period_days(tmp_path):
    _write_catalogue(tmp_path, [_BASE])  # no update_period_days at all
    failures = tier_b_indicator_freshness_declared(tmp_path)
    assert len(failures) == 1
    assert "electors-total" in failures[0].message
    assert "update_period_days" in failures[0].message


def test_rejects_zero(tmp_path):
    row = {**_BASE, "update_period_days": 0}
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_freshness_declared(tmp_path)
    assert len(failures) == 1
    assert "update_period_days" in failures[0].message


def test_rejects_negative(tmp_path):
    row = {**_BASE, "update_period_days": -1}
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_freshness_declared(tmp_path)
    assert len(failures) == 1


def test_rejects_non_int(tmp_path):
    row = {**_BASE, "update_period_days": "365"}
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_freshness_declared(tmp_path)
    assert len(failures) == 1


def test_reports_each_offending_row(tmp_path):
    rows = [
        {**_BASE, "indicator_id": "a-good", "update_period_days": 30},
        {**_BASE, "indicator_id": "b-bad"},
        {**_BASE, "indicator_id": "c-bad", "update_period_days": 0},
    ]
    _write_catalogue(tmp_path, rows)
    failures = tier_b_indicator_freshness_declared(tmp_path)
    assert len(failures) == 2
    ids = sorted(f.message for f in failures)
    assert any("b-bad" in m for m in ids)
    assert any("c-bad" in m for m in ids)


def test_check_is_dark_not_chained_into_run():
    """PR-Z3b-cli ships the check DARK -- NOT in run(). Enforced post-tail."""
    from yen_gov import validate as v

    src = Path(v.__file__).read_text(encoding="utf-8")
    assert "tier_b_indicator_freshness_declared" in src  # function present
    assert "+ tier_b_indicator_freshness_declared" not in src


def test_no_op_when_catalogue_missing(tmp_path):
    assert tier_b_indicator_freshness_declared(tmp_path) == []
