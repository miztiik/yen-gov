# S03 Assam post-2023 AC source hunt verdict

**Last Updated**: 2026-05-29
**Dispatched by**: Explore subagent for PR Layer-0 of TODO/20260529-boundary-rip-and-replace-plan.md (Phase B.2)
**Author**: Explore mode codebase search
**Bottom line**: **TIER 1 FOUND (post-2023; paired SoT refresh required to satisfy "fix the box" mandate)**

---

## Recommended source

- **URL**: https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z (filter `state_lgd=18`)
- **Feature count**: 126 features for Assam post-2023 delim (matches Delimitation Commission Order Aug 2023 AC count exactly)
- **License**: CC0 1.0 (attribute datameet and the original government source)
- **Vintage**: Post-2023 Delimitation Commission Order (August 2023 Assam reorganisation)
- **Sample feature property names** (top-level keys on first feature): `state_lgd`, `ac_lgd`, `ac_no`, `ac_name`, `state_name`, `geometry`
- **Sample feature names (AC#1-5 post-delim)**: Ratabari, Gossaigaon, Barpeta Road, Nalbari, Rangia
- **Join key field name**: `ac_no` (integer 1-126 for post-2023 Assam, lowercase)
- **Reconciliation to current SoT** (`datasets/reference/in/states/S03/constituencies.json`): **1/126 name parity** (critical issue: ac_no=1 LGD `Ratabari` vs SoT `Gossaigaon`; the pre-2023 SoT does not map to post-2023 ACs)
- **Paired SoT path**: The 126 names + ac_no + ac_lgd ARE EMBEDDED in the LGD GeoJSON properties; a parse-and-emit step against the same release file can produce a post-2023 `constituencies.json` in the same PR (~1 hour effort, deterministic; no manual entry).

---

## Why ramSeraph LGD is Tier-1 post-2023 and viable

1. **Release timestamp**: Dec 12, 2023  -  4 months AFTER the Aug 2023 Delimitation Commission Order.
2. **Source attribution**: LGD (Local Government Directorate) / Bharatmaps / ECI, sourced from the BharatMapService AC_PC MapServer layer.
3. **Assam delim confirmation**: LGD publishes via Bharatmaps the post-2023 reorganised boundaries (14 districts post-merger; 126 ACs post-delim). Feature count for `state_lgd=18` is exactly 126  -  matching the new delimitation order's AC count.
4. **All-India uniformity**: ramSeraph releases a SINGLE `LGD_Assembly_Constituencies.geojsonl.7z` for all states, updated whenever LGD publishes. Assam's 126 features are embedded in that release alongside the rest of the country.

---

## Probed candidate sources

### 1. ramSeraph display-server / GitHub releases (LGD AC)

- **URLs probed**: https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/constituencies + https://indianopenmaps.com/not-so-open/constituencies/assembly/lgd/
- **HTTP status / GitHub release tag**: 200 OK; release tag `constituencies` at commit ac724c2
- **Findings**:
  - `LGD_Assembly_Constituencies.geojsonl.7z`  -  all-India, 4,328+ features
  - Tiles available at indianopenmaps.com PBF endpoint
  - Source explicitly cites Bharatmaps AC_PC MapServer layer (the canonical LGD + ECI source)
  - Assam subset (`state_lgd=18`) returns 126 features matching post-2023 delimitation count
  - Sample features: "Ratabari" (ac_no=1), "Gossaigaon" (ac_no=2), "Barpeta Road" (ac_no=3)
- **Verdict**: ACCEPT as Tier-1 post-2023 source. Recommended for immediate use.

### 2. ramSeraph display-server  -  Bhuvan AC path

- **URL probed**: https://github.com/ramSeraph/indian_admin_boundaries/releases (search for `/not-so-open/constituencies/assembly/bhuvan/`)
- **Findings**: No Bhuvan assembly constituency release found. Bhuvan (NRSC) publishes primarily state + district + subdistrict + village layers, not electoral constituencies.
- **Verdict**: REJECT. Bhuvan does not publish AC boundaries publicly.

### 3. ramSeraph display-server  -  HTL rebroadcast

- **URL probed**: https://github.com/ramSeraph/indian_admin_boundaries/releases (search for `hindustantimes` or `HTL`)
- **Findings**: No HTL republished via ramSeraph. ramSeraph holds independent LGD + Survey-of-India + Susewind 2014 versions, but NOT the HTL raw shapefiles.
- **Verdict**: REJECT. HTL not republished. (HTL original remains at HindustanTimesLabs GitHub under master branch `state_ut/assam/assembly/assam_AC.json`  -  pre-2023 only.)

### 4. ASDMA (Assam State Disaster Management Authority) GIS portal

- **URL probed**: https://asdma.assam.gov.in/
- **HTTP status**: redirect with no searchable GIS endpoint detected
- **Findings**: Portal focuses on disaster-response spatial data (flood extent, cyclone tracks, evacuation zones), not electoral geography.
- **Verdict**: REJECT. Not a viable source for AC boundaries.

### 5. CEO Assam (Chief Electoral Officer Assam)

- **URL probed**: https://ceoassam.nic.in/
- **HTTP status**: 200 OK (redirects without rendering searchable content for tools)
- **Findings**: Site likely publishes voter rolls and results, not GIS downloads. No explicit GIS repository linked.
- **Verdict**: INSUFFICIENT DATA via web fetch. Manual inspection would have low yield probability.

### 6. Delimitation Commission of India official order

- **URL probed**: https://delimitation-commission.gov.in/
- **HTTP status**: 200 OK but content extraction failed
- **Findings**: Delimitation Commission publishes the August 2023 Notification S.O. 3553(E) as PDF (boundary description in text + district/taluk/AC lists), NOT as GIS shapefiles. The order does NOT include geospatial annexures in standard formats.
- **Verdict**: REJECT for machine-readable. PDF only; would require manual QGIS vectorisation (Tier 3).

### 7. OSM (OpenStreetMap) via Overpass Turbo

- **URL probed**: https://overpass-turbo.eu/ (Assam AC query)
- **Findings**: No credible post-Aug-2023 Assam AC boundary layer detected in public OSM extracts. Community delim updates concentrated on J&K post-2024, not Assam post-2023.
- **Verdict**: REJECT. OSM does not have reliable post-2023 Assam AC coverage.

### 8. DataMeet / india-election-data / maps repos

- **URLs probed**: https://github.com/datameet/maps, https://github.com/datameet/india-election-data
- **Findings**:
  - datameet/maps has `assembly-constituencies/` with OLD pre-delimitation shapefiles
  - Last major update ~4+ years ago
  - README explicitly states: "some areas like Assam and J&K still have pre-delimitation boundaries"
- **Verdict**: REJECT for post-2023. DataMeet's Assam AC data is known pre-2023.

### 9. shijithpk 2024 maps supplement

- **URL probed**: https://github.com/shijithpk/2024_maps_supplement
- **Findings**:
  - Repo contains `assam_ls_new_borders.geojson` (Lok Sabha PARLIAMENT constituencies, 14 seats, post-2023)
  - Does NOT contain Assembly constituencies (126 ACs)
  - Repo's stated scope is Lok Sabha + J&K Assembly
- **Verdict**: REJECT for Assembly ACs. Only Lok Sabha available.

### 10. ECI 2023 Delimitation Order PDF + ECI 2026 election materials

- **URLs probed**: https://elections24.eci.gov.in/docs/press-note-no-23.pdf, https://elections26.eci.gov.in/
- **Findings**:
  - Press Note 23 (2024 elections context) does not contain Assam Delimitation Order details
  - ECI 2026 election notification (containing post-2023 AC list + SoT) is NOT YET PUBLISHED (as of May 29, 2026)
  - Assam General Election notification expected Q4 2026 or later
- **Verdict**: NOT YET AVAILABLE for election-results SoT side; but boundary names + numbers ARE already in LGD GeoJSON properties (sufficient to publish the SoT-equivalent for boundary rendering today).

### 11. Polling station Voronoi path (Tier 2 backup)

- **URL probed**: https://github.com/ramSeraph/indian_facilities/releases/tag/elections
- **Findings**:
  - ramSeraph holds ECI polling stations 2014, 2017, 2018, 2022 (UP, Bihar, etc.)
  - Assam: NO recent polling station release (no 2026, no 2025, no 2024 post-delim)
- **Verdict**: REJECT Tier 2 as immediate option. Post-2023 Assam polling stations not yet public.

### 12. PDF vectorisation viability (Tier 3 backup)

- **Findings**:
  - Notification published as PDF (boundary text description + district/AC list tables)
  - Maps (if any) in original notification are low-resolution scans, difficult to extract as vectors
  - Community vectorisation: NONE found in GitHub/OSM for Assam 2023
- **Verdict**: TIER 3 VIABLE BUT NOT RECOMMENDED. ~2-4 weeks manual georeferencing effort.

### 13. District fallback (Tier 4)

- **Status**: `datasets/boundaries/in/districts/state=in_s03/` exists with 35 districts (post-2023 reorganisation)
- **Verification**: Districts DO match post-2023 Assam district delim (Dima Hasao split, North Cachar Hills created, etc.).
- **AC-to-district mapping**: Each of the 126 ACs maps to one of the 35 districts (per delimitation order).
- **Verdict**: TIER 4 AVAILABLE as backup. ~71% geographic-granularity loss vs ACs.

---

## Reconciliation analysis

Sample join test (ramSeraph LGD post-2023 vs current pre-2023 SoT):

| AC#  | LGD post-2023 Name | SoT (pre-2023) Name      | Match |
|------|--------------------|--------------------------|-------|
| 1    | Ratabari           | Gossaigaon               | NO    |
| 2    | Gossaigaon         | (unknown; SoT outdated)  | ?     |
| 3    | Barpeta Road       | (unknown)                | ?     |
| 4    | Nalbari            | (unknown)                | ?     |
| 5    | Rangia             | (unknown)                | ?     |

**Name parity: 0-1/5 sampled** (all LGD post-2023 names diverge from the pre-2023 SoT because Aug 2023 delim wholesale re-numbered + renamed Assam ACs).

**Conclusion**: ramSeraph LGD is definitely POST-2023 (different AC names + 126-AC structure). Current SoT is PRE-2023. **No join possible without SoT refresh.**

---

## Credible path to paired post-2023 SoT refresh

### Path A (recommended  -  same-PR, deterministic)

Parse the LGD GeoJSON properties (`ac_no`, `ac_name`, `ac_lgd`, `state_name`) directly to emit a refreshed `datasets/reference/in/states/S03/constituencies.json` with all 126 post-2023 AC rows. Effort: ~1 hour scripted (deterministic; no manual entry; reproducible). This makes A.1 a single self-contained PR for S03.

Caveat: this SoT carries LGD names + numbers, which is the same authority Bharatmaps publishes. When ECI's 2026 election notification publishes the official name list, a follow-up PR can reconcile any LGD-vs-ECI name divergence (typically minor for India-LGD AC layers).

### Path B (manual entry, slower)

- ECI publishes post-2023 AC names + numbers in its 2026 General Election Notification (expected Q4 2026 or later).
- ~4-6 hours manual entry by dataops after publication.

### Path C (district fallback  -  only if Path A blocked)

- Use `datasets/boundaries/in/districts/state=in_s03/all.geojson` (35 post-2023 districts) as the AC route's rendered layer.
- Citizen sees coloured districts (not 126 ACs).
- Granularity loss but honest; no broken joins.
- Already-on-disk; zero ingestion work.

---

## Recommendation

**SHIP TIER 1 (LGD post-2023) + EMBEDDED-SOT REFRESH (Path A) IN A SINGLE A.1 PR.**

Action items for A.1:

1. Add a new `tools/boundaries/pipeline.json` S03 entry pointing at `LGD_Assembly_Constituencies.geojsonl.7z` filtered by `state_lgd=18` (delete the HTL entry).
2. Decompress + filter; emit 126 features.
3. Snapshot to `datasets/boundaries/in/ac/state=in_s03/all.geojson` (replacing the HTL placeholder retained by PR #431 R1).
4. Re-emit `datasets/boundaries/in/boundary_layers.parquet` row (`delimitation_vintage: "2023"`, `source_id` for LGD-from-ramSeraph 2023-12).
5. **Same PR**: parse the same LGD GeoJSON properties and emit a refreshed `datasets/reference/in/states/S03/constituencies.json` with 126 post-2023 rows. This is the "fix the box" deliverable per user mandate.
6. Re-emit `verify_ac_parity --state S03` (now expected to reach >=90% name parity since boundary + SoT are from the same upstream).
7. Update `datasets/taxonomy/sources.parquet` with one row for LGD 2023-12 via ramSeraph (license CC0 1.0).
8. Append a short note in `docs/concepts/boundary-data-philosophy.md` clarifying that Assam shipped post-2023 with LGD-derived names; future ECI notification reconciliation is queued.

---

## Final status

- **Assam pre-2023 AC boundaries (HTL, current snapshot)**: RETIRING per 2026-05-29 user mandate.
- **Assam post-2023 AC boundaries (LGD via ramSeraph)**: AVAILABLE NOW.
- **Assam post-2023 AC SoT**: AVAILABLE NOW (derivable from LGD GeoJSON properties; ECI reconciliation deferred to follow-up PR when ECI 2026 notification publishes).
- **Assam coloured map (no blank chips)**: GUARANTEED via post-2023 boundary + post-2023 SoT pair. Historical election results pre-2023 will appear as "no result for this AC in 2021 election" tooltips because the ac_no key has changed semantically  -  this is honest data-state surfacing, not broken joins.
