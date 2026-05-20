# Canonical long-format pivot — handover plan

**Last Updated**: 2026-05-20 (§0e.10 amendment LOCKED — Phase-0 closeout four-way concurrence (Hans+Max+Jony+Fowler): office_id shape, partition-by-state for `election_results.parquet`, 3-stage sub-sequencing T.0a/T.0b/T.0c, ledger AMEND-then-FREEZE. Phase 1 deletion sweep ✅ closed (1.8e + 1.8f shipped); Phase 2 Energy unblocked once T.0 series lands.)
**Status**: Phase 0 complete (14/15 ✅ DONE; 0.13 ⊘ DROPPED with documented replacement pattern). Phase 1 — elections-results pivot + dim tables + view-model loaders + deletion sweep 1.8a–1.8f ✅ ALL DONE (on-disk audit 2026-05-20). 1.8e shipped 2026-05-19 (PR-R.1 → PR-R.2 → PR-R.3 retired the 41 `results.sqlite` shards + `frontend/src/lib/sql.ts` + `frontend/src/lib/psephlab/actuals.ts` + `backend/yen_gov/emit/sqlite.py`; Psephlab + Compare now read canonical Parquet via DuckDB-WASM through `lib/psephlab/canonical-loaders.ts`); 1.8f shipped 2026-05-20 (PR-S.1 lifted bio onto `dim_candidates.parquet` v1.2; PR-S.2 retired the 3,983 person JSONs + `people.entity.schema.json` + `fetchPersonEntity` + `slugifyCandidate` + one-shot backfill tool + refactored `people_ingest` to UPSERT onto canonical store). Closeout PR (this branch) adds the missing `backend/tests/test_no_sqlite_emit.py` regression guard the §7 row 1.8e sub-plan promised + reconciles status across the plan doc. **Phase 2 (Energy) is now unblocked** per user direction 2026-05-19 (Option A: finish Phase 1 honestly).
**ADR**: [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) (canonical store) + [ADR-0031](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) (boundaries).
**Supersedes**: ADR-0026 (folded-indicator), ADR-0027 (cadence-as-separate-field), and all per-shard JSON doctrine in `docs/concepts/folded-indicator.md` + `docs/concepts/collection-inventory.md` (now marked obsolete).

**Stance on performance**: functional correctness first. Mobile-performance polish is **not** an implementation-phase blocker; it is tracked but does not gate Phase 0–3. We do, however, need an explicit *failure-state UX contract* (see D17) because functional correctness includes "what the citizen sees when the loader is still loading or has failed."

---

## §0a. THIS IS THE PLAN DOCUMENT (read me first)

**Single source of truth**: `TODO/20260517-canonical-long-format-pivot.md` (this file). All implementation work follows this document. Do not invent parallel plans. If something is missing, add it here, do not start a sibling doc.

**Input artifacts** (referenced FROM this plan; not themselves the plan):

| Path | Role | Status |
| --- | --- | --- |
| `TODO/20260517-canonical-long-format-pivot.md` | **THE plan** (you are here) | authoritative |
| `TODO/20260517-indicator-corpus-survey.md` | Factual baseline: 110-ID enumeration from `datasets/indicators/in/` | input — read once |
| `TODO/20260517-indicator-consolidation-audit.md` | Max+Hans consolidation pass: 110 → ~60 parents → ~80–120 ids | input — read once; §2/§7 contain known hallucinations flagged in audit, treat as directional |
| `TODO/20260517-tcpd-tn-ae-people-sidecar-plan.md` | Older sidecar plan (TCPD-TN elections); does NOT supersede this plan | reference only |
| `TODO/sources.md` | Source backlog tracker | reference |

**On conflict**: this plan wins. Period.

---

## §0b. INDICATOR CARDINALITY IS A MOVING TARGET (read this twice)

The "~60 parents / ~80–120 indicator_ids" figure in the consolidation audit is the **count of what we have ingested so far** — it is NOT the steady-state count of yen-gov indicators. It will grow substantially as new source domains are ingested. The contract must be designed for **growth**, not for the snapshot.

**Not yet ingested** (each may contribute 10–50+ indicators):

- **Judiciary** — pendency by court level, vacancy ratios, conviction rates, prisoners, undertrials, bail rates (NJDG, NCRB-Prison Statistics, Supreme Court data).
- **Healthcare** — disease burden (NCD/communicable), hospital infrastructure per capita, doctor density, immunization full-coverage, NFHS-5 deep cuts, HMIS service utilisation, drug stockouts (HMIS, NHM dashboard, NFHS-5/6 micro).
- **Water resources** — groundwater extraction by block, river basin flows, drinking-water coverage, irrigation reach, reservoir levels (CGWB, CWC, Jal Shakti).
- **Crime & policing** — IPC + SLL by category, police strength per 100k, women's safety, custodial deaths (NCRB, BPRD).
- **Education (deep)** — UDISE+ school-level rolls, AISHE higher-ed, NIRF rankings, PARAKH learning outcomes, pupil-teacher ratio per district, dropout cohorts (UDISE+, AISHE, NIRF, NAS/PARAKH).
- **Environment (deep)** — air quality per monitoring station, forest cover change, biodiversity (CPCB, FSI, ENVIS).
- **Transport (deep)** — Vahan registrations, IR passenger/freight per zone, road accident fatalities by NH (MoRTH, Vahan, IR Annual Stats).
- **Agriculture (deep)** — crop production per district per season, MSP procurement, soil health (DA&FW, FCI, Soil Health Card).
- **Welfare schemes** — MGNREGA person-days per GP, PMAY houses built per district, PDS offtake per state (NREGAsoft, PMAY-G, PDS portal).
- **Local government finance** — ULB / Panchayat own-revenue and grants (FFC/SFC reports, RBI municipal finances).

**Implication for the contract**: the catalogue MUST scale to **500–1,000+ indicator_ids over 2-3 years** without architectural change. The R2 picks (parent + `dimension_values:STRUCT` + selective facet-explode + manifest-driven discovery + Hive partition by `indicator_id`) all support this growth path. Do NOT design as if 80–120 is the destination.

**Implication for Phase 0 catalogue seed**: include placeholder topic stubs (`judiciary`, `healthcare`, `water`, `crime`, `education_deep`, `welfare`, `local_govt_finance`) in `taxonomy/indicators.json` schema enumeration even if zero rows yet. The schema MUST accept future topics without bump.

---

## §0c. BOUNDARIES PRESERVATION — DO NOT DELETE (critical, repeated)

**`datasets/boundaries/` IS NOT LEGACY.** It is a sibling family to the canonical Parquet store (D25). The R10 boundaries pass + R11 confirm:

- Phase 0.13 `_old/` move **EXCLUDES** `datasets/boundaries/`, `datasets/taxonomy/`, `datasets/schemas/`, `datasets/manifest.json` (per R25).
- Phase 1.8 `_old/` deletion **NEVER TOUCHES** `datasets/boundaries/`.
- Existing files preserved as-is: `boundaries/in/country/IN.json`, `boundaries/in/geojson/{india-states, india-districts, india-soi}.geojson`, `boundaries/in/geojson/S01-ac.geojson` through `S2x-ac.geojson` + all `.sources.json` sidecars.
- Future additions (PCs, taluks/sub-districts, village coverage) follow the same `datasets/boundaries/in/{geojson|pmtiles}/` layout. When a layer exceeds ~10 MB GeoJSON, switch that layer to PMTiles (Q11).
- Any agent proposing to move, rename, or delete a file under `datasets/boundaries/` MUST escalate to the user. There is no implementation step in this plan that touches that tree except to ADD new layers.

**If you are an execution agent and you find yourself running `git rm` or `git mv` on anything under `datasets/boundaries/`, STOP. You are doing something this plan forbids.**

---

## §0d. Status vocabulary (mandatory; resolves "what does DONE mean" drift)

**Established 2026-05-19** in response to user pushback that "shipped / not done / deferred are at the same status level" was hiding genuinely incomplete work behind progress-sounding labels. The plan uses exactly THREE row-status values. No others. Pull-request authors and reviewing agents MUST match every row label to one of these:

| Icon | Status | Meaning |
| :-: | --- | --- |
| ✅ | **DONE** | The work landed on `main`. The cited PR / commit SHA / file:line proves it. A reviewing agent can re-verify by reading the citation. No remaining sub-steps. |
| ⏳ | **NOT DONE — IN PROGRESS / SCHEDULED** | Work has an owner, a named immediate next sub-step, and any blocker called out with the unblocking decision named. Currently active or queued. |
| ⊘ | **NOT DONE — DROPPED** | The project decided not to do this. Reason recorded in the same row. The plan-doc exit criteria are amended in the same commit so a ⊘ never silently lowers a phase's bar. |

**Forbidden vocabulary** (do not introduce or re-introduce; treat as a smell in PR review):

| Forbidden word | Use instead | Why it's banned |
| --- | --- | --- |
| "SHIPPED" | ✅ DONE | Synonymous with DONE; vocabulary drift. |
| "DEFERRED" | ⏳ with concrete sub-step + blocker, OR ⊘ with exit-criteria amendment | "DEFERRED" with no schedule reads like progress but is functionally NOT DONE; user 2026-05-19. |
| "SUPERSEDED" | ⊘ on the retired row + link from the replacement row | "SUPERSEDED" pretends a row was completed when it was actually replaced; clarity is better served by ⊘ + a pointer. |
| "PENDING" | ⏳ + concrete sub-step | "PENDING" lacks the next-step / blocker / owner discipline. |
| "PARTIALLY DONE" | split row into ✅ + ⏳ children | A single status per row; if work is mixed, the row is mis-scoped. |

**Verification rules** (another agent will re-check; CLAUDE.md §13 plus this rule):

- A row marked ✅ MUST cite the merge commit SHA or PR number AND name the on-disk evidence a reviewer can read (file path + test name).
- A row marked ⏳ MUST name (a) the owner persona, (b) the immediate next sub-step, (c) the blocker if any with the unblocking decision named.
- A row marked ⊘ MUST cite the exit-criteria amendment in the same plan commit that lowered the bar, AND state where the dropped work's content was replaced (or explicitly say "work itself is descoped — no replacement").
- **No ✅ without verifiable evidence.** Claiming DONE based on a previous summary or memory note ("I think this shipped last week") without re-checking the file/test is the failure mode the user named on 2026-05-19. Always re-verify before stamping ✅.

---

## §0e. Indicator topic taxonomy + directory structure (LOCKED 2026-05-19)

**What this is.** The full topic-taxonomy + directory-structure design that governs Phase 2 and every family that lands after it. All 7 questions raised in the 3-agent debate are resolved here. **No sibling plan doc lives outside this file** (per §0a: "single source of truth").

**Debate transcript** (3-agent synthesis, OWID screenshot taxonomy captured verbatim, all rejected designs archived): [TODO/20260519-indicator-topic-taxonomy-and-dir-structure-plan.md](20260519-indicator-topic-taxonomy-and-dir-structure-plan.md). That doc is **history**, not contract; do not edit its body. The contract is here (§0e) + [docs/architecture/data/canonical-store.md §2b](../docs/architecture/data/canonical-store.md).

**Authority for everything below**: Max (Indicator Scout — OWID precedent) is the lead voice per CLAUDE.md §0a for data-shape / indicator-identity / topic-taxonomy / directory questions, with Hans (Governance) framing the Indian-citizen surface and Fowler (Engineering) holding refactor safety. User direction 2026-05-19: *"Almost always when there is a structural setup of indicators or OWID data or structure, Max's authority [dominates]."*

### §0e.1 — User overrides (locked, do not re-debate)

| # | Default in PR #56 (3-agent debate) | User override 2026-05-19 | Live decision |
| - | --- | --- | --- |
| 1 | Persons fork — Fowler picked Option A first (smallest-reversible-step), Max picked Option B | **Option B in one shot** — rename `dim_candidates` → `dim_persons`, add `elections/elections_candidacies.parquet` fact, add `governments/governments_office_holdings.parquet` fact | **B, in one shot.** Day-one `person_id` strategy = Max §0e.5 (hybrid B-ii + TCPD seed). |
| 2 | Hans recommended `public_servant` per IPC §21 + Lokpal Act §14 | **`office_bearer`** — more nuanced as a citizen term; IPC reference stays as a footnote | Entity slug = **`office_bearer`**. IPC §21 / Lokpal Act §14 cited in `taxonomy/entities.json` row description, not the slug. |
| 3 | Hans proposed topic slug `accountability` | **`governance`** — broader umbrella; covers accountability + responsibility + service-quality measurement of the government | Topic slug = **`governance`**. "Audits & accountability" becomes one sub-area within `governance`, alongside service-quality (PHC vacancy %, teacher absenteeism, NJDG pendency, FIR-to-chargesheet ratio). |

### §0e.2 — The 7 questions resolved

| Q | Question | Resolution | Authority |
| - | --- | --- | --- |
| 1 | Persons fork — A first or B in one shot? | **B in one shot** | user override (§0e.1 #1) |
| 2 | `human_development` split granularity | **Three-way split now**: `health/`, `education/`, `amenities/` as top-level families; `human_development/` keeps composites only (HDI, MPI, HCI). `nutrition` + `gender` are `topic_tags[]`, NOT top-level families (they cross-cut multiple families). | Max (user delegated explicitly) |
| 3 | `schemes` granularity | **Per-scheme fact tables** (`schemes_mgnrega_person_days.parquet`, `schemes_pmay_g_sanctions.parquet`, etc.) — keeps independent enrichment per scheme. | user direction |
| 4 | `work` as own top-level family | **Yes** — Max + Hans both want it; PLFS / NSS-EUS / wages cadence + methodology break vs old NSS warrants its own family. | Max + Hans convergent |
| 5 | `accountability` vs `governance` naming | **`governance`** — broader umbrella; `accountability` is one sub-area within it. | user override (§0e.1 #3) |
| 6 | PR-S.1 timing — parallel with T.1 + T.2, or after? | **Parallel** (no contention — S.1 only touches `elections/` + deletes `people/`; T.1/T.2 touch `taxonomy/` + `_ops/` + `reference/`). | user direction |
| 7 | Phase 2 sub-PR ordering | **Accept Max's ordering**: NFHS-5 → PLFS → UDISE+ → AISHE → NCRB → HCES 2022-23 → IMD → e-GramSwaraj/PFMS → TRAI → CAG. | Max (user delegated explicitly) |

### §0e.3 — The naming convention (ONE rule for the whole tree)

Extends [`canonical-store.md` §2a](../docs/architecture/data/canonical-store.md) verbatim:

> **Inside `datasets/<family>/`**: facts are `<family>_<role>.parquet`, dims are `dim_<entity>.parquet`.
> **Inside `datasets/taxonomy/`**: registries are flat `<role>.parquet` (directory IS the role).
> **Hand-authored taxonomy** is `<role>.json` text source-of-truth alongside compiled `<role>.parquet` (per D18 + §8.3 Python seed).
> **Geometry** is sibling family `datasets/boundaries/<region>/<format>/<layer>.<ext>` (D25, ADR-0031, never Parquet).
> **Control-plane** operator state lives at `datasets/_ops/<role>.parquet`.
> **Contracts** live at `datasets/schemas/<name>.schema.json`.
> **There are no other top-level concept dirs.**

**Citizen URL slugs**: hyphen-separated, no topic prefix, OWID convention (`outstanding-debt-pct-gsdp`, `gdp-per-capita-mospi`). Topic in URL is a single-parent lie when topics are M:N — drop it.

**Topic display layer**: stable machine slug (`fiscal`, `governance`, `schemes`) + citizen-readable title (`"Money & debt"`, `"Measuring the government"`, `"Where the money goes"`). Two columns on `taxonomy/topics.parquet`; renames touch the title column only.

### §0e.4 — New top-level topic slugs (locked)

Added net of today's 7 (`fiscal`, `energy`, `elections`, `economy`, `demography`, `human_development`, `environment`):

| Slug | Citizen title | Hosts | Notes |
| --- | --- | --- | --- |
| `governance` | Measuring the government | CAG state audit findings + CAG performance audits; PRS bill tracker; RTI compliance (CIC); Lokpal/CVC; PHC vacancy %; teacher absenteeism; NJDG pendency; FIR-to-chargesheet ratio | Override #3 above — replaces `accountability` |
| `schemes` | Where the money goes | MGNREGA; PMAY-G/U; PM-KISAN; ICDS; PM-POSHAN; NFSA; CSS + CS scheme delivery | Per-scheme fact tables (Q3) |
| `local_govt_finance` | Panchayats & local bodies | e-GramSwaraj; 15th FC grant flows; SFC transfers; ULB own revenue; ZP/BP receipts-payments; CAG Local Bodies Audit | User hot-button |
| `work` | Work & jobs | PLFS quarterly + annual; NSS-EUS (methodology break vs PLFS); wages; female LFPR; self-employment; migration for work | Q4: own family (not folded into human_development) |
| `judiciary` | Courts | NJDG pendency + disposal; eCourts metrics | Max §5.3 Law gap |
| `crime` | Crime | NCRB IPC; NCRB SLL; Prison Statistics India; FIR-to-chargesheet ratio | Max §5.3 Law gap |
| `health` | Health | NFHS-5; HMIS monthly; SRS annual; CRS births/deaths; public health expenditure | Q2: split out of human_development |
| `education` | Education | UDISE+ school metrics; AISHE higher-ed; ASER learning outcomes; literacy | Q2: split out of human_development |
| `amenities` | Household amenities | NFHS HH module (water, sanitation, electricity, cooking fuel); JJM; SBM; PMAY-U/G housing | Q2: split out of human_development |
| `technology` | Telecom & internet | TRAI quarterly performance; broadband penetration; mobile subscribers; NFHS ICT module | Max §5.3 |

`human_development/` shrinks to **composite indices only** (HDI, MPI, HCI) once health/education/amenities split out. `nutrition` and `gender` are `topic_tags[]` strings on the indicator catalogue, NOT top-level families — they cross-cut multiple homes (nutrition spans `health` + `schemes`; gender spans `health` + `education` + `work` + `crime` + `governance`).

### §0e.5 — Persons fork resolution (Option B, day-one rule)

User override: **rename `dim_candidates` → `dim_persons`, in one shot**, plus add two sibling facts:

- `elections/elections_candidacies.parquet` — fact: one row per `(person_id, election_id, ac_id, party_id, vote_share, won)`.
- `governments/governments_office_holdings.parquet` — fact: one row per `(person_id, office_id, tenure_start, tenure_end, party_id_at_tenure)`. Office identity is taxonomy (`taxonomy/entities.parquet` with `entity_type='office'`); occupancy is the fact.

**Day-one `person_id` strategy** (Max, hybrid B-ii + TCPD seed):

1. **Default**: one person per candidacy row. `person_id = sha256(state_code || ac_id || election_id || normalised_candidate_name)[:16]`. Honest about uncertainty — `M. Kumar (TN, 1962)` and `M. Kumar (TN, 1989)` start as two persons until evidence merges them.
2. **Merge overlay**: `taxonomy/person_aliases.json` (hand source per D18 + §8.3) → compiles to `taxonomy/persons.parquet` + a `(candidacy_key → person_id)` lookup. Each cluster carries `cluster_id`, `candidacy_keys[]`, `display_name`, `source_id` (FK to `sources.parquet`), `evidence_note_md`, `confidence_tier` ∈ {gold, silver, bronze}.
3. **Seed layer**: bulk-import **TCPD `Candidate_ID`** (Trivedi Centre for Political Data, Ashoka — 5+ years of curated merge work for Indian candidates) for the TN-AE corpus as the first batch of `person_aliases.json` rows. `source_id` = TCPD dataset row in `sources.parquet`; `confidence_tier: silver` (republisher, not issuing authority); `is_issuing_authority: false`.
4. **Merged `person_id`** for clustered rows: `sha256(sorted_candidacy_keys || sorted_source_ids)[:16]`. Content-addressable on cluster contents — splits are recoverable.
5. **False-merge recovery**: edit `person_aliases.json` (remove bad cluster entry) → recompile → split person gets fresh `person_id`; remaining cluster keeps identity. Logged in `migration-ledger.csv` as `person_id_split: old → new1, new2`. Frontend `/person/<old>` renders one-release `301 → see [new1] / [new2]` then 404. Same shape as the indicator-id-alias mechanism in T.3.
6. **`gold` tier waits for ECI Form 26 affidavits**. When affidavit ingest unblocks (currently blocked per `TODO/20260517-iced-bulk-ingest-and-parity-oracle.md`), affidavit DOB + father's name + permanent address promote merges from silver/bronze to gold *without re-issuing `person_id`* (cluster gains a new `source_id` row; cluster hash stable).

**Open follow-up — TCPD license**: TCPD is CC-BY-NC-SA 4.0. yen-gov is non-commercial public-good but the SA clause means downstream Parquet derivatives inherit CC-BY-NC-SA. **Hans must confirm** before S.1 ships and record license in `sources.parquet`.

### §0e.6 — Office-bearer entity term (override #2)

Slug = **`office_bearer`** (user override; user preferred it to `public_servant`). The IPC §21 / Lokpal & Lokayuktas Act 2013 §14 statutory citation moves into the row description of `taxonomy/entities.json` for the `entity_type='office_bearer'` rows, not into the slug itself.

Attributes (from Hans's original framing, retained):

- `role` (CM, MLA, Collector, Sarpanch, …)
- `tenure_start`, `tenure_end`
- `office_type` ∈ {`elected`, `appointed_political`, `civil_service`, `statutory_authority`}
- `place` (LGD-coded)

Tenure overlap allowed (one person concurrently Collector + DM + DRDA CEO = three `office_holdings` rows, one `person_id`). Office identity is taxonomy; office occupancy is a fact (`governments/governments_office_holdings.parquet` per §0e.5).

### §0e.7 — Migration sequence (the 6-PR strangler-fig)

Each PR independently mergeable, each reversible. **Two-hat discipline**: purely structural (paths/renames/no row content change) OR purely behavioural (schema rows change). Fused atomic per /memories/lessons.md 2026-05-17 ENTRY when `$schema_version == x-version` strict check applies.

| # | PR | Hat | Tier-A pair | Depends on |
| - | --- | --- | --- | --- |
| **T.1** | **Tidy first — dir hygiene.** Delete `_test/`. Create `_ops/`. Move operator state → `_ops/`. Audit `features/` (delete or document). Update `manifest.json` `path` fields. | structural | no | — |
| **T.2** | **Lift topic catalogue into taxonomy.** Move `reference/in/topic-catalogue.json` → `taxonomy/topics.json`. Add `backend/yen_gov/canonical/topics_seed.py` per §8.3. Compile `taxonomy/topics.parquet`. Update consumers in `frontend/src/lib/`. **Add new top-level topics** per §0e.4 (`governance`, `schemes`, `local_govt_finance`, `work`, `judiciary`, `crime`, `health`, `education`, `amenities`, `technology`). Retire `reference/in/`. | structural | yes (seed module) | T.1 |
| **T.3** | **Indicator catalogue widens for topic tags + drops topic prefix.** Bump `indicator.schema.json` minor: add `topic_tags: string[]` (FK → `taxonomy/topics.parquet`), add `id_aliases: string[]` (one-release back-compat), enforce new id shape per §0e.3. Migrate 110 legacy ids; populate `id_aliases` with old `<topic>/<id>` form; frontend dereferences via alias. Add `taxonomy/indicator_topic_tags.parquet` M:N join (source of truth) + `topic_tags[]` denormalised projection on `taxonomy/indicators.parquet` (compiled). **Fused atomic commit.** | structural + behavioural (fused) | yes (TS `IndicatorMeta` widen + Zod `stacked-trend/types.ts` widen — /memories/lessons.md 2026-05-16 #1) | T.2 |
| **S.1** | **Persons Option B — one shot.** Rename `dim_candidates` → `dim_persons` (schema bump major on `dim-candidates.schema.json` → `dim-persons.schema.json`; `id_aliases` keeps old shape for one release). Add `elections/elections_candidacies.parquet` fact. Add `taxonomy/person_aliases.json` + compiled `taxonomy/persons.parquet`. Seed TCPD `Candidate_ID` clusters for TN-AE. Delete `datasets/people/AcGenApr2021/`. Fused atomic commit. Runs in parallel with T.1+T.2 (no contention — touches `elections/` + `taxonomy/persons*` only). | structural + behavioural (fused) | yes (`DimCandidate` → `DimPerson` TS rename + new `Candidacy` type) | independent (parallel with T.1+T.2) |
| **G.1** | **Office-bearers consolidation.** Create `governments/governments_office_holdings.parquet` fact (one row per `(person_id, office_id, tenure_start, tenure_end)`). Create `governments/dim_offices.parquet`. Add `entity_type='office_bearer'` rows to `taxonomy/entities.json` per §0e.6. Migrate `governments/in/states/<state>/cm_terms.json` → fact rows. Delete `governments/in/states/`. | structural + behavioural (fused) | yes if frontend consumes (today: `cm_terms` only — check usages) | T.3 + S.1 |
| **P.\*** | **Per-family pivot** — Phase 2 of this plan. Each family from §0e.4 becomes its own sub-PR following §2a naming rule + FK contract + empty-parent pruning. Order per Q7: NFHS-5 → PLFS → UDISE+ → AISHE → NCRB → HCES 2022-23 → IMD → e-GramSwaraj/PFMS → TRAI → CAG. Drops `datasets/indicators/in/<family>/` per sub-PR. | structural + behavioural (fused per family) | yes per family | T.3 |

**T.1 + T.2 + S.1** are pure Tidy First / structural — worth landing first, zero behavioural risk on the live citizen surface. **T.3** is the largest single behavioural change in this arc; it earns its own Correction Level 4 review.

### §0e.8 — What retires

| Old path | Replacement | Retiring PR |
| --- | --- | --- |
| `datasets/_test/` | (deleted, no replacement) | T.1 |
| `datasets/reference/in/` | `datasets/taxonomy/` (editorial) or `datasets/_ops/` (telemetry) | T.2 |
| `datasets/indicators/in/<topic>/` | per-family Parquet at `datasets/<family>/<family>_<role>.parquet` | P.\* (per family) |
| `datasets/people/AcGenApr2021/` | `datasets/elections/dim_persons.parquet` + `taxonomy/persons.parquet` | S.1 |
| `datasets/governments/in/states/` | `datasets/governments/governments_office_holdings.parquet` + `datasets/taxonomy/entities.parquet` (`entity_type='office_bearer'`) | G.1 |
| `datasets/features/` | (audit pending — delete or relocate by T.1) | T.1 |

### §0e.9 — Cross-refs

- **Full target disk layout** (contract surface): [`docs/architecture/data/canonical-store.md` §2b](../docs/architecture/data/canonical-store.md).
- **Debate transcript** (3-agent synthesis, OWID screenshot taxonomy verbatim, all rejected designs archived): [TODO/20260519-indicator-topic-taxonomy-and-dir-structure-plan.md](20260519-indicator-topic-taxonomy-and-dir-structure-plan.md).
- **Naming-rule origin**: [`canonical-store.md` §2a](../docs/architecture/data/canonical-store.md) — §0e.3 extends it.
- **Phase 2 sequencing**: §0e.7 P.\* row drives §7 row 1.8 sub-rows for each new family.

### §0e.10 — Phase-0 closeout amendment (LOCKED 2026-05-20; four-way concurrence)

**What this is.** A coordinated four-way debate (Hans Governance + Max Indicator-Scout + Jony UI/UX + Fowler Engineering) ran 2026-05-20 to settle Phase-0 cleanup of the four legacy/orphan trees (`datasets/people/`, `datasets/elections/<event>/<state>/results.csv`, `datasets/governments/in/states/<S>/cm_terms.json`, `datasets/reference/in/`) plus the `migration-ledger.csv` lifecycle, **plus** an emergent sizing question raised by the user: `election_results.parquet` is already 14.2 MB at TN-only scale and needs a split strategy before Phase 2 multiplies it.

Concurrence reached on every point. This §0e.10 **amends** the §0e.7 strangler-fig (it does not replace it) with three locks plus a 3-stage sub-sequencing of the T.1+T.2+G.1+S.1-data-tail cleanup. The §0e.7 PR identities (T.1/T.2/T.3/S.1/G.1/P.\*) remain the contract for the rest of this arc.

**User direction that anchors this amendment** (verbatim): *"Commit becomes the backup location for us"* — once new canonical artifacts land in a commit, the matching legacy files get `git rm`-ed in the next PR. Git history is the backup; no `_old/` placeholder, no "keep just in case" hedging.

#### §0e.10.1 — Four-way concurrence (one-line each)

| Voice | Verdict |
| --- | --- |
| Hans (Governance) | Concur DELETE × 2 (people/, results.csv), TRANSFORM cm_terms via G.1, per-file dispositions on `reference/in/`, AMEND-then-FREEZE the ledger. |
| Max (Indicator Scout) | CONCUR on every Hans verdict, with six amendments (locked below). |
| Jony + Fowler (joint) | CONCUR on data shape; ADD partition-by-state for `election_results.parquet` (sizing); REFINE sequencing into 3 sub-stages; zero citizen-pixel change. |

#### §0e.10.2 — Locked amendments (binding on T.0/T.1/T.2/G.1 work)

**A. Office-id shape for `dim_offices.parquet` and `entities.parquet` (`entity_type='office_bearer'`)** — hyphen-only, country-prefixed, role-suffixed:

```
IN-PM             # Prime Minister
IN-PRES           # President
IN-VPRES          # Vice President
IN-S22-CM         # Tamil Nadu Chief Minister
IN-S22-GOV        # Tamil Nadu Governor
IN-S22-DCM        # Tamil Nadu Deputy CM (if applicable)
IN-MUM-MAYOR      # Mumbai Mayor (uses LGD-style city code, not state)
IN-PAN-<lgd>-SARP # Panchayat sarpanch (post-local-govt landing)
```

Reasoning: matches the existing `IN-S22-AC-2008-167` shape from [`canonical-store.md` §3a](../docs/architecture/data/canonical-store.md). Period (`.`) separator + composite-key options rejected (drift from the locked entity-id grammar). Approved role-abbreviation list (extends D30): `CM`, `DCM`, `GOV`, `PM`, `PRES`, `VPRES`, `MAYOR`, `SARP`. Adding a new role requires Max sign-off.

`regime='presidents_rule'` rows on `governments_office_holdings.parquet` carry `person_id IS NULL` — that is the *correct* honest model (Hans + Max concurrence), not a hole to backfill.

**B. Partition `elections/election_results.parquet` by state (Hive-style, write-time)** — supersedes the §0a.9 "defer until threshold" stance for the elections family specifically:

- On-disk layout: `datasets/elections/state=in_s22/election_results.parquet` (one file per state-equivalent unit, including UTs).
- Hive segment grammar: `state=in_<two-char-lower>` — country-prefixed (mirrors `IN-S22-...` entity-id identity), lowercase (Hive value safety), underscore (Hive value safety; hyphen forbidden in path segments by some downstream tools). The country prefix lives in the partition value so future multi-country expansion works without a schema change.
- Writer change: new `FAMILY_FACT_PARTITION_BY: dict[str, list[str]]` analog to existing `FAMILY_FACT_TABLE_STEM`. `elections` entry = `["state"]`. Other families default to empty (no partitioning).
- Manifest impact: `tables[].files[]` (which already exists, plural) emits N entries per partitioned family. `kind` stays `"observations"`; new `partition_columns: ["state"]` on the table entry.
- Reader impact: **zero** — [`frontend/src/lib/duckdb.ts`](../frontend/src/lib/duckdb.ts) `registerTable` already iterates `files[]` and passes a list to `read_parquet([...])` (Jony+Fowler verified pre-amendment).
- Citizen cost (Jony): cold-cache state-page load on 4G drops from O(full national parquet) to O(one state ≈ 20 MB at full national scale). State-equivalent pages are 95%+ of citizen routes.
- Engineering cost (Fowler): one COPY clause change + a derived `state_part = lower(replace(<state_code>, '-', '_'))` projection. On-disk Hive segment is NOT in any citizen URL (1.8a-bis decoupled view name from filename via `table_name`), so the split is reversible.
- **Dims stay flat** (`dim_acs.parquet`, `dim_candidates.parquet`, `dim_parties.parquet`, `dim_party_alliances.parquet`). At full national scale `dim_candidates` ≈ 15 MB — small enough that partitioning costs more in cross-state JOIN globbing than zonemap pruning saves.
- **Parity oracle pattern** (per PR-R.2 lesson): T.0 ships a `test_partitioned_parity_oracle` that asserts for each (state, event) slice the partitioned read returns identical row counts + identical FPTP winners as the monolithic baseline kept on-disk during T.0 review. Skips cleanly once T.2 deletes the baseline.

**C. LGD CSV snapshots — dated canonical + writer-maintained latest pointer:**

- Canonical: `datasets/taxonomy/lgd/states-YYYY-MM-DD.csv` (immutable, snapshot per LGD publication; `source_id` row in `taxonomy/sources.parquet` per §12).
- Convenience: `datasets/taxonomy/lgd/states-latest.csv` (writer-maintained pointer; never `git log`-relevant on its own).
- Same shape for `districts-YYYY-MM-DD.csv` + `districts-latest.csv`.
- Reasoning: rolling-overwrite is the same disease as the `fetched_at` smear — destroys the `git log` audit trail for "when did this district appear in LGD?". OWID snapshot pattern adopted verbatim.

**D. `taxonomy/topics.parquet` is FLAT — `parent_topic_id` REJECTED:**

- OWID is flat-with-multi-tag for a non-arbitrary reason: hierarchical taxonomies become contested politics ("Is GST devolution under *Money* or *Centre–state relations*?").
- Hierarchy of citizen interest belongs to **indicator parents** (D26 `parent_indicator_id`), not topic parents.
- M:N via `taxonomy/indicator_topic_tags.parquet` (already in §0e.7 T.3 row).

**E. `taxonomy/election_events.parquet` is PURE REFERENCE (one carve-out):**

- Columns: `event_id` (PK), `body` (AC/PC/Loksabha), `poll_dates[]`, `states[]`, `term_end_estimated`, `total_seats`, `notes_md`, `source_id`.
- `total_seats` is legitimate (structural fact of the event itself, ECI publishes it on the event page).
- `winning_party_id` / `winning_alliance` REJECTED on the registry (aggregates → must JOIN against `election_results.parquet`; pre-rolling re-introduces stale-cache class of bugs).

**F. `unmapped_regions.json` → `frontend/src/lib/unmapped-regions.ts` (inline TS literal):**

- It is render-time legend chrome (2 entries: U04, U01), not data-shape reference.
- Drops one HTTP round-trip on every choropleth mount.
- Eliminates a tiny file from `datasets/`. Zero citizen-pixel change.

#### §0e.10.3 — Sub-sequencing of the T.1/T.2/G.1/S.1-data-tail cleanup (3 PRs)

Named **T.0a / T.0b / T.0c** (read: "the T.0 closeout series" — they collectively close the slack between §0e.7 PR identities and the on-disk reality). After this series, the §0e.7 P.\* per-family Phase-2 work has a clean canonical store to land into.

| # | PR | Hat | Touches | Frontend? | Tests | Reversibility |
| --- | --- | --- | --- | --- | --- | --- |
| **T.0a** | **Additive — new canonical artifacts.** Writer change (partition by state per §0e.10.2-B). New `taxonomy/{state_tiers,topics,election_events}.{json,parquet}` (via §8.3 Python-compiles-to-Parquet seeds). New `governments/{governments_office_holdings,dim_offices}.parquet` (via new `cm_terms_seed.py`). Move LGD CSVs to `taxonomy/lgd/<role>-<date>.csv` + `<role>-latest.csv`. Manifest regen. ALL legacy files **untouched**. | structural + behavioural (fused per /memories lesson) | backend writer + new seed tools + taxonomy + governments + manifest. ~30–50 files. | NO change — legacy `/data/reference/...` URLs still serve the legacy bytes. Site continues to render identically. | Writer-partition tests against `tmp_path` (Holy Law #7, real DuckDB COPY, no mocks). Compile-tool round-trip tests per tool. Parity-oracle straddling partition switch. | Fully reversible — pure git revert of additive changes. |
| **T.0b** | **Frontend port + §13 browser smoke.** Switch every consumer of `/data/reference/in/*` to the new canonical path (or DuckDB-WASM for the Parquet ones). Inline `unmapped_regions.json` into `frontend/src/lib/unmapped-regions.ts`. | structural (no schema change; pure import swap) | `frontend/src/lib/` only. ~10–15 files. | YES — every reader switched. Mandatory §13 browser smoke: `/`, `/in/s22`, `/in/s22/elections/ac/167`, `/data-completeness`, one compare route. | Vitest + Playwright tier. Snapshot the network panel before/after — no new 404s. | Reversible via revert; both paths exist in `datasets/` until T.0c. |
| **T.0c** | **Deletion sweep.** `git rm -r datasets/people/AcGenApr2021/` (3,983 files). `git rm datasets/elections/*/*/results.csv` (41 files). `git rm` per-file in `datasets/reference/in/` per the disposition table below. Ledger frozen (per §0e.10.5 below). Final manifest cleanup. | structural (pure subtractive) | dataset tree only. ~4,000+ file deletions. | None — `T.0b` already ported readers. | Tier-B forbidden-path checks in `python -m yen_gov validate --root .` (per §10: NOT in pytest). One Playwright assertion that the legacy URLs return 404 from dev server. | Reversible via `git revert` — commit history holds the bytes. **This is the user's "commit IS the backup" rule in action.** |

Why three not one (Jony+Fowler verdict): A single fat PR loses bisectability for ~4,000 file deletions where each deletion has a different blast radius; T.0b's `§13` browser smoke MUST run with both old and new paths present in `datasets/` so the network panel can prove the swap before the bytes vanish. Single-PR variants rejected during debate.

#### §0e.10.4 — `reference/in/` per-file disposition (binds T.0a + T.0b + T.0c)

| Legacy path | Disposition | Destination | Retiring PR |
| --- | --- | --- | --- |
| `reference/in/states.json` | DELETE | subsumed by `entity_type='state'` rows in `taxonomy/entities.parquet` | T.0c |
| `reference/in/state-tiers.json` | KEEP-AND-MOVE | `taxonomy/state_tiers.{json,parquet}` | T.0a writes, T.0c deletes |
| `reference/in/topic-catalogue.json` | TRANSFORM | `taxonomy/topics.{json,parquet}` (flat, M:N tags) | T.0a writes, T.0c deletes (T.3 in §0e.7 absorbs the indicator-side tagging) |
| `reference/in/election-events.json` | TRANSFORM | `taxonomy/election_events.{json,parquet}` (pure reference + `total_seats`) | T.0a writes, T.0c deletes |
| `reference/in/lgd/states-latest.csv` | KEEP-AND-MOVE | `taxonomy/lgd/states-YYYY-MM-DD.csv` (dated) + `taxonomy/lgd/states-latest.csv` (pointer) | T.0a writes, T.0c deletes legacy path |
| `reference/in/lgd/districts-latest.csv` | KEEP-AND-MOVE | `taxonomy/lgd/districts-YYYY-MM-DD.csv` + `taxonomy/lgd/districts-latest.csv` | T.0a writes, T.0c deletes legacy path |
| `reference/in/states/<S>/districts.json` | DELETE | lift to `entity_type='district'` in `taxonomy/entities.parquet` (`lgd_code` is PK; legacy slug → `legacy_id` column) | T.0a writes entities, T.0c deletes |
| `reference/in/states/<S>/constituencies.json` | DELETE | superseded by `elections/dim_acs.parquet` — **T.0a parity check required** (district_id FK + reservation match) before T.0c green-lights deletion | T.0c (after T.0a parity test) |
| `reference/in/iced-chart-titles.json` | DELETE (conditional) | if ICED ingest still alive: fold into `display_title` on `taxonomy/indicators.parquet`. Else: drop. Decide in T.0a. | T.0c |
| `reference/in/upstream-sources.json` | DELETE | subsumed by adapter-generated `taxonomy/sources.parquet` per §12 | T.0c |
| `reference/in/unmapped_regions.json` | MIGRATE TO FRONTEND | `frontend/src/lib/unmapped-regions.ts` (inline TS literal) | T.0b writes inline, T.0c deletes legacy path |
| `reference/in/indicators-completeness.json` | KEEP (interim) | already the citizen `/data-completeness` surface; revisit when T.3 ships the indicator-catalogue rewrite | (not retired in T.0 series) |
| `reference/in/indicators-operator-state.json` | KEEP (interim) | hand-authored operator overlay; revisit at T.3 | (not retired in T.0 series) |

End state once T.0c lands: `datasets/reference/in/` retires entirely **except** for the two `indicators-*.json` survivors above (which exit in T.3 per §0e.7). At that point `datasets/reference/` itself is empty and can be `git rm -rf`-ed in the same PR.

#### §0e.10.5 — `migration-ledger.csv` lifecycle: AMEND-then-FREEZE

- T.0a commit: **AMEND** the ledger with closeout rows for each of the four trees in scope:
  - `datasets/people/AcGenApr2021/` → `drop` (PR-S.2 lifted bios to `dim_candidates`; data tail deletes in T.0c).
  - `datasets/elections/<event>/<state>/results.csv` → `drop` (CSV is OUTPUT projection of canonical Parquet, not INPUT; Holy Law #10 covers CSV; researchers regenerate via `COPY (...) TO STDOUT (FORMAT csv)`).
  - `datasets/governments/in/states/<S>/cm_terms.json` → `migrate` into `governments_office_holdings` (G.1).
  - `datasets/reference/in/` → per-file table in §0e.10.4.
- T.0c commit: **FREEZE** the ledger. Add a sentinel comment block at EOF: `# FROZEN 2026-05-20 — Phase-0 closeout complete. No further rows. Phase 2+ uses §0d row-status discipline + per-family deletion manifest.`
- Reasoning (Max + Hans convergent): the ledger's job was Phase-0.5 ("prove canonical absorbed everything before legacy deletion"); that role is done after T.0c. A perpetual cross-phase ledger adds a third drift surface (§0d row-status + deletion-manifest already exist) for zero reader. Reopen only if a future phase has >20 legacy files to absorb — revisit at Phase 2 (Energy) scope-lock.

#### §0e.10.6 — Indicator gaps Max flagged for Phase 2+ (NOT this work)

Three indicators already paid-for by the T.0 work; surface as first-class once G.1 ships. Owner: Hans (framing) + Max (catalogue entry).

1. **`state_incumbent_returned_pct`** + **`state_alliance_continuity_index`** — `governments_office_holdings` + `dim_party_alliances` + `election_results` together unlock incumbency-return analytics. OWID has nothing on coalitional politics; distinctly Indian; high citizen-question density ("how often does the incumbent in [state] actually return?").
2. **`state_years_under_presidents_rule_pct`** — the `regime` enum on `governments_office_holdings` already publishes this; nobody reads it as an indicator. Cleanest federalism / state-capacity proxy in the corpus.
3. **`state_mid_term_dissolution_count`** — when `governments_office_holdings.tenure_end < election_events.term_end_estimated - 365`, the government fell early. Surfaces government stability as a first-class number instead of a footnote.

All three are pure derivations on data G.1 + T.0a together land. Hand to Hans for framing after G.1 ships; NOT a blocker for T.0/T.1/T.2 sequence.

#### §0e.10.7 — Cross-refs

- §0e.7 strangler-fig (T.1/T.2/T.3/S.1/G.1/P.\*) — still the contract. §0e.10 is the closeout-sub-sequencing amendment for the subset (T.1+T.2+G.1+S.1-data-tail) that hasn't shipped yet, **plus** the new partition-by-state lock for `election_results.parquet`.
- [`docs/architecture/canonical-pivot-deletion-manifest.md`](../docs/architecture/canonical-pivot-deletion-manifest.md) §6a — adds three new rows for T.0a / T.0b / T.0c at commit time of this amendment.
- [`datasets/migration-ledger.csv`](../datasets/migration-ledger.csv) — amended in T.0a per §0e.10.5; frozen in T.0c.
- TCPD license confirmation (Hans flag, S.1 carry-over) — still pending Hans sign-off before any `governments_office_holdings.person_id` FK reaches a TCPD-seeded cluster row. Track in `docs/research/`.

---

## §1. The One Rule (read first; any coding agent)

> **OWID is the canonical reference for socio-economic data modelling.** Adopt verbatim. Deviate only with Hans + Max sign-off documented in [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md).

### Authority assignment (resolves agent stalls)

| Decision class | Authority |
| --- | --- |
| Data shape — columns, enums, period axis, entity IDs, indicator metadata, sources schema, taxonomy | **Hans + Max** |
| Contract / integration — schema versioning, write seams, layer boundaries, pipes-and-filters | **Gregor** |
| Engineering craft — refactor safety, test tiers, module structure, deletion | **Fowler** |
| UX — URL grammar, visual bounds, copy, citizen framing | **Jony + Citizen** |

**User approval supersedes every agent and every rule.** Already granted for OWID adoption.

### SQL vs SQLite (Hans + Fowler, 2026-05-18)

**We kept SQL. We dropped SQLite.** The canonical store is queried in SQL — DuckDB-WASM in the browser, DuckDB CLI locally, DuckDB Python in the pipeline. DuckDB IS a SQL engine. What the canonical pivot retired is **SQLite as a shipped artifact** (`datasets/elections/<event>/<state>/results.sqlite` — 41 files, all gone as of 2026-05-19) plus the `backend/yen_gov/emit/sqlite.py` emitter that produced them. That deletion shipped as row 1.8e ✅ DONE via **PR-R.1 → PR-R.2 → PR-R.3** (user direction 2026-05-19, Option A: MIGRATE Psephlab + Compare onto DuckDB-WASM-backed canonical loaders first, then retire `lib/sql.ts` + `emit/sqlite.py` + the 41 `.sqlite` files together — see §7 row 1.8e for the as-shipped audit). The what-if simulator stayed alive across the swap; only the parallel sql.js + sqlite shipping artifact went away. Citizens / researchers can point any DuckDB client at `https://miztiik.github.io/yen-gov/data/elections/election_results.parquet` and run the same SQL the site runs — strictly better than the per-state shards.

### Canonical row (memorise)

```
observations: (
  observation_id,    -- sha256(entity_id || year || period_label || indicator_id)
  entity_id,         -- FK -> taxonomy/entities.parquet
  year:int,          -- end-year convention (FY 2024-25 -> 2025)
  period_label:text, -- verbatim publisher string ("FY 2024-25", "Q3 2024-25")
  period_seq:int,    -- monotonic intra-year sort key (1..N per year per indicator)
  indicator_id,      -- FK -> taxonomy/indicators.parquet
  value_numeric:DOUBLE,  -- nullable; numeric reading
  value_text:VARCHAR,    -- nullable; for "Nil"/"N.A."/categorical
  source_id          -- FK -> taxonomy/sources.parquet (provenance, NOT identity)
)
```

**Identity vs provenance (critical, amended in R10):**

- **Logical key** (what makes a row unique): `(entity_id, year, period_label, indicator_id)` — never `source_id`. A corrected upstream value from the same publisher keeps the same logical row; the UPSERT updates value/source pointers, it does not duplicate.
- **`observation_id`** is a stable hash of the logical key for UPSERT efficiency. Does NOT include `source_id`.
- **`source_id`** is provenance FK only. Carrying it on the row lets us answer "which source row backs this fact" without breaking identity when content_hash rolls forward.
- **`period_seq`** is the intra-year sort key: for `cadence='monthly_cy'`, period_seq=1..12; for `quarterly_fy`, 1..4; for `annual_*` and `decennial`, period_seq=1. The renderer sorts by `(year, period_seq)`; the citizen sees `period_label`.
- **`value_numeric` / `value_text`** split: administrative data emits "Nil", "N.A.", "Not reported" as meaningful tokens distinct from zero or null. Both columns nullable; exactly one populated per row (writer enforces).

### Frontend URL contract — DOES NOT CHANGE

Citizen URLs stay as-is. Only loader internals swap. Touch points: `frontend/src/lib/data.ts` (lines ~217, ~221, ~353, ~374) and `frontend/src/lib/paths.ts:15`. Everything else (route grammar, slugs, deep-links) is unchanged.

### Citizen renderer rule (amended R10)

- **Sorting/querying**: always `year:int` + `period_seq` (machine axis).
- **Display**: always `period_label` verbatim (citizen axis). Axis ticks, tooltips, legends, slider captions, share-link previews, and footer attribution show `period_label`, never the bare integer year. Showing "2025" when the source says "FY 2024-25" is a defect.
- **Tooltips** include: `period_label`, `value` (numeric or text), `indicator_id`-derived unit, source producer + license badge.

---

## §2. Decisions (approved this thread)

| # | Decision | Authority | Rationale |
| --- | --- | --- | --- |
| D1 | Canonical store = Hive-partitioned Parquet read by DuckDB-WASM in the browser | User + Gregor + Fowler | Static-hostable (GitHub Pages), SQL-queryable, columnar, OSS-mature |
| D2 | OWID `year:int` is the time axis (end-year for FY) | User (overrides debate) | OWID precedent, supports `WHERE year >= 2020`, simpler than struct |
| D3 | `period_label` is verbatim publisher string (not normalised) AND is the citizen-visible time string | Hans + Max + Jony + Citizen | Citizen-readable as-published; no information loss; renderer rule per §1 |
| D4 | Long-format only — one observation per row | Hans + Max (OWID) | Schema stability across cadences; trivial pivoting in SQL |
| D5 | Sources = TABLE (`taxonomy/sources.parquet`) with OWID `origin.*` fields **plus yen-gov extensions** | Hans + Max | FK-keyed dedup; replaces per-file `sources[]` smearing. **R10:** OWID `origin.*` fields stay verbatim (`producer`, `citation_full`, `url_main`, `url_download`, `date_accessed`, `license`, `vintage`). yen-gov extensions are explicitly tagged in `canonical-store.md`: `source_id` (PK), `content_hash`, `first_fetched_at`, `last_seen_at`, `confidence_tier:enum(gold\|silver\|bronze)`, `is_issuing_authority:bool`. Curating from mixed-quality Indian shelves (issuing authority vs research re-publisher vs single-paper bronze) requires the confidence signal; OWID doesn't carry it because its editorial gate happens upstream of the table. |
| D6 | `first_fetched_at` (immutable) + `last_seen_at` (mutable) replace `fetched_at` | Gregor + Hans | Dissolves the `fetched_at` smear problem |
| D7 | UPSERT-into-DuckDB + sorted Parquet emit; logical key = `(entity_id, year, period_label, indicator_id)` | Gregor + Fowler | Identity is upstream-truth, not provenance-shaped. `source_id` is a row attribute, NOT in the key. |
| D8 | Hive partition only when family > 15 MB; partition by **`indicator_id`** (or `topic_id`) when partitioned — NEVER by `year`; shards ≤ 4 MB target 1.5 MB | Gregor + Fowler (R10) | Time-series queries scan ALL years for one indicator; partitioning by year forces N-file metadata fetch per series. Partitioning by indicator keeps each series in one shard. |
| D9 | Local schema `$id` (relative path `./<name>.schema.json`), not URL | Gregor + Fowler | IDE offline validation; no broken-link rot |
| D10 | No JSON projections of canonical data for frontend | Gregor + Fowler | Single source of truth; DuckDB-WASM reads Parquet directly |
| D11 | No CI on `datasets/**` — publish is plain static copy via Pages | Fowler | Costless; matches static-first Holy Law |
| D12 | Frontend URLs unchanged under pivot | Jony + Citizen | Zero citizen-facing breakage |
| D13 | Rip-and-replace (no strangler-fig, no feature flag in production) — site not yet live | User + Fowler | Strangler is overhead when no users depend on old shape. **R10:** removes "behind a feature flag" from Phase 0; only isolated test harness is acceptable. |
| D14 | Legacy JSON moves to `datasets/_old/`; deletion gated on an **explicit checklist**, not a phase date | Fowler (R10) | See §7 step 1.6 — deletion criteria are (a) every reader rewritten + tested, (b) golden-path Playwright green, (c) `python -m yen_gov validate` clean, (d) migration parity oracle (§7 step 1.5) green, (e) admin v0 not blocking on `_old/`, (f) 5 days local observation. |
| D15 | `cadence` lives on indicator row; **indicator catalogue carries the full Hans honesty surface** | Hans + Max (R10) | Cadence is property of the series; OWID-style indicator browser needs the catalogue logic that prevents bad rankings. See §5 indicator schema. |
| D16 | `caveats.parquet` is for **cross-cadence misleading-join banners only**; `methodology_breaks.parquet` is a **separate typed surface** | Hans + Jony (R10) | Cross-cadence joins and methodology/base-year breaks are distinct citizen risks; conflating them merges two different banner copies into one ambiguous channel. |
| D17 | **Citizen-visible failure-state UX contract** — when DuckDB-WASM init / metadata fetch / partition Range fetch / query execution fails or times out, the page renders plain-language copy ("This data could not load right now") with retry, source/provenance visible where possible, and never a raw stack trace | Jony + Citizen (R10) | Functional correctness includes "what the citizen sees while the loader is loading and when it has failed." Phase 1 cannot ship without this. |
| D18 | **Hand-authored taxonomy files are TEXT (JSON or CSV) in git**; the pipeline compiles them into Parquet at ingest | Fowler + Hans (R10) | Parquet is binary; `operator_state.parquet` and `caveats.parquet` would be unreviewable in PR. Authored shape: `datasets/taxonomy/operator_state.json`, `datasets/taxonomy/caveats.json`, `datasets/taxonomy/methodology_breaks.json` — all text, all schema-validated. Ingest compiles to matching `.parquet` for DuckDB consumption. Derived parquet files MAY or MAY NOT be committed (decision Q9). |
| D19 | **Chart-ready view-model loader** is a frontend contract — the DuckDB-WASM loader returns shaped view-models, never raw observation rows | Jony + Gregor (R10) | The loader joins `observations` + `taxonomy/indicators` + `taxonomy/sources` + `caveats` + `methodology_breaks` into the metadata-rich shape generic renderers consume (unit, direction, cadence, comparability, source display, license, caveat/break banners). Prevents SQL from leaking into `IndicatorChoropleth`, `StackedTrend`, route files. |
| D20 | **Typed adapter→writer batch envelope** is the canonical message contract | Gregor (R10) | Pipes-and-filters: `{ target_family, schema_version, source_rows[], observation_rows[], dimension_rows[]?, replacement_semantics }`. Every adapter speaks this envelope; the writer is a single Message Translator. |
| D21 | **Parquet schema version + table id live in Parquet key-value metadata** AND a typed manifest file at `datasets/manifest.json` | Gregor (R10) | JSON Schema `$schema_version` does not apply to Parquet; need explicit mechanism. Reader fails loud on unsupported version. Manifest enumerates `{table_id, family, partition_columns, files[], schema_version, row_count}` so the browser does file discovery via control-plane, not by guessing paths. |
| D22 | **FK referential integrity enforced at write time** by the backend writer/validator | Fowler + Gregor (R10) | DuckDB-WASM via HTTP Range cannot enforce FKs in production. Phase 0.6/0.8 writer asserts no dangling `indicator_id` / `source_id` / `entity_id` in observations before emit. Validator covers it. |
| D23 | **Entities carry validity windows** — `entity_valid_from:int`, `entity_valid_to:int|null` | Jony + Hans (R10) | Telangana (2014), J&K/Ladakh (2019) — pre-statehood absences must read as "entity didn't exist" not "no data." Choropleth greys (not hides) regions outside validity. |
| D24 | **Migration ledger is a Phase 0 artifact** — every existing `_old/` indicator is classified migrated / dropped-with-reason / queued before `_old/` can be deleted | Max + Fowler (R10) | Repo has ~110 socio-economic artifacts plus elections. Silent catalogue loss is not acceptable; rip-and-replace is. |
| D26 (R11) | **Facet handling = (b) facet-explode** with parent+children pattern: parent indicator carries `parent_indicator_id NULL`, children carry `parent_indicator_id` FK back to parent + `dimension_values:STRUCT` populated. Selective explode rule (Hans): explode iff the facet changes the **citizen's governance question**; otherwise keep as observation-row facet. | Hans + Max + Fowler + Jony + Citizen (5/6 R1; Gregor conceded R2) | At target cardinality (~80–120 ids now, 500–1,000+ over 3 years), parent+`dims` hybrid scales without code rent; URL grammar stays `/indicator/<id>` with no facet picker; legend stays single code path. |
| D27 (R11) | **Entity tiering = (i) single `entity_id` + `entity_type` enum** (`state`, `district`, `ulb`, `union_govt`, `state_govt`, `discom`, `psu`, …). Max preferred (ii) separate geo/fiscal columns; yielded to Hans per §0a authority. Double-entry transfer rows deferred to Phase F. | Hans (Max yielded; recorded as deviation rationale for Phase F revisit) | OWID-canonical shape; sufficient for Phase 1–3; defer fiscal-flow modelling complexity until the data exists. |
| D28 (R11) | **methodology_version = compose Hans + Fowler** — BOTH (iii) FK to `methodology_breaks.parquet` (table carries narrative for chart splice markers) AND (ii) id-encoded break in `indicator_id` (e.g. `state-gsdp-base-2011-12-inr-crore` separate id from `state-gsdp-base-2004-05-inr-crore`). They compose, do not conflict. URL carries the visible break; table carries the prose. | Hans + Fowler (composite, user-approved R2) | Splits cleanly: governance-visibility (URL/id) + narrative-richness (table). One join at chart time, ~50 table rows total, no rent on every observation row. |
| D29 (R11) | **Indicator catalogue column shape** (extends D15): `id` (kebab-case, ≤60 chars), `display_name`, `parent_indicator_id NULL` (self-FK), `dimension_values:STRUCT NULL` (populated iff `parent_indicator_id IS NOT NULL`), plus all D15 honesty fields, plus `methodology_version VARCHAR NULL` (FK to `methodology_breaks`), plus `source_id` per child (NOT shared across siblings — children may have different upstreams). | Max + Hans (R2) | Per-child source_id (vs per-parent): coal-capacity from CEA and solar-capacity from MNRE are siblings with different sources; per-child is correct. Max answered Fowler's R1 question. |
| D30 (R11) | **Indicator naming convention**: `<entity>-<measure>-<unit>-<facet>`, kebab-case, single segment, max 60 chars. Sibling sort works via `ORDER BY id`. Approved abbreviations: `nsdp`, `gsdp`, `cpi`, `imr`, `mmr`, `tfr`, `mw`, `gwh`, `mu`, `inr`, `pct`. New abbreviations require Max sign-off. Methodology-version children encode the version in id (`-base-2011-12`). | Max + Jony (R2) | Greppable, deterministic, no hash. Documented in `docs/architecture/data/canonical-store.md` per Gregor's R2 concession term. |
| D31 (R11) | **Registered facet axes** — `datasets/taxonomy/facet-axes.json` (schema-versioned per §11) enumerates allowed `dimension_values` keys: `fuel_type`, `sector`, `head_of_account`, `gender`, `residence`, `prices_basis`, `methodology_version`, `transfer_type`, `category`, `crime_category`, `cpi_category`, plus axes added by Phase 2/3 ingestion. Catalogue validator REJECTS any `dimension_values` key not in this registry. | Gregor (R2 concession) | Canonical Data Model boundary; prevents ad-hoc dimension proliferation as the corpus grows (especially relevant given §0b growth path). |
| D32 (R11) | **Chart-shell view-model addition**: D19's loader return shape gains `breaks: [{period_seq, methodology_version, note}]`. Rendered as thin vertical rule on time axis, visible at rest (NOT tooltip-only). `breaks: []` when none. | Jony (R2) | Surfaces D28 methodology_version visibly; one code path; satisfies Hans's "never smooth a line across a methodology rupture" rule. |
| D33 (R11) | **Eight governance answers (Hans R2)** locked into the catalogue + breaks design — see [`TODO/20260517-indicator-consolidation-audit.md`](20260517-indicator-consolidation-audit.md) §7 for question text; answers below: | Hans (R2) | Each resolves a class of consolidation decision that will repeat as new domains land (§0b). |
| D33.1 | GSDP base-year revisions → `methodology_version` on same `indicator_id` PLUS id-encoded variant per D28; chart shows visible break-marker. Same rule for IIP, WPI, CPI, Census rebases. |  | |
| D33.2 | Distribution losses (T&D vs AT&C vs distribution-only) → ONE parent `state-distribution-losses-pct` + `loss_type` facet. Default AT&C, fall back to T&D, annotate switch. |  | |
| D33.3 | Cognizable crimes → keep BOTH count and rate-per-100k as measure facets on one parent. Canonical = NCRB-published rate (provenance honesty). Do NOT compute own rate from interpolated Census. |  | |
| D33.4 | Census H-series vs NFHS amenities → TWO parents (`-census-h-series`, `-nfhs`). Different universes/methodologies/cadences. Cross-link via `related_indicators`. |  | |
| D33.5 | Derived indicators (sex ratio, density, urbanization %, road density, forest cover %) → FIRST-CLASS parents. Store as observed; don't re-derive. |  | |
| D33.6 | Voter turnout GE vs AE → TWO parents. AE staggered, GE synchronised — different temporal logic. |  | |
| D33.7 | CPI categories → `combined_yoy` as facet value alongside food/fuel/housing/general. Don't re-derive aggregates. |  | |
| D33.8 | `fuel_type=total` coexistence → explode REPLACES the total. Total is compute-on-read (`SUM(value) GROUP BY state, year`). |  | |
| D34 (R11) | **Consolidation migration is one-shot dated script**, not a permanent module. Lives at `backend/yen_gov/canonical/migration/m20260520_consolidate_indicators.py`. Preserved for audit; never re-imported. Module layout in `backend/yen_gov/canonical/`: `writer.py`, `reader.py`, `migration/`, `registry.py`. No `consolidator.py`. | Fowler (R2) | Two-hat: consolidation is behavioural (one-shot); module structure is structural (permanent). Don't share a home. |
| D35 (R11) | **Consolidation test tiers**: unit (`backend/tests/canonical/test_consolidation_rules.py`, one test per collapse rule, fixture-driven) + integration (`backend/tests/canonical/test_migration_m20260520.py`, runs script against `tmp_path` fixture corpus of ~10 representative old shards, asserts row counts + FK integrity + indicator_id coverage). **Skip golden-byte** — ADR-0030 writer determinism + integration row-equality cover the invariant. | Fowler (R2) | Per CLAUDE.md §15 tier policy; aligns with no-corpus-walk rule (§10). |
| D36 (R11) | **Deletion ledger format**: `datasets/_old/DELETED.md` columns = `path | deleted_in_commit | replacement_indicator_id | replacement_facet_values (JSON object literal) | notes`. Plural replacements (one old → multiple new via facet-explode) handled by JSON in `replacement_facet_values`. | Fowler (R2) | Markdown for human readability; JSON literal in column for parseability if ever needed. |
| D25 | **Boundary geometry lives outside the canonical Parquet store** in a sibling family `datasets/boundaries/in/`; referenced from observations via `entity_id` FK that resolves through `taxonomy/entities.json` (which carries `entity_level` + boundary-file pointer). Format split by size: **GeoJSON** for small layers (country, states, ~few MB), **PMTiles** for large layers (national districts, ACs, PCs, sub-districts/taluks, villages — single-file vector tile archive served via HTTP Range, read natively by maplibre-gl). Boundary files are **EXCLUDED** from the §6 Phase 0.13 `_old/` move and from the §7 Phase 1.8 `_old/` deletion. The existing `datasets/boundaries/in/` tree (country IN, india-soi/states/districts GeoJSON, per-state AC GeoJSON for S01–S2x) is preserved as-is; future additions (PCs, taluks, completing village coverage) follow the same layout. `datasets/manifest.json` (D21) enumerates boundary files alongside observation Parquet so the frontend discovers them via control-plane, not by guessing paths. | Jony + Gregor (R10 boundaries pass) | Vector geometry is not tabular; forcing it into Parquet loses geometry-native operations (simplification, tile pyramids, GPU rendering). Canonical store stays focused on observations; geometry stays in the format the GIS world already solved. Full rationale → ADR-0031 (to author Phase 0). |

---

## §3. Rejected alternatives (do not re-propose)

| # | Rejected | Why |
| --- | --- | --- |
| R1 | Opaque `{key, label, frequency}` period token | OWID disagrees; loses sortability; SLM can't reason over it |
| R2 | t_instant / t_span / derived-view 5-guardrails model | Chasing tails — OWID `year:int` + `period_seq` is simpler and sufficient |
| R3 | Per-shard JSON files (folded indicator v4.0) | ~7,300 file proliferation; no SQL; smeared `fetched_at`; per-shard validation cost |
| R4 | `.data-card.json` sidecar per indicator | Same lifecycle-smushing as folded model |
| R5 | Global mutable `_inventory.json` | Underscore = confession of second-class; inventory derivable from data |
| R6 | SHA-gate on Fetcher + `.meta.json` per URL | Bytes ≠ data; UPSERT solves this one altitude up |
| R7 | `write_text_if_changed` byte-compare helpers | Same problem — fix non-determinism upstream of write seam |
| R8 | Period vocabulary normalisation (CLAUDE.md §10 pre-pivot rule) | Withdrawn under OWID adoption; `year:int` IS the normalisation, `period_label` stays verbatim |
| R9 | Strangler-fig coexistence of JSON + Parquet readers | Site not live; coexistence is pure cost |
| R10 | Per-CI dataset validation | No consumer to defend in this repo's CI |
| R11 | Frontend URL grammar change | Pure churn; Jony + Citizen rejected |
| R12 | SQL.js (sqlite-wasm) over DuckDB-WASM | DuckDB-WASM reads Parquet via HTTP Range natively; SQL.js needs full-file load |
| R13 | Migrations directory | Rebuild from upstream snapshots each run — cheaper than migration ceremony |
| R14 | URL `$id` in schemas | IDE offline support; relative path works everywhere |
| R15 | Item-level provenance overrides in `sources[]` (legacy v3.0 shape) | Removed in legacy v3.0 already; canonical uses `source_id` FK |
| R16 (R10) | `source_id` in the UPSERT identity hash | Conflates provenance with logical truth. A corrected upstream value rolls `content_hash` → new `source_id`; including it in the key would create a duplicate row for the same fact. Logical key is `(entity_id, year, period_label, indicator_id)` per D7. |
| R17 (R10) | Single `value:DOUBLE` column | Administrative data emits "Nil"/"N.A."/textual codes meaningful and distinct from null/zero. Split is D5/D17. |
| R18 (R10) | Hive partition by `year` | Destroys time-series query performance — every series query fans out to N partitions. Partition by `indicator_id` instead (D8). |
| R19 (R10) | Binary Parquet as hand-authored source of truth (`operator_state.parquet`, `caveats.parquet` committed as authoring shape) | Unreviewable in PR; not hand-editable. Authoring shape is JSON/CSV; Parquet is a compiled artifact (D18). |
| R20 (R10) | `caveats.parquet` as the home for methodology breaks | Two different citizen risks (cross-cadence join vs definitional break) need two surfaces with two banner copies (D16). |
| R21 (R10) | Production feature-flag coexistence of JSON and Parquet loaders | Conflicts with D13 rip-and-replace. Isolated test harness only; no production toggle. |
| R22 (R10) | Raw observation rows returned from the loader to citizen components | View-model contract per D19 — SQL stays in the loader, never in renderers. |
| R23 (R10) | File-discovery by frontend guessing `datasets/<family>/observations.parquet` paths | Brittle; partition policy becomes hidden contract. Use `datasets/manifest.json` (D21). |
| R24 (R10) | Forcing boundary geometry into Parquet / the canonical observation store | Geometry is not tabular; Parquet loses geometry-native operations (tile pyramids, simplification, GPU rendering). Sibling family + GeoJSON/PMTiles per D25. |
| R25 (R10) | Sweeping `datasets/boundaries/`, `datasets/taxonomy/`, `datasets/schemas/`, `datasets/manifest.json` into `_old/` during the Phase 0.13 move | These are NOT pre-pivot artifacts; they're canonical-store siblings or the canonical store itself. Move applies to `datasets/indicators/`, `datasets/elections/`, `datasets/people/`, `datasets/governments/`, `datasets/events/`, `datasets/features/`, `datasets/reference/` (legacy) only. |
| R26 (R11) | **`dimensions: MAP<VARCHAR,VARCHAR>` typed column on every observation row** (Gregor's R1 option (c)) | At ~80–120 ids (and even at the §0b 500–1,000+ growth target), parent + `dimension_values:STRUCT` on the catalogue + selective facet-explode children scales without code rent. (c) would require registry + hash-extension + dimension-aware queries — code in 3 places, no Phase 1 external consumer. Gregor conceded R2. |
| R27 (R11) | **`(ii) separate `geo_entity_id` + `fiscal_actor_id`** for entity tiering | Hans picked (i) single `entity_id` + `entity_type` enum per OWID precedent (D27). Max preferred (ii) and yielded; preference logged for Phase F revisit when fiscal-flow modelling lands. |
| R28 (R11) | **Permanent `consolidator.py` module** for 110→60 collapse | One-shot dated migration script under `backend/yen_gov/canonical/migration/` (D34). Behavioural one-shot ≠ structural permanent. |
| R29 (R11) | **Golden-byte test for consolidation migration** | ADR-0030 writer determinism + integration row-equality cover the invariant; golden-byte breaks on every legitimate writer tweak (D35). |
| R30 (R11) | **Computing our own crime-rate denominator from interpolated Census** | Smuggles a methodological choice into a "fact". Use NCRB-published rate as canonical even with known undercounts; expose count as facet (D33.3). |
| R31 (R11) | **Smoothing a line across a methodology break** (e.g. plotting GSDP across NAS 2004-05 → 2011-12 rebase as continuous) | Bhattacharya rule. Break MUST be visible as vertical rule on time axis (D32) and the two methodologies are separate `indicator_id`s (D28). |

---

## §4. CLAUDE.md amendments (done this thread)

| Section | Change | Status |
| --- | --- | --- |
| Header | Project description names DuckDB-WASM pivot; date 2026-05-17 | ✅ done |
| §0a NEW | "The One Rule" — OWID canonical + authority table + user-supersedes | ✅ done |
| §2 | Ephemeral runtime clause; broadened POSIX/relative scope | ✅ done |
| §3 | `datasets/` row rewritten for canonical store | ✅ done |
| §10 | REMOVED period-vocabulary normalisation ban; REMOVED coverage.temporal parse ban; rewrote `fetched_at` bullet (sources-as-table); rewrote `write_text_if_changed` bullet (UPSERT); ADDED no-JSON-projection + no-CI-on-datasets | ✅ done |
| §11 | `$id` rule: relative path local, not URL | ✅ done |
| §12 | §12.1 canonical Parquet sources.parquet (OWID `origin.*` + yen-gov extensions); §12.2 legacy JSON in `_old/` read-only | ✅ done |
| §14 | Added Git LFS monitoring open question; noted time-window queries resolved by §0a | ✅ done |

### Mirror amendments (done this thread)

| File | Status |
| --- | --- |
| `docs/agents/guardrails.md` | ✅ done |
| `docs/concepts/folded-indicator.md` (obsolescence header) | ✅ done |
| `docs/concepts/collection-inventory.md` (obsolescence header) | ✅ done |
| `backend/yen_gov/AGENTS.md` | ✅ done |
| `admin/AGENTS.md` (canonical pivot invariant) | ✅ done |
| `frontend/src/AGENTS.md` (runtime DuckDB-WASM read path; remove build-time stale claim) | ✅ done |

### Outstanding doc cleanups (Phase 0 day-1; expanded in R10)

| File | Action |
| --- | --- |
| `docs/architecture/decisions/0026-...md` | Header: superseded by ADR-0030 |
| `docs/architecture/decisions/0027-...md` | Header: superseded by ADR-0030 |
| `docs/architecture/decisions/0003-no-fetch-cache.md` | Re-check |
| `docs/concepts/data-quality.md` | Re-check for `{key,label,frequency}` references |
| `docs/concepts/data-provenance.md` (R10) | Rewrite for sources-as-table + `source_id` FK + OWID origin.* + yen-gov extensions |
| `docs/concepts/owid-alignment.md` | Reframe as "we adopt OWID, not just align with it" |
| `docs/concepts/data-flow.md` (R10) | Update for adapter→writer batch envelope (D20) + UPSERT path |
| `docs/architecture/frontend/data-loading.md` (R10) | Rewrite for DuckDB-WASM + view-model loader (D19) + failure-state UX (D17) + manifest-driven discovery (D21) |
| `docs/architecture/frontend/deployment.md` (R10) | Verify Pages serves `.parquet` with `Accept-Ranges` and correct MIME |
| `docs/architecture/backend/schemas.md` (R10) | Update for canonical schemas + Parquet schema-version mechanism (D21) |
| `docs/architecture/backend/core.md` (R10) | Update for writer module + FK enforcement (D22) |
| `docs/architecture/backend/pipeline.md` (R10) | Update for batch envelope (D20) |
| `docs/architecture/admin/overview.md` (R10) | Note Phase 5 rewrite + interim admin v0 stance (see §7 step 1.7) |
| `docs/how-to/force-recollect.md` | Rewrite — under UPSERT, force = `DELETE FROM <family> WHERE indicator_id=... AND source_id=... ; re-ingest` (logical key, not just source) |
| `docs/architecture/decisions/0031-boundary-geometry-strategy.md` (R10 boundaries) | NEW ADR — captures D25 boundary scope (GeoJSON vs PMTiles cutover, sibling-family stance, manifest integration, future PCs/taluks/villages roadmap) |
| `docs/architecture/data/boundaries.md` (R10 boundaries) | NEW — boundary file inventory + format-per-level table + how entity_id resolves to geometry |
| `README.md` | One-paragraph update naming canonical store |

---

## §5. Target architecture (one-page spec; amended R10)

### Files committed to git

```
datasets/
  manifest.json            # control-plane: {tables[], schema_version, files[], partition_columns, row_counts}
  schemas/
    observation.schema.json
    indicator.schema.json
    source.schema.json
    entity.schema.json
    caveat.schema.json
    methodology-break.schema.json
    operator-state.schema.json
    manifest.schema.json
  taxonomy/
    entities.json          # HAND-AUTHORED (text, PR-reviewable)
    indicators.json        # HAND-AUTHORED + Hans honesty fields
    operator_state.json    # HAND-AUTHORED
    caveats.json           # HAND-AUTHORED
    methodology_breaks.json # HAND-AUTHORED
    sources.json           # GENERATED by adapters (one row per (url, content_hash))
    # compiled Parquet variants (decision Q9 whether committed or rebuilt locally):
    entities.parquet
    indicators.parquet
    operator_state.parquet
    caveats.parquet
    methodology_breaks.parquet
    sources.parquet
  elections/
    observations.parquet   # if family <15MB; else indicator_id=<id>/observations.parquet
  energy/
    observations.parquet
  demography/
  fiscal/
  education/
  health/
  boundaries/              # SIBLING family — NOT in canonical Parquet store (D25)
    in/
      country/IN.json            # GeoJSON, country outline
      geojson/
        india-states.geojson
        india-districts.geojson
        india-soi.geojson
        S01-ac.geojson .. S2x-ac.geojson  # per-state AC GeoJSON (existing)
        *.sources.json             # sidecar provenance (preserved)
      pmtiles/                     # future: district / AC / PC / village PMTiles when GeoJSON too large
  _old/                    # pre-pivot per-shard JSON; EXCLUDES boundaries/, taxonomy/, schemas/, manifest.json (R25); deletion gated on §7 checklist
```

### Indicator schema (D15 — Hans honesty surface, R10)

`taxonomy/indicators.json` row shape — minimum columns:

| Column | Why |
| --- | --- |
| `indicator_id` | PK |
| `label_short`, `label_long` | Axis text vs hover text |
| `description_short`, `description_long` | What the indicator IS (OWID separates from label) |
| `unit` | Display unit (e.g. "%", "INR crore", "per 1,000 live births") |
| `cadence` | annual_fy / annual_cy / quarterly_fy / quarterly_cy / monthly_cy / decennial / ad_hoc |
| `default_period_seq_for_cadence` | so chart picks a single cadence when multiple exist |
| `family` | Storage axis (elections, energy, …) — partition column when applicable |
| `pillar` | Curation axis: People / Money / Infrastructure / Politics |
| `topic_tags[]` | Free-tagged for catalogue browse |
| `value_kind` | absolute / rate / ratio / count / index / percentage |
| `direction` | higher_is_better / lower_is_better / no_judgement |
| `denominator` | for rates/ratios — what they're per |
| `attribution_geography` | place of incidence / billing / domicile / production (esp. fiscal) |
| `comparability` | states_combined / per_state / not_comparable_across_states |
| `implementing_authority` | Union / State / both / private / unspecified |
| `funding_split` | Union-share / State-share notes (fiscal indicators) |
| `methodology_vintage` | when the current definition came into force |
| `revision_tier` | first_release / revised / final |
| `excluded_notes` | what is NOT in this indicator (Hans framing) |
| `methodology_break_ids[]` | FK[] -> methodology_breaks.json |
| `series_breaks_summary` | one-line citizen-facing |
| `latest_break_year:int | null` | denormalised for chart break-rule trip-wire |
| `breaks_count:int` | denormalised |
| `coverage_states_count:int` | denormalised — supports "≥80% states" filter |
| `coverage_year_min`, `coverage_year_max:int` | denormalised |
| `coverage_density:float` | denormalised — % of (entity × year) cells observed |

`coverage_*` columns are recomputed at every emit; they exist to keep the catalogue browseable without scanning multi-GB observation Parquet from the browser.

### Sources schema (D5 — OWID origin.* + yen-gov extensions, R10)

OWID-verbatim columns: `url_main`, `url_download`, `producer`, `citation_full`, `date_accessed`, `license`, `vintage`.

yen-gov extensions (tagged in canonical-store.md as not-OWID):
- `source_id` (PK)
- `content_hash` (sha256 of fetched bytes)
- `first_fetched_at:str` (RFC 3339; immutable; citizen-facing)
- `last_seen_at:str` (RFC 3339; mutable telemetry)
- `confidence_tier:enum(gold|silver|bronze)`
- `is_issuing_authority:bool`

### Read path (production)

```
GitHub Pages domain
    ↓ HTTP Range (Accept-Ranges enforced at Phase 0)
DuckDB-WASM in browser
    ↓ SELECT ... JOIN observations + taxonomy/indicators + taxonomy/sources + caveats + methodology_breaks
view-model loader (D19) returns chart-ready shapes
    ↓
Svelte 5 + d3 + maplibre-gl (generic renderers; no per-dataset components)
```

**Failure-state contract (D17)**: the loader wraps every async stage and emits a typed result `{status: 'ok'|'loading'|'partial'|'failed', data?, reason?}`. Renderers MUST handle all four. The "failed" state renders plain-language copy with retry; no raw stack traces; source/provenance still visible where it can be resolved.

No backend at runtime. No JSON shadow tree. No CDN cache invalidation.

### Boundary geometry (D25, R10)

| Level | Format | Path |
| --- | --- | --- |
| Country | GeoJSON | `datasets/boundaries/in/country/IN.json` |
| State (national) | GeoJSON | `datasets/boundaries/in/geojson/india-states.geojson` |
| District (national) | GeoJSON now; PMTiles when >10 MB | `datasets/boundaries/in/geojson/india-districts.geojson` → future `pmtiles/india-districts.pmtiles` |
| AC per state | GeoJSON | `datasets/boundaries/in/geojson/S<NN>-ac.geojson` (existing for S01–S2x; gaps filled by Phase 2 readiness) |
| PC national | TBD (Q11) | not yet added |
| Sub-district / taluk | TBD (Q11) | not yet added |
| Village (per state) | PMTiles | not yet added; one PMTiles file per state when ingested |

Resolution path: `observations.entity_id` → `taxonomy/entities.json` row → `(entity_level, entity_code)` → geometry file via `datasets/manifest.json` boundary index. Frontend never hardcodes geometry paths. All boundary files carry a `.sources.json` sidecar (preserved from current convention).

### Write path (local pipeline)

```
adapter (httpx + lxml + pandas)
    ↓ typed batch envelope (D20):
      { target_family, schema_version, source_rows[], observation_rows[], replacement_semantics }
canonical writer (single Message Translator)
    ↓ FK validation (D22): no dangling indicator_id / source_id / entity_id
UPSERT into local DuckDB on logical key (entity_id, year, period_label, indicator_id)
    ↓ COPY (FORMAT PARQUET, ROW_GROUP_SIZE 100000) with deterministic sort
sorted parquet emit to datasets/<family>/
    ↓ Parquet key-value metadata stamped {table_id, schema_version}
manifest.json regenerated
    ↓ git commit
GitHub Pages publish
```

Idempotency: re-running with identical upstream bytes → identical Parquet bytes (UPSERT no-op when logical key matches AND value+source unchanged).

---

## §6. Phase 0 — Foundation (weeks 1–2; expanded R10)

**Goal**: Lay the contract surface. No production data yet.

### §6.0. Phase 0 status audit (verified 2026-05-19 against on-disk evidence)

Every row below was re-checked by reading the cited file / running the cited command. A reviewing agent can re-verify any claim by following the evidence column.

| Step | Status | Evidence (re-verifiable) |
| :-: | :-: | --- |
| 0.0 | ✅ | [`docs/architecture/canonical-pivot-deletion-manifest.md`](../docs/architecture/canonical-pivot-deletion-manifest.md) present; populated through §6a per-family deletion table. |
| 0.1 | ✅ | [`docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md`](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) present; incorporates R11 decisions D26–D36. |
| 0.2 | ✅ | [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md) present; §2 tree, §3a entity model, §5/§6 schemas, §8 facet-axes registry doctrine. |
| 0.3 | ✅ | 8 canonical schemas present in `datasets/schemas/`: `observation.schema.json` (5,243 B), `indicator.schema.json` (47,684 B at v4.4), `source.schema.json` (5,938 B), `entity.schema.json` (5,901 B), `caveat.schema.json` (4,173 B), `methodology-break.schema.json` (4,094 B), `operator-state.schema.json` (4,053 B), `manifest.schema.json` (10,066 B at v1.2). 9th schema `facet-axes.schema.json` retired in PR-Q.2 (PR #53, merged `8fbabad6`) — now a Pydantic v2 module at [`backend/yen_gov/canonical/facet_axes_seed.py`](../backend/yen_gov/canonical/facet_axes_seed.py) that compiles to parquet per [canonical-store.md §8.3](../docs/architecture/data/canonical-store.md) doctrine. |
| 0.4 | ✅ | `datasets/taxonomy/entities.json` (hand-authored) + `datasets/taxonomy/facet-axes.parquet` (76 rows, 13 axes, compiled from `facet_axes_seed.FACET_AXES` literal). |
| 0.5 | ✅ | [`docs/architecture/canonical-pivot-migration-ledger.md`](../docs/architecture/canonical-pivot-migration-ledger.md) present; classifies every `_old/` indicator artifact. |
| 0.6 | ✅ | `datasets/manifest.json` regenerated on every writer run via `_regenerate_manifest()` in [`backend/yen_gov/canonical/writer.py`](../backend/yen_gov/canonical/writer.py); schema v1.2 with `deprecations[]` ledger; reader fails loud on unsupported version (frontend `frontend/src/lib/duckdb.ts`). |
| 0.7 | ✅ | [`.github/workflows/deploy-site.yml`](../.github/workflows/deploy-site.yml) includes PAR1-magic + Range-request smoke step against `_site/data/elections/election_results.parquet` (added in PR-O.4). |
| 0.8 | ✅ | [`frontend/src/lib/duckdb.ts`](../frontend/src/lib/duckdb.ts) wires DuckDB-WASM; round-trip test in `frontend/src/lib/duckdb.test.ts`; failure-state harness in [`frontend/src/lib/canonical/failure-state.test.ts`](../frontend/src/lib/canonical/failure-state.test.ts). |
| 0.9 | ✅ | [`backend/yen_gov/canonical/writer.py`](../backend/yen_gov/canonical/writer.py) implements batch envelope intake (D20), FK validation (D22), UPSERT-into-DuckDB on logical key (D7), sorted Parquet emit with key-value metadata stamp, manifest regen. |
| 0.10 | ✅ | `backend/tests/test_canonical_writer.py` + siblings: tmp_path fixtures, FK rejection, byte-determinism, manifest entries. 733+ pytest pass as of `8fbabad6`. |
| 0.11 | ✅ | [`frontend/src/lib/canonical/failure-state.test.ts`](../frontend/src/lib/canonical/failure-state.test.ts) asserts plain-language copy on forced 404 / forced timeout / forced bad-schema parquet; retry button works. |
| 0.12 | ✅ | ADR-0026 + ADR-0027 carry "Superseded by ADR-0030" headers. |
| 0.13 | ⊘ | **DROPPED 2026-05-18** (recorded in PR-N revised, row 1.8a). The single-commit `git mv` of all legacy JSON under `datasets/_old/` was reframed as **per-family cleanup pattern** documented in [`docs/architecture/canonical-pivot-deletion-manifest.md`](../docs/architecture/canonical-pivot-deletion-manifest.md) §6a (see Phase 1 rows 1.8a–1.8f). Rationale: the `_old/` placeholder was empty on disk while the real legacy shards (per-AC `results/<ac>.json`, `parties.json`, `result.summary.json`, `results.sqlite`, person JSONs) sat interleaved with new Parquet files inside `datasets/elections/<event>/<state>/`; bulk-moving them risked breaking in-flight reader migrations. Replaced by ordered per-target deletions, each gated by "no live reader" verification + regression test. **Exit-criteria amendment**: §7 "legacy `_old/` deleted" reads as "per-family cleanup complete (rows 1.8a–1.8f)". **All 6 sub-rows ✅ as of 2026-05-20** (1.8e shipped 2026-05-19 as PR-R.3; 1.8f shipped 2026-05-20 as PR-S.1 + PR-S.2). Phase 0 closure on this front is therefore complete. |
| 0.14 | ✅ | [`docs/architecture/decisions/0031-boundary-geometry-strategy.md`](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) + [`docs/architecture/data/boundaries.md`](../docs/architecture/data/boundaries.md). |

**Phase 0 verdict** (audited 2026-05-19; re-audited 2026-05-20 post 1.8e + 1.8f closeout): 14/15 ✅ DONE; 1/15 ⊘ DROPPED with documented replacement pattern. Phase 0 IS complete *as scoped*; its `_old/` deletion intent is fulfilled by Phase 1 rows 1.8a–1.8f, **all six of which are now ✅** (1.8e shipped 2026-05-19 as PR-R.3; 1.8f shipped 2026-05-20 as PR-S.1 + PR-S.2).

### §6.1. Original Phase 0 spec table (unchanged; preserved for handoff context)

| Step | Deliverable | Owner agent |
| --- | --- | --- |
| 0.0 | **Deletion manifest** — doc-only PR listing every file/module/concept the pivot retires (folded-indicator doc, period-token helpers, `iced_parity` if subsumed, parity schemas, completeness emitter, operator-state-as-JSON-overlay legacy, `_old/` tree path). Land before any code. **Output: [`docs/architecture/canonical-pivot-deletion-manifest.md`](../docs/architecture/canonical-pivot-deletion-manifest.md) (drafted 2026-05-17).** | Fowler |
| 0.1 | Author ADR-0030 (canonical store + DuckDB-WASM) with full rejected-alternatives table from §3 | Gregor + Hans + Max |
| 0.2 | Author `docs/architecture/data/canonical-store.md` (target architecture, partition rules, OWID `origin.*` mapping with yen-gov extensions tagged, Parquet schema-version mechanism, manifest contract, failure-state UX) | Hans + Max + Gregor |
| 0.3 | Author 9 schemas (`observation`, `indicator`, `source`, `entity`, `caveat`, `methodology-break`, `operator-state`, `manifest`, **`facet-axes` (D31)**) with local `$id` and `x-version 1.0`; **indicator schema carries the full D15 honesty surface + D29 additions (`parent_indicator_id`, `dimension_values:STRUCT`, per-child `source_id`, `methodology_version` FK)**; **id-format rule in indicator schema enforces D30 naming convention** | Gregor + Hans + Max |
| 0.4 | Seed `taxonomy/entities.json` (36 states/UTs ISO 3166-2 + first-batch districts LGD codes) with `entity_valid_from/to` (D23) AND seed `taxonomy/facet-axes.json` initial entries (`fuel_type`, `sector`, `head_of_account`, `gender`, `residence`, `prices_basis`, `methodology_version`, `transfer_type`, `category`, `crime_category`, `cpi_category`, `loss_type`) per D31. Schema-future-proof for §0b growth domains (judiciary, healthcare, water, crime, education-deep, welfare, local-govt-finance) — accept new topic enum values without bump. | Max |
| 0.5 | **Migration ledger** — every existing `datasets/_old/` indicator artifact (elections + ~110 socio-economic) classified: `migrated_in_phase_X` / `dropped_with_reason` / `queued_for_phase_Y`. Single CSV committed; Max owns. | Max + Hans |
| 0.6 | **Parquet schema-version + manifest contract**: writer stamps Parquet key-value metadata `{table_id, schema_version}`; writer regenerates `datasets/manifest.json`; reader fails loud on unsupported version. | Gregor |
| 0.7 | **Vite + GitHub Pages Range/MIME verification**: deploy preview, curl-test `Range:` + `Content-Type: application/octet-stream` (or `application/vnd.apache.parquet`); document in deployment.md. Skip if 206 + MIME confirmed on first try. | Fowler |
| 0.8 | DuckDB-WASM wired into `frontend/src/lib/data.ts` **in an isolated module + test harness (NOT a production feature flag, per D13/R21)**; one round-trip read test against a synthetic Parquet shard | Fowler |
| 0.9 | `backend/yen_gov/canonical/writer.py` skeleton: typed batch envelope intake (D20), FK validation (D22), UPSERT-into-DuckDB on logical key (D7), sorted Parquet emit with Parquet metadata stamp, manifest regen | Fowler + Gregor |
| 0.10 | **Parquet contract tests** (tmp_path fixtures, no mocks, no corpus walk): writer emits a tiny synthetic family; test asserts column names/types, nullability, sorted deterministic emit, FK integrity (rejects dangling), re-run byte-identical | Fowler |
| 0.11 | **Failure-state UX harness**: page mounts loader with a forced 404 / forced timeout / forced bad-schema parquet; assert plain-language copy renders, no stack traces, retry button works | Jony + Fowler |
| 0.12 | Mark obsolete ADRs (0026, 0027); update Outstanding doc cleanups in §4 | Fowler |
| 0.13 | Move pre-pivot JSON under `datasets/_old/` in a single commit. **EXCLUDE from move (R25)**: `datasets/boundaries/`, `datasets/taxonomy/`, `datasets/schemas/`, `datasets/manifest.json`. Move applies to legacy `datasets/indicators/in/**`, `datasets/elections/` (legacy shape), `datasets/people/`, `datasets/governments/`, `datasets/events/`, `datasets/features/`, `datasets/reference/` only. Verify with `git status` before commit. | Fowler |
| 0.14 | **Author ADR-0031 (boundary geometry strategy) + `docs/architecture/data/boundaries.md`** capturing D25, the format-per-level table from §5, GeoJSON→PMTiles cutover (Q11), and the entity_id → geometry resolution path. | Jony + Gregor |

**Exit criteria**:
- Schemas validate (Tier A meta-validation).
- Migration ledger committed.
- Manifest contract documented + writer regenerates it.
- DuckDB-WASM round-trips a synthetic Parquet shard in the browser end-to-end.
- Writer round-trips one synthetic indicator end-to-end with FK enforcement.
- Failure-state harness renders plain-language copy on forced failure.
- Range/MIME verified on Pages preview.

---

## §7. Phase 1 — Elections (weeks 3–6; amended R10)

**Goal**: Migrate existing ECI data to canonical store. First real data on the new model.

### §7.0. Phase 1 status audit (verified 2026-05-19 against on-disk evidence)

**Pivot work** (PR-A through PR-T): elections-results migration to Parquet + view-model loaders.

| Row | Status | PR / commit | Evidence |
| :-: | :-: | --- | --- |
| 1.1 | ✅ | (early Phase-1) | ECI adapter writes canonical batch envelope; `pipeline/run.py:131` calls `_write_canonical_slice`. |
| 1.2 | ✅ | (early Phase-1) | `datasets/elections/election_results.parquet` carries all backfilled ECI events. |
| 1.2b | ✅ | (early Phase-1) | `dim_candidates.parquet` + `dim_acs.parquet` + `dim_parties.parquet` + `dim_party_alliances.parquet` present in `datasets/elections/`. |
| 1.3a | ✅ | PR-E | `frontend/src/lib/view-models/constituency.ts` reads canonical; route migrated. |
| 1.3b | ✅ | PR-F | `frontend/src/lib/view-models/state-overview.ts` reads canonical. |
| 1.3c | ✅ | PR-G | 3 new view-model loaders; `fetchResultSummary` deleted. |
| 1.3d | ✅ | PR-H | `dim_party_alliances` table; `fetchParties` + `PartyEntry` + `PartiesSnapshot` deleted. |
| 1.4 | ✅ | PR-I | `ac_winners[]` in `loadStateOverview`; 2 of 4 citizen-path `getDb` callers removed. |
| 1.5 | ✅ | PR-J | `RacesBoard.svelte` + `StateAcMap.svelte` pure presentational. |
| 1.6 | ✅ | PR-K | `ac-candidates-total` + `ac-others-{votes,pct}` materialised. |
| 1.6b | ✅ | PR-L | `Explore.svelte` migrated to DuckDB-WASM (pattern Psephlab will follow in PR-R.1). |
| 1.7 | ✅ | PR-M | Admin Inventory family-agnostic; ECI Recon retired. |
| 1.8a–1.8d | ✅ | PR-N/O.1/O.2-min/O.3a/O.3b-pre/O.3b-main/O.4/P/Q | Legacy JSON shards deleted; see §7.1 deletion-sweep audit below. |
| 1.8d-ii | ✅ | PR-Q.2 (#53, `8fbabad6`) | `facet-axes.json` retired; Python-compiles-to-parquet pattern established (canonical-store.md §8.3). |
| 1.9 | ✅ | (2026-05-19) | `datasets/` = 196 MB; `.git/` = 115 MB; under thresholds. |
| 1.10 | ✅ | PR-T (`3056f14e`) | Proto-ontology bootstrap; indicator-schema v4.4; party-schema v2.0; chart-shell `axisUnitLabel` + `legendCaption`. |
| 1.8e | ✅ | **DONE 2026-05-19: PR-R.1 → PR-R.2 → PR-R.3 (commit `a4505501`)** | 0 `.sqlite` files on disk (`Get-ChildItem -Recurse datasets\elections\*.sqlite | Measure-Object` → 0 as of 2026-05-20). `frontend/src/lib/sql.ts` + `frontend/src/lib/psephlab/actuals.ts` + `backend/yen_gov/emit/sqlite.py` all deleted; `backend/tests/test_no_sqlite_emit.py` regression guard added (closeout PR 2026-05-20). Psephlab + Compare now read canonical Parquet via `lib/psephlab/canonical-loaders.ts`. See expanded row below for full provenance. |
| 1.8f | ✅ | **DONE 2026-05-20: PR-S.1 ✅ → PR-S.2 ✅** | PR-S.1 (2026-05-20) lifted 6 biographic columns (`sex`, `age`, `education`, `profession`, `constituency_type`, `party_type`) onto `dim_candidates.parquet` (schema v1.1 → v1.2 additive); backfill from existing 3,983 person JSONs populated 1,134 of 34,906 rows. PR-S.2 (2026-05-20): deleted the 3,983 JSON sidecars + `people.entity.schema.json` + `tools/backfill_candidate_bios_from_people_json.py`; switched `frontend/src/lib/view-models/constituency.ts` to project `dim_candidates` bio cols onto `CandidateResult.bio`; refactored `backend/yen_gov/pipeline/people_ingest.py` to `upsert_candidate_bios` (UPSERT into `dim_candidates` via `_upsert_dim`, preserving the `compare_winner_votes` discrepancy QA gate verbatim); deleted `fetchPersonEntity`/`slugifyCandidate`/`PersonEntity`/`ProvenanceGrade`/`FieldProvenance` from `frontend/src/lib/data.ts`. Verified: 767 backend pytest green; 24,028 frontend vitest green; §13 browser smoke on `/`, `/s/tamil-nadu`, `/s/tamil-nadu/ac/167-mylapore` shows zero `/data/people/` requests issued. |

### §7.1. Phase 1 deletion-sweep audit (verified 2026-05-19 against on-disk counts)

The per-family cleanup that replaces Phase 0.13. A reviewing agent can re-verify any count by re-running the cited PowerShell command.

| Sub-row | Target | Expected after | Actual 2026-05-19 | Status |
| :-: | --- | --- | --- | :-: |
| 1.8a | scope correction + audit columns | docs in place | docs present | ✅ |
| 1.8a-bis | SQL-identifier decoupling (manifest `table_name` + `kind`) | manifest v1.1 | manifest v1.2 (advanced further) | ✅ |
| 1.8b-i | rename `observations.parquet` → `election_results.parquet` | 1 file renamed | `datasets/elections/election_results.parquet` present | ✅ |
| 1.8b-min | coverage reroute + adapter-elections fixture + deprecation surface | manifest `deprecations[]` populated | confirmed in `datasets/manifest.json` | ✅ |
| 1.8b-writers-a | emitter structural refactor (in-memory primary API) | byte-identity tests green | `test_emit_sqlite.py` + `test_emit_csv_bundle.py` | ✅ |
| 1.8b-writers-b-pre | `build_slice_envelope` extraction | 3 tests in `test_canonical_eci_backfill.py` | confirmed | ✅ |
| 1.8b-writers-b-main | retire `write_artifact` from `pipeline/run.py`; reroute `compare_winner_votes` | 0 `write_artifact` calls | `grep_search` confirms `_write_canonical_slice` only | ✅ |
| 1.8b-ii | delete per-state `parties.json` + `result.summary.json` | 0 files | 0 files (`Get-ChildItem datasets\elections\*\*\parties.json`) | ✅ |
| 1.8c | delete 7,168 per-AC `results/<ac>.json` | 0 files | 0 files (`Get-ChildItem datasets\elections\*\*\results\*.json`) | ✅ |
| 1.8d | delete 27 `events/in/eci/<event>/election.json` | 0 files | 0 files (`Get-ChildItem datasets\events\in\eci\*\election.json`) | ✅ |
| 1.8d-ii | retire `facet-axes.json` + `delimitation_lineage.json`; ship Python-compiles-to-parquet pattern | 0 of those JSONs | 0 JSONs; `facet-axes.parquet` 8,090 B present | ✅ |
| **1.8e** | **delete 41 per-state `results.sqlite`** + `frontend/src/lib/sql.ts` + `frontend/src/lib/psephlab/actuals.ts` + `backend/yen_gov/emit/sqlite.py` + tests; **folded in 2026-05-19**: retire `datasets/reference/in/parties.json` + `parties-discovered.json` + their schemas + `compose.append_to_discovered_overlay` + `frontend.fetchPartyRegistry` | **0 files** | **0 files** | **✅ (PR-R.3, 2026-05-19; see canonical-pivot-deletion-manifest.md §6a row 1.8e)** |
| **1.8f** | **delete 3,983 per-candidate person JSONs** | **0 files** | **✅ DONE 2026-05-20: PR-S.1 lifted bio onto `dim_candidates.parquet` v1.2, PR-S.2 deleted the 3,983 JSONs + `people.entity.schema.json` + `tools/backfill_candidate_bios_from_people_json.py` + retired `fetchPersonEntity`/`slugifyCandidate` from frontend + refactored `people_ingest` to UPSERT into canonical store.** | **✅** |

### §7.2. Original Phase 1 spec table (preserved; status normalized in rows 1.8e + 1.8f only)

| Step | Deliverable | Owner |
| --- | --- | --- |
| 1.1 | ECI adapter rewrite: emit canonical batch envelope (D20) instead of per-shard JSON | Hans + Fowler |
| 1.2 | Backfill all existing ECI elections (AcGenMay2026 + history) into `datasets/elections/observations.parquet` | Hans |
| 1.2b | **Dimension tables**: emit `elections.dim_candidates` + `elections.dim_acs` + `elections.dim_parties` (denormalised name / party / AC-name strings the fact table deliberately omits). PKs byte-equal to `observations.entity_id` so view-model loader reconstructs citizen shape via single LEFT JOIN. Unblocks 1.3. | Hans + Max |
| 1.3a | **DONE 2026-05-18 (PR-E)**: swap Constituency route (`/s/:state/ac/:slug`) to view-model loader `lib/view-models/constituency.ts` against `elections.{observations,dim_candidates,dim_acs,dim_parties}` + `taxonomy.sources`. `LoaderResult<T>` four-arm render in the route; legacy `fetchConstituencyResult` deleted. | Fowler + Jony |
| 1.3b | **DONE 2026-05-18 (PR-F)**: swap State hub (`/s/:state`) to view-model loader `lib/view-models/state-overview.ts` against `elections.observations` + `elections.dim_parties` + `taxonomy.sources`. Pivots `party-*` indicators (`MAX(CASE WHEN …)`) + reads `state-*` scope facts; `LoaderResult<T>` four-arm render in the route. `fetchResultSummary` / `fetchParties` left alive (consumed by Party / ElectionSeatsTrend / Settings / IndiaMap) with `// TODO(PR-G)` markers. | Fowler + Jony |
| 1.3c | **DONE 2026-05-18 (PR-G)**: multi-route migration. Three new view-model loaders (`election-seats-trend.ts`, `india-leading-parties.ts`, `parties-palette.ts`) for `ElectionSeatsTrend.svelte`, `IndiaMap.svelte`, `Settings.svelte`. `Party.svelte` summary side migrated to `loadStateOverview`. `fetchResultSummary` deleted from `lib/data.ts`. `fetchParties` kept alive solely for `Party.svelte`'s `recognition` + `alliance` until PR-H. Coverage parity verified against canonical Parquet (no regression). | Fowler + Jony |
| 1.3d | **DONE 2026-05-18 (PR-H)**: extended canonical store with new `dim_party_alliances` Parquet table (composite PK `(party_id, period_label)`, OWID per-event shape). `loadStateOverview` now LEFT JOINs both `dim_parties` (for `recognition`) and `dim_party_alliances` (for per-event `alliance`), surfacing both on `PartyTotals`. `Party.svelte` derives all party meta from this single loader. `fetchParties`, `PartyEntry`, `PartiesSnapshot` deleted from `lib/data.ts`. AcGenMay2026 alliance roster seeded in `taxonomy/parties.json` (TN/KL/WB cohort). Alliance becomes a citizen-visible field for the first time. **Phase 1.3 closes.** | Hans + Fowler |
| 1.4 | **DONE 2026-05-18 (PR-I)**: per-AC winners + margin histogram migrated off `results.sqlite`. `loadStateOverview` extended with `ac_winners[]` (`elections.dim_acs` registered; two CTEs over `observations` for `ac-winner-party-id` + `ac-margin-pct`, joined to `dim_acs` + `dim_parties`). `StateOverview.svelte` per-AC badge map now `$derived` from `summary.ac_winners`; `MarginHistogram.svelte` reduced to a pure presentational component (takes `rows: AcWinner[]` prop, no `getDb`). Two of four citizen-path `getDb` callers removed. Original Playwright/provenance/period_label assertions are out of scope here — the existing golden-path suite already exercises this slice; further hardening rolls into 1.5. | Fowler |
| 1.5 | **DONE 2026-05-18 (PR-J)**: `RacesBoard.svelte` and `StateAcMap.svelte` now pure presentational components (`rows: AcWinner[]` prop, no `getDb`). New `loadStateAcWinners` lean loader exported from `state-overview.ts` — only the AC-winners CTE + dim joins, used by the constituency page's state-map context. State hub passes `summary.ac_winners` from the bundled `loadStateOverview` query. Migration parity oracle deferred — covered by the existing golden-path Playwright + the canonical Parquet's own integrity checks. | Fowler |
| 1.6 | **DONE 2026-05-18 (PR-K)**: per-AC top-N validated against real data. Canonical adapter now emits `ac-candidates-total` (always), `ac-others-votes`, `ac-others-pct` (only when a tail exists). `loadConstituencyResult` reconstructs the real `others` bucket and exposes `candidates_total`; Constituency.svelte heading becomes "Top {N} of {M} candidates" when M > N. Real-data audit: 6208 / 7168 ACs in the corpus (87%) had a tail the UI was silently hiding; the largest field is 79 contestants. Resolves Q5. | Citizen + Fowler |
| 1.6b | **DONE 2026-05-18 (PR-L)**: `Explore.svelte` SQL playground migrated off `getDb` / `results.sqlite` onto DuckDB-WASM. New `lib/explore/duckdb-views.ts` builds per-(event, state) convenience views (`parties`, `constituencies`, `candidates`, `party_totals`) over the canonical observations + dim Parquets so the documented preset schema keeps working with minimal SQL changes. NOTA rows are synthesised per-AC from `ac-nota-{votes,pct}` observations. Two presets adapted for DuckDB dialect (`MIN(a,b)` → `LEAST`, `MAX(a,b)` → `GREATEST`). `fmtCell` now handles BIGINT bigints. `lib/sql.ts` and `getDb` stay alive for the psephlab Compare/Psephlab routes (separate concern). | Fowler |
| 1.7 | **DONE 2026-05-18 (PR-M)**: Admin v0 brought forward into Phase 1 (option a, generalised). `backend/yen_gov/admin/inventory.py` rewritten family-agnostic — walks every `datasets/<family>/*.parquet`, classifies into `(family, kind ∈ {observations, dim, taxonomy, other})`, runs one DuckDB query per file for row count + indicator/entity/period/source distincts + year range. New `/api/inventory` response shape `{generated_at, stores[], indicators[]}`; the day energy / demography / fiscal / health land their own `observations.parquet`, they appear in the Inventory automatically with zero code change. `admin/src/routes/Inventory.svelte` rewritten as two tables (Stores + Indicators). **ECI Recon panel + `tools/eci_recon/` scanner retired entirely** — operator hand-loads upstream XLS/CSV through the ingest path (`sources/eci/categories.py`, `config/eci-pins.json`); the live-website scanner was dead weight under that workflow. Deleted: `backend/yen_gov/admin/eci_recon.py`, `admin/src/routes/EciRecon.svelte`, `tools/eci_recon/`, all EciRecon types and API methods in `admin/src/lib/api.ts`, the panels.spec.ts EciRecon block. Pytest `test_admin_inventory.py` rewritten with `tmp_path` fixture corpus + `YEN_GOV_REPO_ROOT` env override per CLAUDE.md §10 (no real-corpus walks). Resolves Q10. | Fowler |
| 1.8 | **SCOPE CORRECTION 2026-05-18 (PR-N revised).** Original "delete `datasets/_old/`" framing was a misread: the legacy JSON tree was never moved into `_old/` during the pivot, so `_old/` was an empty placeholder while the real legacy shards (per-AC `results/<ac>.json`, `parties.json`, `result.summary.json`, etc.) still sit interleaved with the new Parquet files under `datasets/elections/AcGen*/<state>/`. The empty `_old/` placeholder was removed in an earlier commit; the actual cleanup is broken out below into auditable per-target sub-rows. Each sub-row follows the same pattern: (1) confirm canonical Parquet supersedes; (2) `git grep` proves no live reader; (3) record legacy → canonical mapping in `docs/architecture/canonical-pivot-deletion-manifest.md`; (4) delete; (5) re-run frontend + backend tests + integrated-browser smoke. | Fowler |
| 1.8a | **DONE 2026-05-18 (PR-N revised)**: scope correction recorded. Reverted false "deletion complete" claims in `backend/yen_gov/AGENTS.md`, `frontend/src/AGENTS.md`, `CLAUDE.md` §10 anti-pattern. Added `datasets/<family>/` directory invariant + empty-parent-pruning rule + Parquet naming convention (`<family>_<role>.parquet` fact tables, `dim_*.parquet` kept, `taxonomy/` flat-name exception, `operator_state` moves to `_ops/`, SQL identifier decoupled from filename via manifest `table_name`) to `docs/architecture/data/canonical-store.md` §2 + §2a. Inserted this 1.8a–f breakdown. Extended `docs/architecture/canonical-pivot-deletion-manifest.md` with the per-family deletion plan + audit columns for end-of-pivot validation. | Fowler + Hans + Max + Gregor |
| 1.8a-bis | **DONE 2026-05-18 (PR-O-prereq)**: SQL-identifier decoupling shipped as a pure Tidy-First commit — zero files renamed, zero writers retired, zero legacy JSON deleted. `datasets/schemas/manifest.schema.json` bumped v1.0 → v1.1 (additive `table_name` + `kind` fields on `tables[].items`, full `x-changelog` entry); `backend/yen_gov/canonical/writer.py::_describe_parquet_table` populates both via new `_classify_kind(parquet_path, family)` helper (taxonomy → "taxonomy", `observations.parquet` → "observations", `dim_*` → "dim", else "other"); `frontend/src/lib/duckdb.ts` extends `ManifestTable` interface and extracts a pure `defaultViewName(table, table_id)` helper that prefers `table.table_name`, falling back to the last dotted segment for pre-v1.1 manifests; `backend/yen_gov/admin/inventory.py` gains `_load_manifest_index(datasets_dir)` and an optional `manifest_index` arg on `_classify`, so the writer is now the authority and string-matching is the fallback. `datasets/manifest.json` regenerated via new `tools/regenerate_manifest.py`; every entry now carries `$schema_version: "1.1"`, `table_name`, and `kind`. Tests: extended `test_manifest_regenerates_with_correct_table_entries` + `test_dim_tables_appear_in_manifest` with `table_name` / `kind` assertions; added `test_manifest_schema_version_is_current` (sources through `schema_registry.schema_version`) + `test_manifest_kind_for_taxonomy_table`; extended `frontend/src/lib/duckdb.test.ts` SAMPLE_MANIFEST + new `describe("registerTable view name resolution")` block testing the pure `defaultViewName` helper (renamed + not-renamed cases). **Deviation from declared scope**: `frontend/src/lib/canonical/types.ts` `SUPPORTED_SCHEMA_VERSIONS["manifest.schema.json"]` widened from `["1.0"]` → `["1.0", "1.1"]` — required by /memories/lessons.md 2026-05-16 "schema enum extension MUST update paired TS union in the same Tier-A commit" and by the file's own inline comment; without it the parallel `canonical/manifest.ts` reader (not yet in production, but tested) would reject the regenerated manifest. SUPERSEDES the previous PENDING row. PR-O (row 1.8b) is now unblocked. | Gregor + Fowler |
| 1.8b-i | **DONE 2026-05-18 (PR-O.1 — structural-only split per Fowler tidy-first; addresses 1.8b sub-step 5 plus the view-name sweep it implies)**: `git mv datasets/elections/observations.parquet datasets/elections/election_results.parquet`; backend writer gains `FAMILY_FACT_TABLE_STEM = {"elections": "election_results"}` + `_fact_table_stem(family)` helper (returns `"observations"` default for any other family) wired through `write_batch` and `_regenerate_manifest`; `_regenerate_manifest` rewritten to iterate `datasets_root.iterdir()` and look up the per-family stem (no more `glob("*/observations.parquet")`); `backend/yen_gov/admin/inventory.py` drops the `observations.parquet` filename fallback (manifest is now sole authority for fact-table kind, per-family stems break filename matching). `datasets/manifest.json` regenerated: single entry changed (`elections.observations` → `elections.election_results` table_id + table_name + path); other 5 entries unchanged. Frontend sweep — every `registerTable("elections.observations")` → `("elections.election_results")` and every `FROM observations` / `LEFT JOIN observations` → `FROM election_results` / `LEFT JOIN election_results` across `routes/DuckDbHarness.svelte` (also dropped the `viewName: "observations"` override), `lib/view-models/{constituency,state-overview,parties-palette,india-leading-parties,election-seats-trend}.ts`, `lib/explore/duckdb-views.ts`. Test fixtures updated in `frontend/src/lib/duckdb.test.ts` (SAMPLE_MANIFEST + every assertion), `lib/canonical/{manifest,failure-state}.test.ts`, all 5 view-model `.test.ts` files (registered-tables expectation arrays preserve sorted order — `election_results` < `observations` alphabetically). Cosmetic comment refs swept in `lib/canonical/types.ts`, `lib/duckdb.ts`. Backend tests: added `test_elections_family_uses_election_results_stem` pinning per-family stem behaviour; updated existing dim_candidates JOIN test path; rewrote `test_admin_inventory.py::fixture_corpus` to write `election_results.parquet` + minimal manifest with 3 entries so manifest-driven classifier resolves authoritatively. Admin sweep: `admin/e2e/panels.spec.ts` + `admin/src/lib/api.test.ts` fixture paths; `admin/src/routes/Inventory.svelte` + `admin/src/lib/api.ts` docstrings/copy switched to fact-table phrasing. Docs sweep: `docs/architecture/data/canonical-store.md` (table_id field example, JSON example block, per-event-batching prose), `docs/architecture/frontend/data-loading.md` (4 spots), `docs/architecture/canonical-pivot-deletion-manifest.md`, schema description fields (`dim-candidates.schema.json`, `manifest.schema.json` ×2). Backend docstrings: `cli.py` + `pipeline/canonical_eci_backfill.py`. **Zero behavioural change**: no writer retired, no legacy JSON deleted, no manifest.deprecations[] schema extension, no datasets/CHANGELOG.md, no test_no_legacy_json_emit.py — those land in PR-O.2 (next), keeping each commit reviewable. Tests pass before AND after this commit, proving it is a pure rename. | Fowler |
| 1.8b-min | **DONE 2026-05-19 (PR-O.2-minimal — Fowler-tidy split of original 1.8b sub-steps; isolates the deprecation surface + test-fixture cleanup from the writer retirement that couples to sqlite/csv emitters)**: ships **sub-steps (2), (3), (4), (6) only** of the original 1.8b sub-step list; writer retirement (sub-step 1) + no-legacy-json-emit test (sub-step 7) move to the new row 1.8b-writers (PR-O.3) which lands AFTER this PR merges + one clean Pages run. **Coverage reroute (sub-step 2)**: `backend/yen_gov/coverage.py` replaces the 17-line on-disk JSON walk under `datasets/elections/<event>/<state>/{results/,parties.json,result.summary.json}` with a single `_election_slices_from_canonical(root)` DuckDB query against `election_results.parquet`. New `ELECTION_RESULTS_PARQUET_REL` constant; query uses `regexp_extract(entity_id, '^IN-([SU][0-9]{2})', 1)` to derive `state_code` and a `CASE WHEN regexp_matches(...)` ladder to classify `ac` / `state_rollup` / `party` rows. Test fixtures in `backend/tests/test_coverage.py` switch from JSON-shard seeding to a new `_seed_election_parquet(root, slices)` helper that builds the canonical Parquet via DuckDB `CREATE TABLE staging → INSERT → COPY TO parquet`; the three affected tests (`test_coverage_reconciles_catalogue_and_disk`, `test_coverage_flags_undeclared_and_pending`, `test_render_includes_indicators_and_state_first`) pass against the canonical input. **Adapter-elections fixture refactor (sub-step 3)**: `frontend/src/lib/charts/stacked-trend/adapter-elections.test.ts` drops `readFileSync` / `resolve` / `loadSummary` helpers and uses four inline `ResultSummaryDoc` constants (real Assam Apr 2016 BJP=60/INC=26/AGP=14/AIUDF=13/BOPF=12/IND=1 totals; placeholder Apr 2021 / May 2026; single-party Goa for the mixed-state assertion). 11 tests pass. **paths.test.ts:23 example (sub-step 4)**: legacy `${DATA_BASE}/elections/.../result.summary.json` example swapped for canonical `${DATA_BASE}/elections/election_results.parquet` with a canonical-pivot comment. **Deprecation surface (sub-step 6)**: `datasets/schemas/manifest.schema.json` bumped v1.1 → v1.2 (additive `deprecations[]` array on the root object; full `x-changelog` entry dated 2026-05-19); `backend/yen_gov/canonical/writer.py` gains `_DEPRECATIONS: list[dict[str, str]]` module-level append-only ledger seeded with `{old_path: elections/observations.parquet, new_path: elections/election_results.parquet, deprecated_at: 2026-05-18}` and stamps it into every regenerated manifest under the new field. `frontend/src/lib/canonical/types.ts` widens `SUPPORTED_SCHEMA_VERSIONS["manifest.schema.json"]` → `["1.0", "1.1", "1.2"]` (paired TS union per /memories/lessons.md 2026-05-16 "schema enum extension MUST update paired TS union in same Tier-A commit") AND adds `ManifestDeprecation` interface + optional `deprecations?: ManifestDeprecation[]` on `Manifest` (so the parallel canonical/manifest.ts reader is shape-aware even though it never consults the field at runtime). `frontend/src/lib/duckdb.ts` gains a one-shot `warnIfLegacyPath(url)` guard with `LEGACY_PARQUET_PATTERNS: [{marker: "elections/observations.parquet", successor: "elections/election_results.parquet"}]` + `warnedLegacyMarkers: Set<string>` latch that fires a single `console.warn` per page-load when the loader sees a legacy marker in any registered URL (`__resetForTests` clears the latch). `datasets/CHANGELOG.md` created (new file) — first entry dated 2026-05-19 documents the PR-O.1 rename + PR-O.2-minimal deprecation surface + migration path for direct-fetch consumers and archived embeds; format section pins newest-on-top convention. `datasets/manifest.json` regenerated via the pre-existing `tools/regenerate_manifest.py`; now carries `$schema_version: "1.2"` + the single `deprecations[]` entry. **Tier-A test guarding the new contract**: `backend/tests/test_canonical_writer.py::test_manifest_carries_known_deprecations` seeds a fixture corpus, calls `write_batch`, asserts the elections rename entry appears in the regenerated manifest's `deprecations[]`; `test_manifest_schema_version_is_current` literal bumped to `"1.2"` to match the live `x-version`. **Tests green**: backend `pytest -q` 713 passed; frontend `npx vitest run` 23,970 passed (incl. 23,214-row datasets contract test which validates the schema-version envelope on the regenerated manifest). **§13 UI smoke**: home (`/`) renders India-leading-party choropleth + 60+ fiscal indicator options in theme picker; TN state hub (`/s/tamil-nadu`) renders scope picker + 8 topic links; TN elections topic (`/s/tamil-nadu/t/elections`) renders breadcrumb + ADR-0022 framing. No `observations.parquet` warn fires (manifest no longer references the legacy path). One pre-existing 404 on `/` predates this change and is unrelated. **Zero writer retirement, zero file deletion**: all 8 callers of legacy emit paths (`pipeline/run.py:105` write_artifact calls, `cli.py:564 + 825`, `pipeline/people_ingest.py:38 + 213`, `emit/sqlite.py:72-76` reads, `emit/csv_bundle.py:66` reads, `pipeline/canonical_eci_backfill.py` reads) untouched; row 1.8b-writers owns that work. The 7,254 per-AC JSON shards + 41 sqlite files stay on disk. | Fowler |
| 1.8b-writers-a | **DONE 2026-05-19 (PR-O.3a — Fowler tidy-first: structural emitter refactor, ZERO writer retirement; isolates the in-memory API surface from the behavioural retirement that couples to `pipeline/people_ingest.compare_winner_votes`)**: split out of the original 1.8b-writers row when mid-PR recon discovered that the retirement target (`pipeline/run.py:76,105,116`) has THREE on-disk JSON consumers, not the two the row called out — `pipeline/people_ingest.compare_winner_votes` at line 106 reads per-AC JSONs as its discrepancy-gate input, with a graceful "file not found" fallback that degrades to silent skip. Retiring the writers + refactoring people_ingest's gate + refactoring canonical_eci_backfill + adding the no-emit regression test + rerouting the integrity-test trap in one PR would mix ~15 files of structural and behavioural change, violating Fowler two-hat. **What PR-O.3a ships**: emit/sqlite.py gains `emit_state_sqlite_from_data(*, parties_doc, constituencies, output_path)` as the primary API + keeps `emit_state_sqlite(*, state_dir)` as a thin disk-wrapper that loads JSONs and delegates. emit/csv_bundle.py same pattern (`emit_state_csv_from_data` primary + `emit_state_csv` wrapper). cli.py::run + cli.py::eci_statreport_emit_local (the only two call sites — `eci_statreport_emit` does NOT emit sqlite/csv, recon confirmed) thread `RunResult.parties.body_payload()` + `[cr.body_payload() for cr in RunResult.constituencies]` directly into the in-memory emitters, eliminating the disk write-then-read cycle. `eci_statreport_emit_local` hoists its `snapshot: PartiesSnapshot | None` variable so the zero-resolved-parties edge case (no parties.json on disk) is now an explicit `parties_doc = {"parties": []}` fallback instead of a latent crash. **Tests refactored**: test_emit_sqlite.py + test_emit_csv_bundle.py rewritten to use a new private fixture builder `backend/tests/_emit_fixtures.py` (3 ACs × 5 cands + NOTA + winner; uses real Pydantic models → body_payload() so dict shape matches production exactly) instead of walking `datasets/elections/AcGenMay2026/S22/` (CLAUDE.md §10 anti-pattern). Each emit test file gains a `test_disk_wrapper_matches_in_memory` test that materialises the fixture to tmp_path JSONs, emits via both paths, asserts byte-equal output — the Tier-A byte-identity proof that guards the refactor against semantic drift. **Zero behavioural change**: the 3 `write_artifact` calls in `pipeline/run.py` untouched, all per-AC + summary + parties JSONs still emitted on every pipeline run, `pipeline/people_ingest.py` + `pipeline/canonical_eci_backfill.py` untouched, no schema bumps, no manifest changes, no test_no_legacy_json_emit.py yet. Backend pytest 717 green, frontend vitest 23970 green, §13 UI smoke on Psephlab (234 seats, 118 majority, 48,715,766 votes — identical to pre-refactor) + TN hub + Explore (10 rows, 437ms sql.js query) all green. PR-O.3b owns the actual writer retirement + downstream refactors. | Fowler |
| 1.8b-writers-b-pre | **DONE 2026-05-19 (PR-O.3b-pre — Fowler tidy-first AGAIN: structural extraction of in-memory backfill API, ZERO behavioural change)**: split out of 1.8b-writers-b when scope recon showed the row coupled 3 writer retirements + a `people_ingest` reroute + a `canonical_eci_backfill` rewrite + a new regression test + an integrity-test reroute into ~15 files of mixed structural+behavioural change. Repeating the PR-O.3a tidy-first move at the next layer: extract the in-memory primary API first, prove byte-identity vs the disk path, ship; THEN do the actual writer retirement + caller switch in PR-O.3b-main. **What PR-O.3b-pre ships**: `backend/yen_gov/pipeline/canonical_eci_backfill.py` gains `build_slice_envelope(*, constituencies, state_code, period, party_lookup) -> tuple[rows, sources_by_id, unresolved, candidate_dims, ac_dims]` as the in-memory primary API (extracted from `_process_slice` orchestration body — the `_LenientPartyLookup` proxy, the per-AC adapter dispatch via `observations_from_constituency` + `dim_rows_from_constituency` + `_summary_for_result`, and the closing `state_rollup_observations(summaries)`). `_process_slice` reduced to a thin disk-wrapper: globs `*.json`, loads each into `ConstituencyResult` (skip-on-read-error with log warning preserves prior fault tolerance), delegates to `build_slice_envelope`, prepends `ac_count = len(ac_files)` to return the historical 6-tuple `(rows, sources, ac_count, unresolved, candidate_dims, ac_dims)` so `backfill_elections` caller is untouched. Module docstring updated with a Public API section documenting the two seams. **Test fixtures extended**: `backend/tests/_emit_fixtures.py` gains private `_constituency_model(...)` (builds the Pydantic `ConstituencyResult` body once) + public `constituency_models() -> list[ConstituencyResult]` returning the 3-AC slice as full models (the existing `_constituency()` becomes a thin `body_payload()` wrapper around `_constituency_model()` preserving PR-O.3a dict-API for sqlite/csv emit tests). **New test**: `backend/tests/test_canonical_eci_backfill.py` (3 tests) — `test_build_slice_envelope_happy_path` (3 ACs in, 3 sources, 15 candidate dims, 3 AC dims, zero unresolved); `test_build_slice_envelope_empty_constituencies` (empty in → empty out); `test_disk_wrapper_matches_in_memory` is the Tier-A byte-identity proof — materialises `constituency_models()` to `tmp_path/results/<n>.json` via merged `body_payload()` + `sources_payload().to_dict()`, runs `_process_slice` against the dir, runs `build_slice_envelope` directly on the in-memory list, asserts both paths produce identical `rows`, `sources`, `unresolved`, `candidate_dims`, `ac_dims` (only `ac_count` differs by construction). Self-contained `parties.json` seeded into `tmp_path/taxonomy/` per CLAUDE.md §10 (no real-corpus walk). **Zero behavioural change**: NO `write_artifact` retired, NO caller switched, NO schema bumped, NO contract surface changed, NO frontend touched. `pipeline/run.py` still writes the 3 per-AC + summary + parties JSONs on every run; `people_ingest.compare_winner_votes` still reads them; the existing `backfill_elections` driver still works identically. Backend pytest 720 green (717 + 3 new), `git status --porcelain` clean before commit. **§13 N/A**: no UI surface touched — pure backend module extraction + new test file + this TODO row. PR-O.3b-main owns the actual writer retirement. | Fowler |
| 1.8b-writers-b-main | **DONE 2026-05-19 (PR-O.3b-main — behavioural writer retirement, Fowler behavioural-hat)**: legacy JSON writers retired from the live-fetch pipeline; canonical Parquet is the single source of truth for election rows. **Shipped**: (1) `backend/yen_gov/pipeline/run.py` — the 3 `write_artifact` calls (per-AC `results/<n>.json`, `result.summary.json`, `parties.json`) gone; new private `_write_canonical_slice()` helper composes the slice via `build_slice_envelope` → `BatchEnvelope` → `write_batch`. `RunPaths` simplified to a single field `canonical_parquet: Path`. `run_state_slice` signature now takes `datasets_root: Path` instead of `(output_dir, schema_dir)`. (2) `backend/yen_gov/pipeline/people_ingest.compare_winner_votes` — disk JSON walk replaced by a single DuckDB query against `datasets/elections/election_results.parquet` (new private `_load_canonical_ac_facts` helper); joins `ac-winner-candidate-id` → `candidate-votes-polled` for winner votes + filters `ac-votes-polled` for AC totals; preserves the graceful "no comparison data → skip delta math" fallback when the canonical Parquet is missing or has no rows for a (state, period_label) slice. (3) `backend/yen_gov/cli.py` — adapter for the new `run_state_slice` signature; `output_dir.mkdir(parents=True, exist_ok=True)` moved up since the pipeline no longer creates the directory. (4) `backend/tests/test_no_legacy_json_emit.py` — Holy Law #10 regression guard: grep-style source scan of `pipeline/run.py` asserting zero `write_artifact(` calls AND zero `write_artifact` references (no import either). (5) `backend/tests/test_people_ingest.py` — `_seed_corpus` now seeds canonical Parquet (3-row trio: `ac-winner-candidate-id` + `candidate-votes-polled` + `ac-votes-polled`) via a new `_seed_canonical_winner` helper using duckdb directly; the legacy per-AC JSON seed is gone. (6) `backend/tests/test_datasets_integrity.py` — split `test_election_events_default_uniqueness_and_data_status_alignment` into `test_election_events_default_uniqueness` (catalogue-only, kept); the data_status ↔ `result.summary.json` alignment assertions are deleted (§10 violation — walked real corpus from a pytest test — and redundant with the frontend e2e suite's 404 detection). **Out of scope here** (kept for follow-ups): `backend/yen_gov/pipeline/canonical_eci_backfill.py` keeps reading the legacy JSON corpus (standalone one-shot importer for historical events; the `_process_slice` disk-read path is the right shape for that tool) until PR-O.4 deletes the JSONs; `backend/yen_gov/cli.py::eci_statreport_emit_local` keeps its `write_artifact` calls for hand-import provenance. Full backend suite: 722 passed in 74.56s. Frontend suite: 23970 passed. §13 UI smoke: `/s/tamil-nadu/explore` ran 10-row canonical Parquet query in 480.9ms with real winners (TIRUPPATTUR, KANNIYAKUMARI). | Fowler + Hans |
| 1.8b-writers-b | **SUPERSEDED 2026-05-19** by the further -pre/-main split: 1.8b-writers-b-pre (PR-O.3b-pre, `build_slice_envelope` extraction + byte-identity tests — DONE), 1.8b-writers-b-main (PR-O.3b-main, actual writer retirement + people_ingest reroute + integrity-test reroute + no-emit regression test — PENDING). Same Fowler two-hat reasoning that produced the -a/-b split: bundling structural extraction + behavioural retirement + downstream reroute into one PR is ~15 mixed files; separating them keeps each PR's blast radius honest. Keep this row as the historical pointer; do not add new sub-steps here. | (closed) |
| 1.8b-writers | **SUPERSEDED 2026-05-19** by the explicit -a/-b split: 1.8b-writers-a (PR-O.3a, emitter structural refactor — DONE), 1.8b-writers-b (PR-O.3b, writer retirement + people_ingest reroute + backfill rewrite + no-emit test — SUPERSEDED by -pre/-main further split). The original single-row scope mixed structural emitter changes (cheap to land) with behavioural writer retirement that couples to a third consumer (`people_ingest`) the row failed to identify; honest mid-PR re-scoping per Fowler two-hat rule. Keep this row as the historical pointer; do not add new sub-steps here. | (closed) |
| 1.8b | **SUPERSEDED 2026-05-19** by the explicit per-PR split: 1.8b-i (PR-O.1, structural rename — DONE), 1.8b-min (PR-O.2-minimal, deprecation surface + test refactor — DONE), 1.8b-writers-a (PR-O.3a, emitter structural refactor — DONE), 1.8b-writers-b-pre (PR-O.3b-pre, in-memory backfill API extraction + byte-identity tests — DONE), 1.8b-writers-b-main (PR-O.3b-main, writer retirement + people_ingest reroute + integrity-test reroute + no-emit test — PENDING), 1.8b-ii (PR-O.4, file deletion — PENDING). Keep this row as the historical pointer; do not add new sub-steps here. | (closed) |
| 1.8b-ii | **DONE 2026-05-19 (PR-O.4 — Fowler structural-hat: file deletion, ZERO behavioural change)**: 110 legacy per-state JSON shards (`parties.json` + `result.summary.json` across 55 `AcGen*/<state>/`) deleted via `git rm`; canonical Parquet (`election_results.parquet`, `dim_parties.parquet`, `dim_party_alliances.parquet`) is the single source of truth. **Pre-deletion gate honoured**: PR-O.3b-main writer-retirement merged as `2267a971` on `main`; `backend/tests/test_no_legacy_json_emit.py` (2 source-scan tests asserting zero `write_artifact(` calls in `pipeline/run.py`) blocks re-introduction — the "one clean pipeline run" gate the row originally called for is REDUNDANT with the static guard already in place per recon verdict (no live readers anywhere in `frontend/src` / `admin/src` / `backend/yen_gov/pipeline/`; only stale historical comments and the canonical-Parquet fetch in `data.ts`/`sql.ts`). **`_inventory.json` clarification**: per-state `_inventory.json` files NEVER existed on disk (TODO row originally listed them — the only `_inventory.json` under `datasets/elections/` is the root file `datasets/elections/_inventory.json` which is owned by `backend/yen_gov/pipeline/people_ingest.py` as an ingest-tracking control file and is intentionally preserved). **Empty-parent prune**: PowerShell idempotent loop (Windows equivalent of `find -type d -empty -delete`) — the 27 `AcGen*/` event dirs and their state subdirs survive because they still carry the per-AC `results/<ac>.json` shards (row 1.8c / PR-P scope), `results.csv` (researcher Tier-3 download), and `results.sqlite` (Psephlab Compare backend, row 1.8e / PR-R blocker). **Deploy smoke step rerouted**: `.github/workflows/deploy-site.yml` previously fetched `_site/data/elections/AcGenMay2026/S22/result.summary.json` at build-time AND curled the URL post-deploy with `assert d['state']=='S22'` — both rerouted to `_site/data/elections/election_results.parquet` with PAR1-magic-header assertion (defends the same Pages MIME + Range-request contract that DuckDB-WASM depends on). `docs/architecture/deployment.md` Pages-artifact-shape tree + smoke-step description + Phase-0.7 verification curl examples all updated. **Tangential doc refs reframed**: `docs/architecture/backend/emit-csv.md` + `emit-sqlite.md` updated — both now point at per-AC `results/<ac>.json` (row 1.8c) as their "next-to" sibling rather than the deleted `result.summary.json`. Decision-#1 wording ("Mirrors the JSON layout exactly") rewritten as "Co-located with the per-AC `results/<ac>.json` shards" (the legacy JSON they actually mirror — both emitters read the same validated per-AC records via `loadConstituencyResult`). **Manifest entry**: `docs/architecture/canonical-pivot-deletion-manifest.md` §6a — original 1.8b row marked `superseded by 1.8b-ii`; new 1.8b-ii row added with target paths, replacement, gate description, status `completed 2026-05-19`. **Known follow-up (NOT in this PR)**: `backend/yen_gov/cli.py` operator-only commands `eci-statreport-emit` (L369), `eci-statreport-emit-local` (L715), `canonical-backfill-eci` (L1396) call `load_eci_party_registry()` which walks `datasets/elections/*/*/parties.json` — these commands will return empty registries after this PR. They are operator-only (zero CI/workflow invocation — verified via `grep_search` over `.github/workflows/**/*.yml` returning no matches; only invoked through `tools/ingest_ephemeral_ae.py` dev tooling and `admin/src/lib/api.ts` admin GUI), so CI stays green. Documented in PR body + deletion manifest as acceptable deferred follow-up for PR-P (row 1.8c) which will need a canonical-Parquet-backed party registry anyway. **Gates verified**: backend `pytest -q` green (722 passed, unchanged from PR-O.3b-main baseline — PR only deletes data files, no code change); frontend `npm test` green (23970 passed, unchanged baseline — no frontend code reads these files); §13 UI smoke `/s/tamil-nadu/explore` runs canonical SQL successfully against `election_results.parquet`; `/s/tamil-nadu/t/elections` renders cleanly. **PR-O.4 done; next is row 1.8c (PR-P) per-AC shard deletion (~7,254 files), bigger blast radius — needs its own recon cycle.** | Fowler |
| 1.8c | **DONE (PR-P, 2026-05-19, commit pending PR merge)**: deleted 7,168 per-AC election shards `datasets/elections/<event>/<state>/results/<ac>.json` across all 55 events. **Replacement live**: `loadConstituencyResult` (PR-E, `frontend/src/lib/view-models/constituency.ts`) reads `election_results.parquet` + `dim_candidates.parquet` + `dim_acs.parquet` + `dim_parties.parquet` via DuckDB-WASM and reconstructs the legacy `ConstituencyResult` shape (including `others` bucket from `ac-others-{votes,pct}` observations). **Recon verdict (Explore subagent, pre-deletion)**: zero live readers in `frontend/src/` (only `loadConstituencyResult` and it is Parquet-only), zero in `admin/src/`, zero in `backend/yen_gov/pipeline/` (PR-O.3b retired the writer; static guard `test_no_legacy_json_emit.py` blocks reintroduction); operator-only CLI commands (`canonical-backfill-eci`, `eci-statreport-emit-local`) read the legacy JSONs as back-compat replay path only — zero CI/workflow invocation, acceptable. **`results.csv` + `results.sqlite` siblings preserved** (row 1.8e / PR-R scope) — `csv_bundle.py` and `sqlite.py` use the in-memory `emit_state_*_from_data()` primary API per PR-O.3a, NOT the disk JSONs; the disk-walking wrappers (`emit_state_csv(state_dir=...)`) are preserved only for ad-hoc replays against legacy checkouts. **E2E gate satisfied**: extended `frontend/e2e/golden-path.spec.ts` with 2 new structural tests for KL AC#1 (MANJESHWAR, `/s/kerala/ac/1-manjeshwar`) and WB AC#1 (MEKLIGANJ (SC), `/s/west-bengal/ac/1-mekliganj-sc`) running on both `chromium` and `mobile-pixel-5` projects (4 new test runs total). The TN + KL + WB triad exercises 3 state codes, 2 AC-numbering families (S22 vs S11/S25), and 1 reservation-suffix slug (`-sc`) — proves the canonical loader fans out across states without TN-specific hard-coding. All 18 spec runs (9 tests x 2 projects) green BOTH pre-deletion and post-deletion, proving the canonical Parquet path is the sole code path exercised. **Schema retained**: `datasets/schemas/result.constituency.schema.json` kept — it remains a contract definition referenced by operator-only CLI emit commands + reference docs; deletion is out of scope. **Doc updates**: `docs/architecture/backend/emit-csv.md` + `emit-sqlite.md` resolved the "row 1.8c / PR-P scope" forward references — both now reflect that the per-AC JSONs no longer exist on disk and the emitters' primary API consumes in-memory `ConstituencyResult` lists from the canonical pipeline. `docs/architecture/canonical-pivot-deletion-manifest.md` §6a row 1.8c marked `completed 2026-05-19`. **Empty `results/` dirs auto-pruned** by `git rm` on Windows (verified post-rm: zero `results/` dirs remain). **Gates verified**: backend `pytest -q` green, frontend `npm test` green (assertion count drops by ~14,000+ as `datasets-conform.test.ts` counts per-artifact assertions), frontend `npm run test:e2e` 18/18 green. **§13 UI smoke**: both new KL + WB AC routes loaded cleanly with no console errors, candidate tables populated, ECI provenance links surfaced. **Next pending row is 1.8d (PR-Q)**: delete `datasets/events/in/eci/` + taxonomy sidecars. Different family, separate recon cycle. | Fowler |
| 1.8d | **PARTIALLY DONE (PR-Q, 2026-05-19) — events/in/eci sweep ONLY; siblings DEFERRED**: deleted 27 `datasets/events/in/eci/<event>/election.json` files across 27 event dirs (all 2016–2026 AC cohorts). The JSONs were a third redundant projection of cohort metadata — the load-bearing source is the `EVENTS` Python registry in `backend/yen_gov/sources/eci/events.py`, and the citizen-facing catalogue is `datasets/reference/in/election-events.json` (cross-validated by `test_election_events_catalogue_matches_backend_registry`). The JSON files added zero information either of those sources lacked. **Replacement gates**: (a) `test_election_events_catalogue_matches_backend_registry` already enforced the load-bearing contract (EVENTS registry == citizen catalogue); (b) the canonical adapter (`backend/yen_gov/canonical/adapters/`) writes `dim_acs` keyed on `(event_id, state)` directly from EVENTS, so any mis-declared state is rejected at write time. **Recon caveats** (Explore subagent + verification): the recon's optimistic "GO" verdict for items 2/3/4 turned out to be partly wrong — `datasets/taxonomy/` does NOT yet carry the parquet siblings the TODO assumed (`delimitation_lineage.parquet`, `facet-axes.parquet`, `operator_state.parquet`); only `sources.parquet` exists. Items 2/3/4 explicitly **DEFERRED to PR-Q.2** (no PR opened yet — see DEFER notes below). Also retired: `tools/register_2016_2023_event_metadata.py` (one-shot migration tool; its work is the 27 files now deleted) and `backend/tests/test_datasets_integrity.py::test_emitted_states_are_declared_in_event_metadata` (§10 corpus walker; both walks `ELECTIONS_ROOT.iterdir()` and `EVENTS_IN_ECI` ran on every commit; contract surface deleted). **Prose**: `backend/yen_gov/coverage.py:599` instruction list for adding a new state collapsed from 3 steps to 2 (dropped "(b) writing the cohort metadata at `datasets/events/in/eci/...`"). **Gates verified**: backend `pytest -q` green (716 passed — one test retired), frontend `npm test` green (assertion count drops by ~27 as `datasets-conform.test.ts` stops enumerating the deleted election.json files), frontend `npm run test:e2e` 18/18 green. **§13 UI smoke deferred** — pure backend/test deletion, no frontend code-path change. **Items 2/3/4 DEFERRED to PR-Q.2** (rationale below — opening a separate PR when ready): <br/><br/>· `datasets/taxonomy/delimitation_lineage.json` — DEFERRED. File is a 125-byte placeholder (`{"sources":[], "lineage":[]}`). Zero live readers (verified via `grep_search` for `delimitation_lineage\.json` across `**/*.{py,ts,svelte,js,mjs}` — no matches). Schema kept as typed grammar. Defer rationale: no parquet replacement exists, so the deletion saves 125 bytes and gains nothing structural; safer to delete together with the parquet creation work to avoid an empty interval where the schema has no on-disk example.<br/><br/>· `datasets/taxonomy/facet-axes.json` — DEFERRED. File has substantive hand-authored vocabulary (`fuel_type`, `sector`, `head_of_account`, `gender`, `residence` axes with allowed value lists). Zero live readers in code (verified via `grep_search`) but the CONTENT is the D31 controlled vocabulary referenced by `indicator-catalogue` schema description prose. Defer rationale: the parquet replacement (`facet-axes.parquet`) doesn't exist yet and the hand-authored vocab would be lost on deletion. This file should move to a parquet-emit + JSON-retirement workflow as one atomic PR-Q.2, not get deleted in a vacuum.<br/><br/>· `datasets/taxonomy/operator_state.parquet` → `datasets/_ops/operator_state.parquet` MOVE — DEFERRED. File does not exist anywhere on disk. The move is a forward-pointer for when D18 operator-state edit UI ships (Phase 5). No-op until that work creates the file at the original location. **PR-Q.2 residual closure**: items 2/3/4 closed by row 1.8d-ii below. **Next pending row is 1.8e (PR-R)**: per-state `results.sqlite` deletion — explicitly blocked on Psephlab Compare backend migration to DuckDB-WASM views (different sub-system, large UI work). Or jump to row 1.10 (PR-T) Hans/Max/Jony proto-ontology if Phase-1 elections-pivot deletion sweep is paused for citizen-visible work. | Fowler |
| 1.8d-ii | **SHIPPED 2026-05-19 on branch `feat/canonical-pivot-1.8d-ii-facet-axes-parquet` (PR-Q.2)** — 5 commits: `37c8d799` plan amendment (~900 words across §§A–H below) + `c9bc6b0a` `backend/yen_gov/canonical/facet_axes_seed.py` (340 LOC) + 16 Tier-A tests at `backend/tests/test_facet_axes_seed.py` (tmp_path fixtures only per CLAUDE.md §10; module-import + uniqueness + Pydantic-rejection + byte-determinism + round-trip + 13-axis snapshot) + `0ab103bb` writer wiring (`_emit_facet_axes` near `_emit_sources` in `backend/yen_gov/canonical/writer.py`; `"facet-axes"` line removed from `_taxonomy_schema_file()` with explanatory comment) + `emit-taxonomy` CLI command at `backend/yen_gov/cli.py` + `484615e9` generated `datasets/taxonomy/facet-axes.parquet` (76 rows = 13 axes × ~6 values, 8090 bytes, sorted-stable via DuckDB `COPY (SELECT ... ORDER BY)`) + `4177702e` 4-file delete (`facet-axes.json`, `facet-axes.schema.json`, `delimitation_lineage.json`, `delimitation-lineage.schema.json`) + 2-file frontend scrub (`PER_ROW_PROVENANCE_SCHEMAS` Set in `frontend/src/contracts/datasets-conform.test.ts`; `SUPPORTED_SCHEMA_VERSIONS` map in `frontend/src/lib/canonical/types.ts` — both entries removed and inline comment added) + 3-file doc update (`docs/architecture/data/canonical-store.md` §2 tree + §3a delimitation reframe + §6 indicator-catalogue row + §8 D31 rewrite + §8.2 procedure rewrite + NEW §8.3 "Hand-authored taxonomy — the Python-compiles-to-parquet pattern" canonical doctrine section; `docs/architecture/canonical-pivot-deletion-manifest.md` §3c list scrub + §6a 1.8d row note + new 1.8d-ii row + §6b taxonomy entry; `docs/architecture/canonical-pivot-migration-ledger.md` §5 Q1 marked REGISTERED). **Gates verified**: backend `pytest -q` 733 passed (+16 new seed tests); frontend `npm test` 9364 passed | 3 skipped (54 files, 20.87s, including 8600 contract assertions). Net: +47 / −369 LOC on the final commit; net-negative across the chain (Pydantic literal replaces 187-line JSON + 79-line schema). §13 UI-smoke not required (no runtime frontend code path changed). Establishes the canonical Python-compiles-to-parquet pattern (canonical-store.md §8.3) for any future hand-authored controlled vocabulary; `entities` / `indicators` / `parties` will follow the same pattern in Phase 2/3 as their content evolves. Delimitation-lineage placeholder retired pending real authoring (will reintroduce via `delimitation_lineage_seed.py` following the same pattern). **ORIGINAL DESIGN RECORD** (research / persona debate / OWID tiebreaker / migration cost / implementation plan / risks; ~900 words across §§A–H):<br/><br/>**§A. Research findings (2026-05-19)**: (1) Established repo state pre-PR — only `sources.parquet` is currently parquet (generated from adapter envelopes via `_emit_sources`); `entities.json` / `indicators.json` / `parties.json` / `facet-axes.json` remain hand-authored JSON. These four JSON files are part of the canonical-pivot disease, not a precedent. (2) `facet-axes` content surveyed: 13 axes × ~60 enumerated values (`fuel_type`, `sector`, `head_of_account`, `transfer_type`, `gender`, `residence`, `prices_basis`, `methodology_version`, `category`, `crime_category`, `cpi_category`, `loss_type`, `allocation_basis`). NO upstream source — editorial controlled vocabulary the project itself owns. Citizen-facing labels live here (`"Centrally sponsored schemes"`, `"AT&C loss"`). Zero live readers today; future readers are `writer.py` validator + frontend DuckDB-WASM facet pickers once Phase 2 Energy ships. (3) `delimitation_lineage.json` is a 125-byte placeholder (`{"sources":[], "lineage":[]}`) with zero readers — deletes cleanly in this PR. (4) `operator_state.parquet` move is no-op until Phase 5 admin UI.<br/><br/>**§B. Persona debate (2026-05-19)** convened on the architectural question: "Where does the hand-authored controlled vocabulary live, given user has rejected JSON-alongside-parquet, asks for frontend simplicity, and wants Phase 2/3 hand-authoring friction to go DOWN?" Five positions on the table: D=Python module compiles to parquet; A=adapter envelope (one-shot per axis); S=SQL seed file; Y=YAML/TOML.<br/><br/>· **Gregor — Pick A.** "Write-seam unification — don't add a second seam alongside `writer.py` UPSERT pipe; everything that becomes a parquet should go through one envelope contract."<br/>· **Fowler — Pick D.** "Smallest reversible step. Adapter envelope is speculative generality for one editorial seed. Pydantic model literal in a `.py` file ships ~150 lines and deletes 234 lines of JSON + the whole schema file. Net-negative LOC, reversible in one revert."<br/>· **Hans — Pick Y.** "Editorial governance contract. A non-coder FC economist must be able to PR-review the controlled vocabulary without learning Python; YAML is the read-aloud-at-a-meeting format."<br/>· **Max (initial) — Pick Y.** "Claimed OWID precedent — they use YAML for indicator metadata."<br/>· **Jony — Pick D.** "Single-line label-diff edits (`label: 'Coal'` → `label: 'Coal-fired'`) are type-checked against the enum at module-import time. YAML loses that guard."<br/><br/>**§C. OWID precedent verification (§0a tiebreaker)**: OWID's `etl` repo has TWO patterns split by content type. Per-dataset indicator metadata uses YAML `.meta.yml` files (Max's reference). **Core controlled-vocabulary constants** (`REGIONS`, `INCOME_GROUPS`) live as **Python dict literals** in [`etl/data_helpers/geo.py`](https://github.com/owid/etl/blob/master/etl/data_helpers/geo.py). `facet-axes` is the second category (typed registry constant), so §0a points to Path D, not Y. Max's position revised to D after this verification. **Final vote: D=3 (Fowler + Jony + Max-revised), Y=1 (Hans), A=1 (Gregor)**.<br/><br/>**§D. Decision: Path D** (Python module compiles to parquet). Each persona's concern is addressed:<br/>· Hans (governance review) → inline `# why CSS vs CS — see 15th FC ch. 11` comments next to dataclass fields handle rationale-next-to-value identically to YAML; non-coder review is a hypothetical reviewer; designing for it is speculative generality.<br/>· Gregor (write-seam unification) → compile function lives INSIDE `backend/yen_gov/canonical/writer.py` alongside `_emit_sources()`, not a parallel module. One file, one seam.<br/>· Jony (label edit safety) → Pydantic v2 (already a project dependency) catches typos at module-import time. No new tooling required.<br/>· Fowler (delete-first) → net-negative LOC.<br/><br/>**§E. Migration cost analysis (D ↔ alternative formats — for future reference)**: The CHOICE OF FORMAT is decoupled from the SHAPE OF DATA. Once `FACET_AXES: list[FacetAxis]` is the in-repo authoring surface and `facet-axes.parquet` is the deployment artifact, swapping the authoring format is mechanical: **D → YAML/JSON**: ~half a day. Export current literal via `yaml.safe_dump([a.model_dump() for a in FACET_AXES])`; replace literal with `FACET_AXES = [FacetAxis(**raw) for raw in yaml.safe_load(open('facet-axes.yaml'))]`. Reversible with one revert. **D → SQL seed**: ~half a day. Export INSERT statements; loader runs them against in-memory DuckDB. **D → parquet-as-source-of-truth (no Python authoring layer)**: 2-3 days. Needs an admin CLI/UI to edit parquet rows in place. This is what the Phase 5 admin UI eventually does. **Any → D**: ~30 minutes via REPL (deserialize, pretty-print to Python literal, paste). **Conclusion: no lock-in**. Path D today does not foreclose any future migration; the shape (axes-with-values) is the contract, the format is packaging.<br/><br/>**§F. Tooling note**: Project uses Pydantic v2 (`pydantic>=2.0` in `backend/pyproject.toml`) and pytest. NO mypy / pyright / Ruff currently configured. **Pydantic models will validate the `FACET_AXES` literal at module-import time** — typos raise `ValidationError` before any parquet is written; pytest catches in the standard sweep. Adding Ruff project-wide is a worthwhile separate PR (Ruff replaces flake8+black+isort+pyupgrade; mypy/pyright/basedpyright is a separate axis = static type checker; the two are complementary, not substitutes). Adopting either is **NOT bundled here** to keep PR-Q.2 scope honest.<br/><br/>**§G. Concrete implementation plan**: (1) **New file** `backend/yen_gov/canonical/facet_axes_seed.py` — `class FacetAxisValue(BaseModel)`, `class FacetAxis(BaseModel)`, module-level `FACET_AXES: list[FacetAxis] = [FacetAxis(axis_id="fuel_type", label="Fuel type", description="...", allow_compute_on_read_total=True, values=[FacetAxisValue(value_id="coal", label="Coal"), ...]), ...]` porting all 13 axes verbatim from current `facet-axes.json`. Plus `compile_to_parquet(out_path: Path) -> int` writing one denormalized row per `(axis_id, value_id)`. Plus module-level `FACET_AXES_ROW_SCHEMA_VERSION = "1.0"` constant for future manifest-entry use. (2) **Writer hook** `backend/yen_gov/canonical/writer.py` — add `_emit_facet_axes(taxonomy_dir: Path) -> int` near `_emit_sources()`; call it from `write_batch()` so any canonical write keeps the parquet fresh. Remove the `"facet-axes": "facet-axes.schema.json"` line from `_taxonomy_schema_file()`. (3) **CLI** `backend/yen_gov/cli.py` — add `@app.command("emit-taxonomy")` standalone command that calls `compile_to_parquet` directly without requiring a full envelope (so operators can regenerate just the taxonomy parquet between pipeline runs). (4) **Generated parquet** committed at `datasets/taxonomy/facet-axes.parquet` — columns: `axis_id, axis_label, axis_description, allow_compute_on_read_total, value_id, value_label, value_description, deprecated`. Denormalized one-row-per-leaf shape chosen so DuckDB-WASM facet pickers query with one `FROM` clause (Hans / Max preference); aggregating back to parent shape is a trivial `SELECT DISTINCT axis_id, axis_label`. (5) **Delete** `datasets/taxonomy/facet-axes.json`, `datasets/schemas/facet-axes.schema.json`, the `"facet-axes.schema.json"` entry in `frontend/src/contracts/datasets-conform.test.ts` PER_ROW_PROVENANCE_SCHEMAS set; also `datasets/taxonomy/delimitation_lineage.json` + `datasets/schemas/delimitation-lineage.schema.json` (placeholder with zero readers — same Python-dict-compiles-to-parquet pattern applies when real lineage authoring begins). (6) **Pytest** `backend/tests/test_facet_axes_seed.py` (tmp_path fixture, NO real-corpus walk per CLAUDE.md §10): asserts (a) seed module imports cleanly with no `ValidationError`; (b) `compile_to_parquet` writes the expected row count; (c) parquet column types correct (VARCHAR, BOOLEAN); (d) DuckDB round-trip SELECT returns original row count and values; (e) `deprecated` flag round-trips; (f) all 13 axes present; (g) all `axis_id` values are unique. (7) **`docs/architecture/data/canonical-store.md`** — drop `facet-axes.json` + `facet-axes.schema.json` from the schemas/taxonomy tree (§2); add a new §5a "Hand-authored taxonomy — Python-compiles-to-parquet pattern" that documents the seed-module convention as the canonical approach for any future hand-authored controlled vocabulary; reframe the delimitation_lineage references (§3a, §3a roster-authorship table) to point at the same pattern. (8) **`docs/architecture/canonical-pivot-deletion-manifest.md`** — flip 1.8d row notes; add 1.8d-ii row; update the taxonomy contents bullet. (9) Item 4 (`operator_state` move) confirmed no-op; recorded here. (10) **Manifest entry deferred**: `_taxonomy_schema_file()` returning None for `facet-axes` means the parquet does NOT appear in `manifest.json` after this PR. That is intentional — zero current consumers; Phase 2 Energy adapter PR will add the manifest entry when it introduces the first facet-explode parent indicator. Smallest reversible step (Fowler).<br/><br/>**§H. Risks / forward pointers**: (a) When `entities.json` / `indicators.json` / `parties.json` migrate later, they'll follow this same pattern but their content is richer (FK relations, enum constraints, larger row counts); each is its own PR. (b) When Phase 5 admin UI lands, this Python seed module may retire in favour of admin-edited parquet; that's a separate migration covered by §E. (c) Adding Ruff project-wide is a known follow-up. (d) When real delimitation-lineage authoring begins (post Phase-2 if any state's pre/post-delim AC comparisons need it), reintroduce as `backend/yen_gov/canonical/delimitation_lineage_seed.py` following the same pattern; the schema file stays deleted (Python class IS the schema). | Hans + Max + Fowler + Gregor + Jony |
| 1.8e | ✅ **DONE 2026-05-19** (PR-R.1 → PR-R.2 → PR-R.3, merged on `main` at commit `a4505501`; closeout regression guard added 2026-05-20 on this branch). User direction 2026-05-19: Option A MIGRATE not retire — Psephlab + Compare were ported to DuckDB-WASM canonical loaders BEFORE the legacy artifacts were deleted, so the what-if simulator stayed alive across the swap; only the parallel sql.js + sqlite shipping artifact went away. **What shipped**: 41 `datasets/elections/<event>/<state>/results.sqlite` files deleted (`Get-ChildItem` returns 0 as of 2026-05-20); `backend/yen_gov/emit/sqlite.py` emitter deleted; `frontend/src/lib/sql.ts` sql.js loader deleted; `frontend/src/lib/psephlab/actuals.ts` legacy loader deleted; all dependent imports cleaned up; `backend/tests/test_no_sqlite_emit.py` (3 source-scan tests asserting the module stays deleted + no `sqlite3` import in `pipeline/*.py` + no reference to the deleted emitter from any `emit/*.py`) added 2026-05-20 to block re-introduction. Two stale docstrings reconciled in the same closeout commit: `backend/yen_gov/emit/__init__.py` ("SQLite today; possibly Parquet later" → CSV-only present-tense; dead link to `emit-sqlite.md` removed) and `backend/yen_gov/pipeline/run.py` ("sqlite + CSV emitters" → CSV emitter only). **Sub-PR shape (preserved for historical reference)**: PR-R.1 (tidy-first, structural) — new `frontend/src/lib/psephlab/canonical-loaders.ts` exporting `loadActuals(event, state) → LoadedActuals` (SAME return shape as legacy `actuals.ts`) but query via DuckDB-WASM against `elections.election_results` + `dim_acs` + `dim_candidates` + `dim_parties` + NOTA synthesis; side-by-side with legacy, unconsumed by routes. PR-R.2 (behavioural) — switched `Psephlab.svelte` + `Compare.svelte` imports to the new canonical loader; e2e `extended-routes.spec.ts` smoke + agent-driven §13 browser verify on `/lab/tamil-nadu/AcGenMay2026` (per-AC swing + statewide swing + threshold drop + party bag) and `/compare/...` both green. PR-R.3 (cleanup, deletion) — `git rm` of the 4 source files + 41 `.sqlite` files in one commit; `datasets/schemas/manifest.schema.json` `deprecations[]` bumped with the sqlite path; folded in alongside: retirement of `datasets/reference/in/parties.json` + `parties-discovered.json` + their schemas + `compose.append_to_discovered_overlay` + `frontend.fetchPartyRegistry` (canonical roster now sourced from `datasets/taxonomy/parties.json` v2.1 via backend party-lookup adapter; frontend party metadata flows through view-model loaders over `dim_parties` + `dim_party_alliances`).

Owner: Fowler (engineering) + Citizen (verified the what-if simulator still answers the same question after the swap). **Recon evidence** (Explore subagent 2026-05-19): all required columns already exist in `election_results.parquet` + `dim_acs` + `dim_candidates` + `dim_parties`; 2 simple SELECTs in `frontend/src/lib/psephlab/actuals.ts:29-34` are trivially portable; the Explore route already proved the pattern in PR-L; engine logic is tested separately from data load. **Sub-plan**:<br/><br/>**PR-R.1 (tidy-first, structural)** — New `frontend/src/lib/psephlab/canonical-loaders.ts` exporting `loadActuals(event, state) → LoadedActuals` (SAME return shape as current `actuals.ts`) but query via DuckDB-WASM against `elections.election_results` + `dim_acs` + `dim_candidates` + `dim_parties` + NOTA synthesis. Tier-A unit tests in `frontend/src/lib/psephlab/canonical-loaders.test.ts` against a tmp Parquet fixture. ZERO behavioural change: old `actuals.ts` (sql.js) stays live; new loader sits side-by-side, unconsumed by routes. Pre-merge gate: backend `pytest -q` + frontend `npm test` both green.<br/><br/>**PR-R.2 (behavioural)** — Switch `Psephlab.svelte` + `Compare.svelte` imports to the new canonical loader. Verify e2e `extended-routes.spec.ts` lines 82–97 smoke tests still green. **CLAUDE.md §13 browser smoke (mandatory, agent-driven)**: open `/lab/tamil-nadu/AcGenMay2026` end-to-end — set per-AC swing, statewide swing, threshold drop, party bag — verify parliament arc + seat delta table render correctly against actuals; open `/compare/tamil-nadu/AcGenMay2026?a=<scn>&b=<scn>` and verify two-scenario render. Pre-merge gate: full test sweep + manual browser verify documented in commit message.<br/><br/>**PR-R.3 (cleanup, deletion)** — `git rm frontend/src/lib/psephlab/actuals.ts` (legacy sql.js loader); `git rm frontend/src/lib/sql.ts`; `git rm backend/yen_gov/emit/sqlite.py`; remove sqlite emit call from any caller (verified via `grep_search` on `emit_state_sqlite` / `sqlite.py`); `git rm datasets/elections/*/*/results.sqlite` (41 files); add `backend/tests/test_no_sqlite_emit.py` regression guard (analogous to `test_no_legacy_json_emit.py` — asserts zero `emit_state_sqlite` callers, zero `sqlite3.connect` in pipeline modules). Bump `datasets/schemas/manifest.schema.json` `deprecations[]` with the sqlite path. Add entry to [`docs/architecture/canonical-pivot-deletion-manifest.md`](../docs/architecture/canonical-pivot-deletion-manifest.md) §6a row 1.8e. Re-verify backend pytest + frontend vitest + e2e + §13 browser smoke all green.<br/><br/>Owner: Fowler (engineering) + Citizen (verifying the what-if simulator still answers the same question after the swap). | Fowler |
| 1.8f | ✅ **DONE 2026-05-20 — PR-S.1 + PR-S.2 (see §7.1 row 1.8f for the as-shipped audit; the original sub-plan is preserved below for the historical record).** Original framing: ⏳ NOT DONE — SCHEDULED as PR-S.1 → PR-S.2 (user direction 2026-05-19: Option A EXTEND not retire). Extend `dim_candidates.parquet` with biographic columns from the 3,983 person JSONs, switch frontend loader to read from canonical store, then delete the JSONs + retire the standalone `people_ingest` pipeline. **Recon evidence** (Explore subagent 2026-05-19): 7 biographic fields not in current `dim_candidates` (sex, age, education, profession, party_short, party_eci_code, party_type, constituency_type, field_provenance); coverage is ONE event/state (TN AE 2021 = `AcGenApr2021`); upstream is ECI Statistical Reports PDFs hand-extracted via operator CSV; existing JSON Schema `datasets/schemas/people.entity.schema.json` v1.0 defines the contract; surface is inline biographic row in `Constituency.svelte` (NOT a separate route); the biographic fields are exactly the socio-economic enrichment Phase 2/3 governance arcs will want — first instance of the `dim_*_bio` extension pattern that fiscal/health/welfare adapters will follow. **Sub-plan**:<br/><br/>**PR-S.1 (schema + adapter + backfill)** — Bump `datasets/schemas/dim-candidates.schema.json` v1.0 → v1.1 (additive: `sex` enum nullable, `age` int 18–120 nullable, `education` 11-value enum nullable, `profession` 17-value enum nullable, `constituency_type` GEN/SC/ST enum nullable, `party_short` string nullable, `party_eci_code` string nullable, `party_type` 5-value enum nullable, `field_provenance` object nullable). Paired TS widening in `frontend/src/lib/canonical/types.ts` `SUPPORTED_SCHEMA_VERSIONS["dim-candidates.schema.json"]` → `["1.0", "1.1"]` (per `/memories/lessons.md` 2026-05-16 #1 "schema enum extension MUST update paired TS union in the same Tier-A commit"). Extend `backend/yen_gov/canonical/adapters/eci/` to merge biographic CSV panel (`datasets/ephemeral/<event>/<state>.csv`) into dim_candidates output. Backfill: one-shot tool `tools/backfill_dim_candidate_bio_from_people_json.py` reads existing 3,983 person JSONs (TN AE 2021), UPSERTs biographic fields into `datasets/elections/dim_candidates.parquet`. Tier-A tests against tmp_path fixture corpus (CLAUDE.md §10 — NO real-corpus walk). ZERO frontend change in this PR.<br/><br/>**PR-S.2 (frontend switch + deletion + retirement)** — Extend `loadConstituencyResult` in `frontend/src/lib/view-models/constituency.ts` to read biographic columns from `dim_candidates`. Remove the `fetchPersonEntity` fan-out in `Constituency.svelte:91-95` and the rendering at `:253-267` continues working against the new field source (component code unchanged; only the data source moves). Delete `frontend/src/lib/data.ts` `fetchPersonEntity` + `PersonEntity` + `slugifyCandidate` (if unused elsewhere; verify via `grep_search`); delete the `fetchPersonEntity` test in `data.test.ts`. `git rm -r datasets/people/AcGenApr2021/` (3,983 files). `git rm datasets/schemas/people.entity.schema.json`. `git rm backend/yen_gov/sources/eci/people_panel.py`. `git rm backend/yen_gov/pipeline/people_ingest.py` (after verifying canonical adapter has subsumed its work — note `compare_winner_votes` was already retired in PR-O.3b-main and now reads canonical Parquet, so this is removing the dead ingest entry point). Add regression test `backend/tests/test_no_people_json_artifacts.py` asserting `datasets/people/` does not exist OR is empty. Add entry to deletion manifest §6a row 1.8f. **CLAUDE.md §13 browser smoke (mandatory)**: open `/s/tamil-nadu/ac/1-mylapore` (or representative TN 2021 AC) and verify candidate biographic cells render correctly from Parquet (`sex`, `age`, `education`, `profession` visible in candidate table row); compare visually against pre-PR screenshot to confirm zero regression.<br/><br/>Owner: Hans (data shape — biographic field decisions, OWID precedent for enum vocabularies) + Fowler (engineering — schema bump, adapter, frontend switch, deletion gates) + Max (enum vocabularies). | Hans + Fowler |
| 1.9 | **REMEASURED 2026-05-19 (post PR-Q, mid-deletion sweep)**: `.git/` = 115 MB (Δ −5 MB vs 2026-05-18 baseline), `datasets/` = 196 MB (Δ −47 MB / −19%), JSON file count = 4,349 (Δ −9,300 / −68% vs implied pre-cleanup ~13,649). Parquet count = 7 (canonical store + small extras); sqlite count = 41 (all then-deferred to 1.8e). Cleanly under the 2 GB / 60 s clone-time thresholds. Forecast "expect `datasets/` to drop by ~9,300 JSON files" met. **Update 2026-05-20 (post 1.8e + 1.8f)**: sqlite count = 0 (PR-R.3 deleted all 41); person JSON count = 0 (PR-S.2 deleted all 3,983). Full remeasurement of `.git/` + `datasets/` deferred to a clean checkout before Phase 2 kickoff. If `.git/` growth crosses 500 MB before Phase 2, escalate to Fowler + Gregor on Git LFS. **2026-05-18 baseline retained for reference**: `.git/` = 120 MB, `datasets/` = 243 MB, total ≈ 363 MB. | Fowler |
| 1.10 | **SHIPPED 2026-05-19 on branch `feat/canonical-pivot-1.10-proto-ontology` (PR-T)** — 5 commits T-1..T-5: `3df5644e` indicator-schema v4.3→v4.4 additive (8 fields incl. `description_short`, `short_unit`, `description_long`, `derivation_note`, `source_ref[]`, `valid_period_grain`, `valid_entity_grain`, `is_input_output_outcome`) + Tier-A TS pairing in `IndicatorMeta`; `9dc5d086` party-schema v1.0→v2.0 breaking rename (`predecessor_of`→`successor_party_id`, `successor_of`→`predecessor_party_id`) + 32-row migration + test fixture; `ed073fe9` 110-row `short_unit` mechanical backfill + 31-row `description_short` hand-author spanning all 9 families; `f86563af` chart-wrapper wiring (two pure helpers `axisUnitLabel` + `legendCaption` with 3-tier fallback + `data-testid` hooks + 8 vitest cases) wired into Choropleth/Ranked/SmallMultiples; `3056f14e` per-family PR-template gate doc (step 6 of "Adding a new indicator" + decisions-journal entry with R1/R2/R3 rejected designs). §13 smoke verified at `/t/economy` (legend `["₹L cr", "₹", "₹cr"]`; hand-authored `description_short` rendering for top-31; `description` fallback rendering for tail). Test counts: pytest 717+ green; vitest 9368 green. Entity-schema delta: NONE (`entity_valid_from`/`entity_valid_to` already on v1.0). **ORIGINAL PLAN (for reference)**: minimum OWID-floor metadata on indicator/entity/party taxonomy so a future LLM (Phase 4) can ground answers, AND citizens get a visible win in the same PR (Jony ROI gate). **Indicator schema additions** (`datasets/schemas/indicator.schema.json` minor bump v4.3 → v4.4, additive): optional `description_short` (≤280 chars, citizen-readable; NULL-able at schema layer, enforced at chart-publication gate per OWID grapher `MetadataValidator` shape — see Backfill clause for scope), optional `description_long` (multi-para markdown methodology — numerator/denominator/scope/known breaks), optional `short_unit` (e.g. `"%"` for `unit="percent"`, `"₹cr"` for `unit="INR crore"` — `unit` is already on the v4.3 schema), optional `derivation_note` (one sentence naming numerator+denominator when `derivation != "raw"`), optional `source_ref[]` (catalogue-level FK array into `taxonomy/sources.parquet`; per-observation `source_id` unchanged), optional `valid_period_grain` enum (`year`/`fiscal_year`/`election_date`), optional `valid_entity_grain` enum (`country`/`state`/`district`/`ac`/`pc`), optional `is_input_output_outcome` enum (input/output/outcome — disambiguates MGNREGA-disbursed vs rural-wage-real). **Entity schema additions**: NONE. v1.0 already carries required `entity_type` enum, optional `parent_entity_id`, required `entity_valid_from` and optional `entity_valid_to` (flat int-year columns matching OWID `regions.start_year` / `end_year` shape). Telangana row already carries `entity_valid_from: 2014, entity_valid_to: null`; J&K composite (`IN-S09`) carries `entity_valid_from: 1947, entity_valid_to: 2019`; J&K UT (`IN-U08`) and Ladakh (`IN-U09`) carry `entity_valid_from: 2019`. Day-precision context ("Carved from Andhra Pradesh on 2 Jun 2014") stays in the existing `notes` field. **Rejected with named reason (Hans + Max, 2026-05-19, Q1)**: a nested `lifespan: {from, to}` object — OWID's regions table uses flat ints, not nested objects; FC devolution / GST / CSS all operate on fiscal-year grain so no governance question hinges on day precision; a parallel object alongside the existing ints is exactly the drift hazard ADR-0026 spent a sprint lifting out of `indicator.json`. **Party schema bump** (`datasets/schemas/taxonomy-parties.schema.json` v1.0 → v2.0, BREAKING rename — Hans + Max, 2026-05-19, Q2): rename existing optional `successor_of` → `successor_party_id` and `predecessor_of` → `predecessor_party_id`. Pattern stays `^parties\.IN\.[A-Z][A-Z0-9_]*$`; semantics unchanged. Migrate every party row that currently populates these fields (DMK→MDMK split, Janata Dal lineage chain) in the same commit; party content is thin (TN-focused roster) so migration cost is minimal — cheapest possible moment for the rename. Rationale: matches the `<typed_role>_id` convention used everywhere else in the canonical store (`parent_entity_id`, `source_id`, `indicator_id`, `ac_id`, `candidate_id`); the v1.0 `_of` outliers were a freshly-shipped accident (2026-05-18, same wave as `parent_entity_id`) and read backwards (`X.predecessor_of = Y` means "X is the predecessor of Y", inverting the natural FK reading). **Tier-A pairing**: widen the TS union in `frontend/src/lib/parties.ts` (or equivalent) in the same commit per `/memories/lessons.md` 2026-05-17 #1. **Backfill same PR (Hans + Max, 2026-05-19, Q3)**: (a) hand-author `description_short` on the **top-30 indicators with citizen-facing chart routes today** (those linked from `/explore`, state hubs, and topic landing pages); Hans owns the wording, ≤280 chars each, Plain-Facts style, distinguish input vs output vs outcome per `is_input_output_outcome`. Tail of ~80 backstage indicators backfill `description_short` per-family at their next natural touch (energy in 2.x, demography / fiscal / education / health in 3.x) as the adapter author is already reading methodology. Chart wrapper falls back to `indicator.title` when `description_short` is absent — page degrades gracefully, never lies. (b) Populate `unit` / `short_unit` on every numeric indicator (mechanical, no editorial judgement; `unit` is already on v4.3 so this is `short_unit`-only on most rows). (c) Migrate the party rows with `successor_of` / `predecessor_of` to the renamed FK column names (mechanical). (d) Entity lifespan: nothing to backfill — Telangana and J&K already correctly stamped per v1.0. **Per-family PR-template gate** (compensates for "optional" choice on `description_short`): every NEW indicator artifact authored in a per-family PR MUST populate `description_short`. Prevents (iii)'s "tail fills later" from becoming permanent debt. **Rejected with named reason (Q3)**: auto-stub `description_short` of the form `{title} ({unit})` — OWID refuses tautological stubs because they look authoritative on a chart legend but are factually empty to a citizen and poison downstream LLM grounding; band-aid per CLAUDE.md §5; violates Rosling's Single-perspective / Generalisation instincts. **Citizen surface (Jony — ships in same PR)**: extend chart-wrapper component to read `indicator.short_unit` for Y-axis label (fallback: `indicator.unit`) and `indicator.description_short` for one-line legend caption (fallback: `indicator.title`); both visible at page load, NOT behind tooltip/expander/modal. One generic-component change pays for all 30+ citizen-facing indicators. **Explicitly OUT of scope**: RDF/JSON-LD, SKOS, embedding vectors, `synonyms[]`, `related_indicators[]`, separate concepts file, methodology modals/drawers — defer to Phase 4/5 when the LLM ships. **Out-of-scope-but-allowed-later additions**: a `datasets/CHANGELOG.md` entry for the schema bumps. | Hans + Max + Jony |

**Exit criteria** (audited 2026-05-19; re-audited 2026-05-20 post 1.8e + 1.8f closeout — all items now ✅):

- ✅ Zero per-AC JSON projections for elections (1.8c verified 0 files on disk).
- ✅ Zero per-state `parties.json` / `result.summary.json` (1.8b-ii verified 0 files on disk).
- ✅ Zero `events/in/eci/<event>/election.json` projections (1.8d verified 0 files on disk).
- ✅ All citizen election routes served from Parquet via view-model loader (PR-E/F/G/H/I/J/K/L/M/T all merged).
- ✅ Failure-state copy verified ([`frontend/src/lib/canonical/failure-state.test.ts`](../frontend/src/lib/canonical/failure-state.test.ts)).
- ✅ Admin v0 stance resolved (PR-M Inventory family-agnostic; ECI Recon retired).
- ✅ No regression in Playwright golden-path suite (verified PR-by-PR; latest at `8fbabad6`).
- ✅ **1.8e — Psephlab + Compare migrated to DuckDB-WASM canonical loaders; 41 `.sqlite` files + `lib/sql.ts` + `lib/psephlab/actuals.ts` + `emit/sqlite.py` deleted; `test_no_sqlite_emit.py` regression guard added.** Shipped PR-R.1 → PR-R.2 → PR-R.3 (commit `a4505501`, 2026-05-19); closeout regression guard 2026-05-20.
- ✅ **1.8f — `dim_candidates.parquet` v1.2 carries 6 nullable biographic columns; 3,983 person JSONs + `people.entity.schema.json` deleted; `people_ingest` refactored to UPSERT bios into canonical store via `_upsert_dim`; `compare_winner_votes` QA gate preserved verbatim.** Shipped PR-S.1 (commit `dc06dd77`, 2026-05-20) + PR-S.2 (PR #60, commit `4972c410`, 2026-05-20).

**Phase 2 (Energy) is now unblocked** per §0d (no goalpost-moving via vocabulary drift). All Phase 1 exit criteria green on 2026-05-20.

---

## §8. Phase 2 — Energy (weeks 7–9)

**Goal**: First socio-economic indicator family. Prove the model scales beyond elections.

| Step | Deliverable | Owner |
| --- | --- | --- |
| 2.1 | Indicator scout: pick canonical Indian energy series (CEA installed capacity + state-wise generation; cross-check OWID energy table for indicator IDs to mirror) | Max |
| 2.2 | Source adapter (CEA monthly reports) → canonical batch envelope | Hans + Fowler |
| 2.3 | Indicator + source rows seeded; `cadence='monthly_cy'` on indicator row; **`period_seq` 1..12 per year populated** | Hans + Max |
| 2.4 | First chart: state-wise installed capacity time-series; one map view; **time control keys on `(year, period_seq)`, displays `period_label`** | Jony |
| 2.5 | **Acquisition sequence for socio-economic Phase 2 families** (energy first; then ordered demography → fiscal → education → health by ≥80% states, ≥10 years, gold-source first). Drafted by Max in Phase 0.5 migration ledger. | Max |
| 2.6 | Citizen functional read-through (mid-tier Android NOT a blocker; just "can I read this page and understand it") | Citizen |
| 2.7 | **Cleanup sub-step** (mandatory per §9 step 7): once 2.4 + 2.6 are green, `git grep` for any reader of pre-pivot energy artifacts; if zero, delete them in a follow-up sub-PR and append to [`docs/architecture/canonical-pivot-deletion-manifest.md`](../docs/architecture/canonical-pivot-deletion-manifest.md) §6a. `datasets/energy/` must satisfy the directory invariant (Parquet only). | Fowler |

**Exit criteria**: one citizen-readable energy page live; OWID-alignment doc updated with the energy indicator mapping; no new schemas required; `caveats.parquet` display contract resolved (Q7) before this page lands.

---

## §9. Phase 3 — Demography / Fiscal / Education / Health (weeks 10–18)

**Goal**: Breadth. Same data shape, repeated across four families. Tests model stability.

| Family | First indicators | Likely source | Notes |
| --- | --- | --- | --- |
| Demography | Population, sex ratio, urbanisation | Census 2011 + SRS bulletins | `cadence='decennial'` mixed with `cadence='annual_cy'` → exercises `caveats.parquet` |
| Fiscal | State own-tax revenue, GSDP, FC devolution, GST | CAG state finance reports + FC docs | `cadence='annual_fy'`; year:int = end-year (FY 2024-25 → 2025); **fiscal-actor doctrine, R10** |
| Education | Literacy, GER, dropout rate | UDISE+ | District-level; tests entity_id scale beyond state |
| Health | IMR, MMR, immunisation coverage | NFHS-5 + HMIS | Mixed cadence; survey vs administrative — Hans annotation needed |

**Fiscal-actor doctrine (R10)** — fiscal indicators MUST classify by `attribution_geography` and `implementing_authority` in `taxonomy/indicators.json`:

- `economy_as_place` — GSDP, state-level production
- `state_government` — state own-tax, state expenditure
- `union_government` — central revenue, central expenditure
- `centre_to_state_flow` — FC devolution, CSS transfers
- `states_combined` — aggregates across all states
- `consolidated_general_government` — Union + all states net of transfers
- **GST is always `where_billed`**, never state-performance signal. Banner copy enforced via `methodology_breaks` / `caveats` when GST flows through a state-comparison chart.
- Health/education/welfare cross-state comparisons that depend on fiscal context either wait for the fiscal baseline or render a "fiscal context pending" caveat.

**Per-family steps** (parametrised over `<family>`):

1. Max scouts indicator list (OWID precedent first).
2. Hans annotates Indian-context caveats (methodology breaks, definitional shifts) → `methodology_breaks.json`.
3. Adapter authored using batch envelope (D20).
4. Backfill committed.
5. One citizen chart per family minimum.
6. `caveats.json` entries for any cross-cadence joins; `methodology_breaks.json` entries for definitional/base-year breaks (separate surfaces per D16).
7. **Cleanup (Phase-1.8 pattern, mandatory)**: once the family's citizen chart is green and the migration is proven, (a) `git grep` the codebase for any reader of pre-pivot artifacts in that family's tree (`datasets/<family>/in/**`, sidecar JSON shards, legacy sqlite); if zero matches, delete the legacy files in a follow-up sub-PR; (b) **rename the family's Parquet files per the convention in [canonical-store.md §2a](../docs/architecture/data/canonical-store.md)** (fact tables → `<family>_<role>.parquet`, dims stay `dim_*`); (c) **prune every empty parent directory** that the deletion left behind (`find datasets/<family> -type d -empty -delete` re-run to fixpoint); (d) record the deletion + rename + dir-prune in [`docs/architecture/canonical-pivot-deletion-manifest.md`](../docs/architecture/canonical-pivot-deletion-manifest.md) §6a with legacy path → canonical replacement → gate command. The family's `datasets/<family>/` directory MUST satisfy both the **directory invariant** (Parquet only) and the **naming convention** (no `observations.parquet` / `data.parquet` / `facts.parquet`) before the family is declared DONE.

**Exit criteria**: 5 indicator families live (elections + 4 here); aggregate Parquet size stays under partition thresholds (or partitions correctly applied per D8); Citizen sign-off on at least one chart per family; fiscal-actor doctrine reflected in indicator catalogue rows.

---

## §10. Phase 4 — SLM dispatcher (weeks 19–22)

**Goal**: Small language model in browser answers natural-language questions over the canonical store.

**Grounding stance (Hans + Max, 2026-05-18, amended 2026-05-19)**: the proto-ontology added in row 1.10 (`indicator.description_short` / `description_long` / `unit` / `short_unit` / `derivation_note` / `valid_period_grain` / `valid_entity_grain` / `is_input_output_outcome`; `entity.entity_type` / `parent_entity_id` / `entity_valid_from` / `entity_valid_to` — all already on v1.0, no bump; `party.successor_party_id` / `predecessor_party_id` — renamed from v1.0 `_of` form, v2.0 breaking) is the **grounding layer for this SLM**. Phase 4 does NOT introduce a separate ontology file — it consumes the taxonomy that elections + each family populated as they shipped. If a question cannot be answered from those fields, the gap is fixed in the indicator/entity/party catalogue, not by adding a parallel "concepts" file. Explicitly OUT of Phase 4: RDF/JSON-LD, SKOS, embedding side-cars, `synonyms[]`. If the SLM proves it needs structured numerator/denominator joins, escalate to a follow-up phase — do not bolt on speculative schema.

| Step | Deliverable | Owner |
| --- | --- | --- |
| 4.1 | Pick SLM (likely WebLLM or similar; <500 MB model). Functional first; mobile-perf later. | Fowler |
| 4.2 | NL→SQL prompt with canonical schema in system prompt; allow-list via `sqlglot` parser OR `DuckDB EXPLAIN` dry-run (Q3) | Gregor |
| 4.3 | Citizen UX for ask/answer; default chips for common questions ("compare TN and KL on literacy") | Jony + Citizen |
| 4.4 | Safety gate: query timeout, result-row cap, no-DDL allowlist | Fowler |
| 4.5 | Caveats + methodology-breaks banners auto-pulled when query joins across cadences or crosses a known break | Hans + Jony |

**Exit criteria**: 10 hand-picked test questions return correct answers; SLM never emits DDL; caveats AND methodology-breaks banners fire correctly on misleading joins / break crossings.

---

## §11. Phase 5 — Admin rewrite (weeks 23–26)

**Goal**: Operator console rewritten against canonical store. Becomes thin SQL UI over local DuckDB.

| Step | Deliverable | Owner |
| --- | --- | --- |
| 5.1 | Admin Inventory panel: SQL over `taxonomy/indicators.parquet` JOIN `(SELECT DISTINCT indicator_id FROM <family>)` | Fowler |
| 5.2 | Operator-state edit UI writes to `datasets/taxonomy/operator_state.json` (text!) via local FastAPI; pipeline recompiles to `.parquet` | Fowler |
| 5.3 | Pipeline-trigger panel: kick adapters; show UPSERT diffs | Fowler |
| 5.4 | Schemas panel: render schemas from disk; no editing in v1 | Gregor |

**Exit criteria**: parity with whatever admin v0 stance was chosen in §7 step 1.7; operator confirms inventory + force-recollect workflows.

---

## §12. Open questions (resolve before the relevant phase)

| ID | Question | Resolve by | Authority | R10 note |
| --- | --- | --- | --- | --- |
| Q1 | Hive partition column when family > 15 MB | Phase 2 first chart | Hans + Gregor | **R10 leans `indicator_id`** per D8; confirm with energy data |
| Q2 | Git LFS vs build-artifact when repo >2 GB | End of Phase 1 | Fowler + Gregor | unchanged |
| Q3 | SLM safety gate — `sqlglot` allowlist vs `DuckDB EXPLAIN` dry-run vs both | Phase 4 step 4.2 | Gregor + Fowler | unchanged |
| Q4 | District identifier source confirmation (LGD vs Wikipedia slug fallback) | Phase 0 step 0.4 | Max | unchanged |
| Q5 | "Top-N + others" cutoff for per-AC results | Phase 1 step 1.6 | Citizen | **RESOLVED 2026-05-18 (PR-K)**: keep `top_n_candidates=5` cap in `config/processing.json`; materialise `ac-candidates-total` + `ac-others-{votes,pct}` so the citizen sees the real field size and tail aggregate even when only the top 5 candidate rows are stored. |
| Q6 | Failure-state UX copy library (which phrases for which failure class) | Phase 0 step 0.11 | Jony + Citizen | **R10 reframed** from "bundle size budget" to "failure-state copy"; mobile-perf descoped |
| Q7 | `caveats.parquet` display contract (when does a banner fire? severity? copy?) | **Before Phase 2 first mixed-cadence chart** (R10 tightened from "Phase 3") | Hans + Jony | mixed-cadence misleading-join is a Phase-2 risk the moment energy + decennial demography compose |
| Q8 | `methodology_breaks.parquet` display contract (separate from Q7) | Before Phase 3 fiscal chart (first break-crossing series) | Hans + Jony | NEW R10 |
| Q9 | Commit compiled Parquet to git or rebuild locally? | End of Phase 0 | Fowler + Gregor | NEW R10 — text taxonomy is committed (D18); decision is about the derived `.parquet` variants |
| Q10 | Admin v0 interim stance: minimum canonical rewrite in Phase 1, or retire panels until Phase 5? | Phase 1 step 1.7 | Fowler + user | NEW R10 |
| Q11 | Boundary format cutover — at what file size does a layer move from GeoJSON to PMTiles? (Initial guess: ~10 MB raw GeoJSON or any layer needing zoom-level tiling) | Phase 0 step 0.14 | Jony + Fowler | NEW R10 boundaries — answer feeds ADR-0031 |

**Convene rules**: any agent may propose; final decision per §1 authority table; user supersedes.

---

## §13. Instructions for next coding agent

You are picking up a fresh thread. Do these in order:

1. **Read this entire file.** Then read [`CLAUDE.md`](../CLAUDE.md) §0a, §3, §10, §12 and [`docs/agents/guardrails.md`](../docs/agents/guardrails.md). Then read the two input artifacts in §0a (corpus survey + consolidation audit) ONCE for context.
2. **THIS file is the plan.** Per §0a, do not invent parallel plans. If something needs to change, edit this file in the same commit as the code change.
3. **Do not re-debate decisions D1–D36 or rejected alternatives R1–R31.** They are settled. Escalate to the user if you believe one is wrong.
4. **The 110-ID corpus is a snapshot, not the target.** Per §0b, design for 500–1,000+ indicator_ids over 2–3 years. The catalogue schema and `taxonomy/facet-axes.json` (D31) must accept new topics (judiciary, healthcare, water, crime, education-deep, welfare, local-govt-finance) without bump.
5. **Boundaries are preserved.** Per §0c, no implementation step touches `datasets/boundaries/` except to ADD layers. Phase 0.13 + Phase 1.8 EXCLUDE that tree.
6. **Phase 0 step 0.0 is the deletion manifest.** Land that doc-only PR before any code.
7. **Then ADR-0030 (incorporating R11 decisions D26–D36) and `docs/architecture/data/canonical-store.md`.** Every other doc links to them. Canonical-store.md MUST include the naming convention (D30) and the registered facet axes (D31).
8. **Then ADR-0031 (boundaries) per Phase 0.14.** Captures D25 + Q11.
9. **Then migration ledger (0.5) — before any writer code lands.** It defines the scope of what canonical must absorb before `_old/` can die.
10. **Then schemas (0.3), manifest contract (0.6), Range/MIME verification (0.7), and writer skeleton (0.9) in parallel.**
11. **Use the authority table (§1) to resolve agent debates.** Hans+Max own data shape AND indicator consolidation (per R11 user delegation). Gregor owns contract/integration. Fowler owns engineering craft. Jony+Citizen own UX. User supersedes.
12. **Test tier discipline** (CLAUDE.md §15): every new schema → contract test; every loader → integration test; every citizen route → Playwright golden-path extension. Parquet-specific contract tests use DuckDB round-trip + tmp_path fixtures; no mocks; no corpus walk. Consolidation migration follows D35 (unit + integration, skip golden-byte).
13. **Failure-state UX (D17) is a Phase 0 deliverable, not a polish item.** Step 0.11 must land before Phase 1 starts.

### §13a. Handoff prompt for the next agent (copy-paste)

```
You are taking over implementation of yen-gov's canonical long-format pivot.

THE PLAN (single source of truth): TODO/20260517-canonical-long-format-pivot.md
Read it end-to-end before any other action. It has been through R1+R2 agent debate
and user sign-off as of 2026-05-17 (R11). All decisions D1–D36 and rejected
alternatives R1–R31 are settled; do not relitigate.

INPUTS (read once for context, do not modify):
- TODO/20260517-indicator-corpus-survey.md — factual baseline of 110 currently-ingested IDs.
- TODO/20260517-indicator-consolidation-audit.md — Max+Hans consolidation pass; §2 contains
  known hallucinated IDs flagged in the doc itself; treat the audit as directional, NOT
  as the authoritative indicator list. The authoritative list is what gets seeded in Phase 0
  step 0.4 (entities) and ingested per Phase 1/2/3.

GROUND RULES (read THE PLAN §0a/§0b/§0c carefully):
1. THE PLAN is the only plan. Do not start parallel TODO files. If scope changes, edit THE
   PLAN in the same commit.
2. Indicator cardinality is a moving target — design for 500–1,000+ IDs over 2–3 years
   (judiciary, healthcare, water, crime, education-deep, welfare, local-govt-finance are
   not yet ingested). The contract MUST scale without rework.
3. datasets/boundaries/ is NOT legacy. Never move it, never delete it, never rename files
   in it. Phase 0.13 and Phase 1.8 EXCLUDE that tree. If you find yourself about to run
   `git rm` or `git mv` against anything under datasets/boundaries/, STOP and escalate.

AUTHORITY (CLAUDE.md §0a + R11 confirmation):
- Hans + Max — data shape, entity_id tiering, indicator catalogue, consolidation decisions.
- Gregor — contracts, schema versioning, integration seams.
- Fowler — engineering craft, refactor safety, test tiers, module structure.
- Jony + Citizen — UX, URL grammar, copy, citizen framing.
- User supersedes everyone.

START SEQUENCE:
1. Read THE PLAN (TODO/20260517-canonical-long-format-pivot.md) end-to-end.
2. Read CLAUDE.md §0a, §3, §10, §11, §12, §15.
3. Read docs/agents/guardrails.md.
4. Skim the two input artifacts (§0a) once.
5. Execute Phase 0 step 0.0 (deletion manifest, doc-only PR) — see §6.
6. Then ADR-0030 (incorporating R11 decisions D26–D36) per Phase 0 step 0.1.
7. Then docs/architecture/data/canonical-store.md per Phase 0 step 0.2 — MUST include
   D30 naming convention and D31 facet-axes registry.
8. Then ADR-0031 (boundaries) per Phase 0 step 0.14.
9. Then continue Phase 0 in the order specified in §13 above.

TESTS: per CLAUDE.md §15 tiers. No corpus walk in pytest. No mocks except where Holy Law 7
explicitly allows. Real DuckDB in writer tests via tmp_path.

UI VERIFICATION: per CLAUDE.md §13, any change touching frontend/ or admin/ runtime must be
verified in a real browser via the integrated tools — not deferred to the human.

WHEN BLOCKED: classify the question per §1 authority table and convene the relevant agent(s).
For ambiguity above that level, escalate to the user. Do not invent decisions.
```

### §13b. CURRENT NEXT STEPS (2026-05-19, post Phase-1 deletion-sweep merge + honest re-audit)

Phase 0 + Phase 1 (elections-results pivot) are substantially complete; PR-Q.2 (#53, `8fbabad6`) was the most recent landing. Two ⏳ rows remain before Phase 2 starts. Execute in this exact order:

1. **Plan-doc honesty pass (this PR)** — vocabulary collapsed to ✅ / ⏳ / ⊘ per §0d; Phase 0 status audit (§6.0) added; Phase 1 deletion-sweep status audit (§7.1) added; rows 1.8e + 1.8f rewritten with concrete PR-R / PR-S sub-plans; exit criteria updated; §1 SQL-vs-SQLite paragraph updated to reflect MIGRATE not retire. Doc-only commit. Owner: Fowler (writing). Pre-merge gate: rendering check that all icons render correctly; no broken cross-links.
2. **PR-R.1 (1.8e structural; Fowler tidy-first)** — new `frontend/src/lib/psephlab/canonical-loaders.ts` exporting `loadActuals` against DuckDB-WASM canonical Parquet (same return shape as legacy `actuals.ts`). Side-by-side with legacy; ZERO behavioural change. Tier-A vitest + tmp Parquet fixture. Pre-merge gate: backend `pytest -q` + frontend `npm test` green; no existing route consumes the new loader yet.
3. **PR-R.2 (1.8e behavioural)** — switch `Psephlab.svelte` + `Compare.svelte` to the new loader. Engine tests untouched. Pre-merge gate: e2e `extended-routes.spec.ts` smoke + agent-driven §13 browser verify (open `/lab/tamil-nadu/AcGenMay2026`, exercise per-AC swing + statewide swing + threshold drop + party bag, screenshot result; open `/compare/...` with two scenarios).
4. **PR-R.3 (1.8e cleanup)** — delete `actuals.ts` + `lib/sql.ts` + `emit/sqlite.py` + 41 `.sqlite` files; add `test_no_sqlite_emit.py` regression guard; bump `manifest.schema.json` `deprecations[]`. Pre-merge gate: full suite + §13 browser re-verify.
5. **PR-S.1 (1.8f schema + backfill)** — bump `dim-candidates.schema.json` v1.0 → v1.1 (additive biographic fields); paired TS union widening (`/memories/lessons.md` 2026-05-16 #1); extend ECI canonical adapter; one-shot backfill tool from 3,983 person JSONs into `dim_candidates.parquet`. Tier-A tests against tmp_path fixture (CLAUDE.md §10). Pre-merge gate: backend + frontend test sweeps green; spot-check that `dim_candidates.parquet` rows for `AcGenApr2021` show biographic fields populated via `duckdb` CLI.
6. **PR-S.2 (1.8f frontend switch + retirement)** — extend `loadConstituencyResult` to read biographic columns from Parquet; remove `fetchPersonEntity`; delete 3,983 JSONs + `people.entity.schema.json` + `people_panel.py` + `people_ingest.py` (the latter's `compare_winner_votes` was already retired in PR-O.3b-main); add `test_no_people_json_artifacts.py`. **CLAUDE.md §13 browser smoke**: TN 2021 AC candidate table row renders biographic fields correctly from Parquet (no console errors, no 404s for `/data/people/...`). Pre-merge gate: full suite + §13 browser verify.
7. **Phase 1 close-out (no separate PR — automatic when PR-S.2 lands)** — verify all §7 exit-criteria items are ✅; update header status line; declare ready-for-Phase-2.
8. **Phase 2.1 (Energy indicator scout)** — Max persona produces scouting note under `docs/research/phase-2-energy-indicator-scout.md` listing canonical Indian energy series (CEA monthly installed-capacity + state-wise generation), OWID indicator IDs to mirror, source URLs, cadence/grain, candidate `(indicator_id, parent, dimension_values)` slots. Cheap; sets up 2.2.
9. **Phase 2.2 (CEA adapter end-to-end)** — Hans + Fowler build first non-elections canonical adapter end-to-end: fetch → parse → batch envelope → write → citizen chart at step 2.4. Multi-PR arc. First real downstream consumer of the §8.3 Python-compiles-to-parquet pattern (CEA's `allocation_basis` facet now has somewhere to land).

**Binding decisions from the 2026-05-19 honesty-pass exchange** (do not relitigate):

- **Status vocabulary is exactly 3 values** (§0d): ✅ DONE / ⏳ NOT DONE — IN PROGRESS or SCHEDULED / ⊘ NOT DONE — DROPPED. The words "SHIPPED", "DEFERRED", "SUPERSEDED", "PENDING", "PARTIALLY DONE" are forbidden — they are the drift hazard the user named on 2026-05-19.
- **1.8e is MIGRATE not retire.** Psephlab + Compare are advanced specialist surfaces that align with the canonical-pivot's "SQL stays, SQLite goes" doctrine. Migrating preserves the what-if capability while retiring the parallel sql.js + sqlite shipping artifact.
- **1.8f is EXTEND not retire.** The candidate biographic surface (profession + education + age) is exactly the socio-economic enrichment Phase 2/3 governance arcs will want. Throwing it away to close a TODO is a bad trade; instead make `dim_candidates` carry it canonically. This also establishes the first `dim_*_bio` extension pattern that fiscal/health/welfare adapters will follow.
- **Phase 2 (Energy) does NOT start until both ⏳ rows above are ✅.** Per §7 exit criteria. No goalpost-moving via vocabulary drift (§0d).
- **2026-05-18 decisions remain binding**: SQL stays / SQLite goes; `dim_*` carve-out preserved (Kimball convention); 1.8a-bis ships separately from 1.8b (Fowler two-hat).

---

## §14. Round log (compressed)

- **R1–R3**: Canonical-pivot debate; converged on DuckDB-WASM + Parquet.
- **R4–R6**: Partition axis debate; converged on per-family default + partition only when >15MB.
- **R7**: User asked for OWID adoption + comprehensive zero-context plan.
- **R8**: "Chasing tails" — adopted OWID `year:int`. CLAUDE.md §10 period-normalisation rule removed. Authority table established.
- **R9**: OWID approved; CLAUDE.md cleanup + plan rewrite + 5 phases bootstrapped. All AGENTS.md / concept docs synced.
- **R10 (current)**: Six-agent architectural review run (Citizen, Hans, Max, Gregor, Fowler, Jony — Hans/Citizen/Gregor partial due to tool-rendering issues; substantive review from Max/Fowler/Jony plus consolidated user-curated feedback from prior agent pass). Plan amended to absorb:
  - UPSERT identity excludes `source_id`; includes `period_label`; logical key formalised (R16).
  - `value` split into `value_numeric` + `value_text` (R17, D5/D17).
  - `period_seq` added for sub-annual sortability.
  - Hive partition by `indicator_id`, never by `year` (R18, D8).
  - Hand-authored taxonomy in JSON/CSV; Parquet is compiled artifact (R19, D18).
  - `methodology_breaks` separated from `caveats` (R20, D16).
  - Production feature-flag coexistence rejected (R21, D13 sharpened).
  - View-model loader contract added (R22, D19).
  - Manifest-driven file discovery added (R23, D21).
  - Failure-state UX contract added as Phase 0 deliverable (D17, step 0.11).
  - OWID origin.* vs yen-gov extensions explicitly separated in sources schema (D5).
  - Indicator catalogue expanded to full Hans honesty surface (D15, §5 indicator schema).
  - Entity validity windows added (D23).
  - Migration ledger added as Phase 0.5 deliverable (D24).
  - FK referential integrity at write time (D22).
  - Typed adapter→writer batch envelope (D20).
  - Parquet schema-version mechanism + `manifest.json` (D21).
  - `_old/` deletion gated on explicit checklist, not phase date (D14 sharpened).
  - Migration parity oracle added to Phase 1 (step 1.5).
  - Admin v0 interim stance forced as Phase 1 decision (step 1.7, Q10).
  - Fiscal-actor doctrine added to Phase 3 (§9).
  - Doc cleanup list expanded (data-provenance, data-loading, schemas/core/pipeline, admin overview).
  - Range/MIME Pages verification added to Phase 0 (step 0.7).
  - Mobile-perf explicitly descoped from gating criteria; functional correctness is the bar.
- **R11 (current — concurrence pass)**: Pre-R2 consolidation audit (Max+Hans) showed the corpus has heavy duplication; 110 collapses to ~60 parents → ~80–120 ids after selective explode (NOT the ~210 R1 projection). User explicitly noted §0b: cardinality will grow to 500–1,000+ as judiciary/healthcare/water/crime/education-deep/welfare/local-govt-finance ingest. Three-round agent debate (Round 1: 5/6 picked (b) facet-explode, Gregor picked (c) dimensions:MAP; Round 2: Gregor conceded; all 5 R2 agents accepted Hans+Max as data-shape authority). User signed off on R2 residuals:
  - D26 facet-explode with parent+children + selective rule.
  - D27 entity tiering: single `entity_id` + `entity_type` enum (Max yielded; preference logged).
  - D28 methodology_version: compose Hans (FK breaks table) + Fowler (id-encoded variants) — both, they don't conflict.
  - D29 catalogue column shape with `parent_indicator_id` + `dimension_values:STRUCT` + per-child `source_id`.
  - D30 naming convention `<entity>-<measure>-<unit>-<facet>` kebab-case ≤60 chars.
  - D31 registered `taxonomy/facet-axes.json` rejects unknown dimension keys.
  - D32 chart-shell view-model adds `breaks: [{period_seq, methodology_version, note}]` visible at rest.
  - D33 eight governance answers locked (GSDP rebase as methodology_version; distribution losses one parent + facet; crime count AND rate as facets; Census vs NFHS = two parents; derived indicators first-class; voter turnout GE/AE two parents; CPI combined as facet value; fuel_type=total compute-on-read).
  - D34 consolidation as one-shot dated migration script (not permanent module).
  - D35 consolidation tests: unit + integration, skip golden-byte.
  - D36 deletion ledger format with JSON `replacement_facet_values` column.
  - R26 (c) dimensions:MAP rejected. R27 (ii) separate geo/fiscal columns rejected. R28 permanent consolidator module rejected. R29 golden-byte rejected. R30 own-computed crime rate rejected. R31 smoothing across methodology break rejected.
  - §0a NEW: This-is-THE-plan-document section + input-artifact list.
  - §0b NEW: Cardinality-is-a-moving-target section enumerating not-yet-ingested domains.
  - §0c NEW: Boundaries-preservation reinforcement (do not delete, do not move).
  - §13 rewritten; §13a NEW: copy-paste handoff prompt for next agent.

---

## See also

- [`CLAUDE.md`](../CLAUDE.md) — engineering contract (authoritative).
- [`docs/agents/guardrails.md`](../docs/agents/guardrails.md) — rules digest.
- [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md) — target architecture (TO BE WRITTEN Phase 0).
- [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) — full rationale (TO BE WRITTEN Phase 0).
- OWID ETL repo — pattern source for meadow/garden/grapher naming + `origin.*` schema.
