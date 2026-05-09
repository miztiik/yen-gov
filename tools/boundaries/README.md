# tools/boundaries

**Last Updated**: 2026-05-09

Builds vector-tile boundary files (`datasets/boundaries/in/*.pmtiles`) consumed by the frontend [map](../../docs/architecture/frontend/map.md). The pipeline downloads upstream GeoJSON, simplifies with [mapshaper](https://github.com/mbloch/mapshaper), and packs to [PMTiles](https://github.com/protomaps/PMTiles) with [tippecanoe](https://github.com/felt/tippecanoe).

This tool is **CI-only** by design (see [Why CI-only](#why-ci-only)). On Windows you do not need to install tippecanoe locally — trigger the [`boundaries` workflow](../../.github/workflows/boundaries.yml) and merge the resulting PR.

## Layout

| File | Role |
| --- | --- |
| [pipeline.json](pipeline.json) | Declarative list of upstream URLs, output paths, simplification + tippecanoe options per file. Edit this to add states or change sources. |
| [build.py](build.py) | Orchestrator. Self-contained (stdlib only). Reads `pipeline.json`, downloads, simplifies, packs, writes manifest. |
| `../../.github/workflows/boundaries.yml` | CI runner. Installs tools, executes `build.py`, opens a PR with the regenerated `datasets/boundaries/in/`. |

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
| India states | [geohacker/india](https://github.com/geohacker/india) `state/india_state.geojson` | CC-BY 4.0 (GADM v2 derivative) | 35 features; joins on `NAME_1`. datameet has no clean states-as-features GeoJSON. |

### ⚠️ Assam delimitation caveat

The Assam AC shapefile may predate the 2008 Delimitation Order's revisions. Before the boundaries workflow PR is merged, cross-check that every `AC_NO` 1..126 in the simplified GeoJSON matches a constituency under [`datasets/reference/in/states/S03/constituencies.json`](../../datasets/reference/in/states/S03/constituencies.json) (compare names too, not just counts — a renumbering would pass a count check but produce a wrong-color map). If they don't match, hold the merge and source a 2026-current shapefile.

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

Native Windows is not supported (tippecanoe has no maintained Windows build). Use WSL2 or just trigger the workflow.

## Why CI-only

- **Tippecanoe needs Linux/macOS.** Forcing every contributor on every OS to install build-essential + sqlite-dev + node + mapshaper for an artifact that changes once per delimitation cycle is bad ergonomics.
- **Reproducibility is improved by a fixed CI image.** Different mapshaper versions can produce subtly different simplifications; pinning the workflow's tool versions makes the manifest's `size_bytes` deterministic enough to spot regressions in PR diffs.
- **The output is small enough to commit.** A few hundred kB per file × handful of files ≈ <2 MB total. No LFS, no submodule.

## See also

- [Frontend map architecture](../../docs/architecture/frontend/map.md)
- CLAUDE.md §3 (datasets is a contract surface), §4 (tools self-contained), §12 (provenance)
- [ADR-0003: no fetch cache](../../docs/architecture/decisions/0003-no-fetch-cache.md) — why raw downloads land under `.runtime/raw/`, not under `datasets/`
