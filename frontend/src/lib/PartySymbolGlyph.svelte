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
   * Resolve a `dim_parties.election_symbol_asset_path` value to a runtime
   * URL the browser can fetch. Returns `null` when the path is absent so
   * callers can branch on truthiness without re-implementing the
   * BASE_URL join.
   *
   * Pure (no DOM, no fetch) so vitest pins the contract in node.
   */
  export function glyphUrlFor(
    assetPath: string | null | undefined,
  ): string | null {
    if (assetPath == null) return null;
    const trimmed = assetPath.trim();
    if (trimmed.length === 0) return null;
    return `${import.meta.env.BASE_URL}${trimmed.replace(/^\/+/, "")}`;
  }
</script>

<script lang="ts">
  interface Props {
    assetPath: string | null | undefined;
    size?: number;
    class?: string;
  }
  let { assetPath, size = 16, class: extraClass = "" }: Props = $props();
  const url = $derived(glyphUrlFor(assetPath));
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
