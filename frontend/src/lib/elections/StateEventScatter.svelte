<!--
  StateEventScatter - extracted from StateElection.svelte during R3
  (Beck two-hat: pure structural extraction, no behaviour change) of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).

  Renders the "Turnout vs winning margin · {state_name} constituencies"
  scatter chart that previously lived inline on the state-event route.

  The body filter chip is initialised to match the URL's body once on
  first paint then left to the citizen; lock_body={true} hides the Body
  toggle UI because the surface is single-body fixed by the URL.

  Props match the data the inline mount consumed; the parent route
  passes `winners` (already pre-filtered to the state by the W2b loader)
  + `body` (active "ac" | "pc") + `state_name` (for the H2) + `params`
  (for the click navigation builder).

  Preserves data-testid: state-event-scatter.
-->
<script lang="ts">
  import Scatter from "../charts/Scatter.svelte";
  import type {
    ScatterDatum,
    ScatterFilters,
  } from "../charts/scatter-model";
  import { link } from "../links";
  import { slugify } from "../slug";
  import { navigate } from "../url";
  import type { ElectionResultRow } from "../view-models/election-results";

  interface Props {
    winners: readonly ElectionResultRow[];
    /** Active body for this surface; null when the catalogue row has
     * not resolved (the parent gates this mount behind `event_row` but
     * Svelte-check cannot narrow that guard across the component
     * boundary, so we accept null and no-op the body-init effect when
     * absent). */
    body: "ac" | "pc" | null;
    state_name: string;
    /** params.event is used as the fallback event_id when the catalogue
     * row hasn't resolved; mirrors the inline mount's behaviour. */
    fallback_event_id: string;
    /** Explicit event_id from the catalogue row when resolved. The
     * inline mount picked `event_row?.event_id ?? params.event`; we
     * accept both pieces as props to keep the parent's resolve logic
     * unchanged. */
    resolved_event_id?: string;
  }

  let { winners, body, state_name, fallback_event_id, resolved_event_id }: Props
    = $props();

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
    const ev = resolved_event_id ?? fallback_event_id;
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
