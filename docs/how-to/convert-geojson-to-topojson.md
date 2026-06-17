# How to convert GeoJSON to TopoJSON

**Last Updated**: 2026-05-31

Runbook for [tools/topojson/convert_layer.py](../../tools/topojson/convert_layer.py), the deterministic Mapshaper wrapper that ships every `.topojson` sibling under `datasets/boundaries/in/`.

Distilled from [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](../../docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md) rows P2.1 + P4.x. See [ADR-0047](../architecture/frontend/topojson-loader.md#adr-0047-topojson-as-render-encoding) for why this encoding exists.

## See also

- [docs/architecture/frontend/topojson-loader.md](../architecture/frontend/topojson-loader.md) - what consumes the output
- [tools/topojson/README.md](../../tools/topojson/README.md) - install + version pin reference
- [docs/architecture/frontend/topojson-loader.md#adr-0047-topojson-as-render-encoding](../architecture/frontend/topojson-loader.md#adr-0047-topojson-as-render-encoding)
- [docs/architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy](../architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy)

## Prerequisites

1. `cd frontend && bun install --frozen-lockfile` once per worktree. The pinned `mapshaper` lives at `frontend/node_modules/.bin/mapshaper`. `bun.lock` is the version contract per CLAUDE.md Holy Law #9.
2. Confirm version pin: `Get-Content tools/topojson/.mapshaper-version` returns `0.7.22` today. The converter reads this file and stamps it into every sidecar; CI fails if a sidecar references a version other than the pinned one.
3. Python: the converter has no third-party deps. Plain `python -m tools.topojson.convert_layer` works under any 3.11+ interpreter.

## Single-shard mode

```powershell
python -m tools.topojson.convert_layer `
  --input datasets/boundaries/in/states/all.geojson `
  --output datasets/boundaries/in/states/all.topojson `
  --layer states
```

Outputs:

- `datasets/boundaries/in/states/all.topojson` - the TopoJSON encoding.
- `datasets/boundaries/in/states/all.topojson.meta.json` - the idempotency sidecar (sha256 of input + mapshaper version + quantization + simplification + clean flag).

Re-running the same command is a no-op when the sidecar matches the input. Delete the sidecar to force a re-encode.

## Batch mode

For multi-shard layers (AC, PC, ULB-wards, panchayats, villages, postal), use the batch entry point. It chains all cache-miss shards into one mapshaper subprocess so Node startup overhead is paid once per chunk, not once per shard. Throughput on Windows lifts from approximately 6 shards/min to >= 60 shards/min for medium shards (PR #496).

1. Build a manifest JSON file:

   ```json
   [
     { "input": "datasets/boundaries/in/villages/state=tamil-nadu/district=603/all.geojson",
       "output": "datasets/boundaries/in/villages/state=tamil-nadu/district=603/all.topojson",
       "layer": "village" },
     { "input": "datasets/boundaries/in/villages/state=tamil-nadu/district=604/all.geojson",
       "output": "datasets/boundaries/in/villages/state=tamil-nadu/district=604/all.topojson",
       "layer": "village" }
   ]
   ```

   NOTE (2026-06-16): the two shipping national TopoJSON layers — `in/country/all.topojson` and `electoral/delim=2024/ac/all.topojson` — are built by their own dedicated consolidation scripts (`tools/topojson/build_country.py`, `tools/boundaries/consolidate_ac_2024.py`), not this batch tool. This batch entry point remains the general path for any future per-shard layer that needs a TopoJSON sibling.

2. Run:

   ```powershell
   python -m tools.topojson.convert_layer `
     --batch .tmp_ac_manifest.json `
     --batch-size 50
   ```

`--batch-size` controls how many shards mapshaper chains into a single subprocess. 50 is the empirical sweet spot for shards of approximately 100-500 features each. Lower it for very large shards (a national PC layer is ~543 features; ULB wards ~ 100 features per shard).

## Config knobs

[config/topojson.json](../../config/topojson.json) holds tunable knobs per CLAUDE.md Holy Law #6 (no hardcoding):

- `default_quantization`: integer coordinate grid; OWID default `100000` (about 1m precision). Per-layer override goes in `per_layer.<name>.quantization`.
- `simplification`: Mapshaper `-simplify` flag value; current default `none` (the 2026-06-16 map-geometry rip removed simplification entirely — TopoJSON ships quantization + arc-sharing only, no vertex deletion, so coastlines stay crisp). Per-layer override in `per_layer.<name>.simplification`.
- `clean`: opt-in `-clean` flag (silently mutates topology - gap-fill, sliver removal). Default `false`. Set per-layer only when the input is known dirty and a visual diff confirms the cleanup is desired.

The schema lives at [datasets/schemas/topojson-config.schema.json](../../datasets/schemas/topojson-config.schema.json); validated by Tier-A on every `pytest -q`.

## Determinism contract

- Mapshaper version pinned in `tools/topojson/.mapshaper-version`. Bumping is a schema-version-style migration: regenerate every `.topojson`, validate diffs, swap.
- Subprocess env injects `LC_ALL=C` + `LC_NUMERIC=C` to avoid locale-sensitive numeric formatting.
- Idempotency sidecar key = sha256(input) + mapshaper_version + quantization + simplification + clean. Re-runs short-circuit before mapshaper is invoked when the key matches.
- Mapshaper version bump = regenerate-everything migration; the version mismatch trips Tier-B.

## Conformance gates

After any conversion run:

1. `pytest backend/tests/test_topojson_convert_layer.py -q` - unit tests for the converter.
2. `bun --cwd frontend run test src/contracts/boundaries-conform.test.ts` - confirms every shipped `.topojson` has a sibling `.geojson` (until the cleanup commissioned at parent plan P5.4) and asserts feature-count parity per shard.
3. Smoke the affected citizen route in the integrated browser per CLAUDE.md section 13.

## Troubleshooting

**Mapshaper OOM on a large shard** (villages, full-state ULB wards):

```powershell
$env:NODE_OPTIONS = "--max-old-space-size=4096"
python -m tools.topojson.convert_layer --batch .tmp_manifest.json --batch-size 10
```

Lower `--batch-size` (10-20) for the largest shards so each subprocess chunk fits in 4 GB heap.

**Mapshaper not found**: `cd frontend && bun install --frozen-lockfile` from inside the worktree where the conversion runs (worktrees do NOT share `node_modules`).

**Locale-sensitive output drift between developer machines**: the converter forces `LC_ALL=C`. If you still see numeric-format drift, your shell is overriding the env block - confirm with `python -c "import os; print(os.environ.get('LC_ALL'))"` inside the subprocess wrapper.

**Output is non-deterministic across runs on the same machine**: delete the sidecar and re-run. If the second run produces a different byte payload, file a bug against the pinned mapshaper version (this is the contract the determinism gates protect).

**Want to override quantization for one layer**: edit `config/topojson.json`:

```json
{
  "$schema": "../datasets/schemas/topojson-config.schema.json",
  "$schema_version": "1.0",
  "default_quantization": 100000,
  "simplification": "weighted 5%",
  "per_layer": {
    "villages": { "quantization": 50000 }
  }
}
```

No code change required. Re-run the converter; the sidecar mismatch forces a regenerate.
