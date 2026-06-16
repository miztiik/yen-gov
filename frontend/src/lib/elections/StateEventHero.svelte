<!--
  StateEventHero - extracted from StateElection.svelte during R3
  (Beck two-hat: pure structural extraction, no behaviour change) of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).

  R4 (2026-06-15) extends this surface per the J-elevated-3 HeroCards
  verdict: icon glyphs on every KPI card, plus an optional
  delta-pill row on Turnout (always-on when prior exists), Voters,
  and Polled (the pct deltas threshold at >=2% per the row spec). The
  delta data flows in via the new `delta` prop on each KPI; cards
  whose delta prop is null OMIT the row entirely (J-elevated-3
  first-event card-collapse pin: the slot is absent, not zeroed).

  Renders the page header (H1 + body chip + polled-on date) + the
  load-error card (alternative arm) + the 4-card KPI strip (Seats /
  Total voters / Total polled / Turnout) + the pending card.

  Props mirror the inline mount's references PLUS the new
  `turnout_delta` field. Voters / Polled delta fields are reserved
  for a follow-up PR (the loader path that derives them requires the
  per-event summary.csv shape - the event_summary.csv mart only
  carries turnout_pct).

  Preserves data-testids: state-event-header, state-event-body-chip,
  state-event-load-error, state-event-kpis, state-event-kpi-seats,
  state-event-pending. ADDS: state-event-kpi-turnout-delta.
-->
<script lang="ts">
  import TopicIcon from "../TopicIcon.svelte";
  import type { ElectionEventRow } from "../election-events";
  import type { LoaderResult } from "../loader-result";
  import type { ElectionResultRow } from "../view-models/election-results";

  export interface HeroKpis {
    total_seats: number;
    total_electors: number | null;
    total_polled: number | null;
    turnout_pct: number | null;
  }

  /**
   * Hero delta payload (R4 / J-elevated-3 amend). Production passes
   * the projection over the loaded event_summary mart + the
   * `previous_same_body` derive; tests pass a literal. When the
   * field is null the entire delta row is OMITTED (first-event-on-
   * record card-collapse pin) - never rendered as "0" or em-dash.
   */
  export interface HeroDelta {
    /** Turnout pp-delta vs prior same-body event. Always shown when
     *  non-null per J-elevated-3 ("pp-delta ALWAYS shown when prior
     *  exists"). */
    turnout_pp: number | null;
    /** Human-readable label of the comparison event, e.g.
     *  "Assembly 2019". Required when turnout_pp is non-null. */
    prev_event_label: string | null;
  }

  interface Props {
    event_row: ElectionEventRow;
    body: "ac" | "pc" | null;
    event_pretty: string;
    result: LoaderResult<ElectionResultRow[]>;
    loading: boolean;
    pending: boolean;
    kpis: HeroKpis;
    delta?: HeroDelta;
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
    delta = { turnout_pp: null, prev_event_label: null },
    fmtInt,
    fmtCompact,
    fmtPct,
  }: Props = $props();

  // Format pp-delta: "+2.1pp" / "-1.4pp" / "0.0pp". Always carries
  // a sign because the citizen reads "+/-" as the structural cue
  // (direction) even before they read the number.
  function fmtPpDelta(pp: number): string {
    const sign = pp >= 0 ? "+" : "";
    return `${sign}${pp.toFixed(1)}pp`;
  }

  const turnout_delta_present = $derived(
    delta.turnout_pp !== null && delta.prev_event_label !== null,
  );
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
  <!-- KPIs strip. R4 (J-elevated-3) adds a TopicIcon glyph next to
       every label + an optional delta row on Turnout. Cards keep
       their existing data-testids verbatim so all prior e2e
       assertions still pass. -->
  <section
    class="grid grid-cols-2 gap-3 sm:grid-cols-4"
    data-testid="state-event-kpis"
  >
    <div class="rounded-lg border border-slate-200 bg-white p-3">
      <div class="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
          <TopicIcon name="landmark" cls="h-4 w-4" />
        </span>
        <span>Seats</span>
      </div>
      <div
        class="mt-1.5 text-2xl font-semibold tabular-nums text-slate-900"
        data-testid="state-event-kpi-seats"
      >
        {loading ? "-" : fmtInt(kpis.total_seats)}
      </div>
    </div>
    <div class="rounded-lg border border-slate-200 bg-white p-3">
      <div class="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-700">
          <TopicIcon name="users" cls="h-4 w-4" />
        </span>
        <span>Total voters</span>
      </div>
      <div class="mt-1.5 text-2xl font-semibold tabular-nums text-slate-900">
        {fmtCompact(kpis.total_electors)}
      </div>
    </div>
    <div class="rounded-lg border border-slate-200 bg-white p-3">
      <div class="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
          <TopicIcon name="vote" cls="h-4 w-4" />
        </span>
        <span>Total polled</span>
      </div>
      <div class="mt-1.5 text-2xl font-semibold tabular-nums text-slate-900">
        {fmtCompact(kpis.total_polled)}
      </div>
    </div>
    <div class="rounded-lg border border-slate-200 bg-white p-3">
      <div class="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
          <TopicIcon name="activity" cls="h-4 w-4" />
        </span>
        <span>Turnout</span>
      </div>
      <div class="mt-1.5 text-2xl font-semibold tabular-nums text-slate-900">
        {fmtPct(kpis.turnout_pct)}
      </div>
      {#if turnout_delta_present}
        {@const pp = delta.turnout_pp ?? 0}
        {@const positive = pp >= 0}
        <div
          class="mt-1.5 inline-flex items-center gap-1 rounded-yen-pill px-2 py-0.5 text-[11px] font-medium tabular-nums {positive
            ? 'bg-emerald-50 text-emerald-700'
            : 'bg-rose-50 text-rose-700'}"
          data-testid="state-event-kpi-turnout-delta"
          title="Turnout point-percentage change vs the previous same-body event"
        >
          <TopicIcon
            name={positive ? "trending-up" : "trending-down"}
            cls="h-3 w-3 shrink-0"
          />
          <span>{fmtPpDelta(pp)} vs {delta.prev_event_label}</span>
        </div>
      {/if}
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
