"""PR-3 corpus repair: substitute empty party_id with parties.IN.UNK or alias hit.

Run from the repo root:

    python -m tools.elections_party_id_repair --apply

Sweeps every ``datasets/elections/<assembly|parliament>/.../candidacies.csv``
and the sibling ``summary.csv``. For each row carrying an empty ``party_id``:

  1. Pass the row's ``party_short_raw`` through ``party_resolver.resolve(...)``.
     - Alias hit -> write the real ``parties.IN.<X>`` id.
     - Miss (including empty raw) -> write the ``parties.IN.UNK`` sentinel;
       ``party_short_raw`` is preserved verbatim (CLAUDE.md section 10 "no
       silent demotion").

  2. Rewrite the file in-place, preserving every other column byte-identical.

For ``summary.csv``: applies the same logic to ``winner_party_id``
(from ``winner_party_short_raw``) and ``runnerup_party_id``
(from ``runnerup_party_short_raw``). Because both files derive the same
``party_id`` value from the same ``party_short_raw`` string, the
``summary == recompute(candidacies)`` parity invariant holds row-for-row.

The fix at the writer seam (PR-3 v1.2, 4 ``backend/yen_gov/canonical/reingest/``
modules) prevents NEW empty-``party_id`` rows from being emitted; this script
backfills the historical on-disk corpus to the post-fix contract so the
Tier-A FK closure test (``test_party_id_fk_closure``) can flip from xfail
to strict.

Dry-run (default) prints stats without touching files; pass ``--apply`` to
write.

Use ``--reresolve-unk`` to ALSO retry the ``parties.IN.UNK`` fallback rows
when new aliases have been added to parties.csv (e.g. after PR-W-1's TCPD
enrichment lifts 1,500+ previously-unresolved publisher labels into the
resolver). Without this flag the tool only handles empty-party_id rows;
with it, both empty + UNK paths get re-resolved through the current alias
table. Per Wave 0 / Hans rule ("no silent demotion"), UNK rows that still
fail to resolve are LEFT as UNK (the party_short_raw is preserved for
citizen UI fallback).
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

# Allow ``python tools/...`` from repo root without setting PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.party_resolver import load_resolver, UNK


CANDIDACY_PID_COL = "party_id"
CANDIDACY_RAW_COL = "party_short_raw"
SUMMARY_WPID_COL = "winner_party_id"
SUMMARY_WRAW_COL = "winner_party_short_raw"
SUMMARY_RPID_COL = "runnerup_party_id"
SUMMARY_RRAW_COL = "runnerup_party_short_raw"


def _candidacies_paths() -> list[Path]:
    assembly = sorted(
        (REPO_ROOT / "datasets" / "elections" / "assembly").glob(
            "state=*/election=*/candidacies.csv"
        )
    )
    parliament = sorted(
        (REPO_ROOT / "datasets" / "elections" / "parliament").glob(
            "election=*/candidacies.csv"
        )
    )
    return assembly + parliament


def _summary_paths() -> list[Path]:
    assembly = sorted(
        (REPO_ROOT / "datasets" / "elections" / "assembly").glob(
            "state=*/election=*/summary.csv"
        )
    )
    parliament = sorted(
        (REPO_ROOT / "datasets" / "elections" / "parliament").glob(
            "election=*/summary.csv"
        )
    )
    return assembly + parliament


def _read_csv_preserve_order(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write CSV with deterministic LF line terminator + no extra trailing comma."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fieldnames})
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")


def _repair_candidacy_row(
    row: dict[str, str],
    resolver,
    stats: dict,
    *,
    reresolve_unk: bool = False,
) -> bool:
    """Repair ``party_id`` if empty (or UNK when reresolve_unk=True).

    Returns True if the row was changed.

    The ``reresolve_unk`` flag is the PR-W-1 follow-up path: after new
    aliases are added to parties.csv, ``parties.IN.UNK`` rows whose
    ``party_short_raw`` now hits an alias get promoted to a real
    ``party_id``. UNK rows that still miss STAY UNK (Hans no-silent-
    demotion rule preserves the raw publisher label).
    """
    pid = (row.get(CANDIDACY_PID_COL) or "").strip()
    if pid != "" and not (reresolve_unk and pid == UNK):
        return False
    raw = (row.get(CANDIDACY_RAW_COL) or "").strip()
    resolved = resolver.resolve(party_short=raw, eci_code=None) if raw else UNK
    # No-op when reresolve_unk leaves an UNK as UNK (no actual cell change).
    if pid == resolved:
        return False
    row[CANDIDACY_PID_COL] = resolved
    if resolved == UNK:
        stats["unk_rows"] += 1
        if raw:
            stats["unresolved_labels"][raw] += 1
        else:
            stats["unk_no_raw_rows"] += 1
    else:
        stats["alias_rows"] += 1
        stats["alias_pids"][resolved] += 1
    return True


def _repair_summary_row(
    row: dict[str, str],
    resolver,
    stats: dict,
    *,
    reresolve_unk: bool = False,
) -> bool:
    """Repair winner_party_id + runnerup_party_id if empty (or UNK).

    Mirrors ``_repair_candidacy_row``'s ``reresolve_unk`` semantics for
    the two summary id columns; preserves the uncontested-seat carve-out
    on the runnerup column.
    """
    changed = False
    for pid_col, raw_col, kind in (
        (SUMMARY_WPID_COL, SUMMARY_WRAW_COL, "winner"),
        (SUMMARY_RPID_COL, SUMMARY_RRAW_COL, "runnerup"),
    ):
        if pid_col not in row:
            continue
        pid = (row.get(pid_col) or "").strip()
        if pid != "" and not (reresolve_unk and pid == UNK):
            continue
        raw = (row.get(raw_col) or "").strip()
        resolved = resolver.resolve(party_short=raw, eci_code=None) if raw else UNK
        if pid == resolved:
            continue
        # Summary's runnerup_party_id may legitimately be empty for an
        # uncontested seat (no runner-up exists). The candidacies for that
        # AC will have only one real row; if there's no runnerup, the
        # corresponding party_short_raw will also be empty AND the row
        # really should have no runnerup populated. Detect the uncontested
        # case by checking the sibling runnerup_candidate cell - if THAT
        # is also empty, leave both runnerup columns empty (don't fabricate
        # a runnerup with parties.IN.UNK where the publisher said there
        # wasn't one). Same logic doesn't apply to winner (every AC has a
        # winner).
        if kind == "runnerup" and not raw:
            runnerup_cand = (row.get("runnerup_candidate") or "").strip()
            if not runnerup_cand:
                # Uncontested seat: leave runnerup columns null. No row change.
                continue
        row[pid_col] = resolved
        changed = True
        bucket = stats.setdefault(kind, {
            "unk_rows": 0,
            "alias_rows": 0,
            "unresolved_labels": Counter(),
            "alias_pids": Counter(),
        })
        if resolved == UNK:
            bucket["unk_rows"] += 1
            if raw:
                bucket["unresolved_labels"][raw] += 1
        else:
            bucket["alias_rows"] += 1
            bucket["alias_pids"][resolved] += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply repairs to disk. Default is dry-run (stats only).",
    )
    parser.add_argument(
        "--reresolve-unk",
        action="store_true",
        help=(
            "Also retry parties.IN.UNK rows against the current alias "
            "table. PR-W-1 follow-up: after TCPD enrichment lifts new "
            "aliases into parties.csv, previously-UNK rows may now "
            "resolve to real party_ids."
        ),
    )
    args = parser.parse_args()

    resolver = load_resolver()

    cand_stats = {
        "files_scanned": 0,
        "files_changed": 0,
        "rows_scanned": 0,
        "rows_changed": 0,
        "alias_rows": 0,
        "unk_rows": 0,
        "unk_no_raw_rows": 0,
        "unresolved_labels": Counter(),
        "alias_pids": Counter(),
    }
    summ_stats: dict = {
        "files_scanned": 0,
        "files_changed": 0,
        "rows_scanned": 0,
        "rows_changed": 0,
    }

    for path in _candidacies_paths():
        cand_stats["files_scanned"] += 1
        fieldnames, rows = _read_csv_preserve_order(path)
        cand_stats["rows_scanned"] += len(rows)
        file_changed = False
        for row in rows:
            if _repair_candidacy_row(
                row, resolver, cand_stats, reresolve_unk=args.reresolve_unk
            ):
                cand_stats["rows_changed"] += 1
                file_changed = True
        if file_changed:
            cand_stats["files_changed"] += 1
            if args.apply:
                _write_csv(path, fieldnames, rows)

    for path in _summary_paths():
        summ_stats["files_scanned"] += 1
        fieldnames, rows = _read_csv_preserve_order(path)
        summ_stats["rows_scanned"] += len(rows)
        file_changed = False
        for row in rows:
            if _repair_summary_row(
                row, resolver, summ_stats, reresolve_unk=args.reresolve_unk
            ):
                summ_stats["rows_changed"] += 1
                file_changed = True
        if file_changed:
            summ_stats["files_changed"] += 1
            if args.apply:
                _write_csv(path, fieldnames, rows)

    print(f"{'APPLIED' if args.apply else 'DRY-RUN'} repair report:")
    print()
    print("Candidacies:")
    print(f"  files scanned: {cand_stats['files_scanned']}")
    print(f"  files changed: {cand_stats['files_changed']}")
    print(f"  rows scanned: {cand_stats['rows_scanned']}")
    print(f"  rows changed: {cand_stats['rows_changed']}")
    print(f"    via alias resolution: {cand_stats['alias_rows']}")
    print(f"    via parties.IN.UNK fallback: {cand_stats['unk_rows']}")
    print(f"      of which had empty party_short_raw: {cand_stats['unk_no_raw_rows']}")
    print(f"  distinct alias-resolved party_ids: {len(cand_stats['alias_pids'])}")
    print(f"  distinct unresolved publisher labels: {len(cand_stats['unresolved_labels'])}")
    if cand_stats["alias_pids"]:
        print()
        print("  Top 10 alias-resolved party_ids:")
        for pid, count in cand_stats["alias_pids"].most_common(10):
            print(f"    {count:5d}  {pid}")
    if cand_stats["unresolved_labels"]:
        print()
        print("  Top 30 unresolved publisher labels (defer to PR-W-1 TCPD bulk enrichment):")
        for label, count in cand_stats["unresolved_labels"].most_common(30):
            print(f"    {count:5d}  {label!r}")
    print()
    print("Summary:")
    print(f"  files scanned: {summ_stats['files_scanned']}")
    print(f"  files changed: {summ_stats['files_changed']}")
    print(f"  rows scanned: {summ_stats['rows_scanned']}")
    print(f"  rows changed: {summ_stats['rows_changed']}")
    for kind in ("winner", "runnerup"):
        bucket = summ_stats.get(kind)
        if not bucket:
            continue
        print(f"  {kind}:")
        print(f"    via alias resolution: {bucket['alias_rows']}")
        print(f"    via parties.IN.UNK fallback: {bucket['unk_rows']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
