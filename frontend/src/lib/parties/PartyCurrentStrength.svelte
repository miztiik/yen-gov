<script lang="ts" module>
  /**
   * `PartyCurrentStrength` — "Where this party sits today" strip for
   * the per-party detail page (PR-7 of TODO/20260614-party-page-
   * reimagination-plan.md).
   *
   * Surfaces a 3-line strip directly UNDER the page header card and
   * ABOVE the existing latest-of one-liners on `/parties/<slug>`. The
   * strip answers the citizen question "how big is this party right
   * now?" by collapsing two body-grain headlines + one cross-body
   * "Last contested" footer into a glance-readable block:
   *
   *   <landmark> Parliament (Jun 2024): 211 of 543 seats - 36.7% vote share.
   *   <flag> State Assemblies (latest cycles in 31 of 31 states): 1,776 of 4,035 seats.
   *   Last contested: West Bengal State Assembly, May 2026.
   *
   * The view-model (`PartyCurrentStrength`) is built upstream by
   * `loadPartyCurrentStrength` in `../view-models/party-current-strength.ts`;
   * this component is a pure display layer.
   *
   * Caller-side suppression contracts:
   *   - `current_strength === null`: the entire strip is hidden. The
   *     view-model returns null for sentinel parties (NOTA / UNK) and
   *     for parties with no LS AND no AC history. NOTA gets a defence-
   *     in-depth `is_sentinel` short-circuit at the component level
   *     too, so even a stale view-model from a cached load cannot leak
   *     a meaningless headline onto the sentinel page.
   *   - `parliament_latest === null`: skip line 1.
   *   - `state_assemblies_latest === null`: skip line 2.
   *   - `last_contested === null`: skip line 3 (only when both
   *     of the above are also null - by view-model construction this
   *     means the strip is null overall and we never reach this branch).
   *
   * Tailwind tokens follow Jony J1's "warm density" convention used on
   * the rest of `/parties/<slug>`: slate-800 16px for the primary
   * Parliament line, slate-700 14px for the State Assemblies line,
   * and slate-500 12px italic for the per-entity "Last contested"
   * footer when present.
   *
   * PR-11 (TODO/20260615-party-page-citizen-fixes-plan.md, Jony +
   * Citizen): the slate-400 12px italic disclaimer that previously
   * followed the "Last contested" footer ("Election-night results -
   * does not track post-election defections, resignations, or bye-
   * elections later than the latest cycle.") has been DELETED. The
   * methodology body it carried now lives on the citizen-facing
   * concept page `docs/concepts/party-page-coverage.md` (linked from
   * the Party page footer "About this page" line). Same body, one
   * authoritative home, less per-card chrome on every party page.
   *
   * Numeric tokens use `tabular-nums` + Indian-style comma grouping
   * via `Intl.NumberFormat("en-IN")` so seats values like `1,776`
   * align correctly across the two body lines. Vote share uses
   * `toFixed(1)` (one decimal, matching the LS donut chart elsewhere).
   *
   * Glyphs are 16px PNG/SVG icons from `frontend/public/icons/`
   * (`landmark.svg` for Parliament, `flag.svg` for State Assembly),
   * positioned inline-block with a 6px right margin and aria-hidden=
   * "true" because the line copy is already self-explanatory and the
   * glyph is decorative.
   */
  import type { PartyCurrentStrength } from "../view-models/party-current-strength";

  /** Indian-style number grouping for seats values (e.g. 1776 -> "1,776",
   *  10000 -> "10,000"). v1 simplification: a single shared formatter
   *  bound at module-load (Intl is cheap, but the binding keeps the
   *  render hot-path zero-allocation). Pure; exported for vitest if a
   *  future PR pins the formatting. */
  const numberFormatter = new Intl.NumberFormat("en-IN");

  export function formatSeats(value: number): string {
    return numberFormatter.format(Math.trunc(value));
  }

  export function formatVoteShare(value: number): string {
    return `${value.toFixed(1)}%`;
  }

  export type { PartyCurrentStrength };
</script>

<script lang="ts">
  import TopicIcon from "../TopicIcon.svelte";
  import { link } from "../links";

  interface Props {
    current_strength: PartyCurrentStrength | null;
    /** Sentinel short-circuit: NOTA / UNK suppress the strip even if
     *  the view-model accidentally arrived populated. */
    is_sentinel: boolean;
    /** Party short code (e.g. "CPI") - names the strip heading +
     *  aria-label so the section reads "CPI latest scorecard". */
    party_label: string;
  }

  const { current_strength, is_sentinel, party_label }: Props = $props();

  const visible = $derived(!is_sentinel && current_strength !== null);
  const parliament = $derived(current_strength?.parliament_latest ?? null);
  const assemblies = $derived(current_strength?.state_assemblies_latest ?? null);
  const lastContested = $derived(current_strength?.last_contested ?? null);
</script>

{#if visible}
  <section
    data-testid="party-current-strength"
    class="mt-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:mt-4 md:p-5"
    aria-label={`${party_label} latest scorecard`}
  >
    <h2 class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
      {party_label} latest scorecard
    </h2>
    {#if parliament}
      <p
        data-testid="party-current-strength-parliament"
        class="flex items-start text-base text-slate-800"
      >
        <TopicIcon
          name="landmark"
          cls="mr-2 mt-1 inline-block flex-none w-4 h-4 text-slate-500"
        />
        <span>
          Parliament ({#if parliament.event_id}<a
              href={link.nationalElection(parliament.event_id)}
              class="text-sky-700 hover:underline">{parliament.month_label}</a>{:else}{parliament.month_label}{/if}):
          <span class="tabular-nums font-semibold">{formatSeats(parliament.seats_won)}</span>
          of
          <span class="tabular-nums">{formatSeats(parliament.seats_total)}</span>
          seats{#if parliament.vote_share_pct !== null} - <span class="tabular-nums">{formatVoteShare(parliament.vote_share_pct)}</span> vote share{/if}{#if parliament.rank_label} - {parliament.rank_label}{/if}.
        </span>
      </p>
    {/if}
    {#if assemblies}
      <p
        data-testid="party-current-strength-assemblies"
        class="mt-2 flex items-start text-sm text-slate-700"
      >
        <TopicIcon
          name="flag"
          cls="mr-2 mt-0.5 inline-block flex-none w-4 h-4 text-slate-500"
        />
        <span>
          State Assemblies (latest cycles in
          <span class="tabular-nums">{assemblies.state_count}</span> of 31 states):
          <span class="tabular-nums font-semibold">{formatSeats(assemblies.seats_won)}</span>
          of
          <span class="tabular-nums">{formatSeats(assemblies.seats_total)}</span>
          seats.
        </span>
      </p>
    {/if}
    {#if lastContested}
      <p
        data-testid="party-current-strength-last"
        class="mt-3 text-xs text-slate-500"
      >
        Last contested: {lastContested.prefix}{" "}{#if lastContested.href}<a
            href={lastContested.href}
            class="text-sky-700 hover:underline"
            data-testid="party-current-strength-last-link">{lastContested.date_text}</a>{:else}{lastContested.date_text}{/if}.
      </p>
    {/if}
  </section>
{/if}
