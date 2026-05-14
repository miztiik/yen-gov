import { OTHER_CATEGORY_ID, type StackedTrendBar, type StackedTrendCategory, type StackedTrendSegment } from "./types";

export interface RollupConfig {
  coverage_ceiling: number;
  max_named_categories: number;
}

export interface RollupInputBar {
  period_id: string;
  period_label: string;
  order: number;
  kind?: string;
  segments: StackedTrendSegment[];
}

export interface RollupResult {
  named_category_ids: string[];
  bars: StackedTrendBar[];
  other_present: boolean;
}

function totalForBar(segs: StackedTrendSegment[]): number {
  return segs.reduce((acc, s) => acc + (s.availability === "present" && s.value != null ? s.value : 0), 0);
}

function topUntilCeiling(segs: StackedTrendSegment[], ceiling: number, cap: number): Set<string> {
  const total = totalForBar(segs);
  if (total <= 0) return new Set();
  const sorted = segs
    .filter((s) => s.availability === "present" && s.value != null && s.value > 0)
    .slice()
    .sort((a, b) => (b.value as number) - (a.value as number));
  const out = new Set<string>();
  let cum = 0;
  for (const s of sorted) {
    if (out.size >= cap) break;
    out.add(s.category_id);
    cum += s.value as number;
    if (cum / total >= ceiling) break;
  }
  return out;
}

export function applyGlobalUnion(
  bars: RollupInputBar[],
  config: RollupConfig,
): RollupResult {
  const union = new Set<string>();
  for (const b of bars) {
    for (const id of topUntilCeiling(b.segments, config.coverage_ceiling, config.max_named_categories)) {
      union.add(id);
    }
  }

  const cap = config.max_named_categories;
  let namedIds: string[];
  if (union.size <= cap) {
    namedIds = Array.from(union);
  } else {
    const sumByCategory = new Map<string, number>();
    for (const b of bars) {
      for (const s of b.segments) {
        if (!union.has(s.category_id)) continue;
        if (s.availability !== "present" || s.value == null) continue;
        sumByCategory.set(s.category_id, (sumByCategory.get(s.category_id) ?? 0) + s.value);
      }
    }
    namedIds = Array.from(union)
      .sort((a, b) => (sumByCategory.get(b) ?? 0) - (sumByCategory.get(a) ?? 0))
      .slice(0, cap);
  }

  const namedSet = new Set(namedIds);
  let otherPresent = false;

  const outBars: StackedTrendBar[] = bars.map((b) => {
    const named: StackedTrendSegment[] = [];
    let otherValue = 0;
    let otherHasPresent = false;
    const naCarry: StackedTrendSegment[] = [];

    for (const s of b.segments) {
      if (namedSet.has(s.category_id)) {
        named.push(s);
        continue;
      }
      if (s.availability === "not_applicable") {
        naCarry.push(s);
        continue;
      }
      if (s.availability === "present" && s.value != null) {
        otherValue += s.value;
        otherHasPresent = true;
      }
    }

    const segments: StackedTrendSegment[] = [...named];
    if (otherHasPresent && otherValue > 0) {
      segments.push({
        category_id: OTHER_CATEGORY_ID,
        value: otherValue,
        availability: "present",
      });
      otherPresent = true;
    } else if (naCarry.length > 0) {
      segments.push({
        category_id: OTHER_CATEGORY_ID,
        value: null,
        availability: "not_applicable",
      });
    }

    return {
      period_id: b.period_id,
      period_label: b.period_label,
      order: b.order,
      kind: b.kind,
      segments,
    };
  });

  return { named_category_ids: namedIds, bars: outBars, other_present: otherPresent };
}

export function fillNotApplicable(
  bars: RollupInputBar[],
  unionIds: Iterable<string>,
): RollupInputBar[] {
  const ids = new Set(unionIds);
  return bars.map((b) => {
    const present = new Set(b.segments.map((s) => s.category_id));
    const missing: StackedTrendSegment[] = [];
    for (const id of ids) {
      if (!present.has(id)) {
        missing.push({ category_id: id, value: null, availability: "not_applicable" });
      }
    }
    return { ...b, segments: [...b.segments, ...missing] };
  });
}

export function buildCategories(
  named_ids: string[],
  labels: Record<string, string>,
  other_present: boolean,
): StackedTrendCategory[] {
  const cats: StackedTrendCategory[] = named_ids.map((id, i) => ({
    id,
    label: labels[id] ?? id,
    order: i,
  }));
  if (other_present) {
    cats.push({ id: OTHER_CATEGORY_ID, label: "Other", order: 999 });
  }
  return cats;
}
