"""Hand-author Wikipedia-derived overrides on parties.csv (PR-W-3).

Idempotent one-shot script for the per-row identity edits that the
mechanical adapter cannot apply (its enrich leg is fill-empty-only,
per CLAUDE.md section 10 "auto-correct BANNED on publisher
disagreement").

PR-W-3 mints policy
-------------------

The PR-W-3 adapter run produced 8 ``UNVERIFIED + mint-new`` rows in
the verdict.csv (parties Wikipedia knows about but the canonical
parties.csv lacks under that ``parties.IN.<SLUG>`` id). Per the
brief's recommended default ("mint-new rare; Hans 33 + Q7 splits
done"), and per CLAUDE.md section 10 (auto-correct BANNED), PR-W-3
DEFERS all 8 candidate mints to a future curator-led PR (the
candidates are recorded below for the next session's hand-curation).

The 8 mint-new candidates (preserved verbatim from the 2026-06 verdict.csv
for the next curator):

  1. ``parties.IN.HJC`` (Haryana Janhit Congress) - Bhajan Lal Bishnoi's
     defunct regional party (founded 2007).
  2. ``parties.IN.HSP`` (Hindustani Awam Morcha - Secular) - Jitan Ram
     Manjhi's BR-recognised party (founded 2015 split from JDU).
  3. ``parties.IN.JKPC`` (J&K People's Conference) - Sajad Lone's
     JK-recognised party (founded 1978).
  4. ``parties.IN.JNP`` (Janata Party) - HISTORIC 1977-1988 national
     party (predecessor to JD lineage). NOTE: parties.IN.JP already
     exists as the same entity under a different slug; this mint
     candidate is a DUPLICATE-SLUG case and should be RESOLVED as
     an alias of JP, NOT a separate row.
  5. ``parties.IN.KEC_M`` (Kerala Congress (M)) - Mani faction of KEC
     (founded 1979 split).
  6. ``parties.IN.MUL`` (Muslim League Kerala State Committee) - LEGACY
     SLUG for IUML Kerala body. Resolve as IUML alias, NOT a separate
     row.
  7. ``parties.IN.NCP_K`` (Nationalist Congress Kerala) - 2024 KL-local
     split, parallel to NCP / NCP_SP Q7 logic but smaller in citizen
     visibility. Genuine mint candidate.
  8. ``parties.IN.NPEP`` (NPP Meghalaya regional precursor) - Same
     lineage as parties.IN.NPP; legacy slug. Resolve as NPP alias,
     NOT a separate row.

Net per-candidate disposition (proposed):

  - **Mint**: HJC, HSP, JKPC, KEC_M, NCP_K (5 genuine new identities).
  - **Alias of existing**: JNP -> JP (alias-add), MUL -> IUML (alias-add),
    NPEP -> NPP (alias-add).

PR-W-3 ships ZERO of these (defers to a follow-up curator session).
The next curator MAY run a hand-written sister script under
``tools/recon_curate_wikipedia_parties/mint_followups.py`` or extend
this file with explicit ``_HANS_MINTS`` + ``_HANS_EDITS`` lists
mirroring PR-W-1 + PR-W-2 patterns. Each edit MUST cite a Wikipedia
URL + a 1-paragraph justification.

PR-W-3 hand-edits policy
------------------------

PR-W-3 ships ZERO hand-edits. The Q1-owned Wikipedia enrichments
(brand_colour, symbol_asset, wikipedia URL, name_native_script) are
applied via the mechanical fill-empty-only path in the curator
``__main__.py``. There are NO Wikipedia values that contradict an
existing canonical Q1-owned cell in the 2026-06 snapshot (the
adapter's ``_has_disputed_overwrite`` guard emitted 0 conflict rows
in the verdict; ``verdicts: VERIFIED=70, DISPUTED=0, UNVERIFIED=8``).
The SDF / MNS / NTK colour DEFERRED notes in the snapshot rows
elected to LEAVE the brand_colour cell empty rather than declare a
contradiction; the canonical authored values stand.

Run from the repo root (dry-run by default; --apply writes):

    python -m tools.recon_curate_wikipedia_parties.hans_mints --apply

(In PR-W-3 this script is a no-op stub - the mint + edit lists are
empty by design. Future curators populate the lists per the
disposition above and re-run with --apply.)
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


#: Lineage / flip edits the Wikipedia adapter cannot mechanically apply.
#: Empty in PR-W-3 by design (see module docstring).
_HANS_EDITS: list[tuple[str, dict[str, str]]] = []


#: Mint-new rows the Wikipedia adapter surfaced as UNVERIFIED.
#: Empty in PR-W-3 by design (see module docstring "PR-W-3 mints policy").
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

    # Apply edits (overwrite-when-different). Empty in PR-W-3.
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

    # Apply mints (idempotent: skip if id already present). Empty in PR-W-3.
    for mint in _HANS_MINTS:
        pid = mint["party_id"]
        if pid in by_pid:
            mints_skipped.append(pid)
            continue
        rows.append(mint)
        mints_applied.append(pid)

    # Re-sort parties.csv by party_id when mints added (matches the
    # writer-chain convention). Empty in PR-W-3.
    if mints_applied:
        rows.sort(key=lambda r: (r.get("party_id") or "").strip())

    if args.apply and (edits_applied or mints_applied):
        _write_csv(PARTIES_CSV, fieldnames, rows)

    print(f"[hans-mints-wikipedia] parties.csv = {PARTIES_CSV.as_posix()}")
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
            "  PR-W-3 design: no Wikipedia overrides + no Wikipedia mints.\n"
            "  See module docstring for the 8 mint-new candidates deferred\n"
            "  to a future curator-led PR."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
