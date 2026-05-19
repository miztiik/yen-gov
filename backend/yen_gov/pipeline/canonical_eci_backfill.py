"""Canonical ECI backfill — JSON corpus → Parquet via the canonical adapter.

Walks ``datasets/elections/<event>/<state>/results/*.json`` (the legacy per-AC
artifacts emitted by the older `eci-statreport-emit*` commands), reconstructs
the contest-scoping source for each AC, calls the canonical ECI adapter, and
hands the resulting BatchEnvelope to ``canonical.writer.write_batch``.

This is the Phase 1.1 step-5 driver. It does NOT re-fetch from ECI; it reads
the on-disk JSON corpus that prior live-emit runs have already produced.

Public API:

- :func:`build_slice_envelope` — **in-memory primary API.** Takes a list of
  parsed ``ConstituencyResult`` objects and returns the per-slice canonical
  rows (observations, sources, candidate dims, AC dims). Used by
  ``pipeline/run.py`` after a live ECI fetch produces constituencies in
  memory, so the canonical write does not depend on the per-AC JSON
  artifacts the writers used to emit (TODO row ``1.8b-writers-b``).
- :func:`backfill_elections` — driver that walks the on-disk corpus,
  delegates per-slice work to :func:`_process_slice` (thin disk-wrapper
  around the primary API), and batches per-event into ``write_batch``.

Design notes:

- ``source_id`` is derived deterministically from the source URL — first 12
  hex chars of sha256(url), prefixed ``src-``. Stable across re-runs.
- ``content_hash`` is empty string (we don't have the original upstream bytes
  on this backfill path; the OWID-shape ``sources.parquet`` schema allows it).
- ``delim_year`` defaults to 2008 for all post-delimitation AC contests. The
  pre-delimitation backfill (delim_year=1976) will land in a follow-up.
- Unresolved party shorts fall back to ``parties.IN.UNK`` and are recorded
  in the returned ``BackfillResult.unresolved_parties`` for operator triage.
  This is the documented compromise that lets candidate-* + ac-* rows ship
  complete; party-* rollups for UNK are computed but flagged in the result.
- The driver uses a single in-memory BatchEnvelope per (event, state) slice
  so the writer's UPSERT semantics keep re-runs idempotent.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from yen_gov.canonical.adapters.eci import (
    PartyLookup,
    dim_rows_from_constituency,
    load_party_lookup,
    observations_from_constituency,
    parse_period_label,
    party_alliance_dim_rows,
    party_dim_rows,
    state_rollup_observations,
)
from yen_gov.canonical.adapters.eci.party_lookup import UnknownPartyError
from yen_gov.canonical.adapters.eci.rollups import ACContestSummary
from yen_gov.canonical.envelope import (
    AcDimRow,
    BatchEnvelope,
    CandidateDimRow,
    ObservationRow,
    PartyAllianceDimRow,
    PartyDimRow,
    SourceRow,
)
from yen_gov.canonical.writer import WriteResult, write_batch
from yen_gov.core.models import ConstituencyResult

log = logging.getLogger(__name__)


DEFAULT_DELIM_YEAR = 2008
FORFEITURE_THRESHOLD_PCT = 16.67  # ECI deposit-forfeiture cutoff


@dataclass
class SliceResult:
    event_id: str
    state_code: str
    acs_processed: int
    observation_rows_written: int
    source_rows_written: int
    unresolved_parties: dict[str, int] = field(default_factory=dict)
    error: str | None = None


@dataclass
class BackfillResult:
    slices: list[SliceResult] = field(default_factory=list)
    acs_processed: int = 0
    states_processed: int = 0
    events_processed: int = 0
    unresolved_parties: dict[str, int] = field(default_factory=dict)
    write_result: WriteResult | None = None

    @property
    def observation_rows_written(self) -> int:
        if self.write_result is not None:
            return self.write_result.observation_rows_written
        return sum(s.observation_rows_written for s in self.slices)

    @property
    def source_rows_written(self) -> int:
        if self.write_result is not None:
            return self.write_result.source_rows_written
        return sum(s.source_rows_written for s in self.slices)

    @property
    def failed_slices(self) -> list[SliceResult]:
        return [s for s in self.slices if s.error is not None]


ProgressFn = "callable[[SliceResult], None] | None"


def backfill_elections(
    *,
    datasets_root: Path,
    events: list[str] | None = None,
    states: list[str] | None = None,
    on_slice: ProgressFn = None,
    on_write_start: "callable[[int, int], None] | None" = None,
    on_event_written: "callable[[str, int, int, float], None] | None" = None,
    corpus_root: Path | None = None,
) -> BackfillResult:
    """Walk the per-AC JSON corpus and emit one event per write_batch call.

    Per-event batching:

    - Parse every (event, state) slice belonging to one event into a single
      in-memory envelope, then call ``write_batch`` once for that event.
    - Each event's rows are persisted to ``datasets/elections/election_results.parquet``
      before the next event starts. If the run aborts mid-corpus, work done
      so far is on disk; a re-run skips events whose observation_ids are
      already present (UPSERT semantics make it a no-op).
    - ``on_slice`` fires after each (event, state) parse; ``on_event_written``
      fires after each successful event write with (event_id, n_obs, n_sources,
      duration_s) for live progress visibility.

    Args:
        datasets_root: repo's ``datasets/`` directory. Used for the taxonomy
            (``party_lookup``) AND as the default JSON-corpus root + write
            target.
        events: optional allow-list of event_ids (e.g. ["AcGenMay2026"]).
        states: optional allow-list of state codes (e.g. ["S22"]).
        on_slice: callback invoked after each (event, state) slice is parsed.
        on_write_start: callback invoked before each event's write_batch.
        on_event_written: callback invoked after each event's write_batch.
        corpus_root: optional override for the per-AC JSON corpus directory
            (containing ``<event>/<state>/results/*.json``). Defaults to
            ``datasets_root / "elections"``. Lets the operator point the
            backfill at a restored snapshot under e.g.
            ``datasets/ephemeral/legacy-corpus/elections`` without polluting
            the canonical write target. Write target is unchanged
            (``datasets_root / "elections" / "election_results.parquet"``).

    Returns:
        BackfillResult summarising parsed-row counts, slice errors, and
        unresolved parties. ``observation_rows_written`` is the sum across
        all successful per-event writes.
    """
    import time

    party_lookup = load_party_lookup(datasets_root)
    elections_root = corpus_root if corpus_root is not None else (datasets_root / "elections")

    event_dirs = sorted(
        p for p in elections_root.iterdir()
        if p.is_dir() and not p.name.startswith("_")
        and (not events or p.name in events)
    )

    result = BackfillResult()
    result.events_processed = len(event_dirs)
    unresolved: dict[str, int] = defaultdict(int)
    seen_states: set[tuple[str, str]] = set()
    total_obs_written = 0
    total_src_written = 0
    last_obs_written = 0
    last_src_written = 0

    for event_dir in event_dirs:
        event_id = event_dir.name
        try:
            period = parse_period_label(event_id)
        except ValueError:
            log.warning("skipping unparseable event_id: %s", event_id)
            continue

        event_obs: list[ObservationRow] = []
        event_sources: dict[str, SourceRow] = {}
        event_candidate_dims: list[CandidateDimRow] = []
        event_ac_dims: dict[str, AcDimRow] = {}  # ac_id -> row (UPSERT-dedupe)

        state_dirs = sorted(
            p for p in event_dir.iterdir()
            if p.is_dir() and p.name.startswith(("S", "U"))
            and (not states or p.name in states)
        )
        for state_dir in state_dirs:
            state_code = state_dir.name
            results_dir = state_dir / "results"
            if not results_dir.is_dir():
                continue
            try:
                rows, sources, ac_count, slice_unresolved, cand_dims, ac_dims = _process_slice(
                    results_dir=results_dir,
                    state_code=state_code,
                    period=period,
                    party_lookup=party_lookup,
                )
            except Exception as exc:
                log.exception("slice %s/%s parse failed", event_id, state_code)
                sr = SliceResult(
                    event_id=event_id, state_code=state_code,
                    acs_processed=0,
                    observation_rows_written=0, source_rows_written=0,
                    error=f"parse: {type(exc).__name__}: {exc}",
                )
                result.slices.append(sr)
                if on_slice is not None:
                    on_slice(sr)
                continue

            event_obs.extend(rows)
            for sid, srow in sources.items():
                event_sources.setdefault(sid, srow)
            event_candidate_dims.extend(cand_dims)
            for ad in ac_dims:
                event_ac_dims.setdefault(ad.ac_id, ad)
            for short, n in slice_unresolved.items():
                unresolved[short] += n
            seen_states.add((event_id, state_code))
            sr = SliceResult(
                event_id=event_id, state_code=state_code,
                acs_processed=ac_count,
                observation_rows_written=len(rows),
                source_rows_written=len(sources),
                unresolved_parties=slice_unresolved,
            )
            result.slices.append(sr)
            result.acs_processed += ac_count
            if on_slice is not None:
                on_slice(sr)

        if not event_obs:
            continue

        if on_write_start is not None:
            on_write_start(len(event_obs), len(event_sources))

        # Party dims are seeded once per event from the (event-wide) registry.
        # The first source row of the event is used as the provenance pointer
        # for the parties.json registry — UPSERT keeps later events idempotent.
        first_source_id = sorted(event_sources.keys())[0] if event_sources else ""
        party_dim_payload = (
            [PartyDimRow(**r) for r in party_dim_rows(party_lookup, source_id=first_source_id)]
            if first_source_id
            else []
        )
        # Alliance dim mirrors party_dim: emit the full alliance_history roster
        # on every envelope. Writer UPSERTs on composite PK (party_id,
        # period_label), so multiple events re-emitting are idempotent.
        party_alliance_payload = (
            [
                PartyAllianceDimRow(**r)
                for r in party_alliance_dim_rows(party_lookup, source_id=first_source_id)
            ]
            if first_source_id
            else []
        )

        envelope = BatchEnvelope(
            target_family="elections",
            schema_version="1.0",
            source_rows=sorted(event_sources.values(), key=lambda s: s.source_id),
            observation_rows=event_obs,
            candidate_dim_rows=event_candidate_dims,
            ac_dim_rows=list(event_ac_dims.values()),
            party_dim_rows=party_dim_payload,
            party_alliance_dim_rows=party_alliance_payload,
        )
        t0 = time.time()
        try:
            wr = write_batch(envelope, datasets_root)
            dt = time.time() - t0
            # wr.observation_rows_written is the CUMULATIVE parquet size
            # after this event's UPSERT (not just this event's rows). Keep
            # only the last value to avoid double-counting in totals.
            last_obs_written = wr.observation_rows_written
            last_src_written = wr.source_rows_written
            total_obs_written += len(event_obs)
            total_src_written += len(event_sources)
            if on_event_written is not None:
                on_event_written(
                    event_id, wr.observation_rows_written,
                    wr.source_rows_written, dt,
                )
        except Exception as exc:
            log.exception("event %s write FAILED", event_id)
            for sr in result.slices:
                if sr.event_id == event_id and sr.error is None:
                    sr.error = f"event-write: {type(exc).__name__}: {exc}"

    result.states_processed = len(seen_states)
    result.unresolved_parties = dict(unresolved)
    result.write_result = WriteResult(
        family="elections",
        observations_path=datasets_root / "elections" / "observations.parquet",
        sources_path=datasets_root / "taxonomy" / "sources.parquet",
        manifest_path=datasets_root / "manifest.json",
        observation_rows_written=last_obs_written,
        source_rows_written=last_src_written,
    )

    return result


def _process_slice(
    *,
    results_dir: Path,
    state_code: str,
    period,
    party_lookup: PartyLookup,
) -> tuple[
    list[ObservationRow], dict[str, SourceRow], int, dict[str, int],
    list[CandidateDimRow], list[AcDimRow],
]:
    """Process one (event, state) slice → observations + sources + dims + AC count.

    Thin disk-wrapper around :func:`build_slice_envelope` — globs ``*.json``
    under ``results_dir``, loads each into ``ConstituencyResult`` (logging
    and skipping unreadable files), then delegates the canonical-envelope
    construction to the in-memory primary API.

    Pre-O.3b-pre this function did the whole orchestration inline. The split
    was extracted so ``pipeline/run.py`` can call the same builder against
    in-memory constituencies it just produced live, without re-reading the
    per-AC JSONs the writers used to emit. See TODO row ``1.8b-writers-b``.
    """
    ac_files = sorted(
        results_dir.glob("*.json"), key=lambda p: int(p.stem)
    )
    constituencies: list[ConstituencyResult] = []
    for ac_path in ac_files:
        try:
            constituencies.append(_load_constituency_result(ac_path))
        except Exception as exc:
            log.warning("skipping unreadable %s: %s", ac_path, exc)
            continue

    rows, sources, unresolved, candidate_dims, ac_dims = build_slice_envelope(
        constituencies=constituencies,
        state_code=state_code,
        period=period,
        party_lookup=party_lookup,
    )
    # NOTE: returned ``ac_count`` mirrors the historical contract — number of
    # *.json files on disk, NOT successfully-loaded ConstituencyResults. Skip-on-
    # read keeps the slice resilient, but the count must reflect the operator's
    # on-disk corpus so progress reporting stays honest.
    return (
        rows, sources, len(ac_files), unresolved,
        candidate_dims, ac_dims,
    )


def build_slice_envelope(
    *,
    constituencies: list[ConstituencyResult],
    state_code: str,
    period,
    party_lookup: PartyLookup,
) -> tuple[
    list[ObservationRow], dict[str, SourceRow], dict[str, int],
    list[CandidateDimRow], list[AcDimRow],
]:
    """Build the per-slice canonical rows from in-memory ConstituencyResults.

    Primary API for callers that already hold the parsed ConstituencyResult
    objects in memory (e.g. ``pipeline/run.py`` after a live ECI fetch).
    For disk-driven callers, see the thin wrapper :func:`_process_slice`.

    Inputs:
        constituencies: parsed ConstituencyResult per AC; ``cr.sources`` may
            be empty (hand-imported XLSX path uses a synthetic source URL).
            Order is preserved into the output where it matters
            (``observation_rows`` are appended in AC order).
        state_code: ECI state code (e.g. ``"S22"``).
        period: parsed period (output of ``parse_period_label(event_id)``).
        party_lookup: shared resolver from
            ``yen_gov.canonical.adapters.eci.party_lookup``.

    Returns the 5-tuple ``(observations, sources, unresolved, candidate_dims,
    ac_dims)`` — matches ``_process_slice``'s shape minus the
    ``ac_count`` (which is a property of the on-disk corpus, not of the
    in-memory data; callers compute it themselves).
    """
    rows: list[ObservationRow] = []
    sources: dict[str, SourceRow] = {}
    summaries: list[ACContestSummary] = []
    unresolved: dict[str, int] = defaultdict(int)
    candidate_dims: list[CandidateDimRow] = []
    ac_dims_by_id: dict[str, AcDimRow] = {}

    for cr in constituencies:
        source_id, source_row = _source_for_result(cr, period_label=period.period_label)
        sources.setdefault(source_id, source_row)

        proxy_lookup = _LenientPartyLookup(party_lookup, unresolved)
        ac_rows = observations_from_constituency(
            result=cr,
            period=period,
            delim_year=DEFAULT_DELIM_YEAR,
            party_lookup=proxy_lookup,
            source_id=source_id,
        )
        rows.extend(ac_rows)

        dims = dim_rows_from_constituency(
            result=cr,
            period=period,
            delim_year=DEFAULT_DELIM_YEAR,
            party_lookup=proxy_lookup,
            source_id=source_id,
        )
        candidate_dims.extend(CandidateDimRow(**d) for d in dims["candidate"])
        for d in dims["ac"]:
            ac_dims_by_id.setdefault(d["ac_id"], AcDimRow(**d))

        summaries.append(_summary_for_result(
            result=cr,
            period=period,
            source_id=source_id,
            party_lookup=proxy_lookup,
        ))

    if summaries:
        rows.extend(state_rollup_observations(summaries=summaries))

    return (
        rows, sources, dict(unresolved),
        candidate_dims, list(ac_dims_by_id.values()),
    )


def _load_constituency_result(path: Path) -> ConstituencyResult:
    doc = json.loads(path.read_text(encoding="utf-8"))
    for k in ("$schema", "$schema_version"):
        doc.pop(k, None)
    return ConstituencyResult.model_validate(doc)


class _LenientPartyLookup:
    """Wraps PartyLookup; unknowns fall back to parties.IN.UNK and are counted."""

    def __init__(self, inner: PartyLookup, miss_counter: dict[str, int]):
        self._inner = inner
        self._misses = miss_counter

    def resolve(self, **kwargs) -> str:
        try:
            return self._inner.resolve(**kwargs)
        except UnknownPartyError:
            short = kwargs.get("party_short") or kwargs.get("party_full") or "<empty>"
            self._misses[short] += 1
            return "parties.IN.UNK"


def _source_for_result(cr: ConstituencyResult, *, period_label: str) -> tuple[str, SourceRow]:
    """Pick the first source on the per-AC JSON as the contest-scoping source.

    Per canonical-store.md §11.4: each AC contest is scoped by one source.
    The legacy emit path put Section 10 first, partywise second — keeping
    that order means the contest-scoping source is always the Section-10
    XLSX URL, which is what we want for AC-level provenance.
    """
    if not cr.sources:
        # Hand-imported XLSX path (cli.py eci-statreport-emit-local) writes
        # sources=[] per ADR-0002. Synthesise a stable source_id from the
        # event+state so re-runs are deterministic and rows still FK-link.
        synthetic_url = f"local://{cr.election}/{cr.state}/eci-section-10"
        source_id = _source_id_for_url(synthetic_url)
        ts = "2026-05-13T00:00:00Z"
        return source_id, SourceRow(
            source_id=source_id,
            url=synthetic_url,
            content_hash="",
            producer="Election Commission of India",
            citation_full=f"ECI Section 10 (Detailed Results), {cr.election} {cr.state} — hand-imported",
            url_main=synthetic_url,
            url_download=synthetic_url,
            date_accessed=ts[:10],
            first_fetched_at=ts,
            last_seen_at=ts,
            license="OGL-IN-1.0",
            vintage=cr.election,
            confidence_tier="silver",
            is_issuing_authority=True,
        )

    first = cr.sources[0]
    url = first.url
    fetched_at = first.fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    source_id = _source_id_for_url(url)
    return source_id, SourceRow(
        source_id=source_id,
        url=url,
        content_hash="",
        producer="Election Commission of India",
        citation_full=f"ECI Section 10 (Detailed Results), {cr.election} {cr.state}",
        url_main=url,
        url_download=url,
        date_accessed=first.fetched_at.strftime("%Y-%m-%d"),
        first_fetched_at=fetched_at,
        last_seen_at=fetched_at,
        license="OGL-IN-1.0",
        vintage=cr.election,
        confidence_tier="gold",
        is_issuing_authority=True,
    )


def _source_id_for_url(url: str) -> str:
    return "src-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def _summary_for_result(
    *,
    result: ConstituencyResult,
    period,
    source_id: str,
    party_lookup,
) -> ACContestSummary:
    votes_by_party: dict[str, int] = defaultdict(int)
    forfeitures_by_party: dict[str, int] = defaultdict(int)
    on_ballot: set[str] = set()
    for cand in result.candidates:
        is_ind = cand.party_short.strip().lower() in {"ind", "independent"}
        pid = party_lookup.resolve(
            party_short=cand.party_short,
            eci_code=str(cand.party_eci_code) if cand.party_eci_code else None,
            is_independent=is_ind,
        )
        votes_by_party[pid] += cand.votes
        on_ballot.add(pid)
        if cand.vote_share_pct < FORFEITURE_THRESHOLD_PCT:
            forfeitures_by_party[pid] += 1

    winner_pid = party_lookup.resolve(
        party_short=result.winner.party_short,
        eci_code=str(result.winner.party_eci_code) if result.winner.party_eci_code else None,
        is_independent=result.winner.party_short.strip().lower() in {"ind", "independent"},
    )

    return ACContestSummary(
        state_code=result.state,
        eci_no=result.eci_no,
        delim_year=DEFAULT_DELIM_YEAR,
        period=period,
        total_electors=result.totals.electors,
        votes_polled=result.totals.votes_polled,
        nota_votes=result.nota.votes,
        winner_party_id=winner_pid,
        source_id=source_id,
        votes_by_party=dict(votes_by_party),
        party_was_on_ballot=on_ballot,
        forfeitures_by_party=dict(forfeitures_by_party),
    )
