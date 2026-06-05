# ECI + census decommission sweep — receipt (2026-06-05)

PR-stage **0e** of the B2b.5 elections clean-start reingest
([TODO/20260604-b2b5-elections-reingest-subplan.md](../../TODO/20260604-b2b5-elections-reingest-subplan.md)
section "Round-8 ECI + census decommission sweep", steps 1–4).

## Outcome (TL;DR)

The mandated sweep (`grep -rniE 'eci_st_code|\bst_code\b|state=in_[su][0-9]{2}'`
across `datasets/` + `backend/yen_gov/` + `frontend/src/`, plus the
census-as-join-key grep) was run. **The elections-owned spine is already
compliant**; the `eci_st_code` (ECI STATE/UT code `S22`/`U08`) token survives
**only as a live internal translation key** (legacy-parquet `IN-S22` → LGD slug)
in **cross-subsystem datapoint loaders + the Hive partition grammar that the
elections sub-plan does NOT own** (per the sub-plan's own step 4: "clean each hit
in the chunk that OWNS that surface … cross-surface hits get a one-line
forward-pointer so the owning chunk picks them up").

Achieving the gate's repo-wide zero-state is therefore a **coordinated
cross-subsystem migration** (≥7 backend surfaces + 8 live test files + a frontend
reader + the boundary/manifest partition grammar — the last of which is **already
in flight** in the parallel boundary slug-partition chunk). It is forward-pointed
below, not executed here, to avoid a head-on collision with that in-flight work
and a same-PR rewrite of subsystems outside elections.

**Gate `eci-census-decommission-sweep` status: NOT YET ZERO (re-scoped).** This
receipt is the audit deliverable; the gate-closing repoint is tracked as a
coordinated lift (see "Forward-pointers" + "Scope note").

### Invariants verified compliant

- **`eci_no` RETAINED.** `datasets/data/entities/electoral.csv` header carries
  `entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation`.
  `eci_no` (the per-constituency serial, NOT the state code) is the candidacies
  bind key for B2b.5.2+. A sweep that strips it would be a regression; it is intact.
- **Census codes are LABEL-only, never join keys.** The census grep found zero
  `JOIN`/`WHERE`/`merge`/`==`/`.get(` lookups keyed on `census_2001_code` /
  `census_2011_code`. The only hits are the two seed emitters
  ([state_codes_csv.py](../../backend/yen_gov/canonical/seed/state_codes_csv.py#L107-L108),
  [geo_csv.py](../../backend/yen_gov/canonical/seed/geo_csv.py#L195-L196)) writing
  the columns from the parsed LGD snapshot. They renumber + go null for post-2011
  entities (Telangana / Ladakh / DNHDD), so they are honest labels, never keys.
- **State spine already dropped `eci_st_code`.**
  `datasets/data/entities/state_codes.csv` (0b, #763) has no `eci_st_code` column;
  `columns.json` notes confirm it is "NOT carried (round-8 decommission)".

## Classified hits

Disposition legend: **DROPPED** = removed from the elections spine already ·
**RETAINED-BRIDGE** = deliberately kept as the documented `S<NN>`→slug translation
alias the cross-surface loaders read · **FORWARD** = live consumer owned by another
chunk, repointed there · **FALSE-POS** = doc/comment mention, no live column/key ·
**RETAINED-eci_no** = the constituency serial, not a sweep target.

### A. Elections-owned spine (this sub-plan) — already compliant

| File:line | Token | Disposition |
| --- | --- | --- |
| `backend/yen_gov/canonical/seed/state_codes_csv.py:19` | `eci_st_code` (docstring "DROPPED") | DROPPED — spine has no such column |
| `datasets/data/_schema/columns.json:41,53` | `eci_st_code` (notes "NOT carried"/"DROPPED") | FALSE-POS — notes only, no column |
| `backend/yen_gov/canonical/seed/geo_csv.py:20,80,90,124` | `eci_st_code` → `geo.csv` `aliases` token | RETAINED-BRIDGE — see §B rationale; geo.csv keeps `S<NN>` alias so the cross-surface resolvers keep working until they pivot |
| `datasets/data/entities/electoral.csv` (header) | `eci_no` | RETAINED-eci_no — candidacies bind key |
| `datasets/data/entities/state_codes.csv` | — | DROPPED — no `eci_st_code` column (0b) |

### B. Cross-subsystem LIVE consumers — FORWARD to owning chunk

`eci_st_code` is the relational join key inside the **legacy source parquets**
(keyed `IN-S22`); these loaders translate it to the LGD slug **at the write
boundary** when projecting to the slug-keyed canonical CSVs. The committed CSV
outputs under `datasets/data/datapoints/geo/` are **already slug-keyed**
(`andhra-pradesh`, `andhra-pradesh/<district>`), so `eci_st_code` is an
**input-translation artifact**, not a canonical-output column. Each loader can
pivot to read the `S<NN>` token from `geo.csv` aliases (which already carries it)
instead of `lgd_states.json` — a mechanical repoint owned by each loader's chunk.

| File:line | Token | Owning chunk (forward-pointer) |
| --- | --- | --- |
| `backend/yen_gov/canonical/reingest/energy_datapoints.py:55-93` | `eci_st_code`→slug map | **B2b.1 energy** — repoint `load_eci_to_slug()` to geo.csv aliases |
| `backend/yen_gov/canonical/reingest/livestock_datapoints.py:57-152` | `eci_st_code`/district translate | **B2b.2 livestock** — same repoint |
| `backend/yen_gov/canonical/reingest/governments_term_shape.py:117-174` | reads geo.csv `S<NN>` alias | **B2b.3 governments** — ALSO must re-key `datasets/data/datapoints/office_holdings.csv` (still emits `IN-S<NN>` ids — the one canonical output not yet slug-migrated) BEFORE the geo.csv alias can drop |
| `backend/yen_gov/canonical/reingest/state_tiers.py:71` | `st_code`→slug | **state-tiers owner** |
| `backend/yen_gov/canonical/reingest/election_events.py:77` | `st_code`→slug | **election-events owner** |
| `backend/yen_gov/canonical/reingest/ac_crosswalk.py:67` | `st_code`→slug | **0d-del** deletes `ac_crosswalk.*` outright — resolves on delete |
| `backend/yen_gov/canonical/adapters/eci/state_slug.py:1-39` | `eci_to_lgd_slug()` bridge | retire once all callers pivot to geo.csv |
| `backend/yen_gov/canonical/adapters/eci_ae_panel.py:749-750`, `eci_ls.py:498-499` | ADR-0050 inventory join-key | **inventory/adapters owner** (translate at write boundary, per ADR-0050) |
| `backend/yen_gov/canonical/writer.py:205-235` | `_eci_to_lgd_slug_case_sql()` Hive-partition CASE | **boundary/partition chunk** (in flight) — see §C |
| `backend/yen_gov/sources/datagovin_ogd/ingest_pincode_polygons.py:240-259` | `_ECI_TO_LGD_SLUG()` partition bucket | **pincode/boundary owner** |

### C. Hive partition grammar `state=in_s22` — FORWARD to boundary chunk (IN FLIGHT)

The `in_s<NN>` partition-key grammar is the legacy elections-parquet + boundary
partition spine. It is **already mid-migration to slug partitions** in the
parallel boundary slug-partition chunk (the same migration whose interim state
produces the 35 pre-existing `pytest (ingest pipeline, non-admin)` baseline
failures on `main`: `test_ac_parity_per_state`, `test_rename_partition_keys`,
`test_people_ingest`). The elections sub-plan must NOT touch this concurrently.

| File:line | Token | Owning chunk |
| --- | --- | --- |
| `datasets/schemas/boundary-layers.schema.json:62,84` | `state=in_s22` path grammar | boundary slug-partition chunk (in flight) |
| `datasets/schemas/manifest.schema.json:26,91` | `=`/`in_s22` path pattern | boundary/manifest chunk |
| `datasets/boundaries/boundary_layers.parquet` (binary) | partition values | boundary chunk |
| `datasets/migration-ledger.csv:203` | `state=in_s22` example | doc/ledger — FALSE-POS (historical example) |

### D. Frontend — FORWARD to F1 / X1a (reader flip)

| File:line | Token | Owning chunk |
| --- | --- | --- |
| `frontend/src/lib/canonical/indicator-from-canonical.ts:73-84` | `canonicalEntityToLegacy('IN-S22')→'S22'` | **F1/X1a** — on the being-retired legacy-parquet read path; dead code once the canonical allowlist covers all citizen indicators |
| `frontend/src/lib/canonical/indicator-from-canonical.test.ts:1255-1695` | test of the above | retires with the function |

### E. Taxonomy source + schema — dies with `lgd_states.json` (0d-del / X1b)

| File:line | Token | Disposition |
| --- | --- | --- |
| `datasets/taxonomy/lgd_states.json:20-405` | `eci_st_code` (36 rows) | RETAINED-BRIDGE — upstream map the §B loaders read; the spine (`state_codes.csv`) no longer reads it. Deleted when the taxonomy JSON is retired (0d-del / X1b) AFTER all §B readers pivot to geo.csv |
| `datasets/schemas/lgd-states.schema.json:11,36,67` | `eci_st_code` field | retires with `lgd_states.json` |

## Why gate-closure is re-scoped (not executed here)

1. **Cross-subsystem, not elections-owned.** The live `eci_st_code` readers are
   energy / livestock / governments / state-tiers / election-events / pincode /
   inventory-adapters + the boundary partition grammar + the frontend reader.
   The sub-plan's step 4 explicitly forward-points these to their owning chunks.
2. **8 currently-green test files** would turn red the instant `eci_st_code`
   leaves `lgd_states.json` or the `geo.csv` alias, until each owning chunk
   repoints its loader + fixtures
   (`test_csv_parquet_parity` energy/livestock/state_tiers/election_events/ac_crosswalk,
   `test_seed_geo_csv`, pincode ingest, writer CASE).
3. **`office_holdings.csv` is not slug-migrated** — the governments family must
   re-key its committed output to slugs (B2b.3 territory) before the geo.csv
   bridge alias can drop.
4. **The `in_s22` partition migration is already in flight** in the boundary
   chunk; a concurrent elections-side rewrite would collide.
5. **The citizen payload does not depend on this.** The election RESULTS
   (`electoral.csv`, Tier R, B2b.5.2/5.3/5.4) bind via `eci_no` (RETAINED),
   never `eci_st_code`. Delivering them is unblocked.

The gate-closing repoint is therefore a coordinated lift, sequenced into the
ECI→slug transition already underway in B2b/B3/X1a, with each §B/§C/§D hit cleaned
by its owning chunk. This receipt is the audit + forward-pointer set that lets
those chunks pick up their share.

## Sweep commands (reproducible)

```
git grep -niE 'eci_st_code'                  -- backend/yen_gov frontend/src datasets ':!datasets/ephemeral'
git grep -niE '\bst_code\b'                  -- backend/yen_gov frontend/src
git grep -niE 'state=in_[su][0-9]{2}'        -- backend/yen_gov frontend/src datasets ':!datasets/ephemeral'
git grep -niE 'census_20(01|11)_code'        -- backend/yen_gov frontend/src
```
