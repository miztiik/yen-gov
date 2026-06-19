"""Tests for core.events - typed pipeline event surface."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

from yen_gov.core.events import (
    ALL_EVENT_NAMES,
    ArtifactRejected,
    ArtifactWritten,
    FetchCompleted,
    FetchFailed,
    FetchRetried,
    FetchSkipped,
    FetchStarted,
    ParseCompleted,
    ParseFailed,
    ParseStarted,
    PipelineCompleted,
    PipelineStarted,
    _Event,
    emit,
)
from yen_gov.core.logging import StructuredLogger


_EVENT_CLASSES = (
    PipelineStarted, PipelineCompleted,
    FetchStarted, FetchCompleted, FetchRetried, FetchFailed, FetchSkipped,
    ParseStarted, ParseCompleted, ParseFailed,
    ArtifactWritten, ArtifactRejected,
)


class _TickEvent(_Event):
    """Test-only event carrying a datetime field (no real event has one)."""

    event_name: ClassVar[str] = "test.tick"
    when: datetime | None = None


def test_all_event_names_registered():
    declared = {cls.event_name for cls in _EVENT_CLASSES}
    assert declared == set(ALL_EVENT_NAMES), "ALL_EVENT_NAMES out of sync with declared classes"
    assert len(ALL_EVENT_NAMES) == 12
    assert "fetch.skipped" in ALL_EVENT_NAMES


def test_event_names_unique_and_namespaced():
    assert len(set(ALL_EVENT_NAMES)) == len(ALL_EVENT_NAMES)
    for name in ALL_EVENT_NAMES:
        stage, _, verb = name.partition(".")
        assert stage and verb, f"event {name!r} must be <stage>.<verb>"


def test_path_serialised_as_posix(tmp_path: Path):
    p = tmp_path / "a" / "b.htm"
    e = ArtifactWritten(path=p, schema_id="x", schema_version="1.0")
    extra = e.to_extra()
    assert "/" in extra["path"]  # POSIX
    assert "\\" not in extra["path"]


def test_emit_writes_through_logger(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        emit(log, FetchCompleted(url="https://x/y", status_code=200, raw_path=tmp_path / "raw.htm", bytes=42))
        emit(log, FetchRetried(url="https://x/y", attempt=1, error="timeout"))
        emit(log, FetchFailed(url="https://x/y", error="500"))
    lines = [json.loads(ln) for ln in log.path.read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in lines] == ["fetch.completed", "fetch.retried", "fetch.failed"]
    assert [r["level"] for r in lines] == ["INFO", "WARN", "ERROR"]
    assert lines[0]["status_code"] == 200
    assert lines[0]["bytes"] == 42


def test_pipeline_lifecycle(tmp_path: Path):
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        emit(log, PipelineStarted(run_id="r"))
        emit(log, ParseStarted(raw_path=tmp_path / "x", parser="eci.partywise"))
        emit(log, ParseCompleted(raw_path=tmp_path / "x", parser="eci.partywise", items=234))
        emit(log, PipelineCompleted(run_id="r", status="ok", artifacts_written=235))
    events = [json.loads(ln)["event"] for ln in log.path.read_text(encoding="utf-8").splitlines()]
    assert events == ["pipeline.started", "parse.started", "parse.completed", "pipeline.completed"]


def test_events_are_frozen():
    e = FetchStarted(url="https://x", source="eci")
    with pytest.raises(ValidationError):
        e.url = "mutated"  # type: ignore[misc]


def test_oracle_to_extra_relativises_path_under_repo_root(tmp_path: Path):
    # ORACLE: a pydantic event built with an absolute Path under repo_root emits
    # a deterministic, repo-relative POSIX path field (no drive letter). This is
    # the golden to_extra() shape the pydantic swap must reproduce.
    repo_root = tmp_path
    abs_path = repo_root / "datasets" / "data" / "raw.htm"
    e = FetchCompleted(url="https://x/y", status_code=200, raw_path=abs_path, bytes=42)
    assert e.to_extra(repo_root=repo_root) == {
        "url": "https://x/y",
        "status_code": 200,
        "raw_path": "datasets/data/raw.htm",
        "bytes": 42,
    }


def test_oracle_logged_line_is_repo_relative_posix_and_z(tmp_path: Path):
    # The full log line: path field repo-relative POSIX (no 'C:'), ts ends 'Z',
    # stage tag present. Pinned as a golden line (ts checked by shape, not value).
    repo_root = tmp_path
    abs_path = repo_root / "datasets" / "x.csv"
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        emit(
            log,
            ArtifactWritten(path=abs_path, schema_id="geo", schema_version="1.0"),
            repo_root=repo_root,
            stage="publish",
        )
    rec = json.loads(log.path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["event"] == "artifact.written"
    assert rec["level"] == "INFO"
    assert rec["stage"] == "publish"
    assert rec["path"] == "datasets/x.csv"
    assert "C:" not in rec["path"]
    assert "\\" not in rec["path"]
    assert rec["ts"].endswith("Z")
    assert rec["schema_id"] == "geo"
    assert rec["schema_version"] == "1.0"


def test_to_extra_datetime_to_z():
    e = _TickEvent(when=datetime(2026, 6, 19, 12, 30, 0, tzinfo=timezone.utc))
    assert e.to_extra()["when"] == "2026-06-19T12:30:00Z"


def test_fetch_skipped_event(tmp_path: Path):
    raw = tmp_path / "raw" / "2019.json"
    e = FetchSkipped(year=2019, raw_path=raw, reason="hash unchanged")
    assert e.event_name == "fetch.skipped"
    assert e.level == "INFO"
    assert e.msg() == "skipped 2019: hash unchanged"
    assert e.to_extra(repo_root=tmp_path) == {
        "year": 2019,
        "raw_path": "raw/2019.json",
        "reason": "hash unchanged",
    }
    with StructuredLogger(run_id="r", runtime_root=tmp_path, echo=False) as log:
        emit(log, e, repo_root=tmp_path, stage="fetch")
    rec = json.loads(log.path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["event"] == "fetch.skipped"
    assert rec["level"] == "INFO"
    assert rec["stage"] == "fetch"
    assert rec["year"] == 2019
    assert rec["raw_path"] == "raw/2019.json"
