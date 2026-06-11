<script lang="ts">
  // NationalElection - rebuilt national event view for the election
  // experience overhaul plan PR-W3c (2026-06-10).
  //
  // Surface: `/t/elections/<event-slug>` (route table in main.ts).
  // Layout:
  //   1. Header           - citizen-facing event label + national chip.
  //   2. KPIs strip       - Total seats / Total electors / Total polled /
  //                         Turnout %. Derived from the W2b generic
  //                         loader's per-PC rows (NATIONAL-PC dispatch
  //                         was extended in the same PR with `electors`
  //                         + `votes_polled` projections; see
  //                         lib/view-models/election-results.ts).
  //   3. India choropleth - one polygon per state, coloured by the party
  //                         that won the most seats in that state. Click
  //                         a state polygon to drill into the per-state
  //                         event view (PR-W3b rebuilds the target page).
  //   4. Top-parties bar  - top 10 parties by national seat count, with
  //                         party-coloured horizontal bars sized against
  //                         the leader.
  //
  // Renamed from `NationalElectionsAtlas.svelte` in the same PR. The
  // pre-rebuild surface was a "Map | Equal seats" toggle over the
  // 543-PC national choropleth with a filter rail; that layout is gone,
  // replaced by the citizen-readable summary above. The hex/tile
  // cartogram + filter rail will return on PR-W4c (analyst-grade
  // scatter + filters lab) and PR-W3d (firehose) respectively, not
  // here.
  //
  // Data path (one loader, three projections):
  //   loadElectionResults({event}) -> ElectionResultRow[]
  //     -> KPIs           : sum electors, sum votes_polled,
  //                         avg turnout_pct, count rows
  //     -> per-state lead : group_by(state_code, party) -> top
  //     -> top-parties    : group_by(party) -> sort desc -> slice(10)
  //
  // The bespoke `loadIndiaLeadingParties` is intentionally NOT used here
  // (the W2b loader carries the same rows in a richer shape). PR-W5a
  // retires it once the surviving consumer (the home-page IndiaMap)
  // also flips.

  import MapChoropleth from "../lib/maplibre/MapChoropleth.svelte";
  import { INDIA_STATES } from "../lib/maplibre/sources";
  import {
    loadElectionResults,
    type ElectionResultRow,
  } from "../lib/view-models/election-results";
  import { loadStates, type StateRow } from "../lib/view-models/states";
  import type { LoaderResult } from "../lib/loader-result";
  import {
    getPartyColor,
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../lib/colors/resolver";
  import { navigate } from "../lib/url";
  import { link } from "../lib/links";
  import Scatter from "../lib/charts/Scatter.svelte";
  import type {
    ScatterDatum,
    ScatterFilters,
  } from "../lib/charts/scatter-model";
  import { slugify } from "../lib/slug";

  interface Props {
    /** Route params; `event` is the event slug (e.g. "general-2024"). */
    params: { event: string };
  }
  let { params }: Props = $props();
  const event = $derived(params.event);

  // ---- Loader (one call powers KPIs + choropleth + top-parties bar) ----
  let result = $state<LoaderResult<ElectionResultRow[]>>({ status: "loading" });
  let states_taxonomy = $state<StateRow[] | null>(null);
  loadStates()
    .then((s) => (states_taxonomy = s))
    .catch(() => (states_taxonomy = []));

  $effect(() => {
    const ev = event;
    result = { status: "loading" };
    loadElectionResults({ event: ev }).then((r) => {
      // Guard against a stale event switch resolving after a newer one.
      if (ev === event) result = r;
    });
  });

  const winners = $derived<ElectionResultRow[]>(
    result.status === "ok" || result.status === "partial" ? result.data : [],
  );
  const pending = $derived(
    result.status === "partial" ||
      (result.status === "ok" && winners.length === 0),
  );

  // ---- KPIs ------------------------------------------------------------
  interface Kpis {
    total_seats: number;
    total_electors: number | null;
    total_polled: number | null;
    turnout_pct: number | null;
  }
  const kpis = $derived.by<Kpis>(() => {
    if (winners.length === 0) {
      return {
        total_seats: 0,
        total_electors: null,
        total_polled: null,
        turnout_pct: null,
      };
    }
    let elec = 0;
    let elec_known = 0;
    let polled = 0;
    let polled_known = 0;
    let turn_sum = 0;
    let turn_known = 0;
    for (const w of winners) {
      if (w.electors != null) {
        elec += w.electors;
        elec_known++;
      }
      if (w.votes_polled != null) {
        polled += w.votes_polled;
        polled_known++;
      }
      if (w.turnout_pct != null) {
        turn_sum += w.turnout_pct;
        turn_known++;
      }
    }
    return {
      total_seats: winners.length,
      total_electors: elec_known > 0 ? elec : null,
      total_polled: polled_known > 0 ? polled : null,
      turnout_pct: turn_known > 0 ? turn_sum / turn_known : null,
    };
  });

  // ---- Palette (party_id -> hex via the canonical 3-tier resolver) ----
  function partyIdFor(w: {
    party_id: string | null;
    party_short: string | null;
  }): string {
    if (w.party_id) return w.party_id;
    const slug = (w.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  }
  function rowFor(pid: string, w: ElectionResultRow): PartyRowForResolver | null {
    if (w.brand_colour_hex == null) return null;
    return {
      party_id: pid,
      eci_code: w.party_eci_code,
      brand_colour: {
        hex: w.brand_colour_hex,
        confidence: w.brand_colour_confidence ?? "medium",
      },
    };
  }
  const palette_bundle = $derived.by(() => {
    const ids: string[] = [];
    const rowMap = new Map<string, PartyRowForResolver | null>();
    const seen = new Set<string>();
    for (const w of winners) {
      const pid = partyIdFor(w);
      if (seen.has(pid)) continue;
      seen.add(pid);
      ids.push(pid);
      rowMap.set(pid, rowFor(pid, w));
    }
    return { palette: resolvePartyPalette(ids, rowMap), rowMap };
  });
  function fillForParty(pid: string, w: ElectionResultRow): string {
    const { palette, rowMap } = palette_bundle;
    return (
      palette.get(pid)?.hex ??
      getPartyColor(pid, rowMap.get(pid) ?? null).hex
    );
  }

  // ---- Per-state leading party (for state choropleth fills) ----------
  interface StateLead {
    state_code: string;
    party_id: string;
    party_short: string;
    seats: number;
    color: string;
  }
  const state_leads = $derived.by<Map<string, StateLead>>(() => {
    const out = new Map<string, StateLead>();
    if (winners.length === 0) return out;
    // Group seats per (state_code, party_id). Track ONE sample row per
    // party so the colour-resolver has the brand_colour mirror to read.
    const by = new Map<
      string,
      Map<string, { seats: number; sample: ElectionResultRow }>
    >();
    for (const w of winners) {
      const sc = w.state_code;
      const pid = partyIdFor(w);
      const inner = by.get(sc) ?? new Map();
      const cur = inner.get(pid) ?? { seats: 0, sample: w };
      cur.seats += 1;
      inner.set(pid, cur);
      by.set(sc, inner);
    }
    for (const [sc, parties] of by) {
      let top:
        | { pid: string; seats: number; sample: ElectionResultRow }
        | null = null;
      for (const [pid, p] of parties) {
        if (!top || p.seats > top.seats) {
          top = { pid, seats: p.seats, sample: p.sample };
        }
      }
      if (!top) continue;
      out.set(sc, {
        state_code: sc,
        party_id: top.pid,
        party_short: top.sample.party_short ?? "UNK",
        seats: top.seats,
        color: fillForParty(top.pid, top.sample),
      });
    }
    return out;
  });

  // ---- Choropleth fills + tooltips, keyed on the LGD boundary key ----
  const fills = $derived.by<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    if (!states_taxonomy) return out;
    for (const s of states_taxonomy) {
      const lead = state_leads.get(s.eci_code);
      if (lead) out[s.boundary_join_key] = lead.color;
    }
    return out;
  });
  const tooltips = $derived.by<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    if (!states_taxonomy) return out;
    for (const s of states_taxonomy) {
      const lead = state_leads.get(s.eci_code);
      if (!lead) {
        out[s.boundary_join_key] =
          `<div class="font-semibold">${escapeHtml(s.display_name)}</div>` +
          `<div class="text-slate-500">no data</div>`;
        continue;
      }
      out[s.boundary_join_key] =
        `<div class="font-semibold">${escapeHtml(s.display_name)}</div>` +
        `<div class="text-slate-600">Leading: ${escapeHtml(lead.party_short)} (${lead.seats} seats)</div>` +
        `<div class="text-slate-400 text-[10px] mt-1">click to drill in &rarr;</div>`;
    }
    return out;
  });
  function escapeHtml(s: string): string {
    return s.replace(/[&<>"']/g, (c) =>
      c === "&"
        ? "&amp;"
        : c === "<"
          ? "&lt;"
          : c === ">"
            ? "&gt;"
            : c === '"'
              ? "&quot;"
              : "&#39;",
    );
  }

  // Reverse-lookup boundary key -> ECI for click navigation.
  const KEY_TO_ECI = $derived.by<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    for (const s of states_taxonomy ?? []) {
      out[s.boundary_join_key] = s.eci_code;
    }
    return out;
  });

  function onStateClick(sel: { key: string | number }): void {
    const code = KEY_TO_ECI[String(sel.key)];
    if (code) navigate(link.stateElection(code, event));
  }

  // ---- Top-parties bar (top 10 nationally by seats) ------------------
  interface PartyTotal {
    party_id: string;
    party_short: string;
    seats: number;
    color: string;
  }
  const TOP_N = 10;
  const top_parties = $derived.by<PartyTotal[]>(() => {
    const by = new Map<string, PartyTotal>();
    for (const w of winners) {
      const pid = partyIdFor(w);
      const cur = by.get(pid);
      if (cur) {
        cur.seats += 1;
      } else {
        by.set(pid, {
          party_id: pid,
          party_short: w.party_short ?? "UNK",
          seats: 1,
          color: fillForParty(pid, w),
        });
      }
    }
    return [...by.values()].sort((a, b) => b.seats - a.seats).slice(0, TOP_N);
  });
  const top_party_max = $derived(top_parties[0]?.seats ?? 1);

  // ---- Display label for the citizen-facing H1 -----------------------
  const event_pretty = $derived.by<string>(() => {
    // general-2024 -> "Parliament Election 2024"; assembly-2023 ->
    // "Assembly Election 2023". Bye-event + legacy ECI forms
    // (LsGenJun2024) pass through verbatim.
    const m = /^(general|assembly)-(\d{4})$/.exec(event);
    if (m) {
      const body_pretty = m[1] === "general" ? "Parliament" : "Assembly";
      return `${body_pretty} Election ${m[2]}`;
    }
    return event;
  });

  // ---- Number formatters (Indian locale, compact for big numbers) ----
  const INT_FMT = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
  const COMPACT_FMT = new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 2,
  });
  function fmtInt(n: number | null): string {
    return n == null ? "-" : INT_FMT.format(n);
  }
  function fmtCompact(n: number | null): string {
    return n == null ? "-" : COMPACT_FMT.format(n);
  }
  function fmtPct(n: number | null): string {
    return n == null ? "-" : `${n.toFixed(1)}%`;
  }

  // ---- Scatter chart projection (PR-W4c) ------------------------------
  // Project the loader's per-PC winners into the chart's row shape; the
  // chart owns its own d3 scales + filter dispatch + click handler. The
  // chart is invariant on the loader output that it does not consume —
  // it ignores `entity_name` vs `constituency_name` mismatch and the
  // `period_label` -> `event_id` rename happens here once.
  let scatter_filters = $state<ScatterFilters>({
    body: "parliament",
    reservation: "all",
    margin_band: "all",
  });
  const scatter_data = $derived.by<ScatterDatum[]>(() => {
    const out: ScatterDatum[] = [];
    for (const w of winners) {
      if (w.turnout_pct == null || w.margin_pct == null) continue;
      out.push({
        entity_id: w.entity_id,
        state_slug: w.state_slug,
        constituency_slug: slugify(w.entity_name),
        constituency_name: w.entity_name,
        event_id: event,
        turnout_pct: w.turnout_pct,
        margin_pct: w.margin_pct,
        // PCs without an `electors` figure (long-tail) get a tiny
        // placeholder so the dot still paints; the radius scale clamps
        // to the floor at render time.
        electors: w.electors ?? 0,
        winner_party_id: partyIdFor(w),
        winner_party_short: w.party_short ?? "UNK",
        reservation: w.reservation,
        body: "parliament",
      });
    }
    return out;
  });
  function onScatterDotClick(d: ScatterDatum): void {
    navigate(
      `${link.stateElection(d.state_slug, d.event_id)}/${d.constituency_slug}`,
    );
  }
</script>
<main class="mx-auto max-w-6xl space-y-6 p-4">
  <header class="space-y-2">
    <h1 class="text-2xl font-semibold text-slate-900">
      India &middot; {event_pretty}
    </h1>
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <span
        class="inline-block rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
        data-testid="national-event-chip"
      >national</span>
      <span class="text-slate-500">
        Event slug <code class="text-slate-700">{event}</code>
      </span>
    </div>
  </header>

  {#if result.status === "failed"}
    <!-- OWID precedent: chart frame still renders with a retry; no 404. -->
    <div
      class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
      data-testid="national-event-error"
    >
      <p class="mb-2">Data couldn't load: {result.reason}</p>
      {#if result.retry}
        <button
          type="button"
          class="rounded border border-amber-300 bg-white px-3 py-1 text-xs hover:bg-amber-100"
          onclick={() => result.status === "failed" && result.retry?.()}
          >Try again</button
        >
      {/if}
    </div>
  {:else}
    <!-- KPIs strip ------------------------------------------------------ -->
    <section
      class="grid grid-cols-2 gap-3 sm:grid-cols-4"
      data-testid="national-event-kpis"
    >
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="text-xs uppercase tracking-wide text-slate-500">
          Total seats
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtInt(kpis.total_seats)}
        </div>
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="text-xs uppercase tracking-wide text-slate-500">
          Total electors
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtCompact(kpis.total_electors)}
        </div>
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="text-xs uppercase tracking-wide text-slate-500">
          Total polled
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtCompact(kpis.total_polled)}
        </div>
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="text-xs uppercase tracking-wide text-slate-500">
          Turnout
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtPct(kpis.turnout_pct)}
        </div>
      </div>
    </section>

    {#if pending}
      <div
        class="rounded border border-dashed border-slate-300 bg-slate-50 p-3 text-center text-sm text-slate-500"
        data-testid="national-event-pending"
      >
        Results for this election are not published yet - the boundary map
        below still draws.
      </div>
    {/if}

    <!-- India choropleth ----------------------------------------------- -->
    <section class="space-y-2" data-testid="national-event-map">
      <h2 class="text-sm font-medium text-slate-700">
        Winning party by state
      </h2>
      <p class="text-xs text-slate-500">
        Each state is coloured by the party that won the most seats in
        that state. Click a state to drill into its per-state results.
      </p>
      <MapChoropleth
        entry={INDIA_STATES}
        {fills}
        {tooltips}
        height="520px"
        onSelect={onStateClick}
      />
    </section>

    <!-- Top-parties bar (top 10 nationally by seats) ------------------- -->
    <section class="space-y-2" data-testid="national-event-top-parties">
      <h2 class="text-sm font-medium text-slate-700">
        Top parties by seats
      </h2>
      {#if top_parties.length === 0}
        <p class="text-xs text-slate-500">
          No party totals available for this event yet.
        </p>
      {:else}
        <ol class="space-y-1.5">
          {#each top_parties as p, i (p.party_id)}
            <li
              class="flex items-center gap-3 text-sm"
              data-testid="national-event-top-parties-row"
            >
              <span class="w-5 text-right text-xs text-slate-500"
                >{i + 1}.</span
              >
              <span
                class="w-14 truncate font-medium text-slate-700"
                title={p.party_short}>{p.party_short}</span
              >
              <div class="relative h-5 flex-1 rounded bg-slate-100">
                <div
                  class="h-full rounded"
                  style:width="{(p.seats / top_party_max) * 100}%"
                  style:background-color={p.color}
                ></div>
              </div>
              <span
                class="w-14 text-right font-medium tabular-nums text-slate-900"
                >{p.seats}</span
              >
            </li>
          {/each}
        </ol>
      {/if}
    </section>

    <!-- Scatter chart (PR-W4c MUST-FEATURE) ---------------------------- -->
    <section class="space-y-2" data-testid="national-event-scatter">
      <h2 class="text-sm font-medium text-slate-700">
        Turnout vs winning margin &middot; all constituencies
      </h2>
      <Scatter
        data={scatter_data}
        filters={scatter_filters}
        onFiltersChange={(next) => (scatter_filters = next)}
        onDotClick={onScatterDotClick}
      />
    </section>
  {/if}
</main>
