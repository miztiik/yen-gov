"""Boundary snapshot — fetch upstream sources and publish GeoJSON for the frontend.

Why this exists alongside build.py
==================================

build.py produces PMTiles (small, range-requestable) but requires `mapshaper`
and `tippecanoe` on PATH. Those aren't available on Windows out of the box,
and the frontend currently runs entirely off the GeoJSON fallback path
(see frontend/src/lib/maplibre/sources.ts > resolveSource).

This script snapshots the upstreams listed in pipeline.json into the Hive-
partitioned ``datasets/boundaries/in/<level>/state=<S>/...`` tree (per T.0d
§1 admin spine) AND emits the canonical ``boundary_layers.parquet`` control
table with a FK to ``taxonomy/sources.parquet`` per CLAUDE.md §12 v2.0.

The four sidecar writers that previously stamped per-file ``.sources.json`` /
``.unkeyed.json`` / ``.metadata.json`` + ``S22-villages-index.json`` are
GONE — their content lives in the parquet ledger as queryable columns
(amends ADR-0031; closes the cardinality-explosion class of bugs at
1000+ shard scale per Hans 2026-05-22 panel).

Source format dispatch
======================

Each pipeline.json entry carries a ``source`` block (format + urls + optional
coord_precision / state_filter / split_by) PLUS the new T.0d ``source_triple``
block (producer, title, vintage) that maps to a ``source_id`` in
``BOUNDARY_SOURCE_ID_BY_NICKNAME`` via the upstream URL prefix.

Dependencies
============

stdlib + ``pyshp`` (for shp_bundle) + ``py7zr`` (for geojsonl_7z). Install
with::

    pip install pyshp py7zr duckdb pydantic

The last two are pulled in transitively via ``boundary_layers_seed``.

Re-running
==========

    python tools/boundaries/snapshot.py

Re-fetches every entry, writes geojson to the Hive partition, collects one
``BoundaryLayerRow`` per emitted shard, and at end-of-run UPSERTs them all
into ``boundary_layers.parquet`` + ``sources.parquet``. Existing files in
the Hive tree are overwritten; deleting an entry from pipeline.json does
not delete the local copy (manual cleanup — we don't want a typo in the
config to accidentally nuke a snapshot).
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

# Add repo root's backend/ to sys.path so we can import the canonical
# emission seam. tools/ are otherwise self-contained per CLAUDE.md §3,
# but boundary_layers_seed is the contract surface for what this script
# writes — we honour the contract, not duplicate it.
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))
sys.path.insert(0, str(_THIS_DIR))

from yen_gov.canonical.boundary_layers_seed import (  # noqa: E402
    BOUNDARY_SOURCE_ID_BY_NICKNAME,
    BOUNDARY_SOURCE_ID_BY_TRIPLE,
    BoundaryLayerRow,
    compile_to_parquet,
)

from _paths import KIND_TO_LEVEL, derive_hive  # noqa: E402

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
    """Pipeline-entry id used for runtime scratch directories.

    Retained post-T.0d to name the .runtime/raw/snapshot/<bundle_dir>/
    scratch space (still ADR-0003: ephemeral, never datasets/). The
    citizen-facing OUTPUT path is now derived via `derive_partition_path`
    + `derive_hive` (Hive layout). For `kind: villages` with
    `source.split_by`, returns a template containing `{<property>}` so
    the orchestrator can substitute per district shard.
    """
    kind = entry["kind"]
    state = entry.get("state")
    if kind == "states":
        return "india-states.geojson"
    if kind == "country" and entry.get("country") == "IN" and not state:
        return "india-soi.geojson"
    if kind == "pc" and not state:
        # National-scope PC layer. The delim segment (e.g. ``2024``) is
        # carried in the partition_path / layer_id; the legacy basename
        # is only used to name ``.runtime/raw/<basename>`` scratch
        # directories for fetch formats and never appears on the
        # citizen path, so a stable basename suffices.
        delim = entry.get("delimitation_vintage")
        return f"india-pc-{delim}.geojson" if delim else "india-pc.geojson"
    if kind == "ac" and state:
        return f"{state}-ac.geojson"
    if kind == "districts" and not state:
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


def derive_partition_path(
    entry: dict[str, Any],
    district_lgd: str | None = None,
) -> tuple[str, str]:
    """Return (partition_path, layer_id) for one pipeline entry's shard.

    For `kind: villages` with `split_by`, the caller supplies
    `district_lgd` per shard.
    """
    kind = entry["kind"]
    state = entry.get("state")
    # ``delimitation_vintage`` is a top-level pipeline.json field on
    # electoral-constituency entries (kind in {ac, pc}); None for
    # admin-spine layers. derive_hive inserts it as a ``delim=<year>``
    # Hive segment immediately after the kind segment so per-state /
    # per-district sub-partitions still nest below it.
    delim = entry.get("delimitation_vintage")
    return derive_hive(
        kind=kind,
        delim=delim,
        state=state,
        district_lgd=district_lgd,
    )


def _resolve_source_id(entry: dict[str, Any]) -> str:
    """Resolve a pipeline entry's source_id from its source_triple block.

    pipeline.json carries the (producer, title, vintage) triple per entry
    (added in T.0d chunk 2a). We look up the source_id by hashing the
    triple in ``BOUNDARY_SOURCE_ID_BY_TRIPLE`` so multiple publications
    by the same producer (e.g. shijithpk's J&K AC layer and India PC
    layer) route to distinct ``source_id`` values. Falls back to
    URL-prefix matching when the source_triple block is absent (catches
    partially-migrated pipeline entries).
    """
    triple = entry.get("source_triple")
    if triple:
        triple_key = (
            triple.get("producer", ""),
            triple.get("title", ""),
            triple.get("vintage", ""),
        )
        source_id = BOUNDARY_SOURCE_ID_BY_TRIPLE.get(triple_key)
        if source_id is not None:
            return source_id
        msg = (
            f"source_triple {triple_key!r} on entry kind={entry.get('kind')!r} "
            f"does not match any of the {len(BOUNDARY_SOURCE_ID_BY_TRIPLE)} "
            "known boundary citation rows. Adding a new boundary source "
            "requires extending boundary_layers_seed.SOURCE_NICKNAMES + "
            "_BOUNDARY_SOURCE_TRIPLES + by_nickname dict in the same commit."
        )
        raise ValueError(msg)
    # Fallback: URL prefix matching (legacy entries pre source_triple).
    # local_file entries have no urls; they MUST carry source_triple.
    urls = entry.get("source", {}).get("urls", [])
    if urls:
        url0 = urls[0]
        for prefix, nickname in (
            ("https://raw.githubusercontent.com/datameet/maps/", "datameet"),
            ("https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/", "htl"),
            ("https://raw.githubusercontent.com/shijithpk/", "shijithpk"),
            ("https://github.com/ramSeraph/", "ramseraph"),
            ("https://raw.githubusercontent.com/yashveeeeeeer/", "yashveeeeeeer"),
        ):
            if url0.startswith(prefix):
                return BOUNDARY_SOURCE_ID_BY_NICKNAME[nickname]
    msg = f"could not resolve source_id for entry kind={entry.get('kind')!r}"
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


def fetch_local_file(src: Path, out_path: Path) -> None:
    """Copy a repo-local GeoJSON FeatureCollection to the canonical Hive
    output path. Used when the upstream snapshot was hand-delivered to
    ``datasets/ephemeral/`` (no live URL to re-fetch from). The source
    file MUST exist and MUST be a valid GeoJSON FeatureCollection; we
    validate the top-level shape before copying so a malformed drop is
    caught loudly at snapshot time, not silently propagated.

    The ``fetched_at`` timestamp that the live-fetch path returns is
    intentionally NOT recorded here: under ADR-0032 v2.0 the citation
    triple (producer, title, vintage) IS the identity, and live-fetch
    telemetry belongs in ``.runtime/`` sidecars. A locally-delivered
    file shares the SAME source_id as the live-fetch path would (same
    triple = same row), differing only in
    ``verification_method='transcribed'`` on the sources row.
    """
    if not src.is_file():
        msg = (
            f"format=local_file source path does not exist: {src}. "
            "local_file entries reference a repo-relative path under "
            "datasets/ephemeral/ that MUST be present in the working tree "
            "before snapshot runs. There is no fallback fetch."
        )
        raise FileNotFoundError(msg)
    with src.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        msg = (
            f"format=local_file source is not a GeoJSON FeatureCollection: {src} "
            f"(top-level type={data.get('type') if isinstance(data, dict) else type(data).__name__!r})"
        )
        raise ValueError(msg)
    if not isinstance(data.get("features"), list):
        msg = f"format=local_file source has no 'features' array: {src}"
        raise ValueError(msg)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out_path)


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


def apply_exclude_filter(
    features: list[dict[str, Any]],
    filter_spec: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Drop features whose property matches the exclude spec; keep the rest.

    Inverse of `apply_state_filter`. `filter_spec` shape (one of):
        {"property": "status", "equals": "Pre delimitation"}    # single
        {"property": "status", "one_of": ["a", "b"]}             # multi

    Returns `(kept, dropped)`. Empty `kept` IS a valid outcome here
    (the exclude can legitimately drop everything when the caller
    knows what they are doing); empty `dropped` is ALSO valid (no
    matches = no-op, common when filtering for vintage tags that
    only appear in some upstream slices).

    Used by Phase D.2 AC promotion to drop `status="Pre delimitation"`
    features from the ramSeraph LGD national release (D.1 recon §4).
    """
    prop = filter_spec["property"]
    if "equals" in filter_spec:
        target = filter_spec["equals"]
        match = lambda f: f.get("properties", {}).get(prop) == target  # noqa: E731
    elif "one_of" in filter_spec:
        targets = set(filter_spec["one_of"])
        match = lambda f: f.get("properties", {}).get(prop) in targets  # noqa: E731
    else:
        msg = f"exclude_filter {filter_spec!r} requires `equals` or `one_of`"
        raise ValueError(msg)

    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for f in features:
        (dropped if match(f) else kept).append(f)
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

# -----------------------------------------------------------------------------
# Orchestration: write Hive shards + accumulate canonical rows
# -----------------------------------------------------------------------------


def _emit_split_shards(
    entry: dict[str, Any],
    source: dict[str, Any],
    features: list[dict[str, Any]],
    datasets_root: Path,
    source_id: str,
) -> list[BoundaryLayerRow]:
    """Group features by ``source.split_by`` and emit one Hive-partitioned
    GeoJSON shard per group. Returns one ``BoundaryLayerRow`` per successfully
    emitted shard. Shards exceeding ``SNAPSHOT_BYTE_BUDGET`` are deleted and
    omitted from the row list (mirrors single-file budget behaviour).

    Post-T.0d shape: each shard writes to
    ``datasets/boundaries/in/<kind>/state=in_<lc>/district=<lgd>/all.geojson``
    via ``derive_hive`` — no index manifest, no sidecars. The shard layer-id
    encodes the same partition tuple, so the canonical parquet ledger gives
    the frontend everything the old index manifest used to provide (no
    404-probing).
    """
    split = source["split_by"]
    prop = split["property"]
    state = entry.get("state")
    if not state:
        msg = "split_by currently requires the entry to declare a state"
        raise ValueError(msg)
    coord_precision = source.get("coord_precision")
    simpl_alg = "coord-precision-round" if coord_precision is not None else None
    simpl_tol = 10 ** -coord_precision if coord_precision is not None else None

    groups, dropped_no_prop = apply_split_by(features, split)
    print(
        f"  split_by[{prop}] -> {len(groups)} groups "
        f"(skipped {len(dropped_no_prop)} feature(s) with no {prop})",
        flush=True,
    )

    rows: list[BoundaryLayerRow] = []
    for key in sorted(groups, key=lambda k: str(k)):
        district_lgd = str(key)
        partition_path, layer_id = derive_hive(
            kind=entry["kind"],
            state=state,
            district_lgd=district_lgd,
        )
        shard_path = datasets_root / partition_path
        emit_feature_collection(shard_path, groups[key])
        size = shard_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            shard_path.unlink()
            print(
                f"  SKIP shard {partition_path} — {size / 1024 / 1024:.1f} MB "
                f"exceeds {SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget",
                flush=True,
            )
            continue
        retained = len(groups[key])
        rows.append(
            BoundaryLayerRow(
                layer_id=layer_id,
                level=KIND_TO_LEVEL[entry["kind"]],
                partition_path=partition_path,
                format="geojson",
                crs="EPSG:4326",
                original_feature_count=retained,
                retained_feature_count=retained,
                unkeyed_count=0,
                size_bytes=size,
                source_id=source_id,
                entity_state=state,
                entity_district=district_lgd,
                simplification_algorithm=simpl_alg,
                simplification_tolerance_deg=simpl_tol,
                delimitation_vintage=entry.get("delimitation_vintage"),
            )
        )
    return rows


def _count_features_in_geojson(path: Path) -> int:
    """Count features in a GeoJSON file by parsing it. Used to derive the
    ``original_feature_count`` / ``retained_feature_count`` columns for
    entries where features are not held in memory (the ``geojson`` /
    ``shp_bundle`` paths write to disk first and don't expose a list)."""
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return len(data.get("features") or [])


def snapshot_one(
    entry: dict[str, Any],
    datasets_root: Path,
    raw_root: Path,
) -> list[BoundaryLayerRow]:
    """Snapshot one ``pipeline.json`` entry. Returns one ``BoundaryLayerRow``
    per emitted shard — one row for non-split entries, N rows for the
    villages-split case. Returns ``[]`` when the entry is skipped (oversize).

    ``datasets_root`` is the absolute path to the repo's ``datasets/`` dir;
    shards write under ``datasets_root / partition_path`` where
    ``partition_path`` is the Hive layout returned by ``derive_hive``.
    """
    source = entry["source"]
    fmt: str = source["format"]
    urls: list[str] = source.get("urls", [])
    source_id = _resolve_source_id(entry)
    state = entry.get("state")
    coord_precision = source.get("coord_precision")
    simpl_alg = "coord-precision-round" if coord_precision is not None else None
    simpl_tol = 10 ** -coord_precision if coord_precision is not None else None

    label = f"{entry['kind']}:{entry.get('state', '-')}"
    print(
        f"[{label}] format={fmt} ({len(urls)} url{'s' if len(urls) != 1 else ''}) source_id={source_id}",
        flush=True,
    )
    for u in urls:
        print(f"  {u}", flush=True)
    if fmt == "local_file":
        print(f"  local-file path: {source.get('path')!r}", flush=True)

    # Legacy basename still useful for naming runtime/raw scratch dirs.
    legacy_basename = derive_output_basename(entry)
    partition_path, layer_id = derive_partition_path(entry)
    out_path = datasets_root / partition_path

    if fmt == "geojson":
        fetch_geojson(urls, out_path)
        feature_count = _count_features_in_geojson(out_path)
        size = out_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            out_path.unlink()
            print(f"  SKIP — {size / 1024 / 1024:.1f} MB exceeds budget", flush=True)
            return []
        return [
            BoundaryLayerRow(
                layer_id=layer_id,
                level=KIND_TO_LEVEL[entry["kind"]],
                partition_path=partition_path,
                format="geojson",
                crs="EPSG:4326",
                original_feature_count=feature_count,
                retained_feature_count=feature_count,
                unkeyed_count=0,
                size_bytes=size,
                source_id=source_id,
                entity_state=state,
                simplification_algorithm=simpl_alg,
                simplification_tolerance_deg=simpl_tol,
                delimitation_vintage=entry.get("delimitation_vintage"),
            )
        ]

    if fmt == "local_file":
        # Repo-relative path resolved against datasets_root's parent
        # (i.e. the repo root). pipeline.json carries
        # e.g. ``datasets/ephemeral/india_ls_seats_545.geojson`` directly.
        # No fetched_at timestamp recorded: the citation triple is the
        # identity per ADR-0032 v2.0; verification_method on the source
        # row is ``transcribed``.
        rel = source.get("path")
        if not rel:
            msg = f"format=local_file requires source.path on entry kind={entry['kind']!r}"
            raise ValueError(msg)
        src = (datasets_root.parent / rel).resolve()
        fetch_local_file(src, out_path)
        feature_count = _count_features_in_geojson(out_path)
        size = out_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            out_path.unlink()
            print(f"  SKIP — {size / 1024 / 1024:.1f} MB exceeds budget", flush=True)
            return []
        return [
            BoundaryLayerRow(
                layer_id=layer_id,
                level=KIND_TO_LEVEL[entry["kind"]],
                partition_path=partition_path,
                format="geojson",
                crs="EPSG:4326",
                original_feature_count=feature_count,
                retained_feature_count=feature_count,
                unkeyed_count=0,
                size_bytes=size,
                source_id=source_id,
                entity_state=state,
                simplification_algorithm=simpl_alg,
                simplification_tolerance_deg=simpl_tol,
                delimitation_vintage=entry.get("delimitation_vintage"),
            )
        ]

    if fmt == "shp_bundle":
        bundle_dir = raw_root / "snapshot" / legacy_basename.removesuffix(".geojson")
        fetch_shp_bundle(urls, out_path, bundle_dir, coord_precision=coord_precision)
        feature_count = _count_features_in_geojson(out_path)
        size = out_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            out_path.unlink()
            print(f"  SKIP — {size / 1024 / 1024:.1f} MB exceeds budget", flush=True)
            return []
        return [
            BoundaryLayerRow(
                layer_id=layer_id,
                level=KIND_TO_LEVEL[entry["kind"]],
                partition_path=partition_path,
                format="geojson",
                crs="EPSG:4326",
                original_feature_count=feature_count,
                retained_feature_count=feature_count,
                unkeyed_count=0,
                size_bytes=size,
                source_id=source_id,
                entity_state=state,
                simplification_algorithm=simpl_alg,
                simplification_tolerance_deg=simpl_tol,
                delimitation_vintage=entry.get("delimitation_vintage"),
            )
        ]

    if fmt == "geojsonl_7z":
        bundle_dir = (
            raw_root
            / "snapshot"
            / legacy_basename.removesuffix(".geojson").replace("{", "_").replace("}", "_")
        )
        features, _ = fetch_geojsonl_7z(
            urls, bundle_dir, coord_precision=coord_precision,
        )
        if "state_filter" in source:
            features, dropped_by_filter = apply_state_filter(features, source["state_filter"])
            print(
                f"  state_filter kept {len(features)} "
                f"(dropped {len(dropped_by_filter)} out-of-scope)",
                flush=True,
            )
        if "exclude_filter" in source:
            features, dropped_by_exclude = apply_exclude_filter(features, source["exclude_filter"])
            print(
                f"  exclude_filter kept {len(features)} "
                f"(dropped {len(dropped_by_exclude)} matching)",
                flush=True,
            )
        original_count = len(features)
        if "split_by" in source:
            return _emit_split_shards(
                entry, source, features, datasets_root, source_id=source_id,
            )
        emit_feature_collection(out_path, features)
        size = out_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            out_path.unlink()
            print(f"  SKIP — {size / 1024 / 1024:.1f} MB exceeds budget", flush=True)
            return []
        return [
            BoundaryLayerRow(
                layer_id=layer_id,
                level=KIND_TO_LEVEL[entry["kind"]],
                partition_path=partition_path,
                format="geojson",
                crs="EPSG:4326",
                original_feature_count=original_count,
                retained_feature_count=len(features),
                unkeyed_count=0,
                size_bytes=size,
                source_id=source_id,
                entity_state=state,
                simplification_algorithm=simpl_alg,
                simplification_tolerance_deg=simpl_tol,
                delimitation_vintage=entry.get("delimitation_vintage"),
            )
        ]

    msg = f"unknown source.format: {fmt!r}"
    raise ValueError(msg)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot upstream boundary geometries into the canonical Hive tree.",
    )
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
    parser.add_argument(
        "--preserve-existing",
        action="store_true",
        help=(
            "Preserve boundary_layers rows already on disk that the current "
            "run does not re-emit. Use when running with --kind / --state "
            "filters to add or refresh a subset of layers without rebuilding "
            "everything (e.g. ingesting a new PC layer without re-fetching "
            "the other 6 upstream URLs). Without this flag the writer "
            "replaces all rows with the current run's emissions, which is "
            "the right behaviour for a full rebuild only."
        ),
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cfg_path = root / args.config
    if not cfg_path.is_file():
        print(f"config not found: {cfg_path}", file=sys.stderr)
        return 2

    with cfg_path.open(encoding="utf-8") as fh:
        cfg = json.load(fh)

    datasets_root = root / "datasets"
    raw_root = root / cfg.get("raw_dir", ".runtime/raw/boundaries")

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

    all_rows: list[BoundaryLayerRow] = []
    for e in entries:
        all_rows.extend(snapshot_one(e, datasets_root, raw_root))

    print(f"\nemitted {len(all_rows)} layer rows", flush=True)
    n_layers, n_sources = compile_to_parquet(
        all_rows,
        datasets_root,
        merge_with_existing=args.preserve_existing,
    )
    print(
        f"compiled to parquet: {n_layers} boundary_layers; "
        f"sources upserted (total now {n_sources})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
