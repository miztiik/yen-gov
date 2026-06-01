<script lang="ts">
  // Phase 6 (charting modernisation plan) — internal sandbox surface.
  //
  // Mounts every Phase 1.6 / 3.5 generic renderer side-by-side against
  // fixture data so a reviewer can:
  //
  //   1. See what each renderer looks like in isolation.
  //   2. Verify the renderer ↔ builder contract is intact at runtime
  //      (a build that compiles but blows up on first render shows here).
  //   3. Try the renderers without needing a citizen route to adopt
  //      them first. The four "orphan" renderers (HorizontalGroupedBar,
  //      OrderedCategoryBar, DumbbellRange, FacetPanelGrid) get their
  //      first runtime exercise here.
  //
  // Doctrine:
  //   - Dev-only route at /dev/charts-sandbox (mirrors
  //     /dev/duckdb-harness — not citizen-discoverable; not linked
  //     from the left rail).
  //   - Fixture data is realistic-shaped but synthetic. Numbers are
  //     illustrative; this page MUST NOT be cited.
  //   - No new library dependency. The plan's Phase 6 specifically
  //     considered Plotly / ECharts / Observable Plot; we chose
  //     internal sandbox per CLAUDE.md §0a (Engineering craft = Fowler)
  //     because our existing renderers cover every named gap.
  //
  // CLAUDE.md §0: no aria/role; visible affordances only.

  import HorizontalGroupedBar from "../lib/charts/HorizontalGroupedBar.svelte";
  import OrderedCategoryBar from "../lib/charts/OrderedCategoryBar.svelte";
  import DumbbellRange from "../lib/charts/DumbbellRange.svelte";
  import TimeSeriesLine from "../lib/charts/TimeSeriesLine.svelte";
  import FacetPanelGrid from "../lib/charts/FacetPanelGrid.svelte";
  import { buildHorizontalGroupedBarViewModel, buildFacetPanelGridViewModel } from "../lib/charts/multi-dim-view-models";
  import { buildOrderedCategoryBarViewModel } from "../lib/charts/bar-view-models";
  import { buildDumbbellRangeViewModel, buildTimeSeriesLineViewModel } from "../lib/charts/time-view-models";
  import TileCartogram from "../lib/charts/TileCartogram.svelte";
  import ChartShell from "../lib/charts/ChartShell.svelte";
  import {
    buildTileRows,
    type TileLayoutRow,
    type TileWinnerInput,
  } from "../lib/view-models/election-tile-layout";

  // ─── fixture 1 — installed capacity by fuel, 4 states × 3 fuels ───
  type CapacityRow = { state_id: string; state_label: string; fuel_id: string; fuel_label: string; capacity_gw: number | null };
  const capacity_rows: CapacityRow[] = [
    { state_id: "TN", state_label: "Tamil Nadu", fuel_id: "coal", fuel_label: "Coal", capacity_gw: 12.7 },
    { state_id: "TN", state_label: "Tamil Nadu", fuel_id: "hydro", fuel_label: "Hydro", capacity_gw: 2.3 },
    { state_id: "TN", state_label: "Tamil Nadu", fuel_id: "renewable", fuel_label: "Renewable", capacity_gw: 19.4 },
    { state_id: "GJ", state_label: "Gujarat", fuel_id: "coal", fuel_label: "Coal", capacity_gw: 24.1 },
    { state_id: "GJ", state_label: "Gujarat", fuel_id: "hydro", fuel_label: "Hydro", capacity_gw: 0.8 },
    { state_id: "GJ", state_label: "Gujarat", fuel_id: "renewable", fuel_label: "Renewable", capacity_gw: 23.8 },
    { state_id: "KA", state_label: "Karnataka", fuel_id: "coal", fuel_label: "Coal", capacity_gw: 11.4 },
    { state_id: "KA", state_label: "Karnataka", fuel_id: "hydro", fuel_label: "Hydro", capacity_gw: 4.1 },
    { state_id: "KA", state_label: "Karnataka", fuel_id: "renewable", fuel_label: "Renewable", capacity_gw: 17.5 },
    { state_id: "RJ", state_label: "Rajasthan", fuel_id: "coal", fuel_label: "Coal", capacity_gw: 17.3 },
    { state_id: "RJ", state_label: "Rajasthan", fuel_id: "hydro", fuel_label: "Hydro", capacity_gw: 1.9 },
    { state_id: "RJ", state_label: "Rajasthan", fuel_id: "renewable", fuel_label: "Renewable", capacity_gw: null },
  ];

  // Group cells by state for the HGB / FPG builders.
  const cap_by_state = new Map<string, CapacityRow[]>();
  for (const r of capacity_rows) {
    if (!cap_by_state.has(r.state_id)) cap_by_state.set(r.state_id, []);
    cap_by_state.get(r.state_id)!.push(r);
  }
  const grouped_rows = Array.from(cap_by_state.entries()).map(([state_id, rows]) => ({
    state_id,
    state_label: rows[0].state_label,
    rows,
  }));

  const hgb_vm = buildHorizontalGroupedBarViewModel({
    rows: grouped_rows,
    toRow: (s) => ({
      id: s.state_id,
      label: s.state_label,
      pinned_rank: s.state_id === "TN" ? 1 : null,
      cells: s.rows.map((r) => ({
        group_id: r.fuel_id,
        group_label: r.fuel_label,
        value: r.capacity_gw,
        colour: r.fuel_id === "coal" ? "#475569" : r.fuel_id === "hydro" ? "#0284c7" : "#16a34a",
      })),
    }),
    policy: "value_desc",
    aggregator: { kind: "sum" },
    group_order: ["coal", "hydro", "renewable"],
  });

  // ─── fixture 2 — wealth-quintile electricity access (OCB) ───────
  type QuintileRow = { quintile_id: string; quintile_label: string; quintile_order: number; pct: number };
  const quintile_rows: QuintileRow[] = [
    { quintile_id: "q1", quintile_label: "Poorest", quintile_order: 1, pct: 78.4 },
    { quintile_id: "q2", quintile_label: "Poor", quintile_order: 2, pct: 89.1 },
    { quintile_id: "q3", quintile_label: "Middle", quintile_order: 3, pct: 96.3 },
    { quintile_id: "q4", quintile_label: "Richer", quintile_order: 4, pct: 98.7 },
    { quintile_id: "q5", quintile_label: "Richest", quintile_order: 5, pct: 99.6 },
  ];

  const ocb_vm = buildOrderedCategoryBarViewModel({
    rows: quintile_rows,
    toItem: (r) => ({ id: r.quintile_id, label: r.quintile_label, value: r.pct, order: r.quintile_order }),
    policy: "axis_order",
  });

  // ─── fixture 3 — literacy rate 2011 → 2021 (DR) ─────────────────
  type LiteracyRow = { state_id: string; state_label: string; v_2011: number | null; v_2021: number | null };
  const literacy_rows: LiteracyRow[] = [
    { state_id: "KL", state_label: "Kerala",      v_2011: 94.0, v_2021: 96.2 },
    { state_id: "TN", state_label: "Tamil Nadu",  v_2011: 80.1, v_2021: 86.8 },
    { state_id: "MH", state_label: "Maharashtra", v_2011: 82.3, v_2021: 88.5 },
    { state_id: "UP", state_label: "Uttar Pradesh", v_2011: 67.7, v_2021: 76.6 },
    { state_id: "BR", state_label: "Bihar",       v_2011: 61.8, v_2021: null },
  ];

  const dr_vm = buildDumbbellRangeViewModel({
    rows: literacy_rows,
    toEndpoints: (r) => ({
      id: r.state_id,
      label: r.state_label,
      pinned_rank: r.state_id === "TN" ? 1 : null,
      earliest: { period_label: "2011", value: r.v_2011 },
      latest: { period_label: "2021", value: r.v_2021 },
    }),
    policy: "latest_change",
  });

  // ─── fixture 4 — GSDP per capita over time (TSL) ────────────────
  type GsdpRow = { state_id: string; state_label: string; year: string; gsdp_per_cap: number | null };
  const gsdp_rows: GsdpRow[] = [
    { state_id: "TN", state_label: "Tamil Nadu", year: "2018", gsdp_per_cap: 178000 },
    { state_id: "TN", state_label: "Tamil Nadu", year: "2019", gsdp_per_cap: 193000 },
    { state_id: "TN", state_label: "Tamil Nadu", year: "2020", gsdp_per_cap: 186000 },
    { state_id: "TN", state_label: "Tamil Nadu", year: "2021", gsdp_per_cap: 218000 },
    { state_id: "TN", state_label: "Tamil Nadu", year: "2022", gsdp_per_cap: 241000 },
    { state_id: "TN", state_label: "Tamil Nadu", year: "2023", gsdp_per_cap: 263000 },
    { state_id: "KA", state_label: "Karnataka",  year: "2018", gsdp_per_cap: 198000 },
    { state_id: "KA", state_label: "Karnataka",  year: "2019", gsdp_per_cap: 214000 },
    { state_id: "KA", state_label: "Karnataka",  year: "2020", gsdp_per_cap: 205000 },
    { state_id: "KA", state_label: "Karnataka",  year: "2021", gsdp_per_cap: 245000 },
    { state_id: "KA", state_label: "Karnataka",  year: "2022", gsdp_per_cap: 271000 },
    { state_id: "KA", state_label: "Karnataka",  year: "2023", gsdp_per_cap: 298000 },
    { state_id: "BR", state_label: "Bihar",       year: "2018", gsdp_per_cap: 43000 },
    { state_id: "BR", state_label: "Bihar",       year: "2019", gsdp_per_cap: 47000 },
    { state_id: "BR", state_label: "Bihar",       year: "2020", gsdp_per_cap: null },
    { state_id: "BR", state_label: "Bihar",       year: "2021", gsdp_per_cap: 54000 },
    { state_id: "BR", state_label: "Bihar",       year: "2022", gsdp_per_cap: 59000 },
    { state_id: "BR", state_label: "Bihar",       year: "2023", gsdp_per_cap: 63000 },
  ];

  const tsl_vm = buildTimeSeriesLineViewModel({
    rows: gsdp_rows,
    toPoint: (r) => ({
      series_id: r.state_id,
      series_label: r.state_label,
      series_pinned_rank: r.state_id === "TN" ? 1 : null,
      series_colour: r.state_id === "TN" ? "#dc2626" : r.state_id === "KA" ? "#0284c7" : "#16a34a",
      period_id: r.year,
      period_label: r.year,
      value: r.gsdp_per_cap,
    }),
    policy: "value_desc",
    suppress_breaks: false,
  });

  // ─── fixture 5 — facet panel grid (capacity per fuel × state) ───
  const fpg_vm = buildFacetPanelGridViewModel({
    rows: capacity_rows,
    toPanelRow: (r) => ({
      panel_id: r.fuel_id,
      panel_label: r.fuel_label,
      id: r.state_id,
      label: r.state_label,
      pinned_rank: r.state_id === "TN" ? 1 : null,
      value: r.capacity_gw,
    }),
    row_policy: "value_desc",
    panel_policy: "value_desc",
    shared_scale: true,
  });

  // Pretty number formatters.
  const fmtGw = (v: number) => `${v.toFixed(1)} GW`;
  const fmtPct = (v: number) => `${v.toFixed(1)}%`;
  const fmtInr = (v: number) => `₹${(v / 1000).toFixed(0)}k`;

  // ─── fixture 6 — TileCartogram (equal-area hex; synthetic 5×5 patch) ───
  // A small synthetic AC layout + winners so the renderer↔builder contract
  // (election-tile-layout.ts -> TileCartogram.svelte) gets a runtime exercise.
  // Numbers/parties illustrative only.
  const _tc_parties: { key: string; short: string }[] = [
    { key: "BJP", short: "BJP" },
    { key: "INC", short: "INC" },
    { key: "NCP", short: "NCP" },
    { key: "SHS", short: "SHS" },
  ];
  const tc_tiles: TileLayoutRow[] = [];
  const tc_winners: TileWinnerInput[] = [];
  {
    let n = 1;
    for (let r = 0; r < 5; r++) {
      for (let q = 0; q < 5; q++) {
        const unit_id = `IN-S13-AC-2008-${n}`;
        tc_tiles.push({
          layout_kind: "ac",
          scope: "S13",
          delim_year: 2008,
          unit_id,
          eci_no: n,
          q,
          r,
          label: `AC ${n}`,
          source_id: "synthetic",
          derivation_method: "centroid-hexbin",
        });
        // leave a couple of tiles winner-less to show the "pending" neutral style
        if (n % 7 !== 0) {
          const p = _tc_parties[(q + r) % _tc_parties.length];
          tc_winners.push({
            unit_id,
            party_key: p.key,
            party_short: p.short,
            margin_pct: ((q * 7 + r * 11) % 30) + 1,
          });
        }
        n++;
      }
    }
  }
  let tc_selected = $state<string | null>(null);
  const tc_rows = $derived(buildTileRows(tc_tiles, tc_winners, { selected_unit_id: tc_selected }));
  const tc_legend = $derived(
    _tc_parties.map((p) => ({
      label: p.short,
      color: tc_rows.find((r) => r.tooltip_html.includes(`Winner: ${p.short}`))?.fill ?? "#94a3b8",
    })),
  );
</script>

<section class="mx-auto max-w-5xl space-y-10 p-6 text-slate-800">
  <header class="space-y-2">
    <p class="text-xs uppercase tracking-wider text-slate-500">Dev-only sandbox</p>
    <h1 class="text-2xl font-semibold">Charts sandbox</h1>
    <p class="text-sm text-slate-600">
      Phase 6 of the charting modernisation plan. Every Phase 1.6 / 3.5
      generic renderer is mounted here with synthetic fixture data so
      reviewers can sanity-check the renderer ↔ builder contract at
      runtime. <strong>Numbers on this page are illustrative only — do
      not cite.</strong> This route is not linked from the citizen UI
      and ships behind the same /dev/* convention as
      <code class="text-xs">/dev/duckdb-harness</code>.
    </p>
  </header>

  <section class="space-y-3" data-sandbox-section="hgb">
    <h2 class="text-lg font-semibold">HorizontalGroupedBar</h2>
    <p class="text-sm text-slate-600">
      One row per state, three grouped bars per row (Coal / Hydro /
      Renewable). Pinned row = Tamil Nadu (amber accent). Sort policy
      <code>value_desc</code> aggregated by sum.
    </p>
    <HorizontalGroupedBar
      view_model={hgb_vm}
      chart_title="Installed capacity by fuel (synthetic)"
      chart_subtitle="One bar group per fuel; row = state."
      format_value={fmtGw}
    />
  </section>

  <section class="space-y-3" data-sandbox-section="ocb">
    <h2 class="text-lg font-semibold">OrderedCategoryBar</h2>
    <p class="text-sm text-slate-600">
      Categories rendered in axis order (poorest → richest). The
      renderer never re-sorts; the builder enforces
      <code>axis_order</code> only.
    </p>
    <OrderedCategoryBar
      view_model={ocb_vm}
      chart_title="Electricity access by wealth quintile (synthetic)"
      chart_subtitle="Axis-ordered; no value-sort permitted."
      format_value={fmtPct}
    />
  </section>

  <section class="space-y-3" data-sandbox-section="dr">
    <h2 class="text-lg font-semibold">DumbbellRange</h2>
    <p class="text-sm text-slate-600">
      Endpoints 2011 → 2021. Up = green, down = red, flat = slate,
      missing = open ring or hatch. Bihar's 2021 endpoint is null on
      purpose to exercise the missing-endpoint code path.
    </p>
    <DumbbellRange
      view_model={dr_vm}
      chart_title="Literacy rate, 2011 → 2021 (synthetic)"
      chart_subtitle="Sort policy = latest_change (|Δ|)."
      format_value={fmtPct}
    />
  </section>

  <section class="space-y-3" data-sandbox-section="tsl">
    <h2 class="text-lg font-semibold">TimeSeriesLine</h2>
    <p class="text-sm text-slate-600">
      Three series, six years each. Bihar's 2020 point is null to test
      the dashed-bridge path (<code>suppress_breaks: false</code>).
      Pinned series = Tamil Nadu (thicker stroke).
    </p>
    <TimeSeriesLine
      view_model={tsl_vm}
      chart_title="GSDP per capita over time (synthetic)"
      chart_subtitle="Pinned series is rendered thicker."
      format_value={fmtInr}
    />
  </section>

  <section class="space-y-3" data-sandbox-section="fpg">
    <h2 class="text-lg font-semibold">FacetPanelGrid</h2>
    <p class="text-sm text-slate-600">
      One panel per fuel; rows = states. <code>shared_scale: true</code>
      so the citizen can compare panel sizes meaningfully. Renderer
      highlights the row with the panel max.
    </p>
    <FacetPanelGrid
      view_model={fpg_vm}
      chart_title="Capacity per fuel × state (synthetic, shared scale)"
      chart_subtitle="Panels share a global max."
      format_value={fmtGw}
    />
  </section>

  <section class="space-y-3" data-sandbox-section="tile-cartogram">
    <h2 class="text-lg font-semibold">TileCartogram</h2>
    <p class="text-sm text-slate-600">
      Equal-area hex cartogram — one hexagon per constituency, sized
      equally so dense urban seats are as visible as large rural ones.
      Synthetic 5×5 AC patch; fill = winning party, opacity = margin.
      Every 7th tile has no winner to exercise the neutral
      <em>results-pending</em> style. Click a hex to toggle selection.
      {#if tc_selected}<strong> Selected: {tc_selected}</strong>{/if}
    </p>
    <ChartShell
      title="Synthetic AC tile cartogram"
      subtitle="Illustrative only — not a real result."
    >
      <TileCartogram
        tiles={tc_rows}
        height="360px"
        legend={tc_legend}
        onSelect={(id) => (tc_selected = tc_selected === id ? null : id)}
      />
    </ChartShell>
  </section>
</section>
