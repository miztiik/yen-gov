# Party Symbol Assets Plan

**Last Updated**: 2026-06-01
**Status**: Proposed research handoff - no implementation landed
**Scope**: Collect sanitized SVG election symbols for the parties citizens most often see. Frontend rendering comes later.

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

- Do not chase colours in this plan.
- Keep a source-coloured SVG if that is the source asset.
- Otherwise keep monochrome.
- Party colour anchors remain separate frontend presentation aids.

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
    "asset_source_url": "https://...",
    "asset_source_kind": "commons",
    "license_label": "CC-BY-SA-3.0",
    "render_mode": "monochrome",
    "symbol_status": "verified",
    "notes": null
  }
}
```

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
- `asset_source_url`: ECI/CEO/Commons/official source URL or null for placeholder.
- `asset_source_kind`: `eci`, `state_ceo`, `commons`, `party_official`, `generated_from_eci`, or `editorial_placeholder`.
- `license_label`: source license or project label, e.g. `eci-common-symbol`, `CC-BY-SA-3.0`, `public-domain`, `project-placeholder`.
- `render_mode`: `monochrome` or `source_coloured`.
- `symbol_status`: `verified`, `placeholder`, `missing`, or `deferred_historical`.
- `notes`: nullable operator note.

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

- `taxonomy-parties.schema.json` minor bump adds `recognition` and nullable `election_symbol` fields.
- `dim-parties.schema.json` minor bump mirrors only the frontend-needed subset when the compile path is updated.
- Every `recognition` value is from the enum.
- Every non-null `election_symbol.asset_path` starts with `party-symbols/`, is POSIX-relative, ends in `.svg`, and has a kebab-case filename.
- Every non-placeholder asset path exists under `frontend/public/party-symbols/`.
- Every SVG hash matches `asset_sha256`.
- Every SVG passes the existing icon-registry style allowlist: no `script`, no event-handler attributes, no `foreignObject`, no external `href`, no remote fonts, no embedded raster blobs, no inline `style`, and no `use`.
- `symbol_status = "placeholder"` must use `party-symbols/placeholder.svg` and must not claim a real symbol name/source.
- No Svelte or TypeScript file contains a party-id-to-symbol-path map. Future frontend code derives URLs from party data.
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

- Add `recognition` and nullable `election_symbol` fields to `taxonomy-parties.schema.json` with a minor bump.
- Update the taxonomy parties validator/tests with small fixtures.
- Decide whether `dim_parties` mirrors symbol fields immediately or waits until frontend rendering. If mirrored now, bump `dim-parties.schema.json` minor and update the compiler.

Acceptance:

- Schema tests green.
- Existing parties with no symbol remain valid.
- No frontend rendering change.

### PR-SYM-2 - Reproducible roster report

Goal: choose the first 80/20 collection set without hand-picking in chat.

Work:

- Add a small report script or documented DuckDB query that produces: party_id, code, full name, wins, win_states, win_events, candidacies, total_votes.
- Join current ECI recognised-party sources to mark `recognition` candidates.
- Flag historical/alias-heavy rows for review instead of auto-assigning symbols.
- Produce a checked-in handoff note under `notes/` or the PR body with the first 40-60 targets.

Acceptance:

- Reviewer can rerun the query.
- The report explains every excluded top-winner alias trap.
- The target set covers current recognised parties and the main citizen-visible winners.

### PR-SYM-3 - Sanitizer + placeholder asset

Goal: make bad SVGs impossible to commit silently before the first real batch lands.

Work:

- Reuse or factor the existing icon-registry SVG allowlist for party-symbol assets.
- Add `frontend/public/party-symbols/placeholder.svg`.
- Add tests that walk `frontend/public/party-symbols/*.svg` and reject unsafe SVGs.

Acceptance:

- Malicious fixture tests reject scripts, event handlers, external links, `foreignObject`, `style`, `use`, and embedded rasters.
- Placeholder SVG passes the same sanitizer.

### PR-SYM-4 - Seed first SVG batch

Goal: collect the first visible set, without frontend rendering yet.

Work:

- Add 40-60 sanitized SVG assets under `frontend/public/party-symbols/`.
- Update `datasets/taxonomy/parties.json` with `recognition` and `election_symbol` metadata for those parties.
- Use source-coloured SVGs only when the source asset is already coloured; otherwise store monochrome.
- Use placeholder metadata for recognised parties where the SVG was not collected in this batch.

Acceptance:

- Inventory table in the PR body lists `party_id`, short name, wins/rank where applicable, recognition status/source, symbol name, asset path, source URL, license label, hash, render mode, symbol status, and sanitizer result.
- Coverage report shows recognised-party coverage and top-N winner coverage before/after.
- No frontend route renders symbols yet.

### PR-SYM-5 - Later frontend renderer

Goal: render collected symbols next to parties once the data and assets are stable.

Work:

- Add a party-symbol view-model path that reads `dim_parties`/party data.
- Render `asset_path` mechanically from data and the Vite base URL.
- Use the placeholder only when `symbol_status = "placeholder"`.
- Do not create a party-id-to-path map in Svelte or TypeScript.

Acceptance:

- Unit tests cover verified, placeholder, missing, and invalid asset states.
- Browser smoke per [CLAUDE.md](../CLAUDE.md) section 13 on one affected route.

## 9. Closed decisions and deferred questions

Closed for v1:

- Recognition is a party attribute in `taxonomy/parties.json`, mirrored into `dim_parties`; no separate recognition table.
- SVG bytes live under `frontend/public/party-symbols/`; metadata lives on party rows.
- No `party_symbols` registry or `party_symbol_assignments` relation for v1.
- No flags, logos, banners, or composites.
- No party-colour chase. Keep source-coloured assets if they exist; otherwise monochrome.
- User policy accepts ECI/common election-symbol glyphs as suitable v1 assets when source, hash, and sanitizer result are recorded.
- Split-party deep history is deferred.

Still open:

- Exact Tier 0 size: 40, 50, or 60 parties.
- Whether `dim_parties` should mirror `election_symbol` fields before frontend rendering or in the renderer PR.
- Whether the sanitizer should reuse `frontend/src/lib/icons/` directly or expose a small shared validation helper for `frontend/public/party-symbols/` tests.

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