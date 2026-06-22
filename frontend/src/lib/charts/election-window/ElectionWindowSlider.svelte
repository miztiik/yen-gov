<script lang="ts">
  // ElectionWindowSlider - a draggable two-handle range slider over the
  // full election axis, with the selection constrained to 1..3 cycles.
  //
  // Interaction (Pointer Events, touch-friendly via touch-action:none):
  //   - drag the "start" or "end" handle to RESIZE the window (1..3)
  //   - drag the band body to PAN the window, preserving its size
  // All index math is delegated to ./helpers (setStart / setEnd / panTo /
  // clampWindow); this component holds no clamping logic of its own.
  //
  // Doctrine: CLAUDE.md section 0 a11y descoped - no aria, no role.
  // Visible affordances only. Test seams via data-* attributes.

  import {
    clampWindow,
    panTo,
    setEnd,
    setStart,
    windowSize,
    type WindowConstraints,
    type WindowRange,
  } from "./helpers";

  type DragMode = "start" | "end" | "pan";

  interface DragState {
    readonly mode: DragMode;
    readonly pointerId: number;
    readonly originIndex: number;
    readonly originRange: WindowRange;
    readonly target: HTMLElement;
  }

  interface Props {
    labels: readonly string[];
    range: WindowRange;
    min_size?: number;
    max_size?: number;
    on_change?: (next: WindowRange) => void;
  }

  let {
    labels,
    range,
    min_size = 1,
    max_size = 3,
    on_change,
  }: Props = $props();

  const count = $derived(labels.length);
  const constraints = $derived<WindowConstraints>({
    count: Math.max(1, count),
    minSize: min_size,
    maxSize: max_size,
  });
  const clamped = $derived.by<WindowRange>(() => {
    if (count === 0) return { start: 0, end: 0 };
    return clampWindow(range, constraints);
  });
  const size = $derived(count === 0 ? 0 : windowSize(clamped));

  let drag = $state<DragState | null>(null);
  let rail_el = $state<HTMLDivElement | null>(null);

  function tickPct(index: number): string {
    if (count <= 1) return "50%";
    return `${(index / (count - 1)) * 100}%`;
  }

  function bandLeftPct(): string {
    return tickPct(clamped.start);
  }

  function bandWidthPct(): string {
    if (count <= 1) return "0%";
    return `${((clamped.end - clamped.start) / (count - 1)) * 100}%`;
  }

  function indexAtClientX(clientX: number): number {
    if (count <= 1 || rail_el === null) return 0;
    const rect = rail_el.getBoundingClientRect();
    const ratio = rect.width <= 0 ? 0 : (clientX - rect.left) / rect.width;
    const raw = Math.round(ratio * (count - 1));
    return Math.min(count - 1, Math.max(0, raw));
  }

  function emit(next: WindowRange): void {
    on_change?.(next);
  }

  function beginDrag(mode: DragMode, event: PointerEvent): void {
    if (count === 0) return;
    const target = event.currentTarget as HTMLElement;
    const originIndex = indexAtClientX(event.clientX);
    target.setPointerCapture(event.pointerId);
    drag = {
      mode,
      pointerId: event.pointerId,
      originIndex,
      originRange: clamped,
      target,
    };
    event.preventDefault();
  }

  function handlePointerMove(event: PointerEvent): void {
    if (drag === null || drag.pointerId !== event.pointerId) return;
    const idx = indexAtClientX(event.clientX);
    if (drag.mode === "start") {
      emit(setStart(drag.originRange, idx, constraints));
      return;
    }
    if (drag.mode === "end") {
      emit(setEnd(drag.originRange, idx, constraints));
      return;
    }
    emit(
      panTo(
        drag.originRange,
        drag.originRange.start + idx - drag.originIndex,
        constraints,
      ),
    );
  }

  function finishDrag(event: PointerEvent): void {
    if (drag === null || drag.pointerId !== event.pointerId) return;
    if (drag.target.hasPointerCapture(event.pointerId)) {
      drag.target.releasePointerCapture(event.pointerId);
    }
    drag = null;
  }
</script>

<div
  class="election-window-slider"
  data-component="election-window-slider"
  data-window-start={clamped.start}
  data-window-end={clamped.end}
  data-size={size}
>
  {#if count > 0}
    <div class="election-window-slider__rail" bind:this={rail_el}>
      <div class="election-window-slider__track"></div>
      <button
        type="button"
        title="Drag window"
        class="election-window-slider__band"
        style:left={bandLeftPct()}
        style:width={bandWidthPct()}
        onpointerdown={(event) => beginDrag("pan", event)}
        onpointermove={handlePointerMove}
        onpointerup={finishDrag}
        onpointercancel={finishDrag}
      ></button>
      {#each labels as label, i (`${label}-${i}`)}
        {@const in_window = i >= clamped.start && i <= clamped.end}
        <div
          class="election-window-slider__tick"
          class:election-window-slider__tick--active={in_window}
          style:left={tickPct(i)}
          data-tick-index={i}
          data-in-window={in_window ? "true" : "false"}
        ></div>
      {/each}
      <button
        type="button"
        class="election-window-slider__handle"
        title="Drag start"
        style:left={tickPct(clamped.start)}
        data-handle="start"
        onpointerdown={(event) => beginDrag("start", event)}
        onpointermove={handlePointerMove}
        onpointerup={finishDrag}
        onpointercancel={finishDrag}
      >
        <span></span>
      </button>
      <button
        type="button"
        class="election-window-slider__handle"
        title="Drag end"
        style:left={tickPct(clamped.end)}
        data-handle="end"
        onpointerdown={(event) => beginDrag("end", event)}
        onpointermove={handlePointerMove}
        onpointerup={finishDrag}
        onpointercancel={finishDrag}
      >
        <span></span>
      </button>
    </div>

    <div class="election-window-slider__labels">
      {#each labels as label, i (`label-${label}-${i}`)}
        {@const in_window = i >= clamped.start && i <= clamped.end}
        <span
          class:election-window-slider__label--active={in_window}
          style:left={tickPct(i)}
        >{label}</span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .election-window-slider {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-family: var(--font-sans);
    font-size: 0.6875rem;
    color: rgb(71 85 105);
  }

  .election-window-slider__rail {
    position: relative;
    height: 2rem;
    margin: 0 0.75rem;
    touch-action: none;
  }

  .election-window-slider__track,
  .election-window-slider__band {
    position: absolute;
    top: 50%;
    height: 0.5rem;
    transform: translateY(-50%);
    border-radius: 999px;
  }

  .election-window-slider__track {
    left: 0;
    right: 0;
    background: rgb(241 245 249);
    border: 1px solid rgb(226 232 240);
  }

  .election-window-slider__band {
    background: rgb(186 230 253);
    border: 0;
    border-inline: 2px solid rgb(3 105 161);
    padding: 0;
    cursor: grab;
  }

  .election-window-slider__band:active {
    cursor: grabbing;
  }

  .election-window-slider__tick {
    position: absolute;
    top: 50%;
    width: 0.375rem;
    height: 0.375rem;
    border-radius: 999px;
    transform: translate(-50%, -50%);
    background: rgb(203 213 225);
    border: 1px solid rgb(148 163 184);
    pointer-events: none;
  }

  .election-window-slider__tick--active {
    background: rgb(14 116 144);
    border-color: rgb(12 74 110);
  }

  .election-window-slider__handle {
    position: absolute;
    top: 50%;
    width: 1rem;
    height: 1.35rem;
    padding: 0;
    transform: translate(-50%, -50%);
    border-radius: 0.35rem;
    border: 1px solid rgb(14 116 144);
    background: rgb(248 250 252);
    box-shadow: 0 1px 2px rgb(15 23 42 / 0.14);
    cursor: ew-resize;
    display: grid;
    place-items: center;
  }

  .election-window-slider__handle span {
    width: 0.25rem;
    height: 0.8rem;
    border-inline: 1px solid rgb(100 116 139);
  }

  .election-window-slider__labels {
    position: relative;
    height: 1rem;
    margin: 0 0.75rem;
  }

  .election-window-slider__labels span {
    position: absolute;
    transform: translateX(-50%);
    white-space: nowrap;
    color: rgb(71 85 105);
    font-variant-numeric: tabular-nums;
  }

  .election-window-slider__label--active {
    color: rgb(12 74 110) !important;
    font-weight: 700;
  }
</style>
