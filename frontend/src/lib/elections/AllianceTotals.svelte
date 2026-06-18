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
  //   2. Alliance-first total line: "NDA 11 / INDIA 0 / Others 0"
  //   3. Caption: "alliance as of polling date <date>"
  //   4. Toggle: "Show party breakdown"
  //      - Expands to a grouped list of (alliance -> [party x seats])
  //
  // Citizen-readable framing: parties without an alliance row collapse
  // under "Others". An alliance entry shows as "<alliance> <seats>" with
  // no comma after the last entry.
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
  import {
    deriveAllianceBreakdown,
    type AllianceBreakdown,
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
  }

  let {
    event,
    winners,
    polled_on,
    state_slug,
    source_title,
    headingClass = "text-sm font-medium text-slate-700",
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

  const breakdown = $derived<AllianceBreakdown>(
    lookup === null
      ? { rows: [], by_alliance: new Map(), has_any: false }
      : deriveAllianceBreakdown(winners, lookup),
  );

  // Gap-closure G6 (TODO/20260616-state-event-page-gap-closure-plan.md):
  // upgrade the plain "NDA 11 / INDIA 0" text line into a winner /
  // runner-up card summary with member chips + a seat-share bar. The
  // percentage is SEAT-share (seats / total seats won), the honest
  // figure derivable from the seat counts we hold - NOT vote-share
  // (which the alliance model does not carry).
  const total_alliance_seats = $derived(
    breakdown.rows.reduce((s, r) => s + r.seats, 0),
  );

  interface AllianceCard {
    alliance: string;
    seats: number;
    share_pct: number;
    members: string[];
  }

  const summary = $derived.by<{
    winner: AllianceCard | null;
    runner_up: AllianceCard | null;
    tail: AllianceCard[];
  }>(() => {
    const total = total_alliance_seats || 1;
    const toCard = (alliance: string, seats: number): AllianceCard => ({
      alliance,
      seats,
      share_pct: (seats / total) * 100,
      members: (breakdown.by_alliance.get(alliance) ?? []).map(
        (p) => p.party_short,
      ),
    });
    // Declared alliances only (exclude the "Others" bucket) rank for the
    // winner / runner-up cards; "Others" + any 3rd+ alliance fall to the
    // tail chips.
    const declared = breakdown.rows.filter((r) => r.alliance !== "Others");
    const winner = declared[0]
      ? toCard(declared[0].alliance, declared[0].seats)
      : null;
    const runner_up = declared[1]
      ? toCard(declared[1].alliance, declared[1].seats)
      : null;
    const named = new Set(
      [winner?.alliance, runner_up?.alliance].filter(Boolean) as string[],
    );
    const tail = breakdown.rows
      .filter((r) => !named.has(r.alliance))
      .map((r) => toCard(r.alliance, r.seats));
    return { winner, runner_up, tail };
  });

  function membersLabel(members: string[], max = 3): string {
    if (members.length <= max) return members.join(", ");
    return `${members.slice(0, max).join(", ")} +${members.length - max}`;
  }

  let expanded = $state(false);
  function toggle(): void {
    expanded = !expanded;
  }
</script>

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

    <!-- Winner / runner-up cards (G6). Seat-share bar + member chips.
         A single-alliance event renders just the winner card. -->
    <div
      class="mt-3 grid gap-3 sm:grid-cols-2"
      data-testid="alliance-totals-headline"
    >
      {#if summary.winner}
        {@const wc = summary.winner}
        <div
          class="rounded-lg border border-emerald-200 bg-emerald-50/40 p-3"
          data-testid="alliance-totals-winner"
        >
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
              Winner
            </span>
            <span class="text-xs text-slate-400 tabular-nums">
              {wc.share_pct.toFixed(0)}%
            </span>
          </div>
          <div class="mt-0.5 flex items-baseline justify-between gap-2">
            <span class="font-semibold text-slate-900">{wc.alliance}</span>
            <span class="text-2xl font-bold tabular-nums text-slate-900">
              {wc.seats}
            </span>
          </div>
          {#if wc.members.length > 0}
            <p class="mt-0.5 truncate text-xs text-slate-500" title={wc.members.join(", ")}>
              {membersLabel(wc.members)}
            </p>
          {/if}
          <div class="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              class="h-full rounded-full bg-emerald-500"
              style="width: {wc.share_pct}%;"
            ></div>
          </div>
        </div>
      {/if}

      {#if summary.runner_up}
        {@const rc = summary.runner_up}
        <div
          class="rounded-lg border border-slate-200 bg-slate-50/60 p-3"
          data-testid="alliance-totals-runnerup"
        >
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Runner-up
            </span>
            <span class="text-xs text-slate-400 tabular-nums">
              {rc.share_pct.toFixed(0)}%
            </span>
          </div>
          <div class="mt-0.5 flex items-baseline justify-between gap-2">
            <span class="font-semibold text-slate-900">{rc.alliance}</span>
            <span class="text-2xl font-bold tabular-nums text-slate-900">
              {rc.seats}
            </span>
          </div>
          {#if rc.members.length > 0}
            <p class="mt-0.5 truncate text-xs text-slate-500" title={rc.members.join(", ")}>
              {membersLabel(rc.members)}
            </p>
          {/if}
          <div class="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              class="h-full rounded-full bg-slate-400"
              style="width: {rc.share_pct}%;"
            ></div>
          </div>
        </div>
      {/if}
    </div>

    {#if summary.tail.length > 0}
      <div
        class="mt-2 flex flex-wrap gap-1.5"
        data-testid="alliance-totals-tail"
      >
        {#each summary.tail as t (t.alliance)}
          <span class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600">
            <span class="font-medium">{t.alliance}</span>
            <span class="tabular-nums text-slate-400">({t.seats})</span>
          </span>
        {/each}
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
      <ul
        class="mt-3 space-y-3 text-sm"
        data-testid="alliance-totals-breakdown"
      >
        {#each breakdown.rows as r (r.alliance)}
          <li>
            <div class="text-xs font-semibold uppercase text-slate-500">
              {r.alliance} ({r.seats})
            </div>
            <ul class="mt-1 ml-3 space-y-0.5 text-slate-700">
              {#each breakdown.by_alliance.get(r.alliance) ?? [] as p (p.party_id)}
                <li class="flex justify-between gap-3">
                  <span class="truncate">{p.party_short}</span>
                  <span class="tabular-nums text-slate-500">{p.seats}</span>
                </li>
              {/each}
            </ul>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
{/if}

