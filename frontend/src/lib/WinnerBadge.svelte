<!--
  WinnerBadge: citizen-facing constituency-result winner pane (PR-SYM-6b).

  Renders the winner's name + party with:
    - an accent stripe coloured by the 3-tier resolver (getPartyColor)
    - the party's ballot-symbol glyph when `election_symbol_asset_path`
      is populated on dim_parties (PR-SYM-6b3); no placeholder otherwise

  Hans + Jony lens:
    - Hans (honesty): the colour resolver still records its provenance tier
      (anchor / brand / fallback) internally on `resolved.source` for the
      diagnostics surface (Settings), but the citizen-facing badge no longer
      surfaces it. A colour-provenance pill on every constituency result was
      provenance bleeding into the citizen UI as noise, not insight.
    - Jony (restraint): one accent stripe carries the visual identity; the
      glyph (when present) carries the citizen-recognition anchor. Nothing
      else competes for attention.

  Glyph render strategy (PR-SYM-6b3):
    - assets under `frontend/public/party-symbols/` are pre-sanitized at
      author time by `lib/party-symbols/sanitizer.ts` (node-only). The
      runtime renderer never imports the sanitizer; it just builds the
      static URL via `glyphUrlFor(path)` and emits an `<img>` tag.
    - on fetch / decode error the `<img>` is hidden (`hidden` flipped
      from `onerror`) so a broken asset never leaves a placeholder behind
      per the no-placeholder doctrine.
-->
<script lang="ts" module>
  /**
   * Resolve a `dim_parties.election_symbol_asset_path` value to a runtime
   * URL the browser can fetch. Returns `null` when the path is absent so
   * the template can branch on truthiness.
   *
   * Pure (no DOM, no fetch) so vitest pins the contract in node.
   *
   * Re-exported from `PartySymbolGlyph.svelte` so existing test fixtures
   * and external imports keep working after the glyph renderer was
   * extracted into a shared component (PR-SYM-6h).
   */
  export { glyphUrlFor } from "./PartySymbolGlyph.svelte";
</script>

<script lang="ts">
  import { getPartyColor } from "./colors/resolver";
  import PartySymbolGlyph from "./PartySymbolGlyph.svelte";
  import { link } from "./links";
  import type { WinnerInfo } from "./data";

  interface Props { winner: WinnerInfo }
  let { winner }: Props = $props();

  // The resolver expects a `party_id`. Older fixtures may omit it; fall
  // back to a derived id from the short name so the algorithmic tier
  // still produces something deterministic rather than throwing.
  const resolved = $derived(
    getPartyColor(
      winner.party_id ?? `parties.IN.${winner.party_short || "UNK"}`,
      winner.brand_colour_hex
        ? {
            party_id: winner.party_id ?? "",
            brand_colour: {
              hex: winner.brand_colour_hex,
              confidence: winner.brand_colour_confidence ?? "low",
            },
          }
        : null,
    ),
  );

  // PR-2 of TODO/20260612-party-rendering-and-party-pages-plan.md:
  // the party-short label becomes a navigate-to-detail affordance when
  // the canonical `link.party()` resolver returns a non-null slug.
  // UNK / null party_id / explicit overrides without a per-party page
  // (e.g. NOTA via the link builder's own null path) keep the bare
  // text - the citizen sees no broken link.
  const party_href = $derived(link.party(winner.party_id));
</script>

<div class="flex items-start gap-3" data-testid="winner-badge">
  <!-- Accent stripe: identity. Coloured by the resolved tier. -->
  <span
    class="block w-1.5 self-stretch rounded-sm shrink-0"
    style="background-color: {resolved.hex};"
    aria-hidden="true"
  ></span>
  <div class="min-w-0 flex-1">
    <div class="text-xs uppercase text-slate-500">Winner</div>
    <div class="font-semibold truncate">{winner.name}</div>
    <div class="flex items-center gap-2 mt-0.5">
      <PartySymbolGlyph
        assetPath={winner.election_symbol_asset_path}
        size={20}
        class="w-5 h-5"
        fallback="placeholder"
      />
      {#if party_href}
        <a class="text-slate-500 text-sm truncate hover:underline" href={party_href}>{winner.party_short}</a>
      {:else}
        <span class="text-slate-500 text-sm truncate">{winner.party_short}</span>
      {/if}
    </div>
  </div>
</div>
