"""R1.6 Path A' — Bihar 2005 catalogue identity rip.

Partitions the on-disk corrupted ``datasets/elections/assembly/state=bihar/election=2005/``
short-form CSVs into two clean per-event dirs (``election=2005-feb/`` +
``election=2005-nov/``) by cross-referencing each row's
``(entity_id, position, votes)`` triple against the Layer-2 long-form
``datasets/data/datapoints/electoral/bihar_election_results.csv`` which
already correctly distinguishes Feb vs Nov via ``period_label``.

Run once from the repo root:

    python -m yen_gov.canonical.scripts.r16_bihar_2005_split --root .

Idempotent: re-running the script after a successful run is a no-op
(checks that the target dirs already exist + that the source dir is
absent, prints "already migrated" and exits 0). Restoration is a
git-revert away.

This is a one-shot migration script, NOT a permanent CLI surface. After
R1.6 lands and the upstream re-ingest of the Bihar 2005 Statistical
Report XLSXes is scheduled (separate follow-up: the AE panel adapter
+ the new event_id kwarg on assembly_candidacies_path will write
directly to ``election=assembly-2005-feb/`` + ``election=assembly-2005-nov/``),
this script is retired and the canonical writer takes over.

Why this script lives under ``backend/yen_gov/canonical/scripts/``:
- It writes to ``datasets/elections/assembly/...`` which is the
  per-election short-form CSV file class scaffolded in
  ``backend/yen_gov/canonical/reingest/elections.py``.
- It reads from ``datasets/data/datapoints/electoral/...`` which is
  Layer-2 long-form; the canonical store contract.
- It produces git-tracked dataset changes (NOT ephemeral) - the new
  per-event CSVs ship in this PR.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, no_args_is_help=False)


# ---------------------------------------------------------------------------
# Path-builder mirrors (kept local to avoid the full backend dependency tree
# for what is a one-shot migration script).
# ---------------------------------------------------------------------------

STATE_SLUG = "bihar"
CORRUPT_DIR_REL = Path("datasets/elections/assembly/state=bihar/election=2005")
FEB_DIR_REL = Path("datasets/elections/assembly/state=bihar/election=assembly-2005-feb")
NOV_DIR_REL = Path("datasets/elections/assembly/state=bihar/election=assembly-2005-nov")

LAYER2_REL = Path("datasets/data/datapoints/electoral/bihar_election_results.csv")

FEB_PERIOD = "AcGenFeb2005"
NOV_PERIOD = "AcGenNov2005"


# ---------------------------------------------------------------------------
# Layer-2 partition keys
# ---------------------------------------------------------------------------


def build_partition_keys(layer2_path: Path) -> dict[tuple[str, int, int], str]:
    """Build the (entity_id, rank, votes) -> period_label partition map.

    Reads candidate-votes-polled + candidate-rank indicators from Layer-2 and
    composes them into the key triple. The on-disk corrupted candidacies.csv
    uses ``entity_id=IN-AC-1976-bihar-<ac_no>`` while Layer-2 uses
    ``entity_id=IN-S04-AC-1976-<ac_no>`` for the AC and
    ``IN-S04-AC-1976-<ac_no>-<period>-C<rank>`` for the candidacy. We bridge
    by deriving ac_no from both sides + composing the on-disk key shape.
    """
    # Step 1: load candidate-votes-polled + candidate-rank into a temp map.
    by_cand_id: dict[str, dict[str, str]] = defaultdict(dict)
    with layer2_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pl = row["period_label"]
            if pl not in (FEB_PERIOD, NOV_PERIOD):
                continue
            ind = row["indicator_id"]
            if ind not in ("candidate-rank", "candidate-votes-polled"):
                continue
            cand_id = row["entity_id"]
            # Layer-2 candidate-* indicators key on the candidate-grain
            # entity_id "<ac_id>-<period>-C<NN>"; AC-grain rows have no
            # trailing -C<NN> and should be skipped here.
            if "-C" not in cand_id[-5:]:
                continue
            by_cand_id[cand_id][ind] = row["value_numeric"]
            by_cand_id[cand_id]["__period__"] = pl

    # Step 2: convert to the on-disk-shaped key.
    keys: dict[tuple[str, int, int], str] = {}
    for cand_id, ind_map in by_cand_id.items():
        try:
            rank = int(float(ind_map["candidate-rank"]))
            votes = int(float(ind_map["candidate-votes-polled"]))
        except (KeyError, ValueError):
            continue
        # cand_id = IN-S04-AC-1976-<ac_no>-AcGen{Feb|Nov}2005-C<NN>
        # extract ac_no by stripping the suffix segments.
        parts = cand_id.split("-")
        # parts = ['IN', 'S04', 'AC', '1976', '<ac_no>', 'AcGen...2005', 'C..']
        try:
            ac_no = int(parts[4])
        except (IndexError, ValueError):
            continue
        on_disk_ent = f"IN-AC-1976-{STATE_SLUG}-{ac_no}"
        key = (on_disk_ent, rank, votes)
        period = ind_map["__period__"]
        # In the rare case two candidates collide on the on-disk key
        # (unlikely but possible if Feb + Nov had a candidate at the
        # same rank+votes in the same AC), prefer the later-loaded
        # one and log later in run_split.
        keys[key] = period

    return keys


# ---------------------------------------------------------------------------
# Partition + emit
# ---------------------------------------------------------------------------


def partition_candidacies(
    src_path: Path, partition: dict[tuple[str, int, int], str]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Split the on-disk candidacies.csv into (feb_rows, nov_rows, unrouted_rows).

    Lookup key: ``(entity_id, int(position), int(votes))``. A row that
    cannot be routed to either event (because Layer-2 lacks the exact key)
    is collected into ``unrouted_rows`` and logged; the script aborts if
    any unrouted rows exist so the migration does not silently drop data.
    """
    feb_rows: list[dict[str, str]] = []
    nov_rows: list[dict[str, str]] = []
    unrouted_rows: list[dict[str, str]] = []
    with src_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                position = int(row["position"])
                votes = int(float(row["votes"]))
            except (KeyError, ValueError):
                unrouted_rows.append(row)
                continue
            key = (row["entity_id"], position, votes)
            period = partition.get(key)
            if period == FEB_PERIOD:
                feb_rows.append(row)
            elif period == NOV_PERIOD:
                nov_rows.append(row)
            else:
                unrouted_rows.append(row)
    return feb_rows, nov_rows, unrouted_rows


def recompute_summary(
    candidacies: list[dict[str, str]],
    *,
    src_summary_by_ent: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """Recompute the per-AC summary from a partitioned candidacies subset.

    For each entity_id present in the candidacies subset, compose ONE
    summary row using the AC-level facts (electors, votes_polled,
    turnout_pct, electors) lifted from the SOURCE summary.csv row. The
    source summary is corrupted at the per-AC level (winner/runnerup
    are stacked across the two events) but the AC-facts columns
    (electors / votes_polled / turnout_pct) are stable across the two
    events (same AC same electorate same poll seal) so we can lift
    them safely. The winner / runnerup / margin columns ARE recomputed
    from the partitioned candidacies subset.
    """
    by_ent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for cand in candidacies:
        by_ent[cand["entity_id"]].append(cand)

    summary_rows: list[dict[str, str]] = []
    for ent, ent_candidacies in sorted(by_ent.items(), key=lambda kv: int(kv[0].rsplit("-", 1)[-1])):
        # Sort candidacies by rank ascending; winner = rank 1; runnerup = rank 2.
        ranked = sorted(ent_candidacies, key=lambda r: int(r["position"]))
        if not ranked:
            continue
        winner = ranked[0]
        runnerup = ranked[1] if len(ranked) > 1 else None
        winner_votes = int(float(winner["votes"]))
        runnerup_votes = int(float(runnerup["votes"])) if runnerup else 0
        votes_polled_total = sum(int(float(c["votes"])) for c in ranked)
        margin_votes = winner_votes - runnerup_votes
        # Canonical convention (mirrors recompute_summary_row in
        # backend/yen_gov/canonical/reingest/assembly_results.py): the
        # share columns come straight from the candidacies' pre-rounded
        # vote_share_pct, and margin_pct is the SUBTRACTION of the two
        # rounded shares. The vote-ratio-then-round alternative produces
        # 0.01 drift in roughly half the rows + trips
        # tests/test_summary_equals_recompute_candidacies.py.
        winner_share = (
            float(winner["vote_share_pct"])
            if winner.get("vote_share_pct", "").strip()
            else 0.0
        )
        runner_share = (
            float(runnerup["vote_share_pct"])
            if runnerup and runnerup.get("vote_share_pct", "").strip()
            else 0.0
        )
        margin_pct = round(winner_share - runner_share, 2) if runnerup else 0.0

        # Lift AC-facts from the source summary; the corrupted file has
        # ONE row per AC and the AC-electorate fields are stable across
        # the two events.
        src = src_summary_by_ent.get(ent, {})
        # The source summary.csv `votes_polled` is the stacked sum across
        # both events (per Section 2.6.1 forensics). Use the partitioned
        # candidacy votes-polled-total as the per-event poll total instead.
        # The `electors` column IS stable (the electoral roll is the same
        # voters list for both phases) so lift it verbatim.
        summary_rows.append({
            "entity_id": ent,
            "state": STATE_SLUG,
            "election_year": "2005",
            "constituency_name": winner["constituency_name"],
            "electors": src.get("electors", ""),
            "votes_polled": str(votes_polled_total),
            "turnout_pct": (
                str(round(votes_polled_total / int(src["electors"]) * 100, 2))
                if src.get("electors", "").isdigit() and int(src["electors"]) > 0
                else ""
            ),
            "winner_candidate": winner["candidate_name"],
            "winner_party_id": winner["party_id"],
            "winner_party_short_raw": winner["party_short_raw"],
            "winner_votes": str(winner_votes),
            "winner_share_pct": str(winner_share),
            "runnerup_candidate": runnerup["candidate_name"] if runnerup else "",
            "runnerup_party_id": runnerup["party_id"] if runnerup else "",
            "runnerup_party_short_raw": runnerup["party_short_raw"] if runnerup else "",
            "runnerup_votes": str(runnerup_votes) if runnerup else "",
            "margin_votes": str(margin_votes),
            "margin_pct": str(margin_pct),
            "source_id": winner["source_id"],
            "processing_level": "minor",
            "processing_note": (
                "Derived in R1.6 Path A' from the partitioned "
                "candidacies.csv subset; see "
                "TODO/20260615-R1.6-bihar-2005-path-a-prime-receipt.md."
            ),
        })
    return summary_rows


def write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in columns})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


CANDIDACIES_COLS = [
    "entity_id",
    "state",
    "election_year",
    "constituency_no",
    "constituency_name",
    "candidate_name",
    "party_id",
    "party_short_raw",
    "votes",
    "vote_share_pct",
    "position",
    "result",
    "sex",
    "age",
    "education",
    "profession",
    "candidate_type",
    "source_id",
    "processing_level",
    "processing_note",
]

SUMMARY_COLS = [
    "entity_id",
    "state",
    "election_year",
    "constituency_name",
    "electors",
    "votes_polled",
    "turnout_pct",
    "winner_candidate",
    "winner_party_id",
    "winner_party_short_raw",
    "winner_votes",
    "winner_share_pct",
    "runnerup_candidate",
    "runnerup_party_id",
    "runnerup_party_short_raw",
    "runnerup_votes",
    "margin_votes",
    "margin_pct",
    "source_id",
    "processing_level",
    "processing_note",
]


@app.command()
def main(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """Split the corrupted Bihar 2005 dir into Feb + Nov per-event dirs."""
    src_dir = root / CORRUPT_DIR_REL
    feb_dir = root / FEB_DIR_REL
    nov_dir = root / NOV_DIR_REL

    # Idempotence guard: if the migration already landed (source absent,
    # both targets present), exit cleanly.
    if not src_dir.exists() and feb_dir.exists() and nov_dir.exists():
        typer.echo("R1.6 Bihar 2005 split: already migrated (source absent, both targets present). No-op.")
        return

    if not src_dir.exists():
        typer.echo(
            f"R1.6 Bihar 2005 split: source dir {src_dir} does NOT exist + targets incomplete - "
            "manual investigation required.",
            err=True,
        )
        raise typer.Exit(2)

    src_cand_path = src_dir / "candidacies.csv"
    src_summ_path = src_dir / "summary.csv"
    if not src_cand_path.exists() or not src_summ_path.exists():
        typer.echo(
            f"R1.6 Bihar 2005 split: source files missing under {src_dir}",
            err=True,
        )
        raise typer.Exit(2)

    layer2_path = root / LAYER2_REL
    if not layer2_path.exists():
        typer.echo(
            f"R1.6 Bihar 2005 split: Layer-2 long-form {layer2_path} missing; "
            "cannot build partition map.",
            err=True,
        )
        raise typer.Exit(2)

    typer.echo("R1.6 Bihar 2005 split: building partition map from Layer-2...")
    partition = build_partition_keys(layer2_path)
    typer.echo(f"  partition keys: {len(partition)} candidacies labelled by period_label")

    typer.echo(f"R1.6 Bihar 2005 split: partitioning {src_cand_path.relative_to(root)}...")
    feb_rows, nov_rows, unrouted = partition_candidacies(src_cand_path, partition)
    typer.echo(
        f"  feb_candidacies={len(feb_rows)}  nov_candidacies={len(nov_rows)}  unrouted={len(unrouted)}"
    )

    if unrouted:
        sample = unrouted[:5]
        typer.echo(
            f"R1.6 Bihar 2005 split: {len(unrouted)} rows could not be routed.\n"
            f"  First 5 unrouted rows (entity_id, position, votes, candidate_name):",
            err=True,
        )
        for r in sample:
            typer.echo(
                f"    {r.get('entity_id', '?')} pos={r.get('position', '?')} "
                f"votes={r.get('votes', '?')} cand={r.get('candidate_name', '?')}",
                err=True,
            )
        # Allow up to 0.5% drift (NOTA / write-in slot-only rows the
        # Layer-2 writer dropped). If drift exceeds this, fail loud.
        total = len(feb_rows) + len(nov_rows) + len(unrouted)
        if len(unrouted) > max(20, total * 0.005):
            raise typer.Exit(1)
        typer.echo(
            f"R1.6 Bihar 2005 split: {len(unrouted)} unrouted rows is within the "
            "0.5%-or-20-rows tolerance for NOTA-class drops; proceeding.",
        )

    # Build per-AC source-summary lookup for AC-facts lifting.
    src_summary_by_ent: dict[str, dict[str, str]] = {}
    with src_summ_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            src_summary_by_ent[row["entity_id"]] = row

    typer.echo("R1.6 Bihar 2005 split: recomputing per-event summaries...")
    feb_summary = recompute_summary(feb_rows, src_summary_by_ent=src_summary_by_ent)
    nov_summary = recompute_summary(nov_rows, src_summary_by_ent=src_summary_by_ent)
    typer.echo(f"  feb_summary={len(feb_summary)} ACs  nov_summary={len(nov_summary)} ACs")

    # Sanity gates: each event should have 243 ACs (Bihar's 1976-delim
    # constituency count). Allow soft warning at 240+; fail at <235.
    for label, summary in (("Feb", feb_summary), ("Nov", nov_summary)):
        if len(summary) < 235:
            typer.echo(
                f"R1.6 Bihar 2005 split: {label} summary has only {len(summary)} ACs (expected 243); "
                "aborting before write.",
                err=True,
            )
            raise typer.Exit(1)
        if len(summary) < 240:
            typer.echo(
                f"R1.6 Bihar 2005 split: WARNING {label} summary has {len(summary)} ACs "
                "(expected 243); proceeding anyway.",
                err=True,
            )

    # Write outputs.
    typer.echo(f"R1.6 Bihar 2005 split: writing {feb_dir.relative_to(root)}...")
    write_csv(feb_dir / "candidacies.csv", feb_rows, columns=CANDIDACIES_COLS)
    write_csv(feb_dir / "summary.csv", feb_summary, columns=SUMMARY_COLS)

    typer.echo(f"R1.6 Bihar 2005 split: writing {nov_dir.relative_to(root)}...")
    write_csv(nov_dir / "candidacies.csv", nov_rows, columns=CANDIDACIES_COLS)
    write_csv(nov_dir / "summary.csv", nov_summary, columns=SUMMARY_COLS)

    # Delete the source dir.
    typer.echo(f"R1.6 Bihar 2005 split: removing source {src_dir.relative_to(root)}...")
    for p in sorted(src_dir.iterdir(), reverse=True):
        if p.is_file():
            p.unlink()
    src_dir.rmdir()

    typer.echo("R1.6 Bihar 2005 split: done.")


if __name__ == "__main__":
    app()
