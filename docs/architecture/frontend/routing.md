# Frontend routing

**Last Updated**: 2026-05-26

## What this is

The operational form of the URL scheme decided in [ADR-0028](../decisions/0028-url-scheme-place-first-flat-indicator-slug.md), as amended by [ADR-0037](../decisions/0037-url-grammar-drop-india-prefix.md). This doc is for the engineer wiring the router; the ADRs are for the reviewer asking "why this shape."

> **Phase 1 status (2026-05-25).** Grammar A end-state is documented here but not yet wired into `frontend/src/main.ts`. The live code currently routes Grammar B (`/s/<state>/...`); see [ADR-0037](../decisions/0037-url-grammar-drop-india-prefix.md) for the binding decision, the three-voice digest, the four-phase strangler-fig, and the open user-gate questions blocking Phase 2/3/4. Phase 1 shipped `frontend/src/lib/links.ts` (Grammar A builders, zero call-sites) plus the three Tier-A contract tests in PR #173. Phase 2 adds the route table; Phase 3 lands the legacy redirect; Phase 4 deletes Grammar B.

## Mode

**Path routing** on GitHub Pages via the standard SPA fallback: `_site/404.html` is a copy of `_site/index.html`. GitHub Pages serves `404.html` for any unknown path; the bundled router takes over from `window.location.pathname`. ADR-0028 supersedes ADR-0016's hash-routing decision.

The fallback file is regenerated as part of the Vite build (`postbuild` step copies `dist/index.html` → `dist/404.html`).

## Route grammar (Grammar A end-state, per ADR-0037)

```
/                                               country home (India implicit on .in)
/<state-slug>                                   state or UT hub
/<state-slug>/<district-slug>                   district  (deferred until renderer ships)
/<state-slug>/<ac-slug>                         AC

/<indicator-slug>                               indicator @ national
/<state-slug>/<indicator-slug>                  indicator @ state
/<state-slug>/<ac-slug>/<indicator-slug>        indicator @ AC

/t                                              topic Front Door (index)
/t/<topic-id>                                   topic landing
/<state-slug>/t/<topic-id>                      per-state topic landing

/<state-slug>/explore                           state SQL explorer
/<state-slug>/party/<party-slug>                party-in-state surface
/<state-slug>/elections/<event>                 per-state per-event landing (shipped Grammar B, PR #193)

/lab/<state-slug>/<event>                       election lab (existing surface, retained)
/compare/<state-slug>/<event>                   election compare (existing surface, retained)
/compare                                        cross-surface compare home (chrome)

/about, /settings, /disclaimer, /data-completeness    chrome
```

The indicator is always the **last segment**. Position disambiguates — no `/i/` marker, no `?i=` query string. (`/i` is pre-reserved as a marker retrofit if the disjointness test starts firing at scale — see [ADR-0037 §rejected](../decisions/0037-url-grammar-drop-india-prefix.md) and Max §10k-scaling for the threshold rationale.)

## Slug shapes

| Kind | Shape | Source of truth |
|---|---|---|
| State / UT | lowercase hyphenated full English name (`tamil-nadu`, `uttar-pradesh`, `andaman-and-nicobar-islands`) — NEVER abbreviated to `tn`/`up`/`a-n`. Enforced by `frontend/src/contracts/state-slugs-full-name.test.ts`. | `datasets/taxonomy/entities.json` (filter `entity_type IN ('state','ut') AND entity_valid_to IS NULL`) |
| District | lowercase hyphenated (`chennai`) | `datasets/taxonomy/entities.json` (filter `entity_type='district' AND parent_entity_id=f'IN-{state}'`) |
| AC | lowercase hyphenated name, **no number prefix** (`mylapore`, not `167-mylapore`) | `datasets/elections/dim_acs.parquet` (`name` column). Collision fallback `<name>-2` enforced at emit. |
| Topic | the `id` field from the topic catalogue (`fiscal`, `energy`, `health`) | `datasets/taxonomy/topics.json` |
| Indicator | lowercase hyphenated flat slug (`installed-capacity`, `per-capita-income`) | Future `url_slug` field on `datasets/taxonomy/indicators.parquet` (Phase 3 per [ADR-0037](../decisions/0037-url-grammar-drop-india-prefix.md) §Max-3i). |

Indian-citizen-readable. Read-aloud test (Jony): `tamil-nadu/mylapore/installed-capacity` → "Tamil Nadu, Mylapore, installed capacity." Three nouns. No scaffolding.

### Entity-type framing (page chrome contract)

Constitutional honesty is carried by the page chrome, not the URL. The state-hub page MUST render an `entity_type` badge (`state` | `UT`) directly under the H1, with the legislative-scope note where applicable (Delhi NCT, J&K UT-since-2019, Chandigarh / Lakshadweep / Ladakh UTs without legislature). The URL `/<state-slug>` reads as a place-fact (Wikipedia-trained mental model); the page chrome closes the constitutional loop. See [ADR-0022](../decisions/0022-place-first-ia-with-topic-catalogue.md) §constitutional-honesty.

## Resolver contract

For a path `/<a>/<b>/<c>`:

```
1. If `a` is in RESERVED_PATH_TOKENS (`t`, `compare`, `about`, `settings`,
   `disclaimer`, `data-completeness`, `lab`, `dev`, `s`, `ac`, `party`,
   `i`, `explore`) → dispatch to the chrome/legacy/event handler keyed by `a`.
2. Else look up `a` in the state registry. If present, current node = state.
3. Else look up `a` in the indicator-slug registry. If present, render
   national indicator and stop.
4. Else 404.

5. (Once a state matched at step 2) If `b` exists:
   a. Look up `b` in {districts(a) ∪ ACs(a)}. If present, current node = district/AC.
   b. Else if `b` is in RESERVED_PATH_TOKENS (`t`, `explore`, `party`, `elections`),
      dispatch to the sub-namespace handler keyed by `b`. (`elections` dispatches
      `/<state-slug>/elections/<event>` to [StateElection.svelte](../../../frontend/src/routes/StateElection.svelte),
      per the elections-renderer Q1+PR-2 work in PR #193 — see
      [indicators.md §Decisions-journal-2026-05-24](indicators.md).)
   c. Else look up `b` in the indicator-slug registry. If present, render
      {state=a, indicator=b}.
   d. Else render the missing-scope stub (per ADR-0037 §missing-scope):
      indicator page chrome with "not published at state scope" + deep
      link to nearest scope. Never silent-redirect. Never 404.

6. (Once a state + geography matched at step 5a) If `c` exists:
   a. Look up `c` in the indicator-slug registry. If present, render
      {state=a, geo=b, indicator=c}.
   b. Else render the missing-scope stub.
```

A real 404 is allowed only when the first segment is unknown to every registry — it means the URL is malformed. We do not "guess" or fall through to the homepage.

## Collision contract

Pairwise disjointness across the registries that share the URL namespace — enforced by Tier-A contract tests (CLAUDE.md §15) under `frontend/src/contracts/`:

```
urlIndicatorSlugs ⊥ stateSlugs ⊥ topicSlugs ⊥ acSlugsAcrossAllStates ⊥ RESERVED_PATH_TOKENS
```

| Slug class | Asserted by | Phase asserted |
|---|---|---|
| stateSlugs ⊥ topicSlugs ⊥ RESERVED | `frontend/src/contracts/url-namespace-disjointness.test.ts` | Phase 1 |
| stateSlugs full-name invariant | `frontend/src/contracts/state-slugs-full-name.test.ts` | Phase 1 |
| acSlugs ⊥ {stateSlugs, topicSlugs, RESERVED} | `url-namespace-disjointness.test.ts` (extension) | Phase 2 (needs DuckDB-WASM in the test harness to read `dim_acs.parquet`) |
| urlIndicatorSlugs ⊥ {all others} | `url-namespace-disjointness.test.ts` (extension) | Phase 3 (needs `url_slug` field on `taxonomy/indicators.parquet`) |

When the test goes red, the answer is to rename the colliding slug, never to add an exception to the test. Doctrine: slugs are part of the citizen contract; collisions are slug-quality bugs.

## Strangler-fig for legacy URLs

Legacy URL grammars to be redirected forward to Grammar A:

- `#/`, `#/s/<state>`, `#/s/<state>/ac/<ac>` (hash-routed per superseded ADR-0016)
- `/s/<state>`, `/s/<state>/t/<topic>`, `/s/<state>/ac/<ac>` (Grammar B — currently shipping, locked by PR #172)
- `/india/<state>/...` (Grammar C — ADR-0028 as originally written; never implemented but documented for one release cycle in case any external bookmark made it that far)

Migration: a `RedirectLegacyUrl.svelte` component mounted on the legacy patterns rewrites `window.location` via `history.replaceState` to the matching Grammar A path on mount. Lifetime: one release cycle, then deleted in Phase 4b. Documented sunset date in the component comment.

External bookmarks and search-engine index entries are real consumers of the old URLs; the ~50-line redirect component is cheaper than link rot.

## Cross-state indicator-compare surface

Lives ON the indicator page itself in Phase 3+, not at a separate URL. OWID precedent: `/grapher/co2-emissions-per-capita` IS the compare surface — the country-picker is a control on the chart, not a separate URL. The existing election-compare surface at `/compare/<state>/<event>` is a different beast (compares one event outcome across many states) and stays. See [ADR-0037 §cross-state](../decisions/0037-url-grammar-drop-india-prefix.md).

## Pre-built routes file

Not used. With ~36 states × ~150 indicators × 3 geography depths ≈ 16,000 combinations, route enumeration is wasteful. The router resolves at runtime against the geography and indicator registries (already loaded for chrome anyway).

If a future need (sitemap.xml, OG-meta pre-rendering for shareable top-N pages) earns it, that's a Vite build step emitting a small file — separate ADR, not this one.

## Router patterns (Phase 2 target)

The route table in `frontend/src/main.ts` will declare these patterns once Phase 2 wires Grammar A in alongside the current Grammar B routes:

```svelte
<Route path="/" component={CountryHome} />
<Route path="/t" component={TopicsIndex} />
<Route path="/t/:topic" let:params component={TopicLanding} />
<Route path="/:slugA" let:params component={RootResolver} />
<Route path="/:slugA/:slugB" let:params component={StateChildResolver} />
<Route path="/:slugA/:slugB/:slugC" let:params component={GeoChildResolver} />
```

The `RootResolver` consults RESERVED + state-registry + indicator-registry to decide whether `:slugA` is chrome, a state, or a national indicator. Similar resolvers handle the deeper paths per the §Resolver contract above.

## What lives where

- [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts) — Grammar A URL builders: `link.stateHub`, `link.acDeepLink`, `link.stateIndicator`, etc. Future single source for every internal `<a href>`. Also exports `RESERVED_PATH_TOKENS`.
- [frontend/src/lib/links.test.ts](../../../frontend/src/lib/links.test.ts) — Phase 1 positive shape contract for `links.ts`.
- [frontend/src/lib/url.ts](../../../frontend/src/lib/url.ts) — LEGACY Grammar B builders. Live today; deleted in Phase 4.
- [frontend/src/lib/url.test.ts](../../../frontend/src/lib/url.test.ts) — 42-test contract locking Grammar B (PR #172). Deleted in Phase 4 alongside `url.ts`.
- [frontend/src/contracts/url-namespace-disjointness.test.ts](../../../frontend/src/contracts/url-namespace-disjointness.test.ts) — namespace disjointness across state/topic/AC/indicator/RESERVED.
- [frontend/src/contracts/state-slugs-full-name.test.ts](../../../frontend/src/contracts/state-slugs-full-name.test.ts) — Hans's full-name state-slug invariant.
- [frontend/src/lib/paths.ts](../../../frontend/src/lib/paths.ts) — UNRELATED to URL grammar; holds `DATA_BASE` (runtime data-fetch prefix). Not the place to add new route-URL builders.
- `frontend/src/main.ts` — route table (Phase 2 work).
- `RedirectLegacyUrl.svelte` — strangler-fig (Phase 3 work).
- `indicator-slug-registry.ts` — loads `indicators-completeness.json` once, exposes `slugToId(slug) → indicator_id` and `idToSlug(id) → slug` (Phase 3 work, when `url_slug` field lands).

## See also

- [ADR-0028 — URL scheme](../decisions/0028-url-scheme-place-first-flat-indicator-slug.md) — amended on the country-prefix question.
- [ADR-0037 — drop /india/ prefix](../decisions/0037-url-grammar-drop-india-prefix.md) — the binding 2026-05-25 amendment; carries the three-voice digest, the four-phase plan, and the open user-gate questions.
- [ADR-0016 — hash routing](../../archive/decisions/0016-frontend-hash-routing.md) — superseded (archived 2026-06-04 per D-DOC3.6; trace folded into [url-grammar.md](url-grammar.md#adr-0016-frontend-rejected-alternatives)).
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) — the fallback doctrine this scheme exemplifies.
