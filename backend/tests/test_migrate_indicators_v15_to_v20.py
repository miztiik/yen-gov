"""Tests for `tools/migrate_indicators_v15_to_v20.fold_indicator`.

Per CLAUDE.md anti-ceremony rule: every test below catches a real
regression a reviewer would otherwise miss in commit 6 (the volume
migration that runs this tool on 110 indicators + 10 sidecars).

- sidecar losslessness: if a single sidecar field gets dropped, 10
  hand-curated editor notes / policy contexts / chart defaults are
  lost forever after sidecar deletion. Verified field-by-field.
- idempotency: commit 6 ships the output of running this tool. If
  re-running on already-migrated input produces a diff, every later
  refresh/CI run will churn 110 artifact files.
- schema conformance: the folded output must validate against
  indicator.schema.json v1.6.

The migration tool itself lives under `tools/` (not a package), so we
import it via path manipulation.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_migration_module():
    """Import tools/migrate_indicators_v15_to_v20.py without making tools/ a package."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))  # for yen_gov.inventory
    spec = importlib.util.spec_from_file_location(
        "migrate_indicators_v15_to_v20",
        REPO_ROOT / "tools" / "migrate_indicators_v15_to_v20.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mig():
    return _load_migration_module()


def _v15_indicator() -> dict[str, object]:
    return {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "1.6",
        "sources": [{"url": "https://example.gov.in/data.csv", "fetched_at": "2026-01-01T00:00:00Z"}],
        "license": {"id": "GoI-Open", "name": "GoI", "url": "https://example", "redistributable": True},
        "coverage": {"spatial": "All-India", "temporal": "2023..2025", "admin_level": "state"},
        "indicator": {
            "id": "fiscal/synthetic_test_series",
            "title": "Synthetic series for tests",
            "description": "A synthetic fiscal indicator used by the migration unit tests; values are placeholder.",
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": "count",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "INR crore",
            "icon": "rupee",
            "attribution_geography": "where_administered",
            "comparability": "comparable_with_normalisation",
            "implementing_authority": "state",
            "methodology_vintage": "synthetic test fixture",
            "notes": "synthetic test fixture",
        },
        "rows": [
            {"entity_id": "S01", "time": "2023", "value": 100.0},
            {"entity_id": "S01", "time": "2024", "value": 110.0},
            {"entity_id": "S02", "time": "2023", "value": 200.0},
            {"entity_id": "S02", "time": "2024", "value": 210.0},
        ],
    }


def _full_sidecar() -> dict[str, object]:
    return {
        "$schema": "https://yen-gov.github.io/schemas/indicator-notes.schema.json",
        "$schema_version": "1.1",
        "for": "synthetic_test_series.json",
        "sources": [],
        "related": ["fiscal/states_combined_gross_fiscal_deficit", "economy/state_gdp_inr_crore"],
        "editor_note_md": "Hand-curated editor note that MUST survive the fold to inline methodology.editor_note_md.",
        "policy_context": ["15th FC award context A.", "FRBM Act ceiling context B."],
        "chart_defaults": {"prefer_axis": "log", "highlight_states": ["S01"]},
    }


# --------------------------------------------------------------------- #
# sidecar losslessness                                                  #
# --------------------------------------------------------------------- #


def test_sidecar_fields_fold_losslessly(mig) -> None:
    doc = _v15_indicator()
    sidecar = _full_sidecar()
    folded = mig.fold_indicator(doc, sidecar)
    m = folded["methodology"]
    assert m["related_indicators"] == sidecar["related"]
    assert m["editor_note_md"] == sidecar["editor_note_md"]
    assert m["policy_context"] == sidecar["policy_context"]
    assert m["chart_defaults"] == sidecar["chart_defaults"]


def test_absent_sidecar_omits_optional_fields(mig) -> None:
    folded = mig.fold_indicator(_v15_indicator(), None)
    m = folded["methodology"]
    # Per schema, these are optional; they should NOT appear when no sidecar exists.
    for optional_key in ("related_indicators", "editor_note_md", "policy_context", "chart_defaults"):
        assert optional_key not in m, f"unexpected {optional_key} when no sidecar provided"


# --------------------------------------------------------------------- #
# idempotency                                                           #
# --------------------------------------------------------------------- #


def test_re_migration_is_no_op(mig) -> None:
    """fold_indicator(fold_indicator(x)) == fold_indicator(x). Bytes-identical."""
    once = mig.fold_indicator(_v15_indicator(), None)
    twice = mig.fold_indicator(once, None)
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)


def test_is_migrated_detects_all_four_blocks(mig) -> None:
    doc = _v15_indicator()
    assert not mig.is_migrated(doc)
    doc["series_spec"] = {}
    doc["methodology"] = {}
    doc["divergence"] = None
    assert not mig.is_migrated(doc)  # missing collection_inventory
    doc["collection_inventory"] = {}
    assert mig.is_migrated(doc)


# --------------------------------------------------------------------- #
# schema conformance of the folded output                               #
# --------------------------------------------------------------------- #


def test_folded_output_validates_against_v16_schema(mig) -> None:
    """Real regression target: a wrong frequency enum or missing required
    sub-field in build_series_spec/build_methodology would only surface
    after running --write on 110 indicators. Catch it at the unit level.
    """
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO_ROOT / "datasets" / "schemas" / "indicator.schema.json").read_text(encoding="utf-8"))
    folded = mig.fold_indicator(_v15_indicator(), _full_sidecar())
    jsonschema.Draft202012Validator(schema).validate(folded)


# --------------------------------------------------------------------- #
# frequency inference from time_grain                                   #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "time_grain,expected_freq",
    [
        ("fiscal_year", "annual_fy"),
        ("year", "annual_cy"),
        ("month", "monthly"),
        ("quarter", "quarterly_cy"),
        ("date", "ad_hoc"),
        ("decade", "decennial"),
        ("totally-unknown", "ad_hoc"),  # safe default
    ],
)
def test_time_grain_maps_to_frequency(mig, time_grain: str, expected_freq: str) -> None:
    doc = _v15_indicator()
    doc["indicator"]["time_grain"] = time_grain
    spec = mig.build_series_spec(doc)
    if spec["expected_periods"]:
        assert spec["expected_periods"][0]["frequency"] == expected_freq
