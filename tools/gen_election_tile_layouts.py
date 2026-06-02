#!/usr/bin/env python3
"""Generate election tile-cartogram (equal-area hex) layouts from boundary centroids.

Reconstructs the one-time hexbin pass that seeds
`datasets/grapher/election_tile_layouts.json` (schema
`grapher-election-tile-layout.schema.json` v1.0, owned by the frontend per
ADR-0045). One tile per real constituency for a given (layout_kind, scope,
delim_year); axial pointy-top odd-r coords (q, r); zero cell overlaps; north-up.

Per CLAUDE.md §4 this is a standalone tool: it reads the boundary geojson and
the layout JSON directly from the repo root with stdlib only and MUST NOT import
`backend/yen_gov`. It is idempotent per scope: re-running a scope replaces only
that scope's tiles in the layout file, leaving every other scope untouched.

Usage:
  # one AC state by ECI code
  python tools/gen_election_tile_layouts.py --layout-kind ac --scope S13
  # every standard-schema AC state/UT
  python tools/gen_election_tile_layouts.py --layout-kind ac --all-states
  # the national PC layout
  python tools/gen_election_tile_layouts.py --layout-kind pc --scope national

Exit codes: 0 ok, 1 soft failure (e.g. a scope skipped), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAYOUT_PATH = REPO / "datasets" / "grapher" / "election_tile_layouts.json"
SCOPES_PATH = REPO / "datasets" / "grapher" / "election_tile_scopes.json"
AC_DIR = REPO / "datasets" / "boundaries" / "in" / "ac"
PC_PATH = REPO / "datasets" / "boundaries" / "in" / "pc" / "delim=2024" / "all.geojson"

DELIM_YEAR = 2008
ROW_PITCH = math.sqrt(3) / 2  # pointy-top: vertical row pitch / horizontal pitch
GRID_SLACK = 1.45  # spare cells so the greedy spiral rarely travels far

# Boundary directory slug -> ECI state/UT code. Mirrors _LOCAL_NAME_TO_ECI in
# backend/yen_gov/cli.py (hyphenated to match the boundary partition dirs).
SLUG_TO_CODE: dict[str, str] = {
    "andhra-pradesh": "S01",
    "arunachal-pradesh": "S02",
    "assam": "S03",
    "bihar": "S04",
    "goa": "S05",
    "gujarat": "S06",
    "haryana": "S07",
    "himachal-pradesh": "S08",
    "karnataka": "S10",
    "kerala": "S11",
    "madhya-pradesh": "S12",
    "maharashtra": "S13",
    "manipur": "S14",
    "meghalaya": "S15",
    "mizoram": "S16",
    "nagaland": "S17",
    "odisha": "S18",
    "punjab": "S19",
    "rajasthan": "S20",
    "sikkim": "S21",
    "tamil-nadu": "S22",
    "tripura": "S23",
    "uttar-pradesh": "S24",
    "west-bengal": "S25",
    "chhattisgarh": "S26",
    "jharkhand": "S27",
    "uttarakhand": "S28",
    "telangana": "S29",
    "delhi": "U05",
    "puducherry": "U07",
    "jammu-and-kashmir": "U08",
}
CODE_TO_SLUG = {code: slug for slug, code in SLUG_TO_CODE.items()}

# State partitions whose boundary geojson lacks the standard `ac_no` property
# (a different upstream schema). Skipped by the generator until an adapter +
# verified election entity_id join lands. Tracked in the gap-closure plan.
NON_STANDARD_AC_SLUGS = {"jammu-and-kashmir"}


# ---------------------------------------------------------------------------
# Geometry helpers (stdlib only; no shapely)
# ---------------------------------------------------------------------------
def _ring_centroid(ring: list[list[float]]) -> tuple[float, float, float]:
    """Signed-area centroid of one polygon ring. Returns (cx, cy, abs_area)."""
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    n = len(ring)
    for i in range(n - 1):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[i + 1][0], ring[i + 1][1]
        cross = x0 * y1 - x1 * y0
        area2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area2) < 1e-15:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return (sum(xs) / len(xs), sum(ys) / len(ys), 0.0)
    area = area2 / 2.0
    return (cx / (6.0 * area), cy / (6.0 * area), abs(area))


def feature_centroid(geom: dict) -> tuple[float, float, float]:
    """Area-weighted centroid of a Polygon / MultiPolygon. Returns (lon, lat, area)."""
    gtype = geom["type"]
    coords = geom["coordinates"]
    if gtype == "Polygon":
        parts = [coords]
    elif gtype == "MultiPolygon":
        parts = coords
    else:  # pragma: no cover - boundary corpus is (Multi)Polygon only
        raise ValueError(f"unsupported geometry type {gtype!r}")
    sx = sy = total = 0.0
    for poly in parts:
        cx, cy, area = _ring_centroid(poly[0])  # exterior ring
        if area == 0.0:
            area = 1e-12
        sx += cx * area
        sy += cy * area
        total += area
    return (sx / total, sy / total, total)


# ---------------------------------------------------------------------------
# Hexbin placement
# ---------------------------------------------------------------------------
def _cell_pixel(q: int, r: int) -> tuple[float, float]:
    """Pointy-top odd-r offset cell -> pixel centre (horizontal pitch = 1)."""
    return (q + 0.5 * (r & 1), r * ROW_PITCH)


def assign_hex_cells(units: list[dict]) -> None:
    """Mutate each unit dict in-place adding integer 'q','r' axial coords.

    units: [{eci_no, lon, lat, ...}]. Greedy nearest-free-cell hexbin with a
    grid sized to the constituencies' geographic aspect ratio. North-up.
    Deterministic: units are processed in ascending eci_no order.
    """
    n = len(units)
    if n == 0:
        return
    lat_mean = sum(u["lat"] for u in units) / n
    lon_scale = math.cos(math.radians(lat_mean)) or 1e-6  # equirectangular x scale
    xs = [u["lon"] * lon_scale for u in units]
    ys = [u["lat"] for u in units]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    width = (maxx - minx) or 1e-9
    height = (maxy - miny) or 1e-9

    # Grid dims: cols*rows ~= n*slack, with cols/(rows*ROW_PITCH) ~= width/height.
    rows = max(1, round(math.sqrt(n * GRID_SLACK * height / (width * ROW_PITCH))))
    cols = max(1, math.ceil(n * GRID_SLACK / rows))

    occupied: set[tuple[int, int]] = set()
    order = sorted(range(n), key=lambda i: units[i]["eci_no"])
    for i in order:
        nx = (xs[i] - minx) / width
        ny = (ys[i] - miny) / height
        ideal_x = nx * (cols - 1)
        ideal_y = (1.0 - ny) * (rows - 1) * ROW_PITCH  # north (high lat) -> top
        tr = round((1.0 - ny) * (rows - 1))
        tq = round(ideal_x - 0.5 * (tr & 1))
        q, r = _place_nearest_free(tq, tr, ideal_x, ideal_y, occupied)
        occupied.add((q, r))
        units[i]["q"] = q
        units[i]["r"] = r

    _normalise_coords(units)


def _place_nearest_free(
    tq: int,
    tr: int,
    ideal_x: float,
    ideal_y: float,
    occupied: set[tuple[int, int]],
) -> tuple[int, int]:
    """Spiral out from (tq,tr) to the free cell closest (in pixel space) to ideal."""
    radius = 0
    while True:
        found: list[tuple[float, int, int]] = []
        for dq in range(-radius, radius + 1):
            for dr in range(-radius, radius + 1):
                if max(abs(dq), abs(dr)) != radius:
                    continue
                q, r = tq + dq, tr + dr
                if (q, r) in occupied:
                    continue
                px, py = _cell_pixel(q, r)
                dist = (px - ideal_x) ** 2 + (py - ideal_y) ** 2
                found.append((dist, q, r))
        if found:
            # Also scan one ring further: a cell one ring out can be pixel-closer
            # than the nearest cell on this ring because of the odd-r offset.
            radius_extra = radius + 1
            for dq in range(-radius_extra, radius_extra + 1):
                for dr in range(-radius_extra, radius_extra + 1):
                    if max(abs(dq), abs(dr)) != radius_extra:
                        continue
                    q, r = tq + dq, tr + dr
                    if (q, r) in occupied:
                        continue
                    px, py = _cell_pixel(q, r)
                    dist = (px - ideal_x) ** 2 + (py - ideal_y) ** 2
                    found.append((dist, q, r))
            found.sort()
            return (found[0][1], found[0][2])
        radius += 1


def _normalise_coords(units: list[dict]) -> None:
    """Shift q,r so the grid starts near the origin, preserving odd-r parity."""
    min_q = min(u["q"] for u in units)
    min_r = min(u["r"] for u in units)
    r_shift = min_r if min_r % 2 == 0 else min_r - 1  # even shift keeps parity
    for u in units:
        u["q"] -= min_q
        u["r"] -= r_shift


# ---------------------------------------------------------------------------
# Scope builders
# ---------------------------------------------------------------------------
def build_ac_scope(slug: str) -> list[dict]:
    """Build the AC tile list for one state partition slug. Empty list -> skip."""
    code = SLUG_TO_CODE[slug]
    path = AC_DIR / f"state={slug}" / "all.geojson"
    gj = json.loads(path.read_text(encoding="utf-8"))
    features = gj["features"]

    # Aggregate features by ac_no: multi-part constituencies and border slivers
    # share an ac_no; the area-weighted centroid favours the dominant geometry.
    by_ac: dict[int, dict] = {}
    for feat in features:
        props = feat["properties"]
        try:
            ac_no = int(props.get("ac_no") or 0)
        except (TypeError, ValueError):
            ac_no = 0
        if ac_no <= 0:
            continue
        lon, lat, area = feature_centroid(feat["geometry"])
        bucket = by_ac.setdefault(
            ac_no, {"sx": 0.0, "sy": 0.0, "area": 0.0, "name": None, "best_area": -1.0}
        )
        bucket["sx"] += lon * area
        bucket["sy"] += lat * area
        bucket["area"] += area
        if area > bucket["best_area"]:
            bucket["best_area"] = area
            bucket["name"] = (
                props.get("ac_name") or props.get("seat_name_en") or f"AC {ac_no}"
            )

    source_id = f"boundaries/in/ac/state={slug}/all.geojson"
    units: list[dict] = []
    for ac_no, b in by_ac.items():
        units.append(
            {
                "eci_no": ac_no,
                "lon": b["sx"] / b["area"],
                "lat": b["sy"] / b["area"],
                "unit_id": f"IN-{code}-AC-{DELIM_YEAR}-{ac_no}",
                "label": str(b["name"]),
            }
        )
    assign_hex_cells(units)
    return [_tile("ac", code, source_id, u) for u in units]


def build_pc_scope() -> list[dict]:
    """Build the national PC tile list from the delim-2024 boundary corpus."""
    gj = json.loads(PC_PATH.read_text(encoding="utf-8"))
    units: list[dict] = []
    for feat in gj["features"]:
        props = feat["properties"]
        sc = str(props["state_ut_code"])
        ls = int(props["ls_seat_code"])
        lon, lat, _ = feature_centroid(feat["geometry"])
        units.append(
            {
                "eci_no": ls,
                "lon": lon,
                "lat": lat,
                "unit_id": f"IN-PC-{DELIM_YEAR}-{sc}-{ls}",
                "label": str(props.get("ls_seat_name") or f"PC {ls}"),
            }
        )
    assign_hex_cells(units)
    source_id = "boundaries/in/pc/delim=2024/all.geojson"
    return [_tile("pc", "national", source_id, u) for u in units]


def _tile(kind: str, scope: str, source_id: str, u: dict) -> dict:
    return {
        "layout_kind": kind,
        "scope": scope,
        "delim_year": DELIM_YEAR,
        "unit_id": u["unit_id"],
        "eci_no": u["eci_no"],
        "q": u["q"],
        "r": u["r"],
        "label": u["label"],
        "source_id": source_id,
        "derivation_method": "centroid-hexbin",
    }


# ---------------------------------------------------------------------------
# Layout file merge
# ---------------------------------------------------------------------------
def load_layout() -> dict:
    if LAYOUT_PATH.exists():
        return json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    return {
        "$schema": "https://yen-gov.github.io/schemas/grapher-election-tile-layout.schema.json",
        "$schema_version": "1.0",
        "tiles": [],
    }


def merge_scope(doc: dict, kind: str, scope: str, new_tiles: list[dict]) -> None:
    """Replace every tile for (kind, scope, DELIM_YEAR) with new_tiles."""
    kept = [
        t
        for t in doc["tiles"]
        if not (
            t["layout_kind"] == kind
            and t["scope"] == scope
            and t["delim_year"] == DELIM_YEAR
        )
    ]
    kept.extend(new_tiles)
    kept.sort(key=lambda t: (t["layout_kind"], t["scope"], t["delim_year"], t["eci_no"]))
    doc["tiles"] = kept


def write_layout(doc: dict) -> None:
    LAYOUT_PATH.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_scopes_manifest(doc: dict) -> None:
    """Emit the tiny covered-scopes manifest derived from the layout doc.

    The frontend reads this (not the large layout file) to decide whether to
    offer the equal-seats toggle for a state, so the toggle never appears for a
    scope that has no tiles. Always rewritten in lockstep with the layout.
    """
    counts: dict[tuple[str, str, int], int] = {}
    for t in doc["tiles"]:
        key = (t["layout_kind"], t["scope"], t["delim_year"])
        counts[key] = counts.get(key, 0) + 1
    scopes = [
        {
            "layout_kind": kind,
            "scope": scope,
            "delim_year": delim,
            "tile_count": n,
        }
        for (kind, scope, delim), n in sorted(counts.items())
    ]
    manifest = {
        "$schema": "https://yen-gov.github.io/schemas/grapher-election-tile-scopes.schema.json",
        "$schema_version": "1.0",
        "scopes": scopes,
    }
    SCOPES_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def assert_no_overlap(tiles: list[dict], label: str) -> None:
    cells = [(t["q"], t["r"]) for t in tiles]
    if len(set(cells)) != len(cells):
        raise SystemExit(f"[FAIL] {label}: overlapping hex cells")
    ids = [t["unit_id"] for t in tiles]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"[FAIL] {label}: duplicate unit_id")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout-kind", choices=["ac", "pc"], required=True)
    parser.add_argument(
        "--scope",
        help="ECI state/UT code (e.g. S13) for an AC scope, or 'national' for PC.",
    )
    parser.add_argument(
        "--all-states",
        action="store_true",
        help="Build every standard-schema AC state/UT (layout-kind ac only).",
    )
    args = parser.parse_args(argv)

    doc = load_layout()
    soft_fail = False

    if args.layout_kind == "pc":
        tiles = build_pc_scope()
        assert_no_overlap(tiles, "pc/national")
        merge_scope(doc, "pc", "national", tiles)
        print(f"  [ok] pc/national: {len(tiles)} tiles")

    elif args.all_states:
        for slug in sorted(SLUG_TO_CODE):
            if slug in NON_STANDARD_AC_SLUGS:
                print(f"  [skip] {slug}: non-standard boundary schema (no ac_no)")
                soft_fail = True
                continue
            code = SLUG_TO_CODE[slug]
            tiles = build_ac_scope(slug)
            if not tiles:
                print(f"  [skip] {slug}: no constituencies found")
                soft_fail = True
                continue
            assert_no_overlap(tiles, f"ac/{code}")
            merge_scope(doc, "ac", code, tiles)
            print(f"  [ok] ac/{code} ({slug}): {len(tiles)} tiles")

    else:
        if not args.scope:
            parser.error("AC layout needs --scope <CODE> or --all-states")
        code = args.scope
        slug = CODE_TO_SLUG.get(code)
        if slug is None:
            parser.error(f"unknown AC scope {code!r}")
        if slug in NON_STANDARD_AC_SLUGS:
            print(f"  [skip] {slug}: non-standard boundary schema (no ac_no)")
            return 1
        tiles = build_ac_scope(slug)
        assert_no_overlap(tiles, f"ac/{code}")
        merge_scope(doc, "ac", code, tiles)
        print(f"  [ok] ac/{code} ({slug}): {len(tiles)} tiles")

    write_layout(doc)
    write_scopes_manifest(doc)
    print(f"  wrote {LAYOUT_PATH.relative_to(REPO)} ({len(doc['tiles'])} tiles total)")
    print(f"  wrote {SCOPES_PATH.relative_to(REPO)}")
    return 1 if soft_fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
