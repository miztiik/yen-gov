# ADR-0020: Indicator artifact as the generic data contract for non-election data

**Last Updated**: 2026-05-11
**Status**: accepted (supersedes the per-category-component direction sketched in early Phase 5 notes)

## Context

yen-gov began as an election viewer. The 2026-05-11 mandate expanded scope to *"compare states' performance and categorise them based on categories like how are we doing on power"* — i.e. socio-economic, fiscal, infrastructure, governance indicators across all states.

Three architectural shapes were considered:

1. **Per-category Svelte components**: `PowerMap.svelte`, `HealthIndex.svelte`, `EconomyTimeline.svelte`, each with its own props, its own data loader, its own legend.
2. **A generic indicator schema + one renderer**: every indicator declared as a JSON artifact validated against `indicator.schema.json`; one Svelte component (`IndicatorChoropleth.svelte`) renders any of them metadata-driven.
3. **A SQL-only flow**: pipe everything into per-state per-topic SQLite (per [ADR-0019](0019-dataset-topology-and-column-discipline.md)) and let the `/explore` page do all the rendering via sql.js.

A side-bar concern surfaced from the Governance Strategist agent review: indicators ship with significant *honesty caveats* — comparability, attribution geography, methodology vintage, series breaks — and these caveats must reach the citizen reliably. A per-component world makes these caveats opt-in and easy to forget.

## Decision

Adopt **Option 2**: a generic `indicator.schema.json` artifact + a metadata-driven `IndicatorChoropleth.svelte` (and its sibling primitives in Phase 6D — ranked table, compare-two view, small-multiples).

The artifact is the contract; the renderer is its implementation; the schema bumps cascade through both with clear minor/major rules per [ADR-0014](0014-sqlite-emitter.md)-style discipline.

### Why generic over per-category

1. **Citizen consistency**. Every indicator reads the same way — title, comparability banner, coverage caption, time slider, map, legend, notes, license. A site where each chart family has a different layout is harder to learn.
2. **Honesty enforcement is structural**. Routing every indicator through one renderer means the comparability banner / coverage caption / methodology caption / license chip *always* appear when their corresponding fields are set. They are not contingent on a per-indicator component author remembering them.
3. **Velocity**. The roadmap calls for 30+ indicators across 8 categories. One generic component scales; thirty per-indicator components do not.
4. **Schema-driven evolution**. New honesty fields (v1.1 added 7 of them) propagate to every indicator chart in one renderer change. With per-category components each would need a port.

### Why not SQL-only

The `/explore` page (sql.js + per-state SQLite) is the right home for *power-user ad-hoc queries*. It is the wrong home for *the citizen-default view of an indicator* because:

- Citizens land on a state page and expect a curated narrative, not a SQL prompt.
- Honesty caveats need to be *editorial* (the comparability banner with hand-written copy), not derived from a SQL row.
- The indicator schema's `notes`, `methodology_vintage`, `comparability` fields are exactly that editorial layer.

Both surfaces will coexist: indicators ship as JSON artifacts under `datasets/indicators/in/<category>/<id>.json` for the curated view; an emitter (Phase 6E) will additionally project them into per-state SQLite for the explore surface.

### What goes in the artifact, what doesn't

Goes in:

- **Provenance** (`sources[]`, `license`, `coverage`).
- **Editorial honesty** (`comparability`, `attribution_geography`, `funding_split`, `implementing_authority`, `methodology_vintage`, `series_breaks[]`, `notes`).
- **Rendering hints** (`value_kind`, `direction`, `scale_hint`, `unit`, `denominator`, `icon`).
- **Data** (`rows[]` as long-form `{entity_id, time, value, facet}`).

Stays out:

- Per-component layout overrides (no "render this with the candle-chart variant" flag) — the renderer choice is in code.
- Sourced commentary or analysis — those belong in `notes/` or a future blog directory, not in indicator artifacts.
- Computed quantities derived from other indicators (per-capita, growth rates) — these are renderer-time computations enabled by `denominator` and series semantics, not pre-computed columns.

### Schema discipline

- **Minor bumps** (`1.0 → 1.1`) are additive: new optional fields. No data migration required.
- **Major bumps** (`1.x → 2.0`) are breaking. Require a migration of all consumer artifacts and a `from`/`to` mapping in `docs/reference/schemas.md`.
- The validator strictly enforces `$schema_version` equality with `x-version` (per the `schema_version` rule in CLAUDE.md §11). A schema bump *must* either bump every consumer artifact or accept the bump as additive (in which case existing artifacts at the older version remain valid until/unless schema enforcement is tightened).
- Every bump appends to `x-changelog` with date and the agent / review that motivated it.

### v1.1 additions, with rationale

| Field | Why it was added | Driver |
|---|---|---|
| `attribution_geography` | A "states ranked by installed power MW" map was indistinguishable on disk from a "states ranked by power consumption" map; the renderer had no way to surface that the first is a *siting* statistic. | Governance Strategist review 2026-05-11 |
| `comparability` | Some indicators are not comparable across states no matter how much normalisation is applied; the renderer needs to *know* this so it can suppress the rank column and surface a banner. | Governance Strategist review 2026-05-11 |
| `funding_split` | Centre-vs-state attribution is the most-asked civic question about social-sector spending; indicators need to declare it where known. | Governance Strategist review 2026-05-11 |
| `implementing_authority` | Citizen-visible chip near the title — *"who actually does this thing"*. | Governance Strategist + Citizen agent reviews 2026-05-11 |
| `methodology_vintage` | GSDP base years, NFHS rounds, UDISE→UDISE+ — methodology shifts are the leading source of bogus year-over-year deltas. | Governance Strategist review 2026-05-11 |
| `series_breaks[]` | Charts must refuse to compute trends across breaks; until they do, at least surface the break visually. | Governance Strategist review 2026-05-11 |
| `icon` | Visual taxonomy across categories; lets the citizen orient inside a long category page. | UI/UX review 2026-05-11 |

## Consequences

- **Data review burden moves to the editorial layer**. Adding an indicator now requires answering "is this comparable across states?" and "where is this attributable?" before publication. That is a *good* burden — it forces the question that civic data sites usually duck.
- **The renderer becomes a critical path**. A bug in `IndicatorChoropleth.svelte` blocks every indicator. Mitigation: 22 vitest cases pin the pure helpers in `indicators.ts` (`uniqueTimes`, `rollupByEntity`, `formatValue`, `fillForValue`, etc.); the Svelte template is exercised on every state-overview page in dev.
- **Schema versions multiply**. Every minor field needs a changelog entry; every consumer fixture needs `$schema_version` bumped. Lived with via the strict validator and the additive-only minor-bump policy.
- **Per-indicator overrides are deferred**. If a future indicator genuinely needs a custom visual (e.g. an electoral-swing arrow chart), it will live as a sibling component, not a flag on the artifact. The indicator system is not the universal viz toolkit; it is the default surface for "value over space and time".

## Related

- [ADR-0002](0002-provenance-as-sources-list.md) — `sources[]` is mandatory on every artifact, including indicators.
- [ADR-0014](0014-sqlite-emitter.md) — per-state per-topic SQLite topology that indicators will project into.
- [ADR-0019](0019-dataset-topology-and-column-discipline.md) — column-naming discipline for the SQL projection.
- [`docs/architecture/frontend/indicators.md`](../frontend/indicators.md) — implementation reference for the renderer.
- [`docs/concepts/cross-state-comparison.md`](../../concepts/cross-state-comparison.md) — what cross-state comparison means once we have this contract.
- [`datasets/schemas/indicator.schema.json`](../../../datasets/schemas/indicator.schema.json) — the schema itself.
