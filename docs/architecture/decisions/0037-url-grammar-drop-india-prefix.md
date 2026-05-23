# ADR-0037: URL grammar — drop the `/india/` prefix; state slug is the root

**Last Updated**: 2026-05-25
**Status**: accepted
**Amends**: [ADR-0028 (URL scheme — place-first cascade, flat indicator slug, path routing)](0028-url-scheme-place-first-flat-indicator-slug.md) — on the country-prefix question only; ADR-0028's place-first cascade doctrine, flat-indicator-slug doctrine, path-routing decision, no-vintage-in-URL decision, and collision-contract framing are all preserved.

## Context

ADR-0028 (2026-05-17) locked `/india/<state>/<ac>/<indicator>` as the canonical URL grammar after a five-voice debate (Gregor, Fowler, Jony, Hans, Max). The decision was correct at the time and was endorsed by the user verbatim: "we are over complicating. Country can directly be India... slash India slash delhi."

In practice, ADR-0028 was never implemented. The codebase shipped `/s/<state>/...` instead (the legacy `RedirectLegacyUrl.svelte` strangler-fig target became the live grammar). PR #172 (2026-05-25, `aa78203b`) audited and locked the shipped `/s/<state>/...` shape into a 42-test contract — codifying drift without resolving it.

On 2026-05-25 the user re-opened the question: "Having nicer URLs is important. In fact I thought it would be just an estate slug name, not even the slash-yes-slash-state. So can you have a conversation debate with all the agents together not independently and then come up to conclusion plan of how this thing can be tracked and updated. So we put this to rest one way or the other."

This ADR records the resolution.

## Decision

**Drop the `/india/` segment from ADR-0028's grammar. The state slug sits at the URL root.** Everything else about ADR-0028 stands.

### Final route grammar

| Surface | URL |
|---|---|
| Country home | `/` |
| State hub | `/tamil-nadu` |
| AC | `/tamil-nadu/mylapore` (pure name, no `167-` prefix per ADR-0028 §AC-slug) |
| District (when renderer ships) | `/tamil-nadu/chennai` |
| Indicator @ national | `/installed-capacity` |
| Indicator @ state | `/tamil-nadu/installed-capacity` |
| Indicator @ AC | `/tamil-nadu/mylapore/installed-capacity` |
| Topic index | `/t` |
| Topic landing | `/t/energy` |
| Per-state topic | `/tamil-nadu/t/energy` |
| Party-in-state | `/tamil-nadu/party/<slug>` |
| State explore | `/tamil-nadu/explore` |
| Election lab | `/lab/<state>/<event>` (existing surface; not relocated) |
| Election compare | `/compare/<state>/<event>` (existing surface; not relocated) |
| Cross-state indicator compare | `/installed-capacity` with compare-mode tab (Phase 3+) |
| Chrome | `/about`, `/settings`, `/disclaimer`, `/data-completeness`, `/compare` |

### Reserved positional tokens

`RESERVED = ["t", "compare", "about", "settings", "disclaimer", "data-completeness", "lab", "dev", "s", "ac", "party", "i", "explore"]`. No state slug, topic slug, indicator slug, or AC slug may equal any reserved token. The last six are retained reservations (`s`, `ac`, `party`, `explore` = legacy-redirect anchors; `i` = pre-reserved fallback for the future indicator-marker retrofit; `dev` = the existing dev-only Vite alias).

### Strengthened collision invariant

ADR-0028's contract was `indicator_slugs ⊥ {state_slugs ∪ district_slugs ∪ ac_slugs ∪ RESERVED_SEGMENTS}`. This ADR strengthens it to **5-way pairwise disjointness**:

```
urlIndicatorSlugs ⊥ stateSlugs ⊥ topicSlugs ⊥ acSlugsAcrossAllStates ⊥ RESERVED
```

`topicSlugs` was implicit in ADR-0028 (topics lived under `/india/<state>` so couldn't collide); without the `/india/` prefix topics need explicit guarding. `acSlugsAcrossAllStates` is the largest namespace (~4,123 names) and was missing from the disjointness rule as drafted; AC names include common nouns (`central`, `north`, `south`, `kalyan`) that will collide with future indicator slugs.

### Full-name state slug invariant (new)

Every state slug MUST be the slugified full English `display_name`. `/uttar-pradesh` not `/up`. `/madhya-pradesh` not `/mp`. Two precedents converge on this: Wikipedia (`/wiki/Uttar_Pradesh`) and data.gov.in (`/uttar-pradesh`) are the two URL surfaces a citizen has actually been trained on; ECI's `S24` and MoSPI's `UP` are URLs the citizen never reads. All 36 current state slugs derived from `datasets/taxonomy/entities.json` already meet this invariant; the test is a regression guard.

### Page chrome must carry entity-type framing

The URL `/<state>` reads as a place-fact (Wikipedia-trained mental model). For constitutional honesty (Delhi is NCT-UT not state; J&K became UT in 2019; Chandigarh + Lakshadweep + Ladakh are UTs without legislature), the state-hub page MUST render an `entity_type` badge (state | UT) under the H1 with the legislative-scope note where applicable, per [ADR-0022](0022-place-first-ia-with-topic-catalogue.md) constitutional-honesty rule. The URL alone cannot carry this; the page chrome closes it.

### Missing-scope behaviour

When a citizen visits `/tamil-nadu/<indicator>` for an indicator that exists in the catalogue but has no state-scope rows: **render a stub with a one-click deep link to the nearest scope where the indicator is published.** Never silent-redirect. Never 404. OWID precedent: `/grapher/<slug>?country=ATA` renders chart frame with "No data for this entity" and the country-picker visible. Wikipedia precedent: redlinks. The stub names the missing thing honestly: "installed-capacity (Tamil Nadu) — not published at state scope. See national: /installed-capacity."

### Cross-state indicator-compare surface

Lives on the indicator page itself, not at `/compare/<indicator>`. OWID precedent: `/grapher/co2-emissions-per-capita` IS the compare surface — the country-picker is a control on the chart, not a separate URL. The existing election-compare surface at `/compare/<state>/<event>` is a different beast (compares one event outcome across many states) and stays. The cross-state indicator-compare lands in Phase 3+ as a compare-mode tab on the indicator page.

## Five-voice digest

Sequential debate on 2026-05-25 (transcript and binding synthesis in [TODO/20260525-url-grammar-grammar-a-migration.md](../../../TODO/20260525-url-grammar-grammar-a-migration.md)). Convergence and dissent:

- **Jony (UI/UX, §0a authority on URL grammar):** chose Grammar A. Read-aloud test: "Tamil Nadu, Mylapore, installed capacity" — three nouns, zero scaffolding. ADR-0028's `/india/` was scaffolding for never-built country-multi-tenancy on a `.in` domain.
- **Hans (Governance):** ratified A. Added full-name slug invariant (Wikipedia + data.gov.in are the trained precedents; ECI codes + MoSPI abbreviations are negative precedents). Added entity-type badge constraint on page chrome. Methodology-break survival (Telangana from AP, 2014) is mildly better under A because URL carries the semantic mismatch.
- **Max (Indicator Scout, swing voice on OWID precedent):** ratified A with one amendment — strengthen the collision invariant to include `acSlugs` (largest namespace, was missing from ADR-0028). Missing-scope = stub-not-redirect-not-404 per OWID precedent. Cross-state compare collapses into indicator page per OWID precedent. 10k-indicator scaling = collision-safe today but test signals when `/i/<slug>` marker retrofit is due.

## Alternatives considered

1. **Keep ADR-0028 verbatim (`/india/<state>/...`).** Rejected — on a `.in` domain `/india/` reads as a stutter; yen-gov is India-only by [CLAUDE.md §0 non-goals](../../../CLAUDE.md); paying one segment of URL tax on every page for an optionality we don't have is what gets deleted.
2. **Keep the shipped `/s/<state>/...` grammar (Grammar B).** Rejected — `/s/` and `/ac/` are positional markers that don't disambiguate (state slugs ⊥ AC slugs by construction); markers that don't disambiguate read as scaffolding.
3. **Hive partition form `/s/in_s33/167/...`** (original rip-and-replace prompt §2). Rejected — Hive partition keys are a filesystem dialect, not a citizen sentence; already rejected by [slug.ts L3-5](../../../frontend/src/lib/slug.ts) and not re-litigated.
4. **Topic landing at root (`/energy` not `/t/energy`).** Rejected — even when topic slugs don't collide with state slugs today (they don't: `energy`, `fiscal`, `health` vs `tamil-nadu`, `gujarat`), dropping `/t/` forces the root resolver to consult three registries per navigation AND makes every future topic-name addition a state-collision audit. The 2 characters of `/t/` buy permanent topic-namespace freedom.
5. **Per-state topic at `/<state>/<topic>` (flattening the per-state `/t/`).** Deferred — pending user direction; current Phase 1 paths.ts ships `/<state>/t/<topic>` for collision-isolation parity with the top-level topic landing. Decision needed before Phase 2 route-table change.

## Consequences

**Good**

- URL is OWID-aligned on the load-bearing dimension (flat indicator slug, place-first cascade, path routing) and Wikipedia-aligned on the slug-as-entity dimension (the URL names what the page IS).
- One-segment state-swap (`/tamil-nadu/<indicator>` → `/kerala/<indicator>`) survives.
- Read-aloud test passes for every URL in the grammar (verified per Jony §3).
- Entity-rename/split survival is mildly better than B because URL is human-debuggable (verified per Hans §5).
- Collision detection is one Tier-A contract test reading four registries; failure mode is "rename the colliding slug, never add an exception."

**Bad**

- All shipped `/s/<state>/*` URLs change. Strangler-fig redirect (Phase 3) covers one release cycle then is deleted in Phase 4b. External citations created during Phase 2/3 window risk link-rot when the redirect retires.
- PR #172's 42-test contract on the `/s/<state>` shape becomes Phase 4 deletion target. Until then, both contracts coexist (PR #172's contract tests `url.ts`; this ADR's tests target the new `paths.ts`).
- AC slug shape change (`167-mylapore` → `mylapore`) requires resolver to look up AC by name not number. Phase 2 work.
- Per-state topic URL shape (`/<state>/t/<topic>` vs alternatives) is a deferred user-gate question.

## Migration

Four-phase strangler-fig per [TODO/20260525-url-grammar-grammar-a-migration.md](../../../TODO/20260525-url-grammar-grammar-a-migration.md):

- **Phase 1** (this PR): create `links.ts` with Grammar A builders + three Tier-A tests. Zero call-site migration. PR #172's 42-test contract stays green. The `paths.ts` module name is already taken by the runtime `DATA_BASE` prefix helper (unrelated concern); the new route-URL builders live in `links.ts` so the two responsibilities stay separated.
- **Phase 2**: add Grammar A routes alongside `/s/*` in `main.ts`. Internal `<a href>` callers migrate component-by-component from `url.ts` to `links.ts`. AC slug shape change ships here. AC namespace (4,112 names) joins the disjointness contract.
- **Phase 3**: `RedirectLegacyUrl.svelte` rewrites `/s/<state>*` to Grammar A. Cross-state compare collapses into indicator page. `url_slug` field on `taxonomy/indicators.parquet` lands here (per Max §3i). Indicator slugs join the disjointness contract — the 5-way invariant becomes fully asserted.
- **Phase 4**: delete `/s/*` routes, `url.ts` legacy builders, PR #172's 42-test contract. Replace with Grammar A equivalents. Redirect retained one release cycle then deleted in 4b.

## See also

- [ADR-0028](0028-url-scheme-place-first-flat-indicator-slug.md) — amended by this ADR on the country-prefix question.
- [ADR-0022](0022-place-first-ia-with-topic-catalogue.md) — place-first IA doctrine; entity-type badge constraint cites this.
- [ADR-0016](0016-frontend-hash-routing.md) — superseded by ADR-0028; routing-mode decision still stands.
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) — fallback doctrine; this ADR is the second application.
- [docs/architecture/frontend/routing.md](../frontend/routing.md) — operational route grammar (updated in this PR).
- [TODO/20260525-url-grammar-grammar-a-migration.md](../../../TODO/20260525-url-grammar-grammar-a-migration.md) — debate transcript, phase plan, open user-gate questions.
- [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts) — Grammar A builders (Phase 1 of this ADR).
