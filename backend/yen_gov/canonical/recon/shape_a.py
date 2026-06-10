"""Shape-A — the canonical intermediate schema every parity adapter materialises.

Per Wave 0 / Gregor section 5 verdict (plan section 2.PR-2): every Tier-C
parity adapter (one per upstream source: TCPD, ECI registered-list,
Wikipedia, IndiaVotes, ...) projects its source rows into ONE common shape
before the Compare-Aggregator (``aggregator.py``) sees them. That common
shape is ``ShapeARow``. Decoupling adapter peculiarity from comparison
logic is the EIP pipes-and-filters pattern the rest of the canonical store
uses for ingest-to-write transforms.

A shape-A row carries:

  - ``external_key``      : adapter-side natural key for the row (the
                            publisher's own row identifier - e.g. a TCPD
                            party_id, an ECI registration number, the
                            Wikipedia list-page slug). Used as a stable
                            cross-reference back to the upstream record.
  - ``external_short``    : short name AS PUBLISHED by the upstream
                            (e.g. "AIADMK" / "ADMK" / "A.I.A.D.M.K.").
  - ``external_full``     : full / legal name AS PUBLISHED by the upstream.
  - ``external_scope``    : the source-family identifier the adapter
                            registered under (e.g. "tcpd-parties",
                            "eci-registered", "wikipedia-parties"). The
                            aggregator treats DISTINCT ``external_scope``
                            values as DISTINCT oracles when computing
                            ``n_oracles_present``.
  - ``external_vintage``  : the upstream snapshot date or year
                            (YYYY-MM-DD or YYYY). Per ADR-0042 / CLAUDE.md
                            section 12, the operator snapshot window pin
                            of the upstream observation.
  - ``proposed_party_id`` : the canonical ``party_id`` (parties.IN.<SLUG>)
                            the adapter believes this row should resolve
                            to. May be a NEW id if proposed_action is
                            ``mint-new``; otherwise SHOULD exist in
                            ``datasets/data/entities/parties.csv``.
  - ``proposed_action``   : one of ``match`` | ``enrich`` | ``mint-new``
                            | ``alias-add`` | ``conflict`` (per plan
                            section 2.PR-2 brief). The adapter's
                            recommendation; the Compare-Aggregator may
                            keep it or escalate to ``conflict`` when two
                            oracles disagree.
  - ``notes``             : free-text adapter note (nullable). Used by
                            curators to record disambiguation hints (e.g.
                            "ECI code 145 reassigned from AAP to XYZ in
                            2022").

The shape-A CSV is an ephemeral working artifact under
``datasets/ephemeral/party-parity/<source>/<vintage>/<sha>/shape-a.csv``
(adapter-written; not a long-format canonical CSV under
``datasets/data/``). Tier-B does NOT walk it. The JSON Schema reference
for the row shape lives at
``datasets/schemas/party-parity-shape-a.schema.json`` (CSV-column-contract
style — column-by-column dtype + nullability declarations).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Final, Literal


#: The closed enum of adapter-proposed actions per plan section 2.PR-2.
#: The Compare-Aggregator MAY upgrade the per-row proposed action to
#: ``conflict`` when two oracles disagree, but never invents an action
#: outside this set.
ProposedAction = Literal["match", "enrich", "mint-new", "alias-add", "conflict"]

VALID_PROPOSED_ACTIONS: Final[tuple[str, ...]] = (
    "match",
    "enrich",
    "mint-new",
    "alias-add",
    "conflict",
)


@dataclass(frozen=True, slots=True)
class ShapeARow:
    """One row of the canonical Shape-A intermediate format.

    Field order is the EMISSION order; ``write_shape_a_csv`` honours it
    verbatim for the CSV header. Per CLAUDE.md section 11 schema-versioning
    discipline, any field rename / removal is a MAJOR bump on
    ``party-parity-shape-a.schema.json``; additive new fields are MINOR.
    """

    external_key: str
    external_short: str
    external_full: str
    external_scope: str
    external_vintage: str
    proposed_party_id: str
    proposed_action: ProposedAction
    notes: str | None = None


def _header() -> tuple[str, ...]:
    """Field-declared header order (single source of truth)."""
    return tuple(f.name for f in fields(ShapeARow))


def write_shape_a_csv(rows: Iterable[ShapeARow], path: Path) -> int:
    """Write ``rows`` to ``path`` in shape-A CSV format.

    Creates the parent directory if absent. Empty ``notes`` is serialised
    as an empty string. Returns the number of rows written.

    The CSV header is fixed by ``ShapeARow`` field declaration order.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    header = _header()
    count = 0
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            d = asdict(row)
            if d.get("notes") is None:
                d["notes"] = ""
            if row.proposed_action not in VALID_PROPOSED_ACTIONS:
                raise ValueError(
                    f"shape-A row {row.external_key!r} has invalid "
                    f"proposed_action={row.proposed_action!r}; "
                    f"must be one of {VALID_PROPOSED_ACTIONS}"
                )
            writer.writerow(d)
            count += 1
    return count


def read_shape_a_csv(path: Path) -> list[ShapeARow]:
    """Read a shape-A CSV from ``path`` into a list of ``ShapeARow``.

    Empty ``notes`` cells are restored to ``None`` (matching the dataclass
    default) to round-trip cleanly with ``write_shape_a_csv``.
    """
    header = _header()
    out: list[ShapeARow] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or tuple(reader.fieldnames) != header:
            raise ValueError(
                f"shape-A CSV {path.as_posix()!r} header mismatch: "
                f"got {reader.fieldnames!r}, expected {list(header)!r}"
            )
        for raw in reader:
            action = raw["proposed_action"]
            if action not in VALID_PROPOSED_ACTIONS:
                raise ValueError(
                    f"shape-A CSV {path.as_posix()!r} row "
                    f"{raw.get('external_key')!r} has invalid "
                    f"proposed_action={action!r}; must be one of "
                    f"{VALID_PROPOSED_ACTIONS}"
                )
            notes = raw["notes"]
            out.append(
                ShapeARow(
                    external_key=raw["external_key"],
                    external_short=raw["external_short"],
                    external_full=raw["external_full"],
                    external_scope=raw["external_scope"],
                    external_vintage=raw["external_vintage"],
                    proposed_party_id=raw["proposed_party_id"],
                    proposed_action=action,  # type: ignore[arg-type]
                    notes=notes if notes != "" else None,
                )
            )
    return out


__all__ = [
    "ShapeARow",
    "ProposedAction",
    "VALID_PROPOSED_ACTIONS",
    "write_shape_a_csv",
    "read_shape_a_csv",
]
