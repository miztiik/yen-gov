"""Structured pipeline events.

Each pipeline stage (fetch, parse, validate, emit) raises one of these
events at start and finish. They serve two purposes:

  1. Human-meaningful structured log lines via core.logging.StructuredLogger.
     The event_name is the stable string a future log-tailing UI greps on.
  2. A typed surface for the (future) FastAPI monitoring wrapper to subscribe
     to without re-parsing log text.

Events are pydantic ``BaseModel``s, frozen via ``ConfigDict(frozen=True)`` - one
typed model at every in-process boundary (the ingest pipeline plan's D3). They
keep a HAND-ROLLED ``to_extra`` serializer rather than ``model_dump(mode="json")``
because the latter serialises ``Path`` through ``str()`` (a backslash path on
Windows) and renders a tz-aware ``datetime`` as ``+00:00`` not ``Z`` - both of
which would break the repo-relative-POSIX + ``Z``-timestamp log contract
(CLAUDE.md section 2). The hand-rolled serializer routes every ``Path`` through
the single path-emit seam (``canonical/ingest/paths.py``) when a ``repo_root`` is
in scope, and every ``datetime`` to an RFC 3339 ``Z`` string.

Naming convention: <stage>.<verb> with verb in past tense for completion
events and present tense for in-progress (fetch.started / fetch.completed /
fetch.retried). When you add a new event, add it to ALL_EVENT_NAMES so the
test suite can pin the stable surface.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict


class _LoggerLike(Protocol):
    def info(self, event: str, msg: str, *, stage: str | None = None, **extra: object) -> None: ...
    def warn(self, event: str, msg: str, *, stage: str | None = None, **extra: object) -> None: ...
    def error(self, event: str, msg: str, *, stage: str | None = None, **extra: object) -> None: ...


class _Event(BaseModel):
    """Base for all events. Subclasses set the class-level event_name and level."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_name: ClassVar[str] = ""
    level: ClassVar[str] = "INFO"  # INFO | WARN | ERROR

    def msg(self) -> str:
        # Subclasses override for human-readable lines. Default = event name.
        return self.event_name

    def to_extra(self, *, repo_root: Path | None = None) -> dict[str, object]:
        """Flatten model fields to JSON-serialisable scalars.

        ``Path`` routes through the path-emit seam when ``repo_root`` is in
        scope (-> repo-relative POSIX, no drive letter); otherwise it falls
        back to ``.as_posix()``. The orchestrator passes ``repo_root`` when it
        logs real paths. ``datetime`` -> RFC 3339 with ``Z``; primitives pass
        through; anything else is ``repr()``'d to keep the line JSON-safe.

        Deliberately NOT ``model_dump(mode="json")``: that serialises ``Path``
        via ``str()`` (backslashes on Windows) and emits ``+00:00`` not ``Z``,
        both of which violate the log path/timestamp contract.
        """
        out: dict[str, object] = {}
        for name in type(self).model_fields:
            v = getattr(self, name)
            if isinstance(v, Path):
                if repo_root is not None:
                    # Lazy import keeps this module importable without pulling
                    # the canonical store layer into core's load-time graph;
                    # the path seam is a pure stdlib leaf (plan D3).
                    from yen_gov.canonical.ingest.paths import to_repo_relative_posix

                    out[name] = to_repo_relative_posix(v, repo_root=repo_root)
                else:
                    out[name] = v.as_posix()
            elif isinstance(v, datetime):
                out[name] = v.isoformat().replace("+00:00", "Z")
            elif isinstance(v, (str, int, float, bool)) or v is None:
                out[name] = v
            else:
                # Fallback - repr to keep the line JSON-safe.
                out[name] = repr(v)
        return out


def emit(
    logger: _LoggerLike,
    event: _Event,
    *,
    repo_root: Path | None = None,
    stage: str | None = None,
) -> None:
    """Send an event through a StructuredLogger at its declared level.

    ``repo_root`` is forwarded to ``to_extra`` so any ``Path`` field is emitted
    repo-relative POSIX; ``stage`` tags the line with the owning pipeline stage
    (``fetch`` / ``enrich`` / ``publish``).
    """
    method = getattr(logger, event.level.lower())
    method(event.event_name, event.msg(), stage=stage, **event.to_extra(repo_root=repo_root))


# --- pipeline lifecycle ----------------------------------------------------

class PipelineStarted(_Event):
    event_name: ClassVar[str] = "pipeline.started"
    run_id: str = ""

    def msg(self) -> str:
        return f"pipeline run {self.run_id} starting"


class PipelineCompleted(_Event):
    event_name: ClassVar[str] = "pipeline.completed"
    run_id: str = ""
    status: str = "ok"  # ok | failed
    artifacts_written: int = 0

    def msg(self) -> str:
        return f"pipeline run {self.run_id} {self.status} ({self.artifacts_written} artifacts)"


# --- fetch -----------------------------------------------------------------

class FetchStarted(_Event):
    event_name: ClassVar[str] = "fetch.started"
    url: str = ""
    source: str = ""

    def msg(self) -> str:
        return f"fetch {self.url}"


class FetchCompleted(_Event):
    event_name: ClassVar[str] = "fetch.completed"
    url: str = ""
    status_code: int = 0
    raw_path: Path | None = None
    bytes: int = 0

    def msg(self) -> str:
        return f"fetched {self.url} -> {self.status_code} ({self.bytes}B)"


class FetchRetried(_Event):
    event_name: ClassVar[str] = "fetch.retried"
    level: ClassVar[str] = "WARN"
    url: str = ""
    attempt: int = 0
    error: str = ""


class FetchFailed(_Event):
    event_name: ClassVar[str] = "fetch.failed"
    level: ClassVar[str] = "ERROR"
    url: str = ""
    error: str = ""


class FetchSkipped(_Event):
    event_name: ClassVar[str] = "fetch.skipped"
    level: ClassVar[str] = "INFO"
    year: int = 0
    raw_path: Path | None = None
    reason: str = ""

    def msg(self) -> str:
        return f"skipped {self.year}: {self.reason}"


# --- parse -----------------------------------------------------------------

class ParseStarted(_Event):
    event_name: ClassVar[str] = "parse.started"
    raw_path: Path | None = None
    parser: str = ""


class ParseCompleted(_Event):
    event_name: ClassVar[str] = "parse.completed"
    raw_path: Path | None = None
    parser: str = ""
    items: int = 0


class ParseFailed(_Event):
    event_name: ClassVar[str] = "parse.failed"
    level: ClassVar[str] = "ERROR"
    raw_path: Path | None = None
    parser: str = ""
    error: str = ""


# --- artifact emit ---------------------------------------------------------

class ArtifactWritten(_Event):
    event_name: ClassVar[str] = "artifact.written"
    path: Path | None = None
    schema_id: str = ""
    schema_version: str = ""


class ArtifactRejected(_Event):
    event_name: ClassVar[str] = "artifact.rejected"
    level: ClassVar[str] = "ERROR"
    path: Path | None = None
    schema_id: str = ""
    error: str = ""


# Stable surface - pin via test so we notice unintended renames.
ALL_EVENT_NAMES: tuple[str, ...] = (
    "pipeline.started",
    "pipeline.completed",
    "fetch.started",
    "fetch.completed",
    "fetch.retried",
    "fetch.failed",
    "fetch.skipped",
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
    "FetchSkipped",
    "FetchStarted",
    "ParseCompleted",
    "ParseFailed",
    "ParseStarted",
    "PipelineCompleted",
    "PipelineStarted",
    "emit",
]
