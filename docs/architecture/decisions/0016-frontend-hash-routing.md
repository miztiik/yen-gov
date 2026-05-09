# ADR-0016: Frontend hash-based routing (custom, no router lib)

**Last Updated**: 2026-05-09
**Status**: accepted

## Context

The frontend has grown beyond a single State Overview screen. Phase 8 introduces per-AC, per-party, and a state-index landing route. This requires a routing layer.

Constraints from prior ADRs:

- **ADR-0011**: Svelte 5 + Vite + bun. No SvelteKit (we are not server-rendering; the app is a static SPA).
- **ADR-0013**: Production is GitHub Pages serving the `_site/` artifact verbatim. GitHub Pages does not natively rewrite unknown paths to `index.html` (the `404.html` workaround exists but is brittle: it intercepts as a 404 then JS-redirects, leaking a brief 404 in network panels and breaking link previews).

The repo's Holy Law #1 (static-first) means any router that depends on history-mode rewrites would force us to also commit a `404.html` shim and document the workaround — a perpetual footgun.

## Decision

Use **hash-based routing** with a tiny custom router (~50 lines) under `frontend/src/lib/router.ts`. URLs look like:

- `#/`                                 — country index (currently lists states with data)
- `#/s/:state`                         — state overview (today's App.svelte)
- `#/s/:state/ac/:eci_no`              — per-constituency result
- `#/s/:state/party/:party_eci_code`   — per-party detail across the state

The router exposes a `route` rune (`$state`-based store) parsed from `window.location.hash` and updated on `hashchange`. Components read `route.params` directly. Navigation is via standard `<a href="#/...">` — no link component required.

No router library is added. The current need (4 routes, no nesting, no guards, no transitions) does not justify a dependency.

## Consequences

**Good**

- Zero deploy-time configuration. Works identically under `vite dev` and on GitHub Pages.
- No 404.html shim. Direct deep links survive page reload because the path the server sees is always `index.html` (the hash never reaches the server).
- ~50 lines of code, fully readable. No hidden behaviour, no version churn from an external lib.
- Deep links are shareable and bookmark-able.

**Bad**

- URLs include `#/`. Less aesthetic than history-mode paths. We accept this — the alternative is the 404.html footgun.
- Search engines index hash routes inconsistently. We are not optimising for SEO on this app (the data is the product, not the URL surface).
- Custom code = our problem to maintain. Mitigated by the trivial scope (parse → match → render).

## Alternatives considered

- **svelte-routing / svelte-spa-router**: viable, but adds a dependency and an opinion (slot-based routing, named params with `:slug` syntax, etc.) for a 4-route app. Rejected on YAGNI.
- **SvelteKit with adapter-static**: gives us file-system routing and SSG. Rejected because (a) Holy Law #1 forbids assuming any backend, and adapter-static is a heavy migration path; (b) we already have a working Vite + plain-Svelte setup per ADR-0011; (c) routing is the only thing SvelteKit would buy us right now.
- **History-mode custom router + 404.html shim**: pretty URLs, but every deep-link load goes through a redirect. Rejected on the brittleness called out in Context.
