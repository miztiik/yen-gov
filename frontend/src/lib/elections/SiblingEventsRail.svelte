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
     (one spotlight, monochrome).
   - The rail NAVIGATES years (tap a chip = go to that election).
     COMPARING is a deliberate act offered as a soft, inviting CTA
     BELOW the rail (Jony + Citizen 2026-06-18: not a right-parked
     button, not a hidden tap-mode) - one ready "with {prior}" pairing
     plus "or another year" -> the compare page's two dropdowns.
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

  interface Props {
    model: SiblingEventsRailModel;
  }
  let { model }: Props = $props();

  let nav_el: HTMLElement | undefined = $state();

  // Soft compare CTA (Jony + Citizen 2026-06-18): the rail NAVIGATES
  // years (tap a chip = go to that election); COMPARING is a deliberate
  // act offered as a gentle invitation below the rail, not a mode on the
  // rail. `model.compare_href` is the prior-vs-current pairing; the
  // compare page's two dropdowns let the citizen pick any other.

  // Edge-fade overflow affordance. The left/right fades signal
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
            <a
              href={ev.href}
              aria-current={ev.is_current ? "page" : undefined}
              data-active={ev.is_current}
              data-testid={ev.is_current
                ? "sibling-events-rail-current"
                : "sibling-events-rail-chip"}
              title={ev.display}
              class="inline-flex shrink-0 items-center rounded-yen-pill border px-3 py-1.5 text-sm font-medium tabular-nums transition-colors {ev.is_current
                ? 'border-slate-900 bg-slate-900 text-white'
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

    </div>

    {#if model.compare_href && model.prior_year !== null}
      <!-- Soft, inviting compare CTA (not parked on the right): one
           ready pairing (vs the prior election) + an invitation to pick
           another year on the compare page. The rail above stays
           navigation-only (tap a year = go there). -->
      <div
        class="flex flex-wrap items-center gap-x-2 gap-y-1 px-0.5 text-sm"
        data-testid="sibling-events-rail-compare-cta"
      >
        <span class="text-slate-500">See how this election compares</span>
        <a
          href={model.compare_href}
          data-testid="sibling-events-rail-compare-ready"
          class="inline-flex items-center rounded-yen-pill border border-slate-300 bg-white px-3 py-1 font-medium text-slate-800 transition-colors hover:border-slate-900 hover:bg-slate-900 hover:text-white"
        >
          with {model.prior_year}
        </a>
        <a
          href={model.compare_href}
          data-testid="sibling-events-rail-compare-another"
          class="text-slate-500 underline-offset-2 transition-colors hover:text-slate-900 hover:underline"
        >
          or another year &rarr;
        </a>
      </div>
    {/if}
  </div>
{/if}
