// Constituency district + reservation enrichment loader (STATE lane,
// Row 4 of TODO/20260622-election-constituency-grouping-plan.md).
//
// WHAT this answers: given an Assembly Constituency (AC) electoral_id,
// what is its (a) human-readable LGD district name, (b) reservation
// category (GEN / SC / ST), and (c) ECI ballot-order serial (eci_no)?
//
// The state assembly page groups its constituency list by DISTRICT. The
// district label is not native to the per-AC election result rows; it is
// joined here from the canonical entity store:
//
//   electoral_district_membership.csv  (AC electoral_id -> district slug,
//                                        is_primary = the plurality
//                                        district when an AC spans more
//                                        than one)
//        |  filter is_primary = true
//        v
//   geo.csv (entity_kind = 'district') (district slug -> display NAME;
//                                        resolve the slug, never
//                                        title-case it - that mangles
//                                        names like "Dr. B.R. Ambedkar
//                                        Konaseema")
//
//   electoral.csv (entity_kind = 'ac')  (AC electoral_id -> reservation,
//                                        eci_no)
//
// Reusable across Rows 5/6: Row 5 (parliament PC->AC->district leaves)
// and Row 6 (landing-page district grouping) consume the SAME map.
//
// Read seam: the project's typed DuckDB-WASM boundary (CLAUDE.md Holy
// Law #3) - `registerCsvFile` -> `read_csv(url, columns=...)` with the
// columns map sourced from columns.json via `csvColumnsClause`. The
// hardened `auto_detect=false` flag is REQUIRED: the deployed
// DuckDB-WASM dialect sniffer mis-detects multi-column CSVs whose fields
// carry quoted commas (district / constituency names) as a single
// column and throws. The columns map is authoritative, so there is
// nothing left to sniff. (The election-only `null_padding=true` opt is
// intentionally NOT used here - these are entity reads, where a
// column-count mismatch must fail loud, not be silently NULL-padded.)

import { csvColumnsClause } from "../canonical/csv-columns";
import { query, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { slugify } from "../slug";
import { reservationKind, type ReservationKind } from "./constituency-list-tokens";

// ---- File-class keys (columns.json) + dev/prod URLs (/data/<rel>) -----

const MEMBERSHIP_REL = "datasets/data/entities/electoral_district_membership.csv";
const GEO_REL = "datasets/data/entities/geo.csv";
const ELECTORAL_REL = "datasets/data/entities/electoral.csv";

const MEMBERSHIP_URL = `${DATA_BASE}/data/entities/electoral_district_membership.csv`;
const GEO_URL = `${DATA_BASE}/data/entities/geo.csv`;
const ELECTORAL_URL = `${DATA_BASE}/data/entities/electoral.csv`;

// Pinned read options: the files carry a header row and the columns
// map already declares every column + type, so the broken dialect
// sniffer is pinned off. See the module header for the deploy-bug
// rationale.
const READ_OPTS = "header=true, auto_detect=false";

// ---- Public shapes ----------------------------------------------------

/** Per-AC enrichment: the three fields the assembly seat list needs that
 *  are not native to the per-AC election-result row. Any field is null
 *  when it cannot be resolved (e.g. a re-delimited AC with no membership
 *  edge yet -> `district_name` null -> the list's "Other" bucket). */
export interface AcEnrichment {
  /** LGD district DISPLAY name (resolved from the slug), or null. */
  district_name: string | null;
  /** ECI reservation category: "GEN" / "SC" / "ST", or null. */
  reservation: string | null;
  /** ECI ballot-order serial, or null. */
  eci_no: number | null;
}

/** One `electoral_district_membership.csv` edge (AC -> district). */
export interface MembershipRow {
  electoral_id: string;
  lgd_district_id: string;
  is_primary: boolean;
}

/** One `geo.csv` district row (entity_id is the slug; name is display). */
export interface DistrictRow {
  entity_id: string;
  name: string;
}

/** One `electoral.csv` AC row's enrichment fields. */
export interface ElectoralAcRow {
  entity_id: string;
  reservation: string | null;
  eci_no: number | null;
}

// ---- Pure builder (unit-tested with in-memory fixtures) ---------------

/**
 * Build the `entity_id -> AcEnrichment` lookup from the three canonical
 * row sets. Pure + deterministic so the Row-4 oracle exercises it with
 * in-memory fixtures (no DuckDB spin-up).
 *
 * Contract:
 *  - The district is the `is_primary = true` membership edge ONLY; an AC
 *    spanning several districts maps to exactly its plurality district,
 *    so no AC ever lands in two groups.
 *  - The district VALUE is always a resolved display name or null -
 *    never a raw slug. A membership edge whose slug has no `districts`
 *    row contributes no district (null), rather than leaking the slug.
 *  - Every AC present in `electoralAcs` gets an entry (reservation +
 *    eci_no always; district where a primary edge exists). A
 *    membership-only AC absent from `electoralAcs` still gets a
 *    district-only entry (defensive; electoral.csv is normally the
 *    superset).
 */
export function buildAcEnrichmentMap(
  membership: readonly MembershipRow[],
  districts: readonly DistrictRow[],
  electoralAcs: readonly ElectoralAcRow[],
): Map<string, AcEnrichment> {
  // district slug -> display name
  const districtName = new Map<string, string>();
  for (const d of districts) districtName.set(d.entity_id, d.name);

  // AC electoral_id -> primary-district display name (resolved only)
  const acDistrict = new Map<string, string>();
  for (const m of membership) {
    if (!m.is_primary) continue;
    const name = districtName.get(m.lgd_district_id);
    // Resolve-or-drop: never emit a raw slug. Real corpus FK-resolves
    // every membership slug in geo.csv (Tier-B invariant), so this only
    // guards against a genuinely missing district master row.
    if (name != null) acDistrict.set(m.electoral_id, name);
  }

  const out = new Map<string, AcEnrichment>();
  for (const e of electoralAcs) {
    out.set(e.entity_id, {
      district_name: acDistrict.get(e.entity_id) ?? null,
      reservation: e.reservation ?? null,
      eci_no: e.eci_no ?? null,
    });
  }
  // Defensive: a membership-only AC (not in electoral.csv) still groups.
  for (const [electoral_id, name] of acDistrict) {
    if (!out.has(electoral_id)) {
      out.set(electoral_id, {
        district_name: name,
        reservation: null,
        eci_no: null,
      });
    }
  }
  return out;
}

// ---- DuckDB-WASM read shapes ------------------------------------------

interface RawMembership {
  electoral_id: string;
  lgd_district_id: string;
  is_primary: boolean;
}
interface RawDistrict {
  entity_id: string;
  name: string;
}
interface RawElectoral {
  entity_id: string;
  reservation: string | null;
  // columns.json `integer` lifts to DuckDB BIGINT -> JS bigint.
  eci_no: number | bigint | null;
}

// ---- Async loader (singleton-cached per page session) -----------------

let enrichmentPromise: Promise<Map<string, AcEnrichment>> | null = null;

/** Reset the cache; for tests and HMR. Production never calls this. */
export function _resetAcEnrichmentCacheForTests(): void {
  enrichmentPromise = null;
}

/**
 * Fetch + join the three entity CSVs into the `entity_id -> AcEnrichment`
 * map (once per session, cached). Callers default district / reservation
 * / eci_no to null until this resolves, so the list renders immediately.
 */
export async function loadAcEnrichment(): Promise<Map<string, AcEnrichment>> {
  if (enrichmentPromise) return enrichmentPromise;
  enrichmentPromise = (async () => {
    await Promise.all([
      registerCsvFile(MEMBERSHIP_URL),
      registerCsvFile(GEO_URL),
      registerCsvFile(ELECTORAL_URL),
    ]);
    const [membershipCols, geoCols, electoralCols] = await Promise.all([
      csvColumnsClause(MEMBERSHIP_REL),
      csvColumnsClause(GEO_REL),
      csvColumnsClause(ELECTORAL_REL),
    ]);

    const membership = await query<RawMembership>(
      `SELECT electoral_id, lgd_district_id, is_primary
         FROM read_csv('${MEMBERSHIP_URL}', ${membershipCols}, ${READ_OPTS})
        WHERE is_primary`,
    );
    const districts = await query<RawDistrict>(
      `SELECT entity_id, name
         FROM read_csv('${GEO_URL}', ${geoCols}, ${READ_OPTS})
        WHERE entity_kind = 'district'`,
    );
    const electoralAcs = await query<RawElectoral>(
      `SELECT entity_id, reservation, eci_no
         FROM read_csv('${ELECTORAL_URL}', ${electoralCols}, ${READ_OPTS})
        WHERE entity_kind = 'ac'`,
    );

    return buildAcEnrichmentMap(
      membership.map((m) => ({
        electoral_id: m.electoral_id,
        lgd_district_id: m.lgd_district_id,
        is_primary: Boolean(m.is_primary),
      })),
      districts,
      electoralAcs.map((e) => ({
        entity_id: e.entity_id,
        reservation: e.reservation ?? null,
        eci_no: e.eci_no == null ? null : Number(e.eci_no),
      })),
    );
  })();
  // On failure, drop the cache so a later attempt re-fetches instead of
  // permanently rejecting.
  enrichmentPromise.catch(() => {
    enrichmentPromise = null;
  });
  return enrichmentPromise;
}

// ===========================================================================
// Row 5 - parliament PC -> AC -> District (TODO/20260622-election-
// constituency-grouping-plan.md).
// ===========================================================================
//
// The state-scoped GENERAL page groups its constituency list by PARLIAMENT
// CONSTITUENCY (PC): each PC is a group whose HEADER carries the Lok Sabha
// (MP) result and whose LEAVES are the PC's child ACs (each tagged with its
// LGD district). The AC -> PC link is NATIVE in electoral.csv - every
// `entity_kind='ac'` row's `parent` IS its PC `entity_id` (plan finding 5),
// and a parliament PC winner's `entity_id` (NATIONAL-PC loader) is the SAME
// electoral.csv PC id, so the join `AC.parent == PCwinner.entity_id` needs
// ZERO new data.
//
// Row 4's `AcEnrichment` map is keyed by AC and carries only
// {district_name, reservation, eci_no} - it does NOT carry the AC `name` or
// its `parent` PC. This section ADDS the richer `AcEntity` (name +
// parent_pc_id + state + delim_year) plus the pure `buildPcGrouping`, which
// tags each state AC with its parent PC name (or null for a re-delimitation
// orphan -> the component's "Other"/ungrouped path, never dropped per plan
// 7.2). The Row 4 exports above stay byte-identical (Row 4 + Row 6 depend on
// them).

/** A full AC entity for the parliament PC -> AC -> District list. Superset
 *  of `AcEnrichment` with the AC `name`, its parent PC id, the owning state
 *  slug and the delimitation year (so a general page restricts to the live
 *  delimitation and never mixes an old-delim AC into a current PC group). */
export interface AcEntity {
  /** AC electoral_id (e.g. "IN-AC-2008-andhra-pradesh-3166"). */
  entity_id: string;
  /** AC display name (e.g. "Gannavaram"). */
  name: string;
  /** Parent PC entity_id (electoral.csv `parent`), or null. Equals a PC
   *  winner's `entity_id` at NATIONAL-PC scope, so the leaf groups under
   *  that PC. */
  parent_pc_id: string | null;
  /** Owning state LGD slug (electoral.csv `state`), e.g. "andhra-pradesh". */
  state: string;
  /** Delimitation year (electoral.csv `delim_year`), or null. */
  delim_year: number | null;
  /** Resolved LGD district DISPLAY name (is_primary edge), or null - never a
   *  raw slug (mirrors `buildAcEnrichmentMap`). */
  district_name: string | null;
  /** ECI reservation category "GEN" / "SC" / "ST", or null. */
  reservation: string | null;
  /** ECI ballot-order serial, or null. */
  eci_no: number | null;
}

/** One `electoral.csv` AC row's fields needed to build an `AcEntity`. */
export interface ElectoralAcEntityRow {
  entity_id: string;
  name: string;
  /** electoral.csv `parent` (the PC entity_id for an AC row). */
  parent: string | null;
  /** electoral.csv `state` (LGD slug). */
  state: string;
  delim_year: number | null;
  reservation: string | null;
  eci_no: number | null;
}

/**
 * Build the flat `AcEntity[]` list from the three canonical row sets. Pure +
 * deterministic so the Row-5 oracle exercises it with in-memory fixtures
 * (no DuckDB spin-up). The district resolution mirrors `buildAcEnrichmentMap`
 * exactly: the is_primary edge -> display name, resolve-or-null, NEVER a raw
 * slug.
 */
export function buildAcEntities(
  membership: readonly MembershipRow[],
  districts: readonly DistrictRow[],
  electoralAcs: readonly ElectoralAcEntityRow[],
): AcEntity[] {
  // district slug -> display name
  const districtName = new Map<string, string>();
  for (const d of districts) districtName.set(d.entity_id, d.name);

  // AC electoral_id -> primary-district display name (resolved only)
  const acDistrict = new Map<string, string>();
  for (const m of membership) {
    if (!m.is_primary) continue;
    const name = districtName.get(m.lgd_district_id);
    if (name != null) acDistrict.set(m.electoral_id, name);
  }

  return electoralAcs.map((e) => ({
    entity_id: e.entity_id,
    name: e.name,
    parent_pc_id: e.parent ?? null,
    state: e.state,
    delim_year: e.delim_year ?? null,
    district_name: acDistrict.get(e.entity_id) ?? null,
    reservation: e.reservation ?? null,
    eci_no: e.eci_no ?? null,
  }));
}

// ===========================================================================
// Name bridge - results-id scheme mismatch
// (fix/assembly-district-name-join).
// ===========================================================================
//
// Assembly RESULT winners carry the RESULTS-scheme entity_id
// `IN-S<NN>-AC-<delim>-<eci_no>` (state code + ballot serial). The canonical
// district edge (electoral_district_membership.csv) + `loadAcEnrichment` are
// keyed on the CANONICAL electoral_id `IN-AC-<delim>-<state>-<serial>`, so an
// entity_id join misses for every results-scheme winner. The ECI ballot
// `eci_no` is the documented-unreliable field (electoral.csv's serial for an
// AC differs from its ballot number), so it can NOT bridge the two schemes
// either. The ONLY reliable shared field is the AC NAME.
//
// `buildAcNameIndex` keys the canonical `AcEntity[]` by `(state, slug(name))`
// so a winner whose entity_id misses the canonical enrichment falls back to a
// name lookup. The state landing page (StateOverview) consumes the SAME index
// for its district grouping, so there is ONE name-match seam (DRY) and both
// pages get identical coverage.

/** Name-bridge value: the enrichment fields a results-scheme winner needs,
 *  resolved by (state, normalized AC name). Superset of `AcEnrichment` with
 *  the canonical `entity_id` so a caller can re-key onto the canonical id. */
export interface AcNameInfo {
  entity_id: string;
  district_name: string | null;
  reservation: string | null;
  eci_no: number | null;
}

/** Name-bridge key: canonical state slug + normalized AC name. Keying by
 *  state too means same-named ACs in different states never collide. */
function acNameKey(state: string, name: string): string {
  return `${state}\u0000${slugify(name)}`;
}

/**
 * Build a `(state, slug(name)) -> AcNameInfo` index from the canonical
 * `AcEntity[]`. When two canonical rows share a (state, name) - e.g. the
 * district-bearing `...-<serial>` row and a district-less `...-eci<NN>`
 * ballot alias - the DISTRICT-BEARING row wins, so an alias never shadows the
 * real district edge (mirrors the landing page's skip-null rule). A row whose
 * name slugs to "" is skipped (no usable key). Pure + deterministic so the
 * oracle exercises it with in-memory fixtures (no DuckDB spin-up).
 */
export function buildAcNameIndex(
  acEntities: readonly AcEntity[],
): Map<string, AcNameInfo> {
  const index = new Map<string, AcNameInfo>();
  for (const ac of acEntities) {
    if (!slugify(ac.name)) continue;
    const key = acNameKey(ac.state, ac.name);
    const existing = index.get(key);
    // Prefer the district-bearing row over a district-less alias sharing the
    // same (state, name); otherwise last writer wins.
    if (existing && existing.district_name != null && ac.district_name == null) {
      continue;
    }
    index.set(key, {
      entity_id: ac.entity_id,
      district_name: ac.district_name,
      reservation: ac.reservation,
      eci_no: ac.eci_no,
    });
  }
  return index;
}

/**
 * Resolve one AC's canonical enrichment via the NAME bridge, or null when no
 * `(state, name)` row matches (the caller then leaves the seat ungrouped ->
 * "Other"). `state` is the canonical state slug (electoral.csv `state`, e.g.
 * "andhra-pradesh"); `name` is the result-row AC display name.
 */
export function resolveAcByName(
  index: ReadonlyMap<string, AcNameInfo>,
  state: string,
  name: string,
): AcNameInfo | null {
  return index.get(acNameKey(state, name)) ?? null;
}

/** The three enrichment fields an assembly seat row needs, resolved for a
 *  single winner: the LGD district display name, the reservation category,
 *  and the ECI ballot serial. Any field is null when unresolved. */
export interface ResolvedAcMeta {
  district_name: string | null;
  reservation: string | null;
  eci_no: number | null;
}

/**
 * Resolve one assembly winner's {district, reservation, eci_no}, trying the
 * exact `entity_id` enrichment FIRST and falling back to the `(state, name)`
 * bridge whenever the entity_id lookup yields NO DISTRICT.
 *
 * WHY the fallback keys on a missing DISTRICT, not a missing ROW: an assembly
 * RESULT winner carries the results-scheme entity_id
 * `IN-AC-<delim>-<state>-eci<NN>` (the ECI ballot-alias form). That id IS
 * present in `loadAcEnrichment`'s map - electoral.csv carries an
 * `entity_kind='ac'` row for it - but the ballot-alias form has NO membership
 * edge, so its `district_name` is null while its `reservation` + `eci_no` are
 * populated. A plain `enrichment.get(id) ?? resolveAcByName(...)` therefore
 * SHORT-CIRCUITS on the present-but-district-less row and never consults the
 * name bridge, stranding every ballot-alias winner in the list's "Other"
 * bucket. Falling back on a null `district_name` fixes that while still
 * letting the exact entity_id row win for every field it actually carries
 * (no regression for winners whose id resolves a real district edge).
 */
export function resolveAssemblyAcMeta(
  enrichment: ReadonlyMap<string, AcEnrichment> | null,
  nameIndex: ReadonlyMap<string, AcNameInfo> | null,
  stateSlug: string,
  winnerId: string,
  winnerName: string,
): ResolvedAcMeta {
  const byId = enrichment?.get(winnerId) ?? null;
  const byName =
    byId?.district_name == null && nameIndex
      ? resolveAcByName(nameIndex, stateSlug, winnerName)
      : null;
  return {
    district_name: byId?.district_name ?? byName?.district_name ?? null,
    reservation: byId?.reservation ?? byName?.reservation ?? null,
    eci_no: byId?.eci_no ?? byName?.eci_no ?? null,
  };
}

/** Minimal PC shape `buildPcGrouping` keys on: the PC winner's canonical
 *  entity_id (the AC `parent` target) and its display name (the group key +
 *  the `pc_group` stamped on each child leaf). A parliament `ElectionResultRow`
 *  satisfies this via {entity_id, entity_name}. */
export interface PcRef {
  entity_id: string;
  name: string;
}

/** One PC-mode leaf: a child AC tagged with its parent PC name (the group
 *  key) and its own LGD district label. `pc_group` is null for a
 *  re-delimitation orphan (parent PC absent from the supplied PCs) -> the
 *  component's "Other"/ungrouped path (never dropped, plan 7.2). */
export interface PcLeafEntity {
  entity_id: string;
  name: string;
  pc_group: string | null;
  district_name: string | null;
  reservation: string | null;
  eci_no: number | null;
}

/** The pure PC -> AC grouping result for one state's general page. */
export interface PcGrouping {
  /** One leaf per in-scope state AC (the live delimitation), each tagged
   *  with its parent PC name or null (orphan). */
  leaves: PcLeafEntity[];
  /** Child-AC count per PC entity_id - feeds the group header's
   *  `child_count`. Orphan leaves (null pc_group) are NOT counted. */
  childCountByPcId: Map<string, number>;
}

/**
 * Pure PC -> AC grouping for a state's general (parliament) page. Restricts
 * `acEntities` to the given state AND delimitation, tags each AC with its
 * parent PC name (from `pcs`, the state's PC winners) or null when the
 * parent PC is not among them (a re-delimitation orphan -> the component's
 * "Other" path), and counts children per PC. Never mutates input.
 *
 * `delimYear` pins the live delimitation so an old-delim AC (electoral.csv
 * carries multiple delimitation cycles) never lands in a current PC group;
 * pass null to disable the delimitation filter.
 */
export function buildPcGrouping(
  pcs: readonly PcRef[],
  acEntities: readonly AcEntity[],
  stateSlug: string,
  delimYear: number | null,
): PcGrouping {
  const pcIdToName = new Map<string, string>();
  for (const p of pcs) pcIdToName.set(p.entity_id, p.name);

  const leaves: PcLeafEntity[] = [];
  const childCountByPcId = new Map<string, number>();
  for (const ac of acEntities) {
    if (ac.state !== stateSlug) continue;
    if (delimYear != null && ac.delim_year !== delimYear) continue;
    const pcName =
      ac.parent_pc_id != null ? pcIdToName.get(ac.parent_pc_id) ?? null : null;
    leaves.push({
      entity_id: ac.entity_id,
      name: ac.name,
      pc_group: pcName,
      district_name: ac.district_name,
      reservation: ac.reservation,
      eci_no: ac.eci_no,
    });
    if (pcName != null && ac.parent_pc_id != null) {
      childCountByPcId.set(
        ac.parent_pc_id,
        (childCountByPcId.get(ac.parent_pc_id) ?? 0) + 1,
      );
    }
  }
  return { leaves, childCountByPcId };
}

// ---- Async loader (singleton-cached per page session) -----------------

interface RawElectoralEntity {
  entity_id: string;
  name: string;
  parent: string | null;
  state: string;
  // columns.json `integer` lifts to DuckDB BIGINT -> JS bigint.
  delim_year: number | bigint | null;
  reservation: string | null;
  eci_no: number | bigint | null;
}

let acEntitiesPromise: Promise<AcEntity[]> | null = null;

/** Reset the cache; for tests and HMR. Production never calls this. */
export function _resetAcEntitiesCacheForTests(): void {
  acEntitiesPromise = null;
}

/**
 * Fetch + join the canonical entity CSVs into the flat `AcEntity[]` list
 * (once per session, cached). Reuses the SAME read seam + pinned read
 * options as `loadAcEnrichment` (auto_detect off; the columns map is
 * authoritative). Callers default to an empty list until this resolves.
 */
export async function loadAcEntities(): Promise<AcEntity[]> {
  if (acEntitiesPromise) return acEntitiesPromise;
  acEntitiesPromise = (async () => {
    await Promise.all([
      registerCsvFile(MEMBERSHIP_URL),
      registerCsvFile(GEO_URL),
      registerCsvFile(ELECTORAL_URL),
    ]);
    const [membershipCols, geoCols, electoralCols] = await Promise.all([
      csvColumnsClause(MEMBERSHIP_REL),
      csvColumnsClause(GEO_REL),
      csvColumnsClause(ELECTORAL_REL),
    ]);

    const membership = await query<RawMembership>(
      `SELECT electoral_id, lgd_district_id, is_primary
         FROM read_csv('${MEMBERSHIP_URL}', ${membershipCols}, ${READ_OPTS})
        WHERE is_primary`,
    );
    const districts = await query<RawDistrict>(
      `SELECT entity_id, name
         FROM read_csv('${GEO_URL}', ${geoCols}, ${READ_OPTS})
        WHERE entity_kind = 'district'`,
    );
    const electoralAcs = await query<RawElectoralEntity>(
      `SELECT entity_id, name, parent, state, delim_year, reservation, eci_no
         FROM read_csv('${ELECTORAL_URL}', ${electoralCols}, ${READ_OPTS})
        WHERE entity_kind = 'ac'`,
    );

    return buildAcEntities(
      membership.map((m) => ({
        electoral_id: m.electoral_id,
        lgd_district_id: m.lgd_district_id,
        is_primary: Boolean(m.is_primary),
      })),
      districts,
      electoralAcs.map((e) => ({
        entity_id: e.entity_id,
        name: e.name,
        parent: e.parent ?? null,
        state: e.state,
        delim_year: e.delim_year == null ? null : Number(e.delim_year),
        reservation: e.reservation ?? null,
        eci_no: e.eci_no == null ? null : Number(e.eci_no),
      })),
    );
  })();
  // On failure, drop the cache so a later attempt re-fetches instead of
  // permanently rejecting.
  acEntitiesPromise.catch(() => {
    acEntitiesPromise = null;
  });
  return acEntitiesPromise;
}

// ===========================================================================
// Row 7 - national outer accordion (State -> PC -> AC -> District).
// TODO/20260622-election-constituency-grouping-plan.md.
// ===========================================================================
//
// The NATIONAL general page (`/t/elections/general-*`, NationalElection.svelte)
// wraps the state general list with an OUTER STATE level: the top-level groups
// are the ~36 states/UTs; expanding a state lazy-mounts the SAME PC-mode
// StateEventConstituencyList for that state (State -> PC -> AC -> District).
//
// These two PURE helpers do the render-only state selection the outer accordion
// needs - NO new data-shaping. `buildNationalStateGroups` buckets the national
// PC winners by state and calls the EXISTING `buildPcGrouping` per state (so the
// per-state PC -> AC -> District structure is byte-identical to the state page),
// and `filterNationalBranches` runs the ONE national search + Reserved filter
// across state / PC / AC names, returning only the matching branches with an
// auto-expand flag. Both are exercised by national-constituency-list.test.ts
// with bounded (1-2 state) fixtures - never the full corpus.

/** Minimal national PC winner shape `buildNationalStateGroups` keys on: the
 *  PC's canonical entity_id + display name (the group key) and which state it
 *  belongs to. A parliament `ElectionResultRow` satisfies this structurally. */
export interface NationalPcWinner {
  entity_id: string;
  entity_name: string;
  state_code: string;
  state_slug: string;
}

/** One state branch of the national list: the state's PC winners + the
 *  `buildPcGrouping` output (child AC leaves + per-PC child counts). */
export interface NationalStateGroup {
  state_code: string;
  state_slug: string;
  /** PC refs (entity_id + name) for this state, in winner order. */
  pcs: PcRef[];
  /** Child AC leaves for this state (from `buildPcGrouping`). */
  leaves: PcLeafEntity[];
  /** Child-AC count per PC entity_id (orphan leaves not counted). */
  childCountByPcId: Map<string, number>;
}

/**
 * Bucket national PC winners by state and run `buildPcGrouping` per state.
 * Pure + deterministic; REUSES `buildPcGrouping` (no new data-shaping) so each
 * state's PC -> AC -> District structure is identical to its own general page.
 * Returned sorted by state_slug for a stable order (the component resolves the
 * display name + presentation order). Never mutates input.
 */
export function buildNationalStateGroups(
  winners: readonly NationalPcWinner[],
  acEntities: readonly AcEntity[],
  delimYear: number | null,
): NationalStateGroup[] {
  const byState = new Map<
    string,
    { code: string; slug: string; pcs: PcRef[] }
  >();
  for (const w of winners) {
    let bucket = byState.get(w.state_slug);
    if (!bucket) {
      bucket = { code: w.state_code, slug: w.state_slug, pcs: [] };
      byState.set(w.state_slug, bucket);
    }
    bucket.pcs.push({ entity_id: w.entity_id, name: w.entity_name });
  }
  const out: NationalStateGroup[] = [];
  for (const bucket of byState.values()) {
    const grouping = buildPcGrouping(
      bucket.pcs,
      acEntities,
      bucket.slug,
      delimYear,
    );
    out.push({
      state_code: bucket.code,
      state_slug: bucket.slug,
      pcs: bucket.pcs,
      leaves: grouping.leaves,
      childCountByPcId: grouping.childCountByPcId,
    });
  }
  out.sort((a, b) => a.state_slug.localeCompare(b.state_slug, "en"));
  return out;
}

/** One PC the national search filter keys on: the PC's canonical id + name
 *  (searchable) + its parliament (Lok Sabha) reservation (GEN/SC/ST) so the
 *  Reserved filter narrows to SC/ST parliament seats. */
export interface NationalFilterPc {
  entity_id: string;
  name: string;
  reservation: string | null;
}

/** Input branch for `filterNationalBranches`: one state, its PCs (with
 *  reservation), its child AC leaves, and the resolved display name (the
 *  state-name search target). */
export interface NationalBranchInput {
  state_code: string;
  state_slug: string;
  state_name: string;
  pcs: readonly NationalFilterPc[];
  leaves: readonly PcLeafEntity[];
}

/** A branch selected for rendering: the (optionally filtered) PCs + leaves and
 *  whether the outer state row should auto-expand (search/filter active and
 *  matched). With no active query/filter every branch is returned with full
 *  pcs + leaves and `auto_expand=false` (first paint: all states collapsed). */
export interface NationalBranchView {
  state_code: string;
  state_slug: string;
  state_name: string;
  pcs: NationalFilterPc[];
  leaves: PcLeafEntity[];
  auto_expand: boolean;
}

/**
 * Run the ONE national search + Reserved filter across state / PC / AC names.
 * Pure + deterministic. Granularity is the PC (the parliament seat): a PC is
 * KEPT when - after the Reserved (GEN/SC/ST) filter passes on the PC - the
 * search query is empty, OR the state name matches, OR the PC name matches, OR
 * any of the PC's child ACs match; a kept PC carries ALL its child ACs so the
 * citizen sees the full seat composition. Re-delimitation orphan leaves
 * (pc_group=null) are matched directly on their own name + reservation so they
 * are never dropped (plan 7.2). A branch is returned ONLY when it has at least
 * one visible leaf, and then with `auto_expand=true`, so the national search
 * auto-expands ONLY the matching state branches. With no active query/filter
 * ALL branches are returned (full content, collapsed). Never mutates input.
 */
export function filterNationalBranches(
  branches: readonly NationalBranchInput[],
  query: string,
  reserved: ReservationKind | "All",
): NationalBranchView[] {
  const q = query.trim().toLowerCase();
  const active = q.length > 0 || reserved !== "All";

  if (!active) {
    return branches.map((br) => ({
      state_code: br.state_code,
      state_slug: br.state_slug,
      state_name: br.state_name,
      pcs: [...br.pcs],
      leaves: [...br.leaves],
      auto_expand: false,
    }));
  }

  const out: NationalBranchView[] = [];
  for (const br of branches) {
    const stateMatch = q.length > 0 && br.state_name.toLowerCase().includes(q);

    // PCs kept after the PC-level Reserved filter + the name search.
    const keptPcNames = new Set<string>();
    const keptPcs: NationalFilterPc[] = [];
    for (const pc of br.pcs) {
      if (reserved !== "All" && reservationKind(pc.reservation) !== reserved) {
        continue;
      }
      let keep =
        q.length === 0 || stateMatch || pc.name.toLowerCase().includes(q);
      if (!keep) {
        keep = br.leaves.some(
          (l) => l.pc_group === pc.name && l.name.toLowerCase().includes(q),
        );
      }
      if (keep) {
        keptPcNames.add(pc.name);
        keptPcs.push(pc);
      }
    }

    // Leaves: a child AC rides on its kept PC; an orphan (pc_group=null) is
    // matched on its own name + reservation so the "Other" bucket survives.
    const keptLeaves = br.leaves.filter((l) => {
      if (l.pc_group != null) return keptPcNames.has(l.pc_group);
      if (reserved !== "All" && reservationKind(l.reservation) !== reserved) {
        return false;
      }
      if (q.length === 0) return true;
      if (stateMatch) return true;
      return l.name.toLowerCase().includes(q);
    });

    if (keptLeaves.length === 0) continue;
    out.push({
      state_code: br.state_code,
      state_slug: br.state_slug,
      state_name: br.state_name,
      pcs: keptPcs,
      leaves: keptLeaves,
      auto_expand: true,
    });
  }
  return out;
}
