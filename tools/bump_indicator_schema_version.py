"""One-shot: bump $schema_version of every indicator artifact to 1.5.

Phase 3 of TODO/PER-INDICATOR-DOCS-PLAN.md — schema bump is purely
additive, so existing v1.4 artifacts remain valid; only the version
stamp needs to roll forward to satisfy the Tier-B validator
(backend/yen_gov/validate.py: $schema_version must equal x-version).

Preserves field order by only touching the $schema_version value.
Safe to re-run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "1.5"
INDICATORS_DIR = ROOT / "datasets" / "indicators" / "in"


def main() -> int:
    if not INDICATORS_DIR.exists():
        print(f"missing: {INDICATORS_DIR}", file=sys.stderr)
        return 1
    n_changed = 0
    n_total = 0
    for path in sorted(INDICATORS_DIR.rglob("*.json")):
        if path.name.endswith(".notes.json"):
            continue
        n_total += 1
        text = path.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("$schema_version") == TARGET_VERSION:
            continue
        doc["$schema_version"] = TARGET_VERSION
        new_text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
        path.write_text(new_text, encoding="utf-8")
        n_changed += 1
    print(f"bumped {n_changed} / {n_total} artifact(s) to v{TARGET_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
