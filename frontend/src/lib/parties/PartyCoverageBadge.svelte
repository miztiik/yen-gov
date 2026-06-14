<script lang="ts">
  // PR-9 of TODO/20260614-party-page-reimagination-plan.md - section 11.
  //
  // Per-card coverage badge: a one-line italic caption rendered
  // directly under the matching card (Parliament chart, State
  // Assembly chart, Strongholds, Current Strength, Alliance Context).
  // Text is built by `buildPartyProvenance` in
  // `frontend/src/lib/view-models/party-sources.ts`; an empty string
  // suppresses the entire <p>. Holy Law #9 (provenance is mandatory).

  interface Props {
    text: string;
  }

  let { text }: Props = $props();
</script>

{#if text}
  <p
    class="text-xs italic text-slate-400 mt-2"
    data-testid="party-coverage-badge"
  >
    {text}
  </p>
{/if}
