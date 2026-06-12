"""ECI Parliament (PC) constituency-wise results adapter / driver.

Reads the frozen ECI Report-33 constituency-wise detailed-result CSV plus the
Report-34 AC→PC crosswalk and emits canonical PC-grain Parquet rows through
the shared BatchEnvelope writer.

The PC rows share the existing ``datasets/elections/state=<key>/`` fact family
(no ``grain=`` partition); the writer routes ``IN-PC-...`` entity_ids to the
matching ``in_<state>`` shard alongside the AC rows. ``dim_pcs.parquet`` is the
PC-grain dimension sibling of ``dim_acs.parquet``.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from yen_gov.canonical.adapters.eci.identity import Period
from yen_gov.canonical.adapters.eci.rollups import (
    PCContestSummary,
    parliament_rollup_observations,
)
from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.party_resolver import (
    PartyLookup,
    UnknownPartyError,
    load_party_lookup,
    party_alliance_dim_rows,
    party_dim_rows,
)
from yen_gov.canonical.adapters.eci.pc_observations import (
    dim_rows_from_pc,
    observations_from_pc,
    persons_and_candidacies_from_pc,
)
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.envelope import (
    BatchEnvelope,
    CandidacyRow,
    ObservationRow,
    PartyAllianceDimRow,
    PartyDimRow,
    PcDimRow,
    PersonDimRow,
    SourceRow,
)
from yen_gov.canonical.writer import WriteResult, write_batch
from yen_gov.sources.eci.ls_constituencywise import (
    PcCandidateRaw,
    PcResultRaw,
    parse_ls_constituencywise,
)
from yen_gov.sources.eci.ls_ge_tcpd import parse_ls_ge_tcpd
from yen_gov.canonical.adapters.eci.pc_crosswalk import load_crosswalk_and_lookup

# ECI Section 158 RPA deposit-forfeiture cutoff (1/6 of valid votes) — same
# threshold used by the AC pipeline at ``canonical_eci_backfill`` and
# ``eci_ae_panel``.
FORFEITURE_THRESHOLD_PCT = 16.67

_INDEPENDENT_ALIASES_FOR_SUMMARY = {"independent", "ind", "ind.", "independents"}

# The 2024 Parliament general election: results declared 2024-06-04. The
# event_id MUST be parseable by ``parse_period_label`` (body+month+year), so
# the polling-month-style ``LsGenJun2024`` is the canonical id.
LS_2024_EVENT = Period(period_label="LsGenJun2024", year=2024, period_seq=6)
# Current Parliament boundaries are the 2008 delimitation.
LS_2024_DELIM_YEAR = 2008
SOURCE_INPUT_ID = "eci_ls"
INVENTORY_PATH_REL = ("datasets", "elections", "_inventory.json")


@dataclass(frozen=True)
class PcGeEvent:
    """Per-election parameters for the PC-grain ingest driver.

    Factored out of the hardcoded 2024 constants so the same driver can ingest
    earlier general elections (EGC-B2 Phase 2). The driver functions default to
    :data:`LS_2024`, keeping the 2024 path byte-identical; later elections pass
    their own instance with the matching ``delim_year`` (see
    ``canonical/adapters/eci/pc_crosswalk.py`` for the year->delim mapping).
    """

    period: Period
    delim_year: int
    source_title: str
    vintage: str
    source_input_id: str = SOURCE_INPUT_ID


# Default event: the already-ingested 2024 Parliament general election.
LS_2024 = PcGeEvent(
    period=LS_2024_EVENT,
    delim_year=LS_2024_DELIM_YEAR,
    source_title=(
        "General Election to Lok Sabha 2024 — Constituency Wise Detailed "
        "Result (Report 33)"
    ),
    vintage="2024",
)


# The 2019 Parliament general election: results declared 2019-05-23. Ingested
# from the TCPD All-States GE panel (EGC-B2 Phase 2). Same 2008 delimitation
# as 2024, so the constituency boundaries (and therefore ``pc_id`` grammar)
# match the current map.
LS_2019_EVENT = Period(period_label="LsGenMay2019", year=2019, period_seq=5)
LS_2019 = PcGeEvent(
    period=LS_2019_EVENT,
    delim_year=2008,
    source_title=(
        "General Election to Lok Sabha 2019 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="2019",
    source_input_id="tcpd_ge",
)


# The 2014 Parliament general election: results declared 2014-05-16. Same 2008
# delimitation as 2019/2024. Andhra Pradesh still contested as the undivided
# 42-seat state (Telangana split takes effect 2014-06-02, after polling), so
# the crosswalk maps the 2014 AP rows onto the modern S01/S29 successors.
LS_2014_EVENT = Period(period_label="LsGenMay2014", year=2014, period_seq=4)
LS_2014 = PcGeEvent(
    period=LS_2014_EVENT,
    delim_year=2008,
    source_title=(
        "General Election to Lok Sabha 2014 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="2014",
    source_input_id="tcpd_ge",
)


# The 2009 Parliament general election: results declared 2009-05-16. First GE
# fought on the 2008 delimitation, so the constituency boundaries match the
# current map. Andhra Pradesh contested as the undivided 42-seat state.
LS_2009_EVENT = Period(period_label="LsGenMay2009", year=2009, period_seq=3)
LS_2009 = PcGeEvent(
    period=LS_2009_EVENT,
    delim_year=2008,
    source_title=(
        "General Election to Lok Sabha 2009 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="2009",
    source_input_id="tcpd_ge",
)


# The 2004 Parliament general election (14th Parliament): polling Apr-May 2004,
# results declared 2004-05-13. Contested on the **1976 delimitation** — the
# constituency boundaries differ from the current (2008) map, so 2004 is a
# table/timeseries-only year (no choropleth painting). Chhattisgarh, Jharkhand
# and Uttarakhand are now distinct states and their seats resolve as-was; the
# undivided Andhra Pradesh contested its 42 seats. No override rows are needed
# beyond the standing DNH/DD merge — the automatic resolver covers all 543.
LS_2004_EVENT = Period(period_label="LsGenMay2004", year=2004, period_seq=2)
LS_2004 = PcGeEvent(
    period=LS_2004_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 2004 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="2004",
    source_input_id="tcpd_ge",
)


# The 1999 Parliament general election (13th Parliament): polling Sep-Oct 1999,
# results declared 1999-10-06. Contested on the **1976 delimitation** (table/
# timeseries-only year). Chhattisgarh, Jharkhand and Uttarakhand did not yet
# exist (created 2000); their seats were polled inside Madhya Pradesh, Bihar
# and Uttar Pradesh respectively and are coded as-was. The automatic resolver
# covers all 543 constituencies (only the DNH/DD merge uses override rows).
LS_1999_EVENT = Period(period_label="LsGenOct1999", year=1999, period_seq=1)
LS_1999 = PcGeEvent(
    period=LS_1999_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 1999 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1999",
    source_input_id="tcpd_ge",
)


#: GE-year -> event registry. The 2024 row is the ECI Report-33 path (kept for
#: completeness); historical years (1999-2019) are the TCPD-panel path. Phase 2
#: of EGC-B2 extends this as each year's PR lands.
EVENT_BY_GE_YEAR: dict[int, PcGeEvent] = {
    1999: LS_1999,
    2004: LS_2004,
    2009: LS_2009,
    2014: LS_2014,
    2019: LS_2019,
    2024: LS_2024,
}


@dataclass(frozen=True)
class LsIngestResult:
    write_result: WriteResult | None
    event_id: str
    pc_count: int
    inventory_path: Path
    unresolved_parties: dict[str, int]
    skipped: bool = False


class _LenientPartyLookup:
    """Maps unresolved long-tail parties to the canonical sentinel.

    Mirrors the panel adapter's lenient wrapper so a single unknown party
    string does not halt a 542-PC backfill.
    """

    def __init__(self, inner: PartyLookup, miss_counter: Counter[str]):
        self._inner = inner
        self._misses = miss_counter

    def resolve(self, **kwargs) -> str:
        try:
            return self._inner.resolve(**kwargs)
        except UnknownPartyError:
            short = kwargs.get("party_short") or kwargs.get("party_full") or "<empty>"
            self._misses[str(short)] += 1
            return "parties.IN.UNK"


def _is_independent_for_summary(party_name: str) -> bool:
    return party_name.strip().lower() in _INDEPENDENT_ALIASES_FOR_SUMMARY


def _summary_for_pc_result(
    *,
    result: PcResultRaw,
    period: Period,
    delim_year: int,
    party_lookup: PartyLookup,
    source_id: str,
) -> PCContestSummary:
    """Build a per-PC :class:`PCContestSummary` from one ``PcResultRaw``.

    Mirror of :func:`canonical_eci_backfill._summary_for_result` for the PC
    grain. NOTA is excluded from ``votes_by_party`` / ``party_was_on_ballot``
    (it is a ballot option, not a party). Forfeiture threshold matches the
    AC pipeline (16.67% of valid votes = the 1/6 RPA Section 158 cutoff).
    """
    non_nota = [c for c in result.candidates if not c.is_nota]
    nota_votes = sum(c.total_votes for c in result.candidates if c.is_nota)
    valid = float(result.valid_votes) if result.valid_votes else None

    votes_by_party: dict[str, int] = defaultdict(int)
    on_ballot: set[str] = set()
    forfeitures_by_party: dict[str, int] = defaultdict(int)
    for cand in non_nota:
        pid = party_lookup.resolve(
            party_full=cand.party_name,
            is_independent=_is_independent_for_summary(cand.party_name),
        )
        votes_by_party[pid] += cand.total_votes
        on_ballot.add(pid)
        if valid is not None and valid > 0:
            share_pct = float(cand.total_votes) / valid * 100.0
            if share_pct < FORFEITURE_THRESHOLD_PCT:
                forfeitures_by_party[pid] += 1

    # Winner = highest non-NOTA vote count (deterministic tie-break on name
    # to match ``_ranked_non_nota`` in pc_observations.py).
    ranked = sorted(non_nota, key=lambda c: (-c.total_votes, c.name))
    winner = ranked[0]
    winner_pid = party_lookup.resolve(
        party_full=winner.party_name,
        is_independent=_is_independent_for_summary(winner.party_name),
    )

    return PCContestSummary(
        state_code=result.state_code,
        eci_no=result.pc_no,
        delim_year=delim_year,
        period=period,
        total_electors=result.total_electors,
        votes_polled=result.total_votes_polled,
        nota_votes=nota_votes,
        winner_party_id=winner_pid,
        source_id=source_id,
        votes_by_party=dict(votes_by_party),
        party_was_on_ballot=on_ballot,
        forfeitures_by_party=dict(forfeitures_by_party),
    )


def pc_source_row(event: PcGeEvent = LS_2024) -> SourceRow:
    title = event.source_title
    source_id = derive_source_id(
        "Election Commission of India", title, event.vintage
    )
    return SourceRow(
        source_id=source_id,
        producer="Election Commission of India",
        title=title,
        vintage=event.vintage,
        license="OGL-IN-1.0",
        confidence_tier="gold",
        is_issuing_authority=True,
        verification_method="transcribed",
        url_main=None,
        citation_full=None,
        notes=None,
    )


def build_pc_envelope(
    *,
    datasets_root: Path,
    csv_path: Path,
    crosswalk_path: Path,
    allow_unknown_parties: bool = False,
    event: PcGeEvent = LS_2024,
) -> tuple[BatchEnvelope, int, dict[str, int]]:
    """Parse the ECI Report-33 + Report-34 CSVs into a BatchEnvelope.

    Returns ``(envelope, pc_count, unresolved_parties)``.
    """
    results = parse_ls_constituencywise(
        csv_path,
        crosswalk_path=crosswalk_path,
        datasets_root=datasets_root,
    )
    return _envelope_from_results(
        results,
        datasets_root=datasets_root,
        event=event,
        allow_unknown_parties=allow_unknown_parties,
    )


def build_pc_envelope_from_tcpd(
    *,
    datasets_root: Path,
    csv_path: Path,
    year: int,
    event: PcGeEvent,
    allow_unknown_parties: bool = False,
) -> tuple[BatchEnvelope, int, dict[str, int]]:
    """Parse one GE year from the TCPD All-States panel into a BatchEnvelope.

    The TCPD historical path (1999-2019); shares the envelope builder with the
    ECI Report-33 path so both produce byte-compatible canonical rows. Returns
    ``(envelope, pc_count, unresolved_parties)``.
    """
    crosswalk, state_lookup = load_crosswalk_and_lookup(datasets_root)
    results = parse_ls_ge_tcpd(
        csv_path,
        year=year,
        crosswalk=crosswalk,
        state_lookup=state_lookup,
    )
    return _envelope_from_results(
        results,
        datasets_root=datasets_root,
        event=event,
        allow_unknown_parties=allow_unknown_parties,
    )


def _envelope_from_results(
    results,
    *,
    datasets_root: Path,
    event: PcGeEvent,
    allow_unknown_parties: bool = False,
) -> tuple[BatchEnvelope, int, dict[str, int]]:
    """Build a canonical PC ``BatchEnvelope`` from parsed ``PcResultRaw`` rows.

    Source-agnostic: the ECI Report-33 (2024) and TCPD panel (historical)
    parsers both feed this, so the canonical rows are identical regardless of
    which upstream produced a given year.
    """
    unresolved: Counter[str] = Counter()
    base_lookup = load_party_lookup(datasets_root)
    lookup = (
        _LenientPartyLookup(base_lookup, unresolved)
        if allow_unknown_parties
        else base_lookup
    )
    source_row = pc_source_row(event)

    observations: list[ObservationRow] = []
    pc_dims: list[PcDimRow] = []
    person_payloads: dict[str, dict] = {}
    candidacy_payloads: list[dict] = []
    summaries: list[PCContestSummary] = []
    for result in results:
        observations.extend(observations_from_pc(
            result=result,
            period=event.period,
            delim_year=event.delim_year,
            party_lookup=lookup,
            source_id=source_row.source_id,
        ))
        pc_dims.extend(
            PcDimRow(**row)
            for row in dim_rows_from_pc(
                result=result,
                delim_year=event.delim_year,
                source_id=source_row.source_id,
            )
        )
        persons, candidacies = persons_and_candidacies_from_pc(
            result=result,
            period=event.period,
            delim_year=event.delim_year,
            party_lookup=lookup,
            source_id=source_row.source_id,
        )
        for p in persons:
            person_payloads[p["person_id"]] = p
        candidacy_payloads.extend(candidacies)
        summaries.append(_summary_for_pc_result(
            result=result,
            period=event.period,
            delim_year=event.delim_year,
            party_lookup=lookup,
            source_id=source_row.source_id,
        ))

    # PR-B parliament-rollup hook (2026-06-13): emit per-(state, party, period)
    # aggregate rows mirroring AC's state_rollup_observations call-site in
    # ``eci_ae_panel`` + ``canonical_eci_backfill``. State-scoped per Hans's
    # locked design verdict — entity_id is ``IN-<STATECODE>-LsGenMay2024-PARTY-BJP``,
    # frontend SUMs across states in SQL. Closes ``ls_history.vote_share_pct ==
    # null`` honest-degradation per ``docs/archive/plans/20260612-party-rendering-
    # and-party-pages-plan.md`` PR-4 closure-ledger known-degradation #1.
    by_state: dict[str, list[PCContestSummary]] = defaultdict(list)
    for s in summaries:
        by_state[s.state_code].append(s)
    for state_summaries in by_state.values():
        observations.extend(parliament_rollup_observations(summaries=state_summaries))

    envelope = BatchEnvelope(
        target_family="elections",
        schema_version="1.0",
        source_rows=[source_row],
        observation_rows=observations,
        pc_dim_rows=pc_dims,
        person_dim_rows=[PersonDimRow(**p) for p in person_payloads.values()],
        candidacy_rows=[CandidacyRow(**c) for c in candidacy_payloads],
        party_dim_rows=[
            PartyDimRow(**r)
            for r in party_dim_rows(base_lookup, source_id=source_row.source_id)
        ],
        party_alliance_dim_rows=[
            PartyAllianceDimRow(**r)
            for r in party_alliance_dim_rows(base_lookup, source_id=source_row.source_id)
        ],
    )
    return envelope, len(results), dict(sorted(unresolved.items()))


def ingest_ls(
    *,
    repo_root: Path,
    csv_path: Path,
    crosswalk_path: Path,
    force: bool = False,
    ingested_at: str = "2026-05-31",
    allow_unknown_parties: bool = False,
    event: PcGeEvent = LS_2024,
) -> LsIngestResult:
    datasets_root = repo_root / "datasets"
    inventory_path = repo_root.joinpath(*INVENTORY_PATH_REL)
    if not force and _inventory_has_event(repo_root, event=event):
        return LsIngestResult(
            write_result=None,
            event_id=event.period.period_label,
            pc_count=0,
            inventory_path=inventory_path,
            unresolved_parties={},
            skipped=True,
        )
    envelope, pc_count, unresolved = build_pc_envelope(
        datasets_root=datasets_root,
        csv_path=csv_path,
        crosswalk_path=crosswalk_path,
        allow_unknown_parties=allow_unknown_parties,
        event=event,
    )
    write_result = write_batch(envelope, datasets_root)
    states = sorted({row.state_code for row in envelope.pc_dim_rows})
    inventory_path = _upsert_inventory(
        repo_root=repo_root,
        states=states,
        ingested_at=ingested_at,
        event=event,
    )
    return LsIngestResult(
        write_result=write_result,
        event_id=event.period.period_label,
        pc_count=pc_count,
        inventory_path=inventory_path,
        unresolved_parties=unresolved,
    )


def ingest_ls_tcpd(
    *,
    repo_root: Path,
    csv_path: Path,
    year: int,
    event: PcGeEvent,
    force: bool = False,
    ingested_at: str = "2026-05-31",
    allow_unknown_parties: bool = False,
) -> LsIngestResult:
    """Ingest one historical GE year from the TCPD All-States panel.

    Mirrors :func:`ingest_ls` (the ECI Report-33 path) but parses the TCPD
    panel and resolves constituencies through the historical crosswalk. The
    inventory dedup keys on ``(election_id, source_input)``, so the TCPD years
    coexist with the ECI 2024 slice.
    """
    datasets_root = repo_root / "datasets"
    inventory_path = repo_root.joinpath(*INVENTORY_PATH_REL)
    if not force and _inventory_has_event(repo_root, event=event):
        return LsIngestResult(
            write_result=None,
            event_id=event.period.period_label,
            pc_count=0,
            inventory_path=inventory_path,
            unresolved_parties={},
            skipped=True,
        )
    envelope, pc_count, unresolved = build_pc_envelope_from_tcpd(
        datasets_root=datasets_root,
        csv_path=csv_path,
        year=year,
        event=event,
        allow_unknown_parties=allow_unknown_parties,
    )
    write_result = write_batch(envelope, datasets_root)
    states = sorted({row.state_code for row in envelope.pc_dim_rows})
    inventory_path = _upsert_inventory(
        repo_root=repo_root,
        states=states,
        ingested_at=ingested_at,
        event=event,
    )
    return LsIngestResult(
        write_result=write_result,
        event_id=event.period.period_label,
        pc_count=pc_count,
        inventory_path=inventory_path,
        unresolved_parties=unresolved,
    )


def _inventory_has_event(repo_root: Path, *, event: PcGeEvent = LS_2024) -> bool:
    path = repo_root.joinpath(*INVENTORY_PATH_REL)
    if not path.is_file():
        return False
    existing = json.loads(path.read_text(encoding="utf-8")).get("ingested") or []
    return any(
        row.get("election_id") == event.period.period_label
        and row.get("source_input") == event.source_input_id
        for row in existing
    )


def _upsert_inventory(
    *,
    repo_root: Path,
    states: list[str],
    ingested_at: str,
    event: PcGeEvent = LS_2024,
) -> Path:
    path = repo_root.joinpath(*INVENTORY_PATH_REL)
    payload: dict = {"ingested": []}
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("ingested", [])
    filtered = [
        row for row in payload["ingested"]
        if not (
            row.get("election_id") == event.period.period_label
            and row.get("source_input") == event.source_input_id
        )
    ]
    # National Parliament event recorded as one inventory slice per state.
    # Schema v2.0 (ADR-0050): state field carries LGD-name slug, not ECI st_code.
    # Callers pass ECI st_code (relational join-key); translate at the write boundary.
    for state in states:
        filtered.append({
            "election_id": event.period.period_label,
            "state": eci_to_lgd_slug(state),
            "source_input": event.source_input_id,
            "ingested_at": ingested_at,
        })
    payload["ingested"] = filtered
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
