# IA Reset — Atlas of Places, with a Topic Front Door

**Status**: P1 + P2 + P2.5 + P3.1 + P3.2 + P3.3a + P3.3b + P3.3c + P3.3d + P4 + P5 complete (2026-05-13). The IA-reset spine is fully landed: Topic Front Door (`/t`, `/t/:topic` with `?peer=`), generic indicator Compare (`/compare?i=&states=&peer=`), grouped LeftRail with StatePill, and now the Home theme switch (`/?theme=election|indicator/<id>`) with animated caption swap. Validator green; vitest 9503/9503; svelte-check 0 errors (4 a11y warnings ignored per CLAUDE.md §0).
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
| **Ingest gate** | — | Central transfers to states (FC devolution + GST compensation + CSS releases), FY15–FY26 (RBI State Finances Statement 8 + Union Budget transfers statement). **Partial: 3 fiscal years (2023-24 Accounts, 2024-25 RE, 2025-26 BE) shipped as `fiscal/net_transfers_from_centre`. FY15+ historical extension still pending (backlog).** | — |
| **P3.1 — state-tiers reference + chrome** ✅ | L3 | `state-tiers.schema.json` v1.0 + `state-tiers.json` (11 tiers, 9 populated); `ListBadge.svelte`, `UnionListBanner.svelte`; `state-tiers.ts` loader (`fetchStateTiers`, `tierMembers`, `resolvePeerSet`, `nonEmptyTierIds`, `tiersForState`); `topic-catalogue.schema.json` bumped to v1.1 (per-artifact `peer_set_default`); `docs/concepts/peer-sets.md`; 5 contract tests in `test_datasets_integrity.py`. **Done 2026-05-12 (commit `7417743`).** | No route changes. |
| **P3.2 — PeerSetFilter wired** ✅ | L2 | `PeerSetFilter.svelte` (controlled component); `IndicatorRanked` + `IndicatorChoropleth` accept optional `peer_set_members?: string[] \| null`; `StateOverview.svelte` per-section overrides keyed `${topic.id}::${artifact.id}`; home_state always admitted to ranked even when not in peer set. **Done 2026-05-12 (commit `abe0087`).** | No route changes. |
| **P3.3a — TopicLanding** ✅ | L3 | `/t/:topic` route (`frontend/src/routes/TopicLanding.svelte`). National-scope view of one topic; closed renderer set; ListBadge + UnionListBanner + per-artifact PeerSetFilter; clear 404 panel for unknown topic id. **Done 2026-05-13 (commit `9d6b717`).** | LeftRail unchanged. |
| **P3.3b — TopicIndex** ✅ | L3 | `/t` route (`frontend/src/routes/TopicIndex.svelte`). Topics grouped by Seventh Schedule list (State / Concurrent / Union / Process); empty groups skipped; cards link to `/t/:topic`. **Done 2026-05-13 (commit `de5c007`).** | LeftRail unchanged. |
| **P3.3c — LeftRail rewrite** ✅ | L3 | Pure `rail-groups.ts` builder + 15-test vitest suite; `StatePill.svelte` replaces always-open `ScopePicker` (popover wraps the same picker); `LeftRail.svelte` renders four groups: My state / How states compare / Centre and states / Settings. Killed verbs (Explore, Analyze Trends, Psephlab, Compare-as-verb) documented in `docs/architecture/frontend/overview.md` rev 3. NO greyed dead links — "Side by side" is emitted only when scope+event both present. `url.topics()` / `url.topic(id)` builders added; TopicIndex/TopicLanding hrefs migrated. **Done 2026-05-13.** | Routes unchanged (no `/s` index added). Renderer set + P3.3a/b routes intact. |
| **P3.3d — polish** ✅ | L2 | `?peer=<peer-set-id>` deep-link state on `/t/:topic` (single global slot — overrides every artifact's catalogue default; per-artifact fidelity deferred); pure `topic-query.ts` parse/serialize + 10-test vitest suite; `PEER_SET_VALUES` runtime constant + `isPeerSet()` guard added to `catalogue.ts`; `TopicLanding` reads on mount + popstate, writes via `history.replaceState` on filter change; breadcrumb row (`Topics › <Topic title>`) replaces `← All topics`. Bad / unknown `?peer` values silently fall back to catalogue defaults. Keyboard polish folded into existing `<details>`/`<summary>` semantics (StatePill, breadcrumb is a `<nav aria-label="Breadcrumb"><ol>`). **Done 2026-05-13.** | Per-artifact `?peer.<artifact-id>=…` fidelity, route-level keyboard shortcut overlay. |
| **P4 — Generic Compare** ✅ | L3 | New `/compare` route (sits alongside the more-specific `/compare/:state/:event` election Compare). URL contract `?i=<indicator-id>&states=<slug-csv>&peer=<peer-set-id>` lives in pure `lib/compare-query.ts` + 17-test vitest suite. Empty state renders a catalogue-driven indicator chooser — not a 404 — so the rail can link in unconditionally. `IndicatorRanked` extended additively with `pinned_states?: string[] \| null`: pinned rows get the existing `compare` accent, sit at top in URL order, and bypass the peer-set filter (citizen never loses a state they explicitly asked for). State chip toggle row writes back via `history.replaceState`. New `url.compareIndicator()` builder; `Compare states` rail entry added under `How states compare` (always visible). Breadcrumb `Topics › Compare states`. **Done 2026-05-13.** | Per-state per-period overlays, multi-indicator side-by-side, in-row delta column. Election Compare unchanged. |
| **P5 — Home theme switch** ✅ | L2 | URL contract `/?theme=election` (default) or `/?theme=indicator/<artifact-id>` for any national-scope indicator in the catalogue. Pure `frontend/src/lib/home-theme.ts` (parse / serialize / default / options / caption) + 25-test vitest suite. `Home.svelte` mounts a `<select>` chip grouped by topic title (`Elections`, `Money & debt`, `Power & energy`, …), reads `?theme=` on mount + popstate, writes back via `history.replaceState`. Caption above the map (`India — …`) animates via Svelte `fade` inside `{#key caption}`; the map itself swaps inside a parallel `{#key current_value}` block so renderer mount/unmount is clean. Renderer dispatch: `election` → existing `IndiaMap` (party theme); `indicator/<id>` → existing `IndicatorChoropleth` with the artifact path. Bad / unknown `?theme=` falls back to default silently. Default theme = election; placeholder hook for future "current event window" detection (no `data_status: live` event exists today). **Done 2026-05-13.** | Map engine unchanged (still `MapChoropleth`); choropleth-feature renderers untouched; election-events recency check is a future enhancement, not a blocker. |

**P1 alone is the option-preserving move** — it ships the contract before any pivot is forced. If the team later disagrees and wants Spine 2 (topic-first), P1 makes it a route-generation change, not a re-architecture.

---

## Deferred (need evidence, not now)

- Faceted search vs. catalogue browsing — defer until ≥30 indicators ship.
- District- and constituency-level indicator rendering — defer until a sub-state dataset arrives.
- Multi-event support in scope picker — **deleted** in P2.5: per-state event resolution replaces the global dropdown (ADR-0023). Multi-event browsing is a per-state surface (`/s/<state>/elections[/<event_id>]`, deferred to P2.6 with B4 below).
- CSV / API export — defer until a researcher actually asks.
- **P2.6 — Per-state election history routes (B4)**: `/s/<state>/elections` (chip strip of all events) + `/s/<state>/elections/<event_id>` (specific event view). Defer until ≥1 state has ≥2 events ingested (LS-2024 sliced separately, or a 2027 by-election). Today every state has exactly one assembly event; the chip strip would have one chip and the route segment would be cosmetic.
- **P2.7 — Backfill 10 missing `cm_terms.json` files**: Andhra Pradesh, Arunachal Pradesh, Bihar, Haryana, Maharashtra, Odisha, Sikkim, Jharkhand, NCT of Delhi, J&K, Puducherry. Match the depth of the existing TN/KL/AS/WB files (terms back to ≥1989, references to ECI Statistical Reports per term). Authoring task that needs Wikipedia + ECI cross-checking, not code; do in a focused session to avoid factual errors.
- **P2.8 — Bootstrap `constituencies.json` for the remaining 22 states/UTs**: as of 2026-05-11 we have 14 of 36 states/UTs covered (12 ECI-Statistical-Report-ingested + 2 legacy Wikipedia-scraped). The other 22 (UP, MP, Karnataka, Gujarat, Rajasthan, Punjab, Telangana, Chhattisgarh, Goa, HP, Tripura, Mizoram, Meghalaya, Nagaland, Manipur, Uttarakhand, plus the smaller UTs) need either an ECI Statistical Report ingest *or* hand-authored bootstrap from the ECI Delimitation Order PDF. Preferred path: extend the eci_xlsx pipeline to cover earlier election years per state (one-time work — election results are frozen-in-stone after the SR is published). Not a blocker for current product since those states have no ingested election data either; tracked here so we don't lose it. See [docs/architecture/backend/sources-eci-vs-wikipedia.md](../docs/architecture/backend/sources-eci-vs-wikipedia.md) for the canonical-source doctrine.
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

---

---

## P3.3c — IA decision pending (BLOCKER, 2026-05-13)

> **RESOLVED 2026-05-13.** Decisions taken (see also commit message and `docs/architecture/frontend/overview.md` rev 3):
> 1. Group set → **Citizen-pure** (My state / How states compare / Centre and states / Settings).
> 2. State pill at top → **yes** (`StatePill.svelte`, popover wraps existing `ScopePicker.svelte`).
> 3. Side by side → **sub-item under "How states compare"**, emitted only when scope+event present (no greyed stub). Demoted from a top-level group because its only entry today (`/compare/:state/:event`) needs both.
> 4. Election Analytics / Psephlab → **killed from rail entirely**; reachable only from election artifacts on the state hub.
>
> Implementation: pure `rail-groups.ts` builder (15 tests) + `StatePill.svelte` + `LeftRail.svelte` rewrite. Original analysis kept below for memory.


The flat tool list (Explore / Analyze Trends / Psephlab / Compare / Settings) with three "Pick a state first" greyed stubs has to go. User direction (verbatim 2026-05-13):

> "this has to be reimagined - work with custom agents (as an example for different domain - dashboard - economic indicators, settings as major groups in the left and then sub items, but come with your own option)"

Four custom agents proposed shapes (full proposals captured in session transcript `81f198f8-dbce-4a7f-b6df-b27838d0f980.jsonl`). Summary:

| Proposer | Top-level groups | Verbs (Analyze/Psephlab/Compare) | ScopePicker |
|---|---|---|---|
| **Hohpe (Architect)** | Topics / Places / About | Killed — verbs are renderer choices, not nav nouns | Removed from shell, contextual on `/t/:topic` only |
| **UI/UX Lead** | Browse / Analyze / About | Kept as Analyze sub-items, never greyed (page prompts for scope) | Contextual sub-header, hidden on index pages |
| **Citizen User** | My State (pinned) / How states compare / Centre and states / Side by side / Settings | "Trends" inline per topic; "Psephlab" rename to Elections; "Compare"→"Side by side" top-level | Pinned "You're looking at: <State>" pill at top of rail |
| **Governance Strategist** | The Union / The States / The Process / Workspace | Compare→"Benchmark against peers"; Psephlab→"Election Analytics" | Contextual on States routes; hidden on Union routes; EventPicker on Process routes |

**Strong agreement across all four:**
1. Kill the global ScopePicker (root cause of "Pick a state first" tollgate).
2. Kill the greyed-out tool stubs (universally judged broken UX).
3. Vocabulary surgery: "Psephlab" is jargon; "Compare" is unanchored.
4. Groups + sub-items, not a flat list (matches user direction).

**Recommended hybrid (for user approval — NOT yet implemented):**

Rail:
- **You're looking at: <State> ▾** — contextual pill at top (Citizen #3). Empty state: "Pick your state".
- **Topics** group: All topics → `/t`; Money & debt → `/t/fiscal`; Power & electricity → `/t/energy`; Elections → `/t/elections`.
- **States** group: All states → `/s` (NEW); My state → `/s/<current>`; Side by side → `/compare/...` (no longer greyed).
- **About** group: About → `/about`; Settings → `/settings`; Repo → external.

ScopePicker: removed from the shell, surfaced inline as the "You're looking at:" pill.

Verbs:
- "Analyze Trends" → killed (already surfaced by `IndicatorSmallMultiples` inside every artifact).
- "Psephlab" → killed from rail; reachable from election artifacts as a contextual link.
- "Compare" → renamed "Side by side", under States group, no scope prerequisite.

### Decisions needed before P3.3c can start

1. **Group set** — accept hybrid (Topics / States / About) OR pick one of the four pure proposals?
2. **State pill at top** — yes (Citizen-style pinned context) OR remove entirely (Hohpe-pure)?
3. **Side by side / Compare** — keep as navigable sub-item OR kill until `/compare` lands in P4?
4. **Election Analytics / Psephlab** — kill from rail entirely (reachable only from election artifacts) OR keep as a sub-item under Topics → Elections?

Once decided, P3.3c becomes a contained Level-3 rewrite: one component (`frontend/src/lib/LeftRail.svelte`), no schema changes, optional new routes (`/s` index if Side-by-side stays).

---

## Session handoff (2026-05-13)

### Done this session
- **P3.1** shipped `7417743 feat(ia): P3.1 state-tiers reference data + ListBadge + UnionListBanner`.
- **P3.2** shipped `abe0087 feat(ia): P3.2 PeerSetFilter wired into IndicatorRanked + IndicatorChoropleth`.
- **P3.3a** shipped `9d6b717 feat(ia): P3.3a TopicLanding route at /t/:topic`.
- **P3.3b** shipped `de5c007 feat(ia): P3.3b TopicIndex at /t (Topic Front Door)`.
- 4 parallel custom-agent IA proposals collected for P3.3c (full text in session transcript).

### Files touched (this session)
- `datasets/schemas/state-tiers.schema.json` (NEW v1.0)
- `datasets/schemas/topic-catalogue.schema.json` (bumped 1.0→1.1, per-artifact `peer_set_default`)
- `datasets/reference/in/state-tiers.json` (NEW; 11 tiers, 9 populated)
- `datasets/reference/in/topic-catalogue.json` ($schema_version 1.1; `fiscal/net_transfers_from_centre` peer_set_default)
- `frontend/src/lib/state-tiers.ts` + `state-tiers.test.ts` (NEW; 12 cases)
- `frontend/src/lib/catalogue.ts` (PeerSet union widened, `resolvePeerSetDefault`, `displayForArtifact`, `indicatorPathForArtifact`)
- `frontend/src/lib/catalogue.test.ts` (+3 tests)
- `frontend/src/lib/ListBadge.svelte` (NEW)
- `frontend/src/lib/UnionListBanner.svelte` (NEW)
- `frontend/src/lib/PeerSetFilter.svelte` (NEW)
- `frontend/src/lib/IndicatorRanked.svelte` + `IndicatorChoropleth.svelte` (added optional `peer_set_members`)
- `frontend/src/routes/StateOverview.svelte` (per-section PeerSetFilter wiring)
- `frontend/src/routes/TopicLanding.svelte` (NEW — P3.3a)
- `frontend/src/routes/TopicIndex.svelte` (NEW — P3.3b)
- `frontend/src/main.ts` (registered `/t` + `/t/:topic`)
- `backend/tests/test_datasets_integrity.py` (+5 contract tests; module constants added)
- `docs/concepts/peer-sets.md` (NEW)

### Verified outcomes (last green run)
- `cd frontend; npm test` → 9357 / 9357 pass.
- `cd frontend; npm run check` → 0 errors, 4 a11y warnings (ignored per CLAUDE.md §0).
- `cd backend; python -m yen_gov validate` → green.
- Browser smoke: `/t` renders 3 groups; `/t/fiscal` renders artifacts with PeerSetFilter; `/t/no-such-topic` renders the 404 panel.

### Pending — clear next steps for new session

**Immediate (must answer before any code is written):**
1. Answer the 4 P3.3c IA decisions above.

**Then in order:**
1. **P3.3c** — implement chosen IA in `frontend/src/lib/LeftRail.svelte`. CLAUDE.md §13 mandates browser smoke on `/`, `/t`, `/about`, `/s/tamil-nadu` after the rewrite.
2. **P3.3d** — `?peer=…` deep-link state on `/t/:topic`; breadcrumbs.
3. **P4** — generic `/compare` route.
4. **P5** — home theme switch.
5. **Backlog** — P2.6 / P2.7 / P2.8 (see "Deferred" section above) + RBI transfers FY15+ historical extension.

### Important context for next session
- Custom agent registry (only valid names for `runSubagent`): `Gregor Hohpe (Architect)`, `Fowler (Engineering)` (added 2026-05-14 — Fowler + Beck combined persona, code-craft / evolutionary-engineering complement to Gregor, voice-friendly invocation token "Fowler"), `Hans (Governance)` (formerly `Governance Strategist`, renamed 2026-05-14 — Rosling + Roy + Bhattacharya combined persona, voice-friendly invocation token "Hans"), `Max (Indicator Scout)` (added 2026-05-14 — Roser + Ritchie OWID-style coverage strategist, upstream of Hans, voice-friendly invocation token "Max"), `Citizen User`, `Jony (UI/UX)` (formerly `UI/UX Lead`, renamed 2026-05-14 — Ive + Brichter combined persona, voice-friendly invocation token "Jony"), `Explore`. NOT registered: Election Strategist, Data Architect.
- `state-tiers.json` has one intentionally empty tier (`fc_horizontal_devolution_share_quintile`) pending RBI Statement 8 ingest. `nonEmptyTierIds()` filters it out so it won't appear in PeerSetFilter dropdowns.
- `topic-catalogue.json` currently has 3 topics (fiscal/State, energy/Concurrent, elections/Process). No Union-list topic yet → `UnionListBanner` code path is unexercised in browser smoke (component-tested only).
- "Pick a state first" greyed stubs in current LeftRail are the explicit anti-pattern P3.3c must remove.
