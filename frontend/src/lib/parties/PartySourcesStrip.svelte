<script lang="ts">
  // PR-9 of TODO/20260614-party-page-reimagination-plan.md - section 11.
  //
  // Bottom-of-page source-pill strip: a collapsed <details> summary
  // ("Sources for this page (N) - Producer A, Producer B...") that
  // expands to a 4-column table (Producer / Title / Vintage / Used in).
  //
  // Renders nothing when `strip.total_count === 0` - the page-level
  // empty state for a sentinel-party / no-data view.
  //
  // Citizen-facing copy is built by `buildPartyProvenance`; this
  // component is presentation-only.

  import type { PartySourcesStrip } from "../view-models/party-sources";

  interface Props {
    strip: PartySourcesStrip;
  }

  let { strip }: Props = $props();
</script>

{#if strip.total_count > 0}
  <details
    class="mt-8 border-t border-slate-200 pt-4 text-sm text-slate-600"
    data-testid="party-sources-strip"
  >
    <summary
      class="cursor-pointer font-medium text-slate-700 hover:text-slate-900"
    >
      Sources for this page ({strip.total_count}) - {strip.producer_summary}
    </summary>
    <div class="mt-3 overflow-x-auto">
      <table class="w-full border-collapse text-xs">
        <thead>
          <tr class="border-b border-slate-300 text-left text-slate-500">
            <th class="py-2 pr-4 font-medium">Producer</th>
            <th class="py-2 pr-4 font-medium">Title</th>
            <th class="py-2 pr-4 font-medium">Vintage</th>
            <th class="py-2 pr-4 font-medium">Used in</th>
          </tr>
        </thead>
        <tbody>
          {#each strip.all as src (src.source_id)}
            <tr
              class="border-b border-slate-100 align-top"
              data-source-id={src.source_id}
            >
              <td class="py-2 pr-4 text-slate-700">{src.producer}</td>
              <td class="py-2 pr-4 text-slate-600">{src.title}</td>
              <td class="py-2 pr-4 text-slate-500">
                {#if src.url}
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="hover:text-blue-700 hover:underline"
                  >
                    {src.vintage}
                  </a>
                {:else}
                  {src.vintage}
                {/if}
              </td>
              <td class="py-2 pr-4 text-slate-500">
                {src.used_in.join(", ")}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </details>
{/if}
