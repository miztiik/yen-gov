# Frontend routing

**Last Updated**: 2026-06-10

## What this is

The operational form of the URL scheme decided in [ADR-0028](../decisions/0028-url-scheme-place-first-flat-indicator-slug.md), as amended by [ADR-0037](../decisions/0037-url-grammar-drop-india-prefix.md). This doc is for the engineer wiring the router; the ADRs are for the reviewer asking "why this shape."

> **Phase 4b shipped (2026-06-10).** The 4-phase URL-prefix-drop strangler-fig is COMPLETE. The route table in [frontend/src/main.ts](../../../frontend/src/main.ts) declares only Grammar A patterns; every internal `<a href>` builder lives on `link.X()` in [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts). PR #869 deleted the Grammar B `url.X()` builders + the 42-test contract; PR-P4 (this release) deleted `RedirectLegacyUrl.svelte` + the `/s/*` redirect route + dropped `s` from `RESERVED_PATH_TOKENS`. Legacy `/s/<state>/...` bookmarks now fall through to the NotFound page (404 with Home + Browse-topics recovery links).

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

## Depth-2 dispatcher resolution rule (Option A, 2026-06-10)

The collision contract above runs STRICT for six pairwise registry pairs (state ⊥ topic, state ⊥ reserved, topic ⊥ reserved, ac ⊥ state, ac ⊥ topic, ac ⊥ reserved). **It does NOT run strict for per-state district vs AC name collisions** — that collision class is a design baseline on the Indian electoral corpus, not a bug to be renamed away.

### The 401-collision baseline

Verified against the shipped corpus (`datasets/taxonomy/entities.json` district rows + `datasets/data/entities/electoral.csv` AC rows) on 2026-06-10:

> **401 (state, slug) pairs across 25 states** have a district name equal to an AC name in the same state.

This is the rule, not the exception. Many Indian ACs are named after their district HQ (`Coimbatore` AC inside Coimbatore district; `Mysore` AC inside Mysore district; etc.). The data spine reflects the underlying electoral geography honestly; the URL surface honours that by **resolving district-first at depth 2**.

### Dispatcher resolution rule for `/<state>/<position2>`

The depth-2 state-sub dispatcher ([frontend/src/routes/StateSubRouter.svelte](../../../frontend/src/routes/StateSubRouter.svelte) + the pure [frontend/src/lib/state-sub-resolver.ts](../../../frontend/src/lib/state-sub-resolver.ts)) resolves the second positional segment against three registries in this LOAD-BEARING order (Jony rule #4):

| Step | Registry | Win condition |
| --- | --- | --- |
| 1 | `RESERVED_PATH_TOKENS` chrome | Always wins — chrome surfaces are never poached by data slugs. |
| 2 | per-state district slugs (entities.json, filtered to `parent_entity_id == "IN-${eci_code}"`) | First-registered slug wins. **On a same-slug collision, the district wins.** |
| 3 | per-state AC slugs (electoral.csv, filtered to this state) | Only reached when steps 1+2 miss. |
| 4 | `notfound` | Falls through to the NotFound surface. |

### Where does the colliding AC live?

The colliding AC is **still reachable** via the canonical event-nested URL:

```
/<state>/elections/<event>/ac/<ac>
```

per [ADR-0052](../decisions/0052-event-context-in-ac-url.md). The bare positional URL `/<state>/<slug>` was always a CONVENIENCE entry for the AC, never a canonical resource — Option A formalises that. Bare-AC links in citizen-facing copy SHOULD use the canonical event-nested form so the AC is always reachable regardless of district name collisions.

The bare-AC route entry (`/<state>/ac/<ac>`) also stays alive for callers that have an `eci_no` but no event id; it `replaceState`-redirects to the state's default event per ADR-0052.

### Why Option A (resolver-as-gate) over the strict-disjointness draft

The original PR-D1 draft attempted to enforce strict per-state `districts ⊥ ACs` disjointness as a build gate (Jony rule #2). The STOP-AND-SURFACE on the 401-collision count surfaced two equally unattractive options:

1. **Block PR-D1 on a Hans+Max-signed-off corpus rename** of ~401 AC rows with a `-N` suffix. That is a citizen-visible URL change touching the canonical data spine — Holy Law-level work that does NOT belong inside a routing-PR scope.
2. **Auto-rename ACs without the data team's signoff.** That violates CLAUDE.md s10 Anti-pattern #1: silent demotion of a user-named artifact.

Option A picks neither. The dispatcher's deterministic first-wins resolution order IS the gate; the AC stays reachable via its canonical URL; the optional corpus cleanup is documented as a follow-up (see [TODO/20260609-url-prefix-drop-phase0-plan.md](../../../TODO/20260609-url-prefix-drop-phase0-plan.md) § "Follow-up deferrals"), NOT a blocker.

### What the build-time gate still asserts

The Deferral 1 describe block in [frontend/src/contracts/url-namespace-disjointness.test.ts](../../../frontend/src/contracts/url-namespace-disjointness.test.ts) (under the heading "Deferral 1 per-state resolver gate (districts vs ACs; Option A)") now carries:

- **SANITY floors** (catches registry-load failure):
  - `>=28 states have districts loaded`
  - `>=15 states have ACs loaded`
  - `>=1 state has both districts AND ACs loaded`
- **POSITIVE presence-of-collisions check** (the OPPOSITE of strict disjointness):
  - `"district-AC name collisions exist; resolver wins per Jony rule #4 (this is by design)"` — asserts `collisions.length > 0` so the regression "corpus accidentally renamed all collisions away" OR "registry-loading silently collapsed" still fails the build.

The other six pairwise disjointness assertions in the same file STAY STRICT.

## Strangler-fig for legacy URLs (RETIRED 2026-06-10 in PR #871)

The 4-phase URL-prefix-drop strangler-fig has shipped end-to-end (PRs #867 / #868 / #869 / #871). The summary that follows is HISTORICAL:

- `#/`, `#/s/<state>`, `#/s/<state>/ac/<ac>` (hash-routed per superseded ADR-0016) — never had a runtime redirect in this plan; superseded long before.
- `/s/<state>`, `/s/<state>/t/<topic>`, `/s/<state>/ac/<ac>` (Grammar B — was the live shape through PR #173) — redirected by `RedirectLegacyUrl.svelte` from PR #867 (2026-06-09) until PR #871 (2026-06-10).
- `/india/<state>/...` (Grammar C — ADR-0028 as originally written) — never implemented; no redirect ever shipped.

After PR #871 the redirect component + the `/s/*` route + `s` from `RESERVED_PATH_TOKENS` are all deleted. Legacy `/s/<state>/...` bookmarks now render the NotFound page (404 with Home + Browse-topics recovery links).

## Cross-state indicator-compare surface

Lives ON the indicator page itself in Phase 3+, not at a separate URL. OWID precedent: `/grapher/co2-emissions-per-capita` IS the compare surface — the country-picker is a control on the chart, not a separate URL. The existing election-compare surface at `/compare/<state>/<event>` is a different beast (compares one event outcome across many states) and stays. See [ADR-0037 §cross-state](../decisions/0037-url-grammar-drop-india-prefix.md).

## Pre-built routes file

Not used. With ~36 states × ~150 indicators × 3 geography depths ≈ 16,000 combinations, route enumeration is wasteful. The router resolves at runtime against the geography and indicator registries (already loaded for chrome anyway).

If a future need (sitemap.xml, OG-meta pre-rendering for shareable top-N pages) earns it, that's a Vite build step emitting a small file — separate ADR, not this one.

## Router patterns (shipped 2026-06-10)

The live route table is in [frontend/src/main.ts](../../../frontend/src/main.ts):

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

- [frontend/src/lib/links.ts](../../../frontend/src/lib/links.ts) — Grammar A URL builders: `link.stateHub`, `link.acDeepLink`, `link.stateIndicator`, etc. The SOLE source of every internal `<a href>` after PR #869. Also exports `RESERVED_PATH_TOKENS`.
- [frontend/src/lib/links.test.ts](../../../frontend/src/lib/links.test.ts) — the positive shape contract for `links.ts`.
- [frontend/src/lib/url.ts](../../../frontend/src/lib/url.ts) — URL utility primitives only after PR #869 (`withBase`, `stripBase`, `navigate`). The Grammar B `url.X()` builders + their 42-test contract have been deleted.
- [frontend/src/contracts/url-namespace-disjointness.test.ts](../../../frontend/src/contracts/url-namespace-disjointness.test.ts) — namespace disjointness across state/topic/AC/indicator/RESERVED.
- [frontend/src/contracts/state-slugs-full-name.test.ts](../../../frontend/src/contracts/state-slugs-full-name.test.ts) — Hans's full-name state-slug invariant.
- [frontend/src/lib/paths.ts](../../../frontend/src/lib/paths.ts) — UNRELATED to URL grammar; holds `DATA_BASE` (runtime data-fetch prefix). Not the place to add new route-URL builders.
- [frontend/src/main.ts](../../../frontend/src/main.ts) — the live route table.
- `RedirectLegacyUrl.svelte` — DELETED in PR #871 (2026-06-10) after the user-triggered soak window. Legacy `/s/*` URLs now fall through to NotFound.
- `indicator-slug-registry.ts` — PENDING; lands when the `url_slug` field is added to the catalogue.

## See also

- [ADR-0028 — URL scheme](../decisions/0028-url-scheme-place-first-flat-indicator-slug.md) — amended on the country-prefix question.
- [ADR-0037 — drop /india/ prefix](../decisions/0037-url-grammar-drop-india-prefix.md) — the binding 2026-05-25 amendment; carries the three-voice digest, the four-phase plan, and the open user-gate questions.
- [ADR-0016 — hash routing](../../archive/decisions/0016-frontend-hash-routing.md) — superseded (archived 2026-06-04 per D-DOC3.6; trace folded into [url-grammar.md](url-grammar.md#adr-0016-frontend-rejected-alternatives)).
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) — the fallback doctrine this scheme exemplifies.
