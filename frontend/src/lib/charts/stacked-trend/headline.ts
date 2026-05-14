import type { StackedTrendBar, StackedTrendHeadline } from "./types";
import { OTHER_CATEGORY_ID } from "./types";

export type HeadlineRule = "max_latest_with_streak" | "designated" | "max_lifetime" | "none";

export interface HeadlineContext {
  entity_label: string;
  category_labels: Record<string, string>;
  value_kind: "count" | "currency" | "rate" | "share" | "raw";
  unit_label: string;
  direction?: "higher_is_better" | "lower_is_better" | "neutral";
}

function categoryLabel(ctx: HeadlineContext, id: string): string {
  return ctx.category_labels[id] ?? id;
}

function presentTotal(b: StackedTrendBar): number {
  return b.segments.reduce((acc, s) => (s.availability === "present" && s.value != null ? acc + s.value : acc), 0);
}

function presentValue(b: StackedTrendBar, category_id: string): number | null {
  const seg = b.segments.find((s) => s.category_id === category_id);
  if (!seg || seg.availability !== "present" || seg.value == null) return null;
  return seg.value;
}

function leaderInBar(b: StackedTrendBar): string | null {
  let bestId: string | null = null;
  let bestVal = -Infinity;
  for (const s of b.segments) {
    if (s.category_id === OTHER_CATEGORY_ID) continue;
    if (s.availability !== "present" || s.value == null) continue;
    if (s.value > bestVal) {
      bestVal = s.value;
      bestId = s.category_id;
    }
  }
  return bestId;
}

function fmtPct(v: number, digits = 0): string {
  return `${(v * 100).toFixed(digits)}%`;
}

function fmtCompact(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  return `${v}`;
}

function fmtMW(v: number): string {
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)} GW`;
  return `${v.toFixed(0)} MW`;
}

export function maxLatestWithStreak(bars: StackedTrendBar[], ctx: HeadlineContext): StackedTrendHeadline {
  if (bars.length < 3) return { rule: "none", text: "" };
  const sorted = bars.slice().sort((a, b) => a.order - b.order);
  const latest = sorted[sorted.length - 1];
  const winner = leaderInBar(latest);
  if (!winner) return { rule: "none", text: "" };

  let wins = 0;
  for (const b of sorted) if (leaderInBar(b) === winner) wins++;
  let streak = 0;
  for (let i = sorted.length - 1; i >= 0; i--) {
    if (leaderInBar(sorted[i]) === winner) streak++;
    else break;
  }

  if (!(wins >= 4 || streak >= 3)) return { rule: "none", text: "" };

  const label = categoryLabel(ctx, winner);
  const text =
    wins >= 4
      ? `${label} won ${ctx.entity_label} in ${wins} of the last ${sorted.length} elections`
      : `${label} has won ${ctx.entity_label} ${streak} elections in a row`;

  const so_what = soWhat(sorted, winner, ctx);
  return { rule: "max_latest_with_streak", text, so_what, highlight_category_id: winner };
}

function soWhat(sorted: StackedTrendBar[], category_id: string, ctx: HeadlineContext): string {
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const firstTotal = presentTotal(first);
  const lastTotal = presentTotal(last);
  const firstVal = presentValue(first, category_id);
  const lastVal = presentValue(last, category_id);
  if (firstVal == null || lastVal == null || firstTotal === 0 || lastTotal === 0) return "";

  const firstShare = firstVal / firstTotal;
  const lastShare = lastVal / lastTotal;
  const ppDelta = (lastShare - firstShare) * 100;
  const label = categoryLabel(ctx, category_id);
  const span = `${sorted.length} ${ctx.entity_label.toLowerCase().includes("election") ? "" : "periods"}`.trim();
  const periods = sorted.length;

  switch (ctx.value_kind) {
    case "share":
      return `${label}: ${fmtPct(firstShare)} → ${fmtPct(lastShare)} (${ppDelta >= 0 ? "+" : ""}${ppDelta.toFixed(0)}pp over ${periods} periods)`;
    case "count": {
      const pctDelta = ((lastVal - firstVal) / Math.max(firstVal, 1)) * 100;
      return `${label}: ${fmtCompact(firstVal)} → ${fmtCompact(lastVal)} (${pctDelta >= 0 ? "+" : ""}${pctDelta.toFixed(0)}% over ${periods} periods)`;
    }
    case "currency":
      return `${label}: ${ctx.unit_label} ${fmtCompact(firstVal)} → ${fmtCompact(lastVal)} over ${periods} periods`;
    case "raw":
      if (ctx.unit_label.toUpperCase() === "MW") {
        return `${label}: ${fmtMW(firstVal)} → ${fmtMW(lastVal)} over ${periods} periods`;
      }
      return `${label}: ${fmtCompact(firstVal)} ${ctx.unit_label} → ${fmtCompact(lastVal)} ${ctx.unit_label}`;
    default:
      return `${label}: ${fmtCompact(firstVal)} → ${fmtCompact(lastVal)}`;
  }
}

export function maxLifetime(bars: StackedTrendBar[], ctx: HeadlineContext, threshold = 0.6): StackedTrendHeadline {
  const totals = new Map<string, number>();
  let grand = 0;
  for (const b of bars) {
    for (const s of b.segments) {
      if (s.category_id === OTHER_CATEGORY_ID) continue;
      if (s.availability !== "present" || s.value == null) continue;
      totals.set(s.category_id, (totals.get(s.category_id) ?? 0) + s.value);
      grand += s.value;
    }
  }
  if (grand === 0) return { rule: "none", text: "" };
  let bestId: string | null = null;
  let bestVal = 0;
  for (const [id, v] of totals) {
    if (v > bestVal) {
      bestVal = v;
      bestId = id;
    }
  }
  if (!bestId) return { rule: "none", text: "" };
  const share = bestVal / grand;
  if (share < threshold) return { rule: "none", text: "" };
  return {
    rule: "max_lifetime",
    text: `${categoryLabel(ctx, bestId)} accounts for ${fmtPct(share)} of ${ctx.entity_label}'s ${ctx.unit_label}`,
    highlight_category_id: bestId,
  };
}

export function designated(text: string, category_id?: string): StackedTrendHeadline {
  return { rule: "designated", text, highlight_category_id: category_id };
}

export function none(): StackedTrendHeadline {
  return { rule: "none", text: "" };
}

export function computeHeadline(
  rule: HeadlineRule,
  bars: StackedTrendBar[],
  ctx: HeadlineContext,
): StackedTrendHeadline {
  switch (rule) {
    case "max_latest_with_streak":
      return maxLatestWithStreak(bars, ctx);
    case "max_lifetime":
      return maxLifetime(bars, ctx);
    case "none":
      return none();
    case "designated":
      return none();
  }
}
