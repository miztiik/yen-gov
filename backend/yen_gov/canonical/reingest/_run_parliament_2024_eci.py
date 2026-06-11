"""G16 driver: emit the LS2024 parliament results from the ECI Statement 33 raw CSV.

Reads ``datasets/ephemeral/2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv``,
ensures the LS2024 ECI source row exists in ``source.csv`` (idempotent;
``src-bfb4e7fb9785`` is already on disk so this is a no-op in the steady state),
calls :func:`parliament_2024_eci.emit_parliament_2024`, runs the FK validator
on each emitted CSV, and writes a coverage receipt under ``datasets/_ops/``.

Run from worktree root with the backend path injected (the shared venv is
bound to the master worktree; without ``PYTHONPATH`` the new module would not
resolve):

    $env:PYTHONPATH = "$pwd\\backend"
    python -m yen_gov.canonical.reingest._run_parliament_2024_eci

The source citation triple matches the existing canonical-store row at
``src-bfb4e7fb9785`` (see :mod:`parliament_2024_eci` module docstring section
"Source row"). ``derive_source_id`` deterministically produces that id from the
triple, so this driver is idempotent w.r.t. ``source.csv`` (no duplicate row
ever inserted per ADR-0042 one-origin-per-snapshot).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest import parliament_2024_eci
from yen_gov.canonical.reingest.elections import (
    PARLIAMENT_CANDIDACIES_FC,
    PARLIAMENT_SUMMARY_FC,
)

# Citation triple - matches the existing source.csv row at src-bfb4e7fb9785
# (publisher edition vintage per ADR-0042). The em-dash is encoded as the
# explicit \u2014 escape so this source file stays ASCII-pure per CLAUDE.md
# section 5; the hash of the resulting UTF-8 bytes deterministically yields
# src-bfb4e7fb9785.
ECI_OWNER = "Election Commission of India"
ECI_TITLE = (
    "General Election to Lok Sabha 2024 \u2014 "
    "Constituency Wise Detailed Result (Report 33)"
)
ECI_VINTAGE = "2024"
ECI_URL = ""

ECI_RAW_REL = (
    "datasets/ephemeral/"
    "2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv"
)
COVERAGE_RECEIPT_REL = "datasets/_ops/parliament-2024-eci-coverage-2026-06-09.md"


def _ensure_source_row(source_csv: Path, source_id: str) -> bool:
    """Insert the LS2024 ECI source row if absent. Return True if inserted.

    Mirrors :func:`_run_parliament_results._ensure_source_row` (same five-col
    contract, same sort-by-source_id discipline). Idempotent: if the row's
    ``source_id`` already exists in ``source.csv`` the function returns False
    without rewriting the file.
    """
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
        return False
    rows.append(
        {
            "source_id": source_id,
            "producer": ECI_OWNER,
            "title": ECI_TITLE,
            "vintage": ECI_VINTAGE,
            "url": ECI_URL,
        }
    )
    rows.sort(key=lambda r: r["source_id"])
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    source_csv.write_text(buf.getvalue(), encoding="utf-8", newline="")
    return True


def _write_coverage(receipt_path: Path, info: dict) -> None:
    lines = [
        "# Parliament 2024 ingest coverage (G16, 2026-06-09)",
        "",
        "Source: ECI Statement 33 raw CSV "
        "(`datasets/ephemeral/2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv`). "
        "Bound to the 2008-delim PC entities in `electoral.csv` "
        "(the 2024 delimitation order takes effect for the LS2029 cycle). "
        "`unbound` counts ECI PCs that did not resolve to an `electoral.csv` "
        "PC entity at delim=2008 (Delhi's 7 PCs + Chandigarh + A&N + a small "
        "name-spelling drift in Maharashtra / UP / WB) - "
        "documented spine gap, not a writer bug. NOTA rows are excluded "
        "(ballot option, not a candidate); Surat is absent from the raw "
        "(unopposed return; ECI excluded it from Statement 33).",
        "",
        "| election | states | candidacies | summary PCs | unbound | raw rows |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| 2024 | {info['states']} | {info['n_candidacies']} | "
        f"{info['n_summary']} | {len(info['unbound'])} | {info['raw_rows']} |",
        "",
        "## Unbound (state_slug, ECI PC name)",
        "",
    ]
    if info["unbound"]:
        for state_slug, pc_name in info["unbound"]:
            lines.append(f"- `{state_slug}` / `{pc_name}`")
    else:
        lines.append("(none)")
    lines.append("")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    entities = repo_root / "datasets" / "data" / "entities"
    source_csv = entities / "source.csv"
    eci_csv = repo_root / ECI_RAW_REL

    source_id = derive_source_id(ECI_OWNER, ECI_TITLE, ECI_VINTAGE)
    inserted = _ensure_source_row(source_csv, source_id)

    info = parliament_2024_eci.emit_parliament_2024(
        eci_csv=eci_csv,
        electoral_csv=entities / "electoral.csv",
        out_root=repo_root,
        source_id=source_id,
        parties_csv=entities / "parties.csv",
    )

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

    _write_coverage(repo_root / COVERAGE_RECEIPT_REL, info)

    print(f"ECI LS2024 source_id: {source_id} (inserted={inserted})")
    print(
        f"emitted LS2024: {info['states']} states, {info['n_candidacies']} "
        f"candidacies + {info['n_summary']} summary rows (unbound "
        f"{len(info['unbound'])} of {info['raw_rows']} raw rows)"
    )
    print(f"  candidacies: {info['candidacies'].relative_to(repo_root).as_posix()}")
    print(f"  summary:     {info['summary'].relative_to(repo_root).as_posix()}")
    print(f"  coverage:    {COVERAGE_RECEIPT_REL}")


if __name__ == "__main__":
    main()
