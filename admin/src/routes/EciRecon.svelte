<script lang="ts">
  // ECI Recon panel — discover, compare, pin category_ids.
  //
  // Three sections (vertical):
  //   1. Sweep — run an enumeration of category_ids 1..N and show the table.
  //      Hits link out to /api/election-result?category_id=<n> for verification.
  //   2. Compare — pick two ids, fetch both, render side-by-side. Used to
  //      disambiguate the May-2026 cohort which appears twice in the catalogue.
  //   3. Pins — table of config/eci-pins.json. Add/edit/delete with confirm
  //      checkbox; backend hot-reloads categories.py so the next pipeline
  //      run picks up changes without restart.

  import { api, type EciHit, type EciSweepResult, type EciPinEntry, type EciProbe } from "../lib/api";

  // --- Sweep state ---
  let sweep_start = $state(1);
  let sweep_end = $state(50);
  let sweep_sleep = $state(300);
  let sweep_running = $state(false);
  let sweep_error = $state<string | null>(null);
  let sweep_data = $state<EciSweepResult | null>(null);

  // --- Compare state ---
  let cmp_a = $state(20);
  let cmp_b = $state(25);
  let cmp_running = $state(false);
  let cmp_error = $state<string | null>(null);
  let cmp_result = $state<{ a: EciProbe; b: EciProbe } | null>(null);

  // --- Pins state ---
  let pins = $state<EciPinEntry[]>([]);
  let pins_loaded_in_process = $state<{ state: string; year: number; category_id: number }[]>([]);
  let pins_error = $state<string | null>(null);
  let pin_form = $state({
    state: "",
    year: 2026,
    category_id: 0,
    cat_name: "",
    notes: "",
  });
  let pin_form_busy = $state(false);
  let pin_form_msg = $state<string | null>(null);
  let prefill_from: number | null = $state(null);

  async function loadLastSweep(): Promise<void> {
    try {
      const r = await api.eciLastSweep();
      if (r.available) {
        sweep_data = r;
      }
    } catch (e) {
      // Non-fatal — first time there is no file.
      console.warn("no prior sweep on disk:", e);
    }
  }

  async function runSweep(): Promise<void> {
    sweep_error = null;
    sweep_running = true;
    try {
      sweep_data = await api.eciSweep(sweep_start, sweep_end, sweep_sleep);
    } catch (e) {
      sweep_error = String(e);
    } finally {
      sweep_running = false;
    }
  }

  async function runCompare(): Promise<void> {
    cmp_error = null;
    cmp_running = true;
    try {
      cmp_result = await api.eciCompare(cmp_a, cmp_b);
    } catch (e) {
      cmp_error = String(e);
    } finally {
      cmp_running = false;
    }
  }

  async function loadPins(): Promise<void> {
    try {
      const r = await api.eciPins();
      pins = r.payload.pins;
      pins_loaded_in_process = r.loaded_in_process;
      pins_error = null;
    } catch (e) {
      pins_error = String(e);
    }
  }

  function prefillFromHit(hit: EciHit): void {
    pin_form.cat_name = hit.cat_name;
    pin_form.category_id = hit.id;
    pin_form.notes = `Discovered via sweep ${sweep_data?.ts ?? ""}; index_url=${hit.index_url}`;
    prefill_from = hit.id;
    // Best-effort state guess (S22, U07, etc.) from cat_name — operator can override.
    const nameToCode: Record<string, string> = {
      "Assam": "S03", "Kerala": "S11", "Puducherry": "U07",
      "Tamil Nadu": "S22", "West Bengal": "S25", "Bihar": "S04",
      "NCT of Delhi": "U05", "Andhra Pradesh": "S01",
      "Arunachal Pradesh": "S02", "Odisha": "S18", "Sikkim": "S21",
      "Haryana": "S07", "Jammu and Kashmir": "U08", "Maharashtra": "S13",
      "Jharkhand": "S27",
    };
    for (const [name, code] of Object.entries(nameToCode)) {
      if (hit.cat_name.includes(name)) {
        pin_form.state = code;
        break;
      }
    }
    // Year — pull a 4-digit run from the cat_name.
    const m = hit.cat_name.match(/(20\d{2})/);
    if (m) pin_form.year = Number(m[1]);
    // Scroll the pins section into view.
    document.getElementById("pin-form")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function submitPin(): Promise<void> {
    pin_form_msg = null;
    pin_form_busy = true;
    try {
      const res = await api.eciUpsertPin({
        state: pin_form.state,
        year: pin_form.year,
        category_id: pin_form.category_id,
        cat_name: pin_form.cat_name,
        notes: pin_form.notes || undefined,
      });
      pin_form_msg = res.replaced
        ? `Replaced pin for (${res.entry.state}, ${res.entry.year}) → ${res.entry.category_id}.`
        : `Added pin for (${res.entry.state}, ${res.entry.year}) → ${res.entry.category_id}.`;
      await loadPins();
    } catch (e) {
      pin_form_msg = `Error: ${e}`;
    } finally {
      pin_form_busy = false;
    }
  }

  async function deletePin(state: string, year: number): Promise<void> {
    if (!confirm(`Delete pin (${state}, ${year})?`)) return;
    try {
      await api.eciDeletePin(state, year);
      await loadPins();
    } catch (e) {
      pins_error = String(e);
    }
  }

  // --- Download (triggers eci-statreport --download via Pipeline endpoint) ---
  let download_busy = $state<Record<string, boolean>>({});
  let download_msg = $state<Record<string, string>>({});

  async function downloadStatReport(p: EciPinEntry, includePdf: boolean): Promise<void> {
    const key = `${p.state}-${p.year}`;
    if (!confirm(
      `Download Statistical Report for (${p.state}, ${p.year}) — category_id ${p.category_id}?\n\n` +
      `Files land in .runtime/raw/eci/ (debug area, not datasets/).\n` +
      (includePdf ? "Includes PDF zips." : "XLSX only (PDF skipped).")
    )) return;
    download_busy = { ...download_busy, [key]: true };
    download_msg = { ...download_msg, [key]: "" };
    try {
      const args = [p.state, String(p.year), "--download"];
      if (!includePdf) args.push("--skip-pdf");
      const res = await api.triggerPipeline({
        command: "eci-statreport",
        args,
        confirm: true,
      });
      download_msg = { ...download_msg, [key]: `Started run ${res.run_id} — see Pipeline panel for live tail.` };
    } catch (e) {
      download_msg = { ...download_msg, [key]: `Error: ${e}` };
    } finally {
      download_busy = { ...download_busy, [key]: false };
    }
  }

  $effect(() => {
    void loadLastSweep();
    void loadPins();
  });
</script>

<div class="space-y-8">
  <header>
    <h1 class="text-2xl font-bold">🛰 ECI Recon</h1>
    <p class="text-sm text-slate-400 mt-1">
      Discover, confirm, and pin <code>category_id</code> values for the
      ECI Statistical Report API. Pins are written to
      <code>config/eci-pins.json</code> and hot-loaded by the pipeline.
    </p>
  </header>

  <!-- 1. Sweep ------------------------------------------------------- -->
  <section class="border border-slate-800 rounded-lg p-4 space-y-3">
    <h2 class="text-lg font-semibold">1. Enumerate</h2>
    <p class="text-xs text-slate-500">
      Sweeps <code>/api/election-result?category_id=&lt;n&gt;</code> for n in
      [start, end]. Result is persisted at
      <code>tools/eci_recon/categories.enumeration.json</code>.
    </p>
    <div class="flex flex-wrap gap-3 items-end text-sm">
      <label class="flex flex-col">
        <span class="text-xs text-slate-400">start</span>
        <input type="number" min="1" bind:value={sweep_start}
               class="bg-slate-800 border border-slate-700 rounded px-2 py-1 w-20" />
      </label>
      <label class="flex flex-col">
        <span class="text-xs text-slate-400">end</span>
        <input type="number" min="1" bind:value={sweep_end}
               class="bg-slate-800 border border-slate-700 rounded px-2 py-1 w-20" />
      </label>
      <label class="flex flex-col">
        <span class="text-xs text-slate-400">sleep_ms</span>
        <input type="number" min="0" max="5000" bind:value={sweep_sleep}
               class="bg-slate-800 border border-slate-700 rounded px-2 py-1 w-24" />
      </label>
      <button onclick={runSweep} disabled={sweep_running}
              class="bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-900 font-semibold rounded px-3 py-1">
        {sweep_running ? "Sweeping…" : "Run sweep"}
      </button>
      {#if sweep_data}
        <span class="text-xs text-slate-500">last: {sweep_data.ts}</span>
      {/if}
    </div>
    {#if sweep_error}
      <p class="text-rose-400 text-sm">{sweep_error}</p>
    {/if}
    {#if sweep_data}
      <div class="text-xs text-slate-400">
        hits={sweep_data.hits.length} · errors={sweep_data.errors.length} · misses={sweep_data.misses.length}
      </div>
      <div class="overflow-x-auto max-h-96 border border-slate-800 rounded">
        <table class="text-sm w-full">
          <thead class="text-xs text-slate-400 sticky top-0 bg-slate-900">
            <tr>
              <th class="text-left px-2 py-1">id</th>
              <th class="text-left px-2 py-1">cat_name</th>
              <th class="text-left px-2 py-1">index_name</th>
              <th class="text-left px-2 py-1">index_url</th>
              <th class="px-2 py-1"></th>
            </tr>
          </thead>
          <tbody>
            {#each sweep_data.hits as h (h.id)}
              <tr class="border-t border-slate-800 hover:bg-slate-900/50">
                <td class="px-2 py-1 font-mono">{h.id}</td>
                <td class="px-2 py-1">{h.cat_name}</td>
                <td class="px-2 py-1 text-xs text-slate-400">{h.index_name || "—"}</td>
                <td class="px-2 py-1 text-xs">
                  {#if h.index_url}
                    <a href={h.index_url} target="_blank" rel="noreferrer" class="text-sky-400 underline break-all">{h.index_url}</a>
                  {:else}
                    <span class="text-slate-600">—</span>
                  {/if}
                </td>
                <td class="px-2 py-1 text-right">
                  <button onclick={() => prefillFromHit(h)}
                          class="text-xs bg-slate-800 hover:bg-slate-700 rounded px-2 py-0.5">📌 Pin…</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>

  <!-- 2. Compare ----------------------------------------------------- -->
  <section class="border border-slate-800 rounded-lg p-4 space-y-3">
    <h2 class="text-lg font-semibold">2. Compare two ids</h2>
    <p class="text-xs text-slate-500">
      Some elections appear under multiple <code>category_id</code> values
      (e.g. one empty placeholder + one real "Copy of Index Cards
      [Digital]"). Compare side-by-side before pinning.
    </p>
    <div class="flex flex-wrap gap-3 items-end text-sm">
      <label class="flex flex-col">
        <span class="text-xs text-slate-400">id A</span>
        <input type="number" min="1" bind:value={cmp_a}
               class="bg-slate-800 border border-slate-700 rounded px-2 py-1 w-20" />
      </label>
      <label class="flex flex-col">
        <span class="text-xs text-slate-400">id B</span>
        <input type="number" min="1" bind:value={cmp_b}
               class="bg-slate-800 border border-slate-700 rounded px-2 py-1 w-20" />
      </label>
      <button onclick={runCompare} disabled={cmp_running}
              class="bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-900 font-semibold rounded px-3 py-1">
        {cmp_running ? "Comparing…" : "Compare"}
      </button>
    </div>
    {#if cmp_error}<p class="text-rose-400 text-sm">{cmp_error}</p>{/if}
    {#if cmp_result}
      <div class="grid grid-cols-2 gap-3 text-xs">
        {#each [cmp_result.a, cmp_result.b] as side (side.id)}
          <div class="border border-slate-800 rounded p-3 space-y-1">
            <div class="font-mono text-amber-400">id={side.id} · {side.kind}</div>
            {#if side.kind === "hit"}
              <div><span class="text-slate-400">cat_name:</span> {side.cat_name}</div>
              <div><span class="text-slate-400">index_name:</span> {side.index_name || "(empty)"}</div>
              <div><span class="text-slate-4notes</th>
            <th class="text-left px-2 py-1">download</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each pins as p (`${p.state}-${p.year}`)}
            {@const key = `${p.state}-${p.year}`}
            <tr class="border-t border-slate-800 align-top">
              <td class="px-2 py-1 font-mono">{p.state}</td>
              <td class="px-2 py-1">{p.year}</td>
              <td class="px-2 py-1 font-mono">{p.category_id}</td>
              <td class="px-2 py-1 text-xs">{p.cat_name}</td>
              <td class="px-2 py-1 text-xs text-slate-500 max-w-xs" title={p.notes}>{p.notes || ""}</td>
              <td class="px-2 py-1 text-xs whitespace-nowrap">
                <button onclick={() => downloadStatReport(p, false)} disabled={download_busy[key]}
                        class="bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 text-white rounded px-2 py-0.5 mr-1"
                        title="Run eci-statreport --download --skip-pdf">
                  {download_busy[key] ? "…" : "⬇ XLSX"}
                </button>
                <button onclick={() => downloadStatReport(p, true)} disabled={download_busy[key]}
                        class="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white rounded px-2 py-0.5"
                        title="Run eci-statreport --download (XLSX + PDF)">
                  ⬇ +PDF
                </button>
                {#if download_msg[key]}
                  <div class="text-[10px] mt-1"
                       class:text-rose-400={download_msg[key].startsWith("Error")}
                       class:text-emerald-400={!download_msg[key].startsWith("Error")}>
                    {download_msg[key]}
                  </div>
                {/if}
              
  </section>

  <!-- 3. Pins -------------------------------------------------------- -->
  <section class="border border-slate-800 rounded-lg p-4 space-y-3">
    <h2 class="text-lg font-semibold">3. Pins (config/eci-pins.json)</h2>
    {#if pins_error}<p class="text-rose-400 text-sm">{pins_error}</p>{/if}

    <div class="overflow-x-auto border border-slate-800 rounded">
      <table class="text-sm w-full">
        <thead class="text-xs text-slate-400">
          <tr>
            <th class="text-left px-2 py-1">state</th>
            <th class="text-left px-2 py-1">year</th>
            <th class="text-left px-2 py-1">category_id</th>
            <th class="text-left px-2 py-1">cat_name</th>
            <th class="text-left px-2 py-1">confirmed_at</th>
            <th class="text-left px-2 py-1">notes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each pins as p (`${p.state}-${p.year}`)}
            <tr class="border-t border-slate-800">
              <td class="px-2 py-1 font-mono">{p.state}</td>
              <td class="px-2 py-1">{p.year}</td>
              <td class="px-2 py-1 font-mono">{p.category_id}</td>
              <td class="px-2 py-1 text-xs">{p.cat_name}</td>
              <td class="px-2 py-1 text-xs text-slate-500">{p.confirmed_at}</td>
              <td class="px-2 py-1 text-xs text-slate-500 max-w-xs truncate" title={p.notes}>{p.notes || ""}</td>
              <td class="px-2 py-1 text-right">
                <button onclick={() => deletePin(p.state, p.year)}
                        class="text-xs text-rose-400 hover:text-rose-300">delete</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <details class="text-xs text-slate-500">
      <summary class="cursor-pointer">Loaded in process: {pins_loaded_in_process.length} pins</summary>
      <pre class="mt-1 bg-slate-900 p-2 rounded overflow-x-auto">{JSON.stringify(pins_loaded_in_process, null, 2)}</pre>
    </details>

    <form id="pin-form" class="space-y-2 border-t border-slate-800 pt-3"
          onsubmit={(e) => { e.preventDefault(); void submitPin(); }}>
      <h3 class="text-sm font-semibold">Add or replace pin</h3>
      {#if prefill_from !== null}
        <p class="text-xs text-amber-400">Pre-filled from sweep id {prefill_from}.</p>
      {/if}
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
        <label class="flex flex-col">
          <span class="text-xs text-slate-400">state (e.g. U07)</span>
          <input bind:value={pin_form.state} required pattern="^[SU][0-9]{'{2}'}$"
                 class="bg-slate-800 border border-slate-700 rounded px-2 py-1" />
        </label>
        <label class="flex flex-col">
          <span class="text-xs text-slate-400">year</span>
          <input type="number" min="2024" max="2099" required bind:value={pin_form.year}
                 class="bg-slate-800 border border-slate-700 rounded px-2 py-1" />
        </label>
        <label class="flex flex-col">
          <span class="text-xs text-slate-400">category_id</span>
          <input type="number" min="1" required bind:value={pin_form.category_id}
                 class="bg-slate-800 border border-slate-700 rounded px-2 py-1" />
        </label>
        <label class="flex flex-col md:col-span-1">
          <span class="text-xs text-slate-400">notes (optional)</span>
          <input bind:value={pin_form.notes}
                 class="bg-slate-800 border border-slate-700 rounded px-2 py-1" />
        </label>
        <label class="flex flex-col col-span-2 md:col-span-4">
          <span class="text-xs text-slate-400">cat_name (verbatim from API)</span>
          <input required bind:value={pin_form.cat_name}
                 class="bg-slate-800 border border-slate-700 rounded px-2 py-1" />
        </label>
      </div>
      <div class="flex items-center gap-3">
        <button type="submit" disabled={pin_form_busy}
                class="bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-900 font-semibold rounded px-3 py-1 text-sm">
          {pin_form_busy ? "Saving…" : "Save pin"}
        </button>
        {#if pin_form_msg}
          <span class="text-xs"
                class:text-rose-400={pin_form_msg.startsWith("Error")}
                class:text-emerald-400={!pin_form_msg.startsWith("Error")}>
            {pin_form_msg}
          </span>
        {/if}
      </div>
    </form>
  </section>
</div>
