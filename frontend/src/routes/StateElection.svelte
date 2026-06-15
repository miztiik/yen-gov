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
  //                                no URL-encoded scenario blob).
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
  // Page chrome: no URL-encoded scenario blob handling on this surface.
  // Inline scenarios are ephemeral by W3b doctrine - refresh resets them.

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
  import { pickEventPanelState } from "../lib/view-models/election-result-panel";
  import {
    getPartyColor,
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../lib/colors/resolver";
  import { INDIA_PC, INDIA_PC_2008 } from "../lib/boundaries/sources";
  import type { PcWinnerRow } from "../lib/charts/StatePcMapD3.svelte";
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
  import { STATE_AC } from "../lib/boundaries/sources";
  import type { AcWinner } from "../lib/view-models/state-overview";
  import {
    buildPartyKeyToPid,
    hiddenPidSet,
  } from "../lib/charts/india-pc-map-helpers";
  import AllianceTotals from "../lib/elections/AllianceTotals.svelte";
  import StateEventScatter from "../lib/elections/StateEventScatter.svelte";
  import StateEventConstituencyList from "../lib/elections/StateEventConstituencyList.svelte";
  import StateEventHero from "../lib/elections/StateEventHero.svelte";
  import StateEventMap from "../lib/elections/StateEventMap.svelte";
  import StateEventPartyComposite from "../lib/elections/StateEventPartyComposite.svelte";
  import SiblingEventsRail from "../lib/elections/SiblingEventsRail.svelte";
  import { buildSiblingEventsRail } from "../lib/elections/sibling-events-rail-model";
  import {
    loadEventSummary,
    type EventSummaryRow,
  } from "../lib/elections/event-summary-loader";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { route } from "../lib/router.svelte";
  import { SHARE_BASE } from "../lib/paths";
  import type { PartyTotals } from "../lib/data";
  import { loadAlliances } from "../lib/psephlab/alliances";
  import type { AllianceLookup } from "../lib/psephlab/types";
  import {
    writeLastEvent,
    type LastEventBody,
  } from "../lib/elections/last-event-memory";

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

  // R2 of TODO/20260615-state-election-event-page-redesign-plan.md
  // (J-elevated-15): persist the last-viewed (state, event_id, body)
  // tuple so the /<state>/elections/ landing route can render a
  // "Last viewed" badge next to the matching year-link. 30-day
  // expiry; per-state-slug localStorage key; no telemetry. Reads of
  // this memory live in StateElectionsLanding.svelte.
  $effect(() => {
    const ev = event_row;
    if (!ev) return;
    writeLastEvent(params.state, ev.event_id, ev.kind as LastEventBody);
  });

  const winners = $derived<ElectionResultRow[]>(
    result.status === "ok" || result.status === "partial" ? result.data : [],
  );
  const pending = $derived(
    result.status === "partial" ||
      (result.status === "ok" && winners.length === 0),
  );
  // Panel-state machine: differentiate loader-in-flight from
  // empty-after-ok so the KPI strip / top-parties / table do not
  // render misleading "Seats 0 / No constituency rows yet" during
  // the ~5-second DuckDB-WASM cold-load window. See doc comment on
  // pickEventPanelState for the four-arm contract. PR
  // fix/state-parl-seats-0-loader (2026-06-12).
  const panel_state = $derived(
    pickEventPanelState(result, winners.length),
  );
  const loading = $derived(panel_state === "loading");

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
  // TODO/20260612 Row D: top-parties bar now reuses the existing
  // PartyBar primitive. The local PartyTotal interface is replaced by
  // the canonical PartyTotals from lib/data.ts (additive widening with
  // alliance_short is in that file). Aggregation pre-bucket: total
  // seats per party AND total votes per party so we can derive
  // vote_share_pct against the event-total polled vote count once.
  const TOP_N = 8;

  // Alliance lookup is shared with AllianceTotals via the module-level
  // cache in psephlab/alliances.ts (one network fetch per event). We
  // run a parallel hook here so each PartyTotals row can carry
  // `alliance_short` when populated; null when the event has no
  // curated alliance row for that party. v2.0 schema (2026-06-12):
  // loader now keys by (event_id, state OR "IN") so passing the LGD
  // state slug (params.state) gives the per-state view while
  // surfacing national-event rows (state="IN") on every state page.
  let alliance_lookup = $state<AllianceLookup | null>(null);
  $effect(() => {
    const ev_id = event_row?.event_id;
    const st = params.state;
    if (!ev_id) {
      alliance_lookup = null;
      return;
    }
    alliance_lookup = null;
    loadAlliances(ev_id, st).then((l) => {
      if (ev_id === event_row?.event_id && st === params.state) {
        alliance_lookup = l;
      }
    });
  });

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
        };
        by.set(pid, bucket);
      }
      bucket.seats += 1;
      // The W2b loader leaves `w.votes` null at winner-only scopes
      // (only the CONSTITUENCY arm projects per-candidate votes). So
      // recover the winner's vote count from the (votes_polled,
      // winner_share_pct) pair the SQL DOES project. When either is
      // null (long-tail uncontested seats) the share contribution
      // for that seat is skipped; has_any_vote tracks whether the
      // party has at least one usable seat so the share denominator
      // doesn't fabricate 0% when every row was unknowable.
      if (w.votes_polled != null && w.vote_share_pct != null) {
        bucket.votes += (w.votes_polled * w.vote_share_pct) / 100;
        bucket.has_any_vote = true;
      }
    }
    const sorted = [...by.values()]
      .sort((a, b) => b.seats - a.seats)
      .slice(0, TOP_N);
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
      alliance_short: alliance_lookup?.(b.pid) ?? null,
    }));
  });

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

  // ---- TODO/20260612 Rows D + F: PC winner projection for StatePcMapD3
  // + per-PC mute overrides. unique_id matches the PC topojson's join
  // shape, which depends on the event's delim_year:
  //   - delim=2024 (LS 2024) -> `<state_code>_<eci_no>` (numeric)
  //   - delim=2008 (LS 2019 / 2014 / 2009) -> `<state_code>_<pc_name_slug>`
  // The 2008 layer uses a name-slug join because canonical electoral.csv
  // carries unreliable eci_no values for delim=2008 PCs (22 of 544 are 0;
  // many populated values are misaligned with ECI's actual numbering).
  // See INDIA_PC_2008 jsdoc + plan TODO/20260612-pc-delim-2008-boundary-
  // ingest-plan.md V6 pre-flight for the alignment evidence.
  //
  // Derives delim year from `ev.event_id`:
  //   - general-2024 -> 2024
  //   - general-{2019,2014,2009} -> 2008
  //   - general-{2004,1999,...} (pre-2009 LS) -> null (no on-disk geometry;
  //     the placeholder card persists for those events).
  //   - non-LS events (`general-*` is the only LS pattern) -> null.
  function pcDelimYearForLsEvent(eventId: string | null | undefined): number | null {
    if (!eventId) return null;
    const m = /^general-(\d{4})$/.exec(eventId);
    if (!m) return null;
    const year = parseInt(m[1], 10);
    if (year >= 2024) return 2024;
    if (year >= 2009) return 2008;
    return null;
  }
  const pc_delim_year = $derived(pcDelimYearForLsEvent(event_row?.event_id));
  const pc_boundary = $derived(pc_delim_year === 2008 ? INDIA_PC_2008 : INDIA_PC);

  const pc_winners = $derived.by<PcWinnerRow[]>(() => {
    if (body !== "pc") return [];
    if (pc_delim_year == null) return [];  // pre-2009 events: no geometry on disk
    const useNameSlug = pc_delim_year === 2008;
    const out: PcWinnerRow[] = [];
    for (const w of winners) {
      if (w.margin_pct == null) continue;
      const tail = useNameSlug ? slugify(w.entity_name) : String(w.eci_no);
      out.push({
        unique_id: `${w.state_code}_${tail}`,
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

  // ---- TODO/20260612 Row F: PartyBar click-to-mute -------------------
  // hidden_parties keys = `party_eci_code ?? party_short` (PartyBar +
  // StateOverview convention). Mute is visual only; per spec we DON'T
  // recompute seats or vote share. Reset on event change so muting
  // "BJP" on chhattisgarh general-2024 doesn't silently carry to
  // general-2019 when the citizen navigates.
  //
  // R3 of TODO/20260615-state-election-event-page-redesign-plan.md
  // (2026-06-15): the toggleHidden handler is now owned by the
  // extracted StateEventPartyComposite subcomponent. `hidden_parties`
  // is passed as $bindable so the subcomponent's button writes flow
  // back to this proxy, which is what the hidden_pids derivation +
  // the AC / PC override paths below continue to read.
  let hidden_parties = $state<Set<string>>(new Set());
  $effect(() => {
    void event_row?.event_id;
    void params.state;
    hidden_parties = new Set();
  });

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

  // Per-AC override map (keyed by eci_no): muted-party cells recede.
  // The base Winner|Margin shim above already paints non-muted cells;
  // these overrides ONLY recede when a party is muted.
  const ac_fills_override = $derived.by<Record<number, string>>(() => {
    const out: Record<number, string> = {};
    if (body !== "ac") return out;
    for (const w of winners) {
      const pid = partyIdFor(w);
      if (hidden_pids.has(pid)) {
        out[w.eci_no] = "#cbd5e1"; // slate-300 recede
      }
    }
    return out;
  });
  const ac_opacities_override = $derived.by<Record<number, number>>(() => {
    const out: Record<number, number> = {};
    if (body !== "ac") return out;
    for (const w of winners) {
      const pid = partyIdFor(w);
      if (hidden_pids.has(pid)) {
        out[w.eci_no] = 0.18;
      }
    }
    return out;
  });

  // Per-PC override map (keyed by unique_id): muted-party recede + the
  // Winner|Margin shim's margin-grey for non-muted PCs when color_mode
  // is "margin".
  const pc_fills_override = $derived.by<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    for (const w of pc_winners) {
      if (hidden_pids.has(w.party_id)) {
        out[w.unique_id] = "#cbd5e1";
      } else if (color_mode === "margin") {
        out[w.unique_id] = marginGrey(w.margin_pct);
      }
    }
    return out;
  });
  const pc_opacities_override = $derived.by<Record<string, number>>(() => {
    const out: Record<string, number> = {};
    for (const w of pc_winners) {
      if (hidden_pids.has(w.party_id)) {
        out[w.unique_id] = 0.18;
      }
    }
    return out;
  });

  // ---- TODO/20260612 Row E: AC Map | Equal seats toggle --------------
  // Lifted from ElectionMap.svelte (same loader, same buildTileRows
  // path). Only mounted on assembly events with a per-state AC tile
  // layout; PC events skip the toggle entirely (no per-state PC tile
  // layouts authored).
  const TILE_AC_DELIM_YEAR = 2008;
  type AcView = "map" | "hex";
  let ac_view = $state<AcView>("map");
  let has_ac_equal_seats = $state<boolean | null>(null);
  $effect(() => {
    const sc = state_code;
    if (!sc || body !== "ac") {
      has_ac_equal_seats = false;
      return;
    }
    fetchElectionTileScopes()
      .then((doc) => {
        if (state_code !== sc) return;
        has_ac_equal_seats = hasLayoutForScope(doc, {
          layout_kind: "ac",
          scope: sc,
          delim_year: TILE_AC_DELIM_YEAR,
        });
      })
      .catch(() => {
        if (state_code === sc) has_ac_equal_seats = false;
      });
  });

  let ac_tile_layout = $state<TileLayoutRow[] | null>(null);
  let ac_tile_layout_error = $state(false);
  let ac_tile_layout_requested = false;
  $effect(() => {
    if (
      ac_view !== "hex" ||
      ac_tile_layout_requested ||
      has_ac_equal_seats === false ||
      !state_code
    )
      return;
    const sc = state_code;
    ac_tile_layout_requested = true;
    fetchElectionTileLayouts()
      .then((doc) => {
        if (state_code !== sc) return;
        ac_tile_layout = selectLayout(doc, {
          layout_kind: "ac",
          scope: sc,
          delim_year: TILE_AC_DELIM_YEAR,
        });
      })
      .catch(() => {
        if (state_code === sc) ac_tile_layout_error = true;
      });
  });

  const ac_hex_winners = $derived<TileWinnerInput[]>(
    body !== "ac" || !state_code
      ? []
      : winners.map((w) => ({
          unit_id: `IN-${state_code}-AC-${TILE_AC_DELIM_YEAR}-${w.eci_no}`,
          party_key: w.party_eci_code,
          party_short: w.party_short ?? "UNK",
          margin_pct: w.margin_pct,
          party_id: partyIdFor(w),
          brand_colour_hex: w.brand_colour_hex,
          brand_colour_confidence: w.brand_colour_confidence,
        })),
  );

  const ac_raw_tile_rows = $derived<TileRow[]>(
    ac_tile_layout == null
      ? []
      : buildTileRows(ac_tile_layout, ac_hex_winners),
  );

  // Re-skin hex tiles for Margin-mode greyscale + party-mute recede -
  // same shape as ElectionMap. The unit_id ends in `...-<eci_no>` so
  // we recover eci_no via the trailing segment.
  const ac_tile_rows = $derived<TileRow[]>(
    ac_raw_tile_rows.map((t) => {
      if (t.pending) return t;
      const eci_no = Number(t.unit_id.split("-").pop());
      const muted =
        t.winner_party_id != null && hidden_pids.has(t.winner_party_id);
      if (muted) return { ...t, fill: "#cbd5e1", opacity: 0.18 };
      if (color_mode === "margin") {
        return { ...t, fill: marginGrey(t.margin_pct ?? null) };
      }
      if (Number.isFinite(eci_no) && ac_fills_override[eci_no]) {
        return { ...t, fill: ac_fills_override[eci_no] };
      }
      return t;
    }),
  );

  function onAcTileSelect(unit_id: string): void {
    const eci_no = Number(unit_id.split("-").pop());
    if (!Number.isFinite(eci_no) || !state_code || !event_row) return;
    const seat = winners.find((w) => w.eci_no === eci_no);
    if (!seat) return;
    const pc_slug = slugify(seat.entity_name);
    navigate(
      `/${params.state}/elections/${encodeURIComponent(event_row.event_id)}/${pc_slug}`,
    );
  }

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

  // ---- R4 (TODO/20260615-state-election-event-page-redesign-plan.md):
  // Load the per-event aggregate mart once for: (a) the SiblingEventsRail
  // winner-color underlines (resolves event_id -> leading_party brand
  // colour), and (b) the HeroCards turnout pp-delta vs the previous
  // same-body event. Mart shape carries leading_party_id + turnout_pct
  // keyed by (event_id, state_code). Cached singleton, so the cost is
  // paid once per page session.
  let event_summary_rows = $state<EventSummaryRow[] | null>(null);
  let event_summary_error = $state<string | null>(null);
  $effect(() => {
    // re-fire on identity change (event navigation reuses this route).
    void event_row?.event_id;
    if (event_summary_rows !== null || event_summary_error !== null) return;
    loadEventSummary()
      .then((rows) => (event_summary_rows = rows))
      .catch((e) => (event_summary_error = String(e)));
  });

  const event_summary_by_id = $derived.by<Map<string, EventSummaryRow>>(() => {
    const out = new Map<string, EventSummaryRow>();
    if (!event_summary_rows || !state_code) return out;
    for (const r of event_summary_rows) {
      // Restrict to the current state's rows; the leading_party for
      // (event_id, state_code) is the per-state winner (Assembly).
      // For Parliament events we still scope by state_code so the
      // colour matches the per-state winner of that LS election.
      if (r.state_code === state_code) {
        out.set(r.event_id, r);
      }
    }
    return out;
  });

  // Resolver consumed by SiblingEventsRail: maps an event_id to its
  // leading party's brand colour for the chip's underline. Returns
  // null when the mart row is missing OR the leading_party has no
  // brand_colour entry in this event's winners. The rail's component
  // falls back to slate-200 in that case.
  function winnerColorForEventId(event_id: string): string | null {
    const row = event_summary_by_id.get(event_id);
    if (!row || !row.leading_party_id) return null;
    // Resolve via the canonical 3-tier resolver. For the leading
    // party of a sibling event we may not have a brand_colour row
    // loaded (winners[] is scoped to the CURRENT event). Hand the
    // resolver a null brand_colour so it falls back to the algorithmic
    // tier (deterministic colour from the party_id).
    return getPartyColor(row.leading_party_id, null).hex;
  }

  const sibling_events_rail_model = $derived.by(() => {
    if (!catalogue || !state_code || !event_row || !body) return null;
    return buildSiblingEventsRail({
      catalogue,
      state_code,
      state_slug: params.state,
      current_event_id: event_row.event_id,
      body,
      winner_color_for_event_id: winnerColorForEventId,
    });
  });

  // Hero turnout-delta payload. Compares the current event's
  // turnout_pct against the previous same-body event's turnout_pct
  // (both derived from event_summary.csv per the plan's RATIFIED
  // sourcing rule). When the prior row is missing OR the field is
  // null on either side, the delta is OMITTED entirely (first-event-
  // on-record card-collapse pin per J-elevated-3 amend).
  interface HeroDeltaPayload {
    turnout_pp: number | null;
    prev_event_label: string | null;
  }
  const hero_delta = $derived.by<HeroDeltaPayload>(() => {
    const prev = previous_same_body;
    const ev = event_row;
    if (!ev || !prev) return { turnout_pp: null, prev_event_label: null };
    const current_row = event_summary_by_id.get(ev.event_id);
    const prev_row = event_summary_by_id.get(prev.event_id);
    if (!current_row || !prev_row) {
      return { turnout_pp: null, prev_event_label: null };
    }
    if (current_row.turnout_pct == null || prev_row.turnout_pct == null) {
      return { turnout_pp: null, prev_event_label: null };
    }
    const pp = current_row.turnout_pct - prev_row.turnout_pct;
    // Compact label: "Assembly 2019" rather than the full catalogue
    // display string "Maharashtra Assembly 2019" since the citizen
    // is already on the Maharashtra page.
    const kind_pretty = prev.kind === "parliament" ? "Parliament" : "Assembly";
    const year_match = /(\d{4})/.exec(prev.event_id);
    const year = year_match ? year_match[1] : prev.event_id;
    return {
      turnout_pp: pp,
      prev_event_label: `${kind_pretty} ${year}`,
    };
  });

  // ---- Display label --------------------------------------------------
  // event_row.display already includes the state name for parliament
  // events ("Chhattisgarh · Parliament 2024") and assembly events
  // ("Chhattisgarh Assembly · November 2023"). For unknown events fall
  // back to a synthesised "Parliament Election YYYY" / "Assembly
  // Election YYYY" label that we prefix with the state explicitly.
  const event_pretty = $derived.by<string>(() => {
    if (event_row) return event_row.display;
    const m = /^(general|assembly)-(\d{4})$/.exec(params.event);
    if (m) {
      const body_pretty = m[1] === "general" ? "Parliament" : "Assembly";
      return `${state_name} ${body_pretty} Election ${m[2]}`;
    }
    return `${state_name} - ${params.event}`;
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

  // R7 (TODO/20260615-state-election-event-page-redesign-plan.md
  // J-elevated-14): OG-card unfurl meta. Generated PNG ships at
  // /share/{state-slug}/{event_id}.png via the build step in
  // `frontend/scripts/build-share-cards.ts`. When the event_id
  // cannot be resolved (404 surfaces upstream) the og:image meta is
  // omitted entirely - WhatsApp / Twitter degrade to text-only
  // previews rather than 404 on a broken image.
  const og_image_url = $derived(
    event_row && state_code
      ? `${SHARE_BASE}/${params.state}/${event_row.event_id}.png`
      : null,
  );
  const og_title = $derived(`${event_pretty} - yen-gov`);
  const og_description = $derived.by(() => {
    if (!event_row || !state_code) return "Election data for India.";
    const body_word = body === "pc" ? "Parliament" : "Assembly";
    return `${state_name} ${body_word} election polled on ${event_row.polled_on}. Seat-by-seat winners, party totals, alliance composition, and turnout context.`;
  });
</script>

<svelte:head>
  <title>{og_title}</title>
  <meta property="og:title" content={og_title} />
  <meta property="og:description" content={og_description} />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={og_title} />
  <meta name="twitter:description" content={og_description} />
  {#if og_image_url}
    <meta property="og:image" content={og_image_url} />
    <meta name="twitter:image" content={og_image_url} />
  {/if}
</svelte:head>

<Breadcrumb {crumbs} />

<PageContainer width="wide">
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
    <!-- Header + load-error + KPIs + pending. R3 of
         TODO/20260615-state-election-event-page-redesign-plan.md
         (2026-06-15): extracted to StateEventHero.svelte as a Beck
         two-hat structural-only refactor; data-testids and DOM shape
         preserved verbatim. R4 will rebuild the KPI strip into the
         J-elevated-3 HeroCards with icon glyphs + turnout-delta. -->
    <StateEventHero
      event_row={ev}
      {body}
      {event_pretty}
      {result}
      {loading}
      {pending}
      {kpis}
      delta={hero_delta}
      {fmtInt}
      {fmtCompact}
      {fmtPct}
    />

    <!-- Sibling-events year-chip rail. R4 J-elevated-4: replaces the
         deleted "Prev / Next / Compare ->" text strip; pure year
         chips with winner-color underlines + a trailing Compare
         pill (no arrows ever). -->
    {#if sibling_events_rail_model}
      <SiblingEventsRail model={sibling_events_rail_model} />
    {/if}

    {#if result.status !== "failed"}
      <!-- TODO/20260612 Rows D + E + F: state choropleth.
           AC events: Winner|Margin sub-toggle + Map | Equal seats arm
                       toggle (latter only when the state has a
                       persisted AC tile layout) + party-mute via
                       PartyBar click.
           PC events: StatePcMapD3 + Winner|Margin sub-toggle + party-
                       mute. No Equal-seats arm (per-state PC tile
                       layouts have not been authored yet; surfaced
                       inline below the map).

           R3 of TODO/20260615-state-election-event-page-redesign-plan.md
           (2026-06-15): extracted to StateEventMap.svelte as a Beck
           two-hat structural-only refactor; the section's DOM shape +
           every data-testid are preserved verbatim. R4 will reorder
           this above the PartyComposite + add the
           SiblingEventsRail. color_mode + ac_view are bound through
           so the parent's override derivations still read the same
           proxy. -->
      {#if state_code && (body === "ac" || body === "pc")}
        {#if body === "pc" || STATE_AC[state_code]}
          <StateEventMap
            {body}
            state_code={state_code}
            event_id={ev.event_id}
            {ac_winners_shim}
            {ac_fills_override}
            {ac_opacities_override}
            {has_ac_equal_seats}
            {ac_tile_layout}
            {ac_tile_layout_error}
            {ac_tile_rows}
            {onAcTileSelect}
            {pc_winners}
            {pc_delim_year}
            {pc_boundary}
            {pc_fills_override}
            {pc_opacities_override}
            state_slug={params.state}
            bind:color_mode
            bind:ac_view
          />
        {/if}
      {/if}

      <!-- Top parties: R3 of TODO/20260615-state-election-event-page-
           redesign-plan.md (2026-06-15): extracted to
           StateEventPartyComposite.svelte as a Beck two-hat structural-
           only refactor; the section's DOM shape + data-testids are
           preserved verbatim. R4 will extend this into a per-party
           row table with [symbol][short][alliance-chip][seats-bar]
           [seats-count][vote-share%]. hidden_parties is bound through
           so the parent's hidden_pids derivation continues to power
           the AC + PC map recede paths. -->
      <StateEventPartyComposite
        {loading}
        {top_parties}
        total_seats={kpis.total_seats}
        bind:hidden_parties
      />

      <!-- Alliance totals -->
      <AllianceTotals
        event={ev.event_id}
        state_slug={params.state}
        winners={winners.map((w) => ({
          party_id: w.party_id,
          party_short: w.party_short,
          party_eci_code: w.party_eci_code,
        }))}
        polled_on={ev.polled_on}
      />

      <!-- R4 (TODO/20260615-state-election-event-page-redesign-plan.md):
           the InlineCounterfactualSwing mount that previously sat
           between AllianceTotals and the constituency table is
           DELETED on this surface. Counterfactual ergonomics live on
           Psephlab; the state-event page is the canonical fact view.
           The component file is retained because Psephlab still
           mounts it; only the mount is removed here. -->

      <!-- Scatter chart (PR-W4c MUST-FEATURE; state filter pre-applied via loader).
           TODO/20260612 Row A.5: lock_body=true hides the Body chip
           since the state-event surface is single-body fixed by the URL.
           R3 (TODO/20260615-state-election-event-page-redesign-plan.md):
           extracted to StateEventScatter.svelte as a Beck two-hat
           structural-only refactor; the section's data-testid and DOM
           shape are preserved verbatim. R4 moves Scatter ABOVE
           ConstituencyList so the citizen reads turnout-vs-margin
           context BEFORE diving into per-AC rows. -->
      <StateEventScatter
        {winners}
        {body}
        {state_name}
        fallback_event_id={params.event}
        resolved_event_id={event_row?.event_id}
      />

      <!-- Constituency table + Compare CTA. R3 of
           TODO/20260615-state-election-event-page-redesign-plan.md
           (2026-06-15): extracted to StateEventConstituencyList as a
           Beck two-hat structural-only refactor; the section's
           data-testids and DOM shape were preserved verbatim. R4
           rebuilds the inside (district-grouped fold + sticky search +
           Compare CTA as a slate-link last row) - the testids stay
           verbatim so all prior e2e assertions still pass. -->
      <StateEventConstituencyList
        {loading}
        {seat_rows}
        {previous_same_body}
        {compare_href}
        {fmtInt}
        {fmtPct}
      />
    {/if}
  {/if}
</PageContainer>
