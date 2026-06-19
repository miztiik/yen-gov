"""ECI Parliament (PC) constituency-wise results adapter / driver.

Reads the frozen ECI Report-33 constituency-wise detailed-result CSV plus the
Report-34 AC->PC crosswalk and emits canonical PC-grain observation rows to the
per-state long-format CSV
``datasets/data/datapoints/electoral/<state_slug>_election_results.csv`` via
``canonical.adapters.eci.electoral_csv.write_electoral_results`` (ingest
rip-replace Row 8; the legacy envelope -> parquet write path retired). Each PC
row's ``IN-PC-...`` entity_id routes to its state's file alongside that state's
AC rows; the UPSERT preserves pre-existing rows. Source citations append to
``datasets/data/entities/source.csv``.
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
from yen_gov.canonical.adapters.eci.electoral_csv import (
    ElectoralBatch,
    upsert_source_csv,
    write_electoral_results,
)
from yen_gov.canonical.envelope import (
    CandidacyRow,
    ObservationRow,
    PartyAllianceDimRow,
    PartyDimRow,
    PcDimRow,
    PersonDimRow,
    SourceRow,
)
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


# Pre-1999 LS GE backbone (PR-3 of TODO/20260613-party-deferred-followups-plan.md).
#
# Adds 10 historical Parliament general elections (1962-1998) to the event
# registry so future ingest runs can iterate the complete LS GE list. This PR
# is backbone only: it lands the constants + delimitation crosswalk; the
# actual TCPD ingest follows in PR-8 of the same plan.
#
# Polling-month convention: each ``period_label`` carries the FIRST polling
# month per Wikipedia LS GE entries cross-referenced against TCPD's lowercase
# ``month`` column in ``datasets/ephemeral/All_States_GE.csv``. Two named
# overrides on first-polling-month per plan-doc PR-3 brief:
#   - 1991 = Jun (NOT May): polling was split by Rajiv Gandhi's assassination
#     (20 May polling + Jun 12 + Jun 15 phases), with results declared 19 Jun
#     1991; Jun is the canonical month for the cycle.
#   - 1998 = Feb (NOT Mar despite TCPD month='3'): first polling was 16 Feb
#     1998; results 10 Mar. Feb is the citizen-recognised polling-month.
#
# ``period_seq`` follows the documented identity.py convention (month number
# 1..12 from ``parse_period_label._MONTH_NUM``). This is a deliberate split
# from the existing 6 LS_<YEAR>_EVENT constants above (which use sequential
# rank 1..6 for historical reasons); changing the existing 6 would invalidate
# already-emitted ``observation_id`` hashes.

# 1998 (12th Parliament): polling Feb 16 - Mar 7 1998 (first poll Feb 16),
# results declared 1998-03-02. **1976 delimitation** (DelimID 3 in TCPD).
# Chhattisgarh/Jharkhand/Uttarakhand did not yet exist.
LS_1998_EVENT = Period(period_label="LsGenFeb1998", year=1998, period_seq=2)
LS_1998 = PcGeEvent(
    period=LS_1998_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 1998 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1998",
    source_input_id="tcpd_ge",
)


# 1996 (11th Parliament): polling Apr 27 - May 7 1996 (first poll Apr 27),
# results declared 1996-05-15. **1976 delimitation** (DelimID 3 in TCPD).
LS_1996_EVENT = Period(period_label="LsGenMay1996", year=1996, period_seq=5)
LS_1996 = PcGeEvent(
    period=LS_1996_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 1996 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1996",
    source_input_id="tcpd_ge",
)


# 1991 (10th Parliament): polling phase 1 May 20 1991, then (after Rajiv
# Gandhi assassination 21 May) phase 2 Jun 12 + phase 3 Jun 15, results
# declared 1991-06-19. **1976 delimitation** (DelimID 3 in TCPD). Jun (NOT
# May) is the citizen-recognised cycle month per the assassination-split
# convention.
LS_1991_EVENT = Period(period_label="LsGenJun1991", year=1991, period_seq=6)
LS_1991 = PcGeEvent(
    period=LS_1991_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 1991 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1991",
    source_input_id="tcpd_ge",
)


# 1989 (9th Parliament): polling Nov 22-26 1989, results declared 1989-11-29.
# **1976 delimitation** (DelimID 3 in TCPD).
LS_1989_EVENT = Period(period_label="LsGenNov1989", year=1989, period_seq=11)
LS_1989 = PcGeEvent(
    period=LS_1989_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 1989 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1989",
    source_input_id="tcpd_ge",
)


# 1984 (8th Parliament): polling Dec 24-28 1984 (most polling within Dec;
# few stragglers slipped into early Jan 1985), results declared 1984-12-31.
# **1976 delimitation** (DelimID 3 in TCPD).
LS_1984_EVENT = Period(period_label="LsGenDec1984", year=1984, period_seq=12)
LS_1984 = PcGeEvent(
    period=LS_1984_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 1984 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1984",
    source_input_id="tcpd_ge",
)


# 1980 (7th Parliament): polling Jan 3-6 1980, results declared 1980-01-07.
# **1976 delimitation** (DelimID 3 in TCPD).
LS_1980_EVENT = Period(period_label="LsGenJan1980", year=1980, period_seq=1)
LS_1980 = PcGeEvent(
    period=LS_1980_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 1980 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1980",
    source_input_id="tcpd_ge",
)


# 1977 (6th Parliament): polling Mar 16-20 1977, results declared 1977-03-22.
# **1976 delimitation** (DelimID 3 in TCPD). First general election held
# after the 1976 delimitation order; the 1976 boundaries governed nine
# consecutive general elections (1977 through 2004).
LS_1977_EVENT = Period(period_label="LsGenMar1977", year=1977, period_seq=3)
LS_1977 = PcGeEvent(
    period=LS_1977_EVENT,
    delim_year=1976,
    source_title=(
        "General Election to Lok Sabha 1977 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1977",
    source_input_id="tcpd_ge",
)


# 1971 (5th Parliament): polling Mar 1-10 1971, results declared 1971-03-11.
# **1967 delimitation** (DelimID 2 in TCPD), shared with 1967.
LS_1971_EVENT = Period(period_label="LsGenMar1971", year=1971, period_seq=3)
LS_1971 = PcGeEvent(
    period=LS_1971_EVENT,
    delim_year=1967,
    source_title=(
        "General Election to Lok Sabha 1971 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1971",
    source_input_id="tcpd_ge",
)


# 1967 (4th Parliament): polling Feb 17-21 1967, results declared 1967-02-28.
# **1967 delimitation** (DelimID 2 in TCPD). Distinct cohort from 1962 — the
# 1967 boundaries reflect the post-1956 States Reorganisation territorial
# rearrangement that did not yet apply to the 1962 cycle.
LS_1967_EVENT = Period(period_label="LsGenFeb1967", year=1967, period_seq=2)
LS_1967 = PcGeEvent(
    period=LS_1967_EVENT,
    delim_year=1967,
    source_title=(
        "General Election to Lok Sabha 1967 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1967",
    source_input_id="tcpd_ge",
)


# 1962 (3rd Parliament): polling Feb 19-25 1962, results declared 1962-02-25.
# Its own delimitation cohort (DelimID 1 in TCPD, pre-1967 reorganisation).
# TCPD month='2' confirms Feb (the brief proposal's ``LsGenJan1962`` was a
# typo; the brief's own polling-month convention parenthetical agrees on Feb).
LS_1962_EVENT = Period(period_label="LsGenFeb1962", year=1962, period_seq=2)
LS_1962 = PcGeEvent(
    period=LS_1962_EVENT,
    delim_year=1962,
    source_title=(
        "General Election to Lok Sabha 1962 — Constituency-wise candidate "
        "results (TCPD compilation of ECI returns)"
    ),
    vintage="1962",
    source_input_id="tcpd_ge",
)


#: GE-year -> event registry. The 2024 row is the ECI Report-33 path (kept for
#: completeness); 1962-2019 are the TCPD-panel path. The pre-1999 cohort
#: (1962-1998) is backbone only — added in PR-3 of
#: TODO/20260613-party-deferred-followups-plan.md so future ingest runs can
#: iterate the full 16-event list; actual ingest follows in PR-8.
EVENT_BY_GE_YEAR: dict[int, PcGeEvent] = {
    1962: LS_1962,
    1967: LS_1967,
    1971: LS_1971,
    1977: LS_1977,
    1980: LS_1980,
    1984: LS_1984,
    1989: LS_1989,
    1991: LS_1991,
    1996: LS_1996,
    1998: LS_1998,
    1999: LS_1999,
    2004: LS_2004,
    2009: LS_2009,
    2014: LS_2014,
    2019: LS_2019,
    2024: LS_2024,
}


@dataclass(frozen=True)
class LsIngestResult:
    observation_rows_written: int
    csv_paths: tuple[Path, ...]
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
) -> tuple[ElectoralBatch, int, dict[str, int]]:
    """Parse the ECI Report-33 + Report-34 CSVs into an ElectoralBatch.

    Returns ``(batch, pc_count, unresolved_parties)``.
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
) -> tuple[ElectoralBatch, int, dict[str, int]]:
    """Parse one GE year from the TCPD All-States panel into an ElectoralBatch.

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
) -> tuple[ElectoralBatch, int, dict[str, int]]:
    """Build a canonical PC ``ElectoralBatch`` from parsed ``PcResultRaw`` rows.

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

    batch = ElectoralBatch(
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
    return batch, len(results), dict(sorted(unresolved.items()))


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
            observation_rows_written=0,
            csv_paths=(),
            event_id=event.period.period_label,
            pc_count=0,
            inventory_path=inventory_path,
            unresolved_parties={},
            skipped=True,
        )
    batch, pc_count, unresolved = build_pc_envelope(
        datasets_root=datasets_root,
        csv_path=csv_path,
        crosswalk_path=crosswalk_path,
        allow_unknown_parties=allow_unknown_parties,
        event=event,
    )
    csv_paths = write_electoral_results(
        datasets_root=datasets_root, observation_rows=batch.observation_rows
    )
    upsert_source_csv(datasets_root=datasets_root, source_rows=batch.source_rows)
    states = sorted({row.state_code for row in batch.pc_dim_rows})
    inventory_path = _upsert_inventory(
        repo_root=repo_root,
        states=states,
        ingested_at=ingested_at,
        event=event,
    )
    return LsIngestResult(
        observation_rows_written=len(batch.observation_rows),
        csv_paths=tuple(csv_paths.values()),
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
            observation_rows_written=0,
            csv_paths=(),
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
    csv_paths = write_electoral_results(
        datasets_root=datasets_root, observation_rows=envelope.observation_rows
    )
    upsert_source_csv(datasets_root=datasets_root, source_rows=envelope.source_rows)
    states = sorted({row.state_code for row in envelope.pc_dim_rows})
    inventory_path = _upsert_inventory(
        repo_root=repo_root,
        states=states,
        ingested_at=ingested_at,
        event=event,
    )
    return LsIngestResult(
        observation_rows_written=len(envelope.observation_rows),
        csv_paths=tuple(csv_paths.values()),
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
