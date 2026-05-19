"""Election data coverage report.

Derives a single-source-of-truth inventory of which (event, state) slices have
been ingested by reconciling two surfaces:

1. The declared catalogue at ``datasets/reference/in/election-events.json``
   (every (state, event) the project intends to cover, with a ``data_status``
   of ``complete`` / ``partial`` / ``pending_upstream``).
2. The on-disk artifacts under ``datasets/elections/<event>/<state>/`` that
   the pipeline actually emitted.

The output is a Markdown inventory rendered to stdout and (optionally) written
to ``docs/reference/data-inventory.md`` so it can be linked from the README
without becoming a hand-maintained list. Run ``python -m yen_gov coverage``
after every ingest; the file is the contract, the catalogue is the spec, and
any divergence between them surfaces in the "Inconsistencies" section.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

CATALOGUE_REL = "datasets/reference/in/election-events.json"
STATES_REL = "datasets/reference/in/states.json"
ELECTIONS_REL = "datasets/elections"
ELECTION_RESULTS_PARQUET_REL = "datasets/elections/election_results.parquet"
INDICATORS_REL = "datasets/indicators/in"
TOPIC_CATALOGUE_REL = "datasets/reference/in/topic-catalogue.json"
INVENTORY_REL = "docs/reference/data-inventory.md"

# Temporal Richness meter: 7 cells x 3 fiscal years, FY06 -> FY26.
# Indian FY starts in April; FY 2007-08 begins April 2007 (so the JSON
# string "2007-04" denotes FY07 in our indicator coverage strings).
# Choice rationale lives in docs/architecture/backend/coverage.md.
BUCKET_EDGES: tuple[tuple[date, date], ...] = (
    (date(2006, 4, 1), date(2009, 3, 31)),  # FY06-FY08
    (date(2009, 4, 1), date(2012, 3, 31)),  # FY09-FY11
    (date(2012, 4, 1), date(2015, 3, 31)),  # FY12-FY14
    (date(2015, 4, 1), date(2018, 3, 31)),  # FY15-FY17
    (date(2018, 4, 1), date(2021, 3, 31)),  # FY18-FY20
    (date(2021, 4, 1), date(2024, 3, 31)),  # FY21-FY23
    (date(2024, 4, 1), date(2027, 3, 31)),  # FY24-FY26
)
BUCKET_LABELS: tuple[str, ...] = (
    "FY06\u2013FY08",
    "FY09\u2013FY11",
    "FY12\u2013FY14",
    "FY15\u2013FY17",
    "FY18\u2013FY20",
    "FY21\u2013FY23",
    "FY24\u2013FY26",
)
N_BUCKETS = len(BUCKET_EDGES)

# Constitutional fact: among UTs only Delhi (U05), Puducherry (U07) and J&K
# (U08) have legislative assemblies. The other five (Andaman, Chandigarh,
# Dadra & NH and Daman & Diu, Lakshadweep, Ladakh) elect MPs to Lok Sabha
# only — there is no AC slice to ingest. All 28 states have assemblies.
UT_CODES_WITH_ASSEMBLY = frozenset({"U05", "U07", "U08"})


@dataclass(frozen=True)
class SliceCoverage:
    """A single (event, state) slice — declared, on disk, or both."""

    event_id: str
    state_code: str
    state_name: str | None  # from states.json; None if state code is unknown
    display: str | None  # citizen-facing label from the catalogue
    polled_on: str | None
    declared_status: str | None  # complete | partial | pending_upstream | None (undeclared)
    on_disk: bool
    ac_count: int  # number of per-AC result files actually present
    has_summary: bool
    has_parties: bool


@dataclass(frozen=True)
class MissingState:
    """A state/UT with an assembly but no entry in the events catalogue."""

    eci_code: str
    name: str
    kind: str  # "state" | "union_territory"


@dataclass(frozen=True)
class IndicatorCoverage:
    """A single indicator artifact projected onto the temporal richness meter."""

    id: str
    category: str
    title: str
    unit: str
    time_grain: str
    span: str  # raw `coverage.temporal` string
    n_periods: int
    n_entities: int
    n_rows: int
    source_host: str
    meter_cells: tuple[bool, ...]
    is_snapshot: bool
    # True iff the indicator id is referenced by any topic in
    # ``datasets/reference/in/topic-catalogue.json``. None when no catalogue
    # is present (e.g. minimal test fixtures) — the wiring section is then
    # silently omitted from the rendered Markdown.
    wired_in_catalogue: bool | None = None


@dataclass(frozen=True)
class StateElectionCoverage:
    """Per-state projection of election slices onto the 7-cell meter."""

    state_code: str
    state_name: str
    events: tuple[str, ...]  # event_ids newest -> oldest
    polled_dates: tuple[str, ...]  # parallel to events; "-" if unknown
    ac_counts: tuple[int, ...]  # parallel to events
    meter_cells: tuple[bool, ...]


@dataclass(frozen=True)
class CoverageReport:
    generated_at: str  # RFC 3339 UTC
    slices: tuple[SliceCoverage, ...]
    missing_states: tuple[MissingState, ...]
    indicators: tuple[IndicatorCoverage, ...] = field(default_factory=tuple)
    state_elections: tuple[StateElectionCoverage, ...] = field(default_factory=tuple)

    @property
    def declared_only(self) -> tuple[SliceCoverage, ...]:
        return tuple(s for s in self.slices if not s.on_disk and s.declared_status)

    @property
    def undeclared_on_disk(self) -> tuple[SliceCoverage, ...]:
        return tuple(s for s in self.slices if s.on_disk and s.declared_status is None)


def _election_slices_from_canonical(
    root: Path,
) -> dict[tuple[str, str], tuple[int, bool, bool]]:
    """Return ``{(event_id, state_code): (ac_count, has_summary, has_parties)}``
    derived from ``datasets/elections/election_results.parquet``.

    Coverage was historically computed by walking
    ``datasets/elections/<event>/<state>/`` for ``results/<n>.json`` +
    ``result.summary.json`` + ``parties.json``. Under the canonical pivot
    (TODO/20260517-canonical-long-format-pivot.md row 1.8b, PR-O.2-minimal)
    the citizen-frontend reads only the canonical Parquet, so coverage now
    reads the same source-of-truth. Mapping:

    - ``ac_count``    : ``COUNT(DISTINCT entity_id)`` matching the AC entity
      pattern ``^IN-<state>-AC-<delim>-<eci_no>$`` for this ``period_label``.
    - ``has_summary`` : whether a state-rollup observation row exists at
      ``entity_id = 'IN-<state>-<event_id>'`` (state-level rollups are the
      canonical successor to ``result.summary.json``).
    - ``has_parties`` : whether any party-rollup observation exists with
      ``entity_id LIKE 'IN-<state>-PARTY-%'`` for this ``period_label``
      (party rollups are the canonical successor to ``parties.json``).

    Entity-id patterns are defined in
    ``backend/yen_gov/canonical/adapters/eci/identity.py`` (see
    ``ac_entity_id``, ``state_rollup_entity_id``, ``party_rollup_entity_id``).

    If the Parquet file is absent (fresh repo, minimal test fixture) the
    function returns an empty mapping, matching the prior "no files on
    disk" behaviour.
    """
    parquet_path = root / ELECTION_RESULTS_PARQUET_REL
    if not parquet_path.exists():
        return {}

    import duckdb

    sql = """
        WITH classified AS (
            SELECT
                period_label AS event_id,
                regexp_extract(entity_id, '^IN-([SU][0-9]{2})', 1) AS state_code,
                entity_id,
                CASE
                    WHEN regexp_matches(entity_id, '^IN-[SU][0-9]{2}-AC-[0-9]+-[0-9]+$')
                        THEN 'ac'
                    WHEN regexp_matches(entity_id, '^IN-[SU][0-9]{2}-PARTY-')
                        THEN 'party'
                    WHEN regexp_matches(entity_id, '^IN-[SU][0-9]{2}-[A-Za-z]+[A-Za-z0-9]*$')
                        THEN 'state_rollup'
                    ELSE 'other'
                END AS kind
            FROM read_parquet(?)
        )
        SELECT
            event_id,
            state_code,
            COUNT(DISTINCT CASE WHEN kind = 'ac' THEN entity_id END)        AS ac_count,
            COUNT(*) FILTER (WHERE kind = 'state_rollup') > 0                AS has_summary,
            COUNT(*) FILTER (WHERE kind = 'party') > 0                       AS has_parties
        FROM classified
        WHERE state_code <> ''
        GROUP BY event_id, state_code
    """
    conn = duckdb.connect(database=":memory:")
    try:
        rows = conn.execute(sql, [str(parquet_path)]).fetchall()
    finally:
        conn.close()

    return {
        (str(event_id), str(state_code)): (
            int(ac_count or 0),
            bool(has_summary),
            bool(has_parties),
        )
        for event_id, state_code, ac_count, has_summary, has_parties in rows
    }


def compute_coverage(root: Path) -> CoverageReport:
    """Reconcile the catalogue with the canonical election Parquet store.

    Reads the declared catalogue at ``datasets/reference/in/election-events.json``
    and the on-disk inventory from ``datasets/elections/election_results.parquet``
    (canonical store, sole source of truth per TODO row 1.8b). The legacy
    per-event/per-state JSON shards (``results/<n>.json``,
    ``result.summary.json``, ``parties.json``) are no longer consulted here
    even when present — they are awaiting deletion in PR-O-ii (row 1.8b-ii).
    """
    catalogue_path = root / CATALOGUE_REL
    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    declared: dict[tuple[str, str], dict] = {}
    for state_code, events in catalogue.get("states", {}).items():
        for ev in events:
            declared[(ev["event_id"], state_code)] = ev

    states_path = root / STATES_REL
    state_names: dict[str, str] = {}
    state_kinds: dict[str, str] = {}
    if states_path.exists():
        for st in json.loads(states_path.read_text(encoding="utf-8")).get("states", []):
            code = st.get("eci_code")
            name = st.get("name")
            kind = st.get("kind")
            if code and name:
                state_names[code] = name
            if code and kind:
                state_kinds[code] = kind

    on_disk = _election_slices_from_canonical(root)

    keys = sorted(set(declared) | set(on_disk))
    slices: list[SliceCoverage] = []
    for event_id, state_code in keys:
        d = declared.get((event_id, state_code))
        ac_count, has_summary, has_parties = on_disk.get(
            (event_id, state_code), (0, False, False)
        )
        slices.append(
            SliceCoverage(
                event_id=event_id,
                state_code=state_code,
                state_name=state_names.get(state_code),
                display=d.get("display") if d else None,
                polled_on=d.get("polled_on") if d else None,
                declared_status=d.get("data_status") if d else None,
                on_disk=(event_id, state_code) in on_disk,
                ac_count=ac_count,
                has_summary=has_summary,
                has_parties=has_parties,
            )
        )

    declared_codes = {state_code for _, state_code in declared}
    missing: list[MissingState] = []
    for code, name in sorted(state_names.items()):
        kind = state_kinds.get(code, "state")
        # Skip UTs without a legislative assembly — they have no AC slice
        # to ingest, so listing them as "missing" is misleading.
        if kind == "union_territory" and code not in UT_CODES_WITH_ASSEMBLY:
            continue
        if code in declared_codes:
            continue
        missing.append(MissingState(eci_code=code, name=name, kind=kind))

    wired_ids = _load_wired_indicator_ids(root)
    indicators = _scan_indicators(root)
    if wired_ids is not None:
        indicators = [
            IndicatorCoverage(
                **{**ind.__dict__, "wired_in_catalogue": ind.id in wired_ids}
            )
            for ind in indicators
        ]

    return CoverageReport(
        generated_at=_max_input_mtime_date(root),
        slices=tuple(slices),
        missing_states=tuple(missing),
        indicators=tuple(indicators),
        state_elections=tuple(_project_state_first(slices, state_names)),
    )


def _max_input_mtime_date(root: Path) -> str:
    """Return ``YYYY-MM-DD`` derived from the newest input the report reads.

    Wall-clock at write time would couple ``data-inventory.md`` bytes to
    when the operator ran ``coverage``, producing a daily git-status churn
    even when nothing about the data changed (CLAUDE.md §10 anti-pattern).
    The report is a pure function of the inputs we scan: the election
    catalogue, states reference, topic catalogue, election artifacts and
    indicator artifacts. Deriving the footer date from
    ``max(input.st_mtime)`` makes re-runs with unchanged inputs produce
    byte-identical output.

    Falls back to ``"unknown"`` when no input exists (fresh checkout or
    sparse fixture tree) so the function stays total.

    Why no idempotency unit test guards this
    ----------------------------------------
    The obvious "call ``render_markdown`` twice, assert byte-equal" test
    is ceremony: it's ``f(x) == f(x)`` for a near-pure function, and it
    only catches a regression if a re-introduced ``datetime.now()`` is
    SUB-DAY (``isoformat()``, ``time()``). A regression that re-adds
    ``datetime.now().strftime("%Y-%m-%d")`` straddles the same UTC day
    in both calls and silently passes. The real regression signal is the
    diff against committed ``docs/reference/**/*.md`` outputs in CI -- if
    someone re-introduces wall-clock here, the next coverage re-run
    changes 110+ doc files and the PR diff is impossible to miss. A
    flimsy unit test that pretends to guard this would be worse than no
    test: it would absolve the reviewer of looking at the doc diff.
    Deleted deliberately, not forgotten.
    """
    inputs: list[Path] = []
    for rel in (CATALOGUE_REL, STATES_REL, TOPIC_CATALOGUE_REL):
        p = root / rel
        if p.is_file():
            inputs.append(p)
    for tree_rel in (INDICATORS_REL, ELECTIONS_REL):
        base = root / tree_rel
        if base.is_dir():
            for path in base.rglob("*.json"):
                if path.is_file():
                    inputs.append(path)
    if not inputs:
        return "unknown"
    newest = max(p.stat().st_mtime for p in inputs)
    return datetime.fromtimestamp(newest, tz=timezone.utc).strftime("%Y-%m-%d")


def _load_wired_indicator_ids(root: Path) -> set[str] | None:
    """Return the set of indicator ids referenced by the topic catalogue.

    Returns ``None`` when ``datasets/reference/in/topic-catalogue.json`` is
    absent (test fixtures, partial checkouts) so the wiring section can be
    omitted gracefully rather than asserting a hard dependency. When the
    catalogue file is present but malformed, returns an empty set so every
    indicator on disk reads as ``unwired`` (which is the honest result).
    """
    catalogue_path = root / TOPIC_CATALOGUE_REL
    if not catalogue_path.exists():
        return None
    try:
        catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    wired: set[str] = set()
    for topic in catalogue.get("topics", []) or []:
        for art in topic.get("artifacts", []) or []:
            if art.get("kind") == "indicator" and art.get("id"):
                wired.add(art["id"])
    return wired


def _parse_temporal(span: str) -> tuple[date, date]:
    """Parse a `coverage.temporal` string into a (start, end) date pair.

    Accepts three shapes:
      * ``"YYYY-MM..YYYY-MM"`` (a closed range, e.g. ``"2007-04..2025-04"``)
      * ``"YYYY-MM"`` (a single point, e.g. ``"2026-03"``)
      * ``"YYYY"`` or ``"YYYY..YYYY"`` (annual / annual range, e.g. ``"2019"``)
    """
    if not span or not isinstance(span, str):
        raise ValueError(f"empty temporal span: {span!r}")
    parts = span.split("..")
    if len(parts) == 1:
        d = _parse_point(parts[0])
        return (d, d)
    if len(parts) == 2:
        return (_parse_point(parts[0]), _parse_point(parts[1]))
    raise ValueError(f"malformed temporal span: {span!r}")


_DATE_RE = re.compile(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?")


def _parse_point(token: str) -> date:
    """Parse a single temporal token into a date.

    Strict shapes ``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD`` are accepted directly.
    For artifacts that put free-form prose alongside a date (legacy snapshot
    convention like ``\"snapshot 2026-05-14 (RS Session 259)\"``), the first
    embedded ISO-like date is extracted. Migrating those artifacts to clean
    canonical strings is preferred, but tolerating them keeps the inventory
    honest in the meantime.
    """
    token = token.strip()
    m = _DATE_RE.search(token)
    if not m:
        raise ValueError(f"unrecognised temporal token: {token!r}")
    y = int(m.group(1))
    mo = int(m.group(2)) if m.group(2) else 4  # FY default
    d = int(m.group(3)) if m.group(3) else 1
    return date(y, mo, d)


def _compute_meter(
    start: date, end: date, edges: tuple[tuple[date, date], ...] = BUCKET_EDGES
) -> tuple[bool, ...]:
    """Return one bool per bucket: True iff [start, end] overlaps the bucket."""
    return tuple(not (end < lo or start > hi) for lo, hi in edges)


def _compute_election_meter(n_events: int) -> tuple[bool, ...]:
    """N rightmost cells filled, capped at the bucket count.

    Mirrors the indicator meter layout (rightmost = newest). For state-first
    election coverage each cell is one election cycle, not a year window.
    """
    n = max(0, min(N_BUCKETS, n_events))
    return tuple([False] * (N_BUCKETS - n) + [True] * n)


def _render_meter(cells: tuple[bool, ...], snapshot: bool = False) -> str:
    glyphs = " ".join("\u25cf" if c else "\u25cb" for c in cells)
    n_filled = sum(1 for c in cells if c)
    suffix = " (snapshot)" if snapshot else ""
    return f"{glyphs} {n_filled}/{len(cells)}{suffix}"


def _scan_indicators(root: Path) -> list[IndicatorCoverage]:
    """Walk ``datasets/indicators/in/**/*.json`` and project each artifact."""
    indicators_root = root / INDICATORS_REL
    out: list[IndicatorCoverage] = []
    if not indicators_root.exists():
        return out
    for path in sorted(indicators_root.rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ind = doc.get("indicator") or {}
        cov = doc.get("coverage") or {}
        span = cov.get("temporal")
        if not span:
            continue
        try:
            start, end = _parse_temporal(span)
        except ValueError:
            continue
        meter = _compute_meter(start, end)
        is_snapshot = (start == end) or ".." not in span
        rows = doc.get("rows") or []
        n_periods = len({_row_period_key(r) for r in rows if r.get("period")}) or (
            1 if is_snapshot else 0
        )
        n_entities = len({r["entity_id"] for r in rows if "entity_id" in r})
        sources = doc.get("sources") or []
        host = ""
        if sources:
            try:
                host = urlparse(sources[0].get("url", "")).netloc
            except ValueError:
                host = ""
        ind_id = ind.get("id") or path.relative_to(indicators_root).with_suffix("").as_posix()
        category = ind_id.split("/", 1)[0] if "/" in ind_id else "other"
        out.append(
            IndicatorCoverage(
                id=ind_id,
                category=category,
                title=ind.get("title") or ind_id,
                unit=ind.get("unit") or "",
                time_grain=ind.get("time_grain") or "",
                span=span,
                n_periods=n_periods,
                n_entities=n_entities,
                n_rows=len(rows),
                source_host=host,
                meter_cells=meter,
                is_snapshot=is_snapshot,
            )
        )
    return out


def _row_period_key(row: dict) -> str:
    p = row.get("period")
    if isinstance(p, dict):
        return str(p.get("start") or p.get("value") or p)
    return str(p)


def _project_state_first(
    slices: list[SliceCoverage], state_names: dict[str, str]
) -> list[StateElectionCoverage]:
    """Group on-disk election slices by state for the state-first meter."""
    by_state: dict[str, list[SliceCoverage]] = {}
    for s in slices:
        if not s.on_disk:
            continue
        by_state.setdefault(s.state_code, []).append(s)
    out: list[StateElectionCoverage] = []
    for code in sorted(by_state):
        # Newest -> oldest (descending by polled_on; fall back to event_id).
        entries = sorted(
            by_state[code],
            key=lambda s: (s.polled_on or "", s.event_id),
            reverse=True,
        )
        out.append(
            StateElectionCoverage(
                state_code=code,
                state_name=state_names.get(code, code),
                events=tuple(s.event_id for s in entries),
                polled_dates=tuple(s.polled_on or "-" for s in entries),
                ac_counts=tuple(s.ac_count for s in entries),
                meter_cells=_compute_election_meter(len(entries)),
            )
        )
    return out


def render_markdown(report: CoverageReport) -> str:
    """Render a CoverageReport as the canonical ``data-inventory.md`` body.

    Generated by ``python -m yen_gov coverage``. Do not hand-edit; re-run after
    each ingest. Any divergence between the declared catalogue and the on-disk
    artifacts is surfaced in the "Inconsistencies" section so it cannot quietly
    rot.
    """
    out: list[str] = []
    out.append("# Data Inventory")
    out.append("")
    out.append(f"**Last Updated**: {report.generated_at} (auto-generated)")
    out.append("")
    out.append(
        "Generated by `python -m yen_gov coverage`. Do not hand-edit. "
        "Re-run after every ingest. Indicator coverage is derived from "
        f"[{INDICATORS_REL}/]({_repo_link(INDICATORS_REL)}/); the declared "
        "election catalogue lives at "
        f"[{CATALOGUE_REL}]({_repo_link(CATALOGUE_REL)}); on-disk election "
        f"artifacts live under [{ELECTIONS_REL}/]({_repo_link(ELECTIONS_REL)}/). "
        "The Temporal Richness meter (\u25cf filled / \u25cb empty) is "
        "explained in "
        "[docs/architecture/backend/coverage.md](../architecture/backend/coverage.md)."
    )
    out.append("")

    total_states = len({s.state_code for s in report.slices if s.on_disk})
    total_acs = sum(s.ac_count for s in report.slices)
    declared_pending = sum(
        1 for s in report.slices if s.declared_status == "pending_upstream"
    )
    out.append("## Summary")
    out.append("")
    out.append(
        f"- {sum(1 for s in report.slices if s.on_disk)} (state, event) slices "
        f"on disk across {total_states} states / "
        f"{len({s.event_id for s in report.slices if s.on_disk})} cohorts."
    )
    out.append(f"- {total_acs:,} per-AC result artifacts emitted in total.")
    if declared_pending:
        out.append(
            f"- {declared_pending} slice(s) declared but awaiting upstream "
            "publication (`data_status: pending_upstream`)."
        )
    if report.missing_states:
        out.append(
            f"- {len(report.missing_states)} state(s) / UT(s) with a "
            "legislative assembly are not yet in the catalogue at all "
            "(see \"Missing\" below)."
        )
    out.append("")

    if report.missing_states:
        out.append("## Missing (no entry in the events catalogue)")
        out.append("")
        out.append(
            "These states/UTs have a legislative assembly but no `event_id` "
            "registered in [election-events.json]"
            f"({_repo_link(CATALOGUE_REL)}). Adding one means: (a) appending "
            "a `(state, year) -> EventInfo` row to "
            "[backend/yen_gov/sources/eci/events.py](../../backend/yen_gov/sources/eci/events.py), "
            "(b) writing the cohort metadata at "
            "`datasets/events/in/eci/<event_id>/election.json`, then "
            "(c) `python -m yen_gov eci-statreport-emit <state> <year>`. "
            "UTs without an assembly (Andaman, Chandigarh, Dadra & NH, "
            "Lakshadweep, Ladakh) are intentionally excluded \u2014 they elect "
            "Lok Sabha MPs only."
        )
        out.append("")
        out.append("| State / UT | Code | Kind |")
        out.append("| --- | --- | --- |")
        for m in report.missing_states:
            out.append(
                f"| {m.name} | `{m.eci_code}` | {m.kind.replace('_', ' ')} |"
            )
        out.append("")

    out.append("## 1. Indicators")
    out.append("")
    if not report.indicators:
        out.append("_No indicator artifacts found under "
                   f"`{INDICATORS_REL}/`._")
        out.append("")
    else:
        wiring_known = any(
            ind.wired_in_catalogue is not None for ind in report.indicators
        )
        n_wired = sum(
            1 for ind in report.indicators if ind.wired_in_catalogue
        )
        n_unwired = sum(
            1 for ind in report.indicators if ind.wired_in_catalogue is False
        )
        out.append(
            f"{len(report.indicators)} artifact(s) under `{INDICATORS_REL}/`. "
            "The Temporal Richness meter projects each indicator's "
            "`coverage.temporal` span onto 7 cells of 3 fiscal years "
            f"(buckets: {', '.join(BUCKET_LABELS)}). Snapshots fill exactly "
            "one cell and carry a `(snapshot)` tag."
        )
        out.append("")
        if wiring_known:
            out.append(
                f"**Frontend wiring**: {n_wired} of "
                f"{n_wired + n_unwired} indicator artifacts are referenced "
                "by [`topic-catalogue.json`]"
                f"({_repo_link(TOPIC_CATALOGUE_REL)}) and therefore reachable "
                "from the IA today; **the remaining "
                f"{n_unwired} are on disk but unreachable from any topic / "
                "state hub** (see \u00a71Z below). The catalogue is "
                "hand-maintained \u2014 every new ingest must add (or "
                "consciously skip) a catalogue entry, or the data quietly "
                "drifts out of the citizen view. Implementation plan: "
                "[`TODO/VIZ-LAYER-GAPS-PLAN.md`]"
                "(../../TODO/VIZ-LAYER-GAPS-PLAN.md); narrative + "
                "mis-framing debt: [data-coverage-report.md \u00a76]"
                "(data-coverage-report.md#6-frontend-wiring-gaps-visualization-layer)."
            )
            out.append("")
        by_cat: dict[str, list[IndicatorCoverage]] = {}
        for ind in report.indicators:
            by_cat.setdefault(ind.category, []).append(ind)
        sub_letters = "abcdefghijklmnop"
        for n, cat in enumerate(sorted(by_cat)):
            label = sub_letters[n] if n < len(sub_letters) else str(n + 1)
            out.append(f"### 1{label}. {cat.title()} ({len(by_cat[cat])})")
            out.append("")
            wired_col = " Wired |" if wiring_known else ""
            wired_sep = " :---: |" if wiring_known else ""
            out.append(
                "| id | unit | time grain | span | rows | entities | "
                f"Temporal Richness |{wired_col} source |"
            )
            out.append(
                "| --- | --- | --- | --- | ---: | ---: | --- |"
                f"{wired_sep} --- |"
            )
            for ind in sorted(by_cat[cat], key=lambda x: x.id):
                if wiring_known:
                    wired_cell = (
                        " \u25cf |" if ind.wired_in_catalogue else " \u25cb |"
                    )
                else:
                    wired_cell = ""
                # Link the id cell to the artifact JSON on disk. The
                # auto-generated per-indicator markdown tree was retired
                # 2026-05-17 (Phase #4a); the JSON is now the single source
                # of truth and is github-browsable as a static surface.
                id_cell = f"[`{ind.id}`](../../datasets/indicators/in/{ind.id}.json)"
                out.append(
                    f"| {id_cell} | {ind.unit or '-'} | "
                    f"{ind.time_grain or '-'} | {ind.span} | "
                    f"{ind.n_rows} | {ind.n_entities} | "
                    f"{_render_meter(ind.meter_cells, ind.is_snapshot)} |"
                    f"{wired_cell} {ind.source_host or '-'} |"
                )
            out.append("")

        if wiring_known and n_unwired:
            out.append("### 1Z. Frontend wiring \u2014 unwired indicators")
            out.append("")
            out.append(
                f"{n_unwired} indicator artifact(s) on disk are NOT referenced "
                "by any topic in [`topic-catalogue.json`]"
                f"({_repo_link(TOPIC_CATALOGUE_REL)}). They validate, they "
                "have provenance, but no route renders them and no citizen can "
                "find them. Adding a catalogue entry (or a conscious "
                "`x-skipped` exclusion) is part of every ingest's Definition "
                "of Done. The visualization-layer plan in "
                "[`TODO/VIZ-LAYER-GAPS-PLAN.md`]"
                "(../../TODO/VIZ-LAYER-GAPS-PLAN.md) sequences the wiring "
                "(plus the `series_breaks` / `vintage` / direction-cue "
                "renderer fixes the new wedges depend on)."
            )
            out.append("")
            unwired_by_cat: dict[str, list[IndicatorCoverage]] = {}
            for ind in report.indicators:
                if ind.wired_in_catalogue is False:
                    unwired_by_cat.setdefault(ind.category, []).append(ind)
            out.append("| category | indicator id | shape hint |")
            out.append("| --- | --- | --- |")
            for cat in sorted(unwired_by_cat):
                for ind in sorted(unwired_by_cat[cat], key=lambda x: x.id):
                    shape = ind.time_grain or "-"
                    if ind.is_snapshot:
                        shape = f"{shape} (snapshot)"
                    id_cell = f"[`{ind.id}`](../../datasets/indicators/in/{ind.id}.json)"
                    out.append(
                        f"| {cat} | {id_cell} | "
                        f"{shape}, {ind.n_entities} entities, {ind.span} |"
                    )
            out.append("")

    out.append("## 2a. Elections \u2014 coverage depth (state-first)")
    out.append("")
    if not report.state_elections:
        out.append("_No on-disk election slices yet._")
        out.append("")
    else:
        out.append(
            f"{len(report.state_elections)} state(s)/UT(s) have at least one "
            "on-disk slice. The Temporal Richness meter here is "
            "**event-cycle-based**: each cell is one election cycle (rightmost "
            "= newest), so a state with 3 ingested elections shows "
            "`\u25cb \u25cb \u25cb \u25cb \u25cf \u25cf \u25cf 3/7`."
        )
        out.append("")
        out.append(
            "| State | Code | Cycles | Temporal Richness | "
            "On-disk event_ids (newest \u2192 oldest) |"
        )
        out.append("| --- | --- | ---: | --- | --- |")
        for se in report.state_elections:
            event_list = ", ".join(se.events) if se.events else "-"
            out.append(
                f"| {se.state_name} | `{se.state_code}` | "
                f"{len(se.events)} | "
                f"{_render_meter(se.meter_cells)} | "
                f"{event_list} |"
            )
        out.append("")

    out.append("## 2b. Elections \u2014 by cohort (event-first)")
    out.append("")
    by_event: dict[str, list[SliceCoverage]] = {}
    for s in report.slices:
        by_event.setdefault(s.event_id, []).append(s)
    for event_id in sorted(by_event):
        out.append(f"### `{event_id}`")
        out.append("")
        out.append(
            "| State | Code | ACs | Summary | Parties | Status | Polled |"
        )
        out.append("| --- | --- | ---: | :---: | :---: | --- | --- |")
        for s in sorted(by_event[event_id], key=lambda x: x.state_code):
            label = s.state_name or s.display or "(unknown)"
            status = s.declared_status or "_undeclared_"
            if not s.on_disk:
                status = f"{status} (catalogue-only)"
            out.append(
                f"| {label} | `{s.state_code}` | "
                f"{s.ac_count if s.on_disk else '-'} | "
                f"{'yes' if s.has_summary else '-'} | "
                f"{'yes' if s.has_parties else '-'} | "
                f"{status} | {s.polled_on or '-'} |"
            )
        out.append("")

    issues: list[str] = []
    for s in report.declared_only:
        if s.declared_status == "pending_upstream":
            continue  # expected gap, not an inconsistency
        issues.append(
            f"- Declared `{s.declared_status}` for `({s.event_id}, "
            f"{s.state_code})` but no artifacts on disk."
        )
    for s in report.undeclared_on_disk:
        issues.append(
            f"- On-disk artifacts for `({s.event_id}, {s.state_code})` "
            "but no entry in the catalogue."
        )
    if issues:
        out.append("## Inconsistencies")
        out.append("")
        out.extend(issues)
        out.append("")

    return "\n".join(out) + "\n"


def _repo_link(rel: str) -> str:
    """Markdown-relative link from ``docs/reference/<file>.md`` to a repo path."""
    # data-inventory.md sits at docs/reference/, so ../../ gets to repo root.
    return "../../" + rel
