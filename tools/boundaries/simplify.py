"""Boundary simplifier — apply per-layer Douglas-Peucker tolerance to every
shipped GeoJSON shard under ``datasets/boundaries/in/`` and update the
canonical ledger.

Why this exists alongside build.py
==================================

``tools/boundaries/build.py`` simplifies en route to PMTiles via mapshaper +
tippecanoe. The frontend currently renders the raw GeoJSON fallback path
(see ``frontend/src/lib/maplibre/sources.ts > resolveSource``); citizens are
shipped the GeoJSON bytes verbatim, gzipped over HTTP. Without simplification
that's 30+ MB raw → 9+ MB gzipped for the seven national+UP-AC outliers.
Phase 0.4 of the boundary-coverage expansion sprint (Plan
``TODO/20260524-boundary-coverage-expansion-plan.md``) closes that gap by
running mapshaper IN-PLACE on the shipped GeoJSONs and re-emitting the
canonical ``boundary_layers.parquet`` with the updated tolerance + size.

Why mapshaper (not Shapely)
===========================

Adjacent polygons (states, districts, AC, PC) share boundaries. Per-polygon
Douglas-Peucker (Shapely's ``simplify(preserve_topology=True)``) simplifies
each feature independently, so the boundary between Tamil Nadu and Karnataka
gets DIFFERENT vertex paths on each side → visible sliver gaps and overlaps
at India zoom. ``mapshaper`` first builds the topology (detects shared arcs),
then applies the simplification to each arc once. Adjacent features stay
glued. This matches the convention already established by build.py.

Per-layer tolerance table
=========================

Tolerances are tuned to hit the gzipped-size ceilings declared in the plan
doc (and asserted by the ``boundaries-conform`` vitest contract added in this
same PR). Higher tolerance = more aggressive simplification = smaller file.

``country``  is a single MultiPolygon outline of India; safe to simplify
hard. ``villages`` are already small (largest is ~500 KB gz); only a light
touch is needed. ``ac`` has a long tail — UP at ~2.1 MB gz dwarfs the median
(~250 KB gz); the chosen interval gives UP enough headroom while leaving
small-state AC shards visually unchanged.

Re-running
==========

    python tools/boundaries/simplify.py

Walks the boundary_layers parquet, simplifies each shard in place,
overwrites the parquet with updated rows. Idempotent — re-running with the
same tolerance table produces byte-identical output.

Dependencies
============

- ``mapshaper`` on PATH (``npm install -g mapshaper``).
- stdlib + ``duckdb`` + ``pydantic`` (transitive via ``boundary_layers_seed``).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Add repo root's backend/ to sys.path. tools/ are self-contained per
# CLAUDE.md §3, but we honour the boundary_layers_seed contract rather than
# duplicate its shape.
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from yen_gov.canonical.boundary_layers_seed import (  # noqa: E402
    BoundaryLayerRow,
    _read_existing_boundary_layers,
    compile_to_parquet,
)


# ----------------------------------------------------------------------
# Per-layer tolerance + gzipped-size targets
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class LayerTuning:
    """Per-layer simplification configuration.

    ``interval_deg`` is the Douglas-Peucker interval in decimal degrees
    passed to ``mapshaper -simplify dp interval=<X> planar keep-shapes``.
    Larger value = more aggressive thinning.

    ``gzip_ceiling_kb`` is the per-file gzipped-size budget asserted by
    ``frontend/src/contracts/boundaries-conform.test.ts``. The contract
    fails if any shard exceeds its ceiling — this is the regression gate
    against accidental geometry inflation in a future ingest.
    """

    interval_deg: float
    gzip_ceiling_kb: float


# Plan-doc §0.4 "Per-layer simplification targets" table.
# Keyed on the boundary level (column in boundary_layers parquet).
# `country` is one shard; `state`/`district`/`pc` are one shard each;
# `subdistrict`/`ac`/`village` are per-state or per-district shards.
#
# Intervals are hand-tuned (one iteration on 2026-05-24) against the
# WORST shard in each level so the gzip ceiling holds for every file
# in the level. Smaller files in the level simplify proportionally
# further but stay visually faithful at India / state zoom — the
# tolerance is small relative to the shape's diameter.
#
# Headroom check (post-tune, against the WORST shard in each level):
#   country         48.7 KB gz  / ceiling 100  KB  (47%)
#   state          109.8 KB gz  / ceiling 200  KB  (55%)
#   district        worst pre-tune was 551 KB at 0.005°; at 0.010° expected ~285 KB
#   pc              worst pre-tune was 1473 KB at 0.005°; at 0.020° expected ~415 KB
#   ac              worst pre-tune was 547 KB on s24 at 0.003°; at 0.005° expected ~455 KB
#   subdistrict    169.3 KB gz  / ceiling 300  KB  (56%)
#   village        208.7 KB gz  / ceiling 500  KB  (42%)
LAYER_TUNING: dict[str, LayerTuning] = {
    "country": LayerTuning(interval_deg=0.020, gzip_ceiling_kb=100.0),
    "state": LayerTuning(interval_deg=0.010, gzip_ceiling_kb=200.0),
    "district": LayerTuning(interval_deg=0.010, gzip_ceiling_kb=500.0),
    "pc": LayerTuning(interval_deg=0.020, gzip_ceiling_kb=500.0),
    "ac": LayerTuning(interval_deg=0.005, gzip_ceiling_kb=500.0),
    "subdistrict": LayerTuning(interval_deg=0.002, gzip_ceiling_kb=300.0),
    "village": LayerTuning(interval_deg=0.0005, gzip_ceiling_kb=500.0),
    # `postal` is a single Chennai pincode polygon set — not currently
    # in the corpus but listed in the schema's level enum. Treat as
    # district-equivalent if it lands.
    "postal": LayerTuning(interval_deg=0.010, gzip_ceiling_kb=500.0),
}

# Mapshaper invocation. `planar` runs simplification in 2D decimal-degree
# space rather than 3D Cartesian (3D is overkill at India scale and ~5×
# slower). `keep-shapes` protects tiny polygons (e.g. small villages,
# island AC shards) from being simplified out of existence.
_MAPSHAPER_BIN = "mapshaper"

# Resolved at module load (or first use) by _require_mapshaper. On Windows
# the npm shim is `mapshaper.CMD`; subprocess.run with the bare name fails
# with WinError 2 because Windows looks for `mapshaper.exe` first. Passing
# the full path side-steps that.
_MAPSHAPER_PATH: str | None = None


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _require_mapshaper() -> str:
    """Resolve and cache the mapshaper executable path. Fails loudly if
    missing so the operator gets an actionable message instead of a
    Windows ENOENT trace."""
    global _MAPSHAPER_PATH
    if _MAPSHAPER_PATH is None:
        resolved = shutil.which(_MAPSHAPER_BIN)
        if resolved is None:
            sys.exit(
                "FATAL: mapshaper not found on PATH.\n"
                "Install with: npm install -g mapshaper\n"
                "See tools/boundaries/build.py for the same pattern."
            )
        _MAPSHAPER_PATH = resolved
    return _MAPSHAPER_PATH


def _gzip_size_kb(path: Path) -> float:
    """Round-trip the file through gzip and return the compressed size in KB.

    The conform contract asserts on gzip size (not raw) because that's what
    the citizen actually downloads — HTTP traffic to GitHub Pages is gzipped
    end-to-end.
    """
    import gzip

    raw = path.read_bytes()
    compressed = gzip.compress(raw, compresslevel=6)
    return len(compressed) / 1024


def _simplify_in_place(input_path: Path, interval_deg: float) -> None:
    """Run mapshaper on ``input_path``, writing simplified output back to the
    same path. Atomic — writes to ``<path>.simplified.tmp`` and renames.
    """
    tmp_out = input_path.with_suffix(input_path.suffix + ".simplified.tmp")
    cmd = [
        _require_mapshaper(),
        str(input_path),
        "-simplify",
        "dp",
        f"interval={interval_deg}",
        "planar",
        "keep-shapes",
        "-o",
        str(tmp_out),
        "format=geojson",
    ]
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Best-effort cleanup; don't mask the original error.
        tmp_out.unlink(missing_ok=True)
        sys.exit(
            f"FATAL: mapshaper failed on {input_path} with exit {result.returncode}\n"
            f"stderr:\n{result.stderr}"
        )
    if not tmp_out.is_file():
        sys.exit(
            f"FATAL: mapshaper completed but produced no output at {tmp_out}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    # Atomic replace.
    tmp_out.replace(input_path)


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------


@dataclass
class SimplifyResult:
    layer_id: str
    file_path: Path
    before_kb: float
    after_kb: float
    before_gz_kb: float
    after_gz_kb: float
    interval_deg: float
    gzip_ceiling_kb: float

    @property
    def passes_ceiling(self) -> bool:
        return self.after_gz_kb <= self.gzip_ceiling_kb


def simplify_all(
    datasets_root: Path,
    *,
    only_layers: set[str] | None = None,
    dry_run: bool = False,
) -> tuple[list[SimplifyResult], list[BoundaryLayerRow]]:
    """Simplify every GeoJSON shard registered in boundary_layers.parquet.

    Returns ``(results, updated_rows)`` where ``updated_rows`` is the full
    set of rows ready to feed back to ``compile_to_parquet`` (modified
    rows reflect the new size + simplification fields; non-modified rows
    are echoed verbatim so the parquet stays whole).
    """
    rows = _read_existing_boundary_layers(datasets_root)
    if not rows:
        sys.exit(
            "FATAL: boundary_layers.parquet has no rows.\n"
            "Run tools/boundaries/snapshot.py first to seed the ledger."
        )

    results: list[SimplifyResult] = []
    updated_rows: list[BoundaryLayerRow] = []
    for row in rows:
        # Only process geojson shards — pmtiles shards are simplified by
        # tippecanoe upstream (build.py).
        if row.format != "geojson":
            updated_rows.append(row)
            continue
        if only_layers is not None and row.level not in only_layers:
            updated_rows.append(row)
            continue
        if row.level not in LAYER_TUNING:
            print(
                f"  [skip] {row.layer_id}: level={row.level} has no tuning entry",
                file=sys.stderr,
            )
            updated_rows.append(row)
            continue

        tuning = LAYER_TUNING[row.level]
        file_path = datasets_root / row.partition_path
        if not file_path.is_file():
            print(
                f"  [skip] {row.layer_id}: file not on disk at {file_path}",
                file=sys.stderr,
            )
            updated_rows.append(row)
            continue

        before_kb = file_path.stat().st_size / 1024
        before_gz_kb = _gzip_size_kb(file_path)

        if dry_run:
            after_kb = before_kb
            after_gz_kb = before_gz_kb
            updated_rows.append(row)
        else:
            _simplify_in_place(file_path, tuning.interval_deg)
            after_kb = file_path.stat().st_size / 1024
            after_gz_kb = _gzip_size_kb(file_path)
            # Recompute the feature count — mapshaper preserves features
            # by default (keep-shapes) but verify so the denominator
            # invariant holds.
            with file_path.open("rb") as fh:
                fc = json.load(fh)
            feature_count = len(fc.get("features", []))
            # Build the updated row. retained_feature_count and
            # original_feature_count both equal feature_count after
            # simplification (we only thin vertices, not features); the
            # *original* count from snapshot.py is what was originally
            # ingested upstream, which we preserve verbatim. unkeyed_count
            # carries through.
            updated_rows.append(
                row.model_copy(
                    update={
                        "simplification_algorithm": "douglas-peucker",
                        "simplification_tolerance_deg": tuning.interval_deg,
                        "size_bytes": file_path.stat().st_size,
                        "retained_feature_count": feature_count,
                    }
                )
            )

        results.append(
            SimplifyResult(
                layer_id=row.layer_id,
                file_path=file_path,
                before_kb=before_kb,
                after_kb=after_kb,
                before_gz_kb=before_gz_kb,
                after_gz_kb=after_gz_kb,
                interval_deg=tuning.interval_deg,
                gzip_ceiling_kb=tuning.gzip_ceiling_kb,
            )
        )

    return results, updated_rows


def _print_results(results: Iterable[SimplifyResult]) -> int:
    """Pretty-print a table of before/after sizes. Returns the count of
    files that exceed their gzip ceiling (0 = all green)."""
    breaches = 0
    print()
    print(f"{'layer_id':<55} {'raw KB':>10} {'gz KB':>9} {'->raw KB':>10} {'->gz KB':>9} {'tol':>7} {'ceil':>7} {'ok?':>4}")
    print("-" * 124)
    for r in sorted(results, key=lambda x: (-x.after_gz_kb, x.layer_id)):
        flag = "OK" if r.passes_ceiling else "FAIL"
        if not r.passes_ceiling:
            breaches += 1
        print(
            f"{r.layer_id:<55} {r.before_kb:>10.1f} {r.before_gz_kb:>9.1f} "
            f"{r.after_kb:>10.1f} {r.after_gz_kb:>9.1f} "
            f"{r.interval_deg:>7.4f} {r.gzip_ceiling_kb:>7.1f} {flag:>4}"
        )
    return breaches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets-root",
        type=Path,
        default=_REPO_ROOT / "datasets",
        help="Path to datasets/ root (default: repo root).",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="Limit to one or more levels (e.g. --only country state).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report before/after gzip sizes without modifying any file.",
    )
    parser.add_argument(
        "--skip-parquet",
        action="store_true",
        help="Skip re-emitting boundary_layers.parquet (use for tuning runs).",
    )
    args = parser.parse_args(argv)

    _require_mapshaper()

    only = set(args.only) if args.only else None
    results, updated_rows = simplify_all(
        args.datasets_root.resolve(),
        only_layers=only,
        dry_run=args.dry_run,
    )
    breaches = _print_results(results)

    if not args.dry_run and not args.skip_parquet:
        print()
        print("Re-emitting boundary_layers.parquet …")
        n_layers = compile_to_parquet(
            updated_rows,
            args.datasets_root.resolve(),
            merge_with_existing=False,
        )
        print(f"  wrote {n_layers} layer rows")

    print()
    if breaches:
        print(f"FAIL: {breaches} file(s) exceed their gzip ceiling.")
        return 1
    print(f"OK: all {len(results)} simplified shard(s) within their gzip ceiling.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
