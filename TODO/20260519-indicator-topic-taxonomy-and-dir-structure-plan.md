# Indicator topic taxonomy + dir-structure plan

> **STATUS (updated 2026-05-19 post-user-review)**: ⊘ **SUPERSEDED AS A PLAN — RETAINED AS DEBATE TRANSCRIPT.** The live design has been folded into [TODO/20260517-canonical-long-format-pivot.md §0e](20260517-canonical-long-format-pivot.md) (sequencing + override decisions) and [docs/architecture/data/canonical-store.md §2b](../docs/architecture/data/canonical-store.md) (full target tree as contract surface). User overrides applied: (1) **Option B in one shot** for persons fork — `dim_candidates` → `dim_persons` + `elections_candidacies` fact + `governments_office_holdings` fact, day-one `person_id` rule per Max (hybrid B-ii + TCPD seed); (2) entity slug = **`office_bearer`** not `public_servant`; (3) topic slug = **`governance`** not `accountability`. Authority for all data-shape / OWID / structural questions consolidated to **Max** per CLAUDE.md §0a + user direction 2026-05-19. **Do not edit this doc** — it is preserved as the record of the 3-agent design conversation that produced the live decisions. Edit `canonical-long-format-pivot.md §0e` or `canonical-store.md §2b` instead.

**Date**: 2026-05-19
**Status (original)**: ⏳ PROPOSED — awaiting user sign-off before any PR ships
**Correction level**: 4 (structural, 4+ files, cross-cutting per CLAUDE.md §6 — "Propose breakdown first")
**Agents consulted**: Hans (Governance), Max (Indicator Scout / OWID), Fowler (Engineering) — dispatched in parallel as read-only subagents on 2026-05-19
**Replaces**: nothing (this is the long-arc design ahead of Phase 2 of the canonical pivot)
**Feeds**: [TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md) Phase 2 (per-family pivot); the eventual PR-S.1/S.2 (people fold)
**Authority (CLAUDE.md §0a)**:
- Data shape (entity taxonomy, indicator identity, topic axis) → **Hans + Max**
- Contract / integration (schema versioning, write seams, layer boundaries) → **Gregor** (not dispatched this round — out of scope)
- Engineering craft (refactor path, naming, dir structure, deletion discipline) → **Fowler**
- UX (citizen-facing titles vs slugs) → **Jony** (not dispatched — Hans covered the citizen-readable framing piece directly)
- **User approval supersedes every agent.** Nothing below ships without an explicit "yes" on each PR in §10.

---

## 1. The question (verbatim from user)

> "The whole idea of this app is to know how are we being governed, is the money I'm paying taxes is put to good use, is the government doing the job of a government?"

> "I'm very particular in having detailed aspects of budget at a granular level, at panchayat level and government projects."

> "We may have done about 10 to 20% of the indicators and the domains that we wanted to do and there is remaining 80% still left out. I want to have that normalization or generalization possible in the directories so that we don't explode in directories but at the same time we find a right home for most of them."

> "Wherever in doubt, follow the OWID purity. So if you need to extend candidates as persons, go ahead and do that."

The five concrete asks distilled from the request:
1. **Topic taxonomy**: where do Poverty / Technology / Inflation / Diseases fit? OWID puts Poverty under BOTH Economy and Living Conditions — yen-gov's current single-parent dir can't represent that.
2. **Panchayat budgets + government projects**: explicit user hot-button, no current home.
3. **Naming consistency**: `dim_` prefix exists for elections only — is that a structural smell?
4. **Persons vs Candidates**: extend `dim_candidates` with biographics, or rename to `dim_persons` + add a candidacies fact table?
5. **Office bearers / governments**: what's the canonical Indian term and where do they live?

Plus an implicit sixth: **the next 80% of indicators must not explode the directory tree**.

---

## 2. OWID Topic Center Management — verbatim from user screenshots

User shared 7 screenshots from OWID's Topic Center Management admin panel. Recorded here (per user direction "Just document that information somewhere in the plan") to anchor the taxonomy debate.

| # | Category | Articles | Sub-topic chips (in display order) |
|---|---|---:|---|
| 1 | **Health** | 11 | Child health · Communicable diseases · Diseases · Maternal health · Mortality · Nutrition · Births · Food · Road accidents · Infant mortality |
| 2 | **Economy** | 12 | Industry · Economic growth · Manufacturing · Food · Household spending · Services · Agriculture · Banking · Inflation · Poverty · Regional differences |
| 3 | **Living Conditions** | 14 | Amenities · Education · Enrolment · Higher education · Poverty · Technology · Assets · Economic growth · Household spending · Literacy |
| 4 | **Work** | 11 | Employment · Female employment · Industry · Services · Self-employment · Agriculture · Manufacturing · Unemployment · Wages · Higher education |
| 5 | **Law** | 3 | Courts · Crime |
| 6 | **Climate** | 3 | Agriculture · Rainfall |
| 7 | **Measurement** | 17 | Employment · Migration · Population growth · Diseases · Female employment · Literacy · Manufacturing · Nutrition · Road accidents |

### Faceted overlaps (the load-bearing observation)

The same chip surfaces under multiple categories. This is a **faceted M:N taxonomy**, not a strict tree:

| Sub-topic | Appears under |
|---|---|
| Higher education | Living Conditions + Work |
| Poverty | Economy + Living Conditions |
| Agriculture | Economy + Work + Climate |
| Industry | Economy + Work |
| Manufacturing | Economy + Work + Measurement |
| Services | Economy + Work |
| Food | Health + Economy |
| Household spending | Economy + Living Conditions |
| Economic growth | Economy + Living Conditions |
| Employment | Work + Measurement |
| Female employment | Work + Measurement |
| Literacy | Living Conditions + Measurement |
| Nutrition | Health + Measurement |
| Diseases | Health + Measurement |
| Road accidents | Health + Measurement |

### Special case — Measurement

OWID's *Measurement* is **methodology articles** ("How is unemployment measured?", "Counting migrants is hard"), not indicator data. yen-gov equivalent is per-indicator inline `methodology` block (already folded per the 2026-05-17 v3.0 → v4.0 lift-out) + `docs/concepts/<topic>-measurement.md` prose, **not** `datasets/indicators/in/measurement/`. Max + Hans both confirmed.

---

## 3. Current yen-gov reality + the 7 naming asymmetries

### Current dir tree

```text
datasets/
  manifest.json  CHANGELOG.md  migration-ledger.csv
  schemas/                          # JSON Schemas (contracts)
  taxonomy/                         # registries — mixed JSON + Parquet
    entities.json
    indicators.json
    parties.json
    sources.parquet
    facet-axes.parquet
  boundaries/in/...                 # geometry (sibling family, ADR-0031)
  elections/                        # CANONICAL family — pivoted (PR-Q, PR-R series)
    election_results.parquet        # long-format fact
    dim_acs.parquet  dim_candidates.parquet  dim_parties.parquet  dim_party_alliances.parquet
    _inventory.json
    AcGenApr2016/ ... AcGenMay2026/ # legacy per-event JSON shards (Phase 2 cleanup)
  indicators/in/<topic>/<snake_id>.json  # 7 single-parent topic dirs (legacy JSON, NOT yet canonical)
    demography/  economy/  energy/  environment/  fiscal/  health/  human_development/  prices/  transport/
  governments/in/states/            # parallel JSON tree for state-government metadata
  people/AcGenApr2021/*.json        # 3,983 candidate biographics (PR-S.1/S.2 scheduled)
  reference/in/
    topic-catalogue.json            # hand-authored — powers the Topic Front Door
    indicators-completeness.json    # generated public index
    ... other ref data ...
  features/                         # unaudited
  ephemeral/                        # gitignored
  _test/                            # cleanup-pending
```

### The 7 structural smells (Fowler's enumeration)

1. **`dim_` prefix lives only in `elections/`.** `elections/dim_acs.parquet` (Kimball-style) but `taxonomy/parties.json` (NOT `dim_parties.json`) and `governments/in/states/` (NOT `dim_states.parquet`). Same conceptual layer, three different naming + format conventions.
2. **`parties` exists twice.** `taxonomy/parties.json` (editorial registry) AND `elections/dim_parties.parquet` (family-local dim). Overlapping content, two homes. **Stays by design** (see §6 §1) provided the compile is one-directional.
3. **`people/` separate from `dim_candidates`.** Biographics blob vs election-scoped row — the PR-S.1 fork.
4. **Topic baked into indicator ID.** `fiscal/outstanding_debt_pct_gsdp` — but if topics are faceted M:N, the prefix is a single-parent lie. Indicator tagged Health + Economy can't have two prefixes.
5. **`governments/in/states/` vs `taxonomy/entities.json`.** Same conceptual table (States are entities).
6. **`reference/in/topic-catalogue.json` lives in `reference/`, not `taxonomy/`.** Topic catalogue IS hand-authored taxonomy.
7. **Legacy `indicators/in/<topic>/*.json` shards** still in place — Phase 2 of the canonical pivot will move them into per-family Parquet.

---

## 4. Hans's voice — governance topic axes (verbatim distillation)

Authority per §0a: Hans owns "data shape (taxonomy choices)" jointly with Max + the governance framing.

### 4.1 The Indian-citizen question is the inverse of the OWID one

> "OWID's 7 categories are output-focused (what happens to people). The Indian citizen's question is the inverse: *did the input I paid for show up?*"

Three axes OWID lacks that yen-gov must add:

- **Scheme delivery** — MGNREGA person-days vs entitlement, PMAY sanctioned-vs-completed, PM-KISAN instalment receipts, NFSA offtake, ICDS attendance, PM-POSHAN meals served. *Delivery* is distinct from *outcome* (child stunting belongs under Health). Conflating the two is Rosling's *Single-perspective* trap.
- **Accountability & audit** — CAG state audit findings, PRS bill-tracker outputs, RTI compliance under CIC, Lokpal/CVC complaints, CAG performance audits of CSS.
- **Public-service quality** — PHC vacancy %, teacher absenteeism, NJDG court pendency, FIR-to-chargesheet ratio, PDS leakage, ration-shop uptime. *Input quality*, not spending.

**Hans's topic-axis proposal**:
- Promote **`schemes`** ("Where the money goes") as a new top-level topic.
- Promote **`accountability`** ("Audits & accountability") as a new top-level topic.
- Consider future split of `human_development` → `health` + `education` (each has its own scheme universe — Samagra Shiksha / UDISE+ / ASER for education).

### 4.2 Fiscal-federalism layer

Centre / State / District / Block / Panchayat / ULB / Ward is **orthogonal to topic**, not a sub-axis. Same "Health expenditure" indicator exists at every layer.

**Pick (a): a `geo_level` column on every observation row**, with `entity_id` carrying the **LGD code** (Local Government Directory, MoPR — `state_code` → `district_code` → `block_code` → `gp_code` → `village_code`; ULBs have their own LGD branch). ECI AC codes stay as a parallel axis for electoral entities.

Rationale: matches OWID's long-format observations + entities-table pattern (per §0a); same indicator at six layers = one indicator with six rows, not six indicators; explicit `geo_level` beats implicit prefix-decoding for DuckDB filter pushdown.

### 4.3 Panchayat budgets + government projects (user hot-button)

Canonical Indian publishers, cadence, topic home:

| Publisher | What | Cadence | Topic |
|---|---|---|---|
| **e-GramSwaraj** (MoPR) | GP-level receipts/payments by scheme; PFMS-linked; ~2.5L of 2.6L GPs | near-daily push | `schemes` + `local_govt_finance` |
| **PFMS** (CGA, MoF) | Every Centre-funded rupee, beneficiary-level | real-time | `schemes` |
| **PMGSY OMMAS** | Habitation-wise rural road sanction → award → completion | quarterly | `schemes` |
| **PMAY-G AwaasSoft / PMAY-U** | House-wise sanction → instalments → geotag | monthly | `schemes` |
| **Union Budget Expenditure Profile** (Stmt 4A CSS + 4B Central Sector) | Scheme-wise BE/RE/Actuals | annual (Feb) | `fiscal` (totals) + `schemes` (per-scheme rows) |
| **CAG State Finance Audit + Local Bodies Audit** | The ONLY audit of UC truthfulness | annual, lagged 18–24m | `accountability` |

> "The user's 'panchayat budget' hot button is served by e-GramSwaraj + SFC transfers + CAG Local Bodies audits — three publishers, three lifecycles; one `schemes` topic doesn't suffice, which is why `accountability` must exist as a sibling."

### 4.4 Office bearers — canonical Indian term

**Pick: `public_servant`** as the entity-type slug. Statutory Indian umbrella under IPC §21 + Lokpal & Lokayuktas Act 2013 §14 — covers PM, CM, MLA, MP, Mayor, Sarpanch, ZP chair, IAS/IPS/state cadre in any posting. Breadth is the point.

Attributes:
- `role` (CM, MLA, Collector, …)
- `tenure_start`, `tenure_end`
- `office_type ∈ {elected, appointed_political, civil_service, statutory_authority}`
- `place` (LGD-coded)

**Rejected synonyms**:
- "Government servant" (DoPT CCS rules) — excludes elected reps.
- "Office bearer" — RWA/society-coded, not statutory.
- "Public functionary" — admin-jargon without statutory backing.

Tenure overlap allowed (one person concurrently Collector + DM + DRDA CEO = three role rows, one person row). Matches OWID's entity-as-attribute pattern.

### 4.5 Comparability traps

Per-indicator inline `methodology` block (already folded in schema v4) is where breaks are annotated — *that is where the citizen lands*. "Measurement" as a topic is an OWID artefact for *meta-academic* questions; in India the breaks are *publisher-driven* and belong next to the rupee, not in a topic ghetto.

Breaks that MUST surface inline as `series_break[]` + as a vertical rule on every chart:
- **PLFS replacing NSS-EUS** (2017–18)
- **CES suppression then resumption** (2011–12 → 2022–23 gap)
- **GSDP base-year 2011-12 → next revision** (forthcoming)
- **2021 Census delay → population denominators now NITI projections**, not enumerated
- **FY vs CY** conflation
- **₹-crore vs USD-billion** magnitude error (Rosling's *Size* instinct)

For state-vs-Centre disagreement (state DES GSDP vs MoSPI) — publish both, don't pick.

### 4.6 "Money & debt" vs "Fiscal" — keep both

**Slug = stable machine id** (`fiscal`, `schemes`, `accountability`, `economy`) — never renamed, never displayed, FK target.
**Title = citizen string** (`Money & debt`, `Where the money goes`, `Audits & accountability`, `Economy`).

> "OWID's one-word chips work for an OECD audience because the topic *is* the indicator family; for an Indian citizen, 'Fiscal' reads as IAS-jargon and 'Money & debt' reads as 'this is about me.'"

Adopt OWID's **two-layer pattern** (stable slug + display name resolved through entities/topics table). Keep yen-gov's Indian-citizen voice on the display layer.

---

## 5. Max's voice — OWID alignment + coverage gap

Authority per §0a: Max owns indicator identity + discovery + OWID precedent.

### 5.1 OWID's actual indicator identity scheme

- Citizen URL: `/grapher/<opaque-slug>` (e.g. `/grapher/child-mortality`, `/grapher/gdp-per-capita-worldbank`).
- **Topics are never in the URL.** They live as metadata tags.
- Backing model:
  - `variables` — one row per indicator: `id, name, slug, unit, dataset_id, source_id, display, presentation` (no topic column).
  - `entities` — `id, name, code`.
  - `origins` / `sources` — provenance (yen-gov already adopts `origin.*` verbatim per §0a).
  - `tags` + `chart_tags` — **M:N join table; the Topic Center the user screenshotted edits THIS table.**

> "The indicator row does NOT carry topic-tags as columns; tags are a separate join table."

### 5.2 Faceted vs single-parent

**Pick (b): separate `indicator_topic_tags` join table (M:N)** — columns `(indicator_id, topic_id, is_primary)`. Same shape as OWID's `chart_tags`. `is_primary=true` per indicator preserves a back-compat single-parent URL while every other topic is a co-tag.

**Rejected**:
- `topic_tags: list[str]` array column on the indicator row — loses referential integrity to the topic catalogue, breaks fast topic→indicator reverse-lookups in DuckDB (would need `UNNEST` everywhere), and the moment topics need attributes (order, blurb, icon, parent — they will) you regret the array. Early OWID grapher tried this and migrated off.
- Nested topic tree (`fiscal/state-finance/debt`) — single-parent in disguise.

*[Fowler's variant in §6 §3 picks the array-on-the-indicator-catalogue shape instead. See §7 for the resolution.]*

### 5.3 Coverage-breadth view of the 80% gap

| OWID category | yen-gov status | Canonical Indian publisher (issuing authority first) |
|---|---|---|
| Health — child / maternal / communicable / nutrition | partial (6 in) | **NFHS** (IIPS, 5-yearly) · **HMIS** (MoHFW monthly) · **SRS** (RGI annual) · **CRS** for births/deaths |
| Living Conditions — amenities (water, sanitation, electricity, cooking fuel) | full gap | **NFHS** household module · **NSS Housing Condition** (78th rd) · **JJM / SBM** dashboards |
| Living Conditions — education / literacy / enrolment / higher ed | full gap | **UDISE+** (school) · **AISHE** (higher ed) · **ASER** (learning outcomes, silver) · Census/NSS literacy |
| Work — employment / unemployment / wages / female participation | full gap | **PLFS** (NSO quarterly + annual) · **NSS-EUS** (legacy, methodology break vs PLFS) · CMIE-CPHS (silver, paywalled) |
| Law — crime / courts / prisons | full gap | **NCRB** *Crime in India* + *Prison Statistics India* · **India Justice Report** (Tata Trusts, silver) · DAKSH eCourts |
| Climate — rainfall / temperature | partial (AQ in) | **IMD** (daily + sub-divisional monthly) · MoEFCC · ISRO Bhuvan land-cover |
| Economy — poverty / inflation / household consumption / banking | partial (RBI fiscal in) | **HCES 2022-23** (NSO, just released — MAJOR, replaces 12-yr poverty gap) · MoSPI CPI/WPI · RBI HBS-IS · NITI MPI |
| Technology — telecom / device ownership / internet | full gap | **TRAI** quarterly performance reports · **NFHS** ICT module |
| **Panchayat-tier finance + central scheme delivery** | full gap | **eGramSwaraj / PriaSoft** (MoPR) · 15th FC grant flows · State Finance Commission reports · **MGNREGA / PMAY-G / JJM / PMGSY** dashboards |

> "Pillar-level reading: **People** (health / education / work / amenities) is the biggest hole — and it is exactly where 'is the government doing its job?' lives. Prioritise NFHS-5 + PLFS + UDISE+ + NCRB before anything fancier."

### 5.4 Measurement is doc-tier, not data-tier — confirm

Confirmed. Methodology = `docs/concepts/<topic>-measurement.md` + the per-indicator inline `methodology` block (already folded per v4.0). Do NOT create `datasets/indicators/in/measurement/`. Same lifecycle problem the v3.0 → v4.0 lift-out solved.

### 5.5 Persons vs Candidates — Max picks (B)

> "Modi is the same person who was Gujarat CM 2001–14 and PM 2014–now; 'candidate' is one role he plays in a specific (election, constituency) slot."

**Max picks (B)**: rename to `dim_persons` + add `candidacies` fact table linking person → (election_id, constituency_id, party_id, vote_share, won). Matches OWID's **entity-vs-observation pattern**.

Rejected **(A) extend `dim_candidates` with biographic fields**: every re-contesting person duplicates DoB / education / criminal record across rows; the dimension stops being a dimension; "show me this person's entire political career" degrades to a string-match heuristic instead of an FK join.

**Bonus from (B)**: `office_holdings` (PM, CM, MLA, MP, Mayor, Sarpanch tenures) lands as a *sibling* fact table keyed on the same `person_id` — Hans's "public_servant" question gets a clean home without further schema reshape.

Canonical terms to adopt: **person** for the entity, **role** for what they hold (candidacy / office_holding / party_position are role sub-types).

*[Fowler picks (A) in §6 §4 for smallest-reversible-step reasons. See §7 for the resolution.]*

### 5.6 Indicator-id naming

**Pick (a): drop the topic prefix entirely → flat opaque indicator ids** with OWID-style source-disambiguator suffix when concept-collisions arise (`literacy-rate-census` vs `literacy-rate-nfhs`; `gdp-per-capita-rbi` vs `gdp-per-capita-mospi`).

- Hyphens for citizen-facing URLs (OWID convention); snake_case stays inside Parquet column names only.
- Makes the id **stable across topic-taxonomy re-shuffles** (topic-catalogue is already at v1.2; the M:N model from §5.2 makes future re-organisation a tag-table UPDATE, not a file rename).

**Rejected (b) `<family>/<id>` where family is the source-domain (`census/literacy_rate_pct`)**: source-family prefixes drift into being topic-prefixes (citizens read `rbi/` as "fiscal/banking topic", `nfhs/` as "health topic"), quietly recreating the single-parent problem §5.2 just solved. Keep `source_family` as a **queryable metadata field**, not a URL segment.

> "OWID precedent is unambiguous: `gdp-per-capita-worldbank` puts the source in a suffix, never a prefix, and never as a directory above the slug. The current `fiscal/outstanding_debt_pct_gsdp` is a 6-character prefix that has cost us this entire conversation; flatten it now while the catalogue is at 10–20% of target, not at 80%."

---

## 6. Fowler's voice — dir structure + naming + refactor path

Authority per §0a: Fowler owns engineering craft, refactor safety, module structure.

### 6.1 ONE naming convention for the whole tree

Extending [canonical-store.md §2a](../docs/architecture/data/canonical-store.md) verbatim, then generalising:

> **Inside `datasets/<family>/`**: facts are `<family>_<role>.parquet`, dims are `dim_<entity>.parquet`.
> **Inside `datasets/taxonomy/`**: registries are flat `<role>.parquet` (directory IS the role).
> **Hand-authored taxonomy** is `<role>.json` text source-of-truth alongside a compiled `<role>.parquet` (per D18 + §8.3 Python seed in the canonical-store doc).
> **Geometry** is a sibling family at `datasets/boundaries/<region>/<format>/<layer>.<ext>` (D25, never Parquet).
> **Control-plane operator state** lives at `datasets/_ops/<role>.parquet`.
> **Contracts** live at `datasets/schemas/<name>.schema.json`.
> **There are no other top-level concept dirs.**

Applied to the 7 asymmetries:

| # | Smell | Resolution |
|---|---|---|
| 1 | `dim_` only on elections | **Collapses.** Every family with slow-changing entity attributes gets `dim_*.parquet` once that family pivots. `dim_` is a Kimball join-locality marker, not an election-ism. |
| 2 | `parties` twice | **Stays by design.** `taxonomy/parties.json` is editorial registry; `elections/dim_parties.parquet` is family-local denormalised dim including `recognition_at_event`. One-way compile, taxonomy → dim. |
| 3 | `people/` vs `dim_candidates` | **Collapses.** Fold biographics into `dim_candidates` (Option A, see §7). `people/` dies. |
| 4 | Topic in indicator ID | **Collapses.** Drop prefix; topics become `topic_tags[]` on the catalogue row. |
| 5 | `governments/in/states/` vs `taxonomy/entities.json` | **Partial collapse.** State identity → `taxonomy/entities.parquet`. State-government facts (CM terms, office-bearer tenures) → `governments/governments_office_bearer_terms.parquet`. |
| 6 | `reference/in/topic-catalogue.json` | **Collapses.** Lives at `taxonomy/topics.json` + compiled `taxonomy/topics.parquet`. `reference/` tree retires. |
| 7 | Legacy `indicators/in/<topic>/*.json` | **Collapses with the canonical pivot itself** (Phase 2 of [TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md)). Dir restructure rides Phase 2's family-by-family pivot. |

What *stays* asymmetric and why: `boundaries/` (sibling family, ADR-0031, geometry isn't tabular); `schemas/` (contracts, not data); `_ops/` (control plane); `_test/` (deletes in step 1).

### 6.2 Proposed target dir tree (Fowler — §8 below renders the full annotated tree)

### 6.3 Faceted topic representation

**Fowler picks (b): primary single-parent dir by publisher family + `topic_tags[]` on `taxonomy/indicators.parquet`** (catalogue row, NOT observation row).

Rationale: the file system is single-parent; OWID's faceted topic model is multi-parent metadata over a single physical home. Honest physical home = **publisher / source family** (fiscal, energy, health, judiciary) — where row grain, schema version, cadence, partition size cluster. The axis that doesn't drift. Topics drift (Hans may rename "Living Conditions" → "Quality of life"; Max may add "Welfare"). Storing topics as `topic_tags[]: string[]` on the catalogue row = O(N catalogue rows) update on rename, not O(N file-tree moves).

**Rejected**:
- **Symlinks** — Windows + git-on-Windows brittle (see /memories/lessons.md PR-R.1 §8 instinct).
- **Topic-less flat dir of all indicators** — loses the size-and-partition story; breaks the family-as-storage-axis decision.
- **Duplicate the file in every relevant topic dir** — guaranteed drift, two `source_id` chains, every emit doubles.

### 6.4 Persons vs Candidates — Fowler picks (A)

**Pick (A): extend `elections/dim_candidates.parquet` with optional bio columns.**

Cost: one schema bump on `datasets/schemas/dim-candidates.schema.json` (minor, additive optional columns), one parquet rewrite, one paired `DimCandidate` TS widening (Tier-A pair per /memories/lessons.md 2026-05-16 #1), one deletion of `datasets/people/AcGenApr2021/`. Ships as ONE fused atomic commit (per /memories/lessons.md 2026-05-17 — schema + io + ripped artifacts + TS + tests together, because strict `$schema_version == x-version` rejects mid-state).

**Is Option B reachable from Option A later? YES — Expand → Migrate → Contract:**

1. **Expand**: schema-bump `dim_candidates` adds optional `person_id` column; compiler leaves it NULL.
2. **Migrate**: populate `person_id` via dated one-shot script; add `taxonomy/persons.parquet`; add `elections/elections_candidacies.parquet` fact; frontend grows `/person/<id>` route.
3. **Contract**: once every row has `person_id != NULL`, alias `dim_candidates` → `dim_candidacies` and drop bio columns that moved to `dim_persons`.

A's only irreversibility risk is "we shipped a bio field on `dim_candidates` we later wish lived on `dim_persons`." That's a column move inside the family — cheap, mechanical, no consumer outside this repo.

**Fowler: "A wins by smallest-reversible-step."**

### 6.5 Entities under the one rule

| Concept | Identity (taxonomy registry) | Family-local Kimball dim (denormalised) | Facts |
|---|---|---|---|
| States / UTs | `taxonomy/entities.parquet` (`entity_type='state'`), from `entities.json` | n/a (states joined across all families) | every family's `<family>_*.parquet` via `entity_id` |
| Districts / ULBs / panchayats | `taxonomy/entities.parquet` (`entity_type='district' \| 'ulb' \| 'panchayat'`), compiled from LGD | per-family when join-locality demands (e.g. `local_govt_finance/dim_panchayats.parquet`) | `local_govt_finance/local_govt_finance_panchayat_budgets.parquet` |
| Constituencies (ACs / PCs) | `taxonomy/entities.parquet` (`entity_type='constituency'`), compiled from ECI | `elections/dim_acs.parquet` (already exists — keep) | `elections/election_results.parquet` |
| Parties | `taxonomy/parties.json` + `taxonomy/parties.parquet` | `elections/dim_parties.parquet` (event-scoped recognition) | facts via `party_id` |
| Persons (candidates today) | `taxonomy/entities.parquet` (`entity_type='person'`) **when Option B lands** | `elections/dim_candidates.parquet` (today) → `dim_candidacies` later | `election_results.parquet` |
| Offices (PM, CM-S22, MLA-IN-S22-AC-2008-167) | `taxonomy/entities.parquet` (`entity_type='office'`) | `governments/dim_offices.parquet` | `governments/governments_office_bearer_terms.parquet` |
| Schemes / projects | `taxonomy/entities.parquet` (`entity_type='scheme'`) | `schemes/dim_schemes.parquet` | `schemes/schemes_*.parquet` |

**The rule that resolves "where does X live"**: identity = taxonomy; denormalised join projection per family = `dim_<entity>`; behaviour over time = fact in `<family>/<family>_<role>.parquet`.

Office-bearers are **facts** (event-time "who held office X from Y to Z"), not dims — sits in `governments/governments_office_bearer_terms.parquet`. Office *identity* (CM-S22 as a slot) is a taxonomy entity; office *occupancy* is a fact.

### 6.6 Smell catalogue — Fowler will VETO

1. **Symlinks under `datasets/`** to express multi-topic membership.
2. **Per-topic duplicate physical files** of the same indicator.
3. **Keeping `<topic>/<id>` as the indicator_id shape** after the topic prefix is dropped.
4. **Renaming `dim_candidates` → `dim_persons` in the same commit that adds bio fields.** Two-hats violation.
5. **Adding `taxonomy/dim_states.parquet`.** `dim_` is a family-local marker; `taxonomy/entities.parquet` is correct.
6. **A top-level `office_bearers/` family parallel to `governments/`.** Office-bearer tenures ARE government facts.
7. **Hand-authoring bio columns directly into the `dim_candidates` Parquet rows.** Hand-authored editorial fields → JSON sidecar that compiles in (D18 + §8.3). Adapter-compiled → adapter writes. Never hand-edit the Parquet.
8. **Putting `topic_tags[]` on the observation row instead of the indicator catalogue row.** Topic is a property of the indicator (slow-changing, 110 → 1000 rows), not the observation (millions of rows).
9. **A "big bang" rename PR** touching paths in `manifest.json`, `frontend/src/lib/data.ts`, `frontend/src/lib/duckdb.ts`, schema `$id`s, and adapter writers simultaneously.

---

## 7. Synthesis — convergences + the one fork

### 7.1 Convergent decisions (all three agents agree)

| # | Decision | Hans | Max | Fowler |
|---|---|---|---|---|
| C1 | Topic taxonomy is **faceted M:N**, not single-parent tree | implied | ✅ explicit | ✅ explicit |
| C2 | **Drop topic prefix from indicator IDs** (`fiscal/outstanding_debt_pct_gsdp` → `outstanding-debt-pct-gsdp`) | concurs | ✅ explicit | ✅ explicit |
| C3 | One naming convention: `<family>/<family>_<role>.parquet` facts, `<family>/dim_<entity>.parquet` dims, `taxonomy/<role>.parquet` registries | concurs | concurs | ✅ explicit |
| C4 | **Measurement = doc-tier prose + inline methodology block**, NOT a topic dir | ✅ explicit | ✅ explicit | n/a |
| C5 | Lift `reference/in/topic-catalogue.json` → `taxonomy/topics.json` + compiled `taxonomy/topics.parquet` | concurs | concurs | ✅ explicit |
| C6 | Two-layer naming: stable slug (machine id) + display title (citizen string) | ✅ explicit | concurs | concurs |
| C7 | Office-bearer entity = **`public_servant`** (statutory IPC §21 + Lokpal Act umbrella); occupancy is a fact, identity is taxonomy | ✅ explicit | concurs (entity-as-attribute) | ✅ explicit (governments fact table) |
| C8 | Fiscal-federalism = `geo_level` column + LGD entity_id, NOT per-layer fact tables | ✅ explicit | concurs | concurs |
| C9 | Hand-authored taxonomy = JSON text source + compiled Parquet (D18 + §8.3) | concurs | concurs | ✅ explicit |
| C10 | Source-family is **queryable metadata on the indicator row**, NOT a URL segment | implied | ✅ explicit | concurs |

### 7.2 The one fork — Persons vs Candidates

| Choice | Max says | Fowler says | User's prior signal |
|---|---|---|---|
| **(A)** Extend `dim_candidates` with bio fields (existing PR-S.1 scope) | reject — biographic duplication, dimension stops being a dimension | ✅ pick by smallest-reversible-step | approved Option A in prior session |
| **(B)** Rename → `dim_persons` + `candidacies` fact + `office_holdings` fact | ✅ pick — OWID entity-vs-observation pattern; office-bearers slot in cleanly | reachable from A via Expand → Migrate → Contract | "if you need to extend candidates as persons, go ahead and do that" — leans toward B |

### 7.3 Resolution (per §0a authority assignment)

**Engineering craft authority (Fowler) governs the FIRST move**: do **A** as PR-S.1.
**Data shape authority (Hans + Max) governs the DESTINATION**: B is the documented end-state.

The path: **Expand → Migrate → Contract** (Fowler §6.4). Three PRs:

- **PR-S.1 (now)** — Option A. Add bio fields to `dim_candidates`. ALSO add an optional `person_id` column to `dim_candidates` (NULL today) so the future migration is reachable without a second schema bump. Schema bump is fused atomic per /memories/lessons.md 2026-05-17.
- **PR-Persons (later, after cross-election person-identity signal exists)** — Migrate step. Create `taxonomy/persons.parquet`. Backfill `dim_candidates.person_id` via dated one-shot script. Add `elections/elections_candidacies.parquet` (forward-facing fact for new schema consumers).
- **PR-Persons-Contract (after every consumer reads via person_id)** — Alias `dim_candidates` → `dim_candidacies`. Drop bio columns that have moved to `dim_persons`. Add `governments/governments_office_bearer_terms.parquet` fact, keyed on `person_id`, for the public_servant entity.

User's "extend candidates as persons" instruction is honoured by **B as the named destination**. The smallest-reversible-step from A → B is the responsible path; B-in-one-shot pre-builds for a join (cross-election person identity) we don't yet have data to populate. Fowler explicitly veto'd "renaming `dim_candidates` → `dim_persons` in the same commit that adds bio fields" (§6.6 #4).

If user prefers the one-shot B path instead, this plan needs §10's PR-S.1 row rewritten and an additional discussion of how `person_id` gets populated on day one without ECI affidavit fingerprinting.

### 7.4 Sub-fork — topic-tag storage shape

Max picked **(b) separate join table `(indicator_id, topic_id, is_primary)`** (OWID `chart_tags` shape).
Fowler picked **(b) array column `topic_tags[]` on `taxonomy/indicators.parquet`** (the catalogue row).

These look like the same letter but are different shapes. **Synthesis**: store as join table in canonical (`taxonomy/indicator_topic_tags.parquet`) for referential integrity + reverse-lookup speed; surface as denormalised array column on `taxonomy/indicators.parquet` for cheap UI reads. The join table is the source of truth; the array is the compiled projection. Same D18 + §8.3 hand-source → compiled-parquet pattern.

---

## 8. Proposed target dir tree

```text
datasets/
  manifest.json                           # control plane (D21)
  CHANGELOG.md  migration-ledger.csv

  schemas/                                # JSON Schemas — contracts
    observation.schema.json  indicator.schema.json  ...

  taxonomy/                               # REGISTRIES (identity, slow-changing)
    entities.json    entities.parquet     # hand source + compiled (D18 + §8.3)
                                          #   entity_type ∈ {state, district, block,
                                          #                  panchayat, ulb, ward,
                                          #                  constituency, person,
                                          #                  party, office, scheme}
    indicators.json  indicators.parquet   # catalogue + denormalised topic_tags[] projection
    indicator_topic_tags.parquet          # M:N join (Max §5.2) — source of truth
    topics.json      topics.parquet       # ← lifted from reference/in/topic-catalogue.json
                                          #   new top-level topics: schemes, accountability
                                          #   (Hans §4.1)
    parties.json     parties.parquet
    persons.parquet                       # NEW once PR-Persons (B) lands; empty today
    sources.parquet                       # adapter-generated, no JSON source
    facet-axes.parquet                    # compiled from facet_axes_seed.py
    methodology_breaks.json  ...parquet   # series breaks Hans §4.5 listed
    caveats.json             ...parquet
    delimitation_lineage.parquet

  boundaries/                             # SIBLING family (D25, ADR-0031) — geometry
    in/geojson/...  in/pmtiles/...

  elections/                              # CANONICAL family — politics
    election_results.parquet              # fact
    dim_acs.parquet                       # constituency dim
    dim_candidates.parquet                # candidate dim (becomes dim_candidacies post-PR-Persons-Contract)
    dim_parties.parquet                   # event-scoped party recognition
    dim_party_alliances.parquet
    elections_candidacies.parquet         # NEW post-PR-Persons: person × contest fact

  governments/                            # CANONICAL family — institutions
    governments_office_bearer_terms.parquet  # fact: PM/CM/MLA/Collector/Sarpanch tenures
                                             # (Hans §4.4 public_servant model)
    dim_offices.parquet                   # PM-IN, CM-S22, MLA-<ac_id>, Collector-<dist_lgd>, ...

  schemes/                                # NEW top-level (Hans §4.1) — "Where the money goes"
    schemes_mgnrega_person_days.parquet   # one fact per scheme × metric
    schemes_pmay_g_sanctions.parquet
    schemes_pm_kisan_disbursements.parquet
    schemes_pmgsy_road_completions.parquet
    schemes_nfsa_offtake.parquet
    dim_schemes.parquet                   # scheme identity + scheme_type + parent_ministry

  accountability/                         # NEW top-level (Hans §4.1) — "Audits & accountability"
    accountability_cag_audit_findings.parquet
    accountability_rti_compliance.parquet
    accountability_prs_bill_tracker.parquet
    accountability_cic_complaints.parquet

  local_govt_finance/                     # NEW (Hans §4.3) — user's panchayat-budget hot button
    local_govt_finance_panchayat_budgets.parquet      # from e-GramSwaraj
    local_govt_finance_15thfc_grant_flows.parquet
    local_govt_finance_sfc_transfers.parquet
    local_govt_finance_cag_local_bodies_audit.parquet
    dim_panchayats.parquet                # LGD-coded panchayat dim

  fiscal/                                 # Phase 2 pivot target (already populated as JSON today)
    fiscal_state_finances.parquet
    fiscal_centre_transfers.parquet
    fiscal_union_deficit.parquet
    fiscal_state_own_revenue.parquet
    dim_fiscal_heads.parquet

  energy/                                 # Phase 2 pivot target
    energy_installed_capacity.parquet
    energy_generation.parquet
    energy_distribution_performance.parquet  # ATC losses, AT&C, billing/collection efficiency
    dim_plants.parquet
    dim_discoms.parquet

  health/                                 # Phase 2 pivot target — expand massively per Max §5.3
    health_births_deaths.parquet          # CRS/SRS
    health_disease_surveillance.parquet   # HMIS, IDSP
    health_nfhs_indicators.parquet        # NFHS-5 + future rounds
    health_public_expenditure.parquet
    dim_health_facilities.parquet         # PHC/CHC/sub-centre

  education/                              # Phase 2 pivot target — new family (split from human_development)
    education_udise_school_metrics.parquet
    education_aishe_higher_ed.parquet
    education_aser_learning_outcomes.parquet
    education_literacy.parquet

  demography/                             # Phase 2 pivot target
    demography_population.parquet
    demography_age_structure.parquet
    demography_migration.parquet
    demography_sex_ratio.parquet

  economy/                                # Phase 2 pivot target
    economy_gdp_gva.parquet
    economy_household_consumption.parquet  # HCES 2022-23 (Max §5.3 MAJOR)
    economy_poverty.parquet                # NITI MPI + HCES-derived
    economy_inflation.parquet              # CPI/WPI

  work/                                   # NEW family per Max §5.3 — full gap today
    work_plfs_employment.parquet
    work_plfs_unemployment.parquet
    work_wages.parquet
    work_female_lfpr.parquet

  judiciary/                              # NEW (Max §5.3 Law gap)
    judiciary_njdg_pendency.parquet
    judiciary_njdg_disposal.parquet

  crime/                                  # NEW (Max §5.3 Law gap)
    crime_ncrb_ipc.parquet
    crime_ncrb_sll.parquet
    crime_ncrb_prisons.parquet

  amenities/                              # NEW (Max §5.3 Living Conditions gap)
    amenities_water_jjm.parquet
    amenities_sanitation_sbm.parquet
    amenities_electricity_access.parquet
    amenities_cooking_fuel.parquet

  technology/                             # NEW (Max §5.3)
    technology_trai_telecom.parquet
    technology_nfhs_ict.parquet

  environment/                            # Phase 2 pivot target
    environment_air_quality.parquet       # AQ already in
    environment_ghg_emissions.parquet
    environment_water_quality.parquet

  prices/                                 # Phase 2 pivot target
    prices_cpi.parquet
    prices_wpi.parquet
    prices_food_retail.parquet

  transport/                              # Phase 2 pivot target
    transport_road_network.parquet
    transport_road_accidents.parquet

  human_development/                      # SHRINKS once health + education + amenities split out
    human_development_hdi.parquet         # composite indices only
    human_development_mpi.parquet

  _ops/                                   # control plane — operator-mutable, NOT citizen-facing
    operator_state.parquet                # ← lifted from taxonomy/ if it currently lives there

  ephemeral/                              # gitignored runtime

  # ----- RETIRES ENTIRELY ------------------------------------------------
  # _test/                                # cleanup-pending → deletes in step 1
  # features/                             # unaudited → audit + relocate or delete
  # indicators/in/<topic>/                # Phase 2 pivot empties these family-by-family
  # governments/in/states/                # → governments/governments_office_bearer_terms.parquet
  # people/AcGenApr2021/                  # → folded into dim_candidates (PR-S.1)
  # reference/in/                         # → taxonomy/ (editorial) or _ops/ (telemetry)
```

**Top-level families added net of today**: `schemes`, `accountability`, `local_govt_finance`, `work`, `judiciary`, `crime`, `amenities`, `technology`, `education`. **Retiring**: `_test/`, `indicators/in/`, `governments/in/`, `people/`, `reference/in/`. Net direction: more families (Hans/Max coverage breadth), fewer artificial trees (Fowler hygiene).

---

## 9. Naming convention summary (the One Rule)

| Layer | Path | Naming | Example |
|---|---|---|---|
| Contract | `datasets/schemas/<name>.schema.json` | snake_case + `.schema.json` | `dim-candidates.schema.json` |
| Taxonomy registry (identity) | `datasets/taxonomy/<role>.parquet` | flat, no `dim_` prefix | `taxonomy/entities.parquet`, `taxonomy/topics.parquet` |
| Taxonomy hand source | `datasets/taxonomy/<role>.json` | sibling to the compiled parquet | `taxonomy/topics.json` |
| Family fact | `datasets/<family>/<family>_<role>.parquet` | family-prefixed for join locality | `schemes/schemes_mgnrega_person_days.parquet` |
| Family dim | `datasets/<family>/dim_<entity>.parquet` | Kimball `dim_` prefix only inside families | `elections/dim_candidates.parquet`, `schemes/dim_schemes.parquet` |
| Geometry | `datasets/boundaries/<region>/<format>/<layer>.<ext>` | sibling family, not Parquet | `boundaries/in/geojson/states.geojson` |
| Control plane | `datasets/_ops/<role>.parquet` | underscore-prefix marks operator-mutable | `_ops/operator_state.parquet` |
| Citizen URL slug | hyphens, no topic prefix | OWID convention | `outstanding-debt-pct-gsdp`, `gdp-per-capita-mospi` |
| Parquet column | snake_case | always | `value_numeric`, `period_label` |
| Topic slug (machine) | snake_case | stable, never displayed | `fiscal`, `schemes`, `accountability` |
| Topic title (citizen) | Title Case | Indian-citizen voice | "Money & debt", "Where the money goes" |
| Entity type | snake_case enum | `state`, `district`, `panchayat`, `constituency`, `person`, `party`, `office`, `scheme`, `ulb` | — |

---

## 10. Migration shape — 6 strangler-fig PRs (Fowler §6.6)

Each PR independently mergeable, each reversible. **Two-hat discipline**: every PR is purely structural (paths/renames/no row content change) OR purely behavioural (schema rows change). Never both unless explicitly marked "fused atomic" per /memories/lessons.md 2026-05-17.

| # | PR | Hat | Tier-A pair? | Reversible by | Depends on |
|---|---|---|---|---|---|
| **T.1** | **Tidy first — dir hygiene.** Delete `_test/`. Create `_ops/`. Move operator state → `_ops/`. Audit `features/` (delete or document). Update `manifest.json` `path` fields. | structural | NO — paths only | `git revert` | — |
| **T.2** | **Lift topic catalogue into taxonomy.** Move `reference/in/topic-catalogue.json` → `taxonomy/topics.json`. Add `backend/yen_gov/canonical/topics_seed.py` per §8.3 of canonical-store.md. Compile to `taxonomy/topics.parquet`. Update consumers in `frontend/src/lib/`. Retire `reference/in/`. **Add new top-level topics `schemes` + `accountability`** (Hans §4.1) in same commit. | structural | YES — paired test for seed module | `git revert` + rerun compile | T.1 |
| **T.3** | **Indicator catalogue widens for topic tags + drops topic prefix from `indicator_id`.** Bump `datasets/schemas/indicator.schema.json` minor: add `topic_tags: string[]` (FK → `taxonomy/topics.parquet`), add `id_aliases: string[]` (one-release back-compat), enforce new id shape per Max §5.6. Migrate the 110 legacy indicators to new ids; populate `id_aliases` with old `<topic>/<id>` form; frontend renderer dereferences via alias. **Add `taxonomy/indicator_topic_tags.parquet` M:N join** (Max §5.2). Two-release later: drop aliases + topic-prefix shape from schema enum. | structural (step a) + behavioural (step b — separate commits within PR) | YES — paired TS widen on `IndicatorMeta` + Zod enum widen on `stacked-trend/types.ts`. **Fused atomic commit** for the schema bump per /memories/lessons.md 2026-05-17 ENTRY. | aliases keep both live; drop in T.6 | T.2 |
| **S.1** | **PR-S.1 Option A** — fold `people/` into `dim_candidates`. Schema bump minor on `dim-candidates.schema.json`, additive optional bio columns. **Add optional `person_id` column** (NULL today, FK forward to future `taxonomy/persons.parquet`) per §7.3. Rewrite `elections/dim_candidates.parquet`. Delete `datasets/people/AcGenApr2021/`. Fused atomic commit. | structural + behavioural (fused) | YES — `DimCandidate` TS widen | re-emit from candidates source; restore `people/` from git | T.3 |
| **G.1** | **Office-bearers consolidation.** Create `governments/governments_office_bearer_terms.parquet` (new fact). Create `governments/dim_offices.parquet`. Migrate `governments/in/states/<state>/cm_terms.json` → fact rows. Delete `governments/in/states/`. New schemas + Tier-A pair if frontend consumes (today: `cm_terms` only — check usages). | structural + behavioural (fused) | YES if frontend consumes; NO if no consumer | re-emit from `cm_terms.json` (kept in `_old/` for one release) | T.3 |
| **P.*** | **Per-family pivot** — Phase 2 of [TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md). Each family (fiscal, energy, health, education-split-out, work-new, judiciary-new, crime-new, amenities-new, technology-new, schemes-new, accountability-new, local_govt_finance-new, …) becomes its own sub-PR following the existing 1.8a-bis naming rule + FK contract. Drops `datasets/indicators/in/<family>/` per sub-PR. | structural + behavioural (fused per family) | YES per family | per-family rollback; previous sub-PR independent | T.3 |

T.1 + T.2 are pure Tidy First (worth landing first — zero behavioural risk, unblock everything else). T.3 is the largest single behavioural change; earns its own Correction Level 4 review.

**Future** (post user-signal on cross-election person identity):
- **PR-Persons-Migrate** — populate `dim_candidates.person_id`; create `taxonomy/persons.parquet`; create `elections/elections_candidacies.parquet`.
- **PR-Persons-Contract** — alias `dim_candidates` → `dim_candidacies`; drop bio columns moved to `dim_persons`.

---

## 11. New top-level topics from Hans (machine slug → citizen title)

| Slug | Title | Sub-topics (initial; expand as indicators land) |
|---|---|---|
| `schemes` | **Where the money goes** | Centrally Sponsored Schemes (CSS); Central Sector schemes (CS); State schemes; Scheme delivery (sanction → award → completion); MGNREGA; PMAY-G/U; PM-KISAN; ICDS; PM-POSHAN; NFSA |
| `accountability` | **Audits & accountability** | CAG state audit findings; CAG performance audits; PRS bill tracker; RTI compliance (CIC); Lokpal/CVC complaints; Local Bodies audits |
| `local_govt_finance` | **Panchayats & local bodies** | Panchayat budgets (e-GramSwaraj); 15th FC grant flows; SFC transfers; ULB own revenue; ZP/BP receipts-payments |
| `work` | **Work & jobs** | Employment (PLFS); Unemployment; Wages; Female labour-force participation; Self-employment; Migration for work |
| `judiciary` | **Courts** | NJDG pendency; disposal rates; eCourts metrics |
| `crime` | **Crime** | NCRB IPC; NCRB SLL; Prison Statistics India; FIR-to-chargesheet ratio |
| `amenities` | **Household amenities** | Water (JJM); Sanitation (SBM); Electricity access; Cooking fuel; Housing condition |
| `technology` | **Telecom & internet** | TRAI quarterly performance; broadband penetration; mobile subscribers; NFHS ICT module |
| `education` | **Education** | UDISE+ school metrics; AISHE higher-ed; ASER learning outcomes; literacy |

`human_development` shrinks to composite indices only (HDI, MPI) once health/education/amenities split out.

---

## 12. Coverage gap from Max — publisher priority list

Implementation order (Max §5.3 ranking — "People is the biggest hole"):

1. **NFHS-5** (IIPS, 5-yearly) — health + amenities + ICT module — single publisher, multiple topics, biggest single-pub coverage win.
2. **PLFS** (NSO, quarterly + annual) — work topic; carries the NSS-EUS methodology break (Hans §4.5).
3. **UDISE+** (school) + **AISHE** (higher ed) — education topic.
4. **NCRB** *Crime in India* + *Prison Statistics India* — crime topic.
5. **HCES 2022-23** (NSO) — economy/poverty topic; **MAJOR**, replaces a 12-year poverty-data gap.
6. **IMD** sub-divisional monthly rainfall — climate topic.
7. **e-GramSwaraj** + **PFMS** — schemes + local_govt_finance topics (user hot-button).
8. **TRAI quarterly** — technology topic.
9. **CAG State Audit + Local Bodies Audit** — accountability topic.

Each publisher = one ingest adapter under `backend/yen_gov/sources/<publisher>/`. Phase 2 PRs land in this order unless user reprioritises.

---

## 13. Cross-references

- [TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md) — Phase 2 per-family pivot is where each new family in §8 lands. This plan does NOT replace that one; it **adds** the dir-restructure + naming-rule + new-family slots to it.
- [TODO/20260517-indicator-corpus-survey.md](20260517-indicator-corpus-survey.md) — relevant for the coverage gap §12.
- [TODO/SOCIO-ECONOMIC-EXPANSION.md](SOCIO-ECONOMIC-EXPANSION.md) — Hans's new topic slots in §11 supersede whatever this file currently proposes; merge or retire after user sign-off.
- [TODO/PER-INDICATOR-DOCS-PLAN.md](PER-INDICATOR-DOCS-PLAN.md) — methodology-prose home per Hans §4.5 + Max §5.4.
- [TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md](IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) — Topic Front Door reads `taxonomy/topics.parquet` post-T.2.
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) — §2a naming rule + §8.3 hand-source → compiled-parquet pattern. This plan EXTENDS §2a, doesn't replace.

---

## 14. Open questions for user (please answer before T.1 ships)

1. **Persons-vs-Candidates fork** — confirm Option A first (per §7.3), or override and want B-in-one-shot? If B-in-one-shot, what cross-election person-identity signal do we use to populate `person_id` from day one?
2. **`human_development` split** — do we split out `health` + `education` in T.2 (Hans §4.1), or keep them under `human_development` until Phase 2 lands their first per-family indicators? Recommend split-in-T.2 so future indicators land in their final home.
3. **`schemes` granularity** — one fact table per scheme (`schemes_mgnrega_person_days.parquet`, `schemes_pmay_g_sanctions.parquet`) OR one giant `schemes_scheme_metrics.parquet` with `scheme_id` + `metric_id` columns? Recommend per-scheme tables for now (clearer partition/row-grain story), revisit if it explodes.
4. **`work` family vs `human_development`** — Hans + Max both want `work` as its own top-level family. Confirm? (Today work indicators would be filed under `human_development` by default.)
5. **`accountability` vs `governance` naming** — both terms fit. `accountability` is what Hans recommended (audit-focused); `governance` would be broader (includes service-delivery quality). Recommend `accountability` per Hans; service-quality lives under the relevant outcome topic (`health` for PHC vacancy %, `education` for teacher absenteeism, `judiciary` for NJDG pendency).
6. **`PR-S.1` timing** — earlier session was about to start PR-S.1 as part of the canonical pivot. Defer until T.1 + T.2 land (so the dir convention is set first), or run in parallel (S.1 only touches `elections/` + deletes `people/`, no taxonomy-tree dependency)? Recommend parallel.
7. **PR sequencing within Phase 2** — sub-PR order from §12 (NFHS → PLFS → UDISE+ → NCRB → HCES → IMD → e-GramSwaraj/PFMS → TRAI → CAG) — accept or reprioritise?

---

## 15. Status vocabulary applied (CLAUDE.md §0d)

| Item | Status |
|---|---|
| OWID screenshot taxonomy capture (§2) | ✅ DONE — embedded verbatim |
| 3-agent debate (§4–6) | ✅ DONE — Hans + Max + Fowler dispatched 2026-05-19, reports synthesised in §7 |
| Naming convention rule (§9) | ✅ DONE — Fowler's rule extending canonical-store.md §2a |
| Target dir tree (§8) | ⏳ NOT STARTED — proposed, awaiting user sign-off |
| 6-PR strangler-fig sequence (§10) | ⏳ NOT STARTED — proposed, awaiting user sign-off on T.1 |
| New top-level topics (§11) | ⏳ NOT STARTED — proposed, sign-off needed on §14 Q4 + Q5 |
| Persons-vs-Candidates fork resolution (§7.3) | ⏳ NOT STARTED — synthesis recommends Option A first; awaits user override per §14 Q1 |
| PR-R.2 / R.3 (psephlab canonical pivot) | ⏳ NOT STARTED — IN PROGRESS — paused per user; resumes after this plan signs off |
