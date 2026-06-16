# 2026-06-14 — ADR / MyNeta 2014 Lok Sabha winners-affidavit ingest handover (Row B)

**Last Updated**: 2026-06-15

> Per-PR handover-doc for Row B of [TODO/20260614-three-ephemeral-ingests-plan.md](20260614-three-ephemeral-ingests-plan.md). Row B extends `datasets/elections/parliament/election=2014/candidacies.csv` with 4 nullable disclosure columns sourced from the ADR/MyNeta 2014 Lok Sabha winners affidavit-analysis file at `datasets/ephemeral/2014_lok_sabha_affidavits.csv`. Citizen surfaces (Row D) come in a separate PR after Rows B + C land.

## 1. Source

- **Publisher**: Association for Democratic Reforms (ADR) via [myneta.info/ls2014/](https://myneta.info/ls2014/).
- **Vintage / cadence**: 2014 Lok Sabha general election; affidavit-disclosure snapshot taken at nomination. Refresh cadence is per-election (so update_period_days = 1825 ~= 5y).
- **License**: Public-good data publication; ADR's `myneta.info` site invites third-party reuse with citation. Plan-doc records the source-row registration step in [datasets/data/entities/source.csv](../datasets/data/entities/source.csv) as the operator-visible citation.
- **Sampling frame / methodology**: ADR's MyNeta team transcribes the candidate-self-declared Form 26 affidavits filed at ECI at nomination. Winners-only filter applied upstream. The file therefore covers EXACTLY the 542 winners of the 2014 LS general (1 winner — Jamshedpur PC, BJP, Bidyut Baran Mahato — is not present in the affidavit transcription; this is a publisher gap, not a join failure).

## 2. Scope

- **Concept(s) measured**:
  - `criminal_cases_declared` — count of criminal cases self-declared in the candidate's Form 26 affidavit.
  - `total_assets_inr` — total self-declared assets in INR (movable + immovable).
  - `total_liabilities_inr` — total self-declared liabilities in INR.
  - `declared_election_expense_inr` — election-expenditure declaration filed post-election.
- **Unit canonical**: `cases` (count) for criminal; `INR` (integer rupees) for the three monetary columns.
- **Normalisation**: `absolute` (raw counts and rupee amounts; no per-capita or per-cohort normalisation in this PR).
- **Entity grain**: `candidate` (one row per winning candidacy in the 2014 LS general). Side A per Max's indicator-catalogue split — entity-attribute columns on the candidacy dimension, NOT indicator rows in the catalogue.
- **Time range**: 2014 LS general election cohort only (this PR). 2019 + 2024 cohorts are NOT in scope; FB-1 may add them in a future ingest if ADR / MyNeta publish parallel files.

## 3. Concept overlap audit (MANDATORY — guardrail #14 + ADR-0046)

This PR does NOT mint a new indicator-catalogue row. The 4 new columns are entity-attribute columns on the candidacy dimension (Side A); aggregate-rollup indicator rows (e.g. "% of state's MPs with declared criminal cases") are deferred to FB-1 per plan-doc.

The pre-flight RUN is still discharged here per CLAUDE.md §10 anti-pattern, so the FB-1 author inherits a starting proposal. The sketched proposal is captured below; the catalogue insertion lives in the follow-on PR.

- **Proposal**: [20260614-2014-ls-affidavits-ingest-handover-proposal.json](20260614-2014-ls-affidavits-ingest-handover-proposal.json)
- **Report**: [20260614-2014-ls-affidavits-ingest-handover-report.json](20260614-2014-ls-affidavits-ingest-handover-report.json)
- **Verdict** (for the FB-1 fold-back, not this PR): `mint_new` — `elections/criminal-cases-declared-cases-affidavit`
- **Exit code**: see `report.json` (run is deterministic — re-runs against the same proposal produce identical reports).

**Verdict** (per concept, scoped to the FB-1 fold-back):

- [x] `Criminal cases declared (candidate affidavit)` -> `mint_new` (no existing concept >= 0.70 on the four-axis fingerprint; new id is `elections/criminal-cases-declared-cases-affidavit`).
- [ ] `Total assets declared (candidate affidavit)` -> FB-1 sibling proposal.
- [ ] `Total liabilities declared (candidate affidavit)` -> FB-1 sibling proposal.
- [ ] `Declared election expense` -> FB-1 sibling proposal.

If `mint_new` (FB-1 fold-back, not this PR):

- [ ] A row will be added in `datasets/taxonomy/concepts.json` declaring `(noun, unit_canonical, normalisation, entity_kinds[])` for the new concept. The new `indicator_id` MUST FK to that `concept_id` via `meta.concept_id`.
- [x] `meta.justification` on the proposal explicitly distinguishes the new concept from any other "criminal" / "cases" concept by sampling-frame: candidate-affidavit-declaration, NOT adjudicated conviction.

## 4. Identifiers

- **`indicator_id`** (FB-1): `elections/criminal-cases-declared-cases-affidavit` (kebab-case; NO `<grain>-` prefix per [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md)). NOT minted in this PR.
- **`concept_id`** (FB-1): TBD at FB-1 mint time.
- **`source_id`**: `src-e9565084cbd1` — derived via `backend.yen_gov.canonical.citation.derive_source_id(producer="Association for Democratic Reforms (ADR / MyNeta)", title="Lok Sabha 2014 Winners — Affidavit Analysis (MyNeta)", vintage="2014")` and registered in [datasets/data/entities/source.csv](../datasets/data/entities/source.csv).
- **`update_period_days`**: 1825 (~5 years; per-election cadence).

**Source-attribution policy** (binding from user 2026-06-15 "your job is to enrich existing data — so take what split you can make and enrich it, dont try to change data already published"):

- The candidacy row's `source_id` STAYS at the ECI publisher's id (`src-d4b15132ad0e`). Votes, party, position, vote_share — those facts come from ECI and the publisher attribution must remain pristine.
- The MyNeta affidavit-source citation chain is preserved out-of-band via:
  1. `source.csv` carries the MyNeta source_id row (operator-visible audit trail).
  2. `datasets/data/_schema/columns.schema.json` x-changelog entry version `2.2` explicitly cites the MyNeta source_id and the 4 new cols.
  3. The PR commit message + this handover-doc bake in the same trail.
- A future schema bump may introduce a sidecar column (e.g. `affidavit_source_id`) to make the linkage explicit on the row; deferred to FB-1.

## 5. Pipeline plan

- **Meadow tier**: N/A — the affidavit file at `datasets/ephemeral/2014_lok_sabha_affidavits.csv` is the input. Adapter consumes the ephemeral file directly.
- **Canonical adapter**: [backend/yen_gov/canonical/adapters/myneta/lok_sabha_2014_winners.py](../backend/yen_gov/canonical/adapters/myneta/lok_sabha_2014_winners.py)
  - Public entry `enrich_2014_ls_candidacies(root, affidavit_path) -> AdapterReport`.
  - Normalisers: [backend/yen_gov/canonical/adapters/myneta/_normalisers.py](../backend/yen_gov/canonical/adapters/myneta/_normalisers.py).
  - Alias overlay: [datasets/_overrides/affidavit-2014-pc-aliases.csv](../datasets/_overrides/affidavit-2014-pc-aliases.csv) (12 hand-curated 1-to-1 PC spelling drifts).
  - CLI shim: `python -m yen_gov enrich-2014-ls-candidacies-with-affidavits --input <path> --root <root>` (in `backend/yen_gov/cli.py`).
- **Schemas**: bumped [datasets/data/_schema/columns.json](../datasets/data/_schema/columns.json) (`$schema_version` 2.1 -> 2.2; 4 new col declarations on BOTH parliament + assembly candidacies file-classes — forward-defensive mirror so AE adapters can populate them later without re-bumping schema) + [datasets/data/_schema/columns.schema.json](../datasets/data/_schema/columns.schema.json) (x-changelog v2.2 entry).
- **Tier-A tests**: `python -m yen_gov validate --root .` (G1). Expected chronic baseline of yen-gov (typically 5 errors, ~9.4k warnings); MUST NOT introduce a NEW error.
- **Tier-B impact**: contract test [frontend/src/contracts/datasets-conform.test.ts](../frontend/src/contracts/datasets-conform.test.ts) (vitest) validates that every published CSV's column shape matches the per-file-class entry in `columns.json`. The 4 added columns are declared on BOTH parliament + assembly candidacies file-classes, so AE candidacies CSVs (which do NOT yet carry the columns) MUST be rectangular — i.e., AE writers will need to either populate the 4 cells (as empty strings) on every row OR the contract test will fail. **Followup audit required**: confirm via G4 whether existing AE candidacies CSVs already pass column-shape after the columns.json bump or whether a one-line patch in the AE writer is needed. **See §7 open-question Q3 below.**

  Adapter pattern enforced (Fowler):
  - Extract Function on the three normalisers (pure, testable).
  - 4-pass deterministic join engine (Pass 1 = exact `(constituency, candidate)`; Pass 2 = exact `(AltSpelling, candidate)`; Pass 3 = alias-overlay sweep; Pass 4 = 1:1 single-winner-in-PC fallback). NO fuzzy matching. NO probabilistic thresholds. The 4 passes are deliberately layered so each pass has a one-line justification.
  - D2 / E1 abort discipline: if `unmatched_count > 0` after Pass 4, write `datasets/_ops/affidavit-2014-unmatched-YYYY-MM-DD.csv` and exit code 2. The adapter does NOT touch `candidacies.csv` or `source.csv` on abort (idempotent).

## 6. Acceptance gates

- [x] G1 `python -m yen_gov validate --root .` OK (chronic baseline — no NEW errors; receipt in PR body)
- [x] G2 `pytest -q backend/tests/test_canonical_myneta_lok_sabha_2014.py` green (16 tests: 11 normaliser units + 7 happy-path integration + 2 abort-on-unmatched)
- [ ] G3 `bun run check` (frontend) — SKIPPED per plan-doc (data-only PR; no frontend code change)
- [ ] G4 `bun run test` (vitest) — SKIPPED per plan-doc (data-only PR; the Tier-B contract test would catch any column-shape regression, but the §7-Q3 AE follow-up will exercise it explicitly)
- [ ] G5 `/state/topic` browser smoke per CLAUDE.md §13 — SKIPPED per plan-doc (no citizen UI in this PR; Row D adds the MP-panel surface)

**Adapter run receipt** (record from a fresh worktree-root run):

```
enrich-2014-ls-candidacies-with-affidavits:
  affidavit_count:  542
  winner_count:     543
  pass1_matched:    339
  pass2_matched:    31
  pass3_matched:    12
  pass4_matched:    160
  unmatched_count:  0
  source_id:        src-e9565084cbd1
OK
```

- 542 / 542 affidavit rows matched (unmatched_count == 0 per D2).
- 542 / 543 winners enriched (the 1 unenriched winner is Jamshedpur PC / BJP / BIDYUT BARAN MAHATO — publisher gap, NOT a join failure).
- Spot-oracle: 2014 ADILABAD winner (Godam Nagesh) shows `criminal_cases_declared=0`, `total_assets_inr=10,378,857`, `total_liabilities_inr=148,784`, `declared_election_expense_inr=2,215,311`.
- Spot-oracle: 2014 ARUKU winner (Kothapalli Geetha) — matched via Pass 3 PC-alias overlay; carries `processing_level='major'` and `processing_note='affidavit join: PC-alias overlay'`.
- Spot-oracle: 2014 MAHARAJGANJ (BIHAR) winner (JANARDAN SINGH \\SIGRIWAL\\) — matched on Pass 1 after backslash-strip normalisation; `criminal_cases_declared=4`.
- ECI source_id preserved on ALL 543 winner rows (verified: `winners with MyNeta source_id (should be 0): 0`).

## 7. Open questions

- **Q1 (Hans / Max)**: Should the FB-1 fold-back mint ONE aggregate indicator family (`criminal-cases-declared-share-of-mps`, normalised per state cohort, with 3 sibling pure-rupee facets) OR FOUR concept rows (one per declared column)? Side A approach (4 entity-attribute columns on candidacies) is already shipped here; Side B (catalogue rollups) is the FB-1 decision. Defer until Rows B + C land.
- **Q2 (Gregor)**: The `source_id` on the candidacies row is preserved as ECI per the binding 2026-06-15 ("dont try to change data already published"). The MyNeta source citation lives in `source.csv` + `columns.schema.json` changelog + this handover-doc. Should a future schema bump introduce a sidecar `affidavit_source_id` column to make the row-level linkage explicit? Defer — the out-of-band citation chain is sufficient for the citizen-correctness gate this PR was scoped to.
- **Q3 (Fowler, MUST resolve before merge)**: `columns.json` mirrors the 4 new cols onto the assembly candidacies file-class too, as forward-defensive scaffolding. AE writers currently do NOT populate the 4 cells. If any existing AE candidacies CSV is now non-rectangular relative to its declared file-class column list, the Tier-B `datasets-conform.test.ts` contract test will fail. Two options: (a) add a one-line patch to each AE writer to emit empty trailing cells (Fowler-cheap; preserves the forward-defensive intent); (b) DROP the AE mirror from `columns.json` and add it back only when the first AE adapter populates the 4 cols (Fowler-honest about YAGNI; preserves the binding "only declare schema where it is realised today"). The current default chosen is (a) plus a forward-defensive note in the changelog; reviewer may flip to (b) if the AE-emitter audit shows the patch is too noisy. The §13-MANDATORY browser smoke is NOT relevant here (data-only PR), so the contract-test result is the load-bearing acceptance signal.

## 8. References

- [TODO/20260614-three-ephemeral-ingests-plan.md](20260614-three-ephemeral-ingests-plan.md) §3 Row B
- [CLAUDE.md](../CLAUDE.md) §10 anti-pattern + §13 mandatory browser smoke
- [docs/agents/ingest-checklist.md](../docs/agents/ingest-checklist.md)
- [docs/concepts/pre-flight-ingest.md](../docs/concepts/pre-flight-ingest.md)
- [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md) grain over entity
- [ADR-0046](../docs/architecture/decisions/0046-pre-flight-ingest.md) pre-flight gate
- [docs/concepts/indicator-catalogue.md](../docs/concepts/indicator-catalogue.md) Side A vs Side B split (Max)
- User binding 2026-06-15: "your job is to enrich existing data — so take what split you can make and enrich it, dont try to change data already published"
