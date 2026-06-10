// URL utility primitives shared across the SPA.
//
// Per ADR-0037 / TODO/20260609-url-prefix-drop-phase0-plan.md PR-P3:
// the `url.X()` Grammar B builders that lived here through Phase 1-2
// have been DELETED. The Grammar A builders live in `./links.ts`
// (`link.X()`). This file retains only the three primitives that don't
// belong on the link object:
//
//   * `withBase(path)`     — prefix a path with the deploy `BASE_URL`.
//                            Used by every `link.X()` builder.
//   * `stripBase(pathname)`— inverse, used by the router to derive the
//                            route path from `window.location.pathname`.
//   * `navigate(path)`     — programmatic navigation (pushState +
//                            popstate dispatch). Called by components
//                            that need to drive navigation imperatively
//                            (Constituency replaceState redirects,
//                            NationalElectionsAtlas drilldown clicks,
//                            etc.).
//
// The `url` builder object was Grammar B (`/s/<state>/...`) and is
// retired in PR-P3. Any new builder belongs on `link` in `./links.ts`.

const BASE = import.meta.env.BASE_URL; // always ends in '/'

/**
 * Prefix a path with the deploy base URL. Inputs MUST start with `/`;
 * we collapse the duplicate slash that would otherwise appear when BASE
 * is `/yen-gov/`.
 */
export function withBase(path: string): string {
  if (!path.startsWith("/")) path = "/" + path;
  return BASE.replace(/\/$/, "") + path;
}

/** Strip the deploy base from `location.pathname` to get the route path. */
export function stripBase(pathname: string): string {
  const baseNoSlash = BASE.replace(/\/$/, "");
  if (baseNoSlash && pathname.startsWith(baseNoSlash)) {
    const tail = pathname.slice(baseNoSlash.length);
    return tail === "" ? "/" : tail;
  }
  return pathname || "/";
}

/**
 * Programmatic navigation — pushes a new entry; triggers the router.
 *
 * Accepts a URL produced by one of the `link.X()` builders (i.e. already
 * base-prefixed). We deliberately do NOT call `withBase()` here: every
 * call site uses a builder, and double-prefixing produced
 * `/yen-gov/yen-gov/...` URLs on project Pages deploys. As a safety
 * net, an unprefixed path that starts with `/` is auto-prefixed so
 * legacy/raw paths still work.
 */
export function navigate(path: string, opts: { replace?: boolean } = {}): void {
  const baseNoSlash = BASE.replace(/\/$/, "");
  const alreadyPrefixed =
    !!baseNoSlash && (path === baseNoSlash || path.startsWith(baseNoSlash + "/"));
  const target = alreadyPrefixed ? path : withBase(path);
  if (opts.replace) history.replaceState(null, "", target);
  else history.pushState(null, "", target);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
