"""Snapshot per-AC FPTP winners from the soon-to-be-deleted results.sqlite
ground-truth into a checked-in fixture.

Run once before deleting the 41 datasets/elections/*/*/results.sqlite files
in PR-R.3 (1.8e closure). The resulting fixture replaces the live-SQLite
inputs to test_canonical_parity_oracle.py; it pins per-AC winners at the
PR-R.2 known-good state so any future canonical-store rebuild that scrambles
winners trips the oracle.

Output: backend/tests/fixtures/canonical_winners_2026_05_19.json
Shape : {
  "captured_at": "2026-05-19T...Z",
  "captured_from_commit": "<git HEAD sha at snapshot time>",
  "slices": {
    "<event_id>/<state_code>": {
      "<ac_eci_no>": {"name": "...", "party_short": "...", "votes": 12345},
      ...
    },
    ...
  }
}

Idempotent: re-running with identical SQLite content produces byte-identical
JSON (sorted keys, no wall-clock other than the explicit captured_at field
which is itself stamped from the youngest SQLite mtime, NOT datetime.now()).

NOT a band-aid for the SQLite deletion — it's the structural fix: the test
question "does the canonical store agree with a trusted ground truth on
per-AC winners" survives the SQLite deletion by capturing the ground truth
as a fixture frozen at the PR-R.2 boundary.
"""
from __future__ import annotations

import io
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
ELECTIONS_ROOT = REPO_ROOT / "datasets" / "elections"
FIXTURE_DIR = REPO_ROOT / "backend" / "tests" / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "canonical_winners_2026_05_19.json"


def discover_sqlites() -> list[tuple[str, str, Path]]:
    out: list[tuple[str, str, Path]] = []
    for event_dir in sorted(ELECTIONS_ROOT.iterdir()):
        if not event_dir.is_dir() or event_dir.name.startswith("_"):
            continue
        for state_dir in sorted(event_dir.iterdir()):
            if not state_dir.is_dir():
                continue
            p = state_dir / "results.sqlite"
            if p.is_file():
                out.append((event_dir.name, state_dir.name, p))
    return out


def snapshot_winners(p: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    with sqlite3.connect(p) as scon:
        scon.row_factory = sqlite3.Row
        for row in scon.execute(
            "SELECT ac_eci_no, name, party_short, votes "
            "FROM candidates "
            "WHERE is_winner = 1 AND is_nota = 0 "
            "ORDER BY ac_eci_no"
        ):
            out[int(row["ac_eci_no"])] = {
                "name": row["name"],
                "party_short": row["party_short"],
                "votes": int(row["votes"]),
            }
    return out


def captured_at_from_corpus(slices: list[tuple[str, str, Path]]) -> str:
    # Derive the timestamp from the youngest source SQLite mtime so re-runs
    # against unchanged corpus produce identical bytes. Avoids datetime.now()
    # in artifact content (lessons.md 2026-05-16 fetched_at smear).
    if not slices:
        return "1970-01-01T00:00:00Z"
    youngest = max(p.stat().st_mtime for _, _, p in slices)
    return datetime.fromtimestamp(youngest, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def head_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def main() -> int:
    slices = discover_sqlites()
    print(f"discovered {len(slices)} SQLite slices")
    payload: dict = {
        "captured_at": captured_at_from_corpus(slices),
        "captured_from_commit": head_sha(),
        "captured_from_n_sqlites": len(slices),
        "note": (
            "Per-AC FPTP winners snapshot taken from the 41 "
            "datasets/elections/<event>/<state>/results.sqlite ground-truth "
            "files at the PR-R.2 boundary, immediately before those files "
            "are deleted in PR-R.3 (1.8e closure). The canonical-store "
            "parity oracle (backend/tests/test_canonical_parity_oracle.py) "
            "asserts current dim_candidates + election_results.parquet "
            "still produce the same per-AC winners as captured here. "
            "Regenerate via tools/snapshot_canonical_parity_oracle_fixture.py "
            "ONLY IF the legacy SQLites are restored and a known-good rebuild "
            "is in scope; in normal operation this file is immutable."
        ),
        "slices": {},
    }
    total_acs = 0
    for event_id, state_code, p in slices:
        winners = snapshot_winners(p)
        if not winners:
            print(f"  WARN: {event_id}/{state_code} has no winners; skipping")
            continue
        payload["slices"][f"{event_id}/{state_code}"] = {
            str(ac): w for ac, w in sorted(winners.items())
        }
        total_acs += len(winners)
    print(f"snapshotted {len(payload['slices'])} slices, {total_acs} AC winners total")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rel = FIXTURE_PATH.relative_to(REPO_ROOT).as_posix()
    print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
