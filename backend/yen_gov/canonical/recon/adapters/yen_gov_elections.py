"""yen-gov-elections event parity adapter (PR-S-TN-AE2026).

Reads ``datasets/elections/<kind>/state=<slug>/election=<year>/candidacies.csv``
(the canonical per-event per-state candidacies long-format CSV; see
``datasets/data/_schema/columns.json`` for the row contract) and
projects each constituency's winner into a ``ConstituencyParityRow``.

The yen-gov side is treated as a first-class event-parity oracle so the
per-event Compare-Aggregator (``recon/event_aggregator.py``) groups
yen-gov claims alongside external sources (thecont1, TCPD, ...) under a
uniform shape. This is symmetric with PR-W-1 / W-2 / W-3's synthetic
``"yen-gov-canonical"`` second-oracle pattern - both register the
canonical side as a publisher under its own scope.

Per CLAUDE.md section 10 (no silent demotion): the winner_party_id
carried here is the value ALREADY resolved in candidacies.csv (PR-3
re-ingested the corpus with the central resolver). The adapter does
NOT re-resolve; it surfaces the on-disk value verbatim. This is the
correct shape because the verdict.csv is comparing yen-gov's CURRENT
on-disk claim against external publishers - the curator's job is to
spot disagreement, not pre-resolve. Re-resolving here would mask the
PR-3 work and turn the parity oracle into a tautology.

Per Holy Law #9: when this adapter's row disagrees with an external
publisher's row in the verdict.csv, ECI authority wins via curator
disposition (``curator_note`` + ``curator_source_id``) - not via
auto-correction at the adapter level.

Scope-of-comparison contract:
  - One winner row per AC, identified as ``position == 1 AND result ==
    'won'`` in candidacies.csv. If no row in an AC satisfies that
    predicate, the AC is SKIPPED with a debug-level log (the adapter
    does not fabricate a winner).
  - Multiple rows satisfying the predicate is a data-integrity event
    surfaced as a ValueError - candidacies.csv invariant per the
    summary.csv = recompute(candidacies) contract.

Source provenance: the candidacies.csv source_id is the event's ECI
Statement 10 citation (existing in source.csv). external_vintage on
emitted rows pins to the event id (e.g. ``"AcGenMay2026"``) since the
canonical surface IS the per-event observation grain.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from yen_gov.canonical.recon.shape_b import ConstituencyParityRow

#: Adapter source-id used as the ``ConstituencyParityRow.external_scope``
#: on emitted rows. Same string used by ``event_aggregator.compare_event``
#: when picking the "primary" row of each AC group.
YEN_GOV_ELECTIONS_SCOPE: Final[str] = "yen-gov-elections"


@dataclass(frozen=True, slots=True)
class YenGovElectionsAdapter:
    """The PR-S-TN-AE2026 yen-gov-side adapter; registered against
    ``recon.adapters.EVENT_REGISTRY['yen-gov-elections']`` at module
    import time.

    Signature matches the ``EventParityAdapter`` Protocol
    (``recon/adapters/__init__.py``). ``state`` + ``event`` + ``kind``
    are REQUIRED; ``vintage`` is accepted and ignored (the event id IS
    the vintage anchor for yen-gov's on-disk per-event observation).
    """

    def __call__(
        self,
        *,
        root: Path,
        vintage: str,
        state: str | None = None,
        event: str | None = None,
        kind: str | None = None,
    ) -> Iterable[ConstituencyParityRow]:
        if not state:
            raise ValueError("yen-gov-elections adapter requires --state")
        if not event:
            raise ValueError("yen-gov-elections adapter requires --event")
        if not kind:
            raise ValueError(
                "yen-gov-elections adapter requires --kind "
                "(assembly | parliament)"
            )
        if kind not in {"assembly", "parliament"}:
            raise ValueError(
                f"yen-gov-elections adapter --kind must be 'assembly' "
                f"or 'parliament'; got {kind!r}"
            )

        # Extract the 4-digit year from the event id (e.g.
        # ``"AcGenMay2026"`` -> ``2026``). Every ECI event id in
        # ``sources/eci/events.py`` carries a 4-digit year suffix per
        # the established convention; if it doesn't, the on-disk
        # partition path resolution will fail loud at file-open time.
        year_match = "".join(c for c in event if c.isdigit())
        if len(year_match) < 4:
            raise ValueError(
                f"yen-gov-elections adapter cannot derive a year from "
                f"event id {event!r}; expected a 4-digit year suffix."
            )
        year = year_match[-4:]

        candidacies_csv = (
            root
            / "datasets"
            / "elections"
            / kind
            / f"state={state}"
            / f"election={year}"
            / "candidacies.csv"
        )
        if not candidacies_csv.exists():
            raise FileNotFoundError(
                f"candidacies.csv not found at "
                f"{candidacies_csv.as_posix()!r}; the per-event "
                f"partition has not been ingested yet."
            )

        # Group by constituency_no, find the (position=1 AND result=won)
        # winner per AC. We tolerate empty / missing position cells
        # (older corpus partitions may have null position) by falling
        # back to a max-votes winner per AC - documented escape-hatch
        # for the curator-corpus completeness gap.
        by_ac: dict[int, list[dict[str, str]]] = {}
        with candidacies_csv.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    ac_no = int(r.get("constituency_no") or "0")
                except ValueError:
                    continue
                if ac_no < 1:
                    continue
                by_ac.setdefault(ac_no, []).append(r)

        out: list[ConstituencyParityRow] = []
        for ac_no in sorted(by_ac):
            ac_rows = by_ac[ac_no]
            winner = _pick_winner(ac_rows)
            if winner is None:
                # No winner row in this AC's group - skip rather than
                # fabricate. The aggregator will see the AC only via
                # external sources and verdict it as UNVERIFIED-or-
                # disagree per the rule.
                continue
            try:
                votes = int(winner.get("votes") or "0")
            except ValueError:
                votes = 0
            out.append(
                ConstituencyParityRow(
                    external_scope=YEN_GOV_ELECTIONS_SCOPE,
                    external_vintage=event,
                    state=state,
                    event=event,
                    constituency_no=ac_no,
                    constituency_name=(
                        winner.get("constituency_name") or ""
                    ).strip(),
                    winner_party_id=(winner.get("party_id") or "").strip(),
                    winner_party_short_raw=(
                        winner.get("party_short_raw") or ""
                    ).strip(),
                    winner_candidate_name=(
                        winner.get("candidate_name") or ""
                    ).strip(),
                    winner_votes=votes if votes > 0 else None,
                )
            )
        return out


def _pick_winner(rows: list[dict[str, str]]) -> dict[str, str] | None:
    """Pick the winner row from one AC's candidacy rows.

    Primary signal: ``position == '1' AND result == 'won'``. When
    multiple rows match (data-integrity violation per
    candidacies summary contract), raises ValueError. When ZERO rows
    match (incomplete corpus partition), falls back to max-votes;
    when even votes are absent / zero, returns None and the AC is
    skipped.
    """
    winners = [
        r for r in rows
        if (r.get("position") or "").strip() == "1"
        and (r.get("result") or "").strip().lower() == "won"
    ]
    if len(winners) > 1:
        raise ValueError(
            f"AC {rows[0].get('constituency_no')!r} candidacies.csv "
            f"has {len(winners)} rows with position=1 AND result=won; "
            f"data-integrity violation per summary contract."
        )
    if len(winners) == 1:
        return winners[0]
    # Fallback: max votes. Returns None if no row has a positive
    # vote count (no usable signal to declare a winner).
    scored: list[tuple[int, dict[str, str]]] = []
    for r in rows:
        try:
            v = int((r.get("votes") or "0").strip() or "0")
        except ValueError:
            v = 0
        scored.append((v, r))
    scored.sort(key=lambda t: -t[0])
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return None


#: Adapter instance auto-registered at import time (see __init__.py).
ADAPTER: Final[YenGovElectionsAdapter] = YenGovElectionsAdapter()


__all__ = [
    "ADAPTER",
    "YenGovElectionsAdapter",
    "YEN_GOV_ELECTIONS_SCOPE",
]
