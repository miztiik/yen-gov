# tools/boundaries

**Last Updated**: 2026-06-14

Builds the boundary tree at `datasets/boundaries/in/` consumed by the frontend [map](../../docs/architecture/frontend/map.md), plus the parquet ledger at `datasets/boundaries/boundary_layers.parquet` that carries provenance + simplification metadata + dropped-feature counts (T.0d, 2026-05-22 — see [ADR-0031 Amendment](../../docs/architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy)). The pipeline downloads upstream GeoJSON / SHP / 7z-archived GeoJSONL, simplifies via `coord_precision` rounding (and for PMTiles outputs, [mapshaper](https://github.com/mbloch/mapshaper) + [tippecanoe](https://github.com/felt/tippecanoe)), and emits to Hive-partitioned paths.

This tool is **local-only** by design (see [Why local-only](#why-local-only)). Run it from a Linux/macOS shell (or WSL2 on Windows) when boundaries need refreshing — typically once per delimitation cycle — then commit the regenerated `datasets/boundaries/in/` (and the regenerated `boundary_layers.parquet`) through a normal PR.

## Layout

| File | Role |
| --- | --- |
| [pipeline.json](pipeline.json) | Declarative list of upstream URLs, output paths, simplification + tippecanoe options per file. Edit this to add states or change sources. |
| [build.py](build.py) | Orchestrator. Self-contained (stdlib only). Reads `pipeline.json`, downloads, simplifies, packs, writes manifest. |
| [generate_frontend_registry.py](generate_frontend_registry.py) | Generates `frontend/src/lib/boundaries/generated-sources.ts` from `datasets/data/entities/boundary_encoding.csv` for high-cardinality panchayat and ward registries. Run with `--check` to verify freshness. |

## Outputs

```
datasets/boundaries/
├── boundary_layers.parquet                     # one row per shard (T.0d ledger)
└── in/
    ├── country/all.geojson                     # IN outline
    ├── states/all.geojson                      # 36 states/UTs
    ├── districts/all.geojson                   # all districts
    ├── subdistricts/state=in_<lc>/all.geojson  # per-state
    ├── villages/state=in_<lc>/district=<lgd>/all.geojson  # per-(state, district)
    ├── ../electoral/delim=<year>/ac/state=<slug>/all.geojson  # per-state AC layer (31 states/UTs)
    └── postal/IN-pincodes-<city>.geojson       # orthogonal; NOT LGD
```

`datasets/boundaries/boundary_layers.parquet` is the CLAUDE.md §12 provenance carrier post-T.0d: PMTiles files cannot embed a `sources` field and per-shard sidecars are retired, so the ledger carries one row per shard with `source_id` (FK to `datasets/taxonomy/sources.parquet`), denominator (`original_feature_count == retained_feature_count + unkeyed_count`), simplification metadata, CRS, and the property name (e.g. `AC_NO`) the frontend joins on (via `notes` or future structured field).

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

The Assam AC shapefile may predate the 2008 Delimitation Order's revisions. Before the boundaries workflow PR is merged, cross-check that every `AC_NO` 1..126 in the simplified GeoJSON matches a constituency under [`datasets/data/entities/boundaries_sot/S03/constituencies.json`](../../datasets/data/entities/boundaries_sot/S03/constituencies.json) (compare names too, not just counts — a renumbering would pass a count check but produce a wrong-color map). If they don't match, hold the merge and source a 2026-current shapefile.

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
| `state_filter` | `{ "property": "state_lgd", "equals": "33" }` | Scope filter: features whose property doesn't match are silently dropped (they belong in another state's file, not in an LGD-join failure log). The post-filter count becomes the unkeyed-count denominator on the ledger row. |
| `split_by` | `{ "property": "dist_lgd" }` | Shards the FeatureCollection by the named property and writes one GeoJSON per group into the matching Hive partition (e.g. `villages/state=tamil-nadu/district=<dist_lgd>/all.geojson`). On-disk presence is self-describing under Hive partitioning, so no `emit_index` manifest is written (retired in T.0d). |
| `metadata` (entry-level, not under `source`) | `{ title, description, category, license, coverage, coordinate_system }` | Folded into the row written to `datasets/boundaries/boundary_layers.parquet`. `coord_precision` populates `simplification_tolerance` (= `10**-coord_precision`) + `simplification_algorithm = "coord-round"`. Surfaces simplification so downstream area/length math doesn't silently lie. |

Unkeyed counts (features dropped because they didn't join to the LGD registry) and source provenance (FK to `datasets/taxonomy/sources.parquet`) are written to the matching row in `boundary_layers.parquet`. The pre-T.0d per-shard sidecars (`*.sources.json` / `*.metadata.json` / `*.unkeyed.json`) are retired — a Tier-B forbidden-path gate (`tier_b_legacy_boundary_sidecars`) rejects them.

### CLI filters

`snapshot.py` accepts repeatable `--kind` and `--state` filters so you can re-snapshot a single source without churning every other entry's `fetched_at`:

```bash
python tools/boundaries/snapshot.py --kind subdistricts --state S22
python tools/boundaries/snapshot.py --kind villages --state S22
```

Both flags are repeatable; an entry must match every supplied filter dimension to run.

### Shared cache across worktrees

`snapshot.py` and every `lift_*.py` script default the upstream-cache root to `<repo>/.runtime/raw/boundaries/`. This is per-worktree by default, which means a fresh `git worktree add ...` starts cold and re-downloads multi-GB LGD bundles (`LGD_Villages.geojsonl.7z` is ~1.8 GB; `LGD_Districts` ~82 MB; `LGD_Subdistricts` ~57 MB). To point every worktree at one shared on-disk cache, use either tier:

```bash
# CLI flag (per-invocation; absolute or relative-to-cwd):
python tools/boundaries/snapshot.py --kind ac --state S05 --raw-dir D:/caches/yen-gov-boundaries

# Env-var (set once; every snapshot.py / lift_*.py call in that shell picks it up):
setx YENGOV_BOUNDARIES_RAW_DIR "D:\caches\yen-gov-boundaries"  # PowerShell, persistent
$env:YENGOV_BOUNDARIES_RAW_DIR = "D:\caches\yen-gov-boundaries"  # PowerShell, session
export YENGOV_BOUNDARIES_RAW_DIR=/caches/yen-gov-boundaries     # bash/zsh
```

Precedence: `--raw-dir` (CLI) > `YENGOV_BOUNDARIES_RAW_DIR` (env-var) > `<repo>/.runtime/raw/boundaries` (default). With neither override set, behaviour is byte-identical to before this PR -- no existing call site changes.

If you cannot change tooling (e.g. a vendored script that hardcodes the path), a directory junction on Windows or a symlink on Unix achieves the same outcome at the filesystem level:

```powershell
New-Item -ItemType Junction -Path .runtime/raw/boundaries -Target D:\caches\yen-gov-boundaries
```

```bash
ln -s /caches/yen-gov-boundaries .runtime/raw/boundaries
```

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
- [Boundary-data philosophy](../../docs/concepts/boundary-data-philosophy.md) -- the "why" behind every source choice (polygons vs topographic raster, GADM rejection, TopoJSON adoption status, DIGIPIN deferral, HTL kept on purpose)
- [Boundary-data sources catalogue](../../docs/reference/boundary-data-sources.md) -- live inventory + per-level coverage + license rows
- CLAUDE.md §3 (datasets is a contract surface), §4 (tools self-contained), §12 (provenance)
- [ADR-0003: no fetch cache](../../docs/architecture/backend/core.md#adr-0003-no-fetch-cache) — why raw downloads land under `.runtime/raw/`, not under `datasets/`
