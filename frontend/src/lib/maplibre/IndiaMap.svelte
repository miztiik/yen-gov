<script lang="ts">
  // India choropleth: each state colored by its leading party (most seats
  // won) in that state's *default* election event from
  // datasets/reference/in/election-events.json. Hover shows seat-and-vote
  // summary; click navigates to the state overview.
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
  import { fetchResultSummary, type ResultSummary } from "../data";
  import {
    defaultEventForState,
    fetchElectionEvents,
    type ElectionEventsCatalogue,
  } from "../election-events";
  import { colors } from "../colors/store.svelte";
  import { navigate, url } from "../url";

  interface Props {
    /** Optional cohort to force every state into. When omitted, each
     *  state's own default event from the catalogue is used. */
    event?: string;
  }
  let { event }: Props = $props();

  // Per-state summary AND the event_id it was loaded from (so the tooltip
  // can show "AcGenNov2023" for MP next to "AcGenMay2026" for TN without
  // misattributing).
  type Loaded = { summary: ResultSummary; event_id: string };
  let summaries = $state<Record<string, Loaded>>({});
  let load_error = $state<string | null>(null);

  $effect(() => {
    summaries = {};
    load_error = null;
    const force_event = event;
    fetchElectionEvents()
      .then(catalogue => {
        const tasks: Promise<readonly [string, Loaded] | null>[] = [];
        for (const code of Object.values(STATE_NAME_TO_ECI)) {
          const ev = force_event ?? defaultEventForState(catalogue, code)?.event_id;
          if (!ev) continue;  // state has no entry in the catalogue → no data path
          tasks.push(
            fetchResultSummary(ev, code)
              .then(s => [code, { summary: s, event_id: ev }] as const)
              .catch(() => null),
          );
        }
        return Promise.all(tasks);
      })
      .then(results => {
        const out: Record<string, Loaded> = {};
        for (const r of results) if (r) out[r[0]] = r[1];
        summaries = out;
      })
      .catch(e => (load_error = String(e)));
  });

  // Pick the leading party (max seats_won, tiebreak votes) per state.
  // Use colors.forSet for a single, set-aware allocation across all
  // leading parties on the map — avoids two unanchored regional parties
  // landing on visually similar hues that the choropleth would conflate.
  const fills = $derived.by(() => {
    const out: Record<string, string> = {};
    void colors.overrides; // declare reactive read
    const tops: { name: string; key: string; eci: string | null; short: string }[] = [];
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      const loaded = summaries[code];
      if (!loaded) continue;
      const top = [...loaded.summary.party_totals]
        .filter(p => p.seats_won > 0)
        .sort((a, b) => b.seats_won - a.seats_won || b.votes - a.votes)[0];
      if (top) {
        tops.push({
          name,
          key: top.party_eci_code ?? top.party_short,
          eci: top.party_eci_code,
          short: top.party_short,
        });
      }
    }
    const palette = colors.forSet(tops.map(t => t.key));
    for (const t of tops) {
      out[t.name] = palette.get(t.key)?.fill ?? colors.fill(t.eci, t.short);
    }
    return out;
  });

  const tooltips = $derived.by(() => {
    const out: Record<string, string> = {};
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      const loaded = summaries[code];
      if (!loaded) {
        out[name] = `<div class="font-semibold">${escape_html(name)}</div><div class="text-slate-500">no data loaded</div>`;
        continue;
      }
      const top = [...loaded.summary.party_totals]
        .filter(p => p.seats_won > 0)
        .sort((a, b) => b.seats_won - a.seats_won)
        .slice(0, 3);
      const rows = top
        .map(p => `<div>${escape_html(p.party_short)} · ${p.seats_won}</div>`)
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

{#if load_error}
  <div class="p-3 text-sm bg-rose-50 border border-rose-200 rounded text-rose-900">
    Failed to load state summaries: <code>{load_error}</code>
  </div>
{/if}

<MapChoropleth
  entry={INDIA_STATES}
  {fills}
  {tooltips}
  height="520px"
  onSelect={on_select}
/>
