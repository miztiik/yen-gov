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

export interface CandidateBio {
  // dim_candidates v1.2 (PR-S.1) biographic columns. Each field is nullable;
  // citizen UI renders the populated subset and shows “Not declared” when
  // every field is null (handled by the renderer, not by replacing nulls).
  sex: string | null;
  age: number | null;
  education: string | null;
  profession: string | null;
  constituency_type: string | null;
  party_type: string | null;
}

export interface CandidateResult {
  rank: number;
  name: string;
  party_eci_code: string | null;
  party_short: string;
  votes: number;
  vote_share_pct: number;
  is_winner?: boolean;
  /** Inline biographic row from dim_candidates.parquet (v1.2). `null` when
   *  no Statistical Report adapter has populated bio for this candidate.
   *  Replaces the retired `fetchPersonEntity()` JSON sidecar fetch path
   *  (PR-S.2, canonical pivot 1.8f). */
  bio?: CandidateBio | null;
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

// people.entity sidecar (PersonEntity, fetchPersonEntity, slugifyCandidate,
// ProvenanceGrade, FieldProvenance) was retired in PR-S.2 (canonical pivot
// 1.8f). Biographic fields now live as columns on dim_candidates.parquet
// (schema v1.2) and surface on `CandidateResult.bio`. The 3,983 per-candidate
// JSON sidecars under datasets/people/ were deleted in the same PR; the
// frontend never refetches a separate URL for bio.

