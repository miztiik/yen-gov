// Tiny hash-based router (docs/architecture/frontend/overview.md). 4 routes, no nesting, no dependency.
//
// Routes are matched against `window.location.hash.slice(1)` (so `#/s/S22`
// matches the path `/s/S22`). Patterns use `:name` for named params, which
// are returned as a string-keyed map. The first registered route to match
// wins.

import { mount, type Component } from "svelte";

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
  const h = window.location.hash;
  if (!h || h === "#" || h === "#/") return "/";
  let p = h.startsWith("#") ? h.slice(1) : h;
  // Strip the fragment query string (e.g. `?s=...` used by Psephlab to
  // serialise scenario state). The route pattern only matches the path.
  const q = p.indexOf("?");
  if (q >= 0) p = p.slice(0, q);
  return p;
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

  function render() {
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

  // If we land with no hash, redirect to "#/" so back/forward behave.
  if (!window.location.hash) window.location.hash = "#/";
  window.addEventListener("hashchange", render);
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
