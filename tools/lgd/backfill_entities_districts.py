"""tools/lgd/backfill_entities_districts.py — fold LGD districts CSV into entities.json.

Phase 0.2 of TODO/20260524-boundary-coverage-expansion-plan.md.

After T.0c-iii (ADR-0033) ``datasets/taxonomy/entities.json`` is the
sole curated registry for the entity dimension. The 145 districts on
disk today are the ECI-mapped slice (S03/S06/S11/S22/S25/U07). The
remaining 639 districts published by LGD (Ministry of Panchayati Raj,
via ramSeraph's opendata mirror, snapshot at
``datasets/taxonomy/lgd/districts-latest.csv``) need to land before
district-keyed citizen surfaces (financial inclusion, rainfall, water,
topography) can render meaningfully.

This script is the GENERATOR per plan §0.2 ("the generator suggests
rows; the operator confirms"). It is:

- **Pure stdlib** — ``csv`` + ``json`` only. Per CLAUDE.md §4 ``tools/``
  MUST NOT import ``backend/yen_gov`` runtime modules. The state-LGD
  resolver logic is re-implemented inline (5 lines) to keep this seam
  closed; the upstream ``yen_gov.canonical.state_lgd_resolver`` is the
  prose reference but not a dependency.
- **Idempotent** — re-runs are no-ops once every CSV row has a
  matching entities.json entry (same lgd_code already present →
  skipped silently). Operators can re-run safely after a fresh LGD
  snapshot to absorb deltas (new districts, renames; mass deletions
  are handled by a separate retire-flow not in scope here).
- **Deterministic** — new rows are sorted by ``(parent_entity_id,
  int(lgd_code))`` before insertion so the patch is byte-stable
  across runs.

Row shape conventions (locked per plan §0.2 + ADR-0033):

- ``entity_id`` = ``IN-<state_eci>-D<lgd_code>`` (e.g. ``IN-S22-D610``
  for Ariyalur). State ECI codes are looked up from entities.json's
  currently-valid state/UT rows (``entity_valid_to is None``); historic
  composite J&K (S09, valid 1947-2019) is filtered out so districts
  for ``state_lgd=1`` correctly attach to U08 (J&K UT, post-2019).
- ``entity_type`` = ``"district"``, ``entity_level`` = ``"district"``.
- ``entity_code`` = ``lgd_code`` string (issuing-authority code per
  CLAUDE.md §3).
- ``display_name`` = LGD CSV ``District Name(In English)`` verbatim.
  Per plan §0.2 the operator confirms casing / hyphenation in a
  follow-up review pass; for the initial backfill we trust the LGD
  publisher's spelling (e.g. ``"North And Middle Andaman"``) — the
  alternative is hand-classifying 639 strings which exceeds the
  generator's scope. Operator-flag-able via a normal docs/data PR
  once any specific row is challenged.
- ``parent_entity_id`` = ``IN-<state_eci>`` (resolved from the state
  map; raises ``KeyError`` loud if a CSV row references an unknown
  state, which would indicate a stale entities.json or a malformed
  CSV).
- ``entity_valid_from`` = ``1947`` for ALL backfilled rows. Defensible
  default: the renderer greys (not hides) entities for observation
  years < ``entity_valid_from``, so 1947 is the data-loss-free choice
  for the post-Independence corpus. Per plan §0.2 operators may amend
  individual rows to the post-2011 gazette-carve-out year (e.g. 2020
  for Mayiladuthurai, 2014 for the Telangana split) in follow-up PRs;
  hand-researching 639 gazette dates exceeds the generator's scope.
- ``entity_valid_to`` = ``None`` (extant).
- ``display_name_local`` = ``None`` (LGD CSV ships only English).
- ``iso_3166_2`` = ``None`` (ISO codes are state-level, not district).
- ``lgd_code`` = ``District Code`` string from CSV.
- ``legacy_id`` = ``None``. The 145 ECI-mapped districts carry the
  Wikipedia 3-letter slug here (``ARI`` for Ariyalur, ``CHN`` for
  Chennai) as a forward-resolve aid for old URLs; the 639 backfilled
  districts have no such public predecessor identifier so they stay
  null. Per ADR-0033 ``legacy_id`` is optional and exists only when
  an entity HAD a prior public identifier.
- ``notes`` = ``"LGD district. Census 2011 code: <N>."`` when the CSV
  ``Census 2011 Code`` column is non-zero; ``"LGD district."`` when
  the code is 0 (post-2011 carve-out — no 2011 ancestor). Carrying
  the Census-2011 code in ``notes`` per plan §0.2 ("LGD-CSV
  Census 2011 Code as a structured-comment field so the operator can
  spot any LGD ↔ Census-2011 mismatches"). NOT a schema field — that
  would require an additive bump to v1.3 and a Pydantic model
  widening cascade; ``notes`` is the citizen-friendly free-text slot
  per entity.schema.json v1.2.

Usage:

    python tools/lgd/backfill_entities_districts.py            # apply in place
    python tools/lgd/backfill_entities_districts.py --dry-run  # print summary only

Acceptance gates (per plan §0.2):

- entities.json row count grows by exactly the count of CSV districts
  not already on disk (today 639 → 0 after first apply; 0 thereafter
  until the next LGD snapshot adds new codes).
- Re-running the script on a freshly-updated file is a byte-identity
  no-op (idempotent).
- ``python -m yen_gov emit-taxonomy --root .`` regenerates
  ``datasets/taxonomy/entities.parquet`` byte-stably (the seed code
  sorts by ``(entity_type, entity_id)``).
- ``python -m yen_gov validate --root .`` reports OK.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTITIES_JSON = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"
LGD_DISTRICTS_CSV = REPO_ROOT / "datasets" / "taxonomy" / "lgd" / "districts-latest.csv"

# Entity-shape constants — mirror datasets/schemas/entity.schema.json v1.2.
# Held here as data (not imported from backend) per CLAUDE.md §4.
_DISTRICT_VALID_FROM_DEFAULT = 1947
_NOTES_WITH_CENSUS = "LGD district. Census 2011 code: {c2011}."
_NOTES_WITHOUT_CENSUS = "LGD district."


def build_state_lgd_to_eci_map(entities: list[dict[str, Any]]) -> dict[int, str]:
    """Project an entities list to ``{lgd_int: ECI_code}`` for state/UT rows.

    Mirrors ``backend.yen_gov.canonical.state_lgd_resolver.build_state_lgd_to_eci_map``
    but re-implemented inline so this tool stays free of backend imports
    per CLAUDE.md §4. Filters to currently-valid state/UT rows
    (``entity_valid_to is None``) so historic composite J&K (S09, valid
    1947-2019) is excluded and ``state_lgd=1`` correctly maps to U08
    (J&K UT, post-2019).
    """
    mapping: dict[int, str] = {}
    for row in entities:
        if row.get("entity_type") not in ("state", "ut"):
            continue
        if row.get("entity_valid_to") is not None:
            continue
        lgd_str = row.get("lgd_code")
        if lgd_str is None:
            continue
        lgd_int = int(lgd_str)
        eci = row["entity_code"]
        if lgd_int in mapping and mapping[lgd_int] != eci:
            raise ValueError(
                f"duplicate state_lgd {lgd_int}: {mapping[lgd_int]!r} vs {eci!r}"
            )
        mapping[lgd_int] = eci
    return mapping


def make_district_row(
    *,
    state_eci: str,
    lgd_code: str,
    display_name: str,
    census_2011_code: str,
) -> dict[str, Any]:
    """Build one entities.json district row from a single LGD CSV row.

    Field order matches the existing district row block in entities.json
    so the resulting JSON visually aligns with the hand-curated 145 on
    diff. ``census_2011_code`` is the raw CSV string (LGD ships "0" for
    post-2011 carve-outs with no 2011 ancestor); we coerce to int to
    test for the absent-marker and reformat into the notes string.
    """
    notes = (
        _NOTES_WITH_CENSUS.format(c2011=int(census_2011_code))
        if int(census_2011_code) > 0
        else _NOTES_WITHOUT_CENSUS
    )
    return {
        "entity_id": f"IN-{state_eci}-D{lgd_code}",
        "entity_type": "district",
        "entity_level": "district",
        "entity_code": lgd_code,
        "display_name": display_name,
        "display_name_local": None,
        "parent_entity_id": f"IN-{state_eci}",
        "entity_valid_from": _DISTRICT_VALID_FROM_DEFAULT,
        "entity_valid_to": None,
        "iso_3166_2": None,
        "lgd_code": lgd_code,
        "legacy_id": None,
        "notes": notes,
    }


def compute_backfill(
    entities_doc: dict[str, Any],
    csv_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Return the list of NEW district rows to add to ``entities_doc``.

    Skips CSV rows whose ``District Code`` is already present on a
    district row in entities.json (idempotent). Raises ``KeyError`` on
    a CSV row whose ``State Code`` is not in the entities.json state
    map (loud-fail per CLAUDE.md §1 Holy Law #5; the right response is
    to add the missing state row to entities.json first, not silently
    drop the district).

    New rows are sorted by ``(parent_entity_id, int(lgd_code))`` for
    determinism so the emitted JSON patch is byte-stable across runs.
    """
    entities = entities_doc["entities"]
    state_map = build_state_lgd_to_eci_map(entities)
    existing_district_lgds: set[str] = {
        e["lgd_code"]
        for e in entities
        if e["entity_type"] == "district" and e.get("lgd_code")
    }

    new_rows: list[dict[str, Any]] = []
    for row in csv_rows:
        lgd_code = row["District Code"].strip()
        if lgd_code in existing_district_lgds:
            continue
        state_lgd_int = int(row["State Code"].strip())
        if state_lgd_int not in state_map:
            raise KeyError(
                f"CSV state_code {state_lgd_int} (row District Code "
                f"{lgd_code} {row.get('District Name(In English)')!r}) "
                "not present in entities.json state/UT map. Add the "
                "missing state row to entities.json before backfilling "
                "its districts."
            )
        state_eci = state_map[state_lgd_int]
        new_rows.append(
            make_district_row(
                state_eci=state_eci,
                lgd_code=lgd_code,
                display_name=row["District Name(In English)"].strip(),
                census_2011_code=row["Census 2011 Code"].strip() or "0",
            )
        )

    new_rows.sort(key=lambda r: (r["parent_entity_id"], int(r["lgd_code"])))
    return new_rows


def apply_backfill(
    entities_path: Path,
    csv_path: Path,
) -> tuple[int, int]:
    """Read entities.json + LGD CSV, compute new rows, write entities.json.

    Returns ``(new_row_count, total_entities_after)``. When
    ``new_row_count`` is 0 the file is NOT rewritten (byte-stable
    idempotency for the no-op case).
    """
    entities_doc = json.loads(entities_path.read_text(encoding="utf-8"))
    with csv_path.open(encoding="utf-8", newline="") as fh:
        csv_rows = list(csv.DictReader(fh))

    new_rows = compute_backfill(entities_doc, csv_rows)
    if not new_rows:
        return 0, len(entities_doc["entities"])

    entities_doc["entities"].extend(new_rows)
    # Write with the same JSON shape entities.json uses today: 2-space
    # indent, ASCII-friendly escapes off, trailing newline. The seed
    # compiler sorts by (entity_type, entity_id) at parquet emit time
    # so the in-file order is operator-friendly (new rows appended at
    # the end of the array; reviewers see exactly which rows are net
    # new in the diff).
    entities_path.write_text(
        json.dumps(entities_doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return len(new_rows), len(entities_doc["entities"])


def _summary(
    new_rows: list[dict[str, Any]],
    total_csv: int,
    total_existing_districts: int,
) -> str:
    by_state: dict[str, int] = {}
    for r in new_rows:
        by_state[r["parent_entity_id"]] = by_state.get(r["parent_entity_id"], 0) + 1
    lines = [
        f"LGD districts CSV rows:           {total_csv}",
        f"districts already in entities:    {total_existing_districts}",
        f"new district rows to add:         {len(new_rows)}",
        "",
        "new rows by parent state/UT (top 10):",
    ]
    for parent, count in sorted(by_state.items(), key=lambda kv: (-kv[1], kv[0]))[:10]:
        lines.append(f"  {parent}: {count}")
    if len(by_state) > 10:
        lines.append(f"  ... {len(by_state) - 10} more states/UTs")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the backfill summary without modifying entities.json.",
    )
    parser.add_argument(
        "--entities",
        type=Path,
        default=ENTITIES_JSON,
        help=f"Path to entities.json (default: {ENTITIES_JSON.relative_to(REPO_ROOT)!s})",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=LGD_DISTRICTS_CSV,
        help=f"Path to LGD districts CSV (default: {LGD_DISTRICTS_CSV.relative_to(REPO_ROOT)!s})",
    )
    args = parser.parse_args(argv)

    entities_doc = json.loads(args.entities.read_text(encoding="utf-8"))
    with args.csv.open(encoding="utf-8", newline="") as fh:
        csv_rows = list(csv.DictReader(fh))
    existing_district_count = sum(
        1 for e in entities_doc["entities"] if e["entity_type"] == "district"
    )
    new_rows = compute_backfill(entities_doc, csv_rows)
    print(_summary(new_rows, total_csv=len(csv_rows), total_existing_districts=existing_district_count))

    if args.dry_run:
        print("\n[dry-run] entities.json unchanged.")
        return 0
    if not new_rows:
        print("\nentities.json already up to date; no write.")
        return 0
    added, total = apply_backfill(args.entities, args.csv)
    print(f"\nwrote {added} new district rows; entities.json now has {total} total rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
