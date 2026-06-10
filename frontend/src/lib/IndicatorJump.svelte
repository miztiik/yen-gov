<script lang="ts" module>
  // IndicatorJump - sticky theme-chip jump strip for long indicator
  // lists (U5 sub-plan U5c; parent plan section 20.12 "Quick-jump").
  //
  // The long indicator-list problem on /s/<state>: by the time the
  // citizen has tapped a state, the page is ~10 topics deep (Economy,
  // Health, Education, Energy, Agriculture, ...). Alphabetical sort
  // serves no civic query; a "type to filter" alone hides the topic
  // structure. The IDP information-design grid metaphor (one tap per
  // theme tile) maps cleanly to a chip strip with scroll-spy.
  //
  // What this component does:
  //   - Renders a thin text filter input above the chip row
  //     (case-insensitive substring match on label) - secondary affordance.
  //   - Renders one tap-target chip per group (icon + label) - PRIMARY
  //     affordance, in the order the parent supplied.
  //   - Tap a chip -> smooth-scrolls to the matching
  //     `<section data-jump-id="<id>">` element in the page.
  //   - Scroll-spy: an `IntersectionObserver` watches each section; the
  //     topmost-in-viewport section's id is written to `current` (a
  //     `$bindable` so the parent can also drive it on first paint).
  //
  // Why module-scope pure helpers (`filterGroups`, `activeIdForOffsets`):
  //   vitest runs in node-env (per `/memories/lessons.md` Skeleton
  //   precedent + the route-crumbs.ts per-route builders that landed
  //   in PR-W1d). The wiring code
  //   (IntersectionObserver, smooth scroll, $effect lifecycle) is
  //   integration-tested via the in-browser smoke on /s/tamil-nadu per
  //   CLAUDE.md section 13; the COMPUTATION (which chips match a query,
  //   which id is active given a scrollY + offsets) is the testable
  //   surface.
  //
  // Tokens consumed (drift-locked by app-tokens.test.ts):
  //   --surface, --surface-sunken, --line, --ink, --ink-muted, --accent
  //   --r-pill (the chip shape; Tailwind `rounded-yen-pill`)
  //
  // Doctrine:
  //   - Mobile-first (~360px target): chips wrap to horizontal scroll
  //     when the row width exceeds the viewport; the filter input is
  //     full-width above the chips.
  //   - The chip set is DERIVED from the actual topics in the parent's
  //     list (one chip per non-empty topic), never hardcoded.
  //   - CLAUDE.md section 0 a11y descoped: no `aria-*`, no `role`.
  //     `<button>` keeps the native keyboard/pointer activation.
  //   - Non-navigation state stays in-memory (plan section 20.8): the
  //     filter query and the scroll-spy current are component-local
  //     `$state` / `$bindable`, NOT mirrored to the URL.

  export interface JumpGroup {
    /** Stable id; must match the parent's `<section data-jump-id="<id>">`. */
    id: string;
    /** Citizen-readable chip label. */
    label: string;
    /** Optional icon id (registered in the icon registry). */
    icon?: string | null;
  }

  /**
   * Narrow `groups` by a case-insensitive substring match on `label`.
   * Empty / whitespace-only query returns the full set unchanged.
   * The match is INFIX, not prefix - "lit" matches "Pollution and Energy"
   * via the embedded "lution" + "ut" + "tio" overlaps... wait, no:
   * "lit" matches "Literacy" but not "Pollution". Substring infix is the
   * citizen's default mental model ("show me anything with X in it").
   */
  export function filterGroups(
    groups: ReadonlyArray<JumpGroup>,
    query: string,
  ): JumpGroup[] {
    const q = query.trim().toLowerCase();
    if (q.length === 0) return [...groups];
    return groups.filter(g => g.label.toLowerCase().includes(q));
  }

  /**
   * Pure scroll-spy helper. Given the current `scrollY` and a list of
   * section offsets (each `{ id, top }`), returns the id of the
   * largest-offset section whose top is at or above `scrollY`. Returns
   * `null` when `scrollY` is above every section's top (the user is
   * still in the page header).
   *
   * Pre-condition: `offsets` is sorted by `top` ascending. (The caller
   * builds the list by walking `document.querySelectorAll`, which
   * returns elements in DOM order = layout order for vertically-stacked
   * sections; the function trusts that order.)
   *
   * Ties (two offsets at the same `top`) are broken by LAST occurrence -
   * the loop assigns `active = o.id` for every <= match, so a later
   * entry overrides an earlier one. This is the right behaviour for
   * collapsed-y sections: the DOM-later section visually paints on top,
   * so the citizen perceives it as "active".
   */
  export function activeIdForOffsets(
    scrollY: number,
    offsets: ReadonlyArray<{ id: string; top: number }>,
  ): string | null {
    if (offsets.length === 0) return null;
    let active: string | null = null;
    for (const o of offsets) {
      if (o.top <= scrollY) active = o.id;
      else break; // sorted ascending: stop at first offset above scrollY
    }
    return active;
  }
</script>

<script lang="ts">
  import TopicIcon from "./TopicIcon.svelte";

  interface Props {
    /** Ordered list of jump-target groups; one chip per group. */
    groups: ReadonlyArray<JumpGroup>;
    /** Active group id (bindable so scroll-spy can drive it). */
    current?: string | null;
    /** Optional extra utility classes for the host container. */
    cls?: string;
    /** Data-test selector used by Playwright + the in-browser smoke. */
    testid?: string;
  }

  let {
    groups,
    current = $bindable<string | null>(null),
    cls = "",
    testid = "indicator-jump",
  }: Props = $props();

  let query = $state("");
  const filtered = $derived(filterGroups(groups, query));

  // IntersectionObserver wiring. Re-runs whenever the GROUPS prop
  // identity changes (a new state with a different topic mix); the
  // returned teardown closes the previous observer before the new one
  // opens. We do NOT re-observe on every `current` write because that
  // would create a feedback loop (current <- IO <- write current).
  $effect(() => {
    // Bail in non-DOM test environments (vitest node-env is a non-goal
    // for component tests per the Skeleton precedent, but defensive
    // typeof checks keep the module importable in those harnesses).
    if (typeof window === "undefined" || typeof IntersectionObserver === "undefined") {
      return;
    }

    const ids = groups.map(g => g.id);
    if (ids.length === 0) return;

    // Observed sections live anywhere in the DOM (the parent uses
    // `<section data-jump-id="<id>">` to mark them). Re-query on each
    // $effect run so a parent that lazily mounts sections (e.g. via
    // {#each indicator_topics}) catches the new nodes.
    const targets: HTMLElement[] = [];
    for (const id of ids) {
      const el = document.querySelector<HTMLElement>(`[data-jump-id="${id}"]`);
      if (el) targets.push(el);
    }
    if (targets.length === 0) return;

    // rootMargin biases the observer toward the TOP of the viewport:
    //   - Top trim (-80px) accounts for the Breadcrumb (~48px) +
    //     this jump strip's own height (~36px). A section's top edge
    //     must cross BELOW that line to count as "intersecting".
    //   - Bottom trim (-60%) means a section is no longer "intersecting"
    //     once it has scrolled into the lower 60% of the viewport, so
    //     the active chip flips before the section title leaves the
    //     top third - the citizen's eyes are at the top, the chip
    //     should match what's at the top.
    const observer = new IntersectionObserver(
      entries => {
        // Pick the topmost section currently considered "intersecting"
        // by the observer (the one whose `boundingClientRect.top` is
        // smallest / most-negative = closest to the viewport top).
        const intersecting = entries
          .filter(e => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (intersecting.length > 0) {
          const id = (intersecting[0].target as HTMLElement).dataset.jumpId;
          if (id) current = id;
        }
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 },
    );
    for (const t of targets) observer.observe(t);

    return () => observer.disconnect();
  });

  function onChipClick(id: string): void {
    if (typeof document === "undefined") return;
    const el = document.querySelector<HTMLElement>(`[data-jump-id="${id}"]`);
    if (!el) return;
    // Smooth-scroll so the citizen retains a sense of place; honour
    // prefers-reduced-motion via the standard "auto" fallback (the
    // browser flips the behaviour automatically per the media query).
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    // Update the active highlight immediately so the chip flips on tap
    // even before the IntersectionObserver catches up post-scroll.
    current = id;
  }
</script>

<div
  class="indicator-jump sticky top-12 lg:top-0 z-10 bg-white/95 backdrop-blur border-y border-line py-2 -mx-3 px-3 sm:-mx-4 sm:px-4 {cls}"
  data-testid={testid}
  data-component="indicator-jump"
>
  <div class="flex flex-col gap-2">
    <input
      type="search"
      bind:value={query}
      placeholder="Filter topics..."
      class="w-full sm:max-w-xs text-xs bg-surface-sunken border border-line rounded-yen-sm px-2.5 py-1.5 text-ink placeholder:text-ink-muted focus:outline-none focus:border-accent focus:bg-surface"
      data-testid="{testid}-filter"
    />

    {#if filtered.length === 0}
      <p class="text-xs text-ink-muted italic px-1">No topics match &ldquo;{query}&rdquo;.</p>
    {:else}
      <div
        class="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1"
        data-testid="{testid}-chips"
      >
        {#each filtered as group (group.id)}
          {@const active = group.id === current}
          <button
            type="button"
            class="indicator-jump__chip inline-flex items-center gap-1.5 shrink-0 min-h-[32px] px-2.5 py-1 rounded-yen-pill text-xs font-medium border transition-colors duration-fast"
            class:is-active={active}
            data-jump-chip={group.id}
            data-jump-active={active}
            title={group.label}
            onclick={() => onChipClick(group.id)}
          >
            {#if group.icon}
              <TopicIcon name={group.icon} cls="w-3.5 h-3.5 shrink-0" />
            {/if}
            <span>{group.label}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  /* Chip palette uses the new tokens directly; un-migrated callers see
     the inactive style by default and the active style only when this
     component decides (so we never accidentally tint a fresh page red).
     The visual contrast (accent fill vs surface) carries the active
     signal without relying on chrome the citizen might not notice. */
  .indicator-jump__chip {
    background: var(--surface);
    color: var(--ink-muted);
    border-color: var(--line);
  }
  .indicator-jump__chip:hover {
    background: var(--surface-sunken);
    color: var(--ink);
  }
  .indicator-jump__chip.is-active {
    background: var(--accent);
    color: #ffffff;
    border-color: var(--accent);
  }
  .indicator-jump__chip.is-active:hover {
    /* Lock the active chip's colours on hover so the highlight stays
       visually stable when the pointer drifts across it. */
    background: var(--accent);
    color: #ffffff;
  }
</style>
