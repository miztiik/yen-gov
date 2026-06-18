/**
 * Resolve a party election-symbol asset path (root-relative, as stored in
 * `dim_parties.election_symbol_asset_path`, e.g. "party-symbols/lotus.svg")
 * to a URL the browser can fetch under the deployed base path.
 *
 * GitHub Pages serves the site under a sub-path (BASE_URL=/yen-gov/), so a
 * bare relative `src` would resolve against the current route, not the site
 * root. This routes through `assetUrl` from the single base/CDN seam
 * (`lib/config/cdn.ts`), which prefixes Vite's `import.meta.env.BASE_URL`
 * (always ends in '/') — the same base every data load + glyph resolves.
 *
 * Fallback policy when `assetPath` is null / undefined / empty:
 *   - "silent"      : return null (today's behaviour); tooltip degrades
 *                     silently with no medallion.
 *   - "placeholder" : return the URL of placeholder.svg (a neutral gray
 *                     ring + center dot).
 *   - "unverified"  : return the URL of unverified.svg (concentric rings).
 *
 * Mirrors `glyphUrlFor` in `$lib/PartySymbolGlyph.svelte` so the DOM and
 * MapLibre tooltip surfaces share one fallback vocabulary.
 */

import { assetUrl } from "../config/cdn";

export type SymbolAssetFallbackMode = "silent" | "placeholder" | "unverified";

export function symbolAssetUrl(
  assetPath: string | null | undefined,
  fallback: SymbolAssetFallbackMode = "silent",
): string | null {
  if (!assetPath) {
    if (fallback === "placeholder") {
      return assetUrl("/party-symbols/placeholder.svg");
    }
    if (fallback === "unverified") {
      return assetUrl("/party-symbols/unverified.svg");
    }
    return null;
  }
  return assetUrl(assetPath);
}
