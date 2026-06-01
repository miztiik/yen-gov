<script lang="ts">
  // NationalElectionsAtlas — the all-India Parliamentary-Constituency results
  // surface for one Lok Sabha event (UK-style elections plan, PR-B4).
  //
  // Two presentations of the same national PC winners, mirroring the state
  // ElectionMap (PR-B3):
  //   * "Map"         → maplibre PC choropleth over INDIA_PC (true geography).
  //   * "Equal seats" → the national PC TileCartogram (one hex per seat).
  //
  // The view persists to `?view=geo|hex`. A seat-total bar runs across the
  // top so the citizen reads "who won how many" before scanning geography.
  //
  // Ships DARK: if PC results are not yet ingested, the boundary still draws
  // and a "results pending" note shows in place of tinted seats. It lights up
  // automatically once the PC parquet lands (PR-A4).
  //
  // CARTOGRAPHY CONTRACT (sources.ts INDIA_PC): the 2 J&K-territory
  // placeholders (ls_seat_code=999) carry no winner, so `hatch_unmapped`
  // renders them with a diagonal hatch — never an election tint.
  //
  // CLAUDE.md §0: no aria/role beyond native; visible affordances only.

  import MapChoropleth from "../lib/maplibre/MapChoropleth.svelte";
  import { INDIA_PC } from "../lib/maplibre/sources";
  import TileCartogram from "../lib/charts/TileCartogram.svelte";
  import {
    fetchElectionTileLayouts,
    selectLayout,
    buildTileRows,
    type TileLayoutRow,
    type TileWinnerInput,
    type TileRow,
  } from "../lib/view-models/election-tile-layout";
  import {
    loadNationalPcWinners,
    type NationalPcWinner,
  } from "../lib/view-models/national-elections";
  import type { LoaderResult } from "../lib/loader-result";
  import { colors } from "../lib/colors/store.svelte";
  import { navigate, url } from "../lib/url";
  import ElectionFilterRail from "../lib/elections/ElectionFilterRail.svelte";
  import {
    DEFAULT_ELECTION_FILTERS,
    parseElectionFilters,
    serializeElectionFilters,
    type ElectionFilters,
  } from "../lib/election-filters";
  import {
    buildKeyedFills,
    buildKeyedOpacities,
    hasModeCoverage,
    type PartyFill,
  } from "../lib/elections/election-map-coloring";

  interface Props {
    /** Route params; `event` is the Lok Sabha event id (e.g. "LsGenJun2024"). */
    params: { event: string };
  }
  let { params }: Props = $props();
  const event = $derived(params.event);

  const DELIM_YEAR = 2008;
  const HEIGHT = "560px";

  // ─── Winners load ───────────────────────────────────────────────────
  let result = $state<LoaderResult<NationalPcWinner[]>>({ status: "loading" });
  $effect(() => {
    const ev = event;
    result = { status: "loading" };
    loadNationalPcWinners(ev).then((r) => {
      // Guard against a stale event switch resolving after a newer one.
      if (ev === event) result = r;
    });
  });

  const winners = $derived<NationalPcWinner[]>(
    result.status === "ok" || result.status === "partial" ? result.data : [],
  );
  const pending = $derived(
    result.status === "partial" ||
      (result.status === "ok" && winners.length === 0),
  );

  // ─── PR-B9 filter rail (party / margin band / colour-by) ────────────────
  // Same URL grammar + typed translator as the state arm (PR-B8); the rail
  // recolours the SAME PC choropleth/cartogram and dims out-of-filter seats.
  function readSearch(): string {
    return typeof window === "undefined" ? "" : window.location.search;
  }
  let filter_search = $state<string>(readSearch());
  const filters = $derived<ElectionFilters>(parseElectionFilters(filter_search));

  function onFilterChange(next: ElectionFilters): void {
    if (typeof window === "undefined") return;
    const base = new URLSearchParams(window.location.search);
    const qs = serializeElectionFilters(next, base);
    const target =
      window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash;
    navigate(target);
    filter_search = qs ? `?${qs}` : "";
  }

  const party_options = $derived.by(() => {
    void colors.overrides;
    const palette = colors.forSet(
      winners.map((w) => w.party_eci_code ?? w.party_short),
    );
    const seen = new Map<string, { code: string; short: string; color: string }>();
    for (const w of winners) {
      const code = w.party_eci_code ?? w.party_short;
      if (seen.has(code)) continue;
      seen.set(code, {
        code,
        short: w.party_short,
        color: palette.get(code)?.fill ?? colors.fill(w.party_eci_code, w.party_short),
      });
    }
    return [...seen.values()];
  });
  const mode_coverage = $derived({
    turnout: hasModeCoverage(winners, "turnout"),
    age: hasModeCoverage(winners, "age"),
  });

  // ─── View toggle (persisted to ?view) ───────────────────────────────
  type ViewMode = "geo" | "hex";
  function readView(): ViewMode {
    if (typeof window === "undefined") return "geo";
    return new URLSearchParams(window.location.search).get("view") === "hex"
      ? "hex"
      : "geo";
  }
  let view = $state<ViewMode>(readView());
  function setView(next: ViewMode): void {
    if (next === view) return;
    view = next;
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (next === "geo") params.delete("view");
    else params.set("view", "hex");
    const qs = params.toString();
    history.replaceState(
      null,
      "",
      window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash,
    );
  }

  function escapeHtml(s: string): string {
    return s.replace(/[&<>"']/g, (c) =>
      c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : c === '"' ? "&quot;" : "&#39;",
    );
  }

  // ─── Palette (one allocation across every winning party) ────────────
  const palette = $derived.by(() => {
    void colors.overrides;
    return colors.forSet(winners.map((w) => w.party_eci_code ?? w.party_short));
  });
  function fillFor(w: NationalPcWinner): string {
    return (
      palette.get(w.party_eci_code ?? w.party_short)?.fill ??
      colors.fill(w.party_eci_code, w.party_short)
    );
  }

  // ─── Geographic (choropleth) arm ────────────────────────────────────
  const party_fill = $derived.by<PartyFill>(() => {
    void colors.overrides;
    const list = winners;
    const palette = colors.forSet(
      list.map((w) => w.party_eci_code ?? w.party_short),
    );
    return (code, short) =>
      palette.get(code ?? short)?.fill ?? colors.fill(code, short);
  });
  const fills = $derived<Record<string, string>>(
    buildKeyedFills(winners, filters.mode, party_fill, (w) => w.join_key),
  );
  const opacities = $derived<Record<string, number>>(
    buildKeyedOpacities(winners, filters.mode, filters, (w) => w.join_key),
  );
  const tooltips = $derived.by(() => {
    const out: Record<string, string> = {};
    for (const w of winners) {
      const m = w.margin_pct == null ? "—" : `${w.margin_pct.toFixed(1)}%`;
      out[w.join_key] =
        `<div class="font-semibold">${escapeHtml(w.pc_name)}</div>` +
        `<div class="text-slate-600">Winner: ${escapeHtml(w.party_short)}</div>` +
        `<div class="text-slate-500">Margin: ${m}</div>`;
    }
    return out;
  });

  function onSelectGeo(sel: { properties: Record<string, unknown> }): void {
    const sc = sel.properties?.state_ut_code;
    if (typeof sc === "string" && sc) navigate(url.stateElection(sc, event));
  }

  // ─── Equal-seats (hex) arm ──────────────────────────────────────────
  let layout = $state<TileLayoutRow[] | null>(null);
  let layout_error = $state(false);
  let layout_requested = false;
  $effect(() => {
    if (view !== "hex" || layout_requested) return;
    layout_requested = true;
    fetchElectionTileLayouts()
      .then((doc) => {
        layout = selectLayout(doc, {
          layout_kind: "pc",
          scope: "national",
          delim_year: DELIM_YEAR,
        });
      })
      .catch(() => (layout_error = true));
  });

  const hex_winners = $derived<TileWinnerInput[]>(
    winners.map((w) => ({
      unit_id: w.unit_id,
      party_key: w.party_eci_code,
      party_short: w.party_short,
      margin_pct: w.margin_pct,
    })),
  );
  const raw_tile_rows = $derived<TileRow[]>(
    layout == null ? [] : buildTileRows(layout, hex_winners),
  );
  // Re-skin the hex tiles with the same mode/filter colouring as the geo arm.
  const hex_fills = $derived<Record<string, string>>(
    buildKeyedFills(winners, filters.mode, party_fill, (w) => w.unit_id),
  );
  const hex_opacities = $derived<Record<string, number>>(
    buildKeyedOpacities(winners, filters.mode, filters, (w) => w.unit_id),
  );
  const tile_rows = $derived<TileRow[]>(
    raw_tile_rows.map((t) => ({
      ...t,
      fill: hex_fills[t.unit_id] ?? t.fill,
      opacity: hex_opacities[t.unit_id] ?? t.opacity,
    })),
  );
  function onSelectHex(unit_id: string): void {
    // unit_id = IN-PC-<delim>-<state_code>-<pc_no>; drill to that state.
    const parts = unit_id.split("-");
    const sc = parts[3];
    if (sc) navigate(url.stateElection(sc, event));
  }
  const layout_unavailable = $derived(
    view === "hex" && (layout_error || (layout != null && layout.length === 0)),
  );

  // ─── Seat-total bar (winners grouped by party, desc) ────────────────
  const seat_totals = $derived.by(() => {
    void colors.overrides;
    const by = new Map<
      string,
      { label: string; color: string; seats: number }
    >();
    for (const w of winners) {
      const key = w.party_eci_code ?? w.party_short;
      const cur = by.get(key);
      if (cur) cur.seats += 1;
      else by.set(key, { label: w.party_short, color: fillFor(w), seats: 1 });
    }
    return [...by.values()].sort((a, b) => b.seats - a.seats);
  });
  const total_seats = $derived(winners.length);
</script>

<main class="mx-auto max-w-5xl space-y-5 p-4">
  <header class="space-y-1">
    <h1 class="text-2xl font-semibold text-slate-900">
      National results — Parliamentary Constituencies
    </h1>
    <p class="text-sm text-slate-500">
      Lok Sabha event <code class="text-slate-700">{event}</code>. Each seat is
      one Member of Parliament; switch between true geography and an
      equal-seats grid where every constituency counts the same.
    </p>
  </header>

  {#if result.status === "failed"}
    <div
      class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    >
      {result.reason}
      {#if result.retry}
        <button
          type="button"
          class="ml-2 underline"
          onclick={() => result.status === "failed" && result.retry?.()}
          >Try again</button
        >
      {/if}
    </div>
  {:else}
    <!-- Seat-total bar -->
    {#if total_seats > 0}
      <section
        class="space-y-1"
        data-testid="national-seat-total-bar"
      >
        <div class="flex h-5 w-full overflow-hidden rounded bg-slate-100">
          {#each seat_totals as p (p.label)}
            <div
              class="h-full"
              style:width="{(p.seats / total_seats) * 100}%"
              style:background-color={p.color}
              title="{p.label}: {p.seats} seats"
            ></div>
          {/each}
        </div>
        <div class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
          {#each seat_totals.slice(0, 8) as p (p.label)}
            <span class="inline-flex items-center gap-1">
              <span
                class="inline-block h-2.5 w-2.5 rounded-sm"
                style:background-color={p.color}
              ></span>
              {p.label}
              <span class="font-medium text-slate-900">{p.seats}</span>
            </span>
          {/each}
        </div>
      </section>
    {/if}

    <!-- View toggle -->
    <div class="flex items-center justify-between gap-3">
      <p class="text-xs text-slate-500">
        {view === "hex" ? "Each tile = one seat" : "Seats sized by geography"}
      </p>
      <div
        class="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-sm"
        role="group"
        data-testid="election-map-toggle"
      >
        <button
          type="button"
          class="rounded-md px-3 py-1 transition-colors {view === 'geo'
            ? 'bg-white font-medium text-slate-900 shadow-sm'
            : 'text-slate-500 hover:text-slate-700'}"
          aria-pressed={view === "geo"}
          data-view="geo"
          onclick={() => setView("geo")}
        >
          Map
        </button>
        <button
          type="button"
          class="rounded-md px-3 py-1 transition-colors {view === 'hex'
            ? 'bg-white font-medium text-slate-900 shadow-sm'
            : 'text-slate-500 hover:text-slate-700'}"
          aria-pressed={view === "hex"}
          data-view="hex"
          onclick={() => setView("hex")}
        >
          Equal seats
        </button>
      </div>
    </div>

    {#if !pending && winners.length > 0}
      <ElectionFilterRail
        {filters}
        parties={party_options}
        coverage={mode_coverage}
        onChange={onFilterChange}
      />
    {/if}

    {#if pending}
      <div
        class="rounded border border-dashed border-slate-300 bg-slate-50 p-3 text-center text-sm text-slate-500"
      >
        Results for this election are not published in the atlas yet — the
        constituency map below shows the seat geography; winners will appear
        here once the count is ingested.
      </div>
    {/if}

    {#if view === "geo"}
      <div data-testid="national-election-map-geo">
        <MapChoropleth
          entry={INDIA_PC}
          {fills}
          {opacities}
          {tooltips}
          height={HEIGHT}
          hatch_unmapped={true}
          onSelect={onSelectGeo}
        />
      </div>
    {:else}
      <div data-testid="national-election-map-hex">
        {#if layout_unavailable}
          <div
            class="flex items-center justify-center rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500"
            style:height={HEIGHT}
          >
            Equal-seats view isn't available yet — switch to
            <button
              type="button"
              class="mx-1 underline hover:text-slate-700"
              onclick={() => setView("geo")}>Map</button
            >
            to see the constituency geography.
          </div>
        {:else if layout == null}
          <p class="p-4 text-sm text-slate-500">Loading equal-seats layout…</p>
        {:else}
          <TileCartogram tiles={tile_rows} height={HEIGHT} onSelect={onSelectHex} />
        {/if}
      </div>
    {/if}
  {/if}
</main>
