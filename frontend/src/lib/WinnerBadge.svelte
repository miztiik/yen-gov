<!--
  WinnerBadge: citizen-facing constituency-result winner pane (PR-SYM-6b).

  Renders the winner's name + party with:
    - an accent stripe coloured by the 3-tier resolver (getPartyColor)
    - a small "source" chip declaring provenance (anchor / brand / fallback)

  Hans + Jony lens:
    - Hans (honesty): the source chip MUST show "fallback" when the renderer
      hashed party_id rather than using an editorial colour. Hiding the
      fallback tier is dishonest.
    - Jony (restraint): one chip, low contrast, secondary weight. The
      accent stripe carries the visual identity; the chip carries the
      provenance metadata.

  Ballot-symbol glyph is intentionally NOT rendered here. The schema column
  `dim_parties.election_symbol_asset_path` lands in a follow-up
  (PR-SYM-6b2) that wires the SVG sanitizer pipeline through the loader.
-->
<script lang="ts">
  import { getPartyColor } from "./colors/resolver";
  import { chipFor } from "./colors/chip";
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
