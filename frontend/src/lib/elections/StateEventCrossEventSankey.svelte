<!--
  StateEventCrossEventSankey - FACTUAL seat-flow (gap-closure G5,
  TODO/20260616-state-event-page-gap-closure-plan.md).

  REPLACES the prior vote-flow APPROXIMATION. The user asked for the exact
  hold/loss matrix: "for a given constituency a party either holds or
  loses to another, so we can sum up across parties". This component joins
  the current + prior winners on entity_id (one seat = one prior winner +
  one current winner), aggregates the (prev -> curr) transitions, and
  draws a true bipartite Sankey: left column = prior winners, right column
  = current winners, ribbon width = NUMBER OF SEATS (not votes, not an
  estimate). A party that held its seat is a self-loop drawn straight
  across; a flip is a cross-ribbon coloured by the party it came from.

  Always-on headline (holds / flips / new) so the citizen gets the story
  even without expanding the diagram. The Sankey is collapsed by default
  behind a "Show seat flow" pill. Caption is FACTUAL - no "approximate" /
  "estimate" language.

  No-prior: the first event of a body for a state has nothing to flow
  from; the section renders the no-prior copy with no button.
-->
<script lang="ts">
  import {
    buildSeatFlowModel,
    type SeatFlowNode,
    type PrevWinnersState,
  } from "./seat-flow-model";
  import type { ElectionResultRow } from "../view-models/election-results";
  import {
    getPartyColor,
    type PartyRowForResolver,
  } from "../colors/resolver";

  interface Props {
    /** Current event's winners (already loaded by the parent). */
    current_winners: readonly ElectionResultRow[];
    /** Prev same-body event's winners as a loader state. */
    prev_winners: PrevWinnersState;
    /** Human-readable label of the prior event (e.g. "Assembly 2019"). */
    prev_event_label: string | null;
    /** Human-readable label of the current event (e.g. "Assembly 2024"). */
    current_event_label: string;
    /** Body discriminator ("Assembly" / "Parliament") for no-prior copy. */
    body_pretty: string;
    /** State name for the no-prior copy. */
    state_name: string;
  }

  let {
    current_winners,
    prev_winners,
    prev_event_label,
    current_event_label,
    body_pretty,
    state_name,
  }: Props = $props();

  let expanded = $state(false);

  const model = $derived.by(() => {
    if (prev_winners.status === "ok") {
      return buildSeatFlowModel({
        current: current_winners,
        previous: prev_winners.rows,
      });
    }
    if (prev_winners.status === "no_prior") {
      return buildSeatFlowModel({ current: current_winners, previous: null });
    }
    return null; // loading / failed
  });

  // ---- Colour resolution -------------------------------------------------
  // The model stays pure (no colour). Resolve each party's brand colour
  // here off the winner rows we already hold, keyed by canonical party_id.
  const colour_by_pid = $derived.by(() => {
    const map = new Map<string, string>();
    const rows: readonly ElectionResultRow[] =
      prev_winners.status === "ok"
        ? [...current_winners, ...prev_winners.rows]
        : current_winners;
    for (const w of rows) {
      const pid =
        w.party_id ?? `parties.IN.${(w.party_short ?? "UNK").toUpperCase()}`;
      if (map.has(pid)) continue;
      const row: PartyRowForResolver | null = w.brand_colour_hex
        ? {
            party_id: pid,
            eci_code: w.party_eci_code,
            brand_colour: {
              hex: w.brand_colour_hex,
              confidence: w.brand_colour_confidence ?? "medium",
            },
          }
        : null;
      map.set(pid, getPartyColor(pid, row).hex);
    }
    return map;
  });

  function nodeColour(n: SeatFlowNode): string {
    if (n.is_bucket) return n.key === "__new__" ? "#cbd5e1" : "#94a3b8";
    return colour_by_pid.get(n.party_id ?? "") ?? "#94a3b8";
  }

  // ---- Layout ------------------------------------------------------------
  const W = 620;
  const H = 380;
  const PAD_Y = 10;
  const COL_W = 14;
  const LEFT_X = 92;
  const RIGHT_X = W - 92 - COL_W;

  interface Band {
    key: string;
    label: string;
    seats: number;
    colour: string;
    y: number;
    h: number;
    used: number;
  }

  interface Ribbon {
    path: string;
    colour: string;
    from_label: string;
    to_label: string;
    seats: number;
    is_hold: boolean;
  }

  function stack(nodes: SeatFlowNode[], total: number): Band[] {
    const usable = H - 2 * PAD_Y;
    const out: Band[] = [];
    let y = PAD_Y;
    for (const n of nodes) {
      const h = total > 0 ? (n.seats / total) * usable : 0;
      out.push({
        key: n.key,
        label: n.label,
        seats: n.seats,
        colour: nodeColour(n),
        y,
        h,
        used: 0,
      });
      y += h + 2;
    }
    return out;
  }

  function ribbonPath(
    y_l_top: number,
    y_l_bot: number,
    y_r_top: number,
    y_r_bot: number,
  ): string {
    const x1 = LEFT_X + COL_W;
    const x2 = RIGHT_X;
    const cx = x1 + (x2 - x1) * 0.5;
    return [
      `M ${x1} ${y_l_top}`,
      `C ${cx} ${y_l_top}, ${cx} ${y_r_top}, ${x2} ${y_r_top}`,
      `L ${x2} ${y_r_bot}`,
      `C ${cx} ${y_r_bot}, ${cx} ${y_l_bot}, ${x1} ${y_l_bot}`,
      "Z",
    ].join(" ");
  }

  const layout = $derived.by(() => {
    if (!model || model.no_prior || model.total_seats === 0) {
      return { left: [] as Band[], right: [] as Band[], ribbons: [] as Ribbon[] };
    }
    const total = model.total_seats;
    const left = stack(model.left, total);
    const right = stack(model.right, total);
    const leftBy = new Map(left.map((b) => [b.key, b]));
    const rightBy = new Map(right.map((b) => [b.key, b]));
    const leftIdx = new Map(left.map((b, i) => [b.key, i]));
    const rightIdx = new Map(right.map((b, i) => [b.key, i]));
    const usable = H - 2 * PAD_Y;

    // Order ribbons by (left band position, right band position) so they
    // stack within each band without crossing more than necessary.
    const ordered = [...model.flows].sort((a, b) => {
      const la = leftIdx.get(a.from_key) ?? 99;
      const lb = leftIdx.get(b.from_key) ?? 99;
      if (la !== lb) return la - lb;
      const ra = rightIdx.get(a.to_key) ?? 99;
      const rb = rightIdx.get(b.to_key) ?? 99;
      return ra - rb;
    });

    const ribbons: Ribbon[] = [];
    for (const f of ordered) {
      const lb = leftBy.get(f.from_key);
      const rb = rightBy.get(f.to_key);
      if (!lb || !rb) continue;
      const h = (f.seats / total) * usable;
      const y_l_top = lb.y + lb.used;
      const y_r_top = rb.y + rb.used;
      lb.used += h;
      rb.used += h;
      ribbons.push({
        path: ribbonPath(y_l_top, y_l_top + h, y_r_top, y_r_top + h),
        colour: lb.colour,
        from_label: lb.label,
        to_label: rb.label,
        seats: f.seats,
        is_hold: f.is_hold,
      });
    }
    return { left, right, ribbons };
  });

  let hover_idx = $state<number | null>(null);
</script>

<section class="space-y-2" data-testid="state-event-seat-flow">
  <h2 class="text-sm font-medium text-slate-700">
    Seat flow: where each seat moved
  </h2>

  {#if prev_winners.status === "loading"}
    <div
      class="h-24 animate-pulse rounded bg-slate-50 ring-1 ring-slate-200/70"
      data-testid="state-event-seat-flow-loading"
    ></div>
  {:else if prev_winners.status === "failed"}
    <p class="text-xs text-slate-500">
      Seat-flow comparison data could not load: {prev_winners.reason}
    </p>
  {:else if !model || model.no_prior}
    <p
      class="text-xs text-slate-500"
      data-testid="state-event-seat-flow-no-prior"
    >
      Seat-flow needs a prior election; this is the first {body_pretty}
      event on record for {state_name}.
    </p>
  {:else}
    <!-- Always-on factual headline. -->
    <p
      class="text-sm text-slate-700"
      data-testid="state-event-seat-flow-headline"
    >
      <span class="font-semibold tabular-nums">{model.holds}</span> held &middot;
      <span class="font-semibold tabular-nums">{model.flips}</span> flipped
      {#if model.unmatched > 0}
        &middot;
        <span class="font-semibold tabular-nums">{model.unmatched}</span>
        new / redrawn
      {/if}
      <span class="text-slate-400">of {model.total_seats} seats</span>
    </p>

    <button
      type="button"
      class="inline-flex items-center gap-1 rounded-yen-pill border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
      data-testid="state-event-seat-flow-toggle"
      aria-expanded={expanded}
      onclick={() => (expanded = !expanded)}
    >{expanded ? "Hide seat flow" : "Show seat flow"}</button>

    {#if expanded}
      <div class="mt-2" data-testid="state-event-seat-flow-diagram">
        <div
          class="flex items-center justify-between text-[11px] font-medium uppercase tracking-wide text-slate-500"
        >
          <span>{prev_event_label ?? "Previous"}</span>
          <span>{current_event_label}</span>
        </div>
        <svg
          viewBox="0 0 {W} {H}"
          class="h-auto w-full"
          role="img"
          aria-label="Seat flow from the previous election to this one"
        >
          {#each layout.ribbons as r, i (i)}
            <path
              d={r.path}
              fill={r.colour}
              opacity={hover_idx === null
                ? r.is_hold
                  ? 0.45
                  : 0.3
                : hover_idx === i
                  ? 0.8
                  : 0.12}
              onmouseenter={() => (hover_idx = i)}
              onmouseleave={() => (hover_idx = null)}
            >
              <title
                >{r.from_label} &rarr; {r.to_label}: {r.seats} seat{r.seats === 1
                  ? ""
                  : "s"}{r.is_hold ? " (held)" : ""}</title
              >
            </path>
          {/each}

          {#each layout.left as b (b.key)}
            <rect
              x={LEFT_X}
              y={b.y}
              width={COL_W}
              height={Math.max(1, b.h)}
              fill={b.colour}
            />
            <text
              x={LEFT_X - 6}
              y={b.y + b.h / 2}
              text-anchor="end"
              dominant-baseline="middle"
              font-size="11"
              fill="#0f172a">{b.label}</text
            >
            <text
              x={LEFT_X - 6}
              y={b.y + b.h / 2 + 12}
              text-anchor="end"
              dominant-baseline="middle"
              font-size="9"
              fill="#64748b">{b.seats}</text
            >
          {/each}

          {#each layout.right as b (b.key)}
            <rect
              x={RIGHT_X}
              y={b.y}
              width={COL_W}
              height={Math.max(1, b.h)}
              fill={b.colour}
            />
            <text
              x={RIGHT_X + COL_W + 6}
              y={b.y + b.h / 2}
              text-anchor="start"
              dominant-baseline="middle"
              font-size="11"
              fill="#0f172a">{b.label}</text
            >
            <text
              x={RIGHT_X + COL_W + 6}
              y={b.y + b.h / 2 + 12}
              text-anchor="start"
              dominant-baseline="middle"
              font-size="9"
              fill="#64748b">{b.seats}</text
            >
          {/each}
        </svg>
        <p
          class="mt-1 text-[11px] italic text-slate-500"
          data-testid="state-event-seat-flow-caption"
        >
          Each constituency's seat moved from its {prev_event_label ?? "prior"}
          winner to its {current_event_label} winner. Ribbon width = number of
          seats; a ribbon that returns to the same party is a hold.
        </p>
      </div>
    {/if}
  {/if}
</section>
