<script lang="ts">
  // Row C of TODO/20260617-party-page-polish-and-cdn-config-plan.md
  // (Jony P2). The page-foot provenance block for /parties/<slug>.
  //
  // Replaces the five inline per-card "Source: ..." pill rows
  // (the retired `SourceList` mounts) + the standalone "About this
  // page" link with ONE quiet foot block: a mapped sentence that
  // states each publisher ONCE (ECI for the data cards, Wikipedia for
  // alliance line-ups), every name still clickable (Holy Law #9), then
  // the single "About this page ->" link.
  //
  // The grouping is owned by the pure `buildProvenanceFooterClauses`
  // projector; this component is presentation only. The per-pill
  // link/plain rendering MIRRORS `../sources/SourceList.svelte` so the
  // styling is identical: a slate-700 link (target=_blank) with the
  // optional vintage suffix when the pill carries a url, or a plain
  // slate-700 span when it does not (never a fabricated link).
  //
  // Whitespace note: the clause/pill tokens are glued tight on each
  // template line (no stray newlines inside the loop body) so the
  // rendered sentence reads "<Label A>: <pubs>. <Label B>: <pubs>."
  // without spurious spaces around the punctuation.

  import type { PartyProvenance } from "../view-models/party-sources";
  import { buildProvenanceFooterClauses } from "./party-provenance-footer-model";
  import { docsUrl } from "../repo";

  interface Props {
    /** Per-card publisher-pill envelope from the party view-model
     *  (`view_model.provenance`). */
    provenance: PartyProvenance;
  }

  let { provenance }: Props = $props();

  const clauses = $derived(buildProvenanceFooterClauses(provenance));
</script>

{#if clauses.length > 0}
  <p
    class="mt-8 text-[11px] text-slate-400 leading-tight"
    data-testid="party-provenance-footer"
  >
    {#each clauses as clause, ci (clause.label)}{#if ci > 0}<span>.</span>{" "}{/if}<span>{clause.label}:</span>{" "}{#each clause.pills as pill, pi (pill.label)}{#if pi > 0}<span class="text-slate-300"> &middot; </span>{/if}{#if pill.url}<a
          class="text-slate-700 hover:underline"
          href={pill.url}
          target="_blank"
          rel="noopener noreferrer"
          title={pill.label}
        >{pill.label}{pill.vintage_summary ? ` (${pill.vintage_summary})` : ""}</a>{:else}<span class="text-slate-700">{pill.label}{pill.vintage_summary ? ` (${pill.vintage_summary})` : ""}</span>{/if}{/each}{/each}<span>.</span>
  </p>
{/if}

<!--
  The single "About this page" link, lifted verbatim from Party.svelte's
  retired standalone footer. Points at the GitHub-rendered concept doc
  via the `docsUrl()` seam (no in-app `/docs/concepts/:slug` route
  exists - same pattern as `CountingMethodDoc.svelte` + `Psephlab.svelte`).
  Always renders (page-level coverage affordance), independent of whether
  any publisher pill resolved.
-->
<p class="mt-8 text-sm text-slate-400">
  <a
    href={docsUrl("docs/concepts/party-page-coverage.md")}
    target="_blank"
    rel="noreferrer"
    class="hover:underline"
    data-testid="party-page-coverage-link"
  >About this page -&gt;</a>
</p>
