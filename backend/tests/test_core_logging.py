"""Tests for core.logging.StructuredLogger."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from yen_gov.core.logging import StructuredLogger, new_run_id


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln]


def test_writes_jsonl_under_runtime_logs(tmp_path: Path):
    with StructuredLogger(run_id="run-1", runtime_root=tmp_path, echo=False) as log:
        log.info("fetch.started", "starting fetch", url="https://example.com")

    expected = tmp_path / ".runtime" / "logs" / "run-1" / "yen-gov.log"
    assert expected.exists()
    records = _read_lines(expected)
    assert len(records) == 1
    rec = records[0]
    assert rec["level"] == "INFO"
    assert rec["event"] == "fetch.started"
    assert rec["msg"] == "starting fetch"
    assert rec["url"] == "https://example.com"
    assert rec["ts"].endswith("Z")


def test_all_levels_emit(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        log.debug("e.d", "d")
        log.info("e.i", "i")
        log.warn("e.w", "w")
        log.error("e.e", "e")
    records = _read_lines(log.path)
    assert [r["level"] for r in records] == ["DEBUG", "INFO", "WARN", "ERROR"]


def test_rejects_invalid_level(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        with pytest.raises(ValueError, match="level"):
            log.log("TRACE", "e", "m")


def test_rejects_empty_event(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        with pytest.raises(ValueError, match="event"):
            log.info("", "msg")


def test_rejects_extra_key_collision(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        with pytest.raises(ValueError, match="collides"):
            log.info("e", "m", ts="oops")


def test_rejects_bad_run_id(tmp_path: Path):
    with pytest.raises(ValueError, match="single path segment"):
        StructuredLogger(run_id="a/b", runtime_root=tmp_path, echo=False)


def test_appends_across_instances(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        log.info("e1", "first")
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        log.info("e2", "second")
    records = _read_lines(log.path)
    assert [r["event"] for r in records] == ["e1", "e2"]


def test_echo_to_stderr(tmp_path: Path, capsys):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=True) as log:
        log.info("e", "m", k="v")
    captured = capsys.readouterr()
    line = captured.err.strip()
    rec = json.loads(line)
    assert rec["event"] == "e"
    assert rec["k"] == "v"


def test_stage_tag_present_when_passed(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        log.info("fetch.started", "go", stage="fetch", url="https://x")
    rec = _read_lines(log.path)[0]
    assert rec["stage"] == "fetch"
    # One stream: stage is a structured field after the four structural ones.
    assert list(rec)[:5] == ["ts", "level", "event", "msg", "stage"]


def test_stage_absent_when_not_passed(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        log.info("fetch.started", "go")
    rec = _read_lines(log.path)[0]
    assert "stage" not in rec


def test_rejects_unknown_stage(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        with pytest.raises(ValueError, match="stage"):
            log.info("e", "m", stage="bogus")


def test_new_run_id_format():
    rid = new_run_id()
    assert re.fullmatch(r"\d{8}-[0-9a-f]{8}", rid), rid
    # No path separator, so it is a valid StructuredLogger run_id.
    assert "/" not in rid and "\\" not in rid


def test_new_run_id_accepted_by_logger(tmp_path: Path):
    rid = new_run_id()
    with StructuredLogger(run_id=rid, runtime_root=tmp_path, echo=False) as log:
        log.info("e", "m")
    assert (tmp_path / ".runtime" / "logs" / rid / "yen-gov.log").exists()
