"""Structured pipeline events.

Each pipeline stage (fetch, parse, validate, emit) raises one of these
events at start and finish. They serve two purposes:

  1. Human-meaningful structured log lines via core.logging.StructuredLogger.
     The event_name is the stable string a future log-tailing UI greps on.
  2. A typed surface for the (future) FastAPI monitoring wrapper to subscribe
     to without re-parsing log text.

Events are frozen dataclasses, not Pydantic models, because they never leave
the process and never get persisted as artifacts — keeping them lightweight
avoids dragging the schema-validation toolchain into hot paths.

Naming convention: <stage>.<verb> with verb in past tense for completion
events and present tense for in-progress (fetch.started / fetch.completed /
fetch.retried). When you add a new event, add it to ALL_EVENT_NAMES so the
test suite can pin the stable surface.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Protocol


class _LoggerLike(Protocol):
    def info(self, event: str, msg: str, **extra: object) -> None: ...
    def warn(self, event: str, msg: str, **extra: object) -> None: ...
    def error(self, event: str, msg: str, **extra: object) -> None: ...


@dataclass(frozen=True)
class _Event:
    """Base for all events. Subclasses set the class-level event_name and level."""

    event_name: ClassVar[str] = ""
    level: ClassVar[str] = "INFO"  # INFO | WARN | ERROR

    def msg(self) -> str:
        # Subclasses override for human-readable lines. Default = event name.
        return self.event_name

    def to_extra(self) -> dict[str, object]:
        # asdict + path/datetime → JSON-serialisable scalars.
        # Excludes nothing by default; subclasses can override.
        out: dict[str, object] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, Path):
                # Persisted as POSIX per CLAUDE.md §2.
                out[f.name] = v.as_posix()
            elif isinstance(v, datetime):
                out[f.name] = v.isoformat().replace("+00:00", "Z")
            elif isinstance(v, (str, int, float, bool)) or v is None:
                out[f.name] = v
            else:
                # Fallback — repr to keep the line JSON-safe.
                out[f.name] = repr(v)
        return out


def emit(logger: _LoggerLike, event: _Event) -> None:
    """Send an event through a StructuredLogger at its declared level."""
    method = getattr(logger, event.level.lower())
    method(event.event_name, event.msg(), **event.to_extra())


# --- pipeline lifecycle ----------------------------------------------------

@dataclass(frozen=True)
class PipelineStarted(_Event):
    event_name: ClassVar[str] = "pipeline.started"
    run_id: str = ""

    def msg(self) -> str:
        return f"pipeline run {self.run_id} starting"


@dataclass(frozen=True)
class PipelineCompleted(_Event):
    event_name: ClassVar[str] = "pipeline.completed"
    run_id: str = ""
    status: str = "ok"  # ok | failed
    artifacts_written: int = 0

    def msg(self) -> str:
        return f"pipeline run {self.run_id} {self.status} ({self.artifacts_written} artifacts)"


# --- fetch -----------------------------------------------------------------

@dataclass(frozen=True)
class FetchStarted(_Event):
    event_name: ClassVar[str] = "fetch.started"
    url: str = ""
    source: str = ""

    def msg(self) -> str:
        return f"fetch {self.url}"


@dataclass(frozen=True)
class FetchCompleted(_Event):
    event_name: ClassVar[str] = "fetch.completed"
    url: str = ""
    status_code: int = 0
    raw_path: Path | None = None
    bytes: int = 0

    def msg(self) -> str:
        return f"fetched {self.url} → {self.status_code} ({self.bytes}B)"


@dataclass(frozen=True)
class FetchRetried(_Event):
    event_name: ClassVar[str] = "fetch.retried"
    level: ClassVar[str] = "WARN"
    url: str = ""
    attempt: int = 0
    error: str = ""


@dataclass(frozen=True)
class FetchFailed(_Event):
    event_name: ClassVar[str] = "fetch.failed"
    level: ClassVar[str] = "ERROR"
    url: str = ""
    error: str = ""


# --- parse -----------------------------------------------------------------

@dataclass(frozen=True)
class ParseStarted(_Event):
    event_name: ClassVar[str] = "parse.started"
    raw_path: Path | None = None
    parser: str = ""


@dataclass(frozen=True)
class ParseCompleted(_Event):
    event_name: ClassVar[str] = "parse.completed"
    raw_path: Path | None = None
    parser: str = ""
    items: int = 0


@dataclass(frozen=True)
class ParseFailed(_Event):
    event_name: ClassVar[str] = "parse.failed"
    level: ClassVar[str] = "ERROR"
    raw_path: Path | None = None
    parser: str = ""
    error: str = ""


# --- artifact emit ---------------------------------------------------------

@dataclass(frozen=True)
class ArtifactWritten(_Event):
    event_name: ClassVar[str] = "artifact.written"
    path: Path | None = None
    schema_id: str = ""
    schema_version: str = ""


@dataclass(frozen=True)
class ArtifactRejected(_Event):
    event_name: ClassVar[str] = "artifact.rejected"
    level: ClassVar[str] = "ERROR"
    path: Path | None = None
    schema_id: str = ""
    error: str = ""


# Stable surface — pin via test so we notice unintended renames.
ALL_EVENT_NAMES: tuple[str, ...] = (
    "pipeline.started",
    "pipeline.completed",
    "fetch.started",
    "fetch.completed",
    "fetch.retried",
    "fetch.failed",
    "parse.started",
    "parse.completed",
    "parse.failed",
    "artifact.written",
    "artifact.rejected",
)


__all__ = [
    "ALL_EVENT_NAMES",
    "ArtifactRejected",
    "ArtifactWritten",
    "FetchCompleted",
    "FetchFailed",
    "FetchRetried",
    "FetchStarted",
    "ParseCompleted",
    "ParseFailed",
    "ParseStarted",
    "PipelineCompleted",
    "PipelineStarted",
    "emit",
]
