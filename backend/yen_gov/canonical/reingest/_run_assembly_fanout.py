"""B2b.5.3 assembly fan-out driver: replay the B2b.5.2 emitter across the
remaining state directories, one parallel-safe wave per run.

Run from repo root (cwd=backend for the module path), passing the wave number:

    python -m yen_gov.canonical.reingest._run_assembly_fanout 1

Each wave emits ``elections/assembly/state=<slug>/election=<yr>/{candidacies,
summary}.csv`` for its states (every DelimID-4 election year), reuses the single
TCPD assembly ``source_id`` minted in B2b.5.2, and appends a per-wave coverage
note to ``datasets/_ops/assembly-fanout-coverage-2026-06-05.md`` recording
per-state bind coverage (years, candidacies, summary rows, skipped/unbound
``eci_no`` from state-reorganisation or LGD-spine gaps).

State scoping (per the B2b.5.3 dry-run, 2026-06-05):

- DelimID 4 (the in-force 2008 delimitation) is the only cycle emitted; its
  Constituency_No numbering binds to the emitted ``electoral.csv`` entities.
- TCPD's defunct names (Madras / Mysore / Goa_Daman_&_Diu) carry no DelimID-4
  rows and are absent from the map.
- Delhi is DEFERRED: ``electoral.csv`` carries no Delhi assembly constituencies
  (the LGD coverage report excluded them), so every Delhi candidacy is unbound.
  Delhi lands once the spine gains its ACs (a 0c follow-up), out of scope here.
- Tamil Nadu shipped in B2b.5.2 and is not re-emitted.

The TCPD ``State_Name`` -> LGD slug map is mechanical
(``name.lower().replace("_&_", "-and-").replace("_", "-")``) and verified to hit
exactly the ``electoral.csv`` state set for every wave member.
"""

from __future__ import annotations

import sys
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest import assembly_results
from yen_gov.canonical.reingest._run_assembly_results import (
    TCPD_AE_OWNER,
    TCPD_AE_TITLE,
    TCPD_AE_VINTAGE,
    _ensure_source_row,
)
from yen_gov.canonical.reingest.elections import (
    ASSEMBLY_CANDIDACIES_FC,
    ASSEMBLY_SUMMARY_FC,
)

COVERAGE_RECEIPT = "datasets/_ops/assembly-fanout-coverage-2026-06-05.md"


def _slugify(tcpd_name: str) -> str:
    return tcpd_name.lower().replace("_&_", "-and-").replace("_", "-")


# Parallel-safe waves (each state writes a disjoint sub-tree). TN (B2b.5.2) and
# Delhi (deferred, no spine ACs) are excluded. Names are the TCPD State_Name form.
WAVES: dict[int, list[str]] = {
    1: [
        "Andhra_Pradesh",
        "Arunachal_Pradesh",
        "Assam",
        "Bihar",
        "Chhattisgarh",
        "Goa",
        "Gujarat",
        "Haryana",
        "Himachal_Pradesh",
        "Jammu_&_Kashmir",
    ],
    2: [
        "Jharkhand",
        "Karnataka",
        "Kerala",
        "Madhya_Pradesh",
        "Maharashtra",
        "Manipur",
        "Meghalaya",
        "Mizoram",
        "Nagaland",
        "Odisha",
    ],
    3: [
        "Puducherry",
        "Punjab",
        "Rajasthan",
        "Sikkim",
        "Telangana",
        "Tripura",
        "Uttar_Pradesh",
        "Uttarakhand",
        "West_Bengal",
    ],
}


def _append_coverage(receipt_path: Path, wave: int, lines: list[str]) -> None:
    header = (
        "# Assembly fan-out coverage (B2b.5.3, 2026-06-05)\n\n"
        "Per-state DelimID-4 bind coverage for the assembly election-results\n"
        "fan-out. `skipped_eci_no` counts (state-year, Constituency_No) pairs that\n"
        "did not resolve to an `electoral.csv` entity - overwhelmingly\n"
        "state-reorganisation artefacts (pre-2014 united-Andhra / Telangana ACs,\n"
        "etc.) where the historical constituency has no current LGD entity, plus a\n"
        "small LGD-spine gap (the same class as TN eci_no 17 / 192). Delhi is\n"
        "deferred (no Delhi ACs in `electoral.csv`).\n"
    )
    if not receipt_path.exists():
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(header, encoding="utf-8")
    block = [f"\n## Wave {wave}\n"]
    block.extend(lines)
    with receipt_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(block) + "\n")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("1", "2", "3"):
        raise SystemExit("usage: python -m ..._run_assembly_fanout <1|2|3>")
    wave = int(sys.argv[1])

    repo_root = Path(__file__).resolve().parents[4]
    ephemeral = repo_root / "datasets" / "ephemeral"
    entities = repo_root / "datasets" / "data" / "entities"
    source_csv = entities / "source.csv"

    source_id = derive_source_id(TCPD_AE_OWNER, TCPD_AE_TITLE, TCPD_AE_VINTAGE)
    _ensure_source_row(source_csv, source_id)

    coverage_lines: list[str] = [
        "| state | years | candidacies | summary ACs | skipped_eci_no |",
        "| --- | --- | --- | --- | --- |",
    ]
    grand_c = grand_s = 0
    for tcpd_name in WAVES[wave]:
        slug = _slugify(tcpd_name)
        emitted = assembly_results.emit_state_assembly(
            ae_csv=ephemeral / "All_States_AE.csv",
            electoral_csv=entities / "electoral.csv",
            out_root=repo_root,
            state_name_tcpd=tcpd_name,
            state_slug=slug,
            source_id=source_id,
        )
        for info in emitted.values():
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
        n_c = sum(i["n_candidacies"] for i in emitted.values())
        n_s = sum(i["n_summary"] for i in emitted.values())
        skipped = sum(len(i["unbound_eci_nos"]) for i in emitted.values())
        grand_c += n_c
        grand_s += n_s
        coverage_lines.append(
            f"| {slug} | {len(emitted)} | {n_c} | {n_s} | {skipped} |"
        )
        print(f"  {slug}: {len(emitted)} years, {n_c} candidacies / {n_s} ACs")

    coverage_lines.append(f"| **wave {wave} total** | | {grand_c} | {grand_s} | |")
    _append_coverage(repo_root / COVERAGE_RECEIPT, wave, coverage_lines)

    print(
        f"wave {wave}: {len(WAVES[wave])} states, "
        f"{grand_c} candidacies + {grand_s} summary rows; source_id {source_id}"
    )


if __name__ == "__main__":
    main()
