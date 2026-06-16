// PR-9 of TODO/20260615-party-page-citizen-fixes-plan.md (D9 + D12).
//
// Per-card publisher-pill citation footers for /parties/<slug>.
// Satisfies Holy Law #9 (provenance is mandatory): every section
// that surfaces data MUST cite its source_ids back to
// `datasets/data/entities/source.csv`. PR-9 collapses the prior
// envelope (5 free-text coverage badges + 1 bottom-of-page strip)
// into ONE post-v3.1 `PublisherPill[]` per card, rendered inline
// by `SourceList` from `frontend/src/lib/sources/`. The bottom
// strip retires; the deleted free-text badges retired with it.
//
// This module owns:
//   - the `PartyProvenance` shape (one `PublisherPill[]` per card)
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
import { dedupeToPills } from "../sources";
import type { PublisherPill, SourceRow } from "../sources";
import type {
  PartyDetailViewModel,
  PartyHistoryPoint,
  PartyStronghold,
} from "./party-detail";

/** Source.csv path - the citation ledger per CLAUDE.md section 12. */
const SOURCE_REL = "datasets/data/entities/source.csv";
const SOURCE_URL = `${DATA_BASE}/data/entities/source.csv`;

/** One row of the source.csv lookup. Mirrors `source.csv` columns
 *  (5-col post v3.1; see `datasets/data/_schema/columns.json`). */
export interface PartyPageSource {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  /** May be empty string when the source.csv row has no landing
   *  page; the pill renderer renders the pill as plain text
   *  (not a link) in that case. */
  url: string;
}

/** Per-page Holy-Law-#9 envelope: one `PublisherPill[]` per card.
 *  An empty array means the matching card is not rendered (sentinel
 *  party, or the card has no data). The `SourceList` renderer
 *  suppresses itself when handed an empty array. */
export interface PartyProvenance {
  pills_per_card: Record<CardKey, PublisherPill[]>;
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

/** Pure: project a `PartyPageSource` lookup entry into a `SourceRow`
 *  for `dedupeToPills`. Maps the local `url: string` (empty when
 *  absent) to `SourceRow.url: string | null` (`null` when absent). */
function toSourceRow(s: PartyPageSource): SourceRow {
  return {
    source_id: s.source_id,
    producer: s.producer,
    title: s.title,
    vintage: s.vintage,
    url: s.url.length > 0 ? s.url : null,
  };
}

/** Pure: merge `PublisherPill[]` entries that share the same `label`.
 *  `dedupeToPills` groups upstream by `(producer, series_family)`,
 *  but its budget-overflow / family-equals-pub branches can collapse
 *  multiple groups into the SAME visible label - e.g. when a party
 *  cites many ECI titles whose `series_family` slices ALL overflow
 *  the 30-char pill-label budget, every contributing group falls
 *  back to label = "ECI" while the underlying groups remain distinct.
 *
 *  `SourceList.svelte` keys its `{#each}` over pills by
 *  `(pill.label + pill.vintage_summary)`; same-label pills with the
 *  same vintage summary therefore trip Svelte's `each_key_duplicate`
 *  runtime crash. This 2nd-pass merge collapses any same-label group
 *  to ONE pill with summed `count`, first-non-empty `url`, and a
 *  vintage_summary derived via the same rule `dedupeToPills` itself
 *  uses (single -> verbatim; pair -> "<a> to <b>"; 3+ -> "various").
 *
 *  Citizens see one pill per visible publisher; their click target
 *  is the first non-empty url among contributing groups; the vintage
 *  range spans every contributing group. Holy Law #9 is unchanged -
 *  every source_id resolved upstream still attributes a pill. */
export function mergeLabelDuplicates(
  pills: readonly PublisherPill[],
): PublisherPill[] {
  if (pills.length <= 1) return [...pills];
  const groups = new Map<string, PublisherPill[]>();
  for (const p of pills) {
    const existing = groups.get(p.label);
    if (existing) existing.push(p);
    else groups.set(p.label, [p]);
  }
  const out: PublisherPill[] = [];
  for (const [label, group] of groups) {
    if (group.length === 1) {
      out.push(group[0]!);
      continue;
    }
    const distinct = Array.from(
      new Set(
        group
          .map((p) => p.vintage_summary.trim())
          .filter((v) => v.length > 0),
      ),
    ).sort();
    let vintage_summary: string;
    if (distinct.length === 0) vintage_summary = "";
    else if (distinct.length === 1) vintage_summary = distinct[0]!;
    else if (distinct.length === 2)
      vintage_summary = `${distinct[0]} to ${distinct[1]}`;
    else vintage_summary = "various";
    const count = group.reduce((sum, p) => sum + p.count, 0);
    const url =
      group.map((p) => p.url ?? "").find((u) => u.length > 0) ?? null;
    out.push({ label, vintage_summary, url, count });
  }
  out.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return a.label.localeCompare(b.label);
  });
  return out;
}

/** Pure: assemble the page-level provenance envelope from a
 *  populated detail VM plus the source.csv lookup. THROWS when any
 *  rendered card has data but resolves zero source_ids (Holy Law #9
 *  STOP-AND-SURFACE). Also throws when a source_id is referenced
 *  by a card but is absent from `source_lookup` (FK violation -
 *  citation-ledger drift).
 *
 *  The function is deterministic - same inputs always produce the
 *  same output. Per-card pill ordering is the stable order produced
 *  by `dedupeToPills` (count DESC, then label ASC). */
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
  // Resolve each card's source_ids against the lookup. FK violation
  // (source_id cited by a card but absent from source.csv) THROWS
  // immediately so the citizen sees the page-level error state
  // rather than a silently-dropped citation.
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
        throw new Error(
          `party-sources: source_id "${sid}" cited by card "${card}" on /parties/${vm.metadata.party_id} is not present in datasets/data/entities/source.csv`,
        );
      }
      per_card[card]!.push(row);
    }
  }
  // Holy Law #9 STOP-AND-SURFACE: every RENDERED card must cite at
  // least one source. A card with no data is fine (pills array stays
  // empty -> SourceList renders nothing); a card WITH data but zero
  // sources is a writer-side gap that would render an unattributed
  // citizen-facing surface.
  for (const card of Object.keys(CARD_LABELS) as CardKey[]) {
    if (!cardHasData(vm, card)) continue;
    if (per_card[card]!.length === 0) {
      throw new Error(
        `party-sources: card "${card}" on /parties/${vm.metadata.party_id} has data but resolves zero source_ids (Holy Law #9)`,
      );
    }
  }
  // Project each card's resolved sources into the deduped
  // PublisherPill[] the SourceList renderer consumes. An empty card
  // (no data, no sources) collapses to an empty array; the renderer
  // suppresses itself in that case. The `mergeLabelDuplicates`
  // 2nd-pass collapses any pills that share a visible label (see
  // helper docstring) so `SourceList.svelte`'s `(label + vintage)`
  // Svelte key stays unique.
  const pills_per_card: Record<CardKey, PublisherPill[]> = {
    parliament: mergeLabelDuplicates(
      dedupeToPills(per_card.parliament.map(toSourceRow)),
    ),
    state_assembly: mergeLabelDuplicates(
      dedupeToPills(per_card.state_assembly.map(toSourceRow)),
    ),
    strongholds: mergeLabelDuplicates(
      dedupeToPills(per_card.strongholds.map(toSourceRow)),
    ),
    current_strength: mergeLabelDuplicates(
      dedupeToPills(per_card.current_strength.map(toSourceRow)),
    ),
    alliance_context: mergeLabelDuplicates(
      dedupeToPills(per_card.alliance_context.map(toSourceRow)),
    ),
  };
  return { pills_per_card };
}
