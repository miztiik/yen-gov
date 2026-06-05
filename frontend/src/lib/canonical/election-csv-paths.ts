// Per-(state, year) election CSV path builder (F1.3a).
//
// View-models receive identity in the legacy shape inherited from the
// route layer:
//   - `state_code` like "S22" (ECI ballot serial; pre-LGD vocabulary)
//   - `event_id`   like "AcGenApr2021" or "LsGenJun2024"
//                  (ECI ballot-event id; `<Kind>Gen<Month><Year>` shape)
// The on-disk CSV layout per the platform-reset plan section 21.3 keys
// instead on LGD state slugs + the 4-digit election year:
//   - assembly:   `datasets/elections/assembly/state=<slug>/election=<yr>/{candidacies,summary}.csv`
//   - parliament: `datasets/elections/parliament/election=<yr>/{candidacies,summary}.csv`
//
// This module is the single translation seam between those two
// vocabularies. Anything that builds an `read_csv('datasets/elections/...')`
// SQL fragment MUST go through these helpers - per CLAUDE.md Holy Law #6
// ("no hardcoding") + the F1.3 sub-plan's "drop the ECI st_code map"
// directive (post-F1.1 the ECI->slug map is the only callable surface).

import { electionStatePartition } from "../election-partitions";

/** Extract the trailing 4-digit year from an ECI event id like
 *  `AcGenApr2021` or `LsGenJun2024`. Throws if the id does not end
 *  in four digits - the event-id grammar guarantees a year suffix
 *  (see `frontend/src/lib/election-events.ts` `event_id` doc), so any
 *  non-matching input is a programmer error, not a runtime miss. */
export function eventYear(event_id: string): number {
  const m = event_id.match(/(\d{4})$/);
  if (!m) {
    throw new Error(`election-csv-paths: event_id "${event_id}" has no 4-digit year suffix`);
  }
  return Number(m[1]);
}

/**
 * Repo-relative CSV file_class glob shapes (matching keys in
 * `datasets/data/_schema/columns.json`). Exported so callers can
 * cross-reference the typed-read column-map helper without restating
 * the glob inline.
 */
export const ASSEMBLY_CANDIDACIES_GLOB =
  "datasets/elections/assembly/state=*/election=*/candidacies.csv" as const;
export const ASSEMBLY_SUMMARY_GLOB =
  "datasets/elections/assembly/state=*/election=*/summary.csv" as const;
export const PARLIAMENT_CANDIDACIES_GLOB =
  "datasets/elections/parliament/election=*/candidacies.csv" as const;
export const PARLIAMENT_SUMMARY_GLOB =
  "datasets/elections/parliament/election=*/summary.csv" as const;
export const ENTITIES_ELECTORAL_GLOB =
  "datasets/data/entities/electoral.csv" as const;

/** Concrete on-disk path for a per-(state, year) assembly candidacies
 *  file. Inputs are the ECI vocabulary the view-models already carry. */
export function assemblyCandidaciesPath(
  state_code: string,
  event_id: string,
): string {
  const slug = electionStatePartition(state_code);
  const year = eventYear(event_id);
  return `datasets/elections/assembly/state=${slug}/election=${year}/candidacies.csv`;
}

/** Concrete on-disk path for a per-(state, year) assembly summary file. */
export function assemblySummaryPath(
  state_code: string,
  event_id: string,
): string {
  const slug = electionStatePartition(state_code);
  const year = eventYear(event_id);
  return `datasets/elections/assembly/state=${slug}/election=${year}/summary.csv`;
}

/** Concrete on-disk path for a per-year parliament candidacies file.
 *  Parliament CSVs are NOT state-sharded (plan section 21.3 + 23.4);
 *  one file per election year carries every state's PCs. */
export function parliamentCandidaciesPath(event_id: string): string {
  const year = eventYear(event_id);
  return `datasets/elections/parliament/election=${year}/candidacies.csv`;
}

/** Concrete on-disk path for a per-year parliament summary file. */
export function parliamentSummaryPath(event_id: string): string {
  const year = eventYear(event_id);
  return `datasets/elections/parliament/election=${year}/summary.csv`;
}

/** Concrete on-disk path for the canonical AC + PC entity table. One
 *  file for every entity_id the candidacies + summary FKs target. */
export function electoralEntitiesPath(): string {
  return "datasets/data/entities/electoral.csv";
}
