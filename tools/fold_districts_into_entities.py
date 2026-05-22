"""Fold 145 district rows from per-state ``districts.json`` files into
``datasets/taxonomy/entities.json`` as ``entity_type='district'`` rows.

T.0c-iii Phase A migration tool — one-shot. Run ONCE alongside the
companion change to ``backend/yen_gov/canonical/entities_seed.py``
that switches duplicate-``entity_id`` behaviour from "raise" to
"entities.json wins, skip districts.json row".

What this script does (and only this):

1. Reads ``datasets/taxonomy/entities.json`` (40 base entities today).
2. Walks ``datasets/reference/in/states/*/districts.json`` (6 files
   today: Assam, Gujarat, Kerala, Tamil Nadu, West Bengal, Puducherry).
3. Projects each district to an entity row using the EXACT same
   ``_district_to_entity`` projection the seed already uses, so the
   resulting ``entities.parquet`` (read by every downstream join) is
   byte-identical before and after this migration.
4. Skips districts without an ``lgd_code`` (Mahe / Yanam in
   Puducherry today) — matches the seed's existing behaviour because
   the canonical ``entity_id`` grammar ``IN-<state>-D<lgd_code>``
   requires an LGD code.
5. Sorts the new district rows by ``(parent_entity_id, entity_code)``
   for human-readable grouping in ``entities.json`` (parquet sort is
   independently fixed at ``(entity_type, entity_id)``).
6. Inserts each district as a single-line JSON object before the
   closing ``]`` of the ``entities`` array. Preserves the existing
   column alignment of the 40 base rows by doing a text insertion
   rather than a full ``json.dumps`` round-trip.

This script is KEPT in the tree (not deleted post-migration) as the
documented re-runner if districts.json ever changes shape and the
fold-in needs replaying — analogous to ``tools/repartition_elections.py``
from T.0a. Re-running on already-folded ``entities.json`` is a no-op:
every district's ``entity_id`` is already in the base set, so
``skipped_already_present`` accounts for all of them.

References:
    - TODO/20260517-canonical-long-format-pivot.md §0e.10.4 row 318
      (``reference/in/states/<S>/districts.json`` DELETE).
    - TODO/20260521-phase-2-preflight-audit-gregor.md #5 (T.0c-iii
      added as the cleanup arc that retires districts.json before
      Phase 2 NFHS-5).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.entities_seed import (  # noqa: E402
    _district_to_entity,
    _load_base_entities,
    _load_districts_files,
)


def main() -> int:
    entities_json = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"
    districts_root = REPO_ROOT / "datasets" / "reference" / "in" / "states"
    district_files = sorted(districts_root.glob("*/districts.json"))

    base = _load_base_entities(entities_json)
    base_ids = {e.entity_id for e in base}
    base_valid_from = {e.entity_id: e.entity_valid_from for e in base}

    new_rows = []
    skipped_no_lgd = 0
    skipped_already_present = 0
    for state_code, district in _load_districts_files(district_files):
        if not district.lgd_code:
            skipped_no_lgd += 1
            continue
        parent_id = f"IN-{state_code}"
        if parent_id not in base_valid_from:
            raise SystemExit(
                f"districts.json for {state_code!r}: unknown parent "
                f"entity {parent_id!r}; add the state to entities.json first"
            )
        entity = _district_to_entity(state_code, district, base_valid_from[parent_id])
        if entity.entity_id in base_ids:
            skipped_already_present += 1
            continue
        new_rows.append(entity)

    print(
        f"loaded {len(base)} base entities; "
        f"projected {len(new_rows)} new district rows "
        f"(skipped {skipped_no_lgd} without lgd_code, "
        f"{skipped_already_present} already in entities.json)"
    )

    if not new_rows:
        print("nothing to fold in; entities.json is up to date")
        return 0

    # Human-readable order: group by parent state, sort by LGD code
    # within each state. Parquet sort is fixed (entity_type, entity_id)
    # and runs inside the seed regardless of input order.
    new_rows.sort(key=lambda r: (r.parent_entity_id or "", r.entity_code))

    # Text-insertion preserves the column alignment of the 40 base rows.
    # Expected file ending today: `... }\n  ]\n}\n` (last entity, then
    # entities-array close, then root-object close, then trailing
    # newline).
    text = entities_json.read_text(encoding="utf-8")
    close_marker = "\n  ]\n}\n"
    if not text.endswith(close_marker):
        raise SystemExit(
            f"unexpected file ending in {entities_json}; "
            f"expected `\\n  ]\\n}}\\n` close marker"
        )
    head = text[: -len(close_marker)]
    if not head.endswith("}"):
        raise SystemExit(
            f"unexpected character before entities-array close: "
            f"head[-1]={head[-1]!r}"
        )
    head = head + ","

    district_lines = [""]  # blank-line separator from the historic UTs above
    for i, r in enumerate(new_rows):
        payload = r.model_dump()
        line_json = json.dumps(payload, ensure_ascii=False)
        comma = "" if i == len(new_rows) - 1 else ","
        district_lines.append(f"    {line_json}{comma}")
    district_section = "\n".join(district_lines)

    new_text = head + "\n" + district_section + close_marker
    entities_json.write_text(new_text, encoding="utf-8")
    print(
        f"wrote {entities_json.relative_to(REPO_ROOT).as_posix()}: "
        f"{len(base)} base + {len(new_rows)} districts = "
        f"{len(base) + len(new_rows)} entities"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
