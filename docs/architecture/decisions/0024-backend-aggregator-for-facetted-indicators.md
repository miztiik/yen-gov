# ADR-0024: Backend Aggregator (not frontend adapter) for facetted indicators

**Last Updated**: 2026-05-14
**Status**: accepted

## Context

The new `StackedTrend` chart primitive (see [`docs/architecture/frontend/charts/stacked-trend.md`](../frontend/charts/stacked-trend.md)) consumes either an election-results time-series or a single facetted indicator artifact (long-form rows where each row carries a `facet` discriminator, per [ADR-0020](0020-indicator-artifact-as-data-contract.md)).

The energy proof-of-value needs to render a per-state stacked bar of installed capacity by fuel source (coal, gas, hydro, nuclear, solar, wind, biomass, other_re). The current backend ships **eight separate** indicator artifacts under `datasets/indicators/in/energy/installed_capacity_*_mw.json` — one per fuel source. None carries a `facet` field; each is a standalone single-source indicator.

Two paths to feed this into `StackedTrend` were considered:

- **Option A — Frontend multi-file adapter.** The `StackedTrend` adapter fetches all eight artifacts in parallel, joins them by `entity_id` + `time`, synthesises a facetted view-model in-browser. No backend change.
- **Option B — Backend Aggregator.** A new backend composer reads the eight artifacts and emits a single new `installed_capacity_by_source_mw.json` with `facet` rows. The frontend adapter reads ONE file. Standard Pipes-and-Filters / Aggregator pattern.

## Decision

Adopt **Option B**: build the backend Aggregator (`backend/yen_gov/composers/energy_capacity_by_source.py`) and emit the composed artifact in the same commit as the chart.

## Why

### 1. Adapter composition is the wrong layering (Holy Law #5)

`StackedTrend`'s adapter is a **Message Translator**: one upstream shape → one canonical view-model. Composition (joining N upstream artifacts into one) is **Aggregator** territory. Pushing aggregation into the translator:

- conflates two unrelated patterns at the same boundary,
- bakes a precedent that "the frontend adapter can join datasets" (it can't — it translates one),
- makes the next composed indicator (fiscal heads, scheme outlays, sector employment) face the same ambiguity: backend or adapter? The right answer must be one place.

The first chart primitive establishing the canonical model is the worst place to shortcut the canonical model.

### 2. Backend Aggregator is reusable (and not as small as it looks)

The composer happy-path is ~80 lines: read 8 JSON files, validate each against `indicator.schema.json` v1.2, build a dict keyed `(entity_id, time, fuel)`, emit one `installed_capacity_by_source_mw.json` with `facet ∈ {coal, gas, hydro, nuclear, solar, wind, biomass, other_re}` per row.

Realistic with all production concerns — schema-validation of every input, key-join across mismatched period coverage, source-array deduplication and ordering, `availability` derivation per cell, `unit_changed_at` detection across upstream methodology vintages, output validation, plus pytest suite against real fixtures (Holy Law #7) — this is **150–250 lines of Python plus a similarly-sized test file**. Half-day to one-day of work, not a half-hour. The pattern repeats verbatim for every future composed indicator (fiscal heads, scheme outlays, sector employment), so the muscle is reusable.

### 3. The composed artifact is itself the right citizen-facing thing

Even outside the StackedTrend use case, "installed capacity by source" is a more useful artifact than eight separate single-source artifacts. The `/explore` page can SELECT FROM it; CSV export is one download not eight; ranking states by their renewable share is a single query. Building the composed artifact serves the broader system, not just one chart.

### 4. Provenance is cleaner

The composed artifact's `sources[]` is the union of all eight upstream `sources[]`, captured at composer-run time with one `fetched_at` per upstream. This is the canonical multi-entry shape per CLAUDE.md §12. A frontend adapter would have to merge sources at render time, repeatedly, on every page load — a pure waste, and the merge logic would itself be untested code on the hot path.

### 5. The cutoff lives where it belongs

The composer doesn't apply the rollup (the cutoff is a view decision, not a data fact — see the chart doc's "Top-N + coverage-ceiling rollup" section). The composer just facetises. The frontend adapter still owns the rollup, with the configured cutoff. Each layer does exactly one thing.

## Reconciliation with the actual CEA per-fuel files (added 2026-05-14)

The doc's earlier draft assumed eight leaf fuel categories (`coal, gas, hydro, nuclear, solar, wind, biomass, other_re`). The actual `datasets/indicators/in/energy/installed_capacity_*_mw.json` set is **seven** files and they are not all leaves of the same tree:

| File | Role | Use in stack? |
|---|---|---|
| `installed_capacity_coal_mw.json` | leaf (subset of thermal) | yes |
| `installed_capacity_gas_mw.json` | leaf (subset of thermal) | yes |
| `installed_capacity_hydro_mw.json` | leaf (large hydro only) | yes |
| `installed_capacity_nuclear_mw.json` | leaf | yes |
| `installed_capacity_renewable_mw.json` | umbrella (solar + wind + small hydro + biomass + WtE per MNRE) | yes (kept as one bucket — CEA does not publish the leaf split per state on the IC sheet) |
| `installed_capacity_thermal_mw.json` | umbrella (coal + lignite + gas + diesel) | NOT in stack — used to derive `other_thermal = thermal − coal − gas` (the lignite + diesel residual) |
| `installed_capacity_total_mw.json` | grand total | NOT in stack — used as a cross-check against the sum of the leaf facets |

**Composer leaf facets:** `coal, gas, nuclear, hydro, renewable, other_thermal`. Six categories; sum equals the grand total within a per-cell tolerance. `other_thermal` is collapsed into a single `other` bucket per-state when the residual is < 0.5% of that state's total (most states have negligible lignite/diesel; TN, GJ, RJ are the meaningful exceptions).

**Anchor list:** the doc's `POWER_SOURCE_ANCHORS` is updated in lockstep — anchors keyed `coal, gas, nuclear, hydro, renewable, other_thermal`, plus the generic `OTHER` neutral grey already used by the chart for the post-rollup tail. The earlier `solar / wind / biomass / other_re` anchors are kept *commented out* in the source for the day CEA (or another upstream) publishes the leaf split, but they are not referenced by the v1 composer.

**Validation in the composer pytest:** for every `(state, time)` cell, `sum(leaf facets) ≈ total ± 0.5%`. A larger gap fails the build — that's the canonical "we silently dropped a fuel" guard.

## What this rules out

- **Per-fuel files as a permanent surface.** They remain on disk (no breaking change) but the citizen-facing chart consumes the composed artifact only. If a citizen-facing view wants only one fuel, it consumes the composed artifact filtered.
- **Frontend adapters that fan out fetches.** The adapter is one-input, one-output. If a future chart needs a join, build the composer first.
- **Pre-rolling the top-N in the backend.** The composer ships every fuel; the rollup is a view layer responsibility.

## Consequences

- New backend module: `backend/yen_gov/composers/energy_capacity_by_source.py` (the composer module itself), invoked from `backend/yen_gov/cli.py` as a `compose` subcommand and from the existing pipeline orchestration. Test fixture: `backend/tests/test_energy_capacity_composer.py`. The composers package is new (`backend/yen_gov/composers/__init__.py` + this file) and is the home for every future Aggregator.
- New emitted artifact: `datasets/indicators/in/energy/installed_capacity_by_source_mw.json` (validates against `indicator.schema.json` v1.2; declares `chart_type: "stacked-trend"`, `default_mode: "percent"`).
- The eight per-fuel files remain. They are not citizen-facing for the energy mix view; they remain consumable by other queries / future per-fuel pages.
- Sets the precedent for every future composed indicator (fiscal composition, scheme outlays, sector employment, demographic age-bands).
- Indicator schema bumps 1.1 → 1.2 in the same commit (additive: `chart_type`, `default_mode`).
- **Cost honesty:** the composer is a half-day to one-day of work once schema validation, source-array merging, availability derivation, unit-change detection, and a real-fixture pytest suite are factored in. Don't underestimate.

## Alternatives considered

### Option A — frontend multi-file adapter

**Rejected** because:

- Pushes Aggregator concerns into a Translator (Holy Law #5: structural fixes only).
- Repeats the join on every page load (waste).
- Sets a bad precedent for the next composed indicator.
- Provenance merging would happen at render time, untested and on the hot path.

The only argument for Option A was "ships faster". That argument loses to Holy Law #5.

### Option C — augment each per-fuel file with a `facet` field, leave them separate

**Rejected** because the chart still needs to fetch eight files; nothing structural changes; we've added complexity (every artifact has an unused `facet` field) without removing the join.

## Related

- [ADR-0020](0020-indicator-artifact-as-data-contract.md) — the indicator artifact contract this consumes.
- [`docs/architecture/frontend/charts/stacked-trend.md`](../frontend/charts/stacked-trend.md) — the chart consuming the composed artifact.
- [CLAUDE.md](../../../CLAUDE.md) §5 (structural fixes), §11 (schema versioning), §12 (provenance).
