<script lang="ts">
  // State-level AC choropleth. Each AC colored by its winning party;
  // opacity proportional to margin of victory (clearer wins → bolder fill).
  // Hover shows the AC name + winner + margin; click navigates to the AC
  // detail page.
  //
  // Joins AC_NO from the boundary GeoJSON to the canonical `ac_eci_no`
  // column in results.sqlite (ADR-0019). The HTL shapefiles use 1-based
  // AC_NO matching ECI's numbering, except for Assam where boundaries
  // predate the 2023 delimitation (caveat surfaced in sources.ts
  // attribution).

  import MapChoropleth from "./MapChoropleth.svelte";
  import { STATE_AC } from "./sources";
  import { colors } from "../colors/store.svelte";
  import { navigate, url } from "../url";
  import type { AcWinner } from "../view-models/state-overview";

  interface Props {
    state: string;
    /** Per-AC winners + margin. Parent loads via `loadStateOverview` (state hub)
     *  or `loadStateAcWinners` (constituency drill-down) and passes them in.
     *  `null` = still loading; `[]` = loaded but empty (not_published). */
    rows: AcWinner[] | null;
    /**
     * When set, the map dims every other AC to a low opacity so this one
     * stands out. Used by the per-AC drill-down page to render a state map
     * with the focused constituency emphasised.
     */
    highlight_eci_no?: number;
    /** Override map height. Defaults to a tall canvas suitable for the state
     * overview; the per-AC page can pass a shorter value. */
    height?: string;
  }
  let { state: state_code, rows: input_rows, highlight_eci_no, height = "520px" }: Props = $props();

  interface Row {
    eci_no: number;
    name: string;
    winner_party_eci_code: string | null;
    winner_party_short: string;
    margin_pct: number;
  }

  // PR-J (Phase 1.5): rows now flow in from the parent via the canonical
  // view-model loaders (loadStateOverview / loadStateAcWinners). The
  // legacy `getDb` + `results.sqlite` query is gone — this is a pure
  // presentational map.
  const rows = $derived<Row[] | null>(
    input_rows == null
      ? null
      : input_rows.map((w) => ({
          eci_no: w.ac_eci_no,
          name: w.ac_name,
          winner_party_eci_code: w.party_eci_code,
          winner_party_short: w.party_short,
          margin_pct: w.margin_pct,
        })),
  );

  const entry = $derived(STATE_AC[state_code]);

  const fills = $derived.by(() => {
    const out: Record<number, string> = {};
    void colors.overrides;
    const list = rows ?? [];
    // colors.forSet: one allocation across every winning party in the state
    // so two unanchored regional parties never land on near-identical hues.
    const palette = colors.forSet(
      list.map(r => r.winner_party_eci_code ?? r.winner_party_short),
    );
    for (const r of list) {
      const k = r.winner_party_eci_code ?? r.winner_party_short;
      out[r.eci_no] = palette.get(k)?.fill
        ?? colors.fill(r.winner_party_eci_code, r.winner_party_short);
    }
    return out;
  });

  // Map margin% → opacity in [0.35, 0.95]. Anything ≥30% margin saturates.
  // Below 1% (knife-edge) drops to the floor so it visually screams "close".
  // When `highlight_eci_no` is set, every AC except the highlighted one is
  // multiplied by ~0.18 so the focused seat reads first; the highlighted
  // seat is forced to full opacity so it never washes out.
  const opacities = $derived.by(() => {
    const out: Record<number, number> = {};
    for (const r of rows ?? []) {
      const m = Math.max(0, Math.min(30, r.margin_pct ?? 0));
      const base = 0.35 + (m / 30) * 0.6;
      if (highlight_eci_no === undefined) {
        out[r.eci_no] = base;
      } else if (r.eci_no === highlight_eci_no) {
        out[r.eci_no] = 1;
      } else {
        out[r.eci_no] = base * 0.18;
      }
    }
    return out;
  });

  const tooltips = $derived.by(() => {
    const out: Record<number, string> = {};
    for (const r of rows ?? []) {
      const m = r.margin_pct == null ? "—" : `${r.margin_pct.toFixed(1)}%`;
      out[r.eci_no] =
        `<div class="font-semibold">${r.eci_no}. ${escape_html(r.name)}</div>` +
        `<div class="text-slate-600">Winner: ${escape_html(r.winner_party_short)}</div>` +
        `<div class="text-slate-500">Margin: ${m}</div>`;
    }
    return out;
  });

  function escape_html(s: string): string {
    return s.replace(/[&<>"']/g, c =>
      c === "&" ? "&amp;" :
      c === "<" ? "&lt;" :
      c === ">" ? "&gt;" :
      c === '"' ? "&quot;" : "&#39;",
    );
  }

  function on_select(sel: { key: string | number }): void {
    const eci_no = Number(sel.key);
    if (Number.isFinite(eci_no)) navigate(url.acByNo(state_code, eci_no));
  }
</script>

{#if !entry}
  <div class="p-3 text-sm text-slate-500">
    No boundary source registered for state <code>{state_code}</code>.
  </div>
{:else}
  <MapChoropleth
    {entry}
    {fills}
    {opacities}
    {tooltips}
    {height}
    highlight_key={highlight_eci_no}
    onSelect={on_select}
  />
{/if}
