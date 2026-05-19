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
  recognition?: string | null;
  alliance?: string | null;
  seats_contested: number | null;
  seats_won: number;
  votes: number;
  vote_share_pct: number;
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
  /** Total candidates contesting the AC seat — kept rows + collapsed tail.
   *  Sourced from `ac-candidates-total` observation; equals `candidates.length`
   *  when no tail exists. Optional for back-compat with fixtures that predate
   *  Phase 1.6. */
  candidates_total?: number;
  winner: WinnerInfo;
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

