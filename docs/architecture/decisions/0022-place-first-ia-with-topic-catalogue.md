# ADR-0022: Place-first IA with a topic-catalogue contract

**Last Updated**: 2026-05-11
**Status**: accepted
**Supersedes**: the IA portion of [TODO/SOCIO-ECONOMIC-EXPANSION.md](../../../TODO/SOCIO-ECONOMIC-EXPANSION.md) §6 (the spatial-first vs indicator-first question).
**Sequel**: [ADR-0023 — Election event identity is per-place; government-timeline is the citizen unit](0023-election-event-identity-per-place.md). The first concrete consequence of this ADR's "elections are one of many" doctrine was that `/s/<state>` 404'd for every state outside the May-2026 cohort because the global Election dropdown was a federal falsehood. ADR-0023 deletes that dropdown, makes per-state event resolution the contract, and promotes the government timeline to the citizen anchor.

## Context

yen-gov began as an election viewer. The 2026-05-11 mandate ([ADR-0020](0020-indicator-artifact-as-data-contract.md)) expanded scope to civic indicators: fiscal, energy, demographics, infrastructure, governance. By 2026-05-11 two non-election indicators were live (`energy/installed_mw_by_state`, `fiscal/outstanding_debt_pct_gsdp`) and a third — central transfers from the Centre — was queued. The generic `IndicatorChoropleth` / `IndicatorRanked` / `IndicatorSmallMultiples` renderers (also from ADR-0020) made *rendering* a new indicator costless, but *finding* one still required scrolling [`StateOverview.svelte`](../../../frontend/src/routes/StateOverview.svelte) past the election sections, where indicators were bolted on as inline-literal sections (`"National context"`, `"Fiscal capacity"`).

This created a navigation seam visible to anyone who scrolled, and made the IA itself the bottleneck for non-election expansion. The strategic question — what is the *primary axis* of yen-gov's site map (Place, Topic, or both)? — was open and explicitly marked Correction Level 5 in PLAN.md.

A single-session strategy review (2026-05-11) ran four persona reviews in parallel — Citizen User, Architect (Hohpe), UI/UX Lead, Governance Strategist — against three named candidate spines: Atlas of Places (place-first, evolution of current), Atlas of Subjects (topic-first), Two-Doors Atlas (hybrid two-axis). Dissents surfaced and were not papered over: Citizen voted Two-Doors; Architect and UI/UX voted Atlas of Places; Governance voted Atlas of Subjects. The Architect refused Two-Doors outright on canonical-URL grounds; the Governance Strategist refused unconstrained Place-first on the grounds that listing State, Union, and Concurrent subjects as siblings under one Chief Minister "encodes a federal falsehood".

## Decision

Adopt **Atlas of Places, with a Topic Front Door** — a disciplined subset of the place-first spine, with two non-negotiable concessions:

1. A **typed topic-catalogue contract** ships from day one — `datasets/schemas/topic-catalogue.schema.json` v1.0 + `datasets/reference/in/topic-catalogue.json` — even though the only initial consumer is the in-place section nav. This is the option-preserving move (Architect's "Spine 0"): if the team later pivots to topic-first, that becomes a route-generation change rather than a re-architecture.
2. A **first-class Topic Front Door** as a top-nav peer (`/t` flat index, `/t/:topic` national landings) is on the roadmap (Phase P3 in [TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md](../../../TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md)). Citizens whose first question is "compare states on X" no longer need to enter through a state.

### Doctrine: elections are one indicator family among many

**User-mandated 2026-05-11.** This is the most load-bearing decision in this ADR and supersedes anything else in this doc that contradicts it.

- Elections are **not** the spine of yen-gov. They are not the default theme. They are not a featured topic. They are not the lead section on `/s/:state` by default.
- **Social-welfare topics are first-class**: fiscal, education, health, livelihood, infrastructure. The home India map's default theme is a welfare or coverage indicator, not the latest election leader.
- The catalogue order in `topic-catalogue.json` reflects this: fiscal first, energy second, elections third (and not `featured: true`). Future welfare topics (education, health) lead the order as they are ingested.
- Election artifacts retain their full rendering capability (Psephlab, per-AC drill-down, party page, election Compare). Demotion is in **prominence**, not in **capability**. The catalogue's polymorphic `kind` lets election and indicator artifacts coexist without one subsuming the other.
- The Topic Front Door's `/t` index lists topics in catalogue order. Elections appears in that list; it does not lead it.
- Home-page India map default theme: a featured social-welfare or coverage indicator, never "latest election leader". A theme-switcher exists for citizens who want the election view, but the citizen who lands cold on `/` is shown welfare data first.

**Why this matters.** A site whose default surface is "who won the latest election" trains the citizen to read state performance through a partisan lens. yen-gov's civic purpose is the opposite: *who governs* is one question; *how well they govern* is the question that should land first. Putting elections on the spine — even with the cleanest IA in the world — quietly defeats that purpose.

### What is canonical and what isn't

- **Place is the canonical spine.** `/s/:state` is the resource. URLs do not duplicate. There is no `/in/s/tn/t/fiscal` intersection route. Topic landings (`/t/:topic`) are *peer surfaces* on the same data, not parallel resources.
- **Topic membership lives in the catalogue, not on the indicator artifact.** `indicator.schema.json` does not gain a `topic` field. The catalogue is a separate Canonical Data Model that maps topics → artifacts via polymorphic `{ kind, id }` references. This is the architect's hard line on taxonomy creep: the indicator schema describes the *fact*; the catalogue describes the *navigation*; they evolve independently.
- **Election artifacts keep their own schemas.** The catalogue's `artifacts[].kind` enum (`indicator | election | feature_collection`) lets the renderer dispatch; election results stay under `datasets/elections/` with `result.summary.schema.json` and `result.constituency.schema.json`. Forcing election-as-indicator was rejected as the Lossy Translator anti-pattern (per-candidate / per-AC structure does not survive long-form `(entity_id, time, value)`).

### What the catalogue carries

Each topic declares:

- `id` — URL slug (single-segment for top-level, slash-segmented for sub-topics).
- `title`, `summary`, `icon`, `featured` — citizen-facing chrome.
- `list` — Seventh Schedule location: `state | union | concurrent | na`. Mandatory. Drives the constitutional honesty banner.
- `peer_set_default` — default tier filter for cross-state ranked tables under this topic. For fiscal indicators, this is `general_category` (UTs and special-category states get separate panels).
- `artifacts[]` — polymorphic `{ kind, id, display?, default?, featured?, scope? }` references.

Citizen-visible code-strings are replaced via `display` (e.g. `"AcGenMay2026"` → `"Tamil Nadu Assembly · May 2026"`). Codes never appear in URLs the citizen sees.

### Constitutional honesty as a structural rule

- Every topic header must render a `List: <value>` badge sourced from the catalogue.
- Every cross-state ranking on a Union-list subject must render the banner: *"This subject is administered by the Government of India; state-level variation reflects implementation, not policy authority."*
- Every cross-state surface defaults to the topic's `peer_set_default` for filtering; UT and special-category panels appear separately when applicable.

These are not stylistic preferences. They are correctness invariants: a yen-gov page that ranks states on a Union-list subject without the banner has misled the citizen, regardless of how elegant the chart looks.

### Schema-as-design-system, formalised

Adopting this spine commits to a closed renderer set ([`docs/concepts/schema-is-the-design-system.md`](../../concepts/schema-is-the-design-system.md)). New topic landings, state-hub sections, and intersection views compose only from `MapChoropleth`, `IndicatorChoropleth`, `IndicatorRanked`, `IndicatorSmallMultiples`, plus thin chrome (`SourceList`, list-badge, peer-set filter, coverage badge). New component types require an ADR. Curated heroes, scrollytelling sections, and topic-specific chrome are rejected at PR.

The state-hub generic hero, where it exists, composes only from catalogue entries with `featured: true`, rendered via existing `IndicatorChoropleth` thumbnails — no bespoke code.

## Alternatives considered

### Atlas of Subjects (topic-first, Spine 2)

`/t/:topic` is the resource; `/s/:state` becomes a flat index of every topic with that state's data. Election results live as one topic among many.

**Arguments for**: Governance Strategist's first choice. Topic URLs telegraph constitutional location. Cross-state comparison is the default motion. Researcher workflows ("download all fiscal indicators") fall out for free.

**Arguments against**:

- *First-pixel speed*. The Citizen test (a TN voter the day after polling, on a 4G phone with a toddler) showed Lakshmi has to read English topic names before she can find her constituency. Spine 1 lets her tap her state on the map immediately.
- *Schema leak risk*. The natural temptation is to add `topic` to `indicator.schema.json` so `/t/:topic` "just works" without a side-file. Resisting that temptation requires the same catalogue contract this ADR ships, which means topic-first does not actually eliminate the catalogue — it just makes it the only source of truth.
- *Topic-landing chrome creep*. Each topic landing argues for a custom hero (Health wants a facility finder; Fiscal wants a stacked bar; Elections wants a leader map). UI/UX Lead's slip warning: five topics in, you have five micro-products.
- *Mobile topnav crowding*. 8 topics × overflow-menu pattern at small viewports.

### Two-Doors Atlas (hybrid, Spine 3)

Two equal axes Place + Topic, converging at intersection routes (`/in/s/tn/t/fiscal` ≡ `/in/t/fiscal/s/tn`).

**Arguments for**: Citizen User's first choice. Both place-first (Lakshmi) and topic-first (Arjun) citizens land on a working first screen.

**Arguments against**:

- *Canonical-URL footgun*. "Two paths, one resource" works in a server-arbitrated REST API; in a static SPA it means double the prerendered HTML, double the sitemap, split link equity in search, and a non-trivial test that says "these two routes render byte-equivalent payloads". Pay this cost only with evidence both audiences route differently. We don't have it.
- *Test surface*. ~600 routes (8 topics × 36 states/UTs × 2 axes) vs. ~50 for Spine 1.
- *Architect refused outright.* "An architecture-conference demo, not a contract a two-person team can keep honest across 50 indicators and a yearly election cycle."

The "two front doors" goal of Spine 3 is satisfied in the chosen spine by making the Topic Front Door a top-nav peer of the place-first home — without the dual-URL cost.

## Consequences

- **`indicator.schema.json` stays clean.** No `topic` field; no IA leakage into fact data. Future indicator additions remain a single-file change.
- **A new contract surface to maintain.** `topic-catalogue.json` is hand-authored taxonomy and a soft governance surface (who decides what "Energy" means?). Mitigated by keeping it small, validating it strictly, and committing changes deliberately. Per CLAUDE.md §12, hand-authored content carries an empty `sources: []` array — the commit message records rationale.
- **Polymorphic `kind` dispatch in the renderer.** The frontend will need a small dispatcher that, given a catalogue artifact reference, picks the right component. This is centralised in the catalogue-consuming layer; it does not propagate into individual renderers.
- **Election routes are unchanged.** Psephlab, per-AC drill-down, party page, election Compare all stay exactly where they are. The catalogue *references* election artifacts; it does not subsume them.
- **The state-hub section list becomes data-driven.** `StateOverview.svelte` stops carrying inline section literals (`"National context"`, `"Fiscal capacity"`) and reads its sections from the catalogue. Adding a new topic with state-scope artifacts adds the section automatically.
- **Constitutional honesty is enforced structurally.** The list-badge component reads from the catalogue; the Union-list ranking banner is a renderer-level guard, not opt-in. A maintainer cannot accidentally ship a Union-list ranked table without the banner.
- **The 8th fiscal indicator is a one-file change.** Drop the JSON artifact under `datasets/indicators/in/fiscal/`; if it should appear on `/t/fiscal`, add a one-line entry to the catalogue's `fiscal.artifacts[]`. No Svelte changes.
- **Phase ordering is fixed.** P1 (this ADR + the catalogue contract) → P2 (de-jargon `AcGenMay2026`, decouple state-list from election-data, state-hub reads catalogue) → ingest gate (central transfers) → P3 (Topic Front Door routes) → P4 (`/compare` tool route) → P5 (Home theme switch). See [TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md](../../../TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) for the full plan.
- **Reversibility preserved.** If the team later wants to pivot to topic-first, the catalogue is already the source of truth; only route generation changes. The pivot is no longer a Level-5 design call — it becomes a Level-3 routing change.

## See also

- [ADR-0020](0020-indicator-artifact-as-data-contract.md) — the indicator artifact contract this catalogue references.
- [ADR-0002](0002-provenance-as-sources-list.md) — `sources[]` discipline; empty-array convention for hand-authored content.
- [TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md](../../../TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) — phased migration plan, deferred questions, persona dissents on record.
- [docs/concepts/schema-is-the-design-system.md](../../concepts/schema-is-the-design-system.md) — the closed-renderer-set guardrail this ADR commits to.
- [datasets/schemas/topic-catalogue.schema.json](../../../datasets/schemas/topic-catalogue.schema.json) — the schema.
- [datasets/reference/in/topic-catalogue.json](../../../datasets/reference/in/topic-catalogue.json) — the populated catalogue.
