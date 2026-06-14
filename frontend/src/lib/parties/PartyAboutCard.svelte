<script lang="ts" module>
  /**
   * `PartyAboutCard` — co-located metadata card for the per-party page
   * (PR-6 of TODO/20260614-party-page-reimagination-plan.md).
   *
   * The component renders ONE display of party identity metadata in one
   * of two layouts:
   *
   *   - Desktop (default): a 240px-wide bordered side-rail card with
   *     an "About this party" header above a `<dl>` of typed rows.
   *     Mounted by `Party.svelte` inside an `<aside class="hidden
   *     lg:block">` wrapper so it surfaces only at the `lg`+ breakpoint.
   *
   *   - Mobile (`mobile` prop): a flat unbordered `<dl>` block, mounted
   *     by `Party.svelte` inside a `<div class="lg:hidden">` wrapper so
   *     it surfaces only BELOW the `lg` breakpoint. The card visually
   *     dissolves into a tight bulleted list of facts below the
   *     strongholds section on phones.
   *
   * Sentinel rows (NOTA / IND / UNK, signalled by `meta.is_sentinel`)
   * suppress every row EXCEPT recognition: founded_year carries
   * non-semantic values for NOTA (2013 is the PUCL ruling year, not a
   * party founding), and aliases / lineage / Wikipedia are uniformly
   * empty for sentinels by upstream contract. The card collapses to a
   * single recognition row — the citizen-facing copy ("Special
   * category") is the only meaningful surface for these rows.
   *
   * Pure helpers `foundingYearLabel` + `recognitionLabel` are exported
   * from the `<script module>` so the vitest pin can drive them against
   * synthetic inputs without mounting Svelte (project doctrine - no
   * `@testing-library/svelte`).
   */
  import type { PartyMeta } from "../view-models/parties";

  /**
   * Compose the citizen-facing active-range one-liner from the typed
   * (founded_year, dissolved_year) pair on `parties.csv`.
   *
   *   - Both years present: `Active YYYY-YYYY` (defunct party with a
   *     known founding date, e.g. Janata Party 1977-1988).
   *   - Founded only: `Active since YYYY` (live party with a known
   *     founding date - the common case).
   *   - Dissolved only: `Dissolved YYYY` (defunct party whose founding
   *     year is missing from upstream).
   *   - Both blank: null (caller suppresses the row).
   *
   * The phrasing is Hans H7 - "Active since" reads as ongoing on a
   * citizen surface; "Founded YYYY" (the prior copy) misled some
   * readers into thinking a defunct party was still operating.
   *
   * Pure; exported for vitest.
   */
  export function foundingYearLabel(
    founded: number | null,
    dissolved: number | null,
  ): string | null {
    if (founded !== null && dissolved !== null) {
      return `Active ${founded}-${dissolved}`;
    }
    if (founded !== null) {
      return `Active since ${founded}`;
    }
    if (dissolved !== null) {
      return `Dissolved ${dissolved}`;
    }
    return null;
  }

  /**
   * Hans H7 recognition vocabulary - replaces the prior "National
   * party" / "State party" / "Unrecognised registered party" /
   * "Special" copy. The change widens "party" into a fuller phrase
   * that disambiguates the legal category from the noun-as-party
   * (so a citizen scanning the card knows "Nationally recognised
   * party" is an ECI legal class, not a value judgment).
   *
   * Sentinel rows (IND, NOTA) surface as "Special category" - the
   * prior "Special" was too terse and read as a UX easter egg rather
   * than an honest data-class.
   *
   * Pure; exported for vitest.
   */
  export function recognitionLabel(scope: string | null): string {
    switch (scope) {
      case "national":
        return "Nationally recognised party";
      case "state":
        return "State-recognised party";
      case "unrecognised_registered":
        return "Registered party (unrecognised)";
      case "defunct":
        return "Defunct";
      case "sentinel":
        return "Special category";
      default:
        return "Recognition unknown";
    }
  }

  /**
   * Strip the `parties.IN.` taxonomy prefix from a party_id so the
   * AboutCard's predecessor / successor list renders the citizen-
   * facing short token (`BJS`, `JP`) rather than the verbose opaque
   * id (`parties.IN.BJS`).
   *
   * Pure; exported for vitest. Defensive: callers may pass any
   * party_id string; non-`parties.IN.*` shapes fall back to the
   * trailing dot-token (the splitPipe loader already trims empties,
   * so the empty-string case is by-construction unreachable from a
   * canonical row, but the helper still handles it gracefully).
   */
  export function shortPartyToken(party_id: string): string {
    const parts = party_id.split(".");
    return parts[parts.length - 1] || party_id;
  }

  export type { PartyMeta };
</script>

<script lang="ts">
  import { link } from "../links";

  interface Props {
    meta: PartyMeta;
    /** Resolves an ISO 3166-2 IN-* code to a citizen-readable state
     *  name. Caller plumbs `(c) => states.name(c)` from the route
     *  via `frontend/src/lib/states.svelte.ts` so this component
     *  stays free of route-level state dependencies. */
    statesNameFn: (code: string) => string | null;
    /** When true: flat `<dl>` mobile layout (no border, no header).
     *  Caller mounts the mobile instance inside a `<div
     *  class="lg:hidden">` wrapper. Default: bordered desktop card
     *  (caller mounts inside `<aside class="hidden lg:block">`). */
    mobile?: boolean;
  }

  const { meta, statesNameFn, mobile = false }: Props = $props();

  const founding = $derived(
    foundingYearLabel(meta.founded_year, meta.dissolved_year),
  );
  const recognition = $derived(recognitionLabel(meta.recognition_scope));
  // Home-states row gates on state-recognition AND non-empty list:
  // national parties have home_states empty by contract; sentinels
  // are short-circuited by is_sentinel; only state-recognised parties
  // with a populated home_state_codes list surface a meaningful row.
  const showHomeStates = $derived(
    !meta.is_sentinel
      && meta.recognition_scope === "state"
      && meta.home_state_codes.length > 0,
  );
  const showAliases = $derived(
    !meta.is_sentinel && meta.aliases.length > 0,
  );
  const showPredecessors = $derived(
    !meta.is_sentinel && meta.predecessor_party_ids.length > 0,
  );
  const showSuccessors = $derived(
    !meta.is_sentinel && meta.successor_party_ids.length > 0,
  );
  const showWikipedia = $derived(!meta.is_sentinel && meta.wikipedia !== null);
  const showFounding = $derived(!meta.is_sentinel && founding !== null);
  const aliasesText = $derived(meta.aliases.join(", "));
</script>

{#snippet rows()}
  {#if showFounding}
    <div data-testid="party-about-founding">
      <dt class="sr-only">Active</dt>
      <dd>{founding}</dd>
    </div>
  {/if}
  <div data-testid="party-about-recognition">
    <dt class="sr-only">Recognition</dt>
    <dd>{recognition}</dd>
  </div>
  {#if showHomeStates}
    <div data-testid="party-about-home-states">
      <dt class="text-xs text-slate-500">Home states</dt>
      <dd>
        {#each meta.home_state_codes as code, i (code)}{i > 0 ? ", " : ""}{statesNameFn(code) || code}{/each}
      </dd>
    </div>
  {/if}
  {#if showAliases}
    <div data-testid="party-about-aliases">
      <dt class="text-xs text-slate-500">Also known as</dt>
      <dd>{aliasesText}</dd>
    </div>
  {/if}
  {#if showPredecessors}
    <div data-testid="party-about-predecessors">
      <dt class="text-xs text-slate-500">Predecessor(s)</dt>
      <dd>
        {#each meta.predecessor_party_ids as pid, i (pid)}{i > 0 ? ", " : ""}{@const href = link.party(pid)}{#if href}<a {href} class="text-sky-600 hover:underline">{shortPartyToken(pid)}</a>{:else}{shortPartyToken(pid)}{/if}{/each}
      </dd>
    </div>
  {/if}
  {#if showSuccessors}
    <div data-testid="party-about-successors">
      <dt class="text-xs text-slate-500">Successor(s)</dt>
      <dd>
        {#each meta.successor_party_ids as sid, i (sid)}{i > 0 ? ", " : ""}{@const href = link.party(sid)}{#if href}<a {href} class="text-sky-600 hover:underline">{shortPartyToken(sid)}</a>{:else}{shortPartyToken(sid)}{/if}{/each}
      </dd>
    </div>
  {/if}
  {#if showWikipedia}
    <div data-testid="party-about-wikipedia">
      <dt class="sr-only">Wikipedia</dt>
      <dd>
        <a
          href={meta.wikipedia}
          target="_blank"
          rel="noopener noreferrer"
          class="text-sky-600 hover:underline"
        >
          Wikipedia
        </a>
      </dd>
    </div>
  {/if}
{/snippet}

{#if mobile}
  <dl
    class="space-y-2 text-sm text-slate-700"
    data-testid="party-about-card-mobile"
  >
    {@render rows()}
  </dl>
{:else}
  <aside
    class="rounded border border-slate-200 bg-white p-4 text-sm text-slate-700"
    data-testid="party-about-card-desktop"
  >
    <h2
      class="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3"
    >
      About this party
    </h2>
    <dl class="space-y-2">
      {@render rows()}
    </dl>
  </aside>
{/if}
