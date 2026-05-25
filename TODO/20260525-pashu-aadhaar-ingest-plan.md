# Pashu Aadhaar ingest — handover plan

**Last Updated**: 2026-05-25
**Status**: ◻ QUEUED — depends on Phase 0 of the livestock umbrella plan ([TODO/20260525-livestock-ndlm-ingest-plan.md](20260525-livestock-ndlm-ingest-plan.md)).
**Parent**: [livestock NDLM ingest plan](20260525-livestock-ndlm-ingest-plan.md). This is Phase 1.B + Phase 2.B of that plan, carved out as its own doc because Pashu Aadhaar is **citizen-misreading-prone** and warrants a focused Hans framing pass.
**Doc-class routing**: **plan-doc** per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md).
**Personas**: Hans (Governance — the honest-renderer call); Max (Indicator Scout — slug + comparability); Gregor (Architect — meadow path); Fowler (engineering craft).

---

## 1. Why this is special — the misreading risk

Pashu Aadhaar is a **12-digit Unique ID issued to a livestock animal** under the Centre's National Digital Livestock Mission (NDLM). The Bharat Pashudhan portal exposes per-district counts of UIDs-issued-to-date, faceted by species (Cattle, Buffalo, Sheep, Goat, Pig, Mithun, Yak, Equine) and gender.

**The trap**: a citizen reads "Maharashtra: 47 lakh Pashu Aadhaars issued" as "Maharashtra has 47 lakh cattle / buffaloes / etc." This is wrong on two counts:

1. **Tagged != population**. Many tagged animals have died; NDLM has no de-registration workflow today. The count grows monotonically with enrolment effort; never shrinks with mortality.
2. **Coverage is uneven across districts**. Programme priority districts (Operation Greens, RGM-priority breeds) get aggressive tagging campaigns; remote / non-priority districts may have <10% coverage. Ranking states by raw count rewards enrolment-machine throughput, not livestock density.

Rosling-trap candidate: ranking a UID-issuance ledger by state could let a citizen-reader conclude UP has more cows than Maharashtra when it might just have more enrolment effort.

## 2. Hans framing call — honest-renderer

**Verdict** (Hans's reading per Max's open question, pinned 2026-05-25):

| Field | Value | Why |
| --- | --- | --- |
| `comparability` | `directional_only` (4-level ladder, [indicator-naming.md](../docs/concepts/indicator-naming.md) §10.1) | Cross-state ranking would mislead until DAHD publishes a denormaliser (target population). Trend within a state is honest (it's the same tagging programme over time); cross-state rank is not. |
| `renderer_rules` | `["no_rank_table"]` (controlled vocabulary per [indicator-naming.md](../docs/concepts/indicator-naming.md) §10.2) | Refuse the ranked-states-by-Pashu-Aadhaar table outright. Choropleth is acceptable IF accompanied by the caveat below; bar-chart-by-state is not. |
| `excludes` (v1.5 field) | `["Animals not yet tagged (programme coverage is uneven across districts)", "Tagged animals that have died (no de-registration workflow today)"]` | Citizen-readable; surfaces under the chart. |
| `notes` | "Pashu Aadhaar is a UID-issuance ledger, not a livestock census. The count is monotone-growing with enrolment effort. Use within-state-over-time for honest reading; the bar-chart-by-state view is intentionally suppressed." | Footnote on the artifact. |
| Citizen title | `Animals issued Pashu Aadhaar (count)` | NOT `Livestock population` — Max's slug honours this. |
| `description` | "Cumulative count of livestock animals issued a 12-digit Pashu Aadhaar unique ID under the National Digital Livestock Mission. Reported per state and per district. The count includes animals that have since died (NDLM has no de-registration today) and excludes animals not yet tagged — programme coverage is uneven across districts." | 1-3 sentences per [indicator-naming.md](../docs/concepts/indicator-naming.md) §5.2. |

## 3. The 2 indicator IDs

| # | indicator_id | grain | facet |
| --- | --- | --- | --- |
| 3 | `agriculture/state_pashu_aadhaar_animals_tagged_count` | state | species x gender |
| 4 | `agriculture/district_pashu_aadhaar_animals_tagged_count` | district | species x gender |

Both lift into `datasets/livestock/livestock_pashu_aadhaar.parquet` (single fact table — same row contract per Hans's 4-rule fact-table split in the parent plan §5.3).

## 4. Source citation

| Field | Value |
| --- | --- |
| Producer | `Department of Animal Husbandry and Dairying, Ministry of Fisheries, Animal Husbandry and Dairying, Government of India` |
| Title | `Bharat Pashudhan — Pashu Aadhaar Animal Registrations — District-wise` |
| Vintage | per (year, CY/FY) tuple — e.g. `"2024"` or `"2024-25"` |
| License | `OGL-IN-1.0` (verify against portal footer in Phase 1.B PR) |
| URL | `https://bharatpashudhan.ndlm.co.in/keyStatistics` (portal) and `https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/getAnimalRegistrationDistrictWise` (machine endpoint) |
| Derivation | `derive_source_id("Department of...", "Bharat Pashudhan — Pashu Aadhaar...", "2024-25")` per [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) |

## 5. NDLM endpoint shape (verified 2026-05-25)

`POST https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/getAnimalRegistrationDistrictWise`
Body: `{"isYearFinancial": false, "year": 2024, "stateCd": <LGD>}`

Response (TN 2024 CY example, abbreviated):

```json
{
  "flg": true,
  "data": {
    "totalCount": 1213753,
    "totalMaleCount": 67288,
    "totalFemaleCount": 1146465,
    "totalOutput": {
      "576": {
        "code": 576, "name": "KARUR",
        "maleCount": 358, "femaleCount": 33565, "total": 33923,
        "details": {
          "1": {"speciesCd": 1, "speciesName": "Cattle",  "maleCount": 173, "femaleCount": 29804, "total": 29977},
          "2": {"speciesCd": 2, "speciesName": "Buffalo", "maleCount": 10,  "femaleCount": 3516,  "total": 3526},
          "5": {"speciesCd": 5, "speciesName": "Sheep",   ...},
          "6": {"speciesCd": 6, "speciesName": "Goat",    ...},
          "7": {...}
        }
      },
      "577": {...},
      ...
    }
  }
}
```

**Facet enumeration** (verified species codes from TN probe):

| speciesCd | speciesName |
| --- | --- |
| 1 | Cattle |
| 2 | Buffalo |
| 5 | Sheep |
| 6 | Goat |
| 7+ | Pig / Mithun / Yak / Equine (probe other states to confirm full set in Phase 1.B PR) |

NDLM's `code` is the LGD MoHA district code (recon: 588/588 districts resolve — see [parent plan §7](20260525-livestock-ndlm-ingest-plan.md#7-lgd-district-recon-result-gregors-1-risk-foreclosed)).

## 6. Meadow shape

`datasets/livestock/_meadow/ndlm/<vintage>/animal_registration_district.json`:

```json
{
  "$schema_version": "1.0",
  "source_id": "src-XXXXXXXXXXXX",
  "rows": [
    {"entity_id": "IN-S33-D576", "time": "<vintage>", "facet": {"speciesCd": 1, "speciesName": "Cattle", "gender": "F"}, "value": 29804},
    {"entity_id": "IN-S33-D576", "time": "<vintage>", "facet": {"speciesCd": 1, "speciesName": "Cattle", "gender": "M"}, "value": 173},
    ...
  ]
}
```

(`entity_id` shape `IN-S<S>-D<lgd_district>` per [canonical-store.md §3a](../docs/architecture/data/canonical-store.md). Confirm prefix convention against the PR #267 district backfill in Phase 1.B PR — may be `IN-D<lgd>` flat instead.)

## 7. Tier-A tests

| # | Symbol | Asserts | Lands in |
| --- | --- | --- | --- |
| 1 | `pashu_aadhaar_facet_axis_enum_closure` | Every row's `facet.speciesCd` is in the enumerated species axis (defined in `facet_axes_seed.py`). Catches an upstream species expansion before it FK-drops. | Phase 1.B PR |
| 2 | `pashu_aadhaar_indicator_comparability_directional_only` | `taxonomy/indicators.parquet` rows for indicators 3 + 4 have `comparability == 'directional_only'` AND `renderer_rules` contains `'no_rank_table'`. Hard-fails if a future PR weakens the honesty contract. | Phase 2.B PR |
| 3 | `pashu_aadhaar_excludes_non_empty` | Both indicators' `excludes[]` is non-empty (carries the "tagged != population" caveat). | Phase 2.B PR |

## 8. Acceptance criteria — Phase 2.B done means

- [ ] 2 indicator rows added to `datasets/taxonomy/indicators.json` honouring §2 honest-renderer fields.
- [ ] `datasets/livestock/livestock_pashu_aadhaar.parquet` written by `backend/yen_gov/canonical/adapters/livestock/pashu_aadhaar.py`.
- [ ] Tier-A tests 1-3 green.
- [ ] §13 browser smoke on `/i/agriculture/state_pashu_aadhaar_animals_tagged_count`:
  - Renders trend line (within-state-over-time).
  - Renders choropleth WITH the citizen-readable caveat under it.
  - Does NOT render a ranked-states bar chart (renderer honours `no_rank_table`).
  - Footer surfaces the `excludes[]` text.
- [ ] PR body cites Hans's framing verdict (this doc §2) verbatim.

## 9. Out of scope

- ABIP / RGM / NADCP — separate sub-PRs (see parent plan §9 Phase 1.D + 1.E).
- A denormalised "tagging coverage %" indicator (numerator = tagged, denominator = livestock census population). Needs a separate target-population data source (DAHD Livestock Census 2019). **Queued — not Phase 2.B.**
- TopoJSON adoption (separate plan: [TODO/20260525-topojson-frontend-perf-plan.md](20260525-topojson-frontend-perf-plan.md)).
