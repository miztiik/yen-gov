<!--
  YearComparePicker - the reusable year-picker popover (PR1 of
  TODO/20260617-election-compare-ux-overhaul-plan.md, Jony section 2b).

  ONE primitive, two mounts:
   - the sibling rail's "Compare" entry (label="Compare"); selecting a
     year navigates to the compare page for (picked -> current); and
   - the compare page's From / To selectors (label = the event display);
     selecting a year re-navigates the compare URL on that axis.

  The popover is a small grid of year chips that mirror the rail chip
  styling (2px winner-colour underline). The component is intentionally
  dumb: it renders the `options` the pure `year-compare-picker-model`
  produced and fires `onSelect(event_id)`; each consumer owns the
  navigation. Closes on Escape + click-outside. Section-0 descopes a11y,
  so this carries only the natural button semantics + aria-expanded.
-->
<script lang="ts">
  import type { YearPickerOption } from "./year-compare-picker-model";

  interface Props {
    /** Button label, e.g. "Compare" (rail) or "To: Assembly 2026". */
    label: string;
    /** Options from buildYearPickerOptions (ordering + disabled baked in). */
    options: YearPickerOption[];
    /** Fired with the picked option's event_id; consumer navigates. */
    onSelect: (event_id: string) => void;
    /** Popover horizontal anchor relative to the button. */
    align?: "left" | "right";
    /** data-testid for the trigger button (lets the compare page keep
     *  its `compare-elections-from-badge` / `-to-badge` hooks). */
    testid?: string;
  }

  let {
    label,
    options,
    onSelect,
    align = "left",
    testid = "year-compare-picker",
  }: Props = $props();

  let open = $state(false);
  let root_el: HTMLElement | undefined = $state();

  function pick(o: YearPickerOption): void {
    if (o.is_disabled) return;
    onSelect(o.event_id);
    open = false;
  }

  // Escape + click-outside dismiss. Listeners only live while open. The
  // opening click never self-closes: the trigger button is inside
  // `root_el`, so the click-outside guard reads it as "inside".
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

<span class="relative inline-block" bind:this={root_el}>
  <button
    type="button"
    onclick={() => (open = !open)}
    data-testid={testid}
    aria-expanded={open}
    class="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200"
  >
    <span>{label}</span>
    <span aria-hidden="true" class="text-[10px] leading-none text-slate-400"
      >{open ? "\u25b4" : "\u25be"}</span
    >
  </button>

  {#if open}
    <div
      class="absolute z-20 mt-1 max-h-72 w-44 overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg {align ===
      'right'
        ? 'right-0'
        : 'left-0'}"
      data-testid="year-compare-picker-panel"
    >
      {#each options as o (o.event_id)}
        <button
          type="button"
          disabled={o.is_disabled}
          onclick={() => pick(o)}
          data-testid="year-compare-picker-option-{o.event_id}"
          class="flex w-full items-center justify-between rounded px-2 py-1 text-left text-sm tabular-nums transition-colors {o.is_disabled
            ? 'cursor-default bg-slate-50 text-slate-400'
            : 'text-slate-700 hover:bg-slate-100'}"
          style="border-bottom: 2px solid {o.winner_color_hex ?? '#e2e8f0'};"
        >
          <span>{o.year_label}</span>
          {#if o.is_disabled}
            <span class="text-[10px] uppercase tracking-wide text-slate-400"
              >current</span
            >
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</span>
