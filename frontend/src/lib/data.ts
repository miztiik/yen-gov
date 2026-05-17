// Schema-shaped TypeScript views over the datasets/ artifacts. These mirror
// datasets/schemas/{result.summary,result.constituency,party,state,constituency}.schema.json.
// If a schema bumps (CLAUDE.md §11), update these in the same commit.

export interface SourceRef {
  url: string;
  fetched_at: string;
}

export interface PartyTotals {
  party_eci_code: string | null;
  party_short: string;
  party_full: string | null;
  seats_contested: number | null;
  seats_won: number;
  votes: number;
  vote_share_pct: number;
}

export interface ResultSummary {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  election: string;
  state: string;
  body: string;
  total_seats: number;
  totals: { electors?: number; votes_polled?: number; turnout_pct?: number } | null;
  party_totals: PartyTotals[];
}

export interface CandidateResult {
  rank: number;
  name: string;
  party_eci_code: string | null;
  party_short: string;
  votes: number;
  vote_share_pct: number;
  is_winner?: boolean;
}

export interface NotaResult { votes: number; vote_share_pct: number; }
export interface OthersBucket { candidate_count: number; votes: number; vote_share_pct: number; }
export interface WinnerInfo {
  name: string;
  party_eci_code: string | null;
  party_short: string;
  votes: number;
  margin_votes: number;
  margin_pct: number;
}

export interface ConstituencyResult {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  election: string;
  state: string;
  body: string;
  eci_no: number;
  constituency_name?: string;
  totals: { electors?: number; votes_polled: number; turnout_pct?: number };
  candidates: CandidateResult[];
  nota: NotaResult;
  others: OthersBucket | null;
  top_n_cutoff: number;
  winner: WinnerInfo;
}

export interface PartyEntry {
  eci_code: string;
  short_name: string;
  full_name: string;
  symbol?: string;
  recognition?: "national" | "state" | "registered_unrecognised" | "unknown";
  alliance?: string;
}

export interface PartiesSnapshot {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  election: string;
  parties: PartyEntry[];
}

/**
 * One entry in the central party registry returned by `fetchPartyRegistry`.
 *
 * Unlike the per-event `PartyEntry` (where `eci_code` is required, since the
 * per-event schema rejects unresolved labels), the registry entry models the
 * full lifecycle: a party may exist with `eci_code: null` (master entry whose
 * code we have not yet observed in any cohort) and / or with `recognition:
 * "unknown"` (auto-extended discovered overlay, awaiting operator triage).
 *
 * `source` records which layer the entry came from so callers can render
 * a "(unverified — from upstream)" badge on `discovered` entries instead of
 * silently presenting them as recognised.
 */
export interface PartyRegistryEntry {
  eci_code: string | null;
  short_name: string;
  full_name: string;
  recognition: "national" | "state" | "registered_unrecognised" | "unknown";
  recognized_in_states?: string[];
  aliases?: string[];
  source: "master" | "discovered";
}

export interface PartyRegistry {
  /** short_name (canonical OR alias) → registry entry. */
  byShort: Record<string, PartyRegistryEntry>;
  /** eci_code → registry entry (only entries whose code is known). */
  byEciCode: Record<string, PartyRegistryEntry>;
}

interface PartiesMasterFile {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  parties: Array<{
    eci_code?: string | null;
    short_name: string;
    full_name: string;
    recognition: "national" | "state" | "registered_unrecognised";
    recognized_in_states?: string[];
    aliases?: string[];
  }>;
}

interface PartiesDiscoveredFile {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  parties: Array<{
    eci_code?: string | null;
    short_name: string;
    full_name: string;
    recognition: "unknown";
    first_seen: { election_id: string; state_code: string };
    sources: SourceRef[];
  }>;
}


export interface ConstituencyEntry {
  eci_no: number;
  name: string;
  district_id?: string;
  pc_id?: string;
  electors?: number;
  established_year?: number;
  reservation: "GEN" | "SC" | "ST";
  notes?: string;
}

export interface DistrictEntry {
  id: string;
  id_source: "lgd" | "wikipedia";
  name: string;
  headquarters?: string;
  created_on?: string;
  split_from?: string[];
  notes?: string;
}

export interface DistrictsCollection {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  state: string;
  districts: DistrictEntry[];
}

export interface ConstituenciesCollection {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  state: string;
  body: string;
  status: "provisional" | "complete";
  constituencies: ConstituencyEntry[];
}

export interface StateEntry {
  eci_code: string;
  iso_3166_2: string;
  name: string;
  kind: "state" | "union_territory";
  capital?: string;
  notes?: string;
}

export interface StatesCollection {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  country: string;
  states: StateEntry[];
}

import { DATA_BASE } from "./paths";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${DATA_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`fetch ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function fetchStates(): Promise<StatesCollection> {
  return fetchJson<StatesCollection>("/reference/in/states.json");
}

export function fetchResultSummary(event: string, state: string): Promise<ResultSummary> {
  return fetchJson<ResultSummary>(`/elections/${event}/${state}/result.summary.json`);
}

export function fetchParties(event: string, state: string): Promise<PartiesSnapshot> {
  return fetchJson<PartiesSnapshot>(`/elections/${event}/${state}/parties.json`);
}

/**
 * Load the central party registry (master + auto-extended discovered overlay)
 * and return a merged lookup map.
 *
 * Merge policy mirrors the backend (`backend/yen_gov/pipeline/compose.py:
 * load_eci_party_registry`):
 *
 *   1. Discovered overlay loads first (`recognition: "unknown"`, `source:
 *      "discovered"`).
 *   2. Master loads second and overwrites by `short_name` — operator
 *      curation always wins over auto-extended labels.
 *   3. Master `aliases[]` populate additional `byShort` keys that resolve
 *      to the canonical entry, but never overwrite an entry already
 *      present (an alias must not collide with a real short_name).
 *
 * Both files are 404-tolerant: a fresh checkout without the discovered
 * overlay still returns a registry built from the master alone (and vice
 * versa). Returns an empty registry only if BOTH files 404 — that case
 * means the static bundle is broken, not a normal runtime state.
 */
export async function fetchPartyRegistry(): Promise<PartyRegistry> {
  const [master, discovered] = await Promise.all([
    fetch(`${DATA_BASE}/reference/in/parties.json`).then(async r =>
      r.status === 404 ? null : r.ok ? ((await r.json()) as PartiesMasterFile) : null,
    ),
    fetch(`${DATA_BASE}/reference/in/parties-discovered.json`).then(async r =>
      r.status === 404 ? null : r.ok ? ((await r.json()) as PartiesDiscoveredFile) : null,
    ),
  ]);

  const byShort: Record<string, PartyRegistryEntry> = {};
  const byEciCode: Record<string, PartyRegistryEntry> = {};

  // Layer 1: discovered overlay (lower priority).
  for (const p of discovered?.parties ?? []) {
    const entry: PartyRegistryEntry = {
      eci_code: p.eci_code ?? null,
      short_name: p.short_name,
      full_name: p.full_name,
      recognition: "unknown",
      source: "discovered",
    };
    byShort[p.short_name] = entry;
    if (entry.eci_code) byEciCode[entry.eci_code] = entry;
  }

  // Layer 2: master (overwrites discovered for the same short_name).
  for (const p of master?.parties ?? []) {
    const entry: PartyRegistryEntry = {
      eci_code: p.eci_code ?? null,
      short_name: p.short_name,
      full_name: p.full_name,
      recognition: p.recognition,
      recognized_in_states: p.recognized_in_states,
      aliases: p.aliases,
      source: "master",
    };
    byShort[p.short_name] = entry;
    if (entry.eci_code) byEciCode[entry.eci_code] = entry;
    for (const alias of p.aliases ?? []) {
      if (!(alias in byShort)) byShort[alias] = entry;
    }
  }

  return { byShort, byEciCode };
}


export function fetchConstituencies(state: string): Promise<ConstituenciesCollection> {
  return fetchJson<ConstituenciesCollection>(`/reference/in/states/${state}/constituencies.json`);
}

export function fetchDistricts(state: string): Promise<DistrictsCollection> {
  return fetchJson<DistrictsCollection>(`/reference/in/states/${state}/districts.json`);
}

// people.entity sidecar — biographics ECI publishes only in PDF Statistical
// Reports (sex/age/education/profession) keyed off (election, ac, slug).
// Mirrors datasets/schemas/people.entity.schema.json v1.0. Optional fields
// are absent (not "Unknown") when not declared; field_provenance carries a
// grade entry only for populated fields.
export type ProvenanceGrade =
  | "issuing_authority"
  | "sworn_declaration"
  | "third_party_curated"
  | "derived";
export interface FieldProvenance { grade: ProvenanceGrade; source_id: string; }

export interface PersonEntity {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  election_id: string;
  state: string;
  ac_code: number;
  candidate_slug: string;
  name: string;
  party_short: string;
  sex?: "Male" | "Female" | "Other";
  age?: number;
  constituency_type?: "GEN" | "SC" | "ST";
  education?: string;
  profession?: string;
  field_provenance?: Record<string, FieldProvenance>;
}

// Stable lowercase slug — must mirror backend's
// yen_gov.sources.eci.people_panel.slugify so the URL composer here lines
// up with the artifact filename written on the producer side. Citizen
// never sees this slug; it is purely the join key.
export function slugifyCandidate(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function fetchPersonEntity(
  election: string,
  ac_code: number,
  candidate_slug: string,
): Promise<PersonEntity | null> {
  // 404-tolerant: not every (election, AC, candidate) triple has a
  // biographic sidecar (only ingested ECI Statistical Report slices do,
  // currently TN AE 2021). Absence is the normal "not yet ingested" path,
  // not an error.
  return fetch(
    `${DATA_BASE}/people/${election}/${ac_code}/${candidate_slug}.json`,
  ).then(async res => {
    if (res.status === 404) return null;
    if (!res.ok) {
      throw new Error(
        `fetch /people/${election}/${ac_code}/${candidate_slug}.json failed: ${res.status} ${res.statusText}`,
      );
    }
    return (await res.json()) as PersonEntity;
  });
}

export function fetchConstituencyResult(
  event: string,
  state: string,
  eci_no: number,
): Promise<ConstituencyResult | null> {
  // Per-AC results are absent when the constituency was countermanded /
  // postponed (the backend skips emitting a stub — see sources-eci.md).
  // A 404 here is therefore expected, not an error: callers render the
  // "no result published" state. Other failures still throw.
  return fetch(`${DATA_BASE}/elections/${event}/${state}/results/${eci_no}.json`)
    .then(async res => {
      if (res.status === 404) return null;
      if (!res.ok) {
        throw new Error(
          `fetch /elections/${event}/${state}/results/${eci_no}.json failed: ${res.status} ${res.statusText}`,
        );
      }
      return (await res.json()) as ConstituencyResult;
    });
}
