<script lang="ts">
  // Breadcrumb - shared rendering primitive for every page's crumb
  // trail. Pure prop-in / DOM-out: the parent supplies a `crumbs:
  // Crumb[]` array (typically derived from `route.crumbs?.(route.params)`)
  // and this component renders the trail with the same chrome the
  // U2b breadcrumb spine shipped under.
  //
  // PR-W1d (election experience overhaul, 2026-06-10): file renamed
  // from the U2b place-first breadcrumb to this shared primitive.
  // The U2b derivation (state name lookup, AC name recovery, etc.)
  // moved OUT of this component and INTO per-route crumb builders
  // in lib/route-crumbs.ts so ONE component renders both the
  // election cascades and the socio-econ cascades. Per parent
  // plan-doc 20260609-election-experience-overhaul-plan.md section
  // 0.5: this is a shared seam consumed by both surfaces.
  //
  // What this DOES NOT do:
  //   - derive crumbs from the URL (that lives in route-crumbs.ts).
  //   - call the catalogue resolvers (state-name, AC-name, topic-name);
  //     callers do that inside their crumb builder.
  //   - sibling-jump menu (the trailing `v` peer-list popover);
  //     deferred from the U2b sub-plan and not in scope for PR-W1d.
  //   - mobile / desktop layout shift; the sticky offset is `top-12`
  //     on mobile (under the 48px LeftRail mobile header) and
  //     `lg:top-0` on desktop. Unchanged from the U2b chrome.

  import TopicIcon from "./TopicIcon.svelte";
  import type { Crumb } from "./breadcrumb-types";

  interface Props {
    /** The full crumb trail to render. Empty arrays render nothing
     * (`null`-tolerant for routes with no crumb builder declared). */
    crumbs?: Crumb[] | null;
  }
  let { crumbs = [] }: Props = $props();

  // Defensive: a missing crumbs prop or an empty array means the
  // route did not declare a crumbs builder (or it returned nothing);
  // render no chrome rather than an empty `<nav>` so the page below
  // doesn't get pushed down by an invisible sticky bar.
  const trail = $derived(crumbs ?? []);
</script>

{#if trail.length > 0}
  <nav
    aria-label="Breadcrumb"
    class="sticky top-12 lg:top-0 z-20 bg-white/80 backdrop-blur border-b border-line"
    data-testid="geo-breadcrumb"
  >
    <ol
      class="flex items-center gap-1 list-none m-0 p-0
             max-w-screen-2xl mx-auto px-4 sm:px-6 py-2 min-h-9
             text-sm text-ink-muted overflow-hidden"
    >
      {#each trail as crumb, i (i)}
        {#if i > 0}
          <li aria-hidden="true" class="shrink-0 flex items-center text-line">
            <TopicIcon name="chevron-right" cls="w-4 h-4 shrink-0" />
          </li>
        {/if}
        <li class="min-w-0 truncate">
          {#if crumb.isLeaf || !crumb.href}
            <span
              class="text-ink font-medium truncate"
              aria-current="page"
            >{crumb.label}</span>
          {:else}
            <a
              href={crumb.href}
              class="text-ink-muted hover:text-ink hover:underline truncate"
            >{crumb.label}</a>
          {/if}
        </li>
      {/each}
    </ol>
  </nav>
{/if}
