<script lang="ts">
  // ChartShell — shared chart shell and action footer (Phase 1.4 task 1).
  //
  // Per TODO/20260518-frontend-charting-modernisation-plan.md Phase 1.4.
  //
  // Responsibilities:
  //
  //   - Title row: chart name on the left + optional `toolbar` snippet
  //     on the right (renderers hang their mode toggle / export
  //     buttons there — e.g. StackedTrendV2's Share/Total chips and the
  //     Phase 2.7 SVG download button).
  //   - Subtitle row when supplied (typically the comparability /
  //     attribution one-liner).
  //   - Honesty banner strip: small slate-50 chips above the chart body
  //     surfacing series-break / unit-change / vintage / missing-data
  //     caveats. Same vocabulary as `StackedTrendV2Honesty` but at the
  //     shell level so every renderer can disclose without re-rendering.
  //   - Chart body: the `children` snippet — the renderer's actual SVG /
  //     canvas / HTML chart.
  //   - Source disclosure: `<SourceListV2 sources={sources}
  //     schema_version={schema_version} />`, default collapsed (per
  //     Phase 1.4: "default collapsed on dense chart pages").
  //   - Action footer: the closed enum of approved actions (`view_data`,
  //     `download`, `copy_link`, `share`, `reset_view`, `full_range`)
  //     filtered + canonical-sorted by the pure helpers in
  //     `./chart-shell/actions.ts`. Renderer cannot emit unapproved ids.
  //
  // R-08 Branch by Abstraction: this PR ships the shell structurally
  // with ZERO callers. v1 chart headers / footers (StackedTrendV2's
  // built-in heading, SeatDonut's standalone layout, etc.) continue to
  // ship untouched. Per-renderer migration onto ChartShell happens one
  // PR at a time once each renderer is ready to consume the shell.
  //
  // R-24 fetch-telemetry: zero. The source slot delegates to
  // `SourceListV2` which already refuses url / fetched_at / content_hash.
  //
  // R-28 manifest discipline: the `sources` prop arrives as a typed
  // `readonly SourceV2Row[]`, resolved upstream by view-models /
  // adapters from `taxonomy.sources` via the manifest-registered
  // `table_id`. This component never sees a parquet path literal.
  //
  // CLAUDE.md §0 a11y descoped: no `aria-*`, no `role`. Visible
  // affordances only. Buttons remain real `<button>` so keyboard /
  // pointer activation works for free.
  //
  // Vitest gate: helper-side only. The action vocabulary is closed by
  // `actions.test.ts` (13 cases). Component-level DOM assertions land
  // in Playwright when the first renderer adopts the shell — vitest is
  // node-env without jsdom (see IndicatorChoropleth.boundaries.test.ts
  // comment line 4).

  import type { Snippet } from "svelte";
  import SourceListV2 from "../SourceListV2.svelte";
  import {
    filterAllowedActions,
    sortActionsForFooter,
  } from "./chart-shell/actions";
  import type {
    ChartShellActionSpec,
    ChartShellHonestyBanner,
    SourceV2Row,
  } from "./chart-shell/types";

  interface Props {
    /** Chart heading. Always rendered. Concise — citizen-readable. */
    title: string;
    /** Optional one-line context under the title (comparability,
     *  attribution, indicator slug). Hidden when null/undefined. */
    subtitle?: string | null;
    /** Honesty disclosures shown as inline chips above the chart body.
     *  Empty array = no chip strip. Each chip surfaces `text` with the
     *  `kind` available as a `data-honesty-kind` attribute so future
     *  styling can colour-code by severity. */
    honesty_banners?: readonly ChartShellHonestyBanner[];
    /** Footer source ledger (v2.0). Resolved upstream from
     *  `taxonomy.sources` via the manifest-registered `table_id`.
     *  Empty array renders the SourceListV2 "hand-authored" arm. */
    sources?: readonly SourceV2Row[];
    /** Optional schema-version label surfaced next to the source count
     *  (helps curators spot drift). */
    schema_version?: string | null;
    /** Footer action toolbar specs. Unknown ids are dropped silently
     *  by `filterAllowedActions` before render; approved ids are
     *  rendered in canonical order by `sortActionsForFooter`. */
    actions?: readonly ChartShellActionSpec[];
    /** Chart body. The renderer's SVG / canvas / HTML chart goes here. */
    children?: Snippet;
    /** Right-aligned controls hung next to the title (mode toggles,
     *  export glyphs, etc.). Kept distinct from `actions` because
     *  toolbar controls are renderer-specific and not vocabulary-gated;
     *  `actions` is the **footer** action row with the closed enum. */
    toolbar?: Snippet;
  }

  const {
    title,
    subtitle = null,
    honesty_banners = [],
    sources,
    schema_version = null,
    actions = [],
    children,
    toolbar,
  }: Props = $props();

  // Closed-enum filter + canonical sort. The renderer never sees an
  // unapproved id. This is the structural guarantee that satisfies the
  // Phase 1.4 contract test "action footer does not render unapproved
  // controls" without the test having to crawl every chart route.
  const footerActions = $derived(
    sortActionsForFooter(filterAllowedActions(actions)),
  );
</script>

<div class="chart-shell" data-component="chart-shell">
  <header class="chart-shell__header">
    <div class="chart-shell__title-row">
      <h3 class="chart-shell__title">{title}</h3>
      {#if toolbar}
        <div class="chart-shell__toolbar" data-slot="toolbar">
          {@render toolbar()}
        </div>
      {/if}
    </div>
    {#if subtitle}
      <p class="chart-shell__subtitle">{subtitle}</p>
    {/if}
    {#if honesty_banners.length > 0}
      <ul
        class="chart-shell__honesty"
        data-slot="honesty-banners"
      >
        {#each honesty_banners as banner}
          <li
            class="chart-shell__honesty-chip"
            data-honesty-kind={banner.kind}
          >
            {banner.text}
          </li>
        {/each}
      </ul>
    {/if}
  </header>

  <div class="chart-shell__body" data-slot="body">
    {#if children}
      {@render children()}
    {/if}
  </div>

  <footer class="chart-shell__footer">
    {#if sources}
      <div class="chart-shell__sources" data-slot="sources">
        <SourceListV2 {sources} {schema_version} />
      </div>
    {/if}
    {#if footerActions.length > 0}
      <div class="chart-shell__actions" data-slot="actions">
        {#each footerActions as action}
          <button
            type="button"
            class="chart-shell__action"
            data-action={action.id}
            disabled={action.disabled === true}
            onclick={() => action.on_invoke()}
          >
            {action.label}
          </button>
        {/each}
      </div>
    {/if}
  </footer>
</div>

<style>
  /* Layout-only. Visual tokens stay Tailwind-side once a real renderer
     adopts the shell; this stylesheet is the minimum so the structural
     PR previews cleanly without callers. */
  .chart-shell {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .chart-shell__title-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .chart-shell__title {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: rgb(15 23 42); /* slate-900 */
  }
  .chart-shell__toolbar {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }
  .chart-shell__subtitle {
    margin: 0;
    font-size: 0.75rem;
    color: rgb(100 116 139); /* slate-500 */
  }
  .chart-shell__honesty {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }
  .chart-shell__honesty-chip {
    padding: 0.125rem 0.5rem;
    border-radius: 0.25rem;
    background: rgb(241 245 249); /* slate-100 */
    color: rgb(71 85 105); /* slate-600 */
    font-size: 0.6875rem;
  }
  .chart-shell__footer {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .chart-shell__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }
  .chart-shell__action {
    padding: 0.25rem 0.625rem;
    border: 1px solid rgb(226 232 240); /* slate-200 */
    border-radius: 0.25rem;
    background: white;
    color: rgb(51 65 85); /* slate-700 */
    font-size: 0.75rem;
    cursor: pointer;
  }
  .chart-shell__action:hover:not(:disabled) {
    background: rgb(248 250 252); /* slate-50 */
  }
  .chart-shell__action:disabled {
    color: rgb(148 163 184); /* slate-400 */
    cursor: not-allowed;
  }
</style>
