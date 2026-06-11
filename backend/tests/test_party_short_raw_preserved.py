"""Tier-A corpus oracle: no candidacy row has blank party_short_raw.

Companion to ``test_party_id_fk_closure.py``. Walks every on-disk
``candidacies.csv`` and asserts that ``party_short_raw`` is non-empty for
every emitted row. An emitted candidacy with a blank publisher label is the
defining failure mode this test exists to catch (CLAUDE.md section 5 +
section 10 "no silent demotion").

Two writer-bug classes prompted this test (2026-06-11 audit):

  1. **F1.1 schema-migration without re-emit**: the F1.1 backfill (#791,
     2026-06-05) created Delhi candidacies.csv files using the v1 schema
     that lacked the ``party_short_raw`` column. The G1 PR (#831,
     2026-06-08) added the column to all on-disk files via in-place
     migration but never re-emitted Delhi (Delhi was on the DEFERRED list
     in ``_run_assembly_fanout.py``). Result: 6 Delhi slices
     (2008/2009/2013/2015/2017/2020) carried 3,068 candidacy rows with
     empty ``party_short_raw`` despite TCPD's ``All_States_AE.csv`` having
     100% Party population.

  2. **TCPD 2017+ NOTA-as-Candidate shape**: TCPD vintage 2017+ marks the
     NOTA ballot line as ``Candidate='NOTA', Party=''`` (empty cell);
     pre-2017 used ``Party='NOTA'``. The writer's original NOTA filter
     only checked the Party column, so the 2017+ shape escaped filtering
     and emitted ~264 rows across 72 slices with blank
     ``party_short_raw`` + ``parties.IN.UNK``.

Both bug classes are now structurally fixed at the writer (extended NOTA
detection via ``is_nota_row`` checks both Candidate and Party; Delhi
added to the assembly fanout). This test is the always-on safety net so
any future regression to either bug class fails ``pytest -q`` instead of
surfacing in citizen UI.

CLAUDE.md section 14 carve-out: corpus-walking pytest is allowed at
Tier-A when the walk IS the contract (here: structural emit invariant).
The walk is bounded to the ~260 candidacies.csv files and the test fails
fast with an actionable per-slice report.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSEMBLY_ROOT = REPO_ROOT / "datasets" / "elections" / "assembly"
PARLIAMENT_ROOT = REPO_ROOT / "datasets" / "elections" / "parliament"


def _walk_candidacies() -> list[Path]:
    assembly = sorted(ASSEMBLY_ROOT.glob("state=*/election=*/candidacies.csv"))
    parliament = sorted(PARLIAMENT_ROOT.glob("election=*/candidacies.csv"))
    return assembly + parliament


def test_no_candidacy_row_has_blank_party_short_raw() -> None:
    """Every emitted candidacy row carries a non-empty publisher label.

    Failure surface: per-slice counts of the offending rows + a representative
    sample so a regression PR's report points at exactly which slice + which
    candidates the writer dropped the label for.
    """
    paths = _walk_candidacies()
    assert paths, (
        "no candidacies.csv files found under "
        f"{ASSEMBLY_ROOT.relative_to(REPO_ROOT).as_posix()} or "
        f"{PARLIAMENT_ROOT.relative_to(REPO_ROOT).as_posix()}; "
        "did the directory layout move?"
    )

    offenders: list[tuple[str, int, str, str]] = []
    for path in paths:
        rel = path.relative_to(REPO_ROOT).as_posix()
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if not (row.get("party_short_raw") or "").strip():
                    offenders.append(
                        (
                            rel,
                            int(row.get("constituency_no") or 0),
                            row.get("candidate_name", ""),
                            row.get("party_id", ""),
                        )
                    )

    if not offenders:
        return

    # Group by file for actionable reporting (a regression typically hits
    # one or a few slices).
    by_file: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for rel, eci_no, cand, pid in offenders:
        by_file[rel].append((eci_no, cand, pid))

    lines: list[str] = [
        f"{len(offenders)} candidacy rows have blank party_short_raw "
        f"across {len(by_file)} files. Examples (first 5 per file, "
        "first 10 files):"
    ]
    for rel in list(by_file.keys())[:10]:
        lines.append(f"  {rel} ({len(by_file[rel])} rows):")
        for eci_no, cand, pid in by_file[rel][:5]:
            lines.append(f"    eci_no={eci_no} cand={cand!r} pid={pid!r}")
    raise AssertionError("\n".join(lines))
