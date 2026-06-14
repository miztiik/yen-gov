# 2026-06-14 ECI MCC-period daily enforcement-seizures ingest handover (PR-A of plan TODO/20260614-three-ephemeral-ingests-plan.md)

**Last Updated**: 2026-06-14

> Per-event self-contained data ingest. PR-A of the 3-ingest plan-doc [20260614-three-ephemeral-ingests-plan.md](20260614-three-ephemeral-ingests-plan.md). Authors the new file-class `datasets/elections/parliament/election=*/mcc_seizures.csv` and emits the 2019 vintage (360 rows: 36 states/UTs x 10 dates).

## 1. Source

- **Publisher**: Election Commission of India (ECI). Press notes issued daily during the MCC period of a general election from the ECI Newsroom (https://www.eci.gov.in/issue-details-page/press-releases).
- **Vintage / cadence**: 2019 17th-LS general election. The 360 input rows span 29-Mar-2019 (start of MCC) through 07-Apr-2019. Publisher cadence: daily during MCC; future MCC vintages (2024, 2029) will append a new per-event CSV under `election=YYYY/`.
- **License**: Government of India open data (default). Publisher carries no explicit license stamp on the press notes; treat as `gov-publisher-open` per the citation ledger.
- **Sampling frame / methodology**: ECI consolidated state-level daily seizure totals reported by ECI flying squads, surveillance teams, and partner enforcement agencies (Income Tax, Excise, NCB, State Police) during the MCC enforcement window. The publisher itself reports the rounded totals; yen-gov preserves them verbatim (D3 'no derived totals').

## 2. Scope

- **Concept(s) measured**: Daily enforcement-seizure totals (cash, liquor qty + value, drugs/narcotics qty + value, precious metals qty + value, other items/freebies value, publisher TOTAL).
- **Unit canonical**: `INR_crore` for value columns; `lakh_litres` for liquor quantity; `kg` for drugs and precious metals quantity.
- **Normalisation**: `absolute` (publisher publishes nominal INR; we do NOT deflate).
- **Entity grain(s)**: `state` (one row per state/UT per date). NB: pre-2020-merger UTs (Dadra and Nagar Haveli, Daman and Diu) carry HISTORICAL slugs (`dadra-and-nagar-haveli`, `daman-and-diu`) since the 2019 publisher rows are historically distinct from the post-merger combined UT.
- **Time range**: 2019-03-29 through 2019-04-07 (10 days). The publisher's MCC window for the 17th LS GE.

## 3. Concept overlap audit (MANDATORY — guardrail #14 + ADR-0046)

- **Proposal**: [20260614-eci-mcc-seizures-2019-ingest-handover-proposal.json](20260614-eci-mcc-seizures-2019-ingest-handover-proposal.json)
- **Report**: [20260614-eci-mcc-seizures-2019-ingest-handover-preflight.json](20260614-eci-mcc-seizures-2019-ingest-handover-preflight.json)
- **Verdict**: `mint_new` (rationale: "no concept overlap >= 0.70; proceed with mint_new")
- **Target indicator_id** (if not `mint_new`): n/a (verdict is `mint_new`).
- **Exit code**: 1 (soft-warn).

**Soft-warn rationale documented (expected per plan-doc D1):**

The one warn is `concept_fk`: "proposal has no concept_id; mint_new requires a new row in datasets/taxonomy/concepts.json in the same PR". This warn is EXPECTED and intentionally NOT actioned in this PR because:

1. This ingest emits a **per-event self-contained CSV** (parallel to the per-event `candidacies.csv` / `summary.csv` already present under `parliament/election=*`), NOT a meadow-tier indicator that joins `datasets/data/datapoints/elections/*.csv`.
2. The plan-doc §0 D1 explicitly scopes this PR to per-event file emission; meadow-tier indicator minting for MCC seizures (and the matching concepts.json row) is deferred to a follow-up PR once D4 (UX design pass) settles whether the citizen-facing surface needs a long-format indicator or simply the per-event exhibit.
3. The remaining 5 checks all pass: `concept_overlap`, `grain_prefix`, `update_period_days`, `justification` (length 707), `source_id_derivation`.

**Verdict** (per concept):

- [x] `MCC-period daily enforcement-seizures press-note series` -> `mint_new` (per-event file, no indicator_id minted in this PR; soft-warn on `concept_fk` documented above).

## 4. Identifiers

- **`indicator_id`**: n/a — this PR adds a per-event file-class, not a meadow-tier indicator. The file lives at `datasets/elections/parliament/election=2019/mcc_seizures.csv`.
- **`concept_id`**: n/a in this PR (deferred per §3 soft-warn rationale).
- **`source_id`**: `src-f9f6b95cf429` (derived via `derive_source_id("Election Commission of India", "Press Note - Daily Enforcement Seizures during 17th Lok Sabha General Election (MCC)", "2019")`; appended at alphabetical anchor in `datasets/data/entities/source.csv`, no re-sort).
- **`update_period_days`**: 1825 (once per 5-year general-election cycle; the 2024 MCC vintage will land in a future PR).

## 5. Pipeline plan

- **Meadow tier**: n/a (per-event file pattern; the publisher's CSV lives at `datasets/ephemeral/2019_eci_seizures.csv` and is gitignored).
- **Canonical adapter**: [`backend/yen_gov/canonical/adapters/eci/mcc_seizures.py`](../backend/yen_gov/canonical/adapters/eci/mcc_seizures.py) (pure-function module exposing `ingest()`, `parse_eci_date()`, `parse_number_or_none()`, `strip_ut_suffix()`, `resolve_state_slug()`; reuses the bhukya-style `_load_state_index` pattern over `datasets/data/entities/state_codes.csv` plus a closed 4-entry `_PUBLISHER_STATE_REMAP` override for the 4 publisher names not covered by canonical lgd_name + alias resolution).
- **Schemas**: [`datasets/data/_schema/columns.schema.json`](../datasets/data/_schema/columns.schema.json) bumped `x-version` 2.0 -> 2.1 with x-changelog entry; [`datasets/data/_schema/columns.json`](../datasets/data/_schema/columns.json) bumped `$schema_version` 2.0 -> 2.1 and added the new file-class `datasets/elections/parliament/election=*/mcc_seizures.csv` with 13 columns (composite PK `(state_slug, date)` in that declaration order; `total_seizure_inr_crore` is NOT derived per D3; no FK on `state_slug` because pre-2020-merger UTs carry historical slugs that have no row in modern `state_codes.csv`).
- **CLI**: New Typer command `python -m yen_gov ingest-eci-mcc-seizures-2019 --root . --input <path-to-ephemeral-csv>` registered in [`backend/yen_gov/cli.py`](../backend/yen_gov/cli.py).
- **Tier-A tests**: [`backend/tests/test_canonical_eci_mcc_seizures.py`](../backend/tests/test_canonical_eci_mcc_seizures.py) (24 tests: 4 strip-UT, 5 date-parse, 4 number-parse, 8 resolve-slug, 2 remap-shape invariant, 1 end-to-end oracle skipped when ephemeral CSV absent).
- **Tier-B impact**: `python -m yen_gov validate --root .` exercises the column-contract validator on the new file-class; no new sub-validators added.

## 6. Acceptance gates

- [x] G1 `python -m yen_gov validate --root .` OK (delta=0 vs baseline; new file conforms)
- [x] G2 `pytest -q backend\tests\test_canonical_eci_mcc_seizures.py` 23 passed, 1 skipped (skip = end-to-end oracle when ephemeral CSV is absent, expected behavior in CI; manually verified locally - 360 rows, 36 states, 10 dates, bijection holds)
- [N/A] G3 `bun run check` — frontend touches none in PR-A
- [N/A] G4 `bun run test` — frontend touches none in PR-A
- [SKIP] G5 §13 browser smoke — data-only PR; UX surface lands in PR-D per plan-doc §5

## 7. Open questions

- For the 2024 vintage (future PR): the 17th LS press-note format is stable through 2024; confirm the 18th LS publishes the same 9-column shape before scheduling the next ingest.
- For the meadow-tier promotion (future PR): D4 in the plan-doc is "decide UX surface in PR-D" — if the citizen-facing presentation needs a long-format indicator for chart joins, mint one then with the matching `concepts.json` row (resolves the soft-warn carried in this PR).

## 8. References

- Plan-doc: [TODO/20260614-three-ephemeral-ingests-plan.md](20260614-three-ephemeral-ingests-plan.md) §2 (PR-A)
- [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md) grain over entity
- [ADR-0046](../docs/architecture/decisions/0046-pre-flight-ingest-gate.md) pre-flight ingest gate
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md)
- [csv-column-contract.md](../docs/architecture/data/csv-column-contract.md) §3.4 (per-event file pattern)
- User-memory lesson (2026-06-13, PR #1000): "State slug source-of-truth is `entities.json display_name`, NOT `state_iso_seed.csv`" — for THIS data-tier PR the slug source is `state_codes.csv.lgd_name` (canonical LGD spine) plus a 4-entry remap for the publisher's pre-2020 + non-canonical names.
