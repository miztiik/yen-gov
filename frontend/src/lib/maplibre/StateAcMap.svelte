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
  import { loadAcLgdLookup } from "../view-models/ac-crosswalk";
  import { mirrorLgdKeys } from "../elections/election-map-coloring";

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
    event?: string | null;
    /**
     * PR-B8 colour-by override. When set, these replace the default
     * winner-party fills / margin-based opacities (keyed by `ac_eci_no`),
     * letting the filter rail recolour + dim the SAME choropleth without a
     * bespoke widget. `highlight_eci_no` still wins for the per-AC drill-down.
     */
    fillsOverride?: Record<number, string>;
    opacitiesOverride?: Record<number, number>;
  }
  let {
    state: state_code,
    rows: input_rows,
    highlight_eci_no,
    height = "520px",
    event = null,
    fillsOverride,
    opacitiesOverride,
  }: Props = $props();

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

  // Row B2 (ADR-0049): load the canonical eci_no -> lgd_ac_id map for this
  // state from taxonomy.ac_crosswalk. Covered states get a non-empty map and
  // flip the map's colour join to lgd_ac_id; uncovered states (S03/Assam,
  // U08/J&K) and the pre-load window keep the eci_no/ac_no join. A load error
  // degrades to the legacy join rather than blanking the choropleth.
  let lgd_lookup = $state<Map<number, number> | null>(null);
  $effect(() => {
    const sc = state_code;
    lgd_lookup = null;
    loadAcLgdLookup(sc)
      .then((m) => { if (state_code === sc) lgd_lookup = m; })
      .catch(() => { if (state_code === sc) lgd_lookup = null; });
  });

  // Dual-key the fills/opacities so the choropleth resolves identically
  // whether maplibre matches a polygon on lgd_ac_id (covered) or ac_no
  // (uncovered). `canonical_join` flips in the SAME tick `lgd_lookup`
  // resolves, atomically with the mirrored keys appearing — so there is no
  // frame where the join points at keys the fills map lacks.
  const canonical_join = $derived(lgd_lookup != null && lgd_lookup.size > 0);

  const fills = $derived.by(() => {
    if (fillsOverride) return fillsOverride;
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
    // The override path still honours `highlight_eci_no` so the per-AC
    // drill-down keeps its focus-dimming even when the filter rail supplies
    // base opacities.
    if (opacitiesOverride && highlight_eci_no === undefined) return opacitiesOverride;
    const out: Record<number, number> = {};
    for (const r of rows ?? []) {
      const base =
        opacitiesOverride?.[r.eci_no] ??
        0.35 + (Math.max(0, Math.min(30, r.margin_pct ?? 0)) / 30) * 0.6;
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

  // Row B2 (ADR-0049): mirror the eci_no-keyed fills/opacities under each
  // AC's lgd_ac_id so the choropleth's canonical join resolves to the same
  // colour. Returns the inputs unchanged until `lgd_lookup` resolves.
  const final_fills = $derived(mirrorLgdKeys(fills, lgd_lookup));
  const final_opacities = $derived(mirrorLgdKeys(opacities, lgd_lookup));

  // Row B3 (ADR-0049): the canonical map join is now lgd_ac_id, so the
  // MapChoropleth selection/highlight emit lgd_ac_id keys. Invert the
  // crosswalk lookup so click-to-navigate can recover the citizen-facing
  // eci_no (the URL never carries lgd_ac_id).
  const reverse_lookup = $derived.by(() => {
    if (!lgd_lookup) return null;
    const out = new Map<number, number>();
    for (const [eci, lgd] of lgd_lookup) out.set(lgd, eci);
    return out;
  });

  // The highlighted seat is addressed by eci_no by the parent route; map it
  // to its lgd_ac_id so the canonical-join highlight filter matches. Falls
  // back to the eci_no itself for unmapped states (S03/U08) and the brief
  // pre-lookup window.
  const highlight_lgd = $derived(
    highlight_eci_no == null
      ? undefined
      : (lgd_lookup?.get(highlight_eci_no) ?? highlight_eci_no),
  );

  // Row URL (ADR-0049): the AC link grammar carries a readable name suffix
  // (`/s/<state>/ac/<eci_no>-<name-slug>`). Map the selected eci_no back to
  // its AC name from `rows`; an absent name makes `url.ac` fall back to the
  // bare eci_no (still parse-tolerant).
  const name_by_eci = $derived.by(() => {
    const m = new Map<number, string>();
    for (const r of rows ?? []) m.set(r.eci_no, r.name);
    return m;
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

  function on_select(sel: { key: string | number; properties?: Record<string, unknown> }): void {
    // The canonical map join is lgd_ac_id (Row B3), so `sel.key` is an
    // lgd_ac_id for covered states. Recover the citizen-facing eci_no via
    // the inverted crosswalk; fall back to the feature's `ac_no` label
    // (eci_no-valued for covered states today) during the pre-lookup window,
    // then to the raw key for unmapped states (S03 `ac_no` / U08 `seat_id`
    // are already eci_no/seat values).
    const raw = Number(sel.key);
    const acno = sel.properties?.ac_no;
    const eci_no =
      reverse_lookup?.get(raw)
      ?? (acno != null && Number.isFinite(Number(acno)) ? Number(acno) : raw);
    if (Number.isFinite(eci_no))
      navigate(url.ac(state_code, eci_no, name_by_eci.get(eci_no) ?? "", event));
  }
</script>

{#if !entry}
  <div class="p-3 text-sm text-slate-500">
    No boundary source registered for state <code>{state_code}</code>.
  </div>
{:else}
  <MapChoropleth
    {entry}
    fills={final_fills}
    opacities={final_opacities}
    {tooltips}
    {height}
    canonical_join={canonical_join}
    highlight_key={highlight_lgd}
    onSelect={on_select}
  />
{/if}
