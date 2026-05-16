"""Strip collection_inventory + series_spec.expected_* from indicator artifacts.

Migrates indicator artifacts from schema v3.0 to v4.0 (CLAUDE.md §11):

  - Removes the entire ``collection_inventory`` block (lifted to the
    external completeness index per ADR-0026).
  - Removes ``series_spec.expected_geographies``,
    ``series_spec.expected_periods``, and
    ``series_spec.expected_periods_inference`` (lifted to the same index).
    ``series_spec.description`` stays.
  - Bumps ``$schema_version`` from "3.0" to "4.0".
  - Idempotent: re-running on already-migrated artifacts is a no-op.

Side effects:
  - Walks ``datasets/indicators/in/**/*.json``.
  - Seeds ``datasets/reference/in/indicators-operator-state.json`` from the
    pre-migration ``collection_inventory.{frozen, refetch_requested,
    unavailable_periods}`` so operator state is preserved.

Reads operator state ONLY if currently absent or hand-empty; never
overwrites pre-existing operator-state entries.

Run:
    python tools/rip_to_v4.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDICATORS_DIR = REPO / "datasets" / "indicators" / "in"
OPERATOR_STATE_PATH = REPO / "datasets" / "reference" / "in" / "indicators-operator-state.json"

OLD_SERIES_SUBKEYS = (
    "expected_geographies",
    "expected_periods",
    "expected_periods_inference",
)


OPERATOR_STATE_SCHEMA_ID = "https://yen-gov.github.io/schemas/indicators-operator-state.schema.json"
OPERATOR_STATE_SCHEMA_VERSION = "1.0"


def _load_existing_operator_state() -> dict:
    if not OPERATOR_STATE_PATH.exists():
        return {}
    try:
        doc = json.loads(OPERATOR_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(doc, dict):
        return {}
    inds = doc.get("indicators")
    return inds if isinstance(inds, dict) else {}


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def rip_one(path: Path, op_state_acc: dict[str, dict]) -> bool:
    """Mutate one indicator file in place. Return True if it changed."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    # Preserve operator state before stripping the inventory block.
    inv = doc.get("collection_inventory")
    ind_id = (doc.get("indicator") or {}).get("id")
    if ind_id and isinstance(inv, dict):
        op = {}
        if inv.get("frozen") is True:
            op["frozen"] = True
        if inv.get("refetch_requested") is True:
            op["refetch_requested"] = True
        un = inv.get("unavailable_periods") or []
        if un:
            op["unavailable_periods"] = un
        if op:
            # Don't clobber pre-existing operator state for this id.
            op_state_acc.setdefault(ind_id, op)

    # Strip collection_inventory.
    if "collection_inventory" in doc:
        del doc["collection_inventory"]
        changed = True

    # Strip series_spec.expected_*.
    series_spec = doc.get("series_spec")
    if isinstance(series_spec, dict):
        for k in OLD_SERIES_SUBKEYS:
            if k in series_spec:
                del series_spec[k]
                changed = True

    # Bump $schema_version.
    if doc.get("$schema_version") != "4.0":
        doc["$schema_version"] = "4.0"
        changed = True

    if changed:
        _write_json(path, doc)
    return changed


def main() -> None:
    op_state = _load_existing_operator_state()
    seeded = dict(op_state)  # accumulator, starts from existing

    paths = sorted(INDICATORS_DIR.rglob("*.json"))
    # Exclude .notes.json sidecars.
    paths = [p for p in paths if not p.name.endswith(".notes.json")]

    changed_count = 0
    for p in paths:
        if rip_one(p, seeded):
            changed_count += 1

    # Write operator-state file (always create with envelope, even when empty).
    if not OPERATOR_STATE_PATH.exists() or seeded != op_state:
        envelope = {
            "$schema": OPERATOR_STATE_SCHEMA_ID,
            "$schema_version": OPERATOR_STATE_SCHEMA_VERSION,
            "sources": [],
            "indicators": seeded,
        }
        _write_json(OPERATOR_STATE_PATH, envelope)

    print(f"rip_to_v4: scanned {len(paths)} indicators, mutated {changed_count}")
    print(f"rip_to_v4: operator-state has {len(seeded)} entries at {OPERATOR_STATE_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()
