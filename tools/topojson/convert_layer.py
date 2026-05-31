"""GeoJSON to TopoJSON converter (P2.1).

Wraps the Mapshaper CLI as a deterministic, idempotent subprocess.
Designed so a single Phase 1 (states) run AND the cascade Track A/A2
runs (P3.x, P4.x) share one entry point.

Usage:
    python -m tools.topojson.convert_layer \
      --input datasets/boundaries/in/states/all.geojson \
      --output datasets/boundaries/in/states/all.topojson \
      --layer states \
      [--config config/topojson.json]

Determinism:
    - Mapshaper version pinned in tools/topojson/.mapshaper-version.
    - Subprocess env injects LC_ALL=C + LC_NUMERIC=C.
    - Idempotency sidecar: <output>.topojson.meta.json keyed by
      sha256(input) + mapshaper_version + quantization + simplification
      + clean flag. Re-run with unchanged inputs is a no-op.
    - -clean flag is OPT-IN per layer via config; default OFF.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_PIN_PATH = Path(__file__).resolve().parent / ".mapshaper-version"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "topojson.json"


def _read_pinned_version() -> str:
    return VERSION_PIN_PATH.read_text(encoding="utf-8").strip()


def _resolve_mapshaper() -> list[str]:
    """Resolve the mapshaper invocation as a command-prefix list.

    Prefers the binary that `bun install` drops under
    `frontend/node_modules/.bin/` (this is the project's version
    contract via `frontend/bun.lock`). Falls back to `bunx mapshaper`
    (resolves the same binary when CWD has access to the lockfile) and
    finally a direct `mapshaper` on PATH for environments where neither
    is available (minimal CI containers). The shell=False subprocess
    pattern avoids PowerShell quoting traps.
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
        "mapshaper not found. Install via `cd frontend && bun install`; "
        "see tools/topojson/README.md."
    )


def _detect_version(cmd_prefix: list[str]) -> str:
    proc = subprocess.run(
        [*cmd_prefix, "--version"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LC_NUMERIC": "C"},
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"mapshaper --version failed: stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    return proc.stdout.strip() or proc.stderr.strip()


def _load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _layer_settings(config: dict[str, Any], layer: str) -> dict[str, Any]:
    per_layer = (config.get("per_layer") or {}).get(layer, {})
    return {
        "quantization": int(per_layer.get("quantization", config["default_quantization"])),
        "simplification": str(per_layer.get("simplification", config["simplification"])),
        "clean": bool(per_layer.get("clean", False)),
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _idempotency_key(
    input_path: Path,
    mapshaper_version: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "input_sha256": _sha256_file(input_path),
        "mapshaper_version": mapshaper_version,
        "quantization": settings["quantization"],
        "simplification": settings["simplification"],
        "clean": settings["clean"],
    }


def _sidecar_path(output_path: Path) -> Path:
    # <output>.topojson.meta.json sits next to the output. Naming keeps
    # both files visible under the same Hive partition listing.
    return output_path.with_suffix(output_path.suffix + ".meta.json")


def _sidecar_matches(sidecar_path: Path, key: dict[str, Any]) -> bool:
    if not sidecar_path.exists():
        return False
    try:
        recorded = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return all(recorded.get(k) == v for k, v in key.items())


def _run_mapshaper(
    cmd_prefix: list[str],
    input_path: Path,
    output_path: Path,
    layer: str,
    settings: dict[str, Any],
) -> None:
    # Mapshaper auto-derives the topojson object name from the input
    # filename ("all.geojson" -> "all"). `-rename-layers` forces the
    # name to the supplied --layer so the frontend's
    # `topojson.feature(t, t.objects.<layer>)` call is stable.
    cmd: list[str] = [
        *cmd_prefix,
        str(input_path),
        "-rename-layers",
        layer,
    ]
    if settings["clean"]:
        cmd.append("-clean")
    # Mapshaper -simplify expects each token as a separate argv element
    # (e.g. `-simplify 5% weighted`), not one whitespace-glued string.
    cmd.append("-simplify")
    cmd.extend(shlex.split(settings["simplification"]))
    cmd.extend(
        [
            "-o",
            f"format=topojson",
            f"quantization={settings['quantization']}",
            str(output_path),
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LC_NUMERIC": "C"},
    )
    if proc.returncode != 0:
        # Surface mapshaper's stderr verbatim - the caller needs to see
        # the original diagnostic, not an opaque wrapper error.
        raise RuntimeError(
            "mapshaper exited "
            f"{proc.returncode}: stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )


def convert(
    input_path: Path,
    output_path: Path,
    layer: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    """Convert one GeoJSON file to TopoJSON.

    Returns the idempotency key dict written to the sidecar. Re-runs
    with matching sidecar short-circuit (no mapshaper invocation, no
    output rewrite).
    """
    if not input_path.exists():
        raise FileNotFoundError(f"input GeoJSON not found: {input_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"converter config not found: {config_path}")

    pinned_version = _read_pinned_version()
    cmd_prefix = _resolve_mapshaper()
    detected_version = _detect_version(cmd_prefix)
    if detected_version != pinned_version:
        raise RuntimeError(
            f"mapshaper version mismatch: pinned={pinned_version!r} "
            f"detected={detected_version!r}. Re-run "
            "`cd frontend && bun install` to align, or bump "
            "tools/topojson/.mapshaper-version intentionally."
        )

    config = _load_config(config_path)
    settings = _layer_settings(config, layer)
    key = _idempotency_key(input_path, pinned_version, settings)
    sidecar_path = _sidecar_path(output_path)

    if output_path.exists() and _sidecar_matches(sidecar_path, key):
        return key

    _run_mapshaper(cmd_prefix, input_path, output_path, layer, settings)

    sidecar_path.write_text(
        json.dumps(key, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.topojson.convert_layer",
        description="Convert one GeoJSON file to TopoJSON via mapshaper.",
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--layer",
        required=True,
        help="TopoJSON object name to wrap the FeatureCollection (e.g. 'states').",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to topojson.json config (default: config/topojson.json).",
    )
    args = parser.parse_args(argv)
    key = convert(args.input, args.output, args.layer, args.config)
    print(json.dumps(key, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
