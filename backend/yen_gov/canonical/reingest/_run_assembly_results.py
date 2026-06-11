"""One-off driver for B2b.5.2: emit the Tamil Nadu assembly-election results
(candidacies + summary CSVs) from the local TCPD ``All_States_AE.csv``, and
ensure the TCPD assembly-compilation source row exists in ``source.csv``.

Run from repo root (cwd=backend for the module path):

    python -m yen_gov.canonical.reingest._run_assembly_results

The TCPD assembly source is SCALAR per endpoint (one citation for the whole
``All_States_AE`` compilation snapshot, not one per year-of-data) per the
ADR-0042 / OWID one-origin-per-snapshot doctrine; the fan-out (B2b.5.3) reuses
the same ``source_id``.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest import assembly_results
from yen_gov.canonical.reingest.elections import (
    ASSEMBLY_CANDIDACIES_FC,
    ASSEMBLY_SUMMARY_FC,
)

# TCPD assembly compilation citation (vintage = operator snapshot window, the
# same 2026-06-05 LGD/elections download window used across B2b.5.0).
TCPD_AE_OWNER = "Trivedi Centre for Political Data, Ashoka University"
TCPD_AE_TITLE = (
    "Indian Assembly Elections - Constituency-wise candidate results "
    "(TCPD compilation of ECI returns)"
)
TCPD_AE_VINTAGE = "2026-06-05"
TCPD_AE_URL = "https://tcpd.ashoka.edu.in/lok-dhaba/"

# The TN pilot (B2b.5.2). Fan-out across the other states lands in B2b.5.3.
STATE_NAME_TCPD = "Tamil_Nadu"
STATE_SLUG = "tamil-nadu"


def _ensure_source_row(source_csv: Path, source_id: str) -> None:
    """Append the TCPD assembly-compilation source row if absent (SAME-PR rule)."""
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
            "producer": TCPD_AE_OWNER,
            "title": TCPD_AE_TITLE,
            "vintage": TCPD_AE_VINTAGE,
            "url": TCPD_AE_URL,
        }
    )
    rows.sort(key=lambda r: r["source_id"])
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    source_csv.write_text(buf.getvalue(), encoding="utf-8", newline="")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    ephemeral = repo_root / "datasets" / "ephemeral"
    entities = repo_root / "datasets" / "data" / "entities"
    source_csv = entities / "source.csv"

    source_id = derive_source_id(TCPD_AE_OWNER, TCPD_AE_TITLE, TCPD_AE_VINTAGE)
    _ensure_source_row(source_csv, source_id)

    emitted = assembly_results.emit_state_assembly(
        ae_csv=ephemeral / "All_States_AE.csv",
        electoral_csv=entities / "electoral.csv",
        out_root=repo_root,
        state_name_tcpd=STATE_NAME_TCPD,
        state_slug=STATE_SLUG,
        source_id=source_id,
        parties_csv=entities / "parties.csv",
    )

    for year, info in sorted(emitted.items()):
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

    print(f"TCPD AE source_id: {source_id}")
    total_c = sum(i["n_candidacies"] for i in emitted.values())
    total_s = sum(i["n_summary"] for i in emitted.values())
    print(
        f"emitted {len(emitted)} TN election years; "
        f"{total_c} candidacies + {total_s} summary rows"
    )
    for year, info in sorted(emitted.items()):
        gap = info["unbound_eci_nos"]
        gap_note = f" (skipped unbound eci_no {gap})" if gap else ""
        print(
            f"  {year}: {info['n_candidacies']} candidacies / "
            f"{info['n_summary']} ACs{gap_note}"
        )


if __name__ == "__main__":
    main()
