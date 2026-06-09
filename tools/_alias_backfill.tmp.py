"""G16 alias backfill — idempotent script (KEEP THIS as receipt).

Reads ``datasets/data/entities/electoral.csv``, walks the 36 G16-discovered
BOUND (state, lgd_canonical_name) -> eci_published_alias mappings, and APPENDS
the ECI verbatim alias to the ``aliases`` column for each matching row. All
non-target rows are preserved byte-for-byte. Re-running the script is
idempotent (an alias already present is not re-added).

The 14 SPINE-GAP rows (10 expected: Delhi x7 + Chandigarh + A&N + Dadra-DNH;
4 unexpected: Mumbai South, Lucknow, Kolkata Dakshin, Kolkata Uttar) are NOT
touched — there is no LGD-canonical PC row to attach the alias to. They are
recorded in the PR body and the receipt at ``tools/_alias_receipt.tmp.md``.

Run from the worktree root:
    python tools/_alias_backfill.tmp.py

The matching discovery file is ``tools/_alias_discovery.tmp.py`` (deleted
post-merge); this script is KEPT as a receipt so the orchestrator can re-run
it after a future spine-fix lands.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

# (state_slug, lgd_canonical_name) -> eci_published_alias (verbatim, case + punctuation preserved)
# Derived from tools/_alias_discovery.tmp.py BOUND rows (run 2026-06-09).
BOUND_ALIASES: dict[tuple[str, str], str] = {
    ("andhra-pradesh", "Anantapur"): "Ananthapur",
    ("andhra-pradesh", "Kurnool"): "Kurnoolu",
    ("andhra-pradesh", "Narasaraopet"): "Narsaraopet",
    ("andhra-pradesh", "Tirupati"): "Thirupathi",
    ("assam", "Mangaldoi"): "Darrang-Udalguri",
    ("assam", "Autonomous District"): "Diphu",
    ("assam", "Gauhati"): "Guwahati",
    ("bihar", "Pataliputra"): "Patliputra",
    ("chhattisgarh", "Janjgir Champa"): "JANJGIR-CHAMPA",
    ("jammu-and-kashmir", "Anantnag"): "ANANTNAG-RAJOURI",
    ("jharkhand", "Palamau"): "Palamu",
    ("karnataka", "Bengaluru North"): "Bangalore North",
    ("karnataka", "Bengaluru Rural"): "Bangalore Rural",
    ("karnataka", "Bengaluru South"): "Bangalore South",
    ("karnataka", "Bengaluru Central"): "Bangalore central",
    ("karnataka", "Belagavi"): "Belgaum",
    ("karnataka", "Ballari"): "Bellary",
    ("karnataka", "Vijayapura"): "Bijapur",
    ("karnataka", "Kalaburagi"): "Gulbarga",
    ("karnataka", "Mysuru"): "Mysore",
    ("karnataka", "Shivamogga"): "Shimoga",
    ("karnataka", "Tumakuru"): "Tumkur",
    ("karnataka", "Udupi Chikkamagaluru"): "Udupi Chikmagalur",
    ("maharashtra", "Bhandara - Gondiya"): "Bhandara Gondiya",
    ("maharashtra", "Gadchiroli-Chimur"): "Gadchiroli - Chimur",
    ("maharashtra", "Hatkanangle"): "Hatkanangale",
    ("maharashtra", "Mumbai North-Central"): "Mumbai North Central",
    ("maharashtra", "Mumbai North-East"): "Mumbai North East",
    ("maharashtra", "Mumbai North-West"): "Mumbai North West",
    ("maharashtra", "Mumbai South-Central"): "Mumbai South Central",
    ("maharashtra", "Ratnagiri - Sindhudurg"): "Ratnagiri- Sindhudurg",
    ("maharashtra", "Yavatmal-Washim"): "Yavatmal- Washim",
    ("telangana", "Mahabubnagar"): "Mahbubnagar",
    ("uttar-pradesh", "Bahraich"): "Baharaich",
    ("uttarakhand", "Hardwar"): "Haridwar",
    ("west-bengal", "Bardhaman - Durgapur"): "Bardhaman-Durgapur",
}
assert len(BOUND_ALIASES) == 36, f"expected 36 BOUND aliases, got {len(BOUND_ALIASES)}"


def append_alias(existing: str, new_alias: str) -> str:
    """Append ``new_alias`` to a pipe-delimited cell; preserve original if already present."""
    existing = (existing or "").strip()
    if not existing:
        return new_alias
    parts = [p.strip() for p in existing.split("|") if p.strip()]
    if new_alias in parts:
        return existing  # idempotent
    parts.append(new_alias)
    return "|".join(parts)


def main() -> None:
    here = Path(__file__).resolve().parent.parent
    electoral_csv = here / "datasets" / "data" / "entities" / "electoral.csv"
    raw = electoral_csv.read_text(encoding="utf-8")

    rdr = csv.DictReader(io.StringIO(raw))
    fieldnames = list(rdr.fieldnames or [])
    rows = list(rdr)
    modified = 0
    for row in rows:
        if row.get("entity_kind") != "pc":
            continue
        if (row.get("delim_year") or "").strip() != "2008":
            continue
        key = (row.get("state", ""), row.get("name", ""))
        eci_alias = BOUND_ALIASES.get(key)
        if eci_alias is None:
            continue
        before = row.get("aliases", "") or ""
        after = append_alias(before, eci_alias)
        if after != before:
            row["aliases"] = after
            modified += 1
        elif before == after:
            # Idempotent re-run: alias already present.
            pass

    # Write back with LF terminator, no quoting unless required (matches original style).
    # Use ``write_bytes`` to avoid the Windows ``write_text`` LF -> CRLF translation.
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    writer.writerows(rows)
    electoral_csv.write_bytes(out.getvalue().encode("utf-8"))

    print(f"electoral.csv: {modified} alias cells updated this run")
    # Verify count of non-empty aliases on PC-2008 rows after the write.
    rdr2 = csv.DictReader(io.StringIO(electoral_csv.read_text(encoding="utf-8")))
    aliased = [
        r for r in rdr2
        if r.get("entity_kind") == "pc"
        and (r.get("delim_year") or "").strip() == "2008"
        and (r.get("aliases") or "").strip()
    ]
    print(f"electoral.csv: {len(aliased)} total PC-2008 rows with non-empty aliases")
    expected = len(BOUND_ALIASES)
    if len(aliased) != expected:
        print(f"WARN: expected {expected} aliased PC rows, got {len(aliased)}")
    else:
        print(f"OK: all {expected} BOUND rows have their alias set")


if __name__ == "__main__":
    main()
