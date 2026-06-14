"""One-off driver for B2b.5.4: emit the parliament election results
from the local TCPD ``All_States_GE.csv``, ensure the TCPD GE source row exists
in ``source.csv``, and append a coverage note under ``datasets/_ops/``.

Run from repo root (cwd=backend for the module path):

    # all four DelimIDs (default; 3 -> 1 -> 2 -> 4 in priority order)
    python -m yen_gov.canonical.reingest._run_parliament_results

    # one DelimID at a time (PR-Q7c reingest pattern)
    python -m yen_gov.canonical.reingest._run_parliament_results --delim 3

The TCPD GE source is SCALAR per endpoint (one citation for the whole
``All_States_GE`` compilation snapshot) per ADR-0042 / OWID
one-origin-per-snapshot; distinct from the assembly ``All_States_AE`` source.

PR-Q7c (2026-06-12) extended the driver to walk DelimID 1 / 2 / 3 so the
65 pre-2009 parliament events still flagged ``data_status: pending_upstream``
in ``election_events.json`` (31 general-1999 + 34 general-2004 state slices)
flip to ``complete`` once the historical PC entities are minted by
``_run_historical_pc_entities``. The bind for the historical cycles
requires the historical entities to exist on disk first (otherwise every
DelimID 1/2/3 row lands in ``unbound`` and the year is skipped).
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest import parliament_results
from yen_gov.canonical.reingest.elections import (
    PARLIAMENT_CANDIDACIES_FC,
    PARLIAMENT_SUMMARY_FC,
)

TCPD_GE_OWNER = "Trivedi Centre for Political Data, Ashoka University"
TCPD_GE_TITLE = (
    "Indian General Elections (Lok Sabha) - Constituency-wise candidate results "
    "(TCPD compilation of ECI returns)"
)
TCPD_GE_VINTAGE = "2026-06-05"
TCPD_GE_URL = "https://tcpd.ashoka.edu.in/lok-dhaba/"

COVERAGE_RECEIPT = "datasets/_ops/parliament-coverage-2026-06-05.md"

# DelimIDs the driver walks, in priority order. DelimID 3 is the bulk of
# the historical work (1977-2008 covering all LS cycles up to and
# including the 14th LS); DelimID 1/2 are the early cohorts; DelimID 4
# is the in-force 2008 cycle (re-emit is byte-stable so re-runs are
# safe). Override with ``--delim <id>`` on the CLI.
DELIMS: list[str] = ["3", "1", "2", "4"]


def _ensure_source_row(source_csv: Path, source_id: str) -> None:
    with source_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or [
            "source_id",
            "producer",
            "title",
            "vintage",
            "url",
        ]
        rows = list(reader)
    if any(r["source_id"] == source_id for r in rows):
        return
    rows.append(
        {
            "source_id": source_id,
            "producer": TCPD_GE_OWNER,
            "title": TCPD_GE_TITLE,
            "vintage": TCPD_GE_VINTAGE,
            "url": TCPD_GE_URL,
        }
    )
    rows.sort(key=lambda r: r["source_id"])
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    source_csv.write_text(buf.getvalue(), encoding="utf-8", newline="")


def _write_coverage(
    receipt_path: Path,
    emitted_by_delim: dict[str, dict],
) -> None:
    lines = [
        "# Parliament coverage (B2b.5.4, 2026-06-05; PR-Q7c historical delims, 2026-06-12)",
        "",
        "Per-cycle PC bind coverage. `unbound` counts (state, pc_no) pairs that"
        " did not resolve to an `electoral.csv` PC entity for the matching"
        " delim cohort - state-reorganisation artefacts + the small LGD-spine"
        " gap + historical state-name divergence. PR-Q7c (2026-06-12) extends"
        " the driver to DelimID 1/2/3 once `_run_historical_pc_entities` has"
        " minted the historical PC cohorts.",
        "",
        "| delim_id | election | states | candidacies | summary PCs | unbound |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for delim_id in sorted(emitted_by_delim):
        emitted = emitted_by_delim[delim_id]
        for year, info in sorted(emitted.items()):
            lines.append(
                f"| {delim_id} | {year} | {info['states']} | {info['n_candidacies']} | "
                f"{info['n_summary']} | {len(info['unbound'])} |"
            )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m yen_gov.canonical.reingest._run_parliament_results",
    )
    parser.add_argument(
        "--delim",
        choices=DELIMS,
        default=None,
        help=(
            "Restrict the emission to one TCPD DelimID. Default: run all"
            f" four ({', '.join(DELIMS)}) in sequence."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    delims_to_run = [args.delim] if args.delim else list(DELIMS)

    repo_root = Path(__file__).resolve().parents[4]
    ephemeral = repo_root / "datasets" / "ephemeral"
    entities = repo_root / "datasets" / "data" / "entities"
    source_csv = entities / "source.csv"

    source_id = derive_source_id(TCPD_GE_OWNER, TCPD_GE_TITLE, TCPD_GE_VINTAGE)
    _ensure_source_row(source_csv, source_id)

    emitted_by_delim: dict[str, dict] = {}
    grand_c = grand_s = 0
    for delim_id in delims_to_run:
        emitted = parliament_results.emit_parliament(
            ge_csv=ephemeral / "All_States_GE.csv",
            electoral_csv=entities / "electoral.csv",
            out_root=repo_root,
            source_id=source_id,
            delim_id=delim_id,
            parties_csv=entities / "parties.csv",
        )
        for info in emitted.values():
            validate_csv(
                path=info["candidacies"],
                file_class=PARLIAMENT_CANDIDACIES_FC,
                repo_root=repo_root,
            )
            validate_csv(
                path=info["summary"],
                file_class=PARLIAMENT_SUMMARY_FC,
                repo_root=repo_root,
            )
        n_c = sum(i["n_candidacies"] for i in emitted.values())
        n_s = sum(i["n_summary"] for i in emitted.values())
        grand_c += n_c
        grand_s += n_s
        emitted_by_delim[delim_id] = emitted
        print(
            f"  delim {delim_id}: {len(emitted)} LS cycles, "
            f"{n_c} candidacies / {n_s} PCs"
        )
        for year, info in sorted(emitted.items()):
            print(
                f"    {year}: {info['states']} states, {info['n_candidacies']} "
                f"candidacies / {info['n_summary']} PCs (unbound {len(info['unbound'])})"
            )

    _write_coverage(repo_root / COVERAGE_RECEIPT, emitted_by_delim)

    delim_label = args.delim or "all"
    print(f"TCPD GE source_id: {source_id}")
    print(
        f"delim={delim_label}: {grand_c} candidacies + {grand_s} summary rows"
    )


if __name__ == "__main__":
    main()
