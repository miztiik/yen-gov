"""
Bootstrap `datasets/reference/in/states/<S>/constituencies.json` for every
state that already has ECI election results on disk.

Why this exists
---------------
The original `python -m yen_gov reference <state>` command scrapes Wikipedia
for AC names + reservation. That was a Phase-0 expedient when we had no
ingested election results and Wikipedia was the only freely available
machine-readable list of ACs. After Phase 6/N2 landed (commit 29da524) we
have ECI Statistical Report Section-10 Excel files ingested for 14 states,
and every per-AC result file already carries `eci_no` + `constituency_name`
(which encodes reservation as a `(SC)` / `(ST)` suffix per ECI's own
publication convention). That is the canonical source — going to Wikipedia
to re-derive what ECI already published is a worse pipeline.

This script walks the on-disk election results for one state and emits a
`status: provisional` constituencies.json keyed by ECI number, with
`sources` pointing at the ECI Statistical Report URLs the data actually
came from. Districts and PC mapping (which `status: complete` requires)
are left for a future LGD-codes pass; the schema's `provisional` tier was
designed exactly for this case.

Usage
-----
    python tools/bootstrap_constituencies_from_results.py S01
    python tools/bootstrap_constituencies_from_results.py --all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS = REPO_ROOT / "datasets"
ELECTION_EVENTS = DATASETS / "reference" / "in" / "election-events.json"

# ECI publishes constituency names with the reservation as a parenthetical
# suffix, e.g. "PALAKONDA (ST)" or "YERRAGONDAPALEM (SC) (SC)" (the
# duplicated suffix is an upstream artefact in some 2024 reports). Strip
# any number of trailing reservation tags and capture the last one as
# authoritative.
_RES_TAG = re.compile(r"\s*\((SC|ST|GEN)\)\s*$", re.IGNORECASE)


def _strip_reservation(raw_name: str) -> tuple[str, str]:
    """Return (clean_name, reservation). Repeats the strip until no tag
    remains so that doubled `(SC) (SC)` collapses cleanly."""
    name = raw_name.strip()
    reservation = "GEN"
    while True:
        m = _RES_TAG.search(name)
        if not m:
            break
        reservation = m.group(1).upper()
        name = name[: m.start()].rstrip()
    # Convert ECI's UPPER CASE to title case so the citizen-facing UI looks
    # right. Leave acronyms alone where the file already uses mixed case.
    if name.isupper():
        name = name.title()
    return name, reservation


def _default_event_for_state(catalogue: dict, state_code: str) -> dict | None:
    rows = catalogue.get("states", {}).get(state_code, [])
    for row in rows:
        if row.get("default") and row.get("data_status") == "complete":
            return row
    # Fall back to first complete row.
    for row in rows:
        if row.get("data_status") == "complete":
            return row
    return None


def bootstrap_state(state_code: str, catalogue: dict, *, dry_run: bool = False) -> str:
    event_row = _default_event_for_state(catalogue, state_code)
    if event_row is None:
        return f"{state_code}: SKIP — no event with data_status=complete in catalogue"

    event_id = event_row["event_id"]
    state_dir = DATASETS / "elections" / event_id / state_code
    results_dir = state_dir / "results"
    summary_path = state_dir / "result.summary.json"
    if not results_dir.exists():
        return f"{state_code}: SKIP — {results_dir} missing"

    # Load summary for upstream provenance.
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    upstream_sources = summary.get("sources", [])

    items: list[dict] = []
    for f in sorted(results_dir.iterdir()):
        if not f.suffix == ".json":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        eci_no = d["eci_no"]
        raw = d.get("constituency_name", "").strip()
        if not raw:
            return f"{state_code}: ERROR — {f.name} has no constituency_name"
        name, reservation = _strip_reservation(raw)
        items.append({"eci_no": eci_no, "name": name, "reservation": reservation})

    items.sort(key=lambda x: x["eci_no"])

    out = {
        "$schema": "https://yen-gov.github.io/schemas/constituency.schema.json",
        "$schema_version": "4.1",
        "sources": upstream_sources,
        "state": state_code,
        "body": "AC",
        "status": "provisional",
        "constituencies": items,
    }

    out_dir = DATASETS / "reference" / "in" / "states" / state_code
    out_path = out_dir / "constituencies.json"
    if out_path.exists():
        return f"{state_code}: SKIP — {out_path.relative_to(REPO_ROOT).as_posix()} already exists (refusing to overwrite hand-authored or scraped data)"

    if dry_run:
        return f"{state_code}: WOULD WRITE {len(items)} ACs to {out_path.relative_to(REPO_ROOT).as_posix()}"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return f"{state_code}: OK — wrote {len(items)} ACs to {out_path.relative_to(REPO_ROOT).as_posix()}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("state", nargs="?", help="ECI state code (e.g. S01); omit when using --all")
    p.add_argument("--all", action="store_true", help="Bootstrap every state with data_status=complete")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    catalogue = json.loads(ELECTION_EVENTS.read_text(encoding="utf-8"))

    if args.all:
        states = sorted(catalogue.get("states", {}).keys())
    elif args.state:
        states = [args.state.upper()]
    else:
        p.error("provide a state code or --all")
        return 2

    for sc in states:
        print(bootstrap_state(sc, catalogue, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
