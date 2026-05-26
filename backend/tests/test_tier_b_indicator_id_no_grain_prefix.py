"""Tier-B tests for ``tier_b_indicator_id_no_grain_prefix`` (PR-B1 dark).

Per ADR-0044 + TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md
Phase B, indicator_id values that encode grain in the prefix
(``^(state|district|national)-``) are rejected. The check ships dark in
PR-B1 (function present, NOT chained into ``run()``) and enforces post-PR-B9.

Per CLAUDE.md anti-pattern (pytest never walks the real corpus) these
tests use ``tmp_path`` fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.validate import tier_b_indicator_id_no_grain_prefix


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


def test_passes_when_indicator_id_has_no_grain_prefix(tmp_path):
    _write_catalogue(tmp_path, [_BASE])
    assert tier_b_indicator_id_no_grain_prefix(tmp_path) == []


def test_rejects_state_prefix(tmp_path):
    bad = {**_BASE, "indicator_id": "state-electors-total"}
    _write_catalogue(tmp_path, [bad])
    failures = tier_b_indicator_id_no_grain_prefix(tmp_path)
    assert len(failures) == 1
    assert "state-electors-total" in failures[0].message
    assert "grain prefix" in failures[0].message


def test_rejects_district_prefix(tmp_path):
    bad = {**_BASE, "indicator_id": "district-pashu-aadhaar-count"}
    _write_catalogue(tmp_path, [bad])
    failures = tier_b_indicator_id_no_grain_prefix(tmp_path)
    assert len(failures) == 1
    assert "district-pashu-aadhaar-count" in failures[0].message


def test_rejects_national_prefix(tmp_path):
    bad = {**_BASE, "indicator_id": "national-installed-capacity-mw"}
    _write_catalogue(tmp_path, [bad])
    failures = tier_b_indicator_id_no_grain_prefix(tmp_path)
    assert len(failures) == 1
    assert "national-installed-capacity-mw" in failures[0].message


def test_does_not_reject_ac_or_party_or_candidate_or_india_prefixes(tmp_path):
    """The dark check only fences state/district/national. ac/party/candidate
    are real entity kinds per ADR-0044 standing reference; india-* is the
    legacy country-grain prefix (will migrate in B4 but is not in scope of
    this gate)."""
    rows = [
        {**_BASE, "indicator_id": "ac-turnout-pct"},
        {**_BASE, "indicator_id": "party-vote-share-pct"},
        {**_BASE, "indicator_id": "candidate-rank"},
        {**_BASE, "indicator_id": "india-thermal-capacity-retired-mw"},
    ]
    _write_catalogue(tmp_path, rows)
    assert tier_b_indicator_id_no_grain_prefix(tmp_path) == []


def test_check_is_dark_not_chained_into_run():
    """PR-B1 ships the check DARK -- NOT in run(). Enforced post-PR-B9."""
    from yen_gov import validate as v

    src = Path(v.__file__).read_text(encoding="utf-8")
    # Find the run() function body and confirm no chain entry.
    assert "tier_b_indicator_id_no_grain_prefix" in src  # function present
    # Naive but sufficient: the only mention should be the def + docstring,
    # never the `+ tier_b_indicator_id_no_grain_prefix(root)` chain pattern.
    assert "+ tier_b_indicator_id_no_grain_prefix" not in src


def test_no_op_when_catalogue_missing(tmp_path):
    assert tier_b_indicator_id_no_grain_prefix(tmp_path) == []
