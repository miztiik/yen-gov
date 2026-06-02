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
  // (`datasets/grapher/election_tile_layouts.json`). States without a layout
  // never show the toggle at all — the geographic map renders on its own. A
  // tiny covered-scopes manifest (`election_tile_scopes.json`) is fetched up
  // front to decide this without pulling the large layout file.
  //
  // CLAUDE.md §0: no aria/role; visible affordances only.

  import StateAcMap from "../maplibre/StateAcMap.svelte";
  import TileCartogram from "../charts/TileCartogram.svelte";
  import {
    fetchElectionTileLayouts,
    fetchElectionTileScopes,
    hasLayoutForScope,
    selectLayout,
    buildTileRows,
    type TileLayoutRow,
    type TileWinnerInput,
    type TileRow,
  } from "../view-models/election-tile-layout";
  import type { AcWinner } from "../view-models/state-overview";
  import {
    getPartyColor,
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../colors/resolver";
  import { navigate, url } from "../url";
  import {
    DEFAULT_ELECTION_FILTERS,
    type ElectionFilters,
  } from "../election-filters";
  import {
    buildAcFills,
    buildAcOpacities,
    type PartyFill,
  } from "./election-map-coloring";

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
    /** PR-B8 filter state (colour-by mode + party/margin dimming). */
    filters?: ElectionFilters;
  }
  let {
    state: state_code,
    rows,
    event = null,
    delim_year = 2008,
    height = "520px",
    filters = DEFAULT_ELECTION_FILTERS,
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
  // Whether this state has a persisted hex layout at all. `null` = unknown
  // (manifest still loading). The toggle only appears when this is `true`.
  let has_equal_seats = $state<boolean | null>(null);
  $effect(() => {
    fetchElectionTileScopes()
      .then((doc) => {
        has_equal_seats = hasLayoutForScope(doc, {
          layout_kind: "ac",
          scope: state_code,
          delim_year,
        });
      })
      .catch(() => (has_equal_seats = false));
  });

  let layout = $state<TileLayoutRow[] | null>(null);
  let layout_error = $state(false);
  // Only fetch when the hex arm is first shown — keeps the JSON off the
  // critical path for citizens who never leave the geographic view.
  let layout_requested = false;
  $effect(() => {
    if (view !== "hex" || layout_requested || has_equal_seats === false) return;
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

  // ─── PR-B8 recolour / dim ───────────────────────────────────────────
  // PR-SYM-6f4: One-identity migration. AcWinner carries `party_id`
  // (from `view-models/state-overview` extended in PR-SYM-6d) plus the
  // additive brand_colour mirror, so we resolve through the canonical
  // 3-tier `getPartyColor` / `resolvePartyPalette` path. Rows without
  // `party_id` derive a stable `parties.IN.<UPPER(short)>` so the
  // resolver still degrades to anchor / algorithmic tiers without losing
  // identity stability. Mirrors PR #587 (IndiaMap) precedent.
  function partyIdFor(r: {
    party_id?: string | null;
    party_short: string;
  }): string {
    if (r.party_id) return r.party_id;
    const slug = (r.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  }

  function rowFor(pid: string, r: AcWinner): PartyRowForResolver | null {
    if (r.brand_colour_hex == null) return null;
    return {
      party_id: pid,
      eci_code: r.party_eci_code,
      brand_colour: {
        hex: r.brand_colour_hex,
        confidence: r.brand_colour_confidence ?? "medium",
      },
    };
  }

  // One palette allocation across every winning party, batched via
  // `resolvePartyPalette` so per-AC `party_fill(...)` calls below stay
  // O(1) map gets. Also feeds the legend below so they agree by id.
  const palette_bundle = $derived.by(() => {
    const list = rows ?? [];
    const ids: string[] = [];
    const rowMap = new Map<string, PartyRowForResolver | null>();
    const idByKey = new Map<string, string>();
    const labelByPid = new Map<string, string>();
    for (const r of list) {
      const key = r.party_eci_code ?? r.party_short;
      if (idByKey.has(key)) continue;
      const pid = partyIdFor(r);
      idByKey.set(key, pid);
      if (!labelByPid.has(pid)) labelByPid.set(pid, r.party_short);
      if (!rowMap.has(pid)) {
        ids.push(pid);
        rowMap.set(pid, rowFor(pid, r));
      }
    }
    const palette = resolvePartyPalette(ids, rowMap);
    return { palette, idByKey, labelByPid, rowMap };
  });

  const party_fill = $derived.by<PartyFill>(() => {
    const { palette, idByKey, rowMap } = palette_bundle;
    return (code, short) => {
      const key = code ?? short;
      const pid = idByKey.get(key);
      if (pid) {
        return (
          palette.get(pid)?.hex ??
          getPartyColor(pid, rowMap.get(pid) ?? null).hex
        );
      }
      // Party not present in `rows` (defensive): derive a stable id and
      // resolve through the same tiers so the swatch stays identity-stable.
      const fallback_pid = `parties.IN.${(short ?? "UNK").trim().toUpperCase()}`;
      return getPartyColor(fallback_pid, null).hex;
    };
  });

  const fills_override = $derived<Record<number, string>>(
    buildAcFills(rows ?? [], filters.mode, party_fill),
  );
  const opacities_override = $derived<Record<number, number>>(
    buildAcOpacities(rows ?? [], filters.mode, filters),
  );

  const raw_tile_rows = $derived<TileRow[]>(
    layout == null ? [] : buildTileRows(layout, hex_winners),
  );
  // Re-skin the hex tiles with the same mode/filter colouring as the geo arm.
  const tile_rows = $derived<TileRow[]>(
    raw_tile_rows.map((t) => {
      const eci_no = Number(t.unit_id.split("-").pop());
      const fill = fills_override[eci_no];
      const opacity = opacities_override[eci_no];
      return {
        ...t,
        fill: fill ?? t.fill,
        opacity: opacity ?? t.opacity,
      };
    }),
  );

  // Compact party legend (distinct winning parties, palette-consistent
  // with the choropleth). Built off the same `palette_bundle` so swatch
  // and polygon agree by `party_id`.
  const legend = $derived.by(() => {
    const { palette, idByKey, labelByPid, rowMap } = palette_bundle;
    const seen = new Map<string, { label: string; color: string }>();
    for (const pid of idByKey.values()) {
      if (seen.has(pid)) continue;
      seen.set(pid, {
        label: labelByPid.get(pid) ?? pid,
        color:
          palette.get(pid)?.hex ??
          getPartyColor(pid, rowMap.get(pid) ?? null).hex,
      });
    }
    return [...seen.values()];
  });

  // Row URL (ADR-0049): the AC link grammar carries a readable name suffix
  // (`/s/<state>/ac/<eci_no>-<name-slug>`). The map click only knows the
  // eci_no, so map it back to the AC name from `rows`; an absent name makes
  // `url.ac` fall back to the bare eci_no (still parse-tolerant).
  const name_by_eci = $derived.by(() => {
    const m = new Map<number, string>();
    for (const r of rows ?? []) m.set(r.ac_eci_no, r.ac_name);
    return m;
  });

  function onSelectUnit(unit_id: string): void {
    const eci_no = Number(unit_id.split("-").pop());
    if (Number.isFinite(eci_no))
      navigate(url.ac(state_code, eci_no, name_by_eci.get(eci_no) ?? "", event));
  }

  const layout_unavailable = $derived(
    view === "hex" &&
      (has_equal_seats === false ||
        layout_error ||
        (layout != null && layout.length === 0)),
  );
</script>

<div class="space-y-3">
  <div class="flex items-center justify-between gap-3">
    <p class="text-xs text-slate-500">
      {view === "hex" ? "Each tile = one seat" : "Seats sized by geography"}
    </p>
    {#if has_equal_seats === true}
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
    {/if}
  </div>

  {#if view === "geo"}
    <div data-testid="election-map-geo">
      <StateAcMap
        state={state_code}
        {rows}
        {event}
        {height}
        fillsOverride={fills_override}
        opacitiesOverride={opacities_override}
      />
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
