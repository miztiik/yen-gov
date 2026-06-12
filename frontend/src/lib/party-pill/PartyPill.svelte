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
   *
   * Tooltip (PR-1 of TODO/20260612-party-rendering-and-party-pages-plan.md):
   *   The pill carries a hover/focus/click-pin popover that loads
   *   parties.csv metadata on demand. State machine + UNK guard are
   *   PURE helpers (`tooltipReducer`, `shouldOpenTooltipFor`) so
   *   vitest can pin the contract without mounting Svelte; the
   *   template wires the four DOM events (mouseenter / mouseleave /
   *   focus / blur / click) + window-level Escape + click-outside
   *   listeners to those helpers.
   */
  export {
    pickInkForFill,
    resolvePartyPill,
    type PartyPillResolved,
    type PartyPillTreatment,
  } from "./party-pill-resolve";

  /** Tooltip open/pin state machine. `open` controls whether the
   *  popover is rendered at all; `pinned` controls whether a hover-leave
   *  closes it. UNK / null party_id rows never open the tooltip
   *  (UNK is operator telemetry, not a citizen entity). */
  export interface TooltipState {
    readonly open: boolean;
    readonly pinned: boolean;
  }

  /** Pure: does this party_id qualify for a tooltip? UNK is the only
   *  party_id explicitly excluded - it's the resolver fallback for
   *  unresolved rows and has no citizen-meaningful identity to show. */
  export function shouldOpenTooltipFor(
    party_id: string | null | undefined,
  ): boolean {
    if (!party_id) return false;
    if (party_id === "parties.IN.UNK") return false;
    return true;
  }

  /** Pure: derive the next tooltip state from an interaction. Tests
   *  drive every transition without mounting the component. */
  export function tooltipReducer(
    state: TooltipState,
    action: "hover" | "leave" | "click" | "escape" | "close",
    party_id: string | null | undefined,
  ): TooltipState {
    switch (action) {
      case "hover":
        if (!shouldOpenTooltipFor(party_id)) return state;
        return { open: true, pinned: state.pinned };
      case "leave":
        // Hover-leave only dismisses an UNPINNED tooltip; click-pinned
        // tooltips survive until Esc / click-outside / explicit close.
        if (state.pinned) return state;
        return { open: false, pinned: false };
      case "click":
        if (!shouldOpenTooltipFor(party_id)) return state;
        // Click toggles pin: first click opens-and-pins; second click
        // closes-and-unpins.
        if (state.pinned) return { open: false, pinned: false };
        return { open: true, pinned: true };
      case "escape":
      case "close":
        return { open: false, pinned: false };
    }
  }

  /** Idempotent closed-state factory; exported for tests + the
   *  template's `$state(...)` initialiser. */
  export function tooltipClosed(): TooltipState {
    return { open: false, pinned: false };
  }
</script>

<script lang="ts">
  import PartyTooltip from "./PartyTooltip.svelte";
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
     *  pattern). When omitted renders as a `<span>` (display only).
     *  PR-1: click also toggles the tooltip pin state, so a caller's
     *  `onclick` runs AND the pill pins/unpins on the same gesture
     *  (compose, never replace). */
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

  // --- Tooltip wiring (PR-1) ----------------------------------------------

  let tooltip = $state<TooltipState>(tooltipClosed());
  let anchorRect: DOMRect | null = $state(null);
  let trigger: HTMLElement | undefined = $state(undefined);

  function captureAnchor(): void {
    if (trigger) anchorRect = trigger.getBoundingClientRect();
  }

  function handlePointerEnter(): void {
    captureAnchor();
    tooltip = tooltipReducer(tooltip, "hover", party_id);
  }
  function handlePointerLeave(): void {
    tooltip = tooltipReducer(tooltip, "leave", party_id);
  }
  function handleClick(): void {
    // Compose: run the caller's onclick first (existing semantics -
    // e.g. PartyBar's mute toggle), then toggle pin state. The pin
    // toggle is suppressed for UNK / null via tooltipReducer's own
    // guard.
    onclick?.();
    captureAnchor();
    tooltip = tooltipReducer(tooltip, "click", party_id);
  }
  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === "Escape" && tooltip.open) {
      tooltip = tooltipReducer(tooltip, "escape", party_id);
    }
  }
  function handleWindowClick(e: MouseEvent): void {
    if (!tooltip.open) return;
    const target = e.target as Node | null;
    if (!target) return;
    if (trigger?.contains(target)) return;
    // The tooltip card itself sets pointer-events: auto + carries
    // data-component="party-tooltip"; clicks inside it should NOT
    // dismiss. Find the closest party-tooltip ancestor.
    if (
      target instanceof Element &&
      target.closest('[data-component="party-tooltip"]')
    ) {
      return;
    }
    tooltip = tooltipReducer(tooltip, "close", party_id);
  }
</script>

<svelte:window onkeydown={handleKeydown} onclick={handleWindowClick} />

{#if onclick}
  <button
    bind:this={trigger}
    type="button"
    class="party-pill party-pill--{size} party-pill--{resolved.treatment}"
    class:party-pill--muted={muted}
    data-component="party-pill"
    data-treatment={resolved.treatment}
    data-party-id={party_id ?? ""}
    style={pill_style}
    onclick={handleClick}
    onmouseenter={handlePointerEnter}
    onmouseleave={handlePointerLeave}
    onfocus={handlePointerEnter}
    onblur={handlePointerLeave}
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
    bind:this={trigger}
    class="party-pill party-pill--{size} party-pill--{resolved.treatment}"
    class:party-pill--muted={muted}
    data-component="party-pill"
    data-treatment={resolved.treatment}
    data-party-id={party_id ?? ""}
    style={pill_style}
    onclick={handleClick}
    onmouseenter={handlePointerEnter}
    onmouseleave={handlePointerLeave}
    onfocus={handlePointerEnter}
    onblur={handlePointerLeave}
    role="presentation"
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

{#if tooltip.open && party_id && shouldOpenTooltipFor(party_id)}
  <PartyTooltip
    party_id={party_id}
    anchor={anchorRect}
    onClose={() => (tooltip = tooltipReducer(tooltip, "close", party_id))}
  />
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
