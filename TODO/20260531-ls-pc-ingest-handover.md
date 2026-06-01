# 2024 Lok Sabha (PC) election results ingest handover

**Last Updated**: 2026-05-31

> New-source ingest handover for the 2024 General Election to Lok Sabha, parliamentary-constituency (PC) grain. Companion to plan-doc [20260531-uk-style-elections-experience-plan.md](20260531-uk-style-elections-experience-plan.md) Lane A (PR-A1 .. PR-A4). Baked agent verdicts (Max + Hans + Gregor) live in that plan-doc's PR-A1..A4 sections and are NOT re-derived here.

## 1. Source

- **Publisher**: Election Commission of India (ECI), <https://results.eci.gov.in/> statistical reports.
- **Primary file**: `2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv` (ECI Report 33, "Constituency Wise Detailed Result"). Local ephemeral snapshot under `datasets/ephemeral/`.
- **Crosswalk file**: `2024_india_loksabha_34-Details-Of-Assembly-Segment-Of-PC.csv` (ECI Report 34). Carries `PC NO` + `PC NAME` + State and the AC-segment composition. Used ONLY to source the missing `pc_no` (Report 33 has PC Name but no PC No) and as the AC<->PC crosswalk. NOT the PC spine (it is EVM-only / AC-segment grain and drops postal votes plus the single-PC non-assembly UT seats).
- **Vintage / cadence**: ECI general-election release; one definitive edition per general election (every ~5 years). `update_period_days = 1825`.
- **License**: ECI statistical reports are public-record election data (academic / research use per the report disclaimer footer).
- **Sampling frame / methodology**: full-population count of valid votes per candidate per PC. Report 33 is POSTAL-INCLUSIVE (each candidate row carries General [EVM] + Postal + Total). NOTA is a candidate row (`Party Name = NOTA`). Delimitation: 2008 order (543 PCs).

## 2. Scope

- **Concept(s) measured**: parliamentary-constituency election result -- votes polled, turnout, NOTA, winner candidate, winner party, margin, electors, effective number of candidates.
- **Unit canonical**: `votes` (counts), `%` (shares), `entity_id` (winner refs).
- **Normalisation**: `absolute` for counts, `share` for percentages, `absolute` (id-valued) for winner refs.
- **Entity grain(s)**: `pc` (parliamentary constituency). Per Option B (ADR-0048), pc-* measures that also exist at AC grain share ONE `concept_id` whose `entity_kinds` lists both `ac` and `pc`.
- **Time range**: 2024 (Phase 2 ships 2024 only; the seam is built to admit prior general elections behind a `delim_year` token).

### Recon findings (PR-A1, source probe 2026-05-31)

Probe of Report 33 (header detection corrected; csv.reader row index 2 is the real header after a banner row 0 and a group sub-header row 1):

- 542 contested PCs present (Surat PC-24 Gujarat won unopposed and is excluded by ECI from Report 33; 2024 total is 543 seats).
- 8904 candidate body rows; 36 real states/UTs plus 3 footer junk pseudo-rows ("Disclaimer", "Note -...", "These statistical reports...") that the parser MUST skip.
- Single-PC non-assembly UTs present (A&N, Chandigarh, Lakshadweep, Ladakh, DNH-DD, Puducherry; NCT Delhi 7 PCs) -- confirms the direct ECI file carries the seats an AC-segment spine would drop.
- Header columns (17 meaningful + 3 trailing empty): `State Name, PC Name, Candidate Name, Gender, Age, Category, Party Name, Party Symbol, Total Votes Polled In The Constituency, Valid Votes, General, Postal, Total, Over Total Electors In Constituency, Over Total Votes Polled In Constituency, Over Total Valid Votes Polled In Constituency, Total Electors`.
- Per-PC totals (`Total Votes Polled In The Constituency`, `Valid Votes`, `Total Electors`) repeat identically on every candidate row of that PC.
- KEY GAP: Report 33 has NO `PC No` column. `pc_no` is sourced from the Report 34 crosswalk on `(State Name, PC Name)`. This is a PR-A3 parser concern.

## 3. Concept overlap audit (MANDATORY -- guardrail #14 + ADR-0046)

- **Proposal**: [20260531-ls-pc-proposal.json](20260531-ls-pc-proposal.json) (representative measure `pc-votes-polled`)
- **Report**: [20260531-ls-pc-report.json](20260531-ls-pc-report.json)
- **Verdict**: `add_facet` (concept overlap 1.0 with `votes-polled`)
- **Target indicator_id**: `elections/votes-polled` (extend `entity_kinds` to include `pc`)
- **Exit code**: 0 (all six checks pass)

**Verdict** (per concept, Option B concept-binding -- bind pc-* to the existing AC concept by extending its `entity_kinds`, never mint a duplicate):

- [x] `votes polled` -> `add_facet` on `elections/votes-polled` (overlap 1.0; pre-flight verified exit 0)
- [ ] `turnout` -> bind to `turnout` (entity_kinds -> `['ac','pc']`)
- [ ] `electors` -> bind to `electors`
- [ ] `NOTA votes` -> bind to `nota-votes`
- [ ] `margin %` -> bind to `margin`; `margin votes` -> bind to `margin-absolute`
- [ ] `others votes` -> bind to `others-votes`
- [ ] `winner` -> bind to `winner`; `winning party` -> bind to `winning-party-ac` (grain-neutral concept; the `(AC)` noun wart is tolerated, entity_kinds extended to `['ac','pc']`)
- [ ] PC-exclusive measures with no AC sibling (`pc-effective-candidates-laakso`, `pc-candidates-total`) mint their OWN concept with `entity_kinds: ['pc']`.

The representative pre-flight run proves the binding path resolves to `add_facet`/`upsert` (not `mint_new`) for shared concepts. PR-A2 extends each bound concept's `entity_kinds` in `datasets/taxonomy/concepts.json` and authors the pc-* indicator rows.

## 4. Identifiers

- **`indicator_id`** family: `elections/pc-*` (kebab-case `<measure>-<unit>-<facet>`; `pc-` is a FACT-grain prefix preserved by ADR-0044, NOT a grain prefix matched by the `^(state|district|national)-` gate).
  - `pc-total-electors`, `pc-votes-polled`, `pc-turnout-pct`, `pc-nota-votes`, `pc-nota-pct`, `pc-winner-candidate-id`, `pc-winner-party-id`, `pc-margin-votes`, `pc-margin-pct`, `pc-effective-candidates-laakso`, `pc-candidates-total`, `pc-others-votes`, `pc-others-pct`.
- **`concept_id`**: shared with the AC sibling per Option B (e.g. `pc-votes-polled` -> `votes-polled`); PC-exclusive measures mint a `['pc']`-only concept.
- **`source_id`**: derived via `backend.yen_gov.canonical.citation.derive_source_id` (never hand-author per CLAUDE.md section 12). Producer "Election Commission of India", title "General Election to Lok Sabha 2024 - Constituency Wise Detailed Result (Report 33)", vintage "LsGen2024".
- **`update_period_days`**: `1825` (~5-year general-election cadence).

### Entity id and event id conventions

- **PC entity_id** (globally unique per Gregor must-fix): `IN-PC-<delim_year>-<state_code>-<pc_no>`. ECI `pc_no` is per-state (each state restarts at 1), so the `state_code` segment is load-bearing for global uniqueness. `<delim_year>` is the 4-digit delimitation order year (`2008` for 2024). Example: Araku (Andhra Pradesh, PC 1) -> `IN-PC-2008-AP-1`.
- **event_id**: `LsGen2024` (Lok Sabha general election 2024). Added as a `kind: "lok_sabha"` row in `datasets/elections/election_events.json` in PR-A4.
- **period_label**: `2024` (the poll year). The `delim_year` discontinuity is carried by the entity_id token, not the period axis.

## 5. Pipeline plan

- **Meadow tier**: not used for this ingest -- ECI Report 33 CSV is parsed directly into canonical ObservationRows (the CSV is already a tidy per-candidate table; no intermediate parsed-JSON tier needed). The source CSV stays an ephemeral snapshot.
- **Source parser** (PR-A3): `backend/yen_gov/sources/eci/ls_constituencywise.py` -- stdlib `csv` only (NO xlrd / pandas). Skips banner row 0 + group sub-header row 1; asserts the real header (row index 2) carries the expected cells (`State Name`, `PC Name`, `Candidate Name`, `Party Name`, `General`, `Postal`, `Total`, `Valid Votes`, `Total Electors`) and raises a fail-fast error at the parser boundary on any missing column (Gregor Message-Translator + fail-fast verdict). Skips footer junk pseudo-rows. Joins `pc_no` from the Report 34 crosswalk on `(State Name, PC Name)`.
- **Canonical adapter** (PR-A3): `backend/yen_gov/canonical/adapters/eci/pc_observations.py` -> `observations_from_pc(...)`.
- **Write seam** (PR-A4, Gregor verdict): PC ObservationRows share the EXISTING `datasets/elections/state=<key>/election_results.parquet` family, disambiguated by `entity_id` prefix + `indicator_id` + `entity_kind=pc`. NOT a sibling family; NO `grain=` partition dimension added. PC dim rows -> `datasets/elections/dim_pcs.parquet`. `lok_sabha` event -> `election_events.json`. `sources.parquet` UPSERT.
- **Schemas**: adding `pc` to the catalogue `entity_kinds` enum is a MINOR additive bump + x-changelog entry (PR-A2). `observation.schema.json` does NOT enumerate `entity_kind` (grep-confirm in PR-A2). `kind: "lok_sabha"` already exists in the events enum (no events-schema bump). Reader-before-writer per ADR-0047.
- **Tier-A tests** (PR-A3): `backend/tests/test_pc_observations.py` against a tiny 2-3 PC inline fixture (NOT the real corpus per CLAUDE.md section 10).
- **Tier-B impact**: `tier_b_one_indicator_per_concept` keys on `(concept_id, sorted entity_kinds)`; `ac` and `pc` are distinct entity_kinds so binding pc to an AC concept never collides. `tier_b_indicator_id_no_grain_prefix` does not match `pc-`. `coverage.py` MUST be updated to discriminate AC vs PC (Gregor must-fix) so PC coverage is not double-counted against AC.

## 6. Acceptance gates

- [x] PR-A1: G1 `python -m yen_gov validate --root .` OK; pre-flight report committed (exit 0). No pytest/vitest for the recon row.
- [ ] PR-A2: G1 validate; G2 targeted pytest (catalogue + concept registry).
- [ ] PR-A3: G2 targeted pytest (`test_pc_observations` + downstream readers); G1 validate.
- [ ] PR-A4: per-year PC-count assertion (542 contested in Report 33 / 543 total seats) as the ingest gate; G1 validate.

## 7. Open questions

- **Historical PC CSV acquisition (escalation, deferred past Phase 2):** Phase 2 ships 2024 only (ECI Report 33). Per the Hans+Max baked verdict, prior general elections need direct-PC CSVs: acquire the 2019 ECI constituency-wise CSV (same shape as 2024) and the TCPD direct PC-level GE release for 1999-2014 (confirm URL + licence). `All_States_GA.csv` (TCPD AC-segment, EVM-only, 1999-2019) is FALLBACK-ONLY; any year ingested from it tags every PC total `segment_approximate = true` and a `methodology_breaks.parquet` row records the 2008 delimitation discontinuity. Not blocking PR-A2..A4 (those ship 2024).
- Surat PC-24 (unopposed): ship as a winner-only row (no votes-polled / turnout) sourced from ECI Report 2A, or omit from 2024 PC coverage entirely? Defer to Max/Hans in PR-A4. Default: omit from vote-bearing measures, optionally add a winner-only row.
- `pc-effective-candidates-laakso`: compute in-adapter from per-candidate Total, or defer as a derived rollup? Default: compute in `rollups.py` (PR-A3).

## 8. References

- [20260531-uk-style-elections-experience-plan.md](20260531-uk-style-elections-experience-plan.md) (Lane A baked verdicts)
- [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md) grain over entity
- [ADR-0045](../docs/architecture/decisions/0045-grapher-catalogue-split.md) grapher catalogue split
- [ADR-0046](../docs/architecture/decisions/0046-pre-flight-ingest-gate-contract.md) pre-flight ingest gate
- [ADR-0048](../docs/architecture/decisions/0048-elections-drill-ia-and-tile-cartogram.md) elections drill IA + tile cartogram
- [docs/architecture/data/elections-indicators.md](../docs/architecture/data/elections-indicators.md) (Lok Sabha / PC scope section)
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md)
- [docs/concepts/indicator-naming.md](../docs/concepts/indicator-naming.md)
