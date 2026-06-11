<script lang="ts">
  // SourceList: the post-v3.1 publisher-pill footer for any chart card.
  //
  // Renders one pill per (producer x series_family), grouped at the
  // view-model layer via `dedupeToPills(rows)`. Plain-text middot
  // separators, NO chip backgrounds, NO border, NO chevron, NO
  // expand-collapse for the citizen-side. Empty pill array renders
  // nothing (no row, no whitespace) - per the Jony + Citizen verdict
  // 2026-06-11.
  //
  // The info-icon ("About this data") is OWNED BY `AboutThisData.svelte`,
  // not this component. The pill row always renders inline; the icon
  // expansion lives in `AboutThisData` alongside methodology, scope,
  // caveats, methodology breaks, full citation list. Concern separation.
  //
  // The "+N more" affordance: when pills.length > 3, the first 3 render
  // inline + a `+N more` button. Clicking the button toggles an inline
  // expansion below the truncated row showing every pill. No overlay,
  // no popover, no platform back-swipe interference (Jony rule).
  //
  // Doctrine: see frontend/src/lib/sources/README.md and the inline
  // ADR `citation-ledger-5col` in docs/concepts/data-provenance.md.

  import type { PublisherPill } from "./types";

  interface Props {
    /** Deduped publisher pills, produced by `dedupeToPills(rows)` upstream. */
    pills: readonly PublisherPill[];
    /** Maximum pills to render inline before collapsing the tail behind
     *  a "+N more" affordance. Defaults to 3 per Jony's mid-tier-Android
     *  density rule. Callers can override (e.g. IndicatorDoc page might
     *  want unlimited inline). */
    max_inline?: number;
  }

  let { pills, max_inline = 3 }: Props = $props();

  let show_all = $state(false);

  // Whether to render the tail collapsed behind a "+N more" link.
  const overflow = $derived(pills.length > max_inline);
  const visible = $derived(
    overflow && !show_all ? pills.slice(0, max_inline) : pills,
  );
  const hidden_count = $derived(
    overflow && !show_all ? pills.length - max_inline : 0,
  );
</script>

{#if pills.length > 0}
  <p class="text-[11px] text-slate-400 leading-tight">
    <span>Source:</span>
    {#each visible as pill, i (pill.label + pill.vintage_summary)}
      {#if i > 0}<span class="text-slate-300"> &middot; </span>{/if}
      {#if pill.url}
        <a
          class="text-slate-700 hover:underline"
          href={pill.url}
          target="_blank"
          rel="noopener noreferrer"
          title={pill.label}
        >{pill.label}{pill.vintage_summary ? ` (${pill.vintage_summary})` : ""}</a>
      {:else}
        <span class="text-slate-700">{pill.label}{pill.vintage_summary ? ` (${pill.vintage_summary})` : ""}</span>
      {/if}
    {/each}
    {#if hidden_count > 0}
      <span class="text-slate-300"> &middot; </span>
      <button
        type="button"
        class="text-slate-500 hover:underline"
        onclick={() => (show_all = true)}
      >+{hidden_count} more</button>
    {/if}
  </p>
{/if}
