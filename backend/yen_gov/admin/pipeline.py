"""Pipeline endpoints — list runs, tail logs, trigger commands.

Operator controls for ``yen_gov.cli`` from the admin Svelte app. The
trigger spawns ``python -m yen_gov <command> ...`` as a subprocess and
captures stdout+stderr into ``.runtime/logs/<run_id>/console.log``;
the run id is a sortable timestamp slug per user preference.

Concurrency: a single in-process lock allows one active spawn at a
time. The admin app is single-user-developer; we surface a 409 to the
UI rather than queuing.

Safety: every trigger requires ``confirm: True`` in the request body.
This is a deliberate speed-bump against double-click misclicks since
``run`` hits the live ECI site and writes to ``datasets/``.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_LOGS = REPO_ROOT / ".runtime" / "logs"

# Whitelist of CLI commands the panel can spawn. Anything outside this
# set returns 400 — keeps the surface minimal and auditable.
ALLOWED_COMMANDS: dict[str, str] = {
    "validate": "Two-tier schema + data validation (read-only).",
    "run": "Fetch + parse + emit one (event, state) AC slice. NETWORK + WRITES.",
    "reference": "Wikipedia scrape for reference data. NETWORK + WRITES.",
    "ingest-energy-power-plants": "india-geodata energy points → features + indicator. NETWORK + WRITES.",
    "ingest-fiscal-rbi": "RBI State Finances workbook → 8 fiscal indicators. NETWORK + WRITES.",
}

# Single-flight lock. The admin surface is single-user-developer
# (CLAUDE.md §1: localhost only); queueing would be over-engineering.
_lock = threading.Lock()
_active: dict[str, Any] | None = None


def _sweep_orphans() -> None:
    """Mark any pre-existing 'running' runs as 'abandoned'.

    If uvicorn is killed mid-run, the watcher thread dies with it and
    the run's meta.json stays at status='running' forever. On the next
    server start there can be no live subprocess for it (Popen is
    process-scoped), so the only honest status is 'abandoned'.
    """
    if not RUNTIME_LOGS.exists():
        return
    for d in RUNTIME_LOGS.iterdir():
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("status") == "running":
            meta["status"] = "abandoned"
            meta["finished_at"] = datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
            try:
                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            except OSError:
                pass


_sweep_orphans()


def _now_run_id() -> str:
    """Sortable timestamp run id (user preference: numeric, no T separator)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "_admin"


def _list_runs() -> list[dict[str, Any]]:
    if not RUNTIME_LOGS.exists():
        return []
    out: list[dict[str, Any]] = []
    for d in sorted(RUNTIME_LOGS.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        console = d / "console.log"
        structured = d / "yen-gov.log"
        meta = d / "meta.json"
        info: dict[str, Any] = {
            "run_id": d.name,
            "started_at": datetime.fromtimestamp(d.stat().st_mtime, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "has_console_log": console.exists(),
            "has_structured_log": structured.exists(),
            "command": None,
            "exit_code": None,
            "status": "unknown",
        }
        if meta.exists():
            try:
                info.update(json.loads(meta.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass
        # If still in flight (we hold the lock and run_id matches), reflect that.
        if _active and _active.get("run_id") == d.name and _active.get("status") == "running":
            info["status"] = "running"
        out.append(info)
    return out


@router.get("/pipeline/runs")
def list_runs() -> dict[str, Any]:
    """List runs under ``.runtime/logs/`` with status + meta."""
    runs = _list_runs()
    active = _active.copy() if _active else None
    return {
        "runs": runs[:100],  # cap for UI
        "total": len(runs),
        "active": active,
        "allowed_commands": ALLOWED_COMMANDS,
    }


def _tail(path: Path, max_lines: int) -> list[str]:
    """Read up to the last ``max_lines`` lines of a text file, fast-ish.

    Reads the whole file (logs are bounded by run length, single-digit MB
    in the worst case). If we ever need true tail-from-end seeking,
    swap for a chunked reverse-read.
    """
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as e:
        raise HTTPException(404, f"log not readable: {e}") from e
    return [ln.rstrip("\n") for ln in lines[-max_lines:]]


@router.get("/pipeline/runs/{run_id}")
def get_run(run_id: str, max_lines: int = 500) -> dict[str, Any]:
    """Return run meta + tail of console.log + tail of yen-gov.log."""
    if "/" in run_id or "\\" in run_id or run_id in ("", ".", ".."):
        raise HTTPException(400, "invalid run_id")
    d = RUNTIME_LOGS / run_id
    if not d.is_dir():
        raise HTTPException(404, f"no such run: {run_id}")

    meta: dict[str, Any] = {}
    meta_path = d / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    console: list[str] = []
    if (d / "console.log").exists():
        console = _tail(d / "console.log", max_lines)

    structured: list[dict[str, Any]] = []
    if (d / "yen-gov.log").exists():
        for ln in _tail(d / "yen-gov.log", max_lines):
            try:
                structured.append(json.loads(ln))
            except json.JSONDecodeError:
                # Tolerate the rare partial line at tail.
                continue

    status = meta.get("status", "unknown")
    if _active and _active.get("run_id") == run_id and _active.get("status") == "running":
        status = "running"

    return {
        "run_id": run_id,
        "status": status,
        "meta": meta,
        "console_tail": console,
        "structured_tail": structured,
    }


class TriggerBody(BaseModel):
    command: Literal[
        "validate",
        "run",
        "reference",
        "ingest-energy-power-plants",
        "ingest-fiscal-rbi",
    ] = Field(
        ..., description="CLI subcommand to spawn."
    )
    args: list[str] = Field(
        default_factory=list,
        description="Positional args (e.g. ['AcGenMay2026', 'S22'] for run).",
    )
    confirm: bool = Field(False, description="Must be true; speed-bump.")


def _spawn(command: str, args: list[str], run_id: str) -> dict[str, Any]:
    """Start the subprocess and a watcher thread to update meta on exit."""
    log_dir = RUNTIME_LOGS / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    console_path = log_dir / "console.log"
    meta_path = log_dir / "meta.json"

    full_argv = ["python", "-m", "yen_gov", command, *args]
    meta = {
        "run_id": run_id,
        "command": command,
        "args": args,
        "argv": full_argv,
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "running",
        "exit_code": None,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    fh = console_path.open("w", encoding="utf-8", buffering=1)  # line-buffered
    fh.write(f"$ {shlex.join(full_argv)}\n")
    fh.flush()

    proc = subprocess.Popen(
        full_argv,
        cwd=str(REPO_ROOT),
        stdout=fh,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    global _active
    _active = {**meta, "pid": proc.pid}

    def _watch() -> None:
        global _active
        rc = proc.wait()
        try:
            fh.write(f"\n[exit {rc}]\n")
            fh.flush()
        finally:
            fh.close()
        finished = {
            **meta,
            "status": "ok" if rc == 0 else "failed",
            "exit_code": rc,
            "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        meta_path.write_text(json.dumps(finished, indent=2), encoding="utf-8")
        with _lock:
            if _active and _active.get("run_id") == run_id:
                _active = None

    threading.Thread(target=_watch, name=f"watch-{run_id}", daemon=True).start()
    return meta


@router.post("/pipeline/runs", status_code=202)
def trigger_run(body: TriggerBody) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(400, "confirm must be true")

    # Whitelist already enforced by Literal, but keep an explicit guard
    # in case the union grows past safe-by-default.
    if body.command not in ALLOWED_COMMANDS:
        raise HTTPException(400, f"command not allowed: {body.command}")

    # Reject obviously unsafe arg shapes; CLI Typer adds its own parsing.
    for a in body.args:
        if not isinstance(a, str) or len(a) > 200 or "\n" in a or "\x00" in a:
            raise HTTPException(400, f"bad arg: {a!r}")

    with _lock:
        if _active and _active.get("status") == "running":
            raise HTTPException(
                409,
                f"another run is in flight: {_active.get('run_id')}",
            )
        run_id = _now_run_id()
        meta = _spawn(body.command, body.args, run_id)

    return {"run_id": run_id, "meta": meta}
