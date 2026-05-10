<script lang="ts">
  // Shared chart tooltip. Replaces the native browser <title> tooltip
  // (always-black, OS-styled, can't carry color or layout) with a small
  // floating card that components can drive imperatively:
  //
  //   const tip = $state<TooltipState | null>(null);
  //   ...
  //   onmouseenter={(e) => tip = { x: e.clientX, y: e.clientY,
  //                                color: party.color,
  //                                title: party.name,
  //                                lines: [{label: 'Seats', value: '108'}] }}
  //   onmouseleave={() => tip = null}
  //   <ChartTooltip tip={tip} />
  //
  // Position is fixed to the viewport (clientX/Y) so the tooltip works
  // regardless of the chart's containing block / transform context.
  // Edge-detection nudges the card back inside the viewport so it never
  // clips on the right or bottom.

  export interface TooltipLine {
    label: string;
    value: string;
    /** Optional muted display (e.g. "of 234"). */
    suffix?: string;
  }
  export interface TooltipState {
    /** Page coordinates (clientX/clientY from a mouse event). */
    x: number;
    y: number;
    /** 4-px top stripe color — usually the party color. */
    color: string;
    /** Bold first line. */
    title: string;
    /** Optional one-line context under the title (e.g. party long name). */
    subtitle?: string;
    /** Key/value rows. */
    lines: TooltipLine[];
    /** Optional foot note (e.g. "Click to mute"). */
    hint?: string;
  }

  // Prop name is `tip` (not `state`) — Svelte 5's compiler treats a
  // prop literally named `state` as a Svelte store accessor, which then
  // shadows the `$state` rune (compiles to `$state()(...)` and crashes).
  let { tip }: { tip: TooltipState | null } = $props();

  let el: HTMLDivElement | undefined = $state(undefined);
  let placement: { left: number; top: number } = $state({ left: -9999, top: -9999 });

  // Re-position whenever the tip moves. We place the card 12 px below
  // and 12 px right of the cursor by default; if that overflows the
  // viewport edge we flip to the opposite side. Read DOM rect in the
  // effect so the first frame has correct width/height.
  $effect(() => {
    if (!tip || !el) {
      placement = { left: -9999, top: -9999 };
      return;
    }
    const margin = 12;
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let left = tip.x + margin;
    let top = tip.y + margin;
    if (left + rect.width + 4 > vw) left = tip.x - rect.width - margin;
    if (top + rect.height + 4 > vh) top = tip.y - rect.height - margin;
    if (left < 4) left = 4;
    if (top < 4) top = 4;
    placement = { left, top };
  });
</script>

<!-- The tooltip is always rendered (hidden via opacity) so we can measure
     its size before positioning. pointer-events:none means it never eats a
     mouse event from the chart underneath. -->
<div
  bind:this={el}
  class="pointer-events-none fixed z-50 min-w-[140px] max-w-[260px] rounded-lg bg-white shadow-xl ring-1 ring-slate-200/80 overflow-hidden text-left transition-opacity duration-100"
  style:left="{placement.left}px"
  style:top="{placement.top}px"
  style:opacity={tip ? "1" : "0"}
  role="tooltip"
  aria-hidden={!tip}
>
  {#if tip}
    <div class="h-1" style:background-color={tip.color}></div>
    <div class="px-3 py-2 space-y-1.5">
      <div class="font-semibold text-slate-800 text-sm leading-tight">{tip.title}</div>
      {#if tip.subtitle}
        <div class="text-[11px] text-slate-500 leading-snug">{tip.subtitle}</div>
      {/if}
      {#if tip.lines.length > 0}
        <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
          {#each tip.lines as line}
            <dt class="text-slate-500">{line.label}</dt>
            <dd class="text-right tabular-nums text-slate-800 font-medium">
              {line.value}{#if line.suffix}<span class="text-slate-400 font-normal"> {line.suffix}</span>{/if}
            </dd>
          {/each}
        </dl>
      {/if}
      {#if tip.hint}
        <div class="text-[10px] text-slate-400 pt-1 border-t border-slate-100 mt-1">{tip.hint}</div>
      {/if}
    </div>
  {/if}
</div>
