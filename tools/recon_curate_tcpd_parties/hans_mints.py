"""Hand-author Hans 33-case lineage rows + mints on parties.csv (PR-W-1).

Idempotent one-shot script for the lineage / lineage-link items the
TCPD parity adapter cannot mechanically discover:

  - **Set predecessor_party_ids on AMMK** = parties.IN.AIADMK (Sasikala
    wing 2018 breakaway; canonical AMMK row already present).

  - **Set predecessor_party_ids on AIFB(S)** = parties.IN.AIFB
    (Subhasist faction; canonical AIFB_S row already present).

  - **Enrich parties.IN.JP** = Janata Party canonical row (full name,
    founded_year=1977, dissolved_year=1988, predecessor=BJS, successors
    =BJP|JD). The pre-1980 Janata Party is the canonical home for pre-
    BJP votes per Hans rule (NEVER backtag pre-1980 votes as BJP). The
    canonical row ``parties.IN.JP`` already exists with aliases
    ``JANATA PARTY|JAP|JNP|JNP (JP)`` (TCPD-curator-enriched), so we
    DO NOT mint a new ``parties.IN.JNP``  - that would collide with the
    JNP alias on parties.IN.JP and the resolver would fail-loud.

  - **Set successor_party_ids on BJS** = parties.IN.JP|parties.IN.BJP
    (Jana Sangh -> Janata Party 1977 merger -> BJP 1980 founding).

  - **Set predecessor_party_ids on BJP** = parties.IN.JP.

  - **Set successor_party_ids on JD** = parties.IN.JDU|parties.IN.JDS|
    parties.IN.RJD|parties.IN.BJD|parties.IN.LJP|parties.IN.SP
    (Janata Dal 1988 -> the major regional parties of the 1990s).

  - **Set predecessor_party_ids on JDU/JDS/RJD/BJD/LJP/SP** = parties.IN.JD.

Sources:
  - TCPD parties catalogue (src-4040a970f10c, added by recon_curate).
  - Hans 33-case catalogue verdicts (Wave 0 / Hans section 1, plan-doc
    section 3 PR-W-1 brief item 6).
  - Standard Indian political-party historiography (well-documented
    non-controversial lineages).

Run from the repo root (dry-run by default; --apply writes):

    python -m tools.recon_curate_tcpd_parties.hans_mints --apply

Run AFTER ``python -m tools.recon_curate_tcpd_parties --apply`` so the
TCPD source_id citation row is already in source.csv AND the
parties.IN.JP aliases column carries the JNP / JAP / JNP (JP) variants.
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


#: Lineage edits the TCPD adapter cannot mechanically discover.
#: Each tuple: (party_id, {field: value, ...}). Applied fill-or-overwrite-
#: when-different: lineage fields are first-class identity contracts and
#: the operator's authoritative call overrides any prior cell content
#: (unlike the fill-empty-only enrich leg in the parity curator).
_HANS_LINEAGE_EDITS: list[tuple[str, dict[str, str]]] = [
    # AMMK (Amma Makkal Munnetra Kazhagam) - Sasikala wing 2018 breakaway.
    (
        "parties.IN.AMMK",
        {"predecessor_party_ids": "parties.IN.AIADMK"},
    ),
    # AIFB(S) - Subhasist faction of AIFB.
    (
        "parties.IN.AIFB_S",
        {"predecessor_party_ids": "parties.IN.AIFB"},
    ),
    # BJS (Bharatiya Jana Sangh) - 1951-1977; merged into Janata Party 1977.
    (
        "parties.IN.BJS",
        {
            "full": "Bharatiya Jana Sangh",
            "founded_year": "1951",
            "dissolved_year": "1977",
            "successor_party_ids": "parties.IN.JP|parties.IN.BJP",
        },
    ),
    # JP (Janata Party 1977-1988) - the canonical home for pre-1980 votes
    # that descend into BJP/JD. The canonical row already exists as a
    # sparse 'JP' slug; TCPD curator enriched aliases to include JANATA
    # PARTY|JAP|JNP|JNP (JP). Here we fill the identity metadata.
    (
        "parties.IN.JP",
        {
            "full": "Janata Party",
            "wikipedia": "https://en.wikipedia.org/wiki/Janata_Party",
            "founded_year": "1977",
            "dissolved_year": "1988",
            "predecessor_party_ids": "parties.IN.BJS",
            "successor_party_ids": "parties.IN.BJP|parties.IN.JD",
            "recognition_scope": "defunct",
        },
    ),
    # BJP (Bharatiya Janata Party) - founded 1980 from former Jana Sangh
    # members within the Janata Party. predecessor = parties.IN.JP per
    # Hans rule (NEVER backtag pre-1980 votes as BJP; they belong to JP
    # / BJS).
    (
        "parties.IN.BJP",
        {
            "predecessor_party_ids": "parties.IN.JP",
            "founded_year": "1980",
        },
    ),
    # JD (Janata Dal) - founded 1988 from the breakup of Janata Party.
    (
        "parties.IN.JD",
        {
            "full": "Janata Dal",
            "predecessor_party_ids": "parties.IN.JP",
            "successor_party_ids": (
                "parties.IN.JDU|parties.IN.JDS|parties.IN.RJD"
                "|parties.IN.BJD|parties.IN.LJP|parties.IN.SP"
            ),
            "founded_year": "1988",
        },
    ),
    # The 1990s-era regional descendants of Janata Dal.
    (
        "parties.IN.JDU",
        {
            "predecessor_party_ids": "parties.IN.JD",
            "founded_year": "1999",
        },
    ),
    (
        "parties.IN.JDS",
        {
            "predecessor_party_ids": "parties.IN.JD",
            "founded_year": "1999",
        },
    ),
    (
        "parties.IN.RJD",
        {
            "predecessor_party_ids": "parties.IN.JD",
            "founded_year": "1997",
        },
    ),
    (
        "parties.IN.BJD",
        {
            "predecessor_party_ids": "parties.IN.JD",
            "founded_year": "1997",
        },
    ),
    (
        "parties.IN.LJP",
        {
            "predecessor_party_ids": "parties.IN.JD",
            "founded_year": "2000",
        },
    ),
    (
        "parties.IN.SP",
        {
            "predecessor_party_ids": "parties.IN.JD",
            "founded_year": "1992",
        },
    ),
]


#: No fresh mints in this PR. The canonical roster ALREADY covers every
#: party named in the Hans 33-case catalogue (TVK present via TCPD slug
#: ``parties.IN.TVK``; AMMK present; AIFB / AIFB_S present; BJP / BJS /
#: JP / JD / JDU / JDS / RJD / BJD / LJP / SP all present). Verdict.csv
#: surfaces 1,734 additional UNVERIFIED mint-new candidates from TCPD
#: that are NOT in the Hans 33-case catalogue; those are deferred to a
#: separate curator pass (per CLAUDE.md section 10: hand-curation is the
#: only path for new mints).
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
    skipped_no_canonical: list[str] = []

    # Apply edits.
    for pid, payload in _HANS_LINEAGE_EDITS:
        row = by_pid.get(pid)
        if row is None:
            skipped_no_canonical.append(pid)
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

    # Apply mints (idempotent: skip if id already present).
    for mint in _HANS_MINTS:
        pid = mint["party_id"]
        if pid in by_pid:
            continue
        rows.append(mint)
        mints_applied.append(pid)

    # Re-sort parties.csv by party_id to keep deterministic order.
    if mints_applied:
        rows.sort(key=lambda r: (r.get("party_id") or "").strip())

    if args.apply and (edits_applied or mints_applied):
        _write_csv(PARTIES_CSV, fieldnames, rows)

    print(f"[hans-mints] parties.csv = {PARTIES_CSV.as_posix()}")
    print(f"  apply mode:                {args.apply}")
    print(f"  edits applied:             {len(edits_applied)}")
    for pid, log in edits_applied:
        print(f"    {pid}")
        for entry in log:
            print(f"      - {entry}")
    print(f"  new rows minted:           {len(mints_applied)}")
    for pid in mints_applied:
        print(f"    + {pid}")
    if skipped_no_canonical:
        print(f"  skipped (no canonical):    {len(skipped_no_canonical)}")
        for pid in skipped_no_canonical:
            print(f"    ? {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

