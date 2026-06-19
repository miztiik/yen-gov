"""CLI smoke for the ingest sub-app (Row 4): mount + run usage + status.

The orchestrator's success path is fully exercised (with injected fixtures) in
``test_ingest_orchestrator.py``; here we verify the typer wiring: the sub-app
mounts, lists ``run`` + ``status``, enforces the run-scope usage rule, and the
``status`` verb reports per-source year spans end-to-end against a tmp repo.
"""
from __future__ import annotations

import io
from pathlib import Path

from openpyxl import Workbook
from typer.testing import CliRunner

from yen_gov.canonical.adapters.rbi_handbook import (
    ingest as rbi_ingest,
    spec_by_indicator_id,
)
from yen_gov.canonical.ingest.cli import ingest_app

runner = CliRunner()

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "kerala,Kerala,IN,state,IN-KL|S11|lgd:32,32,32\n"
    "odisha,Odisha,IN,state,IN-OD|S18|lgd:21,21,21\n"
    "jammu-and-kashmir,Jammu & Kashmir,IN,state,IN-JK|U08|lgd:1,1,1\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
)
_TFR_ROWS: list[list[object]] = [
    ["Table 6: State-Wise Total Fertility Rate", None, None, None],
    ["State", 2016, 2017, 2018],
    ["1. Andhra Pradesh", 1.7, 1.6, 1.6],
    ["2. Kerala", 1.8, 1.7, 1.7],
    ["Orissa", 2.1, 2.0, 1.9],
    ["Jammu & Kashmir", 2.0, "N.A.", 1.5],
    ["All India", 2.3, 2.2, 2.0],
    ["Source: SRS Statistical Report 2024", None, None, None],
]


def _wb_bytes(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _stage_tfr(repo_root: Path) -> Path:
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    staging = repo_root / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "table-total-fertility-rate.xlsx").write_bytes(_wb_bytes(_TFR_ROWS))
    return staging


class TestHelpAndMount:
    def test_subapp_lists_run_and_status(self):
        result = runner.invoke(ingest_app, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "status" in result.output

    def test_mounted_in_main_cli(self):
        from yen_gov.cli import app

        result = runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "status" in result.output


class TestRunUsage:
    def test_no_scope_exits_two(self, tmp_path):
        result = runner.invoke(ingest_app, ["run", "--root", str(tmp_path)])
        assert result.exit_code == 2
        assert "specify --indicator" in result.output

    def test_resume_flag_is_accepted(self, tmp_path):
        # --resume (Row 5) is part of the run grammar; the usage rule still
        # applies, so a scopeless run with --resume exits 2 (not a parse error).
        result = runner.invoke(
            ingest_app, ["run", "--resume", "--root", str(tmp_path)]
        )
        assert result.exit_code == 2
        assert "specify --indicator" in result.output

    def test_run_help_lists_resume(self):
        result = runner.invoke(ingest_app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--resume" in result.output


class TestStatusCli:
    def test_status_shows_per_source_year_spans(self, tmp_path):
        staging = _stage_tfr(tmp_path)
        rbi_ingest(
            repo_root=tmp_path,
            staging_dir=staging,
            specs=(spec_by_indicator_id("total-fertility-rate"),),
        )
        result = runner.invoke(
            ingest_app,
            ["status", "--indicator", "total-fertility-rate", "--root", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        assert "rbi-handbook" in result.output
        assert "2016-2018" in result.output

    def test_status_reports_no_coverage(self, tmp_path):
        result = runner.invoke(
            ingest_app,
            ["status", "--indicator", "total-fertility-rate", "--root", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        assert "rbi-handbook" in result.output
        assert "none yet" in result.output
