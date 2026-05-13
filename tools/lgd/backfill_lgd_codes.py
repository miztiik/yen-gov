"""tools/lgd/backfill_lgd_codes.py — fill `lgd_code` on every district item.

Reads:
  datasets/reference/in/states.json                    (eci_code -> English name)
  datasets/reference/in/lgd/states-latest.csv          (LGD State Code -> English name)
  datasets/reference/in/lgd/districts-latest.csv       (LGD District Code, State Code, name)
  datasets/reference/in/states/<S>/districts.json      (per-state collections)

For each districts.json:
  1. Map state's eci_code -> English name -> LGD State Code (via name match).
  2. Filter the LGD districts CSV to that state's rows.
  3. For each district item, normalize name and look up LGD numeric code.
  4. Write `lgd_code` field. Leave `id`/`id_source` untouched (cross-references
     in constituencies.json depend on them; LGD is an additive bridge per
     district.schema.json v3.2).
  5. Report unmatched districts (per state).

Run from repo root:
  .venv\\Scripts\\python.exe tools\\lgd\\backfill_lgd_codes.py
Add --apply to write; without it the script is a dry-run preview.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATES_JSON = REPO / "datasets" / "reference" / "in" / "states.json"
LGD_STATES_CSV = REPO / "datasets" / "reference" / "in" / "lgd" / "states-latest.csv"
LGD_DISTRICTS_CSV = REPO / "datasets" / "reference" / "in" / "lgd" / "districts-latest.csv"
DISTRICTS_ROOT = REPO / "datasets" / "reference" / "in" / "states"


# Manual aliases for known canonical-name divergences between our reference
# data and the LGD opendata CSV. Keys are repo-side district names exactly as
# they appear in our districts.json `name` field; values are the LGD
# `District Name(In English)` they should match.
DISTRICT_ALIASES: dict[str, str] = {
    # Tamil Nadu
    "Chennai (formerly Madras)": "Chennai",
    "Kanyakumari": "Kanniyakumari",
    "Nilgiris": "The Nilgiris",
    "Thoothukudi": "Thoothukkudi",
    "Tiruvallur": "Thiruvallur",
    "Tiruvarur": "Thiruvarur",
    # Gujarat
    "Aravalli": "Arvalli",
    "Mehsana": "Mahesana",
    "Chhota Udaipur": "Chhotaudepur",
    "Panchmahal": "Panch Mahals",
    "Dang": "Dangs",
    "Devbhoomi Dwarka": "Devbhumi Dwarka",
    "Kutch": "Kachchh",
    # West Bengal
    "Maldah": "Malda",
    # Assam
    "South Salmara-Mankachar": "South Salmara Mancachar",
    "Kamrup Metropolitan": "Kamrup Metro",
    "Morigaon": "Marigaon",
    "Sibsagar": "Sivasagar",
}


def _norm(s: str) -> str:
    """Lowercase, strip non-alphanumeric — robust against punctuation/whitespace drift."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_state_lgd_bridge() -> dict[str, str]:
    """eci_code -> LGD State Code (string) via canonical English name match."""
    states = json.loads(STATES_JSON.read_text(encoding="utf-8"))["states"]
    name_to_eci = {_norm(s["name"]): s["eci_code"] for s in states}

    bridge: dict[str, str] = {}
    with LGD_STATES_CSV.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            key = _norm(row["State Name (In English)"])
            eci = name_to_eci.get(key)
            if eci:
                bridge[eci] = row["State Code"]
    return bridge


def load_districts_by_state() -> dict[str, list[dict[str, str]]]:
    """LGD State Code -> [ {District Code, District Name (In English)}, ... ]."""
    out: dict[str, list[dict[str, str]]] = {}
    with LGD_DISTRICTS_CSV.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["State Code"], []).append(
                {
                    "code": row["District Code"],
                    "name": row["District Name(In English)"],
                }
            )
    return out


def backfill_one(
    state_path: Path,
    state_lgd_code: str,
    lgd_districts: list[dict[str, str]],
) -> tuple[int, int, list[str], dict]:
    """Returns (matched, total, unmatched_names, mutated_doc)."""
    doc = json.loads(state_path.read_text(encoding="utf-8"))
    by_norm = {_norm(d["name"]): d["code"] for d in lgd_districts}

    # Bump declared $schema_version to 3.2 — adding lgd_code is the v3.2 change.
    doc["$schema_version"] = "3.2"

    matched = 0
    unmatched: list[str] = []
    for item in doc["districts"]:
        repo_name = item["name"]
        alias = DISTRICT_ALIASES.get(repo_name, repo_name)
        code = by_norm.get(_norm(alias))
        if code is not None:
            item["lgd_code"] = code
            matched += 1
        else:
            unmatched.append(repo_name)

    return matched, len(doc["districts"]), unmatched, doc


def write_doc(state_path: Path, doc: dict) -> None:
    state_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    args = parser.parse_args()

    bridge = load_state_lgd_bridge()
    by_state = load_districts_by_state()

    print(f"Loaded {len(bridge)} state bridges, {sum(len(v) for v in by_state.values())} LGD districts.\n")

    total_matched = 0
    total_districts = 0
    all_unmatched: list[tuple[str, str]] = []

    for state_path in sorted(DISTRICTS_ROOT.glob("*/districts.json")):
        eci_code = state_path.parent.name
        lgd_state = bridge.get(eci_code)
        if not lgd_state:
            print(f"[{eci_code}] SKIP — no LGD State Code bridge")
            continue
        districts = by_state.get(lgd_state, [])
        m, t, unmatched, doc = backfill_one(state_path, lgd_state, districts)
        total_matched += m
        total_districts += t
        flag = "OK" if not unmatched else "PARTIAL"
        print(f"[{eci_code}] {flag} matched {m}/{t} (LGD state {lgd_state})")
        for name in unmatched:
            print(f"    UNMATCHED: {name!r}")
            all_unmatched.append((eci_code, name))
        if args.apply:
            write_doc(state_path, doc)

    print(f"\nTotal: {total_matched}/{total_districts} districts matched.")
    if all_unmatched:
        print(f"{len(all_unmatched)} unmatched — extend DISTRICT_ALIASES in this script.")
    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write.")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
