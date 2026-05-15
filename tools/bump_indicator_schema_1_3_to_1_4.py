"""Bulk-bump $schema_version 1.3 -> 1.4 for indicator artifacts.

Phase 4 C2 of TODO/VIZ-LAYER-GAPS-PLAN.md: indicator schema gains
optional `facet_labels` (additive). Per CLAUDE.md §11 the per-artifact
$schema_version MUST equal the schema's x-version, so every indicator
file at 1.3 needs the stamp lifted. Purely additive — no field changes.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "datasets" / "indicators"

bumped = 0
for p in sorted(ROOT.rglob("*.json")):
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("$schema_version") == "1.3":
        doc["$schema_version"] = "1.4"
        p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        bumped += 1
print(f"bumped {bumped} files 1.3 -> 1.4")
