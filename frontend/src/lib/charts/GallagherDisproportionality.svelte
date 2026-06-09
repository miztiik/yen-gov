<script module lang="ts">
  // GallagherDisproportionality - Least-Squares Index visualisation.
  //
  // Hans Option C carve-out from
  // TODO/20260607-e6-alternate-counting-methods-subplan.md "Hans's
  // carve-out (in-scope for E-series, NOT E6)". Measures the gap
  // between vote share and seat share in the EXISTING FPTP result.
  // Pure MEASUREMENT of the system in place; no counterfactual; no
  // honesty banner needed (Hans verdict: "uses only data we already
  // have; no simulating assumption").
  //
  // The Gallagher (Least-Squares) Index:
  //
  //   G = sqrt(0.5 * SUM over parties of (v_i - s_i)^2)
  //
  //   v_i = party i's vote share in percent (0..100)
  //   s_i = party i's seat share in percent (0..100)
  //
  // Calibration bands (Lijphart 1994; OWID precedent):
  //   G in [0, 5)       very proportional      (Netherlands)
  //   G in [5, 10)      moderately proportional
  //   G in [10, 20)     disproportional        (UK, India FPTP)
  //   G >= 20           very disproportional   (Singapore)
  //
  // Per-party gap is `seat_share - vote_share` (positive =
  // OVER-represented, negative = UNDER-represented). Matches the
  // political-science convention and the "+11.0pp" UI label semantics.
  //
  // Testable surface (per repo vitest doctrine - node-env, no jsdom,
  // no @testing-library/svelte; see Skeleton.test.ts +
  // MapHighlightLegend.test.ts + FacetPanelGrid.test.ts for the
  // precedent): the pure helpers `computeGallagher`,
  // `gallagherQualifier`, `buildGallagherRows`, `formatGapPp` live
  // in this module block. The Svelte instance body below is the thin
  // rendering wrapper; DOM-level assertions are deferred to Playwright.

  import type { SeatAllocation } from "../psephlab/types";

  /** One row in the per-party Gallagher breakdown. */
  export interface GallagherRow {
    party_eci_code: string;
    party_short: string;
    party_id: string;
    brand_colour_hex: string | null;
    brand_colour_confidence: "high" | "medium" | "low" | null;
    vote_share_pct: number;
    seat_share_pct: number;
    /** seat_share_pct - vote_share_pct. Positive = over-represented. */
    gap_pp: number;
  }

  /** Output of `computeGallagher`. */
  export interface GallagherResult {
    /** Gallagher G, rounded to 1 decimal. */
    index: number;
    /** Signed gap (seat_share - vote_share) in percentage points per
     *  `party_eci_code`. Positive = over-represented. */
    per_party_gap_pp: Map<string, number>;
  }

  /** Closed enum of qualifier band labels. ASCII only. */
  export type GallagherQualifier =
    | "very proportional"
    | "moderately proportional"
    | "disproportional"
    | "very disproportional";

  /** Citizen-readable footer note. ASCII only. */
  export const GALLAGHER_FOOTER_NOTE: string =
    "Gallagher index measures how much seat shares diverge from vote shares. " +
    "0 = perfect proportionality. Indian FPTP elections typically score 8-15.";

  /** External reference for the "learn more" anchor. */
  export const GALLAGHER_LEARN_MORE_HREF: string =
    "https://en.wikipedia.org/wiki/Gallagher_index";

  /**
   * Pure math: Gallagher (Least-Squares) Index + per-party gap map.
   *
   * G uses every party in `allocation.by_party`; render-time `top_n`
   * collapsing (see `buildGallagherRows`) never changes the headline
   * value. Returns G = 0 for empty / zero-seat inputs.
   */
  export function computeGallagher(
    allocation: SeatAllocation,
    total_seats: number,
  ): GallagherResult {
    const per_party_gap_pp = new Map<string, number>();
    if (
      total_seats <= 0 ||
      !allocation ||
      !allocation.by_party ||
      allocation.by_party.length === 0
    ) {
      return { index: 0, per_party_gap_pp };
    }

    let sum_sq = 0;
    for (const p of allocation.by_party) {
      const seat_share = (100 * p.seats_won) / total_seats;
      const gap = seat_share - p.vote_share_pct;
      per_party_gap_pp.set(p.party_eci_code, gap);
      sum_sq += gap * gap;
    }
    const raw = Math.sqrt(0.5 * sum_sq);
    return {
      index: Math.round(raw * 10) / 10,
      per_party_gap_pp,
    };
  }

  /** Map a G value to its proportionality qualifier band. */
  export function gallagherQualifier(index: number): GallagherQualifier {
    if (!Number.isFinite(index) || index < 5) return "very proportional";
    if (index < 10) return "moderately proportional";
    if (index < 20) return "disproportional";
    return "very disproportional";
  }

  /** Format a signed gap as "+11.0pp" / "-4.8pp". */
  export function formatGapPp(gap_pp: number): string {
    if (!Number.isFinite(gap_pp)) return "0.0pp";
    const sign = gap_pp >= 0 ? "+" : "";
    return `${sign}${gap_pp.toFixed(1)}pp`;
  }

  /**
   * Build the per-party rows for rendering: keep the top `top_n` (by
   * seat share desc, votes desc, party_short asc), aggregate the
   * remainder into an "Other" row with summed vote_share + seat_share
   * + recomputed gap_pp. `max_share` is the largest single
   * `vote_share_pct` or `seat_share_pct` across all rendered rows,
   * for the renderer to scale every bar against the same scale.
   */
  export function buildGallagherRows(
    allocation: SeatAllocation,
    total_seats: number,
    top_n: number,
  ): {
    rows: GallagherRow[];
    other: GallagherRow | null;
    max_share: number;
  } {
    if (
      total_seats <= 0 ||
      !allocation ||
      !allocation.by_party ||
      allocation.by_party.length === 0
    ) {
      return { rows: [], other: null, max_share: 0 };
    }

    const all: GallagherRow[] = allocation.by_party.map((p) => {
      const seat_share = (100 * p.seats_won) / total_seats;
      return {
        party_eci_code: p.party_eci_code,
        party_short: p.party_short,
        party_id: p.party_id,
        brand_colour_hex: p.brand_colour_hex ?? null,
        brand_colour_confidence: p.brand_colour_confidence ?? null,
        vote_share_pct: p.vote_share_pct,
        seat_share_pct: seat_share,
        gap_pp: seat_share - p.vote_share_pct,
      };
    });
    all.sort(
      (a, b) =>
        b.seat_share_pct - a.seat_share_pct ||
        b.vote_share_pct - a.vote_share_pct ||
        a.party_short.localeCompare(b.party_short),
    );

    const n = Math.max(1, Math.floor(top_n));
    let rows: GallagherRow[] = all;
    let other: GallagherRow | null = null;
    if (all.length > n) {
      rows = all.slice(0, n);
      const tail = all.slice(n);
      const sumVote = tail.reduce((s, r) => s + r.vote_share_pct, 0);
      const sumSeat = tail.reduce((s, r) => s + r.seat_share_pct, 0);
      other = {
        party_eci_code: "OTHER",
        party_short: "Other",
        party_id: "OTHER",
        brand_colour_hex: null,
        brand_colour_confidence: null,
        vote_share_pct: sumVote,
        seat_share_pct: sumSeat,
        gap_pp: sumSeat - sumVote,
      };
    }

    let max_share = 0;
    for (const r of rows) {
      if (r.vote_share_pct > max_share) max_share = r.vote_share_pct;
      if (r.seat_share_pct > max_share) max_share = r.seat_share_pct;
    }
    if (other) {
      if (other.vote_share_pct > max_share) max_share = other.vote_share_pct;
      if (other.seat_share_pct > max_share) max_share = other.seat_share_pct;
    }
    return { rows, other, max_share };
  }
</script>

<script lang="ts">
  // NOTE: `SeatAllocation` is imported in the `<script module>` block
  // above; in Svelte 5 the module-scope imports are visible to the
  // instance script, so we MUST NOT re-import the type here (svelte-check
  // rejects it as "Duplicate identifier 'SeatAllocation'").
  import { partyColourHex } from "../psephlab/colour-bridge";

  interface Props {
    allocation: SeatAllocation;
    total_seats: number;
    /** Named-party row cap before the "Other" collapse. Default 8. */
    top_n?: number;
  }
  let { allocation, total_seats, top_n = 8 }: Props = $props();

  const result = $derived(computeGallagher(allocation, total_seats));
  const qualifier = $derived(gallagherQualifier(result.index));
  const layout = $derived(buildGallagherRows(allocation, total_seats, top_n));

  // The "Other" bucket has no brand colour. Slate-400 matches the same
  // neutral other-renderers use (DumbbellRange missing direction,
  // CategoryBar legendColour fallback).
  const OTHER_FILL = "rgb(148 163 184)";

  function fillFor(row: GallagherRow): string {
    if (row.party_eci_code === "OTHER") return OTHER_FILL;
    return partyColourHex(row);
  }

  function widthPct(value: number, max_share: number): string {
    if (max_share <= 0) return "0%";
    const f = Math.max(0, Math.min(1, value / max_share));
    return `${(f * 100).toFixed(3)}%`;
  }
</script>

<section aria-label="Gallagher disproportionality breakdown" class="space-y-3">
  <div class="flex items-baseline gap-3">
    <div class="text-3xl font-bold tabular-nums">{result.index.toFixed(1)}</div>
    <div class="text-sm text-slate-600">
      Gallagher index
      <span class="text-slate-500">- {qualifier}</span>
    </div>
  </div>
  <div class="text-xs text-slate-500">
    Also called Least-Squares Index
    -
    <a
      href={GALLAGHER_LEARN_MORE_HREF}
      target="_blank"
      rel="noreferrer noopener"
      class="underline"
    >learn more</a>
  </div>

  <ol class="space-y-2 mt-2 list-none p-0">
    {#each layout.rows as r (r.party_eci_code)}
      {@const v_w = widthPct(r.vote_share_pct, layout.max_share)}
      {@const s_w = widthPct(r.seat_share_pct, layout.max_share)}
      {@const fill = fillFor(r)}
      <li class="grid grid-cols-[80px_1fr_64px] items-center gap-2 text-xs">
        <span class="font-medium truncate" title={r.party_short}>{r.party_short}</span>
        <div class="space-y-0.5">
          <div class="h-2 rounded bg-slate-100 relative">
            <span
              class="absolute inset-y-0 left-0 rounded"
              style:width={v_w}
              style:background-color={fill}
              style:opacity="0.55"
              title="vote share"
            ></span>
          </div>
          <div class="h-2 rounded bg-slate-100 relative">
            <span
              class="absolute inset-y-0 left-0 rounded"
              style:width={s_w}
              style:background-color={fill}
              title="seat share"
            ></span>
          </div>
        </div>
        <span
          class="text-right tabular-nums"
          style:color={r.gap_pp >= 0 ? "var(--pos)" : "var(--neg)"}
        >{formatGapPp(r.gap_pp)}</span>
      </li>
    {/each}
    {#if layout.other}
      {@const o = layout.other}
      {@const v_w = widthPct(o.vote_share_pct, layout.max_share)}
      {@const s_w = widthPct(o.seat_share_pct, layout.max_share)}
      <li class="grid grid-cols-[80px_1fr_64px] items-center gap-2 text-xs">
        <span class="font-medium truncate text-slate-600">Other</span>
        <div class="space-y-0.5">
          <div class="h-2 rounded bg-slate-100 relative">
            <span
              class="absolute inset-y-0 left-0 rounded"
              style:width={v_w}
              style:background-color={OTHER_FILL}
              style:opacity="0.55"
              title="vote share"
            ></span>
          </div>
          <div class="h-2 rounded bg-slate-100 relative">
            <span
              class="absolute inset-y-0 left-0 rounded"
              style:width={s_w}
              style:background-color={OTHER_FILL}
              title="seat share"
            ></span>
          </div>
        </div>
        <span
          class="text-right tabular-nums"
          style:color={o.gap_pp >= 0 ? "var(--pos)" : "var(--neg)"}
        >{formatGapPp(o.gap_pp)}</span>
      </li>
    {/if}
  </ol>

  <p class="text-xs text-slate-500 mt-2">{GALLAGHER_FOOTER_NOTE}</p>
</section>
