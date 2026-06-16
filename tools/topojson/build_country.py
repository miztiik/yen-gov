"""Build the single combined COUNTRY topojson from the on-disk geojson masters.

Row 2 of TODO/20260616-map-geometry-rip-and-palette-plan.md. This is the ONLY
topojson the repo ships after the rip-and-replace (decision D1/D2): every other
boundary layer ships raw `.geojson`. The country file carries TWO named objects
in ONE topology so arcs are shared and the wire payload stays small:

    objects.states     - 36 state/UT polygons, join key `State_LGD` (int)
    objects.districts   - 785 district polygons, join key `dist_lgd` (int)

Decisions baked in (do NOT re-litigate - see plan section 0.2):
  - quantization=19000 (lossless integer rounding, NOT vertex deletion).
  - NO `-simplify` anywhere (decision D3): coastline vertices are preserved
    so the islands + coastlines render crisp.
  - A LEAN property set that PRESERVES the live join keys verbatim
    (`State_LGD` on states, `dist_lgd` on districts - decision D2 / Gregor G1):
    renaming these would blank every map because boundaries.ts JOIN_KEYS,
    IndiaPartyMap JOIN_PROPERTY, sources.ts INDIA_STATES and
    choropleth-entity-context INDIA_DISTRICTS all read the current names.
    STNAME / STNAME_SH are kept for display + the Lakshadweep island marker
    (Row 1 name-matches `/laksh/i` against STNAME).

Determinism: the mapshaper version is pinned in tools/topojson/.mapshaper-version
and the subprocess injects LC_ALL=C + LC_NUMERIC=C (same contract as
convert_layer.py). The command is passed as an explicit argv list (shell=False)
so comma-separated field lists are never mangled by a shell.

Usage:
    python -m tools.topojson.build_country
    python -m tools.topojson.build_country --output <path> [--quantization 19000]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_PIN_PATH = Path(__file__).resolve().parent / ".mapshaper-version"

STATES_GEOJSON = REPO_ROOT / "datasets" / "boundaries" / "in" / "states" / "all.geojson"
DISTRICTS_GEOJSON = REPO_ROOT / "datasets" / "boundaries" / "in" / "districts" / "all.geojson"
DEFAULT_OUTPUT = REPO_ROOT / "datasets" / "boundaries" / "in" / "country" / "all.topojson"

# Lean property allow-lists, per object. The FIRST field in each list is the
# load-bearing numeric join key and MUST be preserved verbatim.
STATES_FIELDS = "State_LGD,STNAME,STNAME_SH,STCODE11"
DISTRICTS_FIELDS = "dist_lgd,dtname,stname,state_lgd,dtcode11,census_code_2011"

DEFAULT_QUANTIZATION = 19000


def _resolve_mapshaper() -> list[str]:
    """Resolve the mapshaper invocation as a command-prefix list.

    Mirrors convert_layer.py: prefer the binary `bun install` drops under
    frontend/node_modules/.bin (the lockfile-pinned version), then bunx, then
    a direct `mapshaper` on PATH.
    """
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
    raise RuntimeError(
        "mapshaper not found - run `bun install` in frontend/ or install mapshaper globally"
    )


def build_country(
    output_path: Path = DEFAULT_OUTPUT,
    quantization: int = DEFAULT_QUANTIZATION,
) -> Path:
    """Build the combined country topojson. Returns the output path.

    Copies the two geojson masters into a temp dir under DISTINCT basenames
    (`states.geojson` / `districts.geojson`) so mapshaper's `combine-files`
    auto-names the layers `states` + `districts` (the source masters are both
    named `all.geojson`, which would collide into one layer otherwise).
    """
    if not STATES_GEOJSON.exists():
        raise FileNotFoundError(f"states master missing: {STATES_GEOJSON}")
    if not DISTRICTS_GEOJSON.exists():
        raise FileNotFoundError(f"districts master missing: {DISTRICTS_GEOJSON}")

    cmd_prefix = _resolve_mapshaper()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_states = Path(tmp) / "states.geojson"
        tmp_districts = Path(tmp) / "districts.geojson"
        shutil.copyfile(STATES_GEOJSON, tmp_states)
        shutil.copyfile(DISTRICTS_GEOJSON, tmp_districts)

        argv = [
            *cmd_prefix,
            "-i",
            str(tmp_states),
            str(tmp_districts),
            "combine-files",
            "-filter-fields",
            "target=states",
            STATES_FIELDS,
            "-filter-fields",
            "target=districts",
            DISTRICTS_FIELDS,
            # Reset the target to BOTH layers so the output topology carries
            # both objects (a trailing `target=` from -filter-fields would
            # otherwise emit only the last-targeted layer).
            "-target",
            "states,districts",
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
                "mapshaper exited "
                f"{proc.returncode}: stdout={proc.stdout!r} stderr={proc.stderr!r}"
            )

    _verify(output_path)
    return output_path


def _verify(output_path: Path) -> None:
    """Fail loudly if the output is malformed or the island regression returns.

    Mirrors the C2 contract test (Lakshadweep survival) so a bad rebuild is
    caught at build time, not just in CI.
    """
    topo = json.loads(output_path.read_text(encoding="utf-8"))
    objects = topo.get("objects", {})
    for name in ("states", "districts"):
        if name not in objects:
            raise RuntimeError(f"country topojson missing object {name!r}")
    states = objects["states"]["geometries"]
    districts = objects["districts"]["geometries"]
    if len(states) < 30:
        raise RuntimeError(f"states object has only {len(states)} features (expected ~36)")
    if len(districts) < 700:
        raise RuntimeError(f"districts object has only {len(districts)} features (expected ~785)")
    # Every state feature must carry an integer State_LGD; every district a
    # dist_lgd. Renaming/dropping these blanks every map (Gregor G1).
    for g in states:
        if not isinstance((g.get("properties") or {}).get("State_LGD"), int):
            raise RuntimeError("a states feature is missing an integer State_LGD")
    for g in districts:
        if not isinstance((g.get("properties") or {}).get("dist_lgd"), int):
            raise RuntimeError("a districts feature is missing an integer dist_lgd")
    # C2 (NON-NEGOTIABLE): Lakshadweep survives by name into BOTH objects.
    for name, geoms in (("states", states), ("districts", districts)):
        hit = any("laksh" in json.dumps(g.get("properties") or {}).lower() for g in geoms)
        if not hit:
            raise RuntimeError(f"C2 regression: Lakshadweep absent from {name!r} object")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the combined country topojson.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--quantization", type=int, default=DEFAULT_QUANTIZATION)
    args = parser.parse_args(argv)
    out = build_country(args.output, args.quantization)
    size_kb = out.stat().st_size / 1024
    print(f"[build_country] wrote {out} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
