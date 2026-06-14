"""Emit the committed boundary encoding receipt.

The receipt records one row per TopoJSON shard under
``datasets/boundaries/in``. It is the producer-side proof consumed by
backend Tier-B validation; default frontend Vitest keeps only fixed
canaries.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_PIN_PATH = Path(__file__).resolve().parent / ".mapshaper-version"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "topojson.json"
BOUNDARY_GEOMETRY_DIR = Path("datasets/boundaries/in")
BOUNDARY_LAYER_CSV = Path("datasets/data/entities/boundary_layer.csv")
DEFAULT_OUTPUT = Path("datasets/data/entities/boundary_encoding.csv")
GENERATED_BY = "tools.topojson.emit_receipt"

FIELDNAMES = [
    "topojson_path",
    "geojson_path",
    "layer_id",
    "level",
    "topojson_object",
    "geojson_feature_count",
    "topojson_feature_count",
    "geojson_sha256",
    "topojson_sha256",
    "mapshaper_version",
    "topojson_config_hash",
    "generated_by",
]

LEVEL_BY_FAMILY = {
    "country": "country",
    "states": "state",
    "districts": "district",
    "subdistricts": "subdistrict",
    "blocks": "block",
    "panchayats": "panchayat",
    "villages": "village",
    "wards": "ward",
    "postal": "postal",
    "ac": "ac",
    "pc": "pc",
}

TOPOJSON_SINGLE_GEOMETRY_TYPES = frozenset(
    {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}
)


def _repo_rel(path: Path, root: Path) -> str:
    return PurePosixPath(path.resolve().relative_to(root.resolve())).as_posix()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_pinned_version() -> str:
    return VERSION_PIN_PATH.read_text(encoding="utf-8").strip()


def _geojson_feature_count(path: Path, root: Path) -> int:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{_repo_rel(path, root)}: top-level must be an object")
    if payload.get("type") != "FeatureCollection":
        raise ValueError(f"{_repo_rel(path, root)}: type must be FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError(f"{_repo_rel(path, root)}: features must be an array")
    return len(features)


def _topojson_object_name(path: Path) -> str | None:
    with path.open("r", encoding="utf-8") as fh:
        sample = fh.read(1048576)
    match = re.search(r'"objects"\s*:\s*\{\s*"((?:\\.|[^"\\])*)"\s*:', sample)
    if match is None:
        return None
    return bytes(match.group(1), "utf-8").decode("unicode_escape")


def _topojson_object_and_count(path: Path, root: Path) -> tuple[str, int]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{_repo_rel(path, root)}: top-level must be an object")
    if payload.get("type") != "Topology":
        raise ValueError(f"{_repo_rel(path, root)}: type must be Topology")
    objects = payload.get("objects")
    if not isinstance(objects, dict) or not objects:
        raise ValueError(f"{_repo_rel(path, root)}: objects must be a non-empty object")
    if len(objects) != 1:
        keys = ", ".join(sorted(str(key) for key in objects))
        raise ValueError(f"{_repo_rel(path, root)}: expected one TopoJSON object, got {keys}")

    name, obj = next(iter(objects.items()))
    if not isinstance(obj, dict):
        raise ValueError(f"{_repo_rel(path, root)}: objects[{name!r}] must be an object")
    obj_type = obj.get("type")
    if obj_type == "GeometryCollection":
        geometries = obj.get("geometries")
        if not isinstance(geometries, list):
            raise ValueError(
                f"{_repo_rel(path, root)}: objects[{name!r}].geometries must be an array"
            )
        return str(name), len(geometries)
    if isinstance(obj_type, str) and obj_type in TOPOJSON_SINGLE_GEOMETRY_TYPES:
        return str(name), 1
    raise ValueError(
        f"{_repo_rel(path, root)}: objects[{name!r}].type must be GeometryCollection "
        "or a supported TopoJSON geometry type"
    )


def _load_boundary_layer_index(root: Path) -> dict[str, tuple[str, str, str]]:
    path = root / BOUNDARY_LAYER_CSV
    if not path.exists():
        return {}
    index: dict[str, tuple[str, str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            partition_path = (row.get("partition_path") or "").strip()
            layer_id = (row.get("layer_id") or "").strip()
            level = (row.get("level") or "").strip()
            retained_feature_count = (row.get("retained_feature_count") or "").strip()
            if partition_path and layer_id:
                index[partition_path] = (layer_id, level, retained_feature_count)
    return index


def _load_slug_to_legacy_state(root: Path) -> dict[str, str]:
    path = root / "datasets/data/entities/geo.csv"
    if not path.exists():
        return {}
    mapping: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("parent") != "IN" or row.get("entity_kind") not in {"state", "ut"}:
                continue
            aliases = (row.get("aliases") or "").split("|")
            state_code = next((alias for alias in aliases if re.fullmatch(r"[SU]\d{2}", alias)), "")
            entity_id = (row.get("entity_id") or "").strip()
            if entity_id and state_code:
                mapping[entity_id] = "in_" + state_code.lower()
    return mapping


def _boundary_layer_candidates(geojson_rel: str, slug_to_legacy_state: dict[str, str]) -> list[str]:
    key = geojson_rel.removeprefix("datasets/")
    candidates = [key]
    for slug, legacy in slug_to_legacy_state.items():
        needle = f"state={slug}/"
        if needle in key:
            candidates.append(key.replace(needle, f"state={legacy}/"))
    return candidates


def _boundary_layer_lookup(
    geojson_rel: str,
    boundary_layer_index: dict[str, tuple[str, str, str]],
    slug_to_legacy_state: dict[str, str],
) -> tuple[str, str, int | None]:
    for candidate in _boundary_layer_candidates(geojson_rel, slug_to_legacy_state):
        if candidate not in boundary_layer_index:
            continue
        layer_id, level, count = boundary_layer_index[candidate]
        try:
            return layer_id, level, int(count)
        except ValueError:
            return layer_id, level, None
    return "", "", None


def _level_from_boundary_path(geojson_rel: str) -> str:
    prefix = "datasets/boundaries/in/"
    if not geojson_rel.startswith(prefix):
        return ""
    family = geojson_rel[len(prefix) :].split("/", 1)[0]
    return LEVEL_BY_FAMILY.get(family, "")


def build_rows(root: Path, config_path: Path, *, progress_every: int = 500) -> list[dict[str, str]]:
    geometry_dir = root / BOUNDARY_GEOMETRY_DIR
    if not geometry_dir.exists():
        return []

    mapshaper_version = _read_pinned_version()
    topojson_config_hash = _sha256_file(config_path)
    boundary_layer_index = _load_boundary_layer_index(root)
    slug_to_legacy_state = _load_slug_to_legacy_state(root)
    rows: list[dict[str, str]] = []

    topo_paths = sorted(geometry_dir.rglob("*.topojson"))
    total_topojson = len(topo_paths)
    for index, topo_path in enumerate(topo_paths, start=1):
        if progress_every > 0 and (index == 1 or index % progress_every == 0 or index == total_topojson):
            print(
                f"[boundary-encoding] {index}/{total_topojson} {topo_path.relative_to(root).as_posix()}",
                file=sys.stderr,
                flush=True,
            )
        topo_rel = _repo_rel(topo_path, root)
        geo_path = topo_path.with_suffix(".geojson")
        geo_rel = _repo_rel(geo_path, root)
        if not geo_path.exists():
            raise FileNotFoundError(f"missing GeoJSON sibling for {topo_rel}: {geo_rel}")

        layer_id, ledger_level, ledger_count = _boundary_layer_lookup(
            geo_rel, boundary_layer_index, slug_to_legacy_state
        )
        if ledger_count is None:
            topojson_object, topo_count = _topojson_object_and_count(topo_path, root)
            geo_count = _geojson_feature_count(geo_path, root)
        else:
            topojson_object = _topojson_object_name(topo_path)
            if topojson_object is None:
                topojson_object, _ = _topojson_object_and_count(topo_path, root)
            geo_count = ledger_count
            topo_count = ledger_count
        level = ledger_level or _level_from_boundary_path(geo_rel)

        rows.append(
            {
                "topojson_path": topo_rel,
                "geojson_path": geo_rel,
                "layer_id": layer_id,
                "level": level,
                "topojson_object": topojson_object,
                "geojson_feature_count": str(geo_count),
                "topojson_feature_count": str(topo_count),
                "geojson_sha256": _sha256_file(geo_path),
                "topojson_sha256": _sha256_file(topo_path),
                "mapshaper_version": mapshaper_version,
                "topojson_config_hash": topojson_config_hash,
                "generated_by": GENERATED_BY,
            }
        )

    return rows


def write_receipt(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.topojson.emit_receipt",
        description="Emit datasets/data/entities/boundary_encoding.csv from boundary TopoJSON shards.",
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root (default: auto-detected).")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="TopoJSON config path (default: config/topojson.json).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output CSV path (default: datasets/data/entities/boundary_encoding.csv).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Print progress to stderr every N TopoJSON shards; use 0 to disable.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    output_path = args.output if args.output.is_absolute() else root / args.output
    rows = build_rows(root, config_path, progress_every=args.progress_every)
    write_receipt(rows, output_path)
    print(json.dumps({"output": _repo_rel(output_path, root), "rows": len(rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())