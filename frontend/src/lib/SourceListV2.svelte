<script lang="ts">
  // SourceList v2 — citizen-facing chart/page footer disclosure.
  //
  // This is the **render surface** for the v2 contract that already
  // ships under `frontend/src/lib/source-list-v2/` (types + format
  // helpers + format.test.ts, 19 cases). The contract is the
  // 11-column citation ledger per ADR-0032 (taxonomy.sources v2.0).
  //
  // Phase 1.4 of TODO/20260518-frontend-charting-modernisation-plan.md.
  //
  // R-08 — Branch-by-Abstraction. **Zero callers** in this PR. The
  // existing v1 `SourceList.svelte` (consuming `SourceRef` with
  // `url` + `fetched_at`) continues to ship to every citizen page
  // untouched. Per-caller migration happens once the data layer
  // (`frontend/src/lib/data.ts` loaders, or a view-model) emits
  // `SourceV2Row[]` end-to-end. Until then this component is
  // type-check green and unit-helper backed but uncalled.
  //
  // R-24 — fetch-telemetry fields (`fetched_at`, `first_fetched_at`,
  // `last_seen_at`, `date_accessed`, `content_hash`, `url`,
  // `url_download`) are FORBIDDEN in this surface. The type system
  // is the only seam — `SourceV2Row` doesn't carry them, and the
  // collapsed / expanded helpers refuse to compose them. The
  // contract test `frontend/src/contracts/sources-v2-shape.test.ts`
  // is the drift detector.
  //
  // No `aria-*` attributes per CLAUDE.md §0 (a11y descoped) — the
  // triangle / expanded-list pattern uses visible affordances only.

  import {
    formatCollapsedSummary,
    formatExpandedDisclosure,
    verificationMethodRank,
    type SourceV2Row,
  } from "./source-list-v2";

  interface Props {
    /** v2.0 ledger rows. Resolved upstream from `taxonomy.sources`
     *  via the manifest-registered `table_id` (R-28). */
    sources: readonly SourceV2Row[];
    /** Optional caller-supplied schema version for the host artifact
     *  (e.g. an indicator JSON's `$schema_version`). Surfaces next to
     *  the count so curators can spot drift. Hidden when null. */
    schema_version?: string | null;
    /** Optional initial-expansion override. Defaults to false (dense
     *  chart pages default collapsed, per the plan). */
    start_open?: boolean;
  }
  let { sources, schema_version = null, start_open = false }: Props = $props();

  // svelte-ignore state_referenced_locally
  let open = $state(start_open);

  // Sort by verification-method trust ordering so the citizen sees
  // the strongest evidence first (live-fetch > archived-snapshot >
  // transcribed > editorial). Stable order — equal-rank rows keep
  // their input order, which preserves the upstream Parquet sort.
  const sortedSources = $derived(
    [...sources].sort(
      (a, b) =>
        verificationMethodRank(a.verification_method) -
        verificationMethodRank(b.verification_method),
    ),
  );

  const collapsedRows = $derived(sortedSources.map(formatCollapsedSummary));
  const expandedRows = $derived(sortedSources.map(formatExpandedDisclosure));

  // Citizen-readable labels for the locked enums. These live on the
  // component rather than the helpers because they are *render-time*
  // text, not data — and a Hindi/regional translation later swaps
  // here, not in `format.ts`.
  const VERIFICATION_LABEL: Record<
    SourceV2Row["verification_method"],
    string
  > = {
    "live-fetch": "Live-fetched from publisher",
    "archived-snapshot": "From archived snapshot",
    transcribed: "Transcribed by hand",
    editorial: "Editorial / yen-gov derived",
  };

  const CONFIDENCE_LABEL: Record<SourceV2Row["confidence_tier"], string> = {
    gold: "Gold — issuing authority",
    silver: "Silver — reputable republisher",
    bronze: "Bronze — single-paper / unverified",
  };

  const LICENSE_LABEL: Record<SourceV2Row["license"], string> = {
    "OGL-IN-1.0": "OGL India v1.0",
    "CC-BY-4.0": "CC BY 4.0",
    "CC0-1.0": "CC0 1.0",
    "public-domain": "Public domain",
    "unknown-public": "Public (license unknown)",
    internal: "yen-gov internal",
  };
</script>

<div class="text-xs text-slate-500" data-component="source-list-v2">
  <button
    type="button"
    class="inline-flex items-center gap-1 hover:text-slate-700"
    onclick={() => (open = !open)}
  >
    <span class="inline-block w-3 text-center font-mono leading-none">
      {open ? "▾" : "▸"}
    </span>
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
      <ul class="mt-2 space-y-3 list-none">
        {#each expandedRows as row, i}
          {@const collapsed = collapsedRows[i]}
          <li
            class="border-l-2 border-slate-200 pl-2"
            data-confidence-tier={row.confidence_tier}
            data-verification-method={row.verification_method}
          >
            <p class="text-slate-700">
              <span class="font-medium">{collapsed.producer}</span>
              <span class="text-slate-400">·</span>
              <span>{collapsed.authority_label}</span>
              {#if collapsed.vintage}
                <span class="text-slate-400">·</span>
                <span class="font-mono text-[11px]">{collapsed.vintage}</span>
              {/if}
            </p>
            <p class="text-slate-500 text-[11px] mt-0.5">{row.citation}</p>
            <p class="text-slate-400 text-[10px] mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
              <span>{CONFIDENCE_LABEL[row.confidence_tier]}</span>
              <span>·</span>
              <span>{VERIFICATION_LABEL[row.verification_method]}</span>
              <span>·</span>
              <span>{LICENSE_LABEL[row.license]}</span>
              {#if row.url_main}
                <span>·</span>
                <a
                  class="text-blue-600 hover:underline"
                  href={row.url_main}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={row.url_main}
                >
                  Publisher page
                </a>
              {/if}
            </p>
            {#if row.notes}
              <p class="text-slate-400 text-[10px] italic mt-0.5">{row.notes}</p>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</div>
