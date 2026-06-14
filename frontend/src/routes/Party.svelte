<script module lang="ts">
  /**
   * Per-party page (`/parties/<slug>`) - PR-4 of
   * TODO/20260612-party-rendering-and-party-pages-plan.md.
   *
   * Replaces the PR-0 STUB with the indiavotes-style body per the
   * Jony B1+B5+B7 verdict:
   *   (1) Header card  - party-coloured 80px avatar + name + sub-line
   *   (2) Latest-of one-liner per body (LS + VS)
   *   (3) KPI strip 2x2 - LS seats, VS seats, elections contested,
   *       active range
   *   (4) LS DualAxisBarLine - seats (bars) + vote-share (line)
   *   (5) VS DualAxisBarLine - parallel
   *   (6) Strongholds top-10 per body - text + tiny W/L sparkline
   *   (7) Metadata footer - founded / dissolved / recognition / home
   *       states / native script / wiki / lineage / aliases
   *
   * Sentinel framing (IND, NOTA): sections (4)+(5)+(6) hide; section
   * (1) renders a grey neutral avatar with a citizen-honest one-liner;
   * section (2) renders only when numerically meaningful; section (7)
   * renders whatever metadata exists.
   *
   * Pure helpers extracted to this `<script module>` block so vitest
   * pins the contract without mounting Svelte (project doctrine - no
   * `@testing-library/svelte`). Same precedent as PartiesIndex.svelte
   * (PR-3).
   *
   * Router props: the App router passes `{ params: matched.params }`
   * as a single prop, so the page destructures `let { params }: Props
   * = $props()` (NOT `let { slug }`); `params.slug` is the URL token.
   * The PR-0 STUB shipped with `let { slug }` which crashed the page
   * with `Cannot read 'split' of undefined`; this rebuild fixes that
   * naturally by adopting the route-wide `params` convention.
   */
  import type { PartyMeta } from "../lib/view-models/parties";
  import type {
    PartyDetailViewModel,
    PartyHistoryPoint,
  } from "../lib/view-models/party-detail";
  import {
    getPartyColor,
    type PartyRowForResolver,
  } from "../lib/colors/resolver";
  import { pickInkForFill } from "../lib/party-pill/party-pill-resolve";

  /** Pure: derive the 4-tile KPI strip values from the view-model. */
  export interface PartyKpiStrip {
    /** Sum of LS seats won across all cycles. */
    ls_seats: number;
    /** Sum of VS seats won across all cycles. */
    vs_seats: number;
    /** Count of cycles where the party contested or won. */
    elections_contested: number;
    /** Formatted active range, e.g. "1989-2024" or "1989" when first==last. */
    active_range: string;
  }

  /** Pure: compute the 4-tile KPI shape from a populated view-model.
   *  Falls back to "-" for the active range when no cycles exist. */
  export function computeKpis(view_model: PartyDetailViewModel): PartyKpiStrip {
    const { totals } = view_model;
    let active_range = "-";
    if (totals.first_year > 0 && totals.last_year > 0) {
      active_range =
        totals.first_year === totals.last_year
          ? `${totals.first_year}`
          : `${totals.first_year}-${totals.last_year}`;
    }
    return {
      ls_seats: totals.ls_seats,
      vs_seats: totals.vs_seats,
      elections_contested: totals.elections_contested,
      active_range,
    };
  }

  /** Pure: format the citizen-readable latest-of one-liner for ONE body
   *  (e.g. "Parliament (2024): 99 of 543 seats won, 21.2% of votes -
   *  down from the party's peak of 415 seats in 1984."). Returns null
   *  when the history is empty so the consumer can skip the line
   *  entirely.
   *
   *  Peak/low framing (PR-1 plan-doc 20260614, Hans H1 verbatim:
   *  comma separators, named verbs, no glyphs):
   *    - When the latest sits BELOW the all-time peak: surface the peak
   *      as a "- down from the party's peak of X seats in Y" downbeat
   *      citizen anchor.
   *    - When the latest IS the all-time peak AND there is an earlier
   *      low: surface the low as a "- up from the party's earlier low
   *      of X in Y" upbeat citizen anchor.
   *    - When the latest is the only cycle (or the series is flat at the
   *      latest's value): no framing - the bare seats + share line
   *      stands on its own. */
  export function formatLatestSentence(
    history: PartyHistoryPoint[],
    total_seats: number,
    body_label: string,
  ): string | null {
    if (history.length === 0) return null;
    const sorted = [...history].sort((a, b) => a.year - b.year);
    const latest = sorted[sorted.length - 1]!;
    // Find both the peak (max seats) and the low (min seats); ties
    // resolved by earliest year for determinism.
    let peak = sorted[0]!;
    let low = sorted[0]!;
    for (const p of sorted) {
      if (p.seats > peak.seats) peak = p;
      if (p.seats < low.seats) low = p;
    }
    const totalStr = total_seats > 0 ? ` of ${total_seats}` : "";
    const seatsPart = `${latest.seats}${totalStr} seats won`;
    const sharePart =
      latest.vote_share_pct == null
        ? ""
        : `, ${latest.vote_share_pct.toFixed(1)}% of votes`;
    let framing = "";
    if (peak.year !== latest.year && peak.seats > latest.seats) {
      framing = ` - down from the party's peak of ${peak.seats} seats in ${peak.year}`;
    } else if (low.year !== latest.year && low.seats < latest.seats) {
      framing = ` - up from the party's earlier low of ${low.seats} in ${low.year}`;
    }
    return `${body_label} (${latest.year}): ${seatsPart}${sharePart}${framing}.`;
  }

  /** Avatar treatment tier - mirrors the 3-tier party-colour resolver +
   *  a fourth "sentinel" tier for IND/NOTA. */
  export type AvatarKind = "anchor" | "brand" | "fallback" | "sentinel";

  /** Pure: derive the avatar style for the header card. Anchor =
   *  full-bleed coloured square. Brand = paper square + 3px coloured
   *  ring. Fallback = paper square + small coloured swatch. Sentinel
   *  = grey neutral square. */
  export interface AvatarStyle {
    kind: AvatarKind;
    /** Background fill for anchor; null for the other tiers. */
    fill: string | null;
    /** Ring colour for brand; null otherwise. */
    ring: string | null;
    /** Ink colour (text on the square). */
    ink: string;
    /** Small swatch colour for fallback; null otherwise. */
    swatch: string | null;
  }

  export function getAvatarStyle(
    party_id: string,
    row: PartyRowForResolver | null,
    is_sentinel: boolean,
  ): AvatarStyle {
    if (is_sentinel) {
      return {
        kind: "sentinel",
        fill: "#cbd5e1", // slate-300 - the canonical neutral
        ring: null,
        ink: "#334155", // slate-700
        swatch: null,
      };
    }
    const resolved = getPartyColor(party_id, row);
    switch (resolved.source) {
      case "anchor":
        return {
          kind: "anchor",
          fill: resolved.hex,
          ring: null,
          ink: pickInkForFill(resolved.hex),
          swatch: null,
        };
      case "brand":
        return {
          kind: "brand",
          fill: null,
          ring: resolved.hex,
          ink: "#0f172a",
          swatch: null,
        };
      case "fallback":
        return {
          kind: "fallback",
          fill: null,
          ring: null,
          ink: "#0f172a",
          swatch: resolved.hex,
        };
    }
  }

  /** Build the PartyRowForResolver shape from a PartyMeta - mirrors the
   *  PartiesIndex.svelte helper so the avatar resolver sees a uniform
   *  row shape across surfaces. */
  export function partyRowFromMeta(meta: PartyMeta): PartyRowForResolver {
    return {
      party_id: meta.party_id,
      brand_colour: meta.brand_colour
        ? { hex: meta.brand_colour, confidence: "medium" }
        : null,
    };
  }

  /** Sentinel one-liner under the H1. Returns null when the party is
   *  not a sentinel (the caller skips the line). Citizen-tested text
   *  per docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md
   *  closure-ledger item 2 + TODO/20260613-party-deferred-followups-plan.md
   *  section 0 doctrine-lock (Citizen 1a/1b overrides Hans 1a/1b - body
   *  drops PUCL citation and "aggregate"/"residual" jargon). */
  export function sentinelFraming(party_id: string): string | null {
    if (party_id === "parties.IN.IND") {
      return (
        "Independent isn't one party. It's everyone who ran without a party - " +
        "thousands of different people across many decades. " +
        "The numbers below mix them all together."
      );
    }
    if (party_id === "parties.IN.NOTA") {
      return (
        "NOTA lets you vote against every candidate on the ballot. " +
        "Even if NOTA gets more votes than any candidate, " +
        "the leading candidate still wins - there is no re-election."
      );
    }
    return null;
  }

  /** Pure: should the NOTA-specific PUCL v. Union of India footnote
   *  render in the metadata footer? Only NOTA per Citizen verdict in
   *  TODO/20260613-party-deferred-followups-plan.md section 3
   *  ("footnote it or drop it" - we footnote in slate-400 small text
   *  so the citizen body strip stays jargon-free). */
  export function showPuclAttribution(party_id: string): boolean {
    return party_id === "parties.IN.NOTA";
  }

  /** Pure: render the W/L sparkline as a string of Unicode block chars.
   *  ▮ (filled square) = won; ▯ (empty square) = lost / no-contest. */
  export function sparkline(results: readonly ("W" | "L")[]): string {
    return results.map((r) => (r === "W" ? "\u25AE" : "\u25AF")).join("");
  }
</script>

<script lang="ts">
  import { loadPartyDetail } from "../lib/view-models/party-detail";
  import { partyIdFromSlug } from "../lib/slug";
  import { link } from "../lib/links";
  import { states } from "../lib/states.svelte";
  import TopicIcon from "../lib/TopicIcon.svelte";
  import DualAxisBarLine from "../lib/charts/DualAxisBarLine/DualAxisBarLine.svelte";
  import RecognitionStrip from "../lib/parties/RecognitionStrip.svelte";
  import PartyStrongholdMap from "../lib/parties/PartyStrongholdMap.svelte";
  import {
    homeStateEciCodes,
    mapPcStrongholdsToChoroplethRows,
  } from "../lib/parties/stronghold-choropleth-rows";
  import { formatLeaderSince } from "../lib/view-models/parties";

  interface Props {
    params: { slug: string };
  }
  let { params }: Props = $props();

  const slug = $derived(params.slug);
  const party_id = $derived(partyIdFromSlug(slug));

  let view_model = $state<PartyDetailViewModel | null>(null);
  let loaded = $state(false);
  let load_error = $state<string | null>(null);

  // Trigger the load whenever party_id changes (router replaces the
  // component on every navigation, so this is effectively once per
  // mount, but `$derived` + the effect makes it resilient under HMR).
  $effect(() => {
    let cancelled = false;
    loaded = false;
    load_error = null;
    view_model = null;
    loadPartyDetail(party_id)
      .then((vm) => {
        if (cancelled) return;
        view_model = vm;
        loaded = true;
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        load_error = err instanceof Error ? err.message : String(err);
        loaded = true;
      });
    return () => {
      cancelled = true;
    };
  });

  // Derived view shape used by the template.
  const meta = $derived(view_model?.metadata ?? null);
  const totals = $derived(view_model?.totals ?? null);
  const kpis = $derived(view_model ? computeKpis(view_model) : null);
  const avatar = $derived(
    meta
      ? getAvatarStyle(meta.party_id, partyRowFromMeta(meta), meta.is_sentinel)
      : null,
  );
  const sentinel_line = $derived(meta ? sentinelFraming(meta.party_id) : null);
  // LS body sub-line. Citizen-facing label is "Parliament" per the
  // PR-1 plan-doc 20260614 Hans H1 verdict; the chart sub-section sets
  // its own header text. We hardcode the body labels here so the test
  // can pin the sentence shape without going through a label registry.
  const ls_latest = $derived(
    view_model
      ? formatLatestSentence(view_model.ls_history, 543, "Parliament")
      : null,
  );
  // VS body sub-line. Total seats are state-specific (Tamil Nadu = 234,
  // UP = 403, etc.); the v1 page uses 0 (no "of N" denominator) because
  // a per-party state-Assembly bar mixes states. Future PR can split
  // the bar by state and surface the per-state denominator.
  const vs_latest = $derived(
    view_model
      ? formatLatestSentence(view_model.vs_history, 0, "State Assembly")
      : null,
  );
  const ls_peak = $derived(view_model?.totals.peak_ls_seats ?? 0);
  const ls_peak_year = $derived(view_model?.totals.peak_ls_year ?? 0);
  const vs_peak = $derived(view_model?.totals.peak_vs_seats ?? 0);
  const vs_peak_year = $derived(view_model?.totals.peak_vs_year ?? 0);

  // LS / VS chart series. Bars = seats; line = vote_share_pct (filter
  // out cycles with no vote-share row so the line never anchors at 0).
  const ls_bars = $derived(
    (view_model?.ls_history ?? []).map((p) => ({
      period_label: p.period_label,
      value: p.seats,
    })),
  );
  const ls_line = $derived(
    (view_model?.ls_history ?? [])
      .filter((p) => p.vote_share_pct != null)
      .map((p) => ({
        period_label: p.period_label,
        value: p.vote_share_pct!,
      })),
  );
  const vs_bars = $derived(
    (view_model?.vs_history ?? []).map((p) => ({
      period_label: p.period_label,
      value: p.seats,
    })),
  );
  const vs_line = $derived(
    (view_model?.vs_history ?? [])
      .filter((p) => p.vote_share_pct != null)
      .map((p) => ({
        period_label: p.period_label,
        value: p.vote_share_pct!,
      })),
  );

  // Bar colour = party brand colour via the resolver.
  const bar_color = $derived.by(() => {
    if (!meta) return "#64748b";
    return getPartyColor(meta.party_id, partyRowFromMeta(meta)).hex;
  });

  // PR-12 stronghold choropleth: derive the PC-side choropleth rows
  // from the LS stronghold mart and the home-state ECI code set from
  // parties.csv. The mapper silently drops rows whose entity_id does
  // not match the PC pattern; the home_states set drives state-
  // cropping for parties with <= 3 home states. National parties
  // (home_states empty or >3) render full-India. See
  // [stronghold-choropleth-rows.ts](../lib/parties/stronghold-choropleth-rows.ts).
  const pcStrongholdRows = $derived(
    view_model
      ? mapPcStrongholdsToChoroplethRows(view_model.ls_strongholds)
      : [],
  );
  const homeStates = $derived(
    meta ? homeStateEciCodes(meta.home_state_codes) : new Set<string>(),
  );

  // Recognition badge label.
  function recognitionLabel(scope: string | null): string {
    switch (scope) {
      case "national":
        return "National party";
      case "state":
        return "State party";
      case "unrecognised_registered":
        return "Unrecognised registered party";
      case "defunct":
        return "Defunct";
      case "sentinel":
        return "Special";
      default:
        return "Recognition unknown";
    }
  }
</script>

<main
  class="max-w-5xl mx-auto p-4 sm:p-6 space-y-6"
  data-testid="party-detail"
  data-party-id={party_id}
>
  {#if !loaded}
    <section
      class="rounded border border-slate-200 bg-white p-6 text-center text-sm text-slate-500"
      data-testid="party-loading"
    >
      Loading party details...
    </section>
  {:else if load_error}
    <section
      class="rounded border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700"
      data-testid="party-error"
    >
      Couldn't load party: {load_error}
    </section>
  {:else if !view_model || !meta || !avatar || !kpis || !totals}
    <!-- Not found: parties.csv has no row for this slug (typo or
         retired party). Friendly recovery link back to the index. -->
    <section
      class="rounded border border-slate-200 bg-white p-8 text-center space-y-3"
      data-testid="party-not-found"
    >
      <h1 class="text-2xl font-bold text-slate-900">Party not found</h1>
      <p class="text-sm text-slate-600">
        No party in the canonical store matches the slug
        <code class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs"
          >{slug}</code
        >.
      </p>
      <p class="text-sm">
        <a
          href={link.parties()}
          class="text-sky-600 hover:underline"
          data-testid="party-not-found-back"
          >Browse every party in the canonical store -&gt;</a
        >
      </p>
    </section>
  {:else}
    <!-- (1) Header card -->
    <header
      class="flex items-start gap-4 sm:gap-6"
      data-testid="party-header"
    >
      <div
        class="relative shrink-0 flex h-20 w-20 items-center justify-center rounded-md text-xl font-bold tracking-wider"
        style:background-color={avatar.fill ?? "var(--surface)"}
        style:color={avatar.ink}
        style:border={avatar.ring
          ? `3px solid ${avatar.ring}`
          : avatar.kind === "fallback"
            ? "1px solid var(--line)"
            : "none"}
        data-testid="party-avatar"
        data-treatment={avatar.kind}
      >
        {meta.short}
        {#if avatar.swatch}
          <span
            class="absolute -bottom-1 -right-1 inline-block h-3 w-3 rounded-full ring-2 ring-white"
            style:background-color={avatar.swatch}
          ></span>
        {/if}
      </div>
      <div class="flex-1 min-w-0 space-y-1.5">
        <h1
          class="text-2xl sm:text-3xl font-bold text-slate-900 truncate"
          data-testid="party-name"
        >
          {meta.full || meta.short}
        </h1>
        <p class="text-sm text-slate-600" data-testid="party-subline">
          {recognitionLabel(meta.recognition_scope)}{#if ls_peak > 0}
            <span class="text-slate-400"> . </span>peak {ls_peak} Parliament seats in {ls_peak_year}
          {/if}
        </p>
        {#if meta.leader && !meta.is_sentinel}
          <p
            class="text-sm text-slate-600"
            data-testid="party-leader-line"
          >
            Led by <span class="font-semibold text-slate-800"
              >{meta.leader.name}</span
            >
            <span class="text-slate-500"
              >({meta.leader.role} since {formatLeaderSince(
                meta.leader.since,
              )})</span
            >
          </p>
        {/if}
        {#if sentinel_line}
          <p
            class="text-xs text-slate-500 italic max-w-prose"
            data-testid="party-sentinel-line"
          >
            {sentinel_line}
          </p>
        {/if}
      </div>
    </header>

    <!-- (2) Latest-of one-liner per body. Hidden for sentinels until
         a meaningful value lands. -->
    {#if !meta.is_sentinel}
      {#if ls_latest}
        <p class="text-sm text-slate-700" data-testid="party-latest-ls">
          {ls_latest}
        </p>
      {/if}
      {#if vs_latest}
        <p class="text-sm text-slate-700" data-testid="party-latest-vs">
          {vs_latest}
        </p>
      {/if}
    {/if}

    <!-- (3) KPI strip 2x2 -->
    {#if !meta.is_sentinel}
      <section
        class="grid grid-cols-2 md:grid-cols-4 gap-2"
        data-testid="party-kpis"
      >
        <div
          class="rounded border border-slate-200 bg-white p-3 text-center"
          data-testid="party-kpi-ls-seats"
        >
          <div class="text-xs text-slate-500">Parliament seats won</div>
          <div class="text-xl font-bold tabular-nums text-slate-900">
            {kpis.ls_seats.toLocaleString()}
          </div>
        </div>
        <div
          class="rounded border border-slate-200 bg-white p-3 text-center"
          data-testid="party-kpi-vs-seats"
        >
          <div class="text-xs text-slate-500">State Assembly seats won</div>
          <div class="text-xl font-bold tabular-nums text-slate-900">
            {kpis.vs_seats.toLocaleString()}
          </div>
        </div>
        <div
          class="rounded border border-slate-200 bg-white p-3 text-center"
          data-testid="party-kpi-cycles"
        >
          <div class="text-xs text-slate-500">Elections contested</div>
          <div class="text-xl font-bold tabular-nums text-slate-900">
            {kpis.elections_contested.toLocaleString()}
          </div>
        </div>
        <div
          class="rounded border border-slate-200 bg-white p-3 text-center"
          data-testid="party-kpi-range"
        >
          <div class="text-xs text-slate-500">Active</div>
          <div class="text-xl font-bold tabular-nums text-slate-900">
            {kpis.active_range}
          </div>
        </div>
      </section>
    {/if}

    <!-- (4) LS DualAxisBarLine -->
    {#if !meta.is_sentinel && ls_bars.length > 0}
      <section class="space-y-2" data-testid="party-ls-chart">
        <RecognitionStrip party_id={meta.party_id} />
        <div class="flex items-end justify-between">
          <h2 class="text-lg font-semibold text-slate-800">
            Parliament - every general election contested
          </h2>
          {#if ls_peak > 0}
            <span class="text-xs text-slate-500">
              best: {ls_peak} seats in {ls_peak_year}
            </span>
          {/if}
        </div>
        <DualAxisBarLine
          bars={ls_bars}
          line={ls_line}
          bar_color={bar_color}
          bar_y_label="Seats"
          line_y_label="Vote %"
          bar_format={(n) => n.toLocaleString()}
          line_format={(n) => `${n.toFixed(1)}%`}
          methodology_breaks={view_model.ls_methodology_breaks}
        />
        {#if view_model.ls_methodology_breaks.length > 0}
          <p
            class="text-[11px] text-slate-400"
            data-testid="party-ls-methodology-caption"
          >
            1) delim 1967 (Parliament constituency boundaries shifted from
            the 1951-Order delimitation to the 1962 Delimitation Commission
            output); 2) delim 1976 (boundaries shifted to the 1971-72
            Delimitation Commission output, frozen by 42nd Amendment until
            2008).
          </p>
        {/if}
      </section>
    {/if}

    <!-- (5) VS DualAxisBarLine -->
    {#if !meta.is_sentinel && vs_bars.length > 0}
      <section class="space-y-2" data-testid="party-vs-chart">
        <div class="flex items-end justify-between">
          <h2 class="text-lg font-semibold text-slate-800">
            State Assembly - every election contested
          </h2>
          {#if vs_peak > 0}
            <span class="text-xs text-slate-500">
              best: {vs_peak} seats in {vs_peak_year}
            </span>
          {/if}
        </div>
        <DualAxisBarLine
          bars={vs_bars}
          line={vs_line}
          bar_color={bar_color}
          bar_y_label="Seats"
          line_y_label="Vote %"
          bar_format={(n) => n.toLocaleString()}
          line_format={(n) => `${n.toFixed(1)}%`}
        />
      </section>
    {/if}

    <!-- (6) Strongholds top-10 per body -->
    {#if !meta.is_sentinel && (view_model.ls_strongholds.length > 0 || view_model.vs_strongholds.length > 0)}
      <section class="space-y-3" data-testid="party-strongholds">
        <h2 class="text-lg font-semibold text-slate-800">Strongholds</h2>
        <p
          class="text-xs text-slate-500"
          data-testid="party-strongholds-coverage"
        >
          Strongholds computed from Parliament elections 1999-2024 and
          State Assembly elections 2008-2026. Earlier history not yet
          ingested.
        </p>

        <!-- PR-12 stronghold choropleth (PC body only this PR; AC
             deferred per the delim mismatch documented in
             stronghold-choropleth-rows.ts). Hidden under 640px per
             Jony 2g + Citizen 3a (the existing top-10 text list
             below remains visible across all viewports). -->
        {#if pcStrongholdRows.length > 0}
          <div class="hidden sm:block" data-testid="party-pc-stronghold-map-wrap">
            <PartyStrongholdMap
              topojson_path="/boundaries/electoral/delim=2024/pc/all.topojson"
              feature_key="unique_id"
              state_property="state_ut_code"
              rows={pcStrongholdRows}
              brand_colour={meta.brand_colour}
              home_states={homeStates}
              title="Parliament strongholds map"
              caption="Stronghold map shows this party's top-10 constituencies by lifetime wins. For per-cycle winners see the respective election pages."
              data_testid="party-pc-stronghold-map"
              polygon_testid="pc-stronghold"
              width={320}
              height={360}
            />
          </div>
        {/if}

        {#if view_model.ls_strongholds.length > 0}
          <div class="space-y-1" data-testid="party-ls-strongholds">
            <h3 class="text-sm font-semibold text-slate-700">Parliament strongholds</h3>
            <ul
              class="divide-y divide-slate-100 border border-slate-200 rounded bg-white"
            >
              {#each view_model.ls_strongholds as s (s.entity_id)}
                {@const winRate = ((s.wins / s.contested) * 100).toFixed(0)}
                <li
                  class="flex items-center justify-between gap-2 px-3 py-2 text-sm"
                  data-testid="party-stronghold-ls"
                >
                  <span class="flex-1 truncate text-slate-800"
                    >{s.constituency_name || s.entity_id}</span
                  >
                  <span class="shrink-0 text-slate-500 tabular-nums">
                    won {s.wins} of {s.contested} ({winRate}%)
                  </span>
                  <span
                    class="shrink-0 font-mono text-xs text-slate-400 tracking-wider"
                    title={s.results.join("")}
                  >{sparkline(s.results)}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if view_model.vs_strongholds.length > 0}
          <div class="space-y-1" data-testid="party-vs-strongholds">
            <h3 class="text-sm font-semibold text-slate-700">State Assembly strongholds</h3>
            <ul
              class="divide-y divide-slate-100 border border-slate-200 rounded bg-white"
            >
              {#each view_model.vs_strongholds as s (s.entity_id)}
                {@const winRate = ((s.wins / s.contested) * 100).toFixed(0)}
                <li
                  class="flex items-center justify-between gap-2 px-3 py-2 text-sm"
                  data-testid="party-stronghold-vs"
                >
                  <span class="flex-1 truncate text-slate-800"
                    >{s.constituency_name || s.entity_id}</span
                  >
                  <span class="shrink-0 text-slate-500 tabular-nums">
                    won {s.wins} of {s.contested} ({winRate}%)
                  </span>
                  <span
                    class="shrink-0 font-mono text-xs text-slate-400 tracking-wider"
                    title={s.results.join("")}
                  >{sparkline(s.results)}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </section>
    {/if}

    <!-- (7) Metadata footer -->
    <footer
      class="border-t border-slate-200 pt-4 space-y-2 text-xs text-slate-600"
      data-testid="party-metadata"
    >
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {#if meta.founded_year}
          <span
            class="inline-flex items-center gap-1.5"
            data-testid="party-meta-founded"
          >
            <TopicIcon name="calendar" cls="w-3.5 h-3.5 text-slate-500 shrink-0" />
            Founded {meta.founded_year}
          </span>
        {/if}
        {#if meta.dissolved_year}
          <span
            class="inline-flex items-center gap-1.5"
            data-testid="party-meta-dissolved"
          >
            <TopicIcon name="x-circle" cls="w-3.5 h-3.5 text-slate-500 shrink-0" />
            Dissolved {meta.dissolved_year}
          </span>
        {/if}
        <span
          class="inline-flex items-center gap-1.5"
          data-testid="party-meta-recognition"
        >
          <TopicIcon name="landmark" cls="w-3.5 h-3.5 text-slate-500 shrink-0" />
          {recognitionLabel(meta.recognition_scope)}
        </span>
        {#each meta.home_state_codes as code (code)}
          <span
            class="inline-flex items-center gap-1.5"
            data-testid="party-meta-home-state"
          >
            <TopicIcon name="map-pin" cls="w-3.5 h-3.5 text-slate-500 shrink-0" />
            {states.name(code) || code}
          </span>
        {/each}
        {#if meta.name_native_script}
          <span
            class="inline-flex items-center gap-1.5 italic"
            data-testid="party-meta-native"
          >
            <TopicIcon name="languages" cls="w-3.5 h-3.5 text-slate-500 shrink-0" />
            {meta.name_native_script}
          </span>
        {/if}
        {#if meta.wikipedia}
          <a
            href={meta.wikipedia}
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1.5 text-sky-600 hover:underline"
            data-testid="party-meta-wiki"
          >
            <TopicIcon name="external-link" cls="w-3.5 h-3.5 shrink-0" />
            Wikipedia
          </a>
        {/if}
      </div>
      {#if showPuclAttribution(meta.party_id)}
        <p
          class="text-[11px] text-slate-400 mt-2"
          data-testid="party-nota-puc-attribution"
        >
          Introduced by the Supreme Court in PUCL v. Union of India (Sep 2013).
        </p>
      {/if}
    </footer>
  {/if}
</main>
