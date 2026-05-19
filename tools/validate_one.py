"""Validate a single JSON file against its declared $schema (relative path)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import jsonschema

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python tools/validate_one.py <path>", file=sys.stderr)
        return 2
    target = Path(sys.argv[1]).resolve()
    data = json.loads(target.read_text(encoding="utf-8"))
    schema_rel = data.get("$schema")
    if not schema_rel:
        print(f"  [warn] {target}: no $schema declared")
        return 1
    schema_path = (target.parent / schema_rel).resolve()
    if not schema_path.exists():
        print(f"  [fail] {target}: schema not found at {schema_path}")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.exceptions.ValidationError as exc:
        print(f"  [FAIL] {target}: {exc.message}")
        print(f"         path: {list(exc.absolute_path)}")
        return 1
    print(f"  [ok] {target.relative_to(Path.cwd())} validates against {schema_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
