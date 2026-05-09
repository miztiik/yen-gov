"""Structured JSON logging to .runtime/logs/<run-id>/yen-gov.log.

Every line is one JSON object. Fields:

  ts     - RFC 3339 UTC timestamp
  level  - DEBUG | INFO | WARN | ERROR
  event  - short stable event name (e.g. "fetch.started", "artifact.written")
  msg    - human-readable line
  ...    - any extra structured fields the caller passed

Two reasons for JSON-per-line over plain text:

  1. The pipeline emits structured events anyway (core/events.py); making them
     greppable from the log file means we don't need a second sink.
  2. Future tooling (the FastAPI monitoring wrapper alluded to in the project
     description) can tail the log and render structured events without
     re-parsing free text.

Per CLAUDE.md §7 [DEBUG]-prefixed lines are never written here — that prefix
is reserved for ephemeral console.log/print debugging that must be removed
before commit. Logs through this module are durable and structured.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


_LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")


class StructuredLogger:
    """Append-only JSON-lines logger.

    Args:
        run_id: identifier for this pipeline run (typically a timestamp slug
            like '2026-05-08T143000Z'). Used to group logs by invocation.
        runtime_root: parent of .runtime/. Logs land at
            <runtime_root>/.runtime/logs/<run_id>/yen-gov.log.
        echo: if True, also write each line to stderr as compact JSON. Useful
            in interactive runs and CI.
    """

    def __init__(
        self,
        *,
        run_id: str,
        runtime_root: Path,
        echo: bool = True,
    ) -> None:
        if not run_id or "/" in run_id or "\\" in run_id:
            raise ValueError(f"run_id must be a single path segment, got {run_id!r}")
        log_dir = runtime_root / ".runtime" / "logs" / run_id
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path = log_dir / "yen-gov.log"
        self._fh: TextIO = self._path.open("a", encoding="utf-8")
        self._echo = echo

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        try:
            self._fh.flush()
        finally:
            self._fh.close()

    def __enter__(self) -> StructuredLogger:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def log(self, level: str, event: str, msg: str, **extra: Any) -> None:
        if level not in _LEVELS:
            raise ValueError(f"level must be one of {_LEVELS}, got {level!r}")
        if not event:
            raise ValueError("event is required")
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "level": level,
            "event": event,
            "msg": msg,
        }
        # Caller's extra fields cannot shadow the structural ones above.
        for k, v in extra.items():
            if k in record:
                raise ValueError(f"extra key {k!r} collides with structural field")
            record[k] = v
        line = json.dumps(record, ensure_ascii=False, sort_keys=False)
        self._fh.write(line + "\n")
        self._fh.flush()
        if self._echo:
            print(line, file=sys.stderr)

    def info(self, event: str, msg: str, **extra: Any) -> None:
        self.log("INFO", event, msg, **extra)

    def warn(self, event: str, msg: str, **extra: Any) -> None:
        self.log("WARN", event, msg, **extra)

    def error(self, event: str, msg: str, **extra: Any) -> None:
        self.log("ERROR", event, msg, **extra)

    def debug(self, event: str, msg: str, **extra: Any) -> None:
        self.log("DEBUG", event, msg, **extra)
