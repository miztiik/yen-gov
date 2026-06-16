"""Dual-key the national 2024 PC geometry for the single-vintage join.

Row 3 of TODO/20260616-map-geometry-rip-and-palette-plan.md (section 0.3,
"one geometry, two indexed keys"). After delim=2008/pc is retired, ALL Lok Sabha
events (2009-2024) join against the single delim=2024/pc/all.geojson. LS 2024
keeps its numeric `unique_id` (`<state_ut_code>_<ls_seat_code>`, e.g. "S07_5");
historical events (2009-2019) join by NAME-SLUG because the canonical electoral
`eci_no` is unreliable for pre-2024 PCs. The 2008 Delimitation Order governs PC
boundaries for LS 2009 THROUGH 2024 - they are the SAME polygons - so a 2019
result on the 2024 polygon of the same-named seat is CORRECT, not approximate.

This stamps two properties onto every 2024 PC feature (idempotent, in place),
mirroring what the delim=2008/pc file already carried (`pc_name_slug` +
`unique_id` = "<state>_<slug>"):

  - `pc_name_slug`: kebab-case slug of `ls_seat_name` (bare).
  - `pc_slug_uid`: `<state_ut_code>_<pc_name_slug>` - the name-slug join key the
    frontend's INDIA_PC_BY_NAME entry joins on for <2024 events (the numeric
    `unique_id` is preserved for the 2024 numeric join).

Measured 2026-06-16: 510/543 (93.9%) of delim=2008 PC name-slugs match a 2024 PC
name-slug exactly; the ~6% tail is spelling variants (recovered by the Row 5b
alias table) + genuine Assam/J&K re-delimitation seats (table-fallback). The
name-slug join is safe by construction: an unmatched seat renders grey, never a
wrong-seat colour.

Usage:
    python -m tools.boundaries.dual_key_pc_2024
    python -m tools.boundaries.dual_key_pc_2024 --pc <path>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PC = REPO_ROOT / "datasets/boundaries/electoral/delim=2024/pc/all.geojson"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def dual_key(pc_path: Path = DEFAULT_PC) -> tuple[int, int]:
    """Stamp pc_name_slug + pc_slug_uid in place. Returns (features, distinct_uids)."""
    fc = json.loads(pc_path.read_text(encoding="utf-8"))
    uids: set[str] = set()
    for feat in fc.get("features", []):
        props = feat.setdefault("properties", {})
        slug = slugify(str(props.get("ls_seat_name") or ""))
        state = str(props.get("state_ut_code") or "")
        props["pc_name_slug"] = slug
        props["pc_slug_uid"] = f"{state}_{slug}" if state and slug else ""
        if props["pc_slug_uid"]:
            uids.add(props["pc_slug_uid"])
    pc_path.write_text(
        json.dumps(fc, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    n = len(fc.get("features", []))
    _verify(pc_path)
    return n, len(uids)


def _verify(pc_path: Path) -> None:
    fc = json.loads(pc_path.read_text(encoding="utf-8"))
    for f in fc["features"]:
        p = f["properties"]
        if "pc_name_slug" not in p or "pc_slug_uid" not in p:
            raise RuntimeError("a PC feature is missing pc_name_slug / pc_slug_uid")
        # unique_id (numeric) must be preserved for the 2024 numeric join.
        if "unique_id" not in p:
            raise RuntimeError("a PC feature lost its numeric unique_id")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dual-key the 2024 PC geometry (pc_name_slug + pc_slug_uid).")
    parser.add_argument("--pc", type=Path, default=DEFAULT_PC)
    args = parser.parse_args(argv)
    n, uids = dual_key(args.pc)
    print(f"[dual-key-pc] stamped {n} PC features ({uids} distinct pc_slug_uid) in {args.pc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
