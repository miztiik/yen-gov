<script lang="ts">
  // ChartShell — shared chart shell and action footer (Phase 1.4 task 1).
  //
  // Per docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md Phase 1.4.
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
  //   - Source disclosure: `<SourceList pills={pills} />` from
  //     $lib/sources (publisher-pill grammar; one row per
  //     producer x series_family). Sources-simplification PR-1 (2026-06-11)
  //     swapped this from the v2 11-col `SourceListV2` to the new
  //     5-col pill component.
  //   - Action footer: the closed enum of approved actions (`view_data`,
  //     `download`, `copy_link`, `share`, `reset_view`, `full_range`)
  //     filtered + canonical-sorted by the pure helpers in
  //     `./chart-shell/actions.ts`. Renderer cannot emit unapproved ids.
  //
  // U5a state-aware body (parent plan section 23.5): the body slot
  // now branches on a `state` prop ("loading" / "error" / "empty" /
  // "data"). Loading defaults to `<Skeleton />` (or a caller-supplied
  // `loading_slot`); error renders "Data unavailable" + an optional
  // `source_line` snippet; empty renders a small inline hatch swatch
  // + a citizen-readable "no rows" line; data renders `children`. The
  // header (title / subtitle / toolbar / honesty banners) and footer
  // (pills / actions) ride UNCHANGED in every state - the chrome
  // stays consistent so the citizen does not lose context. The pure
  // state helpers live in `./chart-shell/state.ts` and are covered by
  // `./chart-shell/state.test.ts` (vitest, node-env).
  //
  // R-08 Branch by Abstraction: this PR ships the shell structurally
  // with ZERO callers. v1 chart headers / footers (StackedTrendV2's
  // built-in heading, SeatDonut's standalone layout, etc.) continue to
  // ship untouched. Per-renderer migration onto ChartShell happens one
  // PR at a time once each renderer is ready to consume the shell.
  //
  //   - R-24 fetch-telemetry: zero. The source slot delegates to the
  //     new `SourceList` from `$lib/sources` which only renders
  //     publisher-pill text; no url / fetched_at / content_hash.
  //
  //   - R-28 manifest discipline: the `pills` prop arrives as a typed
  //     `readonly PublisherPill[]`, deduped upstream by view-models /
  //     adapters from `taxonomy.sources` via the manifest-registered
  //     `table_id`. This component never sees a parquet path literal.
  //
  // CLAUDE.md §0 a11y descoped: no `aria-*`, no `role`. Visible
  // affordances only. Buttons remain real `<button>` so keyboard /
  // pointer activation works for free.
  //
  // Vitest gate: helper-side only. The action vocabulary is closed by
  // `actions.test.ts` (13 cases). Component-level DOM assertions land
  // in Playwright when the first renderer adopts the shell — vitest is
  // node-env without jsdom (see boundaries.integration.test.ts
  // comment line 4).

  import type { Snippet } from "svelte";
  import { SourceList } from "../../sources";
  import Skeleton from "../Skeleton.svelte";
  import {
    filterAllowedActions,
    sortActionsForFooter,
  } from "./chart-shell/actions";
  import {
    DEFAULT_EMPTY_MESSAGE,
    DEFAULT_ERROR_MESSAGE,
    resolveChartShellState,
    type ChartShellState,
  } from "./chart-shell/state";
  import type {
    ChartShellActionSpec,
    ChartShellHonestyBanner,
    PublisherPill,
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
    /** Footer publisher pills. Resolved upstream from `taxonomy.sources`
     *  via the manifest-registered `table_id` + `dedupeToPills` from
     *  $lib/sources. Empty array (or undefined) renders nothing in the
     *  footer source slot. */
    pills?: readonly PublisherPill[];
    /** Footer action toolbar specs. Unknown ids are dropped silently
     *  by `filterAllowedActions` before render; approved ids are
     *  rendered in canonical order by `sortActionsForFooter`. */
    actions?: readonly ChartShellActionSpec[];
    /** Chart body. The renderer's SVG / canvas / HTML chart goes here.
     *  Rendered when `state` resolves to "data" (the default). */
    children?: Snippet;
    /** Right-aligned controls hung next to the title (mode toggles,
     *  export glyphs, etc.). Kept distinct from `actions` because
     *  toolbar controls are renderer-specific and not vocabulary-gated;
     *  `actions` is the **footer** action row with the closed enum. */
    toolbar?: Snippet;
    /** Body state discriminator (U5a, parent plan section 23.5):
     *
     *    - "loading" -> render `<Skeleton />` (default) or `loading_slot`.
     *    - "error"   -> render `<p>{error_message}</p>` + optional
     *                   `source_line` snippet so the citizen knows
     *                   WHICH publisher failed.
     *    - "empty"   -> render a small inline hatch swatch + a
     *                   citizen-readable "no rows" line.
     *    - "data"    -> render `children` (the chart).
     *
     *  null / undefined collapses to "data" so callers that don't opt
     *  in keep their pre-U5a behaviour byte-for-byte. The header +
     *  footer ride UNCHANGED in every state - the chrome stays
     *  consistent so the citizen does not lose context when a chart
     *  fails or returns nothing. */
    state?: ChartShellState | null;
    /** Caller-supplied copy for the error state. Defaults to
     *  `DEFAULT_ERROR_MESSAGE` ("Data unavailable"). Citizen-readable
     *  short text - paragraph, not stack trace. */
    error_message?: string | null;
    /** Caller-supplied copy for the empty state. Defaults to
     *  `DEFAULT_EMPTY_MESSAGE` ("No data for this selection."). */
    empty_message?: string | null;
    /** Optional source-line snippet rendered alongside the error
     *  message so the citizen sees WHICH publisher failed (e.g.
     *  "Source: RBI, fetched 2026-05-11"). Hidden when null /
     *  undefined. */
    source_line?: Snippet;
    /** Optional caller-supplied loading slot to override the default
     *  `<Skeleton />`. Useful when a renderer needs a particular
     *  loading-layout (e.g. multiple skeleton bands stacked to mimic
     *  the chart's final shape). */
    loading_slot?: Snippet;
    /** E1 (parent plan section 25.2): mandatory time label for any
     *  view whose data has a `time` axis OR fixed election vintage.
     *  Renders in the header IMMEDIATELY UNDER the title and ABOVE
     *  the source line / honesty banners. Use tabular-numeral token.
     *
     *  Snapshot example: "Assembly election 2023".
     *  Series example:  "1977 - 2024" (or brushed extent when a
     *  TimeControl is active).
     *
     *  Renderers MUST supply this for election views; null/undefined
     *  skips the slot (genuinely timeless views like boundary-only
     *  layers, which must say so explicitly in the title or
     *  subtitle). The slot is rendered as a SIBLING below the
     *  subtitle and ABOVE the honesty chip strip - chrome, not
     *  tooltip, not legend footnote. */
    time_label?: string | null;
  }

  const {
    title,
    subtitle = null,
    honesty_banners = [],
    pills,
    actions = [],
    children,
    toolbar,
    state = null,
    error_message = null,
    empty_message = null,
    source_line,
    loading_slot,
    time_label = null,
  }: Props = $props();

  // Closed-enum filter + canonical sort. The renderer never sees an
  // unapproved id. This is the structural guarantee that satisfies the
  // Phase 1.4 contract test "action footer does not render unapproved
  // controls" without the test having to crawl every chart route.
  const footerActions = $derived(
    sortActionsForFooter(filterAllowedActions(actions)),
  );

  // Body-state branch resolution. `resolveChartShellState` normalises
  // null / undefined to "data" so an un-opted renderer keeps its
  // pre-U5a behaviour. The four branches map 1:1 to the four body
  // slots below.
  const resolvedState = $derived(resolveChartShellState(state));
  const effectiveErrorMessage = $derived(
    error_message ?? DEFAULT_ERROR_MESSAGE,
  );
  const effectiveEmptyMessage = $derived(
    empty_message ?? DEFAULT_EMPTY_MESSAGE,
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
    {#if time_label}
      <p
        class="chart-shell__time-label"
        data-slot="time-label"
      >
        {time_label}
      </p>
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

  <div class="chart-shell__body" data-slot="body" data-state={resolvedState}>
    {#if resolvedState === "loading"}
      <div class="chart-shell__state chart-shell__state--loading" data-state-slot="loading">
        {#if loading_slot}
          {@render loading_slot()}
        {:else}
          <Skeleton height="8rem" />
        {/if}
      </div>
    {:else if resolvedState === "error"}
      <div class="chart-shell__state chart-shell__state--error" data-state-slot="error">
        <p class="chart-shell__state-line">{effectiveErrorMessage}</p>
        {#if source_line}
          <div class="chart-shell__state-source">
            {@render source_line()}
          </div>
        {/if}
      </div>
    {:else if resolvedState === "empty"}
      <div class="chart-shell__state chart-shell__state--empty" data-state-slot="empty">
        <svg
          class="chart-shell__hatch"
          viewBox="0 0 64 24"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <pattern
              id="chart-shell-no-data-hatch"
              width="6"
              height="6"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" stroke-width="1.5" />
            </pattern>
          </defs>
          <rect width="64" height="24" fill="url(#chart-shell-no-data-hatch)" />
        </svg>
        <p class="chart-shell__state-line">{effectiveEmptyMessage}</p>
      </div>
    {:else if children}
      {@render children()}
    {/if}
  </div>

  <footer class="chart-shell__footer">
    {#if pills && pills.length > 0}
      <div class="chart-shell__sources" data-slot="sources">
        <SourceList {pills} />
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
  .chart-shell__time-label {
    /* E1 mandatory time chrome (parent plan section 25.2). Tabular-
       numeral so digits align across snapshots and ranges. Sits
       between subtitle and honesty chips; chrome, not legend. */
    margin: 0;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--ink, rgb(15 23 42));
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.01em;
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

  /* U5a body-state slots (parent plan section 23.5). Each state has
     identical chrome (the header + footer ride unchanged), only the
     body content shifts. The styling stays muted so a citizen reads
     the state as "the chart is not here right now" rather than
     "something broke" - the latter would over-claim. */
  .chart-shell__state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 6rem;
    padding: 1rem;
    text-align: center;
  }
  .chart-shell__state-line {
    margin: 0;
    color: var(--ink-muted);
    font-size: 0.8125rem;
  }
  .chart-shell__state--error .chart-shell__state-line {
    color: var(--ink);
    font-weight: 500;
  }
  .chart-shell__state-source {
    color: var(--ink-muted);
    font-size: 0.6875rem;
  }
  .chart-shell__hatch {
    display: block;
    width: 4rem;
    height: 1.5rem;
    color: var(--line);
  }
</style>
