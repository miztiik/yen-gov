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
   *   (6) Strongholds top-10 per body - [state name] - [constituency]
   *       + right-flush 10-cell SVG dot strip (PR-5)
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
  import { glyphUrlFor } from "../lib/PartySymbolGlyph.svelte";

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

  /** Avatar treatment - geometry is uniformly a circle; the shape
   *  decision is "render symbol image", "render short token", or
   *  "render sentinel-grey token". Jony J4 (TODO/20260614-party-page-
   *  reimagination-plan.md section 6): symbol presence + sentinel
   *  status collapse the prior 4-tier (anchor/brand/fallback/sentinel)
   *  taxonomy into 3 visual treatments that all share the circle
   *  geometry. Brand colour lives on the ring; never behind a symbol
   *  (ECI symbols are authored for high contrast on white - the lotus
   *  on saffron was the prior page's worst signal-to-noise). */
  export type AvatarKind = "symbol" | "token" | "sentinel";

  /** Pure: derive the avatar style for the header card.
   *  - `symbol`:   paper-white fill + brand ring + centred SVG image.
   *  - `token`:    paper-white fill + brand ring + centred short token.
   *  - `sentinel`: slate-200 fill + NO ring + slate-600 token. The
   *                absent ring is the visual signal "not a party in
   *                the same sense" - matches the recognition strip. */
  export interface AvatarStyle {
    kind: AvatarKind;
    /** Background fill for the circle (always set). */
    fill: string;
    /** Ring colour - brand colour for symbol/token; null for sentinel. */
    ring: string | null;
    /** Token ink colour - used when kind is "token" or "sentinel". */
    ink: string;
    /** Resolved symbol image URL - non-null iff kind is "symbol". */
    symbol_url: string | null;
  }

  export function getAvatarStyle(
    party_id: string,
    row: PartyRowForResolver | null,
    is_sentinel: boolean,
    symbol_asset: string | null,
  ): AvatarStyle {
    if (is_sentinel) {
      return {
        kind: "sentinel",
        fill: "#e2e8f0", // slate-200 - the canonical sentinel neutral
        ring: null,
        ink: "#475569", // slate-600
        symbol_url: null,
      };
    }
    const resolved = getPartyColor(party_id, row);
    const symbol_url = glyphUrlFor(symbol_asset);
    if (symbol_url) {
      return {
        kind: "symbol",
        fill: "var(--surface)",
        ring: resolved.hex,
        ink: "#0f172a", // slate-900 (unused at render-time for kind=symbol)
        symbol_url,
      };
    }
    return {
      kind: "token",
      fill: "var(--surface)",
      ring: resolved.hex,
      ink: "#0f172a", // slate-900
      symbol_url: null,
    };
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
</script>

<script lang="ts">
  import { loadPartyDetail } from "../lib/view-models/party-detail";
  import { partyIdFromSlug } from "../lib/slug";
  import { link } from "../lib/links";
  import { assetUrl } from "../lib/config/cdn";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { route } from "../lib/router.svelte";
  import TopicIcon from "../lib/TopicIcon.svelte";
  import DualAxisBarLine from "../lib/charts/DualAxisBarLine/DualAxisBarLine.svelte";
  import RecognitionStrip from "../lib/parties/RecognitionStrip.svelte";
  // Row E (TODO/20260617-party-page-polish-and-cdn-config-plan.md,
  // Jony P1 + Citizen): the two strongholds lists (Parliament + State
  // Assembly) render via this shared component - a two-line row
  // hierarchy + colour-coded strike-rate badge, top-5 + "Show all".
  import StrongholdList from "../lib/parties/StrongholdList.svelte";
  // Wave-F F6: PartyAboutCard.svelte was RIP'd per CLAUDE.md section 0.5
  // (RIP doctrine) - the metadata it carried (founding range, recognition,
  // Wikipedia link) collapses into the per-party header meta-strip below
  // the "Led by" line. recognitionLabel migrated to its own pure module
  // so it survives the AboutCard delete.
  import { recognitionLabel } from "../lib/parties/recognition-label";
  // PR-7: "Where this party sits today" strip sits directly under the
  // header card and above the latest-of one-liners on /parties/<slug>.
  // The view-model is built upstream by `loadPartyCurrentStrength`
  // and arrives on `view_model.current_strength`; this component
  // self-suppresses for sentinels (defence in depth) and for parties
  // with no contested history.
  import PartyCurrentStrength from "../lib/parties/PartyCurrentStrength.svelte";
  // PR-8: "Who they ride with" Alliance Context strip sits directly
  // under the Current Strength strip. The view-model is built by
  // `loadPartyAllianceContext` and arrives on
  // `view_model.alliance_context`; this component self-suppresses for
  // sentinels (defence in depth) and for parties with no alliance
  // rows on file (Independent + new entrants).
  import PartyAllianceContext from "../lib/parties/PartyAllianceContext.svelte";
  // Row C: the five inline per-card `SourceList` mounts + the
  // standalone "About this page" link are retired in favour of ONE
  // page-foot provenance block. `PartyProvenanceFooter` states each
  // publisher once (ECI for the data cards, Wikipedia for alliance
  // line-ups), keeps every name clickable (Holy Law #9), then renders
  // the single "About this page" link (the `docsUrl()` seam moved into
  // the footer with that link).
  import PartyProvenanceFooter from "../lib/parties/PartyProvenanceFooter.svelte";
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
      ? getAvatarStyle(
          meta.party_id,
          partyRowFromMeta(meta),
          meta.is_sentinel,
          meta.symbol_asset,
        )
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

  // PR-10 of TODO/20260614-party-page-reimagination-plan.md: composite
  // bar data for `DualAxisBarLine mode="composite"`. Each row carries
  // vote_share_pct as the bar value + (seats_won, seats_contested) as
  // the conversion-ratio inputs. Filter cycles with null vote-share or
  // null/zero contested so the composite renderer always has a finite
  // ratio to plot. Cycles where the party didn't contest collapse off
  // the chart (citizen reads "no bar" as "didn't run"); the bar HEIGHT
  // encoding makes a zero-seat / 100%-contested cycle still informative
  // (full-height grey bar with no darker overlay = ran widely, won
  // nothing), which the seats-only encoding could not surface.
  const ls_bars_composite = $derived(
    (view_model?.ls_history ?? [])
      .filter((p) => p.vote_share_pct != null && p.contested != null && p.contested > 0)
      .map((p) => ({
        period_label: p.period_label,
        value: p.vote_share_pct!,
        seats_won: p.seats,
        seats_contested: p.contested!,
      })),
  );
  const vs_bars_composite = $derived(
    (view_model?.vs_history ?? [])
      .filter((p) => p.vote_share_pct != null && p.contested != null && p.contested > 0)
      .map((p) => ({
        period_label: p.period_label,
        value: p.vote_share_pct!,
        seats_won: p.seats,
        seats_contested: p.contested!,
      })),
  );

  // Bar colour = party brand colour via the resolver.
  const bar_color = $derived.by(() => {
    if (!meta) return "#64748b";
    return getPartyColor(meta.party_id, partyRowFromMeta(meta)).hex;
  });

  // PR-8a (D8c of TODO/20260615-party-page-citizen-fixes-plan.md):
  // the 320x360 stronghold-thumbnail component + its
  // pc-row / home-state derivations + the sibling helper module
  // were RIP'd per section 0.5 (RIP doctrine). The PR-7
  // state-prefixed one-line stronghold tally below carries the
  // geographic signal textually; git is the backup if a richer
  // interactive map is needed later.

  // Recognition badge label is sourced from the extracted
  // `recognition-label` helper module (Hans H7 vocabulary, originally
  // PR-6, lifted out in Wave-F F6 so the helper outlives the deleted
  // PartyAboutCard). Single source of truth - the in-header subline
  // and the meta-strip render the same string for the same scope.

  // PR-12 (D12 of TODO/20260615-party-page-citizen-fixes-plan.md): per-
  // route crumb chain mounted via the shared `<Breadcrumb>` primitive.
  // Reactive on route navigation AND on async catalogue load (the
  // `partyCrumbs` builder reads `states` reactively for the home-state
  // fallback in future widenings). The shared component self-suppresses
  // single-leaf chains; the partyCrumbs builder always returns 3 crumbs
  // (Home -> Parties -> <slug>) so the bar renders on every party page.
  const crumbs = $derived(route.crumbs ? route.crumbs(route.params) : []);
</script>

<Breadcrumb {crumbs} />

<PageContainer
  width="wide"
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
        class="relative shrink-0 flex h-20 w-20 items-center justify-center rounded-full"
        style:background-color={avatar.fill}
        style:border={avatar.ring ? `3px solid ${avatar.ring}` : "none"}
        data-testid="party-avatar"
        data-treatment={avatar.kind}
      >
        {#if avatar.kind === "symbol" && avatar.symbol_url}
          <img
            src={avatar.symbol_url}
            width="48"
            height="48"
            alt=""
          />
        {:else}
          <span
            class="text-xl font-bold tracking-wider"
            style:color={avatar.ink}>{meta.short}</span
          >
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
        <!-- Wave-F F6: compact meta-strip replacing the deleted
             PartyAboutCard side-rail. Inlined into the header so the
             page no longer needs an `lg:` grid wrapper. Renders the
             three citizen-facing facts that survived the AboutCard
             RIP:
               1) Active range (founded - dissolved) when at least one
                  endpoint is known.
               2) Recognition vocabulary (Hans H7 - "Nationally
                  recognised party" / "State-recognised party" / etc.).
                  The same string already renders in the subline above
                  for live parties; the meta-strip surfaces it again as
                  a separator-prefixed item for visual symmetry.
               3) Wikipedia link, rendered with the real CC BY-SA 4.0
                  puzzle-globe asset at `/icons/wikipedia.svg` (Wave-F
                  F1) instead of the prior hand-minted W glyph behind
                  TopicIcon.
             HQ + ideology + official website (named in the brief) are
             not on `PartyMeta` and intentionally omitted; restoring
             them is a separate Hans+Max data-shape PR. -->
        {#if !meta.is_sentinel && (meta.founded_year || meta.dissolved_year || meta.wikipedia)}
          <p
            class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500"
            data-testid="party-meta-strip"
          >
            {#if meta.founded_year !== null && meta.dissolved_year !== null}
              <span data-testid="party-meta-active">Active {meta.founded_year}-{meta.dissolved_year}</span>
            {:else if meta.founded_year !== null}
              <span data-testid="party-meta-active">Active since {meta.founded_year}</span>
            {:else if meta.dissolved_year !== null}
              <span data-testid="party-meta-active">Dissolved {meta.dissolved_year}</span>
            {/if}
            {#if meta.recognition_scope}
              <span aria-hidden="true" class="text-slate-300">.</span>
              <span data-testid="party-meta-recognition">{recognitionLabel(meta.recognition_scope)}</span>
            {/if}
            {#if meta.wikipedia}
              <span aria-hidden="true" class="text-slate-300">.</span>
              <a
                href={meta.wikipedia}
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1 text-sky-700 hover:underline"
                aria-label="Wikipedia"
                title="Wikipedia"
                data-testid="party-meta-wikipedia"
              ><img
                  src={assetUrl("/brands/wikipedia.svg")}
                  alt="Wikipedia"
                  title="Wikipedia"
                  width="16"
                  height="16"
                  class="h-4 w-4 inline-block"
                /></a>
            {/if}
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

    <!-- PR-7: "Where this party sits today" strip. Sits directly
         under the header card and above the latest-of one-liners.
         Hidden for sentinel parties (NOTA / UNK) via both the upstream
         view-model returning null AND the component's own
         `is_sentinel` short-circuit (defence in depth). -->
    <PartyCurrentStrength
      current_strength={view_model.current_strength}
      is_sentinel={meta.is_sentinel}
    />

    <!-- PR-8: "Who they ride with" Alliance Context strip. Sits
         directly under the Current Strength strip and above the
         latest-of one-liners. Hidden for sentinels (NOTA / UNK),
         Independent (parties.IN.IND), and parties with no alliance
         rows on file - via both the upstream view-model returning
         null AND the component's own short-circuit. -->
    <PartyAllianceContext
      alliance_context={view_model.alliance_context}
      is_sentinel={meta.is_sentinel}
    />

    <!--
      PR-6 layout: header sits full-width above. Wave-F F6 RIP'd
      the right-column AboutCard, so the prior `1fr+240px` lg-grid
      collapses to a single full-width column at every breakpoint.
      The wrapper survives as a `space-y-6` container so the inter-
      section vertical rhythm is unchanged. PUCL attribution lives
      as a full-width block AFTER this container for NOTA.
    -->
    <div class="space-y-6 min-w-0">

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
          <div class="inline-flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <TopicIcon name="landmark" cls="w-4 h-4 text-slate-500 shrink-0" />
            <span>Parliament seats won</span>
          </div>
          <div class="text-xl font-bold tabular-nums text-slate-900">
            {kpis.ls_seats.toLocaleString()}
          </div>
        </div>
        <div
          class="rounded border border-slate-200 bg-white p-3 text-center"
          data-testid="party-kpi-vs-seats"
        >
          <div class="inline-flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <TopicIcon name="flag" cls="w-4 h-4 text-slate-500 shrink-0" />
            <span>State Assembly seats won</span>
          </div>
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
        <RecognitionStrip
          party_id={meta.party_id}
          symbol_url={avatar.symbol_url}
        />
        <div class="flex items-end justify-between">
          <h2 class="text-lg font-semibold text-slate-800 inline-flex items-center gap-2">
            <TopicIcon name="landmark" cls="w-5 h-5 text-slate-500 shrink-0" />
            <span>Parliament - every general election contested</span>
          </h2>
          {#if ls_peak > 0}
            <span class="text-xs text-slate-500 inline-flex items-center gap-1">
              <TopicIcon
                name="trophy"
                cls="inline-block w-3.5 h-3.5 text-amber-600 shrink-0"
              />
              {ls_peak} seats in {ls_peak_year}
            </span>
          {/if}
        </div>
        <DualAxisBarLine
          mode="composite"
          bars={ls_bars_composite}
          line={[]}
          bar_color={bar_color}
          bar_y_label="Vote share %"
          bar_format={(n) => `${n.toFixed(1)}%`}
          methodology_breaks={view_model.ls_methodology_breaks}
        />
        {#if view_model.ls_methodology_breaks.length > 0}
          <p
            class="text-[11px] text-slate-400"
            data-testid="party-ls-methodology-caption"
          >
            Markers indicate years where measurement methodology changed -
            hover to see what changed.
          </p>
        {/if}
      </section>
    {/if}

    <!-- (5) VS DualAxisBarLine -->
    {#if !meta.is_sentinel && vs_bars.length > 0}
      <section class="space-y-2" data-testid="party-vs-chart">
        <div class="flex items-end justify-between">
          <h2 class="text-lg font-semibold text-slate-800 inline-flex items-center gap-2">
            <TopicIcon name="flag" cls="w-5 h-5 text-slate-500 shrink-0" />
            <span>State Assembly - every election contested</span>
          </h2>
          {#if vs_peak > 0}
            <span class="text-xs text-slate-500 inline-flex items-center gap-1">
              <TopicIcon
                name="trophy"
                cls="inline-block w-3.5 h-3.5 text-amber-600 shrink-0"
              />
              {vs_peak} seats in {vs_peak_year}
            </span>
          {/if}
        </div>
        <DualAxisBarLine
          mode="composite"
          bars={vs_bars_composite}
          line={[]}
          bar_color={bar_color}
          bar_y_label="Vote share %"
          bar_format={(n) => `${n.toFixed(1)}%`}
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

        {#if view_model.ls_strongholds.length > 0}
          <div class="space-y-1" data-testid="party-ls-strongholds">
            <h3 class="text-sm font-semibold text-slate-700 inline-flex items-center gap-2">
              <TopicIcon name="landmark" cls="w-4 h-4 text-slate-500 shrink-0" />
              <span>Parliament strongholds</span>
            </h3>
            <StrongholdList rows={view_model.ls_strongholds} />
          </div>
        {/if}

        {#if view_model.vs_strongholds.length > 0}
          <div class="space-y-1" data-testid="party-vs-strongholds">
            <h3 class="text-sm font-semibold text-slate-700 inline-flex items-center gap-2">
              <TopicIcon name="flag" cls="w-4 h-4 text-slate-500 shrink-0" />
              <span>State Assembly strongholds</span>
            </h3>
            <StrongholdList rows={view_model.vs_strongholds} />
          </div>
        {/if}
      </section>
    {/if}

    <!-- (7) About this party (PR-6, Wave-F F6).
         Card RIP'd: the side-rail mount + mobile mount + lg-grid
         wrapper were ALL removed in Wave-F F6 per CLAUDE.md §0.5
         (RIP doctrine). The metadata the card carried (founding
         range / recognition / Wikipedia) now lives inline in the
         per-party header meta-strip below the "Led by" line.
         The PUCL attribution for NOTA survives as the full-width
         block below; the "About this page →" link survives as the
         footer below it. -->
    </div><!-- /.space-y-6 min-w-0 (full-width body container) -->

    {#if showPuclAttribution(meta.party_id)}
      <p
        class="text-[11px] text-slate-400"
        data-testid="party-nota-puc-attribution"
      >
        Introduced by the Supreme Court in PUCL v. Union of India (Sep 2013).
      </p>
    {/if}

    <!-- Row C: page-foot provenance block. ONE mapped sentence that
         states each publisher once (ECI for the data cards, Wikipedia
         for alliance line-ups), every name clickable (Holy Law #9),
         followed by the single "About this page ->" link (lifted from
         the retired standalone footer). Replaces the five inline
         per-card SourceList pill rows. The sentence self-suppresses
         when no publisher resolved; the About link always renders. -->
    <PartyProvenanceFooter provenance={view_model.provenance} />
  {/if}
</PageContainer>
