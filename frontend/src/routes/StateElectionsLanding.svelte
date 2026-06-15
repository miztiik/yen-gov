<!--
  StateElectionsLanding - the per-state elections landing route mounted
  by R2 of TODO/20260615-state-election-event-page-redesign-plan.md
  (2026-06-15).

  Mounted at /<state>/elections/ (the bare path). Today this 404s; R2
  fills the gap so a citizen visiting /maharashtra/elections/ sees ONE
  page that lists every assembly + parliament event the state has on
  record, with year-as-link to the per-event detail page.

  Layout (plan Section 3):
   - Breadcrumb -> stateElectionsLandingCrumbs(state)
   - PageHeader "{State} elections"
   - Per-body latest-event hero (one card for assembly, one for parliament)
   - Two parallel tables (Vidhan Sabha / Lok Sabha), one row per event,
     year-as-link to /<state>/elections/<event_id>
   - Last-viewed badge per J-elevated-15 (read localStorage on mount;
     30-day expiry; render Last viewed badge next to matching year-link)
   - Cross-link "<- back to {state} welfare context" to /<state>

  Data: consumes fetchElectionEvents() + listEventsForState(catalogue,
  state_code) from ../lib/election-events; states.codeFromSlug for the
  slug -> ECI bridge. NO new loader.
-->
<script lang="ts">
  import { onMount } from "svelte";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import {
    fetchElectionEvents,
    listEventsForState,
    type ElectionEventRow,
    type ElectionEventsCatalogue,
  } from "../lib/election-events";
  import { states } from "../lib/states.svelte";
  import { link } from "../lib/links";
  import { stateElectionsLandingCrumbs } from "../lib/route-crumbs";
  import { readLastEvent, type LastEventMemory } from "../lib/elections/last-event-memory";
  import { SHARE_BASE } from "../lib/paths";

  interface Props {
    params: { state: string };
  }
  let { params }: Props = $props();

  let catalogue = $state<ElectionEventsCatalogue | null>(null);
  let catalogue_error = $state<string | null>(null);
  let last_viewed = $state<LastEventMemory | null>(null);

  onMount(() => {
    last_viewed = readLastEvent(params.state);
    fetchElectionEvents()
      .then((c) => {
        catalogue = c;
      })
      .catch((e: unknown) => {
        catalogue_error = e instanceof Error ? e.message : String(e);
      });
  });

  let state_code = $derived(states.codeFromSlug(params.state));
  let state_name = $derived(state_code ? states.name(state_code) : params.state);

  let assembly_events = $derived(
    catalogue && state_code
      ? listEventsForState(catalogue, state_code, "assembly")
      : [],
  );
  let parliament_events = $derived(
    catalogue && state_code
      ? listEventsForState(catalogue, state_code, "parliament")
      : [],
  );

  let latest_assembly = $derived<ElectionEventRow | null>(
    assembly_events.length > 0 ? assembly_events[0] : null,
  );
  let latest_parliament = $derived<ElectionEventRow | null>(
    parliament_events.length > 0 ? parliament_events[0] : null,
  );

  let crumbs = $derived(stateElectionsLandingCrumbs(params));

  function yearOf(ev: ElectionEventRow): string {
    return ev.polled_on.slice(0, 4);
  }

  function isLastViewed(ev: ElectionEventRow): boolean {
    return last_viewed?.event_id === ev.event_id;
  }

  // R7 (TODO/20260615-state-election-event-page-redesign-plan.md
  // J-elevated-14): OG card unfurl meta. Targets the latest assembly
  // event's share card when one exists; falls back to the latest
  // parliament event; falls back to a no-image-set state when the
  // catalogue is empty for this state. Generated PNG ships at
  // /share/{state-slug}/{event_id}.png via the build step.
  let og_card_event = $derived(latest_assembly ?? latest_parliament);
  let og_image_url = $derived(
    og_card_event
      ? `${SHARE_BASE}/${params.state}/${og_card_event.event_id}.png`
      : null,
  );
  let og_title = $derived(`${state_name} elections - yen-gov`);
  let og_description = $derived(
    `Every Assembly and Parliament election on record for ${state_name}, ` +
      `with year-as-link and a 30-day last-viewed memory.`,
  );
</script>

<svelte:head>
  <title>{state_name} elections - yen-gov</title>
  <meta property="og:title" content={og_title} />
  <meta property="og:description" content={og_description} />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={og_title} />
  <meta name="twitter:description" content={og_description} />
  {#if og_image_url}
    <meta property="og:image" content={og_image_url} />
    <meta name="twitter:image" content={og_image_url} />
  {/if}
</svelte:head>

<PageContainer width="wide">
  <Breadcrumb {crumbs} />

  {#if catalogue_error}
    <div
      class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
      data-testid="state-elections-landing-error"
    >
      Couldn't load: {catalogue_error}
    </div>
  {:else if catalogue == null}
    <div
      class="text-sm text-slate-400"
      data-testid="state-elections-landing-loading"
    >
      Loading...
    </div>
  {:else if state_code == null}
    <div
      class="text-sm text-slate-500"
      data-testid="state-elections-landing-state-notfound"
    >
      State "{params.state}" not found.
    </div>
  {:else}
    <header class="space-y-1">
      <h1
        class="text-2xl font-semibold text-slate-900"
        data-testid="state-elections-landing-header"
      >
        {state_name} elections
      </h1>
      <p class="text-sm text-slate-600">
        Every assembly and parliament election on record for {state_name},
        with the most recent first. Click a year to open that event.
      </p>
    </header>

    {#if assembly_events.length === 0 && parliament_events.length === 0}
      <div
        class="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"
        data-testid="state-elections-landing-empty"
      >
        No elections in the catalogue for {state_name} yet.
      </div>
    {/if}

    {#if latest_assembly || latest_parliament}
      <section
        class="grid gap-3 md:grid-cols-2"
        data-testid="state-elections-landing-latest"
      >
        {#if latest_assembly}
          {@const ev = latest_assembly}
          <a
            href={link.stateElection(params.state, ev.event_id)}
            class="rounded border border-slate-200 bg-white p-4 hover:border-sky-200 hover:bg-sky-50 transition-colors"
            data-testid="state-elections-landing-latest-assembly"
          >
            <div class="text-xs uppercase tracking-wide text-slate-500">
              Latest Vidhan Sabha
            </div>
            <div class="mt-1 text-base font-semibold text-slate-900">
              {state_name} Assembly {yearOf(ev)}
            </div>
            <div class="text-xs text-slate-500">{ev.display}</div>
          </a>
        {/if}
        {#if latest_parliament}
          {@const ev = latest_parliament}
          <a
            href={link.stateElection(params.state, ev.event_id)}
            class="rounded border border-slate-200 bg-white p-4 hover:border-sky-200 hover:bg-sky-50 transition-colors"
            data-testid="state-elections-landing-latest-parliament"
          >
            <div class="text-xs uppercase tracking-wide text-slate-500">
              Latest Lok Sabha (state slice)
            </div>
            <div class="mt-1 text-base font-semibold text-slate-900">
              {state_name} Parliament {yearOf(ev)}
            </div>
            <div class="text-xs text-slate-500">{ev.display}</div>
          </a>
        {/if}
      </section>
    {/if}

    {#if assembly_events.length > 0}
      <section
        class="space-y-2"
        data-testid="state-elections-landing-assembly-table"
      >
        <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-700">
          Vidhan Sabha ({assembly_events.length})
        </h2>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="text-left text-xs uppercase text-slate-500">
              <tr>
                <th class="py-2">Year</th>
                <th class="py-2">Event</th>
                <th class="py-2">Polled on</th>
                <th class="py-2"></th>
              </tr>
            </thead>
            <tbody class="divide-y">
              {#each assembly_events as ev (ev.event_id)}
                <tr
                  class="hover:bg-slate-50"
                  data-testid={`state-elections-landing-assembly-row-${ev.event_id}`}
                >
                  <td class="py-2 font-mono text-sky-700">
                    <a
                      href={link.stateElection(params.state, ev.event_id)}
                      class="hover:underline"
                      data-testid={`state-elections-landing-assembly-link-${ev.event_id}`}
                    >
                      {yearOf(ev)}
                    </a>
                  </td>
                  <td class="py-2 text-slate-600">{ev.display}</td>
                  <td class="py-2 font-mono text-xs text-slate-500">
                    {ev.polled_on}
                  </td>
                  <td class="py-2 text-right">
                    {#if isLastViewed(ev)}
                      <span
                        class="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium text-slate-500 ring-1 ring-slate-200"
                        data-testid={`state-elections-landing-last-viewed-${ev.event_id}`}
                      >Last viewed</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}

    {#if parliament_events.length > 0}
      <section
        class="space-y-2"
        data-testid="state-elections-landing-parliament-table"
      >
        <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-700">
          Lok Sabha ({parliament_events.length})
        </h2>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="text-left text-xs uppercase text-slate-500">
              <tr>
                <th class="py-2">Year</th>
                <th class="py-2">Event</th>
                <th class="py-2">Polled on</th>
                <th class="py-2"></th>
              </tr>
            </thead>
            <tbody class="divide-y">
              {#each parliament_events as ev (ev.event_id)}
                <tr
                  class="hover:bg-slate-50"
                  data-testid={`state-elections-landing-parliament-row-${ev.event_id}`}
                >
                  <td class="py-2 font-mono text-sky-700">
                    <a
                      href={link.stateElection(params.state, ev.event_id)}
                      class="hover:underline"
                      data-testid={`state-elections-landing-parliament-link-${ev.event_id}`}
                    >
                      {yearOf(ev)}
                    </a>
                  </td>
                  <td class="py-2 text-slate-600">{ev.display}</td>
                  <td class="py-2 font-mono text-xs text-slate-500">
                    {ev.polled_on}
                  </td>
                  <td class="py-2 text-right">
                    {#if isLastViewed(ev)}
                      <span
                        class="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium text-slate-500 ring-1 ring-slate-200"
                        data-testid={`state-elections-landing-last-viewed-${ev.event_id}`}
                      >Last viewed</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}

    <p class="text-xs text-slate-500">
      <a
        href={link.stateHub(params.state)}
        class="text-sky-700 hover:underline"
        data-testid="state-elections-landing-state-hub-link"
      >&larr; Back to {state_name} welfare context</a>
    </p>
  {/if}
</PageContainer>
