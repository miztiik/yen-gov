"""One-shot backfill: add ``delimitation_vintage`` to electoral entries in
``tools/boundaries/pipeline.json``.

Kept (not deleted) as the receipt of HOW the G10 follow-on bulk-edit was
performed. Per CLAUDE.md sect 10, structural fixes only — no monkey patches.

Context: G10 (PR #838) added ``delimitation_vintage`` as a REQUIRED kwarg
on ``tools/boundaries/_paths.py::derive_hive(...)`` for
``kind in {"ac", "pc"}``. The 31 AC entries in pipeline.json were not
backfilled at the time (pipeline.json is not exercised by pytest, so the
inputs were dormant). Any future ``python tools/boundaries/snapshot.py
--kind ac`` would have raised
``ValueError("kind='ac' is electoral; ``delim`` is required ...")``.

Behaviour:

* For every ``inputs[*]`` with ``kind == "ac"`` and no ``delimitation_vintage``:
  insert ``"delimitation_vintage": "2008"`` immediately after the ``kind`` key.
  All extant AC geometry reflects the 2008 Delimitation Commission Order;
  the 2024 order takes effect for LS2029 onwards.
* For every ``inputs[*]`` with ``kind == "pc"`` and no ``delimitation_vintage``:
  insert ``"delimitation_vintage": "2024"`` immediately after ``kind``.
  Matches the on-disk ``boundaries/electoral/delim=2024/pc/`` layout
  established by G10 PR #838.
* Other ``kind`` values (``country``, ``states``, ``districts``,
  ``subdistricts``, ``villages``, ``blocks``, ``panchayats``, ``wards``,
  ``postal``) are untouched.

Writes back with 2-space indent + trailing newline to match the existing
file style. Idempotent: re-running on an already-backfilled file is a
no-op (the conditional skips entries that already carry the key).
"""

from __future__ import annotations

import json
from pathlib import Path

PIPELINE_PATH = Path(__file__).resolve().parent / "pipeline.json"

DELIM_BY_KIND: dict[str, str] = {"ac": "2008", "pc": "2024"}


def _insert_after_kind(entry: dict[str, object], value: str) -> dict[str, object]:
    """Return a new dict with ``delimitation_vintage`` placed right after ``kind``.

    Python 3.7+ dict preserves insertion order; rebuilding the dict is
    the cleanest way to insert at a specific position.
    """
    rebuilt: dict[str, object] = {}
    for key, val in entry.items():
        rebuilt[key] = val
        if key == "kind":
            rebuilt["delimitation_vintage"] = value
    return rebuilt


def backfill(path: Path = PIPELINE_PATH) -> tuple[int, int]:
    """Backfill the file in-place. Returns ``(ac_inserted, pc_inserted)``."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    inputs = payload.get("inputs", [])
    ac_inserted = 0
    pc_inserted = 0
    new_inputs: list[dict[str, object]] = []
    for entry in inputs:
        kind = entry.get("kind")
        if kind in DELIM_BY_KIND and "delimitation_vintage" not in entry:
            new_entry = _insert_after_kind(entry, DELIM_BY_KIND[kind])
            new_inputs.append(new_entry)
            if kind == "ac":
                ac_inserted += 1
            elif kind == "pc":
                pc_inserted += 1
        else:
            new_inputs.append(entry)
    payload["inputs"] = new_inputs
    # Write bytes with explicit LF so the file matches the repo line-ending
    # convention regardless of platform default newline translation
    # (Python's ``write_text`` on Windows emits CRLF unless ``newline=""``
    # is passed; using ``write_bytes`` is the unambiguous form).
    serialised = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(serialised.encode("utf-8"))
    return ac_inserted, pc_inserted


if __name__ == "__main__":
    ac, pc = backfill()
    print(f"ac_inserted={ac} pc_inserted={pc}")
