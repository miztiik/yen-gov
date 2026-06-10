# LGD opendata source catalogue

**Last Updated**: 2026-06-11

Catalogue + adoption stance for the **Local Government Directory (LGD)** mirror at [`ramseraph.github.io/opendata/lgd/`](https://ramseraph.github.io/opendata/lgd/). Companion to [boundary-data-sources.md](boundary-data-sources.md) — that doc is geometry, this one is the *registry tables* that issue the identifiers (LGD codes) the rest of yen-gov pivots on.

For the current production inventory of boundary geometry shards and the cross-walk to the LGD ⇔ Census ⇔ Constituency ⇔ PIN code alignment matrix, see [boundary-data-sources.md](boundary-data-sources.md). Current coverage gaps and swap candidates are recorded there.

## Terminology recap

Same as boundary-data-sources.md — reproduced here so the LGD table verdicts below read cleanly:

- **Assembly Constituency (AC)** = the electoral district that elects one MLA to a state legislative assembly. The LGD component is `assembly_constituencies`; the geometry layer is `kind=ac`.
- **Parliamentary Constituency (PC)** = the electoral district that elects one MP to the national lower house. The LGD component is `parliament_constituencies`; the geometry layer is `kind=pc`.
- **LGD code** = the numeric identifier issued by LGD for every administrative unit below the state — stable across name changes, the canonical join key for non-electoral layers (district / subdistrict / village / block / ULB / ward).

## What it is

The Government of India's **Local Government Directory** (<https://lgdirectory.gov.in>) is the canonical issuer of numeric identifiers for every administrative unit below the state — districts, sub-districts, blocks, gram panchayats, urban local bodies, wards, plus assembly and parliament constituencies. The portal itself is a session-bound ASP.NET form (not friendly to scripted ingestion).

[`ramSeraph/opendata/lgd/`](https://github.com/ramSeraph/opendata) extracts every entity table from LGD on a daily cron and publishes each as a 7z-compressed CSV under GitHub Releases. The same data is also republished (monthly) at [data.gov.in/catalog/local-government-directory-lgd](https://data.gov.in/catalog/local-government-directory-lgd); ramSeraph has the freshest snapshot, data.gov.in has the official imprimatur — pick whichever is fresher at ingestion time.

A second mirror — [`ramSeraph/indian_admin_boundaries`](https://github.com/ramSeraph/indian_admin_boundaries) — wraps the SAME LGD tables with the matching geometry from BharatMaps. That repo is the geometry side ([boundary-data-sources.md](boundary-data-sources.md)); this doc is the tables side.

## URL pattern

Every archive lives at:

```
https://github.com/ramSeraph/opendata/releases/download/<release_tag>/<component>.<DDMmmYYYY>.csv.7z
```

Where:

| Token           | Values                                                                                              |
| --------------- | --------------------------------------------------------------------------------------------------- |
| `<release_tag>` | `lgd-latest-extra1` for the rolling ~3-month window (currently Jan–Apr 2026 visible). `lgd-archive` / `lgd-archive-extra1` for older snapshots. |
| `<component>`   | One of the 37 entity names in the table below.                                                      |
| `<DDMmmYYYY>`   | English-locale date stamp, e.g. `03Apr2026`. Daily emit, but not every component changes every day. |

Confirmed example (recon 2026-05-13): `https://github.com/ramSeraph/opendata/releases/download/lgd-latest-extra1/districts.03Apr2026.csv.7z` (~8.5 kB).

The `.csv.7z` archives use a 7z variant that the BSD/GNU `unzip` does not handle. In Python use [`py7zr`](https://pypi.org/project/py7zr/) (pure-Python, works on Windows without the Linux toolchain `tools/boundaries/build.py` requires). On the shell, `7z x` from the [7-Zip](https://www.7-zip.org/) project.

## Component catalogue (37)

Grouped by yen-gov decision verdict. The **Verdict** column is binding: do not ingest a component marked *Out of scope* without first updating this doc and the relevant ADR.

### Adopt — fills a current yen-gov identifier gap

| Component                  | Use                                                                                                                                                  | Verdict                                |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `states`                   | LGD numeric code ↔ canonical English state name. Bridge table for joining LGD entities to our ECI `S22`/`U05`-style codes (match by name).           | **Adopt.** Required to backfill anything else. |
| `districts`                | LGD numeric district code + state code + canonical district name + Census 2001/2011 codes.                                                          | **Adopted.** District identity lives on `datasets/data/entities/geo.csv` (`entity_type='district'` rows) with `lgd_code` as the join key per [ADR-0015](../concepts/electoral-hierarchy.md#adr-0015-constituency-hierarchy-fields). |
| `assembly_constituencies`  | LGD AC code + name + state. The CSV-side counterpart to the `LGD_Assembly_Constituencies` geometry release. Lets us cross-check our ECI `acN`-prefixed IDs against the LGD-issued ones during per-state parity verification. | **Adopt alongside geometry consolidation.** Until the first AC swap promotes, *catalogue only* — ECI's own AC codes already join HTL boundaries cleanly. |
| `parliament_constituencies`| LGD PC code + name + state. Same role as ACs but at the national level (Members of Parliament).                                                       | **Adopt when a national-election cycle enters scope.** Currently *catalogue only.*  |
| `subdistricts`             | LGD sub-district (tehsil/taluk/mandal) numeric code under each district.                                                                            | **Adopted countrywide (PR #257).** |

### Adopt when scope expands (PRI / urban / scheme-delivery panels)

Most rows below are *catalogue only* -- they become required the moment yen-gov ships a citizen surface that pivots on local bodies or schemes.

| Component                                | Pulls in                                                                                  |
| ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| `blocks`                                 | LGD block code (rural development block, distinct from sub-district).                     |
| `district_panchayats`                    | District-level Panchayati Raj body, mapped to LGD district.                               |
| `pri_local_bodies`                       | Three-tier PRI: Zilla / Block / Gram panchayats with LGD codes.                           |
| `pri_local_body_wards`                   | Wards inside each PRI body.                                                                |
| `gp_mapping`                             | Cross-mapping of gram panchayats to higher PRI bodies.                                     |
| `urban_local_bodies`                     | Municipal corporations / councils / nagar panchayats with LGD ULB codes.                  |
| `urban_local_body_wards`                 | Ward roster for each ULB.                                                                  |
| `statewise_ulbs_coverage`                | Coverage roll-up: which ULBs cover which territory per state.                              |
| `traditional_local_bodies`               | Sixth Schedule / customary bodies (esp. NE states).                                       |
| `tlb_villages`                           | Village ↔ Traditional Local Body mapping.                                                 |
| `villages`                               | LGD village code (the leaf node of the rural hierarchy). Large file — verify size before ingestion. The CSV-side counterpart to the `LGD_Villages` geometry release (27/36 states live; 9 gap states tracked in [boundary-data-sources.md](boundary-data-sources.md)). |
| `villages_by_blocks`                     | Village ↔ block mapping (alternate slice of `villages`).                                  |
| `invalidated_census_villages`            | Census 2011 villages that LGD has since retired (deduplicated, merged, etc.).             |
| `nofn_panchayats`                        | Panchayats covered by the National Optical Fibre Network rollout. Useful if a digital-infrastructure indicator ships. |
| `pincode_urban`                          | India Post pincode ↔ ULB mapping. **Adopt as lookup table** when pincode search-affordance UI ships (runs ahead of pincode polygons). |
| `pincode_villages`                       | India Post pincode ↔ village mapping. Companion to `pincode_urban`. |
| `constituencies_mapping_pri`             | AC/PC ↔ PRI local body coverage (which panchayats fall in which constituency).            |
| `constituencies_mapping_urban`           | AC/PC ↔ ULB coverage.                                                                     |
| `constituency_coverage`                  | Combined (rural + urban) coverage roll-up per constituency.                               |
| `parliament_constituencies_lb_mapping`   | PC ↔ local-body roll-up (PC version of `constituency_coverage`).                          |

### Out of scope (administrative-org tables, not citizen-visible)

These are bureaucratic-org charts: which department exists at the centre/state, which designations sit inside it, which units report where. They have no citizen-facing surface in yen-gov and are not gap-fill for any identifier we use. Listed so the next "what's that file?" question has a recorded answer.

`central_admin_depts`, `central_admin_dept_units`, `central_orgs`, `central_org_units`, `central_org_designations`, `state_admin_depts`, `state_admin_dept_units`, `state_orgs`, `state_org_units`, `state_org_designations`.

### Cross-cutting

| Component | Use |
| --------- | --- |
| `changes` | Audit log of every entity-level change LGD has applied (creations, splits, merges, renames, retirements). The right place to look when a `lgd_code` in our reference data stops resolving — diff yesterday's snapshot against today's `changes` file to find the migration. *Catalogue only* until first lineage-debugging incident makes it worth ingesting. |

## How yen-gov uses it

Today: district identity lives on `datasets/data/entities/geo.csv` (`entity_type='district'` rows) with `lgd_code` populated as the LGD-issued canonical key per [ADR-0015](../concepts/electoral-hierarchy.md#adr-0015-constituency-hierarchy-fields) and [ADR-0033](../architecture/backend/sources-wikipedia.md#adr-0033-retire-wikipedia-districts-adapter). The legacy per-state `districts.json` files + `district.schema.json` that originally seeded these rows were retired in T.0c-iii.

Planned (next implementation pass, tracked under `tools/lgd/`):

1. **Snapshot.** Download the latest `states.<DDMmmYYYY>.csv.7z` and `districts.<DDMmmYYYY>.csv.7z` from `lgd-latest-extra1` to `.runtime/raw/lgd/`. Date-discover by walking back day-by-day from `Get-Date -Format "ddMMMyyyy"` until a 200 OK lands.
2. **State-code bridge.** Build `datasets/data/entities/lgd/lgd-to-eci-states.json` by joining LGD `State Name (In English)` to the canonical state names already in `datasets/data/entities/geo.csv` (which carry `entity_code` -- the ECI code). LGD numeric state code -> ECI `S22`/`U05` code.
3. **District backfill.** For each `entity_type='district'` row on `datasets/data/entities/geo.csv` (carrying a `legacy_id` Wikipedia-slug fallback from the Phase-A fold-in), normalise the display name (lowercase, strip whitespace, drop trailing " District"), match against LGD `districts.csv` filtered to that state's LGD code, write the resolved `lgd_code`, and surface unmatched names for manual review. Today most of the 145 Phase-A district rows already carry `lgd_code` from the original wikipedia-scraped fields; the long tail (~600 LGD-only districts for states with no hand-authored seed) lands via this pass.
4. **Provenance.** Each generated artifact carries a `sources` array per CLAUDE.md §12 with the exact ramSeraph release URL and `fetched_at`. Reference materials (the data.gov.in mirror, the LGD portal itself) belong in commit messages, not `sources` (which only lists URLs the pipeline actually fetched).

The geometry side (LGD-derived district polygons) is a separate workstream — see [boundary-data-sources.md](boundary-data-sources.md) §"Format gap: geojsonl.7z" and the `staged_inputs` entry in [`tools/boundaries/pipeline.json`](../../tools/boundaries/pipeline.json).

## Gap-fill discipline

Same rule that governs boundary sources applies here ([boundary-data-sources.md §"Source-selection policy"](boundary-data-sources.md#source-selection-policy-gap-fill-not-bulk-swap)): **adopt only to fill a real gap, never to bulk-swap a working layer.** The 37-component catalogue exists; only the rows marked *Adopt* in the tables above are actually pulled by yen-gov pipelines. Promoting a *Catalogue only* component to *Adopt* requires updating this doc and the ADR or subsystem doc that the new dependency lands in, in the same commit (CLAUDE.md Holy Law #4).

## Schema notes (recon 2026-05-13)

Confirmed from [the anatomy page](https://ramseraph.github.io/opendata/lgd/anatomy):

- `districts.csv` columns: `S.No., State Code, State Name (In English), District Code, District Name (In English), Census 2001 Code, Census 2011 Code`. UTF-8.
- `states.csv` columns: `S.No., State Code, State Name (In English), State Name (In Local)` (~1 kB compressed).
- LGD `State Code` is a sequential integer (1, 2, 3, …), independent of ECI's `S22`/`U05` prefix scheme. Joining the two registries is by *English state name*, not by code — name normalisation (case-fold, whitespace-strip) is mandatory.

Other components' schemas are not yet recon'd in this doc; consult <https://ramseraph.github.io/opendata/lgd/anatomy> at ingestion time and append to this section.

## See also

- [boundary-data-sources.md](boundary-data-sources.md) — geometry side (`ramSeraph/indian_admin_boundaries`, datameet, HTL, etc.)
- [identifiers.md](identifiers.md) — the canonical id table this source backfills
- [ADR-0015](../concepts/electoral-hierarchy.md#adr-0015-constituency-hierarchy-fields) — why `lgd_code` is the preferred district id
- [data-sources.md](data-sources.md) — election-results sources (sister catalogue)
- CLAUDE.md §11 (schema versioning), §12 (provenance), §5 (docs discipline)
