<script lang="ts">
  // India choropleth: each state colored by its leading party (most seats
  // won) in that state's *default* election event from
  // datasets/reference/in/election-events.json. Hover shows seat-and-vote
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
    STATE_NAME_TO_ECI,
  } from "./sources";
  import {
    loadIndiaLeadingParties,
    type IndiaLeadingPartiesViewModel,
  } from "../view-models/india-leading-parties";
  import type { LoaderResult } from "../loader-result";
  import {
    defaultEventForState,
    fetchElectionEvents,
  } from "../election-events";
  import { colors } from "../colors/store.svelte";
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

  function retryLoad(): void {
    const force_event = event;
    result = { status: "loading" };
    (async () => {
      try {
        const catalogue = await fetchElectionEvents();
        const state_event_map: Record<string, string> = {};
        for (const code of Object.values(STATE_NAME_TO_ECI)) {
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

  // Pick the leading party (max seats_won) per state. Loader already sorts
  // party_totals desc by seats_won.
  const fills = $derived.by(() => {
    const out: Record<string, string> = {};
    void colors.overrides; // declare reactive read
    if (result.status !== "ok") return out;
    const per_state = result.data.per_state;
    const tops: { name: string; key: string; eci: string | null; short: string }[] = [];
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      const loaded = per_state[code];
      if (!loaded) continue;
      const top = loaded.party_totals.find((p) => p.seats_won > 0);
      if (top) {
        tops.push({
          name,
          key: top.party_eci_code ?? top.party_short,
          eci: top.party_eci_code,
          short: top.party_short,
        });
      }
    }
    const palette = colors.forSet(tops.map((t) => t.key));
    for (const t of tops) {
      out[t.name] = palette.get(t.key)?.fill ?? colors.fill(t.eci, t.short);
    }
    return out;
  });

  const tooltips = $derived.by(() => {
    const out: Record<string, string> = {};
    const per_state = result.status === "ok" ? result.data.per_state : {};
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      const loaded = per_state[code];
      if (!loaded) {
        out[name] = `<div class="font-semibold">${escape_html(name)}</div><div class="text-slate-500">no data loaded</div>`;
        continue;
      }
      const top = loaded.party_totals
        .filter((p) => p.seats_won > 0)
        .slice(0, 3);
      const rows = top
        .map((p) => `<div>${escape_html(p.party_short)} · ${p.seats_won}</div>`)
        .join("");
      out[name] =
        `<div class="font-semibold">${escape_html(name)} <span class="text-slate-400 font-mono text-[10px]">${code}</span></div>` +
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
    const code = STATE_NAME_TO_ECI[String(sel.key)];
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
