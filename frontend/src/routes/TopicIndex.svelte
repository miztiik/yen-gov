<script lang="ts">
  // Topic index (/t).
  //
  // The Topic Front Door per ADR-0022. Lists every topic in the catalogue,
  // grouped by Seventh Schedule list (State / Concurrent / Union / N/A) so
  // the citizen can read the constitutional shape of the page directly: the
  // groups are ordered State -> Concurrent -> Union -> N/A, which is also
  // the order of "where does the lever live" -> "shared" -> "centre" ->
  // "process". Within each group, topics keep catalogue order (which the
  // hand-authored taxonomy already orders by citizen relevance).
  //
  // Render-only against the catalogue: each topic card carries its title,
  // ListBadge, summary, and an artifact-count line. Click goes to
  // /t/:topic (P3.3a).

  import {
    fetchTopicCatalogue,
    type TopicCatalogue,
    type CatalogueTopic,
    type SeventhScheduleList,
  } from "../lib/catalogue";
  import ListBadge from "../lib/ListBadge.svelte";
  import { url } from "../lib/url";

  let catalogue = $state<TopicCatalogue | null>(null);
  let load_error = $state<string | null>(null);
  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(e => (load_error = String(e)));

  // Render order for the four list groups. Empty groups are skipped at
  // render time, so adding a new "union" topic later automatically shows
  // the Union section without any code change here.
  const GROUP_ORDER: Array<{ list: SeventhScheduleList; label: string; blurb: string }> = [
    {
      list: "state",
      label: "State subjects",
      blurb: "Administered by state governments under the Seventh Schedule State List. The state is the primary decision-maker.",
    },
    {
      list: "concurrent",
      label: "Concurrent subjects",
      blurb: "Both Centre and states may legislate. Outcomes reflect the interplay of central scheme design and state implementation.",
    },
    {
      list: "union",
      label: "Union subjects",
      blurb: "Administered by the Government of India. State-level variation reflects implementation, geography, or historical investment \u2014 not policy authority.",
    },
    {
      list: "na",
      label: "Process topics",
      blurb: "Not a Seventh Schedule subject (e.g. elections themselves \u2014 the process by which governments are formed).",
    },
  ];

  function indicator_count(t: CatalogueTopic): number {
    return t.artifacts.filter(a => a.kind === "indicator").length;
  }
  function election_count(t: CatalogueTopic): number {
    return t.artifacts.filter(a => a.kind === "election").length;
  }

  const groups = $derived.by(() => {
    const c = catalogue;
    if (!c) return [];
    return GROUP_ORDER.map(g => ({
      ...g,
      topics: c.topics.filter(t => t.list === g.list),
    })).filter(g => g.topics.length > 0);
  });
</script>

<section class="p-4 sm:p-6 space-y-6 max-w-6xl">
  <header class="space-y-1">
    <h1 class="text-2xl font-semibold">Topics</h1>
    <p class="text-sm text-slate-600 max-w-3xl">
      Every dataset on yen-gov, organised by what the data is about — not
      by which government produced it. Topics are grouped by the Seventh
      Schedule list (State / Concurrent / Union) so the constitutional locus
      of decision-making is visible before you read any number.
    </p>
  </header>

  {#if load_error}
    <div class="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
      Failed to load topic catalogue: <code>{load_error}</code>
    </div>
  {:else if !catalogue}
    <p class="text-sm text-slate-500">Loading topic catalogue…</p>
  {:else if groups.length === 0}
    <p class="text-sm text-slate-500">No topics catalogued yet.</p>
  {:else}
    <div class="space-y-8">
      {#each groups as group (group.list)}
        <section class="space-y-3">
          <div class="flex items-baseline gap-2 flex-wrap">
            <h2 class="text-base font-semibold uppercase tracking-wide text-slate-700">
              {group.label}
            </h2>
            <ListBadge list={group.list} compact />
          </div>
          <p class="text-xs text-slate-500 max-w-3xl">{group.blurb}</p>
          <ul class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 list-none p-0 m-0">
            {#each group.topics as topic (topic.id)}
              {@const ind = indicator_count(topic)}
              {@const ele = election_count(topic)}
              <li>
                <a
                  href={url.topic(topic.id)}
                  class="block h-full rounded-lg border border-slate-200 bg-white p-4 hover:border-sky-400 hover:shadow-sm transition"
                >
                  <h3 class="text-sm font-semibold mb-1">{topic.title}</h3>
                  <p class="text-xs text-slate-600 line-clamp-3 mb-2">{topic.summary}</p>
                  <p class="text-[0.65rem] uppercase tracking-wide text-slate-500 tabular-nums">
                    {#if ind > 0}{ind} indicator{ind === 1 ? "" : "s"}{/if}
                    {#if ind > 0 && ele > 0} · {/if}
                    {#if ele > 0}{ele} election artifact{ele === 1 ? "" : "s"}{/if}
                    {#if ind === 0 && ele === 0}no artifacts yet{/if}
                  </p>
                </a>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
    </div>
  {/if}
</section>
