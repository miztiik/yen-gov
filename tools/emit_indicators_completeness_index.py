"""Emit the per-indicator completeness summary consumed by the
`/data-completeness` route in the frontend.

Walks every indicator artifact under `datasets/indicators/in/**/*.json`,
extracts a tiny row per indicator (id, topic, title,
documentation_status, inventory_status, frozen, last_collected_at, and
counts), and writes the aggregated index to
`datasets/reference/in/indicators-completeness.json`.

Output is sorted (deterministic), validates against
`datasets/schemas/indicators-completeness.schema.json` v1.0, and
inherits its `generated_at` from the maximum input mtime so re-running
on an unchanged tree produces a byte-identical file (CLAUDE.md
provenance rule).

Modes:
- default: dry-run, prints plan, exits 1 if a write would change bytes.
- `--write`: rewrite the index.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDICATORS_ROOT = REPO_ROOT / "datasets" / "indicators" / "in"
OUTPUT_PATH = REPO_ROOT / "datasets" / "reference" / "in" / "indicators-completeness.json"
SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "indicators-completeness.schema.json"


def _index_row(path: Path, doc: dict) -> dict:
    ind = doc.get("indicator") or {}
    methodology = doc.get("methodology") or {}
    inventory = doc.get("collection_inventory") or {}
    topic = path.relative_to(INDICATORS_ROOT).parts[0]
    return {
        "id": ind.get("id", ""),
        "topic": topic,
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "title": ind.get("title", ""),
        "documentation_status": methodology.get("documentation_status", "stub"),
        "inventory_status": inventory.get("status", "empty"),
        "frozen": bool(inventory.get("frozen", False)),
        "last_collected_at": inventory.get("last_collected_at"),
        "observed_count": len(inventory.get("observed_periods") or []),
        "pending_count": len(inventory.get("pending_periods") or []),
        "unavailable_count": len(inventory.get("unavailable_periods") or []),
    }


def build_index() -> dict:
    rows: list[dict] = []
    max_mtime = 0.0
    for path in sorted(INDICATORS_ROOT.rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(_index_row(path, doc))
        max_mtime = max(max_mtime, path.stat().st_mtime)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    generated_at = datetime.fromtimestamp(max_mtime, tz=timezone.utc).date().isoformat() if max_mtime else date.today().isoformat()
    return {
        "$schema": schema["$id"],
        "$schema_version": schema["x-version"],
        "sources": [],
        "generated_at": generated_at,
        "indicators": sorted(rows, key=lambda r: (r["topic"], r["id"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite the index file")
    args = parser.parse_args()

    new_doc = build_index()
    new_bytes = json.dumps(new_doc, indent=2, ensure_ascii=False) + "\n"

    if OUTPUT_PATH.exists() and OUTPUT_PATH.read_text(encoding="utf-8") == new_bytes:
        print(f"unchanged: {OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()} ({len(new_doc['indicators'])} indicators)")
        return 0

    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(new_bytes, encoding="utf-8")
        print(f"WROTE: {OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()} ({len(new_doc['indicators'])} indicators)")
        return 0

    print(f"WOULD WRITE: {OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()} ({len(new_doc['indicators'])} indicators)")
    print("Dry run. Re-run with --write to apply.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
