<script lang="ts">
  // Left rail: scope picker on top, tool list below. Replaces the previous
  // top-only nav per docs/architecture/frontend/overview.md.
  //
  // Tool availability depends on scope (overview.md > IA table). Tools that
  // require a chosen state render disabled when none is picked, so the user
  // sees the affordance and learns the rule, rather than having entries
  // appear and disappear.

  import { route } from "./router.svelte";
  import { scope } from "./scope.svelte";
  import ScopePicker from "./ScopePicker.svelte";

  interface Tool {
    label: string;
    icon: string;
    /** href as a function of current scope so "Explore" goes to #/ vs #/s/<S>. */
    href: () => string;
    /** Active when the current path matches this predicate. */
    match: (path: string) => boolean;
    /** Disabled reason — when set, the tool renders as a non-link with tooltip. */
    disabled_reason?: () => string | null;
  }

  const tools: Tool[] = [
    {
      label: "Explore",
      icon: "🗺",
      href: () => (scope.state ? `#/s/${scope.state}` : "#/"),
      match: p => p === "/" || (p.startsWith("/s/") && !p.endsWith("/explore")),
    },
    {
      label: "SQL",
      icon: "⌘",
      href: () => (scope.state ? `#/s/${scope.state}/explore` : "#/"),
      match: p => p.endsWith("/explore"),
      disabled_reason: () => (scope.state ? null : "Pick a state first"),
    },
    {
      label: "Psephlab",
      icon: "🧪",
      href: () => (scope.state ? `#/lab/${scope.state}/${scope.election}` : "#/"),
      match: p => p.startsWith("/lab/"),
      disabled_reason: () => (scope.state ? null : "Pick a state first"),
    },
    {
      label: "Compare",
      icon: "⇄",
      href: () => `#/compare`,
      match: p => p.startsWith("/compare"),
      disabled_reason: () => "Coming in phase 3",
    },
    {
      label: "Settings",
      icon: "⚙",
      href: () => "#/settings",
      match: p => p === "/settings",
    },
  ];

  let mobile_open = $state(false);
  const current_path = $derived(route.path);

  // Close the mobile drawer whenever navigation happens.
  $effect(() => {
    void current_path;
    mobile_open = false;
  });
</script>

<!-- Mobile header: brand + hamburger. Hidden on md+. -->
<header class="md:hidden bg-white border-b border-slate-200 sticky top-0 z-30 flex items-center justify-between px-4 h-12">
  <a href="#/" class="font-bold tracking-tight">yen<span class="text-slate-400">-gov</span></a>
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
    class="md:hidden fixed inset-0 bg-slate-900/30 z-20"
    onclick={() => (mobile_open = false)}
    role="presentation"
  ></div>
{/if}

<!-- Rail. On md+ it's a fixed left column; on mobile it's a slide-in drawer. -->
<aside
  class="bg-white border-r border-slate-200 flex flex-col
         md:w-60 md:h-screen md:sticky md:top-0
         fixed md:static top-12 bottom-0 left-0 w-64 z-30
         transition-transform md:transition-none"
  class:translate-x-0={mobile_open}
  class:-translate-x-full={!mobile_open}
  style="transform: var(--rail-transform)"
>
  <!-- Brand (desktop only — mobile uses the header above). -->
  <a href="#/" class="hidden md:flex items-center px-4 h-12 border-b border-slate-200 font-bold tracking-tight hover:bg-slate-50">
    yen<span class="text-slate-400">-gov</span>
  </a>

  <ScopePicker />

  <nav class="flex-1 overflow-y-auto py-2">
    <ul class="space-y-0.5 px-2 text-sm">
      {#each tools as t}
        {@const reason = t.disabled_reason?.() ?? null}
        {@const active = t.match(current_path)}
        <li>
          {#if reason}
            <span
              class="flex items-center gap-3 px-3 py-2 rounded text-slate-400 cursor-not-allowed"
              title={reason}
            >
              <span class="w-5 text-center">{t.icon}</span>
              <span>{t.label}</span>
              <span class="ml-auto text-[10px] uppercase tracking-wide">soon</span>
            </span>
          {:else}
            <a
              href={t.href()}
              class="flex items-center gap-3 px-3 py-2 rounded transition-colors"
              class:bg-slate-100={active}
              class:text-slate-900={active}
              class:font-medium={active}
              class:text-slate-600={!active}
              class:hover:bg-slate-50={!active}
              class:hover:text-slate-900={!active}
            >
              <span class="w-5 text-center">{t.icon}</span>
              <span>{t.label}</span>
            </a>
          {/if}
        </li>
      {/each}
    </ul>
  </nav>

  <footer class="px-4 py-2 text-[10px] text-slate-400 border-t border-slate-200">
    <a href="https://github.com/yen-gov" target="_blank" rel="noreferrer" class="hover:text-slate-600">
      yen-gov · Indian election data
    </a>
  </footer>
</aside>

<style>
  /* Reset the inline style fallback on md+ so the slide transform doesn't
     leak into the static layout. The class:translate-* directives drive
     the mobile slide; on desktop the aside is static-positioned and the
     transform should be identity. */
  @media (min-width: 768px) {
    aside {
      transform: none !important;
    }
  }
</style>
