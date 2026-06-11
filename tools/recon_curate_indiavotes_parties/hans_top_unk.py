"""Hand-author IndiaVotes-derived overrides on parties.csv (UNK enrichment).

Idempotent one-shot script for the per-row identity edits that the
mechanical adapter + curator cannot apply (alias-add fill-only,
mint-new only when IV catalogue knows the party). Operator-run only.

The DOMINANT path for the UNK-enrichment campaign is the mechanical
``tools.recon_curate_indiavotes_parties`` curator (which auto-applies
alias-add for ~50 verdicts and mint-new for ~150 verdicts from the
2026-06 snapshot). This script covers the long-tail cases where:

  1. The publisher label is a TRUE UNK that neither IndiaVotes nor
     Wikipedia knows about (zero-signal, leave as parties.IN.UNK).
  2. The publisher label maps to a Wikipedia-only party that IV did
     not catalogue (curator hand-mint with Wikipedia URL).
  3. IndiaVotes resolves the slug but to a DIFFERENT party than the
     publisher meant (e.g. publisher emits "RLM" intending Rashtriya
     Lok Morcha [Kushwaha 2023] but IV maps RLM -> Rashtriya
     Lokmanch). Curator hand-mints under the correct distinguishing
     slug + adds the original publisher label as an alias on the
     correct row.

Default behaviour: ``_HANS_EDITS`` + ``_HANS_MINTS`` empty. Re-running
with --apply is a no-op when the lists are empty (the dominant path
fixes the UNK rows via the mechanical curator + the elections_party_id_
repair --reresolve-unk sweep). Future curators populate the lists per
their hand-investigation of the residual UNK rows post-mechanical-sweep
and re-run with --apply.

Run from the repo root (dry-run by default; --apply writes):

    python -m tools.recon_curate_indiavotes_parties.hans_top_unk --apply

(In this PR's run the script is a no-op stub; ALL top-200 UNK label
enrichments are mechanically covered by the curator's mint-new branch.
The script ships so the next curator has the seam ready when a
brand-new long-tail emerges from a future election cycle.)
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: (row.get(k) or "") for k in fieldnames})
    path.write_text(buf.getvalue(), encoding="utf-8")


#: Lineage / flip edits the IV curator cannot mechanically apply.
#: Empty by default (see module docstring).
#:
#: Shape per entry: ``(party_id, {column_name: new_value, ...})``.
#: Re-applied byte-identically when the cell already carries the
#: new_value (idempotent re-run is a no-op).
_HANS_EDITS: list[tuple[str, dict[str, str]]] = []


#: Mint-new rows the IV curator cannot mechanically apply (e.g. IV does
#: not catalogue the party, but the curator has Wikipedia-confirmed
#: identity). Empty by default (see module docstring).
#:
#: Shape per entry: full parties.csv row dict (all 18 columns; empty
#: strings for cells the curator does not have).
_HANS_MINTS: list[dict[str, str]] = []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to parties.csv. Default is dry-run.",
    )
    args = ap.parse_args()

    fieldnames, rows = _read_csv(PARTIES_CSV)
    by_pid: dict[str, dict[str, str]] = {
        (r.get("party_id") or "").strip(): r for r in rows if r.get("party_id")
    }

    edits_applied: list[tuple[str, list[str]]] = []
    mints_applied: list[str] = []
    mints_skipped: list[str] = []
    edits_skipped_no_canonical: list[str] = []

    # Apply edits (overwrite-when-different). Empty by default.
    for pid, payload in _HANS_EDITS:
        row = by_pid.get(pid)
        if row is None:
            edits_skipped_no_canonical.append(pid)
            continue
        log: list[str] = []
        for k, v in payload.items():
            current = (row.get(k) or "").strip()
            if current == v:
                continue
            row[k] = v
            log.append(f"{k}={v!r} (was {current!r})")
        if log:
            edits_applied.append((pid, log))

    # Apply mints (idempotent: skip if id already present). Empty by default.
    for mint in _HANS_MINTS:
        pid = mint["party_id"]
        if pid in by_pid:
            mints_skipped.append(pid)
            continue
        rows.append(mint)
        mints_applied.append(pid)

    # Re-sort parties.csv by party_id when mints added.
    if mints_applied:
        rows.sort(key=lambda r: (r.get("party_id") or "").strip())

    if args.apply and (edits_applied or mints_applied):
        _write_csv(PARTIES_CSV, fieldnames, rows)

    print(f"[hans-top-unk] parties.csv = {PARTIES_CSV.as_posix()}")
    print(f"  apply mode:                {args.apply}")
    print(f"  edits applied:             {len(edits_applied)}")
    for pid, log in edits_applied:
        print(f"    {pid}:")
        for entry in log:
            print(f"      - {entry}")
    if edits_skipped_no_canonical:
        print(f"  edits skipped (no canonical):  {len(edits_skipped_no_canonical)}")
        for pid in edits_skipped_no_canonical:
            print(f"    {pid}")
    print(f"  mints applied:             {len(mints_applied)}")
    for pid in mints_applied:
        print(f"    {pid}")
    if mints_skipped:
        print(f"  mints skipped (already present): {len(mints_skipped)}")
        for pid in mints_skipped:
            print(f"    {pid}")
    if not _HANS_EDITS and not _HANS_MINTS:
        print(
            "  UNK-enrichment PR: no IV-overriding mints + no IV-overriding edits.\n"
            "  Mechanical mint path covers the 2026-06 snapshot's top-200 UNK\n"
            "  label cohort. See the curator __main__.py for the dispatch."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
