<script lang="ts">
  // Color overrides editor. Lists the union of (canonical dim_parties +
  // observations-fallback parties) and current overrides. Migrated off the
  // 5-state hardcoded fetchParties fan-out onto the parties-palette
  // view-model loader in PR-G (Phase 1.3c) — net coverage is now every
  // party that has ever scored a party-totals row, not just 5 states.
  import { colors } from "../lib/colors/store.svelte";
  import { ANCHORS } from "../lib/colors/anchors";
  import {
    loadPartiesPalette,
    type PartiesPaletteViewModel,
  } from "../lib/view-models/parties-palette";
  import type { LoaderResult } from "../lib/loader-result";

  let result = $state<LoaderResult<PartiesPaletteViewModel>>({
    status: "loading",
  });

  function retryLoad(): void {
    result = { status: "loading" };
    loadPartiesPalette().then((r) => (result = r));
  }

  $effect(() => {
    retryLoad();
  });

  // Always include any party that has an override but isn't in the palette
  // (e.g. a party loaded from a state not yet ingested into observations).
  const editable = $derived.by(() => {
    const list: { eci_code: string; short_name: string; full_name: string | null }[] = [];
    const seen = new Set<string>();
    const palette = result.status === "ok" ? result.data.parties : [];
    for (const p of palette) {
      list.push({ eci_code: p.eci_code, short_name: p.short_name, full_name: p.full_name });
      seen.add(p.eci_code);
    }
    for (const code of Object.keys(colors.overrides)) {
      if (seen.has(code)) continue;
      list.push({ eci_code: code, short_name: code, full_name: null });
      seen.add(code);
    }
    return list;
  });

  function onPick(eci_code: string, e: Event): void {
    const v = (e.target as HTMLInputElement).value;
    colors.set(eci_code, { fill: v });
  }
</script>

<main class="max-w-3xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold">Settings</h1>
    <p class="text-sm text-slate-500">
      Party color overrides. Saved per-browser; cleared when you reset all.
    </p>
  </header>

  <section class="bg-white rounded-lg shadow-sm p-5 space-y-4">
    <div class="flex justify-between items-baseline">
      <h2 class="text-sm font-semibold uppercase text-slate-500">Party colors</h2>
      <button
        type="button"
        onclick={() => { if (confirm("Reset all party colors to defaults?")) colors.resetAll(); }}
        class="text-xs text-rose-600 hover:underline"
        disabled={Object.keys(colors.overrides).length === 0}
      >Reset all</button>
    </div>

    {#if result.status === "failed"}
      <div class="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
        <p>Could not load parties: {result.reason}</p>
        <button
          type="button"
          onclick={() => result.status === "failed" && result.retry?.()}
          class="mt-2 px-3 py-1 text-xs rounded bg-rose-100 hover:bg-rose-200"
        >Retry</button>
      </div>
    {:else if result.status === "loading"}
      <p class="text-sm text-slate-500">Loading parties…</p>
    {:else}
      <ul class="divide-y">
        {#each editable as p (p.eci_code)}
          {@const override = colors.overrides[p.eci_code]}
          {@const effective = colors.fill(p.eci_code, p.short_name)}
          {@const is_default = !override}
          <li class="flex items-center gap-3 py-2.5">
            <input
              type="color"
              value={effective}
              oninput={(e) => onPick(p.eci_code, e)}
              class="h-8 w-12 rounded border border-slate-200 cursor-pointer p-0"
              title="Pick a color"
            />
            <div class="flex-1">
              <div class="font-medium text-sm">{p.short_name}</div>
              <div class="text-xs text-slate-500">
                {p.full_name ?? "(unmapped party — override only)"}
                <span class="text-slate-400 font-mono ml-1">#{p.eci_code}</span>
              </div>
            </div>
            <code class="text-xs font-mono text-slate-500">{effective}</code>
            <button
              type="button"
              onclick={() => colors.reset(p.eci_code)}
              disabled={is_default}
              class="text-xs px-2 py-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent"
              title="Revert to default"
            >Reset</button>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  <section class="text-xs text-slate-500">
    <p>
      Iconic colours come from {Object.keys(ANCHORS).length} curated anchors
      (national parties + strongly-recognised regional brands like DMK red,
      ADMK green, AITC green). Every other party is assigned a colour
      algorithmically from an OkLCh palette, with same-chart de-duplication
      so no two visible parties ever share a swatch. Pick any colour above to
      override the default per your preference; the override persists in this
      browser.
    </p>
  </section>
</main>
