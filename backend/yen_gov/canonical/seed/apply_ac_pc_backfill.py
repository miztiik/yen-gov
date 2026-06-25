"""Surgical applier: write the P0b geometric AC->PC crosswalk into electoral.csv.

Row P0b. The committed ``datasets/data/entities/electoral.csv`` is a HISTORICAL
multi-source artifact: ``electoral_csv_from_snapshot.py`` emits the LGD-keyed
base rows (``IN-{AC,PC}-2008-<slug>-<lgd>``) and a now-retired legacy backfill
tool then appended the ECI-keyed gap AC rows (``IN-AC-2008-<slug>-eci<N>``,
lifted from the since-deleted ``dim_acs.parquet``). Because the snapshot writer
never emits those ECI-keyed rows, a full snapshot regen cannot fill their
``parent`` - it would DROP them. So the geometric crosswalk links (all ECI-keyed
gap ACs at v1) are applied SURGICALLY here.

Mechanism (provably parent-only diff): read the committed CSV with newline
translation disabled, parse each line, set ``parent`` for exactly the crosswalk
``ac_entity_id``s whose parent is currently empty, RE-SERIALISE ONLY those lines
(same ``QUOTE_MINIMAL`` policy as the canonical writer), and leave every other
line byte-for-byte unchanged - column order, row order, quoting, trailing
newline. The result is a parent-only change on exactly the backfilled rows.

Resolution order matches the seed writer: LGD-first (an AC that already has a
parent is LEFT UNTOUCHED - LGD wins over the crosswalk), crosswalk-second,
NULL-last (a gap AC absent from the crosswalk stays NULL -> UI "data pending").
The applier is idempotent: a second run sets nothing and rewrites nothing.

This module is pure-stdlib (no shapely); it is the runtime-safe counterpart to
the build-time ``ac_pc_geometric_backfill.py`` generator.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

ELECTORAL_FILENAME = "electoral.csv"
CROSSWALK_FILENAME = "ac_pc_geometric_backfill.csv"

_ENTITY_ID_COL = "entity_id"
_PARENT_COL = "parent"
_AC_ENTITY_ID_COL = "ac_entity_id"
_PARENT_PC_ENTITY_ID_COL = "parent_pc_entity_id"

__all__ = ["ApplyResult", "apply_backfill", "CROSSWALK_FILENAME", "ELECTORAL_FILENAME"]


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of one surgical backfill apply."""

    filled: int  # rows whose empty parent was set from the crosswalk
    already_linked: int  # crosswalk ACs that already had a parent (LGD wins)
    missing: tuple[str, ...]  # crosswalk ac_entity_ids absent from electoral.csv
    crosswalk_rows: int  # total crosswalk rows considered


def _load_crosswalk(crosswalk_csv: Path) -> dict[str, str]:
    with crosswalk_csv.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {r[_AC_ENTITY_ID_COL]: r[_PARENT_PC_ENTITY_ID_COL] for r in rows}


def _serialise_row(fields: list[str]) -> str:
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="", quoting=csv.QUOTE_MINIMAL).writerow(fields)
    return buffer.getvalue()


def apply_backfill(*, electoral_csv: Path, crosswalk_csv: Path) -> ApplyResult:
    """Set ``parent`` on the crosswalk ACs in ``electoral_csv`` in place.

    Only rows whose ``parent`` is currently empty are touched (LGD-first); every
    other line is preserved byte-for-byte (row order, quoting, trailing newline).
    The file is rewritten only when at least one parent is filled.

    Raises:
        FileNotFoundError: either input is missing.
        ValueError: ``electoral.csv`` lacks the ``entity_id`` / ``parent`` header.
    """
    if not electoral_csv.exists():
        raise FileNotFoundError(electoral_csv)
    if not crosswalk_csv.exists():
        raise FileNotFoundError(crosswalk_csv)

    crosswalk = _load_crosswalk(crosswalk_csv)

    # Read with newline translation disabled so the on-disk LF bytes survive.
    with electoral_csv.open(encoding="utf-8", newline="") as fh:
        raw = fh.read()
    lines = raw.split("\n")

    header = next(csv.reader([lines[0]]))
    try:
        eid_idx = header.index(_ENTITY_ID_COL)
        parent_idx = header.index(_PARENT_COL)
    except ValueError as err:
        raise ValueError(
            f"electoral.csv header missing entity_id/parent: {header}"
        ) from err

    seen: set[str] = set()
    filled = 0
    already_linked = 0
    for i in range(1, len(lines)):
        line = lines[i]
        if line == "":
            continue
        fields = next(csv.reader([line]))
        entity_id = fields[eid_idx]
        target = crosswalk.get(entity_id)
        if target is None:
            continue
        seen.add(entity_id)
        if fields[parent_idx].strip() != "":
            already_linked += 1  # LGD already linked it -> leave untouched
            continue
        fields[parent_idx] = target
        lines[i] = _serialise_row(fields)
        filled += 1

    missing = tuple(sorted(set(crosswalk) - seen))

    if filled:
        electoral_csv.write_text("\n".join(lines), encoding="utf-8", newline="")

    return ApplyResult(
        filled=filled,
        already_linked=already_linked,
        missing=missing,
        crosswalk_rows=len(crosswalk),
    )
