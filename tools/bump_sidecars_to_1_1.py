"""Backfill indicator-notes sidecars to schema v1.1.

Two-place change per file:
  - $schema_version: "1.0" -> "1.1"
  - inject "sources": [] after "for" key (preserves JSON key order)

Run once; idempotent (skips files already at 1.1 with sources present).
"""

from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sidecars = list((ROOT / "datasets").rglob("*.notes.json"))
print(f"Found {len(sidecars)} sidecars")

for p in sidecars:
    raw = p.read_text(encoding="utf-8")
    obj = json.loads(raw)

    already_done = (
        obj.get("$schema_version") == "1.1"
        and isinstance(obj.get("sources"), list)
    )
    if already_done:
        print(f"  skip (already v1.1): {p.name}")
        continue

    # Rebuild dict preserving the canonical key order:
    # $schema, $schema_version, for, sources, ...rest
    new_obj: dict = {}
    for k in ("$schema", "$schema_version", "for"):
        if k in obj:
            new_obj[k] = obj[k]
    new_obj["$schema_version"] = "1.1"
    new_obj["sources"] = obj.get("sources", [])
    for k, v in obj.items():
        if k not in new_obj:
            new_obj[k] = v

    # Write with same formatting (2-space indent, trailing newline) as existing files
    p.write_text(json.dumps(new_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  bumped: {p.relative_to(ROOT).as_posix()}")

print("done")
