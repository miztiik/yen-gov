"""Contract tests for the goal-catalogue overlay seed.

Exercises the SDG-3 seed in a tmp_path corpus: frameworks + goals emit
unconditionally; goal_indicators is FK-guarded against variables.csv; the
emitted files pass the canonical validator; the seed is idempotent. No
real-corpus walk (CLAUDE anti-pattern); a minimal fixture tree is staged
under tmp_path.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.goals_seed import (
    SDG_FRAMEWORK_ID,
    UN_SOURCE_ID,
    seed_goals,
)


# --------------------------------------------------------------------------- #
# Fixture corpus
# --------------------------------------------------------------------------- #

_VARIABLES_HEADER = (
    "indicator_id,name,concept_id,unit,derivation,topic,source_id,"
    "update_period_days,time_min,time_max,entity_kinds\n"
)

_IMR_VARIABLE_ROW = (
    "infant-mortality-rate-per-1000,Infant mortality rate (per 1\\,000 live births),"
    "infant-mortality-rate,per 1\\,000 live births,,health,src-aaaaaaaaaaaa,"
    "365,2016,2023,country state\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _stage_empty_corpus(tmp_path: Path) -> None:
    # source.csv must exist for the FK target; seed upserts the UN row.
    _write(
        tmp_path / "datasets/data/entities/source.csv",
        "source_id,producer,title,vintage,url\n",
    )


def _stage_variables_with_imr(tmp_path: Path) -> None:
    _write(
        tmp_path / "datasets/data/variables.csv",
        _VARIABLES_HEADER + _IMR_VARIABLE_ROW,
    )


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- #
# Source id derivation
# --------------------------------------------------------------------------- #


def test_un_source_id_is_derived():
    assert UN_SOURCE_ID == derive_source_id(
        "United Nations",
        "Transforming our world: the 2030 Agenda for Sustainable Development (A/RES/70/1)",
        "2015",
    )
    assert UN_SOURCE_ID.startswith("src-")


# --------------------------------------------------------------------------- #
# Frameworks + goals emit unconditionally
# --------------------------------------------------------------------------- #


class TestFrameworkAndGoals:
    def test_framework_row_authority_class(self, tmp_path):
        _stage_empty_corpus(tmp_path)
        seed_goals(repo_root=tmp_path)
        rows = _read_rows(tmp_path / "datasets/data/frameworks.csv")
        assert len(rows) == 1
        fw = rows[0]
        assert fw["framework_id"] == SDG_FRAMEWORK_ID
        # SDG is a non-binding UN GA Resolution, NOT a treaty (Hans rule).
        assert fw["authority_class"] == "intergovernmental_resolution"
        assert "A/RES/70/1" in fw["disclaimer"]
        assert fw["source_id"] == UN_SOURCE_ID

    def test_goal_tree_has_sdg3_subtree(self, tmp_path):
        _stage_empty_corpus(tmp_path)
        seed_goals(repo_root=tmp_path)
        rows = _read_rows(tmp_path / "datasets/data/goals.csv")
        ids = {r["goal_id"] for r in rows}
        assert {
            "sdg-3", "sdg-3.1", "sdg-3.1.1", "sdg-3.2",
            "sdg-3.2.1", "sdg-3.2.2", "sdg-3.7",
        } <= ids

    def test_un_numbers_are_on_indicator_nodes_with_citation(self, tmp_path):
        _stage_empty_corpus(tmp_path)
        seed_goals(repo_root=tmp_path)
        by_id = {r["goal_id"]: r for r in _read_rows(tmp_path / "datasets/data/goals.csv")}
        # The three citable UN thresholds, each on a leaf node, each cited.
        assert by_id["sdg-3.1.1"]["target_value"] == "70"
        assert by_id["sdg-3.2.1"]["target_value"] == "25"
        assert by_id["sdg-3.2.2"]["target_value"] == "12"
        for gid in ("sdg-3.1.1", "sdg-3.2.1", "sdg-3.2.2"):
            assert by_id[gid]["target_bound"] == "at_most"
            assert by_id[gid]["source_id"] == UN_SOURCE_ID
            assert by_id[gid]["target_year"] == "2030"

    def test_target_nodes_carry_no_bare_number(self, tmp_path):
        # The number lives on the official-indicator child, not the target.
        _stage_empty_corpus(tmp_path)
        seed_goals(repo_root=tmp_path)
        by_id = {r["goal_id"]: r for r in _read_rows(tmp_path / "datasets/data/goals.csv")}
        assert by_id["sdg-3.2"]["target_value"] == ""
        assert by_id["sdg-3.2"]["better_direction"] == "lower"

    def test_target_scope_never_subnational(self, tmp_path):
        # No SDG row may claim a per-state statutory target (Hans rule).
        _stage_empty_corpus(tmp_path)
        seed_goals(repo_root=tmp_path)
        rows = _read_rows(tmp_path / "datasets/data/goals.csv")
        scopes = {r["target_scope"] for r in rows}
        assert "sub_national_statutory" not in scopes
        assert scopes <= {"global", "national", ""}

    def test_un_source_row_registered(self, tmp_path):
        _stage_empty_corpus(tmp_path)
        seed_goals(repo_root=tmp_path)
        rows = _read_rows(tmp_path / "datasets/data/entities/source.csv")
        assert any(r["source_id"] == UN_SOURCE_ID for r in rows)


# --------------------------------------------------------------------------- #
# goal_indicators is FK-guarded
# --------------------------------------------------------------------------- #


class TestFkGuardedMappings:
    def test_no_variables_yields_header_only(self, tmp_path):
        # No variables.csv -> every mapping skipped -> header-only file.
        _stage_empty_corpus(tmp_path)
        result = seed_goals(repo_root=tmp_path)
        assert result.mapping_count == 0
        assert "infant-mortality-rate-per-1000" in result.skipped_mappings
        rows = _read_rows(tmp_path / "datasets/data/goal_indicators.csv")
        assert rows == []

    def test_present_indicator_activates_mapping(self, tmp_path):
        _stage_empty_corpus(tmp_path)
        _stage_variables_with_imr(tmp_path)
        result = seed_goals(repo_root=tmp_path)
        assert result.mapping_count == 1
        rows = _read_rows(tmp_path / "datasets/data/goal_indicators.csv")
        assert len(rows) == 1
        m = rows[0]
        assert m["goal_id"] == "sdg-3.2"
        assert m["indicator_id"] == "infant-mortality-rate-per-1000"
        # IMR is a proxy, not the official SDG indicator.
        assert m["mapping_confidence"] == "proxy"
        assert m["mapping_method"] == "editorial_judgement"

    def test_crude_rates_never_mapped(self, tmp_path):
        # crude-birth-rate / crude-death-rate must NOT appear even if shipped
        # (no honest direction-of-good; excluded from the scorecard).
        _stage_empty_corpus(tmp_path)
        _write(
            tmp_path / "datasets/data/variables.csv",
            _VARIABLES_HEADER
            + "crude-death-rate-per-1000,Death rate,crude-death-rate,per 1\\,000,,demography,src-aaaaaaaaaaaa,365,2016,2023,country state\n",
        )
        result = seed_goals(repo_root=tmp_path)
        assert result.mapping_count == 0
        rows = _read_rows(tmp_path / "datasets/data/goal_indicators.csv")
        assert rows == []


# --------------------------------------------------------------------------- #
# Emitted overlay validates + idempotent
# --------------------------------------------------------------------------- #


class TestValidationAndIdempotency:
    def test_emitted_files_pass_validator(self, tmp_path):
        _stage_empty_corpus(tmp_path)
        _stage_variables_with_imr(tmp_path)
        seed_goals(repo_root=tmp_path)
        for rel, fc in (
            ("datasets/data/frameworks.csv", "datasets/data/frameworks.csv"),
            ("datasets/data/goals.csv", "datasets/data/goals.csv"),
            ("datasets/data/goal_indicators.csv", "datasets/data/goal_indicators.csv"),
        ):
            validate_csv(
                path=tmp_path / rel,
                file_class=fc,
                repo_root=tmp_path,
            )

    def test_second_run_is_noop(self, tmp_path):
        _stage_empty_corpus(tmp_path)
        _stage_variables_with_imr(tmp_path)
        seed_goals(repo_root=tmp_path)
        goals = tmp_path / "datasets/data/goals.csv"
        first = goals.read_bytes()
        mtime = goals.stat().st_mtime_ns
        seed_goals(repo_root=tmp_path)
        assert goals.read_bytes() == first
        assert goals.stat().st_mtime_ns == mtime
