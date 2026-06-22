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
