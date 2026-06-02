/**
 * Resolve a party election-symbol asset path (root-relative, as stored in
 * `dim_parties.election_symbol_asset_path`, e.g. "party-symbols/lotus.svg")
 * to a URL the browser can fetch under the deployed base path.
 *
 * GitHub Pages serves the site under a sub-path (BASE_URL=/yen-gov/), so a
 * bare relative `src` would resolve against the current route, not the site
 * root. Vite's `import.meta.env.BASE_URL` (always ends in '/') is the
 * documented seam for this — the same one `paths.ts` uses for data loads.
 *
 * Returns null when there is no asset, so the tooltip medallion degrades
 * silently (no placeholder).
 */
export function symbolAssetUrl(
  assetPath: string | null | undefined,
): string | null {
  if (!assetPath) return null;
  const base = import.meta.env.BASE_URL; // always ends in '/'
  return base + assetPath.replace(/^\/+/, "");
}
