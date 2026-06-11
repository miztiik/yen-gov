"""One-off driver for B2b.5.4: emit the parliament election results
from the local TCPD ``All_States_GE.csv``, ensure the TCPD GE source row exists
in ``source.csv``, and append a coverage note under ``datasets/_ops/``.

Run from repo root (cwd=backend for the module path):

    python -m yen_gov.canonical.reingest._run_parliament_results

The TCPD GE source is SCALAR per endpoint (one citation for the whole
``All_States_GE`` compilation snapshot) per ADR-0042 / OWID
one-origin-per-snapshot; distinct from the assembly ``All_States_AE`` source.
"""

from __future__ import annotations

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


def _write_coverage(receipt_path: Path, emitted: dict) -> None:
    lines = [
        "# Parliament coverage (B2b.5.4, 2026-06-05)",
        "",
        "Per-cycle PC bind coverage for the in-force (2008) delimitation. "
        "`unbound` counts (state, pc_no) pairs that did not resolve to an "
        "`electoral.csv` PC entity - state-reorganisation artefacts + the small "
        "LGD-spine gap + Delhi's PCs (Delhi has no `electoral.csv` constituencies; "
        "deferred with the assembly Delhi gap).",
        "",
        "| election | states | candidacies | summary PCs | unbound |",
        "| --- | --- | --- | --- | --- |",
    ]
    for year, info in sorted(emitted.items()):
        lines.append(
            f"| {year} | {info['states']} | {info['n_candidacies']} | "
            f"{info['n_summary']} | {len(info['unbound'])} |"
        )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    ephemeral = repo_root / "datasets" / "ephemeral"
    entities = repo_root / "datasets" / "data" / "entities"
    source_csv = entities / "source.csv"

    source_id = derive_source_id(TCPD_GE_OWNER, TCPD_GE_TITLE, TCPD_GE_VINTAGE)
    _ensure_source_row(source_csv, source_id)

    emitted = parliament_results.emit_parliament(
        ge_csv=ephemeral / "All_States_GE.csv",
        electoral_csv=entities / "electoral.csv",
        out_root=repo_root,
        source_id=source_id,
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

    _write_coverage(repo_root / COVERAGE_RECEIPT, emitted)

    total_c = sum(i["n_candidacies"] for i in emitted.values())
    total_s = sum(i["n_summary"] for i in emitted.values())
    print(f"TCPD GE source_id: {source_id}")
    print(
        f"emitted {len(emitted)} LS cycles; {total_c} candidacies + "
        f"{total_s} summary rows"
    )
    for year, info in sorted(emitted.items()):
        print(
            f"  {year}: {info['states']} states, {info['n_candidacies']} "
            f"candidacies / {info['n_summary']} PCs (unbound {len(info['unbound'])})"
        )


if __name__ == "__main__":
    main()
