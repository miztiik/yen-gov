"""TCPD per-state per-event AE parity adapter (PR-S-TN-AE2026).

Reads ``datasets/ephemeral/All_States_AE.csv`` - the Trivedi Centre for
Political Data's per-AC compilation of every Indian Assembly election
1961-2021. Filters to the requested (state, year) and projects each
AC's winner (``Position == 1``) into a ``ConstituencyParityRow``.

Compilation cutoff: TCPD's published cut-off is 2021 (per Lok Dhaba's
2026-06 publication metadata). For events POST 2021 (e.g. TN AE 2026,
WB AE 2026, MH AE 2024, KA AE 2023), this adapter returns an EMPTY list
- the source genuinely cannot oracle them. Per the PR-S-TN-AE2026
brief's symmetric stop-condition guidance, the CLI logs the empty-
oracle outcome and continues with the remaining sources (downgrades
3-way to 2-way parity).

Per CLAUDE.md section 10 (no silent demotion): the resolved
``winner_party_id`` comes from the central resolver
(``backend/yen_gov/canonical/party_resolver.py``) applied to TCPD's
``Party`` column (which carries the publisher short form, e.g.
``"AIADMK"``, ``"INC"``, ``"DMK"``). PR-W-1's TCPD-parties adapter
enriched parties.csv with the relevant aliases so the resolver hits
for ~99% of the 2021 corpus.

Per Holy Law #9: when TCPD disagrees with yen-gov OR thecont1 in the
verdict.csv, ECI authority wins via curator disposition. The adapter
NEVER mutates candidacies.csv.

Schema of the upstream CSV (column index established by the
``State_Name`` / ``Year`` / ``Constituency_No`` header positions; see
``recon/adapters/thecont1_state.py`` for the corresponding thecont1
schema):

  - ``State_Name``        (TCPD state token: ``"Tamil_Nadu"``,
                          ``"West_Bengal"``, ...; underscored form -
                          distinct from yen-gov's slug
                          ``"tamil-nadu"``)
  - ``Year``              (4-digit year as string)
  - ``Constituency_No``   (1-based AC number)
  - ``Position``          (1 = winner; 2, 3, ... = runners-up)
  - ``Candidate``         (publisher candidate name)
  - ``Party``             (publisher short / abbreviation)
  - ``Votes``             (integer; total votes for this candidate)
  - ``Constituency_Name`` (publisher constituency name)
  - ``Party_Type_TCPD``   (e.g. ``"National Party"``,
                          ``"State-based Party"``) - unused here but
                          documented for cross-reference with
                          PR-W-1's tcpd_parties adapter.

Source provenance: ``external_vintage`` on emitted rows pins to the
TCPD compilation year (``"2021"`` per the PR-W-1 / TCPD_VINTAGE
constant). This is distinct from the event id (e.g.
``"AcGenMay2026"``) because TCPD's row identity is the compilation
edition, NOT the per-event observation - even for an event TCPD
DOES cover (e.g. TN 2021 = ``"AcGenApr2021"``), the rows come from
the 2021-cutoff compilation, not a per-event TCPD snapshot.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from yen_gov.canonical.party_resolver import UNK, load_resolver
from yen_gov.canonical.recon.shape_b import ConstituencyParityRow

#: Adapter source-id used as the ``ConstituencyParityRow.external_scope``
#: on emitted rows.
TCPD_STATE_SCOPE: Final[str] = "tcpd-state"

#: TCPD compilation cutoff year - constant matches PR-W-1's
#: ``TCPD_VINTAGE`` declaration. Used as the ``external_vintage`` on
#: every emitted row to mark the compilation edition (ADR-0042
#: publisher edition anchor).
TCPD_VINTAGE: Final[str] = "2021"

#: Where the TCPD All_States_AE.csv lives on disk (gitignored
#: ephemeral; operator-dropped). Mirrors
#: ``recon/adapters/tcpd_parties.py``'s DEFAULT_TCPD_CSV pattern.
DEFAULT_TCPD_AE_CSV: Final[Path] = Path(
    "datasets/ephemeral/All_States_AE.csv"
)

#: State-slug -> TCPD ``State_Name`` token map. TCPD's published
#: state names are underscored (``"Tamil_Nadu"``, ``"West_Bengal"``);
#: yen-gov uses the kebab-slug shape (``"tamil-nadu"``,
#: ``"west-bengal"``). This per-state table covers the 5 cohort states
#: targetted by the 2026-06-10 plan (TN, WB, KL, MH, KA, MP) +
#: AP / TG / PY for completeness. Extend per new state in scope.
_TCPD_STATE_NAME_BY_SLUG: Final[dict[str, str]] = {
    "tamil-nadu": "Tamil_Nadu",
    "kerala": "Kerala",
    "west-bengal": "West_Bengal",
    "puducherry": "Puducherry",
    "assam": "Assam",
    "maharashtra": "Maharashtra",
    "karnataka": "Karnataka",
    "madhya-pradesh": "Madhya_Pradesh",
    "andhra-pradesh": "Andhra_Pradesh",
    "telangana": "Telangana",
}


@dataclass(frozen=True, slots=True)
class TcpdStateAdapter:
    """The PR-S-TN-AE2026 TCPD per-state adapter; registered against
    ``recon.adapters.EVENT_REGISTRY['tcpd-state']`` at module import
    time.

    Signature matches the ``EventParityAdapter`` Protocol
    (``recon/adapters/__init__.py``). ``state`` + ``event`` are
    REQUIRED; ``kind`` MUST be ``"assembly"`` (TCPD's PC compilation
    is a separate file - ``All_States_GE.csv`` - handled by a
    sibling adapter in PR-PC-* PRs).
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
            raise ValueError("tcpd-state adapter requires --state")
        if not event:
            raise ValueError("tcpd-state adapter requires --event")
        if not kind or kind != "assembly":
            raise ValueError(
                "tcpd-state adapter supports --kind 'assembly' only; "
                "the upstream All_States_AE.csv is the Assembly-only "
                "TCPD compilation. PC parity uses a sibling adapter "
                "in PR-PC-* PRs."
            )

        # The adapter's vintage is FIXED at the TCPD compilation year
        # per ADR-0042 (publisher edition anchor). Refuse to claim a
        # different vintage; the operator running parity with
        # ``--vintage 2026`` is asking for an oracle TCPD can't
        # provide (see PR-S-TN-AE2026 brief on TCPD coverage gap).
        if vintage and vintage != TCPD_VINTAGE:
            raise ValueError(
                f"tcpd-state adapter only supports vintage "
                f"{TCPD_VINTAGE!r} (the published TCPD compilation "
                f"cutoff); got {vintage!r}. The operator may have "
                f"specified --vintage matching the event year - the "
                f"correct invocation for TCPD always pins to the "
                f"compilation edition."
            )

        tcpd_state_name = _TCPD_STATE_NAME_BY_SLUG.get(state)
        if tcpd_state_name is None:
            raise ValueError(
                f"tcpd-state adapter has no TCPD-token mapping for "
                f"state {state!r}; extend _TCPD_STATE_NAME_BY_SLUG "
                f"in {__name__!r}."
            )

        # Derive year from event id.
        year_digits = "".join(c for c in event if c.isdigit())
        if len(year_digits) < 4:
            raise ValueError(
                f"tcpd-state adapter cannot derive a year from event "
                f"id {event!r}."
            )
        year = year_digits[-4:]

        tcpd_csv = root / DEFAULT_TCPD_AE_CSV
        if not tcpd_csv.exists():
            raise FileNotFoundError(
                f"TCPD All_States_AE.csv not found at "
                f"{tcpd_csv.as_posix()!r}; operator drops the upstream "
                f"file (gitignored ephemeral)."
            )

        # Resolver is cached at the module level via load_resolver's
        # lru_cache - safe to call once per adapter run.
        parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
        resolver = load_resolver(parties_csv)

        # Group by constituency_no, picking ``Position == '1'`` rows
        # only. Streams the file row-by-row (113 MB; full-corpus
        # walk is the bottleneck of this adapter but happens only on
        # operator invocation, not in CI per Tier-C contract).
        #
        # TCPD bypoll-conflation policy (PR-S-WB-AE2021 finding,
        # 2026-06-11): when a state has within-cycle bypolls (death,
        # resignation, defection-disqualification) TCPD's compilation
        # carries TWO Position=1 rows per affected AC for the same
        # Year - the original polling-cycle winner FIRST, the bypoll
        # winner SECOND. Verified across 5 WB 2021 ACs (#7 DINHATA,
        # #86 SANTIPUR, #109 KHARDAHA, #127 GOSABA, #159 BHABANIPUR).
        # For parity against yen-gov's original-cycle candidacies, the
        # FIRST-seen Position=1 row is the one to keep; subsequent
        # rows for the same AC are skipped with a stderr warning so
        # the operator sees the conflation count in the run log. This
        # is a STRUCTURAL fix per CLAUDE.md section 10 (no band-aids):
        # the adapter now correctly tolerates TCPD's published
        # multi-event-per-year shape across all states + years.
        import sys

        by_ac: dict[int, dict[str, str]] = {}
        bypoll_conflated_acs: list[int] = []
        n_state_year_rows = 0
        with tcpd_csv.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                if (r.get("State_Name") or "").strip() != tcpd_state_name:
                    continue
                if (r.get("Year") or "").strip() != year:
                    continue
                n_state_year_rows += 1
                if (r.get("Position") or "").strip() != "1":
                    continue
                try:
                    ac_no = int((r.get("Constituency_No") or "0").strip())
                except ValueError:
                    continue
                if ac_no < 1:
                    continue
                if ac_no in by_ac:
                    # TCPD bypoll-conflation: keep first-seen
                    # (original polling-cycle winner); skip subsequent
                    # rows; record for the operator-facing summary.
                    bypoll_conflated_acs.append(ac_no)
                    continue
                by_ac[ac_no] = r

        if bypoll_conflated_acs:
            print(
                f"tcpd-state adapter [warning]: TCPD "
                f"All_States_AE.csv lists multiple Position=1 rows "
                f"for {len(bypoll_conflated_acs)} AC(s) in "
                f"(State_Name={tcpd_state_name}, Year={year}) - "
                f""
                f"AC#{sorted(bypoll_conflated_acs)!r}. Treating as "
                f"bypoll-conflation per WB-2021 finding; keeping the "
                f"first-seen row (original polling-cycle winner) "
                f"per AC and skipping bypoll re-winners. Parity will "
                f"oracle against original-cycle results.",
                file=sys.stderr,
            )

        # Empty-oracle outcome: TCPD has no rows for the requested
        # (state, year) - typical post-2021 cutoff scenario. Return
        # empty list; CLI logs the empty count and continues with
        # other sources per the brief's symmetric guidance.
        if not by_ac:
            return []

        out: list[ConstituencyParityRow] = []
        for ac_no in sorted(by_ac):
            winner = by_ac[ac_no]
            party_raw = (winner.get("Party") or "").strip()
            try:
                votes = int((winner.get("Votes") or "0").strip() or "0")
            except ValueError:
                votes = 0
            # TCPD encodes NOTA + Independent inline in the Party
            # column ("NOTA", "IND" abbreviations are convention). We
            # check both with the resolver flags so the SENTINELS
            # (parties.IN.NOTA / parties.IN.IND) surface uniformly
            # with yen-gov and thecont1 adapters.
            is_nota = party_raw.upper() in {"NOTA", "NONE", "NONE OF THE ABOVE"}
            is_ind = party_raw.upper() in {"IND", "INDEPENDENT"}
            winner_pid = resolver.resolve(
                party_short=party_raw,
                eci_code=None,
                is_nota=is_nota,
                is_independent=is_ind,
            )
            out.append(
                ConstituencyParityRow(
                    external_scope=TCPD_STATE_SCOPE,
                    external_vintage=TCPD_VINTAGE,
                    state=state,
                    event=event,
                    constituency_no=ac_no,
                    constituency_name=(
                        winner.get("Constituency_Name") or ""
                    ).strip(),
                    winner_party_id=winner_pid if winner_pid else UNK,
                    winner_party_short_raw=party_raw,
                    winner_candidate_name=(
                        winner.get("Candidate") or ""
                    ).strip(),
                    winner_votes=votes if votes > 0 else None,
                )
            )
        return out


#: Adapter instance auto-registered at import time (see __init__.py).
ADAPTER: Final[TcpdStateAdapter] = TcpdStateAdapter()


__all__ = [
    "ADAPTER",
    "TcpdStateAdapter",
    "TCPD_STATE_SCOPE",
    "TCPD_VINTAGE",
    "DEFAULT_TCPD_AE_CSV",
]
