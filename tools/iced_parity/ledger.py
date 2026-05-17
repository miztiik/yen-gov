"""Append-only JSONL ledger I/O for `datasets/parity/in/<id>.ledger.jsonl`.

Pure file I/O. Each record validates against
`datasets/schemas/parity-observation.schema.json` v1.0; this module does
NOT re-validate (callers that need validation should use the standalone
`python -m yen_gov validate --root .` against the aggregate
`indicators-parity.json`, or the JSONL-specific tool that ships in step 7).

The ledger is APPEND-ONLY by convention; no rewrite path exists here on
purpose — `git log <ledger>` is the history substrate per resolution
§5(b), and a rewrite would corrupt that.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Optional

LEDGER_ROOT_REL = "datasets/parity/in"


def ledger_path(repo_root: Path, indicator_id: str) -> Path:
    """Return the absolute path to the ledger for one indicator.

    `indicator_id` is the slug form (e.g. `energy/state_atc_losses_pct`).
    The slash becomes a directory separator on disk; the `.ledger.jsonl`
    suffix is appended.
    """
    return repo_root / LEDGER_ROOT_REL / f"{indicator_id}.ledger.jsonl"


def read_lines(path: Path) -> Iterator[dict]:
    """Yield each ledger record as a dict, in file order (oldest first)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        yield json.loads(raw)


def last_upstream_value(
    path: Path,
    entity_id: str,
    time: str,
    facet: Optional[str] = None,
) -> Optional[float]:
    """Return the most recent `value_upstream` for one cell, or None.

    Walks the ledger newest-first so a partial scan suffices on the
    common case (the cell was last seen recently). Reads the file into
    memory once; the per-indicator ledger is bounded by sample-count *
    runs and stays small for the foreseeable future (Phase 1 budget is
    quarterly runs; SQLite is the deferred structural fix at 10k+ rows
    per §6 risk 4).
    """
    if not path.exists():
        return None
    for raw in reversed(path.read_text(encoding="utf-8").splitlines()):
        if not raw.strip():
            continue
        obs = json.loads(raw)
        if (
            obs.get("entity_id") == entity_id
            and obs.get("time") == time
            and obs.get("facet") == facet
        ):
            return obs.get("value_upstream")
    return None


def append(path: Path, observation: dict) -> None:
    """Append one observation as a single JSON line.

    Creates parent directories if needed. The serialised form matches
    `ParityObservation.to_jsonl_dict()` field order, which mirrors the
    schema's required-fields-first ordering.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(observation, ensure_ascii=False) + "\n")
