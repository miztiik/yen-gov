"""yen-gov canonical per-PC oracle adapter (PR-PC-LS2024).

Synthesises shape-A rows from the yen-gov canonical summary.csv at
``datasets/elections/<kind>/election=<year>/summary.csv``. This is
NOT an external publisher; it is the yen-gov-side oracle that the
per-PC parity-pc CLI auto-includes as the canonical baseline.

Per the PR-PC-LS2024 brief and Holy Law #9: yen-gov canonical
derives from ECI (Holy Law #9 = issuing authority always wins). So
"yen-gov canonical" effectively IS the ECI oracle in the per-PC
parity. When yen-gov disagrees with bhukyavenkatamahesh or TCPD
on a per-PC winner_party_id, ECI wins; the parity is informational
+ flags DISPUTED for the curator (ESCALATE #3 in plan section 0.5).

The adapter is event-aware: it parses the year from the event id
(e.g. ``LsGenJun2024`` -> 2024) and reads the matching summary.csv.
``state`` parameter is ignored (national event reads all states from
the single summary.csv); ``kind`` MUST be ``parliament`` or
``assembly`` per the dataset directory layout.

Vintage pin: derived from the event year + the standard
``v1.0`` baseline (the canonical summary.csv shape has been stable
since the parliament_2024_eci ingest landed). Per ADR-0042 (operator
snapshot window anchor), the vintage carried on emitted shape-A
rows is ``yen-gov-canonical-<year>``.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from yen_gov.canonical.recon.shape_a import ShapeARow

#: Synthetic scope used as the ShapeARow.external_scope on emitted rows.
#: Distinct from the per-party adapters' ``yen-gov-canonical`` scope so
#: the per-PC aggregator counts this as a separate oracle. (The
#: per-party scope used in PR-W-1 / W-2 / W-3 is for the per-party
#: parity bridge; this adapter is for per-CONSTITUENCY parity.)
YEN_GOV_CANONICAL_PC_SCOPE: Final[str] = "yen-gov-canonical-pc"


def _parse_votes(raw: str) -> int | None:
    """Parse the summary.csv ``winner_votes`` cell to int or None."""
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class YenGovCanonicalPcAdapter:
    """The synthetic yen-gov canonical oracle adapter for per-PC parity.

    Signature matches ``ParityAdapter`` Protocol. The state parameter
    is accepted + ignored (the summary.csv is a single-file national
    table; the per-PC aggregator handles per-state slicing). kind +
    event are required so the adapter can navigate to the correct
    ``datasets/elections/<kind>/election=<year>/summary.csv``.
    """

    def __call__(
        self,
        *,
        root: Path,
        vintage: str,
        state: str | None = None,
        event: str | None = None,
        kind: str | None = None,
    ) -> Iterable[ShapeARow]:
        del state  # unused: summary.csv is national.
        year = self._parse_year_from_event(event)
        if year is None:
            raise ValueError(
                f"yen-gov-canonical-pc adapter requires an event id "
                f"with a 4-digit year suffix (e.g. 'LsGenJun2024'); "
                f"got {event!r}"
            )
        kind = (kind or "parliament").strip()
        if kind not in {"parliament", "assembly"}:
            raise ValueError(
                f"yen-gov-canonical-pc adapter only supports kind "
                f"'parliament' | 'assembly'; got {kind!r}"
            )
        summary_csv = (
            root
            / "datasets"
            / "elections"
            / kind
            / f"election={year}"
            / "summary.csv"
        )
        if not summary_csv.exists():
            raise FileNotFoundError(
                f"yen-gov canonical summary.csv not found at "
                f"{summary_csv.as_posix()!r}; expected after the "
                f"PR-3 corpus-wide regen completes."
            )

        out: list[ShapeARow] = []
        with summary_csv.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                state_slug = (r.get("state") or "").strip()
                entity_id = (r.get("entity_id") or "").strip()
                if not state_slug or not entity_id:
                    continue
                try:
                    cno = entity_id.rsplit("-", 1)[1]
                except IndexError:
                    continue
                cname = (r.get("constituency_name") or "").strip().upper()
                pid = (r.get("winner_party_id") or "").strip()
                if not pid:
                    # Empty winner_party_id is the TN-2026 class of
                    # bug PR-1 + PR-3 closed; should not appear in
                    # LS-2024 summary post-PR-3. Emit with UNK so the
                    # per-PC aggregator surfaces it as a DISPUTED
                    # row rather than silently dropping the PC.
                    pid = "parties.IN.UNK"
                pseudo_short = (r.get("winner_party_short_raw") or "").strip()
                vintage_pin = vintage or f"yen-gov-canonical-{year}"
                out.append(
                    ShapeARow(
                        external_key=(
                            f"{state_slug}:{cno}:{cname}"
                        ),
                        external_short=pseudo_short or pid.rsplit(".", 1)[-1],
                        external_full=(
                            (r.get("winner_candidate") or "").strip() or pid
                        ),
                        external_scope=YEN_GOV_CANONICAL_PC_SCOPE,
                        external_vintage=vintage_pin,
                        proposed_party_id=pid,
                        proposed_action="match",
                        notes=(
                            f"yen-gov canonical summary.csv row; "
                            f"entity_id={entity_id}"
                        ),
                        constituency_no=cno,
                        constituency_name=cname,
                        state_code=state_slug,
                        winner_candidate=(
                            r.get("winner_candidate") or ""
                        ).strip() or None,
                        winner_votes=_parse_votes(
                            r.get("winner_votes") or ""
                        ),
                    )
                )
        return out

    @staticmethod
    def _parse_year_from_event(event: str | None) -> int | None:
        """Extract the 4-digit year from an event id."""
        if not event:
            return None
        m = re.search(r"(\d{4})$", event)
        if m:
            return int(m.group(1))
        return None


#: Module-level singleton; recon.adapters.__init__ registers in REGISTRY.
ADAPTER: Final[YenGovCanonicalPcAdapter] = YenGovCanonicalPcAdapter()


__all__ = [
    "ADAPTER",
    "YEN_GOV_CANONICAL_PC_SCOPE",
    "YenGovCanonicalPcAdapter",
]
