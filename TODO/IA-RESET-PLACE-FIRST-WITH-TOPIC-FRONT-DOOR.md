# IA Reset — Atlas of Places, with a Topic Front Door

**Status**: Strategy approved (2026-05-11). **P1 + P2 complete (2026-05-11)** — catalogue contract shipped; state hub reads sections from catalogue; AcGenMay2026 no longer leaks into citizen-visible chrome; state list decoupled from election-data availability. Validator green, 39 vitest + 144 backend pytest pass.
**Correction Level**: 5 (design consultation) for the spine choice; subsequent phases are L2/L3.
**Supersedes**: the IA portion of [TODO/SOCIO-ECONOMIC-EXPANSION.md](SOCIO-ECONOMIC-EXPANSION.md) §6 — this doc closes the spatial-first vs indicator-first question.
**ADR**: [ADR-0022](../docs/architecture/decisions/0022-place-first-ia-with-topic-catalogue.md). **Guardrail**: [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md).

---

## TL;DR

yen-gov's IA stays **place-first** (`/s/:state` is canonical), but gains a **first-class Topic Front Door** (`/t` index + `/t/:topic` national landings) and a typed **topic catalogue contract** that powers both surfaces from data, not Svelte literals. Election remains a named first-class section group, not "just another topic." Constitutional honesty (Seventh Schedule list, state tier, peer sets) is mandatory chrome on every cross-state surface.

This is the disciplined subset of "Spine 1 (Atlas of Places)" with Spine 2's strongest move grafted in (national topic landings as a top-nav peer). Spine 3 (two-doors hybrid) was rejected on canonical-URL grounds.

---

## Why this spine

Four persona reviews ran in parallel. Dissents surfaced:

| Persona | Vote | Core argument |
|---|---|---|
| Citizen User | Spine 3 | Both place-first (Lakshmi) and topic-first (Arjun) citizens land on a working first screen. |
| Architect (Hohpe) | Spine 1 + topic-catalogue contract | Spine 3's "two paths, one URL" is a footgun for a static SPA. Spine 2 invites taxonomy creep into `indicator.schema.json`. |
| UI/UX Lead | Spine 1 + `/t` index | First-pixel speed; lowest bespoke-chrome temptation; shortest maintainer checklist. |
| Governance Strategist | Spine 2 | Spine 1 "encodes a federal falsehood" by listing State, Union, and Concurrent subjects as siblings under one CM. Spine 2's URL telegraphs constitutional location. |

**Resolution**: keep place as the canonical spine (Architect/UX), graft a first-class topic surface (Governance), surface List-badges + peer-set filters everywhere comparisons happen (Governance), keep election artifacts in their own schema family (Architect). Citizen's Spine 3 vote is honoured by making both place and topic top-nav peers, without the dual-URL cost.

---

## Non-negotiable principles

1. **Place is the canonical spine.** `/s/:state` is the resource. No dual URLs. No `/in/s/tn/t/fiscal` intersection routes.
2. **Topic catalogue is a typed contract from day one.** Even before any UI consumes it, the schema and JSON exist and validate. Powers state-hub section nav, `/t` index, and `/t/:topic` landing — all from the same data.
3. **Schema is the design system** (UI/UX standing position, formalised). The closed renderer set is `MapChoropleth`, `IndicatorChoropleth`, `IndicatorRanked`, `IndicatorSmallMultiples`, `TimeSeriesLine`, `CoverageBadge`. New components require an ADR. No bespoke per-topic chrome ships.
4. **Election artifacts keep their schemas.** Polymorphic dispatch via `artifact_kind` in catalogue entries; no forcing election results into long-form indicator rows.
5. **`indicator.schema.json` does NOT gain a `topic` field.** Topic membership lives in the catalogue (Canonical Data Model, separate from the fact table). Architect's hard line.
6. **Seventh Schedule list badge is mandatory** on every topic header (`List: State / Union / Concurrent / N/A`). Cross-state ranking on a Union-list subject requires a banner: *"This subject is administered by the Government of India; state-level variation reflects implementation, not policy authority."*
7. **State tier is a chart-level filter**, not just decoration. Default peer set for fiscal indicators = General-category; UTs and special-category appear in separate panels.
8. **`AcGenMay2026` never appears in user-visible chrome.** Display string is *"Tamil Nadu Assembly · May 2026"* everywhere. Code lives in data files only.
9. **`/compare` is a tool route, not a third spine.** `/compare?i=fiscal/debt&states=tn,ka` — shareable, generic, single route family.
10. **Home map theme-switch is loud, not silent.** Animated legend swap, persistent caption, URL param. Default theme defers to current event window when one is live.

---

## Phased migration

| Phase | Level | Ships | Doesn't change |
|---|---|---|---|
| **P1 — Catalogue contract** ✅ | L3 | `topic-catalogue.schema.json` v1.0; `topic-catalogue.json` populated; ADR-0022; guardrail doc `docs/concepts/schema-is-the-design-system.md`. **Done 2026-05-11.** | No UI changes. Validator green. |
| **P2 — De-jargon and de-couple** ✅ | L2 | `frontend/src/lib/catalogue.ts` (typed loader). `Home.svelte` header no longer says "showing event AcGenMay2026". `Home.svelte` + `ScopePicker.svelte` use catalogue-aware state availability (any national-scope indicator → all states available). `StateOverview.svelte` indicator sections come from the catalogue in catalogue order (fiscal first). **Done 2026-05-11.** | Routes unchanged. Election sections in StateOverview unchanged. Home India-map theme still election (P5 work). |
| **P2.5 — Per-state event identity + government as primary anchor** ✅ | L4 | `election-events.schema.json` v1.0 + `election-events.json` (15 states); `governments.ts` + `election-events.ts` loaders; deletion of global Election dropdown from `ScopePicker`/`scope.svelte.ts`; per-state `defaultEventForState(state)` resolution at every routes-side site that previously hardcoded `AcGenMay2026` (Constituency, Party, Explore, StateOverview, LeftRail); "Your government" card with President's Rule / Governor's Rule / interim regimes; recency banner (<90 days post-poll); `data_status: pending_upstream` honest copy for Bihar 2025; CI consistency tests (`test_election_events_catalogue_matches_backend_registry`, `test_election_events_default_uniqueness_and_data_status_alignment`). ADR-0023 + `docs/concepts/government-vs-election.md`. **Done 2026-05-11.** | Routes unchanged. Election Compare/Psephlab routes unchanged (already took `:event`). Home India-map theme still election (P5 work). 10 of 15 states still need `cm_terms.json` files (graceful degradation in place). |
| **Ingest gate** | — | Central transfers to states (FC devolution + GST compensation + CSS releases), FY15–FY26 (RBI State Finances Statement 8 + Union Budget transfers statement). **Blocks P3.** | — |
| **P3 — Topic Front Door** | L3 | New routes `/t` and `/t/:topic`. Top-nav becomes 3 peers (Atlas · Topics · About). List-badge component. Peer-set filter on Ranked + Choropleth. Union-list banner. | State hub layout unchanged. Election routes unchanged. |
| **P4 — Generic Compare** | L3 | `/compare?i=…&states=…` route using existing renderers. | Election Compare stays at `/compare/:state/:event`. |
| **P5 — Home theme switch** | L2 | Animated legend swap, captioned theme chip, URL-param theme. | Map engine unchanged. |

**P1 alone is the option-preserving move** — it ships the contract before any pivot is forced. If the team later disagrees and wants Spine 2 (topic-first), P1 makes it a route-generation change, not a re-architecture.

---

## Deferred (need evidence, not now)

- Faceted search vs. catalogue browsing — defer until ≥30 indicators ship.
- District- and constituency-level indicator rendering — defer until a sub-state dataset arrives.
- Multi-event support in scope picker — **deleted** in P2.5: per-state event resolution replaces the global dropdown (ADR-0023). Multi-event browsing is a per-state surface (`/s/<state>/elections[/<event_id>]`, deferred to P2.6 with B4 below).
- CSV / API export — defer until a researcher actually asks.
- **P2.6 — Per-state election history routes (B4)**: `/s/<state>/elections` (chip strip of all events) + `/s/<state>/elections/<event_id>` (specific event view). Defer until ≥1 state has ≥2 events ingested (LS-2024 sliced separately, or a 2027 by-election). Today every state has exactly one assembly event; the chip strip would have one chip and the route segment would be cosmetic.
- **P2.7 — Backfill 10 missing `cm_terms.json` files**: Andhra Pradesh, Arunachal Pradesh, Bihar, Haryana, Maharashtra, Odisha, Sikkim, Jharkhand, NCT of Delhi, J&K, Puducherry. Match the depth of the existing TN/KL/AS/WB files (terms back to ≥1989, references to ECI Statistical Reports per term). Authoring task that needs Wikipedia + ECI cross-checking, not code; do in a focused session to avoid factual errors.
- Government-term overlay band on time-series charts (the election ↔ governance link the Strategist named) — horizontal capability, park as Phase-7 component spec.
- Composite indices — permanently off the roadmap.

---

## Open questions — resolved 2026-05-11

1. **Catalogue location** → `datasets/reference/in/topic-catalogue.json`. Treated as reference data, validated by the same pipeline as states.json.
2. **List enum** → minimal `state | union | concurrent | na`. Edge cases (police, paramilitaries) handled by explicit topic-level notes for now; revisit if a real conflict surfaces.
3. **Default Home map theme** → **NOT elections.** A featured social-welfare or coverage indicator (fiscal first today; education / health when ingested). User-mandated doctrine: "do not make elections alone first-class citizens — they are one of many indicators; social welfare should be the first-class citizen." Documented in ADR-0022 §Doctrine and `docs/concepts/schema-is-the-design-system.md`. Implementation deferred to P5; rule recorded.
4. **`/s/:state` hero** → generic hero composed only from catalogue entries with `featured: true`, rendered via existing `IndicatorChoropleth` thumbnails. No bespoke chrome. Implementation in P2. Note: under the doctrine above, election artifacts are NOT featured — the hero shows welfare indicators, not election results.

## Doctrine (load-bearing, user-mandated 2026-05-11)

**Elections are one indicator family among many. Social-welfare topics are first-class.**

- Catalogue order leads with welfare topics (fiscal, future: education, health, livelihood). Elections appears in the list, never at the top.
- Elections is `featured: false` in the catalogue. It does not appear in the state-hub generic hero or as the home India map's default theme.
- Election rendering capability is unchanged — Psephlab, per-AC, party page, election Compare all keep working. Demotion is in **prominence**, not capability.
- Any feature that would make an election-only surface the lead view on a cold landing is rejected on doctrinal grounds. Recorded in [ADR-0022](../docs/architecture/decisions/0022-place-first-ia-with-topic-catalogue.md) §Doctrine and [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) §Companion doctrine.

---

## Catalogue contract sketch (for P1 ADR)

Strawman, not final:

```jsonc
{
  "$schema": "https://yen-gov.github.io/schemas/topic-catalogue.schema.json",
  "$schema_version": "1.0",
  "sources": [],            // hand-authored per CLAUDE.md §12
  "topics": [
    {
      "id": "fiscal",
      "title": "Fiscal capacity",
      "list": "state",      // Seventh Schedule: state | union | concurrent | na
      "icon": "landmark",
      "summary": "How states raise, borrow, and spend.",
      "artifacts": [
        { "kind": "indicator", "id": "fiscal/outstanding_debt_pct_gsdp", "default": true, "featured": true },
        { "kind": "indicator", "id": "fiscal/gross_fiscal_deficit_pct_gsdp" }
      ]
    },
    {
      "id": "elections",
      "title": "Elections",
      "list": "na",         // process, not a Seventh Schedule subject
      "icon": "vote",
      "artifacts": [
        { "kind": "election", "id": "AcGenMay2026", "display": "Tamil Nadu Assembly · May 2026", "default": true }
      ]
    }
  ]
}
```

Renderer dispatches on `kind`. Schema enforces non-empty `topics[]`, `list ∈ enum`, `artifacts[].kind ∈ {indicator, election, feature_collection}`, ID patterns.

---

## Audit findings (reference)

Election-coupled today: 7 of 9 routes; 5 of 5 LeftRail tools (in framing); 9 of 11 StateOverview sections.
Already generic and reusable: `MapChoropleth`, `IndicatorChoropleth`, `IndicatorRanked`, `IndicatorSmallMultiples`, `IndicatorIcon`, `SourceList`, `ChartTooltip`, `colors/store`, `states.svelte.ts`, `indicators.ts`.
Generic indicator artifacts shipped: `energy/installed_mw_by_state`, `fiscal/outstanding_debt_pct_gsdp` (35 states × 19 fiscal years).

Full audit lives in conversation history (2026-05-11 IA reset session); migrate into `docs/architecture/frontend/information-architecture.md` as part of P1.
