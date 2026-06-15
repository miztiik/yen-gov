"""Event-summary derived mart.

The redesigned `/t/elections` (General elections) and `/t/elections/assemblies`
(Assembly elections) routes mounted in PR-E4 need ONE row per election event
so the citizen browser does not scan the per-AC corpus to build the
landing-page tables. This module materialises that aggregate from the
canonical per-event summary.csv files into a single mart CSV at
`datasets/data/marts/elections/event_summary.csv`.

The mart is the read seam for both routes:

- General elections route: filter `scope = 'national'` -> one row per
  Parliament event_id where `state_code IS NULL`. Each row aggregates the
  shipped per-PC winners from
  `datasets/elections/parliament/election=*/summary.csv`.
- Assembly elections route: filter `scope = 'state'` -> one row per
  `(event_id, state_code)` from
  `datasets/elections/assembly/state=*/election=*/summary.csv`.

Inputs (read seam):

- `datasets/data/_schema/columns.json` (file-class contract, PR-E1)
- `datasets/taxonomy/election_events.json` (event_id <-> polled_on + kind;
  state_code is recovered from the catalogue's outer dict key, never from
  display-string parsing -- see R1.5 Gregor verdict 2026-06-15)
- `datasets/taxonomy/lgd_states.json` via `eci_to_lgd_slug()` (eci_st_code ->
  on-disk LGD slug -- the canonical bridge for the assembly partition
  layout; one helper, also used by `eci_ls.py` and `eci_ae_panel.py`)
- `datasets/data/entities/source.csv` (FK target; the writer UPSERTs the
  mart citation row)
- `datasets/elections/{parliament,assembly}/.../summary.csv` (per-PC / per-AC
  winners)

Output (mart, byte-deterministic + idempotent):

- `datasets/data/marts/elections/event_summary.csv`. 12 columns per the
  PR-E1 file-class contract.

Composite PK (`event_id`, `state_code`): `state_code IS NULL` for the single
Parliament row per `event_id` (scope=national); set for each Assembly row
(scope=state).

Per Hans verdict 2026-06-15: `leading_party_id` is the canonical party_id
with the most seats (NOT the alliance label). Alliance attribution is a
writer-side follow-up; the renderer never derives it. Per Fowler verdict:
one CSV serves both routes; per Gregor: composite NULL-in-PK matches
`electoral_district_membership.csv` precedent.

Per Gregor + R1.5 persona round-2 verdict (2026-06-15): the assembly loop
iterates the catalogue's outer dict ITEMS directly. The catalogue is
already keyed by ECI state-code -- recovering state_code from display-string
parsing was a Canonical Data Model violation per Hohpe (EIP ch.8). Disk
slug derivation goes through the single canonical helper
`eci_to_lgd_slug()` at
`backend/yen_gov/canonical/adapters/eci/state_slug.py`.

Re-run after any electoral ingest:

    python -m yen_gov derive-event-summary --root .

Idempotent: re-running on unchanged input yields a byte-identical CSV
(write_csv's skip-write-if-equal keeps mtime stable so re-runs leave a
clean `git status`).
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

EVENT_SUMMARY_REL = PurePosixPath("datasets/data/marts/elections/event_summary.csv")
EVENT_SUMMARY_FILE_CLASS = EVENT_SUMMARY_REL.as_posix()

ELECTION_EVENTS_REL = PurePosixPath("datasets/taxonomy/election_events.json")
SOURCE_CSV_REL = PurePosixPath("datasets/data/entities/source.csv")
PARLIAMENT_GLOB = "datasets/elections/parliament/election=*/summary.csv"
ASSEMBLY_BASE_REL = PurePosixPath("datasets/elections/assembly")

MART_SOURCE_PRODUCER = "yen-gov"
MART_SOURCE_TITLE = "Per-event election summary aggregate (event_summary.csv)"
MART_SOURCE_VINTAGE = "2026-06-15"
MART_SOURCE_URL = (
    "https://github.com/miztiik/yen-gov/blob/main/"
    "datasets/data/marts/elections/event_summary.csv"
)


@dataclass(frozen=True)
class EventSummaryMartResult:
    """Summary of one event_summary mart refresh."""

    out_path: Path
    row_count: int
    national_row_count: int
    state_row_count: int
    skipped_files: int
    source_id: str


@dataclass
class _Agg:
    """Per-(event_id, state_code) winner aggregator."""

    event_id: str
    state_code: str | None
    scope: str  # "national" | "state"
    kind: str
    polled_on: str
    seats_total: int = 0
    electors_total: int = 0
    votes_polled_total: int = 0
    have_turnout: bool = False
    seats_by_party: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def refresh_event_summary_mart(repo_root: Path) -> EventSummaryMartResult:
    """Regenerate `datasets/data/marts/elections/event_summary.csv`."""
    root = repo_root.resolve()

    catalogue = _load_catalogue(root / ELECTION_EVENTS_REL)
    source_id = _ensure_mart_source(root / SOURCE_CSV_REL)

    parliament_files = sorted(root.glob(PARLIAMENT_GLOB))

    aggs: dict[tuple[str, str | None], _Agg] = {}
    skipped = 0

    # Parliament: collapse all per-state PC rows for a given year into one
    # national row per event_id.
    parliament_by_event: dict[str, _Agg] = {}
    for path in parliament_files:
        year = _year_from_election_dir(path.parent.name)
        if year is None:
            skipped += 1
            continue
        canonical = _find_parliament_event(catalogue, year)
        if canonical is None:
            skipped += 1
            continue
        event_id = str(canonical["event_id"])
        agg = parliament_by_event.get(event_id)
        if agg is None:
            agg = _Agg(
                event_id=event_id,
                state_code=None,
                scope="national",
                kind=str(canonical["kind"]),
                polled_on=str(canonical["polled_on"]),
            )
            parliament_by_event[event_id] = agg
            aggs[(event_id, None)] = agg
        _accumulate_summary_rows(path, agg)

    # Assembly: iterate the catalogue's outer dict directly so state_code is
    # never recovered from display-string parsing. The catalogue is keyed by
    # ECI state-code; the disk slug derives from the single canonical helper
    # `eci_to_lgd_slug()` which reads `datasets/taxonomy/lgd_states.json`.
    # Per Gregor + R1.5 persona round-2 verdict (2026-06-15).
    assembly_base = root / ASSEMBLY_BASE_REL
    states_payload = catalogue["states"]
    assert isinstance(states_payload, dict)
    for state_code, evts in states_payload.items():
        if not isinstance(evts, list):
            continue
        try:
            state_slug = eci_to_lgd_slug(state_code)
        except KeyError:
            skipped += sum(1 for _ in evts)
            continue
        state_dir = assembly_base / f"state={state_slug}"
        if not state_dir.is_dir():
            continue
        for path in sorted(state_dir.glob("election=*/summary.csv")):
            year = _year_from_election_dir(path.parent.name)
            if year is None:
                skipped += 1
                continue
            canonical = _find_assembly_event(catalogue, state_code, year)
            if canonical is None:
                skipped += 1
                continue
            event_id = str(canonical["event_id"])
            key = (event_id, state_code)
            agg = aggs.get(key)
            if agg is None:
                agg = _Agg(
                    event_id=event_id,
                    state_code=state_code,
                    scope="state",
                    kind=str(canonical["kind"]),
                    polled_on=str(canonical["polled_on"]),
                )
                aggs[key] = agg
            _accumulate_summary_rows(path, agg)

    rows = _agg_rows(aggs.values(), source_id=source_id)
    out_path = root / EVENT_SUMMARY_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(path=out_path, file_class=EVENT_SUMMARY_FILE_CLASS, rows=rows)

    national_n = sum(1 for r in rows if r["scope"] == "national")
    state_n = sum(1 for r in rows if r["scope"] == "state")
    return EventSummaryMartResult(
        out_path=out_path,
        row_count=len(rows),
        national_row_count=national_n,
        state_row_count=state_n,
        skipped_files=skipped,
        source_id=source_id,
    )


# ---------------------------------------------------------------------------
# Catalogue loader
# ---------------------------------------------------------------------------


def _load_catalogue(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    states = payload.get("states", {})
    if not isinstance(states, dict):
        raise ValueError(
            "election_events.json: 'states' is not a dict "
            f"(got {type(states).__name__})"
        )
    return {"states": states}


def _find_parliament_event(
    catalogue: dict[str, object], year: int
) -> dict[str, object] | None:
    """First catalogue event with kind=parliament + polled_on year == folder year.

    All states' rows for a given national cycle share the same event_id per
    ADR-0023, so the FIRST matching row is canonical.
    """
    states_payload = catalogue["states"]
    assert isinstance(states_payload, dict)
    for evts in states_payload.values():
        if not isinstance(evts, list):
            continue
        for e in evts:
            if e.get("kind") != "parliament":
                continue
            polled_on = str(e.get("polled_on", ""))
            if polled_on.startswith(f"{year}-"):
                return e
    return None


def _find_assembly_event(
    catalogue: dict[str, object], state_code: str, year: int
) -> dict[str, object] | None:
    """Catalogue event for (state_code, year, kind in {assembly, assembly_bye, by_election})."""
    states_payload = catalogue["states"]
    assert isinstance(states_payload, dict)
    evts = states_payload.get(state_code, [])
    if not isinstance(evts, list):
        return None
    for e in evts:
        if e.get("kind") not in ("assembly", "assembly_bye", "by_election"):
            continue
        polled_on = str(e.get("polled_on", ""))
        if polled_on.startswith(f"{year}-"):
            return e
    return None


# ---------------------------------------------------------------------------
# Per-event summary.csv aggregation
# ---------------------------------------------------------------------------


def _accumulate_summary_rows(path: Path, agg: _Agg) -> None:
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            agg.seats_total += 1
            party_id = (row.get("winner_party_id") or "").strip()
            if party_id:
                agg.seats_by_party[party_id] += 1
            electors = _int_or_none(row.get("electors"))
            votes_polled = _int_or_none(row.get("votes_polled"))
            if electors is not None and votes_polled is not None and electors > 0:
                agg.electors_total += electors
                agg.votes_polled_total += votes_polled
                agg.have_turnout = True


def _agg_rows(
    aggs: Iterable[_Agg], *, source_id: str
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for a in aggs:
        if a.seats_by_party:
            ranked = sorted(a.seats_by_party.items(), key=lambda kv: (-kv[1], kv[0]))
            leading_party_id: str | None = ranked[0][0]
            seats_won = ranked[0][1]
            runner_up_party_id: str | None = ranked[1][0] if len(ranked) > 1 else None
            runner_up_seats: int | None = ranked[1][1] if len(ranked) > 1 else None
        else:
            leading_party_id = None
            seats_won = 0
            runner_up_party_id = None
            runner_up_seats = None
        turnout_pct: float | None
        if a.have_turnout and a.electors_total > 0:
            turnout_pct = round(a.votes_polled_total / a.electors_total * 100.0, 4)
        else:
            turnout_pct = None
        out.append(
            {
                "event_id": a.event_id,
                "state_code": a.state_code,
                "scope": a.scope,
                "kind": a.kind,
                "polled_on": a.polled_on,
                "leading_party_id": leading_party_id,
                "seats_won": seats_won,
                "seats_contested": a.seats_total,
                "turnout_pct": turnout_pct,
                "runner_up_party_id": runner_up_party_id,
                "runner_up_seats": runner_up_seats,
                "source_id": source_id,
            }
        )
    # write_csv sorts deterministically by PK columns (event_id, state_code).
    return out


# ---------------------------------------------------------------------------
# source.csv UPSERT
# ---------------------------------------------------------------------------


def _ensure_mart_source(source_csv_path: Path) -> str:
    source_id = derive_source_id(
        producer=MART_SOURCE_PRODUCER,
        title=MART_SOURCE_TITLE,
        vintage=MART_SOURCE_VINTAGE,
    )
    with source_csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        all_rows = list(reader)

    if any(r.get("source_id") == source_id for r in all_rows):
        return source_id

    new_row = {fn: "" for fn in fieldnames}
    new_row["source_id"] = source_id
    if "producer" in fieldnames:
        new_row["producer"] = MART_SOURCE_PRODUCER
    if "title" in fieldnames:
        new_row["title"] = MART_SOURCE_TITLE
    if "vintage" in fieldnames:
        new_row["vintage"] = MART_SOURCE_VINTAGE
    if "url" in fieldnames:
        new_row["url"] = MART_SOURCE_URL
    all_rows.append(new_row)
    with source_csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)
    return source_id


# ---------------------------------------------------------------------------
# Path + value helpers
# ---------------------------------------------------------------------------


_ELECTION_DIR_RE = re.compile(r"^election=(\d{4})$")


def _year_from_election_dir(name: str) -> int | None:
    m = _ELECTION_DIR_RE.match(name)
    return int(m.group(1)) if m else None


def _int_or_none(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


__all__ = [
    "EVENT_SUMMARY_REL",
    "EVENT_SUMMARY_FILE_CLASS",
    "EventSummaryMartResult",
    "refresh_event_summary_mart",
]
