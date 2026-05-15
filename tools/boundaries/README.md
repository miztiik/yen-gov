# tools/boundaries

**Last Updated**: 2026-05-15

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
| India districts | [ramSeraph/indian_admin_boundaries](https://github.com/ramSeraph/indian_admin_boundaries) `LGD_Districts.geojsonl.7z` | CC0-1.0 (datameet attribution requested) | 785 features; joins on `dist_lgd` (LGD numeric district code). `coord_precision: 2` (≈1.1 km) keeps the file under the 12 MB snapshot budget. |

For the full catalogue — including alternatives evaluated (yashveeeeeeer/india-geodata, datta07/INDIAN-SHAPEFILES, datameet's national `India_AC.shp`), what "LGD release" means, and the bar a new boundary source has to clear before being added — see [`docs/reference/boundary-data-sources.md`](../../docs/reference/boundary-data-sources.md).

### ⚠️ Assam delimitation caveat

The Assam AC shapefile may predate the 2008 Delimitation Order's revisions. Before the boundaries workflow PR is merged, cross-check that every `AC_NO` 1..126 in the simplified GeoJSON matches a constituency under [`datasets/reference/in/states/S03/constituencies.json`](../../datasets/reference/in/states/S03/constituencies.json) (compare names too, not just counts — a renumbering would pass a count check but produce a wrong-color map). If they don't match, hold the merge and source a 2026-current shapefile.

## Source format dispatch

Each `inputs[]` entry in [pipeline.json](pipeline.json) carries a `source` block:

```json
"source": {
  "format": "geojson" | "shp_bundle" | "geojsonl_7z",
  "urls":   [ "...", ... ],
  "coord_precision": 3
}
```

| `format` | What `urls` contains | Conversion in `snapshot.py` / `build.py` |
| --- | --- | --- |
| `geojson` | Single-element list with the `.geojson` URL | Streamed verbatim. |
| `shp_bundle` | Every sibling shapefile component (`.shp`, `.dbf`, `.shx`, `.prj`, `.cpg`) | Downloaded into `.runtime/raw/boundaries/`, then converted to GeoJSON via [pyshp](https://pypi.org/project/pyshp/). `coord_precision` rounds coordinates (3 decimals ≈ 110 m) and drops consecutive duplicate vertices, which is enough for state-level choropleth rendering at z≤6. |
| `geojsonl_7z` | Single URL to a `.geojsonl.7z` archive (newline-delimited GeoJSON inside a 7z) | Downloaded into `.runtime/raw/boundaries/`, extracted with [py7zr](https://pypi.org/project/py7zr/), parsed line-by-line, wrapped as `FeatureCollection`. Same `coord_precision` knob as `shp_bundle`. Used by ramSeraph releases (BharatMaps/LGD lineage). |

This split exists so adding a future format (zip+geojson, GeoPackage, GeoParquet) is a new `format` value plus a new branch in `snapshot.py` `fetch_*` — not a rewrite of existing entries. The frontend resolver and the sidecar schema are format-agnostic.

For `format: shp_bundle`, install pyshp once: `pip install pyshp`. For `format: geojsonl_7z`, install py7zr once: `pip install py7zr`.

## Optional `source.*` keys (additive — opt-in)

Three `source` keys are optional opt-ins added during the TN granular-geo expansion ([TODO/TN-GRANULAR-GEO-PLAN.md](../../TODO/TN-GRANULAR-GEO-PLAN.md) Phase 1b). **Entries that omit them behave identically to pre-v5 `snapshot.py`** — these blocks are additive and only activate when present.

| Key | Shape | Effect |
| --- | --- | --- |
| `state_filter` | `{ "property": "state_lgd", "equals": "33" }` | Scope filter: features whose property doesn't match are silently dropped (they belong in another state's file, not in an LGD-join failure log). The post-filter count becomes the unkeyed-sidecar denominator. |
| `split_by` | `{ "property": "dist_lgd", "emit_index": "S22-villages-index.json" }` | Shards the FeatureCollection by the named property and writes one GeoJSON per group. The `{prop}` placeholder in `derive_output_basename` is substituted with the group key (e.g. `S22-villages-568.geojson`). When `emit_index` is set, an index manifest of present group keys is written next to the shards so the frontend loader can avoid 404-probing. |
| `metadata` (entry-level, not under `source`) | `{ title, description, category, license, coverage, coordinate_system }` | When present *and* `coord_precision` is set, a `<basename>.metadata.json` sibling is written conforming to [`feature_collection.metadata.schema.json`](../../datasets/schemas/feature_collection.metadata.schema.json) v1.2 with a `simplification` block (`algorithm: "coord-precision-round"`, `tolerance_deg = 10**-coord_precision`, original/retained feature counts). Surfaces simplification so downstream area/length math doesn't silently lie. |

A `<basename>.unkeyed.json` sidecar conforming to [`boundary.unkeyed.schema.json`](../../datasets/schemas/boundary.unkeyed.schema.json) is always emitted for `geojsonl_7z` entries — even when `dropped` is empty (the canonical "perfect snapshot" signal, written explicitly so consumers never have to distinguish "no drops" from "no sidecar").

### CLI filters

`snapshot.py` accepts repeatable `--kind` and `--state` filters so you can re-snapshot a single source without churning every other entry's `fetched_at`:

```bash
python tools/boundaries/snapshot.py --kind subdistricts --state S22
python tools/boundaries/snapshot.py --kind villages --state S22
```

Both flags are repeatable; an entry must match every supplied filter dimension to run.

## `inputs` vs `staged_inputs`

[pipeline.json](pipeline.json) has two top-level arrays:

- **`inputs`** — what the build runs today. Every entry produces a sibling GeoJSON + sidecar in `datasets/boundaries/in/` and a PMTiles file when `build.py` runs.
- **`staged_inputs`** — catalogued gap-fill entries that are **inert**. `snapshot.py` and `build.py` only iterate `inputs`, so these neither fetch nor build. They exist so the entry is concrete (URL pinned, license recorded, join-key documented) and ready to drop into `inputs` in the same PR as the consuming feature.

The gap-fill-only adoption rule (do not bulk-swap third-party catalogues for sources we already have working) is documented in [`docs/reference/boundary-data-sources.md`](../../docs/reference/boundary-data-sources.md#source-selection-policy-gap-fill-not-bulk-swap).

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
