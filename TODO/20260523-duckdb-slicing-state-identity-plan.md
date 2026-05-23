# DuckDB Slicing And State Identity Sequence

**Last Updated**: 2026-05-23
**Status**: P0 contract freeze DONE via PR #165. P1 `registerSlice` implementation DONE via PR #167. P2 generalisation is complete in this sequence; later phases stay queued until their prerequisites are on `main`.
**Scope**: Frontend DuckDB-WASM slice registration, manifest-directed file selection, state-code alias doctrine, and later YENASK/SemanticCatalogue alignment.
**Spec**: [frontend/data-loading.md](../docs/architecture/frontend/data-loading.md), [canonical-store.md](../docs/architecture/data/canonical-store.md)
**Decision rationale**: [ADR-0036](../docs/architecture/decisions/0036-state-identity-and-slice-registration.md), [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md), [ADR-0028](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md)

---

## Current Decisions

| Decision | Home |
| --- | --- |
| DuckDB-WASM remains the browser SQL engine over canonical Parquet. | [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) |
| State/UT identity is a canonical entity row with ECI, LGD, ISO, and slug aliases. | [ADR-0036](../docs/architecture/decisions/0036-state-identity-and-slice-registration.md) |
| Existing elections keep `state=in_s22`; this is elections-only physical grammar. | [canonical-store.md](../docs/architecture/data/canonical-store.md) |
| Future socio-economic state partitions prefer ISO-like tokens if partitioning is earned. | [ADR-0036](../docs/architecture/decisions/0036-state-identity-and-slice-registration.md) |
| `registerSlice` is manifest-native and takes physical partition filters. | [frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) |
| `/s/...` is current legacy runtime; `/india/...` is the target citizen route grammar. | [frontend/routing.md](../docs/architecture/frontend/routing.md) |

---

## PR Sequence

### P0 - Contract Freeze

| Row | Task | Status | Verification |
| --- | --- | :-: | --- |
| P0.1 | Accept the consultation plan and promote decisions out of TODO. | DONE | User request to implement sequence. |
| P0.2 | Add ADR for state aliases + partition token policy + `registerSlice`. | DONE | ADR-0036 indexed. |
| P0.3 | Update canonical-store and frontend data-loading subsystem docs. | DONE | Docs point to ADR-0036. |
| P0.4 | Replace this TODO with a phase ledger only. | DONE | No rationale lives here after P0. |

### P1 - Slice Seam On Existing Election Partitions

| Row | Task | Current smoke route | Target route note | Verification |
| --- | --- | --- | --- | --- |
| P1.1 | Add `registerSlice` in `frontend/src/lib/duckdb.ts`. | none | n/a | DONE: vitest fake-manifest coverage for match, no match, unknown key, unpartitioned table. |
| P1.2 | Add or update the DuckDB harness slice check. | `/dev/duckdb-harness` | n/a | DONE: browser verifies only `elections/state=in_s22/election_results.parquet` is selected for TN slice. |
| P1.3 | Switch the state-hub election loaders mounted on `/s/tamil-nadu` to `registerSlice`. | `/s/tamil-nadu` (current legacy runtime) | `/india/tamil-nadu` after route migration | DONE: same values/sources; state route only requests the TN election partition. |

P1 uses `state=in_s22` only because that is the current election partition. It must not promote ECI partition grammar as future socio-economic state grammar.

### P2 - Generalise Election Consumers

| Row | Task | Status | Verification |
| --- | --- | :-: | --- |
| P2.1 | Move remaining state-scoped election consumers to slice registration. | DONE | Constituency + Psephlab actuals loader tests; route smoke. |
| P2.2 | Leave Explore/Compare intentionally broad. | DONE | Broad-mode readers still use `registerTable`. |
| P2.3 | Record current `/s/...` smoke targets with legacy labels until route migration. | DONE | Current smoke targets stay labelled legacy/current. |

### P3 - Energy / Socio-Economic Pilot

| Row | Task | Status | Verification |
| --- | --- | :-: | --- |
| P3.1 | Pick one Energy canonical fact table after P.1 Energy stabilises. | QUEUED | Hans + Max data-shape signoff. |
| P3.2 | Decide partition axis from file size and route story. | QUEUED | Manifest stats and shard-size audit. |
| P3.3 | Join through canonical entity rows and aliases. | QUEUED | Tests prove no hardcoded ECI state code in new Energy loader. |
| P3.4 | Mount one Energy-facing canonical route. | QUEUED | Source/unit/period/comparison visible at rest; browser smoke. |

### P4 - SemanticCatalogue / YENASK Control Plane

| Row | Task | Status | Verification |
| --- | --- | :-: | --- |
| P4.1 | Keep YENASK lab-local until real consumer pressure. | QUEUED | No manifest bump just to reserve space. |
| P4.2 | Promote SemanticCatalogue only when needed. | QUEUED | Schema/version tests; no observation values. |
| P4.3 | Update InsightIntent identity to `entity_id` + aliases. | QUEUED | Zod rejects ambiguous/unknown state aliases. |
| P4.4 | Keep model runtime explicit. | QUEUED | No model load on initial paint. |

### P5 - Optional Identity Migration

| Candidate | Status |
| --- | --- |
| Rename state entity IDs from ECI-shaped `IN-S22` to ISO-shaped IDs. | Open; requires ADR + migration plan + consumer audit. |
| Rename election partitions from `state=in_s22`. | Open; probably unnecessary. |
| Add normalized `taxonomy.entity_aliases` table. | Strong additive candidate; separate structural PR. |

---

## Gates

- P1 must preserve `registerTable` behaviour.
- P1 must not introduce JSON observation projections.
- P1 must not touch Energy, SemanticCatalogue, or model runtime.
- Frontend runtime changes require `bun run test`, `bun run test:e2e` when route-visible, and CLAUDE.md §13 browser smoke.
- Current runtime smokes may use `/s/tamil-nadu` only while labelled legacy/current; new route-design text uses `/india/tamil-nadu`.

## See also

- [TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md)
- [TODO/20260518-browser-governance-insight-assistant-plan.md](20260518-browser-governance-insight-assistant-plan.md)
- [TODO/20260522-phase-2-p1-energy-pivot.md](20260522-phase-2-p1-energy-pivot.md)
- [docs/reference/lgd-opendata.md](../docs/reference/lgd-opendata.md)
