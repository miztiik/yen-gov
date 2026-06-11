"""Shape-B - per-(state, event, constituency_no) parity row.

Per the PR-S-TN-AE2026 brief (Wave C of the 2026-06-10 electoral-data-
quality + party-catalogue plan), per-event reconciliation works at a
DIFFERENT grain from the per-party-roster Shape-A established by PR-2:

  - Shape-A (``recon/shape_a.py``): one row per (upstream publisher
    party entity, source scope, source vintage). The Compare-Aggregator
    groups by ``proposed_party_id`` and verdicts agreement of the
    canonical id across publishers (PR-W-1 + W-2 + W-3 cohort).

  - Shape-B (this module): one row per (source scope, state slug, ECI
    event id, constituency_no). The event aggregator (``event_aggregator.py``)
    groups by ``(state, event, constituency_no)`` and verdicts agreement
    of ``(winner_party_id, winner_candidate_name)`` across sources for
    each AC (PR-S-* + PR-PC-* per-event cohort).

The two shapes are SIBLINGS, not nested. An adapter targets exactly one
shape; the CLI dispatches via the source-id's registry (REGISTRY vs
EVENT_REGISTRY in ``adapters/__init__.py``). Keeping them separate
avoids overloading the per-party Compare-Aggregator with polymorphic
verdict semantics and preserves the PR-W-* adapters' bytewise stability.

The shape-B CSV is an ephemeral working artifact under
``datasets/ephemeral/party-parity/state=<slug>/<event>/<sha>/shape-b.csv``
(adapter-written; not a long-format canonical CSV under
``datasets/data/``). The JSON Schema reference for the row shape lives
at ``datasets/schemas/party-parity-shape-b.schema.json`` (CSV-column-
contract style - column-by-column dtype + nullability declarations).

Fields (8 required + 1 optional, mirroring Shape-A's emit-order discipline):

  - ``external_scope``     : the source-family identifier the adapter
                             is registered under in ``EVENT_REGISTRY``
                             (e.g. ``"yen-gov-elections"``,
                             ``"thecont1-state"``, ``"tcpd-state"``).
                             The event aggregator treats DISTINCT
                             ``external_scope`` values within one
                             (state, event, constituency_no) group as
                             DISTINCT oracles for the Hans / Fowler
                             verdict rule.
  - ``external_vintage``   : ADR-0042 operator snapshot window pin
                             (YYYY, YYYY-MM, or YYYY-MM-DD).
  - ``state``              : state slug (e.g. ``"tamil-nadu"``); same
                             slug the on-disk
                             ``datasets/elections/<kind>/state=<slug>/``
                             partition uses.
  - ``event``              : ECI event id (e.g. ``"AcGenMay2026"``);
                             same string the
                             ``election=<year>/`` partition resolves to
                             via ``sources/eci/events.py``.
  - ``constituency_no``    : 1-based constituency number within the
                             state (ECI's ``eci_no``). Comparable
                             across sources because every Indian AE
                             publisher reports the same eci_no scheme.
  - ``constituency_name``  : publisher's published constituency name.
                             Carried verbatim for the curator; not used
                             as a comparison key (publishers differ on
                             casing / spelling).
  - ``winner_party_id``    : canonical ``parties.IN.<SLUG>`` the
                             adapter resolved this source's winner to.
                             May be ``parties.IN.UNK`` per CLAUDE.md
                             section 10 "no silent demotion" when the
                             publisher's label has no canonical alias.
  - ``winner_party_short_raw`` : the publisher's raw party label for
                                 the winner (e.g. ``"ADMK"`` /
                                 ``"All India Anna Dravida Munnetra
                                 Kazhagam"``). Carried verbatim into
                                 the verdict CSV's ``other_sources``
                                 column for curator review.
  - ``winner_candidate_name`` : the publisher's raw winner name. The
                                event aggregator compares this case-
                                insensitively after stripping common
                                punctuation (see
                                ``event_aggregator._normalise_name``).
  - ``winner_votes``       : the publisher's published winner-side
                             total votes (EVM + postal where the
                             publisher reports them separately). Used
                             ONLY for the curator's review column;
                             never a verdict input (publishers differ
                             on EVM-only vs EVM+postal). Nullable for
                             publishers that don't report a vote count.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ConstituencyParityRow:
    """One row of the Shape-B intermediate format (per-AC, per-source).

    Field order is the EMISSION order; ``write_shape_b_csv`` honours it
    verbatim for the CSV header. Per CLAUDE.md section 11 schema-
    versioning discipline, any field rename / removal is a MAJOR bump
    on ``party-parity-shape-b.schema.json``; additive new fields are
    MINOR.
    """

    external_scope: str
    external_vintage: str
    state: str
    event: str
    constituency_no: int
    constituency_name: str
    winner_party_id: str
    winner_party_short_raw: str
    winner_candidate_name: str
    winner_votes: int | None = None


def _header() -> tuple[str, ...]:
    """Field-declared header order (single source of truth)."""
    return tuple(f.name for f in fields(ConstituencyParityRow))


def write_shape_b_csv(rows: Iterable[ConstituencyParityRow], path: Path) -> int:
    """Write ``rows`` to ``path`` in shape-B CSV format.

    Creates the parent directory if absent. ``winner_votes`` None is
    serialised as an empty string. Returns the number of rows written.

    The CSV header is fixed by ``ConstituencyParityRow`` field
    declaration order.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    header = _header()
    count = 0
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            d = asdict(row)
            if d.get("winner_votes") is None:
                d["winner_votes"] = ""
            writer.writerow(d)
            count += 1
    return count


def read_shape_b_csv(path: Path) -> list[ConstituencyParityRow]:
    """Read a shape-B CSV from ``path`` into a list of ``ConstituencyParityRow``.

    Empty ``winner_votes`` cells are restored to ``None`` (matching the
    dataclass default) to round-trip cleanly with ``write_shape_b_csv``.
    Numeric columns (``constituency_no`` + ``winner_votes``) are cast
    from string to int.
    """
    header = _header()
    out: list[ConstituencyParityRow] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or tuple(reader.fieldnames) != header:
            raise ValueError(
                f"shape-B CSV {path.as_posix()!r} header mismatch: "
                f"got {reader.fieldnames!r}, expected {list(header)!r}"
            )
        for raw in reader:
            votes_raw = raw["winner_votes"]
            try:
                votes = int(votes_raw) if votes_raw != "" else None
            except ValueError as exc:
                raise ValueError(
                    f"shape-B CSV {path.as_posix()!r} row "
                    f"{raw.get('constituency_no')!r} has invalid "
                    f"winner_votes={votes_raw!r}"
                ) from exc
            out.append(
                ConstituencyParityRow(
                    external_scope=raw["external_scope"],
                    external_vintage=raw["external_vintage"],
                    state=raw["state"],
                    event=raw["event"],
                    constituency_no=int(raw["constituency_no"]),
                    constituency_name=raw["constituency_name"],
                    winner_party_id=raw["winner_party_id"],
                    winner_party_short_raw=raw["winner_party_short_raw"],
                    winner_candidate_name=raw["winner_candidate_name"],
                    winner_votes=votes,
                )
            )
    return out


__all__ = [
    "ConstituencyParityRow",
    "write_shape_b_csv",
    "read_shape_b_csv",
]
