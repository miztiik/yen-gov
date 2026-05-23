# SourceList v2 — citation-ledger consumer

Pure TypeScript shape + helpers for the citizen-facing chart footer.
This package is the boundary between the canonical store
(`taxonomy.sources` parquet, v2.0 schema per ADR-0032) and the chart
chrome that renders it.

## What lives here

| File | Purpose |
|---|---|
| `types.ts` | `SourceV2Row`, `CollapsedSummary`, `ExpandedDisclosure`, locked enums (`SourceLicense`, `ConfidenceTier`, `VerificationMethod`), `FORBIDDEN_SOURCE_FIELDS`. |
| `format.ts` | `formatCollapsedSummary`, `formatExpandedDisclosure`, `composeDefaultCitation`, `verificationMethodRank`. All pure, all sync, zero dependencies. |
| `format.test.ts` | Vitest coverage for the four helpers + the empty-vintage / hand-authored / overridden-citation edge cases. |
| `../SourceListV2.svelte` | Render surface. Triangle-disclosure footer that consumes `SourceV2Row[]`. **Zero callers** today — see R-08 below. |

The render surface (`SourceListV2.svelte` at the parent `lib/` level)
exists alongside the v1 `SourceList.svelte` per R-08 Branch-by-Abstraction.
V1 continues to ship to every citizen page (it still consumes the
retired `SourceRef { url, fetched_at }` shape that `frontend/src/lib/data.ts`
loaders emit). Per-caller migration to v2 happens once the data layer
emits `SourceV2Row[]` end-to-end (or behind a typed adapter shim) — a
follow-up PR per caller, each carrying its own CLAUDE.md §13 browser
smoke. V1 is deleted only after every caller has migrated.

## Hard constraints

1. **R-24 — fetch-telemetry fields are forbidden in citizen chrome.**
   Never add `fetched_at`, `first_fetched_at`, `last_seen_at`,
   `date_accessed`, `content_hash`, or `url` to any type or helper in
   this module. ADR-0032 P.0e retired all of them; they live in
   `.runtime/<adapter>/<source_id>.json` sidecars for cache invalidation
   only. The contract test at
   `frontend/src/contracts/sources-v2-shape.test.ts` is the drift
   detector — `FORBIDDEN_SOURCE_FIELDS` is the single list.

2. **R-28 — resolve via manifest `table_id`.**
   The parquet location is `taxonomy.sources` in
   `datasets/manifest.json`. Never hardcode
   `/data/taxonomy/sources.parquet` at any call site. The contract test
   asserts this entry is registered at `schema_version: "2.0"`.

3. **R-23 — audits pin to the authoring source.**
   The conform test reads `datasets/schemas/source.schema.json` (JSON,
   PR-reviewable) and `datasets/manifest.json` — NOT a folded JSON
   projection of the parquet (R-27).

4. **Mirror backend semantics, not duplicate them.**
   - `composeDefaultCitation` mirrors
     `backend/yen_gov/canonical/citation.render_citation`.
   - `verificationMethodRank` mirrors
     `backend/yen_gov/canonical/citation.verification_method_rank`.
   - The enums in `types.ts` mirror
     `datasets/schemas/source.schema.json` v2.0.
   If a backend rank or enum changes, this module changes in the same
   PR (fused atomic commit, CLAUDE.md §15).

## Locked enums (mirror `source.schema.json` v2.0)

```
license:              OGL-IN-1.0 | CC-BY-4.0 | CC0-1.0 | public-domain | unknown-public | internal
confidence_tier:      gold | silver | bronze
verification_method:  live-fetch | archived-snapshot | transcribed | editorial
```

Trust ordering: `live-fetch > archived-snapshot > transcribed > editorial`
(see `verificationMethodRank`).
