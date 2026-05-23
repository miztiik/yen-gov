# ADR-0036: State identity aliases and manifest-directed slice registration

**Last Updated**: 2026-05-23
**Status**: Accepted
**Date**: 2026-05-23
**Deciders**: User approval of the DuckDB slicing plan; Gregor on manifest/registerSlice contracts; Hans + Max on state identity aliases; Fowler on reversible sequencing; Jony + Citizen on first-paint posture.
**Cross-cuts**: `datasets/taxonomy/entities`, `datasets/manifest.json`, frontend DuckDB-WASM loaders, future socio-economic partitions, and YENASK/SemanticCatalogue intent resolution.

## Context

ADR-0030 made Parquet + DuckDB-WASM the strategic read path. The next pressure is runtime cost: a citizen state page should not register every election partition when the page asks only for one state's rows, and a casual first paint should not pay the analytical-engine cost before it needs values.

The same discussion exposed an identity trap. Current election partitions are ECI-shaped (`state=in_s22`) because elections ingest is keyed by ECI state codes (`S22`). Many Government of India datasets are keyed by LGD numeric state codes (`33` for Tamil Nadu), while public state identity is better represented by ISO 3166-2 (`IN-TN`). `taxonomy/entities.json` already carries the bridge (`entity_id`, `entity_code`, `lgd_code`, `iso_3166_2`, display name), but the current partition grammar could be mistaken for a universal state identity.

We need one decision that keeps the static DuckDB path, introduces a manifest-backed slice registration seam, and prevents the ECI partition token from leaking into future socio-economic families or YENASK prompts as the one true state code.

## Decision

### State identity

A state or UT is one canonical entity row with authority-specific aliases. No single external authority code owns state identity across yen-gov.

- Citizen URLs use slugs under the ADR-0028 grammar, for example `/india/tamil-nadu`.
- Observation rows use canonical `entity_id` values.
- Existing state `entity_id` values such as `IN-S22` remain unchanged. Renaming them to ISO-shaped IDs is a separate high-blast-radius migration that needs its own ADR and consumer audit.
- `entity_code` on current state rows remains the existing ECI-shaped code (`S22`, `U05`, etc.) until a separate normalized alias table exists. It must not be described as universal state identity.
- `lgd_code` is the GoI/LGD join key for administrative datasets.
- `iso_3166_2` is the preferred public-state alias and the likely source for future state-level socio-economic partition tokens.
- YENASK and any future SemanticCatalogue resolve citizen mentions to `entity_id` first, then pick the source-specific alias required by the table or partition.

### Partition tokens

Partition values are physical delivery tokens, not identity tokens.

- Existing elections keep `state=in_s22` as the current election partition contract. It is elections-only and ECI-contextual.
- Future state-level socio-economic partitions, if they are earned by file size or route shape, prefer ISO-like tokens such as `state=in_tn`.
- Lower administrative partitions prefer LGD codes, for example district, subdistrict, panchayat, village, and local-government finance partitions.
- Frontend code reads `datasets/manifest.json` and never constructs Parquet paths directly from any state code.
- A physical partition rename, including elections `state=in_s22`, is optional and probably unnecessary. If it ever happens, use an expand-migrate-contract sequence with manifest deprecations.

### `registerSlice`

Add a frontend DuckDB seam named `registerSlice` before any SemanticCatalogue or model-runtime work.

The contract is manifest-native:

- Input: `tableId`, exact partition filter, and optional view name.
- Filters are keyed by `manifest.tables[].partition_columns` and matched against each file's `partition_values`.
- The first implementation supports scalar exact-match filters only. Array filters for multi-state compare are deferred until a concrete caller needs them.
- Unknown partition keys fail loud.
- A requested slice with no matching files fails loud for required routes.
- A filter against an unpartitioned table fails unless the caller explicitly allows full-table fallback.
- `registerTable` remains the full-table registration path, especially for Explore and intentionally broad modes.
- No manifest schema bump is required; manifest v1.3 already has `partition_columns` and `files[].partition_values`.

Callers may translate logical route state into a physical partition filter before calling `registerSlice`, but that translation is table-specific and must not be encoded inside `registerSlice`. The seam is deliberately physical because the manifest is the physical inventory. Logical alias resolution belongs in route/view-model helpers now and in SemanticCatalogue later.

### SemanticCatalogue

SemanticCatalogue stays separate from `datasets/manifest.json`. If it graduates beyond lab-local use, it becomes its own schema-versioned control-plane artifact and may be listed from a future manifest `control_artifacts[]` field. It must not contain observation values, latest-value shadows, rank tables, choropleth bins, or route-specific fact projections.

## Consequences

### Good

- Citizen routes can register only the Parquet files they need without adding JSON observation projections or route-specific mini databases.
- The manifest remains a physical inventory; semantic lookup remains a separate control-plane concern.
- Current election partitions keep working while future socio-economic families avoid copying ECI-shaped tokens by accident.
- YENASK gets a clean identity rule: user text resolves to `entity_id`, not to `S22`, `33`, or `IN-TN` directly.
- The first code PR can be small and reversible: add `registerSlice`, prove it on one existing election state slice, then generalise.

### Bad

- `registerSlice` callers must know which table they are slicing and may need small table-specific alias helpers until SemanticCatalogue exists.
- Current `entity_code` remains overloaded for state rows. A normalized `taxonomy.entity_aliases` table is still desirable, but it is intentionally not part of this PR.
- Existing documentation and tests must be precise about `/s/tamil-nadu` being a current legacy smoke route, while `/india/tamil-nadu` is the target citizen route.

## Alternatives considered

### A — ECI everywhere

Use `S22` / `state=in_s22` as universal state identity because elections already use it.

Rejected. ECI codes are election-context identifiers. GoI administrative data commonly uses LGD codes, and public state identity is better represented by ISO 3166-2. Treating ECI as universal would force every non-election ingest to carry an election-shaped alias as its primary identity.

### B — Immediate ISO rename

Rename existing `IN-S22` entity IDs and election partitions to ISO-shaped values now.

Rejected. That would entangle performance work with a core identity migration across datasets, frontend routes, map helpers, tests, and docs. The benefit does not earn the blast radius today. Alias-first preserves current consumers and keeps the migration optional.

### C — LGD everywhere

Use LGD numeric codes as universal state identity because GoI datasets use them.

Rejected. LGD is the right administrative join key, especially below the state level, but its numeric state codes are not citizen-readable, are level-confusable, and do not cover election context cleanly.

### D — Route-specific JSON projections

Generate small JSON fact shadows for state pages and leave DuckDB for Explore/Ask.

Rejected. This violates ADR-0030 D10: no JSON projections of canonical observation data for the frontend. It creates a second truth and weakens the static-first SQL/YENASK path.

### E — Frontend path guessing

Let loaders build paths like `elections/state=${state}/election_results.parquet` directly.

Rejected. ADR-0030 D21/R23 requires manifest-directed discovery. Partition policy is a data-delivery contract, not a string convention every loader re-implements.

### F — Logical selectors inside `registerSlice`

Make `registerSlice({ entity_id: "IN-S22" })` translate to the right partition value internally.

Rejected for the first seam. `registerSlice` would become both a physical registry and a semantic resolver, mixing two axes and forcing it to learn table-specific alias rules. Keeping it manifest-native makes the contract small; logical resolution can sit above it and evolve independently.

## Doc impact

- [canonical-store.md](../data/canonical-store.md) documents state alias identity, elections-only `state=in_s22`, and future partition-token policy.
- [frontend/data-loading.md](../frontend/data-loading.md) documents `registerSlice` next to `registerTable`.
- [TODO/20260523-duckdb-slicing-state-identity-plan.md](../../../TODO/20260523-duckdb-slicing-state-identity-plan.md) becomes a phase ledger that points here instead of carrying rationale.

## See also

- [ADR-0030: Canonical long-format store on Parquet + DuckDB-WASM](0030-canonical-store-duckdb-wasm.md)
- [ADR-0028: URL scheme](0028-url-scheme-place-first-flat-indicator-slug.md)
- [Frontend data loading](../frontend/data-loading.md)
- [Canonical store](../data/canonical-store.md)
- [Identifier conventions](../../reference/identifiers.md)
- [LGD opendata source catalogue](../../reference/lgd-opendata.md)
