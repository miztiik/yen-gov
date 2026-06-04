# Data and Charting Platform Reset for yen-gov (RATIFIED A)

**Last Updated**: 2026-06-03

> Plan formerly titled "Rip-and-Refill". Renamed 2026-06-03 to name the destination, not just the demolition: a clean LGD + OWID long-format data foundation under a reusable, geography-first, swappable-chart platform with yen-ask on top.

> Level-5 design plan. The user has **ratified direction A (aggressive rip-and-refill)** and layered 19 refinements on top of the first draft. Several refinements deliberately OVERRIDE the earlier persona verdicts; per CLAUDE.md section 0a "User approval supersedes every agent." This revision records each override and folds it into the plan.
>
> Investigation basis (all 2026-06-03, research-only): 2 Explore subagents (frontend + backend spaghetti inventory; elections + psephlab + yen-ask audit), 4 persona verdicts (Hans, Max, Fowler, Jony), and a fetch of the OWID/Gapminder long-format CSV format (`open-numbers/ddf--*`).

---

## 0. Thesis (revised)

Keep the irreplaceable assets (the DuckDB-WASM read path, the ECI parsing, the boundary/LGD/AC-PC crosswalks, the parity oracle). **Delete everything else aggressively - no strangler-fig, no migrate-then-bypass: git is the backup.** Re-ingest the mission families clean onto ONE simplified storage model. Consolidate on **LGD** (administrative geography) and **OWID** (indicator modelling + the long-format CSV storage idea). The headline destination is **yen-ask** sitting on top of a clean foundation; the **psephology lab** must be repaired, not dropped.

---

## 1. Direction: RATIFIED A + user overrides

Direction **A (aggressive rip-and-refill)** is locked. The following user refinements override prior plan/persona text:

| # | User directive | Overrides | New rule |
| --- | --- | --- | --- |
| O1 | "no strangler figging - just the new - git is the backup" | Fowler's strangler-fig verdict + old Phase 2 | Delete dead/legacy paths outright; re-ingest clean. Git history is the rollback. |
| O2 | "chart v2 was important work" | old D4 (delete V2 dupes) | KEEP the V2 chart variety. Consolidate into a reusable default-built chart library; delete only true byte-dupes. |
| O3 | provenance "even looser - all optional - producer/owner, url, title, vintage" + "leave licence out completely" | F2/Phase 4 (6-field trim, license kept) | sources = exactly 4 fields, ALL optional: `owner`, `title`, `vintage`, `url`. No license. No confidence/verification. |
| O4 | "consolidate on LGD" | scattered geography handling | LGD is the single administrative-geography spine; ECI AC/PC is the parallel electoral spine; everything joins through LGD. |
| O5 | "consolidate on OWID" + long-format CSV question | Parquet/JSON-everywhere assumption | Adopt the long-format CSV storage shape (lightweight CSV + parent/child tag CSV + long datapoint CSV). See section 3. |
| O6 | "psephology lab ... has to be fixed" | (was unscoped) | First-class repair row; verify in-browser. |
| O7 | "yen-ask is important dont remove it ... headline feature" | (was Phase-5 footnote) | yen-ask is the north star; every storage change keeps yen-ask's 4 concepts working. |
| O8 | "rather not have decisions, instead decomposed into actual locations" | ADR tier | Retire `docs/architecture/decisions/`; fold each live decision into its subsystem/concept doc. |
| O9 | "all government sources are gold - not just RBI - we take what we get, we are beggars. whether it is CAG or RBI" | F1 (single golden source) | **Any government source is gold.** No single anointed golden source. Take whatever the government publishes (RBI, CAG, ministry MIS, PIB, data.gov.in); prefer Accounts/actuals when available; gaps stay labelled, never BE/RE-filled. |
| O10 | "notes and TODO almost same" | two scratch dirs | Merge into one working-docs convention. See section 9. |

---

## 2. Doctrine freezes (Phase 0 - cheap decisions, unblock everything)

Lift each into its named `docs/` home in the same commit it is first depended on. No standalone ADRs (O8).

### F1. Fiscal: any government source is gold; prefer actuals (Hans + O9)
- **No single anointed golden source.** Every government publisher is gold - RBI *State Finances*, CAG, ministry MIS portals, PIB, data.gov.in. We are beggars: take whatever the government publishes for a given fact/year/state.
- **Preference order, not exclusivity:** when more than one government source covers the same fact, prefer **Accounts (actuals)** over Revised over Budget Estimates. Carry the actual on the canonical row; record which publisher it came from via the `owner` provenance field (section 7).
- Where no source publishes an actual for a year, that point is a **labelled gap**, never BE/RE-filled.
- BE/RE may exist only as a *separately named* indicator if a real "promise vs delivery" question demands it (subject to `check-overlap`), never a facet toggle.
- When two government sources disagree on the same actual, that is a provenance/methodology note (and possibly a methodology-break row per F6), not a facet.
- Home: new `docs/concepts/fiscal-estimate-stage.md`.

### F2. Facet legitimacy: four-gate test (Hans)
Before adding ANY facet: (1) same concept/unit/normalisation; (2) same publisher-fact (not different estimates/base-years); (3) facet values sum to a recognisable whole; (4) a real citizen question needs the split. Fail one => not a facet; default = collapse. Home: `docs/concepts/indicator-naming.md`.

### F3. Two electoral spines + admin spine; electoral-hierarchy doc fix (Hans + O4)
- Administrative geography = **LGD** ladder (state > district > sub-district > village), mutating over time. Electoral geography = **ECI AC/PC**, keyed per delimitation cycle. They are two partitions; PCs never nest into districts; AC-into-district containment held only at 2008 delimitation and decays - it is a versioned crosswalk, never an invariant.
- **Live trap to fix early:** amend `docs/concepts/electoral-hierarchy.md` ("an AC is wholly inside one district") to versioned-crosswalk language.

### F4. Granularity freeze: STATE + DISTRICT for v1 (Max)
v1 freezes at state + district grain; AC/PC and sub-district drill-down deferred to v2, family-by-family where the issuing authority publishes it.

### F5. One map engine, two boundary families, map demoted (Jony)
ONE `MapChoropleth`/`StateAcMap` engine fed by two boundary families dispatched on `entity_kind` (admin LGD vs electoral AC/PC). The **spine is the place** (breadcrumb + search + ranked list), the map is a slotted companion. Choropleth earns a hero slot only when the polygon nests cleanly, is comparable, and area does not mislead - else it falls back to ranked list + locator outline. Elections are list-first, map-as-locator.

### F6. One indicator per concept (Max)
Every `indicator_id` carries a `concept_id` FK; run `check-overlap` before minting; match >=70% => UPSERT or facet. New vintage/publisher/base-year = same id + UPSERT (+ a methodology-break row on rebase).

### F7. Computed fields are first-class (user signal)
Per-capita, %-of-GSDP, turnout etc. are computed at write time into datapoint rows with their own `concept_id` + a `derivation` note, never ad hoc in the frontend.

### F8. Storage model: long-format-CSV (O5) - see section 3.

### F9. Provenance: 4 optional fields, no license (O3) - see section 7.

---

## 3. Storage model: adopt the long-format CSV shape (the big decision)

The user's long-format-CSV references show why JSON+Parquet+60-schemas is over-fought. OWID/Gapminder's long-format CSV stores everything as flat, git-diffable CSV:

- **`topics.csv`** = 3 columns `tag, name, parent` - the entire topic tree as a parent-pointer CSV (e.g. `wdi__health__mortality` -> parent `wdi__health`). Lightweight, human-diffable.
- **`datapoints/<kind>/<variable_id>.csv`** = `entity, time, value` long format, one CSV per indicator.
- **`variables.csv`** = indicator metadata (name, unit, type).

DuckDB-WASM reads CSV natively (`read_csv_auto`), so the production read path barely changes. This is the OWID consolidation (O5) the user asked for.

### Decision (FINALIZED 2026-06-03 - Max + Hans, data-shape remit per CLAUDE.md section 0a)
Adopt a long-format-CSV CSV layout as the canonical store. Exact column sets below are the binding contract; Gregor ratifies only the read-path (DuckDB-WASM `read_csv_auto` over the `datasets/data/` tree keeping the same `query(sql)` surface).

```
datasets/data/
  variables.csv                # indicator_id, name, concept_id, unit, derivation, topic, source_id, update_period_days
  concepts.csv       # concept_id, noun, unit_canonical, normalisation, entity_kinds, description
  topics.csv         # topic, name, parent
  entities/geo.csv           # entity_id, name, parent, entity_kind                 (LGD admin ladder)
  entities/electoral.csv     # entity_id, name, entity_kind, delim_year, state, parent, reservation
  entities/electoral_lgd_xwalk.csv  # electoral_id, lgd_district_id, delim_year, boundary_snapshot, overlap_kind
  entities/party.csv         # party_id, short, full, eci_codes, brand_colour, symbol_asset, wikipedia
  entities/source.csv        # source_id, owner, title, vintage, url               (all optional except PK; section 7)
  datapoints/geo/<variable_id>.csv        # entity_id, time, value, source_id
  datapoints/electoral/<variable_id>.csv  # entity_id, time, value, source_id
```

**Catalogue = `variables.csv` (8 columns, Max verdict):**
| Column | Role |
| --- | --- |
| `indicator_id` | PK + row-key (the `<indicator>` token in every datapoint filename). Kebab `<measure>-<unit>-<facet>`, no grain prefix. |
| `name` | single citizen-facing label (collapses old `label_short`+`label_long`). |
| `concept_id` | **FK to `concepts.csv`** - the F6 one-indicator-per-concept hook; `check-overlap` keys here. |
| `unit` | display unit (`INR cr`, `%`, `votes`) for formatting without a JOIN. |
| `derivation` | blank = raw fact; non-blank = formula note for computed fields (F7). |
| `topic` | **FK to `topics.csv`** - single primary topic node (collapses old `topic_tags[]`+`family`+`pillar`). |
| `source_id` | FK to `entities/source.csv` - the indicator's *display* default only; per-row provenance rides each datapoint. |
| `update_period_days` | publisher refresh cadence; the only staleness signal. |

**Dropped from today's catalogue:** `label_long` (-> `name`), `description_short`/`meta.justification` (-> concept entity `description`), `cadence` (redundant), `family`/`pillar` (derived by walking the topic parent-pointer to its root - a pillar is just a topic with null parent), `value_kind`/`direction` (render hints, stay frontend-side), `attribution_geography`/`comparability` (-> concept entity if needed), `parent_indicator_id` (expressed via shared `concept_id`+topic tree), `entity_kinds[]`/`default_entity_kind` (grain lives on each datapoint's geo entity, dispatched at read time per ADR-0044), `vintage` (normalised onto the source entity, reached via `source_id` FK - NOT duplicated on the catalogue).

**Concept stays a first-class entity (`concepts.csv`), NOT a column** - because F6 needs concept to be a shared addressable row that several indicators FK to (a base measure + its per-capita derivation; AC-grain + PC-grain of the same noun), and `check-overlap` queries it standalone on `(noun, unit_canonical, normalisation, entity_kinds)`.

**Topic tree = parent-pointer (`topic, name, parent`), single tag** - the four pillars are simply the roots where `parent` is blank; an indicator carries ONE `topic` column (ancestry makes it visible under every ancestor). Promote to an M:N `indicator_topic_tags.csv` only on a proven cross-subtree listing need (YAGNI now).

**Naming note (Max+Hans signed: Option A):** OWID-grapher's filename `variables.csv` means "the chartable measures" (= yen-gov *indicators*), while yen-gov's `concept_id` means the measured-noun identity (`concepts.csv`). Both names kept to honour the ratified `concept_id` vocabulary; the dual meaning is documented in one paragraph in `docs/concepts/indicator-naming.md` - no rename.

- **CSV is canonical for the catalogue + socio-economic datapoints** (small, git-friendly, diffable; the user's explicit preference over JSON).
- **Parquet retained ONLY as an escape hatch** for genuinely large fact tables (elections `candidacies`/`persons`, hundreds of thousands of rows). Threshold-driven, not default. Section 20.2 (Gregor) sets the concrete threshold + the elections three-way storage split.

> **AMENDMENT 2026-06-04 (Gregor Q1, section 20.1) - the envelope is renamed, the columns are NOT.** The user caught a cargo-cult: DDF is *Gapminder's* format, but CLAUDE.md section 0a names *OWID* as canonical, and OWID does not use DDF. The column contract above stands verbatim (Hans+Max remit). Only the NAMING ENVELOPE changes: the storage envelope is renamed to `datasets/data/`, dropping the `ddf--...--by--...--time` filename grammar (its `--` separator collides with single-dash kebab ids), adopt OWID-grapher directory-segmented names. See section 20.1 for the full renamed tree. Where this section says `variables.csv` read `datasets/data/variables.csv`; `entities/geo.csv` -> `datasets/data/entities/geo.csv`; `datapoints--<id>--by--geo--time.csv` -> `datasets/data/datapoints/geo/<id>.csv`.
- `source_id` is a **per-row column on every datapoint CSV** (F1/O9: RBI vs CAG vs ministry differ per year/state); the catalogue `source_id` is only the display default.
- `unit_canonical`/`normalisation`/`entity_kinds` reached by JOIN `variables.csv.concept_id -> concepts.csv` (DuckDB-WASM joins two small CSVs trivially; no duplication).
- This collapses `datasets/taxonomy/*.json` + `datasets/indicators/in/**` + most of `datasets/schemas/**` into ~8 CSV families with one tiny schema each.

### Electoral entities: SIBLING file (FINALIZED - Hans verdict, user lean confirmed)
Electoral AC/PC entities live in `entities/electoral.csv`, NOT the shared `entities--geo.csv`. Reasons: (1) `parent` means two incompatible things - for LGD it is a true containment invariant, for an AC the only honest parent is its **PC** (never a district); mixing forces a discriminated hack that destroys the clean parent-pointer; (2) `delim_year` is meaningful on every electoral row and NULL on every admin row; (3) AC/PC-to-district linkage is many-valued and decaying, so it is a **crosswalk with a snapshot**, never a `parent` or `district_id` column.

- `entities/electoral.csv` columns: `entity_id, name, entity_kind(ac|pc), delim_year, state(LGD slug - the only invariant admin join), parent(AC->its PC of same delim; PC->state), reservation`.
- `entities/electoral_lgd_xwalk.csv` columns: `electoral_id, lgd_district_id, delim_year, boundary_snapshot(the LGD vintage the overlap was computed against - the decay receipt), overlap_kind(primary|partial)`. A PC gets 6-8 rows; an AC gets 1 `primary` (+ `partial` if it straddles). This is an overlap table, never readable as "AC nests in district" - the storage form of F3.
- **Old + new delimitation coexist as distinct rows** separated by `delim_year`: `IN-S22-AC-2008-1` and `IN-S22-AC-2026-1` never merge, never overwrite. New delimitation = **append new rows**, never mutate old (OWID "new entity, never rewrite"). Datapoints + the `delim=<year>` boundary family point at whichever entity_id matches the event's delim.
- The xwalk is a **computed overlap (F7)**: it must name the `boundary_snapshot` vintage it was computed against, or the decay receipt is hollow.

---

## 4. Elections: the messy-part path (O4 + O6 + O7)

Today (audited): `datasets/elections/state=<lgd-slug>/election_results.parquet` + `dim_acs/dim_pcs/dim_parties/dim_persons/elections_candidacies`. Entity ids already carry delimitation year: AC `IN-<state>-AC-<delim>-<no>`, PC `IN-PC-<delim>-<state>-<no>`. ONE map engine (`StateAcMap` + `TileCartogram` toggle). 2008 delimitation only; no old-delimitation viewing yet.

### E-plan
| Row | Action |
| --- | --- |
| EL1 | **Unify AC + PC under one electoral family** in `entities/electoral.csv` keyed by `(entity_kind, delim_year, state)` with `delim_year` promoted to a first-class column (section 3). Admin-district linkage rides the separate `entities/electoral_lgd_xwalk.csv` snapshot crosswalk, never a `district_id` column. |
| EL2 | **Old + new delimitation in the same map** = a `delim_year`-keyed boundary family under `datasets/boundaries/electoral/delim=<year>/state=<slug>/...`. The map chooses the boundary set from the selected event's `delim_year` (derived from event year via a small lookup). The existing `ElectionTimeSlider` drives the event; the boundary set follows. **Never overlay mismatched polygons**; the AC/PC crosswalk is for navigation only (F3). |
| EL3 | **Parties / symbols / colours - keep / delete / missing:** KEEP `parties.json` -> migrate to `entities/party.csv` (party_id, short, full, eci_codes, brand_colour, symbol_asset, wikipedia). KEEP the 3-layer colour resolver (`anchors` + `oklch` + override) keyed on `party_id`. KEEP the SVG sanitizer + symbol asset pipeline. DELETE the `eci_code`-keyed legacy bridge once datapoints carry `party_id`. MISSING: ~40 ECI ballot symbols still placeholders (1 verified, AAP) + the symbol renderer is not yet wired (was PR-G3) - schedule symbol-wiring as an explicit row. |
| EL4 | **Elections -> socio-economic navigation:** add the missing bridge. From an election view, link each AC/state to its place hub (`/s/:state`) AND to the fiscal/demography topic cards for that entity. Reverse link too (indicator card -> related election). This is the "navigate from elections to indicators" the user wants. |
| EL5 | **Map render:** list-first seat board + map-as-locator per F5; no electoral choropleth promoted to hero. |
| EL6 | **yen-ask `constituency_result` re-point:** that concept SQL currently assumes a direct AC->district key; re-point it to resolve via `entities/electoral_lgd_xwalk.csv` (also tracked under YA1). |

---

## 5. Psephology lab repair (O6)

Audit finding: psephlab code (`frontend/src/routes/Psephlab.svelte` + `lib/psephlab/{canonical-loaders,engine,mutations}`) is structurally sound; the likely break is operational - a missing/renamed canonical shard returns 0 rows and surfaces as `actuals_error`. With the long-format CSV storage change this loader MUST be re-pointed.

| Row | Action |
| --- | --- |
| PL1 | Re-point `psephlab/canonical-loaders.ts` at the new `datasets/data/` electoral datapoint CSVs; confirm the partition/key resolver matches the new entity-id + delim_year shape. |
| PL2 | Generate the canonical shards for at least the pilot states so the loader returns rows (the actual "broken" symptom). |
| PL3 | In-browser verify per CLAUDE.md section 13: load `/lab/:state/:event`, confirm rows render, run one swing mutation, screenshot. |

---

## 6. yen-ask: protect the headline (O7)

Audit: ~5800 LOC, 30 modules, wired at `/lab/yenask`, retrieval-augmented in-browser LLM (MiniLM embeddings + SmolLM2-360M) -> 4 hardcoded concepts -> DuckDB-WASM. Real blockers: G2 (SmolLM2 decode int32-overflow on free text) + G3 (retrieval seam not wired). Depends on `election_results`, `dim_acs/parties/persons/candidacies`, `sources`.

| Row | Action |
| --- | --- |
| YA1 | **Do not remove.** Treat yen-ask's 4 concept SQL templates as a consumer contract: every storage change (section 3) MUST keep `party_totals`, `closest_contests`, `constituency_result`, `turnout_extremes` returning correct rows. Re-point `concepts.ts` SQL at the `datasets/data/` CSVs. |
| YA2 | Park the model-runtime blockers (G2 dtype/device swap, G3 retrieval wiring) as a separate post-foundation track (Andre owns model choice). Foundation first, then yen-ask becomes the headline. |
| YA3 | yen-ask provenance strip currently reads `sources.{producer,title,vintage,license,...}` - update it for the 4-field no-license schema (section 7). |

---

## 7. Provenance diet: 4 optional fields, no license (O3)

Replace the 11-column ledger with exactly four, **all optional**:

| Field | Note |
| --- | --- |
| `owner` | producer / department / government / org name (root, not per-publication) |
| `title` | the dataset/report title |
| `vintage` | edition / year |
| `url` | metadata only; may be blank (GitHub-hosted sources are often not public-linkable) |

- **Dropped entirely:** `license` (O3 - "not always public for github sites, leave it out completely"), `confidence_tier`, `is_issuing_authority`, `verification_method`, `notes`, `citation_full`, `content_hash`.
- `source_id` FK stays on datapoint rows (Holy Law #9 preserved) but is now derivable from `(owner, title, vintage)` and all three may be absent for an unknown source -> a null/`unknown` source_id is permitted.
- Home: collapse `sources.parquet` into `datasets/data/entities/source.csv`; rewrite `derive_source_id`; update yen-ask + `SourceList` components.

---

## 8. Demolition: delete, no strangler (O1)

Git is the backup. No migrate-then-bypass; delete the legacy path and re-ingest clean.

| Row | Delete | Note |
| --- | --- | --- |
| D1 | `datasets/indicators/in/**` JSON write path + `core.io.write_artifact` + all `sources/iced_*` legacy adapters | re-ingest energy etc. onto the long-format CSV spine if/when wanted (energy is low-priority per Max) |
| D2 | `tools/` one-shot scripts: fold the genuinely-reusable ones into `backend/yen_gov/utils/` (O-refinement: "folded into backend utils where necessary"); delete the rest (`*_recon`, `*_probe`, `*_inspect`, executed `migrate_*`/`bump_*`) | ~50 files; net keep a handful as utils |
| D3 | `composers/` empty dead package; repo-root `_probe_ac*.py`, `_probe_jk.py`; `datasets/ephemeral/pre-regen-parquet-snapshot/` (14MB) | confirm zero refs first |
| D4 | Frontend: **keep the V2 chart variety** (O2). Delete only true byte-duplicates after picking the live one; consolidate all chart types into ONE reusable, default-built chart library (`frontend/src/lib/charts/`) that pages compose, not per-indicator bespoke. | this is consolidation, not deletion of the V2 work |
| D5 | The 1700-LOC `cli.py` god-file `write_artifact` half (goes with D1); keep/repurpose the `write_batch`/`ingest` half | |
| D6 | Most of `datasets/schemas/**` (60 -> ~5): one tiny schema each for `concepts`, `entities`, `datapoints`, `source`, and the parquet escape-hatch | follows section 3 |

---

## 9. Repo hygiene (O8 + O10 + the "mess" calls)

| Area | Problem (user) | Action |
| --- | --- | --- |
| `docs/architecture/decisions/` | "rather not have decisions" (O8) | **Retire the ADR *tier*, KEEP the receipts (FINALIZED - Hans).** Delete the parallel numbered filing cabinet + immutability ceremony; but each still-live ADR (~20 on disk: 0003, 0021, 0030, 0031, 0033, 0035-0037, 0040-0050) folds into its subsystem/concept doc as TWO mandatory sections: `Design rationale` (Context+Decision+Consequences) and `Rejected alternatives` (verbatim, **append-only** - it is the anti-re-litigation guard CLAUDE.md depends on). Superseded/rejected ADRs (0002, 0017, 0038, 0039) fold their trace into the survivor's `Rejected alternatives` or move to `docs/archive/decisions/` - never deleted. Redirect index = one `docs/reference/decision-index.md` mapping every `ADR-NNNN -> <doc#anchor>`; numbers never reused. **Real cost is the cross-reference rewrite** (CLAUDE.md leans on 0032/0034/0041/0042/0044-0047), not the file move. Migration acceptance gate: `grep` count of `Rejected alternatives` blocks before == after. **Inventory from the filesystem, not the stale README (it stops at 0047; 0048-0050 exist).** |
| `datasets/` | "a mess" | Reshape to the long-format CSV layout (section 3): `datasets/data/` canonical, `datasets/boundaries/` (admin + electoral/delim-keyed), `datasets/_ops/` operator state. Delete `indicators/in/**`, `ephemeral/`, stale snapshots. |
| `datasets/reference/` | not yet named | **Reshape (mostly absorb).** `reference/in/states`, `reference/in/pincodes` are entity reference -> fold into `datasets/data/entities/*.csv`. `reference/in/indicators-completeness.json` + `indicators-operator-state.json` are operator bookkeeping -> move under `datasets/_ops/` (not citizen-facing). The `reference/` tier itself retires once both are rehomed. |
| `datasets/features/` | not yet named | **Keep, but de-feature in v1.** Holds only `in/energy/power-plants.geojson` (+ sidecar). Energy is low-priority/pruned per Max (section 10 Prune row), so this stays as the single GeoJSON-point exception (DuckDB-WASM can't render geometry; MapLibre reads GeoJSON natively) but is not a v1 focus. Layout unchanged; revisit codec (PMTiles vs GeoJSON) only if energy is re-prioritised. |
| `datasets/boundaries/` | reshaped | **Keep** - reorganised to admin + electoral/delim-keyed layout (section 3); the parity/geo-crosswalk knowledge here is the "new you keep" (section 11). NOT deleted. |
| `.runtime/` | "a mess" | It is gitignored + ephemeral by contract; add a single documented cache layout (`.runtime/cache/<source>/...`) and a `clean` command; never referenced from committed artifacts. |
| `config/` | "probably superfluous" | Audit the 4 files (`eci-pins`, `elections`, `processing`, `topojson`). Fold genuine tunables into the concept CSV or a single `config.json`; delete the rest. Likely collapses to 0-1 files. |
| `datasets/schemas/` | "a mess, consolidate" | Collapse to ~5 schemas (section 3 / D6). |
| `notes/` + `TODO/` | "almost same" (O10) | Merge into ONE convention: `TODO/` holds live plan-docs + handover docs (actionable); `notes/` is retired, its still-relevant content distilled into `docs/` or folded into the relevant plan-doc. One working-docs home, not two. |

---

## 10. Refill the mission families (Max wave order, long-format-CSV, RBI golden)

All RBI-actuals (F1), one-concept-per-indicator (F6), state+district (F4), long-format CSV (section 3).

| Wave | Indicators | Source | Grain |
| --- | --- | --- | --- |
| W1 | own-tax-revenue, central-tax-devolution, net-transfers, outstanding-liabilities-%-GSDP, revenue-expenditure (+ GSDP denominator) | **RBI State Finances** for breadth + actuals; supplement/cross-check with CAG and ministry data where it covers gaps (all gold per O9) | state, ~20yr |
| W2 | gst-collections-state-monthly | GST Council / PIB (data.gov.in mirror) | state, monthly |
| W3 | mgnrega-expenditure + person-days; pm-kisan-disbursed + beneficiaries (DISTRICT nesting proof) | nrega.nic.in MIS; pmkisan.gov.in | district |
| Prune | energy ~100 -> ~10 (or drop from v1); livestock de-featured | - | - |

W1 = re-ingest clean (not migrate); W2/W3 = net-new adapters; do not bundle.

---

## 11. Biggest risk

The parity oracle (`test_canonical_parity_oracle.py`) and the geo/delimitation crosswalk knowledge are tacit. The whole reason to keep-and-refill rather than rewrite is to bank them. With O1 (delete, no strangler) the discipline shifts: **delete legacy code, but NEVER delete the parity fixtures or the geo crosswalk data without a replacement that re-passes them.** Those two are the "new" you keep.

---

## 12. Execution order

1. Phase 0 doctrine freezes F1-F9 (+ fix `electoral-hierarchy.md` immediately - live trap).
2. Settle section 3 long-format CSV column set (Hans+Max+Gregor).
3. Demolition section 8 (delete; fold reusable tools into utils).
4. Repo hygiene section 9 (retire ADRs, reshape datasets/schemas/config, merge notes+TODO).
5. Provenance diet section 7.
6. Storage migration to `datasets/data/` + re-point loaders (frontend DuckDB, psephlab, yen-ask).
7. Elections path section 4 (EL1-EL5).
8. Psephlab repair section 5 + yen-ask re-point section 6.
9. Refill W1 -> W2 -> W3 (section 10).
10. Frontend re-arch: place-spine, reusable chart lib, kill 50MB home load, break god-files.

## 13. Status Reckoner

| ID | Title | Status |
| --- | --- | --- |
| Direction | A ratified + 10 overrides | DONE (this doc) |
| F1-F9 | Doctrine freezes | NOT STARTED |
| section 3 | long-format CSV storage model + columns | **FINALIZED 2026-06-03 (Max+Hans)**; Gregor ratifies read-path only. **Naming envelope renamed 2026-06-04 (Gregor): envelope `datasets/data/`, drop the old `--by--time` grammar, OWID-grapher names; columns unchanged (section 20.1)** |
| D1-D6 | Demolition (no strangler) | NOT STARTED |
| section 9 | Repo hygiene (ADR retire-keep-receipts, datasets/schemas/config/notes) | **ADR rule FINALIZED 2026-06-03 (Hans)**; rest NOT STARTED |
| section 7 | Provenance 4-field | NOT STARTED |
| EL1-EL6 | Elections path | NOT STARTED |
| PL1-PL3 | Psephlab repair | NOT STARTED |
| YA1-YA3 | yen-ask re-point | NOT STARTED |
| W1-W3 | Refill | NOT STARTED |
| FE | Frontend re-arch + reusable charts | NOT STARTED |
| section 14 | Chart system (choropleth + legend + grain + search) | **ANALYSED 2026-06-03 (browser teardown)**; geo source = own district topojson; district coverage 771/784 (98.3%) verified; build deferred to FE row |
| section 14.5 / F5 | Map engine decision | **RESOLVED 2026-06-03 (Jony)**: d3-geo SVG for static welfare maps, maplibre fenced to elections; shared color/legend/geometry layer |
| section 14.3 / C2 | Choropleth legend value-tick (highlighted region draws a marker on the legend band) | **DESIGNED 2026-06-03 (Jony)**; folded into C2; build deferred to FE row |
| section 15 | Reusable base-chart library (6 renderers + 2 modes + 3 primitives) | **DESIGNED 2026-06-03 (Jony)**; consolidation of existing v2 fragments; build deferred to FE row |
| section 15.1 | Treemap + CirclePack renderers; DumbbellRange arrow mode; GeoChoropleth symbol mode (icon-cartogram) | **DECIDED 2026-06-03 (Jony); AMENDED 2026-06-04**: Treemap AND CirclePack both ship (user override, section 20.7); bubble=Scatter(size); animated-SVG REJECTED; icon registry fenced; build deferred to FE row |
| section 15.4 | Standing reference galleries (revisual.co + Data-Analytics) | **RECORDED 2026-06-03 (user-mandated + Jony sweep)**; consult-before-charting doctrine |
| section 16 | Geography-first nav + swappable landing page | **DESIGNED 2026-06-03 (Jony)**; grapher contract `chart_types[]` + grain-feasibility intersect; build deferred to FE row |
| section 16.3a | Chart-type switcher manifestation + citizen choice | **DESIGNED 2026-06-03 (Jony); AMENDED 2026-06-04**: segmented glyph control, instant swap, one-feasible-type=no-switcher; **`?view=` URL persistence STRUCK -> in-memory only (section 20.8)**; build deferred to FE row |
| section 17 | Lightweight enrichment doctrine | **CONFIRMED 2026-06-03**; satisfied by section-3 long-format CSV shape (one-file-per-indicator, append-by-time) |
| section 18 | CHIPS / SIDE framework | **DECIDED 2026-06-03 (Hans+Max)**: ingest-as-published, no recompute, strict framing; pre-ingest blockers listed |
| section 19 | Curated indicator catalogue + new-chart data | **SCOUTED 2026-06-03 (Max)**; wave order set; pyramid + GSDP-heatmap ACQUIRE; lift to docs/ at W-row scoping |
| section 19.4 | New chart-style data (factory / poultry / CO2 / cybercrime) | **SCOUTED 2026-06-03 (Max)**: factory ACQUIRE; livestock-census ACQUIRE (NOT the NDLM tag parquet); CO2-per-state REJECT (national-only); cybercrime ACQUIRE+caveat |
| section 20.1 | Data-model envelope rename (DDF name -> OWID `datasets/data/`) | **DECIDED 2026-06-04 (Gregor)**: drop "DDF" brand + `ddf--` grammar; keep shape + columns; one-paragraph rationale to `docs/concepts/indicator-naming.md` |
| section 20.2 | Elections storage split (per-state CSV + 1 national candidacies.parquet + AC-summary CSV) | **DECIDED 2026-06-04 (Gregor)**: concrete >100K-rows-AND-cross-partition-projection threshold; build deferred to EL rows |
| section 20.3 | Parties / symbols / colours as `entities/party.csv` | **DECIDED 2026-06-04 (Gregor)**: party_id sole key, eci_codes attribute not key, symbol assets keyed by symbol_id; reconciles EL3 |
| section 20.4 | Office-holders family (government + alliances + CM/PM/cabinet as term assignments) | **DECIDED 2026-06-04 (Gregor)**: merge `datasets/governments/` + alliances into one term-assignment family in `datasets/data/`; new `docs/concepts/office-holders.md` |
| section 20.5 | Boundaries follow LGD grain (confirm) | **CONFIRMED 2026-06-04 (Gregor)**: admin keyed LGD, electoral keyed ECI+delim, joined only via xwalk |
| section 20.6 | `datasets/grapher/` + `datasets/_ops/` fate | **CONFIRMED 2026-06-04 (Gregor)**: KEEP both; grapher extended (render hints, ADR-0045), _ops absorbs reference operator files |
| section 20.7 | CirclePack restored as base renderer #8 | **DECIDED 2026-06-04 (user override + Jony)**: both area renderers ship; precise-compare->Treemap, clustered-magnitude->CirclePack |
| section 20.8 | Viz-type switcher without querystring | **DECIDED 2026-06-04 (user + Jony)**: in-memory state only, default chart_types[0]; opt-in `#view=` escape hatch only |
| section 20.9 | Chart index / registry (`docs/reference/chart-index.md`) | **DESIGNED 2026-06-04 (Jony)**: one row per renderer (thumb + long-format CSV shape + when-to-use + feasibility); drift-guard contract test |
| section 20.10 | yen-ask grounding surface under the reset | **DESIGNED 2026-06-04 (Andre)**: catalogue + entity-dict-with-aliases are the LLM contract; +time_min/time_max/entity_kinds; injection-fence; intent-eval gate |
| section 20.11 | National reference line per state chart | **DESIGNED 2026-06-04 (Max+Hans)**: Class A pop-weighted/median, B sum-only, C median-per-edition, D none; compute-at-ingest derived series; `direction` gate for status colour |
| section 20.12 | Nav spine FREEZE (geography-breadcrumb + same-side cluster) + IDP-informed UX | **DESIGNED 2026-06-04 (Jony)**: Candidate C frozen; ASCII mockups; quick-jump; SHA footer; (i)-attribution; /docs/indicator/<id>; time-brush; open-licensed icon family (NOT scraped IDP); build deferred to FE row |
| section 20.13 | backend/ + frontend/ restructure rows (BR + FR) | **DESIGNED 2026-06-04 (Gregor)**: name survivors (parity oracle + geo crosswalk never deleted); kill-50MB-home-load gets its own gate |
| section 21.1 | Guiding doctrine REPLACES the "DATA-SCHEMA-SCALE-ENRICHMENT" slogan | **DECIDED 2026-06-04 (Max+Hans debate)**: question-first / joinable / comparable / cite-able / static spine; new `docs/concepts/data-spine.md` |
| section 21.2 | CSV everywhere, NO parquet (supersedes 20.2) | **DECIDED 2026-06-04 (Gregor+Fowler debate)**: one format; typed `read_csv(columns=...)` + write-time validator replaces 60 JSON schemas; `_ops/range-mime-probe` deleted; geometry untouched |
| section 21.3 | Elections per-election self-contained CSV | **DECIDED 2026-06-04 (Gregor)**: `assembly/state=/election=/{candidacies,summary}.csv` + `parliament/election=/...`; AC-summary per-(state,year) NOT across-years; results==candidacies |
| section 21.4 | Elections backend = ingest-only; delete all fetch code | **DECIDED 2026-06-04 (user+Explore)**: reingest from local TCPD CSV; delete `sources/eci/urls.py` + portal-recon; keep pure parsers |
| section 21.5 | 20.13 REWRITTEN - clean DELETE/BUILD, no strangler | **DECIDED 2026-06-04 (Gregor)**: atomic format cutover; old code deleted in THIS plan; survivors = parity oracle + geo/LGD crosswalks + check-overlap only |
| section 21.6 | Double-underscore BANNED | **DECIDED 2026-06-04 (Gregor)**: directory segmentation + kebab facet slot or OWID dimension column; filename always exactly `<variable_id>.csv` |
| section 21.7 | Modern design-token system (kills "1990" look) | **DESIGNED 2026-06-04 (Jony)**: fill empty `theme.extend`; self-host subset variable fonts; tabular numerals; calm civic-indigo palette; soft elevation; motion tokens; build deferred to U-rows |
| section 21.8 | Frozen Candidate C rendered modern + same-side drawer fix | **DESIGNED 2026-06-04 (Jony)**: GeoBreadcrumb spine; glass app bar; LEFT-drawer fix; companions named; build deferred to U-rows |
| section 21.9 | Rational chart-viz doctrine | **DESIGNED 2026-06-04 (Jony)**: switcher = `chart_types[] INTERSECT feasibleAt()`; pie/3D/blind-bar UNREACHABLE; 1:1 drift-test |
| section 21.10 | Icons -> `frontend/public/icons/` | **DECIDED 2026-06-04 (Jony+Explore)**: party-symbols precedent; repoint `iconsDir` in `vite.config.ts`; allowlist sanitizer unchanged; LICENCES.md |
| section 21.11 | Country topojson FROZEN: NO switch to ehdata geometry | **DECIDED 2026-06-04**: keep own 785-district LGD-keyed file; frozen reqs (a) Lakshadweep/A&N render smoke-test, (b) mapshaper quantize/simplify |
| section 22 | Autonomous execution model (orchestrator + PR subagents) | **DEFINED 2026-06-04 (user mandate)**: tracks D/U/B/F; only F1<-B2+U1, X1<-F1, B3/B4/F2/F3/F4<-X1 block; debate-mode personas at forks only; essential-tests-only DoD |
| section 22.2/22.5 | Chunk graph CORRECTED + Execution Ledger added | **DECIDED 2026-06-04 (round-5 review)**: X1->X1a/X1b split; B2->B2a/B2b; F2->F2a/F2b; D-DOC0 added; 4 hidden edges drawn; ledger is the merge-queue, Reckoner is decisions |
| section 22.6 | Gates catalogue (where each gate fires) | **DECIDED 2026-06-04 (round-5)**: cross-format-parity, parity-oracle-CSV, dual-read-parity, fk-validator, kill-50MB, oracle-non-skip, chart-drift, golden-render, island-render, intent-eval, devanagari |
| section 23.1 | Backend deletion blast radius corrected | **CORRECTED 2026-06-04 (Explore+Fowler)**: writer.py FULL REWRITE; http.py + 5 cli.py Fetcher blocks; schema_registry.py + 80+ importers; write_artifact 20+ surviving callers re-point in B1; schema-delete allowlist (retain config validators) |
| section 23.2 | Column contract has ONE machine-readable home | **DECIDED 2026-06-04 (Gregor)**: `datasets/data/_schema/` (or `columns.json`) sole source; reader maps GENERATED, never hand-typed (ADR-0047 alt F); drift test writer==contract==reader |
| section 23.3 | Frontend read-path rewrite | **CORRECTED 2026-06-04 (Explore)**: `queryParquet()`->`queryCsv()` + glob + ~40 callers; 4 yenask SQL templates show before/after; CSV `entity_id` byte-matches old parquet id |
| section 23.4 | Elections layout sharpening | **DECIDED 2026-06-04 (Gregor)**: parliament CSV carries `state` as MANDATORY column; EL7 `coverage.py` AC-vs-PC disposition; `summary==recompute(candidacies)` consistency gate |
| section 23.5 | Frontend design + nav corrections | **CORRECTED 2026-06-04 (Jony)**: ADDITIVE tokens; Devanagari GSUB/GPOS subset; feasibleAt ranked-fallback; ChartType breaking-enum migration; district URL node; ChartShell error/empty; F2 sandbox-only blast radius |
| section 23.6/23.7 | Deploy hygiene + test-disposition map | **DECIDED 2026-06-04 (Explore+Fowler)**: deploy emit-manifest step; config/tools survivor lists; per-chunk DELETE/REWRITE/NEW churn map (oracle REWRITE, writer test DIE, sources-v2-shape DELETE) |
| section 24 | Operator guide: read order + status lifecycle + kickoff prompt + sub-plan rule | **ADDED 2026-06-04 (user ask)**: Execution Ledger is the ready-reckoner; TODO->IN-FLIGHT->MERGED updated in the chunk's own PR; spawn `<date>-<slug>-subplan.md` with parent back-pointer when a chunk exceeds one PR |
| section 22.7 | Step 0 - doctrine reconciliation (CLAUDE.md + 8 AGENTS.md) | **ADDED 2026-06-04 (user ask)**: D-DOC4 merges FIRST and is the kickoff gate; neutralise-now vs MIGRATING-marker two-phase rule; per-chunk DoD #7 flips the marker that the chunk makes true; doctrine-marker-audit gate proves zero stale assertions survive so no agent reintroduces the deleted Parquet/DDF world |
| section 25 | Election-experience UX refinements | **DESIGNED 2026-06-04 (Jony)**: 25.1 archetypes (reuse RacesBoard/source-line/brush/swing-slider); 25.2 mandatory time_label; 25.3 PartyPill + --party-neutral, symbol separate; 25.4 state silhouette on choropleth+hex; 25.5 margin-vs-party-won modes + recede + margin sub-filter; 25.6a arc seats invariant fix; 25.6b countSeats seam DEFERRED to sub-plan (Citizen+Hans gate) |

---

## 14. Chart system - choropleth + reusable chart library (Flourish-parity, self-hosted)

User ask: replicate the EHdata.org / Flourish district choropleth (bank-branch chart) **without** the SaaS. Integrated-browser teardown of `flo.uri.sh/visualisation/28362650` (2026-06-03) settles the "is this magic?" question: it is **not**. It is a static India-districts geometry + a join on LGD district code + a binned sequential color scale + d3 SVG render. We already own every piece.

### 14.1 What Flourish actually does (teardown findings)

| Element | Flourish setting (observed) | yen-gov equivalent |
| --- | --- | --- |
| Geometry | custom-uploaded India-districts polygons, **766 regions**, join column literally named `lgd_district_code` (console: "Region(s) without matching geometry: 599..765" = newer LGD codes their vintage lacks) | `datasets/boundaries/in/districts/all.topojson` - **785 districts**, property `dist_lgd` = LGD district code. Same key, newer vintage (closes their gaps). **Reuse ours; no external source.** |
| Projection | `Miller (modified Mercator)`, single frame (mainland + Lakshadweep + Andaman + NE all in one projection, no insets) | d3-geo `geoMiller` (or geoMercator) over the topojson; render-all-geometry so islands appear |
| Color | sequential palette `RdPu`, `hcl` color space, **binned** (`bin_mode: custom`, `bin_count: 10`), domain ~12..679 | d3-scale-chromatic `interpolateRdPu` + `scaleQuantize`/threshold; bins from indicator metadata |
| Legend | horizontal rectangular band, `color_band_width: 12`, min/mid/max labels (12 / 200 / 679), title = indicator name | reusable `<ChoroplethLegend>` - the rectangular intensity legend we are missing today |
| Missing grain | `map_include_all_region_geometry: true` + two-color hatch `missing_pattern_color_1: #ffffff`, `missing_pattern_color_2: #d8d8d8` (the dotted grey over J&K / Ladakh / new districts) | SVG `<pattern>` diagonal hatch, same two greys, applied to any region with no datapoint |
| Outlines | `map_stroke: #16181b`, `map_stroke_width: 0.3` | stroke on each district path |
| Tooltip | region label + state metadata + value, colored to the choropleth scale | tooltip reads the same color scale |
| Search | `search_placeholder: "Search District"` - searches region labels, highlights + frames the match (`map_highlight_stroke_*`) | granularity-aware search (14.4) |
| Attribution | one line: `Source: <link> (as of <vintage>)` | one line straight off the source entity (F9) |

Each datapoint row is `{ id: <lgd_district_code>, label, metadata:[state], value:[n] }` - i.e. exactly a long-format `entity,time,value` row joined to the geometry on the LGD code. **The "fast" feel is just inline static geometry + a join; nothing to license.**

### 14.2 Geo source decision (resolves the user's "find their topo/geo, use the same")

- **Use our own** `datasets/boundaries/in/districts/all.topojson` (785 districts, keyed on `dist_lgd`). It is the same kind of asset Flourish uploaded, one vintage newer, already in the repo. No SaaS geometry, no external fetch.
- The correlation the user asked for is **already trivial**: their join key `lgd_district_code` == our `dist_lgd` == the `lgd_district_id` our taxonomy (`lgd_districts.json`, `lgd_ac_pc_district_map.json`) already uses. `entities/geo.csv` (section 3) carries `entity_id` at district grain = LGD district id, so datapoint -> geometry is a direct key join.
- Ties to F5 (one-map-engine-two-families): the SAME choropleth renderer serves socio-economic district maps AND the election spine; the geometry tier (state / district / AC / PC) is selected by the rendered grain.

**District coverage verification ("no surprises" check, user-requested 2026-06-03):**

- `all.topojson` carries **785** district geometries, all bearing `dist_lgd` (784 distinct codes - one geometry has the bogus `dist_lgd=0`).
- `lgd_districts.json` taxonomy carries **784** district rows.
- **771 / 784 (98.3%) of taxonomy districts join cleanly to a geometry.** 13 geometry codes are NOT in the taxonomy (newer carved districts: 599, 601, 671, 769-783) plus the one bogus `dist_lgd=0`. This is the same gap class Flourish hit ("Region(s) without matching geometry 599..765"), one vintage earlier.
- **The hatch-for-missing pattern (C4) handles this exactly:** render all geometry, hatch any region without a datapoint. No render breaks; the 13 unmatched are a reconciliation backlog, not a blocker.
- **Critical finding - zero district-grain indicator data exists today.** All 42 files under `datasets/indicators/in/` are state/national grain; energy + livestock parquet are non-district grain. District choropleths therefore render entirely hatched until W3 refill lands a district-grain indicator. The renderer can be built first, but it has nothing to colour until refill. Sequence: build C1-C5 against a state choropleth (data exists), wire district grain when the first district indicator arrives.

### 14.3 Reusable chart components (the FE row, made concrete)

This is the substance behind the section-13 "FE - reusable charts" row. Build once, schema-driven (one card per measure, per CLAUDE.md), reused by every topic + the election path:

- **C1 `<Choropleth>`** - d3-geo + topojson; props: geometry tier, datapoint rows (id->value), color scale, projection. Renders ALL geometry (islands included); no-data regions get the hatch.
- **C2 `<ChoroplethLegend>`** - the rectangular binned intensity bar we currently lack. Horizontal, configurable band width, min/mid/max + optional bin ticks, title = indicator name + unit. **Value-tick (Jony, observed on the EHdata.org bank-branch chart):** when a region is hovered or matched by `<PlaceSearch>` (14.4), draw a thin marker (caret + hairline) on the legend band at that region's value position, with the numeric value labelled beside it - synced to the same entity that thickens the map stroke, so the citizen sees WHERE on the colour band their place sits, not just its fill. One marker at a time; clears on blur; pure derived state from the active entity id + binned scale (no new data). Reused when the legend is shared with `Matrix` (column highlight).
- **C3 `<MapTooltip>`** - region label, parent (state), formatted value + unit, swatch colored to the same scale.
- **C4 missing-data hatch** - shared SVG `<pattern>` (`#ffffff` / `#d8d8d8`), applied wherever a region has no datapoint (decommissioned J&K data, post-vintage new districts).
- **C5 `<SourceLine>`** - one line, `Source: <owner> (as of <vintage>)`, owner+vintage straight off the source entity (F9 four-field provenance). Matches Flourish's understated attribution the user liked.

### 14.4 Granularity-aware search (user: "dependant on granularity rendered")

`<PlaceSearch>` bound to the **place-spine** (the FE re-arch row). Behaviour:

- The searchable entity set = the grain currently rendered: state | AC | PC | district | sub-district | pincode.
- On match: highlight the segment (thicker stroke, the `map_highlight_stroke_*` analogue) and frame/zoom to it.
- Entity rows come from `entities/geo.csv` (admin ladder) and `entities/electoral.csv` (AC/PC), so search is fed by the canonical store, not a bespoke index.
- Pincode search resolves via the existing postal boundary tier (`datasets/boundaries/in/postal/`) when that grain is shown.

### 14.5 Map engine decision - RESOLVED (Jony verdict 2026-06-03; ratifies F5)

User framed it as "what are we losing, what are we gaining": (1) maplibre-gl for election pan/zoom + d3-geo for static choropleth, OR (2) unify under one engine. **Resolved: split by job.** This is the single biggest "tortoise -> leopard" performance win and is exactly why Flourish renders like a leopard.

**Decision: d3-geo SVG for ALL static welfare choropleths; maplibre-gl fenced to the election AC pan/zoom explorer only.**

| | d3-geo SVG (static welfare maps) | maplibre-gl (election explorer) |
| --- | --- | --- |
| **Gain** | Instant first paint; no GL context, no tile fetches, no per-frame recompute; smaller bundle; matches the Flourish "leopard" feel; trivially server-static; one join + one binned scale | Smooth continuous pan/zoom to AC grain; vector-tile streaming for very deep zoom; gesture inertia |
| **Lose** | No built-in continuous pan/zoom or tile streaming (fine - a national/state fill does not need it) | Heavy: GL context + tiles + per-frame recompute; the "tortoise" cost we are removing from the default path |

Why splitting wins over unifying:
- A static national or state fill never needs a GL context, tile requests, or pan/zoom machinery. Paying that cost on every welfare card is the tortoise.
- The election AC explorer genuinely benefits from deep continuous zoom across ~4000 ACs - keep maplibre there, fenced (ADR-0048 election renderer set).
- Both consume the SAME topojson tiers and the SAME `<ChoroplethLegend>` + `ColorScale` primitives, so "two engines" is not "two stacks" - it is one shared color/legend/geometry layer with two render backends chosen by job.

Performance doctrine adopted with this decision (Jony section E):
1. Ship **pre-simplified, pre-quantized topojson per grain** as static assets (mapshaper/topojson-simplify once at build; drop unused properties; low coordinate precision). Geometry is the heavy part - load once, cache for page lifetime.
2. **Pre-bin color scales** from `grapher.color_scale`; compute the quantized scale once per render and memoize; never recompute per cell or per animation frame.
3. **DuckDB-WASM returns only `(entity_id, value)` for the current time** - small payload joined to static geometry in memory. The one-file-per-indicator shape makes this query trivial.
4. **One generic render path per chart type** - no per-indicator Svelte (already banned by schema-is-the-design-system). Default chart in the initial bundle; Scatter/Radar dynamic-imported on demand.
5. Shared `ColorScale + Legend` primitive serves both `<Choropleth>` and `<Matrix>` (binned sequential + diverging, rectangular intensity legend, diagonal-hatch no-data swatch).

This closes the F5 "one map engine" open question: **F5 is now "one shared color/legend/geometry layer; d3-geo backend for static, maplibre backend fenced to elections."**

### 14.6 Scope / status

Level-5 analysis only - no frontend code until the user signs off. Folds into the section-13 **FE** row and **F5**. Adds no new external dependency (geometry is in-repo; d3 + topojson already in `frontend/package.json`).

---

## 15. Reusable base-chart library (Jony verdict 2026-06-03)

Settles O2 ("keep V2 chart work") and the section-13 FE row. **Key finding: most of this library already exists as fragments** from the prior charts-v2 effort (`frontend/src/lib/charts/`: `OrderedCategoryBar`, `HorizontalGroupedBar`, `DumbbellRange`, `TileCartogram`, `TimeSeriesLine`, `StackedTrendV2`, `composition-bar/`, `temporal-viewport/`, `ChartShell`). **This is a CONSOLIDATION, not a greenfield.** Target end-state: **6 core renderers + 1 optional + 3 shared primitives + 2 modes on existing renderers.** Any further renderer must clear the schema-is-the-design-system bar (>=2 indicators need it AND neither reference gallery's archetype maps onto the set).

### 15.1 The minimal renderer set (collapse aggressively)

| # | Renderer | long-format CSV shape consumed | Covers user asks | Notes |
| --- | --- | --- | --- | --- |
| 1 | **`GeoChoropleth`** | `(geo, time, value)`, one time slice | district/state maps | C1 from section 14; d3-geo SVG (14.5) |
| 2 | **`Matrix`** (heatmap) | `(entity, time, value)`, all slices | **SGDP across states over time** (replaces remittance circle-pack); states x years cell colour | shares ColorScale + Legend with Choropleth |
| 3 | **`CategoryBar`** mode=`ranked\|stacked\|diverging` | `(entity, value)` + optional `facet` | **N/S/E/W confidence (likert)**, **age-sex pyramid**, **workforce M/F**, plain ranked | see collapse below |
| 4 | **`TimeLine`** | `(entity, time, value)`, 1-3 series | trend lines | existing `TimeSeriesLine` |
| 5 | **`Scatter`** | two indicators joined `(entity, time, x, y)` + optional `size` | **CHIP vs NSDP per-capita**, **bubble for GSDP/revenue/tax** (size mode) | trend line + size are props; NO standalone bubble renderer |
| 6 | **`DumbbellRange`** + `marker_style=dot\|arrow` | `(entity, value_start, value_end)` | **crime-direction / year-over-year change** (2021->2022 cybercrime per lakh) | EXISTS in `frontend/src/lib/charts/`; arrow mode = arrowhead end + open-ring origin + diverging colour by `direction`. No new file. |
| 7 | **`Treemap`** (NEW renderer) | `(category\|entity, value)` + optional one `parent` level | **economic-disparity** (revenue-per-capita by city-pop band), expenditure-per-capita, nested-ID coverage | gallery-confirmed, >=2 indicators; part-to-whole WITH precise magnitude compare (full-rectangle tiling, labels survive at 360px) |
| 8 | **`CirclePack`** mode=`pack\|bubble` (NEW renderer) | `(category\|entity, value)` + optional one `parent` level | **city-revenue packed-bubble** (the cityfinance screenshot), market-centre counts, pure-magnitude clusters | RESTORED by user override 2026-06-04 (section 20.7); coexists with Treemap - discriminator: precise-compare -> Treemap, clustered-magnitude vibe -> CirclePack; sqrt area scale (honest area) |
| 9 (optional) | **`Radar`** | `(entity, facet=spoke, value)` | **CHIPS sub-pillar spider** | LOW priority; reads poorly on mid-tier Android; prefer `HorizontalGroupedBar` for sub-pillar compare; build only on explicit request |

**Load-bearing collapses (this is the simplification the user wants):**

- **The N/S/E/W confidence likert AND the age-sex pyramid are the SAME component** - a horizontal stacked bar with a centre baseline. Likert = diverging at a neutral split; pyramid = diverging by sex, category = age band. Both are `CategoryBar mode="diverging"`. **Do NOT build a Pyramid component or a Likert component.**
- **"Pyramid animates over time" = `CategoryBar(diverging)` + the shared `TimeControl` primitive.** The animation is not part of the chart; it is the shared time control driving the value query. The SAME wiring serves workforce-M/F-over-time with zero new code.
- **Treemap AND CirclePack both ship (user override 2026-06-04, section 20.7).** Both encode magnitude by AREA via a sqrt scale (honest area; a 4x value looks 4x not 16x). Discriminator: **Treemap** = part-to-whole where precise size compare matters (tiles, zero dead space); **CirclePack/packed-bubble** = pure magnitude clusters / shallow hierarchy where the message is "these blobs, sized" not exact ranking. `Scatter(size)` still owns the axes-bearing bubble. The earlier "circle-pack dropped, treemap replaces it" verdict is REVERSED.
- **`OrderedCategoryBar` + `HorizontalGroupedBar` + `composition-bar/` collapse INTO one `CategoryBar(mode=...)`.** The consolidation PR must merge these, not ship a 4th bar engine. Watch: `StackedTrendV2` owns time-on-x stacked area; `CategoryBar` owns category-on-axis - document the boundary so a third stacked surface is not forked.
- **Crime-direction = `DumbbellRange(marker_style="arrow")`, NOT a new renderer (Jony).** Arrowhead end + open-ring origin; colour by the indicator's `direction` metadata (so it reads correctly for good-up AND bad-up measures); delta `+/-%` label via existing `format_delta`. Add `marker_style` to the view-model; >=2 indicators want it (crime change + any before/after pair).
- **Icon-cartogram = `GeoChoropleth(mode="symbol")`, NOT a new renderer (Jony).** Reuses the SAME d3-geo projection + per-region centroids; swaps the polygon fill for ONE sanitised SVG glyph per region, area-sized by value (sqrt scale so area is honest), over a faint base outline. Props: `symbol_id` (FK to a closed icon registry), `size=<measure>`, `base_outline_opacity`. Legend shows 2-3 reference symbol sizes with their numeric values. Glyphs come from a small fixed registry reusing the existing party-symbol SVG sanitizer + allowlist (`frontend/src/lib/party-symbols/`); `indicator_render.json` carries `symbol_id`; glyphs are NEVER authored per-indicator inline; missing glyph falls back to a plain sized dot. **REJECTED: animated SVG (smoke/gas puffs scaled by emission)** - violates reductionism (motion carries no signal beyond size), performance (per-frame SVG across 36 regions on mid-tier Android over 4G is the tortoise we are deleting), and clarity (decorative redundancy). The factory/animal glyph sized by value is the whole story.
- **Bespoke-per-indicator art guard:** the icon-cartogram is the one place per-indicator illustration could re-enter. Fenced to the closed sanitised icon registry + dot fallback. No inline drawings, no illustrated "building" bars (gallery editorial art is out of scope).

### 15.2 Three shared primitives

- **`TimeControl`** (extends `temporal-viewport/`) - one play/pause + scrubber + year label in `ChartShell`'s toolbar slot. Snaps to ACTUAL distinct `time` values in the indicator's datapoint CSV (no phantom years). Emits `currentTime`; renderer re-queries `(entity, value WHERE time = currentTime)`. Reused by Choropleth (year-over-year), CategoryBar-diverging (pyramid + workforce), and Matrix (column highlight).
- **`ColorScale + Legend`** - factored out of the choropleth; binned sequential + diverging; rectangular intensity legend; diagonal-hatch no-data swatch; numeric labels always (never colour alone). Serves Choropleth + Matrix.
- **`ChartShell`** (exists) - title, source line (C5), toolbar slot, comparability note.

### 15.3 Do NOT build (reductionist lens)

A Pyramid component; a Likert component; a standalone Bubble renderer (use `Scatter(size)`); maplibre-gl for static welfare maps; animated SVG (smoke/gas puffs); any per-indicator chart Svelte file; per-indicator illustrated art; Radar first (build it last or not at all). Streamgraph, sankey, violin, sunburst, chord, alluvial are explicitly out of scope (desktop / editorial forms) - collapse them to Treemap/CirclePack/Matrix/CategoryBar/Scatter. A new welfare need is met by the base set, never by forking an election renderer (`PartyBar`, `SeatDonut`, `StateAcMap`, etc. stay fenced to elections per ADR-0048). (Circle-pack/packed-bubble were on this list until 2026-06-04; user override restored them as renderer #8 - section 20.7.)

### 15.4 Standing reference galleries (user-mandated; Jony + future agents consult before charting a new indicator)

Two galleries are kept as standing visual references for whoever (Jony / the default agent) is choosing a chart for a NEW indicator:

- **https://revisual.co/chart-gallery** - Indian socio-economic + fiscal + election work; the closest match to yen-gov's data. (Source of the user's bank-branch choropleth, economic-disparity treemap, cybercrime-direction, CHIPS-radar, age-sex examples.)
- **https://github.com/Data-Analytics/data-analytics.github.io** - a D3/Highcharts archetype index; not every directory is a chart, but many are (Choropleth_India_Map, Cartogram, Treemap, Sankey, Bubble_Chart, Heatmap, Marimekko, Radial_Stacked_Bar, Parallel_Axis, election dirs).

**Doctrine line:** before adding a chart for a new indicator, consult BOTH galleries AND pick from the base set (`GeoChoropleth{fill,symbol}` | `Matrix` | `CategoryBar{ranked,stacked,diverging}` | `TimeLine` | `Scatter{size}` | `DumbbellRange{dot,arrow}` | `Treemap` | `CirclePack{pack,bubble}` | optional `Radar`). The dev-facing index of all of these (thumbnail + long-format CSV shape + when-to-use + feasibility rule) lives at `docs/reference/chart-index.md` (section 20.9) - that is where an author picks. Only propose a NEW renderer if (1) neither gallery's relevant archetype maps onto the base set, AND (2) >=2 indicators need it. A single indicator's wish for a novel form is met by the nearest base chart, never by a new Svelte file. Jony's gallery sweep (2026-06-03) confirmed the base set covers every relevant archetype except `Treemap` (added) and `CirclePack` (restored 2026-06-04); streamgraph / sankey / violin / sunburst / chord / alluvial remain out of scope.

---

## 16. Geography-first navigation + swappable landing page (Jony verdict; user freeze)

User freeze: "DATA SET IS FROZEN; front-end pages BOUND TO NAVIGATE BY GEOGRAPHY > Country. State. District. sub-district", with **chart type swappable** and **indicator swappable** on a landing page, with a **sensible default per indicator**.

### 16.1 The swappable contract (grapher-owned, lightweight)

Render choice stays OUT of canonical/topic catalogues (ADR-0045) and lives in `datasets/grapher/indicator_render.json`. Additive MINOR bump v1.0 -> v1.1:

```
{
  "indicator_id": "fiscal/nsdp_per_capita",
  "chart_types": ["choropleth", "heatmap", "ranked"],   // ordered; [0] = default
  "default_mode": "absolute",
  "color_scale": { "type": "sequential", "scheme": "RdPu", "bins": 5 }
}
```

- `chart_types: string[]` - closed enum, ordered, index 0 = the sensible default. The picker offers exactly this list.
- Keep today's singular `chart_type` as a deprecated alias resolving to `chart_types[0]` (reader-before-writer, ADR-0047); remove after cutover.
- If absent, a PURE function `defaultChartTypes(indicatorMeta, grain)` infers from `value_kind`/`unit`/`entity_kind` (geo + single value -> `[choropleth, heatmap, ranked]`; two joined values -> `[scatter]`; ordered facet -> `[bar]`). No per-dataset code.
- Extend the `ChartType` union at `frontend/src/lib/grapher/catalogue.ts` (line ~14) from 3 values to `choropleth | heatmap | bar | line | scatter | radar`. One closed enum, one owner. Stays inside schema-is-the-design-system (the 8th indicator is a JSON edit, never a Svelte edit).

### 16.2 Grain-aware chart feasibility (stops "a map that cannot draw")

Spine Country > State > District > sub-district resolved from the entity ladder. The rendered grain is the page primary key and drives:

(i) **Searchable entities** = children of the current node at target grain + siblings for lateral compare (fed by `<PlaceSearch>`, section 14.4).

(ii) **Offered chart types** = `indicator.chart_types` INTERSECT `feasibleAtGrain(grain, geometryAvailable, hasFacet, hasTimeAxis)`:

| Grain | Entities | Feasible chart types |
| --- | --- | --- |
| Country | 36 states | choropleth (states), heatmap (states x years), ranked, line, scatter |
| State | districts of 1 state | choropleth IF boundary exists, heatmap (districts x years), ranked, line |
| District | sub-districts/blocks | choropleth only if sub-district geometry exists; else heatmap, ranked, line |
| Sub-district | villages/wards | ranked, heatmap; line if time series exists; map usually unavailable |

If geometry is missing at a grain, `choropleth` is silently removed and the default falls to the next entry in `chart_types`. This single intersection rule is what guarantees a citizen is never offered a map that cannot draw. (Ties to the 14.2 finding: district choropleth is silently dropped until district-grain data + reconciled geometry exist.)

### 16.3 Landing-page UX (one card per measure)

- **Default view:** one map/chart filling the column, rendering `chart_types[0]` for the current geography node, with the source/comparability line under it (`ChartShell` + C5), and a numeric legend. No KPI hero tiles (banned by doctrine), no second chart on load (one card per measure).
- **Controls, priority order:** (1) indicator picker (swaps the datapoint CSV file) top-left; (2) chart-type segmented control (within the feasible-intersect set) top-right; (3) geography drill - tap a region/row to descend, breadcrumb to ascend; (4) `TimeControl` in the toolbar, only when the indicator has >1 time value; (5) absolute/percent mode chip from `default_mode`, only when meaningful.
- **Labelling:** every colour scale carries a numeric binned legend + a no-data hatch swatch; every category has a text label; jargon stays out of the primary label (the artifact's `unit` formats the axis).

### 16.3a Chart-type switcher manifestation + citizen choice (Jony verdict 2026-06-03)

Answers the user's question "where is charting-type flexibility for indicators manifesting in the app, and does Jony have an opinion?" - **yes, he does, and it is the control already named in 16.3 (#2), made concrete:**

- The switcher is a SINGLE segmented control in `ChartShell`'s toolbar, top-right of the one card. NOT a dropdown, NOT a settings panel, NOT a second row of chrome.
- Rendered set = the feasible-intersect list (16.2) in `chart_types[]` order; `chart_types[0]` pre-selected and active on load.
- One segment per feasible type, each a 24px mono-glyph (map / grid / bars / line / dots), NOT a word - the glyph is the affordance; the active type's human name shows once as the chart's caption. Active segment filled; others outline.
- Mid-tier Android: thumb-reachable top-right, min 44px touch target per segment, horizontally scrollable only if >4 feasible types (rare; most indicators intersect to 2-3). Tap to swap. No long-press / gesture that competes with the platform back-swipe.
- **Swap is instant** - datapoint rows for `(geo, indicator, time)` are already loaded; only the renderer changes, no re-fetch. This is the whole point: different chart forms speak to different people, and the citizen flips between them for free.
- **Persistence = NONE in the URL (user override 2026-06-04, section 20.8).** Chart-type is in-memory component state only; reload and fresh-share both open on `chart_types[0]`. The URL carries only the navigation axes (geo + indicator + time), never the encoding - honoring the user's axiom "visualization type is not navigation type". An opt-in `#view=` copy-view-link is the only escape hatch, built ONLY if a real share-the-exact-form need appears - never auto-written. (This STRIKES the earlier `?view=<type>` persistence line.)
- **Anti-clutter (keeps freedom from becoming noise):** if the feasible-intersect set has exactly ONE member, render NO switcher (a one-option control is chrome that failed the deletion test). Max 4 segments visible. The switcher changes ENCODING, never DATA - indicator picker (left = what) changes data; type switcher (right = how) changes form.

This is also the citizen-choice answer to the user's "do not hard-pin the landing page to charts - let the end-user choose different visualization": the landing page is not pinned to a renderer; it opens on `chart_types[0]` and the citizen re-encodes in-memory, with the landing surface itself swappable per 16.1/16.2.

---

## 17. Lightweight indicator enrichment (validates F8 / section 3 long-format CSV decision)

User ask: enrichment/amendment of indicators "should be super lightweight ... quite a lot of them are timeseries, so if we granulate accordingly in a column or different file (perhaps column on time) amendments and enrichments become easier."

**This requirement is already satisfied by the section-3 long-format CSV decision - it is a confirmation, not new work.** The datapoint shape is one file per indicator: `datapoints/<kind>/<variable_id>.csv`, rows = `(entity_id, time, value)`. Therefore:

- **Add a new year of an existing indicator = append rows** to that one CSV. No schema touch, no migration, no other file affected.
- **Add a new indicator = add one new CSV file** + one catalogue row. Nothing else changes.
- **Enrich/correct a value = edit the single `(entity, time)` row** in that one file. The blast radius of any amendment is exactly one file, granulated by time exactly as the user described.
- **Facet/sub-category** (sex, age band, fuel) = either an extra column in the datapoint file or a sibling `--by--geo--facet--time` file, so a facet add is also one-file-local.
- Provenance stays light per F9 (4 optional fields: owner, title, vintage, url); `source_id` is a per-row FK to the source entity file, so re-citing a refreshed vintage is a one-cell edit.

**Doctrine line for the plan:** indicator enrichment is a single-file, append-or-edit operation by construction of the long-format CSV storage model. No enrichment workflow, no migration tooling, no per-indicator code is needed beyond editing the one datapoint CSV. This is the chief operator-ergonomics argument FOR the section-3 long-format CSV decision.

---

## 18. CHIPS / SIDE framework decision (Hans + Max verdict 2026-06-03)

User ask: "is the CHIPS framework a recognized framework? can we compute and use it to rank states across India? the radar chart across segments of states is useful."

**What it is:** CHIPS (Connect, Harness, Innovate, Protect, Sustain) is the composite in the **State of India's Digital Economy (SIDE)** report by **IPCIDE - the ICRIER Prosus Centre for Internet and the Digital Economy**. ICRIER is a top-tier Indian economic think-tank; the index recurs annually (SIDE 2023-2026). Sub-national scores are usually "CHIP" (the Sustain pillar is largely national-only).

**Decision: INGEST-AS-PUBLISHED; do NOT recompute. Frame as "one framework's view, not an official ranking."**

Rationale (Hans + Max agree):
- **Credible but not official:** top-tier think-tank, recurring, serious advisory board - BUT not peer-reviewed and not government-endorsed; IPCIDE is co-funded by Prosus (Naspers), a standing interest-alignment that must be disclosed on the source row.
- **Do NOT recompute** the 50-indicator composite: several pillars depend on global-only inputs (ITU, World Bank, GSMA, Ookla) that cannot be state-decomposed. A "yen-gov CHIP" would silently diverge from the published index and mislead - the classic "two live conventions" trap, and it fails the methodology-stable bar.
- **DO opportunistically ingest the state-decomposable underliers as their own indicators** (TRAI teledensity/broadband, Aadhaar saturation, UPI penetration, BharatNet coverage, UDISE digital infra, NCRB cybercrime) - standalone civic value, gold-sourced, lets a citizen see the inputs without yen-gov claiming to reproduce the composite. Sequence after the fiscal/demography refill blocks.

**Mandatory framing + fairness rules (Hans, enforced on every CHIPS view):**
- Preserve the report's own **large-state (>1 crore) vs small-state/UT (<1 crore) split**; never merge into one leaderboard (city-state-UT vs 20-crore-state is the classic unfair comparison).
- Render **Ladakh + Lakshadweep as "not ranked - insufficient data"**, never as worst-rank or blank-implies-zero.
- **Pin the SIDE edition year as a hard methodology-break boundary;** block any smoothed multi-year CHIPS trend line across editions with changed weights/indicators (Rosling Gap-instinct trap).
- Show the **score and score-gap, not just ordinal rank** (small rank gaps are statistically meaningless).
- **Do NOT overlay ruling-party colour** on a single-year CHIPS snapshot (inputs are slow-moving infra + central-scheme driven, not a CM scorecard).
- Layer CHIPS **on top of, not above, government primary sources** - offer a "Compare with" link to the **NITI Aayog SDG India Index** (government, UN-aligned, the most authoritative recurring state composite) and NITI India Innovation Index; show disagreements as methodology notes.
- Every CHIPS row carries `source_id` to one ICRIER/IPCIDE SIDE citation; disclose the Prosus co-funding on that source row.

**Chart choice:** the radar/spider the user likes is the **optional `Radar` renderer (section 15, #6)** - but Jony flags it reads poorly on mid-tier Android; **default the sub-pillar compare to `HorizontalGroupedBar` and offer Radar only as a secondary view.** CHIP-vs-NSDP-per-capita is a `Scatter`.

**Pre-ingest blockers (to docs/research/ before any ingest):** obtain the SIDE methodology annexure per edition (exact 50 indicators + sources + 16 sub-pillar weights + normalisation + per-state dropped-pillar list); confirm reuse/licensing terms for SIDE tables (think-tank tables are not automatically open data); record the per-edition indicator/weight diff (the methodology-break ledger).

---

## 19. Curated indicator catalogue + new-chart data feasibility (Max verdict 2026-06-03)

User ask: "curate a list of indicators of needed data" + the three new charts (N/S/E/W confidence, age-pyramid-over-time + workforce M/F, SGDP timeseries instead of circles).

### 19.1 Acquisition wave order (T1 = clean machine-readable gold source; T2 = multi-file/survey-join/base-break; T3 = PDF/decennial/recompute)

Sequence the easy wins first to break the **zero-district-data wall** (14.2):

1. **Economy / fiscal block first** (single portal, longest arcs, we already hold the core): GSDP nominal + per-capita NSDP 1980-81-> (RBI Handbook of Statistics on Indian States, T1); own tax revenue, fiscal deficit, outstanding liabilities, capital outlay, central transfers (RBI "State Finances: A Study of Budgets", T2 - base/RE/BE breaks).
2. **Demography state series** (unlocks the pyramid): population + age-sex + sex ratio (Census 1951-2011 + NCP projections 2011-2036).
3. **Agriculture APY** (cleanest district-grain entry, famously clean): crop area/production/yield by crop, state+district, 1966-> (DES "Agricultural Statistics at a Glance" / data.gov.in APY, T1) - this is the first district-grain indicator to light up the district choropleth.
4. **Then the join-heavy high-value T2 block:** NFHS health (IMR, immunization, stunting, anaemia - state+district, ~5-yearly), UDISE+ education (GER, dropout, PTR), PLFS labour (LFPR/WPR/unemployment by sex), SDG India Index (NITI, state+district).
5. **Digital underliers (CHIPS inputs, section 18):** TRAI teledensity, Aadhaar saturation, UPI penetration, BharatNet, UDISE digital infra, NCRB cybercrime.

Full theme-by-theme catalogue (Economy, Demography, Health, Education, Energy/Environment, Agriculture, Labour, Governance/Digital) with source/grain/span/cadence/tier per indicator is captured in the Max verdict; lift into `docs/` (Max remit) when W-rows are scoped. Note telecom-circle != state crosswalk caveat for TRAI series.

### 19.2 Age-sex pyramid per state over time (+ workforce reuse) - ACQUIRE

- **Spine = Census C-13/C-14** (age-band x sex, state AND district) at **1991, 2001, 2011** = 3 clean decennial actuals. **+ NCP "Population Projections 2011-2036"** at 5-year steps = 6 projection points. **Present actual vs projection as two visually distinct series** (Rosling: never blend projection and actual without a visible break). Census 2021 is delayed - do not assume it.
- **Workforce variant (M/F over time):** PLFS Annual Reports 2017-18-> give workforce by age-band x sex at state level annually (~7+ points, growing) - the better "moving" series. Do NOT silently splice PLFS to pre-2017 NSS-EUS (methodology break).
- Caveats to surface: decennial gap + delayed 2021 Census; projection-vs-actual break; PLFS-vs-NSS break; state-boundary changes (Telangana 2014, J&K/Ladakh 2019).
- Renders as `CategoryBar(mode="diverging")` + `TimeControl` (section 15) - no new component.

### 19.3 GSDP/NSDP timeseries heatmap (states x years) - ACQUIRE

- **Source = RBI Handbook of Statistics on Indian States** (machine-readable, gold), cross-checked vs MoSPI NAS.
- **Honour base-year breaks (Rosling):** ship **two layers** - (1) long **nominal per-capita NSDP** heatmap 1980-81-> for the sweep, and (2) **real (constant 2011-12) GSDP** heatmap 2011-12-> for honest cross-state comparison. Mark every base-year rebase (1980-81 / 1993-94 / 1999-2000 / 2004-05 / 2011-12) as a break annotation. Do NOT draw one continuous "real GSDP 1980-2024" series across 4 base revisions.
- Renders as `Matrix` (section 15, #2) - replaces the remittance circle-pack the user wants gone.

### 19.4 New chart-style data feasibility (Max verdict 2026-06-03 - factory / poultry / CO2 / cybercrime)

Scouting verdicts for the four new chart archetypes the user asked to "code up". Each pairs with a Jony-confirmed renderer (section 15). **Two warnings the user most needs to hear are flagged.**

| # | Chart | Indicator | Source (gold) | Grain | Span | Cadence | Tier | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Icon-cartogram (factory glyph) | count of registered / operating factories | **ASI, MoSPI** (eSankhyiki + Summary Results) | state (district patchy) | ~1998-99 -> latest | annual | T2 | **ACQUIRE** |
| 2 | Icon-cartogram (animal glyph) | head count by species; **poultry separate** | **Livestock Census, DAHD** | state + district | 2012 + 2019 (quinquennial) | ~5-yearly | T2/T3 | **ACQUIRE - NEW family** |
| 3 | Icon-cartogram (emitter glyph) | CO2 / GHG total per state | none credible (national-only) | - | - | irregular | T3 | **REJECT total-per-state** |
| 4 | DumbbellRange arrow | cyber crimes reported per lakh | **NCRB Crime in India** | state + UT | 2021 + 2022 (+ back) | annual | T2/T3 | **ACQUIRE + mandatory caveat** |

**Detail + the two load-bearing warnings:**

1. **Factories per state (ACQUIRE T2):** ASI is the legal Factories-Act register (gold). The cartogram MUST pick + label ONE field - recommend "factories in operation" (citizen-honest; many registered units are dormant). Absolute count favours large states -> offer a per-capita / per-area secondary view so the glyph is not a population proxy. Annotate NIC-revision + Telangana(2014)/J&K(2019) boundary breaks. Udyam/MSME is a DIFFERENT universe - never label it "factories".

2. **Poultry / livestock per state (ACQUIRE T2/T3 as a NEW family) - WARNING:** the parquet yen-gov already holds (`datasets/livestock/livestock_pashu_aadhaar.parquet`) is **NDLM Pashu Aadhaar TAG counts (`comparability=directional_only`, `no_rank_table`), NOT the Livestock Census.** It measures programme rollout, not animal population - sizing icons by it would rank states by tagging-drive speed, not livestock held. The honest animal-cartogram needs the **DAHD Livestock Census** (true enumeration, state + district, poultry cleanly separable, ~535.8M livestock + ~851.8M poultry in 2019). Keep the two as clearly-separated indicators; do NOT put livestock + poultry on one shared size scale (poultry magnitude >> livestock). District grain here is a second candidate (with Agriculture APY) to break the zero-district-data wall (14.2).

3. **CO2/GHG per state (REJECT total) - WARNING:** there is NO gold, comparable, multi-year per-state TOTAL-emissions series in India - the official MoEFCC inventory is national-only by design. Building one would force splicing incompatible state inventories or presenting civil-society estimates as official (fails the Rosling/OWID comparability bar). **Honest alternatives:** (a) BEST - national CO2/GHG over time as a `TimeLine` (gold, comparable over time), not a cartogram; (b) if a map is non-negotiable - **CEA power-sector CO2 per state** (gold, annual, actual) explicitly labelled "electricity generation CO2 only - not total emissions". The animated-emitter idea is doubly rejected: the animation by Jony (no signal beyond size + performance), and the total-per-state data by Max (does not exist credibly).

4. **Cybercrime direction (ACQUIRE T2/T3) - mandatory caveat:** NCRB publishes the per-lakh rate for 2021 AND 2022 (exactly the arrow chart's pair). **Rosling trap:** a rise in "cyber crimes reported per lakh" can mean BETTER reporting / awareness, not more crime - so an up-arrow may be a good-governance signal. The arrow chart MUST carry "a rise can mean better reporting, not more crime", suppress naive ranking (reuse the livestock `no_rank_table` precedent), and use NCRB's own denominator. This is the section-19.1 item-5 NCRB cybercrime underlier - acquire it there, reuse for the arrow.

Framing / denominator / methodology-break annotation for #1, #2, #4 are Hans's call (flagged inline). Icon glyphs (factory, animal, emitter) come from the closed sanitised icon registry per section 15.1 - NOT per-indicator art.

---

## 20. Persona round 3b (2026-06-04, research-only) - architecture refinements + IDP-informed UX

Answers a 28-part user message studying `https://indiadataportal.com` (IDP, by ISB/Bharti Institute) plus a pressing data-model challenge. Four subagents: **Gregor** (contract/integration), **Andre** (LLM/yen-ask), **Jony** (UX), **Max+Hans** (national-line data). Standing principle the user stated, folded in as doctrine:

> **DATA - SCHEMA - SCALE - ENRICHMENT is the spine. The backend exists to support this, not to constrain it; the frontend must accommodate the data, never restrict it.** When a legitimate data shape does not fit the frontend, change the frontend - not the data.

### 20.1 Data model: drop the "DDF" name, keep the shape (Gregor Q1 - the cargo-cult catch)

The user caught a real cargo-cult. DDF is **Gapminder's** "Data Description Format"; OWID does **not** use DDF (owid-grapher has its own long-format model: one row per entity-time-value + variable-metadata + entities table). CLAUDE.md section 0a names **OWID** as canonical. The triple-file decomposition (datapoints / concepts / entities) is IDENTICAL between DDF and OWID - so "adopt DDF" and "adopt OWID shape" describe the same on-disk normalisation. The only Gapminder-specific things we were importing are the `ddf--<kind>--by--<entity>--time` filename grammar and the "DDF" brand - neither of which we owe allegiance to (we read via DuckDB-WASM, never vizabi/ddf-validation).

**Verdict: HYBRID.** Keep the shape + Hans+Max's column contract verbatim (one file per indicator, append-a-row = new year, new-file = new indicator). DROP the "DDF" name and the `ddf--...--by--...--time` grammar (its `--` separator collides with single-dash kebab ids at the exact surface DuckDB globs). Adopt OWID-grapher directory-segmented names:

```
datasets/data/
  variables.csv              # was variables.csv (chartable measures = indicators); PK variable_id (== indicator_id)
  concepts.csv               # was concepts.csv (measured-noun identity; the F6 one-per-concept hook)
  topics.csv                 # was topics.csv (parent-pointer tree)
  entities/
    geo.csv                  # LGD admin ladder
    electoral.csv            # AC/PC + delim_year
    electoral_lgd_xwalk.csv  # decay-receipt overlap table
    party.csv
    source.csv               # 4 optional fields (section 7)
  datapoints/
    geo/<variable_id>.csv        # entity_id, time, value, source_id   -> glob datapoints/geo/*.csv
    electoral/<variable_id>.csv  # glob datapoints/electoral/*.csv
```

This RESOLVES the old section-3 "concepts.csv means measures vs concept_id means noun" ambiguity by giving them different filenames (`variables.csv` vs `concepts.csv`). Read path: DuckDB-WASM `read_csv_auto` over `datasets/data/`, same `query(sql)` surface; loaders glob `datapoints/<entity_kind>/*.csv`. One-paragraph "why not DDF" rationale -> `docs/concepts/indicator-naming.md`. Forecloses Gapminder vizabi tooling (never used; accepted).

### 20.2 Elections storage: split by read pattern, not a vague "escape hatch" (Gregor Q2)

Reasoned scale: ~0.5-1M candidate-level candidacy rows at full historical coverage (~4,041 ACs x ~14 cycles x ~12 candidates + PCs). Dominant read is **per-state** (~23K rows/state ~= 1-3MB CSV-gzip, <1s parse on mid-tier Android). The ONLY place columnar projection pays off is the single cross-state candidate-grain query (yen-ask `party_totals`/`closest_contests`, deep psephology) that globs all 30 state files (~15-25MB CSV-gzip vs ~8-12MB Parquet with projection pushdown).

**Verdict - three-way split:**
- **(a) Per-state results** read partitioned **CSV-gzip** (`datasets/elections/state=<slug>/results.csv`, each <5MB).
- **(b) ONE national `datasets/elections/candidacies.parquet`** (~0.5-1M rows) for cross-state candidate-grain deep analysis ONLY.
- **(c) A precomputed AC-summary CSV** (one row per AC per election: winner, runner-up, margin_pct, turnout_pct, winning_party_id; ~57K rows partitioned CSV-gzip) as the PRIMARY election read surface - serves `closest_contests`, `turnout_extremes`, the seat board directly; demotes the Parquet to deep-analysis-only.

**Concrete threshold rule** (kills hand-waving): a fact table stays CSV-gzip until it crosses BOTH (1) >~100K rows / >~5MB gzipped in one logical scan AND (2) the dominant query is cross-partition WITH column projection. Only `candidacies` crosses both. Edits section 3 (Parquet bullet) + EL rows.

### 20.3 Parties / symbols / colours = `entities/party.csv` (Gregor Q3, reconciles EL3)

Party identity is ONE entity file `datasets/data/entities/party.csv` (`party_id, short, full, eci_codes, brand_colour, symbol_id, wikipedia`). `party_id` is the SOLE canonical key; `eci_codes` is a descriptive multi-value ATTRIBUTE (a party carries several historical ECI codes), NOT a join key, NOT a re-introduced bridge. Symbols stay static SVG assets keyed by `symbol_id`, sanitised via the existing `frontend/src/lib/party-symbols/` allowlist; missing symbol -> plain dot. Colour stays the 3-layer resolver keyed on `party_id` (`brand_colour` is the anchor input). A candidacy datapoint carries TWO entity FKs (`entity_id` electoral + `party_id`) - the OWID multi-entity-dimension pattern; document once in `docs/concepts/indicator-naming.md`.

### 20.4 Office-holders family: merge government + alliances + CM/PM/cabinet (Gregor Q4)

`datasets/governments/` already half-exists as the right shape (`dim_offices.parquet` + `governments_office_holdings.parquet` = a term/holdings table). Government, alliances, and office-holders are all the SAME Canonical Data Model entity: **a role held by a person/party over a term.** Merge into one family in `datasets/data/`:

```
entities/office.csv     # office_id, name, office_kind(cm|pm|president|cabinet_minister|...), jurisdiction_entity_id, portfolio
entities/holder.csv     # holder_id, person_name, party_id (FK, nullable)
datapoints/office_holdings.csv   # office_id, holder_id, term_start, term_end (null=incumbent), source_id
datapoints/alliance_membership.csv  # alliance_id, party_id, term_start, term_end, source_id   (same term-shape; alliances are NOT a 4th table)
```

`term_end=null` = incumbent (never `datetime.now()`). The jurisdiction FK lets a place hub `/s/:state` show "current CM + cabinet" without a bespoke join (reuses EL4). New `docs/concepts/office-holders.md`. Migrate the existing parquets, do not rebuild.

### 20.5 Boundaries follow LGD grain (Gregor Q5 - CONFIRMED)

Admin boundaries keyed by **LGD codes** (state/district/sub-district/village); verified `dist_lgd` on `all.topojson`, 771/784 (98.3%) join. `entities/geo.csv.entity_id` at district grain IS the LGD district id -> datapoint joins geometry directly. Electoral boundaries keyed by **ECI code + delim vintage** (NOT LGD); geometry under `datasets/boundaries/electoral/delim=<year>/state=<slug>/`. The two key spaces relate ONLY through `entities/electoral_lgd_xwalk.csv` (snapshot crosswalk), never a shared `parent`/`district_id`. Cross-space overlay (electoral result on admin map) MUST route through the xwalk and surface `overlap_kind` - never overlay mismatched polygons (F3/EL2). One engine, two boundary families dispatched on `entity_kind` (F5).

### 20.6 `datasets/grapher/` + `datasets/_ops/` both KEPT (Gregor Q6)

**KEEP `datasets/grapher/`** - render hints, frontend-owned (ADR-0045); section 16.1 actively extends `indicator_render.json`. Do NOT fold into `datasets/data/`. ADR-0045 becomes a Design-rationale + Rejected-alternatives block in the frontend grapher doc per the section-9 ADR-retire-keep-receipts rule. **KEEP `datasets/_ops/`** - operator state, not citizen-facing; it is the correct home for the bits section 9 evicts from `datasets/reference/` (completeness/operator-state JSONs). Reshape contents, keep the tier. Neither is canonical data.

### 20.7 CirclePack RESTORED as base renderer #8 (user override + Jony 19.4)

User: "treemap doesn't replace circle drop - have both coded ... all screenshots i gave are necessary chart types." REVERSES the prior "circle-pack dropped" verdict. Base set is now 8 core + 1 optional (see amended section 15.1). Discriminator (so they are never redundant): **Treemap** = part-to-whole where precise magnitude COMPARE matters (tiles, zero dead space); **CirclePack/packed-bubble** = pure magnitude clusters / shallow hierarchy where the message is "these blobs, sized" not exact ranking (whitespace, grouping-feel). Both use a **sqrt area scale** (honest area). `Scatter(size)` still owns axes-bearing bubbles. All five user screenshots map: crime-arrow -> `DumbbellRange{arrow}`; bank-branch -> `GeoChoropleth{fill}`; economic-disparity -> `Treemap`; city-revenue -> `CirclePack{bubble}`; icon-cartogram -> `GeoChoropleth{symbol}`. Section 15.3 do-not-build edited; section 15.1 row #8 added.

### 20.8 Viz-type switcher WITHOUT querystring (user + Jony 19.2 - STRIKES `?view=`)

User axiom (the deciding principle): **"visualization type is not navigation type."** A querystring is the address of a place in the data; a chart form is how that place is drawn - encoding the second as the first is a category error and litters every shared link. **Verdict: in-memory component state only, default = `chart_types[0]`.** Reload and fresh-share both open on the indicator's opinionated default; the URL carries only place + indicator (+ time). Loses deep-link of the exact form - acceptable, even correct (recipient lands on the default, re-encodes in one tap). Escape hatch: an opt-in "copy view link" may append `#view=` ON DEMAND - never auto-written, built only if a real need appears. `frontend/src/lib/url.ts` does NOT gain a `view` param; the segmented control writes a Svelte `$state` rune in the toolbar, not history. Edits section 16.3a.

### 20.9 Chart index / registry (Jony 19.3 - new `docs/reference/chart-index.md`)

The operational face of schema-is-the-design-system: an author deploying a new indicator needs an index to pick a renderer from. ONE markdown reference doc, one row per base renderer, generated/checked against the live `ChartType` union so it cannot drift. Columns: `Renderer (mode) | Thumb (24px mono-glyph from the open icon family) | long-format CSV shape needed | Use when | Feasibility rule`. Opens with the two-line doctrine (consult both section-15.4 galleries -> pick from this index -> propose a new renderer only if neither gallery's archetype maps AND >=2 indicators need it). Drift guard: a contract test (sibling to `frontend/src/lib/grapher/catalogue.test.ts`) asserts every `ChartType` member has exactly one index row and vice-versa.

### 20.10 yen-ask grounding surface under the reset (Andre)

The 60->5 cleanup is SAFE for grounding because yen-ask only ever needed TWO stable, machine-readable artifacts + the datapoint files - the other ~58 schemas were write-time validators the model never reads. The contract (treat a column rename here as a breaking change with an eval gate):
- **Indicator catalogue = `datasets/data/variables.csv`** - the model's menu. Grounds on `indicator_id, name, concept_id, unit, topic, source_id, update_period_days`. **ADD two precomputed columns** so yen-ask never fact-scans to learn coverage (preserves D-04): `time_min,time_max` (year span) + `entity_kinds` (e.g. "state district"). File path is reconstructable from `indicator_id` - document the grammar, do not store a path column.
- **Entity dictionary = `datasets/data/entities/geo.csv`** - MUST carry an **`aliases`** column (pipe-delimited old/common names: "Madras|TN", "Orissa|Odisha", "Bangalore|Bengaluru"; ECI st_code "S22" as one more alias). This is the single highest-leverage grounding field - without it the model silently fails on every renamed place. The current `CatalogueState` type has no alias field; add it.
- **Datapoint files** = the fact surface, read at execute time via DuckDB-WASM; NEVER scanned at catalogue-build time.

Human-readable slugs win mechanically (tokenizer splits `tamil-nadu`/`literacy-rate` into semantic subwords; `S22`/`ind-042` tokenize to opaque fragments -> worse retrieval, more confabulation). Keep opaque codes ONLY as aliases. **Prompt-injection fence (OWASP LLM01):** catalogue `name`/`description`/`aliases` are operator-authored free text concatenated into the grounding prompt - gate at ingest (ASCII + max-length + no-control-char), wrap catalogue rows as DATA-not-INSTRUCTIONS in the prompt, and KEEP SQL hand-authored in `concepts.ts` + the closed `ConceptId` intent contract (the strongest defence - the reset MUST preserve it). **Eval gate:** extend `fixtures/intent-eval.json` to ~30-40 labelled questions (each indicator by name AND synonym; each entity by canonical AND alias; one staleness question per cadence class); run as a vitest gate on EVERY PR touching `variables.csv` or `geo.csv`; a drop below the >=90% top-1 baseline blocks the change. MiniLM in-memory cosine is enough; no vector DB.

### 20.11 National reference line per state chart (Max + Hans)

The user's instinct is sound but bundles three statistics Rosling would refuse to conflate. **Headline correction: "national median across states" (each state one vote) and "population-weighted national rate" (each person one vote) are DIFFERENT NUMBERS for different questions - for per-capita NSDP they diverge 20-40%. Never print "national" unqualified; always label which.**

| Indicator class | Reference-line type | Default | Verdict |
| --- | --- | --- | --- |
| A. Rate/ratio/per-capita/% (literacy, IMR, LFPR, per-cap NSDP) | pop-weighted national AND median-of-states | **pop-weighted national** (median as toggle) | ACQUIRE; pop-weighted only if numerator+denominator both held, else median labelled "median of states" |
| B. Count/total (factories, MGNREGA spend, livestock head) | national SUM annotation only | national sum (not a compare line) | DEFER median; prefer per-capita normalisation -> moves to Class A |
| C. Index/composite (CHIPS, SDG Index, HDI) | median-of-states, single edition | median-of-states | ACQUIRE within one methodology edition; never across breaks; CHIPS per large/small-state pool |
| D. directional_only / neutral-direction / un-annotated break | none | n/a | NO national line |

**Compute at ingest**, stored as a derived datapoint series on geo entity `entity_id=IN, entity_kind=country` in the same file (pop-weighted-national and median-of-states must be SEPARATELY addressable - reserved `--median` sibling or `stat` discriminator, Gregor's call). Decisive reasons: precision (pop-weighted needs full-precision numerator+denominator the browser lacks from rounded rates), provenance (a stored row gets `source_id`; an in-browser number cannot be cited - Holy Law #9), determinism (git-diffable). **MANDATORY provenance:** reserved `source_id` row `owner="yen-gov (derived)"`, footer reads "national line computed by yen-gov from state values" - a computed figure is explicitly NOT a government figure (F1/O9). Formula stored in the `derivation` column (this is just another F7 write-time-derived series, not a new mechanism).

**`direction` gate (Hans):** the green/amber/red above/on/below colour = `sign(state_value - reference) x direction` using the existing enum `higher_is_better|lower_is_better|neutral`. HARD GATE: an indicator MUST set `direction` (not `neutral`) to show the status colour; `neutral` -> neutral hue, no colour. Live hazard: most current `indicators.json` rows default to `neutral` - setting `direction` per indicator is a PRECONDITION, not an afterthought. Reconcile with the section-3 "direction is a render hint, stays frontend-side" - it still must be authored per indicator somewhere the renderer reads it. Ambiguous (set `neutral`, NO colour): population, sex-ratio (needs distance-from-target, defer), urbanisation, cybercrime (Rosling reporting-trap), fiscal-deficit (Hans per-indicator), per-capita energy. Clean wins (status colour SAFE): literacy(higher), IMR(lower), LFPR(higher), immunization(higher), stunting(lower), per-cap NSDP(higher), GER(higher), dropout(lower), PTR(lower). Coverage ~60-70% of the section-19 catalogue is Class A; ship Class A first (per-cap NSDP, IMR, literacy, LFPR = the demo set). **Pashu Aadhaar reconfirmed Class D** (the IDP screenshot is the same NDLM tag-rollout dataset; animal cartogram uses DAHD Livestock Census, no national line). UX marker: state line (solid, brand), median (thin GREY dashed, recessive, no fill), status glyph at latest point (direction-coloured), trend triangle + delta number (own-change, direction-coloured - a state can be below-median/red-position but improving/green-trend), numbers on hover only. Extend `TimeSeriesLine.svelte` with a `referenceSeries` prop + `StatusGlyph`; no new renderer.

### 20.12 Nav spine FREEZE + IDP-informed UX cluster (Jony - the centerpiece)

**The current bug:** the mobile header anchors the wordmark LEFT and the hamburger RIGHT, but the drawer slides from the LEFT - control and surface point opposite ways. **Coherence rule frozen: any menu trigger opens a surface on the SAME side as the trigger.** Three candidates were drawn (mobile ~360px first, the target device):

```
Candidate A - IDP-style top bar (left logo + right hamburger -> full-screen sheet)   [REJECT: keeps the split; heavy sheet for a one-tap drill]
+--------------------------------+
| YenGov            [search] [=] |   tap [=] -> full-screen category sheet
+--------------------------------+

Candidate B - one-side cluster (logo + menu trigger LEFT; search + ask RIGHT)         [GOOD: trigger+drawer same side]
+--------------------------------+
| [=] YenGov          [?] [ask]  |   tap [=] -> drawer slides from LEFT (coherent)
+--------------------------------+

Candidate C - geography-first spine (breadcrumb is the PRIMARY nav)                    [RECOMMENDED - FREEZE]
MOBILE ~360px                          DESKTOP >=1024px
+--------------------------------+     +-----------+----------------------------------+
| [=] YenGov           [search]  |     | YenGov    | India > Karnataka > Bengaluru U. |
+--------------------------------+     |           |  ^breadcrumb = primary nav       |
| India > Karnataka  > [v]       |     | PLACES    |----------------------------------|
|  ^ breadcrumb spine (sticky)   |     |  India    | Theme:[Economy v] Indicator:[v]  |
+--------------------------------+     |  States   |                                  |
| Theme: Economy  Indicator: v   |     | THEMES    |   [ map / chart fills column ]   |
+--------------------------------+     |  (grid)   |                                  |
|                                |     | COMPARE   |   [ time brush ............... ] |
|  [ map / chart fills column ]  |     | yen-ask   |                                  |
|                                |     +-----------+----------------------------------+
| [ time brush ..............  ] |     (desktop keeps today's left rail; only the
+--------------------------------+      breadcrumb row is added above the content)
  tap a map region  -> descend (breadcrumb grows)
  tap a breadcrumb  -> ascend
  tap [=] -> drawer (LEFT, same side as trigger): Themes grid + Compare + yen-ask
```

**FREEZE Candidate C, built on Candidate B's same-side cluster.** Section 16 already froze geography as the spine; C makes it the always-present sticky breadcrumb (the one element that cannot be deleted - it answers "where am I, up/down"). Hamburger/drawer becomes secondary (themes grid + compare + ask), trigger and drawer share the LEFT side (fixes the bug). Where things live: geography drill = the sticky breadcrumb (primary); search = top-right (a verb the citizen invokes); theme grid (the IDP 20-icon grid) = inside the drawer (mobile) / left-rail THEMES (desktop), a browse surface not a spine; indicator picker = a `[Indicator v]` on the content card (content selection within a place, not navigation). Extend `frontend/src/lib/LeftRail.svelte` (re-cluster mobile header); add one generic `frontend/src/lib/GeoBreadcrumb.svelte`. No new nav library.

Companion UX items (all reductionist, all reuse repo assets):
- **Quick-jump (long indicator lists):** sticky theme-chip jump strip (scroll-spy, IDP grid metaphor) as primary + a thin type-to-filter box inside the list as secondary. Drop alphabetical (serves no civic query). Small `frontend/src/lib/IndicatorJump.svelte`, reused by state page + theme drawer.
- **Deployed git SHA:** Vite `define` injects `__BUILD_SHA__` + `__BUILD_DATE__` at build time (from the Pages workflow `github.sha`); footer in `LeftRail.svelte` gains a muted second line `build a1b2c3d - 2026-06-04 [view]` linking to the commit. Provenance-as-UX, no runtime fetch.
- **Map attribution = ONE (i):** maplibre `AttributionControl({ compact: true })` (or our own `info.svg`) - one (i), tap reveals attribution. Most static welfare maps move to d3-geo SVG (14.5) so their attribution is the one-line `<SourceLine>` (C5); the (i)-collapse applies to the maplibre-fenced election explorer.
- **Methodology per indicator on /docs:** a small (i) by the chart title in `ChartShell` -> `/docs/indicator/<id>`, ONE generic route component (`frontend/src/routes/IndicatorDoc.svelte`) reading catalogue + render + provenance (never hand-authored per indicator). Shows description, methodology/definition + base-year/break notes, source (4-field), cadence + staleness, caveats/comparability, download (the one-file-per-indicator CSV = a direct static link). URL builder `url.indicatorDoc(id)`.
- **Opinionated default + filters (confirm):** open opinionated (`chart_types[0]`), offer exactly TWO citizen choices - the feasible chart switcher (in-memory, 16.3a) + a measure/facet picker (the IDP "Distribution of <measure>" dropdown -> our existing `FacetPicker.svelte`). NO blank x/y axis builder, NO Pie. IDP's Bar/Line/Scatter/Pie/Table row becomes our feasible switcher; IDP's measure dropdown becomes our facet picker.
- **Timeseries brush/slider:** ONE shared primitive (reuse `frontend/src/lib/charts/temporal-viewport/`), two skins - `TimeControl` (play/scrub for animated forms) + `<TimeBrush>` (drag-to-zoom range for line/area), mounted in `ChartShell`'s footer when the indicator has >1 time value. Both read ACTUAL distinct `time` values (no phantom years). Do NOT fork a per-chart brush.
- **Icon strategy (licensing-aware - HARD RULE):** IDP's footer is "(c) 2026 India Data Portal. All rights reserved" - their DATA is reusable-with-citation but their UI ICON ART is proprietary. **Do NOT scrape IDP icons.** The open-licensed equivalent already exists in-repo: `frontend/src/lib/icons/` ships a **Lucide (ISC)** registry with a build-time sanitizer + the party-symbol sanitizer reuses the same allowlist. Doctrine: ONE open icon family (Lucide/ISC; Phosphor/Tabler MIT as fallback for a missing glyph, recorded in `LICENCES.md`) for indicators + themes + menus + stat tiles + chart-index thumbnails + switcher glyphs; sanitized through the allowlist; served via the registry virtual module; NEVER scraped proprietary art.

### 20.13 backend/ + frontend/ restructure rows (Gregor Q7 - name the survivors)

Demolition (D-rows) says what dies; these say what LIVES and where (Holy Law #3 - surviving module boundaries are a contract). The parity oracle (`backend/tests/test_canonical_parity_oracle.py`) + the geo crosswalk fixtures are the irreplaceable assets (section 11) - named as SURVIVORS, never deleted without a replacement that re-passes them.

**BR (backend restructure)** under `backend/yen_gov/`: SURVIVE `canonical/` (writer now emits CSV to `datasets/data/` + the candidacies Parquet), `sources/` (ECI adapters/parsers - irreplaceable parsing knowledge), `pipeline/`, `preflight/` (check-overlap + F6 gate), `coverage.py`. NEW `utils/` (absorbs reusable `tools/`, D2). TRIM `core/` (keep schema_registry + geo/delimitation crosswalk builder; delete `io.write_artifact`, D1). REVIEW `emit/` (keep only canonical-CSV emit; delete JSON-projection half). DELETE `legacy/` (O1), `composers/` (D3). SPLIT `cli.py` (D5).

**FR (frontend restructure)** under `frontend/src/lib/`: CONSOLIDATE `charts/` (8 renderers + 3 primitives + modes; absorb OrderedCategoryBar + HorizontalGroupedBar + composition-bar into one `CategoryBar(mode=...)`; keep V2 variety per O2). KEEP `colors/` + `party-symbols/`. FENCE `maplibre/` (elections only, not on static welfare maps). RE-POINT `canonical/` (glob `datasets/data/datapoints/<kind>/*.csv`), `psephlab/` (PL1), `yenask/` (concepts.ts SQL + the 4 templates, YA1). EXTEND `grapher/` (ChartType union + chart_types[]).

**Kill the 50MB home load gets its OWN acceptance gate** (currently buried in section 12 step 10): measure home-route transfer before/after; target a first-paint payload of one datapoint CSV + one topojson tier (per 14.5), verified in-browser per CLAUDE.md section 13. The single biggest tortoise-to-leopard win.

---

## 21. Round 4 convergence (2026-06-04, debate-style, research-only) - rip-and-replace, CSV-only, modern UI

User directives this round (binding, supersede conflicting persona text per CLAUDE.md section 0a): FULL FREEDOM TO RIP / REPLACE / DESTROY - "clean future, no prisoners, no stranglers"; ONE file format (CSV) everywhere; elections per-election self-contained; delete all network-fetch code and reingest fresh from TCPD CSV; drop the DDF brand entirely; be rational (not blind pie/bar) about chart viz; freeze nav Candidate C and make the UI genuinely modern; move all glyph SVGs to `frontend/public/icons/`; build the replacement and kill the old in THIS plan; converge via persona DEBATE not independent review. Personas were run in internal-debate mode: Gregor-vs-Fowler (storage + deletion), Max-vs-Hans (doctrine), Jony (UI), plus an Explore fact pass.

### 21.1 Guiding doctrine - REPLACES the "DATA - SCHEMA - SCALE - ENRICHMENT" slogan (Max + Hans, converged)

The user asked us NOT to enshrine that off-the-cuff slogan but to derive the real spine from first principles + IDP (FAIR) + OWID + the Max/Hans division of labor. Converged doctrine:

> **yen-gov is a re-curation platform, not a data warehouse. We do not maximise how much data we hold; we maximise how many honest, comparable civic trajectories a citizen can see and trust.**

Five non-negotiables, in order:
1. **Question-first, not data-first.** Begin with a citizen question + an honest definition (Hans), then a vetted comparable source (Max) - never "we have this dataset, what now?". An authoritative-but-mis-framed number is worse than none.
2. **Joinable by issuing-authority identity (FAIR-Interoperable).** Every entity keyed to an LGD / ECI / ISO code, never a display name, so any two indicators merge on geography.
3. **Comparable as one methodology-stable series (OWID).** One indicator = one long-format `(entity, period, value)` series; new vintages UPSERT the same id; definition shifts get a `methodology_breaks` row, never a quiet redefinition.
4. **Cite-able by mandatory provenance (FAIR-Reusable, Holy Law #9).** Every row carries a `source_id` FK; no anonymous data reaches a citizen.
5. **Accessible by static-first delivery (FAIR-Accessible, Holy Law #1).** The schema is the design system: backend pre-emits, frontend bends to whatever the schema declares (closed renderer set). The backend supports the data; the frontend never restricts it.

**Pipeline of responsibility:** acquire (Max) -> define (Hans) -> shape/schema (Gregor) -> store (CSV writer, LGD/ECI/ISO + source_id) -> serve (static bundle, DuckDB-WASM) -> render (Jony + Citizen, closed renderer set).

**Why it beats the slogan:** "DATA-first" invites authoritative-but-misleading acquisition (split into acquire+define, both upstream of schema); "ENRICHMENT" (vague "add value later") becomes FAIR joinability + cite-ability as WRITE-TIME properties; "SCALE" becomes OWID methodology-stable comparability (more entities/years on the same series, never a re-mint); "SCHEMA" kept and sharpened (the slogan's two good instincts - "backend supports not constrains", "frontend shouldn't restrict data" - are already Holy Laws #1/#2 + the closed-renderer rule).

Home: new concept doc `docs/concepts/data-spine.md`, cross-linked from CLAUDE.md section 0a; harmonizes with (does not replace) `citizen-first.md`, `owid-alignment.md`, `schema-is-the-design-system.md`. One-line quotable form: *We do not collect data; we re-curate civic trajectories - question-first, LGD-joinable, methodology-stable, source-cited, and static-served - so the backend supports the data and the frontend bends to it, never the reverse.*

### 21.2 CSV everywhere, no parquet - FINAL (Gregor vs Fowler, converged; supersedes 20.2 + the section-3 Parquet bullet)

Debate outcome: Fowler wins the format COUNT (two formats = two loaders, two schema mechanisms, a permanent cognitive + grounding tax paid on every PR forever; the columnar-projection win is a premature optimisation for a cold query in a static app); Gregor wins that the CONTRACT must survive the format change. **Synthesis: ONE format (CSV) everywhere; the schema contract is enforced at the typed-read boundary + a write-time column validator, NOT by the storage format.** No survivor parquet, no dual loader at rest. The 20.2 three-way split that retained one `candidacies.parquet` is RETRACTED.

**Typed-read mandate (how the contract survives):** loaders MUST use DuckDB `read_csv` with an explicit `columns={col: TYPE}` map per file class, NEVER blind `read_csv_auto`. The per-file column contract (name + dtype + nullability) IS the schema, enforced by a write-time CSV validator. This replaces the ~60 JSON-Schema-on-parquet validators with one column contract per file class (Holy Law #3 preserved - the contract moved surfaces, it did not disappear).

**Per-family ruling (default = CSV; geometry topojson/geojson is NOT a parquet concern, untouched):**

| Family | Today | Ruling |
| --- | --- | --- |
| energy (6 parquet) | -> `datasets/data/datapoints/geo/<variable_id>.csv` long-format. CSV. |
| livestock (3 parquet) | -> `datasets/data/datapoints/geo/<variable_id>.csv`. CSV. |
| governments | -> `entities/office.csv` + `entities/holder.csv` + `datapoints/office_holdings.csv` (20.4 term-shape). CSV. |
| taxonomy (11 parquet incl. dim_*) | -> `datasets/data/{variables,concepts,topics}.csv` + `entities/{geo,electoral,electoral_lgd_xwalk,party,source}.csv`. Dims become CSV too. CSV. |
| reference | `pincode-directory.parquet` (~155K rows) -> CSV (few MB gzip; largest single CSV; workable). CSV. |
| boundaries | `boundary_layers.parquet` (layer-registry ATTRIBUTES) -> CSV. Geometry .topojson/.geojson unchanged. |
| _ops | `range-mime-probe.parquet` -> DELETE (CSV is text/plain; no parquet MIME/Range to probe; the deploy-workflow MIME/Range step dies too). |

Genuinely-unworkable check (honest): NONE. The only honest caveat is performance on the candidacies cross-state glob (a cold path), explicitly accepted by the user.

### 21.3 Elections layout - per-election self-contained CSV (Gregor; answers "ac-csv across years?" = NO)

Two election classes, each FILE is ONE election (never across years), so AC/PC delimitation merge/split is never reconciled in-file - each election is independently enrichable:

```
datasets/elections/
  assembly/                          # Vidhan Sabha, AC-grain
    state=<lgd-slug>/
      election=<year>/
        candidacies.csv              # candidate-grain (one row per constituency x candidate)
        summary.csv                  # constituency-grain (one row per AC) - PRIMARY read surface
  parliament/                        # Lok Sabha, PC-grain
    election=<year>/                 # ONE country-wide file per national election-year
      candidacies.csv                # all PCs across India, candidate-grain
      summary.csv                    # one row per PC
```

Locked decisions:
- "results" and "candidacies" are the SAME grain (one row per constituency x candidate); there is NO separate `results.csv`. The granular file is `candidacies.csv`; "results" is the colloquial label, not a second file.
- Assembly = per (state, year); Parliament = per (national year), country-wide single file (543 PCs x ~15 candidates ~= 8K rows; no state sharding). This is the "per-state AND per-country" the user asked for.
- AC-summary file: YES it exists, PER (state, year), NOT across years. The cross-year "how did this AC vote over time" view is assembled at READ time by globbing `assembly/state=<slug>/election=*/summary.csv`. There is NO stored across-years AC file. (Direct answer to "are you suggesting an ac-csv across years?" - no.)
- Hive partition keys (`state=`, `election=`) are mirrored as explicit columns inside each CSV so a globbed union stays self-describing.
- `candidacies.csv` columns: `entity_id, state, election_year, constituency_no, constituency_name, candidate_name, party_id (FK), votes, vote_share_pct (F7), position, result, sex, age, education, profession, candidate_type, source_id (FK)`.
- `summary.csv` columns: `entity_id, state, election_year, constituency_name, electors, votes_polled, turnout_pct (F7), winner_candidate, winner_party_id, winner_votes, winner_share_pct, runnerup_candidate, runnerup_party_id, runnerup_votes, margin_votes, margin_pct (F7), source_id (FK)`.
- Cross-state deep psephology / yen-ask candidate-grain query globs `assembly/state=*/election=*/candidacies.csv` (~420 files, ~0.5-1M rows, ~15-25MB CSV-gzip scanned) - a COLD path accepted in a static app; the warm path reads the small precomputed `summary.csv`.
- NOTE - aggregate electoral INDICATORS (turnout-pct charted on the electoral map, seats-won-by-party as a measure) are a long-format shape and live at `datasets/data/datapoints/electoral/<variable_id>.csv` (entity,time,value). The raw candidate-level record is a WIDE table that does not fit entity-time-value, so it keeps its own `datasets/elections/` family. Two surfaces, two shapes, deliberately.

### 21.4 Elections backend = ingest-only; delete all fetch code (user + Explore)

Source data is TCPD CSV already on disk; we reingest fresh and do NOT fight converting existing parquet. Explore confirmed the network-fetch code is CLEANLY separable (ingest/parse modules have ZERO reverse-deps on the URL builders): DELETE `backend/yen_gov/sources/eci/urls.py` + any HTTP-client/portal-recon code (check `backend/yen_gov/admin/*.py` for `httpx`/`requests` before deletion); KEEP the pure parsers (`constituencywise.py`, `partywise.py`, `people_panel.py`) and the canonical adapters, re-pointed to read local TCPD/ECI CSV. Simplify tests + docs to match (delete recorded-HTTP / ECI-HTML fixtures).

### 21.5 Section 20.13 REWRITTEN - clean replacement, old code DELETED in this plan (Gregor)

The prior 20.13 SURVIVE/TRIM/REVIEW framing is RETRACTED (answers the user's "why are we keeping old stuff in a rip-and-replace?"). We build the ingest-only backend + the CSV writer + the new CSV loaders, RUN them to produce the data, and DELETE every old module in the same plan. Git history is the only backup. Clean-replacement, NOT strangler: there is no dual-format loader, no compatibility shim. The format flip happens in ONE atomic cutover PR - before it the new code is built-but-dormant (pure addition, main still on parquet); after it the parquet is gone.

DELETE LIST (backend): all network-fetch/scrape code; `legacy/`; `composers/`; all parquet writers (parquet-emit path in `canonical/writer.py`); JSON-projection emitters (JSON half of `emit/`); `core/io.write_artifact`; the ~60 JSON schemas that validated now-deleted parquet/JSON artifacts; `datasets/_ops/range-mime-probe.parquet` + the deploy-workflow MIME/Range step; backend tests whose ONLY purpose was the fetch pipeline or parquet-byte/parquet-schema assertions.

BUILD LIST (backend): `backend/yen_gov/ingest/` (read local TCPD + source CSVs, parse via surviving adapters, normalise to long-format + the elections wide model); `backend/yen_gov/canonical/csv_writer.py` (the ONE writer emitting `datasets/data/**` + `datasets/elections/**/*.csv`, explicit per-file column schemas, deterministic sort, no `datetime.now` in content, source_id stamping); KEEP `preflight/` (check-overlap + F6 gate, against `variables.csv`); per-file CSV column-contract validators.

DELETE LIST (frontend): parquet loaders + DuckDB parquet byte-range config; JSON-projection consumers; true byte-dupe charts only (O2 keeps V2 variety); the 50MB home preload.

BUILD LIST (frontend): `frontend/src/lib/canonical/` re-pointed to DuckDB-WASM `read_csv(columns=...)` over the new CSVs (`query(sql)` surface unchanged); consolidated chart lib (CategoryBar(mode=...) absorbing OrderedCategoryBar + HorizontalGroupedBar + composition-bar; 8 base renderers + 3 primitives); new home route (first paint = one datapoint CSV + one topojson tier).

TEST ASSETS THAT SURVIVE (only because they validate NEW code, format-agnostic): `test_canonical_parity_oracle.py` (winner-votes parity; re-pointed to read CSV - per Explore it now validates against a frozen JSON fixture, not the old SQLites, so it survives a fresh reingest IF row counts + winners are byte-stable; if ingest logic shifts, re-baseline in a successor PR); geo/LGD/AC-PC crosswalk fixtures (validate the JOIN); check-overlap/F6 fixtures (validate `variables.csv`). TEST ASSETS THAT DIE: any fixture asserting parquet bytes / parquet schema-version / JSON-projection shape; any fixture exercising the fetch pipeline (mock HTTP, recorded ECI-HTML).

Kill-the-50MB-home-load keeps its OWN acceptance gate (measure home transfer before/after; first-paint = one datapoint CSV + one topojson tier; verify in-browser per CLAUDE.md section 13).

### 21.6 Double-underscore BANNED (Gregor)

`__` is BANNED in every filename and id. Directory segmentation + the existing kebab `<measure>-<unit>-<facet>` id grammar is sufficient. Rationale: `__` was Gapminder DDF's tag-concatenation device; we already dropped that brand; our topics are a parent-pointer tree (not concatenated tags); yen-gov already has a facet slot (trailing `-<facet>`), so `__` would be a SECOND way to express one thing; OWID-grapher itself does not encode dimensions with `__`. Multi-dimensional variables are handled WITHOUT `__`: (a) partition dimensions (state, year) -> DIRECTORY segmentation; (b) analytical facets (sex, fuel-type) -> EITHER a dimension COLUMN inside the long CSV (`entity_id,time,sex,value,source_id`, FacetPicker reads distinct values) OR separate facet `variable_id`s sharing one `concept_id` via the single-dash slot. Example - literacy by sex: CORRECT `literacy-rate-pct.csv` with a `sex` column, OR `literacy-rate-pct-female.csv` + `literacy-rate-pct-male.csv`; BANNED `literacy-rate__by-sex.csv`. Filename is always exactly `<variable_id>.csv` - one kebab token, no dunder.

### 21.7 Modern design system - kills the "1990" look (Jony)

Diagnosis (verified): the app looks 1990 because `frontend/tailwind.config.js theme.extend` is EMPTY (zero design tokens) - uniform 14px slate text, 4px corners, no elevation, a render-blocking Google-CDN font. The fix is one token layer + eight surgical moves, all reductionist (each REMOVES something).

- **Token home:** new `frontend/src/app-tokens.css` (CSS custom properties on `:root`, imported once in `main.ts`), MIRRORED into `tailwind.config.js theme.extend` so every utility resolves to a `var(--...)`. CSS vars are runtime truth (enables future dark theme); Tailwind is authoring ergonomics. Filling `theme.extend` is the single highest-leverage edit.
- **Type:** self-host (drop the CDN), `Inter` variable (OFL) for ui/body/data + `Noto Sans Devanagari` variable by `unicode-range` + `Outfit` only for the wordmark; all subset to woff2 in `frontend/public/fonts/`, `font-display: swap`, preload Inter-Latin. **Tabular numerals mandatory in every data context** (`font-feature-settings: "tnum" 1`). Type scale minor-third 1.2, base 16px (xs .75 -> 4xl 2.25rem); weights 400/500/600, 300 wordmark.
- **Colour (calm, civic-neutral):** ONE neutral ramp + ONE brand accent + a status triad. `--ink #0f172a`, `--ink-muted #64748b`, `--line #e2e8f0`, `--surface #fff`, `--surface-sunken #f8fafc`; brand `--accent #3538cd` (chakra indigo, deliberately NOT saffron/green to avoid party meaning); status `--pos #15803d`, `--caution #b45309`, `--neg #b91c1c` (DATA-direction only, never chrome). Data ramps come from each indicator's `grapher.color_scale`, never the accent - charts never fight the UI.
- **Spacing/radius/elevation:** keep Tailwind 4px scale but USE it (24-32px section padding, 44px touch targets, ~72ch measure); radius `--r-sm 6 / -md 10 / -lg 14 / -pill`; soft tinted elevation `--e1/-e2/-e3` (low-spread, cheap on mobile GPUs); default surface = `--e1` + `--line` hairline, never a 2px grey border.
- **Motion:** `--dur-fast 120 / --dur 200 / --dur-slow 320`; `--ease-out` (emphasized-decelerate), `--ease-spring` (drawer/segmented-thumb); `prefers-reduced-motion` collapses to ~1ms opacity-only. Feedback, never decoration; no ambient/looping animation.
- **The 8 moves (impact-ordered):** (1) self-hosted subset variable fonts + preload; (2) fill `theme.extend`; (3) tabular numerals + real type scale; (4) calm colour with data-colour isolated; (5) soft elevation + 10-14px radii; (6) translucent sticky glass app bar (`backdrop-blur` + hairline); (7) skeleton loading for DuckDB-WASM latency; (8) micro-interactions (press-scale, drawer spring, segmented-thumb, chart fade-in).

### 21.8 Frozen Candidate C, rendered modern (Jony)

Coherence rule (frozen): any menu trigger opens its surface on the SAME side. Mobile cluster = brand + `[=]` LEFT, `[search]` top-right; drawer slides from LEFT with `--ease-spring` (fixes the right-hamburger/left-drawer bug).

```
MOBILE ~360px                              DESKTOP >=1024px
+----------------------------------+   +-----------+-----------------------------------------+
| [=]  YenGov            [search]  |   | YenGov    |  India > Karnataka > Bengaluru Urban     |  sticky breadcrumb (glass)
|  ^ translucent sticky app bar    |   |           |  ^ primary nav, hairline separators      |
+----------------------------------+   |  PLACES   +-----------------------------------------+
| India > Karnataka  >  v          |   |  India    |  Theme [Economy v]  Indicator [v]  [i]   |  (i)=/docs/indicator/<id>
|  ^ GeoBreadcrumb (sticky, glass) |   |  States   +-----------------------------------------+
+----------------------------------+   |  THEMES   |  +-----------------------------------+  |
| Theme [Economy v]  Indicator [v] |   |  (grid)   |  |  map / chart (one card per measure)|  |
+----------------------------------+   |  COMPARE  |  |  [skeleton] while loading          |  |
|  +----------------------------+  |   |  yen-ask  |  |                     [map|bars|line]|  |  computed switcher (right)
|  |  map / chart (one card)    |  |   |           |  +-----------------------------------+  |
|  |  [skeleton]      [map|bars]|  |   |           |  |  12 |==gradient==| 679 ^           |  |  numeric legend + value-tick
|  +----------------------------+  |   |           |  +-----------------------------------+  |
|  | 12 |==gradient==| 679 ^    |  |   |           |  |  |----- time brush -----[]-----|   |  |
|  +----------------------------+  |   |           |  +-----------------------------------+  |
|  | |--- time brush ---[]---|  |  |   |           |  Source: RBI (as of 2024)  build a1b2c3d |
|  Source: RBI (as of 2024)      |  |   +-----------+-----------------------------------------+
+----------------------------------+    (desktop keeps today's rail; only the breadcrumb row is NEW)
  tap region -> descend; tap crumb -> ascend; tap [=] -> LEFT drawer (spring): Themes grid + Compare + yen-ask
```

Struck by the deletion test: full-screen category sheet (Candidate A); KPI hero tiles (one-card-per-measure); right-side hamburger (the bug); a second chart on load; alphabetical indicator index. CREATE `frontend/src/lib/GeoBreadcrumb.svelte` (sticky primary-nav spine, glass, tap-to-ascend crumbs + trailing `v` sibling-jump). MODIFY `frontend/src/lib/LeftRail.svelte` (same-side left cluster; glass app bar; spring drawer + scrim; `build <sha>` footer line). Companions: `IndicatorJump.svelte`, `Skeleton.svelte`, `SegmentedControl.svelte`, `routes/IndicatorDoc.svelte`.

### 21.9 Rational chart-viz doctrine - the switcher is COMPUTED, never a fixed menu (Jony)

Offered set = `indicator.chart_types[]` (grapher-authored, `[0]` default) INTERSECT `feasibleAt(dataShape, grain, timeCardinality, geometryAvailable)`. Pie / 3D / blind-bar are not "disallowed by policy" - they are UNREACHABLE because no row in the data-shape matrix ever emits them. Data-shape -> allowed-encoding matrix (pure function, no per-indicator code):

| Data shape (after the query) | time | Allowed encodings (intersect grain) |
| --- | --- | --- |
| one measure over geo, one slice | 1 | `GeoChoropleth{fill}` (iff geometry), `CategoryBar{ranked}` |
| one measure over geo, many slices | >1 | `Matrix` (entity x year), `TimeLine`, `GeoChoropleth{fill}`+`TimeControl`, `CategoryBar{ranked}` |
| one measure, 1-3 named series over time | >1 | `TimeLine`, `Matrix` |
| two measures joined per entity (+size) | any | `Scatter{size}` only |
| one measure split by ordered/diverging facet | any | `CategoryBar{diverging}` (+TimeControl if animated) |
| part-to-whole, precise compare | any | `Treemap` |
| pure magnitude clusters / shallow hierarchy | any | `CirclePack{bubble}` |
| start->end pair per entity | 2 | `DumbbellRange{dot,arrow}` |
| one measure over geo, glyph-honest | 1 | `GeoChoropleth{symbol}` |

Grain feasibility gate: `choropleth` is silently removed when geometry is absent at the rendered grain; default falls to the next `chart_types[]` entry (a citizen is NEVER offered a map that cannot draw). Intersect = exactly one encoding -> render NO switcher. The matrix can never emit pie/donut (angle is a perceptual lie -> part-to-whole goes to Treemap/CategoryBar{stacked}), 3D, a bar for two continuous measures (-> Scatter), or a blind unlabeled bar. A contract test (sibling to `frontend/src/lib/grapher/catalogue.test.ts`) asserts `ChartType` union <-> chart-index rows <-> `feasibleAt` matrix are 1:1, so no one can hand-add a pie.

### 21.10 Icons in public/ - glyphs in one swappable place (Jony + Explore wiring)

Target layout (confirmed): `frontend/public/icons/` (Lucide ISC, kebab `<id>.svg`, + `LICENCES.md` provenance ledger) alongside `frontend/public/party-symbols/`. Both are static swappable assets - swapping an SVG file on disk is the entire change. Explore confirmed the party-symbols sanitizer already reads from `frontend/public/party-symbols/`; copy that pattern. Re-point `iconRegistryPlugin` in `frontend/vite.config.ts` so `iconsDir = frontend/public/icons` (currently `src/lib/icons`); it still globs `*.svg`, parses each through the UNCHANGED allowlist (`frontend/src/lib/icons/allowlist.ts` + `parse.ts` stay - they are code, not assets), rejects the build loudly on any disallowed byte, emits the same `virtual:icon-registry`. Update the dev watcher path + the vitest fixture-walker path. The plugin's directory walk IS the manifest (icon id = filename stem, kebab regex). One open family (Lucide ISC; Phosphor/Tabler MIT fallback), each recorded in `LICENCES.md`; never scrape IDP art ("all rights reserved").

### 21.11 Country topojson decision - FROZEN: NO, do not switch to ehdata.org's geometry

Answer to "have we frozen switching the country topo/geojson to what ehdata.org uses (they show Lakshadweep, and it is fast)?": **NO - we keep our own** `datasets/boundaries/in/districts/all.topojson` (785 districts, LGD-keyed `dist_lgd`), with two frozen requirements. Reasons: (1) Lakshadweep is already present in our data - `lgd_district_id 553`, slug `lakshadweep-district`, plus a `state=lakshadweep` election partition; our 785-district file is one vintage NEWER than EHdata/Flourish's 766-region upload (it CLOSES their gaps, not the reverse). (2) "Fast" is not their geometry being special - it is inline static topojson + delta-encoded arcs + simplification; we own the same technique. Adopting an external file would re-introduce a provenance dependency we do not need and is keyed the same way (`lgd_district_code` == our `dist_lgd`). FROZEN requirements attached to the map PR: (a) a render smoke-test MUST confirm Lakshadweep + Andaman & Nicobar + all islands actually draw from our `all.topojson` (Explore could not byte-confirm island geometry without a render); (b) the topojson MUST be quantized/simplified (mapshaper) to match EHdata's snappiness and the kill-50MB-home gate. If and only if the smoke-test shows our file is missing island geometry do we revisit - and even then we FIX our own file (re-clip from the LGD source), we do not adopt theirs.

### 21.12 DDF brand scrubbed from the plan (housekeeping)

Per user ("scrub the plan of DDF string"), the Gapminder "DDF" brand and the `ddf--...--by--...--time` filename grammar are removed from the prescriptive text; the data model is described throughout as "long-format CSV" under `datasets/data/` with OWID-grapher directory-segmented names (section 20.1). The only retained mentions are the explicit "we dropped DDF and why" rationale in 20.1 + 21.6 and the provenance appendix.

---

## 22. Autonomous execution model - orchestrator + PR subagents (2026-06-04)

The user asked: "write it as PR work, merge with main when done; one main ORCHESTRATOR and the PR work in SUBAGENTS; parallelize, do not idle, keep building in parallel; use the custom agents in DEBATE/conversation style to converge, not independent reviews; write the plan to execute autonomously; break it into meaningful chunks; test only what is essential."

### 22.1 Topology

- **One orchestrator** (the default agent) owns the plan-doc, the Status Reckoner, branch hygiene, the merge queue, and the dependency graph below. It NEVER writes feature code directly; it dispatches.
- **PR subagents** (`runSubagent`) each own ONE chunk end-to-end: branch from main, build, write only the essential tests, self-verify gates, open the PR, and report back. Each subagent prompt embeds the chunk's DELETE/BUILD list + acceptance gates + the contract-invariants (21.x) so it executes without re-asking.
- **Persona subagents** are used in DEBATE mode (steelman the opposing view, converge to ONE verdict, mark `PLAN TEXT:`) ONLY when a chunk hits a genuine fork; never as a rubber-stamp review lane. Default pairings: Gregor<->Fowler (contract vs deletion), Max<->Hans (acquire vs define), Jony<->Citizen (craft vs comprehension).
- **Parallelism rule:** chunks with no shared file-set and no dependency edge run concurrently (separate worktrees/branches). The orchestrator keeps >=2 chunks in flight whenever the dependency graph allows - "do not idle."

### 22.2 Meaningful chunks (each = one PR; main green at every rest state)

> **CORRECTED 2026-06-04 (round 5).** The round-4 chunk graph below was tightened after a 4-persona ripple review (Explore + Gregor + Fowler + Jony). The single atomic cutover X1 is SPLIT into X1a (reader flip, both stores on disk) + X1b (parquet delete) so a cross-format parity gate can fire between them; B2 is split into B2a (catalogue) + B2b (per-family reingest); F2 is split into F2a (structural merge) + F2b (new renderers); a doc predecessor D-DOC0 (the column contract) is added; and four hidden dependency edges are drawn. The authoritative chunk list is the **Execution Ledger (section 22.5)** - this graph is the readable overview, the ledger is the merge-queue. All round-5 file-level corrections are in **section 23**.

Phase ordering respects the split format cutover (X1a reader-flip -> dual-read parity gate -> X1b parquet-delete). Letters group by subsystem; numbers are sequence within a track.

```
TRACK D (doctrine + docs)                 -- parallel from t0
  D-DOC4  STEP 0 - doctrine reconciliation: neutralise every CLAUDE.md + AGENTS.md
          assertion the rip invalidates BEFORE any code chunk merges (22.7)
          [HARD PREDECESSOR / kickoff gate of EVERY execution chunk]
  D-DOC0  column contract + typed-read mandate -> docs/architecture/data/canonical-store.md
          (the SINGLE column source of truth)   [HARD PREDECESSOR of B1, F1, drift test]
  D-DOC1  docs/concepts/data-spine.md (21.1) + CLAUDE.md 0a cross-link
  D-DOC2  docs/reference/chart-index.md + the 21.9 data-shape->encoding matrix
          [HARD PREDECESSOR of U4; the matrix is the contract feasibleAt() implements]
  D-DOC3  retire ADRs into subsystem docs per section 9 (keep-receipts; fully parallel)

TRACK B (backend rebuild)                 -- B1 then B2*; parallel with TRACK U
  B1   build ingest/ + canonical/csv_writer.py + per-file CSV validators; RE-POINT the ~12
       surviving sources/*/ingest.py off core/io.write_artifact onto csv_writer (dormant; main still parquet)
       [blocks on D-DOC0; tests: writer unit + FK/enum validator]
  B2a  emit entity + catalogue CSVs (variables, concepts, topics, entities/*) from existing taxonomy
       [blocks on B1; gate: FK validator]
  B2b  reingest existing families to CSV, per-family (B2b-energy / -livestock / -governments /
       -taxonomy / -elections-from-local-TCPD per 21.4); each gated by cross-format parity (22.6)
       [blocks on B2a]
  B3   (after X1b) delete parquet writers, core/io.write_artifact, JSON-projection emit half,
       allowlisted dead JSON schemas (NOT config validators - section 23); delete parquet DATA files
  B4   (after X1b) delete core/http.py + all Fetcher blocks in cli.py + sources/eci fetch + legacy/
       + composers/ + fetch/parquet fixtures + range-mime-probe + deploy MIME/Range step

TRACK U (frontend modern foundation)      -- parallel from t0, no data dep; order tokens->shell->icons->switcher->polish
  U1   app-tokens.css (ADDITIVE semantic vars) + fill tailwind theme.extend + self-host subset fonts
       + REMOVE index.html Google-CDN link/preconnect + retone app.css slate motif (21.7, section 23)
       [tests: build + visual smoke per section 13; Devanagari conjunct check]
  U2   LeftRail re-cluster + GeoBreadcrumb.svelte + glass app bar + spring drawer + same-side fix (21.8)
       + url.district() builder + /s/:state/d/:district route (breadcrumb needs the district node)
       [blocks on U1]
  U3   icons -> frontend/public/icons/ + LICENCES.md + repoint iconRegistryPlugin (3 paths) (21.10)
       [smoke ALL routes - TopicIcon is everywhere]
  U4   SegmentedControl + ChartShell toolbar + feasibleAt() (guaranteed ranked fallback)
       + ChartType union widen + grapher JSON migration + chart-index drift test (21.9, section 23)
       [blocks on D-DOC2]
  U5   Skeleton.svelte + IndicatorJump.svelte + routes/IndicatorDoc.svelte + ChartShell error/empty slots
       [blocks on U1]

TRACK F (frontend data cutover)           -- F1 depends on B2a+B2b + U1 + D-DOC0
  F1   new CSV loaders queryCsv(columns=..., glob) over datasets/data + datasets/elections
       (built + unit-tested); RE-POINT test_canonical_parity_oracle.py to CSV here (it is a REWRITE,
       not a survivor) + generalise it to summary==recompute(candidacies) (home still parquet)
  X1a  CUTOVER-READ (atomic seam flip): point every loader import at CSV. Parquet files REMAIN on disk
       (dead weight, unread). [gate: dual-read cross-format parity oracle, 22.6]
  X1b  CUTOVER-DELETE: delete parquet loader code + DuckDB parquet config + 50MB preload
       [blocks on X1a green; gate: kill-50MB in-browser + oracle-on-CSV runs non-skipped]
  F2a  STRUCTURAL: merge OrderedCategoryBar + HorizontalGroupedBar + composition-bar into CategoryBar(mode=...)
       (behaviour-preserving; blast radius is the production trio + DevChartsSandbox) [golden-render tests]
  F2b  NEW renderers: GeoChoropleth{fill,symbol} + Matrix + Treemap + CirclePack + C2/C3/C5 primitives
  F3   national reference line (20.11): TimeSeriesLine referenceSeries + StatusGlyph + direction gate
  F4   geography maps: d3-geo SVG welfare maps (14.5), district topojson quantize + Lakshadweep/A&N
       render smoke-test (21.11)

YA   yen-ask re-point (20.10): +time_min/time_max/entity_kinds on variables.csv + aliases on geo.csv
     + the 4 concepts.ts SQL rewrites (section 23) + extend intent-eval
     [blocks on B1 (columns) + B2b (data emitted) + X1a (read path); rides after X1a; intent-eval >=90% top-1]
```

Dependency edges that block (everything else parallel from t0): **D-DOC4 (Step 0) -> EVERYTHING** (it merges first; it is the kickoff gate so no later chunk cargo-cults stale doctrine); D-DOC0 -> B1, F1; D-DOC2 -> U4; B1 -> B2a -> B2b; (B2a+B2b) + U1 + D-DOC0 -> F1; F1 -> X1a -> X1b; X1b -> B3, B4, F2a, F3, F4; F2a -> F2b; U1 -> U2, U5; (B1 + B2b + X1a) -> YA. The orchestrator keeps >=2 chunks in flight: after D-DOC4 lands, TRACK D + TRACK U + B1/B2 all run from t0 while the cutover is being prepared.

### 22.3 Per-chunk Definition of Done (essential-tests-only)

Each PR: (1) only the tests that lock THIS chunk's contract - writer unit test for B1, the feasibleAt/chart-index drift test for U4, the intent-eval gate for YA, a render smoke-test for F4; no blanket coverage padding (Holy Law #10 at the appropriate tier, not gold-plating). (2) Full suite green at merge. (3) For any `frontend/`/`admin/` runtime change: in-browser smoke per CLAUDE.md section 13. (4) Docs updated in the same PR. (5) No `[DEBUG]`, no new hardcoding, no new mocks. (6) Orchestrator merges via the normal reversible workflow and stamps the Status Reckoner row with the PR number. (7) **Doctrine sync (Step-0 follow-through):** any chunk that flips a fact the doctrine files assert (a CLAUDE.md Holy Law / anti-pattern / topology row, or any of the 8 `AGENTS.md`) MUST update that exact line in the SAME PR - flipping the `MIGRATING (see plan section NN)` marker D-DOC4 planted into the new true statement. A chunk may not leave a doctrine line describing a world it just deleted.

### 22.4 Contract-invariants every chunk preserves (even under full rip-freedom)

1. Provenance FK mandatory (`source_id` on every datapoint + candidacy row, Holy Law #9). 2. LGD/ECI key separation - they meet only via `entities/electoral_lgd_xwalk.csv`, never a shared parent (F3 / 20.5). 3. One-indicator-per-concept (`concept_id` FK + check-overlap before minting; no grain prefix on ids, F6 / ADR-0044). 4. Schema-per-file, typed (explicit `read_csv(columns=...)` + write-time validator; never `read_csv_auto`). 5. Static-first, deterministic read path (no backend at runtime, `query(sql)` surface unchanged, deterministic sorted CSV, no `datetime.now` in content).

### 22.5 Execution ledger (the orchestrator's single merge-queue; one row per chunk)

This table is the **canonical execution tracker**. The orchestrator reads `Blocks on` as the only merge-queue authority, keeps the `Status` column current (`TODO -> IN-FLIGHT -> MERGED`), and stamps `PR#` on merge. The section-13 Status Reckoner tracks DESIGN decisions; this tracks EXECUTION. Gate names resolve in section 22.6.

| Chunk | Blocks on | Parallel-OK with | Gate | PR# | Status |
| --- | --- | --- | --- | --- | --- |
| D-DOC4 STEP 0 doctrine reconciliation (CLAUDE.md + 8 AGENTS.md) | - | (none - merges FIRST) | doctrine-marker-audit | direct-commit | DONE (2026-06-04, doctrine-migration map in 22.7) |
| D-DOC0 column-contract | D-DOC4 | all D/U/B1-prep | docs-review | #627 | MERGED |
| D-DOC1 data-spine | - | all | docs-review | #722 | MERGED |
| D-DOC2 chart-matrix | - | all except U4 | drift-stub | #721 | MERGED |
| D-DOC3 ADR-retire | - | all | grep-receipts-eq | - | TODO |
| U1 tokens+fonts | - | B*, D*, U3 | build+visual+devanagari | #720 | MERGED (sub-plan archived at [docs/archive/plans/20260604-u1-tokens-fonts-subplan.md](../docs/archive/plans/20260604-u1-tokens-fonts-subplan.md); four sub-rows U1.1=#714, U1.2=#716, U1.3=#718, U1.4=#720; distilled into [docs/architecture/frontend/design-system.md](../docs/architecture/frontend/design-system.md)) |
| U2 breadcrumb+drawer+district-url | U1 | B*, D* | build+visual | - | TODO |
| U3 icons->public | - | all | icon-build+all-routes-smoke | - | TODO |
| U4 feasibleAt+switcher | D-DOC2 | B*, U3 | chart-drift-test | - | TODO |
| U5 skeleton+jump+doc+chartshell-states | U1 | B*, U3 | build | - | TODO |
| B1 csv_writer + ingest re-point | D-DOC0 | U*, D* | writer-unit+fk-validator | #670 | MERGED (sub-plan archived at [docs/archive/plans/20260604-b1-csv-writer-subplan.md](../docs/archive/plans/20260604-b1-csv-writer-subplan.md); seven sub-rows B1.1..B1.7 shipped as PRs #629-#670; distilled to [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md)) |
| B2a entity+catalogue CSVs | B1 | U* | fk-validator | #688 | MERGED (sub-plan archived at [docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md](../docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md); eight emits B2a.1=#673, B2a.2=#675, B2a.3=#677, B2a.4=#680, B2a.5=#678, B2a.6=#682, B2a.7=#684, B2a.8=#686, closure=#688; distilled into [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md) section "Seed emitters") |
| B2b reingest families (per-family) | B2a | U* | cross-format-parity | #689 | DEFERRED-TO-SUBPLAN ([TODO/20260604-b2b-reingest-subplan.md](20260604-b2b-reingest-subplan.md); five family rows B2b.1=energy, B2b.2=livestock, B2b.3=governments, B2b.4=taxonomy-datapoints, B2b.5=elections-from-local-TCPD, B2b.6=closure) |
| F1 CSV loaders + oracle-rewrite | B2a, B2b, U1, D-DOC0 | U* | loader-unit+parity-oracle-CSV | - | TODO |
| X1a reader flip | F1 | - | dual-read-parity | - | TODO |
| X1b parquet delete | X1a | - | kill-50MB+oracle-non-skip | - | TODO |
| B3 delete writers+dead-schemas+parquet-data | X1b | B4 | suite-green+allowlist-audit | - | TODO |
| B4 delete fetch+http+legacy | X1b | B3 | suite-green | - | TODO |
| F2a CategoryBar merge (structural) | X1b | F3,F4 | golden-render | - | TODO |
| F2b new renderers (treemap/circlepack/choropleth/matrix) | F2a | F3,F4 | render-smoke | - | TODO |
| F3 reference line | X1b | F2*,F4 | direction-gate | - | TODO |
| F4 d3-geo + topojson | X1b | F2*,F3 | island-render-smoke | - | TODO |
| YA yen-ask re-point | B1, B2b, X1a | F2* | intent-eval>=90% | - | TODO |

Pre-cutover safety: tag the last all-parquet-green commit `pre-csv-cutover` at the F1/X1a boundary so rollback is `git checkout pre-csv-cutover`, not a log search.

Election-experience chunks (section 25; ride after the renderer consolidation; all on existing seams):

| Chunk | Blocks on | Parallel-OK with | Gate | PR# | Status |
| --- | --- | --- | --- | --- | --- |
| E1 ChartShell time_label slot (25.2) | F2a | E2 | build+visual | - | TODO |
| E2 PartyPill + --party-neutral token (25.3) | U1, F2a | E1 | build+visual | - | TODO |
| E3 state silhouette on StateAcMap+TileCartogram (25.4) | F2b | E2 | island-render-smoke+visual | - | TODO |
| E4 two highlight modes + margin sub-filter (25.5) | E3 | - | visual+legend-drift | - | TODO |
| E5 ParliamentArc seats invariant fix + countSeats seam (25.6a/6b-seam) | X1b | E1 | seats-invariant-test | - | TODO |
| E6 alternate counting methods (25.6b) | E5 | - | (sub-plan) | - | DEFERRED-TO-SUBPLAN |

### 22.6 Gates catalogue (what each gate name means + where it fires)

- **cross-format-parity** (B2b, per family): a harness queries the SAME logical question against (a) surviving parquet and (b) new CSV; asserts identical row count + per-cell equality after a typed read (no float-string drift, null===null not null==="" ). Lives in `backend/tests/test_csv_parquet_parity.py`; reads both real on-disk artifacts (Holy Law #7, no mocks); skips cleanly if either absent. The single most important deletion-safety gate - it is what proves the CSV values match before any parquet writer is deleted.
- **parity-oracle-CSV** (F1): the re-pointed `test_canonical_parity_oracle.py` (a REWRITE - its 4 hardcoded parquet paths become CSV) asserts per-constituency FPTP winner + margin against the frozen `canonical_winners_2026_05_19.json` fixture, AND asserts `summary == recompute(candidacies)` (winner = argmax votes ex-NOTA, margin = winner-runnerup).
- **dual-read-parity** (between X1a and X1b): registers BOTH parquet and CSV views in DuckDB, asserts identical results for (1) per-constituency winners, (2) per-family row counts, (3) a sampled `(entity_id, time, value, source_id)` set across every migrated family. Green => X1b may delete. This assertion file is itself deleted in X1b (only it needs both stores). This is the "old-read == new-read" oracle the rollback story requires.
- **fk-validator** (B1, B2a, B2b): the write-time CSV validator enforces, beyond dtype: `source_id` FK in `entities/source.csv`; `concept_id` FK in `concepts.csv` + `entity_id` in the declared entity file; closed-enum membership (`entity_kind`, `direction`, `result`, `chart_types[]`); no wall-clock value in content columns; deterministic sort; filename is exactly `<variable_id>.csv` (double-underscore ban, 21.6).
- **kill-50MB** (X1b): in-browser transfer measurement (CLAUDE.md section 13), before/after, home route under 50MB.
- **oracle-non-skip** (X1b): asserts the re-pointed CSV tests RUN (non-skipped) - a skipif-when-parquet-absent test reads as false green after deletion; DoD requires the CSV oracle to actively execute.
- **chart-drift-test** (U4): asserts `ChartType union <-> chart-index.md rows <-> feasibleAt() matrix` are 1:1, AND that `ranked` is present in every matrix row (the guaranteed non-empty fallback).
- **golden-render** (F2a): the CategoryBar merge is behaviour-preserving; golden snapshots on the existing call sites must not change.
- **island-render-smoke** (F4): byte-confirm Lakshadweep + A&N + islands actually draw from the arcs-only topojson (21.11).
- **intent-eval** (YA): yen-ask intent classifier >=90% top-1 on the eval set after the grounding-surface change.
- **devanagari** (U1): in-browser smoke renders one Devanagari conjunct word; a codepoint-only font subset that drops GSUB/GPOS shaping fails this.
- **seats-invariant-test** (E5): pins a known result so the parliament arc renders exactly `total_seats` dots with `sum(seats_won) == total_seats == COUNT(DISTINCT constituency winner)`; the ~2x double-count regression cannot return (25.6a).
- **legend-drift** (E4): asserts the two highlight modes (margin / party-won) + the `margin >= X` sub-filter read from ONE shared legend system, no per-map bespoke control (25.5).
- **doctrine-marker-audit** (D-DOC4): `grep` proves (a) zero un-marked stale assertions remain - every CLAUDE.md / AGENTS.md line the plan invalidates is either rewritten to the new truth or carries a `MIGRATING (see plan section NN)` marker; (b) the doctrine-migration map in 22.7 has a row for every marker; (c) no marker points at a non-existent plan section. The audit list is re-run as a tripwire at X1b and at plan close: zero `MIGRATING` markers may survive the final chunk.

### 22.7 Step 0 - doctrine reconciliation (keep CLAUDE.md + AGENTS.md honest during the rip)

The rip invalidates large parts of the standing doctrine (Parquet is the canonical store, DuckDB-WASM reads Parquet, `sources.parquet` ledger, the meadow tier, the indicator-catalogue schema, the ADR filing cabinet, the "no JSON projection" and "frontend reads Parquet only" anti-patterns, the DDF brand). If those lines are left intact, the FIRST execution agent that reads CLAUDE.md to ground itself will faithfully reintroduce the world the plan is deleting. So the very first merged chunk is a doctrine pass, not code.

**Scope (the doctrine surface):** `CLAUDE.md` (Holy Laws, section 3 topology, section 4 layer rules, section 10 anti-patterns, section 11 schema, section 12 provenance) + all eight `AGENTS.md`: `admin/`, `backend/yen_gov/`, `frontend/src/`, `frontend/src/lib/yenask/`, `datasets/livestock/`, `datasets/grapher/`, `tools/boundaries/`, `tools/iced_parity/`. Agent memory (`/memories/repo/`, `/memories/`) is derived, not authoritative (CLAUDE.md section 5) - it is NOT edited here; it self-corrects.

**Two-phase rule (avoids describing a future that does not exist yet):**
1. **Neutralise-now (in D-DOC4 itself):** for every assertion the plan invalidates, EITHER (a) rewrite it immediately if the new truth is already binding regardless of code state (e.g. "canonical store is long-format CSV under `datasets/data/`", "frontend reads CSV via DuckDB-WASM", the DDF-brand drop, the icons-moved-to-public path), OR (b) replace it with a `MIGRATING (see plan section NN)` marker if the fact only becomes true mid-rip (e.g. "Parquet writers deleted" is not true until B3). A marker is honest; a stale absolute is a trap.
2. **Flip-in-chunk (per-chunk DoD #7, 22.3):** the chunk that makes a marked fact true rewrites that exact marker into the new statement in its own PR. By plan close every `MIGRATING` marker is gone (enforced by doctrine-marker-audit).

**Deliverable:** D-DOC4 ships the edited doctrine files PLUS a **doctrine-migration map** (one table: `file:line old-assertion -> new-truth or MIGRATING-marker -> chunk that flips it`) appended to this section when executed, so the audit gate and every later agent can see the full reconciliation at a glance. D-DOC4 is cheap (no code, no tests beyond the grep audit) and merges FIRST; it is the kickoff gate in the prompt (24.4).

**Doctrine-migration map (executed 2026-06-04, directly under user authorization - NOT via PR; commit on `plan/data-charting-reset-round5`).** Every doctrine line the rip invalidates is now either rewritten to the binding new truth (neutralised-now) or carries a `MIGRATING (... per plan chunk(s) ...)` marker that the named chunk flips in its own PR (per-chunk DoD #7). `/memories/` left untouched (derived, not authoritative).

| File (assertion) | Old assertion | New truth or MIGRATING-marker | Chunk that flips it |
| --- | --- | --- | --- |
| CLAUDE.md (preamble) | "Canonical store is Hive-partitioned Parquet" | Rewritten: "long-format CSV under `datasets/data/`" + full DOCTRINE-IN-MIGRATION banner added | neutralised-now |
| CLAUDE.md Holy Law #3 | "Every cross-boundary payload gets a typed schema" | Rewritten: contract surface is per-file CSV column schema + typed `read_csv(columns=...)`; MIGRATING from JSON-Schema-on-Parquet | B3 |
| CLAUDE.md Holy Law #9 + section 12 | `source_id` FK to `datasets/taxonomy/sources.parquet` | Rewritten target `datasets/data/entities/source.csv`; MIGRATING marker | B2a/X1a |
| CLAUDE.md section 3 (`datasets/` row) | "Hive-partitioned Parquet per family" | Rewritten: long-format CSV under `datasets/data/`; MIGRATING marker | B2b/X1b |
| CLAUDE.md section 4 (meadow tier) | meadow tier stated as standing | MIGRATING marker: meadow retires at local-CSV reingest | B4 |
| CLAUDE.md section 10 anti-pattern | "Frontend reads Parquet via DuckDB-WASM only" | Rewritten: reads long-format CSV via `read_csv(columns=...)`; MIGRATING marker | F1/X1a |
| backend/yen_gov/AGENTS.md (canonical-pivot + doc link + FK) | "New writes target Hive-partitioned Parquet"; `sources.parquet` FK | Rewritten: CSV writer -> `datasets/data/**`; FK `entities/source.csv`; banner + MIGRATING markers | B2b/B3/X1b, B2a/X1a |
| frontend/src/AGENTS.md (canonical-pivot + doc link) | "SQL over Hive-partitioned Parquet ... HTTP Range" | Rewritten: SQL over long-format CSV via `read_csv(columns=...)`; banner + MIGRATING markers | F1/X1a |
| admin/AGENTS.md (canonical-pivot) | "reading `datasets/<family>/*.parquet` ... operator_state.parquet" | Rewritten: CSV under `datasets/data/`; CSV operator-state; banner + MIGRATING markers | (admin rewrite, plan-sequenced) |
| frontend/src/lib/yenask/AGENTS.md (3 lines) | "DuckDB-WASM against canonical Parquet"; "taxonomy parquets"; "Joins `taxonomy.sources`" | Rewritten: canonical CSV; taxonomy CSV; `datasets/data/entities/source.csv`; banner + MIGRATING markers | B2b/X1a |
| datasets/livestock/AGENTS.md (canonical + FK) | "canonical Parquet"; FK `sources.parquet` | Banner + MIGRATING markers: CSV under `datasets/data/datapoints/`; FK `entities/source.csv` | B4, B2a/X1a |
| datasets/grapher/AGENTS.md | (Parquet-era data shape implied; ADR cross-refs) | Banner added: data moves to CSV; render-split survives; ADRs retire into subsystem docs | neutralised-now |
| tools/boundaries/AGENTS.md | (section 12 FK `sources.parquet` implied) | Banner added: geometry NOT migrated (topojson/geojson frozen); FK target `entities/source.csv` | neutralised-now |
| tools/iced_parity/AGENTS.md | (Parquet-era canonical compare target) | Banner added: compare target moves to CSV; live fetcher stays out of citizen ingest (network-fetch deletion 21.4) | neutralised-now |
| docs/agents/bootstrap.md + .claude/skills/bootstrap/SKILL.md | (no migration awareness) | Banner + step-6 read of the reset plan added so every persona loads the binding rip doctrine | neutralised-now |



A 4-persona ripple review (Explore codebase-audit + Gregor contracts + Fowler deletion-craft + Jony UI) found the round-4 prose was decision-complete but understated the cutover's blast radius by ~40%. These corrections supersede the conflicting round-4 bullets they name; the chunk graph (22.2) and ledger (22.5) already fold them in. No data-shape decision is reopened.

### 23.1 Backend deletion blast radius (supersedes 21.4 + 21.5 "delete half")

- **`canonical/writer.py` is a FULL REWRITE, not a half-delete.** It is the SOLE canonical emission point (`COPY ... TO ... FORMAT PARQUET` -> CSV row emission). B1 reconstructs it as `csv_writer.py`; the parquet writer is deleted whole in B3. Also rewritten/deleted: `canonical/boundary_layers_seed.py` (emits `boundary_layers.parquet` -> CSV catalogue) and `canonical/election_events_seed.py` (emits `election_events.parquet` -> CSV).
- **Fetcher blast radius is wider than `sources/eci/urls.py`.** DELETE `backend/yen_gov/core/http.py` (the Fetcher class) entirely; remove/rewrite all five `with Fetcher(...)` blocks in `cli.py` (they wrap every election ingest command - re-point to read local TCPD CSV); audit the whole `sources/eci/` directory for HTTP-using modules (B4).
- **`core/schema_registry.py` is DELETED with the 60 schemas; it has 80+ importers.** Every caller of `schema_version()` / `schema_id()` (e.g. `adapters/eci_ae_panel.py`) must source version from a CSV header or a lightweight `datasets/data/_schema/index.json`, not from JSON Schema files. `admin/schemas.py` (validates JSON schemas) is DELETED. `entities_seed.py` `$schema`-stripping becomes a no-op and is removed.
- **`core/io.write_artifact` has 20+ callers in SURVIVING ingest** (`sources/iced_*`, `sources/rbi_xlsx`, `sources/rbi_hbs_*`, `sources/rbi_appendix_*`, `india_geodata/power_plants.py`). Re-pointing those onto `csv_writer` is a **B1 deliverable**; B3 may delete `core/io.write_artifact` ONLY after B1 re-points them, or the backend fails at import. NB a SECOND `write_artifact` exists in `sources/rbi_hbs/emit.py` (distinct JSON dumper) - D1 targets `core/io.write_artifact` only; name the module path in the delete PR.
- **Schema deletion is ALLOWLIST-driven, not `glob-rm`.** Delete only schemas validating a now-dead parquet/JSON artifact. RETAIN config/control-plane validators: `processing`, `elections-config`, `eci_pins`, `topojson-config`, `schema-compatibility`, `schema-evolution`, `manifest`. The B3 PR lists each deleted schema next to the artifact whose death justifies it.

### 23.2 The column contract has ONE machine-readable home (supersedes 21.2 typed-read bullet)

The per-file-class column contract is **one machine-readable artifact** (the ~5 retained schemas under `datasets/data/_schema/`, or one `columns.json` per file class) and is the SOLE source for all three consumers: (a) the backend write-time validator validates emitted headers + dtypes against it; (b) the frontend `read_csv(columns=...)` maps are GENERATED from it (build-time codegen or load-time fetch), never hand-typed; (c) the drift test asserts `writer-emitted header == contract == reader-expected columns` per file class. No second hand-maintained copy of column names/types may exist - that is exactly ADR-0047 alternative F (rejected: duplicate Python+TS constants drift). This is what keeps invariant #4 a real contract after the 60 schemas are gone.

### 23.3 Frontend read-path rewrite (supersedes 21.5 "re-point loaders")

- **`frontend/src/lib/canonical/duckdb.ts` `queryParquet()` is RENAMED `queryCsv()`** and its signature gains glob support: it must emit `read_csv('/data/.../*.csv', columns={...})` and support DuckDB multi-file unions for the elections layout (`assembly/state=*/election=*/summary.csv`). The ~40 callers migrate to explicit `columns={...}` maps (generated per 23.2). `canonical/types.ts` `format` union loses `"parquet"`; `indicator-from-canonical.ts` (core loader) is rewired.
- **The 4 yen-ask SQL templates in `frontend/src/lib/yenask/concepts.ts`** (party_totals, closest_contests, constituency_result, turnout_extremes) construct entity_ids from parquet columns; YA must show the before/after SQL for each (old: `CONCAT('IN-', state_code, '-AC-2008-', ac_no)`; new: `SELECT entity_id FROM summary.csv` where `entity_id` is a direct column). CSV `entity_id` MUST byte-match the old parquet id format or every election render breaks (verified in B2b parity).

### 23.4 Elections layout sharpening (extends 21.3)

- **Parliament CSVs carry `state` as a MANDATORY column** even though `parliament/election=<year>/` has no `state=` path partition; `entity_id` = `IN-PC-<delim>-<state>-<pc_no>`. Without it `constituency_no` is non-unique within the file (it restarts per state) and per-state joins break.
- **EL7 - `coverage.py` disposition:** it is assembly-only today (zero PC logic). Either extend it to discriminate AC vs PC coverage, or explicitly scope-fence it to assembly with a doc note - decide before B2b emits parliament data. An aggregator silently blind to a whole election class is a latent reporting bug.
- **`summary.csv` is a DERIVED projection of `candidacies.csv`** (F7-computed: winner = argmax votes ex-NOTA, margin, turnout). The re-pointed parity oracle (22.6 `parity-oracle-CSV`) is the consistency gate that asserts `summary == recompute(candidacies)`.

### 23.5 Frontend design + nav corrections (extends 21.7 / 21.8 / 21.9)

- **Tokens are ADDITIVE** (new semantic names `--ink`, `--ink-muted`, `--accent`, `--surface`, `--line`, radius/elevation/motion vars), NOT a redefinition of Tailwind's stock `slate-*` ramp. Consequence: between U1 and the last component migration, an un-migrated component keeps its old-but-consistent look and is never broken; re-skin is per-component and reversible. The app is never half-broken, only progressively re-skinned.
- **U1's file set is bigger than `theme.extend`:** also REMOVE the Google-CDN Outfit `<link>` + two `preconnect`s in `index.html` (or the self-hosted font double-loads); retone the hardcoded `slate-400` ballot motif in `app.css` onto a `--surface-sunken` token; move LeftRail's hardcoded brand hex (`#d97706`, `#15803d`, `#000080`) + Outfit dependency onto tokens (in U2).
- **Devanagari subset MUST retain the script's GSUB/GPOS shaping tables + conjunct glyphs** (`fonttools subset --layout-features='*'` / glyphhanger by script), never a codepoint-only prune (which silently breaks conjuncts). Preload ONLY Inter-Latin (one `<link rel=preload>`); Devanagari fetches on demand by `unicode-range`. `font-display: swap`.
- **`feasibleAt()` has a GUARANTEED terminal fallback: `CategoryBar{ranked}`.** Every shape reaching the renderer has at least `(entity, value)`, so the intersect is never empty even when `chart_types:["choropleth"]` and geometry is absent - the citizen sees a ranked bar, never a blank card. The drift test asserts `ranked` in every matrix row.
- **Widening the `ChartType` union (`grapher/catalogue.ts`) is a breaking enum change.** U4 migrates existing `chart_type:"stacked-trend"` rows in `datasets/grapher/*.json` + updates the `topic-dispatch.ts` branch in the SAME PR, accepting the old literal as a deprecated alias until the JSON is migrated (reader-before-writer, ADR-0047).
- **`GeoBreadcrumb` needs a district URL node the router lacks.** `url.ts` stops at state + AC today (no `url.district`, no district route). U2 adds `url.district(stateCode, districtSlug)` + a `/s/:state/d/:district` route (reserve `/sd/:subdistrict`), slug derived from the LGD district id like `states.slug`. Geo stays in the PATH, never a querystring (consistent with 20.8). The indicator is a shallow path axis too (`/s/<state>/i/<indicator-id>`) so a shared link reopens place + measure; only the chart-type switcher stays in-memory.
- **F2 production blast radius is small:** the V2 orphan renderers (`OrderedCategoryBar`, `HorizontalGroupedBar`, `DumbbellRange`, `FacetPanelGrid`, `TileCartogram`) are imported ONLY by `routes/DevChartsSandbox.svelte`. The real migration target is the production trio (`IndicatorChoropleth` / `IndicatorRanked` / `IndicatorSmallMultiples` / `CompositionBar` via `topic-dispatch.ts`) + `StackedTrendV2` (elections). The sandbox is updated or deleted, not preserved.
- **Error/empty states fold into the existing `ChartShell`** (U5), no new component: loading -> Skeleton, fetch-fail -> "Data unavailable" + source line, zero-rows -> the no-data hatch swatch.

### 23.6 Deploy + repo-hygiene corrections (extends section 9)

- **GitHub Pages workflow:** add a `python -m yen_gov emit-manifest` step BEFORE the static-copy step so `datasets/manifest.json` is freshly emitted from the CSV writer; the file-copy list changes (parquets gone, CSVs added). The cutover (X1b) CLEARS and rebuilds the manifest - the old parquet-listing manifest cannot coexist with CSV storage.
- **`config/` survivors must be named:** decide per file (`eci-pins.json`, `elections.json`, `processing.json`, `topojson.json`) which survive vs fold into a concept CSV / single `config.json`; their schema validators are RETAINED (23.1).
- **`tools/` + `docs/` sweep:** section 9's "fold reusable / delete the rest" must list the survivor set, and the ADR-retire PR (D-DOC3) runs a `git grep` for links to deleted paths (`datasets/indicators/in/`, `datasets/ephemeral/`, old schema paths) and rewrites every match - rotted cross-links are a Definition-of-Done failure.

### 23.7 Per-chunk test disposition (DELETE / REWRITE / NEW) - the churn map

Every cutover chunk's PR body carries a 3-column test-disposition table. Pre-identified high-churn files:

| File | Disposition | Chunk | Note |
| --- | --- | --- | --- |
| `frontend/src/lib/canonical/indicator-from-canonical.test.ts` (~2300L) | REWRITE (or large DELETE) | F1/X1a | mocks `duckdb.ts`; fixtures stay, query path flips parquet->csv |
| `backend/tests/test_canonical_writer.py` (6-10min) | DIE -> replaced by csv_writer unit | B1/B3 | obsolete parquet-byte assertions; do not "fix", replace |
| `backend/tests/test_canonical_parity_oracle.py` | REWRITE (4 parquet paths -> CSV) | F1 | NOT a survivor; it is a code change |
| `frontend/src/contracts/sources-v2-shape.test.ts` | DELETE | X1a | asserts `format=="parquet"` |
| `frontend/src/lib/canonical/manifest.test.ts` | REWRITE (`format:"parquet"`->`"csv"`) | X1a | 3 fixture literals |
| `frontend/src/lib/boundaries.contract.test.ts` + `.integration.test.ts` | REWRITE (`boundary_layers.parquet`->CSV) | X1a | |
| `backend/tests/test_boundary_layers_seed.py`, `test_lift_*_national.py`, `test_indicator_schema_v5.py` | REWRITE or DIE | B1/B3 | data-shape tests bound to parquet |

Rule: a PR that deletes a producer without listing the tests it obsoletes is incomplete. `read_csv(columns=...)` typed maps are the new contract surface - a wrong dtype is a silent value bug the cross-format parity gate (22.6) must catch.

---

## 24. Operator guide - how to execute this plan (for the next agent or human)

This section is the entry point. It tells a human how to follow the plan and tells an execution agent how to drive and update it. Read it first.

### 24.1 Plan identity + read order

- **Plan name** (the single artifact to follow): `TODO/20260603-data-and-charting-platform-reset-plan.md` - this file.
- **A human reads it in this order:** section 1 (what + why) -> section 21 (the locked doctrine: CSV-only, design tokens, rational charts) -> section 22 (execution model + the Execution Ledger 22.5 + the Step-0 doctrine reconciliation 22.7) -> section 23 (file-level ripple corrections every agent must honour) -> section 25 (election-experience UX) -> this section 24 (how to drive + update).
- **The two tracking tables:** the **Status Reckoner** (the table in the section-13 region) records DESIGN decisions (what was decided + by whom). The **Execution Ledger** (section 22.5) records EXECUTION state (which chunk is TODO / IN-FLIGHT / MERGED + PR#). For "what is done vs what is not done", the Execution Ledger is the ready-reckoner.

### 24.2 Current execution state

This plan is **Level-5 plan-only**. As of 2026-06-04 NO code has been written: every Execution Ledger row is `TODO`. Pasting the kickoff prompt (24.4) to an agent IS the user signoff that moves the plan from plan-only into execution.

### 24.3 Status lifecycle + the update protocol (every execution agent MUST follow)

Each Execution Ledger row carries one Status: `TODO -> IN-FLIGHT -> MERGED`, plus `BLOCKED` and `DEFERRED`.

- **BEFORE starting a chunk:** confirm every `Blocks on` cell for that row is `MERGED`; if not, the chunk is `BLOCKED` - pick a different one. Then flip the row to `IN-FLIGHT` in the FIRST commit of the chunk's branch, so two agents never grab the same chunk.
- **AFTER the PR merges:** flip the row to `MERGED` and stamp the PR number (the orchestrator does this as part of the merge).
- **Cannot proceed** (upstream not ready, external blocker): mark `BLOCKED` with a one-line reason.
- **Consciously postponed:** mark `DEFERRED` with a pointer to the sub-plan or the trigger that reopens it.
- The **Status Reckoner** is touched only when a DESIGN decision changes - not on every PR.
- **Rule:** the ledger is edited inside the chunk's own PR, never as a separate bookkeeping commit. The merge that ships the work is the merge that flips the status. This keeps the plan's history aligned with the code's history.

### 24.4 Kickoff prompt (paste this to a new execution agent to start)

```
You are an execution agent on yen-gov. Read CLAUDE.md and run the bootstrap skill first.
Your job: execute the next ready chunk of
TODO/20260603-data-and-charting-platform-reset-plan.md.

1. Read sections 1, 21, 22, 23, 24, 25 of that plan. The Execution Ledger
   (section 22.5) is your merge-queue and single source of truth for status.
   The FIRST chunk to merge is D-DOC4 (Step 0, section 22.7): reconcile
   CLAUDE.md + all eight AGENTS.md so no later chunk reintroduces the deleted
   Parquet/DDF world. Do not start any code chunk until D-DOC4 is MERGED.
2. Pick the next chunk whose every "Blocks on" cell is MERGED and whose Status
   is TODO. Honour the dependency edges in 22.2 and the strict ordering
   X1a (reader flip) -> cross-format/dual-read parity gate -> X1b (parquet delete).
3. Branch from main. Flip that chunk's Status to IN-FLIGHT in your first commit.
4. Build ONLY that chunk. Obey: the 5 contract-invariants (22.4); the gate named
   for this chunk in the gates catalogue (22.6); the file-level corrections in
   section 23; the per-chunk essential-tests-only DoD (22.3). No mocks, no
   hardcoding, ASCII-only, relative POSIX paths (CLAUDE.md). For frontend/admin
   runtime changes, in-browser smoke per CLAUDE.md section 13.
5. The cross-format parity gate (22.6) MUST be green before any parquet writer or
   parquet file is deleted. Never delete a producer without listing the tests it
   obsoletes (section 23.7 test-disposition table in your PR body).
6. Open the PR. On merge, flip the row to MERGED and stamp the PR number.
7. If the chunk turns out bigger than one PR, spawn a sub-plan per section 24.5
   instead of inlining the detail here.
Stop after your chunk merges and report which chunk is next on the queue.
```

### 24.5 Sub-plan spawning (keep the parent thin; do not blow the context window)

When a chunk grows past a single PR's worth of detail - more than ~5 sub-steps, its own design forks, or its own multi-row tracker - do NOT inline that detail into this file. Spawn a sub-plan:

- Create `TODO/<YYYYMMDD>-<slug>-subplan.md` with its own mini Execution Ledger.
- The sub-plan's H1 carries a back-pointer line: `Parent: TODO/20260603-data-and-charting-platform-reset-plan.md (chunk <X>)`.
- In THIS parent, the chunk stays as ONE ledger row with Status `DEFERRED-TO-SUBPLAN` and a forward-pointer to the sub-plan path. The parent never absorbs the sub-plan's rows.
- When the sub-plan completes, its parent row flips to `MERGED`, a one-line outcome is distilled into the right `docs/` home per CLAUDE.md section 5, and the sub-plan is archived under `docs/archive/plans/`.

Worked example: the alternate vote-counting methods (section 25 item 6b) are a sub-plan candidate - ship only the `countSeats(method, ...)` seam in-scope (FPTP the sole implementation), and spawn a sub-plan for ranked/approval/proportional what-ifs gated on a Citizen + Hans second opinion. This keeps the parent plan readable in one context window: a map of chunks + gates + invariants, not the full text of every chunk.

---

## 25. Election-experience UX refinements (round 6, Jony)

Jony verdict 2026-06-04 (research-only) on the election views being re-rendered under the frozen Candidate-C shell + section-21.7 tokens + section-21.9 rational chart-viz. Of the six asks, five are clear in-scope calls (removals/consolidations on existing seams - `ChartShell`, `getPartyColor`/`resolvePartyPalette`, `StateAcMap`, `TileCartogram`, `ParliamentArc`, `RacesBoard`); item 6b is a deferred sub-plan candidate. No new bespoke renderer is created.

### 25.1 Reference-study archetypes (adopt the pattern, never the pixels)

Import four interaction archetypes underneath existing renderers; copy no art.

- **A. Competitiveness-columns** (NYT "all races"): already realised as `RacesBoard` (group contests into margin bands; column heights = the headline at a glance). KEEP and reuse for AC results; do not rebuild. Canonical "many contests, one screen" device.
- **B. Entity-brush + persistent range label** (OWID grapher): any time-series carries a brushable extent with the selected start->end printed in the header (feeds 25.2). The brush is the only time control and doubles as the range label - no separate from/to dropdowns.
- **C. Swing-as-a-slider** (psephlab swing/what-if): one horizontal slider re-pivots a result by a uniform swing; this is the interaction shell the deferred counting-method seam (25.6) plugs into later. Adopt the AFFORDANCE now; defer the math.
- **D. Always-on provenance line** (PRS Legislative Research / TCPD): the source + year line is never collapsed away on an election view; it rides in `ChartShell`'s subtitle/source slot at all times. Trust is UX.

Rejected as bespoke art: hand-drawn cartograms, seat-by-seat decorative animations, party-logo confetti, scrollytelling (each fails schema-is-the-design-system). Genuine fork (Citizen second-opinion): which two of A-D lead the first cut (A+D are non-negotiable; B-vs-C order is the soft call).

### 25.2 Temporal labelling (mandatory chrome; lives in ChartShell header)

No election view renders without a visible time label - it is chrome, not a tooltip or a legend footnote.

- **Placement:** `ChartShell` header, immediately under the title, before the source line; tabular-numeral token (21.7). Add ONE generic slot `time_label` (or `{start, end, current}`) on `ChartShell` so every renderer discloses identically - no per-renderer code.
- **Single-snapshot** (AC results, one seat-map, one races board): show the single election year prominently, e.g. "Assembly election 2023" - the largest secondary element after the title.
- **Time-series** (seats-trend, vote-share-over-time, year-over-year choropleth): show START and END as a range, e.g. "1977 - 2024"; when a brush/TimeControl is active, the label reflects the BRUSHED extent live (the brush IS the range label, archetype B), and the scrubbed year prints on the TimeControl thumb.
- **Mandatory-when rule:** renders whenever the data has a `time` axis OR a fixed election vintage (every election view). The only exempt views are genuinely timeless reference layers (boundary outlines with no result bound), which must say so explicitly ("boundary, current delimitation").

### 25.3 Party pill contract (one component, schema-driven; symbol is separate)

One `PartyPill` component is the single coloured party token everywhere AC results show a party (races-board rows, AC drill-down, legend chips, histogram bins). No per-view pill variants.

- **Colour rule:** `PartyPill` calls `getPartyColor(party_id, row)` (the canonical 3-tier anchor/brand/fallback resolver); it NEVER hand-picks a colour. `anchor` -> full-bleed coloured pill; `brand` -> coloured accent ring/stripe on a paper-neutral body (resolver forbids brand colour as chrome fill); `fallback` OR no party row OR null `party_id` -> the NEUTRAL token, NOT the algorithmic hash hue ("unknown party" must read as unknown).
- **Neutral token:** add one design token `--party-neutral` (calm grey, e.g. slate-300 fill / slate-600 text) to the 21.7 token set - the single source of "unmapped party" colour across pills, maps, and arcs (choropleth/hex unmapped cells reuse the SAME token; ties to 25.5 recede + the unmapped-region doctrine).
- **Label rule:** the pill ALWAYS carries `party_short` text; a bare swatch is never allowed (resolver contract: brand/fallback require a paired label).
- **Symbol composition (symbol is NOT inside the pill):** the SVG ballot symbol is its own glyph, loaded ONLY from the sanitised allowlist registry under `frontend/public`; it renders as a SIBLING next to the pill (`[symbol-glyph] [coloured pill: BJP]`), never as the pill's background/fill. An optional thin `PartyTag` wrapper MAY lay out `symbol? + PartyPill` in a row, but pill and symbol stay independent leaves so a view can show either alone.
- **Component impact:** new generic `PartyPill.svelte` (replaces ad-hoc inline chips in `RacesBoard` / `MarginHistogram` / legends); optional `PartyTag` layout wrapper. Both leaf-level, schema-driven.

### 25.4 State boundary on single-state district maps (choropleth + hex)

When the district choropleth (`StateAcMap`) or the hex cartogram (`TileCartogram`) is shown at district/AC grain for ONE state, the state outline is always drawn so the citizen instantly recognises which state they are in. Generalises to all states from one shared boundary source; no per-state code.

- **Choropleth:** draw the state boundary as a single non-interactive outline STROKE on top of the fills - 1.5-2px, calm slate, no fill, `pointer-events: none`. District internal borders stay hairline; the state border is the one bolder edge so the silhouette pops.
- **Hex cartogram:** draw the real state silhouette BEHIND the hex grid as a faint containing shape (very low-opacity neutral fill + thin outline, e.g. slate-200 at ~0.25). The hexes float inside their geographic envelope; the silhouette is decor, never clickable.
- **Generalisation:** both pull the outline from the SAME boundary geometry the choropleth already loads (the active node's state feature). Per the section-16.2 intersect rule, if the state outline geometry is missing the map is already not offered - no degraded case to design.
- **Component impact:** extend `StateAcMap` (outline layer above fills) and `TileCartogram` (silhouette layer below grid), both fed by the existing boundary source. No new component.

### 25.5 Two highlight modes + recede + margin sub-filter (one legend system)

The AC choropleth and hex cartogram support TWO encoding modes on a single shared legend system, flipped by ONE segmented control (reuse the 16.3a switcher pattern in the `ChartShell` toolbar; NOT a per-map widget).

- **Mode A - MARGIN (default, current behaviour):** fill = winner party colour; fill-opacity ~ margin of victory (today `0.35 + clamp(margin,0,30)/30 * 0.6`). Legend = the margin ramp.
- **Mode B - PARTY-WON / SELECTION** ("show me where BJP won"): pick a party (tap a legend pill or a cell). Cells WON by the selected party get a UNIFORM strong fill in that party's colour at FULL opacity (no margin ramp - winning is binary and must pop). Non-matching cells RECEDE: `--party-neutral` at low opacity (~0.15-0.2) + hairline border, so the selected set is the only saturated thing on the map. This fixes "today's highlights are too washed-out to pop".
- **Sub-filter (Mode B only) - "margin >= X%":** a single stepped slider / chip group (0 / 10 / 20 / 30 pp) in the toolbar. When set, only the selected party's cells with margin >= X stay fully filled; narrower wins drop to the recede treatment too ("where did BJP win COMFORTABLY (>= 20%)"). This is the swing-slider affordance (25.1 C): one thumb, instant re-render, no re-fetch (margin is already in the loaded rows).
- **Affordance:** the same segmented-control vocabulary as 16.3a (margin glyph / target glyph); party selection in Mode B is by tapping a legend pill, tapping again clears to all-parties. Recede treatment + neutral token are shared with 25.3 and the unmapped-region doctrine.
- **Component impact:** add `mode` + `selected_party_id` + `min_margin` props to `StateAcMap` and `TileCartogram`; both read the SAME legend component. Schema-driven, no per-map widget.

### 25.6 ParliamentArc correctness fix + swappable counting-method seam

**6a - Correctness fix (IN-SCOPE now; spec-level invariant).** The semicircle must encode ONE SEAT = ONE WEDGE/DOT. Hard invariant:

```
sum over parties of seats_won  ==  total_seats  ==  count of DISTINCT
constituencies in the (state, year) result.
```

The arc geometry already reconciles per-row dots to `total_seats`, so a visible ~2x means the INPUT is doubled upstream, not the renderer. Required: (1) trace the seats feed - `total_seats` and each party's `seats_won` must derive from `COUNT(DISTINCT constituency winner)`, NOT a row count that double-joins `summary x candidacies`, and NOT from summing both an "alliance" and a "party" attribution of the same seat; (2) add a contract assertion at the view-model boundary that rejects/clamps when `sum(seats_won) != total_seats` (fail-fast, fix the join, never silently halve); (3) one regression test pins a known result (e.g. a 234-seat state renders exactly 234 dots and 234 in the legend total).

**6b - Counting-method seam (DEFERRED / aspirational; sub-plan candidate per 24.5).** Today's FPTP "mutations" (the transforms raw votes -> per-seat winner -> seat tally) are RETAINED and become the first implementation behind a named seam. Do NOT build alternate methods now.

- **Seam shape:** a pure function `countSeats(method, candidacies, rules) -> SeatTally` where `method = "fptp"` is the only shipped implementation. `SeatTally` is the exact contract `ParliamentArc` / `SeatDonut` / `RacesBoard` already consume (`parties[]` with `seats_won` summing to `total_seats`).
- **Alternate methods** (approval / ranked / proportional what-ifs) become future implementations of the SAME signature, swapped UNDER the same renderer surface - no renderer rewrite, no new chart. They pair with the swing-slider affordance (25.1 C) as "what if counted differently".
- **Out of scope for the reset.** Open as a sub-plan; gate any build on a Citizen + Hans second opinion (counting-method changes are politically sensitive and must carry a loud "hypothetical recount, not official result" honesty banner).
- **Component impact:** no new component now - fix the seats feed + add the invariant test (6a); introduce the `countSeats(method, ...)` signature wrapping today's FPTP transform as the seam (6b), FPTP the only method until the sub-plan.

---

## Appendix - provenance of verdicts

Persona verdicts + Explore audits 2026-06-03 (research-only). long-format CSV confirmed by fetch of `open-numbers/ddf--open_numbers--world_development_indicators` (`topics.csv` = `tag,name,parent`; `datapoints--<ind>--by--<entity>--time.csv` = `entity,time,value`). Elections/psephlab/yen-ask shapes confirmed by Explore audit (entity-id, partition, LOC, blockers cited inline above). User refinements O1-O10 recorded in section 1 supersede conflicting persona text per CLAUDE.md section 0a.

Second persona round 2026-06-03 (research-only, "consult the custom agents for chart investigation"): **Jony (UI/UX)** -> sections 14.5, 15, 16 (engine split, 5-renderer consolidation, swappable grapher contract, geography spine, landing-page UX). **Max (Indicator Scout)** -> sections 18 (CHIPS data feasibility), 19 (curated catalogue + pyramid/heatmap ACQUIRE). **Hans (Governance)** -> section 18 (CHIPS ingest-as-published + framing/fairness rules; ICRIER/IPCIDE standing + Prosus disclosure verified against icrier.org). District coverage 771/784 (98.3%) verified by terminal join of `all.topojson dist_lgd` vs `lgd_districts.json` (section 14.2).

Third persona round 2026-06-03 (research-only, "use runSubagent to investigate and update the plan" + new chart asks): **Jony (UI/UX)** -> sections 14.3 (C2 legend value-tick), 15.1 (Treemap renderer; DumbbellRange arrow mode; GeoChoropleth symbol mode; circle-pack/packed-bubble/animated-SVG rejected; bespoke-art guard), 15.4 (standing reference galleries + consult-before-charting doctrine), 16.3a (chart-type switcher manifestation + `?view=` param + citizen choice). Galleries fetched + mapped: `revisual.co/chart-gallery` + `github.com/Data-Analytics/data-analytics.github.io` surfaced exactly one missing archetype (Treemap), validating the base set. **Max (Indicator Scout)** -> section 19.4 (factory ACQUIRE T2; livestock-census ACQUIRE NEW family - the existing NDLM Pashu Aadhaar parquet is tag-rollout NOT population; CO2-per-state REJECT - no gold comparable per-state total series, keep national `TimeLine` or CEA power-sector-only; cybercrime ACQUIRE T2/T3 with mandatory reporting-vs-incidence caveat). Two load-bearing warnings surfaced: animal-cartogram must NOT use the repo's existing livestock parquet; per-state total-CO2 cartogram is not feasible.

Persona round 3b 2026-06-04 (research-only, 28-part user message studying `indiadataportal.com` + a data-model challenge) -> section 20. **Gregor (Architect)** -> 20.1 (HYBRID: drop "DDF" name + `ddf--` grammar, keep shape + columns, rename to OWID `datasets/data/` - the user's cargo-cult catch confirmed: OWID does not use DDF, the shapes are identical, we owe Gapminder's brand/grammar nothing), 20.2 (elections three-way split + concrete >100K-AND-cross-partition-projection threshold), 20.3 (`entities/party.csv`, party_id sole key), 20.4 (office-holders term-assignment family + `docs/concepts/office-holders.md`), 20.5 (boundaries LGD-keyed confirm), 20.6 (KEEP grapher + _ops), 20.13 (BR + FR restructure rows naming survivors; parity oracle + geo crosswalk never deleted; kill-50MB-home gate). **Andre (LLM/yen-ask)** -> 20.10 (grounding surface = `variables.csv` + `entities/geo.csv` with aliases; +time_min/time_max/entity_kinds; injection fence keeps hand-authored SQL + closed ConceptId; intent-eval gate >=90% top-1; 60->5 cleanup safe). **Jony (UI/UX)** -> 20.8 (in-memory switcher, `?view=` struck), 20.9 (chart-index reference doc + drift guard), 20.11 UX layer (status glyph/reference line marker), 20.12 (NAV SPINE: Candidate C frozen on Candidate B cluster; ASCII mockups; quick-jump; SHA footer; (i)-attribution; `/docs/indicator/<id>`; time-brush; IDP icons proprietary -> use open-licensed Lucide already in repo, do NOT scrape). **Max + Hans (Governance)** -> 20.11 (national reference line: Class A pop-weighted/median, B sum-only, C median-per-edition, D none; compute-at-ingest derived series with reserved `source_id`; `direction` HARD GATE for status colour; Pashu Aadhaar reconfirmed Class D). IDP licensing checked by fetch of indiadataportal.com homepage + about (footer "all rights reserved"; data reusable-with-citation, UI icon art proprietary). User principle "DATA - SCHEMA - SCALE - ENRICHMENT; backend supports, frontend must not restrict the data" folded in as section-20 doctrine; user overrides (CirclePack restored 20.7; no-querystring 20.8) supersede conflicting persona text per CLAUDE.md section 0a.

Round 4 2026-06-04 (research-only, debate-style, ~13-part user message: full rip-replace freedom "no prisoners, no stranglers"; CSV-only everywhere; reingest from TCPD; scrub DDF; rational chart viz; modern UI; icons to public; autonomous orchestrator+PR-subagent plan) -> sections 21-22. **Explore** (fact pass) -> Lakshadweep present in LGD taxonomy (lgd_district_id 553, slug `lakshadweep-district`) + has an election partition; `all.topojson` is arcs-only (island geometry needs a render smoke-test to byte-confirm); `elections_candidacies.parquet` = 387,810 rows (~50-100MB CSV); network-fetch code (`sources/eci/urls.py`) cleanly separable with zero reverse-deps from ingest (check `admin/*.py` for httpx before deleting); parity oracle validates a frozen JSON fixture (format-agnostic, survives reingest); icons migration to `public/icons` clean per party-symbols precedent (change `iconsDir` in `vite.config.ts`). **Gregor vs Fowler** (debate, converged) -> 21.2/21.3/21.5/21.6 (ALL-CSV no-parquet no-strangler; elections per-election self-contained `assembly/state=/election=/` + `parliament/election=/`; AC-summary per-(state,year) NOT across-years; double-underscore BANNED; 20.13 rewritten as clean DELETE/BUILD in atomic-cutover PR chunks; 5 contract-invariants; typed `read_csv(columns=...)` replaces the 60 JSON schemas). **Max vs Hans** (debate, converged) -> 21.1 (the "DATA-SCHEMA-SCALE-ENRICHMENT" slogan REPLACED by the question-first/joinable/comparable/cite-able/static spine; new `docs/concepts/data-spine.md`). **Jony** (UI) -> 21.7 (design-token system kills the "1990" look: fill empty `theme.extend`, self-host subset variable fonts, tabular numerals, calm civic-indigo palette, soft elevation, motion tokens), 21.8 (frozen Candidate C rendered modern, same-side drawer fix, GeoBreadcrumb spine), 21.9 (rational chart-viz: switcher = `chart_types[] INTERSECT feasibleAt()`, pie/3D/blind-bar UNREACHABLE not merely banned), 21.10 (icons to `frontend/public/icons/` + LICENCES.md, allowlist sanitizer unchanged). **Country topojson** decision (21.11): FROZEN NO - keep our own 785-district LGD-keyed `all.topojson` (newer than EHdata's 766-region upload), with frozen requirements (a) Lakshadweep + A&N render smoke-test, (b) mapshaper quantize/simplify for speed. Autonomous execution model (section 22): one orchestrator + PR subagents, parallel tracks D/U/B/F with only F1<-B2+U1, X1<-F1, B3/B4/F2/F3/F4<-X1 blocking; persona DEBATE mode only at genuine forks. All round-4 verdicts research-only; no code written (Level-5 plan-only until user signoff).

Round 5 2026-06-04 (research-only ripple/second-order review, "engage the subagents and thoroughly review the plan for gotchas; reorganize for execution-trackability; guiding principle = ripple effects + second-order impact") -> sections 22.2 (corrected chunk graph), 22.5 (Execution Ledger), 22.6 (gates catalogue), 23 (file-level corrections). **Explore** (codebase blast-radius fact pass) -> `canonical/writer.py` is the sole emission point (FULL REWRITE not half-delete); Fetcher woven through 5 `with Fetcher(...)` blocks in `cli.py` + `core/http.py` (delete whole, not just `sources/eci/urls.py`); `core/schema_registry.py` has 80+ importers + `admin/schemas.py` (delete both, re-source version); `queryParquet()` -> `queryCsv()` with glob support + ~40 callers; 200+ test edits; `config/`/`tools/`/deploy-workflow/docs second-order impact (23.1/23.3/23.6). **Gregor** (contract + sequencing) -> SPLIT X1 into X1a (reader flip, both stores on disk) + X1b (parquet delete) so a cross-format parity gate fires between them (the rollback story); ONE machine-readable column-contract home (ADR-0047 alt F rejects two hand-typed copies, 23.2); write-time validator enforces FK/enum/no-wallclock BEYOND dtype; 4 missing dependency edges (D-DOC0->B1/F1, D-DOC2->U4, B1->B2 serial, YA->B2b+X1a) + 2 over-bundled chunks split (B2->B2a/B2b, F2->F2a/F2b); parliament CSV carries `state` as MANDATORY column; EL7 `coverage.py` AC-vs-PC disposition; `summary==recompute(candidacies)` consistency gate; tag `pre-csv-cutover`; drafted the Execution Ledger (22.5). **Fowler** (deletion safety + chunk sizing) -> cross-format parity gate is the single biggest hole (`test_csv_parquet_parity.py`, real-on-disk both stores, before deleting any parquet writer); `core/io.write_artifact` has 20+ callers in SURVIVING ingest (re-point is a B1 deliverable, B3 delete depends on it); per-chunk test-disposition table DELETE/REWRITE/NEW (23.7); schema deletion is allowlist-driven (RETAIN config validators); skipif-when-absent reads as false green (oracle-non-skip gate); X1 shrinks to a pure structural seam flip. **Jony** (UI/chart/nav) -> tokens ADDITIVE not slate-override (never half-broken); Devanagari subset MUST retain GSUB/GPOS shaping (conjuncts); `feasibleAt()` guaranteed terminal `CategoryBar{ranked}` fallback (intersect never empty); `ChartType` union widen is a breaking enum (migrate grapher JSON + topic-dispatch same PR); `GeoBreadcrumb` needs a district URL node the router lacks (add `url.district` + `/s/:state/d/:district`); U1 file set bigger than `theme.extend` (index.html CDN link, app.css motif, LeftRail hex); F2 production blast radius is the trio + StackedTrendV2 (V2 orphans are DevChartsSandbox-only); error/empty fold into existing ChartShell. The parity oracle re-point is a REWRITE (4 hardcoded parquet paths -> CSV) confirmed by all three engineering personas. All round-5 verdicts research-only; no code written (Level-5 plan-only until user signoff).

Round 6 2026-06-04 (research-only, user process questions + new election-page asks) -> sections 24 + 25. **Process additions (orchestrator, no persona):** section 24 operator guide - plan name, human read order, the Execution Ledger (22.5) named as the ready-reckoner, the status lifecycle TODO->IN-FLIGHT->MERGED (+BLOCKED/DEFERRED) updated inside the chunk's own PR, a paste-ready kickoff prompt (24.4), and a sub-plan spawning rule (24.5) so a growing chunk becomes `TODO/<date>-<slug>-subplan.md` with a parent back-pointer rather than bloating the parent past a context window. **Jony (UI/UX)** -> section 25 election-experience refinements (research-only): 25.1 adopt four interaction archetypes already half-present (RacesBoard competitiveness-columns, OWID entity-brush range label, psephlab swing-slider, PRS/TCPD always-on source line) - pattern not pixels; 25.2 mandatory `time_label` slot on ChartShell (single year for snapshots, brushed start->end for series); 25.3 one schema-driven `PartyPill` coloured via the 3-tier resolver with a new `--party-neutral` token for unknown parties, the SVG ballot symbol composing BESIDE the pill not inside it; 25.4 draw the state silhouette on both StateAcMap (outline stroke over fills) and TileCartogram (faint silhouette behind the hex grid) so a single-state district map is unambiguous; 25.5 two highlight modes on one legend (MARGIN opacity-ramp vs PARTY-WON uniform-fill with non-matching cells receding to the neutral token) + a "margin >= X%" sub-slider, fixing washed-out highlights; 25.6a fix the ParliamentArc ~2x double-count as a hard invariant (sum(seats_won)==total_seats==distinct constituencies) with a regression test, and 25.6b a `countSeats(method,...)` seam that retains FPTP as the sole implementation now and DEFERS alternate counting methods to a sub-plan gated on a Citizen+Hans second opinion with a "hypothetical recount" honesty banner. Forks flagged for Citizen second-opinion: which two archetypes lead (25.1), and any alternate-counting build (25.6b). All round-6 verdicts research-only; no code written (Level-5 plan-only until user signoff).

Round 6b 2026-06-04 (user ask - doctrine must not reintroduce old nonsense) -> section 22.7 + chunk D-DOC4. Because the rip invalidates large parts of the standing doctrine (Parquet canonical store, DuckDB-WASM-reads-Parquet, `sources.parquet`, the meadow tier, the indicator-catalogue schema, the ADR filing cabinet, the JSON-projection / frontend-reads-Parquet-only anti-patterns, the DDF brand), a Step-0 chunk D-DOC4 now merges BEFORE any code: it reconciles `CLAUDE.md` + all eight `AGENTS.md` (admin, backend/yen_gov, frontend/src, frontend/src/lib/yenask, datasets/livestock, datasets/grapher, tools/boundaries, tools/iced_parity). Two-phase rule: rewrite an assertion now if the new truth is already binding, else plant a `MIGRATING (see plan section NN)` marker that the chunk making it true flips in its own PR (per-chunk DoD #7). New `doctrine-marker-audit` gate proves zero un-marked stale assertions survive, and zero `MIGRATING` markers survive plan close. Agent memory (`/memories/`) is left untouched (derived per CLAUDE.md section 5). Authored directly (orchestrator, no persona); research-only, no code (Level-5 plan-only until user signoff).
