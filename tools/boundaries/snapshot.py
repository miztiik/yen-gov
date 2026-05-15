"""Boundary snapshot — fetch upstream sources and publish GeoJSON for the frontend.

Why this exists alongside build.py
==================================

build.py produces PMTiles (small, range-requestable) but requires `mapshaper`
and `tippecanoe` on PATH. Those aren't available on Windows out of the box,
and the frontend currently runs entirely off the GeoJSON fallback path
(see frontend/src/lib/maplibre/sources.ts > resolveSource).

This script snapshots the upstreams listed in pipeline.json into
`datasets/boundaries/in/geojson/` with a `<file>.sources.json` sidecar
declaring CLAUDE.md §12 provenance. The frontend prefers these local copies
and only falls back to the upstream URL when the local copy is missing.

Source format dispatch
======================

Each pipeline.json entry carries a `source` block::

    "source": {
      "format": "geojson" | "shp_bundle",
      "urls":   [str, ...]              # 1 entry for geojson; the full sibling
                                        # bundle (.shp/.dbf/.shx/.prj/.cpg) for
                                        # shp_bundle
    }

`format: geojson`
    URL[0] is streamed verbatim into datasets/boundaries/in/geojson/<id>.geojson.
    No conversion. Sidecar carries the single URL.

`format: shp_bundle`
    All URLs are downloaded into .runtime/raw/boundaries/snapshot/<id>/
    (per ADR-0003 — intermediate artifacts never live in datasets/). pyshp
    reads the .shp + .dbf and we hand-emit GeoJSON to
    datasets/boundaries/in/geojson/<id>.geojson. Sidecar carries every
    URL with a per-URL fetched_at.

Adding a new format (zip+geojson, geopackage, geoparquet) is a new branch in
`fetch_and_convert()` and a new value in pipeline.json — neither the sidecar
schema nor the frontend resolver changes.

Why a sidecar instead of a top-level `sources` field on the GeoJSON itself
==========================================================================

The GeoJSON spec (RFC 7946 §7.1) reserves all top-level members and
recommends consumers ignore unknown ones. Tooling tolerates extras, but
stuffing provenance into the artifact muddles the format. A sibling
`*.sources.json` keeps each file type to its native shape and still
satisfies the §12 contract.

Dependencies
============

stdlib + `pyshp` (only when `format: shp_bundle` is encountered). Install
with::

    pip install pyshp

Re-running
==========

    python tools/boundaries/snapshot.py

Re-fetches every entry and updates `fetched_at`. Existing files are
overwritten; deleting an entry from pipeline.json does not delete the
local copy (manual cleanup — we don't want a typo in the config to
accidentally nuke a snapshot).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Size-budget guard. Per-state AC GeoJSONs are 400KB–1MB each. The converted
# datameet states layer at coord_precision=3 (~110 m) is ~11 MB unsimplified-
# topology. We tolerate that as a one-time per-session fetch (gzips to ~3 MB).
# Real geometric simplification lives in tools/boundaries/build.py via mapshaper
# → PMTiles, which compresses this 10× further; this script is the
# native-Python gap-filler that doesn't require Node.
SNAPSHOT_BYTE_BUDGET = 12 * 1024 * 1024  # 12 MB per file

USER_AGENT = "yen-gov-boundaries/1.0"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def utc_now() -> str:
    """RFC 3339 UTC timestamp; matches CLAUDE.md §12 fetched_at convention."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stream_to_disk(url: str, dest: Path) -> None:
    """Download a URL to `dest` atomically via .part-rename."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as r, tmp.open("wb") as fh:  # noqa: S310 — public CC0/MIT data
        shutil.copyfileobj(r, fh)
    tmp.replace(dest)


def derive_output_basename(entry: dict[str, Any]) -> str:
    """Output naming mirrors the BoundaryEntry.id convention used in
    frontend/src/lib/maplibre/sources.ts: 'india-states' or '<state>-ac'."""
    kind = entry["kind"]
    state = entry.get("state")
    if kind == "states":
        return "india-states.geojson"
    if kind == "ac" and state:
        return f"{state}-ac.geojson"
    if kind == "districts" and not state:
        # All-India district layer (one file, ~800 features). Per-state
        # district carve-outs would use kind='districts' with state=<S22>;
        # add that branch when the first per-state district consumer ships.
        return "india-districts.geojson"
    msg = f"unknown entry shape: kind={kind} state={state}"
    raise ValueError(msg)


# -----------------------------------------------------------------------------
# Per-format converters
# -----------------------------------------------------------------------------


def fetch_geojson(urls: list[str], out_path: Path) -> list[dict[str, str]]:
    """Single-URL passthrough. Returns the [{url, fetched_at}] sources list."""
    if len(urls) != 1:
        msg = f"format=geojson expects exactly 1 url, got {len(urls)}"
        raise ValueError(msg)
    fetched_at = utc_now()
    stream_to_disk(urls[0], out_path)
    return [{"url": urls[0], "fetched_at": fetched_at}]


def fetch_shp_bundle(
    urls: list[str],
    out_path: Path,
    raw_dir: Path,
    coord_precision: int | None = None,
) -> list[dict[str, str]]:
    """Download every sibling shapefile component into raw_dir, then convert
    the .shp + .dbf to GeoJSON via pyshp.

    `coord_precision` (decimal places) is a cheap geometry simplifier: rounds
    every coordinate, which collapses the gratuitous 12-digit precision common
    in shapefiles. 4 decimals ≈ 11 m at the equator — well below choropleth
    rendering precision and typically shrinks output 5-10×. None = no rounding.

    Returns the per-URL [{url, fetched_at}] sources list.
    """
    try:
        import shapefile  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover — explicit failure mode
        msg = (
            "format=shp_bundle requires the `pyshp` package "
            "(`pip install pyshp`); see tools/boundaries/README.md"
        )
        raise RuntimeError(msg) from e

    raw_dir.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, str]] = []
    shp_path: Path | None = None
    for url in urls:
        basename = url.rsplit("/", 1)[-1]
        dest = raw_dir / basename
        fetched_at = utc_now()
        stream_to_disk(url, dest)
        sources.append({"url": url, "fetched_at": fetched_at})
        if dest.suffix.lower() == ".shp":
            shp_path = dest
    if shp_path is None:
        msg = f"shp_bundle missing a .shp URL among: {urls}"
        raise ValueError(msg)

    # pyshp reads the .shp and .dbf side-by-side (same basename, same dir).
    # Hand-emit a FeatureCollection: preserves field types and avoids any
    # extra dependency. Polygon/MultiPolygon coverage is sufficient for
    # admin boundaries; if a future source ships Points or Lines we widen
    # the type map below.
    reader = shapefile.Reader(str(shp_path.with_suffix("")))

    def _round_coords(geom: Any) -> Any:
        """Recursively round coordinate tuples and drop consecutive duplicates
        in any ring/line. Pure-python, dependency-free; good enough to take a
        rounded India-states layer from ~20 MB to ~3 MB without distorting
        choropleth-scale rendering. Not topology-aware (won't merge shared
        borders) — for that, run tools/boundaries/build.py with mapshaper."""
        if coord_precision is None:
            return geom
        p = coord_precision

        def _is_pair(node: Any) -> bool:
            return (
                isinstance(node, (list, tuple))
                and len(node) >= 2
                and all(isinstance(c, (int, float)) for c in node)
            )

        def _round_pair(node: Any) -> list[float]:
            return [round(float(c), p) for c in node]

        def _walk(node: Any) -> Any:
            if _is_pair(node):
                return _round_pair(node)
            if isinstance(node, (list, tuple)):
                # Ring of coordinate pairs: dedup consecutive identical points.
                if node and all(_is_pair(c) for c in node):
                    out: list[list[float]] = []
                    for c in node:
                        rc = _round_pair(c)
                        if not out or out[-1] != rc:
                            out.append(rc)
                    return out
                return [_walk(c) for c in node]
            return node

        return {**geom, "coordinates": _walk(geom.get("coordinates"))}

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": dict(zip([f[0] for f in reader.fields[1:]], rec.record, strict=False)),
                "geometry": _round_coords(rec.shape.__geo_interface__),
            }
            for rec in reader.iterShapeRecords()
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(geojson, fh, ensure_ascii=False)
        fh.write("\n")
    reader.close()
    return sources


def _round_coords_geom(geom: Any, coord_precision: int | None) -> Any:
    """Coordinate rounder shared by shp_bundle and geojsonl_7z paths.

    Recursively rounds coordinate tuples to `coord_precision` decimal places
    and drops consecutive duplicates inside any ring/line. Pure-python,
    dependency-free; not topology-aware (won't merge shared borders) — for
    that, run tools/boundaries/build.py with mapshaper. Returns geom
    unchanged when coord_precision is None.
    """
    if coord_precision is None:
        return geom
    p = coord_precision

    def _is_pair(node: Any) -> bool:
        return (
            isinstance(node, (list, tuple))
            and len(node) >= 2
            and all(isinstance(c, (int, float)) for c in node)
        )

    def _round_pair(node: Any) -> list[float]:
        return [round(float(c), p) for c in node]

    def _walk(node: Any) -> Any:
        if _is_pair(node):
            return _round_pair(node)
        if isinstance(node, (list, tuple)):
            if node and all(_is_pair(c) for c in node):
                out: list[list[float]] = []
                for c in node:
                    rc = _round_pair(c)
                    if not out or out[-1] != rc:
                        out.append(rc)
                return out
            return [_walk(c) for c in node]
        return node

    return {**geom, "coordinates": _walk(geom.get("coordinates"))}


def emit_feature_collection(out_path: Path, features: list[dict[str, Any]]) -> None:
    """Write `features` as a GeoJSON FeatureCollection at `out_path`.

    Extracted from the per-format fetchers so that `snapshot_one` can interpose
    transforms (state_filter, split_by — Phase 1b commits 2–3) between fetch
    and emit without duplicating the JSON-write boilerplate per format.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features}
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(fc, fh, ensure_ascii=False)
        fh.write("\n")


def fetch_geojsonl_7z(
    urls: list[str],
    raw_dir: Path,
    coord_precision: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Download a 7z archive containing newline-delimited GeoJSON, extract it,
    and return the parsed features plus the sources list.

    Used by the ramSeraph/indian_admin_boundaries layers — every release ships
    one `*.geojsonl.7z` file holding one feature per line. We unpack to
    raw_dir (per ADR-0003 — intermediate artifacts under .runtime/, never
    datasets/), parse line-by-line, and optionally round coordinates. The
    caller emits the FeatureCollection (so transforms can interpose).

    Returns `(features, sources)`. py7zr is required (pure-python, works on
    Windows without the Linux build toolchain).
    """
    try:
        import py7zr  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover — explicit failure mode
        msg = (
            "format=geojsonl_7z requires the `py7zr` package "
            "(`pip install py7zr`); see tools/boundaries/README.md"
        )
        raise RuntimeError(msg) from e

    if len(urls) != 1:
        msg = f"format=geojsonl_7z expects exactly 1 url, got {len(urls)}"
        raise ValueError(msg)

    raw_dir.mkdir(parents=True, exist_ok=True)
    url = urls[0]
    archive_name = url.rsplit("/", 1)[-1]
    archive_path = raw_dir / archive_name
    fetched_at = utc_now()
    stream_to_disk(url, archive_path)

    extract_dir = raw_dir / "_extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive_path, mode="r") as zf:
        zf.extractall(path=extract_dir)

    # Find the .geojsonl member. ramSeraph archives ship a single payload
    # file at the archive root; if that ever changes (multiple per archive,
    # nested directories) we surface the ambiguity rather than guess.
    candidates = sorted(extract_dir.rglob("*.geojsonl"))
    if not candidates:
        msg = f"no .geojsonl file inside archive {archive_name}"
        raise ValueError(msg)
    if len(candidates) > 1:
        msg = (
            f"ambiguous archive {archive_name}: expected 1 .geojsonl member, "
            f"found {len(candidates)}: {[c.name for c in candidates]}"
        )
        raise ValueError(msg)
    payload = candidates[0]

    features: list[dict[str, Any]] = []
    with payload.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            feat = json.loads(line)
            if coord_precision is not None and "geometry" in feat and feat["geometry"]:
                feat["geometry"] = _round_coords_geom(feat["geometry"], coord_precision)
            features.append(feat)

    return features, [{"url": url, "fetched_at": fetched_at}]


# -----------------------------------------------------------------------------
# Per-entry orchestration
# -----------------------------------------------------------------------------


def snapshot_one(
    entry: dict[str, Any],
    out_root: Path,
    raw_root: Path,
) -> dict[str, Any] | None:
    """Snapshot one pipeline.json entry. Returns the manifest record, or None
    if the entry is intentionally skipped (e.g. exceeds the size budget)."""
    source = entry["source"]
    fmt: str = source["format"]
    urls: list[str] = source["urls"]

    basename = derive_output_basename(entry)
    out_path = out_root / basename
    sidecar_path = out_path.with_suffix(out_path.suffix + ".sources.json")
    label = f"{entry['kind']}:{entry.get('state', '-')}"

    print(f"[{label}] format={fmt} ({len(urls)} url{'s' if len(urls) != 1 else ''})", flush=True)
    for u in urls:
        print(f"  {u}", flush=True)

    if fmt == "geojson":
        sources = fetch_geojson(urls, out_path)
    elif fmt == "shp_bundle":
        bundle_dir = raw_root / "snapshot" / basename.removesuffix(".geojson")
        sources = fetch_shp_bundle(
            urls,
            out_path,
            bundle_dir,
            coord_precision=source.get("coord_precision"),
        )
    elif fmt == "geojsonl_7z":
        bundle_dir = raw_root / "snapshot" / basename.removesuffix(".geojson")
        features, sources = fetch_geojsonl_7z(
            urls,
            bundle_dir,
            coord_precision=source.get("coord_precision"),
        )
        emit_feature_collection(out_path, features)
    else:  # pragma: no cover — caught at config-parse time in practice
        msg = f"unknown source.format: {fmt!r}"
        raise ValueError(msg)

    # Enforce budget *after* materializing — we don't know the converted
    # GeoJSON size until pyshp has emitted it. If we overshoot, delete the
    # output (and skip writing the sidecar) so the frontend transparently
    # falls back to the upstream URL.
    size = out_path.stat().st_size
    if size > SNAPSHOT_BYTE_BUDGET:
        out_path.unlink()
        print(
            f"  SKIP — converted output {size / 1024 / 1024:.1f} MB exceeds "
            f"{SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget; "
            "frontend will use the live-fetch fallback for this layer.",
            flush=True,
        )
        return None

    sidecar = {
        "$schema": "https://yen-gov.github.io/schemas/boundary.sources.schema.json",
        "$schema_version": "1.0",
        "$comment": (
            "CLAUDE.md §12 provenance sidecar for the GeoJSON of the same name. "
            "GeoJSON has no native top-level metadata slot; this file carries the "
            "required `sources` array on its behalf."
        ),
        "for": basename,
        "sources": sources,
    }
    with sidecar_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(sidecar, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    record: dict[str, Any] = {
        "id": basename.removesuffix(".geojson"),
        "path": f"boundaries/in/geojson/{basename}",
        "kind": entry["kind"],
        "size_bytes": size,
        "fetched_at": sources[-1]["fetched_at"],
    }
    if "state" in entry:
        record["state"] = entry["state"]
    return record


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot upstream boundary GeoJSONs.")
    parser.add_argument(
        "--config",
        default="tools/boundaries/pipeline.json",
        help="Pipeline config (relative to repo root).",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repo root (default: cwd).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cfg_path = root / args.config
    if not cfg_path.is_file():
        print(f"config not found: {cfg_path}", file=sys.stderr)
        return 2

    with cfg_path.open(encoding="utf-8") as fh:
        cfg = json.load(fh)

    out_root = root / "datasets" / "boundaries" / "in" / "geojson"
    raw_root = root / cfg.get("raw_dir", ".runtime/raw/boundaries")
    out_root.mkdir(parents=True, exist_ok=True)

    records = [
        r for r in (snapshot_one(e, out_root, raw_root) for e in cfg["inputs"]) if r is not None
    ]

    print(f"\nsnapshotted {len(records)} files into {out_root.relative_to(root)}/")
    for r in records:
        size_kb = r["size_bytes"] / 1024
        print(f"  {r['path']:<48s} {size_kb:>8.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
