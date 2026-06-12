<!--
  PartyTooltip — the hover/focus/click-pin popover ridden by PartyPill.

  Plan-doc: TODO/20260612-party-rendering-and-party-pages-plan.md PR-1.
  Doctrine: docs/architecture/frontend/party-rendering.md ("Tooltip (PR-1)").

  Content shape (Jony A2 verdict):
    Header  : symbol glyph (ONLY when symbol_asset truthy; PartySymbolGlyph
              fallback="silent" hides the slot if asset missing per
              Jony A3 + user 2026-06-12) + party short in semibold.
    Body    : full name; "Founded YYYY" iff founded_year populated;
              "Dissolved YYYY" iff dissolved_year populated; recognition
              badge with lucide `landmark` glyph iff recognition_scope
              populated; native script italic iff name_native_script
              populated.
    Footer  : Wikipedia external link (target="_blank" rel="noopener
              noreferrer") iff wikipedia URL populated. Renders "Wikipedia"
              as text when the lucide `external-link` icon is unregistered
              (TopicIcon's silent-miss doctrine; the link stays clickable).

  Sentinel handling (per docs/concepts/party-identity.md section 4 +
  Jony A2 verdict): NOTA / IND / UNK rows surface only the short + full
  + recognition badge (`recognition_scope === "sentinel"`); the founded
  / dissolved / native_script / wiki lines are suppressed so we never
  cite "Founded 2013" for NOTA (the date is the PUCL v Union of India
  ruling, not a party founding event). UNK never reaches this component
  - PartyPill's `shouldOpenTooltipFor` guard rejects it upstream.

  Positioning (Jony A4 verdict): hand-rolled CSS fixed-position with
  viewport-edge clamping, mirroring ChartTooltip.svelte. No
  `@floating-ui` dependency.

  Interaction: pointer-events: auto so the wiki link is clickable.
  Escape / click-outside dismissal lives in PartyPill (the owner of the
  tooltip state). Hover handlers on the card itself keep the tooltip
  open while the cursor is inside it (Escape still closes); when the
  cursor leaves both the pill AND the card, the unpinned tooltip
  dismisses.
-->
<script lang="ts" module>
  import type { PartyMeta } from "../view-models/parties";

  /**
   * Renderable view-model for one tooltip card. The Svelte template
   * just walks these fields; tests assert on this projection via
   * `buildTooltipViewModel` without mounting Svelte (the project does
   * not install @testing-library/svelte; see frontend/src/lib/
   * Skeleton.svelte + IndicatorCard.svelte for the precedent).
   */
  export interface TooltipViewModel {
    /** True while the loader is in-flight; the template renders a
     *  minimal loading skeleton. */
    isLoading: boolean;
    /** True when the loader resolved `null` (party_id absent from
     *  parties.csv). The template renders nothing - PartyPill should
     *  not have opened the tooltip in this case. */
    isMissing: boolean;
    /** True iff the meta row carried a non-empty `symbol_asset`. The
     *  template gates the PartySymbolGlyph render on this so we never
     *  paint a placeholder where the upstream asset is blank. */
    hasSymbol: boolean;
    /** Repo-relative asset path, or empty string when hasSymbol is
     *  false. (PartySymbolGlyph's `fallback="silent"` mode also
     *  collapses empty input - the explicit boolean guard avoids
     *  rendering the wrapping flex slot.) */
    symbolAsset: string;
    /** Party short (display label). */
    short: string;
    /** Party full name; null when blank. */
    full: string | null;
    /** Citizen-readable founded line ("Founded 1980"); null when
     *  founded_year is absent OR when the party is a sentinel. */
    foundedLine: string | null;
    /** Citizen-readable dissolved line ("Dissolved 1996"); null when
     *  dissolved_year is absent OR when the party is a sentinel. */
    dissolvedLine: string | null;
    /** ECI recognition scope (e.g. "national", "state",
     *  "unrecognised_registered", "sentinel"). Null when blank. */
    recognitionScope: string | null;
    /** Non-Latin party name (e.g. "आम आदमी पार्टी"). Null when blank
     *  OR when the party is a sentinel. */
    nativeScript: string | null;
    /** Wikipedia URL; null when blank OR when the party is a sentinel
     *  (sentinels have no wiki entry). */
    wikipediaUrl: string | null;
  }

  /**
   * Project a PartyMeta + loading flag into the renderable view-model.
   * Pure; exported so vitest covers every conditional without a DOM
   * mount. Sentinel handling lives here so the rendering template
   * stays free of `if (is_sentinel)` branches.
   */
  export function buildTooltipViewModel(
    meta: PartyMeta | null,
    loading: boolean,
  ): TooltipViewModel {
    if (loading) {
      return {
        isLoading: true,
        isMissing: false,
        hasSymbol: false,
        symbolAsset: "",
        short: "",
        full: null,
        foundedLine: null,
        dissolvedLine: null,
        recognitionScope: null,
        nativeScript: null,
        wikipediaUrl: null,
      };
    }
    if (!meta) {
      return {
        isLoading: false,
        isMissing: true,
        hasSymbol: false,
        symbolAsset: "",
        short: "",
        full: null,
        foundedLine: null,
        dissolvedLine: null,
        recognitionScope: null,
        nativeScript: null,
        wikipediaUrl: null,
      };
    }
    const hasSymbol = !!meta.symbol_asset && meta.symbol_asset.length > 0;
    const isSentinel = meta.is_sentinel;
    return {
      isLoading: false,
      isMissing: false,
      hasSymbol,
      symbolAsset: hasSymbol ? meta.symbol_asset! : "",
      short: meta.short,
      full: meta.full,
      // Sentinels suppress founded / dissolved / native script / wiki
      // even when the upstream row carries truthy values; per
      // party-identity.md section 4 the date on NOTA is the ruling
      // year, not a founding event.
      foundedLine:
        !isSentinel && meta.founded_year != null
          ? `Founded ${meta.founded_year}`
          : null,
      dissolvedLine:
        !isSentinel && meta.dissolved_year != null
          ? `Dissolved ${meta.dissolved_year}`
          : null,
      recognitionScope: meta.recognition_scope,
      nativeScript: isSentinel ? null : meta.name_native_script,
      wikipediaUrl: isSentinel ? null : meta.wikipedia,
    };
  }

  /** Compute the fixed-position card placement given the anchor rect
   *  (the PartyPill's bounding box) and the viewport size. Mirrors
   *  ChartTooltip.svelte's edge-clamp pattern. Pure; tests pin it
   *  against synthetic rects. */
  export function clampTooltipPlacement(
    anchor: { left: number; right: number; top: number; bottom: number },
    cardSize: { width: number; height: number },
    viewport: { width: number; height: number },
  ): { left: number; top: number } {
    const margin = 6;
    const edge = 4;
    // Default: card pinned below the pill, left-aligned with it.
    let left = anchor.left;
    let top = anchor.bottom + margin;
    // If overflowing the right edge, slide left so the card stays
    // inside the viewport.
    if (left + cardSize.width + edge > viewport.width) {
      left = viewport.width - cardSize.width - edge;
    }
    // If overflowing the bottom, flip above the pill.
    if (top + cardSize.height + edge > viewport.height) {
      const above = anchor.top - cardSize.height - margin;
      if (above >= edge) top = above;
    }
    if (left < edge) left = edge;
    if (top < edge) top = edge;
    return { left, top };
  }
</script>

<script lang="ts">
  import { onMount } from "svelte";
  import PartySymbolGlyph from "../PartySymbolGlyph.svelte";
  import TopicIcon from "../TopicIcon.svelte";
  // `PartyMeta` type is already imported by the `<script module>` block
  // above; re-importing it here would shadow the module-scope binding
  // and trip "Duplicate identifier 'PartyMeta'" (Svelte 5 merges the
  // two scopes for type-checking).
  import { loadPartyMeta } from "../view-models/parties";

  interface Props {
    party_id: string;
    /** Anchor rect of the trigger (the PartyPill bounding box). The
     *  tooltip pins relative to this; pass `null` to render off-screen
     *  while the anchor isn't measured yet. */
    anchor: DOMRect | null;
    /** Caller invokes this when the tooltip should dismiss
     *  (Esc / click-outside / hover-leave). */
    onClose?: () => void;
  }

  const { party_id, anchor, onClose }: Props = $props();

  let meta: PartyMeta | null = $state(null);
  let loading: boolean = $state(true);
  let card: HTMLDivElement | undefined = $state(undefined);
  let placement: { left: number; top: number } = $state({
    left: -9999,
    top: -9999,
  });

  // Fire the loader once per (party_id, mount) cycle. The view-model
  // cache memoises across mounts so re-hovering the same party_id is
  // cheap.
  onMount(() => {
    let cancelled = false;
    loadPartyMeta(party_id).then((result) => {
      if (cancelled) return;
      meta = result;
      loading = false;
    });
    return () => {
      cancelled = true;
    };
  });

  const view = $derived(buildTooltipViewModel(meta, loading));

  // Reposition whenever the anchor or measured card size changes.
  $effect(() => {
    if (!anchor || !card) {
      placement = { left: -9999, top: -9999 };
      return;
    }
    const rect = card.getBoundingClientRect();
    placement = clampTooltipPlacement(
      {
        left: anchor.left,
        right: anchor.right,
        top: anchor.top,
        bottom: anchor.bottom,
      },
      { width: rect.width || 280, height: rect.height || 160 },
      { width: window.innerWidth, height: window.innerHeight },
    );
  });

  function handleCardMouseLeave() {
    // Owner (PartyPill) decides whether to actually close based on
    // its own pinned state.
    onClose?.();
  }
</script>

{#if !view.isMissing}
  <div
    bind:this={card}
    class="party-tooltip fixed z-50 max-w-[280px] min-w-[220px] rounded-lg bg-white text-left ring-1 ring-slate-200/80 shadow-xl overflow-hidden"
    style:left="{placement.left}px"
    style:top="{placement.top}px"
    style:opacity={anchor ? "1" : "0"}
    onmouseleave={handleCardMouseLeave}
    role="tooltip"
    data-component="party-tooltip"
    data-party-id={party_id}
  >
    {#if view.isLoading}
      <div class="px-3 py-2 text-xs text-slate-500" data-testid="tooltip-loading">
        Loading…
      </div>
    {:else}
      <div class="flex items-center gap-2 px-3 pt-2.5 pb-2 border-b border-slate-100">
        {#if view.hasSymbol}
          <PartySymbolGlyph
            assetPath={view.symbolAsset}
            size={28}
            fallback="silent"
            class="rounded-sm"
          />
        {/if}
        <span class="font-semibold text-sm text-slate-800">{view.short}</span>
      </div>
      <div class="px-3 py-2 space-y-1">
        {#if view.full}
          <div class="text-[13px] text-slate-700 leading-snug">{view.full}</div>
        {/if}
        {#if view.foundedLine}
          <div class="text-[11px] text-slate-500" data-testid="tooltip-founded">
            {view.foundedLine}
          </div>
        {/if}
        {#if view.dissolvedLine}
          <div class="text-[11px] text-slate-500" data-testid="tooltip-dissolved">
            {view.dissolvedLine}
          </div>
        {/if}
        {#if view.recognitionScope}
          <div
            class="flex items-center gap-1 text-[11px] text-slate-500"
            data-testid="tooltip-recognition"
          >
            <TopicIcon name="landmark" cls="w-3 h-3 text-slate-400 shrink-0" />
            <span>{view.recognitionScope}</span>
          </div>
        {/if}
        {#if view.nativeScript}
          <div
            class="text-[11px] text-slate-500 italic"
            data-testid="tooltip-native-script"
          >
            {view.nativeScript}
          </div>
        {/if}
      </div>
      {#if view.wikipediaUrl}
        <div class="px-3 pb-2 pt-1 border-t border-slate-100">
          <a
            href={view.wikipediaUrl}
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-[11px] text-blue-600 hover:underline"
            data-testid="tooltip-wikipedia"
          >
            <TopicIcon name="external-link" cls="w-3 h-3 shrink-0" />
            <span>Wikipedia</span>
          </a>
        </div>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .party-tooltip {
    pointer-events: auto;
    transition: opacity 90ms ease-out;
  }
</style>
