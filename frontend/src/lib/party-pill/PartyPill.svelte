<script module lang="ts">
  /**
   * E2 PartyPill (parent plan §25.3) - the SINGLE coloured party
   * token used everywhere AC results show a party (races-board rows,
   * AC drill-down, legend chips, histogram bins). No per-view pill
   * variants; one component, schema-driven via the 3-tier party-
   * colour resolver.
   *
   * Doctrine ties (parent §25.3 + resolver contract):
   *   - Anchor tier   -> full-bleed coloured pill (background = hex,
   *                       text = pickInkForFill(hex)).
   *   - Brand tier    -> paper-neutral body + coloured accent ring
   *                       (resolver forbids brand colour as full chrome
   *                       fill; the chip BODY stays paper-neutral, the
   *                       coloured ring identifies the party).
   *   - Fallback tier -> paper-neutral body + small coloured swatch
   *                       chip + label (a swatch alone is never allowed).
   *   - Neutral       -> `--party-neutral` body + `--party-neutral-text`
   *                       ink (the "Unknown party" affordance; null
   *                       `party_id` or no row data).
   *
   *   - Label rule: pill ALWAYS carries `party_short` text. A bare
   *     swatch is never allowed (resolver contract).
   *   - Symbol composition: the SVG ballot symbol is NOT inside the
   *     pill - it's a SIBLING glyph laid out by an optional PartyTag
   *     wrapper (separate component). PartyPill stays a leaf.
   *   - CLAUDE.md §0: no aria/role on the pill body itself; visible
   *     affordances only (the coloured chip + the readable label).
   *
   * Re-exports the pure helpers from `<script module>` so vitest can
   * cover the tier-selection logic without a DOM (same pattern as
   * GeoChoropleth + CategoryBar etc.).
   */
  export {
    pickInkForFill,
    resolvePartyPill,
    type PartyPillResolved,
    type PartyPillTreatment,
  } from "./party-pill-resolve";
</script>

<script lang="ts">
  import type { PartyRowForResolver } from "../colors/resolver";
  import { pickInkForFill, resolvePartyPill } from "./party-pill-resolve";

  interface Props {
    /** `parties.IN.<SLUG>` taxonomy id. Null/empty triggers the
     *  neutral treatment (the canonical "unknown party" affordance). */
    party_id?: string | null;
    /** Citizen-readable short label (e.g. "BJP"). Falls back to
     *  "Unknown" if not supplied. */
    party_short?: string | null;
    /** Optional party row carrying `brand_colour`. Pass `null` when
     *  the consumer hasn't joined dim_parties; the resolver skips
     *  the brand tier and goes anchor -> fallback. */
    row?: PartyRowForResolver | null;
    /** Size variant. Default `md`. Compact `sm` for legend chips;
     *  larger `lg` for primary-mention chips in detail views. */
    size?: "sm" | "md" | "lg";
    /** Optional click handler. When supplied the pill renders as a
     *  `<button>` (mute/select affordance like the existing PartyBar
     *  pattern). When omitted renders as a `<span>` (display only). */
    onclick?: () => void;
    /** Optional muted state (visually receded, ~0.4 opacity). Used by
     *  the 25.5 PARTY-WON mode "non-matching cells recede" rule. */
    muted?: boolean;
  }

  const {
    party_id = null,
    party_short = null,
    row = null,
    size = "md",
    onclick,
    muted = false,
  }: Props = $props();

  const resolved = $derived(resolvePartyPill({ party_id, party_short, row }));

  // Compute the pill style based on the resolved treatment.
  const pill_style = $derived.by(() => {
    switch (resolved.treatment) {
      case "anchor": {
        const fill = resolved.hex ?? "#cbd5e1";
        const ink = pickInkForFill(fill);
        return `background-color: ${fill}; color: ${ink}; border-color: ${fill};`;
      }
      case "brand": {
        const ring = resolved.hex ?? "#cbd5e1";
        // Paper-neutral body + coloured ring per resolver doctrine
        return `background-color: var(--surface); color: var(--ink); border-color: ${ring}; border-width: 2px;`;
      }
      case "fallback":
        // Paper-neutral body + small swatch (rendered as ::before via
        // class); label remains primary.
        return `background-color: var(--surface); color: var(--ink); border-color: var(--line);`;
      case "neutral":
      default:
        return `background-color: var(--party-neutral); color: var(--party-neutral-text); border-color: var(--party-neutral);`;
    }
  });

  // Optional small swatch chip rendered next to label for fallback
  // tier (the "swatch + label" doctrine). Returns null hex when no
  // swatch should render (anchor/neutral cover via fill; brand
  // covers via ring).
  const swatch_hex = $derived(
    resolved.treatment === "fallback" ? resolved.hex : null,
  );
</script>

{#if onclick}
  <button
    type="button"
    class="party-pill party-pill--{size} party-pill--{resolved.treatment}"
    class:party-pill--muted={muted}
    data-component="party-pill"
    data-treatment={resolved.treatment}
    data-party-id={party_id ?? ""}
    style={pill_style}
    onclick={onclick}
  >
    {#if swatch_hex}
      <span
        class="party-pill__swatch"
        style="background-color: {swatch_hex};"
      ></span>
    {/if}
    <span class="party-pill__label">{resolved.label}</span>
  </button>
{:else}
  <span
    class="party-pill party-pill--{size} party-pill--{resolved.treatment}"
    class:party-pill--muted={muted}
    data-component="party-pill"
    data-treatment={resolved.treatment}
    data-party-id={party_id ?? ""}
    style={pill_style}
  >
    {#if swatch_hex}
      <span
        class="party-pill__swatch"
        style="background-color: {swatch_hex};"
      ></span>
    {/if}
    <span class="party-pill__label">{resolved.label}</span>
  </span>
{/if}

<style>
  .party-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-family: var(--font-sans);
    font-weight: 600;
    line-height: 1;
    border: 1px solid transparent;
    border-radius: 9999px;
    padding: 0.25rem 0.625rem;
    white-space: nowrap;
    cursor: default;
    transition: opacity 120ms ease-out, transform 120ms ease-out;
  }
  button.party-pill {
    cursor: pointer;
  }
  button.party-pill:hover {
    transform: translateY(-1px);
  }

  /* Sizes */
  .party-pill--sm {
    font-size: 0.6875rem; /* 11px */
    padding: 0.125rem 0.5rem;
  }
  .party-pill--md {
    font-size: 0.8125rem; /* 13px */
  }
  .party-pill--lg {
    font-size: 0.9375rem; /* 15px */
    padding: 0.375rem 0.875rem;
  }

  /* Muted state (E2/25.5 recede rule) */
  .party-pill--muted {
    opacity: 0.4;
  }

  /* Fallback swatch chip */
  .party-pill__swatch {
    width: 0.625rem;
    height: 0.625rem;
    border-radius: 9999px;
    border: 1px solid var(--line);
    flex-shrink: 0;
  }
  .party-pill__label {
    /* Tabular-numeral safety for trailing digits inside the label
       (e.g. "BJP+", "INC-23 seats"). Keeps the layout stable across
       short and long labels. */
    font-variant-numeric: tabular-nums;
  }
</style>
