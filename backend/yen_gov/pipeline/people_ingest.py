"""People-ingest orchestrator.

Composes the pure adapter (``yen_gov.sources.eci.people_panel``) with the
canonical-store writer (UPSERTs biographic columns into
``datasets/elections/dim_candidates.parquet`` schema v1.2), the elections
inventory (declarative "done and tested" gate), and the discrepancy
report (per-AC vote comparison against the canonical observations).

Public entry point: ``run_people_ingest``. The CLI in ``yen_gov.cli`` is a
thin wrapper around it.

PR-S.2 (canonical pivot 1.8f) replaced the per-candidate JSON sidecar
emit (3,983 files under ``datasets/people/<event>/<ac>/<slug>.json``) with
an UPSERT into ``dim_candidates``. The discrepancy gate
(``compare_winner_votes``) is preserved verbatim — it already reads the
canonical Parquet (PR-O.3b-main) and remains the named non-negotiable QA
gate for this adapter.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from yen_gov.core.io import write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.eci.people_panel import (
    PersonRow,
    group_by_ac,
    parse_panel,
    slugify,
)


INVENTORY_SCHEMA_FILE = "elections-inventory.schema.json"
CONFIG_SCHEMA_FILE = "elections-config.schema.json"

# Repo-relative paths the orchestrator owns.
INVENTORY_PATH_REL = ("datasets", "elections", "_inventory.json")
CONFIG_PATH_REL = ("config", "elections.json")
REPORTS_DIR_REL = (".runtime", "reports")
DIM_CANDIDATES_PATH_REL = ("datasets", "elections", "dim_candidates.parquet")

# ac_id format: "IN-S22-AC-2008-167" -> state="S22", ac_eci_no=167
_AC_ID_RE = re.compile(r"^IN-([SU]\d{2})-AC-\d+-(\d+)$")


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


def _load_canonical_ac_facts(
    *,
    repo_root: Path,
    election_id: str,
    state: str,
) -> dict[int, dict[str, int]]:
    """Read the canonical election_results.parquet for one (state, event)
    slice and return ``{ac_eci_no: {"winner_votes": int, "votes_polled": int}}``.

    The discrepancy gate (compare_winner_votes) used to read these two
    numbers per AC from per-state JSON shards under
    ``datasets/elections/<event>/<state>/results/<n>.json``. Those writers
    retired in PR-O.3b-main (TODO row ``1.8b-writers-b-main``); the
    canonical store is now the source of truth.

    Returns an empty dict when the canonical Parquet is missing or has no
    rows for this (state, event) slice — the discrepancy gate degrades to
    a silent skip exactly as it did when an on-disk JSON shard was absent.
    """
    import duckdb

    parquet_path = repo_root / "datasets" / "elections" / "election_results.parquet"
    if not parquet_path.is_file():
        return {}

    # Composite query: per AC, derive ``winner_votes`` (the winner candidate's
    # ``candidate-votes-polled`` row, joined via the AC's
    # ``ac-winner-candidate-id`` value_text pointer) and ``votes_polled`` (the
    # AC's ``ac-votes-polled`` row). Both filter on ``period_label = event_id``
    # and the entity_id pattern ``IN-<state>-AC-%`` so we don't accidentally
    # touch other states' rows.
    state_prefix = f"IN-{state}-AC-"
    sql = """
        WITH winners AS (
            SELECT
                CAST(regexp_extract(entity_id, '-([0-9]+)$', 1) AS INTEGER) AS ac_eci_no,
                value_text AS winner_entity_id
            FROM read_parquet(?)
            WHERE indicator_id = 'ac-winner-candidate-id'
              AND period_label = ?
              AND entity_id LIKE ? || '%'
        ),
        winner_votes AS (
            SELECT entity_id, CAST(value_numeric AS BIGINT) AS votes
            FROM read_parquet(?)
            WHERE indicator_id = 'candidate-votes-polled'
              AND period_label = ?
        ),
        ac_totals AS (
            SELECT
                CAST(regexp_extract(entity_id, '-([0-9]+)$', 1) AS INTEGER) AS ac_eci_no,
                CAST(value_numeric AS BIGINT) AS votes_polled
            FROM read_parquet(?)
            WHERE indicator_id = 'ac-votes-polled'
              AND period_label = ?
              AND entity_id LIKE ? || '%'
        )
        SELECT w.ac_eci_no, wv.votes AS winner_votes, tot.votes_polled
        FROM winners w
        LEFT JOIN winner_votes wv ON wv.entity_id = w.winner_entity_id
        LEFT JOIN ac_totals tot ON tot.ac_eci_no = w.ac_eci_no
        ORDER BY w.ac_eci_no
    """
    pp = str(parquet_path)
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            sql, [pp, election_id, state_prefix, pp, election_id, pp, election_id, state_prefix],
        ).fetchall()
    finally:
        con.close()

    out: dict[int, dict[str, int]] = {}
    for ac_eci_no, winner_votes, votes_polled in rows:
        entry: dict[str, int] = {}
        if winner_votes is not None:
            entry["winner_votes"] = int(winner_votes)
        if votes_polled is not None:
            entry["votes_polled"] = int(votes_polled)
        out[int(ac_eci_no)] = entry
    return out


def compare_winner_votes(
    rows_by_ac: dict[int, list[PersonRow]],
    *,
    election_id: str,
    state: str,
    repo_root: Path,
    thresholds: dict[str, dict[str, float]],
    source_input: str,
) -> DiscrepancyReport:
    """Compare the panel's winner-vote totals to the canonical election
    results parquet for this (state, event). Decides halt/warn per the
    thresholds.

    Reads ``datasets/elections/election_results.parquet`` via DuckDB.
    Pre-PR-O.3b-main this function walked per-AC JSON shards under
    ``datasets/elections/<event>/<state>/results/<n>.json`` — those
    writers have retired and the canonical store is the single source of
    truth for AC winner totals. The graceful "no comparison data" fallback
    is preserved: when the canonical Parquet has no rows for an AC, we
    count toward ``acs_total`` and skip the delta math.
    """
    canonical_facts = _load_canonical_ac_facts(
        repo_root=repo_root, election_id=election_id, state=state,
    )
    discrepancies: list[DiscrepancyEntry] = []
    acs_total = 0
    deltas_pp: list[float] = []
    for ac_code, rows in sorted(rows_by_ac.items()):
        acs_total += 1
        facts = canonical_facts.get(ac_code)
        eci_votes = facts.get("winner_votes") if facts else None
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
        votes_polled = facts.get("votes_polled") if facts else None
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


def upsert_candidate_bios(
    rows: Iterable[PersonRow],
    *,
    repo_root: Path,
) -> int:
    """Lift biographic fields from the panel into ``dim_candidates.parquet``.

    For each panel ``PersonRow``, looks up the matching ``dim_candidates``
    row by ``(state, election_id, ac_eci_no, slugify(name))`` and UPSERTs
    the row with bio columns populated. Long-tail panel rows that have no
    matching dim row (rank > top-N cutoff, NOTA, AC not yet ingested via
    a Section-10 adapter) are silently skipped — by design,
    ``dim_candidates`` only carries the top-N candidates per AC per
    ``docs/architecture/data/elections-indicators.md``. The bio enrichment
    is therefore additive on the existing canonical roster, never the
    creator of new candidate rows.

    Returns the count of dim rows actually upserted. Idempotent:
    re-running with identical inputs yields a byte-identical Parquet
    because ``_upsert_dim`` emits sorted COPY output keyed by
    ``candidate_id``.

    No-op (returns 0) when the canonical store is absent — the same
    graceful degradation the writer's ``_load_existing`` provides.
    """
    # Lazy imports: keeps the dependency on the canonical writer scoped
    # to the one function that needs it, matching the pattern in
    # tools/backfill_candidate_bios_from_people_json.py (the one-shot
    # tool this refactor supersedes).
    import duckdb

    from yen_gov.canonical.envelope import CandidateDimRow
    from yen_gov.canonical.writer import (
        _DIM_SPECS,
        _regenerate_manifest,
        _upsert_dim,
    )

    dim_parquet = repo_root.joinpath(*DIM_CANDIDATES_PATH_REL)
    if not dim_parquet.is_file():
        # No canonical roster yet; bio has nothing to enrich. Caller may
        # treat this as a soft no-op (the inventory entry still records
        # the ingest as done so re-runs short-circuit).
        return 0

    # Index input bio by join key. Last row wins on collision (within an
    # AC the panel may carry the same slug for ties; canonical resolves
    # this via ballot_serial on its end, but bio fields are identical for
    # the duplicate so last-wins is safe).
    bio_by_key: dict[tuple[str, str, int, str], PersonRow] = {}
    for r in rows:
        bio_by_key[(r.state, r.election_id, r.ac_code, r.candidate_slug)] = r

    # Load existing dim rows; project all v1.2 columns explicitly so a
    # downstream Pydantic validation surfaces any column drift as a hard
    # failure rather than a silent KeyError.
    con = duckdb.connect(":memory:")
    try:
        dim_rel = con.execute(
            f"SELECT * FROM read_parquet('{dim_parquet.as_posix()}') ORDER BY candidate_id"
        )
        cols = [d[0] for d in dim_rel.description]
        dim_rows_all = [dict(zip(cols, row)) for row in dim_rel.fetchall()]
    finally:
        con.close()

    BIO_COLS = (
        "sex", "age", "education", "profession", "constituency_type",
    )
    matched_payloads: list[dict] = []
    for r in dim_rows_all:
        m = _AC_ID_RE.match(r["ac_id"])
        if not m or not r["name"]:
            continue
        state, ac_eci_no = m.group(1), int(m.group(2))
        key = (state, r["period_label"], ac_eci_no, slugify(r["name"]))
        pr = bio_by_key.get(key)
        if pr is None:
            continue
        payload = {
            "candidate_id": r["candidate_id"],
            "ac_id": r["ac_id"],
            "period_label": r["period_label"],
            "ballot_serial": r["ballot_serial"],
            "name": r["name"],
            "party_id": r["party_id"],
            "rank": r["rank"],
            "source_id": r["source_id"],
            "party_short_raw": r.get("party_short_raw"),
            **{c: getattr(pr, c) for c in BIO_COLS},
            # party_type is not derived from the panel CSV; left NULL.
            "party_type": None,
        }
        # Validate (raises if any enum/range constraint trips).
        CandidateDimRow(**payload)
        matched_payloads.append(payload)

    if not matched_payloads:
        return 0

    spec = _DIM_SPECS["candidate"]
    n = _upsert_dim(
        out_path=dim_parquet,
        rows=matched_payloads,
        spec=spec,
        table_id="elections.dim_candidates",
    )
    _regenerate_manifest(repo_root / "datasets")
    return n


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
    bios_upserted: int
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
                bios_upserted=0,
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
    # source_name/source_authority are reserved for a later enrichment of
    # the canonical sources row; this slice writes bio into dim_candidates
    # without minting a new SourceRow (the candidate row already carries
    # the source_id from the Section-10 ingest that created the dim row).
    _ = (source_name, source_authority, source_url, fetched)

    bios = upsert_candidate_bios(rows, repo_root=repo_root)

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
        bios_upserted=bios,
        inventory_path=inventory_path,
        report_path=report_path,
        report=report,
    )
