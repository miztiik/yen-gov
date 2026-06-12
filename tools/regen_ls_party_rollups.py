"""One-shot regen tool: backfill per-(state, LS event, party) rollup rows.

Closes ``ls_history.vote_share_pct == null`` + ``ls_history.contested == null``
honest-degradation per
``docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md``
PR-4 closure-ledger known-degradation #1.

Why a one-shot tool rather than a pipeline path: the X1a-fu2-D commit
(``bfa9aef2a``, 2026-06-07) retired the elections-family per-state observation
writer (the partitioned ``election_results.parquet`` shards) and transcoded
the surviving rows to ``datasets/data/datapoints/electoral/<slug>_election_results.csv``
via a one-time mechanical rip (the now-deleted
``tools/rip_election_results_to_csv.py``). The canonical writer's
``_emit_observations`` short-circuits to 0 for ``family == "elections"`` and
no replacement per-state CSV writer landed alongside the retirement. The
documented intent ("fastest rip-and-replace, OK to break the app temporarily
and fix by end of PR") was never followed up.

This tool re-applies the same rip-and-replace shape, narrowed to (a) the 6 LS
cycles supported by the in-tree event registry and (b) the NEW party-/state-
rollup rows emitted by ``parliament_rollup_observations`` (added in the
LS-aggregate-ingest PR, 2026-06-13). It:

  1. For each LS event in ``EVENT_BY_GE_YEAR``: builds a BatchEnvelope via
     ``eci_ls.build_pc_envelope_from_tcpd`` (drives the parser + the new
     rollup hook in ``_envelope_from_results``).
  2. Filters ``envelope.observation_rows`` to the rollup outputs only
     (entity_id matches one of the two LS rollup shapes:
     ``IN-S<NN>-Ls...-PARTY-<SHORT>`` for party-* rows and ``IN-S<NN>-Ls...$``
     for state-* rows).
  3. Groups by state slug (derived from the ECI state code via
     ``eci_to_lgd_slug``).
  4. For each state slug, upserts the new rows into
     ``datasets/data/datapoints/electoral/<slug>_election_results.csv`` on
     PK ``(entity_id, period_label, indicator_id)`` (the column contract at
     ``datasets/data/_schema/columns.json``) and writes back deterministically
     (sorted by all 9 columns; same 9-column shape as the original rip).

Atomic write: temp file in the same directory + ``os.replace``, matching the
``emit_state_csv_from_data`` pattern.

Usage:

    python -m yen_gov.canonical.reingest._run_parliament_results --delim 4   # source CSVs must exist
    python tools/regen_ls_party_rollups.py                                   # this tool
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug  # noqa: E402
from yen_gov.canonical.adapters.eci.identity import (  # noqa: E402
    Period,
    parse_period_label,
)
from yen_gov.canonical.adapters.eci.rollups import (  # noqa: E402
    PCContestSummary,
    parliament_rollup_observations,
)
from yen_gov.canonical.adapters.eci_ls import (  # noqa: E402
    EVENT_BY_GE_YEAR,
    build_pc_envelope,
    build_pc_envelope_from_tcpd,
)
from yen_gov.canonical.seed.reservation_sources import (  # noqa: E402
    SLUG_TO_ECI_STATE_CODE,
)

# Citizen-facing per-state CSV dir + 9-column shape (X1a-fu2-D transcode).
CSV_DIR = REPO_ROOT / "datasets" / "data" / "datapoints" / "electoral"
COLUMNS = (
    "entity_id",
    "year",
    "period_label",
    "period_seq",
    "indicator_id",
    "value_numeric",
    "value_text",
    "source_id",
    "derivation",
)

# CSV inputs the parsers need.
TCPD_GE_CSV = REPO_ROOT / "datasets" / "ephemeral" / "All_States_GE.csv"
ECI_2024_RAW_CSV = REPO_ROOT / "datasets" / "ephemeral" / (
    "2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv"
)
ECI_2024_CROSSWALK = REPO_ROOT / "datasets" / "elections" / "_crosswalks" / "ls_2024_pc_to_ac.csv"


def _is_rollup_entity(entity_id: str) -> bool:
    """True for state-rollup (``IN-S22-LsGen...``) or party-rollup
    (``IN-S22-LsGen...-PARTY-DMK``) ids."""
    if not entity_id.startswith("IN-"):
        return False
    parts = entity_id.split("-")
    if len(parts) < 3:
        return False
    # IN-<state>-<period> = 3 segments (state-rollup, no PARTY tail)
    # IN-<state>-<period>-PARTY-<short> = 5+ segments
    if len(parts) == 3:
        return True
    return len(parts) >= 5 and parts[3] == "PARTY"


def _state_slug_from_rollup_id(entity_id: str) -> str | None:
    """Extract LGD state slug from a rollup entity_id.

    ``IN-S22-LsGenMay2024-PARTY-DMK`` -> ``tamil-nadu``.
    """
    parts = entity_id.split("-")
    if len(parts) < 3:
        return None
    state_code = parts[1]
    try:
        return eci_to_lgd_slug(state_code)
    except (KeyError, ValueError):
        return None


def _read_existing_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read the per-state CSV. Returns (header, rows). Empty when file missing."""
    if not path.is_file():
        return list(COLUMNS), []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or COLUMNS)
        return header, list(reader)


def _row_pk(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["entity_id"], row["period_label"], row["indicator_id"])


def _obs_to_csv_row(obs) -> dict[str, str]:
    """Project ObservationRow -> 9-column dict matching the on-disk schema."""
    return {
        "entity_id": obs.entity_id,
        "year": str(obs.year),
        "period_label": obs.period_label,
        "period_seq": str(obs.period_seq),
        "indicator_id": obs.indicator_id,
        "value_numeric": ("" if obs.value_numeric is None
                          else _fmt_number(obs.value_numeric)),
        "value_text": "" if obs.value_text is None else obs.value_text,
        "source_id": obs.source_id,
        "derivation": "" if obs.derivation is None else obs.derivation,
    }


def _fmt_number(v: float) -> str:
    """Match the on-disk number format from the X1a-fu2-D parquet->CSV rip.

    The original rip used pandas/DuckDB COPY which preserves the float
    representation (e.g. ``24.0`` stays ``"24.0"``, not collapsed to ``"24"``).
    We mirror that to keep the file format byte-consistent with the existing
    AC rollup rows already on disk.
    """
    if isinstance(v, float):
        return str(v)
    if isinstance(v, int):
        return f"{float(v)}"
    return str(v)


def _sort_key(row: dict[str, str]) -> tuple:
    """Deterministic sort key on the same 4 cols the writer used."""
    return (
        row["indicator_id"],
        row["entity_id"],
        int(row["year"]) if row["year"] else 0,
        int(row["period_seq"]) if row["period_seq"] else 0,
    )


def _atomic_write(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".elx-", suffix=".csv", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _upsert_per_state_csv(
    state_slug: str,
    new_rows: list[dict[str, str]],
) -> tuple[int, int]:
    """Upsert ``new_rows`` into ``<state_slug>_election_results.csv``.

    Returns ``(added_count, replaced_count)`` for the operator log.
    """
    path = CSV_DIR / f"{state_slug}_election_results.csv"
    header, existing = _read_existing_csv(path)
    if not header:
        header = list(COLUMNS)
    new_pks = {_row_pk(r) for r in new_rows}
    replaced = sum(1 for r in existing if _row_pk(r) in new_pks)
    kept = [r for r in existing if _row_pk(r) not in new_pks]
    merged = kept + new_rows
    merged.sort(key=_sort_key)
    _atomic_write(path, header, merged)
    added = len(new_rows) - replaced
    return added, replaced


def _envelope_for_event(year: int):
    """Build the BatchEnvelope for one LS event via the appropriate parser."""
    event = EVENT_BY_GE_YEAR[year]
    datasets_root = REPO_ROOT / "datasets"
    if event.source_input_id == "tcpd_ge":
        if not TCPD_GE_CSV.is_file():
            raise FileNotFoundError(f"TCPD GE CSV not found: {TCPD_GE_CSV}")
        envelope, pc_count, _unresolved = build_pc_envelope_from_tcpd(
            datasets_root=datasets_root,
            csv_path=TCPD_GE_CSV,
            year=year,
            event=event,
            allow_unknown_parties=True,
        )
        return envelope, pc_count
    if event.source_input_id == "eci_ls":
        if not ECI_2024_RAW_CSV.is_file():
            raise FileNotFoundError(
                f"ECI 2024 raw CSV not found at {ECI_2024_RAW_CSV}; "
                "skip LS2024 regen (it is the only event using eci_ls)."
            )
        envelope, pc_count, _unresolved = build_pc_envelope(
            datasets_root=datasets_root,
            csv_path=ECI_2024_RAW_CSV,
            crosswalk_path=ECI_2024_CROSSWALK,
            allow_unknown_parties=True,
            event=event,
        )
        return envelope, pc_count
    raise ValueError(f"Unknown source_input_id: {event.source_input_id!r}")


def _rollup_rows_from_candidacies(year: int) -> tuple[list, int]:
    """Build rollup ObservationRows from ``datasets/elections/parliament/election=<year>/candidacies.csv``.

    Fallback path for events whose upstream source CSV is not in the worktree
    (e.g. LS2024 needs the ECI Statement-33 raw which isn't always available).
    The candidacies.csv file is the post-ingest snapshot — it carries
    per-candidate ``party_id`` + ``votes`` + ``vote_share_pct`` + ``result``
    + ``source_id`` + ``state`` (LGD slug) + ``constituency_no`` (pc_no).

    Limitation: ``electors`` is not in candidacies.csv, so the state-*
    ``electors-total`` + ``turnout-pct`` rows are skipped (they require a
    JOIN to the pc_dim_rows table which lives elsewhere on disk). Party-*
    rows + the state-* indicators that DO have inputs available
    (votes-polled, nota-pct, majority-threshold-acs, winning-party-id,
    winning-party-seats, effective-parties-laakso) are emitted normally.
    """
    cand_path = (
        REPO_ROOT / "datasets" / "elections" / "parliament"
        / f"election={year}" / "candidacies.csv"
    )
    if not cand_path.is_file():
        raise FileNotFoundError(cand_path)

    event = EVENT_BY_GE_YEAR[year]
    period = event.period
    delim_year = event.delim_year

    # Group candidacy rows by (state_slug, pc_no).
    by_pc: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    with cand_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            slug = r.get("state") or ""
            pc_no_raw = r.get("constituency_no") or ""
            if not slug or not pc_no_raw:
                continue
            try:
                pc_no = int(pc_no_raw)
            except ValueError:
                continue
            by_pc[(slug, pc_no)].append(r)

    # Build PCContestSummary per PC, group by state.
    by_state: dict[str, list[PCContestSummary]] = defaultdict(list)
    skipped_unmapped_slug = set()
    for (slug, pc_no), rows in by_pc.items():
        state_code = SLUG_TO_ECI_STATE_CODE.get(slug)
        if state_code is None:
            skipped_unmapped_slug.add(slug)
            continue

        # Identify NOTA + non-NOTA.
        nota_votes = 0
        non_nota: list[dict[str, str]] = []
        for r in rows:
            if (r.get("party_id") or "").endswith(".NOTA"):
                try:
                    nota_votes += int(r.get("votes") or 0)
                except ValueError:
                    pass
                continue
            non_nota.append(r)
        if not non_nota:
            continue

        # Aggregate party totals + ballot set + forfeitures.
        votes_by_party: dict[str, int] = defaultdict(int)
        on_ballot: set[str] = set()
        forfeitures_by_party: dict[str, int] = defaultdict(int)
        winner_pid: str | None = None
        winner_votes = -1
        votes_polled = 0
        first_source_id: str | None = None
        for r in non_nota:
            pid = r.get("party_id") or ""
            if not pid.startswith("parties."):
                continue
            try:
                v = int(r.get("votes") or 0)
            except ValueError:
                v = 0
            try:
                share = float(r.get("vote_share_pct") or 0)
            except ValueError:
                share = 0.0
            position = (r.get("position") or "").strip()
            result_field = (r.get("result") or "").strip()
            sid = r.get("source_id") or ""
            if first_source_id is None and sid:
                first_source_id = sid

            votes_by_party[pid] += v
            on_ballot.add(pid)
            votes_polled += v
            if share < 16.67:
                forfeitures_by_party[pid] += 1
            if result_field == "won" or position == "1":
                if v > winner_votes:
                    winner_votes = v
                    winner_pid = pid

        if winner_pid is None or first_source_id is None:
            continue

        votes_polled += nota_votes  # state turnout includes NOTA

        summary = PCContestSummary(
            state_code=state_code,
            eci_no=pc_no,
            delim_year=delim_year,
            period=period,
            total_electors=None,  # not in candidacies.csv -> state-* electors row skipped
            votes_polled=votes_polled,
            nota_votes=nota_votes,
            winner_party_id=winner_pid,
            source_id=first_source_id,
            votes_by_party=dict(votes_by_party),
            party_was_on_ballot=on_ballot,
            forfeitures_by_party=dict(forfeitures_by_party),
        )
        by_state[state_code].append(summary)

    if skipped_unmapped_slug:
        print(f"  WARN: {len(skipped_unmapped_slug)} state slugs without ECI code: "
              f"{sorted(skipped_unmapped_slug)[:5]}...")

    rollup_rows = []
    for state_summaries in by_state.values():
        rollup_rows.extend(parliament_rollup_observations(summaries=state_summaries))
    pc_count = sum(len(v) for v in by_pc.values())
    return rollup_rows, pc_count


def main(years: list[int] | None = None) -> int:
    target_years = years or sorted(EVENT_BY_GE_YEAR.keys())
    print(f"Regenerating LS party rollups for {target_years}")
    grand_total_added = 0
    grand_total_replaced = 0
    for year in target_years:
        event = EVENT_BY_GE_YEAR[year]
        print(f"\n=== {year} ({event.period.period_label}, source={event.source_input_id}) ===")
        rollup_rows: list = []
        pc_count = 0
        try:
            envelope, pc_count = _envelope_for_event(year)
            rollup_rows = [
                r for r in envelope.observation_rows
                if _is_rollup_entity(r.entity_id)
            ]
            print(f"  PCs parsed (envelope): {pc_count}; rollup rows: {len(rollup_rows)}")
        except FileNotFoundError as exc:
            print(f"  envelope path unavailable: {exc}")
            print(f"  -> falling back to candidacies.csv rebuild")
            try:
                rollup_rows, pc_count = _rollup_rows_from_candidacies(year)
                print(f"  PCs parsed (candidacies): {pc_count}; rollup rows: {len(rollup_rows)}")
            except FileNotFoundError as exc2:
                print(f"  SKIP: {exc2}")
                continue

        # Group by state slug.
        by_state: dict[str, list[dict[str, str]]] = defaultdict(list)
        skipped_no_slug = 0
        for r in rollup_rows:
            slug = _state_slug_from_rollup_id(r.entity_id)
            if slug is None:
                skipped_no_slug += 1
                continue
            by_state[slug].append(_obs_to_csv_row(r))

        if skipped_no_slug:
            print(f"  WARN: {skipped_no_slug} rollup rows skipped (no LGD slug for state code)")

        year_added = 0
        year_replaced = 0
        for slug in sorted(by_state):
            added, replaced = _upsert_per_state_csv(slug, by_state[slug])
            year_added += added
            year_replaced += replaced
            print(f"    {slug:>30}: +{added:>4} added, {replaced:>4} replaced")
        print(f"  total: +{year_added} added, {year_replaced} replaced across {len(by_state)} states")
        grand_total_added += year_added
        grand_total_replaced += year_replaced

    print(f"\n=== GRAND TOTAL: +{grand_total_added} added, {grand_total_replaced} replaced ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
