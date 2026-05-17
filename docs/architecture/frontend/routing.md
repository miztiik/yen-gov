# Frontend routing

**Last Updated**: 2026-05-17

## What this is

The operational form of the URL scheme decided in [ADR-0028](../decisions/0028-url-scheme-place-first-flat-indicator-slug.md). This doc is for the engineer wiring the router; the ADR is for the reviewer asking "why this shape."

## Mode

**Path routing** on GitHub Pages via the standard SPA fallback: `_site/404.html` is a copy of `_site/index.html`. GitHub Pages serves `404.html` for any unknown path; the bundled router takes over from `window.location.pathname`. ADR-0028 supersedes ADR-0016's hash-routing decision.

The fallback file is regenerated as part of the Vite build (`postbuild` step copies `dist/index.html` → `dist/404.html`).

## Route grammar

```
/india                                          country home
/india/<state-slug>                             state
/india/<state-slug>/<district-slug>             district  (deferred until renderer ships)
/india/<state-slug>/<ac-slug>                   AC

/india/<indicator-slug>                         indicator @ national
/india/<state-slug>/<indicator-slug>            indicator @ state
/india/<state-slug>/<ac-slug>/<indicator-slug>  indicator @ AC

/compare                                        cross-state comparison surface
/explore                                        SQL explorer
/about, /disclaimer, /data-completeness         chrome
```

The indicator is always the **last segment**. Position disambiguates — no `/i/` marker, no `?i=` query string.

## Slug shapes

| Kind | Shape | Source of truth |
|---|---|---|
| State | lowercase hyphenated (`tamil-nadu`, `uttar-pradesh`) | `datasets/reference/in/states.json` |
| District | lowercase hyphenated (`chennai`) | `datasets/reference/in/states/<state>/districts.json` |
| AC | lowercase hyphenated name, **no number prefix** (`mylapore`, not `167-mylapore`) | ECI per-state constituency list. Collision fallback `<name>-2` enforced at emit. |
| Indicator | lowercase hyphenated flat slug (`installed-capacity`, `per-capita-income`) | Derived `url_slug` on `datasets/reference/in/indicators-completeness.json`. |

Indian-citizen-readable. Read-aloud test (Jony): `india/tamil-nadu/mylapore/installed-capacity` → "India, Tamil Nadu, Mylapore, installed capacity." Three nouns, one adjective. No scaffolding.

## Resolver contract

For a path `/india/<a>/<b>/<c>`:

```
1. Confirm `india` literal.
2. Look up `a` in state registry. If present, current node = state. Else 404.
3. If next segment exists:
   a. Look up `b` in {districts(a) ∪ ACs(a)}. If present, current node = district/AC.
   b. Else look up `b` in indicator-slug registry. If present, render {state=a, indicator=b}.
   c. Else 404.
4. If next segment exists after a geography match:
   a. Look up `c` in indicator-slug registry. If present, render {state=a, geo=b, indicator=c}.
   b. Else 404.
```

A real 404 is allowed — it means the path is malformed or refers to a place/indicator that doesn't exist. We do not "guess" or fall through to a homepage.

## Collision contract

ONE Tier-A test (CLAUDE.md §15) — `frontend/src/lib/paths.test.ts`:

```ts
const stateSlugs    = await loadStateSlugs();         // from states.json
const districtSlugs = await loadAllDistrictSlugs();   // from per-state districts.json
const acSlugs       = await loadAllAcSlugs();         // from completeness or per-state ECI lists
const indicatorSlugs = await loadIndicatorSlugs();    // from indicators-completeness.json url_slug field
const RESERVED = ["india", "indicator", "compare", "explore", "about", "disclaimer", "data-completeness"];

assertDisjoint(indicatorSlugs, stateSlugs);
assertDisjoint(indicatorSlugs, districtSlugs);
assertDisjoint(indicatorSlugs, acSlugs);
assertDisjoint(indicatorSlugs, RESERVED);
assertDisjoint(stateSlugs,     RESERVED);
assertDisjoint(districtSlugs,  RESERVED);  // (less likely, still cheap)
assertDisjoint(acSlugs,        RESERVED);
```

When this test goes red, the answer is to rename the colliding slug, never to add an exception to the test. Doctrine: slugs are part of the citizen contract; collisions are slug-quality bugs.

## Strangler-fig for legacy URLs

Existing routes from before ADR-0028:

- `#/`, `#/s/<state>`, `#/s/<state>/ac/<ac>` (hash-routed per superseded ADR-0016)
- `/s/<state>`, `/s/<state>/t/<topic>` (already path-routed in some commits)

Migration: a `RedirectLegacyUrl.svelte` component mounted on the legacy patterns rewrites `window.location` via `history.replaceState` to the new path on mount. Lifetime: one release cycle, then deleted. Documented sunset date in the component comment.

External bookmarks and search-engine index entries are real consumers of the old URLs; the ~30-line redirect component is cheaper than link rot.

## Pre-built routes file

Not used. With ~36 states × ~150 indicators × 3 geography depths ≈ 5,400 combinations, route enumeration is wasteful. The router resolves at runtime against the geography and indicator registries (already loaded for chrome anyway).

If a future need (sitemap.xml, OG-meta pre-rendering for shareable top-N pages) earns it, that's a Vite build step emitting a small file — separate ADR, not this one.

## svelte-routing pattern

Existing app uses [svelte-routing](https://github.com/EmilTholin/svelte-routing). Route declarations in `frontend/src/main.ts` use these patterns:

```svelte
<Route path="/india" component={CountryHome} />
<Route path="/india/:state" let:params component={StatePage} />
<Route path="/india/:state/:slug" let:params component={StateChildResolver} />
<Route path="/india/:state/:geo/:slug" let:params component={GeoChildResolver} />
```

The `*ChildResolver` components consult the registries to decide whether `:slug` is a sub-geography or an indicator, then mount the appropriate child. This is the resolver-contract step 3/4 above expressed in components.

## What lives where

- [paths.ts](../../../frontend/src/lib/paths.ts) — helpers: `stateHref`, `acHref`, `indicatorHref`, `indicatorAtStateHref`, `RESERVED_SEGMENTS`. Single source for every internal `<a href>`.
- `paths.test.ts` — the collision contract test above.
- `main.ts` — route table.
- `RedirectLegacyUrl.svelte` — strangler-fig.
- `indicator-slug-registry.ts` — loads `indicators-completeness.json` once, exposes `slugToId(slug) → indicator_id` and `idToSlug(id) → slug`.

## See also

- [ADR-0028 — URL scheme](../decisions/0028-url-scheme-place-first-flat-indicator-slug.md) — the why.
- [ADR-0016 — hash routing](../decisions/0016-frontend-hash-routing.md) — superseded.
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) — the fallback doctrine this scheme exemplifies.
