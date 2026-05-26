"""PR-A4: ``--table <stem>`` filter on ``lift-energy`` and ``lift-livestock``.

Tests both the adapter-level ``only=`` kwarg (unit-level, no I/O) and the
CLI command (via ``typer.testing.CliRunner``, no I/O — the filter rejects
unknown stems BEFORE attempting any write).

Per plan-doc TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md
PR-A4. Authority: Fowler (refactor safety) per CLAUDE.md §0a.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from yen_gov.canonical.adapters.energy import (
    build_envelopes as energy_build_envelopes,
)
from yen_gov.canonical.adapters.livestock import (
    build_envelopes as livestock_build_envelopes,
)
from yen_gov.cli import app


ENERGY_STEMS = {
    "energy_demand_supply",
    "energy_distribution_performance",
    "energy_fuel_consumption",
    "energy_generation",
    "energy_installed_capacity",
}

LIVESTOCK_STEMS = {
    "livestock_pashu_aadhaar",
    "livestock_owner_registration",
    "livestock_naip_iv",
}


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Adapter-level: build_envelopes(only=...)
# ---------------------------------------------------------------------------


def test_energy_build_envelopes_default_returns_all():
    envs = energy_build_envelopes(REPO_ROOT)
    assert {e.target_table_stem for e in envs} == ENERGY_STEMS


def test_energy_build_envelopes_only_narrows():
    envs = energy_build_envelopes(REPO_ROOT, only={"energy_generation"})
    assert [e.target_table_stem for e in envs] == ["energy_generation"]


def test_energy_build_envelopes_only_multiple_preserves_canonical_order():
    envs = energy_build_envelopes(
        REPO_ROOT,
        only={"energy_installed_capacity", "energy_demand_supply"},
    )
    # canonical write-order is alphabetical-by-stem; filter preserves it.
    assert [e.target_table_stem for e in envs] == [
        "energy_demand_supply",
        "energy_installed_capacity",
    ]


def test_energy_build_envelopes_unknown_stem_raises():
    with pytest.raises(ValueError, match="unknown energy table stem"):
        energy_build_envelopes(REPO_ROOT, only={"energy_bogus"})


def test_livestock_build_envelopes_default_returns_all():
    envs = livestock_build_envelopes(REPO_ROOT)
    assert {e.target_table_stem for e in envs} == LIVESTOCK_STEMS


def test_livestock_build_envelopes_only_narrows():
    envs = livestock_build_envelopes(
        REPO_ROOT, only={"livestock_pashu_aadhaar"}
    )
    assert [e.target_table_stem for e in envs] == ["livestock_pashu_aadhaar"]


def test_livestock_build_envelopes_unknown_stem_raises():
    with pytest.raises(ValueError, match="unknown livestock table stem"):
        livestock_build_envelopes(REPO_ROOT, only={"livestock_bogus"})


# ---------------------------------------------------------------------------
# CLI-level: --table flag rejects unknown stems before any write.
# ---------------------------------------------------------------------------


def test_cli_lift_energy_unknown_table_exits_nonzero(tmp_path):
    # tmp_path lacks a datasets/ subtree, but the --table validator must
    # also fail BEFORE the datasets/ check; assert exit-non-zero + the
    # unknown-stem message regardless of which guard fires.
    (tmp_path / "datasets").mkdir()
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "lift-energy",
            "--root",
            str(tmp_path),
            "--table",
            "energy_bogus",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "unknown energy table stem" in result.output


def test_cli_lift_livestock_unknown_table_exits_nonzero(tmp_path):
    (tmp_path / "datasets").mkdir()
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "lift-livestock",
            "--root",
            str(tmp_path),
            "--table",
            "livestock_bogus",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "unknown livestock table stem" in result.output


def test_cli_lift_energy_help_lists_table_option():
    runner = CliRunner()
    result = runner.invoke(app, ["lift-energy", "--help"])
    assert result.exit_code == 0
    assert "--table" in result.output


def test_cli_lift_livestock_help_lists_table_option():
    runner = CliRunner()
    result = runner.invoke(app, ["lift-livestock", "--help"])
    assert result.exit_code == 0
    assert "--table" in result.output
