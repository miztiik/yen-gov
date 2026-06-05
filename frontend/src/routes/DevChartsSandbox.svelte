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

  import HorizontalGroupedBar from "../lib/charts/CategoryBar.svelte";
  import OrderedCategoryBar from "../lib/charts/CategoryBar.svelte";
  import CategoryBarDiverging from "../lib/charts/CategoryBar.svelte";
  import DumbbellRange from "../lib/charts/DumbbellRange.svelte";
  import TimeSeriesLine from "../lib/charts/TimeSeriesLine.svelte";
  import FacetPanelGrid from "../lib/charts/FacetPanelGrid.svelte";
  import { buildHorizontalGroupedBarViewModel, buildFacetPanelGridViewModel } from "../lib/charts/multi-dim-view-models";
  import { buildOrderedCategoryBarViewModel } from "../lib/charts/bar-view-models";
  import { buildDumbbellRangeViewModel, buildTimeSeriesLineViewModel } from "../lib/charts/time-view-models";
  import TileCartogram from "../lib/charts/TileCartogram.svelte";
  import ChartShell from "../lib/charts/ChartShell.svelte";
  import SegmentedControl from "../lib/SegmentedControl.svelte";
  import GeoChoropleth from "../lib/charts/GeoChoropleth.svelte";
  import type { GeoChoroplethRow } from "../lib/charts/geo-choropleth-helpers";
  import Matrix from "../lib/charts/Matrix.svelte";
  import type { MatrixRow } from "../lib/charts/matrix-helpers";
  import {
    feasibleAt,
    intersectWithCatalogue,
    type DataShape,
  } from "../lib/grapher/feasibleAt";
  import type { ChartType } from "../lib/grapher/catalogue";
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

  // F3 reference-line demo (plan section 20.11) — synthetic
  // "national median GSDP per capita" series. In production this is
  // built from a stored derived datapoint on entity_id=IN with its own
  // reserved source_id; here we hand-author the median across the
  // three demo states per year so the TimeSeriesLine renderer
  // exercises its `reference_series` + StatusGlyph branches.
  const tsl_reference_vm = buildTimeSeriesLineViewModel({
    rows: [
      { year: "2018", median: 152000 },
      { year: "2019", median: 164000 },
      { year: "2020", median: 159000 },
      { year: "2021", median: 178000 },
      { year: "2022", median: 200000 },
      { year: "2023", median: 222000 },
    ],
    toPoint: (r: { year: string; median: number }) => ({
      series_id: "IN-median",
      series_label: "National median",
      period_id: r.year,
      period_label: r.year,
      value: r.median,
    }),
    policy: "value_desc",
  });
  const tsl_reference_series = tsl_reference_vm.series[0] ?? null;

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

  // --- fixture 7 - F2b.3 GeoChoropleth{fill} - state-level synthetic ---
  // Synthetic state-level installed-capacity values keyed on State_LGD
  // (the join field carried on datasets/boundaries/in/states/all.topojson).
  // Numbers are illustrative; this page MUST NOT be cited (sandbox
  // doctrine). The fixture covers a diverse mix of states (north,
  // south, east, west, an island UT) so the renderer's island-render
  // path - the F4 frozen-requirement-a smoke contract -
  // gets exercised at runtime in addition to the offline assertion.
  const f2b3_state_rows: GeoChoroplethRow[] = [
    { entity_key: 5,  value: 4.2 },  // Uttarakhand
    { entity_key: 9,  value: 28.7 }, // Uttar Pradesh
    { entity_key: 10, value: 8.3 },  // Bihar
    { entity_key: 22, value: 31.5 }, // Chhattisgarh
    { entity_key: 23, value: 22.4 }, // Madhya Pradesh
    { entity_key: 24, value: 48.7 }, // Gujarat
    { entity_key: 27, value: 50.2 }, // Maharashtra
    { entity_key: 28, value: 26.1 }, // Andhra Pradesh
    { entity_key: 29, value: 33.0 }, // Karnataka
    { entity_key: 32, value: 4.5 },  // Kerala
    { entity_key: 33, value: 34.4 }, // Tamil Nadu
    { entity_key: 35, value: 0.04 }, // Andaman & Nicobar (island; tests the F4 fix path)
    { entity_key: 31, value: 0.02 }, // Lakshadweep    (island; tests the F4 fix path)
  ];

  // --- fixture 8 - F2b.4 Matrix - entity x time heatmap (synthetic) ---
  // Synthetic 5-state x 6-year matrix of an illustrative per-capita
  // indicator. The matrix shares the binnedSequential color scale
  // with GeoChoropleth (parent plan section 14.5 doctrine #5: "Shared
  // ColorScale + Legend primitive serves both <Choropleth> and
  // <Matrix>"). Hover any cell to see the value-tick caret move on
  // the legend bar (Jony C2 + C3 + C5 primitives all wired through).
  // Numbers MUST NOT be cited.
  const f2b4_matrix_rows: MatrixRow[] = (() => {
    const states = ["KA", "TN", "MH", "GJ", "UP"];
    const years = [2019, 2020, 2021, 2022, 2023, 2024];
    const out: MatrixRow[] = [];
    // Synthetic but plausible-looking growth/decline pattern per state.
    const seed: Record<string, number[]> = {
      KA: [42, 45, 41, 48, 52, 56],
      TN: [50, 51, 48, 53, 58, 61],
      MH: [55, 58, 52, 60, 65, 68],
      GJ: [60, 62, 56, 64, 70, 74],
      UP: [25, 26, 22, 28, 31, 34],
    };
    for (const s of states) {
      for (let i = 0; i < years.length; i += 1) {
        out.push({ entity_id: s, time: years[i], value: seed[s][i] });
      }
    }
    // Inject one missing cell to exercise the hatch fall-through.
    out.push({ entity_id: "MH", time: 2025, value: null });
    return out;
  })();
  const f2b4_state_label = (id: string): string => {
    const map: Record<string, string> = {
      KA: "Karnataka",
      TN: "Tamil Nadu",
      MH: "Maharashtra",
      GJ: "Gujarat",
      UP: "Uttar Pradesh",
    };
    return map[id] ?? id;
  };
  const f2b4_time_label = (t: string): string => t;

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

  // ─── U4 — chart-type switcher seam (in-memory; NO URL persistence) ─
  // Demonstrates the SegmentedControl wired into ChartShell's toolbar
  // slot. The switcher offers the intersection of `feasibleAt(...)`
  // and an authored `chart_types[]`. Active type is in-memory ONLY
  // (plan section 16.3a + 20.8): NEVER persisted to the URL, NEVER
  // written to history. Reload re-opens on `chart_types[0]`.
  //
  // For the smoke this card uses the "one measure over geo, many
  // slices" matrix row (which intersects to four feasible types) and
  // the authored catalogue list ["choropleth", "matrix", "line",
  // "ranked"] so all four segments render. Per plan section 16.3a,
  // when the intersection has exactly one member the switcher renders
  // NO control (a one-option control failed the deletion test); that
  // single-member case is illustrated by the second card below.
  const _u4_shape: DataShape = "one-measure-over-geo-many-slices";
  const _u4_catalogue: ChartType[] = [
    "choropleth",
    "matrix",
    "line",
    "ranked",
  ];
  const u4_feasible = $derived(
    feasibleAt({
      dataShape: _u4_shape,
      grain: "state",
      geometryAvailable: true,
      hasFacet: false,
      hasTimeAxis: true,
    }),
  );
  const u4_offered = $derived(
    intersectWithCatalogue(u4_feasible, _u4_catalogue),
  );
  let u4_current = $state<ChartType>("choropleth");
  // Glyph map - uses icons present in frontend/public/icons/ today.
  // Unrecognised ids fall back to the text label (the chart-index doc
  // §1 Thumb column carries the icons that ship in U3 follow-ups /
  // F2b). Plain `bar-chart` + `trending-up` are already shipped.
  const _u4_glyphs: Partial<Record<ChartType, string>> = {
    ranked: "bar-chart",
    line: "trending-up",
  };
  const _u4_labels: Record<ChartType, string> = {
    choropleth: "Map",
    "choropleth-symbol": "Symbol map",
    matrix: "Grid",
    ranked: "Bars",
    stacked: "Stacked",
    diverging: "Diverging",
    line: "Line",
    scatter: "Scatter",
    "dumbbell-dot": "Dumbbell",
    "dumbbell-arrow": "Dumbbell (arrow)",
    treemap: "Treemap",
    "circle-pack": "Bubbles",
  };
  const u4_options = $derived(
    u4_offered.map((t) => ({
      value: t,
      label: _u4_labels[t],
      glyph: _u4_glyphs[t],
    })),
  );

  // Second card for the single-feasible-encoding case. Authored
  // chart_types: ["scatter"] intersected with "one-measure-over-geo-
  // one-slice" -> empty -> falls back to feasible (["choropleth",
  // "ranked"]); add an authored choropleth-only catalogue to render
  // a one-item switcher, which the UI then suppresses entirely.
  const _u4_solo_catalogue: ChartType[] = ["choropleth"];
  const u4_solo_offered = $derived(
    intersectWithCatalogue(
      feasibleAt({
        dataShape: "one-measure-over-geo-one-slice",
        grain: "state",
        geometryAvailable: true,
        hasFacet: false,
        hasTimeAxis: false,
      }),
      _u4_solo_catalogue,
    ),
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
      <br />Now rendered through <code>CategoryBar mode="stacked"</code>
      (F2a.3+F2a.4 consolidation; the orphan
      <code>HorizontalGroupedBar.svelte</code> retired).
    </p>
    <HorizontalGroupedBar
      mode="stacked"
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
      <br />Now rendered through <code>CategoryBar mode="ranked"</code>
      (F2a.1+F2a.2 consolidation; the orphan
      <code>OrderedCategoryBar.svelte</code> retired).
    </p>
    <OrderedCategoryBar
      mode="ranked"
      view_model={ocb_vm}
      chart_title="Electricity access by wealth quintile (synthetic)"
      chart_subtitle="Axis-ordered; no value-sort permitted."
      format_value={fmtPct}
    />
  </section>

  <section class="space-y-3" data-sandbox-section="diverging-bar">
    <h2 class="text-lg font-semibold">CategoryBar mode="diverging"</h2>
    <p class="text-sm text-slate-600">
      Single-entity, single-period 100%-stacked composition bar.
      Synthetic fuel-mix model so reviewers can see segments + legend +
      caption render through <code>CategoryBar mode="diverging"</code>
      (F2a.5.1; lifted byte-identical from the now-retired
      <code>lib/CompositionBar.svelte</code> body). F2a.5.2 retired
      the standalone renderer; the StateOverview production mount now
      uses this primitive.
    </p>
    <CategoryBarDiverging
      mode="diverging"
      view_model={{
        schema_version: "1.0",
        label: "Tamil Nadu fuel mix (synthetic)",
        subtitle: "FY 2024-25 installed capacity",
        total_value: 41000,
        total_unit: "MW",
        dimension: "fuel_type",
        segments: [
          { id: "coal", label: "Coal", value: 17000, fill: "#475569", swatch_role: "fuel-type", is_tail: false },
          { id: "renewable", label: "Renewable", value: 14500, fill: "#16a34a", swatch_role: "fuel-type", is_tail: false },
          { id: "gas", label: "Gas", value: 5200, fill: "#0284c7", swatch_role: "fuel-type", is_tail: false },
          { id: "hydro", label: "Hydro", value: 2500, fill: "#7c3aed", swatch_role: "fuel-type", is_tail: false },
          { id: "nuclear", label: "Nuclear", value: 1800, fill: "#dc2626", swatch_role: "fuel-type", is_tail: true },
        ],
        honesty_banners: [],
        caption_fptp: null,
      }}
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

  <section class="space-y-3" data-sandbox-section="tsl-reference">
    <h2 class="text-lg font-semibold">TimeSeriesLine — with national reference (F3)</h2>
    <p class="text-sm text-slate-600">
      Same three state series, plus a thin grey dashed "national
      median" reference line and a direction-coloured
      <code>StatusGlyph</code> at each state's latest point. Under
      <code>higher_is_better</code>: Karnataka (above) and Tamil Nadu
      (above) get a green up-triangle; Bihar (below) gets a red
      down-triangle. Per plan section 20.11.
    </p>
    <TimeSeriesLine
      view_model={tsl_vm}
      reference_series={tsl_reference_series}
      indicator_direction="higher_is_better"
      chart_title="GSDP per capita vs national median (synthetic)"
      chart_subtitle="Grey dashed = median across the three demo states; glyphs at latest point."
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

  <section class="space-y-3" data-sandbox-section="u4-switcher">
    <h2 class="text-lg font-semibold">U4 - chart-type switcher seam</h2>
    <p class="text-sm text-slate-600">
      The seam plan section 16.3a + 21.9 commission. The picker is
      <code>feasibleAt(dataShape, grain, geometryAvailable, ...)</code>
      intersected with the authored
      <code>chart_types[]</code>, rendered as a
      <code>SegmentedControl</code> in <code>ChartShell</code>'s
      top-right toolbar slot. Swapping is <strong>in-memory only</strong>
      (NO URL writes); reload re-opens on <code>chart_types[0]</code>.
      Selected: <strong data-testid="u4-current-chart-type">{u4_current}</strong>.
      No new renderer ships in U4 (that is F2b); the chart body below
      shows the active type as text to prove the seam wires through.
    </p>
    <ChartShell
      title="U4 switcher demo - one measure over geo, many slices"
      subtitle="feasibleAt() intersect chart_types[] = [choropleth, matrix, line, ranked]"
    >
      {#snippet toolbar()}
        <SegmentedControl
          options={u4_options}
          value={u4_current}
          onChange={(t) => (u4_current = t)}
          testid="u4-chart-switcher"
        />
      {/snippet}
      <div
        class="flex h-40 items-center justify-center rounded border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500"
        data-testid="u4-chart-body"
      >
        Renderer for <code class="font-mono">{u4_current}</code> would mount here.
      </div>
    </ChartShell>
    <p class="text-xs text-slate-500">
      Single-feasible case: when the intersect has exactly one member
      (here <code>chart_types: ["choropleth"]</code> at one-time-slice
      grain -&gt; <code>[{u4_solo_offered.join(", ")}]</code>), the
      caller MUST render <strong>no</strong> switcher (a one-option
      control is chrome that failed the deletion test, plan section
      16.3a). The card below proves that path:
    </p>
    <ChartShell
      title="U4 single-feasible card (no switcher rendered)"
      subtitle="One-measure-over-geo / one slice - only `choropleth` is feasible."
    >
      {#snippet toolbar()}
        {#if u4_solo_offered.length > 1}
          <SegmentedControl
            options={u4_solo_offered.map((t) => ({
              value: t,
              label: _u4_labels[t],
              glyph: _u4_glyphs[t],
            }))}
            value={u4_solo_offered[0]}
            onChange={() => {}}
            testid="u4-solo-switcher"
          />
        {/if}
      {/snippet}
      <div
        class="flex h-32 items-center justify-center rounded border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500"
        data-testid="u4-solo-body"
      >
        Single-feasible body - no switcher present (deletion test passed).
      </div>
    </ChartShell>
  </section>

  <!-- F2b.3 GeoChoropleth{fill} demo (parent plan section 14.5 + 15.1
       renderer #1; consumes the F4 island-render-smoke contract). The
       fixture deliberately includes Andaman & Nicobar (lgd 35) and
       Lakshadweep (lgd 31) so a reviewer can SEE the islands draw -
       the runtime evidence next to the F4 offline smoke. -->
  <section class="space-y-3" data-testid="f2b3-section">
    <h2 class="text-lg font-semibold">F2b.3 - GeoChoropleth{`{`}fill{`}`} (d3-geo SVG static map)</h2>
    <p class="text-sm text-slate-600">
      Renderer #1 from <a class="underline" href="../docs/reference/chart-index.md">chart-index.md section 1</a>
      consumed by parent plan section 14.5's split-by-job map engine
      decision: d3-geo SVG for ALL static welfare choropleths
      (maplibre-gl fenced to election AC pan/zoom). Mounts the F2b.2
      C2 / C3 / C5 primitives (ChoroplethLegend with value-tick on
      hover; MapTooltip with region + value + swatch; SourceLine).
      Renders the F4-shipped <code>datasets/boundaries/in/states/all.topojson</code>
      (785 districts excluded; 36 states+UTs included). Hover any
      state to see the value-tick caret slide along the legend bar
      (Jony's bank-branch chart observation; parent section 14.3 C2).
    </p>
    <p class="text-xs text-slate-500">
      Fixture data is illustrative; numbers MUST NOT be cited. The
      island UTs (Andaman & Nicobar lgd 35, Lakshadweep lgd 31) are
      seeded with values to give the F4 island-render-smoke a runtime
      sibling - both islands draw, both are interactive, both fill
      the legend value-tick when hovered.
    </p>
    <GeoChoropleth
      topojson_path="/boundaries/in/states/all.topojson"
      feature_key="State_LGD"
      rows={f2b3_state_rows}
      direction="higher_is_better"
      format_tick=".2s"
      format_value={(v) => fmtGw(v)}
      title="Installed capacity by state (synthetic)"
      source_owner="Synthetic sandbox fixture"
      source_vintage="2026-06-06 (illustrative)"
      width={640}
      height={520}
    />
  </section>

  <!-- F2b.4 Matrix (entity x time heatmap) demo (parent plan section
       15.1 row 3; shares ColorScale + Legend with GeoChoropleth via
       color-scale.ts per parent section 14.5 doctrine #5). One cell
       is deliberately set to null to exercise the hatch fall-through. -->
  <section class="space-y-3" data-testid="f2b4-section">
    <h2 class="text-lg font-semibold">F2b.4 - Matrix (entity x time heatmap)</h2>
    <p class="text-sm text-slate-600">
      Renderer #3 from <a class="underline" href="../docs/reference/chart-index.md">chart-index.md section 1</a>.
      Pivots <code>(entity, time, value)</code> rows into a 2D grid;
      shares the binned color scale with GeoChoropleth. Hover any
      cell to see the ChoroplethLegend value-tick caret move along
      the bar (Jony's bank-branch chart observation; parent 14.3 C2).
      The MH 2025 cell is deliberately empty to exercise the C4
      diagonal-stripe hatch fall-through (same visual idiom
      GeoChoropleth uses for no-data regions).
    </p>
    <p class="text-xs text-slate-500">
      Fixture data is illustrative; numbers MUST NOT be cited. The
      shared ColorScale is the strangler-fig contract: F2b.4 Matrix
      and F2b.3 GeoChoropleth paint the same domain in the same
      palette, so a citizen can read across the two renderers without
      a perceptual reset.
    </p>
    <Matrix
      rows={f2b4_matrix_rows}
      entity_label={f2b4_state_label}
      time_label={f2b4_time_label}
      direction="higher_is_better"
      bins={5}
      format_tick=".2s"
      title="Synthetic per-capita indicator across states (illustrative)"
      source_owner="Synthetic sandbox fixture"
      source_vintage="2026-06-06 (illustrative)"
      cell_height={26}
      cell_min_width={48}
      label_width={140}
      width={640}
    />
  </section>
</section>
