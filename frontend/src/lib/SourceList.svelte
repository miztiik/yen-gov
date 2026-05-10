<script lang="ts">
  // Compact, expandable provenance footer. Renders the `sources` array
  // (per CLAUDE.md §12) as a collapsed count by default; clicking expands
  // to a list of upstream URLs with `fetched_at` timestamps. Used in
  // StateOverview to demote provenance from a top-level KPI tile to an
  // on-demand disclosure.
  import type { SourceRef } from "./data";

  interface Props {
    sources: SourceRef[];
    /** Optional schema version to surface alongside provenance. Hidden when null. */
    schema_version?: string | null;
  }
  let { sources, schema_version = null }: Props = $props();

  let open = $state(false);

  function host(url: string): string {
    try { return new URL(url).host; } catch { return url; }
  }
  function fmt(ts: string): string {
    // Render as YYYY-MM-DD HH:mm UTC (drop seconds + Z noise for the tooltip).
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return d.toISOString().replace("T", " ").slice(0, 16) + " UTC";
  }
</script>

<div class="text-xs text-slate-500">
  <button
    type="button"
    class="inline-flex items-center gap-1 hover:text-slate-700"
    aria-expanded={open}
    onclick={() => (open = !open)}
  >
    <span class="inline-block w-3 text-center font-mono leading-none">{open ? "▾" : "▸"}</span>
    <span>
      Sources ({sources.length})
      {#if schema_version}
        <span class="text-slate-400">· schema v{schema_version}</span>
      {/if}
    </span>
  </button>
  {#if open}
    {#if sources.length === 0}
      <p class="mt-2 italic text-slate-400">
        Hand-authored — see commit history for rationale.
      </p>
    {:else}
      <ul class="mt-2 space-y-1 list-none">
        {#each sources as s}
          <li class="flex items-baseline gap-2">
            <a class="text-blue-600 hover:underline truncate" href={s.url} target="_blank" rel="noopener noreferrer" title={s.url}>
              {host(s.url)}
            </a>
            <span class="text-slate-400 font-mono text-[10px]">{fmt(s.fetched_at)}</span>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</div>
