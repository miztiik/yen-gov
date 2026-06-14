"""Backfill OWID-aligned ``processing_level`` + ``processing_note`` columns
on every existing election CSV under ``datasets/elections/{assembly,parliament}/``.

One-shot script (idempotent, re-runnable). Reads every per-event CSV
(candidacies.csv + summary.csv), appends two new columns if absent, and
populates them per the brief:

  - Default: ``processing_level = "minor"``, ``processing_note = ""``.
  - ``party_id == "parties.IN.UNK"``  -> major + UNK rationale.
  - ``party_id == "parties.IN.BJC"``  -> major + TCPD Party_ID 1411 note.
  - ``party_id == "parties.IN.KSP"``  -> major + TCPD Party_ID 4881 note.

Summary rows inherit the winner candidacy's processing tags (winner_party_id
gate). When the winner_party_id is null or unknown, summary defaults to
minor + empty.

Idempotency: a file is rewritten only when (a) the header is missing one of
the two new columns, OR (b) any row's processing tags do not match the
expected value (e.g. an UNK row that already shipped as minor before this
PR will be upgraded to major on re-run). The script emits a one-line
counter on stdout: ``Rewrote N files: M rows defaulted minor, K rows
tagged major.``.

Run with: ``python -m tools.backfill_processing_level`` from the repo root.
The script discovers ``datasets/`` relative to its own location so any cwd
works.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# Note templates (verbatim from the PR brief).
_UNK_NOTE_TEMPLATE = (
    "Publisher label '{label}' unmatched against TCPD/ECI catalogues; "
    "awaiting oracle resolution per "
    "datasets/_ops/unk-ledger-2026-06-12.csv."
)
_BJC_NOTE = (
    "TCPD Party_ID 1411 (Bharatiya Jan Congress). Publisher label 'BJC' "
    "resolved against TCPD 2026-06-14 catalogue; one of two TCPD "
    "candidates (1411 vs 9077) for the BJC abbreviation, disambiguated "
    "by Bihar 1993-2000 geographic+temporal evidence."
)
_KSP_NOTE = (
    "TCPD Party_ID 4881 (Kosal Party). Publisher label 'KSP' resolved "
    "against TCPD 2026-06-14 catalogue."
)

# LS years whose PC-level summary totals were derived by aggregating
# TCPD's per-AC ``All_States_GA.csv`` rows up to the PC grain (segment-
# approximate). The direct-PC TCPD CSV for these years is not published.
# 2024 onward ships from direct-PC TCPD CSVs and stays ``minor``.
TCPD_SOURCED_LS_YEARS = frozenset({1999, 2004, 2009, 2014, 2019})
_TCPD_SEGMENT_NOTE = (
    "PC summary derived from TCPD All_States_GA.csv (AC-segment "
    "aggregation to PC level); direct-PC TCPD CSV not published for "
    "this LS year."
)


def _is_tcpd_sourced_ls_year(year_str: str) -> bool:
    try:
        return int(year_str) in TCPD_SOURCED_LS_YEARS
    except (TypeError, ValueError):
        return False


def _expected_candidacy_tags(row: dict[str, str]) -> tuple[str, str]:
    """Return ``(processing_level, processing_note)`` for a candidacy row."""

    party_id = (row.get("party_id") or "").strip()
    if party_id == "parties.IN.UNK":
        label = (row.get("party_short_raw") or "").strip()
        return "major", _UNK_NOTE_TEMPLATE.format(label=label)
    if party_id == "parties.IN.BJC":
        return "major", _BJC_NOTE
    if party_id == "parties.IN.KSP":
        return "major", _KSP_NOTE
    return "minor", ""


def _expected_summary_tags(
    row: dict[str, str],
    *,
    chamber: str,
    election_year: str,
) -> tuple[str, str]:
    """Summary rows inherit from the winner_party_id, with one chamber-
    aware override: parliament summaries for the TCPD-sourced LS years
    (1999-2019) tag ``major`` with the segment-aggregation note because
    their PC totals were rolled up from per-AC rows. Per-row UNK / BJC /
    KSP gates win over the segment override so the original note is
    preserved."""

    party_id = (row.get("winner_party_id") or "").strip()
    if party_id == "parties.IN.UNK":
        # Summary doesn't carry party_short_raw on the winner gate; use the
        # bare label from winner_party_short_raw which the writer mirrors.
        label = (row.get("winner_party_short_raw") or "").strip()
        return "major", _UNK_NOTE_TEMPLATE.format(label=label)
    if party_id == "parties.IN.BJC":
        return "major", _BJC_NOTE
    if party_id == "parties.IN.KSP":
        return "major", _KSP_NOTE
    if chamber == "parliament" and _is_tcpd_sourced_ls_year(election_year):
        return "major", _TCPD_SEGMENT_NOTE
    return "minor", ""


def _process_file(path: Path, is_summary: bool) -> tuple[bool, int, int]:
    """Read ``path``, append the two new columns if needed, rewrite in place.

    Returns ``(rewrote, n_minor, n_major)``. ``rewrote`` is True iff the
    file body changed on disk.
    """

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        original_fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    has_level = "processing_level" in original_fieldnames
    has_note = "processing_note" in original_fieldnames

    # Derive (chamber, election_year) from the path. Path shape:
    #   datasets/elections/{assembly|parliament}/.../election=YYYY/<file>.csv
    chamber = ""
    election_year = ""
    for parent in path.parents:
        name = parent.name
        if name in ("assembly", "parliament"):
            chamber = name
        elif name.startswith("election="):
            election_year = name.split("=", 1)[1]

    if is_summary:
        def classify(row: dict[str, str]) -> tuple[str, str]:
            return _expected_summary_tags(
                row, chamber=chamber, election_year=election_year,
            )
    else:
        classify = _expected_candidacy_tags

    new_rows: list[dict[str, str]] = []
    n_minor = 0
    n_major = 0
    any_row_diff = False

    for row in rows:
        level, note = classify(row)
        if level == "major":
            n_major += 1
        else:
            n_minor += 1
        if has_level and row.get("processing_level") != level:
            any_row_diff = True
        if has_note and (row.get("processing_note") or "") != note:
            any_row_diff = True
        new_row = dict(row)
        new_row["processing_level"] = level
        new_row["processing_note"] = note
        new_rows.append(new_row)

    needs_rewrite = (not has_level) or (not has_note) or any_row_diff
    if not needs_rewrite:
        return False, n_minor, n_major

    # Header order: keep original ordering, append the two new columns at
    # the tail (mirrors columns.json placement).
    new_fieldnames = list(original_fieldnames)
    if not has_level:
        new_fieldnames.append("processing_level")
    if not has_note:
        new_fieldnames.append("processing_note")

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=new_fieldnames,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(new_rows)

    return True, n_minor, n_major


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    repo_root = here.parent
    datasets_root = repo_root / "datasets" / "elections"
    if not datasets_root.exists():
        print(
            f"error: datasets root not found at {datasets_root}",
            file=sys.stderr,
        )
        return 1

    targets: list[tuple[Path, bool]] = []
    for sub in ("assembly", "parliament"):
        base = datasets_root / sub
        if not base.exists():
            continue
        for candidacies in base.rglob("candidacies.csv"):
            targets.append((candidacies, False))
        for summary in base.rglob("summary.csv"):
            targets.append((summary, True))

    n_files_rewritten = 0
    total_minor = 0
    total_major = 0
    for path, is_summary in targets:
        rewrote, n_minor, n_major = _process_file(path, is_summary)
        total_minor += n_minor
        total_major += n_major
        if rewrote:
            n_files_rewritten += 1

    print(
        f"Rewrote {n_files_rewritten} files: "
        f"{total_minor} rows defaulted minor, "
        f"{total_major} rows tagged major."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
