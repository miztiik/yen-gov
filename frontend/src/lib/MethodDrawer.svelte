<script module lang="ts">
  // MethodDrawer - the categorised method picker. Opens from
  // MethodPickerPill; closes on (a) method selection, (b) backdrop
  // click, (c) Escape key (native <dialog> behaviour).
  //
  // Per Jony + Hans verdict (2026-06-09 round 2): twelve methods do
  // NOT fit in a horizontal-scroll segmented control. The drawer is
  // a bottom sheet (mobile) / modal sheet (desktop) with two
  // categories: "Fully workable today" + "Experimental". Each card
  // shows the short_label + headline + a validity badge.
  //
  // Hans-non-negotiable: the validity badge is INLINE on every card.
  // Hiding the tier would be a more subtle form of dishonesty than
  // the Round-1 "HYPOTHETICAL RECOUNT" banner (see Hans verdict
  // round 2 section 9 (c)).

  /** Shape of a single method-picker option. Mirrors CountingRule
   *  surface without taking a hard dependency on the registry. */
  export interface MethodPickerOption {
    id: string;
    label: string;
    short_label?: string;
    headline?: string;
    validity: "fully_workable" | "medium_validity";
  }

  export interface MethodDrawerProps {
    methods: ReadonlyArray<MethodPickerOption>;
    active_method_id: string;
    open: boolean;
    onpick: (method_id: string) => void;
    onclose: () => void;
  }

  /** Pure helper: split methods into the two validity tiers,
   *  preserving the registry order within each. Exposed for tests. */
  export function partitionByValidity(
    methods: ReadonlyArray<MethodPickerOption>,
  ): { fully_workable: MethodPickerOption[]; medium_validity: MethodPickerOption[] } {
    const fully_workable: MethodPickerOption[] = [];
    const medium_validity: MethodPickerOption[] = [];
    for (const m of methods) {
      if (m.validity === "fully_workable") fully_workable.push(m);
      else medium_validity.push(m);
    }
    return { fully_workable, medium_validity };
  }

  /** Pure helper: validity-tier label. */
  export function validityTierLabel(tier: "fully_workable" | "medium_validity"): string {
    return tier === "fully_workable" ? "Fully workable today" : "Experimental";
  }

  /** Pure helper: validity-badge text (per-card). */
  export function validityBadgeText(tier: "fully_workable" | "medium_validity"): string {
    return tier === "fully_workable" ? "Fully workable" : "Experimental";
  }
</script>

<script lang="ts">
  let { methods, active_method_id, open, onpick, onclose }: MethodDrawerProps = $props();

  let dialog_el: HTMLDialogElement | null = $state(null);

  // Open / close the native dialog based on the `open` prop. Native
  // <dialog> handles the Escape-to-close + backdrop click on click
  // (we attach a click handler below to close on click outside the
  // panel).
  $effect(() => {
    if (!dialog_el) return;
    if (open && !dialog_el.open) {
      dialog_el.showModal();
    } else if (!open && dialog_el.open) {
      dialog_el.close();
    }
  });

  const partitioned = $derived(partitionByValidity(methods));

  function handleBackdropClick(event: MouseEvent): void {
    // Native dialog reports a click on the backdrop with the click
    // target being the dialog element itself (not a child). Treat
    // that as a close request.
    if (event.target === dialog_el) {
      onclose();
    }
  }

  function handleDialogClose(): void {
    // Fired when the dialog closes via ESC or programmatically. Sync
    // parent state so a re-open works.
    onclose();
  }
</script>

<dialog
  bind:this={dialog_el}
  data-component="method-drawer"
  class="bg-transparent p-0 backdrop:bg-slate-900/40 backdrop:backdrop-blur-sm rounded-xl max-w-2xl w-full sm:w-[min(36rem,90vw)] max-h-[85vh]"
  onclick={handleBackdropClick}
  onclose={handleDialogClose}
>
  <div class="bg-surface rounded-xl shadow-xl overflow-hidden">
    <header class="flex items-center justify-between gap-2 px-5 py-3 border-b border-line">
      <h2 class="text-base font-semibold" style:color="var(--ink, #0f172a)">
        Choose a counting rule
      </h2>
      <button
        type="button"
        class="rounded-md border border-line bg-surface px-2 py-1 text-xs font-medium hover:bg-surface-sunken min-h-[36px]"
        style:color="var(--ink-muted, #64748b)"
        onclick={onclose}
        aria-label="Close picker"
      >
        Close
      </button>
    </header>

    <div class="overflow-y-auto max-h-[calc(85vh-3.5rem)] p-4 space-y-5">
      {#each ["fully_workable", "medium_validity"] as const as tier (tier)}
        {@const group = tier === "fully_workable" ? partitioned.fully_workable : partitioned.medium_validity}
        {#if group.length > 0}
          <section>
            <h3 class="text-xs font-semibold uppercase tracking-wide mb-2" style:color="var(--ink-muted, #64748b)">
              {validityTierLabel(tier)}
            </h3>
            <ul class="space-y-2">
              {#each group as m (m.id)}
                {@const is_active = m.id === active_method_id}
                <li>
                  <button
                    type="button"
                    class="w-full text-left rounded-md border p-3 transition-colors min-h-[44px] flex flex-col gap-1"
                    class:border-accent={is_active}
                    class:bg-surface-sunken={is_active}
                    class:border-line={!is_active}
                    class:bg-surface={!is_active}
                    class:hover:border-accent={!is_active}
                    data-method-id={m.id}
                    aria-pressed={is_active}
                    onclick={() => {
                      onpick(m.id);
                      onclose();
                    }}
                  >
                    <div class="flex items-baseline justify-between gap-2 flex-wrap">
                      <span class="font-semibold text-sm" style:color="var(--ink, #0f172a)">
                        {m.short_label ?? m.label}
                      </span>
                      <span
                        class="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded"
                        class:bg-emerald-50={tier === "fully_workable"}
                        class:text-emerald-700={tier === "fully_workable"}
                        class:bg-amber-50={tier === "medium_validity"}
                        class:text-amber-800={tier === "medium_validity"}
                      >
                        {validityBadgeText(tier)}
                      </span>
                    </div>
                    {#if m.headline}
                      <p class="text-xs" style:color="var(--ink-muted, #64748b)">
                        {m.headline}
                      </p>
                    {/if}
                  </button>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      {/each}
    </div>
  </div>
</dialog>
