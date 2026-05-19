"""CSV bundle emitter for one (event, state) slice.

Builds `results.csv` from a list of `ConstituencyResult` body payloads in
**long format** — one row per candidate (real or NOTA), with all per-AC and
per-candidate fields denormalised onto each row.

Public API (PR-O.3a — TODO 1.8b-writers-a — 2026-05-19):
  - `emit_state_csv_from_data(constituencies, output_path)` is the primary
    in-memory entry point. The pipeline calls this directly, avoiding a disk
    write-then-read cycle through per-AC JSON shards.
  - `emit_state_csv(state_dir, output_path=None)` is a thin wrapper that
    loads `results/<n>.json` from disk and delegates. Kept for one-shot CLI
    reruns where the data isn't already in memory.

Per [docs/concepts/dataset-shapes.md](../../../../docs/concepts/dataset-shapes.md):
- Long format round-trips losslessly to the per-AC JSON.
- The CSV is a researcher-facing **derived** artifact. It is NOT a contract
  surface: no JSON Schema, no `x-version`. Layout changes are documented in the
  module docstring and the emit-csv architecture doc.
- The emitter projects the canonical JSON and never imports from `pipeline/`.

Determinism: same input dicts MUST produce a byte-identical .csv output, so PR
diffs only appear when data changed. We achieve this by:
  - sorting rows by (ac_eci_no, rank),
  - using `\n` line terminators (not platform-native),
  - never embedding wall-clock timestamps,
  - atomic temp-file + os.replace, like the SQLite emitter.

Column order (v1):
    election, state, body, ac_eci_no, constituency_name,
    electors, votes_polled, turnout_pct,
    rank, candidate_name, party_short, party_eci_code,
    votes, vote_share_pct, is_winner, is_nota,
    gender, age, category
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from pathlib import Path

LAYOUT_VERSION = 1

_COLUMNS = [
    "election",
    "state",
    "body",
    "ac_eci_no",
    "constituency_name",
    "electors",
    "votes_polled",
    "turnout_pct",
    "rank",
    "candidate_name",
    "party_short",
    "party_eci_code",
    "votes",
    "vote_share_pct",
    "is_winner",
    "is_nota",
    "gender",
    "age",
    "category",
]


def emit_state_csv_from_data(
    *,
    constituencies: list[dict],
    output_path: Path,
) -> Path:
    """Build `results.csv` (long format) from in-memory data. Primary API.

    `constituencies` is a list of body_payload() dicts from
    `ConstituencyResult` (each with ``eci_no``, ``constituency_name``,
    ``totals``, ``candidates``, ``nota``, ...). The list does NOT need to be
    pre-sorted; the emitter sorts CSV rows by (ac_eci_no, rank) for
    byte-determinism.

    The CSV is written atomically: a temp file in the same directory, then
    `os.replace`. Returns the final path.
    """
    if not constituencies:
        raise ValueError(
            "emit_state_csv_from_data: constituencies list is empty"
        )

    rows: list[dict] = []
    for cr in constituencies:
        rows.extend(_rows_for_constituency(cr))

    # Deterministic ordering: (ac_eci_no, rank). NOTA gets rank = max_rank + 1
    # already, so it sorts last per constituency.
    rows.sort(key=lambda r: (r["ac_eci_no"], r["rank"]))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Render in-memory so we can write bytes with explicit `\n` newlines,
    # avoiding the platform-native `\r\n` that csv would otherwise emit.
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = buf.getvalue().encode("utf-8")

    fd, tmp_name = tempfile.mkstemp(
        prefix=".results-", suffix=".csv", dir=str(output_path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp_name, output_path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return output_path


def emit_state_csv(*, state_dir: Path, output_path: Path | None = None) -> Path:
    """Build `results.csv` (long format) by reading JSON shards from `state_dir`.

    Thin disk-wrapper around `emit_state_csv_from_data`. Loads
    `results/<n>.json` files from disk and delegates. Used by one-shot CLI
    reruns; the pipeline's emit step calls `emit_state_csv_from_data`
    directly to skip the disk round-trip.

    `state_dir` must contain `results/<n>.json` files. Returns the final
    path (defaults to `state_dir / "results.csv"`).
    """
    result_files = sorted(
        (state_dir / "results").glob("*.json"),
        key=lambda p: int(p.stem),
    )
    if not result_files:
        raise ValueError(f"no per-AC results found under {state_dir}/results/")

    constituencies = [_load_json(p) for p in result_files]
    return emit_state_csv_from_data(
        constituencies=constituencies,
        output_path=output_path or (state_dir / "results.csv"),
    )


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _rows_for_constituency(cr: dict) -> list[dict]:
    """One row per candidate + one row for NOTA. Skips the collapsed `others`
    aggregate — researchers who need the long tail can re-ingest from the
    canonical JSON. The CSV is the top-N + NOTA view, matching the JSON
    contract surface exactly.
    """
    totals = cr.get("totals") or {}
    base = {
        "election": cr.get("election"),
        "state": cr.get("state"),
        "body": cr.get("body"),
        "ac_eci_no": cr["eci_no"],
        "constituency_name": cr.get("constituency_name") or "",
        "electors": totals.get("electors"),
        "votes_polled": totals.get("votes_polled"),
        "turnout_pct": totals.get("turnout_pct"),
    }

    rows: list[dict] = []
    max_rank = 0
    for cand in cr.get("candidates", []):
        rank = cand["rank"]
        max_rank = max(max_rank, rank)
        rows.append({
            **base,
            "rank": rank,
            "candidate_name": cand["name"],
            "party_short": cand["party_short"],
            "party_eci_code": cand.get("party_eci_code") or "",
            "votes": cand["votes"],
            "vote_share_pct": cand["vote_share_pct"],
            "is_winner": 1 if cand.get("is_winner") else 0,
            "is_nota": 0,
            "gender": cand.get("gender") or "",
            "age": cand.get("age") if cand.get("age") is not None else "",
            "category": cand.get("category") or "",
        })

    nota = cr.get("nota") or {}
    if "votes" in nota:
        rows.append({
            **base,
            "rank": max_rank + 1,
            "candidate_name": "NOTA",
            "party_short": "NOTA",
            "party_eci_code": "",
            "votes": nota["votes"],
            "vote_share_pct": nota.get("vote_share_pct", 0.0),
            "is_winner": 0,
            "is_nota": 1,
            "gender": "",
            "age": "",
            "category": "",
        })

    return rows
