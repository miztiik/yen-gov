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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CATALOGUE_REL = "datasets/reference/in/election-events.json"
STATES_REL = "datasets/reference/in/states.json"
ELECTIONS_REL = "datasets/elections"
INVENTORY_REL = "docs/reference/data-inventory.md"

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
class CoverageReport:
    generated_at: str  # RFC 3339 UTC
    slices: tuple[SliceCoverage, ...]
    missing_states: tuple[MissingState, ...]

    @property
    def declared_only(self) -> tuple[SliceCoverage, ...]:
        return tuple(s for s in self.slices if not s.on_disk and s.declared_status)

    @property
    def undeclared_on_disk(self) -> tuple[SliceCoverage, ...]:
        return tuple(s for s in self.slices if s.on_disk and s.declared_status is None)


def compute_coverage(root: Path) -> CoverageReport:
    """Walk the catalogue + ``datasets/elections/`` tree and return a unified view."""
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

    elections_root = root / ELECTIONS_REL
    on_disk: dict[tuple[str, str], tuple[int, bool, bool]] = {}
    if elections_root.exists():
        for event_dir in sorted(p for p in elections_root.iterdir() if p.is_dir()):
            for state_dir in sorted(p for p in event_dir.iterdir() if p.is_dir()):
                results_dir = state_dir / "results"
                ac_count = (
                    sum(1 for p in results_dir.iterdir() if p.suffix == ".json")
                    if results_dir.exists()
                    else 0
                )
                has_summary = (state_dir / "result.summary.json").exists()
                has_parties = (state_dir / "parties.json").exists()
                on_disk[(event_dir.name, state_dir.name)] = (
                    ac_count,
                    has_summary,
                    has_parties,
                )

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

    return CoverageReport(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        slices=tuple(slices),
        missing_states=tuple(missing),
    )


def render_markdown(report: CoverageReport) -> str:
    """Render a CoverageReport as the canonical ``data-inventory.md`` body.

    Generated by ``python -m yen_gov coverage``. Do not hand-edit; re-run after
    each ingest. Any divergence between the declared catalogue and the on-disk
    artifacts is surfaced in the "Inconsistencies" section so it cannot quietly
    rot.
    """
    out: list[str] = []
    out.append("# Election Data Inventory")
    out.append("")
    out.append(f"**Last Updated**: {report.generated_at} (auto-generated)")
    out.append("")
    out.append(
        "Generated by `python -m yen_gov coverage`. Do not hand-edit. "
        "Re-run after every ingest. Source of truth for declared coverage is "
        f"[{CATALOGUE_REL}]({_repo_link(CATALOGUE_REL)}); on-disk artifacts "
        f"live under [{ELECTIONS_REL}/]({_repo_link(ELECTIONS_REL)}/)."
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

    out.append("## By cohort")
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
