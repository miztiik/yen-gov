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
  recognition?: "national" | "state" | "registered_unrecognised";
  alliance?: string;
}

export interface PartiesSnapshot {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  election: string;
  parties: PartyEntry[];
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

export function fetchConstituencies(state: string): Promise<ConstituenciesCollection> {
  return fetchJson<ConstituenciesCollection>(`/reference/in/states/${state}/constituencies.json`);
}

export function fetchDistricts(state: string): Promise<DistrictsCollection> {
  return fetchJson<DistrictsCollection>(`/reference/in/states/${state}/districts.json`);
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
