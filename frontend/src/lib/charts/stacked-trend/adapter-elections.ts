// Elections-to-StackedTrend adapter — turns one state's chronological list
// of result.summary.json artifacts into a StackedTrendModel where each bar
// is one election and each segment is one party.
//
// Pure function. The wrapper component (ElectionSeatsTrend.svelte) is
// responsible for loading the summaries; this module only transforms the
// already-loaded data.

import { applyGlobalUnion, buildCategories, type RollupConfig, type RollupInputBar } from "./rollup";
import { computeHeadline, type HeadlineContext, type HeadlineRule } from "./headline";
import {
  StackedTrendModel,
  type StackedTrendBar,
  type StackedTrendModel as StackedTrendModelT,
} from "./types";

/** Subset of result.summary.json shape this adapter consumes. */
export interface ResultSummaryDoc {
  $schema_version?: string;
  sources: Array<{ url: string; fetched_at: string; name?: string; authority?: string }>;
  election: string;
  state: string;
  body: string;
  total_seats: number;
  totals?: {
    electors?: number;
    votes_polled?: number;
    turnout_pct?: number;
  };
  party_totals: Array<{
    party_short: string;
    seats_contested: number;
    seats_won: number;
    votes: number;
    vote_share_pct: number;
  }>;
}

export type ElectionsValueKind = "seats_won" | "vote_share_pct" | "votes";

export interface ElectionsAdapterOptions {
  value: ElectionsValueKind;
  config: RollupConfig;
  /** Optional party-code labels for the legend. Falls back to party_short. */
  party_labels?: Record<string, string>;
  headline_rule?: HeadlineRule;
  headline_text?: string;
  validate?: boolean;
}

const MONTH_MAP: Record<string, string> = {
  Jan: "01", Feb: "02", Mar: "03", Apr: "04", May: "05", Jun: "06",
  Jul: "07", Aug: "08", Sep: "09", Oct: "10", Nov: "11", Dec: "12",
};

/**
 * Parse an ECI election event id like "AcGenApr2021" into a sortable
 * "YYYY-MM" period_id and a human "Apr 2021" period_label.
 */
export function parseElectionEventId(event_id: string): { period_id: string; period_label: string } {
  const m = event_id.match(/([A-Z][a-z]{2})(\d{4})$/);
  if (!m) return { period_id: event_id, period_label: event_id };
  const [, mon, year] = m;
  const mm = MONTH_MAP[mon] ?? "00";
  return { period_id: `${year}-${mm}`, period_label: `${mon} ${year}` };
}

function valueFor(row: ResultSummaryDoc["party_totals"][number], kind: ElectionsValueKind): number {
  if (kind === "seats_won") return row.seats_won;
  if (kind === "vote_share_pct") return row.vote_share_pct;
  return row.votes;
}

const MAP_VALUE_KIND: Record<ElectionsValueKind, "count" | "share"> = {
  seats_won: "count",
  votes: "count",
  vote_share_pct: "share",
};

const UNIT: Record<ElectionsValueKind, { id: string; label: string }> = {
  seats_won: { id: "seats", label: "seats" },
  votes: { id: "votes", label: "votes" },
  vote_share_pct: { id: "vote_share_pct", label: "% vote share" },
};

export function electionsToStackedTrend(
  summaries: ResultSummaryDoc[],
  opts: ElectionsAdapterOptions,
): StackedTrendModelT {
  if (summaries.length === 0) {
    throw new Error("electionsToStackedTrend: empty summaries array");
  }
  const states = new Set(summaries.map(s => s.state));
  if (states.size > 1) {
    throw new Error(
      `electionsToStackedTrend: all summaries must be for one state; got ${[...states].join(", ")}`,
    );
  }

  const sorted = [...summaries]
    .map(s => ({ summary: s, parsed: parseElectionEventId(s.election) }))
    .sort((a, b) => a.parsed.period_id.localeCompare(b.parsed.period_id));

  const inputBars: RollupInputBar[] = sorted.map(({ summary, parsed }, i) => ({
    period_id: parsed.period_id,
    period_label: parsed.period_label,
    order: i,
    segments: summary.party_totals.map(p => ({
      category_id: p.party_short,
      value: valueFor(p, opts.value),
      availability: "present" as const,
    })),
  }));

  const rolled = applyGlobalUnion(inputBars, opts.config);
  const categories = buildCategories(
    rolled.named_category_ids,
    opts.party_labels ?? {},
    rolled.other_present,
  );

  const value_kind = MAP_VALUE_KIND[opts.value];
  const unit = UNIT[opts.value];

  const headlineCtx: HeadlineContext = {
    entity_label: sorted[0].summary.state,
    category_labels: opts.party_labels ?? {},
    value_kind,
    unit_label: unit.label,
  };

  const headlineRule: HeadlineRule = opts.headline_rule ?? "max_latest_with_streak";
  const headline =
    opts.headline_text != null
      ? { rule: "designated" as const, text: opts.headline_text }
      : computeHeadline(headlineRule, rolled.bars, headlineCtx);

  const bars: StackedTrendBar[] = rolled.bars
    .slice()
    .sort((a, b) => a.order - b.order);

  // Union sources from every contributing summary; dedupe by URL.
  const seen = new Set<string>();
  const sources: ResultSummaryDoc["sources"] = [];
  for (const s of summaries) {
    for (const src of s.sources) {
      const key = `${src.url}|${src.fetched_at}`;
      if (seen.has(key)) continue;
      seen.add(key);
      sources.push(src);
    }
  }

  const model: StackedTrendModelT = StackedTrendModel.parse({
    unit: { id: unit.id, label: unit.label, value_kind },
    x_axis_label: "Election",
    bar_sort: "by_order_ascending",
    categories,
    bars,
    headline,
    honesty: {
      methodology_vintage: "ECI Form 21 (per-election)",
      notes:
        "Seats are first-past-the-post outcomes; vote-share movements do " +
        "not always translate to seat-share movements at this scale.",
    },
    sources,
    dimension: "party",
    default_mode: opts.value === "vote_share_pct" ? "absolute" : "absolute",
  });

  if (opts.validate ?? true) {
    StackedTrendModel.parse(model);
  }
  return model;
}
