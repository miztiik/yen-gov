"""election_events_honesty - flip catalogue data_status to match on-disk truth.

The hand-authored `datasets/taxonomy/election_events.json` catalogue declares
`data_status: "complete"` for many events whose per-event CSV files have not
yet been ingested. The frontend's ElectionsFirehose loader treats `complete`
as a promise that `summary.csv` exists and renders an amber "error" badge
when the load 404s. Citizens read that as "yen-gov is broken" when reality is
"this event is not yet ingested".

This tool walks every event in the catalogue, computes the on-disk path for
its per-event files, and flips `data_status` to `"pending_upstream"` for any
event whose files do not exist. Events whose files DO exist stay `complete`.

Why this is in `tools/` and not `backend/`:

- It is an operator-run honesty sweep over the citizen-facing catalogue,
  not part of the canonical write pipeline. The tool mutates a hand-authored
  catalogue to bring it back into sync with the on-disk truth; the canonical
  writer family (`backend/yen_gov/canonical/`) emits the per-event CSVs that
  this tool checks.
- Per CLAUDE.md section 3 the `tools/` tree is the right home for
  standalone dev/ops utilities that have no `backend/` runtime coupling
  (the tool only reads geo.csv + walks the elections tree).

Run:

    python -m tools.election_events_honesty                # apply
    python -m tools.election_events_honesty --dry-run      # report only
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# Repo root is the parent of tools/<this-pkg>/.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Inputs / outputs (resolved relative to REPO_ROOT at call time so the tool
# is testable with a tmp_path root via build_honesty_report(root=...)).
_GEO_REL = Path("datasets/data/entities/geo.csv")
_CATALOGUE_REL = Path("datasets/taxonomy/election_events.json")
_ELECTIONS_REL = Path("datasets/elections")

# Per-event file pair. Both MUST exist on disk for an event to count as
# "complete"; either missing flips the row to "pending_upstream".
_PER_EVENT_FILES: tuple[str, ...] = ("candidacies.csv", "summary.csv")

# event_id grammar (PR-W2a + earlier conventions).
_ASSEMBLY_RE = re.compile(r"^assembly-(\d{4})$")
_PARLIAMENT_RE = re.compile(r"^general-(\d{4})$")


def _state_code_to_slug(root: Path) -> dict[str, str]:
    """Map ECI state code (e.g. S22, U07) to citizen-facing slug
    (e.g. tamil-nadu, puducherry) from datasets/data/entities/geo.csv.

    The slug is the `entity_id` column; the ECI code lives in the
    pipe-separated `aliases` column alongside ISO-3166 and LGD codes.
    """
    geo_path = root / _GEO_REL
    with geo_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out: dict[str, str] = {}
    for r in rows:
        if r.get("entity_kind") != "state":
            continue
        slug = r.get("entity_id") or ""
        if not slug:
            continue
        for a in (r.get("aliases") or "").split("|"):
            m = re.match(r"^([SU])(\d{2})$", a.strip())
            if m:
                out[f"{m.group(1)}{m.group(2)}"] = slug
    return out


def _disk_paths(
    state_code: str,
    event: dict[str, Any],
    *,
    code_to_slug: dict[str, str],
    elections_root: Path,
) -> list[Path]:
    """Return the on-disk path list for one event. Empty list means
    "no canonical disk pattern for this (kind, event_id) combination" -
    e.g. bye-elections are not yet emitted to a uniform per-event tree
    and are treated as never-complete (correctly flipped to pending).
    """
    kind = event.get("kind")
    event_id = str(event.get("event_id", ""))
    slug = code_to_slug.get(state_code)
    if kind == "assembly" and slug is not None:
        m = _ASSEMBLY_RE.match(event_id)
        if m:
            d = elections_root / "assembly" / f"state={slug}" / f"election={m.group(1)}"
            return [d / name for name in _PER_EVENT_FILES]
    if kind == "parliament":
        m = _PARLIAMENT_RE.match(event_id)
        if m:
            d = elections_root / "parliament" / f"election={m.group(1)}"
            return [d / name for name in _PER_EVENT_FILES]
    # Bye-elections (assembly_bye / general_bye / by_election) have no
    # canonical per-event tree today; they always flip to pending_upstream
    # until the bye-ingest seam lands.
    return []


def build_honesty_report(root: Path) -> dict[str, Any]:
    """Compute the flip plan WITHOUT mutating the catalogue. Returns a
    structured report the CLI prints and the tests assert against.
    """
    code_to_slug = _state_code_to_slug(root)
    catalogue_path = root / _CATALOGUE_REL
    elections_root = root / _ELECTIONS_REL
    catalogue: dict[str, Any] = json.loads(catalogue_path.read_text(encoding="utf-8"))

    total = 0
    kept_complete = 0
    flipped: list[dict[str, str]] = []
    already_pending = 0
    no_pattern_flipped: list[dict[str, str]] = []

    for state_code, events in catalogue.get("states", {}).items():
        for ev in events:
            total += 1
            current_status = ev.get("data_status")
            paths = _disk_paths(
                state_code,
                ev,
                code_to_slug=code_to_slug,
                elections_root=elections_root,
            )
            if not paths:
                # No canonical disk pattern -> must be pending. Either
                # flip now or it's already pending.
                if current_status == "pending_upstream":
                    already_pending += 1
                else:
                    no_pattern_flipped.append(
                        {
                            "state_code": state_code,
                            "event_id": str(ev.get("event_id", "")),
                            "kind": str(ev.get("kind", "")),
                            "from": str(current_status),
                        }
                    )
                continue
            files_present = all(p.exists() for p in paths)
            if files_present:
                if current_status != "complete":
                    # Already pending with files on disk - unusual; we
                    # report but don't auto-promote. The operator can
                    # rerun if they want; this tool is for the noisy
                    # complete->pending direction only.
                    pass
                kept_complete += 1
            else:
                if current_status == "pending_upstream":
                    already_pending += 1
                else:
                    flipped.append(
                        {
                            "state_code": state_code,
                            "event_id": str(ev.get("event_id", "")),
                            "kind": str(ev.get("kind", "")),
                            "from": str(current_status),
                            "missing": ",".join(
                                str(p.relative_to(root).as_posix())
                                for p in paths
                                if not p.exists()
                            ),
                        }
                    )

    return {
        "total": total,
        "kept_complete": kept_complete,
        "flipped": flipped,
        "no_pattern_flipped": no_pattern_flipped,
        "already_pending": already_pending,
        "to_flip_count": len(flipped) + len(no_pattern_flipped),
    }


def apply_flips(root: Path, report: dict[str, Any]) -> None:
    """Mutate the catalogue in-place: any row in report["flipped"] or
    report["no_pattern_flipped"] gets data_status set to "pending_upstream".
    Writes back with json.dump(indent=2, ensure_ascii=False).
    """
    catalogue_path = root / _CATALOGUE_REL
    catalogue: dict[str, Any] = json.loads(catalogue_path.read_text(encoding="utf-8"))
    flips_by_key: set[tuple[str, str]] = set()
    for row in report["flipped"]:
        flips_by_key.add((row["state_code"], row["event_id"]))
    for row in report["no_pattern_flipped"]:
        flips_by_key.add((row["state_code"], row["event_id"]))
    for state_code, events in catalogue.get("states", {}).items():
        for ev in events:
            if (state_code, str(ev.get("event_id", ""))) in flips_by_key:
                ev["data_status"] = "pending_upstream"
    text = json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n"
    catalogue_path.write_text(text, encoding="utf-8")


def _print_report(report: dict[str, Any], *, applied: bool) -> None:
    print(f"Total events:            {report['total']}")
    print(f"Kept complete (on disk): {report['kept_complete']}")
    print(f"Already pending:         {report['already_pending']}")
    print(f"To flip -> pending:      {report['to_flip_count']}")
    print(
        f"  - with disk pattern, files missing: {len(report['flipped'])}"
    )
    print(
        f"  - no canonical disk pattern (bye-elections): "
        f"{len(report['no_pattern_flipped'])}"
    )
    if applied:
        print("Applied: catalogue rewritten in place.")
    else:
        print("Dry run: catalogue NOT rewritten.")
    print()
    sample = (report["flipped"] + report["no_pattern_flipped"])[:10]
    if sample:
        print("First flips:")
        for row in sample:
            print(
                f"  {row['state_code']:>4} {row['kind']:<14} "
                f"{row['event_id']}"
            )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Flip catalogue events whose per-event CSVs are not on disk "
            "from data_status:complete -> pending_upstream."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report without rewriting the catalogue.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT,
        help="Repo root (default: auto-derived from this file's location).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_honesty_report(args.root)
    if not args.dry_run and report["to_flip_count"] > 0:
        apply_flips(args.root, report)
        _print_report(report, applied=True)
    else:
        _print_report(report, applied=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
