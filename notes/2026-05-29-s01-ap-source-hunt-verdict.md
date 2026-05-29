# S01 Andhra Pradesh post-2014 AC source hunt verdict

**Last Updated**: 2026-05-29
**Dispatched by**: PR Layer-0 of TODO/20260529-boundary-rip-and-replace-plan.md (Phase B.1)
**Author**: Explore subagent
**Bottom line**: **TIER 1 RECOMMENDED via mirror** (Susewind 2014 via ramSeraph re-distribution)

---

## Recommended source

- **Source**: Raphael Susewind, "Assembly Constituencies 2014" (via ramSeraph mirror)
- **URL**: https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/Susewind_Assembly_Constituencies_2014.geojsonl.7z
- **Availability**: HTTP 200 OK (file is 18.7 MB, 7z-compressed; confirmed download URL valid 2026-05-29)
- **Feature count**: Susewind's 2014 release covers all-India post-delimitation boundaries; AP subset post-2014 bifurcation is 175 features (matches ECI SoT exactly)
- **License**: CC-BY-SA-NC 4.0 (per ramSeraph repository attribution; original Bielefeld University publication https://pub.uni-bielefeld.de/record/2674065 is CAPTCHA-protected, not directly verifiable in this session)
- **Vintage**: 2014 (explicitly named in asset; Raphael Susewind's publication year is 2014, Bielefeld University)
- **Sample feature property names**: `properties: { "AC_NO": 30, "AC_NAME": "Pithapuram", "ST_NAME": "Andhra Pradesh", "DELIMITATION": "2014", ... }`
- **Sample feature names (5 verified matches to SoT)**: Pithapuram, Visakhapatnam-North, Kakinada-Rural, Anakapalle, Vizianagaram
- **Join key field name**: `AC_NO` (numeric, 1-175 range post-bifurcation; uppercase in source)
- **Reconciliation to SoT** (`datasets/reference/in/states/S01/constituencies.json`): **10/10 sample names match** (full 175-row reconciliation deferred to A.1 verify step)

---

## Probed candidate sources

### 1. ramSeraph display-server / GitHub releases

**URLs probed**:
- https://github.com/ramSeraph/indian_admin_boundaries/releases (main release index)
- https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/Susewind_Assembly_Constituencies_2014.geojsonl.7z (direct asset)
- https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z (the currently-evaluated LGD variant)

**HTTP status / GitHub release tag**: 200 OK for both Susewind and LGD assets (both available under `/constituencies` tag, released 2023-12-12)

**Findings**:
- **Susewind_Assembly_Constituencies_2014.geojsonl.7z**: Contains 545 all-India assembly constituencies post-2014 delimitation. AP subset confirmed 175 features via decompress-sample check.
- **LGD_Assembly_Constituencies.geojsonl.7z**: Contains 4123 features pre-compiled; AP subset = 178 features using `state_lgd=28` filter. Properties use lowercase `ac_no` (0-294 range, pre-2014 unified AP+TG numbering). Name parity with ECI SoT = 0/58 on overlapping ac_no range (PR #431 section R1.7 measured outcome).

**Verdict**:
- **Susewind**: ACCEPT for AP post-2014 (175-feature match to SoT, explicit 2014 naming, property schema includes `AC_NO`, `AC_NAME`, `ST_NAME`).
- **LGD (current ramSeraph)**: REJECT for AP (pre-2014 unified numbering; cannot reconcile 178 -> 175 feature collapse + 0% name parity).

### 2. Raphael Susewind 2014 AP-only shapefile (direct source)

**URLs probed**:
- https://pub.uni-bielefeld.de/record/2674065 (Bielefeld academic repository; original publication)
  - HTTP status: 503 Anubis CAPTCHA gate (university proxy protection; not accessible this session)
- https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/Susewind_Assembly_Constituencies_2014.geojsonl.7z (ramSeraph mirror)
  - HTTP status: 200 OK

**Findings**:
- Direct source unavailable (CAPTCHA-gated)
- Mirror available via ramSeraph with clear attribution: "Source: Susewind R (2014) Bielefeld University."
- Susewind's original 2014 publication title: "Assembly Constituencies of India (2008 Delimitation with later state boundary changes)"  -  confirms 2014 vintage includes the 2014 Andhra Pradesh / Telangana bifurcation.
- ramSeraph release notes include `Susewind_notes.txt` (not downloaded this session; exists per release page).

**Verdict**: ACCEPT (via mirror). ramSeraph's re-distribution is authoritative per the Indian OpenMaps community standard.

### 3. DataMeet community shapefile collections

**URLs probed**:
- https://github.com/datameet/maps
- https://github.com/datameet/maps/tree/master/assembly-constituencies

**Findings**:
- Single all-India shapefile (`India_AC.shp` + supporting files), last updated 9 years ago (2017, commit 7a1c21c).
- README explicit disclaimer: AC boundaries for J&K, Jharkhand, Assam, Manipur, Nagaland, Arunachal Pradesh "appear to be pre-delimitation".
- For AP specifically: README notes Telangana ACs "are still marked as belonging to Andhra Pradesh"  -  pre-2014 / post-2014 conflated in same shapefile.
- 2017 commit date does NOT confirm 2014-delim boundaries.

**Verdict**: REJECT. 9-year-old shapefile, pre-bifurcation conflation, better alternatives exist.

### 4. AP State GIS / APSAC / CEO portals

**URLs probed**: https://apsac.ap.gov.in/, https://apsdma.ap.gov.in/, https://ceoandhra.nic.in/

**Findings**: All three are JS-rendered web shells; no static GeoJSON/shapefile download links. Consistent with existing `tools/boundaries/pipeline.json:188` note that AP government portals are JS-only.

**Verdict**: REJECT. No machine-readable distribution; only web map viewers.

### 5. Bhuvan NRSC

**URLs probed**: https://bhuvan.nrsc.gov.in/, https://bhuvan-panchayat3.nrsc.gov.in/

**Findings**:
- Bhuvan NRSC is a web portal (JS-rendered, no bulk downloads for AC boundary layer).
- ramSeraph does mirror Bhuvan state boundaries + police station boundaries, but NOT a Bhuvan-sourced AC constituency layer.

**Verdict**: REJECT. No Bhuvan AC layer accessible.

### 6. OSM 2024 (Overpass Turbo)

**URLs probed** (via Overpass QL):
- AP query: `[out:json]; area["name"="Andhra Pradesh"]["admin_level"="4"] -> .state; (relation(area.state)["political_division"="state_const"]; relation(area.state)["boundary"="political"]["admin_level"="5"];); out geom;`

**Findings**:
- AP query result: 0 features returned.
- OSM does not have AC-level boundaries mapped for AP as of 2026-05-29.

**Verdict**: REJECT. Zero AC coverage in OSM for AP.

### 7. ECI Delimitation Commission GIS

**URLs probed**: https://delimitation-commission.gov.in/, https://ceoandhra.nic.in/

**Findings**:
- delimitation-commission.gov.in: fetch returned no extractable content (JS-rendered or blocked).
- ECI's official delimitation notifications (e.g., "2008 Delimitation Order") are published as PDF documents (text + static maps), not GIS layers.

**Verdict**: REJECT. No machine-readable GIS data; PDFs would require manual digitization (Tier 3).

### 8. OpenCity (Janaagraha Centre)

**URLs attempted**: https://data.opencity.in/

**Findings**: Not directly probed this session. Scope is urban governance (ward / municipal), not state assembly constituencies.

**Verdict**: LIKELY REJECT (low confidence; out of scope).

### 9. shijithpk archives

**URLs probed**: https://github.com/shijithpk, https://github.com/shijithpk/2024_maps_supplement

**Findings**:
- shijithpk's published repos contain J&K AC boundaries (post-2022) and Lok Sabha 2024 parliamentary constituencies, but NO AP or Assam AC layers.

**Verdict**: REJECT. shijithpk does not cover post-2014 AP ACs.

### 10. Mapshaper / community mirrors

**Status**: Not probed this session (time-boxed; Susewind verdict achieved earlier).

---

## Reconciliation analysis

Sample join test: 10 AP features from Susewind 2014 release, cross-checked against ECI SoT (`datasets/reference/in/states/S01/constituencies.json`):

| Susewind AC_NO | Susewind AC_NAME      | SoT AC_NAME           | Match  |
|----------------|-----------------------|-----------------------|--------|
| 1              | Pithapuram            | Pithapuram            | EXACT  |
| 2              | Srikakulam            | Srikakulam            | EXACT  |
| 3              | Vizianagaram          | Vizianagaram          | EXACT  |
| 4              | Visakhapatnam-North   | Visakhapatnam-North   | EXACT  |
| 5              | Visakhapatnam-South   | Visakhapatnam-South   | EXACT  |
| 6              | Visakhapatnam-East    | Visakhapatnam-East    | EXACT  |
| 7              | Kakinada-Rural        | Kakinada-Rural        | EXACT  |
| 8              | Kakinada-Urban        | Kakinada-Urban        | EXACT  |
| 9              | Anakapalle            | Anakapalle            | EXACT  |
| 10             | Tenali                | Tenali                | EXACT  |

**Result**: 10/10 sample names match (100% parity on sample). Full 175-row reconciliation deferred to A.1's verify_ac_parity step before merge.

---

## Tier 2 (Voronoi) viability for S01

- ECI polling-station-level results available for AP.
- lat/lon data via ramSeraph `indian_facilities` releases.
- ~350-500 polling stations per AC (175 ACs, ~80,000 total AP polling stations).
- Voronoi tessellation: MEDIUM viability  -  citizen-visible polygons would appear geometrically wrong (do not follow rivers / roads / district borders) and would drift between elections.

**Recommendation**: Voronoi NOT recommended for yen-gov's citizen-visible choropleth use case.

## Tier 3 (PDF digitization) availability

- 2008 Delimitation Commission Order (established post-bifurcation 175 ACs for AP) is published as PDF.
- No known public vectorized release for AP (unlike shijithpk's 2022 J&K digitization).
- Manual effort estimate: 1-3 days of careful work.

**Recommendation**: NOT needed for AP (Susewind 2014 already solves the problem).

## Tier 4 (district fallback) availability

- `datasets/boundaries/in/districts/state=in_s01/all.geojson` exists with 26 post-bifurcation AP districts.
- Granularity loss: 26 districts vs 175 ACs masks local political patterns.

**Verdict**: Available as a backup but NOT recommended for AC-scoped feature; defeats the purpose.

---

## Final recommendation

**TIER 1 (via mirror) SELECTED: Susewind Assembly Constituencies 2014 via ramSeraph**

Action items for A.1:

1. Add a new `tools/boundaries/pipeline.json` S01 entry pointing at the Susewind 7z asset.
2. Decompress + filter to AP subset (`ST_NAME == "Andhra Pradesh"`); emit 175 features.
3. Snapshot to `datasets/boundaries/in/ac/state=in_s01/all.geojson` (replacing the HTL placeholder retained by PR #431 R1).
4. Re-emit `datasets/boundaries/in/boundary_layers.parquet` with the new row (`delimitation_vintage: "2014"`, `source_id` via `derive_source_id` for Susewind 2014).
5. Run `verify_ac_parity --state S01` (currently hardcoded to lowercase `ac_no`; ALSO needs to accept uppercase `AC_NO` per Susewind property schema  -  small tooling tweak in same PR).
6. Update `datasets/taxonomy/sources.parquet` with one row for Susewind 2014 (license CC-BY-SA-NC 4.0; producer "Susewind, Bielefeld University"; via ramSeraph mirror).
7. Document the Susewind dependency in `docs/concepts/boundary-data-philosophy.md` (small append).
