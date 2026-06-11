// CompositionBar — elections (party seats won) adapter (Phase 3.6 (b)).
//
// Per docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md Phase 3.6
// (b). Turns one `(state, election_event)` pair into a typed
// CompositionBarModel by JOINing `elections.election_results` +
// `elections.dim_parties` + `taxonomy.sources` via the manifest-
// registered `table_id`s. R-28 discipline: no hardcoded parquet path.
//
// Module shape mirrors `frontend/src/lib/view-models/election-seats-trend.ts`:
//
//   - `runQueries`               — async DuckDB-WASM SQL with
//                                   manifest registration (R-28 contract).
//   - `assembleCompositionBar`   — pure transformer (exported for
//                                   vitest; takes already-loaded rows
//                                   and emits a CompositionBarModel).
//   - `loadCompositionBarElectionSeats` — async entry; returns a
//                                   `LoaderResult<CompositionBarModel>`.
//
// Doctrine ties:
//
//   - R-08 Branch by Abstraction. SeatDonut / ParliamentArc /
//     AcStackedBar continue to ship; this adapter feeds CompositionBar
//     (Phase 3.6 (a)) which mounts alongside in Phase 3.6 (c).
//
//   - R-16 three-PR split. This is the (b) slice: adapter +
//     GrowthBook experiment definition. The renderer ships in (a); the
//     mount + Playwright in (c).
//
//   - R-24 / R-28. The publisher-pill projection is JOINed against
//     `taxonomy.sources` by `source_id`. No fetch telemetry, no
//     hardcoded parquet path literal.
//
//   - Plan line 1316: "Input: `party-seats-won` rows for one
//     `(state, election_event)` pair from the canonical store." —
//     `runQueries` filters on `indicator_id = 'party-seats-won'` and
//     `period_label = <event>` and `entity_id LIKE 'IN-<state>-...'`.
//
//   - Plan line 1318: "NOTA: render NOTA as its own swatch with the
//     existing NOTA colour anchor; for elections older than 2013 NOTA
//     is null and the segment is absent." — implemented by treating
//     the `NOTA` party-key as a regular party row from the rollup,
//     with the existing `ANCHORS["NOTA"]` swatch applied by
//     `partyColour`.
//
//   - Plan line 1319: "Party palette: source fills from the existing
//     party-colour anchor system." — every segment fill comes from
//     `partyColour(party_eci_code, in_use_codes)`.
//
//   - Plan line 1320: "Caption / framing: the FPTP doctrine footnote
//     already used by `adapter-elections.ts` line 165 is the
//     canonical wording for FPTP context; reuse the exact string."
//     — `CAPTION_FPTP` constant below is the verbatim copy.
//
//   - Plan resolution R-02: single-party-dominant fixture and mount
//     state because TN is alliance-led; party-only chart would
//     misframe it.

import { describeFailure, type LoaderResult } from "../../loader-result";
import { query, registerCsvAsTable, registerCsvFile } from "../../duckdb";
import {
  ELECTION_RESULTS_COLUMNS_CLAUSE,
  electionResultsCsvUrl,
  electionResultsStateSlug,
} from "../../canonical/election-results-csv";
import { getPartyColor, type PartyRowForResolver } from "../../colors/resolver";
import { dedupeToPills, type PublisherPill, type SourceRow } from "../../sources";
import type {
  CompositionBarModel,
  CompositionBarSegment,
} from "./types";
import { CompositionBarModel as CompositionBarModelSchema } from "./types";

/**
 * FPTP doctrine footnote — verbatim from
 * `frontend/src/lib/charts/stacked-trend/adapter-elections.ts`
 * `honesty.notes` (line ~156). Plan line 1320 requires the exact
 * string; do NOT paraphrase. If the upstream changes, this constant
 * must change in lockstep (caught by `adapter-elections-seats.test.ts`).
 */
export const CAPTION_FPTP =
  "Seats are first-past-the-post outcomes; vote-share movements do " +
  "not always translate to seat-share movements at this scale.";

/**
 * Top-N cap for the bar. Anything beyond the top N parties by seats
 * rolls into a visible "Others" tail segment. Plan line 1310 forbids
 * collapsing the tail into a footnote — `Others` renders as a visible
 * swatch with its own label.
 *
 * 8 chosen to match the cutoff already used by `SeatDonut` (see plan
 * line 1317 "reuse the existing helper that already feeds SeatDonut
 * for top-N candidate handling").
 */
export const DEFAULT_TOP_N = 8;

/**
 * Anchor swatch for the tail aggregate. Slate-300; chosen to be
 * distinct from the NOTA swatch (slate-500) so a citizen can tell
 * "Others" apart from "NOTA" at a glance.
 */
const OTHERS_FILL = "#cbd5e1";

/**
 * Anchor swatch for Independent (IND) when neither dim_parties nor
 * the anchors module supplies an iconic colour. Slate-400 keeps it
 * visually-distinct from Others (slate-300) and NOTA (slate-500)
 * without competing with the actual party palette.
 */
const IND_FILL = "#94a3b8";

export interface CompositionBarPartyRow {
  party_eci_code: string | null;
  party_short: string;
  party_full: string | null;
  seats_won: number;
  /** PR-SYM-6f5: canonical `parties.IN.<SLUG>` from dim_parties LEFT JOIN.
   *  Null when the JOIN missed (party not in taxonomy yet); resolver
   *  derives a fallback id from party_short. */
  party_id: string | null;
  /** PR-SYM-6f5: brand-colour mirror from dim_parties v1.1. */
  brand_colour_hex: string | null;
  brand_colour_confidence: "high" | "medium" | "low" | null;
}

export interface CompositionBarSourceJoinRow {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  url: string | null;
}

export interface CompositionBarLoadedRows {
  parties: CompositionBarPartyRow[];
  sources: CompositionBarSourceJoinRow[];
  total_seats: number;
}

interface PartyRow {
  party_short: string;
  party_full: string | null;
  eci_code: string | null;
  seats_won: number | null;
  party_id: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
}

interface SourceJoinRow {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  url: string | null;
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

const num = (v: unknown): number => (v == null ? 0 : Number(v));

/**
 * DuckDB-WASM SQL — JOIN election_results CSV + dim_parties + sources
 * for one (state, event). X1a-fu2-D (2026-06-07): the legacy
 * `elections.election_results` parquet shard was retired and replaced
 * with one CSV per state under
 * `datasets/data/datapoints/electoral/<slug>_election_results.csv`;
 * this loader now reads via inline `read_csv(<url>, columns={...})`
 * keyed by the (state, event) pair. JOIN against dim_parties + sources
 * is unchanged (both already CSV-as-table views via X1a).
 */
async function runQueries(
  state_code: string,
  event_id: string,
): Promise<CompositionBarLoadedRows> {
  const stateSlug = electionResultsStateSlug(state_code);
  const csvUrl = electionResultsCsvUrl(stateSlug);
  await Promise.all([
    registerCsvFile(csvUrl),
    registerCsvAsTable("elections.dim_parties"),
    registerCsvAsTable("taxonomy.sources"),
  ]);

  const partyPrefix = sqlString(`IN-${state_code}-`);
  const eventLit = sqlString(event_id);
  const csvLit = sqlString(csvUrl);

  const partySql = `
    SELECT
      regexp_extract(o.entity_id, '-PARTY-(.+)$', 1) AS party_short,
      dp.full_name                                   AS party_full,
      dp.eci_code                                    AS eci_code,
      dp.party_id                                    AS party_id,
      dp.brand_colour_hex                            AS brand_colour_hex,
      dp.brand_colour_confidence                     AS brand_colour_confidence,
      o.value_numeric                                AS seats_won
    FROM read_csv(${csvLit}, ${ELECTION_RESULTS_COLUMNS_CLAUSE}, header=true) o
    LEFT JOIN dim_parties dp
      ON dp.short_name = regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)
    WHERE o.entity_id LIKE ${partyPrefix} || '%-PARTY-%'
      AND o.period_label = ${eventLit}
      AND o.indicator_id = 'party-seats-won'
  `;
  const rows = await query<PartyRow>(partySql);
  const parties: CompositionBarPartyRow[] = rows.map(r => ({
    party_eci_code: r.eci_code ?? null,
    party_short: r.party_short,
    party_full: r.party_full ?? null,
    seats_won: num(r.seats_won),
    party_id: r.party_id ?? null,
    brand_colour_hex: r.brand_colour_hex ?? null,
    brand_colour_confidence:
      r.brand_colour_confidence === "high" ||
      r.brand_colour_confidence === "medium" ||
      r.brand_colour_confidence === "low"
        ? r.brand_colour_confidence
        : null,
  }));

  const sources = await query<SourceJoinRow>(`
    SELECT DISTINCT
      s.source_id          AS source_id,
      s.producer           AS producer,
      s.title              AS title,
      s.vintage            AS vintage,
      s.url                AS url
    FROM read_csv(${csvLit}, ${ELECTION_RESULTS_COLUMNS_CLAUSE}, header=true) o
    JOIN sources s ON s.source_id = o.source_id
    WHERE o.period_label = ${eventLit}
      AND o.indicator_id = 'party-seats-won'
      AND o.entity_id LIKE ${partyPrefix} || '%'
    ORDER BY s.source_id
  `);

  const total_seats = parties.reduce((sum, p) => sum + p.seats_won, 0);
  return { parties, sources: sources.map(s => ({ ...s })), total_seats };
}

/**
 * Sort by seats descending then by short_name ascending (stable
 * tie-break). Pure; exported for vitest.
 */
export function sortPartiesBySeats(
  parties: readonly CompositionBarPartyRow[],
): readonly CompositionBarPartyRow[] {
  return [...parties].sort((a, b) => {
    if (b.seats_won !== a.seats_won) return b.seats_won - a.seats_won;
    return a.party_short.localeCompare(b.party_short);
  });
}

/**
 * Top-N + tail aggregation. Keeps the top N by seats; collapses the
 * rest into a single "Others" row. The tail's `party_eci_code` is
 * `null` and `party_short` is `OTHERS` so the renderer can paint it
 * with the OTHERS_FILL swatch.
 *
 * Edge cases (per plan line 1338 "Unit: top-N + tail helper against
 * fixtures with N=2, N=5, N=8 segments and a single-party degenerate
 * case"):
 *
 *   - parties.length === 0       → returns [].
 *   - parties.length === 1       → returns the single row; no tail.
 *   - parties.length <= top_n    → returns all rows; no tail.
 *   - parties.length === top_n+1 → returns all rows; no tail (avoid
 *                                  a single-item "Others" — degrades
 *                                  to the original row).
 *   - parties.length >  top_n+1  → returns top N + an aggregated
 *                                  "Others" row carrying the sum of
 *                                  the rest.
 */
export function reduceToTopNWithTail(
  parties: readonly CompositionBarPartyRow[],
  top_n: number = DEFAULT_TOP_N,
): readonly CompositionBarPartyRow[] {
  if (parties.length === 0) return [];
  const sorted = sortPartiesBySeats(parties);
  if (sorted.length <= top_n + 1) return sorted;
  const head = sorted.slice(0, top_n);
  const tail = sorted.slice(top_n);
  const tailSeats = tail.reduce((s, p) => s + p.seats_won, 0);
  if (tailSeats === 0) return head;
  return [
    ...head,
    {
      party_eci_code: null,
      party_short: "OTHERS",
      party_full: "Others",
      seats_won: tailSeats,
      party_id: null,
      brand_colour_hex: null,
      brand_colour_confidence: null,
    },
  ];
}

/**
 * Derive the canonical `parties.IN.<SLUG>` id when the dim_parties JOIN
 * missed (party absent from taxonomy). Mirrors the SeatDonut helper from
 * PR-SYM-6f1 so the resolver gets a stable key for anchor / fallback.
 */
function partyIdFor(party: CompositionBarPartyRow): string {
  if (party.party_id) return party.party_id;
  return `parties.IN.${party.party_short.toUpperCase()}`;
}

/**
 * Resolve a party fill. Lookup order:
 *
 *   1. `OTHERS` -> `OTHERS_FILL` (tail aggregate).
 *   2. `IND` / `Independent` -> `IND_FILL`.
 *   3. `getPartyColor(party_id, row)` (PR-SYM-6f5) - resolver's
 *      anchor / brand / algorithmic-fallback cascade. NOTA lands on
 *      the curated `parties.IN.NOTA` anchor automatically.
 *
 * The `in_use_codes` argument is retained for back-compat with the
 * earlier `partyColour` API but is unused; the resolver does not
 * de-dupe algorithmic slots (per resolver.ts contract).
 */
export function resolvePartyFill(
  party: CompositionBarPartyRow,
  _in_use_codes: readonly string[] = [],
): string {
  if (party.party_short === "OTHERS") return OTHERS_FILL;
  if (party.party_short === "IND" || party.party_short === "INDEPENDENT") {
    return IND_FILL;
  }
  const pid = partyIdFor(party);
  const row: PartyRowForResolver = {
    party_id: pid,
    eci_code: party.party_eci_code,
    brand_colour:
      party.brand_colour_hex && party.brand_colour_confidence
        ? {
            hex: party.brand_colour_hex,
            confidence: party.brand_colour_confidence,
          }
        : null,
  };
  return getPartyColor(pid, row).hex;
}

export interface AssembleOptions {
  state_label: string;
  event_label: string;
  total_seats_override?: number;
  top_n?: number;
  honesty_extra?: { kind: "comparability" | "series_break" | "unit_change" | "vintage" | "missing_data" | "note"; text: string }[];
}

/**
 * Pure transformer — takes loaded rows + UX options, returns a
 * validated CompositionBarModel. Exported for vitest; the loader
 * `loadCompositionBarElectionSeats` wraps this with the async fetch
 * + LoaderResult arms.
 *
 * The denominator (`total_value`) defaults to the sum of seats across
 * ALL party rows (NOT the top-N + tail aggregate; the tail is a
 * recomposition so the sum is identical). Caller can override with
 * `total_seats_override` for cases where the canonical chamber size
 * (e.g. 182 for Gujarat) differs from the rows present in the parquet
 * (rare; defensive).
 */
export function assembleCompositionBar(
  rows: CompositionBarLoadedRows,
  opts: AssembleOptions,
): CompositionBarModel {
  if (rows.parties.length === 0) {
    throw new Error(
      "assembleCompositionBar: zero party rows; loader must guard before calling",
    );
  }
  const top_n = opts.top_n ?? DEFAULT_TOP_N;
  const reduced = reduceToTopNWithTail(rows.parties, top_n);

  // PR-SYM-6f5: `getPartyColor(party_id, row)` resolver does not need
  // an `in_use_codes` set - each party_id resolves through the
  // anchor/brand/algorithmic cascade independently. Passing [] keeps
  // the public resolvePartyFill signature compatible with prior calls.
  const segments: CompositionBarSegment[] = reduced.map(p => ({
    id: p.party_eci_code ?? p.party_short,
    label:
      p.party_short === "OTHERS"
        ? "Others"
        : p.party_full ?? p.party_short,
    value: p.seats_won,
    fill: resolvePartyFill(p, []),
    swatch_role:
      p.party_short === "OTHERS"
        ? "others"
        : p.party_short === "NOTA"
          ? "nota"
          : p.party_short === "IND" || p.party_short === "INDEPENDENT"
            ? "independent"
            : "party",
    is_tail: p.party_short === "OTHERS",
  }));

  const total_value = opts.total_seats_override ?? rows.total_seats;

  return CompositionBarModelSchema.parse({
    schema_version: "1.0",
    label: `${opts.state_label} — ${opts.event_label} Assembly`,
    subtitle: `All ${total_value} seats; FPTP winners only`,
    total_value,
    total_unit: "seats",
    segments,
    honesty_banners: opts.honesty_extra ?? [],
    dimension: "party",
    caption_fptp: CAPTION_FPTP,
  });
}

/**
 * Publisher-pill projection from the JOIN against `taxonomy.sources`.
 * Mirrors the projection in `election-seats-trend.ts` so the
 * `<SourceList pills={...} />` footer sees the same shape regardless of
 * which chart adapter loads the rows. Built via the canonical
 * `dedupeToPills` helper from `$lib/sources` per the sources-
 * simplification PR-1 (2026-06-11).
 */
export function projectPills(
  rows: readonly CompositionBarSourceJoinRow[],
): readonly PublisherPill[] {
  return dedupeToPills(
    rows.map<SourceRow>((s) => ({
      source_id: s.source_id,
      producer: s.producer,
      title: s.title,
      vintage: s.vintage,
      url: s.url,
    })),
  );
}

export interface LoadCompositionBarOptions {
  state_label: string;
  event_label: string;
  top_n?: number;
}

export interface LoadedCompositionBar {
  model: CompositionBarModel;
  pills: readonly PublisherPill[];
}

/**
 * Async loader entry. Returns a LoaderResult so the caller can fan out
 * three render arms (ok / partial / failed) cleanly - same shape as
 * `loadElectionSeatsTrend`.
 */
export async function loadCompositionBarElectionSeats(
  state_code: string,
  event_id: string,
  opts: LoadCompositionBarOptions,
): Promise<LoaderResult<LoadedCompositionBar>> {
  try {
    const rows = await runQueries(state_code, event_id);
    if (rows.parties.length === 0) {
      return {
        status: "partial",
        data: {
          model: emptyModel(opts.state_label, opts.event_label),
          pills: [],
        },
        reason: "not_published",
      };
    }
    const model = assembleCompositionBar(rows, {
      state_label: opts.state_label,
      event_label: opts.event_label,
      top_n: opts.top_n,
    });
    return {
      status: "ok",
      data: {
        model,
        pills: projectPills(rows.sources),
      },
    };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadCompositionBarElectionSeats(state_code, event_id, opts),
    };
  }
}

function emptyModel(
  state_label: string,
  event_label: string,
): CompositionBarModel {
  return CompositionBarModelSchema.parse({
    schema_version: "1.0",
    label: `${state_label} — ${event_label} Assembly`,
    subtitle: null,
    total_value: 1,
    total_unit: "seats",
    segments: [
      {
        id: "PLACEHOLDER",
        label: "No data published",
        value: 1,
        fill: OTHERS_FILL,
        swatch_role: "others",
        is_tail: true,
      },
    ],
    honesty_banners: [
      {
        kind: "missing_data",
        text: "No party-seats-won rows are published for this election event yet.",
      },
    ],
    dimension: "party",
    caption_fptp: null,
  });
}
