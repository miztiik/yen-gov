// Tiny history-based router (docs/architecture/frontend/overview.md).
//
// Routes are matched against `window.location.pathname` with the deploy
// base stripped (see lib/url.ts > stripBase). Patterns use `:name` for
// named params, returned as a string-keyed map. The first registered
// route to match wins.
//
// History routing (vs. hash routing) gives us clean paths like
// `/s/tamil-nadu/ac/167-mylapore`. GitHub Pages does not natively support
// SPA history routing, so a tiny `404.html` shim (in `public/`) bounces
// unknown paths back to `index.html` while preserving the requested path
// in `sessionStorage`. An inline boot script in `index.html` then restores
// the path before the SPA initialises. See public/404.html for the shim.

import { mount, type Component } from "svelte";
import { stripBase } from "./url";

// Pages declare their own params shape via $props(); the router doesn't try to
// share a single typed `RouteProps`. We accept any Component here and let each
// page's $props() type-check its own `params`.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyComponent = Component<any, any, any>;

export interface Route {
  pattern: string;                     // e.g. "/s/:state/ac/:eci_no"
  component: AnyComponent;
  // Optional coercer for params (e.g. parseInt eci_no). Returns the typed
  // params object that gets passed as a single `params` prop to the page.
  parse?: (raw: Record<string, string>) => Record<string, unknown>;
}

interface Compiled {
  re: RegExp;
  keys: string[];
  route: Route;
}

function compile(routes: Route[]): Compiled[] {
  return routes.map(r => {
    const keys: string[] = [];
    const src = r.pattern.replace(/\/:([A-Za-z_][A-Za-z0-9_]*)/g, (_m, k) => {
      keys.push(k);
      return "/([^/]+)";
    });
    return { re: new RegExp("^" + src + "$"), keys, route: r };
  });
}

function currentPath(): string {
  // Strip the deploy base (e.g. `/yen-gov/`) so route patterns stay
  // base-agnostic. The query string is intentionally NOT included — pages
  // that own URL state (Psephlab, Compare) read it directly from
  // `location.search`.
  const path = stripBase(window.location.pathname);
  return path || "/";
}

interface Matched {
  route: Route;
  params: Record<string, unknown>;
}

function resolve(compiled: Compiled[], fallback: Route, path: string): Matched {
  for (const c of compiled) {
    const m = c.re.exec(path);
    if (!m) continue;
    const raw: Record<string, string> = {};
    c.keys.forEach((k, i) => (raw[k] = decodeURIComponent(m[i + 1])));
    const params = c.route.parse ? c.route.parse(raw) : raw;
    return { route: c.route, params };
  }
  return { route: fallback, params: { path } };
}

export function startRouter(opts: {
  target: HTMLElement;
  routes: Route[];
  notFound: Route;
}): void {
  const compiled = compile(opts.routes);
  let current: ReturnType<typeof mount> | null = null;

  function render(): void {
    const path = currentPath();
    const matched = resolve(compiled, opts.notFound, path);
    route.path = path;
    route.params = matched.params;
    opts.target.innerHTML = "";
    current = mount(matched.route.component, {
      target: opts.target,
      props: { params: matched.params },
    });
  }

  // popstate fires for back/forward AND for the synthetic event we dispatch
  // from `url.ts > navigate()`. That covers every navigation path.
  window.addEventListener("popstate", render);

  // Intercept clicks on in-app links so we use pushState instead of a full
  // page reload. Skips: external links, target=_blank, modifier keys (so
  // ⌘-click / middle-click still open in a new tab as the user expects),
  // anchor links (`href="#..."`), and explicit downloads.
  document.addEventListener("click", e => {
    if (e.defaultPrevented || e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = (e.target as HTMLElement | null)?.closest("a");
    if (!a) return;
    const href = a.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
    if (a.target && a.target !== "" && a.target !== "_self") return;
    if (a.hasAttribute("download")) return;
    // Resolve absolute href and stay only if it's same-origin AND under
    // our deploy base.
    let resolved: URL;
    try { resolved = new URL(a.href, window.location.href); }
    catch { return; }
    if (resolved.origin !== window.location.origin) return;
    e.preventDefault();
    if (resolved.pathname + resolved.search + resolved.hash !==
        window.location.pathname + window.location.search + window.location.hash) {
      history.pushState(null, "", resolved.href);
    }
    render();
  });

  render();
  void current;  // silence unused-var linters
}

// Reactive view of the current route. Components import `route` and read
// `route.path` / `route.params` to react to navigation. Mutated by the router
// on each render; never write from a component.
export const route: { path: string; params: Record<string, unknown> } = $state({
  path: "/",
  params: {},
});
