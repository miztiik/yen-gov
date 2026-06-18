// Single base / CDN resolution seam for the whole frontend.
//
// GitHub Pages is the ONLY "CDN" this app deploys to. The deployed base
// path is whatever `import.meta.env.BASE_URL` resolves to at build time:
// "/" for `bun run dev` / `preview` / a user-or-custom-domain Pages site,
// and "/yen-gov/" under a project Pages subpath. The single knob is the
// `BASE_URL` env var, read in `frontend/vite.config.ts`
// (`const BASE_URL = process.env.BASE_URL ?? "/"` -> `base: BASE_URL`) and
// surfaced to runtime as Vite's documented `import.meta.env.BASE_URL`
// (always ends in '/'). There is NO hardcoded host or base literal in this
// module -- that would break dev ('/') vs prod ('/yen-gov/') parity and
// violate CLAUDE.md Holy Law #6.
//
// Every module that builds a runtime URL resolves the base through THIS
// seam and nowhere else:
//   * in-app route URLs      -> `withBase` (consumed by `link.*` in links.ts)
//   * static `public/` assets -> `assetUrl` (svg / png glyphs, brand logos)
//   * dataset fetches         -> `DATA_BASE` (re-exported from paths.ts)
//   * share-card images       -> `SHARE_BASE` (re-exported from paths.ts)
//
// Reading `import.meta.env.BASE_URL` inline in a component is exactly how a
// base-less `src="/brands/wikipedia.svg"` (which 404s on the `/yen-gov/`
// deploy) creeps back in; consolidating the read here makes that a single,
// testable choke point. The sentinel
// `frontend/src/contracts/cdn-assets-use-seam.test.ts` forbids a runtime
// asset `src` from bypassing this seam.
//
// See also:
//   * frontend/src/lib/paths.ts  -- DATA_BASE / SHARE_BASE definitions.
//   * frontend/src/lib/url.ts    -- stripBase / navigate primitives that
//     consume CDN_BASE; re-exports `withBase` from here.
//   * frontend/src/lib/links.ts  -- the `link.*` route builders that
//     consume `withBase` from here.

/** The deploy base path. Always ends in '/'. The single env-driven knob. */
export const CDN_BASE = import.meta.env.BASE_URL;

/**
 * Prefix a path with the deploy base URL. Inputs that do not start with
 * '/' are normalised to absolute first; the duplicate slash that
 * CDN_BASE='/yen-gov/' would otherwise produce is collapsed. This is the
 * CANONICAL definition -- `url.ts` and `links.ts` re-import it so the three
 * builder layers share one body instead of three copies.
 */
export function withBase(path: string): string {
  if (!path.startsWith("/")) path = "/" + path;
  return CDN_BASE.replace(/\/$/, "") + path;
}

/**
 * Base-prefix a `public/` static asset path (svg / png / etc.) so it
 * resolves against the site ROOT, not the current route. GitHub Pages is
 * the only CDN and the base is env-driven via the single
 * `import.meta.env.BASE_URL` knob (set from `BASE_URL` in the deploy
 * workflow / `vite.config.ts` `base`). Delegates to `withBase` so the
 * leading-'/' normalisation and double-slash collapse are shared.
 *
 * Example (prod base '/yen-gov/'):
 *   assetUrl("/brands/wikipedia.svg") -> "/yen-gov/brands/wikipedia.svg"
 * Example (dev base '/'):
 *   assetUrl("/brands/wikipedia.svg") -> "/brands/wikipedia.svg"
 */
export function assetUrl(path: string): string {
  return withBase(path);
}

// DATA_BASE / SHARE_BASE keep their definitions in paths.ts so the many
// existing `from "./paths"` / `from "../paths"` importers stay unchanged;
// they are re-exported here so this module is the single base/CDN import
// surface for any new consumer.
export { DATA_BASE, SHARE_BASE } from "../paths";
