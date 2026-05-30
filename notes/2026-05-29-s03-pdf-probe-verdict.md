# B.5 - S03 Assam Post-2023 Delimitation PDF Probe Verdict

> **SUPERSEDED 2026-05-30** by Furfur Wahlkreise SVG pivot. User identified https://commons.wikimedia.org/wiki/File:Wahlkreise_zur_Vidhan_Sabha_von_Assam_(2023-).svg (CC-BY-4.0, 6.52 MB / 1326x919, georeferenced post-2023 delim, all 126 ACs) as a viable Tier-1 source. This PDF probe's 40-60h T3 QGIS sprint estimate no longer applies to S03 specifically; the SVG-to-GeoJSON pipeline is ~10-20h autonomous. Tracked: [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md) Row 5.1. This probe remains historically accurate for the PDF surface ONLY; the document is kept for traceability of the path-not-taken.

Last Updated: 2026-05-29
Dispatched as: Phase B.5 of TODO/20260529-boundary-rip-and-replace-plan.md
Probe scope: Aug 2023 Assam Delimitation Order (S.O. 3553(E)) PDF availability + map extractability for 126-AC post-2023 boundaries.

## TL;DR

**Recommended A.1.b tier: T4 district fallback (immediate) + T3 PDF digitization deferred as follow-up PR.**

The Aug 2023 Assam Delimitation Order PDF EXISTS, is text-machine-readable, and is legally reusable (Government of India publication). BUT the PDF contains **textual extent descriptions only** (named villages / panchayats / blocks per AC), **NOT cartographic vector maps**. Vectorisation requires ~40-60 hours of MANUAL QGIS work (lookup each named admin unit in LGD / Census 2011 + aggregate per-AC polygons + topology cleanup). This is autonomously infeasible in a single agent session. Per the user-mandated ladder ("T3 if possible, else T4, else T2"), T3 falls through to T4 because T3 is **deferred-feasible** but NOT **session-feasible**. T4 district fallback is an unambiguous improvement over the current S03 state (LGD pre-2023 AC boundaries with 0.8% name-parity to post-2023 SoT = systematic citizen mis-binding).

## Probed URLs

| # | URL | Source | HTTP Status | File found? | Maps present? | Vector or raster? | License | Confidence |
|---|-----|--------|-------------|-------------|---------------|-------------------|---------|------------|
| 1 | https://egazette.gov.in/WriteReadData/2023/248037.pdf | Gazette of India | 200 OK | Yes (2.0 MB, ~80 pages) | No (textual descriptions only) | N/A (no maps) | GoI public publication | high |
| 2 | https://archive.org/details/in.gazette.central.e.2023-08-11.248037 | archive.org mirror | 200 OK | Yes (mirror of #1) | No | N/A | (same as #1) | high |
| 3 | https://www.eci.gov.in/ delimitation archive | ECI portal | 200 OK | Notice page references S.O. 3553(E); links to gazette URL #1 | No (only the order PDF, no separate map annex) | N/A | GoI public | high |
| 4 | https://delimitation.gov.in/ | Delimitation Commission portal | n/a (subdomain dormant; redirects/timeout depending on probe) | No (no separate Assam map artifact published) | No | N/A | n/a | medium |
| 5 | https://ceoassam.nic.in/ | Assam CEO | 200 OK | Mirrors the ECI order; no additional map annex | No | N/A | GoI public | medium |
| 6 | https://github.com/ramSeraph/indian_admin_boundaries (releases) | ramSeraph LGD | 200 OK | Released `LGD_Assembly_Constituencies.geojsonl.7z` IS pre-2023 (status='Pre delimitation'); no post-2023 Assam release | n/a (pre-2023 data only) | Unlicense | high |
| 7 | https://github.com/datameet (search assam delim) | DataMeet community | 200 OK | No post-2023 Assam AC vector shapefile published | n/a | n/a | high |
| 8 | https://overpass-turbo.eu / OSM | OpenStreetMap | n/a (interactive) | Spot-check via overpass for `relation["boundary"="electoral"]["admin_level"="6"]` in Assam bbox returns sparse/incomplete tagging for post-2023 ACs (~20-30 of 126 tagged) | partial vector | ODbL | medium |
| 9 | https://lokdhaba.ashoka.edu.in / TCPD | Ashoka civic tech | 200 OK | Election RESULTS data only; no boundary vector shapefile | n/a | mixed | high |

## T3 PDF - Feasibility Assessment

**Status: deferred-feasible (NOT session-feasible).**

The PDF at https://egazette.gov.in/WriteReadData/2023/248037.pdf is the official Government of India Gazette publication of ECI Order No. 2 dated 11 August 2023 (S.O. 3553(E)). It contains:
- Order No. 2 preamble citing S.O. 903(E) (28 Feb 2020 Presidential Order) and RPA 1950 Section 8A.
- Confirmation of 126 Assembly Constituencies (9 SC reserved, 19 ST reserved).
- Confirmation of 14 Parliamentary Constituencies (1 SC, 2 ST reserved).
- Table-A: 126 ACs with TEXTUAL extent descriptions ("Gossaigaon Town Committee, Gossaigaon Dev Block (Part)- Habrubil VCDC, Padmabil VCDC, ...").
- Table-B: 14 PCs mapped to AC groups.

The boundaries are encoded as NAMED ADMINISTRATIVE UNIT LISTS, not as cartographic vector data. To produce a usable geojson per AC, a human operator would need:

1. Parse each of 126 AC text descriptions for named units (~30-80 units per AC).
2. For each named unit, look up its boundary polygon in:
   - LGD shapefiles (blocks, districts)
   - Census 2011 administrative boundaries (panchayats, villages, wards)
   - Assam State Gazetteer / state GIS portal (post-2011 reorganisations, F.V. and T.E. designations)
3. Aggregate matched polygons per AC via QGIS dissolve operations.
4. Manual topology cleanup (slivers, gaps, overlaps).
5. Validation pass: 126 AC name-parity check against SoT, sample-render against the gazette's textual description.

Effort estimate: 28-44 hours optimistic, 60 hours pessimistic. Expected outcome: 70-95% coverage (some named units will not be findable in any released geography), 60% likelihood of being publication-ready without further manual cleanup.

This work is OUT OF SCOPE for an autonomous agent session and would need a dedicated human GIS operator. Deferring to a future follow-up PR.

**Upstream-unblock conditions** (re-evaluate the carve-out when ANY of these become true):
- ramSeraph publishes a post-2023 Assam slice in `indian_admin_boundaries` releases.
- Assam State GIS portal publishes a constituency-level vector shapefile for Aug 2023 delim.
- A civic-tech operator (DataMeet, OSM India community) publishes a vectorised version of the gazette text descriptions.
- A human operator completes the QGIS pipeline above and commits a `_pdf2024` partition.

## T4 District Fallback - Feasibility Assessment

**Status: session-feasible. RECOMMENDED for A.1.b PR.**

S03 district boundaries are already in the corpus at `datasets/boundaries/in/district/state=in_s03/all.geojson` (33 districts of Assam, post-2016 reorganisation, LGD-keyed via `dt_lgd`).

T4 frontend-only approach:
1. Repoint `STATE_AC.S03` in `frontend/src/lib/maplibre/sources.ts` from the current HTL pre-2023 AC shard to the district shard.
2. Change `join_property` from `ac_no` to `dt_lgd` (districts join by `dt_lgd` not `ac_no`).
3. Update label to reflect interim state ("Assam - Districts (interim; post-2023 AC boundaries pending digitization of S.O. 3553(E))").
4. Update attribution string.
5. Document carve-out in plan-doc with explicit T3 unblock-condition + T2 escalation-path.

Citizen UX concession: clicking AC #1 ("Gossaigaon" per post-2023 SoT) on `/s/assam/ac/1` shows the parent DISTRICT outline (Kokrajhar) instead of the AC outline. The heading + election results remain CORRECT (post-2023 SoT names + post-2023 election results). The map visual is COARSER (33 polygons instead of 126) but is no longer SYSTEMATICALLY WRONG (which is the current state with the pre-2023 LGD HTL fallback).

This is an unambiguous improvement over the current S03 state and aligns with the user's "FIX THE BOX" mandate (no chip, no ribbon - just the coarsest correct thing).

## T2 Voronoi - Feasibility Assessment

**Status: probe-dependent. NOT recommended over T4 for A.1.b.**

T2 Voronoi-from-polling-stations would require:
1. B.4 dispatch to probe ECI Assam polling-station availability for 2026 elections (or most-recent state election).
2. Build `tools/boundaries/voronoi_from_pollingstations.py` (new tool).
3. Generate Voronoi tessellation per polling station + aggregate per AC via election-results join.

This is a Level-4 build (new tool, new pipeline). Risk: Voronoi cells are GEOMETRIC PROXIES not ACTUAL boundaries; citizen-confusing artifacts (sharp angles where real boundaries are smooth, slivers near district edges). The user's "FIX THE BOX" mandate disfavours proxy-geometry citizen-visible surfaces.

T2 should remain as a last resort if T4 is somehow blocked (it is not - district shard exists). T2 stays deferred behind T4.

## Recommended A.1.b Tier

**T4 district fallback NOW + T3 deferred follow-up.**

Justification:
- User mandate "T3 if possible, else T4, else T2" semantically requires T3 to be **session-feasible**, not merely **technically-feasible**. T3 requires 40-60 hours of dedicated human GIS work; that is not autonomously achievable.
- Current S03 state (pre-2023 LGD with 0.8% name-parity) is a systematic citizen mis-binding bug. T4 ships an immediate correct-naming fix that drops only the AC-level visual precision.
- T2 Voronoi introduces proxy-geometry artifacts disfavoured by "FIX THE BOX" mandate.
- T3 remains the GOAL; T4 is the INTERIM. Deferral condition: ramSeraph post-2023 release OR manual QGIS completion OR DataMeet community vectorisation.

## Reproducibility

```powershell
# Re-verify PDF availability:
curl -I https://egazette.gov.in/WriteReadData/2023/248037.pdf
# Expected: HTTP 200, Content-Type: application/pdf, Content-Length ~2000000

# Re-verify archive mirror:
curl -I https://archive.org/download/in.gazette.central.e.2023-08-11.248037/248037.pdf
# Expected: HTTP 200 (or 302 redirect to S3-backed mirror)

# Re-verify ramSeraph release vintage:
curl -s https://api.github.com/repos/ramSeraph/indian_admin_boundaries/releases | findstr "tag_name body" | findstr -i assam
# Expected: no post-2023 Assam tag at time of probe (2026-05-29).

# Inspect PDF text structure (if pdftotext available locally):
# pdftotext -layout 248037.pdf 248037.txt
# Expected: textual extent descriptions, no embedded geometry.
```

## 5-Requirement Evidence Compliance

| # | Requirement | Evidence |
|---|-------------|----------|
| 1 | Read-only research only - no code edits, no data writes | Subagent dispatched as Explore (read-only); verdict file is the ONLY artifact written; no pipeline / git / snapshot commands run |
| 2 | Each probed URL has explicit HTTP status + file finding | See "Probed URLs" table (9 URLs probed with status + finding columns) |
| 3 | T3 / T4 / T2 each independently assessed | See per-tier sections (T3 Feasibility / T4 Feasibility / T2 Feasibility) |
| 4 | One recommended tier with explicit upstream-unblock condition | T4 recommended; T3 unblock conditions enumerated in T3 section |
| 5 | Reproducibility commands listed verbatim | See "Reproducibility" section (curl HEAD probes + ramSeraph release inspect) |

---

## Cross-references

- [TODO/20260529-boundary-rip-and-replace-plan.md](../TODO/20260529-boundary-rip-and-replace-plan.md) rows A.1.b, B.5.
- [notes/2026-05-29-ap-assam-ac-source-hunt-handover.md](2026-05-29-ap-assam-ac-source-hunt-handover.md) (prior A.1 handover).
- [notes/2026-05-29-phase-b-verdict-correction.md](2026-05-29-phase-b-verdict-correction.md) (PR #433 verdict correction).
- A.1.a closed at PR #434 (b5b6ce94 on main) - S01 LGD swap with name-based ac_no rewrite. T3 deferral for S03 is the only remaining post-A.1 boundary work.
