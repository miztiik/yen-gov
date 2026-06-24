<script lang="ts">
  // AllianceTotals - PR-W3b alliance-first display panel.
  //
  // Joins the per-event winner rows (one per AC/PC) with the alliance
  // membership table at `datasets/data/entities/party_alliances.csv`
  // (loaded via `psephlab/alliances.ts.loadAlliances(event, state?)`
  // which keys by (event_id, state) and yields a
  // `(party_id) -> alliance | null` lookup). Plan: TODO/20260612-
  // alliance-phase-1-structural-fix-plan.md v2.0 schema.
  //
  // Layout:
  //   1. Honesty caption (R6 of 20260615-state-election-event-page-redesign-plan)
  //      naming pre-poll vs post-poll attribution + the source title.
  //   2. Two headline cards: the top two FORCES by seats (a declared
  //      alliance OR a promoted lone non-aligned party), seat-rank-neutral
  //      eyebrows ("Most seats" / "Second"), emerald accent only at a
  //      majority. A "no majority" line shows when the leader is a plurality.
  //   3. Tail chips for any 3rd+ force + the residual "Others".
  //   4. Caption: "alliance as of polling date <date>"
  //   5. Toggle: "Show party breakdown" - expands to a stacked seat-bar +
  //      swatch list per force, with a per-force mute eye (issue 3).
  //
  // Citizen-readable framing (issue 1, Max + Jony + Citizen verdict
  // 2026-06-24): a non-aligned party large enough to out-rank a declared
  // alliance is PROMOTED to its own card/row labelled "no pre-poll alliance
  // recorded" (a data-state, not a world claim) instead of being buried in
  // "Others"; only the genuinely small tail collapses under "Other parties".
  //
  // R6 honesty rule (silence on uncurated events): when the lookup
  // returns zero rows for (event_id, state), the entire panel is
  // SUPPRESSED rather than rendering an amber "pending" pill. Per Max +
  // Hans verdict in plan-doc Section 0.1: an uncurated event should
  // be silently absent from the page; rendering a debt-tracking pill is
  // a different surface (the operator receipt at datasets/_ops/, not
  // the citizen page).
  //
  // State scoping (D2 fix, v2.0 schema): pass the LGD state slug
  // (`params.state`, e.g. "tamil-nadu") to scope to per-state rows OR
  // national rows (state="IN"). Omit the prop when rendering on a
  // national surface to see all rows for the event.

  import { loadAlliances } from "../psephlab/alliances";
  import type { AllianceLookup } from "../psephlab/types";
  import { getPartyColor } from "../colors/resolver";
  import {
    deriveAllianceBreakdown,
    type AllianceBreakdown,
    type Force,
    type PartySeats,
    type WinnerInput,
  } from "./alliance-totals-model";

  interface Props {
    event: string;
    /** One row per won seat. Length = total seats for the event/state. */
    winners: readonly WinnerInput[];
    /** Polled-on date for the caption (e.g. "2024-06-01"). Falls back
     *  to a generic caption when missing. */
    polled_on?: string | null;
    /** LGD state slug ("tamil-nadu", "west-bengal", "maharashtra") for
     *  state-scoped consumers. When provided, the alliance lookup
     *  filters to rows where state matches OR state === "IN". When
     *  omitted (e.g. on a national-only surface), returns every row
     *  for the event. v2.0 D2 fix per plan-doc 2026-06-12. Named
     *  `state_slug` (not `state`) to avoid shadowing Svelte 5's
     *  `$state()` rune in the destructured props. */
    state_slug?: string;
    /** Optional source title for the R6 honesty caption (e.g. "Wikipedia"
     *  or "ECI Form 21A"). When provided, the caption reads "as reported
     *  by {source_title}"; otherwise the caption uses a generic phrasing. */
    source_title?: string | null;
    /** Optional section-heading class. Defaults to the legacy plain
     *  treatment so the national election surface is unchanged; the
     *  state-event page passes the canonical harmonised heading
     *  (Row 4, 2026-06-18). */
    headingClass?: string;
    /** The page's current per-party mute set (keys are
     *  `party_eci_code ?? party_short`, shared with the seat arc + AC/PC
     *  maps). Optional: when omitted the per-alliance mute toggle is not
     *  rendered. */
    hidden_keys?: ReadonlySet<string>;
    /** Bulk mute/unmute handler. Called with every member key of a force
     *  (or the "Others" bucket) and whether to hide them. The parent folds
     *  the keys into its `hidden_parties` set in one pass, so the recede
     *  propagates to every surface that reads that set. Optional. */
    onToggleForce?: (keys: string[], hide: boolean) => void;
  }

  let {
    event,
    winners,
    polled_on,
    state_slug,
    source_title,
    headingClass = "text-sm font-medium text-slate-700",
    hidden_keys,
    onToggleForce,
  }: Props = $props();

  let lookup = $state<AllianceLookup | null>(null);

  $effect(() => {
    const ev = event;
    const ss = state_slug;
    lookup = null;
    loadAlliances(ev, ss).then((l) => {
      // Guard against stale event resolves.
      if (ev === event && ss === state_slug) lookup = l;
    });
  });

  const EMPTY: AllianceBreakdown = {
    forces: [],
    others: [],
    others_seats: 0,
    total_seats: 0,
    majority_threshold: 0,
    has_any: false,
  };
  const breakdown = $derived<AllianceBreakdown>(
    lookup === null ? EMPTY : deriveAllianceBreakdown(winners, lookup),
  );

  // Headline cards (issue 1, Max + Jony + Citizen verdict 2026-06-24):
  // rank FORCES (declared alliances + promoted lone non-aligned parties)
  // by seats and read the top two. No "Winner / Runner-up" superlative -
  // the panel tallies a PRE-POLL seat snapshot, not the election outcome,
  // so the eyebrows are seat-rank-neutral ("Most seats" / "Second"). The
  // emerald accent is earned ONLY by a force at/above the majority
  // threshold; a plurality leader gets a neutral accent + a "no majority"
  // line. share_pct is SEAT-share over ALL seats won (incl Others), the
  // honest figure derivable from the counts we hold (not vote-share).
  interface AllianceCard {
    key: string;
    name: string;
    kind: Force["kind"];
    seats: number;
    share_pct: number;
    has_majority: boolean;
    member_label: string;
    member_title: string;
  }

  function toCard(f: Force, total: number, threshold: number): AllianceCard {
    const shorts = f.members.map((m) => m.party_short);
    return {
      key: f.key,
      name: f.name,
      kind: f.kind,
      seats: f.seats,
      share_pct: (f.seats / total) * 100,
      has_majority: threshold > 0 && f.seats >= threshold,
      member_label: f.kind === "alliance" ? membersLabel(shorts) : "",
      member_title: shorts.join(", "),
    };
  }

  const summary = $derived.by<{
    lead: AllianceCard | null;
    second: AllianceCard | null;
    tail: Force[];
  }>(() => {
    const total = breakdown.total_seats || 1;
    const t = breakdown.majority_threshold;
    const forces = breakdown.forces;
    return {
      lead: forces[0] ? toCard(forces[0], total, t) : null,
      second: forces[1] ? toCard(forces[1], total, t) : null,
      tail: forces.slice(2),
    };
  });

  const any_majority = $derived(summary.lead?.has_majority ?? false);

  function membersLabel(members: string[], max = 3): string {
    if (members.length <= max) return members.join(", ");
    return `${members.slice(0, max).join(", ")} +${members.length - max}`;
  }

  // Breakdown groups (issue 2): one stacked seat-bar per force + the
  // residual "Other parties" bucket. Each group carries its member parties
  // (seats desc) and the mute keys that the per-alliance toggle (issue 3)
  // folds into the page's hidden set.
  interface BreakdownGroup {
    key: string;
    name: string;
    kind: Force["kind"] | "others";
    seats: number;
    members: PartySeats[];
    mute_keys: string[];
  }

  const groups = $derived.by<BreakdownGroup[]>(() => {
    const g: BreakdownGroup[] = breakdown.forces.map((f) => ({
      key: f.key,
      name: f.name,
      kind: f.kind,
      seats: f.seats,
      members: f.members,
      mute_keys: f.mute_keys,
    }));
    if (breakdown.others_seats > 0) {
      g.push({
        key: "others",
        name: "Other parties",
        kind: "others",
        seats: breakdown.others_seats,
        members: breakdown.others,
        mute_keys: breakdown.others.map((p) => p.mute_key),
      });
    }
    return g;
  });

  /** Canvas colour for a party's seat-bar segment + swatch (3-tier
   *  resolver: anchor -> brand -> algorithmic fallback). */
  function partyHex(p: PartySeats): string {
    const row = p.brand_colour_hex
      ? {
          party_id: p.party_id,
          brand_colour: {
            hex: p.brand_colour_hex,
            confidence: p.brand_colour_confidence ?? ("medium" as const),
          },
        }
      : null;
    return getPartyColor(p.party_id, row).hex;
  }

  const MAX_MEMBERS = 6;
  let show_all_others = $state(false);

  /** Swatch-list members for a group: the long "Others" tail collapses to
   *  the top MAX_MEMBERS until expanded. The stacked bar always shows all
   *  segments (they are pre-attentive); only the labelled list collapses. */
  function listMembers(g: BreakdownGroup): PartySeats[] {
    if (g.kind === "others" && !show_all_others && g.members.length > MAX_MEMBERS) {
      return g.members.slice(0, MAX_MEMBERS);
    }
    return g.members;
  }

  // ---- per-alliance mute (issue 3) ----------------------------------
  // Reuses the page's existing `hidden_parties` set via the bulk
  // `onToggleForce` callback. Muting a force adds every member key; the
  // recede then propagates to the seat arc + AC/PC maps for free. Mute is
  // visual-only - seat counts in the bars + headline never change.
  type MuteState = "none" | "some" | "all";

  function hiddenCount(keys: string[]): number {
    const hk = hidden_keys;
    if (!hk) return 0;
    let n = 0;
    for (const k of keys) if (hk.has(k)) n++;
    return n;
  }
  function muteState(keys: string[]): MuteState {
    if (!hidden_keys || keys.length === 0) return "none";
    const n = hiddenCount(keys);
    if (n === 0) return "none";
    return n === keys.length ? "all" : "some";
  }
  function toggleGroup(keys: string[]): void {
    if (!onToggleForce) return;
    // All hidden -> reveal; otherwise hide the (rest of the) group.
    onToggleForce(keys, muteState(keys) !== "all");
  }
  function muteLabel(st: MuteState): string {
    return st === "all" ? "Show" : st === "some" ? "Mute all" : "Mute";
  }
  function muteTitle(st: MuteState, name: string): string {
    if (st === "all") return `Show ${name} across the page`;
    if (st === "some") return `Mute the rest of ${name} across the page`;
    return `Mute ${name} across the page`;
  }

  const panel_keys = $derived.by<string[]>(() => {
    const keys = new Set<string>();
    for (const g of groups) for (const k of g.mute_keys) keys.add(k);
    return [...keys];
  });
  const hidden_in_panel = $derived(hiddenCount(panel_keys));
  function showAllPanel(): void {
    if (onToggleForce) onToggleForce(panel_keys, false);
  }

  let expanded = $state(false);
  function toggle(): void {
    expanded = !expanded;
  }
</script>

<!-- Headline card for a single force (issue 1). Emerald accent only at a
     majority; neutral slate otherwise. A lone-party force shows the
     data-state sub-label "no pre-poll alliance recorded". -->
{#snippet forceCard(card: AllianceCard, eyebrow: string, testid: string)}
  <div
    class="rounded-lg border p-3 {card.has_majority
      ? 'border-emerald-200 bg-emerald-50/40'
      : 'border-slate-200 bg-slate-50/60'}"
    data-testid={testid}
  >
    <div class="flex items-baseline justify-between gap-2">
      <span
        class="text-[11px] font-semibold uppercase tracking-wide {card.has_majority
          ? 'text-emerald-700'
          : 'text-slate-500'}"
      >
        {eyebrow}
      </span>
      <span class="text-xs text-slate-400 tabular-nums">
        {card.share_pct.toFixed(0)}%
      </span>
    </div>
    <div class="mt-0.5 flex items-baseline justify-between gap-2">
      <span class="truncate font-semibold text-slate-900">{card.name}</span>
      <span class="text-2xl font-bold tabular-nums text-slate-900">
        {card.seats}
      </span>
    </div>
    {#if card.kind === "party"}
      <p class="mt-0.5 text-xs italic text-slate-400">
        no pre-poll alliance recorded
      </p>
    {:else if card.member_label}
      <p
        class="mt-0.5 truncate text-xs text-slate-500"
        title={card.member_title}
      >
        {card.member_label}
      </p>
    {/if}
    <div class="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
      <div
        class="h-full rounded-full {card.has_majority
          ? 'bg-emerald-500'
          : 'bg-slate-400'}"
        style="width: {card.share_pct}%;"
      ></div>
    </div>
  </div>
{/snippet}

<!-- One breakdown group (issue 2): a stacked seat-bar (one brand-coloured
     segment per member, width prop to seats) above a swatch list, with an
     optional per-alliance mute eye (issue 3). -->
{#snippet groupBlock(g: BreakdownGroup)}
  {@const st = muteState(g.mute_keys)}
  <li class="rounded border border-slate-100 bg-white p-2">
    <div class="flex items-baseline justify-between gap-2">
      <div class="min-w-0">
        <span class="text-sm font-semibold text-slate-800">{g.name}</span>
        {#if g.kind === "party"}
          <span class="ml-1 text-[11px] italic text-slate-400">
            no pre-poll alliance recorded
          </span>
        {/if}
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <span class="text-sm font-semibold tabular-nums text-slate-700">
          {g.seats}
        </span>
        {#if onToggleForce}
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded border border-slate-200 px-1.5 py-0.5 text-[11px] text-slate-500 hover:bg-slate-50 hover:text-slate-700"
            onclick={() => toggleGroup(g.mute_keys)}
            title={muteTitle(st, g.name)}
            data-testid="alliance-mute-{g.key}"
          >
            {#if st === "all"}
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="h-3.5 w-3.5"
                aria-hidden="true"
              >
                <path d="m2 2 20 20" />
                <path d="M6.7 6.7C3.6 8.5 2 12 2 12s3.6 7 10 7c2 0 3.7-.5 5.2-1.3" />
                <path d="M9.9 4.2A10.9 10.9 0 0 1 12 4c6.4 0 10 7 10 7a17.6 17.6 0 0 1-2.3 3.1" />
              </svg>
            {:else}
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="h-3.5 w-3.5"
                aria-hidden="true"
              >
                <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            {/if}
            <span>{muteLabel(st)}</span>
          </button>
        {/if}
      </div>
    </div>
    <div
      class="mt-1.5"
      class:opacity-40={st === "all"}
      class:grayscale={st === "all"}
    >
      <div class="flex h-2.5 overflow-hidden rounded-full bg-slate-100">
        {#each g.members as m (m.party_id)}
          <div
            class="h-full"
            style="width: {(m.seats / g.seats) *
              100}%; background-color: {partyHex(m)};"
            title="{m.party_short} {m.seats}"
          ></div>
        {/each}
      </div>
      <ul class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
        {#each listMembers(g) as m (m.party_id)}
          <li class="inline-flex items-center gap-1">
            <span
              class="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
              style="background-color: {partyHex(m)};"
            ></span>
            <span class="truncate">{m.party_short}</span>
            <span class="tabular-nums text-slate-400">{m.seats}</span>
          </li>
        {/each}
        {#if g.kind === "others" && g.members.length > MAX_MEMBERS && !show_all_others}
          <li>
            <button
              type="button"
              class="text-sky-700 hover:underline"
              onclick={() => (show_all_others = true)}
            >
              +{g.members.length - MAX_MEMBERS} more
            </button>
          </li>
        {/if}
      </ul>
      {#if st === "some"}
        <p class="mt-1 text-[11px] text-slate-400">
          {hiddenCount(g.mute_keys)} of {g.mute_keys.length} hidden
        </p>
      {/if}
    </div>
  </li>
{/snippet}

{#if lookup === null}
  <section
    class="rounded border border-slate-200 bg-white p-4"
    data-testid="alliance-totals"
  >
    <h2 class={headingClass}>Alliance totals</h2>
    <p class="mt-2 text-xs text-slate-500">Loading alliance data&hellip;</p>
  </section>
{:else if !breakdown.has_any}
  <!-- R6 (TODO/20260615-state-election-event-page-redesign-plan.md):
       silence on uncurated events. The entire panel is SUPPRESSED when
       the lookup returns zero rows for (event_id, state); no amber
       "pending" pill is rendered. Per Max + Hans verdict in plan-doc
       Section 0.1 (alliance honesty): an uncurated event should be
       silently absent from the page; debt tracking lives at
       datasets/_ops/ + the operator-receipt surface, not on the citizen
       page. -->
{:else}
  <section
    class="rounded border border-slate-200 bg-white p-4"
    data-testid="alliance-totals"
  >
    <h2 class={headingClass}>Alliance totals</h2>
    <!-- R6 honesty caption above the panel. The wording distinguishes
         pre-poll seat-sharing arrangements from post-poll government
         formation; the cited source attribution flows from the citation
         ledger so the citizen can verify the claim. Per Max-authored
         draft in plan-doc Section 0.1. -->
    <p
      class="mt-1 text-[11px] italic text-slate-500"
      data-testid="alliance-totals-honesty-caption"
    >
      Pre-poll alliance composition{source_title
        ? ` as reported by ${source_title}`
        : ""}. Post-election government formation may differ.
      Uncategorised parties shown under &ldquo;Others&rdquo;.
    </p>

    <!-- Headline: top two FORCES by seats (issue 1, Max + Jony + Citizen
         verdict 2026-06-24). A force is a declared alliance OR a promoted
         lone non-aligned party. Both names sit inside the headline
         container so the per-event e2e (NDA-2024/INDIA-2024, Mahayuti/MVA)
         holds. The eyebrows are seat-rank-neutral; the emerald accent is
         earned only at a majority (handled inside forceCard). -->
    <div
      class="mt-3 grid gap-3 sm:grid-cols-2"
      data-testid="alliance-totals-headline"
    >
      {#if summary.lead}
        {@render forceCard(summary.lead, "Most seats", "alliance-totals-winner")}
      {/if}
      {#if summary.second}
        {@render forceCard(
          summary.second,
          "Second",
          "alliance-totals-runnerup",
        )}
      {/if}
    </div>

    <!-- Plurality honesty: when no force clears the majority threshold the
         accent stays neutral and this line states the gap. -->
    {#if !any_majority && breakdown.total_seats > 0}
      <p
        class="mt-2 text-xs text-slate-500"
        data-testid="alliance-totals-no-majority"
      >
        No bloc holds a majority ({breakdown.majority_threshold} of {breakdown.total_seats}
        seats needed).
      </p>
    {/if}

    {#if summary.tail.length > 0 || breakdown.others_seats > 0}
      <div
        class="mt-2 flex flex-wrap gap-1.5"
        data-testid="alliance-totals-tail"
      >
        {#each summary.tail as t (t.key)}
          <span class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600">
            <span class="font-medium">{t.name}</span>
            <span class="tabular-nums text-slate-400">({t.seats})</span>
          </span>
        {/each}
        {#if breakdown.others_seats > 0}
          <span class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-500">
            <span class="font-medium">Others</span>
            <span class="tabular-nums text-slate-400"
              >({breakdown.others_seats})</span
            >
          </span>
        {/if}
      </div>
    {/if}

    <p class="mt-2 text-xs text-slate-500">
      alliance as of polling date <span class="tabular-nums"
        >{polled_on ?? "unspecified"}</span
      >
    </p>
    <button
      type="button"
      class="mt-2 text-xs text-sky-700 hover:underline"
      data-testid="alliance-totals-toggle"
      onclick={toggle}
    >
      {expanded ? "Hide" : "Show"} party breakdown
    </button>
    {#if expanded}
      <ul class="mt-3 space-y-2" data-testid="alliance-totals-breakdown">
        {#each groups as g (g.key)}
          {@render groupBlock(g)}
        {/each}
      </ul>
      {#if onToggleForce && hidden_in_panel > 0}
        <button
          type="button"
          class="mt-2 text-xs text-sky-700 hover:underline"
          onclick={showAllPanel}
          data-testid="alliance-totals-show-all"
        >
          Show all ({hidden_in_panel} muted)
        </button>
      {/if}
    {/if}
  </section>
{/if}

