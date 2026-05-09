"""Inventory endpoint — read-only listing of state × election coverage.

For every published election under ``datasets/elections/<event>/<state>/``,
report:

* counts of expected vs found per-AC result files (compared against
  ``datasets/reference/in/states/<state>/constituencies.json``);
* the summary file's ``$schema_version`` and ``sources[]`` (provenance);
* file mtime as a freshness proxy;
* whether a sqlite emit and parties.json sit alongside.

This is the walking-skeleton panel for Phase 4 (see
docs/architecture/admin/overview.md). Subsequent endpoints (schema
health, pipeline runs, patches) live in sibling modules.

Path convention: every path emitted here is **POSIX-relative to the
repo root** (CLAUDE.md §2). The admin frontend renders them as-is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Resolve repo root once. The package lives at
# <repo>/backend/yen_gov/admin/inventory.py — three .parent hops up
# from yen_gov/, plus one more to leave backend/.
REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS = REPO_ROOT / "datasets"


def _rel(p: Path) -> str:
    """Repo-relative POSIX path, per CLAUDE.md §2."""
    return PurePosixPath(p.resolve().relative_to(REPO_ROOT.resolve())).as_posix()


def _mtime_iso(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()


def _load_json(p: Path) -> Any:
    with p.open(encoding="utf-8") as f:
        return json.load(f)


@dataclass
class _StateEntry:
    eci_code: str
    name: str


def _load_states() -> dict[str, str]:
    """ECI code → display name from the reference file."""
    f = DATASETS / "reference" / "in" / "states.json"
    if not f.exists():
        return {}
    doc = _load_json(f)
    return {s["eci_code"]: s["name"] for s in doc.get("states", [])}


def _expected_acs(state: str) -> int | None:
    """Expected AC count from the constituencies reference file, or None
    when no reference is bootstrapped for this state yet."""
    f = DATASETS / "reference" / "in" / "states" / state / "constituencies.json"
    if not f.exists():
        return None
    doc = _load_json(f)
    return len(doc.get("constituencies", []))


def _scan_state(event: str, state: str) -> dict[str, Any]:
    base = DATASETS / "elections" / event / state
    summary_p = base / "result.summary.json"
    parties_p = base / "parties.json"
    sqlite_p = base / "results.sqlite"
    results_dir = base / "results"

    summary: dict[str, Any] = {}
    if summary_p.exists():
        try:
            doc = _load_json(summary_p)
            summary = {
                "schema_version": doc.get("$schema_version"),
                "sources": doc.get("sources", []),
                "total_seats": doc.get("total_seats"),
                "path": _rel(summary_p),
                "mtime": _mtime_iso(summary_p),
            }
        except (OSError, json.JSONDecodeError) as e:
            summary = {"error": f"{type(e).__name__}: {e}"}

    ac_files = (
        sorted(p.stem for p in results_dir.glob("*.json"))
        if results_dir.exists()
        else []
    )
    expected = _expected_acs(state)

    return {
        "event": event,
        "state": state,
        "summary": summary or None,
        "parties": _rel(parties_p) if parties_p.exists() else None,
        "sqlite": _rel(sqlite_p) if sqlite_p.exists() else None,
        "ac_results": {
            "found": len(ac_files),
            "expected": expected,
            "missing": (
                None
                if expected is None
                else max(expected - len(ac_files), 0)
            ),
        },
    }


@router.get("/inventory")
def inventory() -> dict[str, Any]:
    """Coverage matrix: every (event × state) folder under
    ``datasets/elections/`` with summary + AC counts.

    Returns
    -------
    dict
        ``events``: ordered list of event ids found on disk.
        ``states``: ECI code → display name mapping (subset present in
        the reference file; states not in the reference still appear in
        ``cells`` keyed by their code).
        ``cells``: list of per-(event, state) summary records.
    """
    elections_root = DATASETS / "elections"
    if not elections_root.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"datasets/elections does not exist at {elections_root!s}; "
                "run from the repo root."
            ),
        )

    state_names = _load_states()
    events = sorted(p.name for p in elections_root.iterdir() if p.is_dir())

    cells: list[dict[str, Any]] = []
    seen_states: set[str] = set()
    for event in events:
        event_dir = elections_root / event
        for state_dir in sorted(event_dir.iterdir()):
            if not state_dir.is_dir():
                continue
            state = state_dir.name
            seen_states.add(state)
            cells.append(_scan_state(event, state))

    # Names dict only includes states actually present in cells (plus any
    # extra reference entries — useful for the admin to spot states with
    # reference data but no election data yet).
    names = {code: state_names.get(code, code) for code in sorted(seen_states | state_names.keys())}

    return {"events": events, "states": names, "cells": cells}
