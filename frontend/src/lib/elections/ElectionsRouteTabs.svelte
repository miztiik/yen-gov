<!--
  ElectionsRouteTabs - shared nav strip mounted ABOVE the H1 on both
  the General-elections route (/t/elections) and the Assembly-elections
  route (/t/elections/assemblies). Per the user-mandated naming + nav
  verdict in TODO/20260615-elections-redesign-plan.md Section 0.1:

   - 2 pills: "General elections" + "Assembly elections"
   - Active pill is filled (slate-900 bg + white text); inactive is
     outline (slate-300 border + slate-700 text)
   - Mobile-friendly: pills stay horizontal at < 640px, full-width row,
     each pill `flex-1` so they never wrap
   - ARIA tablist semantics: <nav role="tablist"> + role="tab" on each
     link + aria-current="page" on the active pill
   - Pattern reuses the existing Tailwind pill family used by the
     firehose body-filter, ScopePicker, HomeElectionsRail door - no new
     chrome

  Sole consumer surfaces (PR-E4): GeneralElections.svelte +
  AssemblyElections.svelte. Citizen-discoverability requirement: the
  sibling route is always one tap away. Citizen test passes (per Section
  0.1 transcript): 30-year-old in Bengaluru sees both surfaces from
  either route in one glance.
-->
<script lang="ts">
  import { link } from "../links";

  let { current }: { current: "general" | "assembly" } = $props();

  // The two routes. Both go through the `link.*` builders so the
  // deploy base (`/yen-gov/`) is always applied - a hardcoded
  // `/t/elections` literal would 404 on GitHub Pages reload/share.
  const TABS = [
    {
      id: "general" as const,
      label: "General elections",
      href: link.generalElections(),
    },
    {
      id: "assembly" as const,
      label: "Assembly elections",
      href: link.assemblyElections(),
    },
  ];
</script>

<nav
  class="flex w-full gap-2 mb-4"
  role="tablist"
  aria-label="Elections views"
  data-testid="elections-route-tabs"
>
  {#each TABS as tab (tab.id)}
    {@const active = current === tab.id}
    <a
      href={tab.href}
      role="tab"
      aria-current={active ? "page" : undefined}
      aria-selected={active}
      data-testid={`elections-route-tab-${tab.id}`}
      data-active={active}
      class="
        flex-1 text-center rounded-full border px-4 py-2 text-sm font-medium
        transition-colors
      "
      class:bg-slate-900={active}
      class:text-white={active}
      class:border-slate-900={active}
      class:border-slate-300={!active}
      class:text-slate-700={!active}
      class:bg-white={!active}
      class:hover:bg-slate-100={!active}
    >
      {tab.label}
    </a>
  {/each}
</nav>
