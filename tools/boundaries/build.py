"""Boundary pipeline — download → simplify → pack to PMTiles.

Self-contained per CLAUDE.md §4 (`tools/` MUST NOT import from `backend/`).
Reads `tools/boundaries/pipeline.json`, fetches each upstream URL into
`.runtime/raw/boundaries/` (per ADR-0003: intermediate artifacts never live in
`datasets/`), simplifies with mapshaper, and packs to PMTiles with tippecanoe.
Emits a single manifest at `datasets/boundaries/in/manifest.json` declaring
provenance for every output file (CLAUDE.md §12).

External tools required (install on a Linux/macOS shell or WSL2; this tool is
local-only by design — see tools/boundaries/README.md):

- mapshaper      (npm install -g mapshaper)
- tippecanoe     (built from felt/tippecanoe)

Why a Python orchestrator and not a shell script:
- The mapping from upstream URL to output path lives in pipeline.json. Python
  reads it as data; the shell would smear it across env vars.
- Manifest authoring (provenance per CLAUDE.md §12) is JSON munging — Python's
  natural turf.

Why one PMTiles per (state, kind) and not one for the whole country:
- Per-state ACs let the frontend lazy-load only the visible state's geometry.
- Bundle the country-level states layer once for the India landing map.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """RFC 3339 UTC timestamp; matches CLAUDE.md §12 fetched_at convention."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def download(url: str, dest: Path) -> None:
    """Stream a URL to disk. Atomic via .part rename so partial downloads don't
    masquerade as complete artifacts on retry."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "yen-gov-boundaries/1.0"})
    with urllib.request.urlopen(req) as r, tmp.open("wb") as fh:  # noqa: S310 — public CC0/MIT data
        shutil.copyfileobj(r, fh)
    tmp.replace(dest)


def run(cmd: list[str], **kwargs: Any) -> None:
    """Subprocess wrapper that fails loudly. No `check=False` shortcut — every
    tool in this pipeline is mandatory; a silent failure invalidates the
    manifest."""
    print(f"  $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def feature_count(geojson_path: Path) -> int:
    with geojson_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    feats = data.get("features", [])
    return len(feats) if isinstance(feats, list) else 0


def build_one(
    entry: dict[str, Any],
    raw_root: Path,
    out_root: Path,
    simplify: dict[str, Any],
) -> dict[str, Any]:
    """Process one pipeline.json entry. Returns its manifest record."""
    url: str = entry["url"]
    kind: str = entry["kind"]
    out_rel: str = entry["out"]
    state = entry.get("state")
    label = f"{kind}:{state}" if state else kind

    # Stable raw path keeps re-runs cheap when CI caches .runtime/.
    raw_basename = url.rsplit("/", 1)[-1]
    raw_path = raw_root / kind / (state or "global") / raw_basename
    out_path = out_root / out_rel

    print(f"\n[{label}] {url}", flush=True)
    print(f"  download → {raw_path.relative_to(Path.cwd())}", flush=True)
    fetched_at = utc_now()
    download(url, raw_path)

    # Simplify with mapshaper. Output is a temporary GeoJSON we then feed to
    # tippecanoe. Skipping simplification on small inputs is a false economy:
    # the AC GeoJSONs are 400KB–1MB unsimplified and would inflate PMTiles
    # disproportionately at low zooms.
    simplified = raw_path.with_suffix(".simplified.geojson")
    pct = simplify["percent"]
    method = simplify.get("method", "visvalingam")
    method_flags = method.split()  # e.g. "visvalingam weighted" → ["visvalingam","weighted"]
    run([
        "mapshaper",
        str(raw_path),
        "-simplify",
        f"{pct * 100:g}%",
        *method_flags,
        "keep-shapes",
        "-o",
        "format=geojson",
        str(simplified),
    ])

    # Pack to PMTiles via tippecanoe.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tip = entry.get("tippecanoe", {})
    tippe_cmd = [
        "tippecanoe",
        "-o", str(out_path),
        "--force",
        "-l", tip.get("layer", kind),
        "-Z", str(tip.get("minzoom", 0)),
        "-z", str(tip.get("maxzoom", 10)),
    ]
    if tip.get("drop_densest_as_needed"):
        tippe_cmd.append("--drop-densest-as-needed")
    tippe_cmd.append(str(simplified))
    run(tippe_cmd)

    record: dict[str, Any] = {
        "path": out_rel.replace("\\", "/"),  # POSIX, per CLAUDE.md §2
        "kind": kind,
        "country": entry.get("country", "IN"),
        "feature_count": feature_count(simplified),
        "size_bytes": out_path.stat().st_size,
        "license": entry["license"],
        "license_url": entry["license_url"],
        "sources": [{"url": url, "fetched_at": fetched_at}],
    }
    if state:
        record["state"] = state
    for opt in ("ac_no_property", "name_property", "id_property", "delimitation_warning"):
        if opt in entry:
            record[opt] = entry[opt]
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build boundary PMTiles + manifest.")
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

    out_root = root / cfg["outputs_dir"]
    raw_root = root / cfg["raw_dir"]
    out_root.mkdir(parents=True, exist_ok=True)

    # Verify external tools are on PATH before downloading anything.
    for tool in ("mapshaper", "tippecanoe"):
        if shutil.which(tool) is None:
            print(f"required tool not found on PATH: {tool}", file=sys.stderr)
            return 3

    records: list[dict[str, Any]] = []
    for entry in cfg["inputs"]:
        records.append(build_one(entry, raw_root, out_root, cfg["simplify"]))

    manifest = {
        "$comment": (
            "Provenance manifest for datasets/boundaries/in/. PMTiles files cannot "
            "embed a 'sources' field, so this sidecar carries the standard CLAUDE.md "
            "§12 provenance contract on their behalf, one entry per packed file."
        ),
        "generated_at": utc_now(),
        "files": records,
    }
    manifest_path = out_root / "manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nwrote manifest: {manifest_path.relative_to(root)} ({len(records)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
