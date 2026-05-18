<script lang="ts">
  // Color overrides editor. Lists the union of (default canonical palette
  // entries with at least one occurrence in loaded data) and current overrides.
  // For Phase 1 we don't pre-load every state's parties.json — the user can
  // override any party they encounter while browsing. This page lets them
  // manage existing overrides and tweak colors for the canonical TN palette.
  import { colors } from "../lib/colors/store.svelte";
  import { ANCHORS } from "../lib/colors/anchors";
  // TODO(PR-G / Phase 1.3c): migrate off fetchParties onto a view-model
  // loader reading canonical Parquet via DuckDB-WASM (mirroring PR-E / PR-F).
  import { fetchParties, type PartyEntry } from "../lib/data";

  // Load TN parties as the seed list for the editor — every party that has
  // any 2026 results will eventually appear here. Browsing a different state
  // will (in a later phase) merge its parties into this list; for v1 we just
  // show the canonical defaults and the user's overrides.
  const event = "AcGenMay2026";
  let known_parties = $state<PartyEntry[] | null>(null);
  let load_error = $state<string | null>(null);

  $effect(() => {
    Promise.all(["S22", "S11", "S25", "S03", "U07"].map(s =>
      fetchParties(event, s).then(p => p.parties).catch(() => [] as PartyEntry[]),
    ))
      .then(arrays => {
        const seen = new Map<string, PartyEntry>();
        for (const arr of arrays) for (const p of arr) {
          if (!seen.has(p.eci_code)) seen.set(p.eci_code, p);
        }
        known_parties = [...seen.values()].sort((a, b) => a.short_name.localeCompare(b.short_name));
      })
      .catch(e => (load_error = String(e)));
  });

  // Always include any party that has an override but isn't in the parties.json
  // seed (e.g. NOTA, IND, or a party loaded from a future state).
  const editable = $derived.by(() => {
    const list: { eci_code: string; short_name: string; full_name: string | null }[] = [];
    const seen = new Set<string>();
    for (const p of known_parties ?? []) {
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

    {#if load_error}
      <p class="text-sm text-rose-700">Could not load parties: <code>{load_error}</code></p>
    {:else if !known_parties}
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
