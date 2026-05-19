"""Cross-page composers that bridge sources/ outputs into schema-bound models.

The constituencywise mapper (`sources.eci.constituencywise.to_constituency_result`)
accepts an optional `party_lookup: dict[full_name, (short, eci_code)]` to fill
`party_short` and `party_eci_code` from full party names. The lookup is built
from a `PartywiseSnapshot` (which carries all three of full / short / code).

Keeping this in `pipeline/` rather than `sources/eci/` enforces the single-
responsibility split documented in docs/architecture/backend/sources-eci.md: the partywise parser knows
nothing about the constituencywise mapper, and vice versa. The composer is
the thread.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from yen_gov.core.models import (
    ConstituencyResult,
    PartiesSnapshot,
    PartyEntry,
    PartyTotals,
    ResultSummary,
    SourceRef,
    SummaryTotals,
)
from yen_gov.sources.eci.partywise import PartywiseSnapshot
from yen_gov.sources.eci.section3 import ParticipatingParty
from yen_gov.sources.eci.statistical_report_detailed import DetailedResultsRaw


def party_lookup_from_partywise(
    snapshot: PartywiseSnapshot,
) -> dict[str, tuple[str, str | None]]:
    """Build the {full_name → (short_name, eci_code)} map for a state.

    Conflict policy: the partywise table lists each party once per state, so
    duplicate full_names are not expected. If two rows do share a full_name
    (ECI page corruption), this raises rather than silently overwriting —
    party identity must be unambiguous before it propagates into per-AC results.
    """
    out: dict[str, tuple[str, str | None]] = {}
    for row in snapshot.parties:
        if row.full_name in out:
            raise ValueError(
                f"duplicate party full_name in partywise snapshot: {row.full_name!r}"
            )
        out[row.full_name] = (row.short_name, row.eci_code)
    return out


def eci_code_by_short_from_partywise(
    snapshot: PartywiseSnapshot,
) -> dict[str, str]:
    """Build {short_name → eci_code} for parties whose code is known.

    Used by the Section-10 path (which carries short codes only) to backfill
    the numeric `party_eci_code`. Parties whose `eci_code` is None on the
    snapshot are simply omitted — caller falls back to None for those.

    Conflict policy: a real partywise page has one row per party, so duplicate
    short_names are unexpected and raise (data-integrity guard).
    """
    out: dict[str, str] = {}
    for row in snapshot.parties:
        if row.eci_code is None:
            continue
        if row.short_name in out and out[row.short_name] != row.eci_code:
            raise ValueError(
                f"partywise snapshot has conflicting eci_codes for short {row.short_name!r}: "
                f"{out[row.short_name]} vs {row.eci_code}"
            )
        out[row.short_name] = row.eci_code
    return out


def compose_result_summary(
    *,
    election: str,
    state: str,
    body: str,
    partywise: PartywiseSnapshot,
    constituencies: list[ConstituencyResult],
    sources: list[SourceRef],
) -> ResultSummary:
    """Aggregate per-AC results + the partywise snapshot into a ResultSummary.

    The partywise snapshot is the spine: it determines which parties get a
    `party_totals` row and what their `seats_won` is. Vote totals come from
    walking every candidate (including those collapsed into `others` via
    `OthersBucket`? — no: OthersBucket loses per-party identity, so this
    composer only sees parties present in the kept top-N candidates plus IND).

    Trade-off: when `processing.results.collapse_others` is true, the votes
    bucketed into `others` are excluded from per-party totals. This is
    documented; a downstream consumer that wants exact party-level vote
    totals must run the pipeline with `top_n_candidates` ≥ the field size.
    Either way, `totals.votes_polled` is the true sum from each constituency,
    so vote shares are computed against the unfiltered denominator.
    """
    if not constituencies:
        raise ValueError("compose_result_summary needs at least one ConstituencyResult")

    votes_by_short: dict[str, int] = defaultdict(int)
    contested_by_short: dict[str, set[int]] = defaultdict(set)
    total_votes_polled = 0

    for cr in constituencies:
        total_votes_polled += cr.totals.votes_polled
        for cand in cr.candidates:
            votes_by_short[cand.party_short] += cand.votes
            contested_by_short[cand.party_short].add(cr.eci_no)

    party_totals: list[PartyTotals] = []
    seen_shorts: set[str] = set()
    for row in partywise.parties:
        seats = row.seats_won + row.leading
        votes = votes_by_short.get(row.short_name, 0)
        share = (votes / total_votes_polled * 100.0) if total_votes_polled > 0 else 0.0
        contested = len(contested_by_short.get(row.short_name, set())) or None
        party_totals.append(PartyTotals(
            party_eci_code=row.eci_code,
            party_short=row.short_name,
            party_full=row.full_name,
            seats_contested=contested,
            seats_won=seats,
            votes=votes,
            vote_share_pct=round(share, 2),
        ))
        seen_shorts.add(row.short_name)

    # Surface vote-bearing parties present in constituencies but absent from
    # partywise (parties that won zero seats but fielded candidates). Without
    # this, their votes vanish from the summary even though they appear in
    # per-AC results — a silent gap a consumer cannot detect.
    for short, votes in sorted(votes_by_short.items()):
        if short in seen_shorts or votes == 0:
            continue
        share = (votes / total_votes_polled * 100.0) if total_votes_polled > 0 else 0.0
        party_totals.append(PartyTotals(
            party_eci_code=None,
            party_short=short,
            party_full=None,
            seats_contested=len(contested_by_short[short]) or None,
            seats_won=0,
            votes=votes,
            vote_share_pct=round(share, 2),
        ))

    return ResultSummary(
        sources=sources,
        election=election,
        state=state,
        body=body,
        total_seats=partywise.total_seats,
        totals=SummaryTotals(votes_polled=total_votes_polled),
        party_totals=party_totals,
    )


def reconcile_winners_against_partywise(
    *,
    partywise: PartywiseSnapshot,
    constituencies: list[ConstituencyResult],
) -> None:
    """Cross-check: per-AC winners aggregated by party_short must match partywise.

    `seats_won + leading` from the partywise table is the authoritative seat
    count per party for the state. We re-derive the same from the per-AC
    winners and raise on any discrepancy. Either source could be wrong; what
    matters is that they agree before we publish.

    Independents are aggregated under "IND" (per `to_constituency_result`).
    Parties present in per-AC winners but absent from partywise raise — we
    deliberately do NOT silently extend the partywise table here, because a
    winning party that doesn't appear in partywise is a data-integrity red
    flag, not a fringe-party edge case.
    """
    expected: dict[str, int] = {
        row.short_name: row.seats_won + row.leading
        for row in partywise.parties
    }
    actual: dict[str, int] = defaultdict(int)
    for cr in constituencies:
        actual[cr.winner.party_short] += 1

    mismatches: list[str] = []
    for short, count in sorted(actual.items()):
        exp = expected.get(short)
        if exp is None:
            mismatches.append(f"{short}: per-AC winners={count}, absent from partywise")
        elif exp != count:
            mismatches.append(f"{short}: per-AC winners={count}, partywise={exp}")
    for short, exp in sorted(expected.items()):
        if exp > 0 and short not in actual:
            mismatches.append(f"{short}: partywise={exp}, per-AC winners=0")

    if mismatches:
        raise ValueError(
            "winner reconciliation failed:\n  " + "\n  ".join(mismatches)
        )


def compose_result_summary_from_section_10(
    raw: DetailedResultsRaw,
    *,
    election: str,
    state: str,
    sources: list[SourceRef],
    party_eci_codes: dict[str, str] | None = None,
) -> ResultSummary:
    """Compose a ResultSummary from Section 10 of an ECI Statistical Report.

    Phase B has no partywise.htm dependency — Section 10 already carries every
    candidate of every AC, so the state-level rollup is fully derivable from
    one sheet. Walking the raw sections (not emitted ConstituencyResults)
    means the per-party totals are exact even when the per-AC emit collapses
    parties below `top_n` into an `others` bucket.

    Conventions:

      - `total_seats` = total AC count in the sheet (`len(raw.sections)`),
        including any countermanded ACs. The "seats decided" number is
        recoverable as the count of party_totals.seats_won, but the
        constitutional seat count is what the schema wants.
      - `totals.electors` = sum of per-AC `total_electors` (drops ACs that
        had no listed electors).
      - `totals.votes_polled` = sum of per-AC `polled_total` (excludes
        countermanded ACs whose polled_total is 0).
      - `totals.turnout_pct` = polled / electors * 100, rounded to 2dp.
        None if either side is unknown.
      - Per-party rows are taken in *seats-won-then-votes-desc* order, with
        IND collapsed under a single "IND" bucket (matching the per-AC
        mapper). NOTA is excluded from party_totals (it is not a party).
      - `party_eci_code` is filled from the optional `party_eci_codes`
        `{short_name → eci_code}` lookup (typically built from a partywise
        snapshot via `eci_code_by_short_from_partywise`). Independents and
        unmapped shorts get None.
      - `body` is hardcoded "AC" — Section 10 only ships for assembly events
        in this slice. PC support is a future concern.
    """
    if not raw.sections:
        raise ValueError("compose_result_summary_from_section_10 needs sections")

    codes = party_eci_codes or {}
    votes_by_short: dict[str, int] = defaultdict(int)
    seats_by_short: dict[str, int] = defaultdict(int)
    contested_by_short: dict[str, set[int]] = defaultdict(set)
    total_polled = 0
    total_electors = 0

    for sec in raw.sections:
        total_polled += sec.polled_total
        if sec.total_electors is not None:
            total_electors += sec.total_electors

        contestants = [c for c in sec.candidates if not c.is_nota]
        for cand in contestants:
            short = "IND" if cand.is_independent else cand.party_short
            votes_by_short[short] += cand.votes_total
            contested_by_short[short].add(sec.eci_no)

        if sec.polled_total == 0:
            continue  # countermanded — no winner
        contestants.sort(key=lambda c: c.votes_total, reverse=True)
        winner = contestants[0]
        winner_short = "IND" if winner.is_independent else winner.party_short
        seats_by_short[winner_short] += 1

    party_totals: list[PartyTotals] = []
    for short in sorted(
        votes_by_short.keys(),
        key=lambda s: (-seats_by_short.get(s, 0), -votes_by_short[s], s),
    ):
        votes = votes_by_short[short]
        share = (votes / total_polled * 100.0) if total_polled > 0 else 0.0
        party_totals.append(PartyTotals(
            party_eci_code=None if short == "IND" else codes.get(short),
            party_short=short,
            party_full=None,
            seats_contested=len(contested_by_short[short]) or None,
            seats_won=seats_by_short.get(short, 0),
            votes=votes,
            vote_share_pct=round(share, 2),
        ))

    turnout_pct = (
        round(total_polled / total_electors * 100.0, 2)
        if total_polled and total_electors else None
    )

    return ResultSummary(
        sources=sources,
        election=election,
        state=state,
        body="AC",
        total_seats=len(raw.sections),
        totals=SummaryTotals(
            electors=total_electors or None,
            votes_polled=total_polled,
            turnout_pct=turnout_pct,
        ),
        party_totals=party_totals,
    )


@dataclass(frozen=True)
class PartyRegistryEntry:
    """One canonical {short → numeric eci_code, full_name} mapping with provenance.

    Sourced from ``datasets/taxonomy/parties.json`` — the single canonical
    party registry adopted in the canonical-store pivot (ADR-0030). PR-R.3
    (1.8e closure) retired the prior 3-layer aggregation (per-event
    parties.json + ``reference/in/parties-discovered.json`` overlay +
    ``reference/in/parties.json`` master); the same lookup is now derived
    from the canonical taxonomy file and its forward index built by
    ``yen_gov.canonical.adapters.eci.party_lookup.load_party_lookup``.

    ``eci_code`` may be ``None`` for taxonomy entries that have an empty
    ``eci_codes[]`` (the party exists in our roster but has not yet
    appeared in any partywise URL we have ingested). The downstream emit
    path treats such entries as unresolved for purposes of writing
    per-event ``parties.json`` (which schema-requires a non-null code).
    """

    eci_code: str | None
    full_name: str
    source_urls: tuple[str, ...]


def load_eci_party_registry(
    elections_root: Path,
) -> dict[str, PartyRegistryEntry]:
    """Build ``{short_name → PartyRegistryEntry}`` from ``datasets/taxonomy/parties.json``.

    Every party row contributes one canonical entry keyed on its
    ``short_name``; every alias in ``aliases[]`` (and the ``full_name``
    itself) gets an additional key pointing at the same entry so upstream
    variants like ``AIADMK`` and ``All India Anna Dravida Munnetra
    Kazhagam`` both resolve. When ``eci_codes[]`` has more than one
    historical code we keep the first — it is the value the per-event
    ``parties.json`` will carry; readers that need the full set should go
    to the canonical taxonomy directly.

    Returns an empty dict if the taxonomy file is absent (fresh checkout).
    The downstream emit path handles that by skipping ``parties.json``
    emit, matching the pre-PR-R.3 fresh-checkout behaviour.
    """
    taxonomy_path = elections_root.parent / "taxonomy" / "parties.json"
    if not taxonomy_path.exists():
        return {}
    doc = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    file_urls = tuple(s["url"] for s in doc.get("sources", []))

    out: dict[str, PartyRegistryEntry] = {}
    for entry in doc.get("parties", []):
        short = entry["short_name"]
        full = entry["full_name"]
        codes = entry.get("eci_codes") or []
        code = codes[0] if codes else None
        canonical = PartyRegistryEntry(
            eci_code=code, full_name=full, source_urls=file_urls,
        )
        # Primary key: short_name. Secondary keys: full_name + every alias.
        # Aliases never overwrite an already-bound short_name (first
        # canonical wins, matching pre-PR-R.3 behaviour).
        for key in (short, full, *(entry.get("aliases") or [])):
            if key and key not in out:
                out[key] = canonical

    return out


def parties_snapshot_from_section3(
    section_3_parties: list[ParticipatingParty],
    *,
    election: str,
    section_3_source: SourceRef,
    registry: dict[str, PartyRegistryEntry],
    fetched_at: str,
) -> tuple[PartiesSnapshot | None, list[str]]:
    """Build a ``PartiesSnapshot`` for an archived event using Section 3 + the registry.

    Section 3 of the Statistical Report tells us *which* parties participated;
    the registry tells us their numeric ``eci_code``. Parties present in
    Section 3 but absent from the registry are returned as the second tuple
    element so the caller can log them — they are NOT silently dropped at
    the call site, but they cannot ship in ``parties.json`` either (the
    schema requires ``eci_code``).

    Returns ``(None, unresolved)`` when zero parties resolve, so the caller
    can skip the file write rather than emit an empty (and schema-invalid,
    minItems=1) artifact.

    ``sources[]`` of the returned snapshot is composed per ADR-0002 as an
    aggregated artifact: Section 3 (the "which parties participated" claim)
    plus every distinct partywise URL from the registry entries that
    contributed (the "this is its eci_code" claim). The ``fetched_at`` arg
    timestamps the registry-merge step so this artifact's provenance is
    self-contained.
    """
    entries: list[PartyEntry] = []
    contributing_urls: set[str] = set()
    unresolved: list[str] = []
    seen_shorts: set[str] = set()
    for p in section_3_parties:
        if p.short_name in seen_shorts:
            continue  # Section 3 is per-event; duplicates would be a parser bug, but be defensive.
        seen_shorts.add(p.short_name)
        reg = registry.get(p.short_name)
        if reg is None or reg.eci_code is None:
            # Either short is wholly unknown OR it is in the canonical
            # taxonomy roster but we have no observed eci_code yet — both
            # are "unresolved" from the per-event parties.json schema's
            # perspective (it requires a non-null eci_code). The caller
            # surfaces these so an operator can extend
            # ``datasets/taxonomy/parties.json`` with the missing alias /
            # eci_code, after which the next run will resolve cleanly.
            unresolved.append(p.short_name)
            continue
        entries.append(PartyEntry(
            eci_code=reg.eci_code,
            short_name=p.short_name,
            full_name=p.full_name,  # Section 3's full_name is the per-event canonical
        ))
        contributing_urls.update(reg.source_urls)

    if not entries:
        return None, unresolved

    sources = [section_3_source] + [
        SourceRef(url=url, fetched_at=fetched_at)
        for url in sorted(contributing_urls)
    ]
    return PartiesSnapshot(
        sources=sources,
        election=election,
        parties=entries,
    ), unresolved

