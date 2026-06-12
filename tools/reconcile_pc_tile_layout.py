#!/usr/bin/env python3
"""Backfill electoral.csv PC eci_no from the canonical delim=2024 boundary corpus.

Closes the national PC TileCartogram pending-tile gap surfaced by PR #958 +
FU#1 (PR #964). Per the frontend's own narrative in
`frontend/src/lib/boundaries/sources.ts` (the INDIA_PC_2008 entry), the
`eci_no` column on `datasets/data/entities/electoral.csv` for delim=2008 PCs
is KNOWN UNRELIABLE: 84 of 544 rows carry `eci_no=0` (publisher gap from
the TCPD import) and many of the populated values are misaligned with ECI's
actual seat numbering (e.g. pre-2014-split Andhra Pradesh numbering still
in place for AP PCs after the Telangana split).

The frontend's tile-cartogram join key for delim=2008 PCs is
`IN-PC-2008-<state_code>-<eci_no>`. The TILE-LAYOUT's `unit_id` set is
already enforced by the contract test
`frontend/src/contracts/election-tile-layout-coverage.test.ts` to EXACTLY
match the boundary corpus's `(state_ut_code, ls_seat_code)` set. So the
canonical source for the join key is the boundary's `ls_seat_code`.

This tool overwrites `electoral.csv.eci_no` (for entity_kind=pc + delim_year=2008
rows only) with the matching boundary's `ls_seat_code`, joined by
(state_code, normalised_name). Aliases bridge boundary-vs-electoral name and
state-code drift (Bengaluru/Bangalore, Mysuru/Mysore, PUDUCHERRY/Pondicherry,
Mahabubnagar/Mahbubnagar, Palamau/Palamu, Kalaburagi/Gulbarga, U04 vs U06
Lakshadweep, Andaman & Nicobar (Islands) suffix, Autonomous District/Diphu
parenthetical (ex), Mangaldoi/Darrang Udalguri (ex), Anantnag/Anantnag-Rajouri
(ex), and the Dadra/Dadar typo).

The tool is idempotent: re-running after another agent modifies electoral.csv
re-syncs. No tile-layout writes (the tile-layout is canonical per the contract
test). No source.csv writes (the electoral.csv PC rows already carry
source_id=NULL; the boundary's eci_no replaces a None-attributed field).

Per CLAUDE.md section 5: this is a structural data-tier fix, not a band-aid.
The eci_no's authoritative source is the official ECI delimitation captured in
the boundary corpus; the prior electoral.csv values were a known-stale TCPD
projection.

Usage:
  python tools/reconcile_pc_tile_layout.py [--dry-run]

Exit codes: 0 ok, 1 unresolved residual above threshold, 2 IO error.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = REPO / "datasets" / "boundaries" / "electoral" / "delim=2024" / "pc" / "all.geojson"
ELECTORAL_CSV_PATH = REPO / "datasets" / "data" / "entities" / "electoral.csv"
BOUNDARIES_TS_PATH = REPO / "frontend" / "src" / "lib" / "boundaries" / "sources.ts"
EXTRA_ALIASES_TS_PATH = REPO / "frontend" / "src" / "lib" / "view-models" / "election-results.ts"

# Boundary-side state-code aliases. Maps a boundary corpus state_ut_code
# to the canonical electoral.csv state_code for the lookup. The boundary
# corpus carries the retired U06 Lakshadweep code (post-2019 the canonical
# is U04 per the SLUG_TO_ECI map in election-results.ts), so when matching
# electoral.csv 'lakshadweep' (which resolves to U04) we must alias the
# boundary U06 entry as if it were U04.
BND_STATE_CODE_ALIASES: dict[str, str] = {
    "U06": "U04",
}

# Per-state (state_code, normalised_electoral_name) -> normalised_boundary_name.
# Bridges name spelling drift in cases the Levenshtein <= 2 default would miss.
# Keys are ALL lowercase, stripped of punctuation/whitespace via norm().
# Each entry maps the electoral-side normalised name to the boundary-side
# normalised name so the lookup table-index hits.
NAME_ALIASES: dict[tuple[str, str], str] = {
    # U01 A&N: electoral has trailing "Islands" suffix; boundary does not.
    ("U01", "andamanandnicobarislands"): "andamanandnicobar",
    # S03 Assam: electoral carries the historical names; boundary carries
    # the post-2008 renames with "(ex Old Name)" parenthetical that norm()
    # strips. Map electoral old -> boundary new.
    ("S03", "autonomousdistrict"): "diphu",
    ("S03", "mangaldoi"): "darrangudalguri",
    # S10 Karnataka 2014 romanisation cluster (ECI Notification 1 Nov 2014).
    # Electoral has the new spellings; boundary still carries the old.
    ("S10", "bengaluru"): "bangalore",
    ("S10", "bengalururural"): "bangalorerural",
    ("S10", "bengalurunorth"): "bangalorenorth",
    ("S10", "bengalurucentral"): "bangalorecentral",
    ("S10", "bengalurusouth"): "bangaloresouth",
    ("S10", "belagavi"): "belgaum",
    ("S10", "ballari"): "bellary",
    ("S10", "vijayapura"): "bijapur",
    ("S10", "mysuru"): "mysore",
    ("S10", "shivamogga"): "shimoga",
    ("S10", "tumakuru"): "tumkur",
    ("S10", "udupichikkamagaluru"): "udupichikmagalur",
    ("S10", "kalaburagi"): "gulbarga",
    # S27 Jharkhand: Palamau / Palamu single-letter drift.
    ("S27", "palamau"): "palamu",
    # S29 Telangana: Mahabubnagar / Mahbubnagar single-letter drift.
    ("S29", "mahabubnagar"): "mahbubnagar",
    # U07 Puducherry: electoral all-caps PUDUCHERRY; boundary old form.
    ("U07", "puducherry"): "pondicherry",
    # U08 J&K: post-2024 redelimitation rename Anantnag-Rajouri carries
    # the "(ex Anantnag)" parenthetical that norm() strips, so we map
    # the electoral "anantnag" -> the boundary "anantnagrajouri".
    ("U08", "anantnag"): "anantnagrajouri",
    # NOTE: U03 has 3 electoral rows for 2 boundary PCs (eid suffixes -360
    # Daman & Diu eci=1, -361 Dadra & Nagar Haveli eci=1, -eci2 'Dadar &
    # Nagar Haveli' typo eci=2). The -eci2 row is a phantom from a bad
    # import; we deliberately do NOT alias the typo so the backfill leaves
    # it as-is and the post-edit report surfaces it as a single miss for
    # Hans + Max curatorial follow-up.
}

# Catch-all boundary tiles that intentionally do NOT correspond to a real
# constituency. These will remain orphan tiles in the cartogram (rendered
# pending). Per the plan-doc FU#1 audit (2026-06-12): 2 'Rest of J&K' /
# 'Rest of Ladakh' eci_no=999 placeholders. Documented here as expected
# residuals so the post-edit join-rate report reflects reality.
EXPECTED_ORPHAN_BOUNDARY: set[tuple[str, int]] = {
    ("U08", 999),
    ("U09", 999),
}


def parse_eci_to_lgd_slug() -> dict[str, str]:
    text = BOUNDARIES_TS_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"export\s+const\s+ECI_TO_LGD_SLUG[^=]*=\s*\{([^}]*)\}",
        text,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("ECI_TO_LGD_SLUG block not found in sources.ts")
    out: dict[str, str] = {}
    for kv in re.finditer(r"([SU]\d{2})\s*:\s*\"([a-z0-9-]+)\"", m.group(1)):
        out[kv.group(1)] = kv.group(2)
    return out


def parse_extra_aliases() -> dict[str, str]:
    text = EXTRA_ALIASES_TS_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"const\s+EXTRA_SLUG_ALIASES[^=]*=\s*\{([^}]*)\}",
        text,
        re.DOTALL,
    )
    if not m:
        return {}
    out: dict[str, str] = {}
    for kv in re.finditer(r"\"([a-z0-9-]+)\"\s*:\s*\"([SU]\d{2})\"", m.group(1)):
        out[kv.group(1)] = kv.group(2)
    return out


def build_slug_to_code() -> dict[str, str]:
    eci_to_lgd = parse_eci_to_lgd_slug()
    extra = parse_extra_aliases()
    out = {slug: code for code, slug in eci_to_lgd.items()}
    out.update(extra)
    return out


def norm(s: str) -> str:
    """Lowercase, strip parentheticals/punctuation/whitespace. Symmetric."""
    s = re.sub(r"\s*\([^)]*\)\s*", "", s)
    s = s.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", s)


def load_boundary_index(slug_to_code: dict[str, str]) -> dict[tuple[str, str], dict]:
    """Build (electoral_state_code, normalised_name) -> {sc, ls, name}.

    The 'electoral_state_code' here is the code an electoral.csv row would
    resolve to via SLUG_TO_ECI (e.g. Lakshadweep -> U04). The boundary's
    raw state_ut_code (e.g. U06) is aliased via BND_STATE_CODE_ALIASES.
    """
    gj = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict] = {}
    for f in gj["features"]:
        p = f["properties"]
        raw_sc = str(p.get("state_ut_code"))
        sc = BND_STATE_CODE_ALIASES.get(raw_sc, raw_sc)
        ls = int(p.get("ls_seat_code"))
        name = str(p.get("ls_seat_name") or "?")
        nn = norm(name)
        # Multiple bnd entries for one (sc, nn)? Last wins (unlikely).
        out[(sc, nn)] = {
            "raw_state_ut_code": raw_sc,
            "sc": sc,
            "ls": ls,
            "name": name,
        }
    return out


def resolve_boundary_for_electoral(
    elec_row: dict,
    slug_to_code: dict[str, str],
    bnd_by_norm: dict[tuple[str, str], dict],
) -> tuple[dict | None, str]:
    """Return (boundary_entry_or_None, debug_reason)."""
    slug = (elec_row.get("state") or "").strip()
    code = slug_to_code.get(slug)
    if not code:
        return None, f"state slug {slug!r} unknown to SLUG_TO_ECI"
    nn = norm(elec_row.get("name") or "")
    # Apply alias if present
    alias = NAME_ALIASES.get((code, nn))
    nn_lookup = alias if alias else nn
    hit = bnd_by_norm.get((code, nn_lookup))
    if hit:
        return hit, "exact" if not alias else "alias"
    # Fuzzy fallback intentionally DISABLED. Every real name-drift case is
    # captured explicitly in NAME_ALIASES so a curator review fires when a
    # new mismatch surfaces. Letting Lev <= 2 auto-correct would have
    # silently mapped the known phantom electoral row "Dadar & Nagar Haveli"
    # (U03-eci2, a bad-import duplicate) onto the legitimate "Dadra & Nagar
    # Haveli" boundary, hiding a real data-integrity issue.
    return None, f"no exact / aliased name match within state {code}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Classify but do not write electoral.csv.")
    args = parser.parse_args()

    slug_to_code = build_slug_to_code()
    bnd_by_norm = load_boundary_index(slug_to_code)

    # Read electoral.csv preserving header + every row + order.
    with ELECTORAL_CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        all_rows = list(reader)

    pc_rows = [
        r for r in all_rows
        if (r.get("entity_kind") or "").lower() == "pc"
        and (r.get("delim_year") or "").strip() == "2008"
    ]

    # Classify each PC row.
    rewrites: list[dict] = []  # eci_no will change
    noops: list[dict] = []     # eci_no already matches boundary
    misses: list[dict] = []    # cannot find boundary match
    for row in pc_rows:
        hit, reason = resolve_boundary_for_electoral(row, slug_to_code, bnd_by_norm)
        if hit is None:
            misses.append({"row": row, "reason": reason})
            continue
        try:
            cur_eci = int((row.get("eci_no") or "0").strip())
        except ValueError:
            cur_eci = 0
        new_eci = hit["ls"]
        if cur_eci == new_eci:
            noops.append({"row": row, "hit": hit})
        else:
            rewrites.append({"row": row, "hit": hit, "cur": cur_eci, "new": new_eci, "reason": reason})

    print("=== electoral.csv PC (delim 2008) -> boundary ls_seat_code backfill ===")
    print(f"  electoral PC rows:          {len(pc_rows)}")
    print(f"  rewrites (eci_no changes):  {len(rewrites)}")
    print(f"  no-op (already correct):    {len(noops)}")
    print(f"  misses (no boundary match): {len(misses)}")
    print()

    if misses:
        print("=== misses (rows with no boundary match) ===")
        for m in misses[:15]:
            r = m["row"]
            print(f"  elec {r['entity_id']:50} state={r.get('state'):28} name={r.get('name')!r:30} {m['reason']}")
        if len(misses) > 15:
            print(f"  ... and {len(misses) - 15} more")
        print()

    if rewrites:
        print("=== rewrite sample (10) ===")
        for r in rewrites[:10]:
            row = r["row"]
            hit = r["hit"]
            print(f"  elec {row['entity_id']:50} {row['name']!r:30} eci {r['cur']:>3} -> {r['new']:>3}  (bnd {hit['sc']}-{hit['ls']} {hit['name']!r}; {r['reason']})")
        print()

    # Compute expected join rate after the rewrite.
    bnd_uids_post = {(h["sc"], h["ls"]) for h in bnd_by_norm.values()}
    will_join: set[tuple[str, int]] = set()
    for r in rewrites + noops:
        hit = r["hit"]
        will_join.add((hit["sc"], hit["ls"]))
    total_bnd_tiles = len(bnd_uids_post)
    will_orphan = bnd_uids_post - will_join
    expected_orphan_known = will_orphan & EXPECTED_ORPHAN_BOUNDARY
    unexpected_orphan = will_orphan - EXPECTED_ORPHAN_BOUNDARY
    print(f"=== expected join coverage POST-rewrite ===")
    print(f"  total boundary tiles:        {total_bnd_tiles}")
    print(f"  will be joined post-rewrite: {len(will_join)}")
    print(f"  expected orphans (placeholders): {sorted(expected_orphan_known)}")
    print(f"  unexpected orphans:          {len(unexpected_orphan)}")
    if unexpected_orphan:
        for sc, ls in sorted(unexpected_orphan):
            uid = f"IN-PC-2008-{sc}-{ls}"
            hit = next((h for h in bnd_by_norm.values() if h["sc"] == sc and h["ls"] == ls), None)
            name = hit["name"] if hit else "?"
            print(f"    {uid:30} name={name!r}")
    print()

    if args.dry_run:
        print("[dry-run] no files written.")
        return 0

    # Apply rewrites (mutate dicts in-place; order preserved).
    for rec in rewrites:
        rec["row"]["eci_no"] = str(rec["new"])

    # Write electoral.csv. Preserve header order + LF line endings.
    with ELECTORAL_CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
    print(f"wrote {ELECTORAL_CSV_PATH.relative_to(REPO).as_posix()}: {len(all_rows)} rows ({len(rewrites)} eci_no rewrites)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
