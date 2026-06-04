"""B2b.5 elections-from-local-TCPD per-election CSV scaffolding (B2b.5.1).

Shared scaffolding for the four per-election CSV file classes declared in
``datasets/data/_schema/columns.json`` (added by B1.1, PR #629; gate
`schema-of-schemas-valid` locks the shape). The actual emit functions land
in B2b.5.2 (assembly TN pilot), B2b.5.3 (assembly fan-out across the other
35 state directories), and B2b.5.4 (parliament 1957..2024); this module is
the contract surface those three emitters import so the FILE_CLASS string
literals do not drift across emitter modules + tests + drivers.

Per parent plan section 21.3 + 23.4:

- Each emitted file is ONE election (delimitation merge/split never
  reconciled in-file); cross-year reads glob
  ``assembly/state=<slug>/election=*/summary.csv`` at read time.
- Parliament CSVs carry ``state`` as a MANDATORY column even though the
  path has no ``state=`` partition (constituency_no restarts per state).
- ``summary.csv`` is a DERIVED projection of ``candidacies.csv``
  (parity-oracle-CSV gate asserts ``summary == recompute(candidacies)``
  per parent 22.6).

Public surface:

    from yen_gov.canonical.reingest.elections import (
        ASSEMBLY_CANDIDACIES_FC,
        ASSEMBLY_SUMMARY_FC,
        PARLIAMENT_CANDIDACIES_FC,
        PARLIAMENT_SUMMARY_FC,
        assembly_candidacies_path,
        assembly_summary_path,
        parliament_candidacies_path,
        parliament_summary_path,
    )

The FILE_CLASS constants are the keys ``csv_writer.write_csv(..., file_class=...)``
expects; the path builders produce the on-disk file location for one
(state, year) or (year) election. Both halves of the pair MUST be co-resolved
because the column contract lives in ``columns.json`` keyed by the same glob.

No I/O, no parquet reads, no network. The module is import-side-effect free
so future drivers can import without spinning up DuckDB or reading fixtures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

__all__ = [
    "ASSEMBLY_CANDIDACIES_FC",
    "ASSEMBLY_SUMMARY_FC",
    "PARLIAMENT_CANDIDACIES_FC",
    "PARLIAMENT_SUMMARY_FC",
    "assembly_candidacies_path",
    "assembly_summary_path",
    "parliament_candidacies_path",
    "parliament_summary_path",
]


ASSEMBLY_CANDIDACIES_FC: Final[str] = (
    "datasets/elections/assembly/state=*/election=*/candidacies.csv"
)
ASSEMBLY_SUMMARY_FC: Final[str] = (
    "datasets/elections/assembly/state=*/election=*/summary.csv"
)
PARLIAMENT_CANDIDACIES_FC: Final[str] = (
    "datasets/elections/parliament/election=*/candidacies.csv"
)
PARLIAMENT_SUMMARY_FC: Final[str] = (
    "datasets/elections/parliament/election=*/summary.csv"
)


def assembly_candidacies_path(
    *, out_root: Path, state_slug: str, election_year: int
) -> Path:
    """Return the assembly ``candidacies.csv`` path for one (state, year).

    Args:
        out_root: directory that anchors ``datasets/elections/`` (typically the
            repo root, ``out_root=<repo_root>``; tests pass ``tmp_path``).
        state_slug: LGD state slug (e.g. ``"tamil-nadu"``; matches
            ``datasets/data/entities/geo.csv.entity_id`` for state-grain rows).
        election_year: four-digit year (e.g. ``2021``).

    Returns:
        ``<out_root>/datasets/elections/assembly/state=<slug>/election=<yr>/candidacies.csv``.
    """
    return (
        out_root
        / "datasets"
        / "elections"
        / "assembly"
        / f"state={state_slug}"
        / f"election={election_year}"
        / "candidacies.csv"
    )


def assembly_summary_path(
    *, out_root: Path, state_slug: str, election_year: int
) -> Path:
    """Return the assembly ``summary.csv`` path for one (state, year).

    See :func:`assembly_candidacies_path` for argument semantics.
    """
    return (
        out_root
        / "datasets"
        / "elections"
        / "assembly"
        / f"state={state_slug}"
        / f"election={election_year}"
        / "summary.csv"
    )


def parliament_candidacies_path(
    *, out_root: Path, election_year: int
) -> Path:
    """Return the parliament ``candidacies.csv`` path for one year.

    The parliament layout has no ``state=`` path partition (one country-wide
    file per LS cycle); the ``state`` column inside the CSV is MANDATORY per
    parent plan section 23.4 because ``constituency_no`` (ECI pc_no) restarts
    per state.

    Args:
        out_root: directory that anchors ``datasets/elections/`` (tests pass
            ``tmp_path``).
        election_year: four-digit national-election year (e.g. ``2024``).

    Returns:
        ``<out_root>/datasets/elections/parliament/election=<yr>/candidacies.csv``.
    """
    return (
        out_root
        / "datasets"
        / "elections"
        / "parliament"
        / f"election={election_year}"
        / "candidacies.csv"
    )


def parliament_summary_path(
    *, out_root: Path, election_year: int
) -> Path:
    """Return the parliament ``summary.csv`` path for one year.

    See :func:`parliament_candidacies_path` for argument semantics + the
    state-column rationale.
    """
    return (
        out_root
        / "datasets"
        / "elections"
        / "parliament"
        / f"election={election_year}"
        / "summary.csv"
    )
