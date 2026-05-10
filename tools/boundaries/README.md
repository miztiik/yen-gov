# tools/boundaries

**Last Updated**: 2026-05-09

Builds vector-tile boundary files (`datasets/boundaries/in/*.pmtiles`) consumed by the frontend [map](../../docs/architecture/frontend/map.md). The pipeline downloads upstream GeoJSON, simplifies with [mapshaper](https://github.com/mbloch/mapshaper), and packs to [PMTiles](https://github.com/protomaps/PMTiles) with [tippecanoe](https://github.com/felt/tippecanoe).

This tool is **local-only** by design (see [Why local-only](#why-local-only)). Run it from a Linux/macOS shell (or WSL2 on Windows) when boundaries need refreshing — typically once per delimitation cycle — then commit the regenerated `datasets/boundaries/in/` through a normal PR.

## Layout

| File | Role |
| --- | --- |
| [pipeline.json](pipeline.json) | Declarative list of upstream URLs, output paths, simplification + tippecanoe options per file. Edit this to add states or change sources. |
| [build.py](build.py) | Orchestrator. Self-contained (stdlib only). Reads `pipeline.json`, downloads, simplifies, packs, writes manifest. |

## Outputs

```
datasets/boundaries/in/
├── india-states.pmtiles            ← India state outlines (z 0–6)
├── ac/
│   ├── S22-ac.pmtiles              ← Tamil Nadu AC boundaries (z 4–10)
│   ├── S11-ac.pmtiles              ← Kerala
│   ├── S25-ac.pmtiles              ← West Bengal
│   └── S03-ac.pmtiles              ← Assam (see warning below)
└── manifest.json                   ← provenance + metadata for every file
```

`manifest.json` is the CLAUDE.md §12 provenance carrier: PMTiles files cannot embed a `sources` field, so the manifest carries one record per packed file with `{ url, fetched_at }`, plus the source license and the property name (e.g. `AC_NO`) the frontend joins on.

## Sources

| State | Source | License | Notes |
| --- | --- | --- | --- |
| TN (S22) | [HindustanTimesLabs/shapefiles](https://github.com/HindustanTimesLabs/shapefiles) `state_ut/tamilnadu/assembly/tamilnadu_AC.json` | MIT | `AC_NO` 1–234 |
| KL (S11) | same repo, `state_ut/kerala/assembly/kerala_AC.json` | MIT | `AC_NO` 1–140 |
| WB (S25) | same repo, `state_ut/westbengal/assembly/westbengal_AC.json` | MIT | `AC_NO` 1–294 |
| AS (S03) | same repo, `state_ut/assam/assembly/assam_AC.json` | MIT | ⚠️ may not match post-2008 delimitation; verify (see below) |
| India states | [datameet/maps](https://github.com/datameet/maps) `States/Admin2.{shp,dbf,shx,prj,cpg}` | CC-BY 4.0 | 36 features; joins on `ST_NM`. Includes the post-2014 Telangana split, post-2019 Ladakh split (PR #73), and merged DNH-DD UT. Replaces the GADM v2 layer that pre-dated all three reorganizations. |

For the full catalogue — including alternatives evaluated (yashveeeeeeer/india-geodata, datta07/INDIAN-SHAPEFILES, datameet's national `India_AC.shp`), what "LGD release" means, and the bar a new boundary source has to clear before being added — see [`docs/reference/boundary-data-sources.md`](../../docs/reference/boundary-data-sources.md).

### ⚠️ Assam delimitation caveat

The Assam AC shapefile may predate the 2008 Delimitation Order's revisions. Before the boundaries workflow PR is merged, cross-check that every `AC_NO` 1..126 in the simplified GeoJSON matches a constituency under [`datasets/reference/in/states/S03/constituencies.json`](../../datasets/reference/in/states/S03/constituencies.json) (compare names too, not just counts — a renumbering would pass a count check but produce a wrong-color map). If they don't match, hold the merge and source a 2026-current shapefile.

## Source format dispatch

Each `inputs[]` entry in [pipeline.json](pipeline.json) carries a `source` block:

```json
"source": {
  "format": "geojson" | "shp_bundle",
  "urls":   [ "...", ... ],
  "coord_precision": 3
}
```

| `format` | What `urls` contains | Conversion in `snapshot.py` / `build.py` |
| --- | --- | --- |
| `geojson` | Single-element list with the `.geojson` URL | Streamed verbatim. |
| `shp_bundle` | Every sibling shapefile component (`.shp`, `.dbf`, `.shx`, `.prj`, `.cpg`) | Downloaded into `.runtime/raw/boundaries/`, then converted to GeoJSON via [pyshp](https://pypi.org/project/pyshp/). `coord_precision` rounds coordinates (3 decimals ≈ 110 m) and drops consecutive duplicate vertices, which is enough for state-level choropleth rendering at z≤6. |

This split exists so adding a future format (zip+geojson, GeoPackage, GeoParquet) is a new `format` value plus a new branch in `materialize_input()` / `fetch_*` — not a rewrite of existing entries. The frontend resolver and the sidecar schema are format-agnostic.

For `format: shp_bundle`, install pyshp once: `pip install pyshp`.

## Running

### In CI (preferred)

GitHub → Actions → **boundaries** → *Run workflow*. The workflow builds, commits to `boundaries/refresh-<run-id>`, and opens a PR. Review the manifest diff and the PMTiles file sizes before merging.

### Locally (Linux/macOS or WSL)

```bash
# one-time
sudo apt-get install -y build-essential libsqlite3-dev zlib1g-dev nodejs npm
sudo npm install -g mapshaper
git clone --depth 1 https://github.com/felt/tippecanoe /tmp/tippecanoe
cd /tmp/tippecanoe && make -j && sudo make install

# every run
cd <repo-root>
python tools/boundaries/build.py
```

Native Windows is not supported (tippecanoe has no maintained Windows build). Use WSL2.

## Why local-only

- **Tippecanoe needs Linux/macOS.** Asking every contributor to install build-essential + sqlite-dev + node + mapshaper would be bad ergonomics, but boundaries change once per delimitation cycle — the maintainer who's actually refreshing them sets up the toolchain once and commits the output. CI dispatch for a years-cadence operation is unnecessary overhead.
- **The output is small enough to commit.** A few hundred kB per file × handful of files ≈ <2 MB total. No LFS, no submodule.
- **Reproducibility comes from pinning, not the runner.** `pipeline.json` pins mapshaper / tippecanoe options; `manifest.json` records `size_bytes` so PR diffs surface unintended drift.

## See also

- [Frontend map architecture](../../docs/architecture/frontend/map.md)
- CLAUDE.md §3 (datasets is a contract surface), §4 (tools self-contained), §12 (provenance)
- [ADR-0003: no fetch cache](../../docs/architecture/decisions/0003-no-fetch-cache.md) — why raw downloads land under `.runtime/raw/`, not under `datasets/`
