<script lang="ts" module>
  // GeoBreadcrumb - place-first primary-nav spine (U2 sub-plan U2b).
  //
  // Sticky breadcrumb chain mounted at the top of every place-first
  // route (Home / StateOverview / StateTopic / Constituency / District).
  // Each crumb is tap-to-ascend; the leaf crumb is the current page,
  // rendered as a plain `<span>` with `aria-current="page"` so the
  // semantic-HTML signal is correct even though CLAUDE.md section 0
  // descopes the broader accessibility doctrine. Sticky + glass styling
  // (`bg-white/80 backdrop-blur` + `border-b border-line`) matches the
  // "primary-nav spine" framing in parent plan section 21.8.
  //
  // Per parent plan section 20.8 + 23.5: geo lives in the PATH (state,
  // district, AC); the breadcrumb is DERIVED from the route - never
  // stored separately. State -> code + name resolution happens in the
  // component layer via the reactive `states` store; the pure helper
  // `computeCrumbs` is fed the already-resolved values so it stays
  // trivially testable in vitest's node-env (no DOM, no mounting).
  //
  // What this DOES NOT do:
  //   - sibling-jump menu (the trailing `v` peer-list popover from the
  //     sub-plan body): deferred to a follow-up sub-row. The breadcrumb
  //     ships with ascend-only navigation in U2b; the popover lifts
  //     when its data-fetch contract is settled (sub-plan stop trigger).
  //   - new design tokens: U2b consumes only existing tokens (`--ink`,
  //     `--ink-muted`, `--line`, `--surface`). U2c mints `--app-bar-bg`
  //     and the brand-colour tokens.
  //   - mobile / desktop layout shift: the sticky offset is `top-12`
  //     on mobile (under the 48px LeftRail mobile header) and
  //     `lg:top-0` on desktop (no mobile header above lg:1024px).

  import { link } from "./links";
  import { parseAcSlug } from "./slug";

  export type Crumb = {
    label: string;
    /** Ascend URL; `null` means the current page (renders as a `<span>`). */
    href: string | null;
  };

  /**
   * Title-case a dash-separated slug. Used for district / topic leaf
   * crumbs where the URL token IS the display name's slugified form.
   * `"north-24-parganas"` -> `"North 24 Parganas"`.
   */
  function slugToTitle(slug: string): string {
    return slug
      .split("-")
      .filter(s => s.length > 0)
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }

  /**
   * Recover the AC display name from an AC slug. The slug shape is
   * `<eci_no>-<name-slug>` (e.g. `167-mylapore`) or bare `<eci_no>`.
   * Returns `"AC <n>"` when no name half is present.
   */
  function acNameFromSlug(slug: string): string {
    const eci_no = parseAcSlug(slug);
    if (eci_no === null) return slugToTitle(slug);
    const dash = slug.indexOf("-");
    if (dash < 0) return `AC ${eci_no}`;
    return slugToTitle(slug.slice(dash + 1));
  }

  /**
   * Derive the place-first crumb chain from a route's path + params.
   *
   * Mount set: `/`, `/s/<state>`, `/s/<state>/t/<topic>`,
   * `/s/<state>/d/<district>`, `/s/<state>/ac/<ac>`,
   * `/s/<state>/elections/<event>/ac/<ac>`.
   *
   * Every chain starts with the India crumb. The current page is the
   * LAST crumb (`href: null`); ascend crumbs carry a builder-built URL
   * through `url.X()` so the slug shape stays canonical per
   * ADR-0048 / ADR-0050.
   *
   * Pure: no DOM, no fetch, no router-state mutation. Callers pass the
   * resolved `stateCode` + `stateName` so the function is trivially
   * testable without mocking the reactive `states` store. When state
   * context is not yet resolved (states.json still in flight, or the
   * slug is unknown), the function degrades to `[India]` alone - the
   * page renders its own "Loading" / "State not found" panel.
   */
  export function computeCrumbs(args: {
    path: string;
    params: Record<string, unknown>;
    stateCode: string | null;
    stateName: string;
  }): Crumb[] {
    const { path, params, stateCode, stateName } = args;

    // Home: just India, current page.
    if (path === "/" || path === "") {
      return [{ label: "India", href: null }];
    }

    const india: Crumb = { label: "India", href: link.home() };

    // State context not yet resolved - graceful degradation.
    if (!stateCode || !stateName) {
      return [india];
    }

    // Classify the leaf grain by which type-specific param is present.
    // Order matters in name only: districtSlug / acSlug / topic are
    // pairwise disjoint across the mount-set routes.
    const districtSlug =
      typeof params.district_slug === "string" ? params.district_slug : null;
    const acSlug =
      typeof params.ac_slug === "string" ? params.ac_slug : null;
    const topic =
      typeof params.topic === "string" ? params.topic : null;

    // StateOverview (/s/:state): state IS the current page.
    if (!districtSlug && !acSlug && !topic) {
      return [india, { label: stateName, href: null }];
    }

    // Deeper grain: state crumb is an ascend link.
    const stateCrumb: Crumb = {
      label: stateName,
      href: link.state(stateCode),
    };

    if (districtSlug) {
      return [
        india,
        stateCrumb,
        { label: slugToTitle(districtSlug), href: null },
      ];
    }
    if (acSlug) {
      return [
        india,
        stateCrumb,
        { label: acNameFromSlug(acSlug), href: null },
      ];
    }
    // topic - StateTopic (/s/:state/t/:topic)
    return [
      india,
      stateCrumb,
      { label: slugToTitle(topic as string), href: null },
    ];
  }
</script>

<script lang="ts">
  import TopicIcon from "./TopicIcon.svelte";
  import { states } from "./states.svelte";
  import { route } from "./router.svelte";

  // Reactive crumb chain. Reading the `route` store directly means a
  // client-side navigation (pushState + popstate) re-derives the chain
  // without re-mounting the component. State resolution lives here in
  // the view layer so the pure helper above stays decoupled from the
  // module-scoped `states` store.
  const stateSlug = $derived(
    typeof route.params.state === "string" ? route.params.state : null,
  );
  const stateCode = $derived(
    stateSlug ? states.codeFromSlug(stateSlug) : null,
  );
  const stateName = $derived(stateCode ? states.name(stateCode) : "");

  const crumbs = $derived(
    computeCrumbs({
      path: route.path,
      params: route.params,
      stateCode,
      stateName,
    }),
  );
</script>

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
    {#each crumbs as crumb, i (i)}
      {#if i > 0}
        <li aria-hidden="true" class="shrink-0 flex items-center text-line">
          <TopicIcon name="chevron-right" cls="w-4 h-4 shrink-0" />
        </li>
      {/if}
      <li class="min-w-0 truncate">
        {#if crumb.href}
          <a
            href={crumb.href}
            class="text-ink-muted hover:text-ink hover:underline truncate"
          >{crumb.label}</a>
        {:else}
          <span
            class="text-ink font-medium truncate"
            aria-current="page"
          >{crumb.label}</span>
        {/if}
      </li>
    {/each}
  </ol>
</nav>
