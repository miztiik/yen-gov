# ADR-0045: Grapher-catalogue split — render fields move out of canonical catalogues

**Last Updated**: 2026-05-26
**Status**: Accepted
**Deciders**: User (autonomous mandate, 2026-05-26 — "visualization is bleeding into storage; renderer rules belong in a frontend-owned grapher catalogue") + Gregor (contract seam, per CLAUDE.md §0a) + Hans + Max (data shape — confirm what stays on canonical).
**Refines**: [ADR-0020](0020-indicator-artifact-as-data-contract.md) — the indicator artifact remains the data contract; this ADR carves out the render-shape fields into a sibling catalogue.
**Plan reference**: [TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md](../../../TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md) PR-A1 (this ADR) → PR-A3a (additive grapher catalogue) → PR-A3b (reader migration) → PR-A3c (rip render fields from canonical).

## Context

Today the canonical indicator catalogue ([datasets/schemas/indicator-catalogue.schema.json](../../../datasets/schemas/indicator-catalogue.schema.json)) and the topic catalogue ([datasets/schemas/topic-catalogue.schema.json](../../../datasets/schemas/topic-catalogue.schema.json)) carry render-shape fields:

- `indicator-catalogue.schema.json`: `renderer_rules` (controlled-vocabulary array; ~30 livestock-block rows populate it).
- `topic-catalogue.schema.json`: `chart_type` + `dimension` (per artifact ref).
- Legacy per-shard `indicator.schema.json` (v4.4, under `datasets/indicators/in/<family>/`): `chart_type`, `default_mode`, `facet_labels`. Slated for deletion in PR-D8 once Phase D rips the 69 legacy shards.

The fan-out is three schemas, not one. The earlier draft of the rip plan mistakenly believed all three lived on the canonical catalogue (the §1bis pre-flight caught this); the split-by-schema below is the corrected scoping.

These fields encode HOW the data should render, not WHAT it is. They couple the canonical data store to today's frontend chart taxonomy. Two failure modes follow:

1. **Storage-layer churn on UX iterations.** A designer change to "stacked area becomes default for fuel-mix on `/t/energy`" touches `topics.json` (`chart_type: "stacked-trend"` → `chart_type: "stacked-area"`), regenerates a parquet, requires a 5-gate DoD on the BACKEND, and lands as a data-shape PR. Wrong layer.
2. **Render-vocabulary drift across schemas.** `chart_type` on the legacy per-shard schema, `chart_type` on the topic catalogue, and the frontend's `RendererRuleSlug` union in [frontend/src/lib/indicators.ts](../../../frontend/src/lib/indicators.ts) are three separate authorities that all answer the same question. They drift; no single owner is the source of truth.

OWID's `Grapher` is the precedent for the separation: a `Variable` (data) carries no chart hints; a `Chart` config (render) is a sibling artifact authored by the visualisation team. yen-gov is small enough not to have separate teams, but the schema seam is the same.

## Decision

**Render-shape fields MUST live in a frontend-owned grapher catalogue at `datasets/grapher/`, not on canonical or topic catalogues.**

### New schemas (PR-A3a, additive)

- [datasets/schemas/grapher-indicator-render.schema.json](../../../datasets/schemas/grapher-indicator-render.schema.json) v1.0 — per indicator: `chart_type`, `default_mode`, `renderer_rules[]`, `facet_labels{}`.
- [datasets/schemas/grapher-topic-render.schema.json](../../../datasets/schemas/grapher-topic-render.schema.json) v1.0 — per `(topic_id, indicator_id)` tuple: `chart_type`, `dimension`.

Seed files:

- [datasets/grapher/indicator_render.json](../../../datasets/grapher/indicator_render.json) — seeded from today's `indicator-catalogue.renderer_rules` + 69 legacy per-shard `chart_type` / `default_mode` / `facet_labels`.
- [datasets/grapher/topic_render.json](../../../datasets/grapher/topic_render.json) — seeded from today's `topic-catalogue` per-ref `chart_type` + `dimension`.

The grapher catalogue is read by the frontend at build time (or HMR module-graph fetch in dev). It is NOT read by any backend write path. It IS validated by Tier-A.

### Schema changes (PR-A3c, deletions; v2.0)

- `indicator-catalogue.schema.json` v2.0: DELETE `renderer_rules`. Bump `x-changelog`.
- `topic-catalogue.schema.json` v2.0: DELETE `chart_type` + `dimension`. Bump `x-changelog`.
- Legacy per-shard `indicator.schema.json` (v4.4): `chart_type` / `default_mode` / `facet_labels` STAY ALIVE until PR-D8 deletes the schema entirely. Don't double-cut — the legacy schema is on the rip queue.

### Reader migration (PR-A3b)

Every frontend read-site for the removed canonical fields routes through [frontend/src/lib/grapher/catalogue.ts](../../../frontend/src/lib/grapher/catalogue.ts) (new) instead:

| Today | After PR-A3b |
| --- | --- |
| [frontend/src/lib/topic-dispatch.ts](../../../frontend/src/lib/topic-dispatch.ts) L41 `artifact.chart_type` | `grapherTopicRender(topic_id, indicator_id).chart_type` |
| [frontend/src/lib/catalogue.ts](../../../frontend/src/lib/catalogue.ts) L71-L72 `chart_type` type | dropped; surface via grapher catalogue |
| [frontend/src/lib/charts/stacked-trend/adapter-indicator.ts](../../../frontend/src/lib/charts/stacked-trend/adapter-indicator.ts) L27, L129 `default_mode` | `grapherIndicatorRender(id).default_mode` |
| [frontend/src/lib/StackedTrendArtifact.svelte](../../../frontend/src/lib/StackedTrendArtifact.svelte) L97 `facet_labels` | `grapherIndicatorRender(id).facet_labels` |
| [frontend/src/lib/humanise.ts](../../../frontend/src/lib/humanise.ts) L4-L13 fallback chain | reads grapher first, falls through to title |
| [frontend/src/routes/TopicLanding.svelte](../../../frontend/src/routes/TopicLanding.svelte) L216 + L249 `dimension` | `grapherTopicRender(topic_id, indicator_id).dimension` |
| [frontend/src/lib/indicator-card.ts](../../../frontend/src/lib/indicator-card.ts) L101 + [frontend/src/lib/IndicatorCard.svelte](../../../frontend/src/lib/IndicatorCard.svelte) L276 `renderer_rules` | `grapherIndicatorRender(id).renderer_rules` |

Parity tests in [frontend/src/lib/grapher/catalogue.parity.test.ts](../../../frontend/src/lib/grapher/catalogue.parity.test.ts) (ships with PR-A3a) assert that every indicator the old reader knew about returns identical values through the grapher catalogue.

## Consequences

**Positive:**

- Canonical data store stops shipping UI hints. Designer changes to chart shape do not touch backend pipelines.
- One owner per question: data shape on canonical, render shape on grapher.
- The grapher catalogue is `tools/`-class — a frontend artifact citizens never see directly; iteration cost drops.
- Schema-version drift between three authorities collapses to one (grapher).

**Negative:**

- One extra read step in every chart path (grapher-catalogue lookup). Caught by parity tests; the lookup is O(1) against a preloaded map.
- 69 legacy shards still carry `chart_type` + `default_mode` + `facet_labels` until PR-D8 deletes them. Documented; not double-cut.
- Frontend allowlist learns one more import seam ([frontend/src/lib/grapher/catalogue.ts](../../../frontend/src/lib/grapher/catalogue.ts)).

**Permanent guardrails** (shipped in PR-Z1):

- Guardrail #2: `indicator-catalogue.schema.json` MUST NOT carry `renderer_rules` / `chart_type` / `default_mode` / `facet_labels` / `dimension`. Enforced by schema v2.0 — those fields are simply absent; contract test rejects any add.
- Guardrail #3: `topic-catalogue.schema.json` MUST NOT carry `chart_type` / `dimension`. Same enforcement.

## Cross-refs

- [ADR-0020](0020-indicator-artifact-as-data-contract.md) — indicator artifact is the data contract; this ADR carves out render.
- [ADR-0022](0022-place-first-ia-with-topic-catalogue.md) — topic catalogue stays; render fields ride elsewhere.
- [ADR-0030](0030-canonical-store-duckdb-wasm.md) — canonical store is unchanged.
- [ADR-0044](0044-grain-over-entity.md) — companion: entity-grain moves off the id slug.
- [docs/concepts/schema-is-the-design-system.md](../../concepts/schema-is-the-design-system.md) — the schema-is-the-design-system rule is preserved; "schema" now means the (canonical + grapher) pair, not canonical alone.
