<!--
  PartySymbolGlyph: shared renderer for party election-symbol assets.

  Inputs:
    - `assetPath`: root-relative path from `dim_parties.election_symbol_asset_path`
      (e.g. "party-symbols/lotus.svg"). Null / empty / undefined renders nothing.
    - `size`: pixel size for both dimensions. Defaults to 16.
    - `class`: optional extra Tailwind classes (e.g. ring, shadow).

  Contract (per Jony + Hans, PR-SYM-6b3 doctrine):
    - Decorative-secondary: alt="" so screen readers skip; the party text
      adjacent carries the accessible name.
    - No placeholder on decode/fetch failure: `onerror` hides the element
      so a broken asset never leaves a placeholder behind.
    - Pure presentational: no fetch, no state, no DOM mutation beyond hide.

  Extracted from WinnerBadge.svelte (PR-SYM-6b3 / #601) so AcStackedBar,
  MarginHistogram, RacesBoard, StateAcMap tooltip, and future consumers
  render the same glyph treatment without copy-pasting <img> markup.
-->
<script lang="ts" module>
  /**
   * Fallback policy when `assetPath` is null / undefined / empty.
   *   - "silent"      : return null; the component renders nothing
   *                     (today's behaviour for every caller that does
   *                     not opt in).
   *   - "placeholder" : return the URL of placeholder.svg (a neutral
   *                     gray ring + center dot) so the empty slot is
   *                     visible as a "party token here, no symbol yet"
   *                     marker.
   *   - "unverified"  : return the URL of unverified.svg (concentric
   *                     gray rings) so the empty slot reads as "we
   *                     have symbol metadata but it is not yet
   *                     verified". Not wired to any consumer today;
   *                     ships forward-compatibly so a future writer
   *                     can flip rows into this state without a
   *                     renderer change.
   *
   * The placeholder + unverified assets are committed under
   * `frontend/public/party-symbols/` and pass the build-time SVG
   * sanitizer (icons allowlist).
   */
  export type GlyphFallbackMode = "silent" | "placeholder" | "unverified";

  /**
   * Resolve a `dim_parties.election_symbol_asset_path` value to a runtime
   * URL the browser can fetch. Returns `null` when the path is absent AND
   * `fallback === "silent"` so callers can branch on truthiness without
   * re-implementing the BASE_URL join. When `fallback` is "placeholder"
   * or "unverified", returns the URL of the corresponding neutral asset
   * instead of null.
   *
   * Pure (no DOM, no fetch) so vitest pins the contract in node.
   */
  export function glyphUrlFor(
    assetPath: string | null | undefined,
    fallback: GlyphFallbackMode = "silent",
  ): string | null {
    const base = import.meta.env.BASE_URL;
    if (assetPath == null || assetPath.trim().length === 0) {
      if (fallback === "placeholder") {
        return `${base}party-symbols/placeholder.svg`;
      }
      if (fallback === "unverified") {
        return `${base}party-symbols/unverified.svg`;
      }
      return null;
    }
    return `${base}${assetPath.trim().replace(/^\/+/, "")}`;
  }
</script>

<script lang="ts">
  interface Props {
    assetPath: string | null | undefined;
    size?: number;
    class?: string;
    fallback?: GlyphFallbackMode;
  }
  let {
    assetPath,
    size = 16,
    class: extraClass = "",
    fallback = "silent",
  }: Props = $props();
  const url = $derived(glyphUrlFor(assetPath, fallback));
</script>

{#if url}
  <img
    src={url}
    alt=""
    width={size}
    height={size}
    class="object-contain shrink-0 {extraClass}"
    style:width="{size}px"
    style:height="{size}px"
    data-testid="party-symbol-glyph"
    loading="lazy"
    decoding="async"
    onerror={(e) => { (e.currentTarget as HTMLImageElement).hidden = true; }}
  />
{/if}
