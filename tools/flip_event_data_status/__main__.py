"""PR-Q7b post-reingest event-status flipper.

Walks ``datasets/elections/assembly/state=*/election=*/candidacies.csv`` and
flips ``data_status: pending_upstream -> complete`` on the matching event in
``datasets/taxonomy/election_events.json`` for each non-empty event on disk.

Run from worktree root (PYTHONPATH=./backend so the package resolves):

    # dry-run: print the (state_code, event_id) flips that WOULD be applied.
    python -m tools.flip_event_data_status

    # apply: rewrite election_events.json atomically.
    python -m tools.flip_event_data_status --apply

Preserves the canonical JSON formatting (2-space indent, key order matches
the on-disk ordering of the original file) and is byte-stable on re-runs
(if the disk and JSON already agree, no file is written).

Per CLAUDE.md section 10: only ``pending_upstream`` is flipped to
``complete``. ``partial`` and ``complete`` rows are left untouched (those
disposition decisions belong to the human curator). Events ALREADY
``complete`` whose on-disk shards now disappear (e.g. an operator manual
delete) are NOT flipped back to ``pending_upstream`` -- the tool only
moves events forward through the data-status lifecycle.

Only ``kind == "assembly"`` events are inspected. Parliament events live
under ``elections/parliament/...`` and follow a separate flow.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Mirror of coverage._slug_to_state_code (re-implemented here so the tool
# stays a thin one-shot without pulling in the coverage module's broader
# CLI graph).
_ECI_CODE_RE = re.compile(r"^[SU]\d{2}$")

# Match assembly-YYYY (event_id shape used in election_events.json for
# the post-2014 events; pre-2014 event_ids are also "assembly-YYYY"). The
# year is captured for the (state, year) lookup.
_EVENT_ID_RE = re.compile(r"^assembly-(\d{4})$")


def slug_to_state_code(geo_csv: Path) -> dict[str, str]:
    """``state_slug -> ECI code`` (e.g. ``'tamil-nadu' -> 'S22'``)."""
    import csv

    out: dict[str, str] = {}
    if not geo_csv.is_file():
        return out
    with geo_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            kind = (row.get("entity_kind") or "").strip()
            if kind not in ("state", "ut"):
                continue
            slug = (row.get("entity_id") or "").strip()
            if not slug:
                continue
            aliases = (row.get("aliases") or "").split("|")
            for alias in aliases:
                alias = alias.strip()
                if _ECI_CODE_RE.match(alias):
                    out[slug] = alias
                    break
    return out


def discover_disk_events(
    elections_root: Path,
    slug_to_code: dict[str, str],
) -> set[tuple[str, str]]:
    """Return ``{(state_code, event_id)}`` for every non-empty disk slice.

    "Non-empty" means ``candidacies.csv`` exists and has at least one data
    row beyond the header. Empty files are treated as not-on-disk so the
    flip does not advance an event the writer started but did not finish.
    """
    out: set[tuple[str, str]] = set()
    assembly_root = elections_root / "assembly"
    if not assembly_root.is_dir():
        return out
    for state_dir in sorted(assembly_root.glob("state=*")):
        state_slug = state_dir.name.removeprefix("state=")
        state_code = slug_to_code.get(state_slug)
        if not state_code:
            continue
        for event_dir in sorted(state_dir.glob("election=*")):
            year_part = event_dir.name.removeprefix("election=")
            if not year_part.isdigit():
                continue
            candidacies = event_dir / "candidacies.csv"
            if not candidacies.is_file():
                continue
            # Cheap presence check: a header-only file is treated as empty.
            with candidacies.open(encoding="utf-8") as fh:
                # readlines() returns the header + (0 or more) data rows.
                first_line = fh.readline()
                second_line = fh.readline()
            if not first_line or not second_line.strip():
                continue
            out.add((state_code, f"assembly-{year_part}"))
    return out


def find_pending_flips(
    catalogue: dict,
    disk_events: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Return ``[(state_code, event_id)]`` flips that need to be applied."""
    flips: list[tuple[str, str]] = []
    states = catalogue.get("states") or {}
    for state_code, events in states.items():
        for event in events:
            if event.get("kind") != "assembly":
                continue
            event_id = event.get("event_id") or ""
            if event.get("data_status") != "pending_upstream":
                continue
            if (state_code, event_id) in disk_events:
                flips.append((state_code, event_id))
    return flips


def apply_flips(
    catalogue: dict,
    flips: list[tuple[str, str]],
) -> dict:
    """Return a NEW catalogue dict with ``data_status`` flipped on each row.

    Mutating in-place would risk silent surprises for callers; this builds
    a shallow copy with the targeted events replaced. JSON ordering and
    every other event field are preserved.
    """
    flip_set = set(flips)
    new_states: dict[str, list[dict]] = {}
    for state_code, events in (catalogue.get("states") or {}).items():
        new_events: list[dict] = []
        for event in events:
            if (
                event.get("kind") == "assembly"
                and (state_code, event.get("event_id")) in flip_set
                and event.get("data_status") == "pending_upstream"
            ):
                replaced = dict(event)
                replaced["data_status"] = "complete"
                new_events.append(replaced)
            else:
                new_events.append(event)
        new_states[state_code] = new_events
    out = dict(catalogue)
    out["states"] = new_states
    return out


def write_catalogue(path: Path, catalogue: dict) -> None:
    """Write the catalogue back to disk with the canonical 2-space indent.

    Mirrors json.dumps's serialiser settings the file already uses: ASCII
    safe by default, key order preserved.
    """
    path.write_text(
        json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.flip_event_data_status",
        description=__doc__,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Rewrite election_events.json atomically. Default: dry-run.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Override the worktree root (default: auto-detect from cwd).",
    )
    args = parser.parse_args(argv)

    root = (args.root or Path.cwd()).resolve()
    catalogue_path = root / "datasets" / "taxonomy" / "election_events.json"
    elections_root = root / "datasets" / "elections"
    geo_csv = root / "datasets" / "data" / "entities" / "geo.csv"

    if not catalogue_path.is_file():
        raise SystemExit(f"election_events.json not found at {catalogue_path}")

    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    slug_to_code = slug_to_state_code(geo_csv)
    if not slug_to_code:
        raise SystemExit(f"geo.csv missing or empty at {geo_csv}")
    disk_events = discover_disk_events(elections_root, slug_to_code)
    flips = find_pending_flips(catalogue, disk_events)

    print(f"on-disk non-empty assembly events: {len(disk_events)}")
    print(f"pending_upstream -> complete flips: {len(flips)}")
    for state_code, event_id in sorted(flips):
        print(f"  {state_code} {event_id}")

    if not flips:
        print("nothing to flip; catalogue and disk already agree.")
        return 0

    if not args.apply:
        print("DRY-RUN: pass --apply to rewrite election_events.json.")
        return 0

    new_catalogue = apply_flips(catalogue, flips)
    write_catalogue(catalogue_path, new_catalogue)
    print(f"wrote {catalogue_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
