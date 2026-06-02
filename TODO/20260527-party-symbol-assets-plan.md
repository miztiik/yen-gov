# Party Symbol Assets Plan

**Last Updated**: 2026-06-02
**Status**: COMPLETE. PR-SYM-0..3 DONE (#524, #526, #527, #528). PR-SYM-4a-redo DONE (#551). PR-SYM-4b DONE (#563). PR-SYM-4c DONE (#564). PR-SYM-6a DONE (#566). PR-SYM-6 series renumbered during execution into 6 PRs (6b/6c/6d/6e/6f); see Plan complete block at end of file. 12 grandfathered consumers remain; tracked in [frontend/src/contracts/party-colour-import-allowlist.test.ts](../frontend/src/contracts/party-colour-import-allowlist.test.ts) (PR #581).
**Scope**: Collect sanitized SVG election symbols for the parties citizens most often see. Frontend rendering comes last.

## Status Reckoner

| PR | Status | Files touched | Schema bump | Gates | Blocks | PR# |
| --- | --- | --- | --- | --- | --- | --- |
| PR-SYM-0 | DONE | `TODO/20260527-party-symbol-assets-plan.md` | none | docs-only | none | #524 |
| PR-SYM-1 | DONE | `datasets/schemas/taxonomy-parties.schema.json` (2.1 -> 2.2), `datasets/taxonomy/parties.json` ($schema_version bump), `backend/tests/test_taxonomy_parties_schema_v22.py` (13 cases) | `taxonomy-parties` minor (`recognition` + `election_symbol`); `dim-parties` NOT bumped (recognition already declared v1.0, election_symbol mirror deferred to PR-SYM-5) | pytest 70 targeted pass + Tier-A validate exit 0 | unblocks PR-SYM-4b | #526 |
| PR-SYM-2 | DONE | `notes/20260601-party-symbol-roster.md` (177 lines: top-60 winners SQL + snapshot pins + Tier 0/1/2 routing + alias-trap flags + recognition source policy) | none | notes-only | unblocks PR-SYM-4 | #527 |
| PR-SYM-3 | DONE | `frontend/src/lib/party-symbols/sanitizer.ts`, `frontend/src/lib/party-symbols/sanitizer.test.ts` (18 cases), `frontend/public/party-symbols/placeholder.svg` | none | vitest 18/18 pass | unblocks PR-SYM-4a | #528 |
| PR-SYM-4a.i | SUPERSEDED by 4a-redo | _hand-authored silhouettes; rejected as inauthentic_ | none | n/a | n/a | #543 |
| PR-SYM-4a.ii | SUPERSEDED by 4a-redo | _Commons party-LOGO bytes mislabelled as election-symbols (e.g. `aap-broom.svg` contained AAP wordmark, not broom)_ | none | n/a | n/a | #545 |
| PR-SYM-4a-redo | DONE (Wikipedia scrape, 55 parties / 50 unique symbols) | `frontend/public/party-symbols/<symbol-noun>.{svg,png,jpg,webp}` (50 new files), `notes/20260601-party-symbol-wiki-inventory.md`, `TODO/20260527-party-symbol-assets-plan.md` reckoner update; deletes the 4 mislabelled files from #545 | none | sanitizer N/A at scrape time (renderer-time enforcement deferred to PR-SYM-5) | unblocks PR-SYM-4b | #551 |
| PR-SYM-4b | DONE | parties.json + recompiled dim_parties.parquet + taxonomy schema v2.2->v2.3 | `taxonomy-parties` minor | Tier-A validate + pytest | PR-SYM-4c, PR-SYM-6a | #563 |
| PR-SYM-4c | DONE | parties.json (wikipedia_url + brand_colour for 55 parties), inventory note, sources.parquet | none | validate + pytest + Garudadev cross-check | PR-SYM-6a | #564 |
| PR-SYM-6a | DONE | resolver.ts + resolver.test.ts (3-tier: anchor / brand / fallback) | none | svelte-check + vitest | PR-SYM-6b | #566 |
| PR-SYM-6b (data) | DONE | dim_parties schema v1.1 + writer + PartyDimRow pydantic + adapter; renumbered from original 6a's mirror split | `dim-parties` minor (`election_symbol` + `brand_colour`) | validate + pytest + svelte-check + vitest | PR-SYM-6c | #570 |
| PR-SYM-6c (loader + AcStackedBar) | DONE | loader projection extends row shape (`party_id` + `brand_colour` + `brand_confidence`); first consumer AcStackedBar migrates | none | svelte-check + vitest + browser smoke | PR-SYM-6d | #571 |
| PR-SYM-6d (MarginHistogram + AcWinner spine) | DONE | MarginHistogram migrates; AcWinner row shape carries `party_id` + brand mirror end-to-end | none | svelte-check + vitest + browser smoke | PR-SYM-6e | #577 |
| PR-SYM-6e (batch resolver + StateAcMap + RacesBoard) | DONE | `resolvePartyPalette` batch helper added at 2nd batch consumer; StateAcMap (234 polygons) + RacesBoard migrate | none | svelte-check + vitest + browser smoke | PR-SYM-6f | #580 |
| PR-SYM-6f (import-allowlist guardrail) | DONE | `frontend/src/contracts/party-colour-import-allowlist.test.ts` (2 cases). Forbids NEW imports of legacy modules; ALLOWLIST enumerates the 12 grandfathered consumers as the durable migration tracker. Legacy module deletion deferred until ALLOWLIST is empty. | none | vitest 2/2 pass | none | #581 |

Hard dependency rules:

- PR-SYM-0 must merge first; everything else cites the plan policy locked there.
- PR-SYM-1, PR-SYM-2, PR-SYM-3 may run in parallel once PR-SYM-0 is merged.
- PR-SYM-4a starts only after PR-SYM-3; PR-SYM-4b starts only after PR-SYM-1, PR-SYM-2, and PR-SYM-4a.
- PR-SYM-4c (wiki enrichment) starts only after PR-SYM-4b (the optional schema fields land in 4b; 4c only populates them).
- PR-SYM-6a starts only after PR-SYM-4b (schema fields must exist). PR-SYM-6b -> 6c -> 6d are strictly sequential; do not parallelise consumer migration.
- `dim-parties.schema.json` mirror splits across two PRs: `recognition` in PR-SYM-1 (closes the existing null-column gap), `election_symbol` + `brand_colour` in PR-SYM-6a (matches the writer-before-reader / reader-before-writer dance from [ADR-0047](../docs/architecture/decisions/0047-schema-version-compatibility-contract.md) at the moment the renderer needs it).
- PR-SYM-5 (single-renderer-PR) is RETIRED. Replaced by PR-SYM-6a/b/c/d per Jony verdict 2026-06-01.

## 11. Wikipedia enrichment (added 2026-06-01)

Amendment to the plan after Hans (Governance) + Jony (UI/UX) red-team. Two optional party-row fields land alongside `election_symbol` in the PR-SYM-4b schema bump and get populated in PR-SYM-4c. Both fields are **enrichment, not required** - graceful fallover when absent.

### 11.1 Doctrine correction

The Wikipedia per-party `{{<Party>/meta/color}}` subtemplate is **editorial consensus on a community wiki**, not party identity in the statutory sense. ECI registers and freezes *symbols* under the Election Symbols (Reservation and Allotment) Order 1968; it does **not** publish or reserve party *colours*. There is no statutory colour register in India. `brand_colour` records the best available editorial consensus on what colour a party uses; it does not claim ECI-canonical status.

User decision 2026-06-01: do NOT surface a citizen-facing disclaimer on the website (redundant when source provenance is already on the data row). The honest framing lives in this plan-doc + the schema description, not the UI.

### 11.2 Field shapes

Both fields are **optional** on every party row.

```jsonc
{
  "wikipedia_url": "https://en.wikipedia.org/wiki/Bharatiya_Janata_Party",  // optional; party article URL
  "brand_colour": {                                                           // optional; entire object
    "hex": "#FF9933",                                                         // required if object present
    "confidence": "high",                                                     // required if object present: high | medium | low
    "source_id": "src.wikipedia.list-of-political-parties-in-india.2026-06-01", // required; FK to sources.parquet
    "source_kind": "wiki",                                                    // required; literal "wiki"
    "notes": null                                                             // required (nullable) for non-faction; REQUIRED non-null for faction-split parties (Hans must-fix)
  }
}
```

`confidence` rubric:

- `high` - single live Wikipedia meta/color template + Garudadev RGBA cross-check agreement + not a faction-split party.
- `medium` - single Wikipedia template, no cross-check available, or Garudadev mismatch within tolerance.
- `low` - faction-split party (SHS-UBT/SHS, NCP/NCP-SP, LJP-RV/LJP-Paswan, AIADMK historical) OR Wikipedia/Garudadev disagreement OR template missing/redirect. Frontend resolver MUST treat `low` as if absent (fall through to algorithmic fallback, do not paint a faction colour the citizen cannot verify).

### 11.3 Provenance

One `sources.parquet` row per snapshot of the list page (e.g. `src.wikipedia.list-of-political-parties-in-india.2026-06-01`), shared across every party row whose colour was lifted in that pass. Build via `backend.yen_gov.canonical.citation.derive_source_id`; never hand-author. Per-party-template `source_id` rows are explicitly rejected (see Rejected in section 12).

### 11.4 Frontend resolver (PR-SYM-6a)

Single pure function `getPartyColor(party_id) -> { hex: string, source: 'anchor' | 'brand' | 'fallback', party_id: string }`.

Resolution chain (graceful fallover - no field is mandatory):

1. `anchor` - if `frontend/src/lib/colors/anchors.ts` has an entry, return it. Full-bleed fill allowed anywhere.
2. `brand` - else if `dim_parties.brand_colour` exists AND `confidence != 'low'`, return `brand_colour.hex`. May fill data marks (map polygon, bar segment) but NOT chrome (chip / badge background); chip uses accent stripe or ring with paper-neutral body.
3. `fallback` - else algorithmic hash-to-hue from `frontend/src/lib/colors/party-colour.ts`. Decoration only; label MUST carry the meaning.

Resolver MUST NOT mutate the returned hex (no auto-darken / lighten / contrast-tune). Identity must not mutate; legibility is a canvas problem solved by anchor overrides authored by humans.

Consumer contract by source tier:

| source | may fill large region | requires paired label | chip treatment |
| --- | --- | --- | --- |
| `anchor` | yes | no | full-bleed allowed |
| `brand` | yes for data marks; NO for chrome | yes | accent stripe or ring; chip body paper-neutral |
| `fallback` | no | yes | swatch + label pair; never swatch alone |

### 11.5 4th-surface trap defense (PR-SYM-6d)

The resolver only ends the inconsistency if a contract test forbids `import .* from '.*colors/anchors'` and `import .* from '.*colors/party-colour'` outside `colors/resolver.ts`. Without that lint, the next consumer reaches past the resolver. PR-SYM-6d ships the contract test + deletes now-unused public exports.

### 11.6 Garudadev `colors.json` as second witness

Lint helper only. Both Garudadev and Wikipedia are downstream of the same Wikipedia editorial community; not an independent authority. At ingest, log Garudadev/Wikipedia hex mismatches to `notes/` and lower `confidence` to `medium`. Never use Garudadev as `source_id`.

### 11.7 Faction-split party audit (follow-up)

Before PR-SYM-4c bulk-populates, run a manual pass on the ~10-15 most-litigated faction colour assignments (SHS-UBT/SHS, NCP/NCP-SP, LJP-RV/LJP-Paswan, AIADMK historical, JD(U)/JD(S), Samajwadi/RLD splits) comparing Wikipedia template, Garudadev value, and the party's own website/flag. Output to `docs/research/`. Every faction-affected row in PR-SYM-4c MUST have `confidence: low` + non-null `notes` citing the ECI freezing-order date and which faction Wikipedia assigned the legacy hex to.

## 0. Load-bearing constraints

- [CLAUDE.md](../CLAUDE.md) Holy Law #1: production is static; symbol bytes must ship in the static bundle, not as remote hotlinks.
- [CLAUDE.md](../CLAUDE.md) Holy Law #3: contracts before logic; add schema fields before frontend rendering.
- [CLAUDE.md](../CLAUDE.md) Holy Law #4: document decisions in the same PR as code.
- [CLAUDE.md](../CLAUDE.md) Holy Law #6: no hardcoded party-to-symbol maps in Svelte or TypeScript. Metadata stays data-driven.
- [CLAUDE.md](../CLAUDE.md) Holy Law #8: use mature open sources first. For v1, ECI/common election-symbol glyphs are project-accepted as generic civic glyphs when source, hash, and sanitization are recorded.
- [CLAUDE.md](../CLAUDE.md) Holy Law #9: provenance is mandatory for observation rows. Party-symbol v1 is a static visual affordance, so it records source URL, source kind, license label, hash, and status inline on the party row instead of creating per-symbol observation-style source rows.
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) owns party identity and dimension-table placement. Recognition stays on party identity / `dim_parties`, not in a separate recognition table.
- [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) owns static frontend loading. `frontend/public/party-symbols/` is an intentional public-media exception; it must not become a data registry.
- [docs/architecture/frontend/charts/icon-registry.md](../docs/architecture/frontend/charts/icon-registry.md) owns the local SVG sanitizer precedent.
- [docs/architecture/frontend/colours.md](../docs/architecture/frontend/colours.md) owns party colour anchors. Colours are presentation; election symbols are separate.

## 1. Research snapshot

User direction, updated 2026-06-01:

- Do not create a separate party-symbol tracking system for v1.
- Target the most recognised and most visible parties first, using an 80/20 rule.
- Use DuckDB over the canonical election corpus to find top parties by seats/wins across states and elections.
- Use Wikipedia, Commons, `thecont1/india-votes-data`, and web search as discovery aids, then verify current recognition/symbol status against ECI where possible.
- Store sanitized SVGs under `frontend/public/party-symbols/*.svg` so the future frontend can serve them easily.
- Focus on election symbols only. No flags, party logos, banners, composites, or motifs.
- Do not chase party colours. If a source SVG is already coloured, keep it as source-coloured; otherwise use monochrome black/white.
- Party recognition is an attribute of the party, not a separate table.
- Use one placeholder icon for recognised parties whose symbol has not been collected yet.
- Split-party edge cases are deferred: current split parties can carry their own symbols; the older unified party can keep its older symbol. Do not model validity-window history until a route needs it.

Repo facts observed on 2026-05-27 and re-checked on 2026-06-01:

- `datasets/taxonomy/parties.json` currently has 617 active party rows.
- `datasets/schemas/taxonomy-parties.schema.json` does not yet expose a first-class `recognition` property, although many notes mention imported recognition labels.
- `datasets/elections/dim_parties.parquet` has `recognition`, but it is null for every row today. The shape exists; the data does not.
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) says `recognition` is party identity on `dim_parties`, while alliances are event-scoped through `dim_party_alliances`.
- `datasets/elections/elections_candidacies.parquet` references 613 distinct party IDs across 387,810 candidacy rows, 139 events, and 8,055 ACs.
- Existing colour anchors live in [frontend/src/lib/colors/anchors.ts](../frontend/src/lib/colors/anchors.ts), keyed by ECI party code. That file is presentation-only and must not become a symbol registry.
- [frontend/src/app.css](../frontend/src/app.css) already warns that party symbols as background motifs carry legal/perception risk. That warning remains valid for motifs; it does not block small ballot-symbol icons next to party names.

DuckDB top-winner probe, run 2026-06-01:

```sql
WITH cand AS (
  SELECT
    c.party_id,
    regexp_extract(c.ac_id, 'IN-(S[0-9]{2}|U[0-9]{2})-', 1) AS state_code,
    c.election_id,
    c.won,
    c.votes_polled
  FROM read_parquet('datasets/elections/elections_candidacies.parquet') c
  WHERE c.party_id IS NOT NULL
    AND c.party_id NOT IN ('parties.IN.IND', 'parties.IN.NOTA', 'parties.IN.UNK')
), agg AS (
  SELECT
    party_id,
    COUNT(*) FILTER (WHERE won) AS wins,
    COUNT(DISTINCT state_code) FILTER (WHERE won) AS win_states,
    COUNT(DISTINCT election_id) FILTER (WHERE won) AS win_events,
    COUNT(*) AS candidacies,
    SUM(votes_polled) AS total_votes
  FROM cand
  GROUP BY party_id
)
SELECT a.party_id, p.eci_code, p.short_name, p.full_name,
       a.wins, a.win_states, a.win_events, a.candidacies,
       CAST(a.total_votes AS BIGINT) AS total_votes
FROM agg a
LEFT JOIN read_parquet('datasets/elections/dim_parties.parquet') p USING (party_id)
ORDER BY a.wins DESC, a.win_states DESC, a.total_votes DESC
LIMIT 40;
```

Top current/high-impact seed parties from the probe include `INC`, `BJP`, `CPI(M)`, `DMK`, `SP`, `AITC`, `BSP`, `AIADMK`, `CPI`, `JD(U)`, `BJD`, `RJD`, `SHS`, `NCP`, `SAD`, `AAP`, `TDP`, `YSRCP`, `JD(S)`, `AIFB`, `IUML`, `RSP`, `JMM`, `AGP`, `BRS`, `SDF`, `NPF`, `MNF`, `INLD`, and `TVK`.

Historical or alias-heavy rows from the top-winner list need lineage review before any current symbol is attached: `JSP`/Janata aliases, `INC_I`, `JD`, `ADK`, `LKD`, `JNP_SC`, `SWA`, `INC_U`, `BKD`, and `NCO`. They may still receive historical/default symbols later, but they are not the first current-recognition collection target.

Commons facts observed from `https://commons.wikimedia.org/wiki/Category:Symbols_of_political_parties_in_India`:

- The direct category has 30 files: 9 SVG, 9 PNG, and 12 JPG/JPEG.
- The category has 10 subcategories: flags, logos, and party-specific symbol categories for AAP, BRS, BJP, CPI(M), INC, NCP, TDP, and AITC.
- Direct SVG examples include `Ceiling fan.svg`, `CPI symbol.svg`, `Elephant electoral symbol.svg`, `India National Level Parties symbols.svg`, `INLD1.svg`, `Janata Dal symbol.svg`, and `Oil lamp.svg`.
- Visual check: most election-symbol SVGs are monochrome ballot glyphs. The colourful files are usually party flags/logos or composites, not ECI ballot-symbol artwork.
- `India National Level Parties symbols.svg` is a high-quality composite but is not a per-party asset set. Treat it as discovery material, not a runtime asset.

ECI facts observed:

- [ECI Political Parties/Candidates](https://www.eci.gov.in/candidate-politicalparty) links to party registration, election symbols, list of political parties, and recognition/de-recognition surfaces.
- [ECI Election Symbol](https://www.eci.gov.in/election-symbol) separates reserved-symbol allotment under Paras 10/10A from common-symbol allotment under Para 10B, with event detail pages and downloadable PDFs.
- [ECI List of Political Parties](https://www.eci.gov.in/list-of-political-parties) exposes main notifications for national parties, state parties, RUPPs, delisted/inactive RUPPs, and free symbols.
- [ECI Recognition & De-recognition](https://www.eci.gov.in/recognition-derecognition) exposes recognition orders, including orders that name the reserved symbol.

External metadata probes observed on 2026-06-01:

- Wikipedia's [List of political parties in India](https://en.wikipedia.org/wiki/List_of_political_parties_in_India) is useful for party-page discovery, split hints, Commons file leads, and references to official material.
- `thecont1/india-votes-data` is an MIT-licensed active repository. Its `data/parties.csv` has fields including `name`, `abv`, `chief`, `colour`, `founded`, `symbol_url`, `seats_loksabha`, `seats_rajyasabha`, `seats_assembly`, `wikipedia_url`, and `alliance`.
- `thecont1/india-votes-data` is useful as a discovery shortlist for symbol candidates, aliases, Wikipedia links, and colour hints. Its `symbol_url` values often point to rendered Wikimedia thumbnails, not Commons file pages or original SVGs.
- `GarudadevDataServices/indian_mlas` has no license surfaced in the initial repository UI probe. Its `scripts/process-data.js` reads `raw_data/india_asm.xlsx`, `raw_data/india_asm.geojson`, and `raw_data/colors.json`; candidate `AGE`, `GENDER`, and `WIKIPEDIA LINK` are lifted directly from the Excel columns.
- `GarudadevDataServices/indian_mlas/raw_data/colors.json` maps party abbreviations and aliases to 4-channel RGBA arrays in the 0..1 range. It is useful as colour QA and alias-discovery input only.

Discovery wording for future PRs:

> Candidate asset discovered via Wikipedia, Commons, thecont1, or search; symbol recognition checked against ECI/CEO material where possible; asset bytes, source URL, license label, hash, and sanitizer result recorded in the collection inventory.

## 2. Core decision

V1 models a **default party election symbol**, not a full symbol-assignment history.

Do **not** create `party_symbols.json`, `party_symbols.parquet`, or `party_symbol_assignments.parquet` for v1. Do **not** track event-specific symbol assignments until a route or source-backed story needs that level of truth.

Model v1 as:

- optional `recognition` on each party row in `datasets/taxonomy/parties.json`, mirrored to `datasets/elections/dim_parties.parquet`;
- optional `election_symbol` metadata on each party row in `datasets/taxonomy/parties.json`;
- sanitized SVG bytes under `frontend/public/party-symbols/*.svg`;
- one reusable placeholder SVG under `frontend/public/party-symbols/placeholder.svg`.

Election-symbol rules:

- Election symbols are ballot-identification glyphs. They are not flags, logos, banners, or motifs.
- Default rendering later should show the symbol next to party names where applicable.
- Store source-coloured SVGs only when the source asset is already coloured. Otherwise store monochrome black/white.
- Do not recolour monochrome symbols with party colours.
- Do not invent symbols for independents, unknown parties, or unresolved rows.
- Recognised parties without collected SVGs get `symbol_status = "placeholder"`, not a fake verified icon.
- Split parties can each carry their current default symbol. The older unified party can keep the older unified symbol. Validity-window history is deferred.

Citizen warning copy, when symbols first surface:

> Symbols are shown where yen-gov has collected a source-backed election-symbol SVG. Some historical and registered unrecognised parties may have missing or changing symbols. Colours are yen-gov chart aids, not ballot-symbol colours.

## 3. 80/20 coverage rule

Do not chase all 617 party rows. The useful first tranche is about 60-100 parties, split by visibility and current recognition.

### Tier 0 - current recognised + high-visibility seed

Target size: 40-60 parties.

Include:

- all current ECI national parties;
- current state-recognised parties visible in yen-gov routes;
- top winners from the DuckDB query above after excluding `IND`, `NOTA`, `UNK`, and legacy alias traps;
- parties already prominent in colour anchors or current state pages.

Initial seed list to review first: `BJP`, `INC`, `CPI(M)`, `CPI`, `AAP`, `DMK`, `AIADMK`, `AITC`, `SP`, `BSP`, `JD(U)`, `BJD`, `RJD`, `SHS`, `NCP`, `SAD`, `TDP`, `YSRCP`, `JD(S)`, `AIFB`, `IUML`, `RSP`, `JMM`, `AGP`, `BRS`, `SDF`, `NPF`, `MNF`, `INLD`, `AIMIM`, `NPP`, `PMK`, `AIUDF`, `SKM`, `NTK`, and `TVK` if present/needed in the 2026 surface.

### Tier 1 - all current recognised parties

Target cumulative size: 60-75 parties.

Backfill `recognition` from the latest ECI national/state recognised-party notification and recognition/de-recognition orders. Recognition is a party identity attribute; it belongs on `taxonomy/parties.json` and then compiles into `dim_parties.recognition`.

### Tier 2 - corpus-impact long tail

Target cumulative size: 100-125 parties.

Add parties meeting any one of these corpus rules:

- party has at least one win and is not a legacy alias trap;
- party has >= 1,000,000 total votes in the corpus;
- party appears in >= 20 election events;
- party is visible in a current route or issue-specific narrative.

### Tier 3 - event-specific or low-exposure rows

Defer everything else. Registered unrecognised parties and independents often receive election-specific common/free symbols. Add them only when a citizen route or source-backed story needs them.

## 4. Source hierarchy

Separate four questions: party identity, recognition, symbol SVG bytes, and presentation colour.

Use this source order for party identity, recognition, and symbol name:

1. ECI main notifications listing national parties, state parties, reserved symbols, registered unrecognised parties, delisted/inactive RUPPs, and free symbols.
2. ECI recognition/de-recognition/restoration/freezing orders, including faction and reserved-symbol disputes.
3. ECI election-symbol detail pages and orders under Paras 10, 10A, and 10B for reserved/common-symbol allotment.
4. State CEO / Returning Officer Form 7A and final list of contesting candidates for election-specific symbol cases.
5. ECI Statistical Reports Section 10 for post-election candidate rows, party short code, symbol text, votes, and reported sex/age/category fields when present.
6. ECI Results Portal pages for current-cycle cross-checks.

Use this source order for SVG bytes:

1. Existing official/source SVG from ECI or State CEO where available.
2. Wikimedia Commons original SVG file page, especially when it matches the ECI symbol name/shape.
3. A new clean SVG trace from ECI/CEO black-and-white source material.
4. Party official site only if it clearly shows the ballot symbol, not a flag/logo.
5. Placeholder SVG for recognised parties whose symbol is not collected yet.

Wikipedia, Commons category pages, `thecont1/india-votes-data`, Garudadev, and general web search are discovery aids. They can tell us where to look; they do not decide recognition status by themselves.

Colour policy:

- Party colours are already a separate frontend presentation contract. The durable home is [frontend/src/lib/colors/anchors.ts](../frontend/src/lib/colors/anchors.ts), with algorithmic fallback in `frontend/src/lib/colors/party-colour.ts` and architecture notes in [docs/architecture/frontend/colours.md](../docs/architecture/frontend/colours.md).
- Do not use the symbol-collection PRs to rebuild the party-colour system.
- Keep a source-coloured SVG if that is the source asset. Otherwise keep monochrome.
- Do not recolour monochrome election symbols with party colours.
- If a future source-backed exact party colour needs to be stored as party data, use the existing `display.colour` override path on party rows rather than adding colour fields to `election_symbol`.
- `thecont1/india-votes-data` and Garudadev colour files are discovery/QA aids for aliases and rough colour sanity checks; they are not canonical party-colour sources by themselves.

License policy:

- User decision 2026-06-01: v1 does not block on per-symbol license anxiety where the asset is an ECI/common election symbol or generic civic glyph.
- Still record `asset_source_url`, `asset_source_kind`, `license_label`, and `asset_sha256` for every non-placeholder SVG.
- Sanitization is mandatory regardless of source.

## 5. Proposed durable layout

Store SVG bytes as public static media; store metadata as party data.

Proposed v1 layout:

```text
frontend/
  public/
    party-symbols/
      placeholder.svg
      lotus.svg
      hand.svg
      hammer-sickle-star.svg
      two-leaves.svg

datasets/
  schemas/
    taxonomy-parties.schema.json      # minor bump: recognition + election_symbol
    dim-parties.schema.json           # minor bump when compiled symbol fields are mirrored
  taxonomy/
    parties.json                      # operator-edited source of truth
    parties.parquet                   # compiled registry view, if/when emitted
  elections/
    dim_parties.parquet               # frontend-readable party dimension
```

Rationale:

- `frontend/public/party-symbols/*.svg` gives the future frontend stable static URLs without remote hotlinks.
- `frontend/public` stores bytes only. It must not contain `party-symbols.json`, CSVs, or party-to-path maps.
- `datasets/taxonomy/parties.json` remains the source of truth for which party gets which default symbol.
- `elections.dim_parties` is the frontend-readable denormalised view, consistent with existing recognition doctrine.
- This is an intentional exception to the older "symbol bytes under datasets" idea. It is safe because the bytes are static public media; the metadata remains data-driven.

## 6. Contract shape

Add optional fields to each party row in `datasets/taxonomy/parties.json`.

Suggested additive fields:

```text
{
  "party_id": "parties.IN.BJP",
  "short_name": "BJP",
  "full_name": "Bharatiya Janata Party",
  "recognition": "national",
  "election_symbol": {
    "symbol_name": "Lotus",
    "asset_path": "party-symbols/lotus.svg",
    "asset_sha256": "...",
    "source_id": "src.commons.symbols-of-political-parties-in-india.YYYY-MM-DD",
    "asset_source_kind": "commons",
    "license_label": "CC-BY-SA-3.0",
    "render_mode": "monochrome",
    "symbol_status": "verified",
    "notes": null
  }
}
```

Name the field `election_symbol` (singular). Reserve `election_symbol_history` for any future validity-window or assignment-history model so the future migration is additive, not breaking.

Suggested `recognition` enum:

- `national`
- `state`
- `registered_unrecognised`
- `unknown`
- `null`

Suggested `election_symbol` fields:

- `symbol_name`: citizen-readable symbol name, e.g. `Lotus`, `Hand`, `Elephant`.
- `asset_path`: path relative to `frontend/public/`, e.g. `party-symbols/lotus.svg`.
- `asset_sha256`: hash of committed SVG bytes.
- `source_id`: FK to one row in `datasets/taxonomy/sources.parquet` per Holy Law #9 and [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md). Null only for `symbol_status = "placeholder"`.
- `asset_source_kind`: `eci`, `state_ceo`, `commons`, `party_official`, `generated_from_eci`, or `editorial_placeholder`. Denormalised hint; the citation truth is `source_id`.
- `license_label`: source license or project label, e.g. `eci-common-symbol`, `CC-BY-SA-3.0`, `public-domain`, `project-placeholder`. Denormalised hint; the citation truth is `source_id`.
- `render_mode`: `monochrome` or `source_coloured`.
- `symbol_status`: `verified`, `placeholder`, `missing`, or `deferred_historical`.
- `notes`: nullable operator note.

Provenance rule: do NOT inline `asset_source_url` on the party row. Each distinct producer (ECI bulletin, Commons file page, state CEO order) gets one row in `datasets/taxonomy/sources.parquet` and `election_symbol.source_id` FKs into it. This keeps party-symbol provenance shaped identically to every other observation in the repo.

Do not add these v1 fields:

- `party_symbols.json`
- `party_symbol_assignments.parquet`
- `party_external_links.json`
- `person_external_links.json`
- `wikipedia_url`
- third-party `colour` / `rgba`
- flags or logos
- event-specific assignment windows

Party/person external links can wait for a profile-page feature. This plan is only about election-symbol SVG collection.

## 7. Validation rules

Backend and frontend contract tests should enforce:

- `taxonomy-parties.schema.json` minor bump adds `recognition` and nullable `election_symbol` fields (PR-SYM-1).
- `dim-parties.schema.json` minor bump adds `recognition` mirror in PR-SYM-1 and the `election_symbol` mirror in PR-SYM-5.
- Every `recognition` value is from the enum.
- Every non-null `election_symbol.asset_path` starts with `party-symbols/`, is POSIX-relative, ends in `.svg`, and has a kebab-case filename.
- Every non-placeholder asset path exists under `frontend/public/party-symbols/`.
- Every SVG hash matches `asset_sha256`.
- Every non-placeholder `election_symbol.source_id` resolves to a row in `datasets/taxonomy/sources.parquet`. Placeholder rows have `source_id = null`.
- Every SVG passes the shared SVG allowlist sanitizer: no `script`, no event-handler attributes, no `foreignObject`, no external `href`, no remote fonts, no embedded raster blobs, no inline `style`, and no `use`.
- The sanitizer is ONE module reused across the icon-registry and the party-symbol registry. Two divergent allowlists is a failure mode; do not copy-paste from `frontend/src/lib/icons/allowlist.ts`. PR-SYM-3 factors the shared module and both registries import it.
- `symbol_status = "placeholder"` must use `party-symbols/placeholder.svg` and must not claim a real symbol name or `source_id`.
- No Svelte or TypeScript file contains a party-id-to-symbol-path map. Future frontend code derives URLs mechanically from party data. PR-SYM-5 ships a contract test that greps for any literal party-id from the top-40 roster in `frontend/src/**` and fails on hit.
- Probe parsers use checked-in fixtures; no pytest test performs live network access or walks the real corpus.
- The collection report distinguishes source discovery, recognition source, asset source, sanitizer result, and placeholder status.

## 8. PR sequence

### PR-SYM-0 - Plan rewrite and policy lock

Goal: close the old relation-heavy design and lock the v1 collection policy.

Work:

- Update this plan with the 2026-06-01 user decisions.
- Record the DuckDB top-N query and the recognised-party-first rule.
- Record that party recognition is an attribute on party identity.
- Record the `frontend/public/party-symbols/` public-media exception.

Acceptance:

- Docs-only PR.
- No assets, schemas, runtime code, or canonical data changes.

### PR-SYM-1 - Recognition + symbol metadata schema

Goal: make the party-row contract explicit before assets land.

Work:

- Add `recognition` (enum) and nullable `election_symbol` (object) to `taxonomy-parties.schema.json` with a minor bump.
- Bump `dim-parties.schema.json` minor to expose `recognition` as a typed enum (was nullable column with no schema declaration). Update the compiler to copy `recognition` from `parties.json` into the compiled `dim_parties.parquet` view.
- Do NOT mirror `election_symbol` into `dim_parties` yet; that mirror ships in PR-SYM-5 alongside the renderer.
- Add backend pytest fixtures (one valid `parties.json` row with `election_symbol`, one with `recognition` only, one with neither, one negative `recognition` value) exercising the schema and the compiler.

Acceptance:

- Schema tests green; both minor bumps appended to each schema's `x-changelog`.
- Existing 617 `parties.json` rows still validate without modification (`election_symbol` and `recognition` are optional).
- Compiled `dim_parties.parquet` regenerates with `recognition` typed; row count unchanged.
- No frontend rendering change.

### PR-SYM-2 - Reproducible roster report

Goal: choose the first 80/20 collection set without hand-picking in chat.

Work:

- Add `notes/YYYY-MM-DD-party-symbol-roster.md` (and optionally `tools/parties/roster_report.py`) that runs the DuckDB top-winner query in section 1 and produces: party_id, eci_code, short_name, full_name, wins, win_states, win_events, candidacies, total_votes.
- Cross-check against the latest ECI national/state recognised-party notification to mark `recognition` candidates per row.
- Flag historical / alias-heavy rows (`JSP`, `INC_I`, `JD`, `ADK`, etc.) for review instead of auto-assigning symbols.
- Record in the note: (a) the verbatim SQL, (b) the git SHA of `datasets/elections/elections_candidacies.parquet` and `datasets/elections/dim_parties.parquet` at probe time, (c) the produced 40-60 target list. The corpus grows, so a rerun in 6 months must either reproduce or knowingly differ from this snapshot.

Acceptance:

- Reviewer can rerun the query verbatim against the recorded SHAs and get byte-identical output.
- The report explains every excluded top-winner alias trap.
- The target set covers all current ECI national parties, current state-recognised parties visible in yen-gov routes, and the main citizen-visible winners.

### PR-SYM-3 - Sanitizer + placeholder asset

Goal: make bad SVGs impossible to commit silently before the first real batch lands.

Work:

- Factor the existing icon-registry SVG allowlist out of `frontend/src/lib/icons/allowlist.ts` into a shared module that both the icon registry and the new party-symbol registry import. ONE allowlist, not two.
- Add `frontend/src/lib/party-symbols/sanitizer.ts` that consumes the shared allowlist and exposes a `sanitizeAndHash(svgBytes) -> { sanitizedBytes, sha256 }` function.
- Add `frontend/public/party-symbols/placeholder.svg` (monochrome, no source, generic civic glyph).
- Add vitest fixtures: malicious SVGs (script, onload, foreignObject, external href, inline style, use, embedded raster) plus the placeholder and a small clean party-symbol fixture. The contract test walks `frontend/public/party-symbols/*.svg` and runs the sanitizer on each.

Acceptance:

- Malicious fixture tests reject scripts, event handlers, external links, `foreignObject`, `style`, `use`, and embedded rasters.
- The shared allowlist module is the only allowlist in `frontend/src/`; a grep for a second `ALLOWED_ELEMENTS` constant finds none.
- Placeholder SVG passes the sanitizer and round-trips to a stable `sha256`.

### PR-SYM-4a - First SVG batch + sources ledger

Goal: land the bytes and their provenance, separate from the 617-row `parties.json` edit so reviewers can read each diff line-by-line.

Work:

- Add 40-60 sanitized SVG assets under `frontend/public/party-symbols/` (one per Tier-0 / Tier-1 target from PR-SYM-2's roster).
- For each distinct producer (ECI bulletin, Commons file page, state CEO order), add one row to `datasets/taxonomy/sources.parquet` per [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md). Build `source_id` via `backend.yen_gov.canonical.citation.derive_source_id`; never hand-author.
- PR body inventory table: `slug | asset_path | sha256 | source_id | license_label | render_mode | sanitizer_result`.
- Do NOT edit `datasets/taxonomy/parties.json` in this PR. The `election_symbol` rows referencing these assets land in PR-SYM-4b.

Acceptance:

- PR-SYM-3 sanitizer vitest passes on every new SVG.
- Every new `source_id` resolves under Tier-A validate.
- No frontend route renders symbols yet.

### PR-SYM-4b - Populate parties.json and recompile dim_parties

Goal: connect the bytes to the party rows; surface in `dim_parties.parquet` for the renderer to pick up.

Work:

- Edit `datasets/taxonomy/parties.json` to add `recognition` and `election_symbol` blocks for each Tier-0 / Tier-1 party on the roster.
- For recognised parties without a collected SVG in PR-SYM-4a, write `symbol_status: "placeholder"` with `source_id: null`.
- Recompile `datasets/elections/dim_parties.parquet`; `recognition` populates from the new schema mirror (`election_symbol` mirror is deferred to PR-SYM-5).
- Update the coverage section of `notes/YYYY-MM-DD-party-symbol-roster.md` with before/after counts.

Acceptance:

- Tier-A validate green: every non-placeholder `election_symbol.source_id` FK resolves; every `asset_path` exists; every `asset_sha256` matches the bytes shipped in PR-SYM-4a.
- Pytest green.
- Coverage report shows recognised-party coverage and top-N winner coverage before/after.
- No frontend route renders symbols yet.

### PR-SYM-5 - Frontend renderer + dim_parties election_symbol mirror

Goal: render collected symbols next to parties.

Work:

- Bump `dim-parties.schema.json` minor to mirror `election_symbol` (writer-before-reader / reader-before-writer per [ADR-0047](../docs/architecture/decisions/0047-schema-version-compatibility-contract.md), one PR).
- Update the compiler to copy `election_symbol` from `parties.json` into `dim_parties.parquet`.
- Add `frontend/src/lib/parties/symbol-url.ts` that mechanically derives a static URL from a `dim_parties` row plus the Vite base URL; uses the placeholder when `symbol_status = "placeholder"`; renders nothing for parties with no `election_symbol` block.
- Wire 1-2 Svelte consumers (e.g. a candidate row or a party badge) to read the URL through `symbol-url.ts`. No party-id literals.
- Add a contract test that greps `frontend/src/**` for any literal party-id from the top-40 roster and fails on hit (Holy Law #6).
- Add the citizen warning copy from section 2 to the first surface that renders a symbol.

Acceptance:

- Unit tests cover verified, placeholder, missing, and invalid asset states.
- svelte-check + vitest green.
- Browser smoke per [CLAUDE.md](../CLAUDE.md) section 13 on one affected route: symbol renders for a verified row, placeholder renders for a placeholder row, no console errors, no 404.

## 9. Closed decisions and deferred questions

Closed for v1:

- Recognition is a party attribute in `taxonomy/parties.json`, mirrored into `dim_parties`; no separate recognition table.
- SVG bytes live under `frontend/public/party-symbols/`; metadata lives on party rows.
- No `party_symbols` registry or `party_symbol_assignments` relation for v1.
- No flags, logos, banners, or composites.
- No party-colour chase. Keep source-coloured assets if they exist; otherwise monochrome.
- User policy accepts ECI/common election-symbol glyphs as suitable v1 assets when source, hash, and sanitizer result are recorded.
- Split-party deep history is deferred.

Closed 2026-06-01 (Gregor sequencing pass, baked into Status Reckoner + section 8):

- `dim_parties` mirror split: `recognition` in PR-SYM-1, `election_symbol` in PR-SYM-5 (writer-before-reader / reader-before-writer per [ADR-0047](../docs/architecture/decisions/0047-schema-version-compatibility-contract.md) lands as one PR per mirror).
- Sanitizer is ONE shared module factored from `frontend/src/lib/icons/allowlist.ts` in PR-SYM-3; both registries import it. No copy-paste.
- PR-SYM-4 splits into PR-SYM-4a (bytes + `sources.parquet`) and PR-SYM-4b (parties.json + recompile) so 40-60 SVG bytes and 617-row `parties.json` edits review independently.
- `election_symbol` is singular per row; future history goes to `election_symbol_history` (additive, not breaking).
- `election_symbol.source_id` FKs into `datasets/taxonomy/sources.parquet` per [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md); no inline `asset_source_url` on the party row.

Closed 2026-06-01 (Hans + Jony red-team pass for Wikipedia enrichment, baked into Status Reckoner + section 11):

- `brand_colour` is editorial Wikipedia consensus, NOT party identity. ECI does not register party colours; only symbols are official.
- `brand_colour` and `wikipedia_url` are both OPTIONAL (enrichment, not required). Graceful fallover throughout.
- `source_kind` literal is `"wiki"` (short). One `sources.parquet` row per list-page snapshot, shared across every party row lifted in that pass.
- `wikipedia_url` is the PARTY ARTICLE URL, not the list-page URL (list page is already pinned via `source_id`).
- `confidence` enum `high | medium | low`; resolver treats `low` as absent (fall through to algorithmic fallback).
- Faction-split parties (SHS-UBT/SHS, NCP/NCP-SP, LJP-RV/LJP-Paswan, AIADMK historical) MUST have `confidence: low` + non-null `notes`.
- Resolver returns `{hex, source, party_id}`, not bare hex. `source` drives per-tier render affordance contract (anchor / brand / fallback).
- Resolver MUST NOT mutate hex for contrast / a11y. Identity is preserved; canvas (chip background, paired label) solves legibility. Anchor override is the policy surface.
- PR-SYM-5 (single renderer PR) is RETIRED. Replaced by PR-SYM-6a/b/c/d to keep diffs reviewable and isolate consumer-by-consumer regressions.
- No citizen-facing disclaimer copy. Provenance lives on the data row + plan-doc; UI stays clean.

Rejected (do not re-litigate):

- **Per-party-template `source_id` rows.** The meta/color template is *transcluded* onto the list page; the list page IS the citation surface. Per-template rows would explode the ledger ~2800x with zero provenance gain.
- **Auto-darken / lighten / contrast-tune of `brand_colour` in the resolver.** Identity must not mutate. If a brand colour is unusable on a given canvas, the fix is an anchor override authored by a human, not a runtime tweak.
- **Treating Garudadev RGBA as an independent authority.** Both Garudadev and Wikipedia are downstream of the same editorial community. Use as lint cross-check only.
- **Surfacing the "Wikipedia editors chose this colour" disclaimer in citizen-facing UI.** User decision 2026-06-01: redundant when source provenance is already on the data row.
- **Mandatory `wikipedia_url` or `brand_colour`.** Both fields are enrichment; renderer fallover handles absence gracefully.

Still open:

- Exact Tier 0 size: 40, 50, or 60 parties (settled inside PR-SYM-2 from the roster query output).
- Whether `brand_colour` eventually moves off `parties.json` to a sibling `party_brand.parquet` family - the field is editorial/mutable on a different cadence than ECI registration data. Defer until first ingest reveals churn rate.

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
- [docs/architecture/frontend/charts/icon-registry.md](../docs/architecture/frontend/charts/icon-registry.md)
- [docs/architecture/frontend/colours.md](../docs/architecture/frontend/colours.md)
- [TODO/PARTY-COLORS-REWORK.md](PARTY-COLORS-REWORK.md)
## Plan complete (2026-06-02)

The PR-SYM series shipped end-to-end. The one-identity party-colour migration spine is live on 4 high-traffic consumers and guarded by a contract test.

### Renumbering note

The original plan named 4 renderer PRs (6a/b/c/d). During execution the row count expanded to 6 (6a/b/c/d/e/f) because (a) the data-layer mirror (schema + writer + pydantic + adapter) earned its own PR separate from the resolver to keep gate matrices independent, and (b) a batch-resolver helper was added at the 2nd batch consumer rather than pre-built. The reckoner above maps each as-shipped PR# to its actual scope.

### Distillation map

| Original | As-shipped | PR | Durable destination |
| --- | --- | --- | --- |
| PR-SYM-1 | PR-SYM-1 | #526 | taxonomy-parties v2.2 schema + tests |
| PR-SYM-4a-redo | PR-SYM-4a-redo | #551 | 50 Wikipedia-sourced election symbol assets |
| PR-SYM-4b | PR-SYM-4b | #563 | parties.json populated + taxonomy v2.3 |
| PR-SYM-4c | PR-SYM-4c | #564 | brand_colour + wikipedia_url for 55 parties |
| PR-SYM-6a | PR-SYM-6a | #566 | resolver.ts (3-tier contract) |
| PR-SYM-6 (data) | PR-SYM-6b | #570 | dim_parties v1.1 schema + writer + adapter |
| PR-SYM-6 (loader+1st) | PR-SYM-6c | #571 | loader projection + AcStackedBar |
| PR-SYM-6 (2nd) | PR-SYM-6d | #577 | MarginHistogram + AcWinner spine |
| PR-SYM-6 (batch helper + 3rd/4th) | PR-SYM-6e | #580 | resolvePartyPalette + StateAcMap + RacesBoard |
| PR-SYM-6 (guardrail) | PR-SYM-6f | #581 | import-allowlist contract test |
| Distillation (this PR) | distill | _pending_ | docs/concepts/party-colour-resolution.md + plan-doc stamp |

### Out of scope, follow-up

12 grandfathered consumers remain on the legacy `colors.fill` / `partyColour` path. The full enumeration with migration tier (A leaf / B loader-contract / C upstream) lives in the ALLOWLIST block in `frontend/src/contracts/party-colour-import-allowlist.test.ts`. Each consumer is a separate one-PR follow-up; legacy modules (`party-colour.ts`, `anchors.ts`, `store.svelte.ts`, `category-colour.ts`) delete when the ALLOWLIST goes empty. The 6-step migration recipe is in [docs/concepts/party-colour-resolution.md](../docs/concepts/party-colour-resolution.md).

