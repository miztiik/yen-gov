"""Bulk-ingest hand-downloaded ECI Section 10 XLSX dumps from datasets/ephemeral/.

Drives `python -m yen_gov eci-statreport-emit-local` over every state-level
assembly-election XLSX in datasets/ephemeral/, recording per-file outcome
in datasets/ephemeral/_ingest_inventory.json. Source files are deleted on
complete success; failed files stay put for re-run.

Out of scope (left in datasets/ephemeral/ untouched):
  - PDFs (pre-EVM scanned reports — no XLSX pipeline path).
  - Lok Sabha XLS (Section 10 is per-PC with different columns; planning
    work pending. Recognised by ``_loksabha_`` in the filename).

Filename grammar handled (case-insensitive on the state token):

    YYYY[_state]_<state_token>[_<rest>].xls{,x}

Where ``<state_token>`` is one of the known state names in
``cli._LOCAL_NAME_TO_ECI`` (greedy longest-match so ``uttar_pradesh`` wins
over ``uttar``). Anything that does not match is recorded as a parse-error
row in the inventory.

Usage::

    python tools/ingest_ephemeral_ae.py            # ingest all
    python tools/ingest_ephemeral_ae.py --dry-run  # plan only, no edits
    python tools/ingest_ephemeral_ae.py --in-place # leave source in ephemeral/

Re-running is idempotent: any (event_id, state_code) whose
``datasets/elections/<event>/<state>/results/`` already holds JSON files
is skipped (status="already_ingested"). Duplicates (two files mapping to
the same (event, state)) are also skipped after the first.

Safety policy (2026-05-17):
  - On a successful new ingest, the source XLSX is MOVED (not deleted) to
    ``datasets/ephemeral/.ingested/``. The operator can bulk-delete that
    subdir after auditing.
  - The driver NEVER touches the source on the ``already_ingested`` branch:
    a pre-existing results dir is not proof that THIS source produced it
    (could be partial output from an earlier failed run, could be from a
    different file). Only the freshly-successful ``ok`` branch consumes
    the source.
  - ``Path.unlink()`` is never called. Recovery from operator mistakes is
    a Move-Item away.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout on Windows (lesson: cp1252 chokes on emit symbols).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

REPO = Path(__file__).resolve().parents[1]
EPHEMERAL = REPO / "datasets" / "ephemeral"
INGESTED = EPHEMERAL / ".ingested"
ELECTIONS = REPO / "datasets" / "elections"
INVENTORY = EPHEMERAL / "_ingest_inventory.json"

# Mirrors _LOCAL_NAME_TO_ECI in backend/yen_gov/cli.py. Keep in sync if
# new state tokens land there. Sorted longest-first for greedy matching.
NAME_TO_ECI: dict[str, str] = {
    "andhra_pradesh": "S01", "arunachal_pradesh": "S02", "assam": "S03",
    "bihar": "S04", "goa": "S05", "gujarat": "S06", "haryana": "S07",
    "himachal_pradesh": "S08", "karnataka": "S10", "kerala": "S11",
    "madhya_pradesh": "S12", "maharashtra": "S13", "manipur": "S14",
    "meghalaya": "S15", "mizoram": "S16", "nagaland": "S17",
    "odisha": "S18", "punjab": "S19", "rajasthan": "S20", "sikkim": "S21",
    "tamil_nadu": "S22", "tripura": "S23", "uttar_pradesh": "S24",
    "west_bengal": "S25", "chhattisgarh": "S26", "jharkhand": "S27",
    "uttarakhand": "S28", "telangana": "S29",
    "delhi": "U05", "puducherry": "U07", "jammu_kashmir": "U08",
}
TOKENS_BY_LEN = sorted(NAME_TO_ECI.keys(), key=len, reverse=True)

YEAR_PREFIX = re.compile(r"^(?P<year>\d{4})_(?:state_)?", re.IGNORECASE)

# Files to leave in place even though they are .xls{,x}.
SKIP_NAME_TOKENS = ("_loksabha_", "loksabha_")


def parse_filename(name: str) -> tuple[int, str, str] | None:
    """Return (year, state_token, eci_state_code) or None if not parseable."""
    m = YEAR_PREFIX.match(name)
    if m is None:
        return None
    year = int(m.group("year"))
    rest = name[m.end():].lower()
    for tok in TOKENS_BY_LEN:
        if rest.startswith(tok):
            return year, tok, NAME_TO_ECI[tok]
    return None


def already_ingested(event_id: str, state: str) -> bool:
    # A state-event is "fully ingested" only when ALL THREE artifacts the
    # emit pipeline produces exist: per-AC results JSONs, the rolled-up
    # result.summary.json, AND parties.json. Presence of just results/
    # JSONs proves nothing — a previous run could have crashed mid-emit
    # (e.g. parties.json write failed on a UNIQUE constraint), leaving a
    # partial directory that would otherwise be mistaken for done.
    sd = ELECTIONS / event_id / state
    rd = sd / "results"
    return (
        rd.is_dir()
        and any(rd.glob("*.json"))
        and (sd / "result.summary.json").exists()
        and (sd / "parties.json").exists()
    )


def load_inventory() -> dict:
    if INVENTORY.exists():
        return json.loads(INVENTORY.read_text(encoding="utf-8"))
    return {"runs": [], "files": {}}


def save_inventory(inv: dict) -> None:
    INVENTORY.write_text(
        json.dumps(inv, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_emit(file: Path, state: str, year: int) -> tuple[bool, str]:
    """Invoke the existing CLI command. Returns (ok, combined_output)."""
    cmd = [
        sys.executable, "-m", "yen_gov", "eci-statreport-emit-local",
        str(file), "--state", state, "--year", str(year), "--keep-source",
    ]
    proc = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Plan only; do not run emit or move files.")
    ap.add_argument("--in-place", action="store_true",
                    help="Leave source files in datasets/ephemeral/ on "
                         "success (default: move to .ingested/).")
    args = ap.parse_args()

    if not EPHEMERAL.is_dir():
        print(f"error: {EPHEMERAL} does not exist", file=sys.stderr)
        return 2

    candidates = sorted(
        p for p in EPHEMERAL.iterdir()
        if p.is_file() and p.suffix.lower() in {".xls", ".xlsx"}
        and not any(tok in p.name.lower() for tok in SKIP_NAME_TOKENS)
    )

    inv = load_inventory()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_rows: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()

    print(f"ephemeral AE ingest run {run_id}  files={len(candidates)}  "
          f"dry_run={args.dry_run}\n")

    counts = {"ok": 0, "already": 0, "duplicate": 0, "parse_error": 0,
              "unregistered": 0, "emit_error": 0}

    # Lazy import so the EVENTS table is loaded once per run, not per file.
    sys.path.insert(0, str(REPO / "backend"))
    from yen_gov.sources.eci.events import event_info_for  # noqa: E402

    for src in candidates:
        rel = src.relative_to(REPO).as_posix()
        parsed = parse_filename(src.name)
        if parsed is None:
            row = {"file": rel, "status": "parse_error",
                   "error": "filename does not match YYYY_[state_]<token>_..."}
            counts["parse_error"] += 1
            run_rows.append(row); inv["files"][rel] = row
            print(f"  [PARSE] {rel}"); continue

        year, token, state = parsed
        try:
            event_id = event_info_for(state, year).event_id
        except KeyError as exc:
            row = {"file": rel, "state": state, "year": year,
                   "status": "unregistered", "error": str(exc)}
            counts["unregistered"] += 1
            run_rows.append(row); inv["files"][rel] = row
            print(f"  [NOEVENT] {rel} -> {state}/{year}"); continue

        pair = (event_id, state)
        if already_ingested(event_id, state):
            # NEVER touch the source on this branch. A pre-existing emit
            # dir is not proof that THIS source produced it (could be a
            # partial from a failed run, could be a different file).
            row = {"file": rel, "state": state, "year": year,
                   "event_id": event_id, "status": "already_ingested"}
            counts["already"] += 1
            seen_pairs.add(pair)
            run_rows.append(row); inv["files"][rel] = row
            print(f"  [SKIP-INGESTED] {rel} -> {event_id}/{state}")
            continue

        if pair in seen_pairs:
            row = {"file": rel, "state": state, "year": year,
                   "event_id": event_id, "status": "duplicate",
                   "note": "another file in this run already covers "
                           f"{event_id}/{state}"}
            counts["duplicate"] += 1
            run_rows.append(row); inv["files"][rel] = row
            print(f"  [DUP] {rel} -> {event_id}/{state}"); continue

        if args.dry_run:
            row = {"file": rel, "state": state, "year": year,
                   "event_id": event_id, "status": "planned"}
            run_rows.append(row); inv["files"][rel] = row
            print(f"  [PLAN] {rel} -> {event_id}/{state}")
            seen_pairs.add(pair); continue

        ok, output = run_emit(src, state, year)
        results_dir = ELECTIONS / event_id / state / "results"
        emitted = (
            sum(1 for _ in results_dir.glob("*.json"))
            if results_dir.is_dir() else 0
        )

        if ok and emitted > 0:
            row = {"file": rel, "state": state, "year": year,
                   "event_id": event_id, "status": "ok",
                   "results_emitted": emitted}
            counts["ok"] += 1
            seen_pairs.add(pair)
            moved_to = None
            if not args.in_place:
                INGESTED.mkdir(parents=True, exist_ok=True)
                dest = INGESTED / src.name
                # Don't clobber: append numeric suffix on collision.
                i = 1
                while dest.exists():
                    dest = INGESTED / f"{src.stem} ({i}){src.suffix}"
                    i += 1
                src.rename(dest)
                moved_to = dest.relative_to(REPO).as_posix()
                row["moved_to"] = moved_to
            print(f"  [OK] {rel} -> {event_id}/{state} ({emitted} ACs)"
                  f"{' -> ' + moved_to if moved_to else ''}")
        else:
            row = {"file": rel, "state": state, "year": year,
                   "event_id": event_id, "status": "emit_error",
                   "results_emitted": emitted,
                   "stderr_tail": output[-1200:]}
            counts["emit_error"] += 1
            print(f"  [FAIL] {rel} -> {event_id}/{state}")
            print("    " + (output.strip().splitlines()[-1] if output.strip()
                            else "(no output)"))

        run_rows.append(row); inv["files"][rel] = row

    inv["runs"].append({
        "run_id": run_id,
        "dry_run": args.dry_run,
        "counts": counts,
        "files": [r["file"] for r in run_rows],
    })
    save_inventory(inv)

    print(f"\nrun {run_id} summary: " +
          " ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"inventory: {INVENTORY.relative_to(REPO).as_posix()}")
    return 0 if counts["emit_error"] == 0 and counts["parse_error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
