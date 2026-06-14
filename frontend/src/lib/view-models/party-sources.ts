// PR-9 of TODO/20260614-party-page-reimagination-plan.md - section 11.
//
// Per-card coverage badges + bottom-of-page source-pill strip for
// /parties/<slug>. Satisfies Holy Law #9 (provenance is mandatory):
// every section that surfaces data MUST cite its source_ids back to
// `datasets/data/entities/source.csv`.
//
// This module owns:
//   - the `PartyProvenance` shape (5 per-card badges + 1 strip)
//   - the `loadSourceLookup()` cache-once accessor for source.csv
//   - `buildPartyProvenance(detail, lookup)` - the pure projector
//     called from `party-detail.ts` after every VM section is
//     populated.
//
// STOP-AND-SURFACE contract (CLAUDE.md section 10): if a card has
// data on the VM but the loader could not derive a single source_id
// to back it, `buildPartyProvenance` THROWS. Silently rendering an
// unattributed card would violate Holy Law #9; the page-level error
// state is the correct fallback.

import { query, registerCsvFile } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { DATA_BASE } from "../paths";
import type {
  PartyDetailViewModel,
  PartyHistoryPoint,
  PartyStronghold,
} from "./party-detail";

/** Source.csv path - the citation ledger per CLAUDE.md section 12. */
const SOURCE_REL = "datasets/data/entities/source.csv";
const SOURCE_URL = `${DATA_BASE}/data/entities/source.csv`;

/** One row of the page-level source strip. Mirrors `source.csv` plus
 *  a derived `used_in` array tying it back to the cards that consumed
 *  it. The strip renderer groups these as a 4-column table. */
export interface PartyPageSource {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  /** May be empty string when the source.csv row has no landing
   *  page; the strip renderer suppresses the column linkout in
   *  that case. */
  url: string;
  /** Citizen-facing card labels (e.g. "Parliament chart",
   *  "Current Strength", "Strongholds"); see `CARD_LABELS` below. */
  used_in: string[];
}

/** Per-card coverage-badge text. Each value is the one-liner the
 *  badge component renders below the matching card; empty string
 *  means "no badge" (the matching card was not rendered, e.g.
 *  sentinel party with no LS history). */
export interface PartyCoverageBadgeText {
  parliament: string;
  state_assembly: string;
  strongholds: string;
  current_strength: string;
  alliance_context: string;
}

/** Bottom-of-page source-pill strip. The summary line shows
 *  `total_count` collapsed; expanded shows `all` as a 4-column
 *  table. */
export interface PartySourcesStrip {
  /** Number of distinct source_ids consumed across every card on
   *  the page. */
  total_count: number;
  /** Dedupe-sorted full list - producer ASC, then vintage DESC. */
  all: PartyPageSource[];
  /** Citizen-readable summary of distinct producers (cap 3 then
   *  "+ N more"). The strip renders this verbatim in the collapsed
   *  `<summary>`. */
  producer_summary: string;
}

/** Per-page Holy-Law-#9 envelope: 5 badges + 1 strip. */
export interface PartyProvenance {
  badges: PartyCoverageBadgeText;
  strip: PartySourcesStrip;
}

/** Card-label constants used in `used_in[]` and the per-card
 *  source-id derivation. Citizen-readable; the strip table column
 *  shows these verbatim. */
export const CARD_LABELS = {
  parliament: "Parliament chart",
  state_assembly: "State Assembly chart",
  strongholds: "Strongholds",
  current_strength: "Current Strength",
  alliance_context: "Alliance Context",
} as const;

type CardKey = keyof typeof CARD_LABELS;

/** Per-card source_id sets the loader populates before calling
 *  `buildPartyProvenance`. The five keys mirror `CARD_LABELS`. */
export interface PartyCardSourceIds {
  parliament: ReadonlySet<string>;
  state_assembly: ReadonlySet<string>;
  strongholds: ReadonlySet<string>;
  current_strength: ReadonlySet<string>;
  alliance_context: ReadonlySet<string>;
}

/** Raw source.csv row from DuckDB. */
interface RawSourceRow {
  source_id: string | null;
  producer: string | null;
  title: string | null;
  vintage: string | null;
  url: string | null;
}

/** Module-level promise cache for the source.csv lookup. The file
 *  is small (~10KB, ~300 rows) and shared across every party page;
 *  a single in-flight fetch suffices for the tab lifetime. */
let sourceLookupCache: Promise<Map<string, PartyPageSource>> | null = null;

/** Load + cache `datasets/data/entities/source.csv` as a
 *  `Map<source_id, PartyPageSource>`. The lookup is read-only by
 *  `buildPartyProvenance`; the `used_in[]` field starts empty and
 *  is populated by the projector per-page. A network failure clears
 *  the cache so the next navigation re-issues the fetch. */
export function loadSourceLookup(): Promise<Map<string, PartyPageSource>> {
  if (sourceLookupCache !== null) return sourceLookupCache;
  sourceLookupCache = (async (): Promise<Map<string, PartyPageSource>> => {
    await registerCsvFile(SOURCE_URL);
    const clause = await csvColumnsClause(SOURCE_REL);
    const sql = `
      SELECT source_id, producer, title, vintage, url
      FROM read_csv('${SOURCE_URL}', ${clause}, header=true)
    `;
    const rows = await query<RawSourceRow>(sql);
    const out = new Map<string, PartyPageSource>();
    for (const r of rows) {
      if (!r.source_id) continue;
      out.set(r.source_id, {
        source_id: r.source_id,
        producer: (r.producer ?? "").trim(),
        title: (r.title ?? "").trim(),
        vintage: (r.vintage ?? "").trim(),
        url: (r.url ?? "").trim(),
        used_in: [],
      });
    }
    return out;
  })().catch((err) => {
    sourceLookupCache = null;
    throw err;
  });
  return sourceLookupCache;
}

/** Test-only cache reset. NOT exported from index.ts. */
export function __resetSourceLookupForTests(): void {
  sourceLookupCache = null;
}

/** Pure: split a pipe-delimited source_ids string into a deduped
 *  array. Empty / null safely returns `[]`. */
export function splitSourceIds(raw: string | null | undefined): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split("|")) {
    const t = part.trim();
    if (t.length === 0) continue;
    if (seen.has(t)) continue;
    seen.add(t);
    out.push(t);
  }
  return out;
}

/** Pure: union per-row source_ids from a `PartyHistoryPoint` list. */
function unionHistorySourceIds(
  rows: readonly PartyHistoryPoint[],
): Set<string> {
  const out = new Set<string>();
  for (const r of rows) for (const sid of r.source_ids) out.add(sid);
  return out;
}

/** Pure: union per-row source_ids from a `PartyStronghold` list. */
function unionStrongholdSourceIds(
  rows: readonly PartyStronghold[],
): Set<string> {
  const out = new Set<string>();
  for (const r of rows) for (const sid of r.source_ids) out.add(sid);
  return out;
}

/** Pure: build the per-card source_id sets from a populated VM
 *  (alliance + current_strength source_ids are passed-through from
 *  the loader since neither lives on a row inside the VM today). */
export function buildPartyCardSourceIds(
  vm: Pick<
    PartyDetailViewModel,
    | "ls_history"
    | "vs_history"
    | "ls_strongholds"
    | "vs_strongholds"
    | "current_strength"
    | "alliance_context"
    | "alliance_source_ids"
    | "current_strength_source_ids"
  >,
): PartyCardSourceIds {
  return {
    parliament: unionHistorySourceIds(vm.ls_history),
    state_assembly: unionHistorySourceIds(vm.vs_history),
    strongholds: new Set([
      ...unionStrongholdSourceIds(vm.ls_strongholds),
      ...unionStrongholdSourceIds(vm.vs_strongholds),
    ]),
    current_strength:
      vm.current_strength === null
        ? new Set<string>()
        : new Set(vm.current_strength_source_ids),
    alliance_context:
      vm.alliance_context === null
        ? new Set<string>()
        : new Set(vm.alliance_source_ids),
  };
}

/** Pure: should a card render its badge AND require a source? Yes
 *  iff the card has data to display. Hidden cards (sentinel + empty)
 *  carry an empty badge string AND skip the source-required check. */
function cardHasData(
  vm: Pick<
    PartyDetailViewModel,
    | "ls_history"
    | "vs_history"
    | "ls_strongholds"
    | "vs_strongholds"
    | "current_strength"
    | "alliance_context"
  >,
  card: CardKey,
): boolean {
  switch (card) {
    case "parliament":
      return vm.ls_history.length > 0;
    case "state_assembly":
      return vm.vs_history.length > 0;
    case "strongholds":
      return vm.ls_strongholds.length > 0 || vm.vs_strongholds.length > 0;
    case "current_strength":
      return vm.current_strength !== null;
    case "alliance_context":
      return vm.alliance_context !== null;
  }
}

/** Pure: derive the year span "YYYY-YYYY" from a list of history
 *  points. Returns "YYYY" when first === last and an empty string
 *  when the list is empty. */
function spanOf(rows: readonly PartyHistoryPoint[]): string {
  if (rows.length === 0) return "";
  let first = rows[0]!.year;
  let last = rows[0]!.year;
  for (const r of rows) {
    if (r.year < first) first = r.year;
    if (r.year > last) last = r.year;
  }
  return first === last ? `${first}` : `${first}-${last}`;
}

/** Pure: dedupe + compress a producer list. Caps at 3 names then
 *  appends "+ N more"; preserves first-seen order. */
export function compressProducers(producers: readonly string[]): string {
  const seen = new Set<string>();
  const order: string[] = [];
  for (const p of producers) {
    const t = p.trim();
    if (t.length === 0) continue;
    if (seen.has(t)) continue;
    seen.add(t);
    order.push(t);
  }
  if (order.length === 0) return "";
  if (order.length <= 3) return order.join(", ");
  const head = order.slice(0, 3).join(", ");
  const more = order.length - 3;
  return `${head} + ${more} more`;
}

/** Pure: pick the most recent vintage across a list of sources.
 *  Vintage is a free-text date-like string ("2024-06-04", "2024",
 *  "2024-Q3"); lexicographic max is good enough for ISO-shape
 *  dates which is the dominant convention on source.csv. Empty
 *  string returned when the list is empty or every vintage is "". */
function latestVintage(sources: readonly PartyPageSource[]): string {
  let max = "";
  for (const s of sources) {
    if (s.vintage && s.vintage > max) max = s.vintage;
  }
  return max;
}

/** Pure: build the citizen-readable badge text for one card. The
 *  shape is per-card; missing knobs gracefully drop their fragments
 *  (e.g. no methodology breaks -> shorter sentence). */
function buildBadgeText(
  card: CardKey,
  vm: Pick<
    PartyDetailViewModel,
    | "ls_history"
    | "vs_history"
    | "ls_strongholds"
    | "vs_strongholds"
    | "current_strength"
    | "alliance_context"
  >,
  sources: readonly PartyPageSource[],
): string {
  if (!cardHasData(vm, card)) return "";
  const producers = compressProducers(sources.map((s) => s.producer));
  const vintage = latestVintage(sources);
  switch (card) {
    case "parliament": {
      const span = spanOf(vm.ls_history);
      const cycles = vm.ls_history.length;
      const tail = vintage ? ` - last refresh ${vintage}` : "";
      return `Parliament ${span} - ${cycles} ${cycles === 1 ? "cycle" : "cycles"} - ${producers}${tail}`;
    }
    case "state_assembly": {
      const span = spanOf(vm.vs_history);
      const cycles = vm.vs_history.length;
      const tail = vintage ? ` - last refresh ${vintage}` : "";
      return `State Assembly ${span} - ${cycles} ${cycles === 1 ? "cycle" : "cycles"} - ${producers}${tail}`;
    }
    case "strongholds": {
      const fragments: string[] = [];
      if (vm.ls_history.length > 0) {
        fragments.push(`Parliament ${spanOf(vm.ls_history)}`);
      }
      if (vm.vs_history.length > 0) {
        fragments.push(`State Assembly ${spanOf(vm.vs_history)}`);
      }
      const head = fragments.length > 0
        ? `Computed from ${fragments.join(" and ")}`
        : "Computed from contested-history cycles";
      const tail = producers ? ` - ${producers}` : "";
      return `${head}${tail}`;
    }
    case "current_strength": {
      const cs = vm.current_strength!;
      const parts: string[] = [];
      if (cs.parliament_latest) {
        parts.push(`Parliament ${cs.parliament_latest.year}`);
      }
      if (cs.state_assemblies_latest) {
        const span = spanOf(vm.vs_history);
        const count = cs.state_assemblies_latest.state_count;
        parts.push(
          `State Assemblies ${span} across ${count} ${count === 1 ? "state" : "states"}`,
        );
      }
      const head = parts.length > 0
        ? `Latest cycle per body - ${parts.join(" - ")}`
        : "Latest cycle per body";
      const tail = vintage ? ` - data current as of ${vintage}` : "";
      return `${head}${tail}`;
    }
    case "alliance_context": {
      const ac = vm.alliance_context!;
      const cycles =
        (ac.parliament !== null ? 1 : 0) + ac.state_assemblies.length;
      const jurisdictions =
        (ac.parliament !== null ? 1 : 0) + ac.state_assemblies.length;
      const tail = producers ? ` - ${producers}` : "";
      return `Recorded for ${cycles} ${cycles === 1 ? "cycle" : "cycles"} across ${jurisdictions} ${jurisdictions === 1 ? "jurisdiction" : "jurisdictions"}${tail}`;
    }
  }
}

/** Pure: assemble the page-level provenance envelope from a
 *  populated detail VM plus the source.csv lookup. THROWS when any
 *  rendered card has data but resolves zero source_ids (Holy Law #9
 *  STOP-AND-SURFACE). Also throws when a source_id is referenced
 *  by a card but is absent from `source_lookup` (FK violation -
 *  citation-ledger drift).
 *
 *  The function is deterministic - same inputs always produce the
 *  same output. The strip rows are sorted by producer ASC, then
 *  vintage DESC, then source_id ASC for stable ordering across
 *  navigations. */
export function buildPartyProvenance(
  vm: Pick<
    PartyDetailViewModel,
    | "metadata"
    | "ls_history"
    | "vs_history"
    | "ls_strongholds"
    | "vs_strongholds"
    | "current_strength"
    | "alliance_context"
    | "alliance_source_ids"
    | "current_strength_source_ids"
  >,
  source_lookup: ReadonlyMap<string, PartyPageSource>,
): PartyProvenance {
  const card_ids = buildPartyCardSourceIds(vm);
  // Build the per-card resolved-source lookup. Each resolved source
  // is a FRESH PartyPageSource (so we can mutate `used_in` without
  // poisoning the shared module-level lookup).
  const per_card: Record<CardKey, PartyPageSource[]> = {
    parliament: [],
    state_assembly: [],
    strongholds: [],
    current_strength: [],
    alliance_context: [],
  };
  for (const card of Object.keys(CARD_LABELS) as CardKey[]) {
    const ids = card_ids[card];
    if (ids.size === 0) continue;
    for (const sid of ids) {
      const row = source_lookup.get(sid);
      if (!row) {
        // FK violation - the marts cite a source_id that is not in
        // source.csv. This is a writer-side data bug; fail loud so
        // it surfaces in the page error state rather than silently
        // dropping the citation.
        throw new Error(
          `party-sources: source_id "${sid}" cited by card "${card}" on /parties/${vm.metadata.party_id} is not present in datasets/data/entities/source.csv`,
        );
      }
      per_card[card]!.push({ ...row, used_in: [] });
    }
  }
  // Holy Law #9 STOP-AND-SURFACE: every RENDERED card must cite at
  // least one source. A card with no data is fine (badge stays "");
  // a card WITH data but zero sources is a writer-side gap that
  // would render an unattributed citizen-facing surface.
  for (const card of Object.keys(CARD_LABELS) as CardKey[]) {
    if (!cardHasData(vm, card)) continue;
    if (per_card[card]!.length === 0) {
      throw new Error(
        `party-sources: card "${card}" on /parties/${vm.metadata.party_id} has data but resolves zero source_ids (Holy Law #9)`,
      );
    }
  }
  // Build the per-card badge text.
  const badges: PartyCoverageBadgeText = {
    parliament: buildBadgeText("parliament", vm, per_card.parliament),
    state_assembly: buildBadgeText(
      "state_assembly",
      vm,
      per_card.state_assembly,
    ),
    strongholds: buildBadgeText("strongholds", vm, per_card.strongholds),
    current_strength: buildBadgeText(
      "current_strength",
      vm,
      per_card.current_strength,
    ),
    alliance_context: buildBadgeText(
      "alliance_context",
      vm,
      per_card.alliance_context,
    ),
  };
  // Build the page-level strip: dedupe-by-source_id, attach
  // `used_in` from the cards that resolved each id, sort stably.
  const strip_by_id = new Map<string, PartyPageSource>();
  for (const card of Object.keys(CARD_LABELS) as CardKey[]) {
    for (const src of per_card[card]!) {
      const existing = strip_by_id.get(src.source_id);
      if (existing) {
        if (!existing.used_in.includes(CARD_LABELS[card])) {
          existing.used_in.push(CARD_LABELS[card]);
        }
      } else {
        strip_by_id.set(src.source_id, {
          ...src,
          used_in: [CARD_LABELS[card]],
        });
      }
    }
  }
  const all = [...strip_by_id.values()];
  all.sort((a, b) => {
    if (a.producer !== b.producer) return a.producer.localeCompare(b.producer);
    if (a.vintage !== b.vintage) return b.vintage.localeCompare(a.vintage);
    return a.source_id.localeCompare(b.source_id);
  });
  const producer_summary = compressProducers(all.map((s) => s.producer));
  return {
    badges,
    strip: {
      total_count: all.length,
      all,
      producer_summary,
    },
  };
}
