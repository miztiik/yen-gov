# Plan: LGD partition-rename successor (M2 / M3 / M4 + reader updates)

**Status:** PROPOSED
**Author:** GitHub Copilot (orchestrator)
**Last Updated:** 2026-06-01
**Level:** 5 (cross-cutting; XL risk; serialises behind one another)
**Parent:** [TODO/20260601-lgd-execution-handover.md](20260601-lgd-execution-handover.md) (rows M2/M3/M4 + F1 + AC1a/AC1b are spun out here)

## Why this is its own plan-doc

The parent execution-handover tagged M2/M3/M4 as XL risk and explicitly required serial execution. A blast-radius audit at the end of PR M1 (ship #560) confirmed: every legacy `state=in_sXX` token in the repo has live readers - CI YAML, frontend e2e, Svelte routes, backend slug generator, parquet KV_METADATA in `datasets/manifest.json`, multiple docs. Executing the rename without updating every reader in the SAME commit produces a broken-frontend / failing-CI state. Therefore each `Mx` execute is its own focused PR that:

1. runs `tools/migrate/rename_partition_keys.py --apply` over its scope
2. updates every co-dependent reader (frontend, backend, CI, manifest, docs)
3. regenerates the affected parquet files where KV_METADATA carries `partition_values`

## Blast-radius inventory (audited 2026-06-01)

Every legacy reference found by `grep -E 'in_[su][0-9]{2}'` across the repo:

| File | Lines | What references | Impact |
| --- | ---: | --- | --- |
| `.github/workflows/deploy-site.yml` | 98, 173 | hardcoded `state=in_s22/election_results.parquet` URLs | CI deploy + smoke check fails on rename |
| `frontend/e2e/duckdb-harness.spec.ts` | 51, 63 | asserts `state-partition` = `"in_s22"` and URL contains `/state=in_s22/` | e2e test fails on rename |
| `frontend/e2e/yenask.spec.ts` | 47 | comment `(in_s22)` | benign, but should update copy |
| `frontend/src/routes/DuckDbHarness.svelte` | 27, 34 | hardcoded `{state: "in_s22"}` registerSlice + display literal | runtime route shows wrong slice |
| `frontend/src/lib/view-models/state-overview.ts` | (TBC) | `entity_id -> state_partition` translation | needs LGD slug map |
| `backend/yen_gov/sources/datagovin_ogd/ingest_pincode_polygons.py` | 22, 239, 257 | function `iso_to_partition_slug` returns `in_s22` form | regenerates Hive paths under legacy convention |
| `datasets/manifest.json` | (multiple) | `partition_values: {state: "in_s22"}` for every shard | manifest must be regenerated post-rename |
| `datasets/boundaries/in/<layer>/state=in_*/` | 261 dirs | the actual data partitions | the move target |
| `docs/architecture/data/canonical-store.md` | 66-67, 776-844, 1087 | every example uses `in_sXX` | docs sweep |
| `docs/architecture/frontend/data-loading.md` | 90 | example | docs sweep |
| `docs/architecture/frontend/map.md` | 178 | example | docs sweep |
| `docs/architecture/frontend/yenask.md` | 168 | comment | docs sweep |
| `docs/how-to/convert-geojson-to-topojson.md` | 46-50 | example | docs sweep |
| `docs/how-to/add-new-boundary-layer.md` | 152 | example | docs sweep |
| `docs/archive/canonical-pivot-plan-20260522-snapshot.md` | 271 | archived plan example | leave (archive) |

## Per-row PR plan

| # | Row | Scope | Bundled reader updates | Risk |
| :-: | --- | --- | --- | :-: |
| **M2** | Rename `datasets/boundaries/**` state= dirs | 225 dir renames + `frontend/src/lib/maplibre/sources.ts` (boundary path templates) + boundaries vitest fixtures + `docs/how-to/add-new-boundary-layer.md` + `docs/architecture/frontend/map.md` | XL |
| **M2-test** | Update boundaries vitest contract tests if any hardcode `in_sXX` | run `bun run test src/contracts/boundaries-conform.test.ts` post-rename to catch | M |
| **M3** | Rename `datasets/elections/**` state= dirs + regenerate `datasets/elections/dim_acs.parquet` if it carries partition slugs in any column | 36 dir renames + `.github/workflows/deploy-site.yml` (2 hardcoded URLs) + `frontend/e2e/duckdb-harness.spec.ts` + `frontend/e2e/yenask.spec.ts` + `frontend/src/routes/DuckDbHarness.svelte` + `frontend/src/lib/view-models/state-overview.ts` + `datasets/manifest.json` (every `partition_values.state` for elections shards) + `docs/architecture/data/canonical-store.md` (all `in_sXX` examples) + `docs/architecture/frontend/data-loading.md` | XL |
| **M4** | Rename residual `datasets/**` state= dirs (postal/wards/panchayats/villages etc. not already covered by M2) + update `backend/yen_gov/sources/datagovin_ogd/ingest_pincode_polygons.py` slug generator to emit LGD slugs | 261 - 225 - 36 = ~0 dirs (M2+M3 cover them); residual = ingest scripts + docs | M |
| **F1** | Frontend redirect map for any pre-rename bookmarks (URLs already use LGD slug per ADR-0048, so likely no-op; verify) + golden-path.spec.ts coverage of the new partition shape | `frontend/src/lib/routes.ts` (only if any old slug exists) + golden-path test | L |

## Pre-flight gates (run before EVERY Mx PR)

1. `python -m tools.migrate.rename_partition_keys --root <scope> --manifest .tmp_<row>_manifest.json` (dry-run)
2. Reviewer + agent eyes on manifest JSON; spot-check 5 random renames
3. `grep -rn 'in_[su][0-9]\{2\}'` in `<scope>` AFTER the rename to confirm zero residual references
4. svelte-check / vitest / pytest all green
5. Browser smoke through `bun run dev` for at least one state route (e.g. `/s/haryana`)

## STOP conditions per row

- M2 STOPS if `bun run test src/contracts/boundaries-conform.test.ts` regresses
- M3 STOPS if `frontend/e2e/duckdb-harness.spec.ts` fails (the DuckDB-WASM partition resolver needs to match the new shape)
- M4 STOPS if the regenerated `datasets/manifest.json` produces a non-empty diff against the canonical writer's output

## After Mx complete

- F1 redirect-map PR (likely no-op; document the no-op + add a route assertion test that `/s/haryana` resolves)
- CLOSE the parent execution-handover plan + this successor plan in one ceremony PR per `docs/how-to/distill-a-plan.md`

## See also

- [PR M1](https://github.com/miztiik/yen-gov/pull/560) - the rename tool + dry-run manifest (this plan's prerequisite)
- [ADR-0050](../docs/architecture/decisions/0050-folder-naming-lgd-slug.md) - folder-naming contract
- [docs/architecture/data/lgd-canonical-keys.md](../docs/architecture/data/lgd-canonical-keys.md) - join contract
- [TODO/20260601-lgd-execution-handover.md](20260601-lgd-execution-handover.md) - parent plan
- `tools/migrate/rename_partition_keys.sample_manifest.json` - the full 261-rename manifest as committed for review
