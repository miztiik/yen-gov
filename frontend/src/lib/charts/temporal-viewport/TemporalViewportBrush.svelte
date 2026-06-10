<script lang="ts" module>
  import type { TemporalPreset } from "./types";

  /**
   * Citizen-facing preset labels. Closed map keyed by preset id.
   * Module-scoped so `TemporalViewportBrush.test.ts` can import it.
   */
  export function presetLabel(p: TemporalPreset, recent_count: number): string {
    switch (p) {
      case "all": return "All";
      case "recent": return `Recent ${recent_count}`;
      case "5y": return "5y";
      case "10y": return "10y";
      case "25y": return "25y";
    }
  }
</script>

<script lang="ts">
  // TemporalViewportBrush — preset + per-period strip selection
  // primitive (Phase 1.5 component slice).
  //
  // Per `docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md`
  // Phase 1.5 — "below the chart, a compact overview strip … allows
  // dragging/resizing the visible window" + "Presets: All, Recent,
  // 10y, 25y".
  //
  // Scope of this component (v1):
  //
  //   - Presets row (closed-enum vocabulary `KNOWN_PRESETS`).
  //   - Reset (≡ preset "all", spelt as a separate affordance for
  //     citizen visibility per plan: "Reset control returns to full
  //     range").
  //   - Period-strip selection: click first period for "from", click
  //     second for "to". Shift+click extends from the existing
  //     anchor. No drag handles, no pointer capture, no scroll
  //     containers — a real overview-strip with draggable handles is
  //     a follow-up if/when the analytics warrant it.
  //
  // Scope explicitly EXCLUDED (per R-16):
  //
  //   - Per-renderer adoption (StackedTrendV2, fiscal/economy lines,
  //     ministerial Gantt). Those ship as separate PRs that import
  //     this component.
  //   - URL serialisation. Window state is local to the component
  //     unless the parent passes a controlled `window` + change
  //     handler. Routes with stable editorial copy can serialise
  //     under ADR-0028 path-segment grammar (e.g.
  //     `/elections/parliament/since-1977`). NEVER query strings or
  //     matrix URIs (R-07).
  //
  // Doctrine ties:
  //
  //   - CLAUDE.md §0 a11y descoped: no `aria-*`, no `role`. Visible
  //     affordances only.
  //   - CLAUDE.md §10 closed enums: preset chips render strictly
  //     from `KNOWN_PRESETS`. Unknown presets passed by a parent are
  //     silently dropped.
  //   - R-07: this primitive carries NO knowledge of routing; the
  //     parent owns URL grammar.
  //   - R-16: brush component → first adopter (StackedTrendV2) is a
  //     separate PR.
  //
  // Test seams:
  //
  //   - `data-component="temporal-brush"` on root.
  //   - `data-domain-kind` on root.
  //   - `data-preset` on every preset chip.
  //   - `data-period-id`, `data-selected`, `data-in-window` on every
  //     strip cell.
  //   - `data-slot="presets" | "strip" | "reset"`.
  //   - Window-state assertions surface via `data-window-from` /
  //     `data-window-to` / `data-is-full` on the root.

  import {
    KNOWN_PRESETS,
    clampWindow,
    fullWindow,
    isFullWindow,
    presetWindow,
    windowIndices,
  } from "./helpers";
  import type {
    TemporalDomain,
    TemporalWindow,
  } from "./types";
  // `TemporalPreset` already imported by the `<script module>` block
  // above; both scripts share the same module file so re-importing
  // would fail with "Duplicate identifier".

  interface Props {
    /** The temporal domain to navigate. Built by the adapter via
     *  `buildDomain(period_ids, domain_kind)`. */
    domain: TemporalDomain;
    /** Currently selected window. If omitted, the brush manages its
     *  own state internally starting at `fullWindow(domain)`. */
    window?: TemporalWindow | null;
    /** Subset of `KNOWN_PRESETS` to surface. Defaults to all five.
     *  Year-derivable presets (`5y` / `10y` / `25y`) auto-hide when
     *  the domain has no `max_year` (election cycles / custom). */
    allowed_presets?: readonly TemporalPreset[];
    /** Optional `recent` preset window size. Default 5. */
    recent_count?: number;
    /** Optional citizen-facing per-period labels keyed by period id.
     *  Falls back to the period_id itself when missing — adapters
     *  pass the same period_label used in the chart axis. */
    period_labels?: Readonly<Record<string, string>> | null;
    /** Fired whenever the window changes (preset click, reset, or
     *  strip selection). */
    on_window_change?: (
      next: TemporalWindow,
      meta: { reason: "preset" | "reset" | "strip"; preset?: TemporalPreset },
    ) => void;
  }

  const {
    domain,
    window: external_window = null,
    allowed_presets = KNOWN_PRESETS,
    recent_count = 5,
    period_labels = null,
    on_window_change,
  }: Props = $props();

  // Internal state mirror. Used only when the parent does NOT control
  // the window. When external_window is provided we surface it
  // verbatim and ignore the mirror.
  //
  // Initialised to `null` and seeded lazily in the `$effect` below
  // (with the effective domain at the time of first run + on every
  // stale-id recovery). This avoids Svelte 5's
  // `state_referenced_locally` warning that fires when a `$state`
  // initial value reads a prop directly.
  let internal_window: TemporalWindow | null = $state(null);

  // Seed on first run; re-seed if the parent swaps the domain to a
  // wholly new set of period_ids — the previous window's ids would
  // be stale.
  $effect(() => {
    if (internal_window === null) {
      internal_window = fullWindow(domain);
      return;
    }
    const probe = windowIndices(internal_window, domain);
    if (probe.from_idx === -1 || probe.to_idx === -1) {
      internal_window = fullWindow(domain);
    }
  });

  const effective_window = $derived(
    external_window ?? internal_window ?? fullWindow(domain),
  );

  const clamped = $derived(clampWindow(effective_window, domain));
  const indices = $derived(windowIndices(clamped, domain));
  const is_full = $derived(isFullWindow(clamped, domain));

  // Hide year-derivable presets when the domain has no parseable
  // year (election_cycle / custom dimensions). `all` and `recent`
  // remain.
  const visible_presets = $derived.by<readonly TemporalPreset[]>(() => {
    const seen = new Set<TemporalPreset>();
    const out: TemporalPreset[] = [];
    for (const p of allowed_presets) {
      if (!KNOWN_PRESETS.includes(p)) continue;
      if (seen.has(p)) continue;
      seen.add(p);
      if ((p === "5y" || p === "10y" || p === "25y") && domain.max_year === null) continue;
      out.push(p);
    }
    return out;
  });

  // Track the first strip click so the second click closes the
  // window. Reset on every committed preset / reset.
  let strip_anchor_idx: number | null = $state(null);

  function applyWindow(
    next: TemporalWindow,
    reason: "preset" | "reset" | "strip",
    preset?: TemporalPreset,
  ): void {
    const safe = clampWindow(next, domain);
    if (external_window === null) {
      internal_window = safe;
    }
    on_window_change?.(safe, { reason, preset });
  }

  function handlePreset(p: TemporalPreset): void {
    const next = presetWindow(p, domain, { recent_count });
    if (next === null) return; // year-derivable preset on year-less domain
    strip_anchor_idx = null;
    applyWindow(next, "preset", p);
  }

  function handleReset(): void {
    strip_anchor_idx = null;
    applyWindow(fullWindow(domain), "reset");
  }

  function handleStripClick(idx: number, event: MouseEvent): void {
    if (event.shiftKey && strip_anchor_idx !== null) {
      const lo = Math.min(strip_anchor_idx, idx);
      const hi = Math.max(strip_anchor_idx, idx);
      applyWindow(
        {
          from_period_id: domain.ordered_period_ids[lo]!,
          to_period_id: domain.ordered_period_ids[hi]!,
        },
        "strip",
      );
      strip_anchor_idx = null;
      return;
    }
    if (strip_anchor_idx === null) {
      strip_anchor_idx = idx;
      applyWindow(
        {
          from_period_id: domain.ordered_period_ids[idx]!,
          to_period_id: domain.ordered_period_ids[idx]!,
        },
        "strip",
      );
      return;
    }
    const lo = Math.min(strip_anchor_idx, idx);
    const hi = Math.max(strip_anchor_idx, idx);
    applyWindow(
      {
        from_period_id: domain.ordered_period_ids[lo]!,
        to_period_id: domain.ordered_period_ids[hi]!,
      },
      "strip",
    );
    strip_anchor_idx = null;
  }

  function labelFor(period_id: string): string {
    return period_labels?.[period_id] ?? period_id;
  }
</script>

<div
  class="temporal-brush"
  data-component="temporal-brush"
  data-domain-kind={domain.domain_kind}
  data-window-from={clamped.from_period_id}
  data-window-to={clamped.to_period_id}
  data-is-full={is_full ? "true" : "false"}
>
  {#if visible_presets.length > 0}
    <div class="temporal-brush__presets" data-slot="presets">
      {#each visible_presets as p (p)}
        <button
          type="button"
          class="temporal-brush__chip"
          data-preset={p}
          onclick={() => handlePreset(p)}
        >
          {presetLabel(p, recent_count)}
        </button>
      {/each}
      <button
        type="button"
        class="temporal-brush__chip temporal-brush__chip--reset"
        data-slot="reset"
        onclick={handleReset}
        disabled={is_full}
      >
        Reset
      </button>
    </div>
  {/if}

  <ol class="temporal-brush__strip" data-slot="strip">
    {#each domain.ordered_period_ids as pid, i (pid)}
      {@const in_window = indices.from_idx !== -1
        && i >= indices.from_idx
        && i <= indices.to_idx}
      {@const selected = pid === clamped.from_period_id
        || pid === clamped.to_period_id}
      <li class="temporal-brush__strip-item">
        <button
          type="button"
          class="temporal-brush__cell"
          data-period-id={pid}
          data-in-window={in_window ? "true" : "false"}
          data-selected={selected ? "true" : "false"}
          onclick={(e) => handleStripClick(i, e)}
          title={labelFor(pid)}
        >
          <span class="temporal-brush__cell-label">{labelFor(pid)}</span>
        </button>
      </li>
    {/each}
  </ol>
</div>

<style>
  /* Layout-only. Visual styling tokens are deferred until the first
     route adopter ships so we can tune to that route's typography. */
  .temporal-brush {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    font-size: 0.8125rem;
  }
  .temporal-brush__presets {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }
  .temporal-brush__chip {
    padding: 0.125rem 0.5rem;
    border-radius: 999px;
    border: 1px solid rgb(203 213 225); /* slate-300 */
    background: rgb(248 250 252); /* slate-50 */
    cursor: pointer;
    font-size: 0.75rem;
    color: rgb(15 23 42); /* slate-900 */
  }
  .temporal-brush__chip:hover {
    background: rgb(226 232 240); /* slate-200 */
  }
  .temporal-brush__chip:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .temporal-brush__strip {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.125rem;
  }
  .temporal-brush__strip-item {
    margin: 0;
    padding: 0;
  }
  .temporal-brush__cell {
    min-width: 2.25rem;
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    border: 1px solid transparent;
    background: rgb(241 245 249); /* slate-100 */
    cursor: pointer;
    font-size: 0.6875rem;
    color: rgb(71 85 105); /* slate-600 */
    text-align: center;
  }
  .temporal-brush__cell[data-in-window="true"] {
    background: rgb(186 230 253); /* sky-200 */
    color: rgb(12 74 110); /* sky-900 */
  }
  .temporal-brush__cell[data-selected="true"] {
    border-color: rgb(14 116 144); /* cyan-700 */
    font-weight: 600;
  }
  .temporal-brush__cell-label {
    display: inline-block;
    white-space: nowrap;
  }
</style>
