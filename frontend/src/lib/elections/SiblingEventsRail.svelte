<!--
  SiblingEventsRail - year-chip rail between `<StateEventHero>` and
  `<StateEventMap>` on `/<state>/elections/<event>`.

  R4 of TODO/20260615-state-election-event-page-redesign-plan.md
  (2026-06-15) - the J-elevated-4 verdict baked into the row spec.
  Replaces the deleted "Prev / Next / Compare ->" text strip per the
  user's 2026-06-15 direction ("dont want arrows for compare - common
  jony make the app for 2027 ready, not 1990 ready"). Reference class:
  Spotify Now Playing, Apple Music year-picker, Instagram story-tray,
  Linear filter chips.

  Rules baked in:
   - Years come pre-sorted ASC from the projection (oldest -> newest);
     citizen reads left-to-right in time.
   - Active chip = filled `bg-slate-900 text-white` (the single
     spotlight); other chips are MUTED (`text-slate-500`) so the
     current year reads as in-focus. NO winner-colour underline
     (Jony 2026-06-18: the citizen called the per-chip colours
     unnecessary noise - one spotlight, monochrome).
   - Compare is a TOGGLE, not a dropdown (Jony 2026-06-18): tap
     "Compare" -> the rail enters compare mode (earlier chips become
     tappable targets, a hint shows) -> tap an earlier year to compare
     it against the current event. The rail the citizen already reads
     IS the picker; no popover, no list.
   - Mobile: `overflow-x-auto` + `scroll-snap-type: x mandatory` +
     `scroll-snap-align: center` per pill - thumb-flick lands the
     next year centered (IG-tray ergonomic).
   - On mount the active chip `scrollIntoView({inline: "center"})` so
     the citizen's year is always centered first paint.
   - When `events.length === 1` (J-elevated-4 single-event pin) the
     rail renders ONE filled pill, centered; no Compare pill, no
     scroll-snap, no sticky.
-->
<script lang="ts">
  import type { SiblingEventsRailModel } from "./sibling-events-rail-model";
  import { link } from "../links";
  import { navigate } from "../url";

  interface Props {
    model: SiblingEventsRailModel;
  }
  let { model }: Props = $props();

  let nav_el: HTMLElement | undefined = $state();

  // Compare mode (Jony 2026-06-18): tap "Compare", then tap an EARLIER
  // year to compare the current event against it. Replaces the dropdown
  // picker - a dropdown is the 1990 pattern we rejected; the rail the
  // citizen already reads IS the picker. Comparison reads older -> current.
  let compare_mode = $state(false);
  const earlier_ids = $derived(
    new Set(model.compare_options.map((o) => o.event_id)),
  );
  const has_earlier = $derived(model.compare_options.length > 0);
  const current_year = $derived(
    model.events.find((c) => c.is_current)?.year_label ?? "",
  );

  // In compare mode a chip click compares (earlier -> current) instead of
  // navigating to that year's page; any click then exits the mode.
  function onChipClick(ev_id: string, e: MouseEvent): void {
    if (!compare_mode) return;
    e.preventDefault();
    if (earlier_ids.has(ev_id)) {
      navigate(
        link.compareElections(model.state_slug, ev_id, model.current_event_id),
      );
    }
    compare_mode = false;
  }

  // PR2: edge-fade overflow affordance. The left/right fades signal
  // "more years this way" ONLY when the rail actually overflows;
  // recomputed on scroll, on model change, and on viewport resize.
  let fade_left = $state(false);
  let fade_right = $state(false);
  function updateFades(): void {
    const el = nav_el;
    if (!el) {
      fade_left = false;
      fade_right = false;
      return;
    }
    // Only fade when the rail actually overflows; otherwise both edges
    // stay clean (a short rail that fits must not show a spurious fade).
    const overflows = el.scrollWidth > el.clientWidth + 1;
    fade_left = overflows && el.scrollLeft > 1;
    fade_right =
      overflows && el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
  }

  // Scroll the current chip to centre on mount and whenever the
  // rail's identity changes (event navigation reuses this same
  // component). `block: "nearest"` so the page doesn't shift
  // vertically. We resolve the current pill via querySelector
  // because Svelte's bind:this doesn't compose with `{#each}`-time
  // conditional targets - cleaner than carrying an array of refs.
  $effect(() => {
    void model.events.find((c) => c.is_current)?.event_id; // re-fire on event change
    if (nav_el) {
      const current = nav_el.querySelector<HTMLAnchorElement>(
        '[data-testid="sibling-events-rail-current"]',
      );
      if (current) {
        try {
          current.scrollIntoView({ inline: "center", block: "nearest" });
        } catch {
          // older browsers without ScrollOptions support: silent no-op.
        }
      }
    }
    updateFades();
  });

  // Recompute fades on viewport resize (overflow can flip when the
  // surrounding column reflows). Initial compute runs here too.
  $effect(() => {
    const onResize = () => updateFades();
    window.addEventListener("resize", onResize);
    updateFades();
    return () => window.removeEventListener("resize", onResize);
  });

  // Esc leaves compare mode.
  $effect(() => {
    if (!compare_mode) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") compare_mode = false;
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const single_event = $derived(model.events.length === 1);
</script>

{#if model.events.length > 0}
  <div class="space-y-1.5">
    <div class="relative -mx-2 flex items-center gap-2 px-2">
      <div class="relative min-w-0 flex-1">
        <nav
          bind:this={nav_el}
          onscroll={updateFades}
          class="flex gap-2 overflow-x-auto whitespace-nowrap py-2 {single_event
            ? 'justify-center'
            : ''}"
          style="scroll-snap-type: x mandatory;"
          aria-label="Sibling elections"
          data-testid="sibling-events-rail"
        >
          {#each model.events as ev (ev.event_id)}
            {@const targetable = compare_mode && earlier_ids.has(ev.event_id)}
            <a
              href={ev.href}
              aria-current={ev.is_current ? "page" : undefined}
              data-active={ev.is_current}
              data-testid={ev.is_current
                ? "sibling-events-rail-current"
                : "sibling-events-rail-chip"}
              title={ev.display}
              onclick={(e) => onChipClick(ev.event_id, e)}
              class="inline-flex shrink-0 items-center rounded-yen-pill border px-3 py-1.5 text-sm font-medium tabular-nums transition-colors {ev.is_current
                ? 'border-slate-900 bg-slate-900 text-white'
                : compare_mode
                  ? targetable
                    ? 'border-slate-400 bg-white text-slate-900 hover:bg-slate-100'
                    : 'border-slate-200 bg-white text-slate-300'
                  : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-900'}"
              style="scroll-snap-align: center;"
            >
              {ev.year_label}
            </a>
          {/each}
        </nav>

        <!-- Edge fades: shown only while the rail overflows that side. -->
        {#if fade_left}
          <div
            aria-hidden="true"
            data-testid="sibling-events-rail-fade-left"
            class="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-white to-transparent"
          ></div>
        {/if}
        {#if fade_right}
          <div
            aria-hidden="true"
            data-testid="sibling-events-rail-fade-right"
            class="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-white to-transparent"
          ></div>
        {/if}
      </div>

      {#if has_earlier}
        <button
          type="button"
          onclick={() => (compare_mode = !compare_mode)}
          aria-pressed={compare_mode}
          data-testid="sibling-events-rail-compare-toggle"
          class="shrink-0 rounded-yen-pill border px-3 py-1.5 text-sm font-medium transition-colors {compare_mode
            ? 'border-slate-900 bg-slate-900 text-white hover:bg-slate-700'
            : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-100'}"
        >
          {compare_mode ? "Cancel" : "Compare"}
        </button>
      {/if}
    </div>

    {#if compare_mode}
      <p
        class="px-0.5 text-xs text-slate-500"
        data-testid="sibling-events-rail-compare-hint"
      >
        Tap an earlier year to compare with {current_year}.
      </p>
    {/if}
  </div>
{/if}
