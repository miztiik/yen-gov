"""Tests for `validate --warn-concept-proliferation` (PR-Z3bconceptlive).

Per TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md
§0quat guardrail #13, the DARK `tier_b_one_indicator_per_concept` check
cannot chain LIVE into `validate.run()` yet because the current
catalogue still has 7 known proliferation clusters surfaced by Z3a
(per-fuel installed-capacity 5x coal / 5x gas / 4x hydro/nuclear/
renewable + 2x vote-share + 2x winning-party-id). Until those are
resolved (UPSERT or facet-collapse per guardrail #13), this PR exposes
a warn-only diagnostic via the CLI: `--warn-concept-proliferation`
prints findings as `[WARN]` lines but does NOT change exit code.

Per CLAUDE.md anti-pattern (pytest never walks the real corpus) these
tests use `tmp_path` fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from yen_gov.cli import app


_runner = CliRunner()

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
    "update_period_days": 365,
}


def _row(indicator_id: str, *, concept_id: str | None = None) -> dict:
    r = {
        **_BASE,
        "indicator_id": indicator_id,
        "entity_kinds": ["state"],
        "default_entity_kind": "state",
    }
    if concept_id is not None:
        r["concept_id"] = concept_id
    return r


def _seed_minimal_root(tmp_path: Path, rows: list[dict]) -> None:
    """Seed only the catalogue needed by tier_b_one_indicator_per_concept."""
    p = tmp_path / "datasets" / "taxonomy"
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
    # schemas dir must exist for validate to load (empty is fine).
    (tmp_path / "datasets" / "schemas").mkdir(parents=True, exist_ok=True)


def test_flag_off_does_not_emit_warnings(tmp_path):
    _seed_minimal_root(
        tmp_path,
        [
            _row("installed-capacity-coal-mw", concept_id="coal-mw-absolute"),
            _row("coal-installed-capacity-mw", concept_id="coal-mw-absolute"),
        ],
    )
    result = _runner.invoke(app, ["validate", "--root", str(tmp_path)])
    assert "[WARN" not in result.stdout
    assert "concept-proliferation" not in result.stdout


def test_flag_on_emits_warnings_without_failing(tmp_path):
    _seed_minimal_root(
        tmp_path,
        [
            _row("installed-capacity-coal-mw", concept_id="coal-mw-absolute"),
            _row("coal-installed-capacity-mw", concept_id="coal-mw-absolute"),
        ],
    )
    result = _runner.invoke(
        app,
        ["validate", "--root", str(tmp_path), "--warn-concept-proliferation"],
    )
    # The flag itself MUST NOT introduce failures; warnings are advisory.
    # (Other unrelated tier-B failures may still fire under a minimal tmp_path
    # root -- we assert only that the [WARN] lines surfaced.)
    assert "[WARN tier B]" in result.stdout
    assert "coal-mw-absolute" in result.stdout


def test_flag_on_short_alias_works(tmp_path):
    _seed_minimal_root(
        tmp_path,
        [
            _row("a", concept_id="dup"),
            _row("b", concept_id="dup"),
            _row("c", concept_id="dup"),
        ],
    )
    result = _runner.invoke(app, ["validate", "--root", str(tmp_path), "-w"])
    assert "[WARN tier B]" in result.stdout
    assert "3 rows" in result.stdout


def test_flag_on_no_proliferation_emits_no_warning(tmp_path):
    _seed_minimal_root(
        tmp_path,
        [
            _row("solo-a", concept_id="concept-a"),
            _row("solo-b", concept_id="concept-b"),
        ],
    )
    result = _runner.invoke(
        app,
        ["validate", "--root", str(tmp_path), "--warn-concept-proliferation"],
    )
    assert "[WARN tier B]" not in result.stdout
    assert "concept-proliferation warning" not in result.stdout


def test_dark_check_still_not_chained_into_run():
    """The LIVE chain remains blocked until proliferation clusters are resolved."""
    from yen_gov import validate as v

    src = Path(v.__file__).read_text(encoding="utf-8")
    assert "tier_b_one_indicator_per_concept" in src  # function present
    assert "+ tier_b_one_indicator_per_concept" not in src  # not chained live
