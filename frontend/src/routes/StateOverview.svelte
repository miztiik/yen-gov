<script module lang="ts">
  // Pure helper for the State Overview KPI tile hero block. Extracted so
  // vitest pins the count + tile-set contract without mounting the
  // component (yen-gov pattern: see CountingMethodDoc.svelte +
  // IndicatorDoc.svelte for the <script module> + sibling .test.ts
  // precedent). The helper is total: every loading / partial-data
  // permutation has a defined output so a renderer that forgets a guard
  // still degrades gracefully.

  import type { ConstituencyEntry } from "../lib/data";
  import type { District } from "../lib/view-models/districts";

  /** One KPI tile spec consumed by the grid. `icon_name` is the
   *  TopicIcon registry key (kebab-case filename under public/icons/
   *  without `.svg`). `chip_bg` + `chip_fg` are literal Tailwind class
   *  strings so JIT picks them up (NOT dynamic colour interpolation -
   *  Tailwind cannot see `bg-${color}-500/15` at runtime). */
  export interface KpiTile {
    readonly key: string;
    readonly label: string;
    readonly value: string;
    readonly icon_name: string;
    readonly chip_bg: string;
    readonly chip_fg: string;
  }

  const INT_FMT_IN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
  const COMPACT_FMT_IN = new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 2,
  });

  /** Slugs of Indian UTs that do NOT have a Vidhan Sabha (state
   *  legislature). Administered by the Centre via a Lt. Governor; no
   *  elected MLAs, no constituencies.json SOT, no "Assembly Map" surface.
   *  Excludes Delhi (U05), Puducherry (U07), Jammu & Kashmir (U08) which
   *  DO have assemblies. Structural fact of Indian polity, not a data gap;
   *  hard-coded as a 5-row Set rather than derived from absence of SOT so
   *  a bootstrap-pending state (genuine data gap) gets the "Assembly Map"
   *  copy + spinner, not the "no legislature" copy.
   *
   *  The slugs MUST be the literal output of `slugify(display_name)`
   *  from `datasets/taxonomy/entities.json` (the runtime catalogue
   *  `states.slug()` resolves through), NOT the short slugs in the
   *  `state_iso_seed.csv` backend bootstrap. U01's display_name is
   *  "Andaman and Nicobar Islands" so the slug carries the `-islands`
   *  suffix; the seed file's shorter `andaman-and-nicobar` is never
   *  what the frontend router sees. */
  export const NO_ASSEMBLY_UT_SLUGS: ReadonlySet<string> = new Set([
    "andaman-and-nicobar-islands",
    "chandigarh",
    "dadra-and-nagar-haveli-and-daman-and-diu",
    "ladakh",
    "lakshadweep",
  ]);

  /** Builds the KPI tile set from reference data + summary electors.
   *
   *  - `acs === null`: empty array (caller decides whether to render
   *    skeletons or hide the section based on `acs_status`).
   *  - `districts === null` with `acs` ready: DISTRICTS tile shows "-"
   *    (em-dash) so the row count stays stable rather than the column
   *    silently reflowing while a slower fetch resolves.
   *  - `electors` null / 0 / undefined: TOTAL VOTERS tile omitted; the
   *    grid reflows from 5 to 4 columns at lg.
   *  - RESERVED counts SC + ST (everything that is not "GEN"); GENERAL
   *    counts "GEN". Sum equals acs.length by construction. */
  export function buildKpiTiles(
    acs: readonly ConstituencyEntry[] | null,
    districts: readonly District[] | null,
    electors: number | null | undefined,
  ): KpiTile[] {
    if (!acs) return [];
    const reserved = acs.filter(c => c.reservation !== "GEN").length;
    const general = acs.length - reserved;
    const tiles: KpiTile[] = [
      {
        key: "assemblies",
        label: "Assemblies",
        value: INT_FMT_IN.format(acs.length),
        icon_name: "landmark",
        chip_bg: "bg-blue-500/15",
        chip_fg: "text-blue-700",
      },
      {
        key: "districts",
        label: "Districts",
        value: districts ? INT_FMT_IN.format(districts.length) : "-",
        icon_name: "compass",
        chip_bg: "bg-purple-500/15",
        chip_fg: "text-purple-700",
      },
      {
        key: "reserved",
        label: "Reserved",
        value: INT_FMT_IN.format(reserved),
        icon_name: "shield",
        chip_bg: "bg-red-500/15",
        chip_fg: "text-red-700",
      },
      {
        key: "general",
        label: "General",
        value: INT_FMT_IN.format(general),
        icon_name: "shield",
        chip_bg: "bg-slate-500/15",
        chip_fg: "text-slate-700",
      },
    ];
    if (electors != null && electors > 0) {
      tiles.push({
        key: "voters",
        label: "Total voters",
        value: COMPACT_FMT_IN.format(electors),
        icon_name: "users",
        chip_bg: "bg-cyan-500/15",
        chip_fg: "text-cyan-700",
      });
    }
    return tiles;
  }
</script>

<script lang="ts">
  // Types `ConstituencyEntry` and `District` are imported in the
  // `<script module>` block above and shared with the instance scope
  // (Svelte 5 module/instance share the same TS module). Importing
  // them here too would duplicate-identifier under svelte-check.
  import { fetchConstituencies } from "../lib/data";
  import { loadDistricts } from "../lib/view-models/districts";
  // PR-F (Phase 1.3b): StateOverview reads state-hub data through the
  // canonical Parquet store via DuckDB-WASM (view-models/state-overview.ts),
  // replacing the per-shard result.summary.json fetch. PR-G (Phase 1.3c)
  // migrated ElectionSeatsTrend, Settings, IndiaMap and the Party-page
  // summary side onto view-models too; `fetchResultSummary` is now deleted.
  // PR-H (Phase 1.3d) closed Party.svelte off `fetchParties`. PR-I (Phase
  // 1.4) extends the view-model with `ac_winners[]` so the per-AC badges +
  // MarginHistogram both consume canonical data — the page no longer fetches
  // `results.sqlite` for its own winners chunk (StateAcMap + RacesBoard
  // still do, migrating in Phase 1.5). Phase-0 closeout T.0c-ii-B.2 ports
  // the district list off `fetchDistricts` (legacy JSON) onto
  // `loadDistricts` (taxonomy.entities via DuckDB-WASM); the JSONs under
  // `datasets/reference/in/states/<S>/districts.json` remain on disk as
  // hand-authored curator input feeding `entities.parquet`.
  import {
    loadStateOverview,
    type StateOverviewViewModel,
  } from "../lib/view-models/state-overview";
  import type { LoaderResult } from "../lib/loader-result";
  import {
    fetchTopicCatalogue,
    indicatorPathForArtifact,
    type TopicCatalogue,
  } from "../lib/catalogue";
  import PartyBar from "../lib/PartyBar.svelte";
  import PartyPill from "../lib/party-pill/PartyPill.svelte";
  import { partyRowForResolver } from "../lib/colors/party-row";
  import SeatDonut from "../lib/SeatDonut.svelte";
  // Phase 3.6 (c) - composition-bar A/B mount. Per plan resolution R-16
  // the new primitive ships behind a sticky-cookie A/B bucket; removal
  // is `git revert` of this PR (touches only this file). See
  // frontend/src/lib/charts/composition-bar/experiment-definition.json.
  //
  // F2a.5.2 (2026-06-05): the standalone `CompositionBar.svelte`
  // renderer was retired; the diverging composition body now lives
  // inside `CategoryBar.svelte` as `mode="diverging"`. The experiment
  // id, cookie mechanism, targeting list and removal contract are
  // unchanged - the citizen-visible DOM still carries
  // `data-segment-id` / `data-share-pct` / `caption_fptp` from the
  // shared `composition-bar/` adapter; only the wrapper element flips
  // from `data-component="composition-bar"` to
  // `data-component="category-bar" data-mode="diverging"`.
  import CategoryBar from "../lib/charts/CategoryBar.svelte";
  import {
    loadCompositionBarElectionSeats,
    type LoadedCompositionBar,
  } from "../lib/charts/composition-bar/adapter-elections-seats";
  import compositionBarExperiment from "../lib/charts/composition-bar/experiment-definition.json";
  import {
    buildCopyLinkActionSpec,
    buildViewDataActionSpec,
  } from "../lib/charts/chart-shell/action-builders";
  import type { ChartShellActionSpec } from "../lib/charts/chart-shell/types";
  import { parseElectionEventId } from "../lib/charts/stacked-trend/adapter-elections";
  import {
    bucketForWithOverride,
    ensureVisitorId,
    type ExperimentDefinition,
  } from "../lib/experiments/bucket";
  import MarginHistogram from "../lib/MarginHistogram.svelte";
  import RacesBoard from "../lib/RacesBoard.svelte";
  import { SourceList } from "../lib/sources";
  import StateAcMapD3 from "../lib/charts/StateAcMapD3.svelte";
  import IndicatorCard from "../lib/IndicatorCard.svelte";
  import ElectionSeatsTrend from "../lib/ElectionSeatsTrend.svelte";
  import TopicIcon from "../lib/TopicIcon.svelte";
  import IndicatorJump, { type JumpGroup } from "../lib/IndicatorJump.svelte";
  import { STATE_AC } from "../lib/boundaries/sources";
  import { states } from "../lib/states.svelte";
  import { getPartyColor } from "../lib/colors/resolver";
  import { link } from "../lib/links";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { route } from "../lib/router.svelte";
  import {
    fetchElectionEvents,
    defaultEventForState,
    listEventsForState,
    findEvent,
    daysSincePolled,
    type ElectionEventsCatalogue,
    type ElectionEventRow,
  } from "../lib/election-events";
  import {
    fetchGovernmentTimeline,
    currentTerm,
    type GovernmentTimeline,
    type GovernmentTerm,
  } from "../lib/governments";

  interface Props { params: { state: string } }
  let { params }: Props = $props();

  // Per-state event resolution (ADR-0023). The state-overview hub used to
  // hardcode `const event = "AcGenMay2026"`; that 404'd every state outside
  // the May-2026 cohort. The catalogue now drives per-state defaults, and
  // the election block degrades gracefully (showing the upstream-pending
  // copy or a "no election data ingested" notice) when no event row exists.
  let election_catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then(c => (election_catalogue = c))
    .catch(() => (election_catalogue = null));

  // params.state is a SLUG (or, for backwards compatibility, an ECI code).
  // Resolve via the reactive states store; null while loading or unknown.
  const state_code = $derived(states.codeFromSlug(params.state));

  // Per-state event picker. Citizen lands on the catalogue default (most
  // recent assembly election); switching the picker re-resolves every
  // election-scoped fetch (summary, winners, SQLite) without leaving the
  // hub. `selected_event_id` is reset whenever the state changes so a
  // selection in TN doesn't bleed into Kerala. The list is intentionally
  // hidden when there is only one event for this state.
  let selected_event_id = $state<string | null>(null);
  const all_events = $derived<ElectionEventRow[]>(
    listEventsForState(election_catalogue, state_code),
  );
  const default_event_row = $derived<ElectionEventRow | null>(
    defaultEventForState(election_catalogue, state_code),
  );
  const event_row = $derived<ElectionEventRow | null>(
    (selected_event_id
      ? findEvent(election_catalogue, state_code, selected_event_id)
      : null) ?? default_event_row,
  );
  const event = $derived(event_row?.event_id ?? null);
  const event_status = $derived(event_row?.data_status ?? null);

  // Reset the picker when the state changes so cross-state navigation
  // never carries a now-invalid event_id.
  $effect(() => {
    void state_code;
    selected_event_id = null;
  });
  const days_since_poll = $derived(event_row ? daysSincePolled(event_row) : null);
  const is_news_cycle = $derived(
    days_since_poll !== null && days_since_poll >= 0 && days_since_poll < 90,
  );

  // Government timeline (ADR-0023 §3) — primary citizen anchor for "who
  // governs this state right now". Loads in parallel with the catalogue;
  // null when the per-state file is not yet authored (graceful degradation).
  let government = $state<GovernmentTimeline | null>(null);
  $effect(() => {
    government = null;
    const sc = state_code;
    if (!sc) return;
    fetchGovernmentTimeline(sc)
      .then(t => { if (state_code === sc) government = t; })
      .catch(() => { /* non-fatal — card just hides */ });
  });
  const cur_term = $derived<GovernmentTerm | null>(currentTerm(government));

  // Four-arm LoaderResult from the canonical view-model loader. `summary` is
  // a thin $derived that exposes `.data` on the `ok` arm only, so the
  // downstream renderer (PartyBar, SeatDonut, KPI tiles, party directory)
  // continues to read the same shape it always did. partial/failed/loading
  // get their own render arms below.
  let summaryResult = $state<LoaderResult<StateOverviewViewModel>>({ status: "loading" });
  const summary = $derived(summaryResult.status === "ok" ? summaryResult.data : null);
  let acs = $state<ConstituencyEntry[] | null>(null);
  // Three-state discriminator for the constituency-reference load:
  //   "loading" → fetch in flight; show a spinner, NOT the bootstrap notice
  //   "failed"  → fetch threw (404, parse error); show the bootstrap notice
  //   "ready"   → constituencies populated; render the AC directory
  // Without this, `acs === null` covered BOTH "in flight" and "failed", and
  // because the summary loader (DuckDB-WASM) often resolves before the
  // JSON fetch, the page briefly flashed the "needs bootstrap" message even
  // when the reference file existed and was about to load — a citizen-
  // visible regression that read as if the state were broken.
  let acs_status = $state<"loading" | "ready" | "failed">("loading");
  let districts = $state<District[] | null>(null);
  let catalogue = $state<TopicCatalogue | null>(null);

  // Indicator sections on the state hub are now data-driven (P2.4 of the
  // IA reset, ADR-0022): each topic in the catalogue that ships at least
  // one `kind: "indicator"` artifact renders as a section in catalogue
  // order. The closed renderer set (IndicatorChoropleth/Ranked/SmallMultiples)
  // is reused unchanged — no per-topic bespoke chrome (per
  // docs/concepts/schema-is-the-design-system.md). Election artifacts in the
  // catalogue are intentionally skipped here; they're rendered by the
  // election-specific sections above (different renderer family).
  const indicator_topics = $derived(
    (catalogue?.topics ?? []).filter(t =>
      t.artifacts.some(a => a.kind === "indicator"),
    ),
  );

  // Jump-strip groups derived from the live indicator topic set (U5c
  // sub-plan; parent plan section 20.12 "Quick-jump"). One chip per
  // topic in catalogue order; the IndicatorJump component handles
  // scroll-spy via IntersectionObserver against the `data-jump-id`
  // marker each topic <section> ships below. `active_topic_id` is
  // bind-driven so the chip flips as the citizen scrolls; we never
  // mirror it to the URL (non-navigation in-memory state per parent
  // plan section 20.8).
  const jump_groups = $derived<JumpGroup[]>(
    indicator_topics.map(t => ({
      id: t.id,
      label: t.title,
      icon: t.icon ?? null,
    })),
  );
  let active_topic_id = $state<string | null>(null);

  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(() => (catalogue = null));

  // Per-AC winner & margin lookup. Comes from the view-model loader (PR-I,
  // Phase 1.4) — `summary.ac_winners` is assembled from `ac-winner-party-id`
  // + `ac-margin-pct` observations JOINed to dim_acs + dim_parties. The
  // Map<eci_no, AcWinner> shape is preserved so the constituency list
  // template (line ~770) can stay unchanged.
  interface AcWinner {
    party_id: string;
    party_eci_code: string | null;
    party_short: string;
    margin_pct: number;
    brand_colour_hex?: string | null;
    brand_colour_confidence?: "high" | "medium" | "low" | null;
  }

  $effect(() => {
    summaryResult = { status: "loading" };
    acs = null;
    acs_status = "loading";
    districts = null;
    const sc = state_code;
    const ev = event;
    if (!sc) return; // wait for slug → code resolution
    // Constituencies + districts are reference data and load even when the
    // state has no election data on disk yet (so the AC directory still
    // renders). The election summary is only fetched when we have an event.
    // Reference-data 404s are non-fatal: the AC directory simply won't render
    // for states whose reference files haven't been built yet (e.g. recently
    // ingested states). Government card + indicator sections still appear.
    if (ev && event_status !== "pending_upstream") {
      loadStateOverview(ev, sc).then(r => {
        if (state_code === sc && event === ev) summaryResult = r;
      });
    } else {
      // No election event for this state, or upstream is still pending.
      // Mark as partial/not_published so the renderer falls through to the
      // existing pending-upstream notice rather than spinning forever.
      summaryResult = {
        status: "partial",
        data: {
          election: ev ?? "",
          state: sc,
          total_seats: 0,
          totals: null,
          party_totals: [],
          ac_winners: [],
          sources: [],
          pills: [],
        },
        reason: "not_published",
      };
    }
    // Track acs success/failure explicitly via `acs_status`. Reference-data
    // 404s remain non-fatal (the rest of the page still renders), but we
    // distinguish "in flight" from "failed" so the bootstrap notice fires
    // only on real failure. The status flips synchronously with the
    // success/error handler so the late-arriving render is unambiguous.
    const acs_p = fetchConstituencies(sc).then(
      c => { if (state_code === sc) { acs = c.constituencies; acs_status = "ready"; } },
      () => { if (state_code === sc) { acs = null; acs_status = "failed"; } },
    );
    const districts_p = loadDistricts(sc).then(
      d => { if (state_code === sc) districts = d; },
      () => { if (state_code === sc) districts = null; },
    );
    // Awaited only to keep the existing fire-and-forget shape; per-promise
    // handlers above already mutated `acs`/`districts`/`acs_status`.
    void Promise.all([acs_p, districts_p]);
  });

  // Map<eci_no, AcWinner> derived from the view-model. Keeps the template
  // lookup `winners.get(ac.eci_no)` unchanged; empty for events with no
  // per-AC observations (older cohorts) or while the loader is in flight.
  const winners = $derived.by<Map<number, AcWinner>>(() => {
    const m = new Map<number, AcWinner>();
    if (!summary) return m;
    for (const w of summary.ac_winners) {
      m.set(w.ac_eci_no, {
        party_id: w.party_id,
        party_eci_code: w.party_eci_code,
        party_short: w.party_short,
        margin_pct: w.margin_pct,
        brand_colour_hex: w.brand_colour_hex,
        brand_colour_confidence: w.brand_colour_confidence,
      });
    }
    return m;
  });

  // KPI tile hero block (UX-only). `buildKpiTiles` is the <script module>
  // pure helper above; the $derived re-runs on any of (acs, districts,
  // summary.totals.electors). Empty array while acs is null (loading
  // state renders skeletons; failed state hides the whole section).
  const kpi_tiles = $derived(
    buildKpiTiles(acs, districts, summary?.totals?.electors ?? null),
  );

  // No-assembly UT detection: the citizen lands on /ladakh expecting an
  // Indian-polity-honest page; "Ladakh Assembly Map" is structurally
  // wrong because Ladakh has no Vidhan Sabha. Drives the hero copy + the
  // optional UT explainer below; the KPI section is independently hidden
  // by `acs_status !== "failed"` (which fires for these same 5 UTs as a
  // side effect of constituencies.json being absent).
  const current_slug = $derived(state_code ? states.slug(state_code) : null);
  const is_no_assembly_ut = $derived(
    current_slug !== null && NO_ASSEMBLY_UT_SLUGS.has(current_slug),
  );

  // Retry callable for the failed arm (PR-E pattern). Captures current
  // event + state_code at click-time; re-invokes the loader and re-routes
  // the result back into summaryResult.
  function retryStateLoad(): void {
    const sc = state_code;
    const ev = event;
    if (!sc || !ev) return;
    summaryResult = { status: "loading" };
    loadStateOverview(ev, sc).then(r => {
      if (state_code === sc && event === ev) summaryResult = r;
    });
  }

  // Show every party from the actuals — no threshold. Earlier the bar
  // dropped parties with no seats AND <1% vote share, which silently
  // erased fringe-but-noisy parties (e.g. TVK in TN). The deselect
  // mechanism (Phase 2) lets users mute parties they don't care about.
  const ranked_parties = $derived(
    summary
      ? [...summary.party_totals].sort(
          (a, b) =>
            b.seats_won - a.seats_won ||
            b.vote_share_pct - a.vote_share_pct ||
            a.party_short.localeCompare(b.party_short),
        )
      : []
  );

  // Seats-by-party defaults to "winners only". A typical state has 7-10
  // seat-winning parties and 20+ that contested without winning anything;
  // showing all 30 floods the chart with zero-length bars and pushes the
  // signal off the screen. Zero-seat parties remain reachable via the
  // dedicated "All parties" directory below, and via this toggle.
  let show_zero_seat = $state(false);
  const winners_count = $derived(
    ranked_parties.filter(p => p.seats_won > 0).length,
  );
  const zero_seat_count = $derived(ranked_parties.length - winners_count);
  const visible_parties = $derived(
    show_zero_seat ? ranked_parties : ranked_parties.filter(p => p.seats_won > 0),
  );

  // ----- Phase 3.6 (c) composition-bar A/B mount -----
  //
  // Sticky-cookie bucket on `visitor_id`; targeting list restricted to
  // single-party-dominant states per plan resolution R-02 (TN is
  // explicitly excluded - alliance-led verdict misframes party-only
  // composition). When the visitor is in the treatment bucket AND the
  // state is in the rollout list, we render the diverging composition
  // bar (post-F2a.5.2: `<CategoryBar mode="diverging" />`; pre-F2a.5.2:
  // the retired `<CompositionBar />` standalone renderer) adjacent to
  // `<SeatDonut />` in the house-composition card; control bucket
  // renders SeatDonut only (current production behaviour).
  //
  // Removal contract: this entire block + the markup mount below + the
  // imports above is the whole footprint. `git revert` of this commit
  // restores the pre-experiment behaviour with zero side effects.
  const composition_bar_experiment = $derived(
    compositionBarExperiment as unknown as ExperimentDefinition,
  );
  const composition_bar_variant = $derived.by<string | null>(() => {
    if (!state_code) return null;
    const visitor_id = ensureVisitorId();
    return bucketForWithOverride(
      composition_bar_experiment,
      { state_code },
      visitor_id,
    );
  });
  const composition_bar_in_treatment = $derived(
    composition_bar_variant === "treatment",
  );
  let composition_bar_result =
    $state<LoaderResult<LoadedCompositionBar> | null>(null);
  $effect(() => {
    composition_bar_result = null;
    const sc = state_code;
    const ev = event;
    const row = event_row;
    if (!sc || !ev || !row) return;
    if (!composition_bar_in_treatment) return;
    if (event_status === "pending_upstream") return;
    const parsed = parseElectionEventId(row.event_id);
    loadCompositionBarElectionSeats(sc, row.event_id, {
      state_label: states.name(sc),
      event_label: parsed.period_label,
    }).then(r => {
      if (state_code === sc && event === ev) composition_bar_result = r;
    });
  });
  const composition_bar_loaded = $derived(
    composition_bar_result?.status === "ok" ? composition_bar_result.data : null,
  );

  // Phase 1.4 task 4 - footer action slots wired on the diverging
  // composition mount (post-F2a.5.2: CategoryBar; pre-F2a.5.2: the
  // retired CompositionBar standalone renderer). Built lazily as a
  // `$derived` so the spec captures the
  // current `composition_bar_loaded.model.segments` at click time (not
  // at mount time). View-model gates are the same as the mount itself:
  // both actions are only attached when we have a loaded model.
  //
  //   - `copy_link`  — copies the visitor's current URL (sticky-cookie
  //                    bucket + URL `?yg_variant=` override mean two
  //                    visitors hitting the same shared link see the
  //                    same chart). No telemetry — R-24.
  //
  //   - `view_data`  — downloads the **currently visible window** as
  //                    a CSV (plan rule line ~1080: "show the
  //                    currently visible chart/window first, not the
  //                    whole indicator corpus"). Filename baked from
  //                    the dimension + state slug + event_id so a
  //                    curator can diff two downloads cleanly.
  const composition_bar_actions = $derived.by<readonly ChartShellActionSpec[]>(
    () => {
      const loaded = composition_bar_loaded;
      const sc = state_code;
      const row = event_row;
      if (!loaded || !sc || !row) return [];
      const slug = states.slug(sc);
      const filename = `composition-bar_${loaded.model.dimension}_${slug}_${row.event_id}.csv`;
      return [
        buildCopyLinkActionSpec(),
        buildViewDataActionSpec({
          filename,
          resolve_rows: () => ({
            header: [
              "rank",
              "id",
              "label",
              "value",
              "unit",
              "is_tail",
              "swatch_role",
            ],
            rows: loaded.model.segments.map((s, i) => [
              i + 1,
              s.id,
              s.label,
              s.value,
              loaded.model.total_unit,
              s.is_tail,
              s.swatch_role,
            ]),
          }),
        }),
      ];
    },
  );

  // ----- Phase 2: search + deselect -----
  //
  // `hidden_parties` keys are `party_eci_code ?? party_short` — same
  // convention used by PartyBar / SeatDonut / ParliamentArc props. Hiding
  // is purely visual; per spec we DON'T recompute seats or vote share.
  let hidden_parties = $state<Set<string>>(new Set());

  function toggleHidden(key: string): void {
    const next = new Set(hidden_parties);
    if (next.has(key)) next.delete(key); else next.add(key);
    hidden_parties = next;
  }

  // Reset the mute set whenever the loaded state changes — otherwise muting
  // "TVK" in TN would still mute "TVK" after navigating to Kerala (where
  // the party may not even be on the ballot).
  $effect(() => {
    void state_code;
    hidden_parties = new Set();
  });

  let party_query = $state("");
  // Mirror seats-by-party: hide zero-seat parties by default. The directory
  // is the canonical place to see *all* parties that contested, but in
  // practice 60-70% of them won zero seats and never even appeared on a
  // chart, so the default view is winners-only with an explicit toggle.
  let show_zero_seat_directory = $state(false);
  let ac_query = $state("");

  const filtered_parties = $derived.by(() => {
    const q = party_query.trim().toLowerCase();
    if (!summary) return [];
    const base = show_zero_seat_directory
      ? summary.party_totals
      : summary.party_totals.filter(p => p.seats_won > 0);
    if (!q) return base;
    return base.filter(p =>
      p.party_short.toLowerCase().includes(q) ||
      (p.party_full ?? "").toLowerCase().includes(q) ||
      (p.party_eci_code ?? "").toLowerCase().includes(q),
    );
  });
  const directory_zero_seat_count = $derived(
    summary ? summary.party_totals.filter(p => p.seats_won === 0).length : 0,
  );

  // Group ACs by district_id, then sort districts by AC count (descending).
  // ACs without a district_id fall under a synthetic '—' bucket so the count
  // surface is honest rather than silently dropping rows. When `ac_query`
  // is set, ACs are filtered by case-insensitive match on name OR by exact
  // eci_no string match; districts with zero matches are dropped from the
  // listing entirely.
  const by_district = $derived.by(() => {
    if (!acs) return [];
    const q = ac_query.trim().toLowerCase();
    const filter = q
      ? (ac: ConstituencyEntry) =>
          ac.name.toLowerCase().includes(q) || String(ac.eci_no) === q
      : () => true;
    const name_by_id = new Map((districts ?? []).map(d => [d.id, d.name]));
    const groups = new Map<string, ConstituencyEntry[]>();
    for (const ac of acs) {
      if (!filter(ac)) continue;
      const k = ac.district_id ?? "";
      const arr = groups.get(k) ?? [];
      arr.push(ac);
      groups.set(k, arr);
    }
    const out: { id: string; name: string; acs: ConstituencyEntry[] }[] = [];
    for (const [id, group] of groups) {
      out.push({
        id,
        name: id ? (name_by_id.get(id) ?? id) : "(unmapped)",
        acs: group.sort((a, b) => a.eci_no - b.eci_no),
      });
    }
    out.sort((a, b) => b.acs.length - a.acs.length || a.name.localeCompare(b.name));
    return out;
  });

  const total_filtered_acs = $derived(
    by_district.reduce((s, g) => s + g.acs.length, 0),
  );

  // Grammar A `/:state` is a 1-segment catch-all that matches any path
  // not consumed by a chrome literal or multi-segment route. When the
  // states registry has loaded AND the slug doesn't resolve to a known
  // ECI code, render the 404 surface instead of the half-rendered state
  // hub. Per ADR-0037 / TODO/20260609-url-prefix-drop-phase0-plan.md
  // PR-P2: this is the gate that keeps the catch-all from poaching
  // unknown URLs.
  const is_unknown_state = $derived(states.isLoaded && state_code === null);

  // PR-W1d: per-route crumb chain. Reactive on route navigation AND
  // on async catalogue load (the builder reads states.svelte inside).
  const crumbs = $derived(route.crumbs ? route.crumbs(route.params) : []);
</script>

<Breadcrumb {crumbs} />

{#if is_unknown_state}
  <!--
    404 surface for unknown 1-segment paths (e.g. `/no-such-route-here`).
    Mirrors the copy + recovery links from routes/NotFound.svelte; we
    inline it here so the existing extended-routes Playwright contract
    keeps asserting `<h1>404` + "This page has moved" + Home / Browse
    topics links from a single locator scope.
  -->
  <main class="max-w-md mx-auto p-12 text-center space-y-4">
    <h1 class="text-3xl font-bold">404</h1>
    <p class="text-slate-600">
      This page has moved. We recently reorganised yen-gov's URL structure.
    </p>
    <p class="text-slate-500 text-sm">
      No route matches <code class="font-mono">/{params.state}</code>.
    </p>
    <nav class="flex justify-center gap-4 pt-2">
      <a class="text-blue-600 hover:underline" href={link.home()}>← Home</a>
      <a class="text-blue-600 hover:underline" href={link.topics()}>Browse topics</a>
    </nav>
  </main>
{:else}
<PageContainer width="wide">
  <header class="space-y-1">
    <div class="border-l-4 border-red-500 pl-3 py-0.5">
      {#if is_no_assembly_ut}
        <h1 class="text-2xl font-bold leading-tight text-slate-900">
          {states.name(state_code)}
        </h1>
        <p class="text-sm text-slate-500">
          Union Territory administered by the Centre. No state legislature.
        </p>
      {:else}
        <h1 class="text-2xl font-bold leading-tight text-slate-900">
          {states.name(state_code)} Assembly Map
        </h1>
        <p class="text-sm text-slate-500">
          {#if acs && acs.length > 0}
            Interactive map showing all {acs.length} assembly constituencies
          {:else}
            Interactive map of assembly constituencies
          {/if}
        </p>
      {/if}
    </div>
    <p class="text-sm text-slate-600">
      {#if event_row}
        {selected_event_id ? "Election" : "Most recent assembly election"}: {event_row.display}.
      {:else if state_code}
        No assembly election data ingested yet for this state.
      {/if}
      <span class="text-slate-400 ml-1">
        State <code class="font-mono">{state_code ?? "…"}</code>
        {#if event}· event <code class="font-mono">{event}</code>{/if}
      </span>
      {#if state_code}
        · <a class="text-blue-600 hover:underline" href={link.explore(state_code)}>Data explorer →</a>
        {#if event}
          · <a class="text-blue-600 hover:underline" href={link.lab(state_code, event)}>Psephlab →</a>
        {/if}
      {/if}
    </p>
    {#if all_events.length > 1}
      <p class="text-xs text-slate-600 flex items-center gap-2 pt-1">
        <label for="event-picker" class="font-medium text-slate-700">Election:</label>
        <select
          id="event-picker"
          data-testid="event-picker"
          class="border border-slate-300 rounded px-2 py-0.5 text-xs bg-white"
          value={event ?? ""}
          onchange={(e) => {
            const value = (e.currentTarget as HTMLSelectElement).value;
            selected_event_id = value || null;
          }}
        >
          {#each all_events as row (row.event_id)}
            <option value={row.event_id}>
              {row.display}{row === default_event_row ? " (latest)" : ""}
            </option>
          {/each}
        </select>
        <span class="text-slate-400">{all_events.length} elections on record</span>
      </p>
    {/if}
  </header>

  {#if !state_code}
    <div class="text-slate-500">Resolving state …</div>
  {:else}
    <!-- State Overview KPI tile hero block (UX-only; spec from Jony
         2026-06-13). Reference-data tiles (assemblies / districts /
         reserved / general) render as long as the constituencies-ref
         fetch is not in the `failed` arm; the optional total-voters
         tile lights up only when summary.totals.electors > 0. Skeleton
         while acs is mid-flight; hidden entirely on failed (the
         existing election-section copy below carries the citizen
         signal - no need for a second "data unavailable" surface). -->
    {#if acs_status !== "failed"}
      <section data-testid="state-overview-kpi" class="space-y-3">
        <div class="border-l-4 border-red-500 pl-3 py-0.5">
          <h2 class="text-lg font-bold text-slate-900">State Overview</h2>
        </div>
        {#if acs_status === "loading"}
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" aria-hidden="true">
            {#each [0, 1, 2, 3] as i (i)}
              <div class="animate-pulse bg-slate-100 rounded-xl h-24 ring-1 ring-slate-200/70"></div>
            {/each}
          </div>
        {:else}
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 {kpi_tiles.length >= 5 ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}">
            {#each kpi_tiles as t (t.key)}
              <div
                data-testid="kpi-tile"
                data-kpi-key={t.key}
                class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/70 p-4"
              >
                <div class="flex items-center gap-3">
                  <div class="rounded-md p-2 shrink-0 {t.chip_bg} {t.chip_fg}">
                    <TopicIcon name={t.icon_name} cls="w-5 h-5" />
                  </div>
                  <div class="text-[10px] uppercase tracking-[0.12em] text-slate-500 font-semibold">
                    {t.label}
                  </div>
                </div>
                <div class="text-3xl font-bold tabular-nums text-slate-800 mt-2">
                  {t.value}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    <!-- Recency banner (ADR-0023 §3 recency rule). When polling closed
         within the last 90 days, the citizen wants to know about the
         election first; otherwise the government card leads. -->
    {#if is_news_cycle && event_row}
      <section class="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-900">
        <strong class="font-semibold">Latest:</strong>
        {event_row.display} — polled {days_since_poll} day{days_since_poll === 1 ? "" : "s"} ago.
      </section>
    {/if}

    <!-- "Your government" card (ADR-0023 §3). Anchors the page on the
         continuing condition (who governs right now) rather than the
         discrete event that produced it. Degrades to a one-line caption
         when no CM holdings for this state exist in
         datasets/taxonomy/office_holdings.json (G.1.c 2026-05-22). -->
    {#if cur_term}
      <section class="bg-white rounded-lg shadow-sm ring-1 ring-slate-200/70 p-4 space-y-2">
        <h2 class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Your government</h2>
        {#if cur_term.regime === "elected"}
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span class="text-lg font-semibold text-slate-800">{cur_term.cm_name ?? "—"}</span>
            <span class="text-sm text-slate-600">Chief Minister</span>
            {#if cur_term.alliance}
              <span class="text-sm text-slate-500">· {cur_term.alliance}</span>
            {/if}
          </div>
          <p class="text-xs text-slate-500">
            In office since {cur_term.start}. Government is an elected ministry.
          </p>
        {:else if cur_term.regime === "presidents_rule"}
          <div class="text-base font-semibold text-amber-800">President's Rule</div>
          <p class="text-xs text-slate-600">
            In effect since {cur_term.start}. The state is administered by the
            Governor under Article 356; the Legislative Assembly is dissolved
            or suspended. {cur_term.notes ?? ""}
          </p>
        {:else if cur_term.regime === "governors_rule"}
          <div class="text-base font-semibold text-amber-800">Governor's Rule</div>
          <p class="text-xs text-slate-600">
            In effect since {cur_term.start}. {cur_term.notes ?? ""}
          </p>
        {:else}
          <div class="text-base font-semibold text-slate-700">Caretaker / interim government</div>
          <p class="text-xs text-slate-600">
            In effect since {cur_term.start}. {cur_term.notes ?? ""}
          </p>
        {/if}
      </section>
    {:else if government === null && state_code}
      <!-- Timeline file not yet authored for this state. Honest one-liner
           rather than silently omitting the card. The government schema is
           v1.0 and the file path is documented in
           docs/concepts/government-vs-election.md so a contributor can fill
           it in without reverse-engineering anything. -->
      <section class="text-xs text-slate-400 italic">
        Government timeline coming soon for {states.name(state_code)}.
      </section>
    {/if}
    <!-- Indicator sections — catalogue-driven, lead the page (P2 commit B
         of IA reset, ADR-0022 §Doctrine). Welfare topics (fiscal first,
         then energy) come BEFORE the election bundle because elections
         are one indicator family among many, not the spine.

         Step #1 of TODO/20260515-state-page-ia-rework-plan.md (the IA
         rework): the per-artifact India choropleth + ranked table +
         small-multiples trio has been replaced with one IndicatorCard
         per artifact. A citizen on /s/<state> is asking "how is MY
         state doing?", not "where does it rank on a map of India?" —
         the card answers that directly (big number + sparkline +
         one-line rank + "See all states →" link to /t/<topic>). The
         triple-render components remain in use on /t/<topic> and
         /compare where the cross-state question IS the right one.
         PeerSetFilter is dropped from this surface because there is no
         visible India view to constrain on /s/<state>; the picker is
         meaningful on /t/<topic>, one click away.

         Election artifacts in the catalogue are intentionally skipped
         here — the existing election-only renderer family below handles
         them. A future refactor (P3+) can collapse the election block
         into a single catalogue dispatch slot of its own; until then
         this single move is what the doctrine actually requires:
         welfare visible first.

         U5c (parent plan section 20.12): a sticky theme-chip jump
         strip sits ABOVE the indicator-list block. One chip per topic
         (icon + title), scroll-spy via IntersectionObserver on each
         section's `data-jump-id` marker, type-to-filter input above
         the chips. Mobile-first; never hardcoded - the chip set is
         derived from `indicator_topics`. -->
    {#if jump_groups.length > 1}
      <IndicatorJump groups={jump_groups} bind:current={active_topic_id} />
    {/if}
    {#each indicator_topics as topic (topic.id)}
      <section class="space-y-3" data-jump-id={topic.id}>
        <h2 class="text-sm font-semibold uppercase text-slate-500 flex items-center gap-2">
          <TopicIcon name={topic.icon} cls="w-4 h-4 text-slate-500 shrink-0" />
          <span>{topic.title}</span>
        </h2>
        <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {#each topic.artifacts.filter(a => a.kind === "indicator") as artifact (artifact.id)}
            {@const path = indicatorPathForArtifact(artifact)}
            {#if path}
              <IndicatorCard
                {topic}
                {artifact}
                indicator_path={path}
                home_state={state_code}
              />
            {/if}
          {/each}
        </div>
      </section>
    {/each}

    <!-- Election sections — preserved unchanged in capability and layout,
         but no longer the page's lead. Per ADR-0023 these are gated on
         the per-state event row: states with `data_status: pending_upstream`
         get an honest "not yet ingested" notice (the upstream flag is
         set whether ECI hasn't published yet OR yen-gov hasn't loaded
         the published file — the citizen-visible outcome is the same:
         the canonical store doesn't carry this cohort); states with no
         row at all (no election data ingested) skip the block entirely. -->
    {#if event_status === "pending_upstream"}
      <section class="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 text-sm text-slate-700">
        <strong class="font-semibold">Not yet ingested.</strong>
        {#if event_row}
          {event_row.display} — polled {event_row.polled_on}.
        {/if}
      </section>
    {:else if event_row && summaryResult.status === "failed"}
      <!-- PR-F: failed arm — DuckDB-WASM / fetch / SQL error reading the
           canonical store. describeFailure() already mapped the raw error
           to citizen-readable copy; retry re-invokes loadStateOverview. -->
      <section class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900 text-sm space-y-2">
        <p>{summaryResult.reason}</p>
        <button
          class="text-xs underline hover:no-underline"
          onclick={retryStateLoad}
        >Retry</button>
      </section>
    {:else if event_row && summaryResult.status === "partial"}
      <!-- PR-F: partial arm — the cohort is not yet ingested into the
           canonical store. Honest "no data" notice; reference-data sections
           (indicator cards, government card, AC directory) above and below
           still render. -->
      <section class="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 text-sm text-slate-700">
        <strong class="font-semibold">Not yet ingested.</strong>
        {#if event_row}
          {event_row.display} — polled {event_row.polled_on}.
        {/if}
      </section>
    {:else if event_row && summaryResult.status === "loading"}
      <div class="text-slate-500">Loading election data…</div>
    {:else if event_row && summary && acs_status === "loading"}
      <!-- Election summary has resolved (DuckDB-WASM JOIN is fast) but the
           per-state constituencies.json fetch is still in flight. Without
           this branch the page falls into the `acs_status === "failed"`
           arm below and flashes the "needs bootstrap" notice for a few
           hundred ms before the JSON arrives — looks identical to a real
           failure to the citizen. Render a neutral loading line instead. -->
      <div class="text-slate-500">Loading constituency directory…</div>
    {:else if event_row && summary && acs_status === "failed"}
      <section class="bg-white rounded-lg shadow-sm p-6 text-sm text-slate-600">
        <p class="font-medium text-slate-700 mb-1">Election results loaded.</p>
        <p>Constituency directory unavailable.</p>
      </section>
    {:else if event_row && summary && acs}

    <!-- G13 (EL5): RacesBoard lifted to be the FIRST election section.
         The map below is demoted to a companion (right column, 2fr); the
         donut + KPI block becomes the dominant left column (3fr). The
         relative column heights of the races board are themselves the
         headline, so it leads the election cluster. -->
    {#if event}
      <section class="bg-white rounded-lg shadow-sm p-5" data-testid="races-board">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Races by competitiveness</h2>
        <RacesBoard state={state_code} rows={summary?.ac_winners ?? null} {event} />
      </section>
    {/if}

    <!-- Top row: donut + key totals (3fr LEFT) + map (2fr RIGHT).
         At <lg the map wraps below the donut (single column). G13 (EL5)
         demoted the map from hero (was 3fr LEFT) to companion (2fr
         RIGHT). -->
    <section class="grid lg:grid-cols-[3fr_2fr] gap-6 items-start">
      <div class="space-y-4 min-w-0">
        <!-- Donut card: subtle radial-tinted background so the chart has
             "presence" against the surrounding white cards instead of
             floating in a flat panel. -->
        <div class="rounded-xl shadow-sm p-5 ring-1 ring-slate-200/70 bg-[radial-gradient(ellipse_at_top,_rgba(248,250,252,1)_0%,_rgba(255,255,255,1)_60%)]">
          <h2 class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 mb-3 text-center">House composition</h2>
          <SeatDonut
            parties={summary.party_totals}
            total_seats={summary.total_seats}
            {hidden_parties}
            onToggleHidden={toggleHidden}
          />
          {#if composition_bar_in_treatment && composition_bar_loaded}
            <!-- Phase 3.6 (c) composition-bar A/B mount - sticky-cookie
                 bucket, removal contract = revert this PR; touches only
                 StateOverview.svelte. Phase 1.4 task 4 footer actions
                 (`copy_link`, `view_data`) are attached when loaded.
                 F2a.5.2: renderer flipped from CompositionBar.svelte to
                 CategoryBar mode="diverging"; view-model + pills +
                 actions wiring is unchanged. -->
            <div class="mt-5 pt-5 border-t border-slate-200/60">
              <CategoryBar
                mode="diverging"
                view_model={composition_bar_loaded.model}
                pills={composition_bar_loaded.pills}
                actions={composition_bar_actions}
              />
            </div>
          {/if}
        </div>
        <!-- KPI strip: three tiles. Numbers centered, single thin bottom
             border in slate. The previous coloured top accents (emerald /
             sky) added visual cost without conveying meaning — the values
             are doing the talking now. -->
        <div class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/70 p-4 space-y-3">
          <div class="grid grid-cols-3 gap-3">
            <div class="text-center px-3 py-2 border-b border-slate-200">
              <div class="text-[10px] uppercase tracking-[0.12em] text-slate-500">Total seats</div>
              <div class="text-2xl font-bold tabular-nums text-slate-800 mt-0.5">{summary.total_seats}</div>
            </div>
            <div class="text-center px-3 py-2 border-b border-slate-200">
              <div class="text-[10px] uppercase tracking-[0.12em] text-slate-500">Votes polled</div>
              <div class="text-2xl font-bold tabular-nums text-slate-800 mt-0.5">{summary.totals?.votes_polled?.toLocaleString() ?? "—"}</div>
            </div>
            <div class="text-center px-3 py-2 border-b border-slate-200">
              <div class="text-[10px] uppercase tracking-[0.12em] text-slate-500">Turnout</div>
              <div class="text-2xl font-bold tabular-nums text-slate-800 mt-0.5">
                {summary.totals?.turnout_pct != null
                  ? `${summary.totals.turnout_pct.toFixed(1)}%`
                  : "—"}
              </div>
            </div>
          </div>
          <div data-testid="state-summary-sources">
            <SourceList pills={summary.pills} />
          </div>
        </div>
      </div>

      {#if event && STATE_AC[state_code]}
        <section class="bg-white rounded-lg shadow-sm p-4 min-w-0" data-testid="state-ac-map">
          <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Constituency map</h2>
          <StateAcMapD3 state={state_code} rows={summary?.ac_winners ?? null} {event} />
          <p class="text-xs text-slate-400 mt-2">
            Hover for winner & margin · click an AC to drill in. Darker fill = larger winning margin.
          </p>
        </section>
      {:else}
        <div></div>
      {/if}
    </section>

    <!-- Full-width seats-by-party bar (below the map row so wide bars
         have room to breathe and 0-seat parties remain readable). -->
    <section class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/70 p-5">
      <div class="flex items-baseline justify-between mb-1 gap-2 flex-wrap">
        <h2 class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Seats by party</h2>
        <div class="flex items-center gap-3 flex-wrap">
          {#if zero_seat_count > 0}
            <button
              class="text-xs text-blue-600 hover:underline"
              onclick={() => (show_zero_seat = !show_zero_seat)}
            >{show_zero_seat
                ? `Hide ${zero_seat_count} zero-seat parties`
                : `Show ${zero_seat_count} parties with no seats`}</button>
          {/if}
          {#if hidden_parties.size > 0}
            <button
              class="text-xs text-blue-600 hover:underline"
              onclick={() => (hidden_parties = new Set())}
            >Show all ({hidden_parties.size} muted)</button>
          {/if}
        </div>
      </div>
      <p class="text-xs text-slate-500 mb-3">
        Bar length = seats won. Number in parentheses = vote share. Sorted by seats.
      </p>
      <PartyBar
        parties={visible_parties}
        total_seats={summary.total_seats}
        {hidden_parties}
        onToggleHidden={toggleHidden}
      />
    </section>

    {#if all_events.length > 0}
      <section class="bg-white rounded-lg shadow-sm p-5">
        <div class="flex items-baseline justify-between mb-1 gap-2 flex-wrap">
          <h2 class="text-sm font-semibold uppercase text-slate-500">Seat composition over time</h2>
          <span class="text-xs text-slate-400">{all_events.length} {all_events.length === 1 ? "election" : "elections"} on record</span>
        </div>
        <p class="text-xs text-slate-500 mb-3">
          Each bar = one assembly election. Segment height = seats won by that party.
          {#if all_events.length === 1}
            Only one election is published for this state so far; future elections will extend the series.
          {/if}
        </p>
        <ElectionSeatsTrend state_code={state_code} value="seats_won" />
      </section>
    {/if}

    {#if event}
      <section class="bg-white rounded-lg shadow-sm p-5">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Margin of victory</h2>
        <MarginHistogram rows={summary?.ac_winners ?? null} />
      </section>
    {/if}

    <section class="bg-white rounded-lg shadow-sm p-5">
      <div class="flex justify-between items-baseline mb-1 gap-3 flex-wrap">
        <h2 class="text-sm font-semibold uppercase text-slate-500">All parties · directory</h2>
        <div class="flex items-center gap-3">
          <input
            type="search"
            placeholder="Search parties…"
            bind:value={party_query}
            class="text-xs rounded border-slate-300 py-1 px-2 w-48"
            aria-label="Search parties by name or ECI code"
          />
          <span class="text-xs text-slate-400">
            {filtered_parties.length} / {summary.party_totals.length}
          </span>
        </div>
      </div>
      <p class="text-xs text-slate-500 mb-3">
        Every party that contested. Click a name to open its party page.
      </p>
      {#if filtered_parties.length === 0}
        <p class="text-sm text-slate-500 italic">No parties match <code>{party_query}</code>.</p>
      {:else}
        <ul class="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm">
          {#each filtered_parties as p}
            {@const party_href = link.party(p.party_id)}
            {@const pill_row = partyRowForResolver(p)}
            {#if party_href}
              <li>
                <a class="hover:underline inline-flex items-center gap-1.5" href={party_href}>
                  <PartyPill size="sm" party_id={p.party_id} party_short={p.party_short} row={pill_row}/>
                  <span class="text-slate-400 text-xs">· {p.seats_won} seats · {p.vote_share_pct.toFixed(1)}%</span>
                </a>
              </li>
            {:else}
              <li class="inline-flex items-center gap-1.5">
                <PartyPill size="sm" party_id={p.party_id} party_short={p.party_short} row={pill_row}/>
                <span class="text-slate-400 text-xs">· {p.seats_won} seats · {p.vote_share_pct.toFixed(1)}%</span>
              </li>
            {/if}
          {/each}
        </ul>
      {/if}
      {#if directory_zero_seat_count > 0}
        <div class="pt-3">
          <button
            class="text-xs text-blue-600 hover:underline"
            onclick={() => (show_zero_seat_directory = !show_zero_seat_directory)}
          >{show_zero_seat_directory
              ? `Hide ${directory_zero_seat_count} zero-seat parties`
              : `Show ${directory_zero_seat_count} parties with no seats`}</button>
        </div>
      {/if}
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5">
      <div class="flex justify-between items-baseline mb-1 gap-3 flex-wrap">
        <h2 class="text-sm font-semibold uppercase text-slate-500">Constituencies by district</h2>
        <div class="flex items-center gap-3">
          <input
            type="search"
            placeholder="Search ACs (name or no.)…"
            bind:value={ac_query}
            class="text-xs rounded border-slate-300 py-1 px-2 w-56"
            aria-label="Search constituencies by name or AC number"
          />
          <span class="text-xs text-slate-400">
            {by_district.length} district{by_district.length === 1 ? "" : "s"} · {total_filtered_acs} / {acs.length} ACs
          </span>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 mb-3">
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-block w-2.5 h-2.5 rounded-sm bg-slate-400"></span>
          coloured square = winning party
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="font-mono tabular-nums">12.3</span>
          right number = winner's lead in percentage points
        </span>
        <!-- Margin-of-victory bands. Colors picked from ColorBrewer's
             RdYlBu sequential scheme (CB-safe across protanopia /
             deuteranopia / tritanopia). The previous rose/amber pair was
             too close in lightness for protanopic viewers. Larger 8-px
             swatches replace the tiny dots. -->
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-block w-2.5 h-2.5 rounded-sm" style:background-color="#d7191c"></span>nail-biter (&lt; 5)
          <span class="inline-block w-2.5 h-2.5 rounded-sm ml-2" style:background-color="#fdae61"></span>contestable (&lt; 10)
          <span class="inline-block w-2.5 h-2.5 rounded-sm ml-2" style:background-color="#2c7bb6"></span>comfortable (≥ 10)
        </span>
      </div>
      {#if by_district.length === 0}
        <p class="text-sm text-slate-500 italic">No constituencies match <code>{ac_query}</code>.</p>
      {:else}
        <div class="space-y-4">
          {#each by_district as g}
            <div>
              <div class="flex items-baseline justify-between border-b border-slate-200 pb-1 mb-2">
                <h3 class="text-sm font-semibold">{g.name}</h3>
                <span class="text-xs text-slate-400 font-mono">{g.id || "—"} · {g.acs.length}</span>
              </div>
              <ul class="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm font-mono">
                {#each g.acs as ac}
                  {@const w = winners.get(ac.eci_no)}
                  <li>
                    <a class="hover:underline flex items-center gap-1.5" href={link.ac(state_code, ac.name, event)}>
                      <span class="text-slate-400 inline-block w-8 text-right pr-1">{ac.eci_no}</span>
                      {#if w}
                        <span
                          class="inline-block w-2 h-2 rounded-sm flex-shrink-0"
                          style:background-color={getPartyColor(
                            w.party_id,
                            w.brand_colour_hex
                              ? {
                                  party_id: w.party_id,
                                  eci_code: w.party_eci_code,
                                  brand_colour: {
                                    hex: w.brand_colour_hex,
                                    confidence: w.brand_colour_confidence ?? "medium",
                                  },
                                }
                              : null,
                          ).hex}
                          title={`${w.party_short} · ${w.margin_pct.toFixed(1)} pt margin`}
                        ></span>
                      {:else}
                        <span class="inline-block w-2 h-2 flex-shrink-0"></span>
                      {/if}
                      <span class="truncate">{ac.name}</span>
                      {#if ac.reservation !== "GEN"}
                        <span class="text-xs text-rose-600">[{ac.reservation}]</span>
                      {/if}
                      {#if w}
                        <!-- Margin colour follows the same RdYlBu band as
                             the legend above (red < 5, orange < 10, blue
                             ≥ 10). Inline hex so the per-row swatch and
                             the legend chip can never drift apart. -->
                        {@const mc = w.margin_pct < 5 ? "#d7191c" : w.margin_pct < 10 ? "#fdae61" : "#2c7bb6"}
                        <span
                          class="ml-auto text-[10px] tabular-nums font-semibold"
                          style:color={mc}
                          title="Winner's margin (% of votes polled)"
                        >{w.margin_pct.toFixed(1)}</span>
                      {/if}
                    </a>
                  </li>
                {/each}
              </ul>
            </div>
          {/each}
        </div>
      {/if}
    </section>
    {/if}
  {/if}
</PageContainer>
{/if}
