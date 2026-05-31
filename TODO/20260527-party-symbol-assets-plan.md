# Party Symbol Assets Plan

**Last Updated**: 2026-06-01
**Status**: Proposed research handoff - no implementation landed
**Scope**: High-quality, license-clear SVG election symbols for Indian political parties. This plan records the research verdict and a granular PR path so a future agent can implement without restarting discovery.

## 0. Load-bearing constraints

- [CLAUDE.md](../CLAUDE.md) Holy Law #1: production is static; symbol bytes must ship in the bundle via `datasets/`, not remote hotlinks.
- [CLAUDE.md](../CLAUDE.md) Holy Law #3: contracts before logic; add a schema before frontend rendering.
- [CLAUDE.md](../CLAUDE.md) Holy Law #4: document decisions in the same PR as code.
- [CLAUDE.md](../CLAUDE.md) Holy Law #6: no hardcoded data in frontend code; symbol assignments are reference data.
- [CLAUDE.md](../CLAUDE.md) Holy Law #8: use open-source / license-clear assets first, but do not confuse license source with semantic authority.
- [CLAUDE.md](../CLAUDE.md) Holy Law #9: provenance is mandatory; every symbol asset and every party-symbol assignment needs a source row.
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) owns taxonomy/dimension-table placement.
- [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) owns `/data/<rel>` runtime loading.
- [docs/architecture/frontend/colours.md](../docs/architecture/frontend/colours.md) owns party colour anchors. Colours are presentation; election symbols are data.
- [TODO/PARTY-COLORS-REWORK.md](PARTY-COLORS-REWORK.md) is the sibling colour plan. Do not merge the colour and symbol concepts.

## 1. Research snapshot

User request: find the 80/20 approach for high-quality SVG election symbols for Indian political parties, starting from Wikimedia Commons but not treating it as the only source. No permanent code changes were requested in the research turn.

Repo facts observed on 2026-05-27:

- `datasets/taxonomy/parties.json` currently has 617 active party rows.
- `datasets/elections/dim_parties.parquet` currently has 617 party rows, but `recognition` is null for every row. Do not use that column yet as the recognised-party gate.
- `datasets/elections/elections_candidacies.parquet` references 613 distinct party IDs across 387,810 candidacy rows, 139 events, and 8,055 ACs.
- In the candidacy corpus, 174 party IDs have at least one win, 222 have at least one candidate with >= 10,000 votes, 190 have >= 100,000 total votes, and 105 have >= 1,000,000 total votes.
- Existing colour anchors live in [frontend/src/lib/colors/anchors.ts](../frontend/src/lib/colors/anchors.ts), keyed by ECI party code. That file is presentation-only and must not become a symbol registry.
- [frontend/src/app.css](../frontend/src/app.css) already warns that party symbols as background motifs carry legal/perception risk. That warning remains valid.

Commons facts observed from `https://commons.wikimedia.org/wiki/Category:Symbols_of_political_parties_in_India`:

- The direct category has 30 files: 9 SVG, 9 PNG, and 12 JPG/JPEG.
- The category has 10 subcategories: flags, logos, and party-specific symbol categories for AAP, BRS, BJP, CPI(M), INC, NCP, TDP, and AITC.
- Direct SVG examples include `Ceiling fan.svg`, `CPI symbol.svg`, `Elephant electoral symbol.svg`, `India National Level Parties symbols.svg`, `INLD1.svg`, `Janata Dal symbol.svg`, and `Oil lamp.svg`.
- Representative file licenses vary: e.g. `Ceiling fan.svg` CC BY-SA 3.0, `CPI symbol.svg` CC BY-SA 3.0, `Elephant electoral symbol.svg` CC BY 4.0, `India National Level Parties symbols.svg` CC BY-SA 3.0, `INLD1.svg` public domain.
- Visual check: most election-symbol SVGs are monochrome ballot glyphs. The colourful files are usually party flags/logos or composites, not ECI ballot-symbol artwork.
- `India National Level Parties symbols.svg` is a high-quality composite but monochrome, partly non-English labelled, and not a per-party asset set. Treat it as discovery material, not a runtime asset.

ECI facts observed:

- [ECI Political Parties/Candidates](https://www.eci.gov.in/candidate-politicalparty) links to party registration, election symbols, list of political parties, and recognition/de-recognition surfaces.
- [ECI Election Symbol](https://www.eci.gov.in/election-symbol) separates reserved-symbol allotment under Paras 10/10A from common-symbol allotment under Para 10B, with event detail pages and downloadable PDFs.
- [ECI List of Political Parties](https://www.eci.gov.in/list-of-political-parties) exposes main notifications for national parties, state parties, RUPPs, delisted/inactive RUPPs, and free symbols.
- [ECI Recognition & De-recognition](https://www.eci.gov.in/recognition-derecognition) exposes recognition orders, including orders that name the reserved symbol.

External metadata probes observed on 2026-06-01:

- Wikipedia's [List of political parties in India](https://en.wikipedia.org/wiki/List_of_political_parties_in_India) is a dynamic editorial page. It is useful for party-page discovery, party split hints, Commons file leads, and references to official material, but it is not recognition or symbol-assignment authority.
- `thecont1/india-votes-data` is an MIT-licensed active repository. Its `data/parties.csv` has fields including `name`, `abv`, `chief`, `colour`, `founded`, `symbol_url`, `seats_loksabha`, `seats_rajyasabha`, `seats_assembly`, `wikipedia_url`, and `alliance`.
- `thecont1/india-votes-data` is useful as a discovery shortlist for Tier 0 party pages, symbol candidates, aliases, and colour hints. Its `symbol_url` values often point to rendered Wikimedia thumbnails such as `upload.wikimedia.org/.../thumb/.../120px-*.svg.png`, not to the Commons file page, original SVG, or ECI assignment order.
- `GarudadevDataServices/indian_mlas` has no license surfaced in the initial repository UI probe. Its `scripts/process-data.js` reads `raw_data/india_asm.xlsx`, `raw_data/india_asm.geojson`, and `raw_data/colors.json`; candidate `AGE`, `GENDER`, and `WIKIPEDIA LINK` are lifted directly from the Excel columns.
- `GarudadevDataServices/indian_mlas/raw_data/colors.json` maps party abbreviations and aliases to 4-channel RGBA arrays in the 0..1 range. It is useful as colour QA and alias-discovery input only; it is not an official party-colour source.
- The upstream source for Garudadev's `india_asm.xlsx` demographics and Wikipedia links is not documented in that repository. Do not import candidate age, gender, or wiki links from it into yen-gov unless each row is independently traced to ECI, State CEO, affidavit, or another accepted authority.

## 2. Core decision

Do not chase all 617 taxonomy parties in the first implementation. The useful first tranche is about 100-125 symbols, not the whole registry.

Model three separate concepts:

- **Election symbol**: the ECI ballot-identification glyph. Usually monochrome. It answers, "what symbol was reserved or allotted?"
- **Party logo / flag**: party brand material. It may be colourful, but it is not necessarily the ECI ballot glyph.
- **Party colour**: yen-gov presentation aid governed by [docs/architecture/frontend/colours.md](../docs/architecture/frontend/colours.md). It must not be used to colourize election symbols and call them official.

Default rendering rule: render verified election symbols as monochrome SVGs. Do not auto-fill a symbol with party colour unless the asset is explicitly a party logo/flag and the UI labels it as such.

Citizen warning copy, when symbols first surface:

> Election symbols are shown where yen-gov has verified an ECI or State CEO source. For registered unrecognised parties, symbols may change by election. Colours are yen-gov visual aids, not official ECI ballot colours.

Short citizen-facing copy for mixed symbol/colour surfaces:

> The symbol is the ballot symbol verified from ECI or State CEO material. The colour is a yen-gov chart colour to help you follow parties across the page; it is not an official ECI ballot colour.

Source-authority warnings:

- Do not use Wikipedia, `thecont1/india-votes-data`, `GarudadevDataServices/indian_mlas`, news articles, or third-party dashboards as `authority_source_id` for `party_symbol_assignments`.
- Do not import thecont1 `parties.csv` fields such as `colour`, `chief`, `founded`, `seats_*`, `wikipedia_url`, or `symbol_url` as yen-gov facts. Use them as discovery leads only.
- Do not use Garudadev `colors.json` as official party colours. yen-gov party colours remain presentation aids governed by [docs/architecture/frontend/colours.md](../docs/architecture/frontend/colours.md).
- Do not import Garudadev `india_asm.xlsx` candidate `AGE`, `GENDER`, or `WIKIPEDIA LINK` fields into `dim_persons` or candidate facts unless the row can be traced to an accepted source.
- Do not infer candidate sex or gender from names, pronouns, photos, titles, Wikipedia prose, or LLM output. Preserve the upstream label and value exactly where ECI, State CEO, or affidavit material publishes it.
- Do not colourize a monochrome ECI election symbol with a party colour and call that official. Election symbols are ballot identifiers; party colours are yen-gov visual aids.

No symbol is better than a guessed symbol. Do not invent a common symbol for `parties.IN.IND`, `parties.IN.UNK`, or other unresolved rows.

## 3. 80/20 coverage rule

### Tier 0 - seed the visible surface first

Target size: 25-35 parties.

Include parties that are already prominent in current yen-gov election pages, high in the candidacy corpus, or represented in colour anchors:

- `parties.IN.BJP` - BJP
- `parties.IN.INC` - INC
- `parties.IN.BSP` - BSP
- `parties.IN.CPIM` - CPI(M)
- `parties.IN.CPI` - CPI
- `parties.IN.AAP` - AAP
- `parties.IN.DMK` - DMK
- `parties.IN.AIADMK` - AIADMK
- `parties.IN.AITC` - AITC
- `parties.IN.SP` - SP
- `parties.IN.JDU` - JD(U)
- `parties.IN.BJD` - BJD
- `parties.IN.RJD` - RJD
- `parties.IN.SHS` and split successors where current routes need them
- `parties.IN.NCP` and split successors where current routes need them
- `parties.IN.SAD` - SAD
- `parties.IN.TDP` - TDP
- `parties.IN.YSRCP` - YSRCP
- `parties.IN.JDS` - JD(S)
- `parties.IN.IUML` - IUML
- `parties.IN.AGP` - AGP
- `parties.IN.AIUDF` - AIUDF
- `parties.IN.PMK` - PMK
- `parties.IN.JMM` - JMM
- `parties.IN.BRS` - BRS
- `parties.IN.SKM` - SKM
- `parties.IN.INLD` - INLD
- `parties.IN.AIMIM` - AIMIM
- `parties.IN.MNS` - MNS
- `parties.IN.NPP` - NPP
- `parties.IN.NPF` - NPF
- `parties.IN.MNF` - MNF
- `parties.IN.NTK` - NTK, if/when present in the taxonomy/corpus under its current party_id
- `parties.IN.TVK` - TVK, if the current 2026 surface needs it

### Tier 1 - all current recognised parties

Target cumulative size: 60-75 parties.

Ingest current ECI national and state-recognised parties from the latest main notification and recognition/de-recognition orders. This is the first official 80/20 cut because recognised parties have reserved symbols that persist across elections until recognition or party status changes.

Prerequisite: backfill or compile party recognition into the canonical party/dimension path before using recognition as a data gate, because `dim_parties.recognition` is currently null.

### Tier 2 - corpus-impact long tail

Target cumulative size: 100-125 parties.

Add parties meeting any one of these corpus rules:

- party has at least one win in `elections_candidacies.parquet`;
- party has >= 1,000,000 total votes in the corpus;
- party appears in >= 20 election events;
- party is visible in a current route or issue-specific narrative.

### Tier 3 - event-specific or low-exposure rows

Defer everything else. For registered unrecognised parties and independents, assignments are often election-specific common/free-symbol allotments. Add them only when a route or source-backed story needs them.

## 4. Source hierarchy

Separate four questions: party identity, symbol assignment, asset bytes/license, and presentation colour. A source that is acceptable for one question is not automatically acceptable for the others.

Use this source order for party identity, recognition, and symbol assignment:

1. ECI main notifications listing national parties, state parties, reserved symbols, registered unrecognised parties, delisted/inactive RUPPs, and free symbols.
2. ECI recognition/de-recognition/restoration/freezing orders, including faction and reserved-symbol disputes.
3. ECI election-symbol detail pages and orders under Paras 10, 10A, and 10B for reserved/common-symbol allotment.
4. State CEO / Returning Officer Form 7A and final list of contesting candidates for election-specific symbol allotment, especially RUPPs and independents.
5. ECI Statistical Reports Section 10 for post-election candidate rows, party short code, symbol text, votes, and reported sex/age/category fields when present.
6. ECI Results Portal pages for current-cycle party/candidate/result cross-checks, but not as artwork or long-term recognition authority.
7. Wikimedia Commons file pages and original asset files as asset/license candidates only. A Wikimedia thumbnail URL is not enough; resolve it to the Commons file page and original file, then record license and asset format.
8. Structured third-party metadata such as `thecont1/india-votes-data` and `GarudadevDataServices/indian_mlas` as discovery/QA only. They may seed candidate links, colours, and review lists, but must not populate `authority_source_id`.
9. Party official sites, press kits, flags, and constitutions for party-logo or brand-colour discovery only; they do not override ECI ballot-symbol assignment.
10. Wikipedia/news/media for discovery only unless the PR explicitly marks the row as low-confidence editorial fallback.

A runtime `party_symbol_assignments` row must have an ECI or State CEO authority source. If no official source is found, the symbol stays absent.

## 5. Proposed durable layout

Put durable symbol assets and metadata under `datasets/`, not `frontend/`.

Proposed layout:

```text
datasets/
  schemas/
    party-symbols.schema.json
  taxonomy/
    party_symbols.json
    party_symbols.parquet
    party_symbol_assignments.parquet
    party_external_links.json
    party_external_links.parquet
    person_external_links.json
    person_external_links.parquet
    party-symbol-assets/
      eci-lotus.svg
      eci-hand.svg
      eci-elephant.svg
  grapher/
    party_colour_anchors.json      # future option if colour anchors move out of frontend code
```

Rationale:

- `datasets/` is the static data contract copied to `/data/` at deploy time.
- `frontend/` must not own data files or hardcoded party-symbol maps.
- Symbol assignment is a relation with validity and provenance, not a timeless field on one party row.
- The same symbol can belong to multiple historical parties or be free/common in one context and reserved in another.
- Party and person external links are separate relations, not symbol fields. A Wikipedia URL answers "where can I read more?"; it does not prove symbol assignment or election results.
- Party colours remain frontend presentation under [docs/architecture/frontend/colours.md](../docs/architecture/frontend/colours.md). If anchors later become persistent data, they belong in a frontend/grapher-owned render catalogue, not in canonical party identity or symbol assignment tables.

## 6. Contract shape

Prefer a separate contract over adding `symbol_path` directly to `taxonomy/parties.json`.

Suggested `party_symbols.json` top-level shape:

```text
{
  "$schema": "../schemas/party-symbols.schema.json",
  "$schema_version": "1.0",
  "symbols": [...],
  "assignments": [...]
}
```

Suggested `symbols[]` fields:

- `symbol_id`: stable slug from the symbol name, e.g. `eci-lotus`, `eci-hand`, `eci-elephant`.
- `display_name`: citizen-readable symbol name, e.g. `Lotus`, `Hand`, `Elephant`.
- `asset_path`: POSIX-relative path under `taxonomy/party-symbol-assets/`.
- `asset_sha256`: hash of the committed asset bytes.
- `asset_format`: `image/svg+xml` for v1.
- `asset_kind`: `election_symbol`, `party_logo`, `party_flag`, or `composite_reference`. Only `election_symbol` is used in ballot/result UI by default.
- `render_mode`: `monochrome`, `source_coloured`, or `brand_coloured`. Default `monochrome`.
- `license`: SPDX-ish text or source license label, e.g. `CC-BY-4.0`, `CC-BY-SA-3.0`, `public-domain`, `unknown-public`.
- `asset_source_url`: original asset URL, e.g. Commons file page or ECI PDF/source page.
- `source_id`: FK to `datasets/taxonomy/sources.parquet` for the asset source.
- `notes`: nullable operator note.

Suggested `assignments[]` fields:

- `party_id`: FK to `datasets/taxonomy/parties.json`.
- `symbol_id`: FK to `symbols[].symbol_id`.
- `scope`: `IN` or ECI state/UT code such as `S22`, when assignment is state-scoped.
- `valid_from_year`: nullable integer.
- `valid_to_year`: nullable integer.
- `assignment_kind`: `reserved_national`, `reserved_state`, `common_symbol`, `free_symbol`, or `historical`.
- `authority_source_id`: FK to `sources.parquet` proving the assignment.
- `confidence_tier`: `gold`, `silver`, or `bronze`.
- `notes`: nullable operator note.

Suggested `party_external_links[]` fields, if the party-profile UI earns this relation:

- `party_id`: FK to `datasets/taxonomy/parties.json`.
- `link_kind`: `wikipedia`, `wikidata`, `official_site`, `eci_profile`, or `other`.
- `url`: canonical external URL.
- `language`: nullable BCP-47 language code, e.g. `en` for English Wikipedia.
- `source_id`: FK to `datasets/taxonomy/sources.parquet` proving where the link was collected or verified.
- `confidence_tier`: `gold`, `silver`, or `bronze`.
- `notes`: nullable operator note.

Suggested `person_external_links[]` fields, if candidate/person profile links are persisted:

- `person_id`: FK to the canonical person dimension once `dim_persons` / person taxonomy lands.
- `link_kind`: `wikipedia`, `wikidata`, `official_site`, `affidavit`, `myneta_profile`, or `other`.
- `url`: canonical external URL.
- `source_id`: FK to `datasets/taxonomy/sources.parquet`.
- `confidence_tier`: `gold`, `silver`, or `bronze`.
- `notes`: nullable operator note.

Do not add `wikipedia_url`, third-party `colour`, `rgba`, or raw upstream `symbol_url` fields to the runtime v1 symbol contract. Those belong in the probe report until a concrete citizen-facing need earns a schema field. The runtime symbol contract should carry only verified asset provenance, assignment authority, and render-safe asset metadata.

Future extension, only if needed: event-specific assignment table keyed by `(party_id, election_id, state_code)` for RUPPs and independents.

## 7. Validation rules

Backend validator / tests should enforce:

- `party-symbols.schema.json` is schema-valid and has `x-version`/`x-changelog` per [CLAUDE.md](../CLAUDE.md) section 11.
- Every `party_id` exists in `taxonomy/parties.json`.
- Every `symbol_id` in assignments exists in `symbols[]`.
- Every `asset_path` is POSIX-relative, starts with `taxonomy/party-symbol-assets/`, exists, ends in `.svg`, and matches `asset_sha256`.
- SVGs are sanitized: no `script`, no event-handler attributes, no `foreignObject`, no external `href`, no remote fonts, and no embedded raster blobs unless a later ADR explicitly allows them.
- No overlapping active assignment for the same `(party_id, scope, assignment_kind)` validity window.
- Every `source_id` / `authority_source_id` resolves to `taxonomy/sources.parquet`.
- `asset_kind = composite_reference` cannot be assigned to a party for UI rendering.
- `render_mode = brand_coloured` requires `asset_kind` of `party_logo` or `party_flag`, not `election_symbol`.
- External-link relations validate FK closure, URL shape, allowed `link_kind`, duplicate prevention on `(party_id, link_kind, url)` or `(person_id, link_kind, url)`, and `source_id` closure.
- Probe parsers use small checked-in fixtures, not live network calls in pytest.
- `india-votes-data` fixtures keep the required headers `name`, `abv`, `colour`, `symbol_url`, and `wikipedia_url`; missing optional values are allowed and reported.
- `indian_mlas` fixtures validate every colour as a 4-item RGBA array with numeric channels between 0 and 1.
- Party matching uses the existing party lookup / alias resolution seam. Unresolved abbreviations are reported, never coerced to `IND` or `UNK`.
- A `symbol_url` discovered from a thumbnail is only a candidate until the pipeline resolves a Commons file page or official source and passes SVG sanitizer/hash checks.
- Probe output must be a report or handoff table only. It must not write symbol assets, party-symbol assignments, frontend anchors, or canonical Parquet.

## 8. PR sequence

### PR-SYM-0 - Recognition/source audit handoff

Goal: make the official coverage cut reproducible before adding assets.

Work:

- Create or update a handoff doc listing the latest ECI national-party and state-party main notification PDFs.
- Record recognition/de-recognition pages that changed current status after the main notification.
- Decide whether recognition belongs on `taxonomy/parties.json`, `dim_parties.parquet`, or a separate party-recognition relation. Consult Hans + Gregor if the shape is not obvious.

Acceptance:

- No asset ingestion yet.
- A reviewer can reproduce the Tier 1 party list from ECI sources.

### PR-SYM-0A - External discovery-source probes

Goal: turn third-party metadata into a candidate review report before any contract or asset ingest changes.

Work:

- Probe `https://raw.githubusercontent.com/thecont1/india-votes-data/main/data/parties.csv` and record row count, headers, repository license, latest observed upstream commit/file SHA, and whether the row is in the Tier 0/1/2 target set.
- Probe `https://raw.githubusercontent.com/GarudadevDataServices/indian_mlas/main/raw_data/colors.json` and record key count, alias patterns, RGBA range, and license status.
- Probe `https://raw.githubusercontent.com/GarudadevDataServices/indian_mlas/main/scripts/process-data.js` and record that candidate age, gender, and Wikipedia links are read from `raw_data/india_asm.xlsx` columns, with no upstream source documented in the repository.
- For each `india-votes-data.symbol_url`, classify whether it is a Wikimedia thumbnail, original SVG, PNG/JPG-only candidate, missing value, or non-Wikimedia URL.
- For each thumbnail candidate, derive the likely Commons file title, then verify through the Commons API or file page before any asset is accepted. Store the Commons file page URL and original SVG URL separately in the report.
- For each `india-votes-data.wikipedia_url`, record it as a discovery cross-link only.
- Join upstream party abbreviations through the existing party lookup / alias resolution seam; report unresolved abbreviations separately.
- Produce a compact candidate table with: upstream source, upstream party code/name, matched `party_id` if any, candidate symbol URL, candidate Commons file page, candidate Wikipedia URL, candidate colour values, license status, assignment authority status, and recommended next action.
- Do not write `datasets/taxonomy/party_symbols.json`, do not commit assets, do not update frontend colour anchors.

Acceptance:

- Report/handoff only; no runtime data, schema, frontend, or asset changes.
- Unit tests cover CSV header parsing, RGBA validation, URL classification, Commons-thumbnail detection, and unresolved-party reporting using fixtures.
- No pytest test performs live network access or walks the real corpus.
- The report clearly separates discovery source, asset/license source, and assignment-authority source.

### PR-LINK-1 - Party/person external-link contract

Goal: persist party and person external profile links only after a citizen-facing profile surface needs them.

Work:

- Add schemas for `party_external_links.json` and/or `person_external_links.json` only when the UI has a concrete consumer.
- Compile the JSON relations to Parquet under `datasets/taxonomy/` and register them in `datasets/manifest.json`.
- Keep Wikipedia links out of result provenance and source lists; they are profile links, not evidence for votes, recognition, or symbol assignment.
- For candidate/person links, do not import Garudadev Excel-derived values unless every row can be traced to accepted source material.

Acceptance:

- FK closure to party/person identity tables and `taxonomy/sources.parquet` is tested.
- Duplicate link keys are rejected.
- Frontend tests prove missing links hide cleanly and no Wikipedia URL is hardcoded in Svelte/TS runtime components.

### PR-SYM-1 - Contract only

Goal: land the schema and docs before logic.

Work:

- Add `datasets/schemas/party-symbols.schema.json` v1.0.
- Add documentation to [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) or a focused sibling doc under `docs/architecture/data/` explaining symbol identity vs assignment.
- Add a tiny fixture in backend tests only. Do not commit real symbol assets unless the PR explicitly owns that data.

Acceptance:

- Schema tests green.
- No frontend runtime changes.

### PR-SYM-2 - Validator and sanitizer

Goal: make bad assets impossible to commit silently.

Work:

- Add pure validation helpers for asset path, hash, FK closure, and validity-window overlap.
- Add SVG sanitizer checks with `tmp_path` fixtures.
- Add Tier-A tests for malicious SVG examples.

Acceptance:

- Tests prove scripts, event handlers, external links, and `foreignObject` are rejected.
- No real corpus walk from pytest.

### PR-SYM-3 - Compile to Parquet and manifest

Goal: expose the symbol contract through the same static data path as other taxonomy artifacts.

Work:

- Add a backend compile path that reads `taxonomy/party_symbols.json` and writes `taxonomy/party_symbols.parquet` and `taxonomy/party_symbol_assignments.parquet`.
- Register both Parquets in `datasets/manifest.json`.
- Keep `party-symbol-assets/*.svg` as static files served under `/data/` by existing dev/prod data-loading rules.

Acceptance:

- `python -m yen_gov emit-taxonomy --root .` or the appropriate writer command emits deterministic Parquet.
- Manifest regeneration is stable except expected table additions.
- Tier-B validator passes.

### PR-SYM-4 - Seed Tier 0 assets

Goal: add first visible symbols with high confidence and screenshots.

Work:

- Add 25-35 Tier 0 SVGs and assignments.
- Prefer Commons SVG where license is clear and visual shape matches ECI/CEO authority; otherwise trace from ECI source only if license policy permits and source is documented.
- Record both asset provenance and assignment authority.
- Use the PR-SYM-0A report only as a shortlist. Every committed asset still needs its own verified asset source/license, and every assignment still needs ECI/CEO authority.

Acceptance:

- All hashes and FKs validate.
- A small generated inventory table in the PR body lists party, symbol, asset source, assignment source, license, and confidence.
- If a symbol candidate came from Wikipedia, Commons, or `india-votes-data`, the PR body identifies it as discovery material and names the separate authority source used for assignment.

### PR-SYM-5 - Frontend loader/render component

Goal: render symbols without making frontend the data owner.

Work:

- Add a loader/view-model that reads manifest-backed symbol tables and maps `asset_path` to `/data/<asset_path>`.
- Add a small `PartySymbol` renderer with fallback to initials or no-icon state.
- Do not hardcode party-specific asset paths in Svelte or TS.

Acceptance:

- Unit tests cover present, absent, and invalid assignment cases.
- Frontend contract test blocks hardcoded `party-symbol-assets/` paths outside the loader/test fixtures.
- Browser smoke per [CLAUDE.md](../CLAUDE.md) section 13 on one route that actually renders symbols.

### PR-SYM-6 - Tier 1 recognised-party expansion

Goal: cover the official recognised-party list.

Work:

- Add all current national/state recognised parties not covered by Tier 0.
- Add recognition validity/source rows or assignments with validity windows where ECI orders require them.

Acceptance:

- Coverage report says every current recognised party has either a verified symbol or a documented missing-asset reason.

### PR-SYM-7 - Tier 2 corpus-impact expansion

Goal: cover high-use long-tail parties.

Work:

- Add parties with wins, >= 1,000,000 total corpus votes, or repeated event appearances.
- Where assignment is event-specific common/free symbol, do not promote it to timeless party identity.

Acceptance:

- Corpus coverage table in PR body shows before/after: percent of candidate rows, votes, wins, and current-route parties with symbols.

## 9. Open questions

- Should party recognition be modelled as a property on `taxonomy/parties.json`, as a compiled `party_recognition.parquet` relation, or as election-scoped rows only? Current `dim_parties.recognition` is null, so this is unresolved.
- What license posture is acceptable for manual SVG traces from ECI PDFs? This needs explicit project policy before tracing many assets.
- Should `thecont1/india-votes-data` metadata be cited as an MIT discovery source in `sources.parquet`, or only in the PR-SYM-0A handoff report, given it is not assignment authority?
- `GarudadevDataServices/indian_mlas` did not surface an explicit license in the initial probe. Should it remain QA-only unless license status is clarified?
- Should Wikipedia URLs be persisted in `party_external_links`, or remain probe-only until a party-profile page earns that field?
- Should candidate/person Wikipedia links wait for the `dim_persons` / canonical person identity work, rather than attach to candidate rows?
- Should logos/flags ever render in citizen results pages, or should v1 restrict itself to `asset_kind = election_symbol` only?
- How should party splits share or fork symbol assignments? Example: Shiv Sena and NCP factions need careful validity windows and assignment authority.
- Should symbol assets be optimized with SVGO during ingest? If yes, sanitizer and hash must run after optimization, and the optimizer config becomes part of the data contract.

## 10. References

- [Wikimedia Commons: Symbols of political parties in India](https://commons.wikimedia.org/wiki/Category:Symbols_of_political_parties_in_India)
- [ECI Political Parties/Candidates](https://www.eci.gov.in/candidate-politicalparty)
- [ECI Election Symbol](https://www.eci.gov.in/election-symbol)
- [ECI List of Political Parties](https://www.eci.gov.in/list-of-political-parties)
- [ECI Recognition & De-recognition](https://www.eci.gov.in/recognition-derecognition)
- [thecont1/india-votes-data `data/parties.csv`](https://github.com/thecont1/india-votes-data/blob/main/data/parties.csv)
- [thecont1/india-votes-data raw `data/parties.csv`](https://raw.githubusercontent.com/thecont1/india-votes-data/main/data/parties.csv)
- [GarudadevDataServices/indian_mlas `raw_data/colors.json`](https://github.com/GarudadevDataServices/indian_mlas/blob/main/raw_data/colors.json)
- [GarudadevDataServices/indian_mlas raw `colors.json`](https://raw.githubusercontent.com/GarudadevDataServices/indian_mlas/main/raw_data/colors.json)
- [GarudadevDataServices/indian_mlas `scripts/process-data.js`](https://github.com/GarudadevDataServices/indian_mlas/blob/main/scripts/process-data.js)
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md)
- [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md)
- [docs/architecture/frontend/colours.md](../docs/architecture/frontend/colours.md)
- [TODO/PARTY-COLORS-REWORK.md](PARTY-COLORS-REWORK.md)
