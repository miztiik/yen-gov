"""thecont1/india-votes-data per-state per-event parity adapter (PR-S-TN-AE2026).

Reads a snapshot of the per-(year, state) Assembly CSV from the
``thecont1/india-votes-data`` GitHub repository (user source #8 in the
2026-06-10 electoral-data-quality plan). Local snapshot path:

    datasets/ephemeral/thecont1-india-votes-data/<year>/Assembly-<StateSlug>.csv

For TN 2026 specifically: ``datasets/ephemeral/thecont1-india-votes-data/
2026/Assembly-Tamil-Nadu.csv``. The remote file name pattern is
``<year>Assembly-<STATE_ABBREV>.csv`` (e.g. ``2026Assembly-TN.csv``)
which the operator re-naming policy normalises to the long-state-slug
shape on snapshot. See the README at
``datasets/ephemeral/thecont1-india-votes-data/README.md`` for the
full provenance + re-snapshot policy (commit policy per Q3: snapshot
IS committed since the upstream is a small per-event CSV; the file is
ephemeral-tier but useful as an audit-trail).

Per the Shape-B contract (``recon/shape_b.py``): one
``ConstituencyParityRow`` per AC, identifying the AC's winner from the
max-(evm_votes + postal_votes) row in the constituency's
candidacy block.

Per CLAUDE.md section 10 (no silent demotion): the resolved
``winner_party_id`` comes from the central resolver
(``backend/yen_gov/canonical/party_resolver.py``) applied to thecont1's
full-name ``party`` column AND short-name resolution via TCPD-published
aliases. When the resolver returns ``parties.IN.UNK``, the adapter
preserves it - the verdict.csv surfaces a disagreement between yen-gov
and thecont1 on that AC, which the curator then dispositions.

Schema of the upstream CSV (verified 2026-06-11 against the 2026 TN
snapshot):

  - ``election_year`` (e.g. ``"2026"``)
  - ``election_type`` (e.g. ``"Assembly"``)
  - ``election_state`` (state abbreviation; ``"TN"`` for Tamil Nadu)
  - ``constituency`` (constituency name as published)
  - ``constituency_no`` (1-based AC number)
  - ``serial_no`` (per-candidate ordinal within the AC)
  - ``candidate`` (candidate name as published)
  - ``party`` (FULL party name as published; e.g. ``"All India Anna
    Dravida Munnetra Kazhagam"``, ``"Independent"``)
  - ``evm_votes`` (integer; EVM votes only)
  - ``postal_votes`` (integer; postal-ballot votes only)

Source provenance: the snapshot file IS committed as the audit-trail
(via the ``datasets/ephemeral/thecont1-india-votes-data/README.md``).
external_vintage on emitted rows pins to the event id (matching the
yen-gov-elections adapter) since the snapshot's identity is bounded
by ``(election_year, election_state)``.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from yen_gov.canonical.party_resolver import UNK, load_resolver
from yen_gov.canonical.recon.shape_b import ConstituencyParityRow

#: Adapter source-id used as the ``ConstituencyParityRow.external_scope``
#: on emitted rows.
THECONT1_STATE_SCOPE: Final[str] = "thecont1-state"

#: State-slug -> snapshot-file-name map. The local snapshot directory
#: uses the long-state-slug shape from
#: ``datasets/data/entities/geo.csv``; the operator re-naming policy at
#: snapshot time normalises the upstream's ``<year>Assembly-<ABBR>.csv``
#: file name (e.g. ``2026Assembly-TN.csv``) to
#: ``Assembly-<StateSlug>.csv`` (e.g. ``Assembly-Tamil-Nadu.csv``) so
#: the same adapter handles every state via the same look-up.
_SNAPSHOT_NAME_BY_STATE_SLUG: Final[dict[str, str]] = {
    "tamil-nadu": "Assembly-Tamil-Nadu.csv",
    "kerala": "Assembly-Kerala.csv",
    "west-bengal": "Assembly-West-Bengal.csv",
    "puducherry": "Assembly-Puducherry.csv",
    "assam": "Assembly-Assam.csv",
}


def _normalise_full_name(full: str) -> str:
    """Normalise a publisher full party name for cross-publisher matching.

    Same shape as PR-W-1's TCPD adapter and PR-W-3's Wikipedia adapter:
    uppercase + collapse internal whitespace + strip non-alphanumeric.
    ``"All India Anna Dravida Munnetra Kazhagam"`` and ``"All India
    Anna Dravida Munnetra Kazhagam (M)"`` collapse to the same key.

    Used by the adapter-local ``by_full`` index to bridge thecont1's
    full-name publisher convention to canonical party_ids when the
    central resolver's by_alias misses.
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper()).strip()
    return re.sub(r"\s+", " ", s)


def _build_by_full_index(parties_csv: Path) -> dict[str, str]:
    """Build a normalised full-name -> party_id index over parties.csv.

    Read once at adapter call time; the per-event run uses the same
    index across all 234 ACs. Skips rows missing the ``full`` cell.

    On duplicate normalised keys (two parties with identical
    normalised full names - a parties.csv-side data-integrity event),
    keeps the FIRST-seen party_id and logs a warning to stderr. This
    is fail-soft because:

    - The collision is unreachable for most per-state parity sweeps
      (e.g. AJSU / AJSUP collide on the Jharkhand-students-union full
      name but TN AE 2026 doesn't reference either).
    - The collision needs curator-side disambiguation in parties.csv
      (edit one of the two ``full`` cells to disambiguate), not
      auto-resolution at adapter level.
    - Hard-failing here would block every per-event parity run until
      the collision is resolved, even for events that don't reference
      the colliding parties.

    A separate curator script may walk parties.csv directly for
    full-name collisions; see follow-on Hans-review work.
    """
    import sys

    out: dict[str, str] = {}
    if not parties_csv.exists():
        return out
    seen_collisions: set[str] = set()
    with parties_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            pid = (row.get("party_id") or "").strip()
            if not pid:
                continue
            full = (row.get("full") or "").strip()
            if not full:
                continue
            key = _normalise_full_name(full)
            if not key:
                continue
            existing = out.get(key)
            if existing is not None and existing != pid:
                if key not in seen_collisions:
                    print(
                        f"thecont1-state adapter [warning]: parties.csv "
                        f"full-name collision on {key!r}: kept "
                        f"{existing!r}, ignoring {pid!r}. "
                        f"Disambiguate via the `full` column for a "
                        f"clean by_full index.",
                        file=sys.stderr,
                    )
                    seen_collisions.add(key)
                continue
            out[key] = pid
    return out


@dataclass(frozen=True, slots=True)
class TheCont1StateAdapter:
    """The PR-S-TN-AE2026 thecont1 adapter; registered against
    ``recon.adapters.EVENT_REGISTRY['thecont1-state']`` at module
    import time.

    Signature matches the ``EventParityAdapter`` Protocol
    (``recon/adapters/__init__.py``). ``state`` + ``event`` + ``kind``
    are REQUIRED; ``vintage`` is accepted and ignored (the event id IS
    the vintage anchor on emitted rows).
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
            raise ValueError("thecont1-state adapter requires --state")
        if not event:
            raise ValueError("thecont1-state adapter requires --event")
        if not kind or kind != "assembly":
            raise ValueError(
                "thecont1-state adapter currently supports --kind "
                "'assembly' only; the upstream repository's per-state "
                "CSV grain is per-Assembly-event."
            )

        # Derive year from event id (same convention as
        # yen_gov_elections adapter). Used to resolve the per-year
        # snapshot directory.
        year_digits = "".join(c for c in event if c.isdigit())
        if len(year_digits) < 4:
            raise ValueError(
                f"thecont1-state adapter cannot derive a year from "
                f"event id {event!r}."
            )
        year = year_digits[-4:]

        file_name = _SNAPSHOT_NAME_BY_STATE_SLUG.get(state)
        if file_name is None:
            raise ValueError(
                f"thecont1-state adapter has no snapshot-name mapping "
                f"for state {state!r}; extend "
                f"_SNAPSHOT_NAME_BY_STATE_SLUG in "
                f"{__name__!r}."
            )

        snapshot_csv = (
            root
            / "datasets"
            / "ephemeral"
            / "thecont1-india-votes-data"
            / year
            / file_name
        )
        if not snapshot_csv.exists():
            raise FileNotFoundError(
                f"thecont1 snapshot not found at "
                f"{snapshot_csv.as_posix()!r}; see "
                f"datasets/ephemeral/thecont1-india-votes-data/"
                f"README.md for the re-snapshot procedure. If the "
                f"upstream repo has not yet published this "
                f"(year, state) CSV, run the parity sweep with this "
                f"source omitted from --source and re-run when the "
                f"upstream file lands."
            )

        # Read entire CSV into memory (per-state per-event CSVs are
        # ~5k rows, well within tolerable working-set).
        with snapshot_csv.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))

        # Two-tier lookup: central resolver for short / alias / ECI
        # code; adapter-local by_full for thecont1's full-name labels.
        # See module docstring for the rationale.
        parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
        resolver = load_resolver(parties_csv)
        by_full = _build_by_full_index(parties_csv)

        # Group by constituency_no + find winner row (max EVM+postal
        # votes per AC).
        by_ac: dict[int, list[dict[str, str]]] = {}
        for r in rows:
            try:
                ac_no = int((r.get("constituency_no") or "0").strip())
            except ValueError:
                continue
            if ac_no < 1:
                continue
            by_ac.setdefault(ac_no, []).append(r)

        out: list[ConstituencyParityRow] = []
        for ac_no in sorted(by_ac):
            ac_rows = by_ac[ac_no]
            # Score by total votes; tie-break by lower serial_no (the
            # upstream's published order).
            scored: list[tuple[int, int, dict[str, str]]] = []
            for r in ac_rows:
                try:
                    evm = int((r.get("evm_votes") or "0").strip() or "0")
                except ValueError:
                    evm = 0
                try:
                    postal = int(
                        (r.get("postal_votes") or "0").strip() or "0"
                    )
                except ValueError:
                    postal = 0
                try:
                    serial = int((r.get("serial_no") or "999").strip() or "999")
                except ValueError:
                    serial = 999
                scored.append((evm + postal, -serial, r))
            scored.sort(key=lambda t: (-t[0], -t[1]))
            if not scored or scored[0][0] <= 0:
                # No usable winner (zero votes); skip the AC.
                continue
            total, _, winner = scored[0]
            party_raw = (winner.get("party") or "").strip()
            # NOTA / Independent surface via dedicated resolver flags.
            is_nota = party_raw.lower() == "none of the above"
            is_ind = party_raw.lower() == "independent"
            # Tier 1: central resolver via short / alias / ECI code.
            winner_pid = resolver.resolve(
                party_short=party_raw,
                eci_code=None,
                is_nota=is_nota,
                is_independent=is_ind,
            )
            # Tier 2: adapter-local by_full bridge when tier 1 misses.
            # Only consult by_full for non-NOTA / non-IND labels (the
            # sentinels are handled in tier 1 via flag). When BOTH
            # lookups miss the adapter preserves parties.IN.UNK per
            # CLAUDE.md section 10 - the verdict.csv will surface a
            # disagreement which the curator handles via mint-new in a
            # follow-on PR-W-* PR.
            if winner_pid == UNK and not is_nota and not is_ind:
                full_key = _normalise_full_name(party_raw)
                if full_key:
                    by_full_hit = by_full.get(full_key)
                    if by_full_hit is not None:
                        winner_pid = by_full_hit
            out.append(
                ConstituencyParityRow(
                    external_scope=THECONT1_STATE_SCOPE,
                    external_vintage=event,
                    state=state,
                    event=event,
                    constituency_no=ac_no,
                    constituency_name=(
                        winner.get("constituency") or ""
                    ).strip(),
                    winner_party_id=winner_pid if winner_pid else UNK,
                    winner_party_short_raw=party_raw,
                    winner_candidate_name=(
                        winner.get("candidate") or ""
                    ).strip(),
                    winner_votes=total,
                )
            )
        return out


#: Adapter instance auto-registered at import time (see __init__.py).
ADAPTER: Final[TheCont1StateAdapter] = TheCont1StateAdapter()


__all__ = [
    "ADAPTER",
    "TheCont1StateAdapter",
    "THECONT1_STATE_SCOPE",
]
