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
  import StateAcMapD3 from "../lib/charts/StateAcMapD3.svelte";
  import StatePcMapD3, {
    type PcWinnerRow,
  } from "../lib/charts/StatePcMapD3.svelte";
  import { INDIA_PC, INDIA_PC_2008 } from "../lib/boundaries/sources";
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
  import { STATE_AC } from "../lib/boundaries/sources";
  import type { AcWinner } from "../lib/view-models/state-overview";
  import {
    buildPartyKeyToPid,
    hiddenPidSet,
  } from "../lib/charts/india-pc-map-helpers";
  import InlineCounterfactualSwing from "../lib/elections/InlineCounterfactualSwing.svelte";
  import AllianceTotals from "../lib/elections/AllianceTotals.svelte";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { route } from "../lib/router.svelte";
  import Scatter from "../lib/charts/Scatter.svelte";
  import type {
    ScatterDatum,
    ScatterFilters,
  } from "../lib/charts/scatter-model";
  import PartyBar from "../lib/PartyBar.svelte";
  import type { PartyTotals } from "../lib/data";
  import { loadAlliances } from "../lib/psephlab/alliances";
  import type { AllianceLookup } from "../lib/psephlab/types";

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
  let hidden_parties = $state<Set<string>>(new Set());
  function toggleHidden(key: string): void {
    const next = new Set(hidden_parties);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    hidden_parties = next;
  }
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

  // ---- Scatter chart projection (PR-W4c) ------------------------------
  // The state filter is implicit (winners is already pre-filtered to
  // `params.state` via the W2b loader's state-scope arm). The body
  // filter chip on the scatter starts on the active event kind so the
  // chart and the page agree on first paint; afterwards the citizen
  // may toggle freely (toggling to the inactive body simply empties
  // the chart, which is the correct UX given the loader is single-body
  // scoped for this surface).
  let scatter_filters = $state<ScatterFilters>({
    reservation: "all",
    margin_band: "all",
  });
  let scatter_body_initialised = false;
  $effect(() => {
    if (scatter_body_initialised) return;
    const b = body;
    if (!b) return;
    scatter_filters = {
      ...scatter_filters,
      body: b === "pc" ? "parliament" : "assembly",
    };
    scatter_body_initialised = true;
  });
  const scatter_data = $derived.by<ScatterDatum[]>(() => {
    const out: ScatterDatum[] = [];
    const ev = event_row?.event_id ?? params.event;
    const body_lit: "parliament" | "assembly" =
      body === "pc" ? "parliament" : "assembly";
    for (const w of winners) {
      if (w.turnout_pct == null || w.margin_pct == null) continue;
      out.push({
        entity_id: w.entity_id,
        state_slug: w.state_slug,
        constituency_slug: slugify(w.entity_name),
        constituency_name: w.entity_name,
        event_id: ev,
        turnout_pct: w.turnout_pct,
        margin_pct: w.margin_pct,
        electors: w.electors ?? 0,
        // TODO/20260612 Row B: margin_votes drives the radius encoding.
        // Null at the loader becomes null on the datum; the Scatter
        // component clamps null -> 0 for layout.
        margin_votes: w.margin_votes,
        winner_party_id: (function () {
          if (w.party_id) return w.party_id;
          const slug = (w.party_short ?? "UNK").trim().toUpperCase();
          return `parties.IN.${slug}`;
        })(),
        winner_party_short: w.party_short ?? "UNK",
        reservation: w.reservation,
        body: body_lit,
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
    <!-- Header -->
    <header class="space-y-2">
      <h1
        class="text-2xl font-semibold text-slate-900"
        data-testid="state-event-header"
      >
        {event_pretty}
      </h1>
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span
          class="inline-block rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
          data-testid="state-event-body-chip"
        >{body === "pc" ? "Parliament" : "Assembly"}</span>
        <span class="text-slate-500">
          Polled <span class="tabular-nums">{ev.polled_on}</span>
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
          <div
            class="mt-1 text-2xl font-semibold text-slate-900"
            data-testid="state-event-kpi-seats"
          >
            {loading ? "-" : fmtInt(kpis.total_seats)}
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

      <!-- TODO/20260612 Rows D + E + F: state choropleth.
           AC events: Winner|Margin sub-toggle + Map | Equal seats arm
                       toggle (latter only when the state has a
                       persisted AC tile layout) + party-mute via
                       PartyBar click.
           PC events: StatePcMapD3 + Winner|Margin sub-toggle + party-
                       mute. No Equal-seats arm (per-state PC tile
                       layouts have not been authored yet; surfaced
                       inline below the map). -->
      {#if body === "ac" && state_code && STATE_AC[state_code]}
        <section
          class="space-y-2"
          data-testid="state-event-map"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-sm font-medium text-slate-700">
              Constituencies
            </h2>
            <div class="flex flex-wrap items-center gap-2">
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
              {#if has_ac_equal_seats === true}
                <div
                  class="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-sm"
                  data-testid="state-event-map-view"
                >
                  <button
                    type="button"
                    class="rounded-md px-3 py-1 transition-colors {ac_view === 'map'
                      ? 'bg-white font-medium text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'}"
                    data-view="map"
                    onclick={() => (ac_view = "map")}
                  >Map</button>
                  <button
                    type="button"
                    class="rounded-md px-3 py-1 transition-colors {ac_view === 'hex'
                      ? 'bg-white font-medium text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'}"
                    data-view="hex"
                    onclick={() => (ac_view = "hex")}
                  >Equal seats</button>
                </div>
              {/if}
            </div>
          </div>
          {#if ac_view === "map"}
            <div data-testid="state-event-map-geo">
              <StateAcMapD3
                state={state_code}
                rows={ac_winners_shim}
                event={ev.event_id}
                height="420px"
                fillsOverride={ac_fills_override}
                opacitiesOverride={ac_opacities_override}
              />
            </div>
          {:else}
            <div data-testid="state-event-map-hex">
              {#if ac_tile_layout_error}
                <div
                  class="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
                >
                  Equal-seats layout couldn't load.
                </div>
              {:else if ac_tile_layout == null}
                <p class="p-4 text-sm text-slate-500">
                  Loading equal-seats layout...
                </p>
              {:else}
                <TileCartogram
                  tiles={ac_tile_rows}
                  height="420px"
                  onSelect={onAcTileSelect}
                />
              {/if}
            </div>
          {/if}
          <p class="text-xs text-slate-500">
            {color_mode === "winner"
              ? "Each constituency is filled with the winning party's colour."
              : "Each constituency is shaded by winning margin (darker = larger margin)."}
          </p>
          {#if ac_view === "map"}
            <!-- TODO/20260612 Row C: sub-threshold marker legend - the
                 StateAcMapD3 component overlays circular markers for ACs
                 whose bbox is too small to render as a polygon at this
                 zoom. Without this caption citizens read the circles as
                 an unexplained second symbology. -->
            <p
              class="text-[11px] text-slate-500"
              data-testid="state-ac-map-legend"
            >
              Circles mark dense urban constituencies whose polygon is too
              small to render at this zoom.
            </p>
          {/if}
        </section>
      {:else if body === "pc" && state_code}
        <!-- TODO/20260612 Row D: PC choropleth via StatePcMapD3,
             filtering the national PC topojson by `state_ut_code ===
             state_code`. Replaces the "Constituency map being
             prepared" placeholder card from PR #954 for LS 2024
             (delim=2024) AND LS 2019 / 2014 / 2009 (delim=2008,
             ingested by FU#3 plan TODO/20260612-pc-delim-2008-
             boundary-ingest-plan.md). Pre-2009 LS events
             (general-2004 / general-1999 / ...) have no PC geometry
             on disk and render the placeholder card below.

             No "Equal seats" arm: per-state PC tile layouts have not
             been authored (only national PC + per-state AC layouts
             exist today). The note below directs the citizen to the
             national surface for the hex view. -->
        {#if pc_delim_year == null}
          <!-- Pre-2009 LS event: no PC geometry available; placeholder
               card persists. This is by design (FU#3 plan-doc Smoke 6
               regression check). -->
          <section
            class="space-y-2"
            data-testid="state-event-map-placeholder"
          >
            <h2 class="text-sm font-medium text-slate-700">
              Constituencies
            </h2>
            <div
              class="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"
            >
              Constituency map for pre-2009 Lok Sabha events is not yet
              available. No machine-readable GIS source for the 1976
              Delimitation Commission Order has been ingested. See the
              constituency table below for results.
            </div>
          </section>
        {:else}
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
          <StatePcMapD3
            state={state_code}
            state_slug={params.state}
            rows={pc_winners}
            event={ev.event_id}
            height="420px"
            fillsOverride={pc_fills_override}
            opacitiesOverride={pc_opacities_override}
            boundary={pc_boundary}
          />
          <p class="text-xs text-slate-500">
            {color_mode === "winner"
              ? "Each constituency is filled with the winning party's colour."
              : "Each constituency is shaded by winning margin (darker = larger margin)."}
          </p>
          <p
            class="text-[11px] text-slate-500"
            data-testid="state-pc-map-legend"
          >
            Circles mark dense urban constituencies whose polygon is too
            small to render at this zoom. Equal-seats view available on
            the
            <a
              class="text-sky-700 hover:underline"
              href={`/t/elections/${encodeURIComponent(ev.event_id)}`}
            >national {ev.event_id} surface</a>.
          </p>
        </section>
        {/if}
      {/if}

      <!-- Top parties (TODO/20260612 Row D: reuses PartyBar; vote-share +
           seats + optional alliance tag. Row F: click-to-mute via
           hidden_parties + reset button when N > 0; mute recedes
           matching cells on the AC + PC maps via the override path. -->
      <section
        class="space-y-2"
        data-testid="state-event-top-parties"
      >
        <div class="flex items-baseline justify-between gap-2 flex-wrap">
          <h2 class="text-sm font-medium text-slate-700">
            Top parties by seats
          </h2>
          {#if hidden_parties.size > 0}
            <button
              type="button"
              class="text-xs text-sky-700 hover:underline"
              data-testid="state-event-top-parties-reset"
              onclick={() => (hidden_parties = new Set())}
            >Show all ({hidden_parties.size} muted)</button>
          {/if}
        </div>
        {#if loading}
          <p
            class="text-xs text-slate-500"
            data-testid="state-event-top-parties-loading"
          >Loading top parties...</p>
        {:else if top_parties.length === 0}
          <p class="text-xs text-slate-500">No party totals yet.</p>
        {:else}
          <PartyBar
            parties={top_parties}
            total_seats={kpis.total_seats}
            {hidden_parties}
            onToggleHidden={toggleHidden}
          />
          <p class="text-[11px] text-slate-500">
            Click a party row to mute it; muted parties recede on the
            map. Vote totals don't recompute.
          </p>
        {/if}
      </section>

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
          Constituencies ({loading ? "-" : fmtInt(seat_rows.length)})
        </h2>
        {#if loading}
          <p
            class="text-xs text-slate-500"
            data-testid="state-event-constituency-table-loading"
          >Loading constituency results...</p>
        {:else if seat_rows.length === 0}
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

      <!-- Scatter chart (PR-W4c MUST-FEATURE; state filter pre-applied via loader).
           TODO/20260612 Row A.5: lock_body=true hides the Body chip
           since the state-event surface is single-body fixed by the URL. -->
      <section class="space-y-2" data-testid="state-event-scatter">
        <h2 class="text-sm font-medium text-slate-700">
          Turnout vs winning margin &middot; {state_name} constituencies
        </h2>
        <Scatter
          data={scatter_data}
          filters={scatter_filters}
          onFiltersChange={(next) => (scatter_filters = next)}
          onDotClick={onScatterDotClick}
          lock_body={true}
        />
      </section>
    {/if}
  {/if}
</PageContainer>
