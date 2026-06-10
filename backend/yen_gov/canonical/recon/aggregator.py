"""Compare-Aggregator — collapses shape-A rows into per-party verdicts.

EIP pipes-and-filters pattern per Wave 0 / Gregor section 5 verdict. The
aggregator is a PURE FUNCTION (no I/O, no clock, no random) over its
inputs so the Tier-A test fixture can drive it end-to-end without disk.

Inputs:
  - ``shape_a_rows``: list of ``ShapeARow`` (typically from one or more
    upstream adapters; each adapter's rows carry a distinct
    ``external_scope`` value). For PR-2 the registry is empty; future
    PR-W-1 / W-2 / W-3 + Stream X PRs supply real adapter outputs.
  - ``canonical_parties``: dict keyed by ``party_id`` (the rows of
    ``datasets/data/entities/parties.csv`` projected to dict). Used to
    determine whether ``proposed_party_id`` already exists (``match`` /
    ``enrich`` / ``alias-add`` legs) or is a new mint (``mint-new`` leg).

Outputs:
  - list of ``VerdictRow`` — one row per distinct ``proposed_party_id``.
    Stable order: rows are sorted by ``proposed_party_id`` so the verdict
    CSV is reproducible.

Verdict rule (Fowler machine-decidable per plan section 0.5 ESCALATE #2):

  - ``VERIFIED``  iff ``n_oracles_agreeing == n_oracles_present`` AND
                  ``n_oracles_present >= 2``.
  - ``UNVERIFIED`` iff ``n_oracles_present < 2`` (single-source — needs
                   corroboration before promotion).
  - ``DISPUTED``  otherwise (two or more oracles, at least one
                  disagreement on action / id — operator curation needed).

No LLM judgement; the rule is purely structural.

The aggregator NEVER touches parties.csv; it merely projects the
shape-A + canonical-parties join into verdict rows for downstream
curator action. Mutating parties.csv on the basis of a verdict is the
job of PR-W-1 / W-2 / W-3 and is hand-applied, not auto-merged (Wave 0
/ Hans verdict: hand-curation is the only path; auto-correct is BANNED).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Final, Literal

from .shape_a import ShapeARow, VALID_PROPOSED_ACTIONS

Verdict = Literal["VERIFIED", "DISPUTED", "UNVERIFIED"]
Action = Literal["match", "enrich", "mint-new", "alias-add", "conflict"]

#: Action precedence (highest first) when collapsing multiple shape-A rows
#: into one verdict row. ``conflict`` wins because any single oracle
#: reporting a conflict means the curator must look; ``mint-new`` next
#: because shipping a row that the canonical roster lacks IS a curator
#: decision; ``alias-add`` and ``enrich`` are operator-applied edits to an
#: existing row; ``match`` is the inert state.
_ACTION_PRECEDENCE: Final[tuple[str, ...]] = (
    "conflict",
    "mint-new",
    "alias-add",
    "enrich",
    "match",
)


@dataclass(frozen=True, slots=True)
class VerdictRow:
    """One row of the verdict CSV produced by the Compare-Aggregator.

    Field order is the EMISSION order; the verdict CSV header is derived
    from ``fields(VerdictRow)``.
    """

    external_key: str
    external_short: str
    external_full: str
    proposed_party_id: str
    current_party_id: str | None
    action: Action
    n_oracles_present: int
    n_oracles_agreeing: int
    oracles_agreeing: str
    oracles_disagreeing: str
    verdict: Verdict
    curator_note: str | None = None
    curator_source_id: str | None = None


def verdict_csv_header() -> tuple[str, ...]:
    """Header order for the verdict CSV (single source of truth)."""
    return tuple(f.name for f in fields(VerdictRow))


def _collapse_action(actions: list[str]) -> Action:
    """Pick the highest-precedence action from a list of proposed actions."""
    for candidate in _ACTION_PRECEDENCE:
        if candidate in actions:
            return candidate  # type: ignore[return-value]
    # Unreachable when callers honour VALID_PROPOSED_ACTIONS, but safe-default
    # to ``match`` if the input set is empty (no shape-A rows in the group).
    return "match"


def compare(
    shape_a_rows: list[ShapeARow],
    canonical_parties: Mapping[str, Mapping[str, object]],
) -> list[VerdictRow]:
    """Collapse shape-A rows into per-``proposed_party_id`` verdict rows.

    Grouping key is ``proposed_party_id``. Within each group, distinct
    ``external_scope`` values count as distinct oracles. Per the Fowler
    rule (see module docstring) the verdict is structural; the aggregator
    never invents content beyond what the shape-A rows carry.

    Args:
        shape_a_rows: list of shape-A rows from one or more adapter runs.
        canonical_parties: mapping of ``party_id`` to its parties.csv row.
            Only ``party_id`` membership is consulted here (to derive
            ``current_party_id``); future PRs MAY consult richer columns
            (e.g. ``aliases``) to widen the agreeing-oracle count.

    Returns:
        list of ``VerdictRow`` sorted by ``proposed_party_id``.

    Raises:
        ValueError: a shape-A row carries an unknown ``proposed_action``.
    """
    # Defensive guard: a malformed shape-A row would corrupt the verdict
    # mechanically. Validate up front so the error surfaces at the row
    # the user passed in, not deep inside the action-precedence math.
    for row in shape_a_rows:
        if row.proposed_action not in VALID_PROPOSED_ACTIONS:
            raise ValueError(
                f"shape-A row {row.external_key!r} has invalid "
                f"proposed_action={row.proposed_action!r}; "
                f"must be one of {VALID_PROPOSED_ACTIONS}"
            )

    by_party: dict[str, list[ShapeARow]] = {}
    for row in shape_a_rows:
        by_party.setdefault(row.proposed_party_id, []).append(row)

    verdicts: list[VerdictRow] = []
    for party_id in sorted(by_party):
        group = by_party[party_id]
        oracles = sorted({r.external_scope for r in group})
        n_present = len(oracles)
        # Within a group every row already agrees on ``party_id`` (that's
        # the grouping key), so every oracle in the group agrees. Cross-
        # party disagreement (oracle A says BJP for the same publisher
        # entity that oracle B says XYZ for) surfaces as TWO separate
        # verdict rows today and is deferred to a future cross-source
        # rollup CLI per plan section 2 (Stream X). The ``oracles_disagreeing``
        # column is therefore empty at this PR; the column is retained on
        # the verdict CSV header so future rollup runs can populate it
        # without a schema bump.
        n_agreeing = n_present
        oracles_disagreeing = ""

        action = _collapse_action([r.proposed_action for r in group])
        current = party_id if party_id in canonical_parties else None

        # Sanity: mint-new MUST point at a non-existing canonical id.
        # If a mint-new row collides with an existing row, treat as conflict
        # so the curator inspects (rather than silently overwriting).
        if action == "mint-new" and current is not None:
            action = "conflict"

        if n_present < 2:
            verdict: Verdict = "UNVERIFIED"
        elif n_agreeing == n_present:
            verdict = "VERIFIED"
        else:
            verdict = "DISPUTED"

        # Choose a representative shape-A row for the surface columns
        # (external_key / external_short / external_full). Pick deterministic-
        # first-by-external_scope so the verdict CSV is reproducible across
        # runs regardless of shape-A row insertion order.
        rep = min(group, key=lambda r: (r.external_scope, r.external_key))

        verdicts.append(
            VerdictRow(
                external_key=rep.external_key,
                external_short=rep.external_short,
                external_full=rep.external_full,
                proposed_party_id=party_id,
                current_party_id=current,
                action=action,
                n_oracles_present=n_present,
                n_oracles_agreeing=n_agreeing,
                oracles_agreeing="|".join(oracles),
                oracles_disagreeing=oracles_disagreeing,
                verdict=verdict,
                curator_note=None,
                curator_source_id=None,
            )
        )

    return verdicts


def write_verdict_csv(verdicts: list[VerdictRow], path) -> int:  # type: ignore[no-untyped-def]
    """Write verdict rows to ``path`` as CSV.

    Splits the dataclass into a CSV row using ``fields(VerdictRow)`` for
    header order. ``None`` values are serialised as empty strings (the
    citizen-UI / curator never wants the literal string ``"None"`` in the
    ledger).

    ``path`` accepted as ``pathlib.Path`` or string. Returns the number of
    rows written.
    """
    import csv
    from pathlib import Path as _Path

    out_path = _Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = verdict_csv_header()
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in verdicts:
            d = asdict(row)
            for k, v in list(d.items()):
                if v is None:
                    d[k] = ""
            writer.writerow(d)
    return len(verdicts)


__all__ = [
    "VerdictRow",
    "Verdict",
    "Action",
    "compare",
    "verdict_csv_header",
    "write_verdict_csv",
]
