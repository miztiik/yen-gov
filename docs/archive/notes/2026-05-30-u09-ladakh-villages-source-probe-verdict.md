# U09 Ladakh villages source probe verdict

**Last Updated**: 2026-05-30

**Cited by**: [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md) Row 5.5.

**Predecessor**: PR #453 (C.4.a) shipped 14 J&K (U08) village shards via `Bhuvan_JK_Villages`; U09 Ladakh deferred indefinitely. This probe re-evaluates upstream candidates.

---

## section 1. Candidate sources surveyed

Per [ramSeraph/indian_admin_boundaries releases](https://github.com/ramSeraph/indian_admin_boundaries/releases) (the canonical mirror of Indian government boundary data):

| Source | Coverage of U09 Ladakh | Vintage | License | Verdict |
| --- | --- | --- | --- | --- |
| `LGD_Villages.geojsonl.7z` | NOT included (release notes: missing HP, J&K, Sikkim, Meghalaya, Mizoram, Manipur, Nagaland, Arunachal Pradesh; Ladakh is implicit-under-J&K = also absent) | post-2014 | CC0 + attrib | NOT viable |
| `bhuvan_villages.geojsonl.7z` (NRSC national) | National layer but does not enumerate Ladakh-as-UT (predates 2019 split) | pre-2019 | CC0 + attrib | NOT viable |
| `Bhuvan_JK_Villages.geojsonl.7z` | U08 J&K only (used in PR #453 for 12 districts); explicitly excludes Ladakh | Census-2011 vintage | CC0 + attrib | NOT viable for U09 |
| `SOI_villages.geojsonl.7z` | "Incomplete, missing quite a few states and districts" per release notes | unspecified | CC0 + attrib | UNLIKELY viable |
| `Census_Villages.geojsonl.7z` | National POINTS (centroids), not polygons | Census 2011 | CC0 + attrib | Wrong geometry type |
| `SOI_VILLAGE_POINT.geojsonl.7z` | POINTS, plus "Missing data for a large swath around Bihar, Jharkhand, UP, MP, Chhattisgarh" | unspecified | CC0 + attrib | Wrong geometry type |
| `shrug-village-pc11.geojsonl.7z` (SHRUG Census 2011) | National POLYGONS including pre-split Ladakh districts | Census 2011 | **CC-BY-NC-SA 4.0** (non-commercial) | License concern + vintage |
| Bhuvan portal direct query | Not enumerated in ramSeraph; not yet probed at https://bhuvan.nrsc.gov.in/ | unknown | unknown | UNVERIFIED |
| MoRD SVAMITVA portal | Property-centroid data, not polygons | post-2020 | unknown | Wrong geometry type |

## section 2. Verdict: NO viable source for modern U09 Ladakh village polygons

The closest match — SHRUG Census 2011 polygons — carries:
1. **Wrong vintage**: pre-2019 Ladakh territories are nested under "Jammu & Kashmir"; modern U09 = Leh + Kargil districts post-bifurcation. Reassignment would require hand-curated mapping of pre-split Census districts to modern Ladakh administrative divisions.
2. **License concern**: CC-BY-NC-SA 4.0 (non-commercial) does not match yen-gov's CC0 / CC-BY default; would require explicit non-commercial-only attribution + downstream licensing constraints.

`Bhuvan_JK_Villages` (which PR #453 used for U08) explicitly EXCLUDES Ladakh per its source-of-truth Bhuvan portal upload.

No other public source ships Ladakh village polygons today.

## section 3. Path verdict

| Path | Verdict |
| --- | --- |
| A (Bhuvan direct portal probe) | UNVERIFIED. Would need manual Bhuvan portal login + navigation; ramSeraph mirror would surface it if available. Low confidence of payoff. |
| B (SVAMITVA portal) | Wrong geometry type (property centroids, not polygons). NOT viable. |
| C (Census 2011 SHRUG + hand-curated reassignment) | Possible but requires (a) NC license acceptance, (b) hand-curated pre-2019->post-2019 district mapping (~200-300 villages reassigned), (c) prominent vintage-mismatch citizen caveat. UNDESIRABLE engineering + licensing tradeoff. |
| **D (defer + document)** | **RECOMMENDED**. Document U09 villages as a known coverage gap in [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md). Reclassify Row 5.5 from "BLOCKED on upstream" to "BLOCKED on citizen-trigger AND upstream". |

## section 4. Recommendation

**Adopt Path D**. Update Row 5.5 status. The unblock trigger becomes BOTH:
- An upstream-quality polygon source for modern U09 Ladakh emerges (Bhuvan-Ladakh-specific release; LGD coverage expansion; or independent civic source), AND
- A citizen indicator demands village-grain rendering for Ladakh specifically.

Until both fire, U09 stays at the higher-grain (district / UT) level on `/s/ladakh`.

## section 5. Updates to plan-doc Row 5.5

After this PR merges:

- Row 5.5 reclassified from `PENDING-actionable` to `BLOCKED-on-upstream-AND-citizen-trigger`.
- Cite THIS probe verdict.
- Row count unchanged at 36 (this PR adds Row 4.9 PENDING -> DONE).

---

## See also

- [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md) - Row 5.5.
- [TODO/20260530-boundary-plan-followups.md](../TODO/20260530-boundary-plan-followups.md) Category 1 - per-row rationale.
- [notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md](2026-05-30-c4-jk-villages-source-hunt-verdict.md) - C.4 verdict (PR #453); explicit "Out of scope" for Ladakh.
- [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) - 3-convention rule + Bhuvan/LGD/ramSeraph lineage.
