"""Tests for core.events — typed pipeline event surface."""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.core.events import (
    ALL_EVENT_NAMES,
    ArtifactRejected,
    ArtifactWritten,
    FetchCompleted,
    FetchFailed,
    FetchRetried,
    FetchStarted,
    ParseCompleted,
    ParseFailed,
    ParseStarted,
    PipelineCompleted,
    PipelineStarted,
    emit,
)
from yen_gov.core.logging import StructuredLogger


_EVENT_CLASSES = (
    PipelineStarted, PipelineCompleted,
    FetchStarted, FetchCompleted, FetchRetried, FetchFailed,
    ParseStarted, ParseCompleted, ParseFailed,
    ArtifactWritten, ArtifactRejected,
)


def test_all_event_names_registered():
    declared = {cls.event_name for cls in _EVENT_CLASSES}
    assert declared == set(ALL_EVENT_NAMES), "ALL_EVENT_NAMES out of sync with declared classes"


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
