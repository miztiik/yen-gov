"""Boundary snapshot — download raw GeoJSONs into datasets/ for in-repo serving.

Why this exists alongside build.py
==================================

build.py produces PMTiles (CC-licensed vector tiles) but requires `mapshaper`
and `tippecanoe` on PATH. Those aren't available on Windows out of the box,
and the frontend currently runs entirely off the GeoJSON fallback path
(see frontend/src/lib/maplibre/sources.ts > resolveSource).

When that fallback fetches across the public internet from
raw.githubusercontent.com on every page load, the maps appear blank for
several seconds (or fail behind restrictive networks). That's a UX
regression for what is supposed to be a static site.

This script snapshots the same upstreams listed in pipeline.json into
`datasets/boundaries/in/geojson/` with a `<file>.sources.json` sidecar
declaring CLAUDE.md §12 provenance. The frontend prefers these local copies
and only falls back to the upstream URL when the local copy is missing.

Why a sidecar instead of a top-level `sources` field on the GeoJSON itself
========================================================================

The GeoJSON spec (RFC 7946 §7.1) reserves all top-level members and
recommends consumers ignore unknown ones. Tooling (maplibre, mapshaper,
tippecanoe) all tolerate extra keys, but stuffing provenance into the
artifact muddles the format. A sibling `*.sources.json` keeps each file
type to its native shape and still satisfies the §12 contract — every data
file under datasets/ ships with its provenance.

Re-running the script
=====================

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


def utc_now() -> str:
    """RFC 3339 UTC timestamp; matches CLAUDE.md §12 fetched_at convention."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Size-budget guard. The unsimplified India states GeoJSON from GADM is
# ~22 MB (one of the largest single artifacts we'd commit). PMTiles compresses
# this >10x, but until tools/boundaries/build.py runs, the country layer
# stays on the existing live-fetch fallback (which works fine — it's only
# the home page India map). Per-state AC GeoJSONs are 400KB–1MB each: well
# under the threshold and worth committing for instant load.
SNAPSHOT_BYTE_BUDGET = 4 * 1024 * 1024  # 4 MB per file


def snapshot_one(entry: dict[str, Any], out_root: Path) -> dict[str, Any] | None:
    """Snapshot one pipeline.json entry. Returns the manifest record, or None
    if the entry is intentionally skipped (e.g. exceeds the size budget)."""
    url: str = entry["url"]
    kind: str = entry["kind"]
    state: str | None = entry.get("state")

    # Output naming mirrors the BoundaryEntry.id convention used in
    # frontend/src/lib/maplibre/sources.ts: "india-states" or "<state>-ac".
    if kind == "states":
        basename = "india-states.geojson"
    elif kind == "ac" and state:
        basename = f"{state}-ac.geojson"
    else:  # pragma: no cover — guard against pipeline.json edits
        msg = f"unknown entry shape: kind={kind} state={state}"
        raise ValueError(msg)

    out_path = out_root / basename
    sidecar_path = out_path.with_suffix(out_path.suffix + ".sources.json")
    label = f"{kind}:{state}" if state else kind

    print(f"[{label}] {url}", flush=True)
    fetched_at = utc_now()

    # Probe size before committing the download to disk. urllib.request gives
    # us Content-Length on a streamed GET; we honour it and bail before
    # writing when the budget is exceeded.
    req = urllib.request.Request(url, headers={"User-Agent": "yen-gov-boundaries/1.0"})
    with urllib.request.urlopen(req) as r:  # noqa: S310 — public CC0/MIT data
        cl_header = r.headers.get("Content-Length")
        size = int(cl_header) if cl_header and cl_header.isdigit() else None
        if size is not None and size > SNAPSHOT_BYTE_BUDGET:
            print(
                f"  SKIP — {size / 1024 / 1024:.1f} MB exceeds "
                f"{SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget; "
                "frontend will use the live-fetch fallback for this layer.",
                flush=True,
            )
            return None
        # Within budget — stream to disk via .part-rename so partial
        # downloads don't masquerade as complete artifacts on retry.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(out_path.suffix + ".part")
        with tmp.open("wb") as fh:
            shutil.copyfileobj(r, fh)
        tmp.replace(out_path)

    # Sidecar: minimal CLAUDE.md §12 envelope. We deliberately don't echo
    # the license here — that lives in pipeline.json and the boundary
    # manifest. Sidecar is provenance only. Validated against
    # datasets/schemas/boundary.sources.schema.json by the Tier-B validator.
    sidecar = {
        "$schema": "https://yen-gov.github.io/schemas/boundary.sources.schema.json",
        "$schema_version": "1.0",
        "$comment": (
            "CLAUDE.md §12 provenance sidecar for the GeoJSON of the same name. "
            "GeoJSON has no native top-level metadata slot; this file carries the "
            "required `sources` array on its behalf."
        ),
        "for": basename,
        "sources": [{"url": url, "fetched_at": fetched_at}],
    }
    with sidecar_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(sidecar, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    record: dict[str, Any] = {
        "id": basename.removesuffix(".geojson"),
        "path": f"boundaries/in/geojson/{basename}",
        "kind": kind,
        "size_bytes": out_path.stat().st_size,
        "fetched_at": fetched_at,
    }
    if state:
        record["state"] = state
    return record


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
    out_root.mkdir(parents=True, exist_ok=True)

    records = [r for r in (snapshot_one(e, out_root) for e in cfg["inputs"]) if r is not None]

    print(f"\nsnapshotted {len(records)} files into {out_root.relative_to(root)}/")
    for r in records:
        size_kb = r["size_bytes"] / 1024
        print(f"  {r['path']:<48s} {size_kb:>8.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
