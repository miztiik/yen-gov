# Health

> Topic spine for the (retired) `health/` indicator family.

**Last Updated**: 2026-05-26
**Status**: RETIRED — see [docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md](../../../docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md) §D6.

## Retirement note (PR-D6)

The 6 legacy `health/*` shards were retired in PR-D6:

- `health/state_birth_rate_per_1000` (SRS)
- `health/state_death_rate_per_1000` (SRS)
- `health/state_infant_mortality_rate_per_1000` (SRS)
- `health/state_total_fertility_rate` (SRS)
- `health/state_public_health_expenditure_inr_crore` (RBI HBS Table 18)
- `health/state_health_expenditure_pct_total_expenditure` (RBI Statement 27)

Reasons:

- All four SRS vital-rate series end at CY2023 with the SRS publication cycle paused; no canonical successor planned.
- RBI Statement 27 had a dedicated single-table ingest path with no canonical schema home; reading-priority deferred.
- The full health-system corpus (NFHS, HMIS, PM-JAY, IDSP, immunisation coverage) was never ingested. Retiring the thin vital-rate ledger collapses the family to a clean structural placeholder until a real canonical health adapter lands.

## Re-ingestion plan

A canonical health adapter (SRS resumption + NHM dashboard + Ayushman Bharat) is queued behind the canonical pivot; flag for Hans review when the first canonical health artifact arrives. See [TODO/20260515-health-ingest-handover.md](../../../TODO/20260515-health-ingest-handover.md) for the prior source recon (SUPERSEDED).
