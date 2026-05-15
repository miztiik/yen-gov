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
    frontend/src/lib/maplibre/sources.ts: 'india-states' or '<state>-ac'.

    For `kind: "villages"` with a `source.split_by` block, returns a
    template basename containing `{<property>}` (e.g.
    `S22-villages-{dist_lgd}.geojson`); the orchestrator substitutes per
    group when emitting shards.
    """
    kind = entry["kind"]
    state = entry.get("state")
    if kind == "states":
        return "india-states.geojson"
    if kind == "country" and entry.get("country") == "IN" and not state:
        # National silhouette (Survey of India outline). Single canonical
        # name today — extend with another branch when a non-IN country
        # silhouette ships.
        return "india-soi.geojson"
    if kind == "ac" and state:
        return f"{state}-ac.geojson"
    if kind == "districts" and not state:
        # All-India district layer (one file, ~800 features). Per-state
        # district carve-outs would use kind='districts' with state=<S22>;
        # add that branch when the first per-state district consumer ships.
        return "india-districts.geojson"
    if kind == "subdistricts" and state:
        return f"{state}-subdistricts.geojson"
    if kind == "villages" and state:
        split = entry.get("source", {}).get("split_by")
        if split:
            return f"{state}-villages-{{{split['property']}}}.geojson"
        return f"{state}-villages.geojson"
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


def apply_state_filter(
    features: list[dict[str, Any]],
    filter_spec: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Slice a national feature list to a sub-national subset.

    `filter_spec` shape (one of):
        {"property": "state_lgd", "equals": 33}        # single value
        {"property": "state_lgd", "one_of": [33, 7]}    # multi value

    Returns `(kept, dropped)`. Empty `kept` is a config error and raises —
    a state filter that matches nothing is almost certainly the wrong
    property name or value, never a legitimate "this state has no
    features" signal (Fowler v5 nit: fail loud, don't emit empty FC).
    """
    prop = filter_spec["property"]
    if "equals" in filter_spec:
        target = filter_spec["equals"]
        match = lambda f: f.get("properties", {}).get(prop) == target  # noqa: E731
    elif "one_of" in filter_spec:
        targets = set(filter_spec["one_of"])
        match = lambda f: f.get("properties", {}).get(prop) in targets  # noqa: E731
    else:
        msg = f"state_filter {filter_spec!r} requires `equals` or `one_of`"
        raise ValueError(msg)

    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for f in features:
        (kept if match(f) else dropped).append(f)
    if not kept:
        msg = (
            f"state_filter {filter_spec!r} matched zero features out of "
            f"{len(features)}; check `property` name + value against the upstream"
        )
        raise ValueError(msg)
    return kept, dropped


def apply_split_by(
    features: list[dict[str, Any]],
    split_spec: dict[str, Any],
) -> tuple[dict[Any, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Group features by `split_spec["property"]`. Returns
    `(groups: {value: [features]}, dropped: [features])` where dropped
    holds features that lack the property entirely (None or missing).

    The orchestrator emits one shard per group at the templated
    `out_path` and one manifest listing the groups present.
    """
    prop = split_spec["property"]
    groups: dict[Any, list[dict[str, Any]]] = {}
    dropped: list[dict[str, Any]] = []
    for f in features:
        v = f.get("properties", {}).get(prop)
        if v is None:
            dropped.append(f)
            continue
        groups.setdefault(v, []).append(f)
    return groups, dropped


def emit_index_manifest(
    index_path: Path,
    state_lgd: int,
    group_keys: list[Any],
    schema_basename: str,
    sources: list[dict[str, str]],
) -> None:
    """Write the per-state index manifest atomically (temp-then-rename so a
    crash mid-write cannot leave a partial manifest beside complete shards
    — Fowler v5 nit). Validates against `boundary.villages_index.schema.json`
    by construction: state_lgd + district codes serialised as digit strings,
    sorted ascending. `sources` is copied verbatim from the upstream the
    shards were derived from (CLAUDE.md §12 — every datasets/ artifact
    carries its own provenance, even derived sidecars).
    """
    payload = {
        "$schema": f"https://yen-gov.github.io/schemas/{schema_basename}",
        "$schema_version": "2.0",
        "$comment": (
            "Index of per-district shards present on disk. The frontend loader "
            "consults this to avoid 404-probing for districts whose village "
            "layer was not emitted (TODO/TN-GRANULAR-GEO-PLAN.md Phase 2)."
        ),
        "sources": sources,
        "state_lgd": str(state_lgd),
        "district_lgd_codes": sorted({str(k) for k in group_keys}),
        "generated_at": utc_now(),
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(index_path.suffix + ".part")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp.replace(index_path)


def _write_sources_sidecar(sidecar_path: Path, basename: str, sources: list[dict[str, str]]) -> None:
    """Write the boundary.sources.schema.json v1.0 sidecar for one shard."""
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


def _make_drop_record(
    feat: dict[str, Any],
    reason: str,
    name_property: str | None = None,
    dropped_at: str | None = None,
) -> dict[str, str]:
    """Build a boundary.unkeyed.schema.json `dropped[]` entry for `feat`.

    `name_property` is the entry's `name_property` (e.g. "vlgname") when known
    — that yields the most useful display name. Falls back to a small set of
    common name fields and finally "(unnamed)" so the record always satisfies
    the schema's `minLength: 1` constraint on `source_feature_name`.
    """
    name = "(unnamed)"
    props = feat.get("properties") or {}
    if name_property:
        v = props.get(name_property)
        if v not in (None, ""):
            name = str(v)
    if name == "(unnamed)":
        for k in ("name", "vlgname", "sdtname", "dtname", "stname"):
            v = props.get(k)
            if v not in (None, ""):
                name = str(v)
                break
    return {
        "source_feature_name": name,
        "reason": reason,
        "dropped_at": dropped_at or utc_now(),
    }


def _write_unkeyed_sidecar(
    sidecar_path: Path,
    basename: str,
    original: int,
    retained: int,
    dropped_records: list[dict[str, str]],
    sources: list[dict[str, str]],
) -> None:
    """Hans v2 denominator sidecar — always emit, even when `dropped_records`
    is empty, so the citizen UI can read 'X of Y features carry an LGD code'
    rather than silently shrink the dataset. `original == retained + len(dropped)`
    is asserted (writer-side invariant; the schema enforces the same shape on
    readers via boundary.unkeyed.schema.json totals). `sources` is copied
    verbatim from the parent GeoJSON's sidecar so this artifact is independently
    attributable per CLAUDE.md §12."""
    if original != retained + len(dropped_records):
        msg = (
            f"unkeyed sidecar denominator mismatch for {basename}: "
            f"original={original} retained={retained} dropped={len(dropped_records)}"
        )
        raise ValueError(msg)
    payload = {
        "$schema": "https://yen-gov.github.io/schemas/boundary.unkeyed.schema.json",
        "$schema_version": "2.0",
        "$comment": (
            "Hans v2 denominator sidecar. Empty `dropped` with totals.dropped=0 "
            "is the canonical 'perfect snapshot' signal — written explicitly so "
            "downstream readers never have to distinguish 'no drops' from 'no sidecar'."
        ),
        "for": basename,
        "sources": sources,
        "totals": {
            "original": original,
            "retained": retained,
            "dropped": len(dropped_records),
        },
        "dropped": dropped_records,
    }
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    with sidecar_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _write_simplification_metadata_sidecar(
    metadata_path: Path,
    basename: str,
    entry_metadata: dict[str, Any],
    sources: list[dict[str, str]],
    coord_precision: int,
    original_feature_count: int,
    retained_feature_count: int,
) -> None:
    """Write `feature_collection.metadata.schema.json` v1.2 sidecar with the
    `simplification` block populated.

    Requires the entry to carry a `metadata` block with at least `license` +
    `coverage` — those are operator-knowledge fields (legal classification,
    spatial/temporal scope) that snapshot.py cannot honestly synthesise
    from the URL alone. Other fields (title, description, category,
    coordinate_system) are passed through verbatim if present.
    """
    payload: dict[str, Any] = {
        "$schema": "https://yen-gov.github.io/schemas/feature_collection.metadata.schema.json",
        "$schema_version": "1.2",
        "$comment": (
            "Simplification metadata for a coord_precision-rounded GeoJSON. "
            "Records the rounding tolerance + feature counts so downstream area/"
            "length math is not silently lying. Per TODO/TN-GRANULAR-GEO-PLAN.md "
            "Phase 1b (Hans v2 nit)."
        ),
        "for": basename,
        "sources": sources,
        "license": entry_metadata["license"],
        "coverage": entry_metadata["coverage"],
        "simplification": {
            "tolerance_deg": 10 ** -coord_precision,
            "algorithm": "coord-precision-round",
            "original_feature_count": original_feature_count,
            "retained_feature_count": retained_feature_count,
        },
    }
    for opt in ("title", "description", "category", "coordinate_system"):
        if opt in entry_metadata:
            payload[opt] = entry_metadata[opt]
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _emit_split_shards(
    entry: dict[str, Any],
    source: dict[str, Any],
    template_basename: str,
    features: list[dict[str, Any]],
    sources: list[dict[str, str]],
    out_root: Path,
    upstream_drops: list[dict[str, str]] | None = None,
    original_count: int | None = None,
) -> dict[str, Any] | None:
    """Group features per `source.split_by`, emit one GeoJSON shard + sources
    sidecar per group, and write the index manifest atomically.

    `template_basename` is the output of `derive_output_basename` containing
    `{<property>}` (e.g. `S22-villages-{dist_lgd}.geojson`); each group's
    value is substituted in to produce the shard basename.

    Per-shard budget: shards over `SNAPSHOT_BYTE_BUDGET` are deleted and
    omitted from both the shard list and the index manifest, mirroring the
    single-file budget behaviour.

    `upstream_drops` carries drop records from steps prior to the split (e.g.
    state_filter exclusions). They flow into the bundle-level unkeyed
    sidecar alongside features missing the split-by property.
    `original_count` is the feature count BEFORE any upstream filtering
    (e.g. the raw upstream count) — used for the unkeyed denominator.
    """
    split = source["split_by"]
    prop = split["property"]
    name_property = entry.get("name_property")
    groups, dropped_no_prop = apply_split_by(features, split)
    print(f"  split_by[{prop}] -> {len(groups)} groups (skipped {len(dropped_no_prop)} feature(s) with no {prop})", flush=True)

    emitted_keys: list[Any] = []
    total_bytes = 0
    skipped_oversize: list[Any] = []
    for key in sorted(groups, key=lambda k: (str(k))):
        shard_basename = template_basename.replace(f"{{{prop}}}", str(key))
        shard_path = out_root / shard_basename
        emit_feature_collection(shard_path, groups[key])
        size = shard_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            shard_path.unlink()
            skipped_oversize.append(key)
            print(
                f"  SKIP shard {shard_basename} — {size / 1024 / 1024:.1f} MB exceeds "
                f"{SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget",
                flush=True,
            )
            continue
        sidecar_path = shard_path.with_suffix(shard_path.suffix + ".sources.json")
        _write_sources_sidecar(sidecar_path, shard_basename, sources)
        emitted_keys.append(key)
        total_bytes += size

    # Index manifest. State LGD comes from the entry's state_filter when
    # present; the manifest schema requires it as a digit string.
    state_lgd = source.get("state_filter", {}).get("equals")
    if state_lgd is None:
        msg = (
            "split_by currently requires a state_filter equals to populate the "
            "index manifest's state_lgd; multi-state split is not yet supported."
        )
        raise ValueError(msg)
    index_basename = split.get("emit_index")
    if not index_basename:
        msg = "split_by requires `emit_index` (basename of the index manifest)"
        raise ValueError(msg)
    schema_basename = split.get("index_schema", "boundary.villages_index.schema.json")
    index_path = out_root / index_basename
    emit_index_manifest(index_path, state_lgd, emitted_keys, schema_basename, sources)

    # Bundle-level unkeyed sidecar (Hans v2 denominator). Aggregates upstream
    # drops (state_filter) + features missing the split-by property. The
    # `for` field points at the conceptual unsplit GeoJSON (no such file
    # exists on disk — only shards do — but the schema's `for` requires a
    # `.geojson` suffix, and the conceptual referent is unambiguous).
    bundle_for = template_basename.replace(f"-{{{prop}}}", "")
    bundle_unkeyed = out_root / f"{bundle_for}.unkeyed.json"
    drops: list[dict[str, str]] = list(upstream_drops or [])
    drops.extend(
        _make_drop_record(f, "no_lgd_code_in_source", name_property)
        for f in dropped_no_prop
    )
    retained_total = sum(len(groups[k]) for k in emitted_keys)
    if original_count is None:
        original_count = retained_total + len(drops)
    _write_unkeyed_sidecar(
        bundle_unkeyed, bundle_for, original_count, retained_total, drops, sources,
    )

    # Per-shard simplification metadata sidecar (when entry opted in via a
    # `metadata` block AND coord_precision was applied).
    coord_precision = source.get("coord_precision")
    entry_metadata = entry.get("metadata")
    if coord_precision is not None and entry_metadata:
        for key in emitted_keys:
            shard_basename = template_basename.replace(f"{{{prop}}}", str(key))
            metadata_path = out_root / f"{shard_basename}.metadata.json"
            _write_simplification_metadata_sidecar(
                metadata_path,
                shard_basename,
                entry_metadata,
                sources,
                coord_precision,
                original_feature_count=len(groups[key]),
                retained_feature_count=len(groups[key]),
            )

    record: dict[str, Any] = {
        "id": template_basename.removesuffix(".geojson"),
        "path": f"boundaries/in/geojson/{index_basename}",
        "kind": entry["kind"],
        "size_bytes": total_bytes,
        "fetched_at": sources[-1]["fetched_at"],
        "shard_count": len(emitted_keys),
        "shard_keys": [str(k) for k in emitted_keys],
    }
    if "state" in entry:
        record["state"] = entry["state"]
    if skipped_oversize:
        record["skipped_oversize"] = [str(k) for k in skipped_oversize]
    return record


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
        bundle_dir = raw_root / "snapshot" / basename.removesuffix(".geojson").replace("{", "_").replace("}", "_")
        features, sources = fetch_geojsonl_7z(
            urls,
            bundle_dir,
            coord_precision=source.get("coord_precision"),
        )
        name_property = entry.get("name_property")
        if "state_filter" in source:
            # State filtering is scope selection (this file is TN-only), not
            # LGD-join failure. Other states' features belong in other files,
            # not in this file's unkeyed sidecar — listing them would bloat
            # the sidecar and misframe the denominator (Hans intent: "of TN
            # villages, how many got an LGD code", not "of India villages,
            # how many are in TN"). They are dropped silently here.
            features, dropped_by_filter = apply_state_filter(features, source["state_filter"])
            print(f"  state_filter kept {len(features)} (dropped {len(dropped_by_filter)} out-of-scope)", flush=True)
        # From here on, `features` is this file's in-scope set. The unkeyed
        # denominator is computed against this, not the global upstream count.
        original_count = len(features)
        upstream_drops: list[dict[str, str]] = []
        if "split_by" in source:
            return _emit_split_shards(
                entry, source, basename, features, sources, out_root,
                upstream_drops=upstream_drops, original_count=original_count,
            )
        emit_feature_collection(out_path, features)
        # Single-file unkeyed sidecar — Hans v2 denominator. Always emit;
        # empty `dropped` is the canonical "perfect snapshot" signal.
        unkeyed_path = out_path.with_suffix(out_path.suffix + ".unkeyed.json")
        _write_unkeyed_sidecar(
            unkeyed_path, basename, original_count, len(features), upstream_drops, sources,
        )
        # Simplification metadata sidecar — only when coord_precision was
        # applied AND the entry opted in via a `metadata` block (license +
        # coverage are operator knowledge we won't synthesise).
        coord_precision = source.get("coord_precision")
        entry_metadata = entry.get("metadata")
        if coord_precision is not None and entry_metadata:
            metadata_path = out_path.with_suffix(out_path.suffix + ".metadata.json")
            _write_simplification_metadata_sidecar(
                metadata_path, basename, entry_metadata, sources,
                coord_precision, original_count, len(features),
            )
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
    parser.add_argument(
        "--kind",
        action="append",
        default=None,
        help="Run only entries whose `kind` matches (repeatable). Default: all.",
    )
    parser.add_argument(
        "--state",
        action="append",
        default=None,
        help="Run only entries whose `state` matches (repeatable). Default: all.",
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

    entries = cfg["inputs"]
    if args.kind:
        entries = [e for e in entries if e.get("kind") in args.kind]
    if args.state:
        entries = [e for e in entries if e.get("state") in args.state]
    if (args.kind or args.state) and not entries:
        print(
            f"no entries matched filters kind={args.kind} state={args.state}",
            file=sys.stderr,
        )
        return 2

    records = [
        r for r in (snapshot_one(e, out_root, raw_root) for e in entries) if r is not None
    ]

    print(f"\nsnapshotted {len(records)} files into {out_root.relative_to(root)}/")
    for r in records:
        size_kb = r["size_bytes"] / 1024
        print(f"  {r['path']:<48s} {size_kb:>8.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
