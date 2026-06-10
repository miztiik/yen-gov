<script lang="ts">
  // StateElection - rebuilt state event view for the election experience
  // overhaul plan PR-W3b (2026-06-10).
  //
  // Surface: /<state>/elections/<event-slug>. Layout:
  //   1. Header                  - state name + event display label.
  //   2. KPIs strip              - seats / voters / polled / turnout.
  //   3. State choropleth        - winner-coloured map, with a
  //                                Winner | Margin colour toggle (NO
  //                                URL persistence per W3b doctrine).
  //   4. Top-parties bar         - top N parties that contested this
  //                                event in this state, by seats.
  //   5. AllianceTotals          - alliance-first display, party
  //                                breakdown on click.
  //   6. InlineCounterfactualSwing - ephemeral state-wide swing
  //                                what-if (component state ONLY,
  //                                NO ?s=<b64>).
  //   7. Constituency table      - per-seat row: name + winner-party
  //                                pill + winner share % + margin %.
  //                                Row click navigates to the new
  //                                bare-slug constituency leaf.
  //   8. Compare CTA             - link to the W4b path-form compare
  //                                URL (route handler ships in PR-W4b;
  //                                the link can exist earlier).
  //
  // Data path:
  //   loadElectionResults({event, state}) - assembly events: STATE-AC.
  //                                         Returns per-AC winner rows.
  //   loadElectionResults({event})        - parliament events: NATIONAL-PC,
  //                                         then filter by state_slug
  //                                         locally. (state-scope only
  //                                         supports assembly today.)
  //
  // Parliament-body events keep most panels but disable the inline
  // counterfactual swing (the psephlab canonical loader is assembly-
  // only); the panel renders a citizen-readable note explaining why.
  //
  // Page chrome: no ?s=<b64> URL handling on this surface. Inline
  // scenarios are ephemeral by W3b doctrine - refresh resets them.

  import {
    fetchElectionEvents,
    findEvent,
    listEventsForState,
    type ElectionEventRow,
    type ElectionEventsCatalogue,
  } from "../lib/election-events";
  import { states } from "../lib/states.svelte";
  import { slugify } from "../lib/slug";
  import { link } from "../lib/links";
  import { navigate } from "../lib/url";
  import {
    loadElectionResults,
    type ElectionResultRow,
  } from "../lib/view-models/election-results";
  import type { LoaderResult } from "../lib/loader-result";
  import {
    getPartyColor,
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../lib/colors/resolver";
  import StateAcMap from "../lib/maplibre/StateAcMap.svelte";
  import { STATE_AC } from "../lib/maplibre/sources";
  import type { AcWinner } from "../lib/view-models/state-overview";
  import InlineCounterfactualSwing from "../lib/elections/InlineCounterfactualSwing.svelte";
  import AllianceTotals from "../lib/elections/AllianceTotals.svelte";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import { route } from "../lib/router.svelte";

  interface Props {
    params: { state: string; event: string };
  }
  let { params }: Props = $props();

  // ---- Catalogue + event resolution ----------------------------------
  let catalogue = $state<ElectionEventsCatalogue | null>(null);
  let catalogue_error = $state<string | null>(null);
  fetchElectionEvents()
    .then((c) => (catalogue = c))
    .catch((e) => (catalogue_error = String(e)));

  const state_code = $derived(states.codeFromSlug(params.state));
  const state_name = $derived(state_code ? states.name(state_code) : "");
  const event_row = $derived<ElectionEventRow | null>(
    findEvent(catalogue, state_code, params.event),
  );
  const body = $derived<"pc" | "ac" | null>(
    !event_row
      ? null
      : event_row.kind === "parliament" || params.event.startsWith("general")
        ? "pc"
        : "ac",
  );

  const states_loading = $derived(!states.isLoaded);
  const catalogue_loading = $derived(
    catalogue === null && catalogue_error === null,
  );

  // ---- W2b loader (one call powers KPIs + map + top-parties + table) -
  let result = $state<LoaderResult<ElectionResultRow[]>>({ status: "loading" });
  $effect(() => {
    const sc = state_code;
    const ev_id = event_row?.event_id;
    const b = body;
    if (!sc || !ev_id || !b) {
      result = { status: "loading" };
      return;
    }
    result = { status: "loading" };
    if (b === "ac") {
      loadElectionResults({ event: ev_id, state: sc }).then((r) => {
        if (ev_id === event_row?.event_id && sc === state_code) result = r;
      });
    } else {
      // PC = national parliament event; load NATIONAL-PC and filter
      // by state locally. The W2b loader doesn't support a per-state
      // parliament scope today.
      loadElectionResults({ event: ev_id }).then((r) => {
        if (ev_id !== event_row?.event_id || sc !== state_code) return;
        if (r.status !== "ok" && r.status !== "partial") {
          result = r;
          return;
        }
        // The per-row state_slug field is the LGD form
        // (e.g. "chhattisgarh"). The URL segment IS the LGD slug.
        const target_slug = params.state;
        const filtered = r.data.filter((row) => row.state_slug === target_slug);
        result = { status: r.status, data: filtered } as LoaderResult<
          ElectionResultRow[]
        >;
      });
    }
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

  // ---- Palette ---------------------------------------------------------
  function partyIdFor(w: {
    party_id: string | null;
    party_short: string | null;
  }): string {
    if (w.party_id) return w.party_id;
    const slug = (w.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  }
  function rowFor(
    pid: string,
    w: ElectionResultRow,
  ): PartyRowForResolver | null {
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

  // ---- Top parties (state-scoped) -------------------------------------
  interface PartyTotal {
    party_id: string;
    party_short: string;
    seats: number;
    color: string;
  }
  const TOP_N = 8;
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

  // ---- StateAcMap shim ------------------------------------------------
  // Reuse the existing AC choropleth for assembly events. AcWinner is the
  // legacy shape the map consumes; map W2b rows -> AcWinner one-to-one.
  // For Winner mode (default): fill = party colour.
  // For Margin mode: fill = greyscale shade by |margin_pct| (darker =
  // larger margin). The shim overrides the per-row brand_colour_hex
  // so the existing StateAcMap colour-by-brand pathway renders Margin
  // without a deeper component change.
  type ColorMode = "winner" | "margin";
  let color_mode = $state<ColorMode>("winner");

  function marginGrey(pct: number | null): string {
    if (pct == null) return "#cbd5e1"; // slate-300 fallback
    // 0% margin -> very light slate; 30%+ margin -> dark slate. Clamp.
    const v = Math.min(1, Math.max(0, pct / 30));
    // Linear blend between slate-200 (#e2e8f0) and slate-700 (#334155).
    const lerp = (a: number, b: number): number =>
      Math.round(a + (b - a) * v);
    const r = lerp(0xe2, 0x33);
    const g = lerp(0xe8, 0x41);
    const b2 = lerp(0xf0, 0x55);
    const toHex = (n: number): string => n.toString(16).padStart(2, "0");
    return `#${toHex(r)}${toHex(g)}${toHex(b2)}`;
  }

  const ac_winners_shim = $derived<AcWinner[]>(
    body !== "ac"
      ? []
      : winners.map<AcWinner>((w) => {
          const pid = partyIdFor(w);
          const winner_hex =
            color_mode === "margin"
              ? marginGrey(w.margin_pct)
              : fillForParty(pid, w);
          return {
            ac_eci_no: w.eci_no,
            ac_name: w.entity_name,
            winner_candidate: w.winner_candidate_name ?? "",
            winner_party_id: pid,
            party_short: w.party_short ?? "UNK",
            party_eci_code: w.party_eci_code,
            brand_colour_hex: winner_hex,
            brand_colour_confidence: w.brand_colour_confidence,
            margin_pct: w.margin_pct,
            turnout_pct: w.turnout_pct,
            winner_age: w.winner_age,
          } as unknown as AcWinner;
        }),
  );

  // ---- Constituency table rows (sorted by entity_name) ---------------
  interface SeatRow {
    entity_id: string;
    entity_name: string;
    winner_party_short: string;
    winner_party_id: string;
    winner_color: string;
    winner_share_pct: number | null;
    margin_pct: number | null;
    href: string;
  }
  const seat_rows = $derived.by<SeatRow[]>(() => {
    const out: SeatRow[] = [];
    const slug_st = params.state;
    const ev = event_row?.event_id ?? params.event;
    for (const w of winners) {
      const pid = partyIdFor(w);
      const name_slug = slugify(w.entity_name);
      out.push({
        entity_id: w.entity_id,
        entity_name: w.entity_name,
        winner_party_short: w.party_short ?? "UNK",
        winner_party_id: pid,
        winner_color: fillForParty(pid, w),
        winner_share_pct: w.vote_share_pct,
        margin_pct: w.margin_pct,
        href: `/${slug_st}/elections/${encodeURIComponent(ev)}/${encodeURIComponent(name_slug)}`,
      });
    }
    out.sort((a, b) =>
      a.entity_name.localeCompare(b.entity_name, "en", { sensitivity: "base" }),
    );
    return out;
  });

  // ---- Previous-event link (W4b CTA target) --------------------------
  // For "compare with previous same-body event": find the event before
  // the active one of the same kind.
  const previous_same_body = $derived.by<ElectionEventRow | null>(() => {
    const cat = catalogue;
    const sc = state_code;
    const ev = event_row;
    if (!cat || !sc || !ev) return null;
    const all = listEventsForState(cat, sc).filter(
      (e) => e.kind === ev.kind,
    );
    // Sorted ascending by polled_on; find index of ev and pick the
    // one before it.
    all.sort((a, b) => a.polled_on.localeCompare(b.polled_on));
    const idx = all.findIndex((e) => e.event_id === ev.event_id);
    if (idx <= 0) return null;
    return all[idx - 1];
  });

  const compare_href = $derived.by<string | null>(() => {
    const ev = event_row;
    const prev = previous_same_body;
    if (!ev || !prev) return null;
    return `/compare/elections/${params.state}/${encodeURIComponent(prev.event_id)}/${encodeURIComponent(ev.event_id)}`;
  });

  // ---- Display label --------------------------------------------------
  const event_pretty = $derived.by<string>(() => {
    if (event_row) return event_row.display;
    const m = /^(general|assembly)-(\d{4})$/.exec(params.event);
    if (m) {
      const body_pretty = m[1] === "general" ? "Parliament" : "Assembly";
      return `${body_pretty} Election ${m[2]}`;
    }
    return params.event;
  });

  // ---- Number formatters ---------------------------------------------
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

  const crumbs = $derived(route.crumbs ? route.crumbs(route.params) : []);
</script>

<Breadcrumb {crumbs} />

<main class="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
  {#if catalogue_error}
    <div
      class="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
      data-testid="state-election-error"
    >
      Failed to load election catalogue: <code>{catalogue_error}</code>
    </div>
  {:else if catalogue_loading || states_loading}
    <p class="text-sm text-slate-500">Loading…</p>
  {:else if !state_code}
    <div class="space-y-2" data-testid="state-election-state-notfound">
      <p class="text-sm">
        <a href={link.home()} class="text-sky-700 hover:underline"
          >← Home</a
        >
      </p>
      <h1 class="text-2xl font-semibold">State not found</h1>
      <p class="text-sm text-slate-600">
        No state with slug
        <code class="rounded bg-slate-100 px-1">{params.state}</code>.
      </p>
    </div>
  {:else if !event_row}
    <div class="space-y-2" data-testid="state-election-event-notfound">
      <h1 class="text-2xl font-semibold">Election not found</h1>
      <p class="text-sm text-slate-600">
        No election with id
        <code class="rounded bg-slate-100 px-1">{params.event}</code>
        is catalogued for {state_name}. See the
        <a
          href={link.stateTopic(state_code, "elections")}
          class="text-sky-700 hover:underline">elections timeline</a
        >.
      </p>
    </div>
  {:else}
    {@const ev = event_row}
    <!-- Header -->
    <header class="space-y-2">
      <h1
        class="text-2xl font-semibold text-slate-900"
        data-testid="state-event-header"
      >
        {state_name} &middot; {event_pretty}
      </h1>
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span
          class="inline-block rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
          data-testid="state-event-body-chip"
        >{body === "pc" ? "Parliament" : "Assembly"}</span>
        <span class="text-slate-500">
          Polled <span class="tabular-nums">{ev.polled_on}</span>
        </span>
        <span class="text-slate-500">
          Event slug <code class="text-slate-700">{params.event}</code>
        </span>
      </div>
    </header>

    {#if result.status === "failed"}
      <div
        class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
        data-testid="state-event-load-error"
      >
        <p>Data couldn't load: {result.reason}</p>
      </div>
    {:else}
      <!-- KPIs strip -->
      <section
        class="grid grid-cols-2 gap-3 sm:grid-cols-4"
        data-testid="state-event-kpis"
      >
        <div class="rounded border border-slate-200 bg-white p-3">
          <div class="text-xs uppercase tracking-wide text-slate-500">
            Seats
          </div>
          <div class="mt-1 text-2xl font-semibold text-slate-900">
            {fmtInt(kpis.total_seats)}
          </div>
        </div>
        <div class="rounded border border-slate-200 bg-white p-3">
          <div class="text-xs uppercase tracking-wide text-slate-500">
            Total voters
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
          data-testid="state-event-pending"
        >
          Results for this election are not published yet.
        </div>
      {/if}

      <!-- State choropleth (assembly only; PC events don't have an AC map) -->
      {#if body === "ac" && state_code && STATE_AC[state_code]}
        <section
          class="space-y-2"
          data-testid="state-event-map"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-sm font-medium text-slate-700">
              Constituencies
            </h2>
            <div
              class="inline-flex rounded border border-slate-200 bg-white p-0.5 text-xs"
              data-testid="state-event-map-mode"
            >
              <button
                type="button"
                class={color_mode === "winner"
                  ? "rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
                  : "px-2 py-0.5 text-slate-500"}
                data-testid="state-event-map-mode-winner"
                onclick={() => (color_mode = "winner")}
              >Winner</button>
              <button
                type="button"
                class={color_mode === "margin"
                  ? "rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
                  : "px-2 py-0.5 text-slate-500"}
                data-testid="state-event-map-mode-margin"
                onclick={() => (color_mode = "margin")}
              >Margin</button>
            </div>
          </div>
          <StateAcMap
            state={state_code}
            rows={ac_winners_shim}
            event={ev.event_id}
            height="420px"
          />
          <p class="text-xs text-slate-500">
            {color_mode === "winner"
              ? "Each constituency is filled with the winning party's colour."
              : "Each constituency is shaded by winning margin (darker = larger margin)."}
          </p>
        </section>
      {/if}

      <!-- Top parties -->
      <section
        class="space-y-2"
        data-testid="state-event-top-parties"
      >
        <h2 class="text-sm font-medium text-slate-700">
          Top parties by seats
        </h2>
        {#if top_parties.length === 0}
          <p class="text-xs text-slate-500">No party totals yet.</p>
        {:else}
          <ol class="space-y-1.5">
            {#each top_parties as p, i (p.party_id)}
              <li
                class="flex items-center gap-3 text-sm"
                data-testid="state-event-top-parties-row"
              >
                <span class="w-5 text-right text-xs text-slate-500"
                  >{i + 1}.</span
                >
                <span
                  class="w-14 truncate font-medium text-slate-700"
                  >{p.party_short}</span
                >
                <div class="flex flex-1 items-center">
                  <div
                    class="h-3 rounded-sm"
                    style={`width:${(p.seats / top_party_max) * 100}%;background-color:${p.color};`}
                  ></div>
                </div>
                <span
                  class="w-10 text-right tabular-nums text-sm text-slate-700"
                  >{fmtInt(p.seats)}</span
                >
              </li>
            {/each}
          </ol>
        {/if}
      </section>

      <!-- Alliance totals -->
      <AllianceTotals
        event={ev.event_id}
        winners={winners.map((w) => ({
          party_id: w.party_id,
          party_short: w.party_short,
          party_eci_code: w.party_eci_code,
        }))}
        polled_on={ev.polled_on}
      />

      <!-- Inline counterfactual swing (assembly only) -->
      {#if state_code}
        <InlineCounterfactualSwing
          event={ev.event_id}
          state_code={state_code}
          disabled={body !== "ac"}
        />
      {/if}

      <!-- Constituency table -->
      <section
        class="space-y-2"
        data-testid="state-event-constituency-table"
      >
        <h2 class="text-sm font-medium text-slate-700">
          Constituencies ({fmtInt(seat_rows.length)})
        </h2>
        {#if seat_rows.length === 0}
          <p class="text-xs text-slate-500">No constituency rows yet.</p>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-left text-xs uppercase text-slate-500">
                <tr>
                  <th class="py-2">Constituency</th>
                  <th class="py-2">Winner</th>
                  <th class="py-2 text-right">Share</th>
                  <th class="py-2 text-right">Margin</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                {#each seat_rows as r (r.entity_id)}
                  <tr
                    class="hover:bg-slate-50"
                    data-testid="state-event-constituency-row"
                  >
                    <td class="py-2">
                      <a
                        class="text-sky-700 hover:underline"
                        href={r.href}
                        data-testid="state-event-constituency-link"
                      >{r.entity_name}</a>
                    </td>
                    <td class="py-2">
                      <span
                        class="inline-block rounded px-1.5 py-0.5 text-xs font-medium text-white"
                        style={`background-color:${r.winner_color};`}
                      >{r.winner_party_short}</span>
                    </td>
                    <td class="py-2 text-right tabular-nums">
                      {fmtPct(r.winner_share_pct)}
                    </td>
                    <td class="py-2 text-right tabular-nums">
                      {fmtPct(r.margin_pct)}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </section>

      <!-- Compare CTA (W4b target) -->
      {#if compare_href && previous_same_body}
        <nav
          class="flex flex-wrap gap-2 text-sm"
          aria-label="Compare elections"
        >
          <a
            class="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-sky-800 hover:bg-sky-100"
            href={compare_href}
            data-testid="state-event-compare-cta"
          >Compare with {previous_same_body.display} →</a>
        </nav>
      {/if}
    {/if}
  {/if}
</main>
