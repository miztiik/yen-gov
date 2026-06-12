"""B2b.5.3 assembly fan-out driver: replay the B2b.5.2 emitter across the
remaining state directories, one parallel-safe wave per run.

Run from repo root (cwd=backend for the module path), passing the wave number:

    # all four DelimIDs (default; 3 -> 1 -> 2 -> 4 in priority order)
    python -m yen_gov.canonical.reingest._run_assembly_fanout 1

    # one DelimID at a time (PR-Q7b reingest pattern)
    python -m yen_gov.canonical.reingest._run_assembly_fanout 1 --delim 3

Each wave emits ``elections/assembly/state=<slug>/election=<yr>/{candidacies,
summary}.csv`` for its states across the requested delimitation cycle(s),
reuses the single TCPD assembly ``source_id`` minted in B2b.5.2, and appends a
per-wave coverage note to
``datasets/_ops/assembly-fanout-coverage-2026-06-05.md`` recording per-state
bind coverage (years, candidacies, summary rows, skipped/unbound ``eci_no``
from state-reorganisation or LGD-spine gaps).

State scoping (per the B2b.5.3 dry-run, 2026-06-05; Delhi added 2026-06-11):

- DelimID 4 (the in-force 2008 delimitation) was the only cycle emitted at
  B2b.5.3; its Constituency_No numbering binds to the seeded ``electoral.csv``
  entities. PR-Q7b (2026-06-12) extends the driver to DelimID 1 / 2 / 3 so
  the ~192 pre-2008 events still flagged ``data_status: pending_upstream``
  in ``election_events.json`` flip to ``complete``. The bind for the
  historical cycles requires PR-Q7b's ``_run_historical_ac_entities`` minter
  to have run first (otherwise every DelimID 1/2/3 row lands in ``unbound``
  and the year is skipped -- the documented pre-PR-Q7b state).
- TCPD's defunct names (Madras / Mysore / Goa_Daman_&_Diu) carry no DelimID-4
  rows and are absent from the map; the same skip rule applies to DelimID
  1/2/3 (no entity to bind into).
- Delhi was DEFERRED at B2b.5.3 because ``electoral.csv`` lacked Delhi
  assembly constituencies. F1.1 (#791, 2026-06-05) extended ``electoral.csv``
  with 70 synthetic Delhi AC rows but never returned Delhi to the fanout
  worklist; the schema-migration added party_short_raw to the orphan Delhi
  candidacies.csv files without re-emitting them. Result: 6 Delhi slices
  (2008/2009/2013/2015/2017/2020) carried 3,068 candidacy rows with empty
  party_short_raw despite TCPD's All_States_AE.csv having 100% Party
  population. Delhi is now in Wave 1 (2026-06-11 writer-bug fix).
- Tamil Nadu shipped in B2b.5.2 and is not re-emitted for DelimID 4 here
  (run ``_run_assembly_results.py`` for TN's 2008 cycle); the multi-delim
  loop DOES emit TN under DelimID 1/2/3 (via Wave 3) because the pre-2008
  TN events still need binding.

The TCPD ``State_Name`` -> LGD slug map is mechanical
(``name.lower().replace("_&_", "-and-").replace("_", "-")``) and verified to hit
exactly the ``electoral.csv`` state set for every wave member.

Re-runs are byte-stable: ``emit_state_assembly`` writes the same candidacies
+ summary content for the same (state, delim, year) inputs, so an apply of
``--delim 4`` after the original B2b.5.3 sweep is a no-op against the
on-disk shards.
"""

from __future__ import annotations

import argparse
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

# DelimIDs the fanout walks, in priority order. DelimID 3 is the bulk of
# the historical work (1974-2012); DelimID 1/2 are the early cohorts;
# DelimID 4 is the in-force 2008 cycle (re-emit is byte-stable so re-runs
# are safe). Override with ``--delim <id>`` on the CLI.
DELIMS: list[str] = ["3", "1", "2", "4"]


def _slugify(tcpd_name: str) -> str:
    return tcpd_name.lower().replace("_&_", "-and-").replace("_", "-")


# Parallel-safe waves (each state writes a disjoint sub-tree). TN was the
# B2b.5.2 pilot for DelimID 4 (run ``_run_assembly_results.py`` to re-emit
# its 2008-cycle shards); the multi-delim loop emits TN under DelimID 1/2/3
# via Wave 3, so the pre-2008 TN events also flip from
# ``data_status: pending_upstream`` to ``complete``. Delhi was DEFERRED at
# B2b.5.3 but added to Wave 1 on 2026-06-11 (F1.1 added the entities; the
# fanout never followed up - see module docstring). Names are the TCPD
# State_Name form.
WAVES: dict[int, list[str]] = {
    1: [
        "Andhra_Pradesh",
        "Arunachal_Pradesh",
        "Assam",
        "Bihar",
        "Chhattisgarh",
        "Delhi",
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
        "Tamil_Nadu",
        "Telangana",
        "Tripura",
        "Uttar_Pradesh",
        "Uttarakhand",
        "West_Bengal",
    ],
}


def _is_tn_default_delim(tcpd_name: str, delim_id: str) -> bool:
    """Skip TN x DelimID 4 in the fanout (B2b.5.2 owns the in-force TN cycle)."""
    return tcpd_name == "Tamil_Nadu" and delim_id == "4"


def _append_coverage(receipt_path: Path, wave: int, lines: list[str]) -> None:
    header = (
        "# Assembly fan-out coverage (B2b.5.3, 2026-06-05)\n\n"
        "Per-state DelimID bind coverage for the assembly election-results\n"
        "fan-out. `skipped_eci_no` counts (state-year, Constituency_No) pairs that\n"
        "did not resolve to an `electoral.csv` entity - overwhelmingly\n"
        "state-reorganisation artefacts (pre-2014 united-Andhra / Telangana ACs,\n"
        "etc.) where the historical constituency has no current LGD entity, plus a\n"
        "small LGD-spine gap (the same class as TN eci_no 17 / 192). Delhi DelimID-4\n"
        "is in Wave 1 (2026-06-11 writer-bug fix); DelimID 1 / 2 / 3 cohorts\n"
        "(1962 / 1967 / 1976 cycles) added 2026-06-12 via PR-Q7b reingest.\n"
    )
    if not receipt_path.exists():
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(header, encoding="utf-8")
    block = [f"\n## Wave {wave}\n"]
    block.extend(lines)
    with receipt_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(block) + "\n")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m yen_gov.canonical.reingest._run_assembly_fanout",
    )
    parser.add_argument(
        "wave",
        type=int,
        choices=(1, 2, 3),
        help="Wave number (each wave is a disjoint state set).",
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
    wave = args.wave
    delims_to_run = [args.delim] if args.delim else list(DELIMS)

    repo_root = Path(__file__).resolve().parents[4]
    ephemeral = repo_root / "datasets" / "ephemeral"
    entities = repo_root / "datasets" / "data" / "entities"
    source_csv = entities / "source.csv"

    source_id = derive_source_id(TCPD_AE_OWNER, TCPD_AE_TITLE, TCPD_AE_VINTAGE)
    _ensure_source_row(source_csv, source_id)

    coverage_lines: list[str] = [
        "| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    grand_c = grand_s = 0
    for tcpd_name in WAVES[wave]:
        slug = _slugify(tcpd_name)
        for delim_id in delims_to_run:
            if _is_tn_default_delim(tcpd_name, delim_id):
                # TN x DelimID 4 is owned by _run_assembly_results (B2b.5.2).
                continue
            emitted = assembly_results.emit_state_assembly(
                ae_csv=ephemeral / "All_States_AE.csv",
                electoral_csv=entities / "electoral.csv",
                out_root=repo_root,
                state_name_tcpd=tcpd_name,
                state_slug=slug,
                source_id=source_id,
                parties_csv=entities / "parties.csv",
                delim_id=delim_id,
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
                f"| {slug} | {delim_id} | {len(emitted)} | {n_c} | {n_s} | {skipped} |"
            )
            print(
                f"  {slug} (delim {delim_id}): {len(emitted)} years,"
                f" {n_c} candidacies / {n_s} ACs"
            )

    delim_label = args.delim or "all"
    coverage_lines.append(
        f"| **wave {wave} delim={delim_label} total** | | | {grand_c} | {grand_s} | |"
    )
    _append_coverage(repo_root / COVERAGE_RECEIPT, wave, coverage_lines)

    print(
        f"wave {wave} delim={delim_label}: {len(WAVES[wave])} states, "
        f"{grand_c} candidacies + {grand_s} summary rows; source_id {source_id}"
    )


if __name__ == "__main__":
    main()
