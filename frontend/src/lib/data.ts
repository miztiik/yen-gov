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
  // dim_persons / elections_candidacies biographic columns. Each field is nullable;
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
  /** Inline biographic row from the canonical person/candidacy join. `null` when
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

// DistrictEntry / DistrictsCollection / fetchDistricts were retired in
// Phase-0 closeout T.0c-ii-B.2. The district list now flows through
// `view-models/districts.ts` against `taxonomy.entities` via DuckDB-WASM.
// The hand-authored `datasets/reference/in/states/<S>/districts.json`
// files remain on disk as curator input feeding `entities.parquet`; the
// frontend just no longer fetches them directly.

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
  notes?: string;
}

export interface StatesCollection {
  $schema: string;
  $schema_version: string;
  sources: SourceRef[];
  country: string;
  states: StateEntry[];
}

// Internal projection target for fetchStates() — reads the canonical entity
// catalogue, NOT the retired states.json shim. See "Strangler-fig closeout
// 2026-05-21" in TODO/20260521-states-json-port-blocker-entities-ut-gap.md
// (Phase A built canonical entities.json; Phase B ported backend consumers;
// Phase C swaps this loader + deletes datasets/reference/in/states.json).
interface EntityRow {
  entity_id: string;
  entity_type: string;
  entity_code: string;
  display_name: string;
  iso_3166_2: string | null;
  entity_valid_to: number | null;
  notes?: string | null;
}

interface EntitiesEnvelope {
  $schema: string;
  $schema_version: string;
  sources?: SourceRef[];
  entities: EntityRow[];
}

import { DATA_BASE } from "./paths";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${DATA_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`fetch ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

/**
 * Load the current set of Indian states and UTs as `StatesCollection`.
 *
 * Backed by `datasets/taxonomy/entities.json` (canonical entity catalogue
 * with temporal validity windows). We filter to current rows
 * (`entity_valid_to === null`) and entity_type in {state, ut}, then project
 * the upstream {entity_code, display_name, entity_type, iso_3166_2, notes}
 * onto the historical `StateEntry` shape so call sites (Home.svelte,
 * ScopePicker.svelte, states.svelte.ts) keep their existing field names.
 * The `entity_type === "ut"` value is translated to `kind: "union_territory"`
 * to preserve the legacy enum that downstream filters key off of.
 *
 * The legacy `datasets/reference/in/states.json` shim was deleted in Phase C
 * of the strangler-fig closeout (see top-of-file comment on `EntityRow`).
 * The `capital` field that lived on the shim had ZERO downstream consumers
 * per the Phase A audit and is intentionally not projected.
 */
export function fetchStates(): Promise<StatesCollection> {
  return fetchJson<EntitiesEnvelope>("/taxonomy/entities.json").then(env => ({
    $schema: env.$schema,
    $schema_version: env.$schema_version,
    sources: env.sources ?? [],
    country: "IN",
    states: env.entities
      .filter(
        e =>
          (e.entity_type === "state" || e.entity_type === "ut") &&
          e.entity_valid_to === null
      )
      .map<StateEntry>(e => ({
        eci_code: e.entity_code,
        iso_3166_2: e.iso_3166_2 ?? "",
        name: e.display_name,
        kind: e.entity_type === "ut" ? "union_territory" : "state",
        ...(e.notes ? { notes: e.notes } : {}),
      })),
  }));
}

export function fetchConstituencies(state: string): Promise<ConstituenciesCollection> {
  return fetchJson<ConstituenciesCollection>(`/reference/in/states/${state}/constituencies.json`);
}

// fetchDistricts retired in Phase-0 closeout T.0c-ii-B.2 — see the
// view-model loader at `view-models/districts.ts`.

// people.entity sidecar (PersonEntity, fetchPersonEntity, slugifyCandidate,
// ProvenanceGrade, FieldProvenance) was retired in PR-S.2 (canonical pivot
// 1.8f / S.1). Biographic fields now live on dim_persons/elections_candidacies
// (schema v1.2) and surface on `CandidateResult.bio`. The 3,983 per-candidate
// JSON sidecars under datasets/people/ were deleted in the same PR; the
// frontend never refetches a separate URL for bio.

