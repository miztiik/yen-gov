"""Mechanical bump of every indicator artifact's `$schema_version` from "1.5" to "1.6".

Part of the folded-indicator-and-collection-inventory PR (commit 3:
expand phase). Reads `datasets/schemas/indicator.schema.json` for the
target version, walks `datasets/indicators/in/**/*.json` (skipping
`*.notes.json` sidecars), and rewrites any artifact whose
`$schema_version != target` with the bumped value. Order of keys is
preserved; nothing else in the file is touched.

The v1.6 changes are purely additive (four new optional top-level
blocks + optional `rows[].period_label`), so existing artifacts remain
valid without any content change. The bump is required because the
strict `$schema_version == x-version` invariant in
`backend/yen_gov/core/validate.py` would otherwise reject every
artifact after the schema bump.

Idempotent: re-running on a fully-bumped tree produces no diff.

Usage (from repo root):
    python tools/bump_indicators_to_1_6.py            # dry-run, print plan
    python tools/bump_indicators_to_1_6.py --write    # apply bump
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "indicator.schema.json"
INDICATORS_ROOT = REPO_ROOT / "datasets" / "indicators" / "in"


def _target_version() -> str:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema["x-version"]


def _bump_one(path: Path, target: str, *, write: bool) -> str:
    """Return one of: 'already', 'bumped', 'skipped:<reason>'."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"skipped:parse-error({exc})"
    if not isinstance(doc, dict):
        return "skipped:not-a-dict"
    if "$schema_version" not in doc:
        return "skipped:no-schema-version"
    if doc["$schema_version"] == target:
        return "already"
    doc["$schema_version"] = target
    if write:
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "bumped"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="apply bump; default is dry-run")
    args = parser.parse_args()

    target = _target_version()
    print(f"Target $schema_version: {target}")

    counts: dict[str, int] = {}
    for path in sorted(INDICATORS_ROOT.rglob("*.json")):
        if path.name.endswith(".notes.json"):
            continue
        outcome = _bump_one(path, target, write=args.write)
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome == "bumped":
            rel = path.relative_to(REPO_ROOT).as_posix()
            verb = "BUMPED" if args.write else "WOULD BUMP"
            print(f"  {verb}: {rel}")
        elif outcome.startswith("skipped:"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            print(f"  {outcome.upper()}: {rel}")

    print()
    print("Summary:")
    for outcome in sorted(counts):
        print(f"  {outcome}: {counts[outcome]}")
    if not args.write and counts.get("bumped", 0) > 0:
        print("\nDry run. Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
