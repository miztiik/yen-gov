# ADR-0050: Folder-naming convention: `state=<lgd-name-slug>` (retire `in_s01`/`in_u07` style)

**Last Updated**: 2026-06-01
**Status**: accepted
**Deciders**: User (locked 2026-06-01, supersedes per CLAUDE.md section 0a), Gregor (contract), Hans (governance precedent on name-stability), Fowler (migration mechanics)

## Context

Every partitioned dataset under `datasets/boundaries/`, `datasets/elections/`, and `datasets/indicators/` currently uses partition keys of the shape `state=in_s07`, `state=in_u05`, etc. The two-character code (`s01`-`s29` for states, `u01`-`u09` for UTs) is a yen-gov internal invention that aligns with neither ECI nor LGD:

- **ECI** state codes use a three-letter form: `S07` (state) / `U05` (UT), historically derived from Census2001 ordering.
- **LGD** state codes are the canonical 2-digit numeric (`07` = Haryana, `08` = Himachal Pradesh, etc.) issued by the Ministry of Panchayati Raj.
- **`in_s07`** is neither - it bolts an `in_` prefix onto an ECI-style code, then re-uses it as a folder label across boundary / election / indicator partitions.

Two problems compound:

1. **Convention split**: Internal partition labels diverge from BOTH external authorities. Every reader (frontend, validator, indicator adapter) carries an internal translation layer.
2. **Code instability**: LGD numeric codes have historically shifted across census cycles (Census2001 -> Census2011 reshuffles for split states, UT reorganisations like J&K 2019, Sikkim district reorg 2021). Any partition convention keyed on the numeric code inherits that churn.

The LGD-canonical plan (`TODO/20260601-lgd-canonical-plan.md`, PR #544, PR #546) made the strategic call: LGD is the canonical INTERNAL join key for every geographic entity. This ADR locks the matching FOLDER convention.

## Decision

Adopt **`state=<lgd-name-slug>`** as the canonical partition-key shape across every dataset partition that today uses `state=in_sXX` / `state=in_uXX`.

- `<lgd-name-slug>` is the kebab-case ASCII slug of the canonical LGD `state_name` (English), e.g. `haryana`, `himachal-pradesh`, `tamil-nadu`, `jammu-and-kashmir`, `andaman-and-nicobar-islands`.
- Disambiguator: there are no collisions among the 36 current state/UT names; if a future split produces a name collision (e.g. hypothetical "Telangana North" vs "Telangana South"), the slug carries the disambiguating suffix.
- Authority list: `datasets/taxonomy/lgd_states.json` (PR L1a) is the single source for the canonical slug.

### What changes

| Surface | Before | After |
| --- | --- | --- |
| Boundary partitions | `datasets/boundaries/in/ac/state=in_s07/all.geojson` | `datasets/boundaries/in/ac/state=haryana/all.geojson` |
| Election partitions | `datasets/elections/state=in_s07/election_results.parquet` | `datasets/elections/state=haryana/election_results.parquet` |
| Indicator partitions | `datasets/indicators/in/<topic>/state=in_s07/...` | `datasets/indicators/in/<topic>/state=haryana/...` |
| URL slugs (frontend) | `/s/haryana` (already name-slug) | `/s/haryana` (unchanged; URL grammar already aligned) |
| In-row columns | `state_code = "S07"` (display) + `lgd_state_id = 7` (join) | unchanged - this ADR addresses partition KEYS, not column values |

### What does NOT change

- The ballot-facing URL grammar from ADR-0048 / ADR-0049 (`/s/<slug>/ac/<eci_no>-<name>`) is already name-slug-based; URLs are unaffected.
- `state_code` columns inside row data (e.g. `S07` in `dim_acs.parquet`) stay as display labels. ADR-0049 already pins LGD codes as the join attribute.
- `entity_id` shape (ADR-0044, `IN-<state>-AC-<delim>-<eci_no>`) is unchanged.

## Rationale

### Why name-slug rather than `lgd_state_id` (the numeric)

The user's verbatim framing (2026-06-01) is the load-bearing argument:

> State names rarely change; LGD numbers historically do.

A partition key written into thousands of files is the most expensive thing in the repo to rewrite. Picking the slug-stable axis over the id-stable axis is the OWID precedent (their dataset partition keys use ISO country names + slug variants, not ISO numeric).

### Why retire `in_sXX` rather than keep both

Piece-meal coexistence is worse than either pure convention. Every reader either:
(a) builds a `name <-> in_sXX` translator inside itself (the trap), or
(b) reads partitions inconsistently across families.

Single canonical convention + a transition redirect-map (PR F1) for citizen bookmarks is the only structural fix.

### Why now (rather than fold into M2 rip silently)

A folder-naming convention IS a contract surface. Tier-A validators, conform tests, frontend `serveDatasets()`, and every external consumer (CI workflows, the Pages publish) read these paths. Treating the convention as an implicit by-product of M2 hides it from future archaeologists; an ADR makes the choice explicit, dated, and challengeable.

## Consequences

- **Migration surface**: Every Parquet partition + every `datasets/boundaries/in/<layer>/state=*` folder + every `datasets/elections/state=*` folder gets renamed in Wave 4 (M2 -> M3 -> M4 per [TODO/20260601-lgd-execution-handover.md](../../../TODO/20260601-lgd-execution-handover.md)). XL risk; serialised; single big-bang script with dry-run + manifest output.
- **Frontend redirects**: URL grammar already uses name slugs, so no citizen-facing URL break. But the partition-key change requires `frontend/src/lib/maplibre/sources.ts` and any internal references to `in_sXX` to flip. Tracked under PR F1.
- **Validator updates**: Tier-A schemas referencing `state=in_*` patterns must accept the new shape. Tracked under M2 wave.
- **Backwards lookups**: A reader handed an old `in_s07` partition path can resolve to the canonical slug via `datasets/taxonomy/lgd_states.json` (the same authority list that produced the slug). No translator service needed; it's a flat-file join.
- **No data change**: This is a partition-key rename. Row contents (every `state_code`, every `lgd_state_id`, every `entity_id`) are unchanged.

## Alternatives considered

### A. Keep `state=in_sXX`; add `lgd_state_id` as a sidecar column on every row

Rejected. Leaves the partition convention split forever. Every reader still translates. Sidecar columns address row-level join but not folder discovery.

### B. Use `state=<lgd_state_id>` (numeric: `state=07`, `state=08`)

Rejected per user verdict: LGD numeric codes have historically reshuffled (Census2001 -> 2011, J&K 2019, possible future splits). Slug-stability > id-stability for partition keys.

### C. Use ECI codes (`state=S07`)

Rejected. ECI is the issuing authority only for election artefacts; the LGD-canonical plan demotes ECI to display-only for non-electoral indicators. Using ECI for partition keys re-introduces the "chasing tails" tax for every health / fiscal / demography indicator.

### D. Versioned slug per delim cycle (`state=haryana-2008`, `state=haryana-2018`)

Rejected. Premature complexity. State-name slugs are stable across delim cycles by construction (delim re-numbers ACs, not states). If a state genuinely renames (e.g. Pondicherry -> Puducherry), the new slug ships under its own data and a one-line `slug_aliases` entry on `lgd_states.json` covers backwards lookups.

## See also

- [ADR-0044](0044-grain-over-entity.md) - entity_id shape (unchanged)
- [ADR-0048](0048-elections-drill-ia-and-tile-cartogram.md) - URL grammar (unchanged)
- [ADR-0049](0049-canonical-ac-join-key.md) - lgd_ac_id as canonical internal key
- [TODO/20260601-lgd-canonical-plan.md](../../../TODO/20260601-lgd-canonical-plan.md) - parent plan
- [TODO/20260601-lgd-execution-handover.md](../../../TODO/20260601-lgd-execution-handover.md) - wave breakdown (M2/M3/M4 executes this ADR)
- `datasets/taxonomy/lgd_states.json` - the slug authority (PR L1a)
