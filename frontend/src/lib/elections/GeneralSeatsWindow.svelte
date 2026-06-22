<script lang="ts">
  import { scaleLinear } from "d3-scale";

  import ElectionWindowSlider from "../charts/election-window/ElectionWindowSlider.svelte";
  import {
    clampWindow,
    defaultWindow,
    type WindowRange,
  } from "../charts/election-window/helpers";
  import type { GeneralElectionRowViewModel } from "../view-models/general-elections-model";

  interface Props {
    rows: readonly GeneralElectionRowViewModel[];
  }

  let { rows }: Props = $props();

  const CHART_W = 420;
  const CHART_H = 268;
  const PLOT_TOP = 28;
  const PLOT_H = 178;
  const BASELINE_Y = PLOT_TOP + PLOT_H;
  const BAR_W = 54;
  const BAR_GAP = 42;
  const OTHERS_FILL = "#cbd5e1";
  const RUNNER_UP_FALLBACK = "#94a3b8";

  let range = $state<WindowRange>(defaultWindow({ count: 1, maxSize: 3 }));
  let last_count = $state(1);

  const sorted = $derived(
    rows.slice().sort((a, b) => a.year - b.year),
  );
  const count = $derived(sorted.length);
  const labels = $derived(sorted.map((row) => String(row.year)));
  const maxSeats = $derived(
    Math.max(1, ...sorted.map((row) => row.seats_contested)),
  );
  const yScale = $derived(
    scaleLinear().domain([0, maxSeats]).range([0, PLOT_H]),
  );
  const safeRange = $derived.by<WindowRange>(() => {
    if (count === 0) return { start: 0, end: 0 };
    return clampWindow(range, { count, maxSize: 3 });
  });
  const visibleRows = $derived(
    count === 0 ? [] : sorted.slice(safeRange.start, safeRange.end + 1),
  );

  $effect(() => {
    if (count === 0) {
      last_count = 0;
      range = { start: 0, end: 0 };
      return;
    }
    const next = last_count === count
      ? clampWindow(range, { count, maxSize: 3 })
      : defaultWindow({ count, maxSize: 3 });
    last_count = count;
    if (range.start !== next.start || range.end !== next.end) range = next;
  });

  function seatHeight(seats: number): number {
    return yScale(Math.max(0, seats));
  }

  function totalWindowWidth(): number {
    return visibleRows.length * BAR_W + Math.max(0, visibleRows.length - 1) * BAR_GAP;
  }

  function barX(index: number): number {
    return (CHART_W - totalWindowWidth()) / 2 + index * (BAR_W + BAR_GAP);
  }

  function leaderY(row: GeneralElectionRowViewModel): number {
    return BASELINE_Y - seatHeight(row.seats_won);
  }

  // Runner-up band height derives from the SAME scalar the model used
  // for others_seats, so the three bands (leader + runner-up + others)
  // always sum to seats_contested. Reading row.runner_up.seats directly
  // would under-fill the bar on a contradictory seats-without-party row.
  function runnerBandSeats(row: GeneralElectionRowViewModel): number {
    return Math.max(0, row.seats_contested - row.seats_won - row.others_seats);
  }

  function runnerY(row: GeneralElectionRowViewModel): number {
    return leaderY(row) - seatHeight(runnerBandSeats(row));
  }

  function othersY(row: GeneralElectionRowViewModel): number {
    return runnerY(row) - seatHeight(row.others_seats);
  }

  function runnerLabelY(row: GeneralElectionRowViewModel): number {
    return (runnerY(row) + leaderY(row)) / 2 + 3;
  }

  function majorityY(row: GeneralElectionRowViewModel): number {
    return BASELINE_Y - seatHeight(row.majority_mark);
  }

  function leaderLabelY(row: GeneralElectionRowViewModel): number {
    return Math.min(BASELINE_Y - 5, leaderY(row) + 13);
  }

  function handleWindowChange(next: WindowRange): void {
    if (count === 0) return;
    range = clampWindow(next, { count, maxSize: 3 });
  }
</script>

<section
  class="general-seats-window"
  data-component="general-elections-stack-window"
>
  {#if count === 0}
    <p class="general-seats-window__empty">No election data</p>
  {:else}
    <div class="general-seats-window__chart">
      <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`}>
        <line
          x1="42"
          x2="378"
          y1={BASELINE_Y}
          y2={BASELINE_Y}
          class="general-seats-window__baseline"
        />
        {#each visibleRows as row, i (row.event_id)}
          {@const x = barX(i)}
          {@const runnerSeats = runnerBandSeats(row)}
          {@const majority = majorityY(row)}
          <g data-event-id={row.event_id}>
            <title>{row.year} - {row.leading.short} {row.seats_won}; Majority: {row.majority_mark}</title>
            <rect
              x={x}
              y={othersY(row)}
              width={BAR_W}
              height={seatHeight(row.others_seats)}
              fill={OTHERS_FILL}
            />
            <rect
              x={x}
              y={runnerY(row)}
              width={BAR_W}
              height={seatHeight(runnerSeats)}
              fill={row.runner_up?.color ?? RUNNER_UP_FALLBACK}
            />
            {#if row.runner_up && seatHeight(runnerSeats) >= 14}
              <text
                x={x + BAR_W / 2}
                y={runnerLabelY(row)}
                text-anchor="middle"
                class="general-seats-window__bar-label"
              >{row.runner_up.short} {runnerSeats}</text>
            {/if}
            <rect
              x={x}
              y={leaderY(row)}
              width={BAR_W}
              height={seatHeight(row.seats_won)}
              fill={row.leading.color}
            />
            <line
              x1={x - 5}
              x2={x + BAR_W + 5}
              y1={majority}
              y2={majority}
              class="general-seats-window__majority"
              data-majority
            />
            {#if i === 0}
              <text
                x={x - 9}
                y={majority + 3}
                text-anchor="end"
                class="general-seats-window__majority-label"
              >{row.majority_mark}</text>
            {/if}
            <text
              x={x + BAR_W / 2}
              y={leaderLabelY(row)}
              text-anchor="middle"
              class="general-seats-window__leader-label"
            >{row.leading.short} {row.seats_won}</text>
            <text
              x={x + BAR_W / 2}
              y={BASELINE_Y + 18}
              text-anchor="middle"
              class="general-seats-window__year"
            >{row.year}</text>
          </g>
        {/each}
      </svg>
    </div>

    <div class="general-seats-window__legend">
      <span class="general-seats-window__swatch"></span>
      <span>Others</span>
      <span>Bars: winner (bottom), runner-up, others (top). Dashed line = majority.</span>
    </div>

    <p class="general-seats-window__windowed">
      Comparing {visibleRows.length} of {count} elections - drag to change
    </p>

    <ElectionWindowSlider
      labels={labels}
      range={safeRange}
      on_change={handleWindowChange}
    />
  {/if}
</section>

<style>
  .general-seats-window {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    border: 1px solid rgb(226 232 240);
    border-radius: 0.75rem;
    background: rgb(255 255 255);
    padding: 0.875rem;
    font-family: var(--font-sans);
  }

  .general-seats-window__empty {
    margin: 0;
    font-size: 0.8125rem;
    color: rgb(100 116 139);
  }

  .general-seats-window__chart {
    width: 100%;
  }

  .general-seats-window__chart svg {
    display: block;
    width: 100%;
    height: auto;
  }

  .general-seats-window__baseline {
    stroke: rgb(226 232 240);
    stroke-width: 1;
  }

  .general-seats-window__majority {
    stroke: rgb(100 116 139);
    stroke-width: 1.2;
    stroke-dasharray: 4 3;
  }

  .general-seats-window__majority-label,
  .general-seats-window__year {
    fill: rgb(71 85 105);
    font-size: 10px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .general-seats-window__leader-label,
  .general-seats-window__bar-label {
    fill: rgb(248 250 252);
    font-size: 10px;
    font-weight: 700;
    paint-order: stroke;
    stroke: rgb(15 23 42 / 0.28);
    stroke-width: 2px;
    stroke-linejoin: round;
  }

  .general-seats-window__windowed {
    margin: 0;
    font-size: 0.6875rem;
    color: rgb(100 116 139);
    text-align: center;
  }

  .general-seats-window__legend {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.375rem;
    font-size: 0.6875rem;
    color: rgb(71 85 105);
  }

  .general-seats-window__swatch {
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 0.2rem;
    background: #cbd5e1;
    border: 1px solid rgb(148 163 184);
  }
</style>