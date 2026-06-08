# Level-4 plan: rip `datasets/reference/in/states/<S>/constituencies.json` SoT, standardise on LGD taxonomy

**Last Updated**: 2026-06-03 (fifth amendment; see sections 0d-correction + 0e)

**Predecessor**: [docs/archive/plans/20260530-eci-to-lgd-acid-migration-plan.md](../docs/archive/plans/20260530-eci-to-lgd-acid-migration-plan.md) (LGD AC_ID join-key migration; merged through PRs #530-#539). That plan landed the `taxonomy/ac_crosswalk.parquet` spine; this plan retires the **per-state ECI-keyed SoT shards** that the spine made redundant.

**Mandate** (verbatim, 2026-06-02): *"dont need a fig - just rip and replace. and retire all eci - use taxonomy and standardize on LGD ... first plan-doc and then follow the plan with big-bang"*. User authorisation per CLAUDE.md section 0a: no strangler-fig, no parallel-read window, single-PR rip-and-replace authorised.

---

## section 0. Why this plan-doc exists

The post-PR-#539 audit confirmed that the SoT shards are largely redundant with `taxonomy/ac_crosswalk.parquet`. Two facts initially looked like they only lived on the SoT shards. **Section 0a (below) records the data audit that ran after this plan-doc landed on main**; the audit invalidated one premise and confirmed the other, so the live scope is narrower than the original plan-doc claimed.

---

## section 0a. Data-audit findings (2026-06-02, post-merge of plan-doc PR #605)

Before executing R1, ran a row-count audit of the SoT shards against the taxonomy. Findings:

1. **`district_id` is DEAD.** Of 4113 AC rows across 31 SoT shards, only 824 (20%) have any value, in only 5 states (S03, S11, S22, S25, U07). The populated values are short author-internal strings (`'KOK'`, `'KAS'`, `'TAL'`, `'COB'`, `'puducherry'`) - **NOT LGD district codes**. The proper LGD-keyed hook already exists in the taxonomy: [`datasets/taxonomy/lgd_ac_pc_district_map.json`](../datasets/taxonomy/lgd_ac_pc_district_map.json) (232 rows of `(lgd_state_id, lgd_ac_id) -> [lgd_district_ids]`) + [`datasets/taxonomy/lgd_acs.json`](../datasets/taxonomy/lgd_acs.json) (carries `lgd_pc_id` + `lgd_state_id` per AC). Exactly one consumer ([`tools/boundaries/s03_t4_district_fallback.py`](../tools/boundaries/s03_t4_district_fallback.py)) reads the SoT field, and it already maintains its own hardcoded `SOT_CODE_TO_DIST_LGD` 35-entry translator because the SoT codes are not LGD-joinable. **Consequence: R1 is DROPPED.** No lift; just delete the dead field with the SoT shards and rewire `s03_t4_district_fallback.py` to read from `lgd_ac_pc_district_map.json` in R3.

2. **Per-state ECI provenance IS unique** to the SoT shards (`sources[].url` + `fetched_at` per state). R2 stands as authored.

3. **Lesson distilled**: before executing a multi-PR data-lift plan, verify the plan's load-bearing premises against the actual data, not from one sample row. The plan-doc R1 was authored after reading `S01:1 Ichchapuram` only, where `district_id: null` was apparently misread as `district_id present`. Recording in `/memories/lessons.md`.

---

## 0b. Second audit finding (2026-06-03) -- frontend consumer chain missed

The R3 framing "single big-bang PR rewriting 7 backend consumers" was undersized. A grep across `frontend/src/` surfaced 5 additional consumers of `datasets/reference/in/states/<S>/constituencies.json`, served at runtime as `/reference/in/states/<S>/constituencies.json` via Vite middleware:

- [frontend/src/lib/data.ts](frontend/src/lib/data.ts#L210) -- `loadConstituencies(state)` JSON-fetches the SoT shard. Load-bearing on every state overview page.
- [frontend/src/lib/data.test.ts](frontend/src/lib/data.test.ts#L90) -- vitest unit pinning the above with a URL mock.
- [frontend/src/routes/StateOverview.svelte](frontend/src/routes/StateOverview.svelte#L694) -- consumes `loadConstituencies` behind a 3-state `acs_status` (loading / ready / failed) discriminator that races the DuckDB-WASM summary loader.
- [frontend/src/lib/view-models/districts.ts](frontend/src/lib/view-models/districts.ts#L31) -- reads `constituencies[].district_id`, the very field R1 dropped after the audit showed 80% null and non-LGD values.
- [frontend/src/lib/maplibre/sources.ts](frontend/src/lib/maplibre/sources.ts#L463) -- code comment referencing U08 SoT shard (deletable update).

Consequence: the rip cannot be a single PR. The frontend consumer is NOT mechanical -- it requires a new DuckDB-WASM view exposing AC rows from `taxonomy/ac_crosswalk.parquet`, plus a districts view-model that LGD-joins via `taxonomy/lgd_ac_pc_district_map.json` instead of trusting the SoT `district_id`. Per user mandate (2026-06-03), R3 splits into R3a (frontend migration, parallel-readable) and R3b (the rip, depends on R3a on main). Pattern: Parallel Change -- EXPAND/MIGRATE in R3a, CONTRACT in R3b.

---

## 0c. Third audit finding (2026-06-03) -- R2 dropped, the 30 missing URLs are orphan-by-design

Before executing R2, audited the actual writer pattern for `taxonomy/sources.parquet`. Findings:

1. **The sources table is a CITATION LEDGER, not an audit-trail dump.** Per CLAUDE.md §12 and ADR-0032: every row in `sources.parquet` exists because at least one observation row carries it as `source_id` FK. The existing writers (`energy_sources_seed.py`, `livestock_sources_seed.py`, `boundary_layers_seed.py`) all follow this shape -- they DELETE owned `(producer, title)` slots then INSERT, ensuring every emitted source_id matches a downstream consumer's FK.
2. **The 30 missing SoT URLs (audit in section 0a + 0b) have NO downstream FK consumer post-rip.** They're a mix of bootstrap-era Wikipedia constituency-list pages, HindustanTimesLabs shapefile (Rajasthan), and per-state ECI XLSXes that were the SoT shard's authoring provenance. None are referenced by `ac_crosswalk.parquet` (which carries 1 distinct `source_id` for the boundary-AC_ID harvest, NOT 30+ for the per-state SoT bootstrap). The 13 SoT URLs that ARE already in `taxonomy/sources.parquet` got there via other seeds (ECI Statistical Reports cited by `election_results.parquet`).
3. **Adding 30 orphan rows would VIOLATE the citation-ledger invariant in reverse**: rows on the FK-target side with no observation FK on the source side are litter. The ledger pattern requires each row to justify its existence with a downstream reference. None of these 30 do post-rip.
4. **Git history preserves the URLs forever.** Anyone asking "where did S22's SoT shard originally cite?" answers via `git log -p docs/archive/plans/... -- datasets/reference/in/states/S22/constituencies.json` (or the same path before its R3b deletion).

**Consequence: R2 is DROPPED.** Status Reckoner updated. Sequencing collapses to R3a -> R3b -> R4. R3b commit body must include the audit-finding rationale so the deleted URLs' fate is recorded in the merge log.

---

## 0d. Fourth audit finding (2026-06-03) -- R3a would regress district grouping; insert R3a-pre to backfill `lgd_ac_pc_district_map.json`

Before executing R3a, audited what `frontend/src/lib/view-models/districts.ts` would see after the cutover. Findings:

1. **The existing `taxonomy/lgd_ac_pc_district_map.json` has 5.6% per-AC coverage** (232 rows for ~4113 ACs, mostly U08/J&K). Cutting `districts.ts` over to this map without backfill would break district-grouping on every state hub except J&K -- ACs would fall to the empty-bucket `""` in [frontend/src/routes/StateOverview.svelte](frontend/src/routes/StateOverview.svelte#L474). Citizen verdict: that is a real UX regression on the 5 SoT-author-coded states (S03, S11, S22, S25, U07) where the current behaviour groups by author 3-letter codes.
2. **The canonical LGD district code is already on every AC boundary feature.** [datasets/boundaries/in/ac/state=*/all.geojson](../datasets/boundaries/in/ac) carries `Dist_LGD` (numeric LGD district code) on 29 of 31 state shards plus `parent_district_lgd` on `state=assam` -- harvestable to 4010 `(lgd_state_id, lgd_ac_id, lgd_district_id)` triples. Only `state=jammu-and-kashmir` is the holdout (91 ACs, carries `seat_district_en` name-string only; reconcile against [datasets/taxonomy/lgd/districts-latest.csv](../datasets/taxonomy/lgd/districts-latest.csv) `State Code=1` -- 22 J&K districts, well-known names).
3. **Blocker uncovered: two incompatible state-id schemes coexist in the repo.** [datasets/taxonomy/lgd_states.json](../datasets/taxonomy/lgd_states.json) and boundary features (`State_LGD` property) carry **real LGD state codes** (Tamil Nadu = 33, Andhra Pradesh = 28). [datasets/taxonomy/lgd_acs.json](../datasets/taxonomy/lgd_acs.json) and [datasets/taxonomy/lgd_ac_pc_district_map.json](../datasets/taxonomy/lgd_ac_pc_district_map.json) declare a field named `lgd_state_id` but use a **different** numbering scheme (Tamil Nadu = 22, the ECI sequence). The field name is a misnomer. A boundary-driven backfill cannot merge into the map without first reconciling these. **[RETRACTED 2026-06-03 -- see section 0d-correction below.]**
4. **5 SoT-author 3-letter codes are no longer needed.** Once the boundary harvest lands in `lgd_ac_pc_district_map.json`, the `(KOK -> 294, KAR -> 292, ...)` translator [`tools/boundaries/s03_t4_district_fallback.py:SOT_CODE_TO_DIST_LGD`](../tools/boundaries/s03_t4_district_fallback.py) is redundant (R3b already plans to delete it) and the SoT shards' `district_id` string field can be dropped wholesale by R3b -- citizen-facing district grouping comes from the LGD-numeric map, not the author mnemonic.

**Consequence: insert R3a-pre as a new precondition for R3a.** Single step (per §0d-correction, R3a-pre.1 is dropped):

- **R3a-pre** -- harvest `(lgd_state_id, lgd_ac_id, [lgd_district_ids])` from 30 boundary shards (29 generic + S03) into `lgd_ac_pc_district_map.json`; J&K 91 ACs reconciled via `seat_district_en` -> `districts-latest.csv` name match. Map grows from 232 -> ~4010 rows. No schema migration needed.

R3a then becomes safe: `districts.ts` LGD-joins against a map that covers all states; `StateOverview.svelte` grouping does not regress.

**Lesson distilled**: when planning a Parallel Change that cuts a consumer over from store A to store B, the audit must verify store B's coverage matches store A's coverage at the consumer's grain. The previous audits (§0a, §0b, §0c) verified the SHAPE compatibility; only this §0d audit verified the COVERAGE compatibility. Recording in `/memories/lessons.md`.

---

## 0d-correction. Fifth amendment (2026-06-03) -- §0d Finding 3 retracted; state-id schemes ARE consistent

Before executing R3a-pre.1, ran a verification audit joining `lgd_acs.json` AC rows on `slug` to confirm the state-id scheme. Findings:

- `lgd_acs.json` row with `lgd_state_id=33` has `slug=arakkonam` (an AC in Tamil Nadu) -- matches [lgd_states.json](../datasets/taxonomy/lgd_states.json) row `lgd_state_id=33 -> Tamil Nadu` (eci `S22`).
- `lgd_acs.json` row with `lgd_state_id=28` has `slug=amalapuram` (AC in Andhra Pradesh) -- matches `lgd_state_id=28 -> Andhra Pradesh`.
- `lgd_acs.json` row with `lgd_state_id=1` has `slug=anantnag` (AC in J&K) -- matches `lgd_state_id=1 -> Jammu And Kashmir`.
- Same pattern across all 31 state-id values in `lgd_acs.json`.

**§0d Finding 3 was wrong.** The `lgd_state_id` field in both `lgd_acs.json` and `lgd_ac_pc_district_map.json` IS the canonical LGD scheme. The prior session conflated "domain spans 1-36" with "ECI-sequence" -- but LGD codes also span 1-38, and direct slug-join verification shows the values match `lgd_states.json` exactly. The boundary harvest can merge directly into the existing map without reconciliation.

**Consequence:** R3a-pre.1 is DROPPED. R3a-pre.2 becomes the sole precondition row (renamed `R3a-pre`). Sequencing collapses to R3a-pre -> R3a -> R3b -> R4.

**Lesson distilled**: a 5th-time-running audit-correction pattern. The Hans verdict applies: every load-bearing premise ("X is incompatible with Y") must be verified against the data, not against the prior session's memory of the data. The prior §0d finding cited a `State_LGD=33` boundary observation as evidence of LGD-scheme + cited the `(1,8),(2,10),...` map-state-id-domain as evidence of ECI-scheme -- both observations were correct, the inference ("therefore incompatible") was the bug. Recording in `/memories/lessons.md`.

---

## 0e. Sixth audit finding (2026-06-03) -- THREE incompatible `lgd_ac_id` schemes coexist; R3a-pre ESCALATED to Level-5

Before running the boundary backfill harvest into `lgd_ac_pc_district_map.json`, ran a final FK audit. The harvest produced 4324 `(lgd_state_id, lgd_ac_id, [lgd_district_ids])` triples. FK validation against `lgd_acs.json`: **3853 of 4324 rows reference unknown `lgd_ac_id` values**. Spot-check Tamil Nadu:

| Source | TN AC #1 example | Range | n | Scheme |
| --- | --- | --- | --- | --- |
| `datasets/boundaries/in/ac/state=*/all.geojson` `lgd_ac_id` | 33001 | 33001-33234 | 233 | state_code x 1000 + ac_no |
| `datasets/taxonomy/ac_crosswalk.parquet` `lgd_ac_id` | 33001 | 33001-33234 | 233 | same as boundary (joined cleanly: 233/233) |
| `datasets/taxonomy/lgd_acs.json` `lgd_ac_id` | 3857 | 3857-4090 | 232 | sequential per state, unrelated to ac_no |
| `datasets/taxonomy/lgd_ac_pc_district_map.json` `lgd_ac_id` | -- | -- | -- | matches `lgd_acs.json` (FK closure proven by `backend/tests/test_lgd_taxonomy.py`) |

Three DIFFERENT identifier conventions all called `lgd_ac_id`:

1. **Boundary + crosswalk style**: `state_code * 1000 + ac_no` (4113 values, full coverage).
2. **`lgd_acs.json` style**: sequential per state, source unclear (3918 values, 5 states gap-filled missing from earlier LGD-portal pull).
3. **Crosswalk's `ac_id` column** (distinct from `lgd_ac_id`): composite string `IN-<state>-AC-<delim>-<n>` (4113 values).

Overlap between scheme 1 and scheme 2 for TN: **0 / 233**. The boundary harvest cannot merge into `lgd_ac_pc_district_map.json` because the join key resolves to different rows.

**Consequence: R3a-pre is ESCALATED to Level-5.** Per CLAUDE.md §6, anything that touches the canonical data model + multiple cross-cutting taxonomy artefacts requires design consultation. Three valid resolution paths exist, each Level-5:

- **Path A (recommended): rebuild `lgd_acs.json` + `lgd_ac_pc_district_map.json` on the boundary/crosswalk scheme.** Drop the sequential-per-state scheme entirely; use `lgd_ac_id = state_code * 1000 + ac_no` everywhere; re-harvest district FK from boundaries (which now joins). Requires schema bump + migration of any reader of `lgd_acs.json`'s `lgd_ac_id`. The boundary scheme is already the de-facto canonical (used by `ac_crosswalk.parquet` which is the SoT this plan-doc is migrating TOWARDS).
- **Path B: build a same-PR scheme-translator.** `lgd_acs.json` keeps its scheme; backfill script joins boundary `(state_code, ac_no)` against crosswalk `(state_code, eci_no)` against `lgd_acs.json` `(state_id, slug)` via `ac_name`. Adds a fragile name-match step; preserves the multi-scheme mess.
- **Path C: deprecate `lgd_ac_pc_district_map.json` + `lgd_acs.json` in favour of a new map built on the canonical scheme.** Sequence the R3a frontend reader to query the new file instead. Lowest-disruption to taxonomy but adds a new file.

**No autonomous data ship.** Authoring the FINAL harvest for any of the three paths without user signoff would commit the repo to one of three different Level-5 architectures. The harvest script `tools/lgd/backfill_ac_pc_district_map.py` IS shipped with this amendment (committed under `tools/`) -- it implements the Path-A harvest mechanics (boundary -> 4324 triples, J&K name-reconciled) and is ready to re-run once the user picks a path; for Path-B it needs an extra translator step; for Path-C it stays as-is but writes to a new file. **The script has NO pytest pin** (the existing FK pytest in `backend/tests/test_lgd_taxonomy.py::test_ac_district_map_fk` would fail if the script's output were committed to `lgd_ac_pc_district_map.json` today because of the scheme mismatch).

**Lesson distilled**: when a backfill source (boundary feature) and a backfill target (taxonomy file) share a field NAME, that does NOT mean they share an ID SCHEME. Always FK-validate harvest output against target BEFORE writing. Recording in `/memories/lessons.md`. This is the THIRD finding-after-correction cycle in two sessions (§0d wrong about state-id; §0d-correction retracted; §0e found the real blocker) -- audit fatigue is real; ship one premise at a time and verify each.

---

## section 1. Hard scope (in)

- ~~Lift `district_id` per AC into `taxonomy/ac_crosswalk.parquet`~~ **DROPPED per section 0a finding 1** (dead field; LGD hook already exists via `taxonomy/lgd_ac_pc_district_map.json`).
- Lift per-state ECI provenance rows into `taxonomy/sources.parquet` with `scope_kind=state`, `scope_value=<eci_state_code>`, `body=AC`, one row per (state, ECI XLSX URL).
- Rewrite **7 consumers** to read from `taxonomy/ac_crosswalk.parquet` + `taxonomy/lgd_acs.json` + `taxonomy/sources.parquet` instead of the SoT shards:
  1. `tools/boundaries/snapshot.py` — replace `sot_ref` field stamping with crosswalk pointer
  2. `tools/boundaries/verify_ac_parity.py` — replace `(state, eci_no, name)` join against SoT with crosswalk query
  3. `tools/boundaries/s03_t4_district_fallback.py` — replace S03 SoT load with crosswalk + LGD join: `ac_crosswalk WHERE eci_state='S03'` JOIN `lgd_ac_pc_district_map.json` ON `lgd_ac_id` -> `lgd_district_ids[]`. **DELETE the hardcoded `SOT_CODE_TO_DIST_LGD` 35-entry translator** (it exists only because the SoT codes were not LGD-joinable; the LGD map replaces it). Output stays `parent_district_id` keyed to LGD numerics (compatible with downstream callers).
  4. `tools/boundaries/pipeline.json` — drop `sot_ref` fields; replace `delimitation_warning` SoT pointers with crosswalk pointers
  5. `tools/bootstrap_constituencies_from_results.py` — RETIRE entirely (it writes the SoT format we're deleting; bootstrap path moves to a single `tools/taxonomy/bootstrap_ac_crosswalk.py` if/when needed)
  6. `frontend/e2e/golden-path.spec.ts` line 153 — replace the `/data/reference/in/states/S22/constituencies.json` mock with a `/data/taxonomy/ac_crosswalk.parquet` mock (or remove the mock if the e2e doesn't need to assert on the AC list)
  7. `docs/reference/data-coverage-report.md` + `docs/reference/boundary-data-sources.md` + `tools/boundaries/README.md` — update all 3 docs to point at the taxonomy as SoT
- Delete the 36 SoT shards: `git rm -r datasets/reference/in/states/`
- Fix the 4 incidental stale ECI residues found in the 2026-06-02 survey:
  - `datasets/elections/_inventory.json` — one residual `state: "S01"` row missed by PR #575
  - `datasets/grapher/election_tile_layouts.json` — re-key `state: "S22"` -> `state: "tamil-nadu"` (cartogram coords; safe slug-rekey)
  - `datasets/schemas/boundary-layers.schema.json` + `datasets/schemas/manifest.schema.json` — loosen the `^[SU]\d{2}$` patterns to accept LGD slugs (or split into a `^[SU]\d{2}$|^[a-z]+(-[a-z]+)*$` union if a transition window is needed)
- Update [CLAUDE.md anti-pattern list](../CLAUDE.md) to forbid future writes under `datasets/reference/in/states/`.

---

## section 2. Hard scope (out)

- `datasets/taxonomy/lgd/` — already clean per 2026-06-02 audit; **DO NOT TOUCH**.
- `datasets/elections/state=<lgd-slug>/` partitions — already migrated (PR #565); **DO NOT TOUCH**.
- `datasets/migration-ledger.csv` audit rows — historical record; **DO NOT REWRITE**.
- `datasets/taxonomy/entities.json` `entity_code` field — still ECI code, by design (ADR-0036 alias model); **DO NOT RENAME**.
- Frontend URL grammar `/s/<state-slug>/ac/<eci_no>-<name-slug>` — kept per Strategy-D-hardened (`eci_no` is the citizen-facing display token); **DO NOT REWRITE**.

---

## section 3. Status Reckoner (revised 2026-06-03, fifth amendment)

| Row | Scope | PR# | Status | Depends on |
| --- | --- | --- | --- | --- |
| R1 | ~~Lift `district_id` per AC into `ac_crosswalk.parquet`~~ | -- | DROPPED (§0a audit) | -- |
| R2 | ~~Lift per-state ECI provenance into `taxonomy/sources.parquet`~~ | -- | DROPPED (§0c audit -- orphan rows would violate citation-ledger invariant) | -- |
| R3a-pre.1 | ~~Normalise `lgd_state_id` field~~ | -- | DROPPED (§0d-correction -- field already uses canonical LGD scheme) | -- |
| R3a-pre | ~~Backfill `lgd_ac_pc_district_map.json` from boundary features~~ | -- | ESCALATED to Level-5 (§0e -- three incompatible `lgd_ac_id` schemes; needs design consultation) | -- |
| R3a | Frontend migration: register `dim_acs` DuckDB-WASM view; rewrite `loadConstituencies` to query view; rewire `districts.ts` to LGD-join; update `data.test.ts` + `StateOverview.svelte` + `golden-path.spec.ts`; SoT shards stay on disk (parallel-readable) | _pending_ | PENDING | R3a-pre on main |
| R3b | The rip: rewrite 4 backend tools (`snapshot.py`, `verify_ac_parity.py`, `s03_t4_district_fallback.py`, `pipeline.json`); retire `bootstrap_constituencies_from_results.py`; `git rm -r datasets/reference/in/states/`; fix 4 incidental ECI residues; update `sources.ts:463` comment; stamp CLAUDE.md anti-pattern; update 3 docs | _pending_ | PENDING | R3a on main |
| R4 | Distil + archive plan-doc | _pending_ | PENDING | R3b |

Sequencing: R3a-pre BLOCKED on user design verdict (paths A/B/C in §0e). R3a + R3b + R4 cannot proceed until R3a-pre unblocks.

---

## section 4. Per-row acceptance gates

### ~~R1 - Lift `district_id` per AC~~ DROPPED

See section 0a finding 1. No work to do.

### ~~R2 - Lift per-state ECI provenance~~ DROPPED

See section 0c finding. Orphan rows violate citation-ledger invariant; URLs preserved in git history.

### ~~R3a-pre.1 - Normalise `lgd_state_id` field~~ DROPPED

See section 0d-correction. The `lgd_state_id` field in `lgd_acs.json` + `lgd_ac_pc_district_map.json` already uses the canonical LGD scheme verified by slug-join. No work to do.

### R3a-pre - Backfill `lgd_ac_pc_district_map.json` from boundary features

**Why:** see §0d finding 1 + 2. Map currently covers 5.6% of ACs; R3a needs ~100% to avoid regressing district grouping.

**Harvest:**
- For 29 generic state shards: read `(State_LGD, lgd_ac_id, Dist_LGD)` per feature from `datasets/boundaries/in/ac/state=*/all.geojson`.
- For S03 (Assam): read `(state_lgd, lgd_ac_id, parent_district_lgd)`.
- For U08 (J&K): per-AC `seat_district_en` (district name string) -> match against `datasets/taxonomy/lgd/districts-latest.csv` rows where `State Code=1` (22 J&K districts). Manual review of any unmatched names; commit a one-off translator if 1-2 names need it.
- Group by `(lgd_state_id, lgd_ac_id)` -> sorted unique `lgd_district_ids[]` (most ACs map to 1 district; some cross-district seats may map to multiple per LGD).
- Merge with existing 232 rows: preserve existing district lists; union with newly-harvested.
- Expected post-backfill: ~4109 rows (4113 ACs minus any unmatched J&K).

**Scope:**
- New script: `backend/yen_gov/tools/backfill_lgd_ac_pc_district_map.py` -- idempotent, runnable as `python -m yen_gov.tools.backfill_lgd_ac_pc_district_map`.
- Updated `datasets/taxonomy/lgd_ac_pc_district_map.json` (committed).
- Tier-A schema validation (file declares `$schema`/`$schema_version`).
- New pytest pin asserting per-state coverage = 100% for all states + UTs except where the boundary shard is known incomplete.

**Gates:**
- [ ] Gate 1: `validate --root .` green
- [ ] Gate 2: `pytest -q` green incl. coverage pin
- [ ] Gate 3-5: n/a (no frontend touched)

### R3a - Frontend migration (PR A; EXPAND + MIGRATE phase of Parallel Change)

**Contract decisions (resolve in PR body, not in code):**

- **View shape:** Register a new slice `dim_acs` in [frontend/src/lib/duckdb.ts](frontend/src/lib/duckdb.ts) following the existing `registerSlice` pattern used by elections + observations slices. Source: `taxonomy/ac_crosswalk.parquet` projected to columns `(state_code, eci_no, ac_name, reservation)`. District FK is NOT joined into the slice -- districts.ts joins separately against `lgd_ac_pc_district_map.json` to keep the slice single-source.
- **Return type:** Rename `Constituency` -> `AcRow` in `data.ts`; new shape `{eci_no: number, name: string, reservation: 'GEN'|'SC'|'ST'}`. Drop `district_id` (R1 audit: 80% null, non-LGD values, no longer authoritative). `ConstituenciesCollection` envelope (`{sources, state, body, status, ...}`) collapses -- DuckDB-WASM query is synchronous-after-registration, no envelope needed.
- **`acs_status` discriminator:** Collapses to a single ready-state once both reads go through the same DuckDB-WASM connection. The race window in `StateOverview.svelte:694` is an artifact of the dual-runtime (HTTP fetch vs WASM query); single-runtime removes it.
- **Test fixture:** `data.test.ts` swaps URL mock for in-memory DuckDB fixture per existing vitest pattern (cite the slice-test pattern already used for elections in `frontend/src/lib/__tests__/` or equivalent).

**Gates:**
- [ ] Gate 1: `python -m yen_gov validate --root .` green (no datasets touched, expected n/a)
- [ ] Gate 2: `pytest -q` green (no backend touched)
- [ ] Gate 3: `svelte-check` 0 errors
- [ ] Gate 4: `vitest` green incl. new `dim_acs` slice test + rewritten `data.test.ts`
- [ ] Gate 5 (browser smoke): home + TN + KL + BR state hubs + 1 AC drill, 0 console errors, **0 `/data/reference/in/states/**` 404s** (load-bearing -- proves JSON-fetch is fully gone)
- [ ] Gate 6 (e2e): `golden-path.spec.ts:153` updated; 1.5s-race mock removed or repurposed
- [ ] SoT shards REMAIN on disk post-merge (parallel-readable window for R3b)

### R3b - The rip (PR B; CONTRACT phase of Parallel Change)

**Hard precondition:** Before staging, verify `git log origin/main --oneline | grep <R3a-merge-sha>` returns the R3a squash commit. SoT shards MUST NOT be deleted until origin/main carries the frontend migration. Stamp the R3a PR# in the PR-B body under "Precondition verified".

**Scope (unchanged from original R3 minus the frontend chain):**
- Rewrite `backend/yen_gov/tools/snapshot.py` to read `ac_crosswalk.parquet` instead of SoT shards
- Rewrite `backend/yen_gov/tools/verify_ac_parity.py` similarly
- Rewrite `backend/yen_gov/lifts/s03_t4_district_fallback.py` to use `lgd_ac_pc_district_map.json`
- Update `config/pipeline.json` source refs
- Retire `backend/yen_gov/bootstrap_constituencies_from_results.py` (delete + remove from imports)
- `git rm -r datasets/reference/in/states/` (36 shards)
- Fix 4 incidental ECI residues (per original R3 scope)
- Update [frontend/src/lib/maplibre/sources.ts](frontend/src/lib/maplibre/sources.ts#L463) comment ref to U08
- Stamp CLAUDE.md anti-pattern: "Do not introduce per-state JSON shards as a SoT for canonical-store-derivable facts"
- Update 3 docs (cite the 3 doc paths from the original R3 row)

**Gates:**
- [ ] Gate 1: `validate --root .` green
- [ ] Gate 2: `pytest -q` green
- [ ] Gate 3: `svelte-check` 0 errors (only comment-ref touched in frontend)
- [ ] Gate 4: `vitest` green
- [ ] Gate 5 (browser smoke): same routes as R3a, 0 console errors, 0 `/data/reference/in/states/**` 404s -- now a regression check, not a load-bearing assertion
- [ ] `git status` confirms 36 shards staged for deletion + no untracked residue under `datasets/reference/in/states/`

### R4 - Distillation

- `git mv TODO/20260602-eci-sot-rip-and-replace-plan.md docs/archive/plans/`
- Append "Plan complete" closure block with per-row PR distillation map per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
- Update `docs/reference/data-coverage-report.md` to remove the `reference/in/states/<S__>/constituencies.json` entry and replace with `taxonomy/ac_crosswalk.parquet` row.
- Emit a `TODO/20260602-eci-sot-rip-handover.md` lesson if any surprises hit during R3.

---

## section 5. Sequencing rationale (revised 2026-06-03, fifth amendment)

R3a-pre -> R3a -> R3b -> R4.

- **R3a-pre before R3a:** R3a's `districts.ts` reader queries the map; without backfill the reader returns `[]` for ~95% of ACs and `StateOverview` grouping degrades to a single empty bucket.
- **R3a before R3b:** Parallel Change discipline. R3a is EXPAND + MIGRATE (canonical reader live on main, legacy artifact still on disk). R3b is CONTRACT (legacy artifact deleted). Reversing the order would create a window where the frontend 404s on every state hub.
- **R3b is the only PR that touches `datasets/reference/in/states/`:** the deletion is atomic with the backend rewires so no commit on main carries an orphaned tool reading deleted shards.
- **R3b commit body MUST include §0c rationale** for the dropped R2: "30 SoT source URLs preserved in git history; not lifted to `taxonomy/sources.parquet` because orphan rows violate the citation-ledger invariant (CLAUDE.md §12)."
- **R4 after R3b on main:** distillation map must cite the final R3a + R3b PR numbers.

---

## section 6. Risk register (R3a)

**Risk:** [frontend/src/lib/view-models/districts.ts](frontend/src/lib/view-models/districts.ts#L31) currently reads `constituencies[].district_id`, which the §0a audit showed populated on only 824/4113 rows (20%) with non-LGD values (`KOK`, `KAS`, `TAL`, `COB`, `puducherry`). The R3a rewrite joins via `taxonomy/lgd_ac_pc_district_map.json` (232 rows, LGD-keyed, authoritative) instead. Two consumer-side cases must be specified:

1. **LGD lookup miss for a given `(lgd_state_id, lgd_ac_id)`** -- e.g. U08 J&K post-reorg ACs where LGD has not yet published the mapping. **Contract:** view-model returns `district: null`. UI renders an empty district badge slot on the AC card -- no crash, no `"Unknown district"` placeholder string. Citizen reads silence as "data not yet available", which is honest.
2. **The 824 SoT rows where some author manually filled `district_id` with a non-LGD code** -- those values are now discarded. If any of those happen to correspond to an LGD-mapped AC, the LGD join recovers the canonical district FK. If not, falls to case 1.

**Test coverage:** `districts.test.ts` (new or updated) MUST include one fixture per case: (a) AC with LGD mapping -> district populated; (b) AC without LGD mapping -> `district: null`, no exception. Snapshot/render test asserts empty badge slot, not placeholder text.

**Doc impact:** add a one-paragraph "District FK provenance" note to [docs/architecture/frontend/data-loading.md](docs/architecture/frontend/data-loading.md) (if it exists; else to the closest frontend data-loading doc) recording that AC district FKs flow from `lgd_ac_pc_district_map.json`, not from the (deleted) SoT shard. This is the durable lift from R3a.

---

## section 7. Open questions

None blocking. Strategy is explicit per user mandate; deliverables are mechanical; consumer list is closed.
