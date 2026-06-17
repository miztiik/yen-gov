"""Consolidate the 31 per-state AC shards into ONE national 2024-vintage topojson.

Row 3 of TODO/20260616-map-geometry-rip-and-palette-plan.md (decision D6: AC
consolidates to ONE national `delim=2024` file). The AC layer ships as TopoJSON
(not raw geojson) per the Gregor + Jony ruling 2026-06-16: at full resolution
the 4149 AC polygons are 100.7 MB raw / 24.1 MB gz as geojson - too big to fetch
whole on a citizen hot path. As a quantization=100000 (~32m grid) arc-shared
topojson it is ~3.7 MB gz, fetched once then cached for every state view. This
relaxes D1 ("topojson for the country file only") to Gregor's bright-line:
TopoJSON is permitted IFF a layer is BOTH (a) a national composite we DERIVE
ourselves (not a byte-faithful passthrough) AND (b) fetched WHOLE on a citizen
hot path. The country file + this national AC file are the only two that qualify.
QUANTIZATION is lossless integer rounding (every vertex preserved), NOT the
vertex-deleting `-simplify` banned by D3 - so D3 is honoured intact.

The existing `delim=2008/ac/state=<slug>/all.geojson` shards are already fully
processed (lgd_ac_id where derived, AP/TG ac_no rewrite, J&K seat_id), so this
CONCATENATES them rather than re-ingesting from the ramSeraph archive (the
geometry is the single AC delimitation either way; the relabel unifies the
vintage label with the PC file). Every feature's ORIGINAL properties are
preserved verbatim so the per-state join contract (lgd_ac_id / ac_no / seat_id
per the STATE_AC registry) keeps working identically. Two properties are ADDED:

  - `state_ut_code`: the ECI state code (e.g. "S22") derived from the SHARD slug
    via datasets/data/entities/geo.csv. The uniform per-state filter key
    StateAcMapD3 uses after the national file replaces the per-state fetch.
  - `ac_name_slug`: kebab-case slug of the AC name (`ac_name`, or `seat_name_en`
    for J&K). Forward-looking dual-key for historical AC joins (plan section 0.3).

Determinism: subprocess injects LC_ALL=C + LC_NUMERIC=C (same contract as
build_country.py).

Usage:
    python -m tools.boundaries.consolidate_ac_2024
    python -m tools.boundaries.consolidate_ac_2024 --output <path> [--quantization 100000]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AC_2008_DIR = REPO_ROOT / "datasets/boundaries/electoral/delim=2008/ac"
DEFAULT_OUTPUT = REPO_ROOT / "datasets/boundaries/electoral/delim=2024/ac/all.topojson"
GEO_CSV = REPO_ROOT / "datasets/data/entities/geo.csv"
TOPOJSON_OBJECT = "ac"
DEFAULT_QUANTIZATION = 100000  # ~32m grid for India bbox; Jony ruling 2026-06-16

_ECI_RE = re.compile(r"^[SU]\d{2}$")


def slugify(value: str) -> str:
    """Kebab-case slug: lowercase, non-alphanumeric runs -> single hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def load_slug_to_eci(geo_csv: Path = GEO_CSV) -> dict[str, str]:
    """Map state/UT slug (geo.csv entity_id) -> ECI code (alias matching [SU]NN)."""
    out: dict[str, str] = {}
    with geo_csv.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("parent") != "IN" or row.get("entity_kind") not in {"state", "ut"}:
                continue
            entity_id = (row.get("entity_id") or "").strip()
            eci = next(
                (a for a in (row.get("aliases") or "").split("|") if _ECI_RE.match(a.strip())),
                "",
            )
            if entity_id and eci:
                out[entity_id] = eci.strip()
    return out


def _feature_name(props: dict) -> str:
    """AC display name across the 4 shard schemas (ac_name | seat_name_en)."""
    return str(props.get("ac_name") or props.get("seat_name_en") or "")


def _resolve_mapshaper() -> list[str]:
    """Resolve the mapshaper invocation (mirrors build_country.py)."""
    local_bin_dir = REPO_ROOT / "frontend" / "node_modules" / ".bin"
    for name in ("mapshaper.exe", "mapshaper.cmd", "mapshaper"):
        candidate = local_bin_dir / name
        if candidate.exists():
            return [str(candidate)]
    bunx = shutil.which("bunx") or shutil.which("bunx.exe")
    if bunx:
        return [bunx, "mapshaper"]
    direct = shutil.which("mapshaper") or shutil.which("mapshaper.cmd")
    if direct:
        return [direct]
    raise RuntimeError("mapshaper not found - run `bun install` in frontend/ or install mapshaper")


def _build_consolidated_geojson(tmp_geojson: Path) -> tuple[int, int]:
    """Concatenate + stamp the 31 shards into one geojson. Returns (features, states)."""
    slug_to_eci = load_slug_to_eci()
    shards = sorted(AC_2008_DIR.glob("state=*/all.geojson"))
    if not shards:
        raise FileNotFoundError(f"no AC shards under {AC_2008_DIR}")

    features: list[dict] = []
    seen_states: set[str] = set()
    for shard in shards:
        slug = shard.parent.name.split("state=", 1)[1]
        eci = slug_to_eci.get(slug)
        if not eci:
            raise ValueError(f"no ECI code for shard slug {slug!r} (check geo.csv)")
        fc = json.loads(shard.read_text(encoding="utf-8"))
        for feat in fc.get("features", []):
            props = dict(feat.get("properties") or {})
            props["state_ut_code"] = eci
            props["ac_name_slug"] = slugify(_feature_name(props))
            features.append(
                {"type": "Feature", "properties": props, "geometry": feat.get("geometry")}
            )
        seen_states.add(eci)

    tmp_geojson.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return len(features), len(seen_states)


def consolidate(
    output_path: Path = DEFAULT_OUTPUT,
    quantization: int = DEFAULT_QUANTIZATION,
) -> Path:
    cmd_prefix = _resolve_mapshaper()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_geojson = Path(tmp) / "ac_national.geojson"
        n_features, n_states = _build_consolidated_geojson(tmp_geojson)
        argv = [
            *cmd_prefix,
            "-i",
            str(tmp_geojson),
            "-rename-layers",
            TOPOJSON_OBJECT,
            "-o",
            "format=topojson",
            f"quantization={quantization}",
            str(output_path),
        ]
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LC_NUMERIC": "C"},
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"mapshaper exited {proc.returncode}: stdout={proc.stdout!r} stderr={proc.stderr!r}"
            )
    _verify(output_path, expected_features=n_features, expected_states=n_states)
    return output_path


def _verify(output_path: Path, expected_features: int, expected_states: int) -> None:
    topo = json.loads(output_path.read_text(encoding="utf-8"))
    if topo.get("type") != "Topology":
        raise RuntimeError("output is not a Topology")
    obj = (topo.get("objects") or {}).get(TOPOJSON_OBJECT)
    if obj is None:
        raise RuntimeError(f"topojson missing object {TOPOJSON_OBJECT!r}")
    geoms = obj.get("geometries") or []
    if len(geoms) != expected_features:
        raise RuntimeError(
            f"topojson has {len(geoms)} geometries, expected {expected_features}"
        )
    states = {g.get("properties", {}).get("state_ut_code") for g in geoms}
    states.discard(None)
    if len(states) != expected_states:
        raise RuntimeError(f"topojson covers {len(states)} states, expected {expected_states}")
    for g in geoms:
        if not g.get("properties", {}).get("state_ut_code"):
            raise RuntimeError("a geometry is missing state_ut_code")
        if "ac_name_slug" not in g.get("properties", {}):
            raise RuntimeError("a geometry is missing ac_name_slug")
    # J&K survival (its seat_name_en schema differs from the ac_name schema).
    if not any(g["properties"].get("state_ut_code") == "U08" for g in geoms):
        raise RuntimeError("J&K (U08) AC features absent from consolidated topojson")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consolidate per-state AC shards into one national topojson.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--quantization", type=int, default=DEFAULT_QUANTIZATION)
    args = parser.parse_args(argv)
    out = consolidate(args.output, args.quantization)
    topo = json.loads(out.read_text(encoding="utf-8"))
    geoms = topo["objects"][TOPOJSON_OBJECT]["geometries"]
    states = sorted({g["properties"]["state_ut_code"] for g in geoms})
    size_mb = out.stat().st_size / (1024 * 1024)
    print(
        f"[consolidate-ac] wrote {out} ({len(geoms)} features, {len(states)} states, {size_mb:.1f} MB)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
