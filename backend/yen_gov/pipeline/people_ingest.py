"""People-ingest orchestrator.

Composes the pure adapter (``yen_gov.sources.eci.people_panel``) with the
existing ``write_artifact`` chokepoint (dict-equal idempotency for free),
the elections inventory (declarative "done and tested" gate), and the
discrepancy report (per-AC vote comparison against existing
result.constituency artifacts).

Public entry point: ``run_people_ingest``. The CLI in ``yen_gov.cli`` is a
thin wrapper around it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.eci.people_panel import (
    ADAPTER_ID,
    PersonRow,
    group_by_ac,
    parse_panel,
    to_people_payload,
)


PEOPLE_SCHEMA_FILE = "people.entity.schema.json"
INVENTORY_SCHEMA_FILE = "elections-inventory.schema.json"
CONFIG_SCHEMA_FILE = "elections-config.schema.json"

# Repo-relative paths the orchestrator owns.
PEOPLE_DIR_REL = ("datasets", "people")
INVENTORY_PATH_REL = ("datasets", "elections", "_inventory.json")
CONFIG_PATH_REL = ("config", "elections.json")
REPORTS_DIR_REL = (".runtime", "reports")


class IngestHalted(RuntimeError):
    """Raised when discrepancy thresholds halt the run."""


@dataclass(frozen=True)
class DiscrepancyEntry:
    ac_code: int
    field: str
    eci_value: int | None
    panel_value: int | None
    delta_abs: int


@dataclass(frozen=True)
class DiscrepancyReport:
    election_id: str
    state: str
    source_input: str
    acs_total: int
    acs_with_mismatch: int
    coverage_pct: float
    mean_delta_pp: float
    halted: bool
    warn: bool
    thresholds: dict[str, dict[str, float]]
    discrepancies: tuple[DiscrepancyEntry, ...]

    def to_dict(self, *, run_id: str) -> dict:
        return {
            "run_id": run_id,
            "election_id": self.election_id,
            "state": self.state,
            "source_input": self.source_input,
            "thresholds": self.thresholds,
            "summary": {
                "acs_total": self.acs_total,
                "acs_with_mismatch": self.acs_with_mismatch,
                "coverage_pct": round(self.coverage_pct, 4),
                "mean_delta_pp": round(self.mean_delta_pp, 4),
                "halted": self.halted,
                "warn": self.warn,
            },
            "discrepancies": [
                {
                    "ac_code": d.ac_code,
                    "field": d.field,
                    "eci_value": d.eci_value,
                    "panel_value": d.panel_value,
                    "delta_abs": d.delta_abs,
                }
                for d in self.discrepancies
            ],
        }


def compare_winner_votes(
    rows_by_ac: dict[int, list[PersonRow]],
    *,
    election_id: str,
    state: str,
    repo_root: Path,
    thresholds: dict[str, dict[str, float]],
    source_input: str,
) -> DiscrepancyReport:
    """Compare the panel's winner-vote totals to the ECI result.constituency
    artifacts already on disk. Decides halt/warn per the thresholds."""
    results_dir = repo_root / "datasets" / "elections" / election_id / state / "results"
    discrepancies: list[DiscrepancyEntry] = []
    acs_total = 0
    deltas_pp: list[float] = []
    for ac_code, rows in sorted(rows_by_ac.items()):
        eci_file = results_dir / f"{ac_code}.json"
        if not eci_file.is_file():
            # Nothing to compare against: count toward acs_total but skip
            # delta math. (Older years may not have ECI artifacts yet.)
            acs_total += 1
            continue
        acs_total += 1
        eci_doc = json.loads(eci_file.read_text(encoding="utf-8"))
        eci_winner = eci_doc.get("winner") or {}
        eci_votes = eci_winner.get("votes")
        panel_winner = next((r for r in rows if r.position == 1), None)
        if panel_winner is None or eci_votes is None:
            continue
        delta_abs = abs(panel_winner.votes - int(eci_votes))
        if delta_abs == 0:
            continue
        discrepancies.append(
            DiscrepancyEntry(
                ac_code=ac_code,
                field="winner_votes",
                eci_value=int(eci_votes),
                panel_value=panel_winner.votes,
                delta_abs=delta_abs,
            )
        )
        votes_polled = (eci_doc.get("totals") or {}).get("votes_polled")
        if votes_polled:
            deltas_pp.append(100.0 * delta_abs / int(votes_polled))

    acs_with_mismatch = len({d.ac_code for d in discrepancies})
    coverage_pct = (100.0 * acs_with_mismatch / acs_total) if acs_total else 0.0
    mean_delta_pp = (sum(deltas_pp) / len(deltas_pp)) if deltas_pp else 0.0

    ac_pair = thresholds["ac_mismatch_pct"]
    delta_pair = thresholds["mean_delta_pp"]
    halted = (
        coverage_pct > ac_pair["halt"] or mean_delta_pp > delta_pair["halt"]
    )
    warn = (
        not halted
        and (coverage_pct > ac_pair["warn"] or mean_delta_pp > delta_pair["warn"])
    )

    return DiscrepancyReport(
        election_id=election_id,
        state=state,
        source_input=source_input,
        acs_total=acs_total,
        acs_with_mismatch=acs_with_mismatch,
        coverage_pct=coverage_pct,
        mean_delta_pp=mean_delta_pp,
        halted=halted,
        warn=warn,
        thresholds=thresholds,
        discrepancies=tuple(discrepancies),
    )


def write_people_files(
    rows: Iterable[PersonRow],
    *,
    repo_root: Path,
    sources: list[Source],
) -> list[Path]:
    """Emit one people.entity artifact per row via ``write_artifact``.

    Returns the list of written (or skipped-because-equal) paths. The
    dict-equal write-skip gate in ``write_artifact`` handles idempotency;
    callers do not need to special-case re-runs.
    """
    sdoc = schema_doc(PEOPLE_SCHEMA_FILE)
    sid = schema_id(PEOPLE_SCHEMA_FILE)
    sver = schema_version(PEOPLE_SCHEMA_FILE)
    base = repo_root.joinpath(*PEOPLE_DIR_REL)
    out: list[Path] = []
    for row in rows:
        path = base / row.election_id / str(row.ac_code) / f"{row.candidate_slug}.json"
        write_artifact(
            path=path,
            schema_id=sid,
            schema_version=sver,
            payload=to_people_payload(row),
            sources=sources,
            schema_for_validation=sdoc,
        )
        out.append(path)
    return out


def upsert_inventory_entry(
    *,
    repo_root: Path,
    election_id: str,
    state: str,
    source_input: str,
    ingested_at: str,
    discrepancy_summary: dict,
) -> Path:
    """Insert or replace the (election_id, state, source_input) entry in
    ``datasets/elections/_inventory.json``. Re-runs are idempotent: the
    underlying ``write_artifact`` skips when nothing changed."""
    inv_path = repo_root.joinpath(*INVENTORY_PATH_REL)
    existing: list[dict] = []
    if inv_path.is_file():
        prior = json.loads(inv_path.read_text(encoding="utf-8"))
        existing = list(prior.get("ingested") or [])

    new_entry = {
        "election_id": election_id,
        "state": state,
        "source_input": source_input,
        "ingested_at": ingested_at,
        "discrepancy_summary": discrepancy_summary,
    }
    filtered = [
        e
        for e in existing
        if (e.get("election_id"), e.get("state"), e.get("source_input"))
        != (election_id, state, source_input)
    ]
    filtered.append(new_entry)
    filtered.sort(
        key=lambda e: (e["election_id"], e["state"], e["source_input"])
    )

    sdoc = schema_doc(INVENTORY_SCHEMA_FILE)
    write_artifact(
        path=inv_path,
        schema_id=schema_id(INVENTORY_SCHEMA_FILE),
        schema_version=schema_version(INVENTORY_SCHEMA_FILE),
        payload={"ingested": filtered},
        sources=[],
        schema_for_validation=sdoc,
    )
    return inv_path


def write_discrepancy_report(
    *,
    repo_root: Path,
    report: DiscrepancyReport,
    run_id: str,
) -> Path:
    """Write the per-run JSON discrepancy report under .runtime/reports/.
    Gitignored, citizen never sees."""
    out_dir = repo_root.joinpath(*REPORTS_DIR_REL)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ingest-discrepancies-{run_id}.json"
    out_path.write_text(
        json.dumps(report.to_dict(run_id=run_id), indent=2) + "\n",
        encoding="utf-8",
    )
    return out_path


def load_thresholds(repo_root: Path) -> dict[str, dict[str, float]]:
    """Read discrepancy_thresholds from config/elections.json."""
    cfg_path = repo_root.joinpath(*CONFIG_PATH_REL)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    return cfg["discrepancy_thresholds"]


@dataclass(frozen=True)
class IngestResult:
    people_written: int
    inventory_path: Path
    report_path: Path
    report: DiscrepancyReport


def run_people_ingest(
    *,
    repo_root: Path,
    csv_path: Path,
    election_id: str,
    state: str,
    year: int,
    source_input: str,
    source_url: str,
    source_authority: str = "Election Commission of India",
    source_name: str | None = None,
    ingested_at: str | None = None,
    run_id: str | None = None,
    force: bool = False,
) -> IngestResult:
    """End-to-end: parse, compare, emit, inventory, report.

    Raises ``IngestHalted`` when discrepancy thresholds halt the run; no
    people files are written and no inventory entry is upserted in that
    case. The discrepancy report IS written so the operator can inspect.
    """
    # Inventory short-circuit (the "done and tested" gate).
    inv_path = repo_root.joinpath(*INVENTORY_PATH_REL)
    if not force and inv_path.is_file():
        prior = json.loads(inv_path.read_text(encoding="utf-8"))
        triples = {
            (e.get("election_id"), e.get("state"), e.get("source_input"))
            for e in (prior.get("ingested") or [])
        }
        if (election_id, state, source_input) in triples:
            # Already ingested; honour declarative gate.
            return IngestResult(
                people_written=0,
                inventory_path=inv_path,
                report_path=Path(),
                report=DiscrepancyReport(
                    election_id=election_id,
                    state=state,
                    source_input=source_input,
                    acs_total=0,
                    acs_with_mismatch=0,
                    coverage_pct=0.0,
                    mean_delta_pp=0.0,
                    halted=False,
                    warn=False,
                    thresholds=load_thresholds(repo_root),
                    discrepancies=(),
                ),
            )

    rows = parse_panel(
        csv_path, election_id=election_id, state_code=state, year=year
    )
    by_ac = group_by_ac(rows)
    thresholds = load_thresholds(repo_root)
    report = compare_winner_votes(
        by_ac,
        election_id=election_id,
        state=state,
        repo_root=repo_root,
        thresholds=thresholds,
        source_input=source_input,
    )

    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = write_discrepancy_report(
        repo_root=repo_root, report=report, run_id=run_id
    )
    if report.halted:
        raise IngestHalted(
            f"discrepancy thresholds exceeded for {election_id}/{state}: "
            f"coverage={report.coverage_pct:.2f}% mean_delta={report.mean_delta_pp:.3f}pp; "
            f"see {report_path}"
        )

    fetched = (
        datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
        if ingested_at
        else datetime.now(timezone.utc).replace(microsecond=0)
    )
    sources = [Source(url=source_url, fetched_at=fetched)]
    # Source.to_dict only emits {url, fetched_at}; name/authority are
    # optional per the schema and not part of Source's contract yet, so
    # they ride on the artifact when needed but this slice doesn't.
    _ = (source_name, source_authority)  # reserved for a later enrichment

    written = write_people_files(rows, repo_root=repo_root, sources=sources)

    ingested_date = (ingested_at or fetched.isoformat()).split("T", 1)[0]
    inventory_path = upsert_inventory_entry(
        repo_root=repo_root,
        election_id=election_id,
        state=state,
        source_input=source_input,
        ingested_at=ingested_date,
        discrepancy_summary={
            "acs_total": report.acs_total,
            "acs_with_mismatch": report.acs_with_mismatch,
            "coverage_pct": round(report.coverage_pct, 4),
            "mean_delta_pp": round(report.mean_delta_pp, 4),
            "halted": report.halted,
        },
    )

    return IngestResult(
        people_written=len(written),
        inventory_path=inventory_path,
        report_path=report_path,
        report=report,
    )
