<script lang="ts">
  // Walking-skeleton shell. Phase 4 v0 has only one panel (Inventory);
  // the nav is a hard-coded list anticipating Schemas / Pipeline /
  // Patches sliding in next. Keeps the topology visible.

  import { onMount } from "svelte";
  import Inventory from "./routes/Inventory.svelte";
  import Schemas from "./routes/Schemas.svelte";
  import Pipeline from "./routes/Pipeline.svelte";
  import { api } from "./lib/api";

  type PanelId = "inventory" | "schemas" | "pipeline";
  let active: PanelId = $state("inventory");
  let api_version = $state<string | null>(null);
  let api_error = $state<string | null>(null);

  onMount(() => {
    void api
      .health()
      .then(h => (api_version = h.version))
      .catch(e => (api_error = String(e)));
  });
</script>

<div class="min-h-screen flex">
  <aside class="w-56 shrink-0 bg-slate-900 border-r border-slate-800 p-4 space-y-4">
    <div>
      <p class="text-sm font-bold tracking-wide">yen-gov<span class="text-amber-400"> · admin</span></p>
      <p class="text-[10px] text-slate-500 mt-1">localhost only · never deployed</p>
    </div>

    <nav class="space-y-1 text-sm">
      <button
        class="block w-full text-left px-2 py-1 rounded"
        class:bg-slate-800={active === 'inventory'}
        onclick={() => (active = 'inventory')}
      >📦 Inventory</button>
      <button
        class="block w-full text-left px-2 py-1 rounded"
        class:bg-slate-800={active === 'schemas'}
        onclick={() => (active = 'schemas')}
      >🩺 Schemas</button>
      <button
        class="block w-full text-left px-2 py-1 rounded"
        class:bg-slate-800={active === 'pipeline'}
        onclick={() => (active = 'pipeline')}
      >⚙ Pipeline</button>
      <span class="block px-2 py-1 text-slate-600 text-xs italic" title="Coming next">📝 Patches</span>
    </nav>

    <footer class="text-[10px] text-slate-500 pt-4 border-t border-slate-800">
      {#if api_error}
        <span class="text-rose-400">API down</span>
      {:else if api_version}
        API v{api_version}
      {:else}
        connecting…
      {/if}
    </footer>
  </aside>

  <main class="flex-1 p-6 overflow-x-auto">
    {#if active === 'inventory'}
      <Inventory />
    {:else if active === 'schemas'}
      <Schemas />
    {:else if active === 'pipeline'}
      <Pipeline />
    {/if}
  </main>
</div>
