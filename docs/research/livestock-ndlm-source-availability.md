# Livestock NDLM source availability — NADCP + Breeding upstream gaps

**Last Updated**: 2026-05-26
**Status**: active

This note records the empirical evidence behind two CLOSED Phase rows in [TODO/20260525-livestock-ndlm-ingest-plan.md](../../TODO/20260525-livestock-ndlm-ingest-plan.md) §11: NADCP (1.D + 2.D) and Breeding (1.E + 2.E). Both upstream-publisher gaps are confirmed exhaustively; both indicator families remain UNFILLED on `/t/agriculture` until DAHD publishes the data. The companion how-to recipe is [docs/how-to/ndlm-data-download.md](../how-to/ndlm-data-download.md).

## Question

For each of the 16 livestock indicators listed in the plan-doc §3, is the NDLM publisher (`https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/`) currently serving non-empty district-grain data? Specifically:

1. **NADCP** (indicator-ids 5 + 6 — animal vaccinations, FMD + Brucellosis): does `getNADCPVaccinationDistrictWise` return non-zero `totalOutput` for any combination of `(stateCd, year, isYearFinancial, diseaseCd, roundNumber, isRoundWise)`?
2. **Breeding** (indicator-ids 7 + 8 — ABIP + RGM interventions): does any per-state endpoint exist on the NDLM API at all?

## Candidates evaluated

| Source | URL | Coverage probed | Result | Verdict |
| --- | --- | --- | --- | --- |
| NDLM `getNADCPVaccinationDistrictWise` | `https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/getNADCPVaccinationDistrictWise` | 32 vintages (CY 2010-2025 + FY 2010-11..2025-26) × 36 states × `diseaseCd in {1, 2}` × `roundNumber: null, isRoundWise: false` = 1152 cells | Every cell returns `{flg: true, data: {totalVaccinations: 0, totalFarmerBenefitted: 0, totalOutput: {}}}` (130 bytes) | EMPTY across full publisher history |
| NDLM `getNADCPVaccinationDistrictWise` with round-wise params | Same endpoint | TN/33 FY2024-25, `diseaseCd in {1, 2}` × `roundNumber in {1..6}` × `isRoundWise: true` = 12 cells (60-cell pre-bulk probe by prior session) | All return empty `totalOutput` (or HTTP 400 on some round-wise variants); silent server-side validation accepts even `diseaseCd: 99` and returns 0 rows | EMPTY regardless of round / disease params |
| NDLM endpoint-name fuzzing | 20+ NADCP name variations (`getNADCPStateWise`, `getNADCPHeaderCount`, `getFMDVaccinationDistrictWise`, `getBrucellosisVaccinationDistrictWise`, `getNADCPRoundWise`, etc.) | All TN/33 FY2024-25 | HTTP 404 on every variant | No alternate NADCP endpoint exists on the API gateway |
| NDLM Breeding endpoint-name fuzzing | 14 ABIP / RGM / Rashtriya Gokul Mission variants on `/epashu/v1/homepage/` | All TN/33 FY2024-25 | HTTP 404 on every variant | No per-state Breeding API endpoint exists |
| NDLM Swagger / OpenAPI | `swagger.json`, `swagger-ui.html`, `openapi.json` under several paths | n/a | HTTP 404 on every path | No machine-readable schema; cannot enumerate hidden endpoints |
| Bharat Pashudhan SPA frontend recon | `https://bharatpashudhan.gov.in/dashboard` | n/a (static fetch) | SPA hydrates client-side; no inline NADCP endpoint reference; portal HTTP 504 sporadically | Inconclusive on UI behaviour; user-side DevTools capture would be definitive |
| data.gov.in | Search queries: `nadcp`, `foot and mouth disease`, `brucellosis`, `animal vaccination`, `livestock vaccination`, `animal disease control` | 6 searches | Zero NADCP datasets across all queries; DAHD catalogue page also returns "Record not found" | No OGD-platform NADCP data |
| DAHD official portal | `https://dahd.gov.in/` | Annual Reports + Publications + Dashboards sections | JS-heavy; no static-fetch path to Annual Report PDFs; `/documents/annual-reports` 404 | Annual Reports may contain state-grain NADCP tables but require browser-based extraction (Tier 3 PDF-scrape, NOT in this sprint scope) |
| PIB (Press Information Bureau) | `pib.gov.in` search for "NADCP" | n/a | Search engine returned zero specific NADCP releases | National-aggregate press snippets only, not state-grain time-series |
| GitHub civic-tech mirrors | Searches for "NADCP", "bharatpashudhan", "FMD vaccination india" | 0 livestock-health repos | Empty | No civic-tech scrapers have already extracted the data |

## Decision

**NADCP** — CLOSED as TRUE GAP on NDLM publisher. The 1152-cell bulk probe (the entire publisher vintage range) is definitive: NDLM serves no NADCP vaccination data via any discoverable endpoint as of 2026-05-26. Indicators `agriculture/state_livestock_vaccinations_administered_count` + `agriculture/district_livestock_vaccinations_administered_count` (plan §3 rows 5-6) remain CATALOGUE-DECLARED + UNFILLED on `/t/agriculture` until a viable upstream emerges. Honest-renderer signalling on the topic page is appropriate (do not render a zero choropleth; render an "upstream not yet publishing" placeholder).

**Breeding** — CLOSED as NO PUBLIC API on NDLM publisher. 14-endpoint probe confirms NDLM exposes neither per-state nor per-district Breeding endpoints. Indicators `agriculture/state_livestock_breeding_interventions_count` + `agriculture/district_livestock_breeding_interventions_count` (plan §3 rows 7-8) remain CATALOGUE-DECLARED + UNFILLED. DAHD / NDDB direct outreach (or PDF Annual Report extraction) is the only remaining path.

**Re-evaluation cadence**: annually, on the date stamp above. The NDLM API is healthy for 3 of 4 livestock endpoints (Owner Reg, Pashu Aadhaar, NAIP IV all return real district data at scale) so the gap is dataset-specific, not infrastructure-wide; DAHD may activate the missing endpoints in a future portal release.

## Open follow-ups

1. **Tier 3 — DAHD Annual Report PDF scrape**: state-grain NADCP coverage tables historically appear in DAHD Annual Reports (typically chapter on Animal Health). Requires browser session to navigate `dahd.gov.in` (static fetch blocked by JS) + PDF table extraction. Useful if the renderer needs ANY historical NADCP numbers; not required for the citizen-honest empty-state.
2. **DevTools capture of NDLM SPA**: user-side Chrome DevTools Network panel inspection on `https://bharatpashudhan.gov.in/` could reveal whether the live UI hits a different NADCP endpoint behind an auth header. 5-minute task for a human; not feasible from headless tool environment.
3. **RTI request to DAHD**: formal Right-to-Information request for state-wise annual FMD + Brucellosis vaccination tables 2019-2025. Typical response: 45 days. Triggers if Tier 3 PDF scrape returns insufficient detail.
4. **DAHD / NDDB outreach for Breeding**: ABIP + RGM both publish official annual reports; PDF tabular data exists but is not API-served. Same Tier 3 path as NADCP.

## References

- `tools/ndlm_download.py` (commit `<this PR>`): bulk downloader; the 32-vintage VINTAGE_BODIES sweep ships the empirical evidence for the NADCP TRUE-GAP verdict. Runs in ~25 min on a clean cache.
- `.runtime/raw/ndlm/_summary.json` (ephemeral, gitignored): `total_calls=4608, fetched=4519, skipped=78, failures=11, total_bytes=18360413`. Every NADCP row has `districts: 0, bytes: 130`.
- [docs/how-to/ndlm-data-download.md](../how-to/ndlm-data-download.md) — the recipe that produced the snapshots.
- [TODO/20260525-livestock-ndlm-ingest-plan.md](../../TODO/20260525-livestock-ndlm-ingest-plan.md) §11 — status table referencing this note for the CLOSED rows.
- DAHD authoritative NADCP scheme page (visited 2026-05-25): `https://dahd.gov.in/schemes/programmes/nadcp` — confirms scheme covers exactly FMD + Brucellosis; does NOT publish data.
- ADR-0032 (sources citation ledger, FROZEN 5-row seed): the two reserved-unused seed rows (`ndlm_nadcp_vaccination`, `ndlm_breeding_*`) stay reserved until upstream resolves.
- ADR-0041 (meadow tier): governs the ephemeral `.runtime/raw/ndlm/` snapshot location.
