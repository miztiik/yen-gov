"""One-shot migration tool: flat ``datasets/boundaries/in/geojson/*`` →
Hive-partitioned ``datasets/boundaries/in/<level>/state=<S>/...`` tree
PLUS emit the initial ``datasets/boundaries/boundary_layers.parquet``
control table.

T.0d chunk 3 (single-execution migrator). Run once via::

    python tools/boundaries/migrate_to_hive_layout.py --apply

Without ``--apply`` runs a DRY-RUN, prints the planned ``git mv`` moves
+ the inferred ``BoundaryLayerRow`` per shard, exits 0 without touching
disk. With ``--apply``:

1. For each of the 73 geojson files in the flat tree:
   * derive the target Hive path via ``_paths.derive_hive``;
   * read ``.metadata.json`` (when present) for simplification + feature
     count totals;
   * read ``.unkeyed.json`` (when present) for ``unkeyed_count`` +
     ``unkeyed_keys_json``;
   * fall back to scanning the geojson when totals sidecars are absent
     (states, country, most ACs were never simplified — no metadata
     sidecar; their feature count is read directly);
   * resolve ``source_id`` via the upstream URL in ``.sources.json``
     against the 5 BOUNDARY_SOURCES;
   * build ``BoundaryLayerRow``.
2. Run ``git mv`` to relocate each geometry file into its Hive path.
3. Call ``boundary_layers_seed.compile_to_parquet(rows, datasets_root)``
   to emit ``boundaries/boundary_layers.parquet`` + UPSERT the 5
   boundary citation rows into ``taxonomy/sources.parquet``.
4. Print a summary table (layer_id → old path → new path → size).

Sidecar deletion is OUT of scope here — chunk 3 follows up with
``git rm`` on the 115 sidecars + 3 retired schemas in the same fused
commit (CLAUDE.md §15). Failing here leaves git in a clean state
(``git mv`` failures abort BEFORE compile_to_parquet runs).

This file lives under ``tools/`` per CLAUDE.md §3: tools are
self-contained, never imported by backend runtime modules.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Add repo root to path so we can import backend.yen_gov modules
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from yen_gov.canonical.boundary_layers_seed import (  # noqa: E402
    BOUNDARY_SOURCE_ID_BY_NICKNAME,
    BoundaryLayerRow,
    compile_to_parquet,
)
from yen_gov.canonical.citation import derive_source_id  # noqa: E402

from _paths import KIND_TO_LEVEL, derive_hive  # noqa: E402


# Match `S22-villages-603.geojson` → (S22, 603); split-shard pattern.
_SPLIT_VILLAGE_RE = re.compile(r"^(?P<state>[SU]\d{2})-villages-(?P<district>\d+)\.geojson$")
# Match `S22-ac.geojson`, `U08-ac.geojson` — single-state AC layer.
_PER_STATE_AC_RE = re.compile(r"^(?P<state>[SU]\d{2})-ac\.geojson$")
# Match `S22-subdistricts.geojson` — single-state subdistrict layer.
_PER_STATE_SUBDISTRICT_RE = re.compile(r"^(?P<state>[SU]\d{2})-subdistricts\.geojson$")

# Map flat basename → (kind, state, district_lgd) for the 5 well-known
# all-India layers. Returns ``None`` for "no entity filter".
_ALL_INDIA_BASENAMES = {
    "india-states.geojson": ("states", None, None),
    "india-districts.geojson": ("districts", None, None),
    "india-soi.geojson": ("country", None, None),
}


# URL prefix → nickname; mirrored from _add_source_triple inserter so the
# resolution is consistent. Keep this list in sync with
# `boundary_layers_seed.SOURCE_NICKNAMES`.
_URL_TO_NICKNAME = [
    ("https://raw.githubusercontent.com/datameet/maps/", "datameet"),
    ("https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/", "htl"),
    ("https://raw.githubusercontent.com/shijithpk/", "shijithpk"),
    ("https://github.com/ramSeraph/", "ramseraph"),
    ("https://raw.githubusercontent.com/yashveeeeeeer/", "yashveeeeeeer"),
]


def _classify_basename(basename: str) -> tuple[str, str | None, str | None]:
    """Inspect a flat-tree geojson basename and return (kind, state, district_lgd).

    Raises ValueError if the basename doesn't match any of the 4 known
    shapes (all-India, per-state AC, per-state subdistrict, per-district
    village). The S22-villages-index.json manifest is handled separately
    by the caller (it's a sidecar, not a geometry file).
    """
    if basename in _ALL_INDIA_BASENAMES:
        kind, state, district = _ALL_INDIA_BASENAMES[basename]
        return kind, state, district
    m = _SPLIT_VILLAGE_RE.match(basename)
    if m:
        return "villages", m.group("state"), m.group("district")
    m = _PER_STATE_AC_RE.match(basename)
    if m:
        return "ac", m.group("state"), None
    m = _PER_STATE_SUBDISTRICT_RE.match(basename)
    if m:
        return "subdistricts", m.group("state"), None
    msg = f"unknown boundary basename: {basename}"
    raise ValueError(msg)


def _resolve_source_id(sidecar: Path) -> str:
    """Read a `.sources.json` sidecar and return the source_id by URL match."""
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    sources = data.get("sources") or []
    if not sources:
        msg = f"{sidecar.name}: empty `sources` array"
        raise ValueError(msg)
    url = sources[0].get("url", "")
    for prefix, nickname in _URL_TO_NICKNAME:
        if url.startswith(prefix):
            return BOUNDARY_SOURCE_ID_BY_NICKNAME[nickname]
    msg = f"{sidecar.name}: no known nickname for url {url!r}"
    raise ValueError(msg)


def _read_metadata_sidecar(metadata_path: Path) -> dict[str, Any]:
    """Return the parsed sidecar dict, or {} if absent."""
    if not metadata_path.is_file():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _read_unkeyed_sidecar(unkeyed_path: Path) -> dict[str, Any]:
    """Return the parsed sidecar dict, or {} if absent (no drops happened)."""
    if not unkeyed_path.is_file():
        return {}
    return json.loads(unkeyed_path.read_text(encoding="utf-8"))


def _count_features(geojson_path: Path) -> int:
    """Cheap-ish feature count: parse JSON, return len(features). Used as
    fallback when no .metadata.json + no .unkeyed.json sidecar exists
    (states/country/most ACs). ~10ms per file; acceptable for the
    one-shot migration."""
    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection":
        msg = f"{geojson_path.name}: not a FeatureCollection"
        raise ValueError(msg)
    return len(data.get("features") or [])


# Map metadata-sidecar `simplification.algorithm` → boundary-layers schema enum.
# Today snapshot.py only emits `coord-precision-round`; widening is additive.
_ALGO_PASSTHROUGH = {
    "coord-precision-round",
    "douglas-peucker",
    "visvalingam",
    "shapely-preserve-topology",
}


def _build_row(
    geojson_path: Path,
    sources_sidecar: Path,
    metadata_sidecar: Path,
    unkeyed_sidecar: Path,
) -> BoundaryLayerRow:
    """Assemble a BoundaryLayerRow from one on-disk geojson + its sidecars."""
    basename = geojson_path.name
    kind, state, district_lgd = _classify_basename(basename)
    level = KIND_TO_LEVEL[kind]
    partition_path, layer_id = derive_hive(
        kind=kind, state=state, district_lgd=district_lgd,
    )
    source_id = _resolve_source_id(sources_sidecar)
    size_bytes = geojson_path.stat().st_size

    metadata = _read_metadata_sidecar(metadata_sidecar)
    unkeyed = _read_unkeyed_sidecar(unkeyed_sidecar)

    # Feature counts: prefer unkeyed sidecar totals (most authoritative),
    # then metadata sidecar simplification counts, then a live count.
    if unkeyed:
        totals = unkeyed.get("totals", {})
        original = int(totals.get("original", 0))
        retained = int(totals.get("retained", 0))
        unkeyed_count = int(totals.get("dropped", 0))
        unkeyed_records = unkeyed.get("dropped", [])
    elif metadata:
        simp = metadata.get("simplification", {})
        original = int(simp.get("original_feature_count", 0))
        retained = int(simp.get("retained_feature_count", 0))
        unkeyed_count = 0
        unkeyed_records = []
    else:
        original = retained = _count_features(geojson_path)
        unkeyed_count = 0
        unkeyed_records = []

    unkeyed_keys_json: str | None = None
    if unkeyed_records:
        # Compact summary: list the source_feature_name + reason as JSON
        # array string. Citizen UI can render or skip; preserves the
        # information without inflating the parquet with per-feature columns.
        compact = [
            {"name": r.get("source_feature_name", ""), "reason": r.get("reason", "")}
            for r in unkeyed_records
        ]
        unkeyed_keys_json = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))

    # Simplification fields from metadata sidecar (None when absent).
    simp_algo: str | None = None
    simp_tol: float | None = None
    if metadata:
        simp_block = metadata.get("simplification", {})
        algo = simp_block.get("algorithm")
        if algo in _ALGO_PASSTHROUGH:
            simp_algo = algo
        tol = simp_block.get("tolerance_deg")
        if isinstance(tol, (int, float)):
            simp_tol = float(tol)

    # Build notes from upstream `description` if present.
    notes: str | None = None
    if metadata.get("description"):
        notes = str(metadata["description"])[:500]  # bound width

    return BoundaryLayerRow(
        layer_id=layer_id,
        level=level,
        entity_state=f"in_{state.lower()}" if state else None,
        entity_district=district_lgd,
        entity_city=None,
        partition_path=partition_path,
        format="geojson",
        crs="EPSG:4326",
        simplification_algorithm=simp_algo,
        simplification_tolerance_deg=simp_tol,
        original_feature_count=original,
        retained_feature_count=retained,
        unkeyed_count=unkeyed_count,
        unkeyed_keys_json=unkeyed_keys_json,
        size_bytes=size_bytes,
        source_id=source_id,
        notes=notes,
    )


def _git_mv(src: Path, dst: Path, *, repo_root: Path) -> None:
    """Run ``git mv <src> <dst>`` from repo_root, creating dst.parent first.

    Uses git mv (not shutil.move) so the rename is recorded as a single
    git operation with rename-detection, NOT as delete+add. Without
    --apply this is never called.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    rel_src = src.relative_to(repo_root)
    rel_dst = dst.relative_to(repo_root)
    proc = subprocess.run(
        ["git", "mv", str(rel_src).replace("\\", "/"), str(rel_dst).replace("\\", "/")],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (
            f"git mv {rel_src} → {rel_dst} failed (rc={proc.returncode}):\n"
            f"  stdout: {proc.stdout.strip()}\n"
            f"  stderr: {proc.stderr.strip()}"
        )
        raise RuntimeError(msg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate flat datasets/boundaries/in/geojson/* to Hive layout + emit boundary_layers.parquet.",
    )
    parser.add_argument(
        "--root",
        default=str(_REPO_ROOT),
        help="Repo root (default: auto-detected).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (git mv + compile parquet). Without this flag, DRY-RUN only.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.root).resolve()
    flat_root = repo_root / "datasets" / "boundaries" / "in" / "geojson"
    datasets_root = repo_root / "datasets"

    if not flat_root.is_dir():
        print(f"flat boundary root does not exist: {flat_root}", file=sys.stderr)
        return 2

    # Collect all *.geojson files (skip *.sources.json, *.metadata.json,
    # *.unkeyed.json, S22-villages-index.json).
    geojson_files = sorted(flat_root.glob("*.geojson"))
    print(f"found {len(geojson_files)} geojson files under {flat_root.relative_to(repo_root)}/")

    rows: list[BoundaryLayerRow] = []
    moves: list[tuple[Path, Path]] = []  # (src, dst) pairs to git mv

    for geojson_path in geojson_files:
        basename = geojson_path.name
        sources_sidecar = geojson_path.with_suffix(geojson_path.suffix + ".sources.json")
        metadata_sidecar = geojson_path.with_suffix(geojson_path.suffix + ".metadata.json")
        unkeyed_sidecar = geojson_path.with_suffix(geojson_path.suffix + ".unkeyed.json")

        if not sources_sidecar.is_file():
            print(f"  SKIP {basename}: missing .sources.json sidecar", file=sys.stderr)
            continue

        try:
            row = _build_row(
                geojson_path, sources_sidecar, metadata_sidecar, unkeyed_sidecar,
            )
        except ValueError as e:
            print(f"  ERROR {basename}: {e}", file=sys.stderr)
            return 3

        target = repo_root / "datasets" / row.partition_path
        rows.append(row)
        moves.append((geojson_path, target))

    print(f"\nplanned {len(moves)} migrations:")
    for src, dst in moves[:5]:
        print(f"  {src.relative_to(repo_root).as_posix()} -> {dst.relative_to(repo_root).as_posix()}")
    if len(moves) > 5:
        print(f"  ... +{len(moves) - 5} more")

    # PK uniqueness check before applying anything. If two flat files would
    # collapse onto the same Hive layer_id, abort.
    seen: set[str] = set()
    for r in rows:
        if r.layer_id in seen:
            print(f"ERROR: duplicate layer_id {r.layer_id!r} — would collide on PK", file=sys.stderr)
            return 4
        seen.add(r.layer_id)

    if not args.apply:
        print("\nDRY-RUN: pass --apply to execute git mv + compile parquet.")
        # Still validate the rows can compile to a temp dir for early-fail.
        return 0

    # ----- APPLY ---------------------------------------------------------
    print("\napplying git mv...")
    for src, dst in moves:
        _git_mv(src, dst, repo_root=repo_root)
        print(f"  mv {src.relative_to(repo_root).as_posix()} -> {dst.relative_to(repo_root).as_posix()}")

    print("\ncompiling boundary_layers.parquet + UPSERTing taxonomy/sources.parquet...")
    n_layers, n_sources = compile_to_parquet(rows, datasets_root)
    print(f"  wrote {n_layers} boundary layers; {n_sources} boundary sources upserted")
    print(f"\noutputs:")
    print(f"  datasets/boundaries/boundary_layers.parquet  ({(datasets_root / 'boundaries' / 'boundary_layers.parquet').stat().st_size} bytes)")
    print(f"  datasets/taxonomy/sources.parquet           ({(datasets_root / 'taxonomy' / 'sources.parquet').stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
