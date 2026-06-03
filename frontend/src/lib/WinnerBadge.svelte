<!--
  WinnerBadge: citizen-facing constituency-result winner pane (PR-SYM-6b).

  Renders the winner's name + party with:
    - an accent stripe coloured by the 3-tier resolver (getPartyColor)
    - the party's ballot-symbol glyph when `election_symbol_asset_path`
      is populated on dim_parties (PR-SYM-6b3); no placeholder otherwise
    - a small "source" chip declaring colour provenance (anchor / brand /
      fallback)

  Hans + Jony lens:
    - Hans (honesty): the source chip MUST show "fallback" when the renderer
      hashed party_id rather than using an editorial colour. Hiding the
      fallback tier is dishonest.
    - Jony (restraint): one chip, low contrast, secondary weight. The
      accent stripe carries the visual identity; the glyph (when present)
      carries the citizen-recognition anchor; the chip carries the colour
      provenance.

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
  import { chipFor } from "./colors/chip";
  import PartySymbolGlyph from "./PartySymbolGlyph.svelte";
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
  const chip = $derived(chipFor(resolved.source));
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
      />
      <span class="text-slate-500 text-sm truncate">{winner.party_short}</span>
      <!-- Source chip: provenance. Border-style encodes the tier so it is
           readable without colour vision. -->
      <span
        class="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded {chip.className}"
        title={chip.tooltip}
        data-testid="winner-colour-source"
        data-source={resolved.source}
      >{chip.label}</span>
    </div>
  </div>
</div>
