"""B2b.5.0c entities/electoral.csv emitter (clean-start from the LGD snapshot).

Regenerates ``datasets/data/entities/electoral.csv`` from the committed LGD
parsed snapshot ``datasets/data/entities/lgd/constituencies.csv`` (B2b.5.0a;
relocated from ``datasets/reference/lgd/`` to ``datasets/data/entities/lgd/`` by
G8-finish 2026-06-08, plan section 9), which is sourced from the freshly-
downloaded PRI super-file and carries, per constituency, the LGD register code
AND the ECI ballot serial (``eci_code``) AND the parent PC. This SUPERSEDES the
prior ``electoral_csv.py`` emitter that read the distrusted
``datasets/taxonomy/lgd_acs.json`` / ``lgd_pcs.json`` registers.

Round-7 / round-8 binding decisions realised here:

- **LGD-native PK** (no ``state_code*1000+eci_no`` arithmetic). The entity_id is
  ``IN-AC-<delim>-<state-slug>-<lgd_code>`` / ``IN-PC-<delim>-<state-slug>-<lgd_code>``
  - the same shape B2a.6 emitted, so existing consumers keep resolving.
- **``eci_no`` folded as a column** - the natural ECI ballot serial (``eci_code``
  in the snapshot), bound by a DIRECT JOIN off the PRI super-file (no name-match
  needed; the PRI carries both the LGD code and the ECI code on every row).
- **``aliases`` column** (pipe-delimited) for transliteration / display synonyms;
  v1 leaves it empty (the snapshot carries one canonical name per constituency)
  but the column exists so yen-ask grounding + future enrichment have a home.

Columns (per ``datasets/data/_schema/columns.json`` after 0c):

- ``entity_id``   (PK)
- ``name``
- ``entity_kind`` (``ac | pc``)
- ``delim_year``  (v1: 2008)
- ``state``       (FK -> ``entities/geo.csv.entity_id``; the LGD state slug)
- ``parent``      (AC -> its PC entity_id; PC -> its state slug)
- ``eci_no``      (the natural ECI ballot serial, folded; NULL only if the PRI
                    lacked an ECI code for that constituency)
- ``aliases``     (pipe-delimited synonyms; nullable)
- ``reservation`` (``GEN | SC | ST``; NULL in v1 - the snapshot does not carry it)

State slug comes from ``datasets/data/entities/state_codes.csv`` (B2b.5.0b),
joined on the snapshot's ``lgd_state_code``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/entities/electoral.csv"

# v1 freezes the delimitation at the in-force 2008 cycle (plan section 3).
DELIM_YEAR_V1 = 2008


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _state_slug_index(state_codes_csv: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in _read_csv_rows(state_codes_csv):
        out[r["lgd_state_id"]] = r["slug"]
    return out


def _entity_id(kind: str, state_slug: str, lgd_code: str, delim_year: int) -> str:
    tag = "AC" if kind == "ac" else "PC"
    return f"IN-{tag}-{delim_year}-{state_slug}-{lgd_code}"


def emit(
    *,
    constituencies_csv: Path,
    state_codes_csv: Path,
    out_path: Path,
    delim_year: int = DELIM_YEAR_V1,
) -> Path:
    """Emit ``out_path`` from the LGD constituency snapshot; return the path.

    Raises:
        FileNotFoundError: a required input is missing.
        ValueError: a constituency references an unknown ``lgd_state_code``, an
            AC's ``parent_pc_lgd_code`` does not resolve to a PC, ``__`` appears
            in any emitted entity_id (plan section 21.6), or an identity collides.
    """
    if not constituencies_csv.exists():
        raise FileNotFoundError(constituencies_csv)
    if not state_codes_csv.exists():
        raise FileNotFoundError(state_codes_csv)

    state_slug_by_code = _state_slug_index(state_codes_csv)
    snapshot = _read_csv_rows(constituencies_csv)

    # PC pass first so AC rows can resolve their parent PC entity_id.
    pc_entity_id_by_key: dict[tuple[str, str], str] = {}  # (state_code, pc_lgd_code) -> entity_id
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for r in snapshot:
        if r["kind"] != "pc":
            continue
        state_code = r["lgd_state_code"]
        state_slug = state_slug_by_code.get(state_code)
        if state_slug is None:
            raise ValueError(f"pc {r['lgd_code']} references unknown lgd_state_code={state_code!r}")
        entity_id = _entity_id("pc", state_slug, r["lgd_code"], delim_year)
        if "__" in entity_id:
            raise ValueError(f"pc entity_id must not contain '__': {entity_id!r}")
        if entity_id in seen:
            raise ValueError(f"duplicate pc entity_id: {entity_id!r}")
        seen.add(entity_id)
        pc_entity_id_by_key[(state_code, r["lgd_code"])] = entity_id
        rows.append(
            {
                "entity_id": entity_id,
                "name": r["name"],
                "entity_kind": "pc",
                "delim_year": delim_year,
                "state": state_slug,
                "parent": state_slug,
                "eci_no": (r.get("eci_code") or "").strip() or None,
                "aliases": None,
                "reservation": None,
            }
        )

    for r in snapshot:
        if r["kind"] != "ac":
            continue
        state_code = r["lgd_state_code"]
        state_slug = state_slug_by_code.get(state_code)
        if state_slug is None:
            raise ValueError(f"ac {r['lgd_code']} references unknown lgd_state_code={state_code!r}")
        entity_id = _entity_id("ac", state_slug, r["lgd_code"], delim_year)
        if "__" in entity_id:
            raise ValueError(f"ac entity_id must not contain '__': {entity_id!r}")
        if entity_id in seen:
            raise ValueError(f"duplicate ac entity_id: {entity_id!r}")
        seen.add(entity_id)
        parent_pc_code = (r.get("parent_pc_lgd_code") or "").strip()
        parent = None
        if parent_pc_code:
            parent = pc_entity_id_by_key.get((state_code, parent_pc_code))
            if parent is None:
                raise ValueError(
                    f"ac {r['lgd_code']} (state {state_code}) references unknown "
                    f"parent PC lgd_code={parent_pc_code!r}"
                )
        rows.append(
            {
                "entity_id": entity_id,
                "name": r["name"],
                "entity_kind": "ac",
                "delim_year": delim_year,
                "state": state_slug,
                "parent": parent,
                "eci_no": (r.get("eci_code") or "").strip() or None,
                "aliases": None,
                "reservation": None,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
