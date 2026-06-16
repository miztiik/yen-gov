<script lang="ts">
  import {
    type CandidateBio,
    type ConstituencyResult,
  } from "../lib/data";
  import { loadConstituencyResult } from "../lib/view-models/legacy/constituency";
  import type { AcWinner } from "../lib/view-models/state-overview";
  import {
    bodyFromEvent,
    loadElectionResults,
    projectAsWinnersByEntity,
    type ElectionResultRow,
  } from "../lib/view-models/election-results";
  import type { LoaderResult } from "../lib/loader-result";
  import {
    fetchElectionEvents,
    defaultEventForState,
    findEvent,
    listEventsForState,
    type ElectionEventsCatalogue,
    type ElectionEventRow,
  } from "../lib/election-events";
  import AcStackedBar from "../lib/AcStackedBar.svelte";
  import StateAcMapD3 from "../lib/charts/StateAcMapD3.svelte";
  import WinnerBadge from "../lib/WinnerBadge.svelte";
  import { STATE_AC } from "../lib/boundaries/sources";
  import { states } from "../lib/states.svelte";
  import { navigate } from "../lib/url";
  import { link } from "../lib/links";
  import PartyPill from "../lib/party-pill/PartyPill.svelte";
  import { partyRowForResolver } from "../lib/colors/party-row";
  import TopicIcon from "../lib/TopicIcon.svelte";
  import PartySymbolGlyph from "../lib/PartySymbolGlyph.svelte";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { route } from "../lib/router.svelte";
  import { findConstituencyBySlug } from "../lib/elections/constituency-lookup";
  import YearPillStrip from "../lib/elections/YearPillStrip.svelte";
  import ConstituencyHistoryBar from "../lib/elections/ConstituencyHistoryBar.svelte";
  import {
    buildHistoryRows,
    type EventResultEntry,
    type HistoryRow,
  } from "../lib/elections/constituency-history-model";
  import EntityProfilePanel from "../lib/parties/EntityProfilePanel.svelte";
  import type { ProfileRow } from "../lib/parties/EntityProfilePanel.svelte";
  import { loadPcAffidavit2014 } from "../lib/elections/pc-affidavit-2014-loader";
  import { buildMpAffidavitRows } from "../lib/elections/mp-affidavit-model";

  // Events that have an affidavit-enriched candidacies.csv on disk.
  // Today only 2014 (Row B of TODO/20260614-three-ephemeral-ingests-
  // plan.md). When future LS events are enriched, add their event_id
  // here OR lift this guard to a manifest read once the count > 3.
  const EVENTS_WITH_AFFIDAVITS = new Set<string>(["general-2014"]);

  // Three valid props shapes:
  //
  //   1. Canonical nested AC (ADR-0052):
  //        /:state/elections/:event/ac/:ac
  //        params = { state, event, ac_slug, eci_no }
  //   2. Bare AC convenience (ADR-0052, redirects to #1):
  //        /:state/ac/:ac
  //        params = { state, ac_slug, eci_no }
  //   3. Bare 4-segment leaf (PR-W3b, election experience overhaul):
  //        /:state/elections/:event/:constituency
  //        params = { state, event, constituency_slug }
  //
  //   Shapes #1 + #2 are AC-only by route shape (slug carries the eci_no).
  //   Shape #3 dispatches AC vs PC from the event-slug body prefix
  //   (`general-` -> PC, `assembly-` -> AC); the eci_no is resolved by
  //   slug lookup against `datasets/data/entities/electoral.csv`.
  interface Props {
    params: {
      state: string;
      event?: string;
      ac_slug?: string;
      eci_no?: number;
      constituency_slug?: string;
    };
  }
  let { params }: Props = $props();

  // Per-state event resolution (ADR-0023): no global "current election".
  // The state's default event from datasets/taxonomy/election_events.json
  // names the artifact directory we read from.
  let election_catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then(c => (election_catalogue = c))
    .catch(() => (election_catalogue = null));

  const state_code = $derived(states.codeFromSlug(params.state));
  // ADR-0052: the event is identity and lives in the path (params.event).
  // A legacy `?event=` query is honoured for one release so pre-ADR-0052
  // bookmarks keep resolving; both fall back to the state default.
  const legacy_query_event = $derived(
    new URLSearchParams(location.search).get("event"),
  );
  const event_token = $derived(params.event ?? legacy_query_event);
  const event_row = $derived(
    (event_token ? findEvent(election_catalogue, state_code, event_token) : null)
      ?? defaultEventForState(election_catalogue, state_code),
  );
  const event = $derived(event_row?.event_id ?? null);

  // PR-W3b: body inference from event-slug prefix. Drives AC vs PC
  // dispatch on the bare 4-segment leaf route. Returns null on shape #1
  // / #2 (event-less or assembly-only AC routes default to AC).
  const constituency_kind = $derived.by<"ac" | "pc">(() => {
    const ev = event;
    if (!ev) return "ac";
    if (ev.startsWith("general") || ev.startsWith("Ls")) return "pc";
    return "ac";
  });

  // PR-W3b: bare-name-slug lookup. Populates `resolved_pc_entity` /
  // `resolved_ac_eci_no` once the canonical electoral.csv reaches the
  // browser. Skipped entirely on shapes #1 / #2 (eci_no already known).
  // PR-W4a (2026-06-10) additive: also surface `resolved_entity_id` so
  // the YearPillStrip + ConstituencyHistoryBar can JOIN per-event
  // loader rows on the canonical entity key.
  let resolved_eci_no = $state<number | null>(null);
  let resolved_entity_name = $state<string | null>(null);
  let resolved_entity_id = $state<string | null>(null);
  let resolved_pc_winner = $state<ElectionResultRow | null>(null);
  let resolved_lookup_pending = $state(false);

  $effect(() => {
    resolved_eci_no = null;
    resolved_entity_name = null;
    resolved_entity_id = null;
    resolved_pc_winner = null;
    resolved_lookup_pending = false;
    const slug = params.constituency_slug;
    const st_slug = params.state;
    const kind = constituency_kind;
    const ev = event;
    if (!slug || !st_slug || !ev) return;
    resolved_lookup_pending = true;
    findConstituencyBySlug(st_slug, kind, slug).then((hit) => {
      if (slug !== params.constituency_slug || ev !== event) return;
      resolved_lookup_pending = false;
      if (!hit) return;
      resolved_eci_no = hit.eci_no;
      resolved_entity_name = hit.name;
      resolved_entity_id = hit.entity_id;
      // For PC drill-down, also project the winner row from the
      // NATIONAL-PC W2b loader. The AC drill-down keeps using its
      // bespoke per-AC loader below.
      if (kind === "pc") {
        loadElectionResults({ event: ev }).then((r) => {
          if (r.status !== "ok" && r.status !== "partial") return;
          const match = r.data.find(
            (row) =>
              row.entity_kind === "pc" &&
              row.eci_no === hit.eci_no &&
              row.state_slug === st_slug,
          );
          if (slug === params.constituency_slug && ev === event) {
            resolved_pc_winner = match ?? null;
          }
        });
      }
    });
  });

  // Effective eci_no the AC view-model consumes. Shape #1 / #2 supply it
  // via the route parse; shape #3 fills it from the slug lookup once it
  // resolves.
  const effective_eci_no = $derived(
    typeof params.eci_no === "number" && params.eci_no > 0
      ? params.eci_no
      : (resolved_eci_no ?? -1),
  );

  // MP affidavit panel (Row D of TODO/20260614-three-ephemeral-ingests-
  // plan.md). Fetches the 2014 LS PC winner's Form-26 affidavit cols
  // when (event, kind, eci_no, state) are all known and the event is
  // affidavit-enriched. The loader returns null when no winner row
  // matches OR every affidavit field is blank, which suppresses the
  // panel (rows.length===0 inside EntityProfilePanel).
  let mp_affidavit_rows = $state<readonly ProfileRow[]>([]);

  $effect(() => {
    mp_affidavit_rows = [];
    const ev = event;
    const st_slug = params.state;
    const ec = effective_eci_no;
    const kind = constituency_kind;
    if (!ev || !st_slug || !ec || ec <= 0) return;
    if (kind !== "pc") return;
    if (!EVENTS_WITH_AFFIDAVITS.has(ev)) return;
    loadPcAffidavit2014(st_slug, ec).then((a) => {
      if (ev !== event || st_slug !== params.state || ec !== effective_eci_no) {
        return;
      }
      mp_affidavit_rows = a ? buildMpAffidavitRows(a) : [];
    });
  });

  // Bare-AC redirect (ADR-0052): when the path carries no event but we
  // have resolved one (default or legacy-query), replaceState to the
  // canonical nested URL so the address bar is always the
  // identity-complete form. Preserves the exact ac slug the visitor
  // arrived with. Only fires on the BARE-AC convenience shape (#2);
  // the new W3b bare-slug shape (#3) carries its own event already.
  $effect(() => {
    if (params.event) return; // already on the canonical nested route
    if (!params.ac_slug) return; // not the bare-AC shape
    const ev = event;
    if (!ev || effective_eci_no <= 0) return;
    navigate(
      `/${params.state}/elections/${encodeURIComponent(ev)}/ac/${params.ac_slug}`,
      { replace: true },
    );
  });

  // PR-E (Phase 1.3a): the canonical view-model loader fronts DuckDB-WASM.
  // The result is a discriminated union — render all four arms.
  // AC dispatch only; the PC arm short-circuits at render time below.
  let loaderResult = $state<LoaderResult<ConstituencyResult>>({ status: "loading" });
  const result = $derived(
    loaderResult.status === "ok" || loaderResult.status === "partial"
      ? loaderResult.data
      : null,
  );
  const not_published = $derived(
    loaderResult.status === "partial" && loaderResult.reason === "not_published",
  );

  // Biographic columns (sex/age/education/profession/constituency_type/
  // party_type) now ride on `result.candidates[i].bio` directly from
  // dim_persons + elections_candidacies (ADR-0035 S.1). No more
  // per-candidate JSON fan-out; one DuckDB query already projected them.

  // State-map context for the "Location in {state}" panel. Lean loader —
  // pulls only ac_winners[] (no party totals / state scope / sources), so
  // the constituency page doesn't pay for queries it never renders.
  // `null` = still loading; `[]` = loaded with no rows (not_published).
  let ac_winners = $state<AcWinner[] | null>(null);

  $effect(() => {
    if (constituency_kind === "pc") {
      // PC drill-down does not use the AC-only loaders.
      loaderResult = { status: "ok", data: null as unknown as ConstituencyResult };
      ac_winners = [];
      return;
    }
    loaderResult = { status: "loading" };
    ac_winners = null;
    const sc = state_code;
    const ev = event;
    const eci = effective_eci_no;
    if (!sc || !ev || eci <= 0) return;
    loadConstituencyResult(ev, sc, eci).then(r => (loaderResult = r));
    // PR-W5a (2026-06-10): flipped state-context AC-map loader from
    // bespoke `loadStateAcWinners` to the generic `loadElectionResults`
    // + `projectAsWinnersByEntity` projection. Output is the same
    // AcWinner[] the maplibre StateAcMap consumes; the bespoke loader
    // was retired in this PR.
    loadElectionResults({ event: ev, state: sc }).then(r => {
      if (r.status !== "ok" && r.status !== "partial") {
        ac_winners = [];
        return;
      }
      ac_winners = projectAsWinnersByEntity(r.data).map(toAcWinner);
    });
  });

  async function retryLoad() {
    const sc = state_code;
    const ev = event;
    const eci = effective_eci_no;
    if (!sc || !ev || eci <= 0) return;
    loaderResult = { status: "loading" };
    loaderResult = await loadConstituencyResult(ev, sc, eci);
  }

  /** Project one generic `ElectionResultRow` (STATE-AC scope, post
   *  `projectAsWinnersByEntity` filter) to the legacy `AcWinner` shape
   *  the maplibre StateAcMap + downstream consumers expect. Mirrors the
   *  field mapping the retired `loadStateAcWinners` bespoke loader used
   *  (default `party_id` -> `"parties.IN.UNK"`, `margin_pct` -> 0 on null). */
  function toAcWinner(r: ElectionResultRow): AcWinner {
    return {
      ac_eci_no: r.eci_no,
      ac_name: r.entity_name,
      party_id: r.party_id ?? "parties.IN.UNK",
      party_eci_code: r.party_eci_code,
      party_short: r.party_short ?? "",
      margin_pct: r.margin_pct ?? 0,
      turnout_pct: r.turnout_pct,
      winner_age: r.winner_age,
      winner_candidate_name: r.winner_candidate_name,
      symbol_asset_path: r.symbol_asset_path,
      brand_colour_hex: r.brand_colour_hex,
      brand_colour_confidence: r.brand_colour_confidence,
    };
  }

  function fmtBiographic(bio: CandidateBio | null | undefined): string {
    if (!bio) return "";
    const parts: string[] = [];
    if (bio.sex) parts.push(bio.sex);
    if (bio.age) parts.push(`age ${bio.age}`);
    if (bio.education) parts.push(bio.education);
    if (bio.profession) parts.push(bio.profession);
    return parts.join(" · ");
  }

  function pct(n: number): string { return n.toFixed(2) + "%"; }

  // PR-W1d: per-route crumb chain. Reactive on route navigation AND
  // on async catalogue load (the builder reads states.svelte inside).
  const crumbs = $derived(route.crumbs ? route.crumbs(route.params) : []);

  // PR-W4a (2026-06-10): YearPillStrip + ConstituencyHistoryBar mounts.
  // Only the bare-slug (W3b shape #3) route exposes both because that is
  // the only shape that resolves the canonical `entity_id` from a slug
  // lookup; the legacy AC eci_no shapes (#1 / #2) ship without the
  // history strip per the PR-W4a plan-doc scope ("mount on the
  // constituency drill page rebuilt by PR-W3b"). When the lookup misses
  // (resolved_entity_id stays null) the components do not render at all.
  const history_events = $derived.by<ElectionEventRow[]>(() => {
    if (!election_catalogue || !state_code || !resolved_entity_id) return [];
    const all = listEventsForState(election_catalogue, state_code);
    const body = constituency_kind;
    return all.filter((row) => {
      try {
        return bodyFromEvent(row.event_id) === body;
      } catch {
        // Catalogue rows with a non-standard prefix slip past bodyFromEvent;
        // drop them from the strip rather than throwing in render.
        return false;
      }
    });
  });

  let history_rows = $state<HistoryRow[]>([]);

  $effect(() => {
    const events = history_events;
    const entity_id = resolved_entity_id;
    const body = constituency_kind;
    const sc = state_code;
    history_rows = [];
    if (events.length === 0 || !entity_id) return;
    let cancelled = false;
    Promise.all(
      events.map(async (ev) => {
        try {
          const scope =
            body === "ac" && sc
              ? { event: ev.event_id, state: sc }
              : { event: ev.event_id };
          const r = await loadElectionResults(scope);
          const rows =
            r.status === "ok" || r.status === "partial" ? r.data : [];
          return { event: ev, rows } as EventResultEntry;
        } catch {
          return { event: ev, rows: [] } as EventResultEntry;
        }
      }),
    ).then((entries) => {
      if (cancelled) return;
      history_rows = buildHistoryRows(entries, entity_id);
    });
    return () => {
      cancelled = true;
    };
  });

  function onPillSelect(event_id: string): void {
    const st = params.state;
    const slug = params.constituency_slug;
    if (!st || !slug) return;
    navigate(`/${st}/elections/${encodeURIComponent(event_id)}/${slug}`);
  }
</script>

<Breadcrumb {crumbs} />

<PageContainer width="wide">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold flex items-center gap-2">
      <TopicIcon name="vote" cls="w-6 h-6 text-slate-500 shrink-0" />
      <span data-testid="constituency-header">
        {#if constituency_kind === "pc"}
          {resolved_entity_name ?? params.constituency_slug ?? "Parliamentary Constituency"}
        {:else if result}
          {result.constituency_name ?? `AC ${result.eci_no}`}
        {:else if resolved_entity_name}
          {resolved_entity_name}
        {:else if effective_eci_no > 0}
          AC {effective_eci_no}
        {:else}
          Constituency
        {/if}
      </span>
    </h1>
    <!-- G12 (EL4) in-page back-link. Duplicates the Breadcrumb crumb on
         purpose: the breadcrumb is chrome, this is contextual "I'm done with
         this AC, take me back to the state hub." -->
    {#if state_code}
      <p class="text-sm">
        <a
          href={link.state(state_code)}
          class="text-slate-500 hover:underline"
          data-testid="back-to-state"
        >← Back to {states.name(state_code)}</a>
      </p>
    {/if}
    <p class="text-sm text-slate-500">
      {states.name(state_code)} ·
      {#if constituency_kind === "pc"}
        Parliament constituency
      {:else if effective_eci_no > 0}
        constituency #{effective_eci_no}
      {/if}
    </p>
  </header>

  {#if constituency_kind === "pc"}
    <!-- PC drill-down (PR-W3b minimal arm).
         Full PC layout (candidates table + map locator + delim-history
         bar) is scope for a later PR; today the leaf renders the
         winner summary so a citizen reaching the URL sees the right
         seat name + which party + which margin. -->
    {#if resolved_lookup_pending}
      <div class="text-slate-500" data-testid="constituency-pc-loading">
        Looking up Parliament constituency…
      </div>
    {:else if !resolved_entity_name}
      <div
        class="p-5 bg-amber-50 border border-amber-200 rounded space-y-2"
        data-testid="constituency-pc-notfound"
      >
        <h2 class="text-sm font-semibold uppercase text-amber-900">
          Constituency not found
        </h2>
        <p class="text-sm text-amber-900">
          No Parliament constituency named
          <code class="rounded bg-amber-100 px-1">{params.constituency_slug}</code>
          in {states.name(state_code) || params.state}.
        </p>
      </div>
    {:else if resolved_pc_winner}
      <section
        class="bg-white rounded-lg shadow-sm p-5 space-y-3 text-sm"
        data-testid="constituency-pc-winner"
      >
        <div class="grid sm:grid-cols-3 gap-4">
          <div>
            <div class="text-xs uppercase text-slate-500">Winning party</div>
            <div class="font-semibold">
              <PartyPill
                size="sm"
                party_id={resolved_pc_winner.party_id}
                party_short={resolved_pc_winner.party_short ?? "\u2014"}
                row={partyRowForResolver(resolved_pc_winner)}
              />
            </div>
            <div class="text-slate-500">
              {resolved_pc_winner.winner_candidate_name ?? ""}
            </div>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500">Margin</div>
            <div class="font-semibold tabular-nums">
              {resolved_pc_winner.margin_pct != null
                ? `${resolved_pc_winner.margin_pct.toFixed(2)}%`
                : "—"}
            </div>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500">Turnout</div>
            <div class="font-semibold tabular-nums">
              {resolved_pc_winner.turnout_pct != null
                ? `${resolved_pc_winner.turnout_pct.toFixed(2)}%`
                : "—"}
            </div>
            {#if resolved_pc_winner.votes_polled != null}
              <div class="text-slate-500 tabular-nums">
                {resolved_pc_winner.votes_polled.toLocaleString()} polled
              </div>
            {/if}
          </div>
        </div>
        <p class="text-xs text-slate-500">
          Parliament constituency drill-down. For the per-state event
          view, see
          {#if event && state_code}
            <a
              class="text-sky-700 hover:underline"
              href={link.stateElection(state_code, event)}
              data-testid="constituency-pc-back-state-event"
            >state event view</a
            >.
          {/if}
        </p>
      </section>

      <!-- MP affidavit panel (Row D of TODO/20260614-three-ephemeral-
           ingests-plan.md). Only mounted when Form-26 affidavit data
           for this (state, eci_no, event) loaded successfully and is
           non-empty; otherwise EntityProfilePanel renders nothing. -->
      <EntityProfilePanel
        entity_kind="mp"
        title="About this MP (2014 declaration)"
        rows={mp_affidavit_rows}
        provenance="Self-declared in Form 26 affidavit at nomination, 2014. Source: ECI / MyNeta."
        amber_banner="Self-declared at nomination, not adjudicated. Read alongside other public records."
      />
    {:else}
      <div
        class="p-5 bg-slate-50 border border-slate-200 rounded space-y-2"
        data-testid="constituency-pc-stub"
      >
        <p class="text-sm text-slate-700">
          {resolved_entity_name} — Parliament constituency in
          {states.name(state_code) || params.state}.
        </p>
        <p class="text-xs text-slate-500">
          Detailed candidate table and history coming in a follow-up PR.
        </p>
      </div>
    {/if}
  {:else if loaderResult.status === "failed"}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900 space-y-2">
      <p>{loaderResult.reason}</p>
      {#if loaderResult.retry}
        <button
          type="button"
          class="text-sm font-semibold underline hover:no-underline"
          onclick={retryLoad}
        >Retry</button>
      {/if}
    </div>
  {:else if not_published}
    <div class="p-5 bg-amber-50 border border-amber-200 rounded space-y-2">
      <h2 class="text-sm font-semibold uppercase text-amber-900">No result published</h2>
      <p class="text-sm text-amber-900">
        The Election Commission has not published a result for AC #{effective_eci_no} in {states.name(state_code)}.
        This typically means the constituency was <strong>countermanded</strong> or <strong>postponed</strong>
        — for example, if a contesting candidate died before polling, or polling was deferred.
      </p>
      <p class="text-xs text-amber-800">
        The backend's Section 10 parser deliberately skips these stubs (see
        <code class="font-mono">docs/architecture/backend/sources-eci.md</code>) rather than emit a misleading
        zero-vote record.
      </p>
    </div>
  {:else if !result}
    <div class="text-slate-500">Loading…</div>
  {:else}
    <section class="bg-white rounded-lg shadow-sm p-5 grid sm:grid-cols-3 gap-4 text-sm">
      <div>
        <WinnerBadge winner={result.winner} />
      </div>
      <div>
        <div class="text-xs uppercase text-slate-500">Margin</div>
        <div class="font-semibold">{result.winner.margin_votes.toLocaleString()}</div>
        <div class="text-slate-500">{pct(result.winner.margin_pct)}</div>
      </div>
      <div>
        <div class="text-xs uppercase text-slate-500">Turnout</div>
        <div class="font-semibold">{result.totals.turnout_pct?.toFixed(2) ?? "—"}%</div>
        <div class="text-slate-500">{result.totals.votes_polled.toLocaleString()} polled</div>
      </div>
    </section>

    {#if event && state_code && STATE_AC[state_code]}
      <section class="bg-white rounded-lg shadow-sm p-4">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Location in {states.name(state_code)}</h2>
        <StateAcMapD3 state={state_code} rows={ac_winners} highlight_eci_no={effective_eci_no} height="360px" {event} />
        <p class="text-xs text-slate-400 mt-2">
          Highlighted: AC #{effective_eci_no}. Other constituencies are dimmed for context. Click any to drill in.
        </p>
      </section>
    {/if}

    <section class="bg-white rounded-lg shadow-sm p-5">
      <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Vote share</h2>
      <AcStackedBar {result} />
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5">
      <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">
        {#if result.candidates_total && result.candidates_total > result.top_n_cutoff}
          Top {result.top_n_cutoff} of {result.candidates_total} candidates
        {:else}
          {result.top_n_cutoff} candidate{result.top_n_cutoff === 1 ? "" : "s"}
        {/if}
      </h2>
      <table class="w-full text-sm">
        <thead class="text-left text-xs text-slate-500 uppercase">
          <tr><th class="py-2 w-10">#</th><th>Candidate</th><th>Party</th><th class="text-right">Votes</th><th class="text-right">Share</th></tr>
        </thead>
        <tbody class="divide-y">
          {#each result.candidates as c}
            {@const bio = fmtBiographic(c.bio)}
            <tr class={c.is_winner ? "bg-emerald-50" : ""}>
              <td class="py-2 text-slate-400 align-top">{c.rank}</td>
              <td class="font-medium align-top">
                <div>{c.name}</div>
                <!--
                  Biographics row: the testid is ALWAYS rendered (even when
                  no Statistical-Report adapter has populated bio columns for
                  this contest yet) so the e2e contract
                  (frontend/e2e/golden-path.spec.ts) can assert the projection
                  path is wired — but when there is no bio it renders EMPTY,
                  not an apologetic "Not declared". Candidate biographics are a
                  mandatory ECI filing; surfacing "Not declared" on every
                  un-ingested contest reads as the citizen's fault rather than
                  a pending ingest, so we fall back to nothing. The e2e asserts
                  `toBeAttached` (testid present in the DOM) rather than
                  `toBeVisible` (which an empty node fails by design).
                -->
                <div class="text-xs text-slate-500 mt-0.5" data-testid="candidate-biographics">
                  {#if bio}{bio}{/if}
                </div>
              </td>
              <td class="align-top">
                <div class="flex items-center gap-1.5">
                  <PartySymbolGlyph assetPath={c.election_symbol_asset_path} size={16} fallback="placeholder" />
                  {#if link.party(c.party_id)}
                    <a class="hover:underline" href={link.party(c.party_id)}>
                      <PartyPill size="sm" party_id={c.party_id} party_short={c.party_short} row={partyRowForResolver(c)}/>
                    </a>
                  {:else}
                    <PartyPill size="sm" party_id={c.party_id} party_short={c.party_short} row={partyRowForResolver(c)}/>
                  {/if}
                </div>
              </td>
              <td class="text-right tabular-nums align-top">{c.votes.toLocaleString()}</td>
              <td class="text-right tabular-nums align-top">{pct(c.vote_share_pct)}</td>
            </tr>
          {/each}
          <tr class="text-slate-500">
            <td></td><td>NOTA</td><td></td>
            <td class="text-right tabular-nums">{result.nota.votes.toLocaleString()}</td>
            <td class="text-right tabular-nums">{pct(result.nota.vote_share_pct)}</td>
          </tr>
          {#if result.others}
            <tr class="text-slate-500">
              <td></td><td>Others ({result.others.candidate_count})</td><td></td>
              <td class="text-right tabular-nums">{result.others.votes.toLocaleString()}</td>
              <td class="text-right tabular-nums">{pct(result.others.vote_share_pct)}</td>
            </tr>
          {/if}
        </tbody>
      </table>
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5 text-xs text-slate-500">
      Sources:
      <ul class="mt-1 space-y-1">
        {#each result.sources as s}
          <li><a class="font-mono hover:underline break-all" href={s.url} target="_blank" rel="noreferrer">{s.url}</a></li>
        {/each}
      </ul>
    </section>
  {/if}

  <!-- PR-W4a (2026-06-10): YearPillStrip + ConstituencyHistoryBar.
       Renders only on the bare-slug (W3b shape #3) leaf route - the
       legacy AC eci_no shapes pre-date this PR and stay simple. The
       strip + bar sit outside the AC/PC dispatch so both arms get
       them once `resolved_entity_id` is known. -->
  {#if resolved_entity_id && event && history_events.length > 0}
    <section
      class="bg-white rounded-lg shadow-sm p-5 space-y-4"
      data-testid="constituency-history-strip"
    >
      <div class="space-y-2">
        <h2 class="text-sm font-semibold uppercase text-slate-500">
          Jump to year
        </h2>
        <YearPillStrip
          events={history_events}
          active={event}
          onSelect={onPillSelect}
        />
      </div>
      <div class="space-y-2">
        <h3 class="text-lg font-medium">Across elections</h3>
        <ConstituencyHistoryBar rows={history_rows} />
      </div>
    </section>
  {/if}
</PageContainer>
