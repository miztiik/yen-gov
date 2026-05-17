<script lang="ts">
  // Left rail: pinned StatePill on top, grouped IA below (P3.3c).
  //
  // The previous flat tools list ("Explore / Analyze Trends / Psephlab /
  // Compare / Settings") with three "Pick a state first" greyed stubs has
  // been replaced — see TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md
  // §"P3.3c" and ADR-0022. The structure is now four groups:
  //
  //     My state · How states compare · Centre and states · Settings
  //
  // Group/item construction is a pure function (`buildRailGroups`) so
  // the IA shape is unit-testable separately from the view. This file is
  // a render-only consumer — there is NO conditional logic on tools or
  // greyed-out items here.
  //
  // Verbs that used to be rail entries:
  //   - "Explore" (the country-level one) → killed; brand wordmark goes home.
  //   - "Analyze Trends" → renamed "Explore trends" under My state.
  //   - "Psephlab" → killed entirely (reachable from election artifacts).
  //   - "Compare" → renamed "Side by side" under How states compare,
  //     emitted only when scope+event are both available (no greyed stub).
  //
  // The pinned `StatePill` replaces the always-open `ScopePicker`; clicking
  // the pill opens the same dropdown.
  //
  // CLAUDE.md §13: any change here must be smoke-tested on /, /t, /about,
  // and /s/tamil-nadu.

  import { route } from "./router.svelte";
  import { scope } from "./scope.svelte";
  import { url } from "./url";
  import { REPO_URL } from "./repo";
  import StatePill from "./StatePill.svelte";
  import { buildRailGroups } from "./rail-groups";
  import {
    fetchElectionEvents,
    defaultEventForState,
    type ElectionEventsCatalogue,
  } from "./election-events";
  import { fetchTopicCatalogue, type TopicCatalogue } from "./catalogue";

  // Per-state default election event for "Side by side". Resolves to null
  // when the state has no election data on disk; in that case the
  // Side-by-side item is omitted from the rail rather than greyed.
  let election_catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then(c => (election_catalogue = c))
    .catch(() => (election_catalogue = null));

  // Topic catalogue → topic.title map. The rail's THIS STATE topic items
  // derive their labels from `topic.title` so that the rail label and the
  // /s/<state>/t/<id> page H1 always agree (Jony 2026-05-16 review). On
  // fetch failure the map stays null and the rail falls back to ids —
  // not pretty but always present.
  let topic_titles = $state<ReadonlyMap<string, string> | null>(null);
  fetchTopicCatalogue()
    .then((c: TopicCatalogue) => {
      topic_titles = new Map(c.topics.map(t => [t.id, t.title]));
    })
    .catch(() => (topic_titles = null));

  const default_event = $derived(
    defaultEventForState(election_catalogue, scope.state)?.event_id ?? null,
  );

  const groups = $derived(
    buildRailGroups({
      state: scope.state,
      defaultEvent: default_event,
      repoUrl: REPO_URL,
      topicTitles: topic_titles,
    }),
  );

  let mobile_open = $state(false);
  const current_path = $derived(route.path);

  // Close the mobile drawer when the user activates any nav link inside
  // the rail. A click handler on the <aside> wrapper (delegated below)
  // is the structural alternative to a $effect-on-route.path watcher:
  // dev-mode HMR wraps the top-level mount() call in a branch() effect
  // whose context $effect cannot validate against, producing a noisy
  // `effect_orphan` pageerror on every page load (svelte#15332-class
  // issue, dev-only — production build is clean). The handler also
  // closes on programmatic in-app navigation, since the router's
  // delegated click handler in router.svelte.ts fires from the same
  // bubble path; the only case it misses is browser back/forward, where
  // the drawer being open on mobile is a marginal scenario anyway.
  function on_rail_click(e: MouseEvent): void {
    const a = (e.target as HTMLElement | null)?.closest("a");
    if (a) mobile_open = false;
  }

  // Ashoka Chakra (Dharmachakra) — 24 navy-blue spokes inscribed in a
  // ring, per the Indian national flag specification. See
  // https://en.wikipedia.org/wiki/Ashoka_Chakra (File:Ashoka_Chakra.svg)
  // for the canonical reference image.
  //
  // Inlined as SVG so it scales with the wordmark and inherits its color
  // via `currentColor`.
  //
  // Geometry on a 48-unit canvas:
  //  - Outer ring at r=22 (stroke 2.2).
  //  - 24 spindle-shaped spokes (NOT plain lines) from r=4.5 (just outside
  //    the hub) to r=20 (just inside the ring). Each spoke is a four-point
  //    diamond: pointed at hub and rim, half-width 0.55 at its midpoint.
  //    The pointed tips are what give the wheel its characteristic
  //    sun-burst look — the previous "stroke a line" implementation read
  //    as a generic radial pattern, not the chakra.
  //  - 24 small rim "bumps" (filled circles, r=0.55) on the inner edge of
  //    the ring at r=20.5, offset by half a spoke (7.5°) so they sit
  //    *between* the spokes — same arrangement as the reference image.
  //  - Solid hub disc at r=3.5 with a contrasting tiny center.
  const chakraSvg = (() => {
    const cx = 24, cy = 24;
    const r_outer = 22;
    const r_hub = 3.5;
    const r_spoke_in = 4.5;
    const r_spoke_out = 20;
    const half_w = 0.55;       // spindle half-width at the midpoint
    const r_bump = 20.5;
    const bump_r = 0.55;

    const parts: string[] = [];
    parts.push(`<circle cx="${cx}" cy="${cy}" r="${r_outer}" fill="none" stroke="currentColor" stroke-width="2.2"/>`);

    for (let k = 0; k < 24; k++) {
      const a = (k * Math.PI) / 12;
      const ux = Math.cos(a), uy = Math.sin(a);   // along-spoke unit vec
      const px = -uy, py = ux;                    // perpendicular unit vec
      // Inner tip, outer tip
      const ix = cx + r_spoke_in * ux,  iy = cy + r_spoke_in * uy;
      const ox = cx + r_spoke_out * ux, oy = cy + r_spoke_out * uy;
      // Two side points at the midpoint of the spoke
      const mx = cx + ((r_spoke_in + r_spoke_out) / 2) * ux;
      const my = cy + ((r_spoke_in + r_spoke_out) / 2) * uy;
      const sx1 = mx + half_w * px, sy1 = my + half_w * py;
      const sx2 = mx - half_w * px, sy2 = my - half_w * py;
      parts.push(
        `<polygon points="${ix.toFixed(2)},${iy.toFixed(2)} ${sx1.toFixed(2)},${sy1.toFixed(2)} ${ox.toFixed(2)},${oy.toFixed(2)} ${sx2.toFixed(2)},${sy2.toFixed(2)}" fill="currentColor"/>`,
      );

      // Rim bump centered between this spoke and the next.
      const ab = a + Math.PI / 24;
      const bx = cx + r_bump * Math.cos(ab);
      const by = cy + r_bump * Math.sin(ab);
      parts.push(`<circle cx="${bx.toFixed(2)}" cy="${by.toFixed(2)}" r="${bump_r}" fill="currentColor"/>`);
    }

    parts.push(`<circle cx="${cx}" cy="${cy}" r="${r_hub}" fill="currentColor"/>`);

    return `<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">${parts.join("")}</svg>`;
  })();
</script>

<!-- Mobile / cramped-desktop header: brand + hamburger. Hidden when the
     viewport is wide enough for the static rail (>= lg / 1024px). The
     breakpoint was raised from md→lg so mid-width screens (768–1023px)
     use the drawer instead of stealing 240px from the page content. -->
<header class="lg:hidden bg-white border-b border-slate-200 sticky top-0 z-30 flex items-center justify-between px-4 h-12">
  <a href={url.home()} class="brand-wordmark" aria-label="Yen Gov home">
    <span class="brand-yen">Yen</span><span class="brand-chakra" aria-hidden="true">{@html chakraSvg}</span><span class="brand-gov">Gov</span>
  </a>
  <button
    class="p-2 -mr-2 text-slate-600 hover:text-slate-900"
    aria-label="Toggle navigation"
    onclick={() => (mobile_open = !mobile_open)}
  >
    {#if mobile_open}✕{:else}☰{/if}
  </button>
</header>

<!-- Backdrop for mobile drawer -->
{#if mobile_open}
  <div
    class="lg:hidden fixed inset-0 bg-slate-900/30 z-20"
    onclick={() => (mobile_open = false)}
    role="presentation"
  ></div>
{/if}

<!-- Rail. On lg+ it's a fixed left column; below lg it's a slide-in drawer. -->
<aside
  onclick={on_rail_click}
  class="bg-white border-r border-slate-200 flex flex-col
         lg:w-60 lg:h-screen lg:sticky lg:top-0
         fixed lg:static top-12 bottom-0 left-0 w-64 z-30
         transition-transform lg:transition-none"
  class:translate-x-0={mobile_open}
  class:-translate-x-full={!mobile_open}
>
  <!-- Brand (lg+ only — cramped widths use the header above). -->
  <a href={url.home()} class="brand-wordmark hidden lg:flex items-center px-4 h-12 border-b border-slate-200 hover:bg-slate-50" aria-label="Yen Gov home">
    <span class="brand-yen">Yen</span><span class="brand-chakra" aria-hidden="true">{@html chakraSvg}</span><span class="brand-gov">Gov</span>
  </a>

  <StatePill />

  <nav class="flex-1 overflow-y-auto py-2" aria-label="Sections">
    {#each groups as g (g.id)}
      <section class="px-2 pb-3" data-rail-group={g.id}>
        <h3 class="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          {g.label}
        </h3>

        {#if g.items.length > 0}
          <ul class="space-y-0.5 text-sm list-none p-0 m-0">
            {#each g.items as item (item.id)}
              {@const active = item.match(current_path)}
              <li>
                <a
                  href={item.href}
                  data-rail-item={item.id}
                  target={item.external ? "_blank" : undefined}
                  rel={item.external ? "noreferrer" : undefined}
                  class="flex items-center gap-2 px-3 py-2 rounded transition-colors"
                  class:bg-slate-100={active}
                  class:text-slate-900={active}
                  class:font-medium={active}
                  class:text-slate-600={!active}
                  class:hover:bg-slate-50={!active}
                  class:hover:text-slate-900={!active}
                >
                  <span class="truncate">{item.label}</span>
                  {#if item.external}
                    <span aria-hidden="true" class="ml-auto text-[10px] text-slate-400">↗</span>
                  {/if}
                </a>
              </li>
            {/each}
          </ul>
        {/if}

        {#if g.hint}
          <p class="px-3 pt-1 text-[11px] italic text-slate-400">{g.hint}</p>
        {/if}
      </section>
    {/each}
  </nav>

  <footer class="px-4 py-2 text-[10px] text-slate-400 border-t border-slate-200">
    <p>Yen Gov · For an informed India</p>
  </footer>
</aside>

<style>
  /* Reset the inline style fallback on lg+ so the slide transform doesn't
     leak into the static layout. The class:translate-* directives drive
     the drawer slide; on lg+ the aside is static-positioned and the
     transform should be identity. */
  @media (min-width: 1024px) {
    aside {
      transform: none !important;
    }
  }

  /* Brand wordmark.
   *
   * Typography: Outfit (Google Fonts, loaded in index.html) at light
   * weight 300 for a slim, sleek silhouette that contrasts with the
   * default UI sans. Letter-spacing tightened slightly so the chakra
   * sits visually between the two words rather than floating.
   *
   * Separator: the Ashoka Chakra (Dharmachakra) replaces the prior
   * '-' hyphen. 24 navy-blue (#000080) spokes per the Indian flag
   * specification (see https://en.wikipedia.org/wiki/Ashoka_Chakra).
   * Sized to match the cap-height of the wordmark.
   *
   * Colors: 'Yen' uses the saffron stripe of the flag (#FF9933) and
   * 'Gov' uses the dark green stripe (#138808), with the navy chakra
   * between them — a quiet tricolor nod without being literal.
   */
  /* Use :where() to drop the selector specificity to (0,0,0) so Tailwind's
   * `hidden` utility (display:none) wins on viewports where we explicitly
   * mark the brand as hidden. Without this, `.brand-wordmark { display:
   * inline-flex }` had higher specificity than `.hidden`, so the drawer
   * brand (which carries `hidden lg:flex`) stayed visible at every width
   * — mobile users saw the wordmark twice (once in the lg:hidden top
   * header, once inside the slide-in drawer). */
  :where(.brand-wordmark) {
    font-family: "Outfit", ui-sans-serif, system-ui, sans-serif;
    font-weight: 300;
    font-size: 1.25rem;
    letter-spacing: -0.01em;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    line-height: 1;
  }
  /* Flag-palette tones, darkened just enough to clear WCAG AA on white at
   * 1.25rem / weight 300. The pure flag colors (#FF9933 saffron, #138808
   * green) fail AA on white — these are the closest accessible cousins. */
  .brand-yen { color: #d97706; }     /* saffron-leaning amber-600 */
  .brand-gov { color: #15803d; }     /* flag-green-leaning emerald-700 */
  .brand-chakra {
    display: inline-flex;
    width: 1.05em;
    height: 1.05em;
    color: #000080;                  /* navy blue per flag spec */
    transform-origin: 50% 50%;
    will-change: transform;
  }
  .brand-chakra :global(svg) {
    width: 100%;
    height: 100%;
    display: block;                  /* eliminate inline-baseline gap so
                                        rotation pivots on the true center */
  }

  /* Spin once on hover/focus of the whole wordmark. The chakra is a true
   * circle (cx=cy=24, r=22) so rotation around its center is wobble-free.
   * The animation runs to completion and then resets — re-hovering plays
   * it again. */
  .brand-wordmark:hover .brand-chakra,
  .brand-wordmark:focus-visible .brand-chakra {
    animation: chakra-spin 3s cubic-bezier(0.4, 0, 0.2, 1) 1;
  }
  @keyframes chakra-spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }
  @media (prefers-reduced-motion: reduce) {
    .brand-wordmark:hover .brand-chakra,
    .brand-wordmark:focus-visible .brand-chakra {
      animation: none;
    }
  }
</style>
