<script lang="ts">
  // ElectionMap — the geographic | equal-seats toggle for a state's
  // assembly results (UK-style elections plan, PR-B3).
  //
  // Two presentations of the SAME winners array:
  //   * "Map"         → the existing maplibre AC choropleth (StateAcMap):
  //                     true geography; large rural seats dominate visually.
  //   * "Equal seats" → the SVG TileCartogram: one equal hexagon per seat,
  //                     so a dense urban cluster reads as loud as a sparse
  //                     rural one. This is the UK-results-night idiom.
  //
  // The selected presentation persists to the URL as `?view=geo|hex` so a
  // citizen can deep-link "show me the equal-seats view". Clicking a unit
  // in either arm navigates to that constituency's page (parity).
  //
  // The equal-seats arm needs a persisted hex layout for the state
  // (`datasets/grapher/election_tile_layouts.json`). Pilot ships S13
  // (Maharashtra, 288 ACs); states without a layout show a graceful
  // "equal-seats view not available yet" note rather than an empty canvas.
  //
  // CLAUDE.md §0: no aria/role; visible affordances only.

  import StateAcMap from "../maplibre/StateAcMap.svelte";
  import TileCartogram from "../charts/TileCartogram.svelte";
  import {
    fetchElectionTileLayouts,
    selectLayout,
    buildTileRows,
    type TileLayoutRow,
    type TileWinnerInput,
    type TileRow,
  } from "../view-models/election-tile-layout";
  import type { AcWinner } from "../view-models/state-overview";
  import { colors } from "../colors/store.svelte";
  import { navigate, url } from "../url";

  interface Props {
    /** ECI state code (e.g. "S13"). */
    state: string;
    /** Per-AC winners. `null` = loading; `[]` = loaded-but-empty. */
    rows: AcWinner[] | null;
    /** Canonical event id, threaded onto AC links. */
    event?: string | null;
    /** Delimitation vintage the hex layout was authored for. */
    delim_year?: number;
    /** Override canvas height. */
    height?: string;
  }
  let {
    state: state_code,
    rows,
    event = null,
    delim_year = 2008,
    height = "520px",
  }: Props = $props();

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
    const target =
      window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash;
    history.replaceState(null, "", target);
  }

  // ─── Equal-seats (hex) layout ───────────────────────────────────────
  let layout = $state<TileLayoutRow[] | null>(null);
  let layout_error = $state(false);
  // Only fetch when the hex arm is first shown — keeps the JSON off the
  // critical path for citizens who never leave the geographic view.
  let layout_requested = false;
  $effect(() => {
    if (view !== "hex" || layout_requested) return;
    layout_requested = true;
    fetchElectionTileLayouts()
      .then((doc) => {
        layout = selectLayout(doc, {
          layout_kind: "ac",
          scope: state_code,
          delim_year,
        });
      })
      .catch(() => (layout_error = true));
  });

  const hex_winners = $derived<TileWinnerInput[]>(
    (rows ?? []).map((w) => ({
      unit_id: `IN-${state_code}-AC-${delim_year}-${w.ac_eci_no}`,
      party_key: w.party_eci_code,
      party_short: w.party_short,
      margin_pct: w.margin_pct,
    })),
  );

  const tile_rows = $derived<TileRow[]>(
    layout == null ? [] : buildTileRows(layout, hex_winners),
  );

  // Compact party legend (distinct winning parties, palette-consistent with
  // the choropleth). Built from the same `colors.forSet` allocation.
  const legend = $derived.by(() => {
    void colors.overrides;
    const list = rows ?? [];
    const palette = colors.forSet(
      list.map((r) => r.party_eci_code ?? r.party_short),
    );
    const seen = new Map<string, { label: string; color: string }>();
    for (const r of list) {
      const key = r.party_eci_code ?? r.party_short;
      if (seen.has(key)) continue;
      seen.set(key, {
        label: r.party_short,
        color: palette.get(key)?.fill ?? colors.fill(r.party_eci_code, r.party_short),
      });
    }
    return [...seen.values()];
  });

  function onSelectUnit(unit_id: string): void {
    const eci_no = Number(unit_id.split("-").pop());
    if (Number.isFinite(eci_no)) navigate(url.acByNo(state_code, eci_no, event));
  }

  const layout_unavailable = $derived(
    view === "hex" && (layout_error || (layout != null && layout.length === 0)),
  );
</script>

<div class="space-y-3">
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

  {#if view === "geo"}
    <div data-testid="election-map-geo">
      <StateAcMap state={state_code} {rows} {event} {height} />
    </div>
  {:else}
    <div data-testid="election-map-hex">
      {#if layout_unavailable}
        <div
          class="flex items-center justify-center rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500"
          style:height
        >
          Equal-seats view isn't available for this state yet — switch to
          <button
            type="button"
            class="mx-1 underline hover:text-slate-700"
            onclick={() => setView("geo")}>Map</button
          >
          to see the results.
        </div>
      {:else if layout == null}
        <p class="p-4 text-sm text-slate-500">Loading equal-seats layout…</p>
      {:else}
        <TileCartogram
          tiles={tile_rows}
          {legend}
          {height}
          onSelect={onSelectUnit}
        />
      {/if}
    </div>
  {/if}
</div>
