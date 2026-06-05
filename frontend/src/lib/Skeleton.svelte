<script lang="ts" module>
  // Skeleton - generic loading placeholder primitive (U5 sub-plan U5a).
  //
  // A single calm shimmer surface sized by props. Used wherever a
  // citizen-facing card needs to disclose "the data is loading" without
  // collapsing the page layout (the chart cards on /s/<state>, the
  // /docs/indicator page, the ChartShell's loading state). The shimmer
  // respects `prefers-reduced-motion` and collapses to a softened
  // sunken surface so accessibility-sensitive users do not get an
  // animating element (per the motion-tokens contract in
  // [docs/architecture/frontend/design-system.md](../../docs/architecture/frontend/design-system.md)).
  //
  // Tokens consumed (drift-locked by
  // frontend/src/contracts/app-tokens.test.ts):
  //   --surface-sunken  -> base fill
  //   --r-md            -> default corner radius (rounded prop = true)
  //   --dur-slow        -> shimmer cycle reference (the keyframes use a
  //                        fixed 1500ms because shimmer rhythm is a
  //                        visual constant, not a token, but the var
  //                        gives a future re-skin one knob to tune)
  //
  // The module-scope `skeletonStyle` helper is the testable surface
  // (vitest is node-env per [docs/architecture/frontend/design-system.md](../../docs/architecture/frontend/design-system.md)
  // section "Drift contract" + GeoBreadcrumb.svelte's `computeCrumbs`
  // precedent); the Svelte body is the rendering wrapper.

  /**
   * Build the inline-style string applied to the root skeleton element.
   * Pure: no DOM, no defaults from outside (caller-supplied values are
   * authoritative). Returns an empty string when both dims are omitted
   * so a parent stylesheet can take over (the leaf still renders, just
   * without inline sizing).
   */
  export function skeletonStyle(args: {
    width?: string;
    height?: string;
  }): string {
    const parts: string[] = [];
    if (args.width) parts.push(`width: ${args.width};`);
    if (args.height) parts.push(`height: ${args.height};`);
    return parts.join(" ");
  }
</script>

<script lang="ts">
  interface Props {
    /** CSS length for the skeleton width. Defaults to 100% so the
     *  leaf fills its parent slot. */
    width?: string;
    /** CSS length for the skeleton height. Defaults to 4rem so a card-
     *  sized loading box appears even when no parent has sized us. */
    height?: string;
    /** Whether to round the corners via --r-md. Defaults to true; pass
     *  false for full-bleed bands. */
    rounded?: boolean;
    /** Extra Tailwind utility classes for the rare positioning case
     *  (margin, max-width). Layout tweaks only; visual tokens live in
     *  this component, not the call site. */
    cls?: string;
  }

  let {
    width = "100%",
    height = "4rem",
    rounded = true,
    cls = "",
  }: Props = $props();

  // $derived so prop changes (e.g. a parent resizing the card) re-flow
  // the inline style; per the Svelte 5 "state_referenced_locally"
  // diagnostic, a bare `const` only captures the initial prop values.
  const style = $derived(skeletonStyle({ width, height }));
</script>

<div
  class="yen-skeleton {rounded ? 'yen-skeleton--rounded' : ''} {cls}"
  data-component="skeleton"
  {style}
></div>

<style>
  .yen-skeleton {
    background: var(--surface-sunken);
    position: relative;
    overflow: hidden;
    display: block;
  }
  .yen-skeleton--rounded {
    border-radius: var(--r-md);
  }
  .yen-skeleton::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgb(255 255 255 / 0.55),
      transparent
    );
    transform: translateX(-100%);
    animation: yen-skeleton-shimmer 1500ms cubic-bezier(0.4, 0, 0.2, 1)
      infinite;
  }
  @keyframes yen-skeleton-shimmer {
    100% {
      transform: translateX(100%);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .yen-skeleton::after {
      animation: none;
      display: none;
    }
    .yen-skeleton {
      opacity: 0.75;
    }
  }
</style>
