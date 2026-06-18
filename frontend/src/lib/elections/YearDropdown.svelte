<!--
  YearDropdown - the compare-page election-year selector (Jony + Citizen
  2026-06-18). A custom popover (NOT a native <select>) so it can carry
  the winner-colour dot + a "selected" check + greyed disabled rows, and
  match the app's pill idiom.

  Two of these sit in the compare-page title-as-control line
  ("<Earlier v> vs <Later v>"). Forward-time + same-year bans come from
  the OPTIONS (buildTimeOrderedYearOptions sets is_disabled); this
  component just refuses to fire onSelect for a disabled row. The
  caller owns navigation (each pick rewrites the compare URL).

  Section-0 descopes a11y; this carries only natural button semantics +
  aria-expanded. Closes on Escape + click-outside.
-->
<script lang="ts">
  import type { YearPickerOption } from "./year-compare-picker-model";

  interface Props {
    /** Faint eyebrow above the pill, e.g. "Earlier" / "Later". */
    label: string;
    options: YearPickerOption[];
    selectedId: string;
    onSelect: (event_id: string) => void;
    testid?: string;
    align?: "left" | "right";
  }

  let {
    label,
    options,
    selectedId,
    onSelect,
    testid = "year-dropdown",
    align = "left",
  }: Props = $props();

  let open = $state(false);
  let root_el: HTMLElement | undefined = $state();

  const selected = $derived(options.find((o) => o.event_id === selectedId));

  function pick(o: YearPickerOption): void {
    if (o.is_disabled) return;
    onSelect(o.event_id);
    open = false;
  }

  $effect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") open = false;
    };
    const onClick = (e: MouseEvent) => {
      if (root_el && !root_el.contains(e.target as Node)) open = false;
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("click", onClick, true);
    };
  });
</script>

<span class="relative inline-flex flex-col" bind:this={root_el}>
  <span class="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-400"
    >{label}</span
  >
  <button
    type="button"
    onclick={() => (open = !open)}
    aria-expanded={open}
    data-testid={testid}
    class="inline-flex min-h-[40px] items-center gap-2 rounded-yen-pill border border-slate-300 bg-white px-3 py-1.5 text-base font-semibold tabular-nums text-slate-900 transition-colors hover:border-slate-400"
  >
    <span>{selected?.year_label ?? "\u2014"}</span>
    <span aria-hidden="true" class="text-xs text-slate-400"
      >{open ? "\u25b4" : "\u25be"}</span
    >
  </button>

  {#if open}
    <div
      class="absolute top-full z-30 mt-1 max-h-72 w-40 overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg {align ===
      'right'
        ? 'right-0'
        : 'left-0'}"
      data-testid="{testid}-panel"
      role="listbox"
    >
      {#each options as o (o.event_id)}
        {@const is_sel = o.event_id === selectedId}
        <button
          type="button"
          disabled={o.is_disabled}
          onclick={() => pick(o)}
          data-testid="{testid}-option-{o.event_id}"
          class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm tabular-nums transition-colors {o.is_disabled
            ? 'cursor-not-allowed text-slate-300'
            : is_sel
              ? 'bg-slate-100 font-semibold text-slate-900'
              : 'text-slate-700 hover:bg-slate-100'}"
        >
          <span
            class="inline-block h-2 w-2 shrink-0 rounded-full"
            style="background-color: {o.winner_color_hex ?? '#e2e8f0'};"
          ></span>
          <span class="flex-1">{o.year_label}</span>
          {#if is_sel}
            <span aria-hidden="true" class="text-slate-500">{"\u2713"}</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</span>
