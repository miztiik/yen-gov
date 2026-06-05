# tools/topojson - GeoJSON to TopoJSON converter

**Status**: active (P2.1 of [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](../../docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md))

Converts an input GeoJSON FeatureCollection to a TopoJSON file via the
[Mapshaper](https://github.com/mbloch/mapshaper) CLI. Idempotent
(skips re-run when source hash + tool version + quantization match a sidecar
meta JSON next to the output). Deterministic (subprocess env pins
`LC_ALL=C` + `LC_NUMERIC=C`).

## Install

Mapshaper ships as a frontend devDependency. Install via:

```powershell
cd frontend
bun install
```

`frontend/bun.lock` is the single version contract. Do NOT install
mapshaper globally with `npm i -g mapshaper`; the project version pin
must match the contract in `bun.lock`.

The pinned version is recorded for humans + audit in
[.mapshaper-version](.mapshaper-version) (a one-line file containing the
exact version string). The converter compares its own `bunx mapshaper
--version` output against that file at start-up and fails fast on a
mismatch.

## Run

```powershell
python -m tools.topojson.convert_layer `
  --input datasets/boundaries/in/states/all.geojson `
  --output datasets/boundaries/in/states/all.topojson `
  --layer states `
  --config config/topojson.json
```

`--layer` names the single TopoJSON object name that wraps the
FeatureCollection (e.g. `states`, `districts`). `--config` is optional;
defaults to `config/topojson.json` at the repo root.

## Determinism contract

- Subprocess env injects `LC_ALL=C` + `LC_NUMERIC=C` so mapshaper's
  numeric formatting is locale-independent.
- `-clean` flag is OPT-IN per layer via `config/topojson.json` (default
  OFF). `-clean` mutates topology (gap-fill, sliver removal) and breaks
  the feature-count + coordinate-shape contracts; only enable when a
  specific input justifies it.
- Idempotency key = `sha256(input) + mapshaper_version + quantization +
  simplification + clean_flag`. Stored as a sidecar
  `<output>.topojson.meta.json` next to the output. A re-run with an
  unchanged input + tool + config short-circuits without re-invoking
  mapshaper. mtime is NOT a contract (git resets mtime on checkout).
- A mapshaper version bump = a schema-version-style migration: bump
  `.mapshaper-version`, re-run conversions, commit both in the same
  PR. Sidecar comparisons will treat outputs as stale and re-emit.

## Acceptance

`backend/tests/test_topojson_convert_layer.py` exercises:

1. Mapshaper invoked with `-o format=topojson quantization=<N>` and the
   `<layer>` name as the object key.
2. Two consecutive runs against the same input produce byte-identical
   output (idempotency).
3. Sidecar meta JSON is written; second run is skipped via sidecar
   match.
4. The output parses as TopoJSON and `topojson.feature(...).features`
   length equals the input GeoJSON feature count.

## See also

- [config/topojson.json](../../config/topojson.json) - per-layer
  quantization + simplification overrides.
- [datasets/schemas/topojson-config.schema.json](../../datasets/schemas/topojson-config.schema.json) -
  schema for the config file (per CLAUDE.md section 11).
- [docs/architecture/frontend/topojson-loader.md#adr-0047-topojson-as-render-encoding](../../docs/architecture/frontend/topojson-loader.md#adr-0047-topojson-as-render-encoding) -
  ADR for the encoding decision (folded into the topojson-loader subsystem doc per D-DOC3.7; the originating ADR file was deleted in D-DOC3.10).
