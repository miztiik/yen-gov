<script lang="ts">
  // India choropleth: each state colored by its leading party (most seats
  // won) in that state's *default* election event from
  // datasets/taxonomy/election_events.json. Hover shows seat-and-vote
  // summary; click navigates to the state overview.
  //
  // Migrated off ~36 per-state fetchResultSummary calls onto one bulk
  // DuckDB-WASM JOIN in PR-G (Phase 1.3c).
  //
  // The optional `event` prop, when set, forces every state to that single
  // cohort (used for cohort-comparison views). When unset (the default
  // home-page case), each state resolves its own most-recent assembly
  // event from the catalogue, so a state with data under AcGenNov2023
  // gets coloured the same way a state with data under AcGenMay2026 does.
  // States with no catalogue entry render in the default fill colour and
  // remain non-interactive.

  import MapChoropleth from "./MapChoropleth.svelte";
  import {
    INDIA_STATES,
  } from "./sources";
  import { loadStates } from "../view-models/states";
  import {
    loadIndiaLeadingParties,
    type IndiaLeadingPartiesViewModel,
  } from "../view-models/india-leading-parties";
  import type { LoaderResult } from "../loader-result";
  import {
    defaultEventForState,
    fetchElectionEvents,
  } from "../election-events";
  import { getPartyColor, resolvePartyPalette } from "../colors/resolver";
  import type { PartyRowForResolver } from "../colors/resolver";
  import type { PartyTotals } from "../data";
  import { navigate, url } from "../url";

  interface Props {
    /** Optional cohort to force every state into. When omitted, each
     *  state's own default event from the catalogue is used. */
    event?: string;
  }
  let { event }: Props = $props();

  // Loader result keyed by state_code. The derived expressions below read
  // from this single source of truth.
  let result = $state<LoaderResult<IndiaLeadingPartiesViewModel>>({
    status: "loading",
  });

  // Currently-valid Indian states+UTs from taxonomy.entities. Iterated by
  // fills / tooltips to build the per-state colour and hover content.
  // Replaces STATE_NAME_TO_ECI per T.0e.
  let states_taxonomy = $state<import("../view-models/states").StateRow[] | null>(null);
  loadStates()
    .then(s => (states_taxonomy = s))
    .catch(() => (states_taxonomy = []));

  // Reverse lookup boundary-join-KEY (LGD code post-D.0) -> ECI used by
  // on_select. Derived so it picks up the loaded list automatically.
  const KEY_TO_ECI = $derived.by(() => {
    const out: Record<string, string> = {};
    for (const s of states_taxonomy ?? []) out[s.boundary_join_key] = s.eci_code;
    return out;
  });

  function retryLoad(): void {
    const force_event = event;
    result = { status: "loading" };
    (async () => {
      try {
        const [catalogue, states_taxonomy] = await Promise.all([
          fetchElectionEvents(),
          loadStates(),
        ]);
        const state_event_map: Record<string, string> = {};
        for (const s of states_taxonomy) {
          const code = s.eci_code;
          const ev = force_event ?? defaultEventForState(catalogue, code)?.event_id;
          if (ev) state_event_map[code] = ev;
        }
        result = await loadIndiaLeadingParties(state_event_map);
      } catch (err) {
        result = {
          status: "failed",
          reason: String(err),
          retry: retryLoad,
        };
      }
    })();
  }

  $effect(() => {
    void event;
    retryLoad();
  });

  // PR-SYM-6f3: One-identity migration. Replace the legacy
  // `colors.forSet(...) -> colors.fill(eci_code, short)` ladder with the
  // canonical 3-tier resolver keyed on `party_id`. When the loader
  // populates `party_id` from dim_parties (current shape from
  // india-leading-parties.ts) we hand it straight through; legacy
  // producers that have not been extended yet surface `party_id == null`,
  // in which case we derive a stable `parties.IN.<UPPER(short_name)>` so
  // the resolver still degrades to anchor / algorithmic tiers without
  // losing identity stability. See PR #585 / #586 for the precedent.
  function partyIdFor(p: PartyTotals): string {
    if (p.party_id) return p.party_id;
    const slug = (p.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  }

  function rowFor(p: PartyTotals): PartyRowForResolver | null {
    if (p.brand_colour_hex == null) return null;
    return {
      party_id: partyIdFor(p),
      eci_code: p.party_eci_code,
      brand_colour: {
        hex: p.brand_colour_hex,
        confidence: p.brand_colour_confidence ?? "medium",
      },
    };
  }

  // Pick the leading party (max seats_won) per state. Loader already sorts
  // party_totals desc by seats_won.
  const fills = $derived.by(() => {
    const out: Record<string, string> = {};
    if (result.status !== "ok") return out;
    const per_state = result.data.per_state;
    const tops: { join_key: string; party: PartyTotals }[] = [];
    for (const s of states_taxonomy ?? []) {
      const code = s.eci_code;
      const loaded = per_state[code];
      if (!loaded) continue;
      const top = loaded.party_totals.find((p) => p.seats_won > 0);
      if (top) tops.push({ join_key: s.boundary_join_key, party: top });
    }
    // Batch-resolve every leading party's hex in one pass via
    // resolvePartyPalette so per-state lookups below are O(1) map gets.
    const ids = tops.map((t) => partyIdFor(t.party));
    const rows = new Map<string, PartyRowForResolver | null>();
    for (const t of tops) rows.set(partyIdFor(t.party), rowFor(t.party));
    const palette = resolvePartyPalette(ids, rows);
    for (const t of tops) {
      const pid = partyIdFor(t.party);
      out[t.join_key] = palette.get(pid)?.hex ?? getPartyColor(pid, rowFor(t.party)).hex;
    }
    return out;
  });

  const tooltips = $derived.by(() => {
    const out: Record<string, string> = {};
    const per_state = result.status === "ok" ? result.data.per_state : {};
    for (const s of states_taxonomy ?? []) {
      const code = s.eci_code;
      const display = s.boundary_join_name;
      const join_key = s.boundary_join_key;
      const loaded = per_state[code];
      if (!loaded) {
        out[join_key] = `<div class="font-semibold">${escape_html(display)}</div><div class="text-slate-500">no data loaded</div>`;
        continue;
      }
      const top = loaded.party_totals
        .filter((p) => p.seats_won > 0)
        .slice(0, 3);
      const rows = top
        .map((p) => `<div>${escape_html(p.party_short)} · ${p.seats_won}</div>`)
        .join("");
      out[join_key] =
        `<div class="font-semibold">${escape_html(display)} <span class="text-slate-400 font-mono text-[10px]">${code}</span></div>` +
        `<div class="text-slate-600">${rows}</div>` +
        `<div class="text-slate-400 text-[10px] mt-1">${escape_html(loaded.event_id)} · click to open →</div>`;
    }
    return out;
  });

  function escape_html(s: string): string {
    return s.replace(/[&<>"']/g, c =>
      c === "&" ? "&amp;" :
      c === "<" ? "&lt;" :
      c === ">" ? "&gt;" :
      c === '"' ? "&quot;" : "&#39;",
    );
  }

  function on_select(sel: { key: string | number }): void {
    const code = KEY_TO_ECI[String(sel.key)];
    if (code) navigate(url.state(code));
  }
</script>

{#if result.status === "failed"}
  <div class="p-3 text-sm bg-rose-50 border border-rose-200 rounded text-rose-900">
    <p>Failed to load state summaries: {result.reason}</p>
    <button
      type="button"
      onclick={() => result.status === "failed" && result.retry?.()}
      class="mt-2 px-3 py-1 text-xs rounded bg-rose-100 hover:bg-rose-200"
    >Retry</button>
  </div>
{/if}

<MapChoropleth
  entry={INDIA_STATES}
  {fills}
  {tooltips}
  height="520px"
  onSelect={on_select}
/>
