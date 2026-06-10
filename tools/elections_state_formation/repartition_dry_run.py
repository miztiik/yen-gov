"""DRY-RUN re-partition proposal for state-formation events (PR-W1b).

Walks every per-state CSV under ``datasets/data/datapoints/electoral/``
and, for each (entity_id, year) row, computes the historical-state slug
via ``yen_gov.canonical.historical_state_slug.historical_state_slug``.
If the proposed historical slug differs from the current per-state
file's slug, emit one row to the proposal CSV:

    entity_id, year, current_file, proposed_file, formation_event_id

The proposal CSV path defaults to
``datasets/_ops/state-formation-repartition-proposal.csv``; override via
``--output``.

NO WRITES to any file under ``datasets/data/`` are performed. This
script is the DRY-RUN side of ESCALATE trigger #1 of
``TODO/20260609-election-experience-overhaul-plan.md``: user sign-off on
the proposal is required before any actual row move.

Invocation
----------

    python -m tools.elections_state_formation.repartition_dry_run \\
        --output datasets/_ops/state-formation-repartition-proposal.csv

Exit codes
----------
0 -- proposal CSV written (even if EMPTY; an empty proposal is a
     LEGITIMATE result meaning no on-disk row needs to move).
1 -- argument / I/O failure.

Pure-stdlib; no `backend.yen_gov` runtime modules are imported beyond
the canonical-helper module
``yen_gov.canonical.historical_state_slug`` (the contract surface --
mirrors the ``tools/boundaries/snapshot.py`` pattern).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Pin `backend/` onto sys.path so we can import the contract-surface
# canonical helper. Same pattern as tools/boundaries/snapshot.py.
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from yen_gov.canonical.historical_state_slug import (  # noqa: E402
    DEFAULT_CATALOGUE_PATH,
    historical_state_slug,
)


DEFAULT_ELECTORAL_ROOT = Path("datasets/data/datapoints/electoral")
DEFAULT_OUTPUT_PATH = Path("datasets/_ops/state-formation-repartition-proposal.csv")
DEFAULT_CATALOGUE = DEFAULT_CATALOGUE_PATH
ELECTORAL_FILE_SUFFIX = "_election_results.csv"


@dataclass(frozen=True)
class ProposalRow:
    """A single (entity_id, year) re-partition proposal."""

    entity_id: str
    year: int
    current_file: str  # POSIX-relative
    proposed_file: str  # POSIX-relative
    formation_event_id: str


def _current_slug_from_file(csv_path: Path) -> str:
    """``andhra-pradesh_election_results.csv`` -> ``andhra-pradesh``."""
    name = csv_path.name
    if not name.endswith(ELECTORAL_FILE_SUFFIX):
        raise ValueError(
            f"electoral file {csv_path} does not end in {ELECTORAL_FILE_SUFFIX!r}"
        )
    return name[: -len(ELECTORAL_FILE_SUFFIX)]


def _event_id_for_pair(
    state_code: str,
    event_year: int,
    catalogue_path: Path = DEFAULT_CATALOGUE,
) -> str | None:
    """Return the formation event_id whose carve-out covers this (state, year), if any.

    Mirrors the helper's own walk but exposes the matched event_id so
    the proposal row can name WHY the re-partition was triggered.
    """
    raw = json.loads(Path(catalogue_path).read_text(encoding="utf-8"))
    events = sorted(raw.get("events", []), key=lambda e: e["event_date"])
    for event in events:
        successors = event["successor_state_ids"]
        if state_code not in successors:
            continue
        year_str = event["event_date"].split("-", 1)[0]
        formation_year = int(year_str)
        if event_year < formation_year:
            return event["event_id"]
    return None


def _state_code_from_entity_id(entity_id: str) -> str:
    """4th hyphen-separated segment of an IN-(PC|AC)-... id."""
    parts = entity_id.split("-")
    if len(parts) < 5:
        raise ValueError(f"entity_id {entity_id!r} too short")
    return parts[3]


def iter_proposal_rows(
    electoral_root: Path = DEFAULT_ELECTORAL_ROOT,
    catalogue_path: Path = DEFAULT_CATALOGUE,
) -> Iterable[ProposalRow]:
    """Yield one ProposalRow per (entity_id, year) row that needs to move.

    Per-row dedup: a state-level CSV typically has 9 rows per AC-year
    (turnout, margin, winner, ...). All 9 collapse to ONE proposal row
    keyed on (entity_id, year). The proposal CSV is operator-facing;
    it names the (entity, year) pairs that need to move, not the
    per-indicator observation rows that follow them.
    """
    seen: set[tuple[str, int]] = set()
    csv_files = sorted(electoral_root.glob(f"*{ELECTORAL_FILE_SUFFIX}"))
    for csv_path in csv_files:
        current_slug = _current_slug_from_file(csv_path)
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                entity_id = row.get("entity_id", "").strip()
                year_raw = row.get("year", "").strip()
                if not entity_id or not year_raw:
                    continue
                try:
                    year = int(year_raw)
                except ValueError:
                    continue
                key = (entity_id, year)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    proposed_slug = historical_state_slug(
                        entity_id,
                        year,
                        catalogue_path=catalogue_path,
                    )
                except (ValueError, KeyError):
                    # Skip rows whose entity_id isn't an electoral
                    # constituency (rollup ids etc.) or whose state code
                    # isn't on the spine. The DRY-RUN proposal is
                    # advisory; it doesn't gate on parse-side coverage.
                    continue
                if proposed_slug == current_slug:
                    continue
                state_code = _state_code_from_entity_id(entity_id)
                event_id = _event_id_for_pair(
                    state_code,
                    year,
                    catalogue_path=catalogue_path,
                )
                if event_id is None:
                    continue
                proposed_file = (
                    f"datasets/data/datapoints/electoral/"
                    f"{proposed_slug}{ELECTORAL_FILE_SUFFIX}"
                )
                current_file = (
                    f"datasets/data/datapoints/electoral/"
                    f"{current_slug}{ELECTORAL_FILE_SUFFIX}"
                )
                yield ProposalRow(
                    entity_id=entity_id,
                    year=year,
                    current_file=current_file,
                    proposed_file=proposed_file,
                    formation_event_id=event_id,
                )


def write_proposal(
    rows: Iterable[ProposalRow],
    output_path: Path,
) -> int:
    """Write the proposal CSV; return the row count."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["entity_id", "year", "current_file", "proposed_file", "formation_event_id"]
        )
        for row in rows:
            writer.writerow(
                [
                    row.entity_id,
                    row.year,
                    row.current_file,
                    row.proposed_file,
                    row.formation_event_id,
                ]
            )
            row_count += 1
    return row_count


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.elections_state_formation.repartition_dry_run",
        description=(
            "DRY-RUN proposal CSV for re-partitioning pre-formation election "
            "rows into historical-state CSVs (PR-W1b). NO writes."
        ),
    )
    parser.add_argument(
        "--electoral-root",
        type=Path,
        default=DEFAULT_ELECTORAL_ROOT,
        help=(
            "Directory containing the per-state *_election_results.csv "
            f"shards (default: {DEFAULT_ELECTORAL_ROOT})."
        ),
    )
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=DEFAULT_CATALOGUE,
        help=(
            f"State-formation events catalogue (default: {DEFAULT_CATALOGUE})."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=(
            f"Output proposal CSV path (default: {DEFAULT_OUTPUT_PATH})."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.electoral_root.is_dir():
        print(
            f"ERROR: electoral root {args.electoral_root} is not a directory",
            file=sys.stderr,
        )
        return 1
    if not args.catalogue.is_file():
        print(
            f"ERROR: catalogue {args.catalogue} not found",
            file=sys.stderr,
        )
        return 1

    rows = list(iter_proposal_rows(args.electoral_root, args.catalogue))
    row_count = write_proposal(rows, args.output)

    print(
        f"DRY-RUN: wrote {row_count} proposal row(s) to "
        f"{args.output.as_posix()}"
    )
    if row_count == 0:
        print(
            "Proposal is EMPTY. This is a legitimate result: no on-disk "
            "electoral row carries a (state, year) pair that falls into "
            "a known formation event's pre-bifurcation window. Helper "
            "is exercised by the test suite at "
            "backend/tests/test_historical_state_slug.py."
        )
    print(
        "STOP-AND-SURFACE (ESCALATE trigger #1): no row will MOVE under "
        "this PR. The proposal CSV is operator-facing; user sign-off is "
        "required before any per-state CSV re-partition write."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
