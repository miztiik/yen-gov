<script lang="ts">
  // The state Assembly election experience — map + equal-seats cartogram,
  // time-slider, and filter rail — extracted verbatim from StateElection.svelte
  // (EGC-A1) so it can mount on BOTH the event permalink (/s/:state/elections/
  // :event) AND the topic door (/s/:state/t/elections) without forking the
  // rendering logic. The component is self-contained: given a state code and a
  // selected assembly event, it loads its own AC winners, derives the slider
  // stops, party chips, and mode coverage, and owns the in-URL filter state.
  //
  // Event-selection POLICY stays with the parent, passed as `onSelectEvent`:
  //   * StateElection (permalink)  navigates the :event path segment;
  //   * StateTopic (topic door)    updates a local selected-event in place.
  // Either way the slider calls onSelectEvent(eventId) and the parent decides
  // how the selection is reflected. `selectedEvent` is the controlled input.
  //
  // Lok Sabha (national) events do NOT mount here — they drill into the
  // national PC atlas. Callers must only pass assembly events.

  import ElectionMap from "./ElectionMap.svelte";
  import ElectionTimeSlider from "./ElectionTimeSlider.svelte";
  import ElectionFilterRail from "./ElectionFilterRail.svelte";
  import { buildSliderStops } from "./election-time-slider";
  import { hasModeCoverage } from "./election-map-coloring";
  import {
    listEventsForState,
    type ElectionEventsCatalogue,
    type ElectionEventRow,
  } from "../election-events";
  import {
    parseElectionFilters,
    serializeElectionFilters,
    type ElectionFilters,
  } from "../election-filters";
  import { colors } from "../colors/store.svelte";
  import { navigate } from "../url";
  import { loadStateAcWinners, type AcWinner } from "../view-models/state-overview";

  interface Props {
    /** Resolved state code (e.g. "S13"). */
    state_code: string;
    /** The currently-selected assembly event. Caller guarantees kind === "assembly". */
    selectedEvent: ElectionEventRow;
    /** Election events catalogue (shared, lazily fetched by the parent). */
    catalogue: ElectionEventsCatalogue | null;
    /** Called when the citizen scrubs the time-slider to another event id. */
    onSelectEvent: (eventId: string) => void;
  }
  let { state_code, selectedEvent, catalogue, onSelectEvent }: Props = $props();

  // Snapping time-slider stops. Same-grain only: the AC map scrubs across this
  // state's ASSEMBLY elections. Chronologically ascending.
  const slider_stops = $derived(
    buildSliderStops(
      listEventsForState(catalogue, state_code).filter(e => e.kind === "assembly"),
    ),
  );

  // Assembly results power the map+toggle surface. `null` = loading.
  let ac_winners = $state<AcWinner[] | null>(null);
  $effect(() => {
    ac_winners = null;
    const sc = state_code;
    const ev = selectedEvent;
    if (!sc || !ev || ev.kind !== "assembly") return;
    loadStateAcWinners(ev.event_id, sc).then(r => {
      ac_winners = r.status === "ok" || r.status === "partial" ? r.data : [];
    });
  });

  // Filter rail (colour-by mode + party/margin dimming). The URL is the single
  // source of truth; the rail is a controlled component. We mirror the parsed
  // query string so reactivity fires after a `navigate` (which dispatches
  // popstate and re-runs the router).
  let filter_search = $state(
    typeof window === "undefined" ? "" : window.location.search,
  );
  const filters = $derived<ElectionFilters>(parseElectionFilters(filter_search));

  function onFilterChange(next: ElectionFilters): void {
    if (typeof window === "undefined") return;
    const base = new URLSearchParams(window.location.search);
    const qs = serializeElectionFilters(next, base);
    const target =
      window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash;
    navigate(target);
    filter_search = qs ? `?${qs}` : "";
  }

  // Distinct winning parties for the rail chips, palette-consistent with the
  // map (same `colors.forSet` allocation ElectionMap/StateAcMap use).
  const party_options = $derived.by(() => {
    void colors.overrides;
    const list = ac_winners ?? [];
    const palette = colors.forSet(
      list.map((r) => r.party_eci_code ?? r.party_short),
    );
    const seen = new Map<string, { code: string; short: string; color: string }>();
    for (const r of list) {
      const code = r.party_eci_code ?? r.party_short;
      if (seen.has(code)) continue;
      seen.set(code, {
        code,
        short: r.party_short,
        color: palette.get(code)?.fill ?? colors.fill(r.party_eci_code, r.party_short),
      });
    }
    return [...seen.values()];
  });

  const mode_coverage = $derived({
    turnout: hasModeCoverage(ac_winners ?? [], "turnout"),
    age: hasModeCoverage(ac_winners ?? [], "age"),
  });
</script>

<section class="space-y-2" data-testid="state-election-map">
  <h2 class="text-lg font-semibold">Results map</h2>
  <p class="text-xs text-slate-500">
    Switch between the geographic map and the equal-seats cartogram. Tap a
    constituency to open its detailed result.
  </p>
  <ElectionTimeSlider
    stops={slider_stops}
    selectedEventId={selectedEvent.event_id}
    onSelect={onSelectEvent}
  />
  <ElectionFilterRail
    {filters}
    parties={party_options}
    coverage={mode_coverage}
    onChange={onFilterChange}
  />
  <ElectionMap
    state={state_code}
    rows={ac_winners}
    event={selectedEvent.event_id}
    {filters}
  />
</section>
