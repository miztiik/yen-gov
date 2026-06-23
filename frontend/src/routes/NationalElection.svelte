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
  //   3. Map (3-way)      - States (one polygon per state, default)
  //                         | Constituencies (543 PC polygons, new)
  //                         | Equal seats (national PC TileCartogram).
  //                         Winner|Margin sub-toggle applies to the two
  //                         per-PC arms (it does NOT apply to the States
  //                         arm whose IndiaPartyMap owns its own fills).
  //   4. Top-parties      - PartyBar with click-to-mute, top 10 parties
  //                         by national seat count. Muting recedes
  //                         matching cells on the Constituencies +
  //                         Equal-seats arms; the States arm carries the
  //                         mute on the PartyBar swatch only (IndiaPartyMap
  //                         loads its own fills and does not accept overrides).
  //   5. Scatter          - turnout vs margin, radius = absolute vote gap.
  //
  // Renamed from `NationalElectionsAtlas.svelte` in PR-W3c. The pre-W3c
  // surface had a "Map | Equal seats" toggle + filter rail that was
  // deliberately removed - "will return on PR-W4c + PR-W3d". This PR
  // (TODO/20260612-pc-choropleth-tile-and-party-filter-restoration-plan.md)
  // closes that deferral via the 3-way toggle above plus the
  // mute-rail wiring on PartyBar.
  //
  // Data path (one loader, four projections):
  //   loadElectionResults({event}) -> ElectionResultRow[]
  //     -> KPIs           : sum electors, sum votes_polled,
  //                         avg turnout_pct, count rows
  //     -> top-parties    : group_by(party) -> sort desc -> slice(10)
  //                         (PartyTotals shape so PartyBar can consume)
  //     -> pc_winners     : PcWinnerRow[] for IndiaPcMapD3 + TileCartogram
  //                         (unique_id = `${state_code}_${eci_no}`)
  //     -> scatter        : per-PC dot, (turnout, margin), radius=|gap|

  import IndiaPartyMap from "../lib/charts/IndiaPartyMap.svelte";
  import IndiaPcMapD3, {
    type PcWinnerRow,
  } from "../lib/charts/IndiaPcMapD3.svelte";
  import { INDIA_PC, INDIA_PC_BY_NAME } from "../lib/boundaries/sources";
  import TileCartogram from "../lib/charts/TileCartogram.svelte";
  import {
    fetchElectionTileLayouts,
    fetchElectionTileScopes,
    hasLayoutForScope,
    selectLayout,
    buildTileRows,
    type TileLayoutRow,
    type TileRow,
    type TileWinnerInput,
  } from "../lib/view-models/election-tile-layout";
  import {
    loadElectionResults,
    type ElectionResultRow,
  } from "../lib/view-models/election-results";
  import type { LoaderResult } from "../lib/loader-result";
  import { navigate } from "../lib/url";
  import { link } from "../lib/links";
  import Scatter from "../lib/charts/Scatter.svelte";
  import type {
    ScatterDatum,
    ScatterFilters,
  } from "../lib/charts/scatter-model";
  import { slugify } from "../lib/slug";
  import { aliasPcSlugUid } from "../lib/elections/pc-slug-alias";
  import PartyBar from "../lib/PartyBar.svelte";
  import ParliamentArc from "../lib/ParliamentArc.svelte";
  import type { PartyResult } from "../lib/psephlab/types";
  import type { PartyTotals } from "../lib/data";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import TopicIcon from "../lib/TopicIcon.svelte";
  import {
    marginShade,
    resolveWinnerBaseColours,
    MARGIN_FILL_OPACITY,
  } from "../lib/elections/election-map-coloring";
  import MarginLegend from "../lib/elections/MarginLegend.svelte";
  import MapCoverageNote from "../lib/charts/MapCoverageNote.svelte";
  import type { MapCoverageEmit } from "../lib/charts/map-coverage";
  import {
    buildPartyKeyToPid,
    hiddenPidSet,
    pcDelimYearForLsEvent,
  } from "../lib/charts/india-pc-map-helpers";
  import AllianceTotals from "../lib/elections/AllianceTotals.svelte";
  import ElectionSeizuresCard from "../lib/elections/ElectionSeizuresCard.svelte";
  import StateEventCrossEventSankey from "../lib/elections/StateEventCrossEventSankey.svelte";
  import type { PrevWinnersState } from "../lib/elections/seat-flow-model";
  import { loadAlliances } from "../lib/psephlab/alliances";
  import type { AllianceLookup } from "../lib/psephlab/types";
  import {
    loadEventSummary,
    type EventSummaryRow,
  } from "../lib/elections/event-summary-loader";
  // Row 7 (TODO/20260622-election-constituency-grouping-plan.md): national
  // constituency list - an outer State accordion wrapping the SAME PC-mode
  // StateEventConstituencyList per expanded state.
  import StateEventConstituencyList from "../lib/elections/StateEventConstituencyList.svelte";
  import {
    loadAcEntities,
    buildNationalStateGroups,
    filterNationalBranches,
    type AcEntity,
    type NationalBranchView,
    type NationalFilterPc,
  } from "../lib/elections/constituency-district-loader";
  import {
    buildPartyStrip,
    type GroupHeaderResult,
    type PartyStrip,
    type ReservationKind,
  } from "../lib/elections/constituency-list-tokens";
  import { loadStates } from "../lib/view-models/states";

  // Events that have an MCC-period seizures CSV ingested under
  // `datasets/elections/parliament/election=<year>/mcc_seizures.csv`.
  // Today only 2019 is on disk (Row A of TODO/20260614-three-
  // ephemeral-ingests-plan.md). When future LS events are ingested,
  // add their event_id here OR lift this guard to a small manifest /
  // catalogue once the count crosses the threshold where a hardcoded
  // set is the wrong shape (Jony >= 4 reuses earns the abstraction).
  const EVENTS_WITH_SEIZURES = new Set<string>(["general-2019"]);

  interface Props {
    /** Route params; `event` is the event slug (e.g. "general-2024"). */
    params: { event: string };
  }
  let { params }: Props = $props();
  const event = $derived(params.event);

  // ---- Loader (one call powers KPIs + top-parties bar + scatter) -----
  // Map fills are NOT derived here; IndiaPartyMap owns that pipeline.
  let result = $state<LoaderResult<ElectionResultRow[]>>({ status: "loading" });

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

  // While the heavy national PC winners query (543 PCs) is in flight the
  // tile layout (a small JSON) has usually already loaded, so the
  // Equal-seats arm's buildTileRows would paint an all-grey "pending" grid
  // until winners arrive. Gate that arm on this flag so it shows the same
  // "Loading equal-seats layout..." placeholder as the still-loading layout
  // instead of flashing grey.
  const equal_seats_loading = $derived(result.status === "loading");

  // ---- Sibling parliament events (prev/next nav + turnout delta) ------
  // One read of the event_summary mart powers the year-chip rail at the
  // top of the page AND the turnout gain/loss pill in the KPI strip. The
  // national-scope rows (scope='national', state_code=null) carry one row
  // per Parliament event with its event-scope turnout_pct + polled_on.
  let national_events = $state<EventSummaryRow[]>([]);
  $effect(() => {
    loadEventSummary()
      .then((rows) => {
        national_events = rows
          .filter(
            (r) =>
              r.scope === "national" &&
              r.kind === "parliament" &&
              r.state_code == null,
          )
          .sort((a, b) => a.polled_on.localeCompare(b.polled_on));
      })
      .catch(() => (national_events = []));
  });

  function eventYearLabel(event_id: string): string {
    const m = /(\d{4})/.exec(event_id);
    return m ? m[1] : event_id;
  }

  // Prev/next year-chip rail rows (ascending, current highlighted).
  interface SiblingChip {
    event_id: string;
    year_label: string;
    href: string;
    is_current: boolean;
  }
  const sibling_chips = $derived<SiblingChip[]>(
    national_events.map((r) => ({
      event_id: r.event_id,
      year_label: eventYearLabel(r.event_id),
      href: link.nationalElection(r.event_id),
      is_current: r.event_id === event,
    })),
  );

  // Turnout gain/loss vs the immediately-prior Parliament election.
  interface TurnoutDelta {
    turnout_pp: number | null;
    prev_event_label: string | null;
  }
  const turnout_delta = $derived.by<TurnoutDelta | null>(() => {
    const idx = national_events.findIndex((r) => r.event_id === event);
    if (idx <= 0) return null;
    const cur = national_events[idx];
    const prev = national_events[idx - 1];
    if (cur.turnout_pct == null || prev.turnout_pct == null) return null;
    return {
      turnout_pp: cur.turnout_pct - prev.turnout_pct,
      prev_event_label: `Parliament ${eventYearLabel(prev.event_id)}`,
    };
  });

  // ---- Previous-event winners for the seat-flow Sankey (#13) ----------
  // Load the immediately-prior Parliament event's per-PC winners so the
  // cross-event seat-flow diagram (holds / flips) renders on the national
  // surface too, not just per-state. Joined on entity_id inside the
  // shared StateEventCrossEventSankey component.
  let prev_winners_state = $state<PrevWinnersState>({ status: "loading" });
  const prev_event_label = $derived.by<string | null>(() => {
    const idx = national_events.findIndex((r) => r.event_id === event);
    if (idx <= 0) return null;
    return `Parliament ${eventYearLabel(national_events[idx - 1].event_id)}`;
  });
  $effect(() => {
    const ev = event;
    const evts = national_events;
    if (evts.length === 0) {
      prev_winners_state = { status: "loading" };
      return;
    }
    const idx = evts.findIndex((r) => r.event_id === ev);
    if (idx < 0) {
      prev_winners_state = { status: "loading" };
      return;
    }
    if (idx === 0) {
      prev_winners_state = { status: "no_prior" };
      return;
    }
    const prevId = evts[idx - 1].event_id;
    prev_winners_state = { status: "loading" };
    loadElectionResults({ event: prevId })
      .then((r) => {
        if (ev !== event) return;
        if (r.status === "ok" || r.status === "partial") {
          prev_winners_state = { status: "ok", rows: r.data };
        } else {
          prev_winners_state = {
            status: "failed",
            reason: r.status === "failed" ? r.reason : "no data",
          };
        }
      })
      .catch((e) => {
        if (ev === event)
          prev_winners_state = { status: "failed", reason: String(e) };
      });
  });

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

  // ---- Palette (party_id derivation only; PartyBar + the map renderers
  // resolve the 3-tier palette internally given each row's
  // brand_colour_hex + party_id).
  function partyIdFor(w: {
    party_id: string | null;
    party_short: string | null;
  }): string {
    if (w.party_id) return w.party_id;
    const slug = (w.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  }

  // ---- Top-parties bar (top 10 nationally by seats) ------------------
  // TODO/20260612 Row F: top-parties uses the canonical PartyBar so the
  // click-to-mute pattern matches Psephlab + StateOverview. The local
  // `PartyTotal` shape from PR-W3c is replaced by the canonical
  // `PartyTotals` from lib/data.ts. Aggregation pre-bucket: total
  // seats per party AND total votes per party so vote_share_pct can
  // be derived against the event-total polled vote count once.
  const TOP_N = 10;

  const event_total_votes = $derived.by<number>(() => {
    let total = 0;
    for (const w of winners) {
      if (w.votes_polled != null) total += w.votes_polled;
    }
    return total;
  });

  interface AggBucket {
    pid: string;
    party_short: string;
    seats: number;
    votes: number;
    has_any_vote: boolean;
    party_eci_code: string | null;
    brand_colour_hex: string | null;
    brand_colour_confidence: "high" | "medium" | "low" | null;
    symbol_asset_path: string | null;
  }
  const top_parties = $derived.by<PartyTotals[]>(() => {
    const by = new Map<string, AggBucket>();
    for (const w of winners) {
      const pid = partyIdFor(w);
      let bucket = by.get(pid);
      if (!bucket) {
        bucket = {
          pid,
          party_short: w.party_short ?? "UNK",
          seats: 0,
          votes: 0,
          has_any_vote: false,
          party_eci_code: w.party_eci_code,
          brand_colour_hex: w.brand_colour_hex,
          brand_colour_confidence: w.brand_colour_confidence,
          symbol_asset_path: w.symbol_asset_path ?? null,
        };
        by.set(pid, bucket);
      }
      bucket.seats += 1;
      if (bucket.symbol_asset_path == null && w.symbol_asset_path)
        bucket.symbol_asset_path = w.symbol_asset_path;
      if (w.votes_polled != null && w.vote_share_pct != null) {
        bucket.votes += (w.votes_polled * w.vote_share_pct) / 100;
        bucket.has_any_vote = true;
      }
    }
    const sorted = [...by.values()].sort((a, b) => b.seats - a.seats);
    return sorted.map<PartyTotals>((b) => ({
      party_eci_code: b.party_eci_code,
      party_short: b.party_short,
      party_full: null,
      seats_contested: null,
      seats_won: b.seats,
      votes: Math.round(b.votes),
      vote_share_pct:
        b.has_any_vote && event_total_votes > 0
          ? (b.votes / event_total_votes) * 100
          : 0,
      party_id: b.pid,
      brand_colour_hex: b.brand_colour_hex,
      brand_colour_confidence: b.brand_colour_confidence,
      // Election symbol glyph (lotus / hand / ...). Threaded so the
      // PartyBar pills standardise on the same symbol affordance the
      // per-state surface already shows.
      symbol_asset_path: b.symbol_asset_path,
      // NationalElection does not load alliance lookup today (alliance
      // backfill is a separate plan-doc per user verdict 2026-06-12);
      // PartyBar renders the tag only when populated, so leaving it
      // null keeps the bar visually clean.
      alliance_short: null,
    }));
  });

  // Top-N slice for the PartyBar (the bar would be unreadable with all
  // ~40 parties); the seat-arc below consumes the FULL list so all 542
  // seats are placed.
  const top_parties_bar = $derived<PartyTotals[]>(top_parties.slice(0, TOP_N));

  // Seat-arc input: every party with >=1 seat, in the psephlab PartyResult
  // shape ParliamentArc consumes. `party_eci_code` falls back to the short
  // name so the arc's mute key matches the PartyBar key space
  // (`party_eci_code ?? party_short`) - muting one surface recedes both.
  const arc_parties = $derived<PartyResult[]>(
    top_parties.map((p) => ({
      party_eci_code: p.party_eci_code ?? p.party_short,
      party_short: p.party_short,
      seats_won: p.seats_won,
      votes: p.votes,
      vote_share_pct: p.vote_share_pct,
      party_id: p.party_id ?? `parties.IN.${p.party_short.toUpperCase()}`,
      brand_colour_hex: p.brand_colour_hex,
      brand_colour_confidence: p.brand_colour_confidence,
      election_symbol_asset_path: p.symbol_asset_path,
    })),
  );

  // National alliance lookup (party_id -> alliance label) for the seat-arc
  // grouping. `state_slug="IN"` scopes party_alliances.csv to the national
  // Parliament-event rows (same scope AllianceTotals uses below). Null until
  // loaded / when the event has no curated alliance rows; the arc then falls
  // back to seats-only ordering.
  let alliance_lookup = $state<AllianceLookup | null>(null);
  $effect(() => {
    const ev = event;
    alliance_lookup = null;
    loadAlliances(ev, "IN")
      .then((l) => {
        if (ev === event) alliance_lookup = l;
      })
      .catch(() => {
        if (ev === event) alliance_lookup = null;
      });
  });

  // ---- TODO/20260612 Row C: 3-way map toggle ---------------------------
  // states (default) | constituencies | hex. Lives in component state
  // only - NOT persisted to the URL (per the W3b doctrine + PR-W4c
  // scatter-pill precedent: filter state is ephemeral; refresh resets).
  type MapView = "states" | "constituencies" | "hex";
  let map_view = $state<MapView>("states");

  // Winner|Margin sub-toggle - applies to Constituencies + Equal-seats
  // arms only (the States arm is owned by IndiaPartyMap which loads
  // its own fills). Same shim pattern StateElection uses for AC.
  type ColorMode = "winner" | "margin";
  let color_mode = $state<ColorMode>("winner");

  // ---- TODO/20260612 Row F: PartyBar click-to-mute -------------------
  // hidden_parties keys are `party_eci_code ?? party_short` - same
  // convention used by PartyBar / Psephlab / StateOverview. Hiding is
  // purely visual; per spec we DON'T recompute seats or vote share.
  let hidden_parties = $state<Set<string>>(new Set());

  function toggleHidden(key: string): void {
    const next = new Set(hidden_parties);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    hidden_parties = next;
  }

  // Reset mute set on event change so muting "BJP" on general-2024
  // does not silently carry to general-2019 when the citizen navigates
  // between events.
  $effect(() => {
    void event;
    hidden_parties = new Set();
  });

  // Bridge PartyBar's key space (party_eci_code ?? party_short) to the
  // canonical party_id space the map renderers use. Built once per
  // winners change. `partyIdFor` upgrades the loader's `party_id:
  // string | null` to the strict `string` shape the helper expects.
  const key_to_pid = $derived(
    buildPartyKeyToPid(
      winners.map((w) => ({
        party_eci_code: w.party_eci_code,
        party_short: w.party_short,
        party_id: partyIdFor(w),
      })),
    ),
  );
  const hidden_pids = $derived(hiddenPidSet(hidden_parties, key_to_pid));

  // ---- TODO/20260612 Rows A + C: PcWinnerRow projection --------------
  // Build the unique_id-keyed PC winners array that drives IndiaPcMapD3
  // + the national TileCartogram. unique_id matches the PC geometry's
  // join shape, which depends on the event's delim_year:
  //   - LS 2024 -> numeric `<state_code>_<eci_no>` (joins INDIA_PC's
  //     `unique_id`, e.g. "S07_5").
  //   - LS 2019 / 2014 / 2009 -> name-slug `<state_code>_<pc_name_slug>`
  //     (joins INDIA_PC_BY_NAME's `pc_slug_uid`, e.g. "S07_karnal").
  // After the 2026-06-16 map-geometry rip (Row 3) there is ONE PC
  // geometry file (delim=2024); pre-2024 events join it by name-slug
  // because canonical electoral.csv carries unreliable eci_no values for
  // the old delimitation. Unmatched seats render grey (safe-by-
  // construction). See INDIA_PC_BY_NAME jsdoc for the alignment
  // evidence.
  //
  // The TileCartogram tile-layout's unit_id is INDEPENDENT of this
  // boundary-join shape (it uses `IN-PC-<delim_year>-<state>-<eci_no>`
  // which the on-disk election_tile_layouts.json was authored against),
  // so the tile arm still consumes pc_eci_no verbatim from PcWinnerRow.
  // `pcDelimYearForLsEvent` is a pure helper (india-pc-map-helpers.ts) so
  // the era-gating rule is unit-tested independently of this component.
  const pc_delim_year = $derived(pcDelimYearForLsEvent(event));
  const pc_boundary = $derived(
    pc_delim_year === 2008 ? INDIA_PC_BY_NAME : INDIA_PC,
  );

  // Coverage of the PC choropleth's join, lifted from IndiaPcMapD3 so the
  // honesty caption renders below the national party legend (not inside the
  // map card). Null until the Constituencies arm mounts + emits.
  let pc_coverage = $state<MapCoverageEmit | null>(null);

  // Pre-2009 LS events (1962 / 1989 / 1991 / ... / 2004) have NO PC-level
  // boundary layer (pcDelimYearForLsEvent -> null), so pc_winners is empty
  // and the Constituencies + Equal-seats arms would draw an all-grey map
  // keyed to 2024 boundaries that never existed for that election. This
  // flag gates BOTH per-PC toggles; the States arm (IndiaPartyMap) covers
  // every year by greying only the states with no rows (e.g. Assam, which
  // genuinely did not poll in 1989 - that nuance belongs in a sourced
  // coverage note, not an empty grey national choropleth).
  const has_pc_choropleth = $derived(pc_delim_year != null);

  // Normalise the map arm when the citizen carries a per-PC selection from
  // a modern event onto a pre-2009 one. The toggles are hidden there, so a
  // stale carry is the only route onto an empty arm. Converges: once
  // map_view is "states" the guard no longer fires.
  $effect(() => {
    if (!has_pc_choropleth && map_view !== "states") {
      map_view = "states";
    }
  });

  const pc_winners = $derived.by<PcWinnerRow[]>(() => {
    if (pc_delim_year == null) return [];
    const useNameSlug = pc_delim_year === 2008;
    const out: PcWinnerRow[] = [];
    for (const w of winners) {
      if (w.margin_pct == null) continue;
      // The shim's brand_colour_hex carries the rendered fill (winner
      // colour OR margin-grey depending on color_mode). The PC map
      // re-resolves the actual party_id -> hex inside via the 3-tier
      // resolver; we override that downstream via fillsOverride when
      // color_mode === "margin" (no different from the AC shim pattern
      // in StateElection).
      const tail = useNameSlug ? slugify(w.entity_name) : String(w.eci_no);
      out.push({
        unique_id: aliasPcSlugUid(`${w.state_code}_${tail}`),
        state_code: w.state_code,
        pc_eci_no: w.eci_no,
        pc_name: w.entity_name,
        party_id: partyIdFor(w),
        party_short: w.party_short ?? "UNK",
        party_eci_code: w.party_eci_code,
        brand_colour_hex: w.brand_colour_hex,
        brand_colour_confidence: w.brand_colour_confidence,
        margin_pct: w.margin_pct,
        winner_candidate_name: w.winner_candidate_name,
        symbol_asset_path: w.symbol_asset_path,
      });
    }
    return out;
  });

  // Seat-ranked, collision-de-conflicted base colour per winning party for the
  // Margin-mode shading. Identity colours (anchor/brand) are fixed; only
  // decorative minor parties are nudged when two hues clash (lower-seat yields).
  const pc_base = $derived.by<Map<string, string>>(() =>
    resolveWinnerBaseColours(pc_winners),
  );

  // PC map per-uid overrides: mute by party_id, and the Margin-mode shading
  // (each seat = its winning party's hue, paled toward a knife-edge). Both win
  // via the IndiaPcMapD3 `fillsOverride` / `opacitiesOverride` precedence path.
  const pc_fills_override = $derived.by<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    for (const w of pc_winners) {
      if (hidden_pids.has(w.party_id)) {
        out[w.unique_id] = "#cbd5e1"; // slate-300 recede
      } else if (color_mode === "margin") {
        out[w.unique_id] = marginShade(
          pc_base.get(w.party_id) ?? "#94a3b8",
          w.margin_pct,
        );
      }
    }
    return out;
  });
  const pc_opacities_override = $derived.by<Record<string, number>>(() => {
    const out: Record<string, number> = {};
    for (const w of pc_winners) {
      if (hidden_pids.has(w.party_id)) {
        out[w.unique_id] = 0.18; // recede opacity (matches RECEDE_OPACITY)
      } else if (color_mode === "margin") {
        // Magnitude is carried by the fill's lightness, so hold opacity flat
        // and high (no second ramp that would fade close races into the page).
        out[w.unique_id] = MARGIN_FILL_OPACITY;
      }
    }
    return out;
  });

  // ---- Hex / Equal-seats arm: national PC tile layout ----------------
  const TILE_DELIM_YEAR = 2008; // national PC tile layout vintage on disk.

  let has_equal_seats = $state<boolean | null>(null);
  $effect(() => {
    fetchElectionTileScopes()
      .then((doc) => {
        has_equal_seats = hasLayoutForScope(doc, {
          layout_kind: "pc",
          scope: "national",
          delim_year: TILE_DELIM_YEAR,
        });
      })
      .catch(() => (has_equal_seats = false));
  });

  let tile_layout = $state<TileLayoutRow[] | null>(null);
  let tile_layout_error = $state(false);
  let tile_layout_requested = false;
  $effect(() => {
    if (map_view !== "hex" || tile_layout_requested || has_equal_seats === false)
      return;
    tile_layout_requested = true;
    fetchElectionTileLayouts()
      .then((doc) => {
        tile_layout = selectLayout(doc, {
          layout_kind: "pc",
          scope: "national",
          delim_year: TILE_DELIM_YEAR,
        });
      })
      .catch(() => (tile_layout_error = true));
  });

  const hex_winners = $derived<TileWinnerInput[]>(
    pc_winners.map((w) => ({
      // Tile layout's unit_id pattern: `IN-PC-<delim_year>-<state>-<eci>`.
      unit_id: `IN-PC-${TILE_DELIM_YEAR}-${w.state_code}-${w.pc_eci_no}`,
      party_key: w.party_eci_code,
      party_short: w.party_short,
      margin_pct: w.margin_pct,
      party_id: w.party_id,
      brand_colour_hex: w.brand_colour_hex,
      brand_colour_confidence: w.brand_colour_confidence,
    })),
  );

  const raw_tile_rows = $derived<TileRow[]>(
    tile_layout == null ? [] : buildTileRows(tile_layout, hex_winners),
  );

  // Re-skin tiles for the Margin-mode party-hue shading + party-mute recede.
  // The fill is the winner's party hue paled by margin (marginShade); opacity
  // stays flat + high in Margin mode so close races don't fade into the page.
  const tile_rows = $derived<TileRow[]>(
    raw_tile_rows.map((t) => {
      if (t.pending) return t;
      // The tile's unit_id final two segments are `<state>-<eci>`.
      const parts = t.unit_id.split("-");
      const eci_no = Number(parts[parts.length - 1]);
      const state_code = parts[parts.length - 2];
      const uid = `${state_code}_${eci_no}`;
      const muted = t.winner_party_id != null && hidden_pids.has(t.winner_party_id);
      if (muted) {
        return { ...t, fill: "#cbd5e1", opacity: 0.18 };
      }
      if (color_mode === "margin") {
        const base =
          (t.winner_party_id != null ? pc_base.get(t.winner_party_id) : null) ??
          t.fill;
        return {
          ...t,
          fill: marginShade(base, t.margin_pct ?? null),
          opacity: MARGIN_FILL_OPACITY,
        };
      }
      // back-compat: also honour pc_fills_override if it was computed
      // for any reason (defensive belt-and-braces against future
      // override sources).
      const override = pc_fills_override[uid];
      if (override != null) return { ...t, fill: override };
      return t;
    }),
  );

  function onTileSelect(unit_id: string): void {
    // unit_id: "IN-PC-2008-S07-8" -> state=S07, eci=8.
    const parts = unit_id.split("-");
    const eci_no = Number(parts[parts.length - 1]);
    const state_code = parts[parts.length - 2];
    if (!Number.isFinite(eci_no) || !state_code) return;
    navigate(link.stateElection(state_code, event));
  }

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
        // TODO/20260612 Row B: margin_votes drives the radius encoding.
        margin_votes: w.margin_votes,
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

  // ====================================================================
  // Row 7: national constituency list (State -> PC -> AC -> District).
  // TODO/20260622-election-constituency-grouping-plan.md.
  //
  // OUTER accordion: the ~36 states/UTs as the top-level groups, collapsed
  // at first paint (ZERO PC/AC DOM mounted - constraint #1). Expanding a
  // state LAZY-MOUNTS the SAME PC-mode StateEventConstituencyList for that
  // state ({#if open} = mount-on-expand, unmount-on-collapse - constraint
  // #2). ONE national search + Reserved filter (below) owns the controls;
  // each inner list runs with hide_controls so there is no per-state search
  // bar (constraint #3 + #4). ALL data-shaping reuses the Row 5 pure helpers
  // buildPcGrouping/loadAcEntities/buildNationalStateGroups (constraint #5);
  // this is render-only state selection.
  // ====================================================================

  // Cached AC entity list (name + parent PC + district + reservation + eci);
  // loaded once when the national PC winners arrive.
  let ac_entities_nat = $state<AcEntity[] | null>(null);
  let ac_entities_nat_error = $state<string | null>(null);
  $effect(() => {
    if (winners.length === 0) return;
    if (ac_entities_nat !== null || ac_entities_nat_error !== null) return;
    loadAcEntities()
      .then((e) => (ac_entities_nat = e))
      .catch((e) => (ac_entities_nat_error = String(e)));
  });

  // State display names (ECI code -> "Tamil Nadu"); loaded once, cached.
  let state_name_by_code = $state<Map<string, string>>(new Map());
  $effect(() => {
    loadStates()
      .then((rows) => {
        const m = new Map<string, string>();
        for (const r of rows) m.set(r.eci_code, r.display_name);
        state_name_by_code = m;
      })
      .catch(() => {});
  });
  function slugToName(slug: string): string {
    return slug
      .split("-")
      .map((p) => (p.length === 0 ? p : p[0].toUpperCase() + p.slice(1)))
      .join(" ")
      .replace(/\bAnd\b/g, "and");
  }
  function stateNameFor(code: string, slug: string): string {
    return state_name_by_code.get(code) ?? slugToName(slug);
  }

  // Live delimitation for the AC->PC join (uniform across the event); mirrors
  // the state general page (StateElection Row 5).
  const nat_delim_year = $derived(winners[0]?.delim_year ?? null);

  // Winner row by PC entity_id (powers the per-state group headers + the outer
  // glance strip).
  const winner_by_id = $derived.by<Map<string, ElectionResultRow>>(() => {
    const m = new Map<string, ElectionResultRow>();
    for (const w of winners) m.set(w.entity_id, w);
    return m;
  });

  // Per-state PC -> AC grouping (REUSES buildPcGrouping per state). Empty until
  // the AC entities resolve.
  const nat_state_groups = $derived.by(() => {
    const ents = ac_entities_nat;
    if (!ents || winners.length === 0) return [];
    return buildNationalStateGroups(
      winners.map((w) => ({
        entity_id: w.entity_id,
        entity_name: w.entity_name,
        state_code: w.state_code,
        state_slug: w.state_slug,
      })),
      ents,
      nat_delim_year,
    );
  });

  // National search + Reserved filter (the ONE pair the outer accordion owns).
  let nat_search_q = $state("");
  let nat_reserved = $state<ReservationKind | "All">("All");
  const NAT_RESERVED_OPTIONS: ReadonlyArray<{
    value: ReservationKind | "All";
    label: string;
  }> = [
    { value: "All", label: "All" },
    { value: "GEN", label: "GEN" },
    { value: "SC", label: "SC" },
    { value: "ST", label: "ST" },
  ];

  // Manually-expanded states (in addition to the search auto-expanded ones).
  let nat_expanded = $state<Set<string>>(new Set());
  function toggleNatState(code: string): void {
    const next = new Set(nat_expanded);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    nat_expanded = next;
  }

  // Reset the search + fold when the citizen navigates to another event.
  $effect(() => {
    void event;
    nat_search_q = "";
    nat_reserved = "All";
    nat_expanded = new Set();
  });

  // Branch inputs (resolve state name + per-PC reservation) for the filter.
  const nat_branch_inputs = $derived.by(() =>
    nat_state_groups.map((g) => ({
      state_code: g.state_code,
      state_slug: g.state_slug,
      state_name: stateNameFor(g.state_code, g.state_slug),
      pcs: g.pcs.map<NationalFilterPc>((p) => ({
        entity_id: p.entity_id,
        name: p.name,
        reservation: winner_by_id.get(p.entity_id)?.reservation ?? null,
      })),
      leaves: g.leaves,
    })),
  );

  // Visible branches after the ONE national search + Reserved filter.
  const nat_branches = $derived<NationalBranchView[]>(
    filterNationalBranches(nat_branch_inputs, nat_search_q, nat_reserved),
  );

  // Global count line ("N seats across M states").
  const nat_count_line = $derived.by<string>(() => {
    const states = nat_branches.length;
    let pcs = 0;
    for (const b of nat_branches) pcs += b.pcs.length;
    const s = `${states} ${states === 1 ? "state" : "states"}`;
    const p = `${pcs} ${pcs === 1 ? "seat" : "seats"}`;
    return `${p} across ${s}`;
  });

  function isNatExpanded(code: string, auto: boolean): boolean {
    return auto || nat_expanded.has(code);
  }

  // Header-chip colour for a PC winner: the resolved per-party base colour
  // (shared with the maps), falling back to the row's brand hex.
  function natColorForPid(pid: string, w: ElectionResultRow): string {
    return pc_base.get(pid) ?? w.brand_colour_hex ?? "#94a3b8";
  }

  // Per-branch group headers (PC name -> Lok Sabha MP result). Built from the
  // winner row; child_count reflects the (possibly filtered) visible leaves.
  function natHeadersFor(
    branch: NationalBranchView,
  ): Record<string, GroupHeaderResult> {
    const childCount = new Map<string, number>();
    for (const l of branch.leaves) {
      if (l.pc_group != null) {
        childCount.set(l.pc_group, (childCount.get(l.pc_group) ?? 0) + 1);
      }
    }
    const out: Record<string, GroupHeaderResult> = {};
    for (const pc of branch.pcs) {
      const w = winner_by_id.get(pc.entity_id);
      if (!w) continue;
      const pid = partyIdFor(w);
      out[pc.name] = {
        chip: w.party_short ?? "UNK",
        color: natColorForPid(pid, w),
        share: w.vote_share_pct,
        margin: w.margin_pct,
        child_count: childCount.get(pc.name) ?? 0,
        reservation: w.reservation,
      };
    }
    return out;
  }

  // Per-branch PC-mode seat rows (child AC leaves). The MP result rides on the
  // group header, NOT the leaf (mirrors StateElection Row 5); the leaf links to
  // its own AC drill-down + shows its district label.
  interface NatSeatRow {
    entity_id: string;
    entity_name: string;
    district: string | null;
    eci_no: number | null;
    reservation: string | null;
    pc_group: string | null;
    winner_party_short: string;
    winner_party_id: string;
    winner_color: string;
    winner_share_pct: number | null;
    margin_pct: number | null;
    href: string;
  }
  function natSeatRowsFor(branch: NationalBranchView): NatSeatRow[] {
    const rows = branch.leaves.map<NatSeatRow>((leaf) => ({
      entity_id: leaf.entity_id,
      entity_name: leaf.name,
      district: leaf.district_name,
      eci_no: leaf.eci_no,
      reservation: leaf.reservation,
      pc_group: leaf.pc_group,
      winner_party_short: "",
      winner_party_id: "",
      winner_color: "#cbd5e1",
      winner_share_pct: null,
      margin_pct: null,
      href: link.ac(branch.state_slug, leaf.name),
    }));
    rows.sort((a, b) => {
      const ea = a.eci_no ?? Number.POSITIVE_INFINITY;
      const eb = b.eci_no ?? Number.POSITIVE_INFINITY;
      if (ea !== eb) return ea - eb;
      return a.entity_name.localeCompare(b.entity_name, "en", {
        sensitivity: "base",
      });
    });
    return rows;
  }

  // Per-branch outer-row glance strip (which party won how many of the state's
  // PCs) - reuses the Row 2 proportional-strip token.
  function natStripFor(branch: NationalBranchView): PartyStrip {
    return buildPartyStrip(
      branch.pcs.map((pc) => {
        const w = winner_by_id.get(pc.entity_id);
        const pid = w ? partyIdFor(w) : "";
        return {
          winner_party_short: w?.party_short ?? "UNK",
          winner_party_id: pid,
          winner_color: w ? natColorForPid(pid, w) : "#cbd5e1",
        };
      }),
    );
  }
</script>
<PageContainer width="wide">
  <header class="space-y-2">
    <h1 class="text-2xl font-semibold text-slate-900">
      India &middot; {event_pretty}
    </h1>
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <span
        class="inline-block rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
        data-testid="national-event-chip"
      >national</span>
    </div>
  </header>

  <!-- Prev/next election navigation: a year-chip rail across every
       Parliament election on record, current highlighted. Mirrors the
       per-state SiblingEventsRail so the citizen can step between
       elections from the top of the page. -->
  {#if sibling_chips.length > 1}
    <nav
      class="-mx-1 flex flex-wrap items-center gap-1.5 overflow-x-auto px-1"
      aria-label="Parliament elections"
      data-testid="national-event-sibling-rail"
    >
      {#each sibling_chips as chip (chip.event_id)}
        {#if chip.is_current}
          <span
            class="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white"
            aria-current="page"
          >{chip.year_label}</span>
        {:else}
          <a
            href={chip.href}
            class="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:border-slate-300 hover:text-slate-900"
            onclick={(e) => {
              e.preventDefault();
              navigate(chip.href);
            }}
          >{chip.year_label}</a>
        {/if}
      {/each}
    </nav>
  {/if}

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
    <!-- Glyph chips mirror the per-state StateEventHero treatment so the
         national + state event surfaces read as one family (icon chip +
         label row, value below). The turnout card carries an up/down
         gain-loss pill vs the previous Parliament election when known. -->
    <section
      class="grid grid-cols-2 gap-3 sm:grid-cols-4"
      data-testid="national-event-kpis"
    >
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
          <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
            <TopicIcon name="landmark" cls="h-4 w-4" />
          </span>
          Total seats
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtInt(kpis.total_seats)}
        </div>
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
          <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-700">
            <TopicIcon name="users" cls="h-4 w-4" />
          </span>
          Total electors
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtCompact(kpis.total_electors)}
        </div>
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
          <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
            <TopicIcon name="vote" cls="h-4 w-4" />
          </span>
          Total polled
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtCompact(kpis.total_polled)}
        </div>
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
          <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
            <TopicIcon name="activity" cls="h-4 w-4" />
          </span>
          Turnout
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtPct(kpis.turnout_pct)}
        </div>
        {#if turnout_delta != null && turnout_delta.turnout_pp != null}
          {@const pp = turnout_delta.turnout_pp}
          {@const positive = pp >= 0}
          <div
            class="mt-1.5 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums {positive
              ? 'bg-emerald-50 text-emerald-700'
              : 'bg-rose-50 text-rose-700'}"
            data-testid="national-event-turnout-delta"
          >
            <TopicIcon name={positive ? "trending-up" : "trending-down"} cls="h-3 w-3 shrink-0" />
            <span>{`${pp >= 0 ? "+" : ""}${pp.toFixed(1)} pp`} vs {turnout_delta.prev_event_label}</span>
          </div>
        {/if}
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

    <!-- TODO/20260612 Rows C + F: 3-way map toggle + Winner|Margin sub
         + party-mute integration. ---- States: existing IndiaPartyMap
         (default; one polygon per state). Constituencies: IndiaPcMapD3
         (543 PC polygons). Equal seats: TileCartogram with the
         national PC layout (545 hex tiles). The Winner|Margin sub-
         toggle applies to the Constituencies + Equal-seats arms only;
         the States arm is driven by IndiaPartyMap which owns its own
         per-state fills and does not accept overrides.

         Party-mute (PartyBar click) applies via fillsOverride +
         opacitiesOverride on the per-PC arms; the States arm carries
         the mute visually on the PartyBar swatch only. -->
    <section class="space-y-2" data-testid="national-event-map">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-sm font-medium text-slate-700">
          {#if map_view === "states"}
            Winning party by state
          {:else if map_view === "constituencies"}
            Winning party by constituency
          {:else}
            Each seat = one hexagon
          {/if}
        </h2>
        <div class="flex flex-wrap items-center gap-2">
          {#if (map_view === "constituencies" || map_view === "hex")}
            <div
              class="inline-flex rounded border border-slate-200 bg-white p-0.5 text-xs"
              data-testid="national-event-map-mode"
            >
              <button
                type="button"
                class={color_mode === "winner"
                  ? "rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
                  : "px-2 py-0.5 text-slate-500"}
                data-testid="national-event-map-mode-winner"
                onclick={() => (color_mode = "winner")}
              >Winner</button>
              <button
                type="button"
                class={color_mode === "margin"
                  ? "rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
                  : "px-2 py-0.5 text-slate-500"}
                data-testid="national-event-map-mode-margin"
                onclick={() => (color_mode = "margin")}
              >Margin</button>
            </div>
          {/if}
          <div
            class="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-sm"
            data-testid="national-event-map-view"
          >
            <button
              type="button"
              class="rounded-md px-3 py-1 transition-colors {map_view === 'states'
                ? 'bg-white font-medium text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'}"
              data-view="states"
              onclick={() => (map_view = "states")}
            >States</button>
            {#if has_pc_choropleth}
              <button
                type="button"
                class="rounded-md px-3 py-1 transition-colors {map_view === 'constituencies'
                  ? 'bg-white font-medium text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'}"
                data-view="constituencies"
                onclick={() => (map_view = "constituencies")}
              >Constituencies</button>
            {/if}
            {#if has_equal_seats === true && has_pc_choropleth}
              <button
                type="button"
                class="rounded-md px-3 py-1 transition-colors {map_view === 'hex'
                  ? 'bg-white font-medium text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'}"
                data-view="hex"
                onclick={() => (map_view = "hex")}
              >Equal seats</button>
            {/if}
          </div>
        </div>
      </div>

      {#if map_view === "states"}
        <p class="text-xs text-slate-500">
          Each state is coloured by the party that won the most seats in
          that state. Click a state to drill into its per-state results.
        </p>
        <div data-testid="national-event-map-states">
          <IndiaPartyMap
            event={event}
            onSelect={(code) => navigate(link.stateElection(code, event))}
          />
        </div>
      {:else if map_view === "constituencies"}
        {#if color_mode === "winner"}
          <p class="text-xs text-slate-500">
            Each constituency is filled with the winning party's colour.
          </p>
        {:else}
          <MarginLegend />
        {/if}
        <div data-testid="national-event-map-pc">
          <IndiaPcMapD3
            rows={pc_winners}
            event={event}
            fillsOverride={pc_fills_override}
            opacitiesOverride={pc_opacities_override}
            boundary={pc_boundary}
            oncoverage={(e) => (pc_coverage = e)}
          />
        </div>
      {:else}
        {#if color_mode === "winner"}
          <p class="text-xs text-slate-500">
            Each hexagon is one seat in Parliament, coloured by the winning party.
          </p>
        {:else}
          <MarginLegend />
        {/if}
        <div data-testid="national-event-map-hex">
          {#if tile_layout_error}
            <div
              class="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
            >
              Equal-seats layout couldn't load.
            </div>
          {:else if tile_layout == null || equal_seats_loading}
            <p class="p-4 text-sm text-slate-500">Loading equal-seats layout...</p>
          {:else}
            <TileCartogram
              tiles={tile_rows}
              height="520px"
              onSelect={onTileSelect}
            />
          {/if}
        </div>
      {/if}
    </section>

    <!-- Top-parties bar (top 10 nationally by seats) ------------------- -->
    <section class="space-y-2" data-testid="national-event-top-parties">
      <div class="flex items-baseline justify-between gap-2 flex-wrap">
        <h2 class="text-sm font-medium text-slate-700">
          Top parties by seats
        </h2>
        {#if hidden_parties.size > 0}
          <button
            type="button"
            class="text-xs text-sky-700 hover:underline"
            data-testid="national-event-top-parties-reset"
            onclick={() => (hidden_parties = new Set())}
          >Show all ({hidden_parties.size} muted)</button>
        {/if}
      </div>
      {#if top_parties.length === 0}
        <p class="text-xs text-slate-500">
          No party totals available for this event yet.
        </p>
      {:else}
        <PartyBar
          parties={top_parties_bar}
          total_seats={kpis.total_seats}
          {hidden_parties}
          onToggleHidden={toggleHidden}
        />
        <p class="text-[11px] text-slate-500">
          Click a party row to mute it; muted parties recede on the
          constituency + hex map arms and the seat semicircle. Vote totals
          don't recompute.
        </p>
      {/if}
    </section>

    <!-- Coverage caption: below the national party legend (ratified
         placement). Only on the Constituencies arm; auto-hides on the
         current-vintage map via MapCoverageNote's own onOldGeometry gate. -->
    {#if map_view === "constituencies" && pc_coverage}
      <MapCoverageNote
        coverage={pc_coverage.coverage}
        geometryYear={pc_coverage.geometryYear}
        onOldGeometry={pc_coverage.onOldGeometry}
        unit="constituencies"
      />
    {/if}

    <!-- Seat semicircle (#10). One dot per Parliament seat, coloured by
         winning party, with a majority midline + symbol-ring legend.
         Shares the same `hidden_parties` set as the bar + maps, so muting
         a party recedes its seats here too. -->
    {#if arc_parties.length > 0 && kpis.total_seats > 0}
      <section class="space-y-2" data-testid="national-event-seat-arc">
        <h2 class="text-sm font-medium text-slate-700">Seats won</h2>
        <ParliamentArc
          parties={arc_parties}
          total_seats={kpis.total_seats}
          {hidden_parties}
          onToggleHidden={toggleHidden}
          alliance_of={(p) => alliance_lookup?.(p.party_id) ?? null}
        />
      </section>
    {/if}

    <!-- Alliance totals (Phase 1 of TODO/20260612-alliance-phase-1-
         structural-fix-plan.md). state_slug="IN" scopes the alliance
         lookup to national-event rows in party_alliances.csv; the 4
         already-curated national events (general-2024 today;
         2019/2014/2009 in Phase 1b) light up as a single panel with
         the alliance-first total + an optional per-party breakdown. -->
    <AllianceTotals
      event={event}
      state_slug="IN"
      winners={winners.map((w) => ({
        party_id: w.party_id,
        party_short: w.party_short,
        party_eci_code: w.party_eci_code,
      }))}
    />

    {#if EVENTS_WITH_SEIZURES.has(event)}
      <!-- Row D of TODO/20260614-three-ephemeral-ingests-plan.md:
           citizen-facing card for the MCC-period enforcement
           seizures press-note series. Gated on the event having
           a publisher-emitted CSV on disk; today only 2019. -->
      <ElectionSeizuresCard event_id={event} />
    {/if}

    <!-- Seat flow vs the previous Parliament election (#13). Always
         visible (the shared component shows the diagram by default).
         Holds / flips headline + bipartite Sankey, joined on entity_id. -->
    {#if winners.length > 0}
      <section class="space-y-2" data-testid="national-event-seat-flow">
        <h2 class="text-sm font-medium text-slate-700">Seat flow</h2>
        <StateEventCrossEventSankey
          current_winners={winners}
          prev_winners={prev_winners_state}
          prev_event_label={prev_event_label}
          current_event_label={event_pretty}
          body_pretty="Parliament"
          state_name="India"
        />
      </section>
    {/if}

    <!-- Scatter chart (PR-W4c MUST-FEATURE).
         TODO/20260612 Row A.5 + E: lock_body=true hides the Body chip
         since the national-event surface is single-body fixed by the
         route (parliament-only via the W2b loader's NATIONAL-PC
         dispatch). -->
    <section class="space-y-2" data-testid="national-event-scatter">
      <h2 class="text-sm font-medium text-slate-700">
        Turnout vs winning margin &middot; all constituencies
      </h2>
      <p class="text-xs text-slate-500" data-testid="national-event-scatter-note">
        Each circle is one constituency. Bigger circles mean a wider winning
        margin - the vote gap between the winner and the runner-up. Click a
        circle to open that seat.
      </p>
      <Scatter
        data={scatter_data}
        filters={scatter_filters}
        onFiltersChange={(next) => (scatter_filters = next)}
        onDotClick={onScatterDotClick}
        lock_body={true}
      />
    </section>

    <!-- Row 7 (TODO/20260622-election-constituency-grouping-plan.md):
         national constituency list. OUTER accordion = states/UTs (collapsed
         at first paint - ZERO PC/AC DOM mounted); expanding a state
         LAZY-MOUNTS the SAME PC-mode StateEventConstituencyList for that
         state (State -> PC -> AC -> District). ONE national search + Reserved
         filter owns the controls; each inner list runs with hide_controls so
         there is no per-state search bar. -->
    {#if winners.length > 0}
      <section
        class="space-y-2"
        data-testid="national-event-constituency-list"
      >
        <h2 class="text-sm font-semibold text-slate-800">
          Constituencies by state
        </h2>
        {#if ac_entities_nat_error}
          <p class="text-xs text-slate-500">
            Constituency details couldn't load.
          </p>
        {:else if ac_entities_nat == null || nat_state_groups.length === 0}
          <p
            class="text-xs text-slate-500"
            data-testid="national-event-constituency-loading"
          >Loading constituencies...</p>
        {:else}
          <!-- Sticky national controls: ONE search (magnifier glyph) + ONE
               Reserved filter across every state. -->
          <div
            class="sticky top-0 z-10 -mx-1 space-y-1.5 bg-white/95 px-1 py-1 backdrop-blur"
          >
            <label class="relative block">
              <span class="sr-only"
                >Search by state, constituency, or assembly segment</span
              >
              <span
                class="pointer-events-none absolute inset-y-0 left-2 flex items-center"
              >
                <TopicIcon
                  name="search"
                  cls="h-4 w-4 shrink-0 text-slate-400"
                />
              </span>
              <input
                type="search"
                placeholder="Search state / constituency..."
                class="w-full rounded border border-slate-300 py-1.5 pl-8 pr-3 text-sm placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                data-testid="national-event-constituency-search"
                bind:value={nat_search_q}
              />
            </label>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div
                class="flex items-center gap-1 text-xs"
                data-testid="national-event-constituency-reserved-filter"
              >
                <span class="text-slate-500">Reserved:</span>
                {#each NAT_RESERVED_OPTIONS as opt (opt.value)}
                  <button
                    type="button"
                    class={`rounded px-1.5 py-0.5 font-medium ${
                      nat_reserved === opt.value
                        ? "bg-slate-800 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                    data-testid="national-event-constituency-reserved-option"
                    data-value={opt.value}
                    aria-pressed={nat_reserved === opt.value}
                    onclick={() => (nat_reserved = opt.value)}
                  >{opt.label}</button>
                {/each}
              </div>
              <p
                class="text-xs tabular-nums text-slate-500"
                data-testid="national-event-constituency-count"
              >{nat_count_line}</p>
            </div>
          </div>

          {#if nat_branches.length === 0}
            <p class="text-xs text-slate-500">
              No constituencies match
              <code class="rounded bg-slate-100 px-1">{nat_search_q}</code>.
            </p>
          {:else}
            <ul class="divide-y border-y">
              {#each nat_branches as branch (branch.state_code)}
                {@const open = isNatExpanded(branch.state_code, branch.auto_expand)}
                {@const strip = natStripFor(branch)}
                <li data-testid="national-event-constituency-state-row">
                  <button
                    type="button"
                    class="flex w-full items-center justify-between gap-3 px-2 py-2 text-left text-sm hover:bg-slate-50"
                    data-testid="national-event-constituency-state-toggle"
                    aria-expanded={open}
                    onclick={() => toggleNatState(branch.state_code)}
                  >
                    <span class="flex min-w-0 items-center gap-2">
                      <TopicIcon
                        name={open ? "chevron-down" : "chevron-right"}
                        cls="h-4 w-4 shrink-0 text-slate-400"
                      />
                      <span class="truncate font-medium text-slate-800"
                        >{branch.state_name}</span
                      >
                      <span
                        class="shrink-0 text-xs tabular-nums text-slate-400"
                        >{branch.pcs.length}
                        {branch.pcs.length === 1 ? "seat" : "seats"}</span
                      >
                    </span>
                    {#if strip.segments.length > 0}
                      <span
                        class="flex min-w-0 max-w-[55%] items-center gap-2"
                      >
                        <span
                          class="hidden h-2.5 min-w-[60px] flex-1 overflow-hidden rounded-full sm:flex"
                          aria-hidden="true"
                        >
                          {#each strip.segments as seg (seg.party_id)}
                            <span
                              style={`width:${seg.pct}%;background:${seg.color}`}
                              title={`${seg.party_short} ${seg.count}`}
                            ></span>
                          {/each}
                        </span>
                        <span
                          class="shrink-0 text-xs font-medium tabular-nums text-slate-600"
                          >{strip.leader_label}</span
                        >
                      </span>
                    {/if}
                  </button>
                  {#if open}
                    <div
                      class="px-2 pb-3"
                      data-testid="national-event-constituency-state-panel"
                    >
                      <StateEventConstituencyList
                        loading={false}
                        seat_rows={natSeatRowsFor(branch)}
                        group_headers={natHeadersFor(branch)}
                        {fmtInt}
                        {fmtPct}
                        hide_controls={true}
                      />
                    </div>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        {/if}
      </section>
    {/if}
  {/if}
</PageContainer>
