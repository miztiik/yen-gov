<script lang="ts" module>
  // Module-scope pure helpers for the inline sparkline's national-
  // reference overlay (G31; parent plan section 20.11). Mounted by
  // the instance script below; tested in IndicatorCard.test.ts.
  //
  // Why module-scope: vitest is node-env (Skeleton + IndicatorJump
  // precedent; no `@testing-library/svelte`). The geometry maths +
  // verdict derivation are the testable surface; the SVG template
  // wiring is exercised by the §13 in-browser smoke on /s/<state>.
  //
  // Doctrine: the four fence rules (ref_rows >= 2, direction != neutral,
  // overlap >= 2, home period exists in ref) are enforced INLINE in the
  // template via `{#if ...}` guards, NOT in the helpers — the helpers
  // are total functions returning safe defaults so a renderer that
  // forgets one guard still degrades gracefully (empty path / "missing"
  // verdict) instead of throwing.

  import type { NationalReferenceRow } from "./canonical/indicator-from-canonical";
  import type { Direction } from "./indicators";
  import {
    computeStatusVerdict,
    type StatusVerdict,
  } from "./charts/status-glyph/helpers";

  /** Sparkline viewBox + padding geometry, mirrored from the instance
   *  script so the reference path projects to identical (x, y) as the
   *  state path. Kept as a shape (not 4 positional args) so the test
   *  can construct one without re-reading the instance constants. */
  export interface SparklineGeom {
    readonly W: number;
    readonly H: number;
    readonly PAD_X: number;
    readonly PAD_Y: number;
  }

  /** State series shape after `seriesForEntity()` — IndicatorRow.time is
   *  the string form (`"2023"`, `"2023-04-01"`), value is non-null. */
  export interface StatePoint {
    readonly time: string;
    readonly value: number;
  }

  /** Build a `period_label -> value` map from pop-weighted reference
   *  rows. Filters out null values (a publisher gap in the reference is
   *  the same as no reference at that period — the polyline gets a
   *  segment break, the glyph reports "missing"). Keys are stringified
   *  from the BIGINT `time` so they line up with the state series'
   *  string-shaped `time`.
   *
   *  Returns an empty map for `undefined` (descriptor opted out / fetch
   *  failed / sibling file absent) and for an empty array — both
   *  collapse to "no reference attached". */
  export function nationalReferenceMap(
    rows: readonly NationalReferenceRow[] | undefined,
  ): ReadonlyMap<string, number> {
    const m = new Map<string, number>();
    if (!rows) return m;
    for (const r of rows) {
      if (r.value === null || r.value === undefined) continue;
      if (Number.isNaN(r.value)) continue;
      m.set(String(r.time), r.value);
    }
    return m;
  }

  /** Merged `y_max` for a sparkline that overlays a reference line on
   *  the state series. Falls back to the state-only `y_max` (max abs
   *  value across the state series, clamped to >=1) when the reference
   *  map is empty. When non-empty, ONLY reference values at periods
   *  present in the state series contribute — a ref period outside the
   *  visible state range must not stretch the Y axis. */
  export function mergedYMax(
    state_series: readonly StatePoint[],
    ref_map: ReadonlyMap<string, number>,
  ): number {
    let m = 0;
    for (const p of state_series) {
      const v = Math.abs(p.value);
      if (v > m) m = v;
    }
    if (ref_map.size > 0) {
      for (const p of state_series) {
        const ref = ref_map.get(p.time);
        if (ref === undefined) continue;
        const v = Math.abs(ref);
        if (v > m) m = v;
      }
    }
    return m || 1;
  }

  /** Project the reference values at state-series periods into a
   *  multi-segment SVG path. Same INDEX-driven x projection as the
   *  state sparkline (so the two lines visually align period-by-
   *  period). Gaps (state period with no matching reference value)
   *  split the path into `M ... L ... L ... M ... L ...` segments so
   *  the renderer never draws a connector across a missing period.
   *
   *  Returns "" when the state series has fewer than 2 points OR the
   *  reference produces fewer than 2 plotted points (a single point
   *  would render as an invisible zero-length path; better to suppress
   *  the second `<path>` entirely). */
  export function referenceSparklinePath(
    state_series: readonly StatePoint[],
    ref_map: ReadonlyMap<string, number>,
    y_max: number,
    geom: SparklineGeom,
  ): string {
    if (state_series.length < 2) return "";
    if (ref_map.size === 0) return "";
    const { W, H, PAD_X, PAD_Y } = geom;
    const span = state_series.length - 1;
    const inner_w = W - 2 * PAD_X;
    const inner_h = H - 2 * PAD_Y;
    const parts: string[] = [];
    let started = false;
    let plotted = 0;
    for (let i = 0; i < state_series.length; i++) {
      const ref = ref_map.get(state_series[i].time);
      if (ref === undefined) {
        // Gap — close the current segment so the next plotted point
        // starts a fresh `M`.
        started = false;
        continue;
      }
      const x = PAD_X + (i / span) * inner_w;
      const y = PAD_Y + inner_h - (Math.abs(ref) / y_max) * inner_h;
      parts.push(`${started ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`);
      started = true;
      plotted += 1;
    }
    if (plotted < 2) return "";
    return parts.join(" ");
  }

  /** Verdict for the StatusGlyph at the state's latest period. Returns
   *  `"missing"` when the home value is null, the reference map has no
   *  entry at the home period, or the direction is `"neutral"` — the
   *  template's `{#if verdict !== "missing"}` guard then suppresses
   *  the glyph (matching the `StatusGlyph.svelte` no-op render for
   *  `"missing"`). */
  export function referenceGlyphVerdict(
    home_latest: { time: string; value: number } | null,
    ref_map: ReadonlyMap<string, number>,
    direction: Direction,
  ): StatusVerdict {
    if (!home_latest) return "missing";
    const ref_value = ref_map.get(home_latest.time);
    if (ref_value === undefined) return "missing";
    return computeStatusVerdict(home_latest.value, ref_value, direction);
  }
</script>

<script lang="ts">
  // IndicatorCard — per-state card primitive used on /s/<state>.
  //
  // Replaces the per-artifact triple-render (IndicatorChoropleth +
  // IndicatorRanked + IndicatorSmallMultiples) on the state hub with a
  // single citizen-scaled card: big number for THIS state + sparkline of
  // THIS state's series + one-line rank against all states + "See all
  // states →" link to /t/<topic>.
  //
  // The triple-render components stay in use on /t/<topic> and /compare
  // where the cross-state question is the right one. On /s/<state> the
  // citizen is asking "how is MY state doing?" — the card answers that
  // and links out to the India view rather than mounting one per card.
  //
  // Plan doc: TODO/20260515-state-page-ia-rework-plan.md §2 + §9 row 1.
  // Doctrine: docs/concepts/schema-is-the-design-system.md (composition
  // over the existing renderer set + sparkline primitive; not a new
  // renderer family — no ADR required).
  // Naming policy: docs/concepts/indicator-naming.md + ADR-0045 —
  // grapher `renderer_rules: [no_rank_table]`, legacy artifact
  // `indicator.renderer_rules`, and `comparability:
  // not_comparable_across_states | directional_only` all suppress the
  // rank line. Single-time-point indicators (series < 2) suppress the
  // sparkline, same rule IndicatorSmallMultiples applies.
  import {
    formatValue,
    type IndicatorArtifact,
  } from "./indicators";
  import {
    latestForEntity,
    seriesForEntity,
    rankForEntity,
    canShowRank,
    ordinal,
  } from "./indicator-card";
  import type { CatalogueTopic, CatalogueArtifact } from "./catalogue";
  import AboutThisData from "./AboutThisData.svelte";
  import ListBadge from "./ListBadge.svelte";
  import TopicIcon from "./TopicIcon.svelte";
  import FacetPicker from "./FacetPicker.svelte";
  import { uniqueFacetsInOrder, pickDefaultFacet } from "./facet-picker";
  import {
    fetchGrapherIndicatorCatalogue,
    lookupIndicatorRender,
    type IndicatorRender,
  } from "./grapher/catalogue";
  import { link } from "./links";
  // 2026-06-15: the G12 (EL4) "View latest election for <state>" footer
  // line was removed from this card. The CTA was first deleted in PR #946
  // (Hans + Jony convergence, 2026-06-11) on the grounds that a fiscal /
  // health / energy / demography card must not advertise the political
  // cascade as the natural pivot - per docs/concepts/schema-is-the-design-
  // system.md ("yen-gov is not an elections site that happens to also show
  // fiscal data... elections are one indicator family alongside" the
  // others) and docs/concepts/citizen-first.md (every family is equally
  // first-class). PR #948 silently reverted the delete via a worktree-
  // staleness squash-merge accident; PR #949 partially restored the file
  // but preserved the un-deleted CTA. This rip re-applies the delete on
  // top of #948's pills-snapshot fix and is paired with a vitest contract
  // test (PR-2 of TODO/20260615-per-card-election-cta-rip-plan.md) that
  // fails loud on any future regression. The `home_state` PROP stays -
  // it still drives the default facet, the big-number value, the sparkline
  // and the rank line. The legitimate ascend to elections already lives
  // on `/<state>` via RacesBoard + ElectionSeatsTrend + SeatDonut +
  // ElectionPicker (5 of 12 surviving entry-points catalogued in the
  // plan-doc section 0.4).
  // Phase B reader-switch: per-artifact branch between the legacy
  // `/data/indicators/in/<topic>/<id>.json` shard fetch and a DuckDB-WASM
  // query against the canonical Parquet store. The allowlist in
  // `./canonical/indicator-allowlist` is the single-source-of-truth for
  // which artifacts have been migrated (one entry today: peak demand MW).
  // Phase B-extension (PR #176): the same routing is now used by every
  // indicator widget via the shared `loadIndicator(path)` helper, so
  // canonical-backed artifacts work consistently across Card, Choropleth,
  // Ranked, and SmallMultiples renderers.
  // See TODO/20260524-p1a-data-reacquisition-plan.md §3 C4.7 Phase B / D.
  import {
    loadIndicator,
    indicatorArtifactNationalReference,
    indicatorArtifactPills,
  } from "./canonical/indicator-from-canonical";
  import type { PublisherPill } from "./sources";
  // G31 (parent plan section 20.11): pop-weighted national reference
  // line + direction-coloured StatusGlyph overlaid on the per-state
  // sparkline. The reference data is opportunistically attached to the
  // artifact by the canonical loader when the descriptor opts in via
  // `has_national_reference: true` (today: outstanding-liabilities-pct-
  // gsdp only). Renders byte-identical to today's baseline when the
  // four fence rules below do not all hold; the citizen never sees a
  // broken reference treatment. The four pure helpers
  // (`nationalReferenceMap`, `mergedYMax`, `referenceSparklinePath`,
  // `referenceGlyphVerdict`) live in this file's `<script module>`
  // block and are in lexical scope without an explicit import (Svelte
  // 5 module-script sharing — Skeleton / IndicatorJump precedent).
  import StatusGlyph from "./charts/status-glyph/StatusGlyph.svelte";

  interface Props {
    /** Catalogue topic this card belongs to (drives header + "See all states" link). */
    topic: CatalogueTopic;
    /** Catalogue artifact reference (for display labels / future overrides). */
    artifact: CatalogueArtifact;
    /** Path under DATA_BASE, e.g. "/indicators/in/fiscal/outstanding_debt_pct_gsdp.json". */
    indicator_path: string;
    /** ECI code of the state on this page (e.g. "S22"). Null while resolving. */
    home_state: string | null;
  }

  let { topic, artifact, indicator_path, home_state }: Props = $props();

  let data = $state<IndicatorArtifact | null>(null);
  let indicator_render = $state<IndicatorRender | null>(null);
  let load_error = $state<string | null>(null);
  // Local snapshot of publisher pills captured at load time. Cannot be
  // derived through `indicatorArtifactPills(data)` because `data` is
  // wrapped in Svelte 5's `$state` Proxy, which breaks the WeakMap
  // identity lookup the accessor relies on (PR #940 lesson). Pass
  // explicitly to AboutThisData so its <SourceList> is non-empty.
  let pills_snapshot = $state<readonly PublisherPill[] | undefined>(undefined);

  $effect(() => {
    data = null;
    indicator_render = null;
    load_error = null;
    pills_snapshot = undefined;
    // Snapshot the path so the closure captured below is stable across
    // re-renders (Svelte 5 $effect re-runs on prop changes).
    const path = indicator_path;
    Promise.all([
      loadIndicator(path),
      fetchGrapherIndicatorCatalogue().catch(() => null),
    ])
      .then(([a, cat]) => {
        if (indicator_path !== path) return;
        // CRITICAL: read pills off the RAW `a` BEFORE the `data = a`
        // assignment wraps it in a `$state` Proxy. After the assignment,
        // `indicatorArtifactPills(data)` returns undefined because the
        // WeakMap is keyed by raw object identity. See user-memory
        // pattern "WeakMap-keyed accessor + Svelte 5 $state Proxy".
        pills_snapshot = indicatorArtifactPills(a);
        data = a;
        indicator_render = cat ? lookupIndicatorRender(cat, a.indicator.id) : null;
      })
      .catch((e) => (load_error = String(e)));
  });

  const meta = $derived(data?.indicator ?? null);

  // PR-D facet wiring (replaces PR 7b commit 2's amber placeholder).
  // When the artifact carries multi-facet rows (e.g. RPO compliance ships
  // {solar, non-solar, total} per state per year), summing across facets
  // via latestForEntity / seriesForEntity / rankForEntity would render
  // meaningless aggregates ("RPO compliance: 287%" because solar 47 +
  // non-solar 76 + total 164). The FacetPicker primitive surfaces one
  // facet at a time; `facet_rows` below pre-filters the rows so the
  // existing facet-agnostic helpers stay correct (they sum across what's
  // passed in).
  //
  // Detection is permissive: ANY row with a non-empty facet flips the
  // multiplexed flag. False positives (single-facet rows that nonetheless
  // carry a facet label) still render via the picker — that is the
  // correct outcome, because the renderer cannot tell from data shape
  // alone whether summing is safe.
  const unique_facets = $derived<string[]>(
    uniqueFacetsInOrder(data?.rows ?? []),
  );
  const is_facet_multiplexed = $derived<boolean>(unique_facets.length > 0);

  // Citizen's current pick. Null until the first $derived run resolves
  // a default; null again if `is_facet_multiplexed` flips false (e.g.
  // `data` reloads as a non-faceted artifact). Mutated only by the
  // FacetPicker `onSelect` callback in the template below.
  let selected_facet = $state<string | null>(null);

  // Effective facet = user pick (if still valid) or computed default.
  // Validation matters when `data` re-loads with a different facet
  // vocabulary — a stale user pick falls back to the new default. Pure
  // $derived; no $effect, no risk of write-during-render loops.
  const effective_facet = $derived<string | null>(
    is_facet_multiplexed
      ? (selected_facet && unique_facets.includes(selected_facet)
          ? selected_facet
          : pickDefaultFacet(data?.rows ?? [], home_state, unique_facets))
      : null,
  );

  // Pre-filtered rows for the per-facet view. When not faceted, this is
  // just `data.rows` passed through; when faceted, only the rows whose
  // `facet` matches `effective_facet`. Either way, the helpers below get
  // a facet-safe input — they remain ignorant of the facet concept.
  const facet_rows = $derived(
    is_facet_multiplexed && effective_facet && data
      ? data.rows.filter(r => r.facet === effective_facet)
      : (data?.rows ?? []),
  );

  const home_latest = $derived(
    data && home_state
      ? latestForEntity(facet_rows, home_state)
      : null,
  );
  const series = $derived(
    data && home_state
      ? seriesForEntity(facet_rows, home_state)
      : [],
  );
  const rank_info = $derived(
    data && home_state && meta
      ? rankForEntity(
          facet_rows,
          home_state,
          meta.direction,
          canShowRank(meta, indicator_render),
        )
      : null,
  );

  // Sparkline geometry — same conventions as IndicatorSmallMultiples
  // (single Y axis = max abs across this state's series; no axes; latest
  // value gets a dot). Wider/taller than the small-multiples tile because
  // there's only one of these per topic, not 36.
  //
  // G31: `H` bumped 48 -> 56 so the StatusGlyph (10 px, positioned 6 px
  // to the right of the state's latest-point dot) does not visually
  // clip the state line's top. The matching CSS class on the `<svg>`
  // bumps `h-12 -> h-14` to keep the viewBox-to-frame stretch neutral
  // (preserveAspectRatio="none"). `overflow="visible"` is added so the
  // glyph's x-overflow past the right edge renders rather than
  // clipping at the viewBox boundary.
  const W = 240;
  const H = 56;
  const PAD_X = 2;
  const PAD_Y = 3;
  const span = $derived(series.length > 1 ? series.length - 1 : 1);

  // G31: pop-weighted national-reference rows attached to the artifact
  // by the canonical loader (or `undefined` when the descriptor opts
  // out / sibling CSV absent / fetch failed). Map keys are stringified
  // from the BIGINT `time` so they join against the state series'
  // string-shaped period_label.
  const reference_rows = $derived(
    data ? indicatorArtifactNationalReference(data) : undefined,
  );
  const ref_map = $derived(nationalReferenceMap(reference_rows));
  // Overlap = count of state periods that also have a reference value.
  // Fence rule 3: render the reference treatment only when overlap >= 2.
  const ref_overlap = $derived.by(() => {
    let n = 0;
    for (const p of series) if (ref_map.has(p.time)) n += 1;
    return n;
  });
  // Fence rules 1 + 2 + 3 (the polyline gate). Rule 4 (home period in
  // ref) gates the StatusGlyph independently below via the verdict.
  const should_render_reference = $derived<boolean>(
    !!meta
      && meta.direction !== "neutral"
      && (reference_rows?.length ?? 0) >= 2
      && ref_overlap >= 2,
  );

  // y_max folds in reference values at overlapping periods so the two
  // polylines share a Y-scale (otherwise the reference line could plot
  // off-canvas when its values exceed the state's max). Falls back to
  // state-only when reference is suppressed.
  const y_max = $derived.by(() =>
    should_render_reference
      ? mergedYMax(series, ref_map)
      : (() => {
          let m = 0;
          for (const p of series) if (Math.abs(p.value) > m) m = Math.abs(p.value);
          return m || 1;
        })(),
  );
  const reference_sparkline_path = $derived(
    should_render_reference
      ? referenceSparklinePath(series, ref_map, y_max, { W, H, PAD_X, PAD_Y })
      : "",
  );
  const reference_glyph_verdict = $derived(
    should_render_reference && meta
      ? referenceGlyphVerdict(home_latest, ref_map, meta.direction)
      : ("missing" as const),
  );
  const sparkline_path = $derived.by(() => {
    if (series.length < 2) return "";
    const inner_w = W - 2 * PAD_X;
    const inner_h = H - 2 * PAD_Y;
    return series
      .map((p, i) => {
        const x = PAD_X + (i / span) * inner_w;
        const y = PAD_Y + inner_h - (Math.abs(p.value) / y_max) * inner_h;
        return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  });
  const sparkline_dot = $derived.by(() => {
    if (series.length < 2) return null;
    const last = series[series.length - 1];
    const inner_w = W - 2 * PAD_X;
    const inner_h = H - 2 * PAD_Y;
    const idx = series.length - 1;
    return {
      cx: PAD_X + (idx / span) * inner_w,
      cy: PAD_Y + inner_h - (Math.abs(last.value) / y_max) * inner_h,
    };
  });

  // Per indicator-naming.md, `higher_is_better` keeps a green tinge,
  // `lower_is_better` red, `neutral` blue. Sparkline stroke only — we do
  // NOT colour the big number (intensity coding stays in the choropleth).
  const stroke = $derived.by(() => {
    if (!meta) return "#0284c7";
    if (meta.direction === "higher_is_better") return "#059669";
    if (meta.direction === "lower_is_better") return "#dc2626";
    return "#0284c7";
  });

  // Link to the topic page until /i/<indicator> exists (per plan §2:
  // "See all states →" → `link.topic(topic.id)`).
  const see_all_href = $derived(link.topic(topic.id));
</script>

<section
  class="bg-white rounded-lg shadow-sm ring-1 ring-slate-200/70 p-4 space-y-3"
  data-testid="indicator-card"
>
  {#if load_error}
    <div class="text-sm bg-rose-50 border border-rose-200 text-rose-900 rounded px-3 py-2">
      Failed to load indicator: <code>{load_error}</code>
    </div>
  {:else if !data || !meta}
    <div class="text-sm text-slate-500">Loading…</div>
  {:else}
    <header class="flex items-baseline gap-2 flex-wrap">
      <h3 class="text-sm font-semibold text-slate-800 flex items-center gap-2">
        <TopicIcon name={meta.icon} cls="w-4 h-4 text-slate-500 shrink-0" />
        <span>{meta.title}</span>
      </h3>
      {#if artifact.display && artifact.display !== meta.title}
        <span class="text-xs text-slate-400">· {artifact.display}</span>
      {/if}
    </header>

    <!-- Facet picker. Only rendered for multi-facet artifacts. The picker
         primitive is stateless (the parent owns `selected_facet`); tapping
         a pill re-derives the big number, sparkline, and rank line for
         that segment via `facet_rows` in the script. Layout: between the
         header and the big-number row per Jony's PR-D verdict section 4. -->
    {#if is_facet_multiplexed && effective_facet}
      <FacetPicker
        facets={unique_facets}
        selected={effective_facet}
        onSelect={(f) => { selected_facet = f; }}
      />
    {/if}

    <!-- Big number + sparkline row. On narrow viewports they stack; the
         sparkline is decorative when home data is missing. For faceted
         artifacts, `facet_rows` (script) feeds the helpers below the
         per-facet slice — no more summing-across-facets meaninglessness. -->
    <div class="flex items-end justify-between gap-4 flex-wrap">
      <div class="min-w-0">
        {#if home_latest}
          <div class="text-3xl font-bold tabular-nums text-slate-900 leading-none">
            {formatValue(home_latest.value, meta)}
          </div>
          <div class="text-[11px] uppercase tracking-[0.1em] text-slate-500 mt-1">
            {home_latest.time}
          </div>
        {:else}
          <div class="text-sm text-slate-400 italic">No data for this state yet.</div>
        {/if}
      </div>

      {#if sparkline_path}
        <svg
          viewBox="0 0 {W} {H}"
          class="w-40 h-14 flex-shrink-0"
          preserveAspectRatio="none"
          overflow="visible"
          aria-hidden="true"
          data-testid="indicator-card-sparkline"
        >
          <!-- G31: reference line BEHIND the state line so the citizen's
               state stays the hero. Slate-400 dashed mirrors the F3
               TimeSeriesLine reference treatment exactly. No end dot;
               the comparator is labelled by the caption below. -->
          {#if reference_sparkline_path}
            <path
              d={reference_sparkline_path}
              fill="none"
              stroke="rgb(148 163 184)"
              stroke-width="1"
              stroke-dasharray="3 3"
              stroke-linecap="round"
              data-testid="indicator-card-reference-path"
            />
          {/if}
          <path
            d={sparkline_path}
            fill="none"
            stroke={stroke}
            stroke-width="1.5"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          {#if sparkline_dot}
            <circle cx={sparkline_dot.cx} cy={sparkline_dot.cy} r="2" fill={stroke} />
          {/if}
          <!-- G31: StatusGlyph 6 px right of the state's latest dot.
               Verdict computed by `referenceGlyphVerdict` honours the
               indicator's direction (`lower_is_better` for outstanding
               liabilities). "missing" verdict renders nothing (no
               glyph), which is the right outcome when the home period
               has no matching reference value. -->
          {#if sparkline_dot && reference_glyph_verdict !== "missing"}
            <StatusGlyph
              verdict={reference_glyph_verdict}
              cx={sparkline_dot.cx + 6}
              cy={sparkline_dot.cy}
              size_px={10}
            />
          {/if}
        </svg>
      {/if}
    </div>

    <!-- G31: one caption line beneath the sparkline row naming the
         comparator. Citizen-readable ("vs national (pop-weighted)") so
         the reference treatment never relies on colour alone (Citizen
         flag, Hans-grade concern). Suppressed when the reference is
         not rendered. -->
    {#if reference_sparkline_path}
      <div
        class="text-[10px] text-slate-500 text-right"
        data-testid="indicator-card-reference-caption"
      >vs national (pop-weighted)</div>
    {/if}

        <!-- Rank line. Suppressed when the indicator is not comparable across
          states or grapher/legacy render policy carries no_rank_table
          (canShowRank encapsulates both). When only one state has data,
          rank is "1 of 1" which is meaningless — suppress total=1 too. -->
    {#if rank_info && rank_info.total > 1}
      <p class="text-xs text-slate-600">
        {ordinal(rank_info.rank)} of {rank_info.total} states, {rank_info.time}.
      </p>
    {/if}

    <footer class="flex items-center justify-between gap-3 pt-1 border-t border-slate-100">
      <ListBadge list={topic.list} compact />
      <a
        class="text-xs text-blue-600 hover:underline"
        href={see_all_href}
        data-testid="indicator-card-see-all"
      >See all states →</a>
    </footer>

    <AboutThisData artifact={data} pills={pills_snapshot} />
  {/if}
</section>
