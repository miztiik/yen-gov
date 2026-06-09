"""Driver: emit AcGenMay2026 partitioned candidacies + summary CSVs for all
five state slices (TN / KL / WB / AS / PY) from the legacy ECI Section 10
results CSVs already produced by ``eci-statreport-emit-local``.

Prerequisites (must be run from repo root, cwd=backend for the module path):

  python -m yen_gov eci-statreport-emit-local \\
      datasets/ephemeral/tn_10-Detailed_Results_*.xlsx --state S22 --year 2026
  # ... and same for kerala/wb/assam/pondy

Each legacy emit writes ``datasets/elections/AcGenMay2026/<STATE>/results.csv``.
THIS driver then pivots each into the partitioned shape the citizen frontend
reads (``datasets/elections/assembly/state=<slug>/election=2026/{candidacies,
summary}.csv``), reusing the existing entity-bind + party-shortcode resolution
+ summary-recompute pipeline from ``assembly_results.py``.

Run:

  python -m yen_gov.canonical.reingest._run_acgenmay2026_eci

Appends per-state bind coverage to ``datasets/_ops/acgenmay2026-fanout-
coverage.md``.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.reingest.assembly_results_from_eci import (
    emit_state_assembly_from_eci_legacy,
)
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.elections import (
    ASSEMBLY_CANDIDACIES_FC,
    ASSEMBLY_SUMMARY_FC,
)


COVERAGE_RECEIPT = "datasets/_ops/acgenmay2026-fanout-coverage.md"
EVENT_YEAR = 2026
EVENT_ID = "AcGenMay2026"

# Each tuple: (state_code, state_slug, source_id_in_source.csv).
# The five source_ids are already registered in datasets/data/entities/source.csv
# (emitted by the long-format aggregate pipeline before the partitioned files
# were noticed missing). Confirmed via:
#   grep AcGenMay2026 datasets/data/entities/source.csv
STATES: list[tuple[str, str, str]] = [
    ("S22", "tamil-nadu", "src-3da941c21223"),
    ("S11", "kerala", "src-920426012b16"),
    ("S25", "west-bengal", "src-fa1aba648c1e"),
    ("S03", "assam", "src-074239c7b852"),
    ("U07", "puducherry", "src-9b0bb5164d79"),
]


def _append_coverage(receipt_path: Path, lines: list[str]) -> None:
    header = (
        "# AcGenMay2026 fan-out coverage (TN / KL / WB / AS / PY)\n\n"
        "Per-state DelimID-2008 bind coverage for the AcGenMay2026 ECI Section 10\n"
        "Detailed Results emit. `skipped_eci_no` counts ECI Constituency_No values\n"
        "that did not resolve to a current `electoral.csv` AC entity for the state\n"
        "(typically an LGD-spine gap). Source XLSXes are hand-downloaded from\n"
        "old.eci.gov.in and held in `datasets/ephemeral/` for the legacy\n"
        "`eci-statreport-emit-local` parse; the partitioned candidacies+summary\n"
        "CSVs are pivoted by `assembly_results_from_eci.py`.\n\n"
        "| state | candidacies | summary ACs | skipped_eci_no |\n"
        "| --- | --- | --- | --- |\n"
    )
    if not receipt_path.exists():
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(header, encoding="utf-8")
    with receipt_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    entities = repo_root / "datasets" / "data" / "entities"
    electoral_csv = entities / "electoral.csv"
    parties_csv = entities / "parties.csv"

    lines: list[str] = []
    grand_c = grand_s = 0
    for state_code, state_slug, source_id in STATES:
        legacy_csv = (
            repo_root / "datasets" / "elections" / EVENT_ID / state_code / "results.csv"
        )
        if not legacy_csv.exists():
            raise FileNotFoundError(
                f"missing legacy results.csv for {state_code}: {legacy_csv}; "
                f"run `python -m yen_gov eci-statreport-emit-local "
                f"<xlsx> --state {state_code} --year {EVENT_YEAR}` first."
            )
        info = emit_state_assembly_from_eci_legacy(
            eci_legacy_csv=legacy_csv,
            electoral_csv=electoral_csv,
            out_root=repo_root,
            state_slug=state_slug,
            election_year=EVENT_YEAR,
            source_id=source_id,
            parties_csv=parties_csv,
        )
        validate_csv(
            path=info["candidacies"],
            file_class=ASSEMBLY_CANDIDACIES_FC,
            repo_root=repo_root,
        )
        validate_csv(
            path=info["summary"],
            file_class=ASSEMBLY_SUMMARY_FC,
            repo_root=repo_root,
        )
        n_c = info["n_candidacies"]
        n_s = info["n_summary"]
        grand_c += n_c
        grand_s += n_s
        skipped = len(info["unbound_eci_nos"])
        lines.append(f"| {state_slug} | {n_c} | {n_s} | {skipped} |")
        print(
            f"  {state_slug}: {n_c} candidacies / {n_s} ACs "
            f"(skipped {skipped} unbound)"
        )
    lines.append(f"| **total** | {grand_c} | {grand_s} | |")
    _append_coverage(repo_root / COVERAGE_RECEIPT, lines)
    print(
        f"AcGenMay2026: {len(STATES)} states, "
        f"{grand_c} candidacies + {grand_s} summary rows"
    )


if __name__ == "__main__":
    main()
