# SourceListV2 — citation-ledger render surface

**Last Updated**: 2026-05-25

Phase 1.4 of the [charting modernisation plan](../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md). Replaces the v1 SourceList which read fields ([ADR-0032](../../decisions/0032-sources-citation-ledger.md)) removed in the v2.0 citation-ledger contract (`url`, `fetched_at`, `content_hash`).

## What it is

- [`frontend/src/lib/SourceListV2.svelte`](../../../../frontend/src/lib/SourceListV2.svelte) — collapsed/expanded disclosure surface for the v2.0 ledger. Renders one block per source, sorted by verification strength, shows all 11 columns of the ledger row.
- [`frontend/src/lib/source-list-v2/format.ts`](../../../../frontend/src/lib/source-list-v2/format.ts) — pure helpers: `formatCollapsedSummary`, `formatExpandedDisclosure`, `composeDefaultCitation`, `verificationMethodRank`.
- **Adopters**: [`StateOverview.svelte`](../../../../frontend/src/routes/StateOverview.svelte) (footer mounts SourceListV2 from `view_model.sources_v2`), [`ElectionSeatsTrend.svelte`](../../../../frontend/src/lib/ElectionSeatsTrend.svelte) (footer migrated in Phase 1.4 step C).

## Doctrinal rules

- **Type system forbids retired columns.** The component takes `SourceV2Row[]` only. The `FORBIDDEN_SOURCE_FIELDS` contract test ([`frontend/src/contracts/sources-v2-shape.test.ts`](../../../../frontend/src/contracts/sources-v2-shape.test.ts)) fails if `url`, `fetched_at`, or `content_hash` reappear on `SourceV2Row` — this is the drift detector that pairs with the runtime invariant.
- **Verification-method sort is HARDCODED canonical order** — `live-fetch` > `archived-snapshot` > `transcribed` > `editorial`. The order is fixed per the plan; there is no config knob.
- **Citizen-readable enum maps live on the component** (license, confidence_tier, verification_method → display string). Pure helpers stay pure; component is the single i18n surface when localisation lands.
- **Defaults are composed, not stored.** When a source row's `citation_full` is null, `composeDefaultCitation` builds `"<producer>, <title>" + (vintage ? " (<vintage>)" : "")` at render time. Adapters never pre-render citations.
- **`loadStateOverview` emits `sources_v2`** as a required field on `StateOverviewViewModel`. Adopters consume the view-model field; they never reach back into the parquet rows.

## Test surface

- [`source-list-v2/format.test.ts`](../../../../frontend/src/lib/source-list-v2/format.test.ts) — 19 vitest cases (formatters, enum tables, rank ordering, default-citation composition).
- [`frontend/src/contracts/sources-v2-shape.test.ts`](../../../../frontend/src/contracts/sources-v2-shape.test.ts) — structural drift detector for `SourceV2Row` shape.

## See also

- [ADR-0032](../../decisions/0032-sources-citation-ledger.md) — sources citation-ledger contract.
- [`chart-shell.md`](chart-shell.md) — ChartShell delegates source rendering here.
- [`overview.md`](../overview.md) — visualization catalog.
- [`docs/concepts/data-provenance.md`](../../../concepts/data-provenance.md) — canonical concept doc.

## Historical citations

Distils `.commit-msg-14.txt`, `.commit-msg-26.txt`, `.commit-msg-27.txt`, `.commit-msg-28.txt` and `.pr-body-14.md`, `.pr-body-26.md`, `.pr-body-27.md`, `.pr-body-28.md` (deleted on distillation).
