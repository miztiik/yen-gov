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
  import { getDb } from "../sql";
  import { colors } from "../colors/store.svelte";

  interface Props {
    event: string;
    state: string;
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
  let { event, state: state_code, highlight_eci_no, height = "520px" }: Props = $props();

  interface Row {
    eci_no: number;
    name: string;
    winner_party_eci_code: string | null;
    winner_party_short: string;
    margin_pct: number;
  }

  let rows = $state<Row[] | null>(null);
  let error = $state<string | null>(null);

  $effect(() => {
    rows = null;
    error = null;
    const ev = event, st = state_code;
    (async () => {
      try {
        const db = await getDb(ev, st);
        const sql = `
          SELECT c.ac_eci_no AS eci_no, c.name,
                 w.party_eci_code AS winner_party_eci_code,
                 w.party_short    AS winner_party_short,
                 100.0 * (w.votes - r2.votes) / NULLIF(c.votes_polled, 0) AS margin_pct
          FROM constituencies c
          JOIN candidates w  ON w.ac_eci_no  = c.ac_eci_no AND w.is_winner = 1
          LEFT JOIN candidates r2 ON r2.ac_eci_no = c.ac_eci_no AND r2.rank = 2 AND r2.is_nota = 0;
        `;
        const res = db.exec(sql);
        if (!res[0]) { rows = []; return; }
        const cols = res[0].columns;
        rows = res[0].values.map(v => {
          const r: Record<string, unknown> = {};
          cols.forEach((c, i) => (r[c] = v[i]));
          return r as unknown as Row;
        });
      } catch (e) {
        error = String(e);
      }
    })();
  });

  const entry = $derived(STATE_AC[state_code]);

  const fills = $derived.by(() => {
    const out: Record<number, string> = {};
    void colors.overrides;
    for (const r of rows ?? []) {
      out[r.eci_no] = colors.fill(r.winner_party_eci_code, r.winner_party_short);
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
    if (Number.isFinite(eci_no)) location.hash = `#/s/${state_code}/ac/${eci_no}`;
  }
</script>

{#if !entry}
  <div class="p-3 text-sm text-slate-500">
    No boundary source registered for state <code>{state_code}</code>.
  </div>
{:else if error}
  <div class="p-3 text-sm bg-rose-50 border border-rose-200 rounded text-rose-900">
    Failed to load winners: <code>{error}</code>
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
