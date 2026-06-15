<script module lang="ts">
  /**
   * Parties index (`/parties`) - PR-3 of
   * TODO/20260612-party-rendering-and-party-pages-plan.md.
   *
   * Replaces the PR-0 stub with the full alphabetical+chip+search
   * surface. The page reads `datasets/data/entities/parties.csv` via
   * `loadAllParties()` (view-models/parties.ts), sorts it server-side
   * (DuckDB `ORDER BY lower(short)`), then runs three client-side
   * filters in user input order: search box -> recognition chip ->
   * group-by-letter. Sentinels (IND, NOTA) render in a "Special"
   * section above 'A'; UNK is filtered out at the loader boundary
   * because no `/parties/<unk>` page exists.
   *
   * The 3 pure helpers (`groupByLetter`, `filterParties`,
   * `recognitionLabel`) live in this `<script module>` block so the
   * vitest pins the contract without mounting Svelte; the Svelte
   * template wires the `<input>` + `<button>` events to those
   * reducers. Same precedent as PartyPill.svelte's PR-1
   * `tooltipReducer` extraction.
   */
  import type { PartySummary } from "../lib/view-models/parties";

  /** A single bucket in the alphabetical view: either the
   *  pre-alphabetical "Special" bucket (sentinels) or one of A-Z. */
  export interface PartyLetterBucket {
    /** Display heading for the section ("\u2605 Special" or "A".."Z"). */
    letter: string;
    /** Anchor id used by the letter-rail jump links. Always lowercased
     *  ASCII; for the sentinel bucket the anchor is "special". */
    anchor: string;
    /** Rows that belong to this bucket, in the input order. */
    parties: PartySummary[];
  }

  /** Recognition-scope filter the chip row drives. `"all"` is the
   *  default pass-through. The three named buckets map to the
   *  `recognition_scope` enum values that appear on parties.csv. */
  export type RecognitionFilter =
    | "all"
    | "national"
    | "state"
    | "unrecognised";

  /** Display label for the recognition chip / inline row tag. Plain
   *  citizen-readable strings; the chip rail + each row's inline
   *  status badge both call this so the labels stay aligned. */
  export function recognitionLabel(scope: string): string {
    switch (scope) {
      case "national":
        return "National";
      case "state":
        return "State";
      case "unrecognised_registered":
        return "Unrecognised";
      case "defunct":
        return "Defunct";
      case "sentinel":
        return "Special";
      default:
        return "";
    }
  }

  /** Pure: does this party row match the recognition-chip selection?
   *  "all" always passes. The chip names map to recognition_scope
   *  values one-to-one. Defunct + sentinel rows fall through under
   *  "all" only - the named chips deliberately narrow. */
  function matchesRecognition(
    row: PartySummary,
    filter: RecognitionFilter,
  ): boolean {
    if (filter === "all") return true;
    if (filter === "national") return row.recognition_scope === "national";
    if (filter === "state") return row.recognition_scope === "state";
    return row.recognition_scope === "unrecognised_registered";
  }

  /** Pure: case-insensitive substring search against
   *  `short` + `full` + `aliases`. The aliases column is the RAW
   *  pipe-delimited string (e.g. `"AAAAP|AAAP"`); a substring search
   *  hits the pipe-joined form correctly so callers do NOT need to
   *  pre-split. Empty query string returns the input untouched. */
  export function filterParties(
    parties: PartySummary[],
    query: string,
    recognition: RecognitionFilter,
  ): PartySummary[] {
    const q = query.trim().toLowerCase();
    const out: PartySummary[] = [];
    for (const row of parties) {
      if (!matchesRecognition(row, recognition)) continue;
      if (q.length > 0) {
        const haystack = `${row.short.toLowerCase()} ${row.full.toLowerCase()} ${row.aliases.toLowerCase()}`;
        if (!haystack.includes(q)) continue;
      }
      out.push(row);
    }
    return out;
  }

  /** Sentinel party ids that get the pre-alphabetical "Special"
   *  treatment in `groupByLetter`. UNK is intentionally absent -
   *  the loader filters it out at the slug=null boundary, but a
   *  defensive secondary filter in `groupByLetter` keeps the
   *  invariant under any future loader change. */
  const SPECIAL_PARTY_IDS = new Set<string>([
    "parties.IN.IND",
    "parties.IN.NOTA",
  ]);

  /** Pure: group an already-filtered party list into the sentinel
   *  Special bucket + A..Z letter buckets. Empty letters are skipped
   *  (the letter rail renders only the populated heads). UNK is
   *  defensively dropped even if the input contains it - the page
   *  must NEVER render UNK as a citizen entity. */
  export function groupByLetter(
    parties: PartySummary[],
  ): PartyLetterBucket[] {
    const special: PartySummary[] = [];
    const letterMap = new Map<string, PartySummary[]>();
    for (const row of parties) {
      if (row.party_id === "parties.IN.UNK") continue; // defensive
      if (SPECIAL_PARTY_IDS.has(row.party_id)) {
        special.push(row);
        continue;
      }
      const first = (row.short[0] ?? "").toUpperCase();
      const letter = /^[A-Z]$/.test(first) ? first : "#";
      const arr = letterMap.get(letter) ?? [];
      arr.push(row);
      letterMap.set(letter, arr);
    }
    const buckets: PartyLetterBucket[] = [];
    if (special.length > 0) {
      buckets.push({
        letter: "\u2605 Special",
        anchor: "special",
        parties: special,
      });
    }
    // A..Z sorted; the catch-all '#' bucket sorts to the END (after Z)
    // so a stray short like "0NE" lands somewhere predictable.
    const letterKeys = [...letterMap.keys()].sort((a, b) => {
      if (a === "#") return 1;
      if (b === "#") return -1;
      return a.localeCompare(b);
    });
    for (const letter of letterKeys) {
      buckets.push({
        letter,
        anchor: `letter-${letter.toLowerCase()}`,
        parties: letterMap.get(letter)!,
      });
    }
    return buckets;
  }
</script>

<script lang="ts">
  /**
   * Page template - thin wrapper around the pure helpers above.
   *
   * Lifecycle:
   *   1. Mount kicks `loadAllParties()` (module-level cache: the second
   *      visit of the tab is instant).
   *   2. Two reactive `$state` cells - `query` (search) + `recognition`
   *      (chip filter) - drive `$derived` pipelines: filtered ->
   *      buckets -> chip counts -> letter rail.
   *   3. Click on a letter chip jumps to `#letter-x` via the `<a href>`
   *      (browser-native, no JS scroll handler).
   *   4. Click on a party pill navigates to `link.party(party_id)` via
   *      the wrapping `<a>` (no `onclick` on the pill itself - the
   *      wrapping anchor handles routing and PartyPill's tooltip
   *      still hover-opens because it inherits pointer events).
   *
   * Performance: 2349 rows on cold load. A naive sectioned render
   * (~26 sections x ~90 rows median, ~3-col grid) renders in <50 ms
   * on a Ryzen 5 / Chrome 121; no virtualisation needed. Re-measure
   * if rows pass ~5000 (lift to `svelte-virtual-list` then).
   */
  import { onMount } from "svelte";
  import PartyPill from "../lib/party-pill/PartyPill.svelte";
  import { partyRowForResolver } from "../lib/colors/party-row";
  import { link } from "../lib/links";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { loadAllParties } from "../lib/view-models/parties";

  let parties: PartySummary[] = $state([]);
  let loaded = $state(false);
  let loadError = $state<string | null>(null);
  let query = $state("");
  let recognition = $state<RecognitionFilter>("all");

  onMount(async () => {
    try {
      parties = await loadAllParties();
    } catch (err) {
      loadError = err instanceof Error ? err.message : String(err);
      parties = [];
    } finally {
      loaded = true;
    }
  });

  const filtered = $derived(filterParties(parties, query, recognition));
  const buckets = $derived(groupByLetter(filtered));

  // Counts per recognition bucket, computed AFTER the search filter so
  // a chip can be hidden when its post-search count is 0. The "all"
  // count mirrors the total post-search hit count.
  const recognitionCounts = $derived.by(() => {
    const counts = {
      all: 0,
      national: 0,
      state: 0,
      unrecognised: 0,
    } as Record<RecognitionFilter, number>;
    const searched = filterParties(parties, query, "all");
    for (const row of searched) {
      counts.all += 1;
      if (row.recognition_scope === "national") counts.national += 1;
      else if (row.recognition_scope === "state") counts.state += 1;
      else if (row.recognition_scope === "unrecognised_registered")
        counts.unrecognised += 1;
    }
    return counts;
  });

  /** Build the PartyPill `row` prop from a PartySummary - mirrors the
   *  flat-loader shape `partyRowForResolver` expects so the resolver
   *  picks up brand-tier colours when present. */
  function pillRow(row: PartySummary) {
    return partyRowForResolver({
      party_id: row.party_id,
      party_short: row.short,
      brand_colour_hex: row.brand_colour,
      brand_colour_confidence: "medium",
    });
  }
</script>

<PageContainer width="wide" data-testid="parties-index">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold text-slate-900">Parties</h1>
    <p class="text-sm text-slate-500">
      Every party that has contested an election in the canonical store.
      Click a party to see its full performance.
    </p>
  </header>

  <!-- Search + recognition chips. The chip row wraps below the input on
       narrow viewports; tap targets are >= 40px tall per the brief. -->
  <section class="space-y-2" data-testid="parties-index-controls">
    <label class="block">
      <span class="sr-only">Search parties</span>
      <input
        type="search"
        bind:value={query}
        placeholder="Search parties by name or alias..."
        class="w-full min-h-[44px] rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        data-testid="parties-search"
      />
    </label>

    <div
      class="flex flex-wrap gap-2"
      role="group"
      aria-label="Filter by recognition"
      data-testid="parties-chips"
    >
      {#each [{ key: "all", label: "All" }, { key: "national", label: "National" }, { key: "state", label: "State" }, { key: "unrecognised", label: "Unrecognised" }] as chip (chip.key)}
        {@const count = recognitionCounts[chip.key as RecognitionFilter]}
        {#if chip.key === "all" || count > 0}
          {@const isActive = recognition === chip.key}
          <button
            type="button"
            class="min-h-[40px] rounded-full border px-3 py-1 text-sm transition-colors"
            class:bg-slate-900={isActive}
            class:text-white={isActive}
            class:border-slate-900={isActive}
            class:bg-white={!isActive}
            class:text-slate-700={!isActive}
            class:border-slate-300={!isActive}
            data-chip-key={chip.key}
            data-chip-active={isActive ? "true" : "false"}
            onclick={() => (recognition = chip.key as RecognitionFilter)}
          >
            {chip.label}
            <span
              class="ml-1 text-xs"
              class:text-slate-200={isActive}
              class:text-slate-400={!isActive}>{count}</span
            >
          </button>
        {/if}
      {/each}
    </div>
  </section>

  <!-- Letter rail. Each link is a native anchor jump; the browser handles
       scrolling. Empty letters are skipped so the rail compacts to the
       populated heads after filter. -->
  {#if buckets.length > 0}
    <nav
      class="flex flex-wrap gap-1"
      aria-label="Jump to letter"
      data-testid="parties-letter-rail"
    >
      {#each buckets as bucket (bucket.anchor)}
        <a
          href="#{bucket.anchor}"
          class="min-w-[36px] min-h-[36px] inline-flex items-center justify-center rounded border border-slate-200 bg-white px-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
          data-letter-anchor={bucket.anchor}
        >
          {bucket.letter}
        </a>
      {/each}
    </nav>
  {/if}

  <!-- Body. Each section is a populated bucket; rows render as a 1/2/3
       column grid (mobile -> tablet -> desktop). Pills inherit pointer
       events from the wrapping <a>, so click navigates to /parties/<slug>
       and hover still opens the PartyPill tooltip. -->
  {#if loadError}
    <section
      class="rounded border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700"
      data-testid="parties-error"
    >
      Couldn't load parties: {loadError}
    </section>
  {:else if !loaded}
    <section
      class="rounded border border-slate-200 bg-white p-6 text-center text-sm text-slate-500"
      data-testid="parties-loading"
    >
      Loading parties...
    </section>
  {:else if filtered.length === 0}
    <section
      class="rounded border border-slate-200 bg-white p-6 text-center text-sm text-slate-600"
      data-testid="parties-empty"
    >
      No parties match {query ? `"${query}"` : "the current filter"}.
    </section>
  {:else}
    {#each buckets as bucket (bucket.anchor)}
      <section class="space-y-2" data-testid="parties-section">
        <h2
          id={bucket.anchor}
          class="scroll-mt-4 text-lg font-semibold text-slate-800"
        >
          {bucket.letter}
          <span class="ml-1 text-xs font-normal text-slate-400"
            >({bucket.parties.length})</span
          >
        </h2>
        <div
          class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2"
        >
          {#each bucket.parties as row (row.party_id)}
            {@const href = link.party(row.party_id)}
            {#if href}
              {@const recogLabel = recognitionLabel(row.recognition_scope)}
              <a
                {href}
                class="flex items-center gap-2 rounded border border-slate-200 bg-white px-2 py-2 min-h-[44px] hover:border-slate-400 hover:bg-slate-50"
                data-party-id={row.party_id}
                data-party-slug={row.slug}
              >
                <PartyPill
                  size="md"
                  party_id={row.party_id}
                  party_short={row.short}
                  row={pillRow(row)}
                />
                <span class="flex-1 truncate text-sm text-slate-700"
                  >{row.full || row.short}</span
                >
                {#if recogLabel}
                  <span
                    class="shrink-0 text-xs text-slate-400"
                    data-recognition-label>{recogLabel}</span
                  >
                {/if}
              </a>
            {/if}
          {/each}
        </div>
      </section>
    {/each}
  {/if}
</PageContainer>

