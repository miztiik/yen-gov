<script lang="ts">
  // EntityProfilePanel - generic 4-to-8-row facts panel per
  // §5.D.2 of TODO/20260614-three-ephemeral-ingests-plan.md
  // (Jony's "≥4 reuses earns the abstraction" rule applied
  // to entity-fact panels).
  //
  // Today the only consumer is the 2014 MP affidavit panel
  // mounted from Constituency.svelte. Future planned reuses:
  // party header strip, AC header strip, candidate detail card.
  //
  // The panel is intentionally minimal:
  //   * `title`                 the headline ("About this MP (2014 declaration)")
  //   * `rows`                  a small list of { label, value, hint? }
  //                             rendered as a definition-list
  //   * `provenance`            optional one-line attribution footer
  //   * `amber_banner`          optional copy that surfaces in an amber
  //                             pill above the rows when the data is
  //                             self-declared / not adjudicated etc.
  //   * `entity_kind`           cosmetic only (carried on a data-attr
  //                             for e2e/QA tooling); doesn't drive
  //                             any styling today.
  //
  // Renders nothing when `rows` is empty (caller's responsibility
  // to gate the mount).

  export interface ProfileRow {
    /** Citizen-readable label, e.g. "Education". */
    readonly label: string;
    /** Citizen-readable value, e.g. "Graduate Professional". */
    readonly value: string;
    /** Optional smaller-text suffix shown after the value, e.g.
     *  a unit annotation ("INR crore") or a methodology hint. */
    readonly hint?: string;
  }

  interface Props {
    title: string;
    rows: readonly ProfileRow[];
    provenance?: string;
    amber_banner?: string;
    entity_kind?: string;
  }

  const { title, rows, provenance, amber_banner, entity_kind }: Props =
    $props();
</script>

{#if rows.length > 0}
  <section
    class="rounded border border-slate-200 bg-white p-4"
    data-testid="entity-profile-panel"
    data-entity-kind={entity_kind ?? ""}
  >
    <header class="mb-2">
      <h2 class="text-sm font-semibold text-slate-800">{title}</h2>
    </header>

    {#if amber_banner}
      <p
        class="mb-3 inline-block rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-800"
        data-testid="entity-profile-panel-amber"
      >
        {amber_banner}
      </p>
    {/if}

    <dl
      class="grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-2"
      data-testid="entity-profile-panel-rows"
    >
      {#each rows as r (r.label)}
        <div class="flex flex-wrap items-baseline gap-x-2">
          <dt class="text-xs uppercase tracking-wide text-slate-500">
            {r.label}
          </dt>
          <dd class="text-sm text-slate-900">
            <span class="tabular-nums">{r.value}</span>
            {#if r.hint}
              <span class="ml-1 text-xs text-slate-500">{r.hint}</span>
            {/if}
          </dd>
        </div>
      {/each}
    </dl>

    {#if provenance}
      <p
        class="mt-3 text-xs text-slate-500"
        data-testid="entity-profile-panel-provenance"
      >
        {provenance}
      </p>
    {/if}
  </section>
{/if}
