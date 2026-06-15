<!--
  StateEventHero - extracted from StateElection.svelte during R3
  (Beck two-hat: pure structural extraction, no behaviour change) of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).

  Renders the page header (H1 + body chip + polled-on date) + the
  load-error card (alternative arm) + the 4-card KPI strip (Seats /
  Total voters / Total polled / Turnout) + the pending card that
  previously lived inline on the state-event route.

  R4 (the same plan-doc, Section 5) will rebuild this into the
  J-elevated-3 HeroCards with icon glyphs + turnout-delta glyph rule
  + first-event-on-record card-collapse pin. R3 preserves the legacy
  DOM verbatim so existing e2e tests still pass.

  Props mirror the inline mount's references: the event_row (`ev`)
  + `body` for the Parliament/Assembly chip + `result` for the
  failed-status branch + `loading` + `kpis` + the Intl formatters
  the parent already constructed.

  Preserves data-testids: state-event-header, state-event-body-chip,
  state-event-load-error, state-event-kpis, state-event-kpi-seats,
  state-event-pending.
-->
<script lang="ts">
  import type { ElectionEventRow } from "../election-events";
  import type { LoaderResult } from "../loader-result";
  import type { ElectionResultRow } from "../view-models/election-results";

  export interface HeroKpis {
    total_seats: number;
    total_electors: number | null;
    total_polled: number | null;
    turnout_pct: number | null;
  }

  interface Props {
    event_row: ElectionEventRow;
    body: "ac" | "pc" | null;
    event_pretty: string;
    result: LoaderResult<ElectionResultRow[]>;
    loading: boolean;
    pending: boolean;
    kpis: HeroKpis;
    fmtInt: (n: number | null) => string;
    fmtCompact: (n: number | null) => string;
    fmtPct: (n: number | null) => string;
  }

  let {
    event_row,
    body,
    event_pretty,
    result,
    loading,
    pending,
    kpis,
    fmtInt,
    fmtCompact,
    fmtPct,
  }: Props = $props();
</script>

<!-- Header -->
<header class="space-y-2">
  <h1
    class="text-2xl font-semibold text-slate-900"
    data-testid="state-event-header"
  >
    {event_pretty}
  </h1>
  <div class="flex flex-wrap items-center gap-2 text-xs">
    <span
      class="inline-block rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
      data-testid="state-event-body-chip"
    >{body === "pc" ? "Parliament" : "Assembly"}</span>
    <span class="text-slate-500">
      Polled <span class="tabular-nums">{event_row.polled_on}</span>
    </span>
  </div>
</header>

{#if result.status === "failed"}
  <div
    class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    data-testid="state-event-load-error"
  >
    <p>Data couldn't load: {result.reason}</p>
  </div>
{:else}
  <!-- KPIs strip -->
  <section
    class="grid grid-cols-2 gap-3 sm:grid-cols-4"
    data-testid="state-event-kpis"
  >
    <div class="rounded border border-slate-200 bg-white p-3">
      <div class="text-xs uppercase tracking-wide text-slate-500">
        Seats
      </div>
      <div
        class="mt-1 text-2xl font-semibold text-slate-900"
        data-testid="state-event-kpi-seats"
      >
        {loading ? "-" : fmtInt(kpis.total_seats)}
      </div>
    </div>
    <div class="rounded border border-slate-200 bg-white p-3">
      <div class="text-xs uppercase tracking-wide text-slate-500">
        Total voters
      </div>
      <div class="mt-1 text-2xl font-semibold text-slate-900">
        {fmtCompact(kpis.total_electors)}
      </div>
    </div>
    <div class="rounded border border-slate-200 bg-white p-3">
      <div class="text-xs uppercase tracking-wide text-slate-500">
        Total polled
      </div>
      <div class="mt-1 text-2xl font-semibold text-slate-900">
        {fmtCompact(kpis.total_polled)}
      </div>
    </div>
    <div class="rounded border border-slate-200 bg-white p-3">
      <div class="text-xs uppercase tracking-wide text-slate-500">
        Turnout
      </div>
      <div class="mt-1 text-2xl font-semibold text-slate-900">
        {fmtPct(kpis.turnout_pct)}
      </div>
    </div>
  </section>

  {#if pending}
    <div
      class="rounded border border-dashed border-slate-300 bg-slate-50 p-3 text-center text-sm text-slate-500"
      data-testid="state-event-pending"
    >
      Results for this election are not published yet.
    </div>
  {/if}
{/if}
