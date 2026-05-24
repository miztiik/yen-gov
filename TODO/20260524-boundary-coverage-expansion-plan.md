# Boundary coverage expansion — phased plan (pincode → subdistricts → villages → AC consolidation → census-2011)

**Date opened**: 2026-05-24
**Status snapshot**: Phase 0 (planning) — no PRs open yet
**Authority**: Hans + Max (data shape) for layer choices; Fowler (engineering craft) for migration mechanics; Jony + Citizen for any UI surface that exposes the new layers.
**Rationale anchors** (do NOT re-state here):
- Source catalogue + cross-walk to the LGD ⇔ Census ⇔ Constituency ⇔ PIN code alignment matrix: [`docs/reference/boundary-data-sources.md`](../docs/reference/boundary-data-sources.md)
- LGD tables side: [`docs/reference/lgd-opendata.md`](../docs/reference/lgd-opendata.md)
- Disk layout + identifier discipline + methodology-break rules: [`docs/architecture/data/boundaries.md`](../docs/architecture/data/boundaries.md)
- Decision history: [ADR-0031 Boundary geometry strategy](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) (+ 2026-05-24 amendment for PC layer + delim partition)
- "Gap-fill, not bulk-swap" policy: [`boundary-data-sources.md` §"Source-selection policy"](../docs/reference/boundary-data-sources.md#why-these-choices)

## Phase 0.0 — Status ready reckoner (UPDATE AFTER EVERY PR)

**This table is the live status ledger for the boundary-coverage expansion.** Update it in the SAME PR as the phase's code/data changes, so a session interruption at any point leaves an accurate map of where work stopped. An agent picking up the work mid-flight should be able to read ONLY this table + the affected phase section to know what to do next.

| Phase | PR | Status | Merged SHA | Notes / blockers |
| --- | :---: | --- | :---: | --- |
| **0.1** Subdistrict CSV ingest (re-run `tools/lgd/snapshot.py`) | — | Not started | — | Re-run snapshot tool first; manual portal fallback documented in §0.1 |
| **0.2** District backfill (639 rows → `entities.json`) | — | Not started | — | Independent of 0.1; needs `tools/lgd/backfill_entities_districts.py` (NEW) |
| **0.3** Subdistrict entity seed | — | Deferred → Phase B.1 | — | Folded into Phase B ingest |
| **0.4** Simplify existing national boundary files (D-P) | — | Not started | — | **Blocks D.0 and D.6** — must ship before survey-grade swaps; needs `tools/boundaries/simplify.py` (NEW) |
| **A.1** Pincode directory CSV (~165k rows) | — | Not started | — | Use existing `datagovin_ogd` adapter — DO NOT build new HTTP client |
| **A.2** Pincode polygons (national) | — | Not started | — | After A.1 |
| **B** Subdistrict national lift (TN → 36 states/UTs) | — | Not started | — | After **0.1** (needs subdistricts CSV on disk) |
| **C** Village national lift (TN → national minus 8 states) | — | Not started | — | After **B** (proves LGD ingest pattern at smaller cardinality) |
| **D.0** State polygon swap (DataMeet → ramSeraph `LGD_States`) | — | Not started | — | After **0.4**; survey-grade upgrade per user override 2026-05-24 |
| **D.1** AC consolidation snapshot recon (one-shot, gating) | — | Not started | — | Independent of 0.4 |
| **D.2** AC consolidation promote 28 states | — | Not started | — | After **D.1** |
| **D.3** AC consolidation — Assam carve-out | — | Not started | — | After **D.1** |
| **D.4** AC consolidation — J&K carve-out | — | Not started | — | After **D.1** |
| **D.5** AC consolidation wrap-up (docs + ledger + ADR amend) | — | Not started | — | After **D.2/D.3/D.4** |
| **D.6** PC polygon swap (shijithpk → ramSeraph `LGD_Parliament_Constituencies`) | — | Not started | — | After **0.4**; survey-grade upgrade per user override 2026-05-24 |
| **E** Census-2011 polygon layer | — | Deferred | — | Out of scope until first Census-driven citizen surface ships |

**Update protocol** (mandatory for every PR landing in this plan):
1. Set `Status` to `In progress` when the worker worktree is created.
2. Set `PR` to `#<number>` once `gh pr create` returns.
3. Set `Status` to `In review` if waiting on CI / human review.
4. Set `Status` to `Merged` + `Merged SHA` to the 7-char short merge SHA once `gh pr merge` confirms `state: MERGED`.
5. If blocked, set `Status` to `Blocked: <reason>` + add detail in `Notes`. Never silently skip.
6. The status update lives in the SAME commit as the phase's code/data work \u2014 NOT a separate docs PR (per CLAUDE.md §5 "docs-only PRs are a code smell").

**Status enum** (case-sensitive): `Not started` | `In progress` | `In review` | `Merged` | `Blocked: <reason>` | `Deferred`

---

## Boundary file-size policy (Jony + Fowler joint, 2026-05-24)

**Two levers in strict order** to keep per-shard size citizen-friendly on patchy 4G:

1. **Simplify geometry** at zoom-appropriate Douglas-Peucker tolerance (lever applied first, every time).
2. **Shard at the citizen's current viewport, no finer** (lever applied only if simplification can't bring a shard under the per-fetch ceiling).

**Per-fetch ceiling**: ≤ 500 KB gzipped per file. **Per-fetch floor**: ≥ ~50 KB gzipped (below this the per-fetch TLS + HTTP/2 header overhead dominates wall-clock; many tiny fetches are wasteful, not faster). Aim for **100–300 KB gzipped per shard** as the sweet spot.

**On-disk reality today (audited 2026-05-24)** — every "national" file currently violates the ceiling by 3–5×:

| File | Raw KB | Est gzip KB | Verdict |
| --- | ---: | ---: | --- |
| `country/all.geojson` | 12,042 | ~2,168 | Way over |
| `states/all.geojson` | 11,330 | ~2,040 | Way over |
| `pc/delim=2024/all.geojson` | 8,564 | ~1,542 | Over |
| `districts/all.geojson` | 6,696 | ~1,205 | Over |
| `ac/state=in_u08/all.geojson` | 5,519 | ~993 | Outlier, over |
| `subdistricts/state=in_s22/all.geojson` | 5,084 | ~915 | Over (TN only ingested today) |
| Largest village per-district shard (`district=593`) | 2,727 | ~491 | At ceiling |
| Most AC per-state shards | 100–1,000 | 20–300 | Sweet spot |
| Most village per-district shards | 100–2,000 | 20–400 | Sweet spot |

**Per-layer simplification targets** (Phase 0.4 implements these; Phase D.0 + D.6 swap targets must clear them):

| Layer | Citizen viewport zoom | Douglas-Peucker tolerance | Target gzipped per shard | Shard rule |
| --- | --- | --- | ---: | --- |
| `country` | India-fits-on-phone | ~0.005° (~500 m) | < 100 KB | 1 national file |
| `states` | India zoom | ~0.002° (~200 m) | < 200 KB | 1 national file (36 features) |
| `districts` | India zoom | ~0.001° (~100 m) | < 500 KB | 1 national file (784 features); shard by state ONLY if still > 500 KB after D-P |
| `pc` | India zoom | ~0.001° | < 500 KB | 1 national file (545 features); shard by state ONLY if > 500 KB after D-P (likely after survey-grade swap) |
| `ac` | state-hub zoom | ~0.001° | < 500 KB per state | per-state shard already; ONLY tighten D-P for the 3–4 outlier states (UP/MP/BR/RJ) |
| `subdistricts` | state-hub zoom | ~0.0005° (~50 m) | < 300 KB per state | per-state shard (Phase B) |
| `villages` | district-drill zoom | ~0.0002° (~20 m) | < 500 KB per district | per-district shard already (Phase C) |

**Why simplification first, sharding second** (Fowler's HTTP economics + Jony's URL grammar):
- TLS+TCP setup on patchy 4G is ~200–500 ms latency per fresh connection; HTTP/2 multiplexes BUT per-request header overhead is still ~50–100 ms.
- Going from 1 file → N files multiplies header overhead linearly; the savings appear only when each shard is genuinely smaller than the per-fetch ceiling AND the viewport actually needs only one shard at a time.
- Citizens looking at India don't see 1 m coastline precision; they see Bharat-shaped blob. Survey-grade vectors are wasted bytes at that zoom.
- Each fetch is also a failure mode + a loading-state flicker. Many small fetches = many retry banners; fewer fetches = cleaner UX.

**The URL grammar stays one-fetch-per-viewport**:
- Home / national choropleth → 1 file `<layer>/all.geojson`
- State hub → 1 file `<layer>/state=<s>/all.geojson`
- District drill (today only meaningful for villages) → 1 file `<layer>/state=<s>/district=<d>/all.geojson`

**This policy applies as a hard gate** on Phase D.0 (state geometry swap) and Phase D.6 (PC swap). Survey-grade BharatMaps polygons will balloon raw size 2–3× vs current sources; Phase D.0 + D.6 PRs MUST simplify down to the targets above before merging.

---

## Phase summary

| Phase | Scope | Status | Active PRs | Blocking |
| --- | --- | --- | --- | --- |
| **0** | LGD coverage prereq: fetch missing `Subdistricts.csv` via `tools/lgd/snapshot.py`; backfill remaining 639 districts into `entities.json`; seed first `entities.json` subdistrict rows | Not started | — | None (gates B + C readiness) |
| **A** | Pincode lookup CSV (Phase A.1) + national pincode polygons (Phase A.2) | Not started | — | None (independent of B/C/D/E) |
| **B** | Sub-district national lift (TN-only → 36 states/UTs) using ramSeraph `LGD_Subdistricts` | Not started | — | Phase 0 subdistrict CSV ingest |
| **C** | Village national lift (TN-only → national, minus 8 states upstream) using ramSeraph `LGD_Villages` | Not started | — | After B (proves the LGD ingest pattern at smaller cardinality) |
| **D** | Survey-grade swap to ramSeraph BharatMaps lineage: state polygons (D.0), AC consolidation (D.1–D.5), PC swap (D.6) | Not started | — | D.1 snapshot recon must happen before any AC promotes; D.0 + D.6 are independent of AC work |
| **E** | Census-2011 polygon layer (`Districts_2011`, `SubDistricts_2011`) — adopt when first census-driven citizen surface ships | Deferred | — | First Census-2011 indicator consumer; out of scope until then |

---

## Phase 0 — LGD code coverage prerequisites

**Why this phase exists**: Phases B and C lift sub-district and village geometry. The geometry is keyed by `lgd_code`; without the matching LGD CSV on disk, the ingest has no name/parent reference to validate against. We have states (100%) and the LGD districts mirror (784 rows), but subdistricts haven't been snapshotted and only 145 of 784 districts are folded into `entities.json` today (the 145 with ECI mappings). Phase 0 closes both gaps.

**Coverage status on disk (audited 2026-05-24)**:

| Layer | LGD CSV mirror (`datasets/taxonomy/lgd/`) | `entities.json` rows | Notes |
| --- | :---: | :---: | --- |
| State | ✅ `states-latest.csv` (36 rows, dated 2026-05-20) | 29 states + 10 UTs = **39 / 39 (100%)**, all carry `lgd_code` + `iso_3166_2` + `legacy_id` (ECI) | No work needed |
| District | ✅ `districts-latest.csv` (784 rows, dated 2026-05-20) | **145 / 784 (18%)**, all 145 carry `lgd_code` | The 145 are the districts with ECI-linked constituencies; 639 non-electoral districts await fold-in. Per [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md) new districts land via hand-curated PR against `entities.json`, not re-scrape — backfill is a one-shot. |
| Subdistrict | ❌ None on disk | **0** | Snapshot tool wired ([`tools/lgd/snapshot.py`](../tools/lgd/snapshot.py) line 50 has `Subdistricts` in `REQUIRED_COMPONENTS`) but no `subdistricts-latest.csv` yet — either the last `tools/lgd/snapshot.py` run pre-dated the Subdistricts wiring, or the upstream release token's Subdistricts asset isn't published yet. Re-run + verify. |
| Village | ❌ None on disk | **0** | Optional component on the snapshot tool. Defer until Phase C. |

### 0.1 — Subdistrict CSV ingest

- **What ships**: `datasets/taxonomy/lgd/subdistricts-<YYYY-MM-DD>.csv` + `subdistricts-latest.csv` + `subdistricts-latest.csv.sources.json` provenance sidecar. Same dated+latest+sources triple shape as states/districts.
- **Tooling**: re-run `python tools/lgd/snapshot.py` from repo root. The tool already lists `Subdistricts` as a required component (added 2026-05-15) but the disk shows only states + districts — so either (a) the upstream release token doesn't have `Subdistricts.<token>.csv.7z`, or (b) the tool hasn't been re-run since the wiring change. Both are operator-runnable in seconds.
- **Recovery if upstream is missing the asset**: file an issue at [`ramSeraph/opendata`](https://github.com/ramSeraph/opendata/issues) requesting the Subdistricts asset on the next release; in the meantime the LGD portal export ([screenshot the user provided](https://lgdirectory.gov.in/globalviewsubdistrict.do)) is a manual fall-back — click "Spreadsheet" per state, drop the 36 CSVs under `.runtime/raw/lgd/subdistricts-portal/`, then a small `tools/lgd/portal_subdistrict_concat.py` (NEW, ~30 lines) concatenates them with a unified header. **Do NOT build a captcha-solving headless-browser scraper** — the portal export is faster manually than a robust scraper, and ramSeraph's automated mirror is the long-term plan.
- **Acceptance gates**:
  - File row count: expect ~6,500 subdistricts nationally (per LGD documentation). Loud-fail < 5,000 or > 8,000.
  - Sidecar `sources.json` carries a `source_id` rooted at the LGD Authority + date token.
  - Tier-A schema-sanity test asserts header shape: `S.No., State Code, District Code, Sub-District Code, Sub-District Name (In English), Sub-District Name (In Local), Census 2011 Code, ...`.
  - **No frontend consumer in this sub-phase** — the CSV is read by Phase B + 0.3 only.

### 0.2 — District backfill (639 rows → `entities.json`)

- **What ships**: hand-curated extension of `datasets/taxonomy/entities.json` to cover the remaining 639 districts in `districts-latest.csv`. Each new row carries `entity_id` = `IN-S{nn}-D{lgd_code}` (the existing convention, e.g. `IN-S22-D568` for Chennai), `entity_type="district"`, `lgd_code` from the CSV, `display_name` from the CSV, `parent_entity_id` = parent state. `legacy_id` (the wikipedia 3-letter code) stays NULL for non-ECI-mapped districts — it's an optional ECI-cross-reference column, not a primary identifier.
- **Tooling**: small generator script (~50 lines) `tools/lgd/backfill_entities_districts.py` (NEW) that reads `districts-latest.csv`, diffs against `entities.json#/entities`, emits a JSON patch the operator hand-reviews + commits. The output is deterministic so the patch is small (only the 639 net-new rows).
- **Why hand-review**: per [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md), `entities.json` is hand-curated; the generator suggests rows but the operator confirms display names (some LGD names have casing / hyphenation quirks we want to normalise) and assigns `entity_valid_from` (default to 1947 for pre-existing, current year for recent carve-outs).
- **Acceptance gates**:
  - All 639 new rows carry `lgd_code` (the existing `test_compile_skips_districts_without_lgd_code` enforces no-row-without-code at compile time).
  - `entities.json` row count goes from 185 to 824 (185 + 639).
  - `entities.parquet` compile is deterministic and byte-stable on re-run.
  - `python -m yen_gov validate --root .` is OK.
  - No frontend consumer changes (state-hub pages today don't list districts; adding them is a separate Jony PR).

### 0.3 — Subdistrict seed into `entities.json` (DEFERRED to Phase B)

- The first user-visible reason to add `entity_type="subdistrict"` rows to `entities.json` is when Phase B emits per-state subdistrict geojsons that need an entity FK target. **Defer**: ship Phase 0.1 + 0.2 first; Phase B adds subdistrict entity rows as part of its own ingest PR (likely a separate sub-phase B.1).

### 0.4 — Simplify existing national boundary files (Jony + Fowler joint, blocks D.0)

- **Why this sub-phase exists**: every "national" file on disk today exceeds the 500 KB gzipped per-fetch ceiling by 3–5× (see "Boundary file-size policy" above). This makes patchy-4G page-load wall-clock unnecessarily painful TODAY, and it will get worse once the Phase D.0 + D.6 survey-grade swaps inflate raw vertex counts.
- **What ships**: a new `tools/boundaries/simplify.py` (~80 lines) that wraps Shapely's [`simplify(tolerance, preserve_topology=True)`](https://shapely.readthedocs.io/en/stable/reference/shapely.simplify.html) (or [`mapshaper`](https://github.com/mbloch/mapshaper) CLI if Shapely's tolerance behavior at very low values is unstable for our coastlines). Runs per-layer at the tolerance specified in the per-layer table above. Emits in place. Deterministic on re-run.
- **Acceptance gates**:
  - Run on existing `country`, `states`, `districts`, `pc/delim=2024`, `subdistricts/state=in_s22`, all AC per-state, all village per-district files.
  - Every resulting file ≤ 500 KB gzipped (measure with `gzip -c | wc -c`).
  - Vitest contract: extend [`frontend/src/contracts/boundaries-conform.test.ts`](../frontend/src/contracts/boundaries-conform.test.ts) to fail the build if any boundary file exceeds the per-layer gzipped ceiling.
  - **§13 browser smoke**: home choropleth + 3 state hubs (TN/KL/BR) + 1 district drill (TN district 568) all render visually indistinguishable at India / state / district zoom levels. Pixel-level diffs at coastlines are expected and acceptable at the simplification tolerance; missing polygons or visible jagged edges at viewport zoom are not.
  - Tier-A + Tier-B + svelte-check pass.
- **Independent of 0.1 + 0.2**: can ship as its own PR before or after the LGD CSV ingest.

---

## Phase A — Pincode (lookup table → then polygons)

**Why this phase exists**: pincode is the only common spatial vocabulary an Indian citizen volunteers ("my pincode is 600028"); it is an orthogonal *search-only* layer per [`boundaries.md` §"Postal"](../docs/architecture/data/boundaries.md#postal-pincode--search-only-orthogonal-layer). The structural surface (schema, loader, `boundaryRelPath("postal")`) already landed; only ingest remains.

**Use the existing adapter, don't build a new one.** [`backend/yen_gov/sources/datagovin_ogd/`](../backend/yen_gov/sources/datagovin_ogd/) already ships the **operator-CSV-cache** pattern for data.gov.in resources — pin a `ResourceMeta` in [`urls.py`](../backend/yen_gov/sources/datagovin_ogd/urls.py), operator runs the one-time captcha-solve and drops the CSV under `.runtime/raw/datagovin/<leaf>.csv`, ingest reads from the cache thereafter. Proven on `fiscal/centre_transfers_gross`. **Do NOT build a new HTTP client**; do NOT use the OGD JSON API ([`urls.py` docstring](../backend/yen_gov/sources/datagovin_ogd/urls.py) explains why: demo key caps at 10 rows/request, 429s after a few pages, real keys gated on SMS-OTP we cannot script).

### A.1 — Pincode directory CSV (citizen lookup table, ~165k rows)

- **Primary source — `pincode-directory` (NEW)**: Department of Posts (issuing authority, **gold** tier), via data.gov.in [`all-india-pincode-directory-till-last-month`](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month). Monthly cadence, GODL-IN, CSV. Columns: `circlename, regionname, divisionname, officename, pincode`. This is **the** authoritative directory — every Post Office row keyed by pincode. Use it as the canonical pincode lookup.
- **Resource UUID discovery**: run [`tools/datagovin_recon.py all-india-pincode-directory-till-last-month`](../tools/datagovin_recon.py) — emits the resource UUID + download URLs by scraping the portal page (data.gov.in builds pages client-side; UUIDs live in the inline JS). Pin the result in [`backend/yen_gov/sources/datagovin_ogd/urls.py`](../backend/yen_gov/sources/datagovin_ogd/urls.py) as a new `ResourceMeta`.
- **What ships**:
  - One operator-captcha-fetched CSV cached at `.runtime/raw/datagovin/pincode_directory.csv` (ephemeral per [`CLAUDE.md §2`](../CLAUDE.md), not committed).
  - Emitted reference table at `datasets/reference/in/pincodes/pincode-directory.csv` (+ companion `pincode-directory-YYYY-MM.csv` immutable snapshot following the LGD dated+latest shape from [PR #73](../docs/reference/lgd-opendata.md)). **NOT** under `datasets/indicators/` — pincode is reference data, not an indicator.
  - New schema `datasets/schemas/pincode-directory.schema.json` v1.0 validating columns + `source_id` FK.
  - One row added to `datasets/taxonomy/sources.parquet` via `backend.yen_gov.canonical.citation.derive_source_id` (producer="Department of Posts (Ministry of Communications)", title="All India Pincode Directory", vintage="<YYYY-MM>", license=`OGL-IN-1.0` if our enum permits OR `unknown-public` until clarified — verify against [§12 enum](../CLAUDE.md), GODL-IN may need adding).
- **Supplementary — LGD pincode tables (DEFER, lower priority)**: [`ramseraph.github.io/opendata/lgd/`](https://ramseraph.github.io/opendata/lgd/) `pincode_urban.<DDMmmYYYY>.csv.7z` + `pincode_villages.<DDMmmYYYY>.csv.7z` map pincode → ULB/village `lgd_code`. **Only adopt if Phase D / Phase B exposes a need for the LGD-code join**; the Dept of Posts directory above is sufficient for the citizen-volunteers-their-pincode use case. When/if adopted, output to `datasets/taxonomy/lgd/pincode-urban.csv` + `pincode-villages.csv` via `tools/lgd/snapshot.py` (existing tool, NOT a new one).
- **Acceptance gates**:
  - Tier-A schema sanity (`pytest -q`): new `pincode-directory.schema.json` validates against JSON Schema 2020-12 meta; new `backend/tests/test_sources_datagovin_ogd_pincode.py` exercises the parser against a 5-row fixture.
  - Tier-B corpus conformance (`python -m yen_gov validate --root .`): the emitted CSV round-trips through the schema.
  - Row-count sanity: ~165k rows expected (every Post Office in India). Loud-fail if <100k or >300k.
  - Provenance: emitted CSV row count = sum across `circlename` partitions = same as upstream CSV row count modulo deduplication on `(officename, pincode)`.
  - **No frontend consumer in this sub-phase** — A.1 is a backend-only data drop. §13 browser smoke not required.

### A.2 — National pincode polygons

- **What ships**: `datasets/boundaries/in/postal/IN-pincodes-<region>.geojson` shards conforming to the existing `postal` schema; ledger row(s) in `boundary_layers.parquet`.
- **Source candidates** (pick one per first-snapshot recon):
  1. ramSeraph [`indian_cadastrals#postal`](https://github.com/ramSeraph/indian_cadastrals/releases/tag/postal) — `PincodeBoundaries.geojsonl.7z` (PostalGIS lineage, CC0-1.0). **Coverage gap**: missing HP, J&K, Sikkim, ML, MZ, MN, NL, AR (8 states/UTs).
  2. Same release — `Datagov_Pincode_Boundaries.geojsonl.7z` (data.gov.in lineage, GODL-IN). **All-India coverage**, but lower granularity in some urban areas.
  3. Same release — `GSDL_Pincodes.geojsonl.7z` (Geospatial Delhi Limited, CC0-1.0). **Delhi only**, but per-sub-locality granularity. Pair with #1 or #2 for the rest of India.
- **Recommended split**: adopt #1 (PostalGIS) as the primary national source + #3 (GSDL) for Delhi; fall back to district polygons for the 8 missing states. Avoids GODL-vs-CC0 license mixing and keeps the granularity story consistent.
- **Tooling**: extend `tools/boundaries/snapshot.py` — `geojsonl_7z` dispatch path already exists. Add the source to `tools/boundaries/pipeline.json#inputs[]` with `kind=postal`, `state_filter` not used (national).
- **Acceptance gates**:
  - Tier-A schema sanity: pincode `postal` geometry validates against the existing schema.
  - Tier-B corpus conformance: ledger row(s) carry `level=postal`, valid `source_id` FK.
  - File-size budget: per-shard ≤ 8 MB gzipped (boundaries.budget.test.ts). If the national pincode file exceeds, split by state-prefix (pincode 6 → first digit gives region) into 9 shards.
  - Frontend boundaries contract test (`frontend/src/contracts/boundaries-conform.test.ts`) passes.
  - §13 browser smoke: ONLY if a consumer surface exists. A.2 alone has no UI consumer — defer §13 smoke until the search affordance lands as a separate PR.

### A.3 — (Future, NOT this plan) Search affordance UI

- Out of scope here. Pincode → "this is your district / AC / PC" surface is a separate Jony + Citizen PR after A.1 + A.2 land.

---

## Phase B — Sub-district national lift

**What ships**: extend the existing sub-district adoption (TN-only today, 300 features) to all 36 states/UTs.

- **Source**: ramSeraph [`indian_admin_boundaries#subdistricts`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/subdistricts) — `LGD_Subdistricts.geojsonl.7z`. Already in [`tools/boundaries/pipeline.json#inputs[]`](../tools/boundaries/pipeline.json) with `state_filter` scoping to `S22`.
- **Mechanics**: remove the `state_filter` (or replace with the full list of 36 codes), re-run `tools/boundaries/snapshot.py --kind subdistrict`, verify all states emit.
- **Acceptance gates**:
  - Ledger row count: 36 `level=subdistrict` shards (one per state partition), not 1.
  - Per-state retained-feature counts non-zero; loud-fail any state with 0 retained features (probably a name-normalisation bug).
  - File-size budget: per-shard ≤ 8 MB gzipped. Large states (UP, MH, RJ) may need a `split_by=district` partition if they exceed.
  - Tier-B corpus conformance passes against the existing `boundary_layers.parquet` schema (no schema bump needed — additive ledger rows only).
  - §13 browser smoke: open any state hub page that already uses the subdistrict layer (if any) and verify it still renders. If no consumer surface exists yet, skip §13 — schema gates are sufficient.

---

## Phase C — Village national lift

**What ships**: extend village adoption (TN-only today, 38 districts) to all states for which ramSeraph publishes village geometry.

- **Source**: ramSeraph [`indian_admin_boundaries#villages`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/villages) — `LGD_Villages.geojsonl.7z`. **Upstream coverage gap**: HP, J&K, Sikkim, ML, MZ, MN, NL, AR are missing. Fall-back files in the same release: `bhuvan_villages.geojsonl.7z` (broad coverage) + `Bhuvan_JK_Villages.geojsonl.7z` (J&K-specific). License chain identical to other LGD files.
- **Mechanics**: same pattern as Phase B but with `split_by=district` enforced from the start (village geometry is the largest layer).
- **Pre-flight**: snapshot once into `.runtime/raw/ramseraph/villages/`, run `du -sh` per state, confirm largest state shard ≤ 8 MB gzipped after default simplification. If not, tighten `simplification_tolerance_deg` for villages above other layers' default.
- **Acceptance gates**:
  - Ledger row count: ~28 states' worth of `level=village` partitions (3 dozen states minus the 8 missing). Each state-partition further sliced by district per the existing TN pattern (~600 districts nationally → ~600 shards).
  - Per-state coverage report: file a recon note in `notes/` for the 8 missing states (do they need bhuvan fall-back, or is "no village layer for state X" acceptable for now?).
  - Tier-B corpus conformance passes.
  - File-size budget: every shard ≤ 8 MB gzipped (the binding constraint here).
  - No frontend smoke required unless a village-aware consumer ships in the same PR.

---

## Phase D — Survey-grade swap to ramSeraph BharatMaps lineage (states + AC + PC)

**Direction approved by user (2026-05-24)**: where ramSeraph publishes a survey-grade BharatMaps polygon for a layer we currently source from a non-survey-grade lineage (DataMeet, HTL, shijithpk), swap to ramSeraph. The gap-fill-not-bulk-swap policy ([`boundary-data-sources.md`](../docs/reference/boundary-data-sources.md#why-these-choices)) is **overridden** for this phase specifically because the upgrade is a citizen-visible quality lift (sub-meter survey vector vs hand-traced QGIS approximation) plus a code-system alignment (everything keyed by `lgd_code` post-swap). Pre-existing override of "no functional gain" framing logged here as the rationale anchor.

ramSeraph BharatMaps lineage applies to three layers we use today:
- `LGD_States` (Phase D.0) — replaces DataMeet `Admin2`.
- `LGD_Assembly_Constituencies` (Phase D.1–D.5) — replaces HTL per-state + shijithpk J&K.
- `LGD_Parliament_Constituencies` (Phase D.6) — replaces shijithpk 2024_maps_supplement.

Districts + sub-districts + villages are ALREADY on the ramSeraph LGD lineage (Phases B + C ingest them); no swap needed there.

### D.0 — State polygon swap (DataMeet → ramSeraph `LGD_States`)

- **What ships**: `INDIA_STATES.geojson_url` in [`frontend/src/lib/maps/sources.ts`](../frontend/src/lib/maps/sources.ts) repointed from the DataMeet `Admin2` file to a ramSeraph-derived `LGD_States.geojsonl.7z` shard converted to per-feature GeoJSON. `INDIA_STATES.join_property` changes from `ST_NM` to whatever the ramSeraph file carries (likely `state_lgd_code` or `STATE`; D.0 recon resolves it). New `lgdCodeToEci(lgdCode)` view-model helper in [`frontend/src/lib/view-models/states.ts`](../frontend/src/lib/view-models/states.ts) wraps the existing `taxonomy.entities` DuckDB-WASM query (the same Parquet that already powers `eciFromStateName`). The 3-entry `boundary_join_name` override map (Andaman & Nicobar, Delhi, J&K) re-validates against the new source's name strings — expect to drop most/all overrides because the LGD source uses canonical names.
- **Why this is technically trivial**: T.0e already retired the old `STATE_NAME_TO_ECI` constant in favour of a DuckDB-WASM lookup against `datasets/taxonomy/entities.parquet`, and that Parquet carries all three code systems (`legacy_id`=`S22`, `lgd_code`=`33`, `iso_3166_2`=`IN-TN`) on every state row. The swap is a property repoint + a new view-model helper, not a data migration.
- **Tooling**: add a `kind=state` entry to [`tools/boundaries/pipeline.json`](../tools/boundaries/pipeline.json) pointing at ramSeraph `LGD_States.geojsonl.7z` (released alongside `LGD_Districts`); run `tools/boundaries/snapshot.py --kind state` to emit `datasets/boundaries/in/state/IN-states.geojson` (single national file, ~120 KB gzipped).
- **Acceptance gates**:
  - File row count: 36 (28 states + 8 UTs) features in the emitted GeoJSON. Loud-fail any other number.
  - Every feature carries `lgd_code` resolvable to a row in `taxonomy.entities` via `lgdCodeToEci`. Vitest contract: `boundaries-conform.test.ts` extension asserts FK resolution for all 36.
  - **Per-shard size ceiling (HARD GATE)**: `states/all.geojson` ≤ 200 KB gzipped after Douglas-Peucker simplification at ~0.002° tolerance (per ["Boundary file-size policy"](#boundary-file-size-policy-jony--fowler-joint-2026-05-24) above). Survey-grade raw will likely be 5–10 MB pre-simplification — D-P is non-negotiable, not optional. Use `tools/boundaries/simplify.py` (Phase 0.4).
  - Existing `frontend/src/contracts/boundaries-conform.test.ts` still passes (schema unchanged; just data source change).
  - **§13 browser smoke (mandatory)**: open the national choropleth (e.g. `/`, `/t/elections`) on a state-keyed indicator, verify all 36 states/UTs render coloured, no console warnings about "unknown state", no white-tile gaps. Compare visually against pre-swap screenshot — expect pixel-level changes at coastlines + disputed borders (survey-grade vs DataMeet trace), but no missing or mis-coloured states.
  - Tier-B corpus conformance OK.
- **Independent of D.1–D.5**: state geometry has no dependency on AC consolidation; can ship as a standalone PR before or after the AC recon. **Depends on Phase 0.4** if the simplifier tool isn't already in tree.

### D.1 — First-snapshot recon (one-shot, gating)

- **What ships**: a recon note in `notes/` (NOT a code PR) recording:
  - The exact property schema of `LGD_Assembly_Constituencies.geojsonl.7z` features (does it carry `lgd_ac_code`? `AC_NO`? `state_code`? `ac_name`?). The catalogue page does not enumerate these; we need to look at the file.
  - The vintage anchor: does the file reflect Assam 2023 re-delim (still 126 ACs but new boundaries) and J&K 2022 re-delim (90 ACs)? Compare counts per state against `datasets/reference/in/states/S{nn}/constituencies.json`.
  - Per-state retained-feature count + total (should be ~4,123 ACs nationally pre-2026).
- **Tooling**: `tools/boundaries/snapshot.py --source constituencies --kind ac` lands the file into `.runtime/raw/ramseraph/constituencies/`; recon is then a manual jq/python inspection per [§2 path rule](../CLAUDE.md#2-path-rules-mandatory) (`.runtime/` is ephemeral; do not reference its paths from anything committed). The recon note may quote findings; it must not link to the raw file path.
- **Acceptance gate (the gating decision for D.2+)**: a yes/no per state. The note must answer: "For state S{nn}, does ramSeraph LGD AC count + names match the source-of-truth `constituencies.json`?" If yes → eligible for promotion in D.2+. If no → flag for individual investigation, keep current source (HTL or shijithpk).

### D.2 — Promote the obvious matches (28 states under 2008 delim)

- **Scope**: every state currently sourced from HTL where D.1 confirms LGD parity.
- **What ships**: replace the per-state HTL entry in [`pipeline.json`](../tools/boundaries/pipeline.json) with a ramSeraph entry sliced by state from the national LGD file; re-run snapshot; verify ledger row count is identical to today (still 1 file per state); citizen-visible map unchanged.
- **Mechanics**: ramSeraph publishes a single national file, but our ledger keeps the per-state-file granularity (cleaner for cache invalidation + per-state map loads). Use a `split_by=state` directive in `pipeline.json` (already supported per `tools/boundaries/snapshot.py`).
- **Acceptance gates per state**:
  - Per-state `AC_NO` (or `lgd_ac_code`) coverage 100% vs the SoT `constituencies.json` — `tools/boundaries/verify_ac_parity.py` (write this script) emits a coverage report.
  - Name-match coverage ≥ 95% (allow 5% Latin/diacritic noise); manual review of mismatches.
  - File-size budget passes.
  - §13 browser smoke on the affected state's election page: choropleth renders, no console errors, no 404s.

### D.3 — Assam (S03) — special case

- **Gate**: D.1 must answer whether LGD reflects 2023 Assam re-delim. Three outcomes:
  1. **LGD has 2023 delim** → swap S03 to ramSeraph (resolves the long-standing delimitation warning in `pipeline.json`).
  2. **LGD has pre-2023 delim** (same as HTL) → no swap value; keep HTL; the delimitation warning stays open.
  3. **Mixed / unclear** → file an open question for Hans + Max + Fowler; do not swap.

### D.4 — J&K (U08) — special case

- **Gate**: D.1 must answer whether LGD has the 90-AC 2022 re-delim layout (current shijithpk source has it). Three outcomes mirror D.3.
  - If LGD = 90 ACs with names matching `datasets/reference/in/states/U08/constituencies.json` → swap U08 from shijithpk to ramSeraph (cleaner license, stable LGD codes).
  - If LGD still has 87 (pre-statehood) ACs → keep shijithpk.

### D.5 — Wrap-up (AC consolidation)

- Update [`boundary-data-sources.md`](../docs/reference/boundary-data-sources.md) inventory table to reflect each promoted state's new producer.
- Update [`docs/architecture/decisions/0031-boundary-geometry-strategy.md`](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) with a 2026-Q3 (or whenever Phase D lands) amendment recording the consolidation outcome per state.
- Refresh `boundary_layers.parquet` ledger; `source_id` on every promoted row points at the ramSeraph `LGD_Assembly_Constituencies` row in `datasets/taxonomy/sources.parquet`.

### D.6 — PC polygon swap (shijithpk → ramSeraph `LGD_Parliament_Constituencies`)

- **What ships**: `pc` layer in [`pipeline.json`](../tools/boundaries/pipeline.json) repointed from `shijithpk/2024_maps_supplement` (Unlicense, GIS-traced in QGIS over the 2024 delim PDF) to ramSeraph `LGD_Parliament_Constituencies.geojsonl.7z` (CC0-1.0, BharatMaps survey-grade). Single national file, ~545 features expected (the 2024 delim count).
- **Recon gate (D.6 prerequisite)**: snapshot once; verify ramSeraph file reflects the 2024 General Election delimitation (post-Jammu UT + post-Telangana). If the LGD file is pre-2024 delim (still 543 PCs with pre-delim boundaries), DO NOT swap — keep shijithpk until LGD catches up.
- **Acceptance gates**:
  - PC feature count = 545 (±1 for J&K / Ladakh boundary edge cases — manually inspect).
  - Every feature carries `lgd_pc_code`; vitest FK-resolution test against `taxonomy.entities` (once PC entities seed lands as a separate dependency — this may push D.6 behind a Phase 0 sub-task).
  - **Per-shard size ceiling (HARD GATE)**: `pc/delim=2024/all.geojson` ≤ 500 KB gzipped after Douglas-Peucker simplification at ~0.001° tolerance (per ["Boundary file-size policy"](#boundary-file-size-policy-jony--fowler-joint-2026-05-24) above). Survey-grade raw will likely be 10–20 MB pre-simplification (vs today's 8.5 MB raw / 1.5 MB gzipped shijithpk file). If still > 500 KB after D-P, shard by state (`pc/delim=2024/state=<s>/all.geojson`) — that's a renderer change in [`frontend/src/lib/maps/sources.ts`](../frontend/src/lib/maps/sources.ts) + view-models, scope it in the same PR.
  - §13 browser smoke on any PC-keyed indicator surface (today: limited; revisit when a Lok Sabha cycle's tracker ships).
- **Independent of D.0–D.5**: can ship as a standalone PR; no AC consolidation dependency. **Depends on Phase 0.4** if the simplifier tool isn't already in tree.

---

## Phase E — Census-2011 polygon layer (DESCOPED, narrowed to district+subdistrict cross-check)

**Decision (user, 2026-05-24)**: descope Census-2011 villages. The `Census_Villages` release is **points, not polygons** — we are a choropleth-first site and points don't render as administrative shapes. Don't adopt.

**What remains useful**: `Districts_2011` + `SubDistricts_2011` polygons exist as a **cross-check oracle** for Phase B (sub-district national lift). They are CC0-1.0 and frozen at Census-2011 vintage — useful to catch any major boundary drift between LGD/BharatMaps (Phase B source) and the canonical Census reference.

- **If/when first Census-2011 indicator ships** (deferred trigger): adopt `Districts_2011.geojsonl.7z` + `SubDistricts_2011.geojsonl.7z` ONLY (the two polygon files, CC0-1.0). Store under `datasets/boundaries/in/<level>/vintage=2011/` (Hive partition extension) — vintage is a property, not a sibling kind. **No `Census_Villages` ingest.**
- **PC11_TV_DIR.csv.7z** (Census-2011 town + village name directory): catalogue only; useful for entity-name cross-referencing if/when a 2011-vintage indicator wants to disambiguate village names against modern LGD names.
- **SHRUG variants** (`shrug-district-pc11`, `shrug-subdistrict-pc11`, `shrug-village-pc11`) are **CC-BY-NC-SA 4.0 — NON-COMMERCIAL**, NOT safe for redistribution from our static bundle. **Do not adopt under any conditions.**
- **No tooling work until trigger fires.** The cross-check use in Phase B (verifying LGD subdistrict counts against Census-2011) happens at-need with a one-off recon script, not as a permanent shard on disk.

---

## Cross-cutting validation (every phase)

Every phase PR must pass:

1. **Tier-A schema sanity** (`pytest -q` in `backend/`): all schema invariants hold.
2. **Tier-B corpus conformance** (`python -m yen_gov validate --root .`): no Tier-B regressions.
3. **`backend/tests/`** loader tests for new data shapes (real fixtures per Holy Law #7 — no mocks except fetch boundary).
4. **`frontend/src/contracts/boundaries-conform.test.ts`** passes — the runtime ajv gate for what the frontend will fetch.
5. **`bun run test`** in `frontend/` is green at commit time (no "I'll add tests later").
6. **§13 browser smoke** when a UI surface changes; skip when phase is pure backend/data.
7. **No new mocks** unless user-requested.
8. **Lockfile sync** (Holy Law #9 + DoD): not applicable here since no `package.json` edits are anticipated. If a phase adds a new frontend dependency (unlikely), include the bun.lock regen.
9. **Provenance**: every new ledger row in `boundary_layers.parquet` carries a `source_id` FK to `datasets/taxonomy/sources.parquet`. Every new sources row uses the v2.0 citation-ledger shape ([ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md)).

---

## Open questions (TBD; promote into the relevant doc on resolution)

- **Phase A.1 output path**: `datasets/reference/in/pincodes/pincode-directory.csv` (proposed default — "reference data, not an indicator") vs `datasets/taxonomy/pincodes/...` (sibling to `taxonomy/entities.parquet`, treats pincode as a first-class taxonomy alongside states/districts/ACs) vs `datasets/postal/pincode_directory.parquet` (treats `postal` as its own family alongside `elections/`, `energy/`, `demography/`). Gregor + Max decision required — affects loader path, validator scope, and how Phase A.2 polygons cross-reference the directory. Recommend `datasets/reference/in/pincodes/` as the lowest-coupling default until Phase A.2 ships and a polygon×directory join is needed.
- **Phase A.1 license enum**: GODL-IN / `OGL-IN-1.0` is not in the current `sources.parquet` license enum (§12 lists `OGL-IN-1.0` — verify these are the same string). If not, either rename or extend the enum in the same PR.
- **Phase A.2 source choice**: PostalGIS (gap-having, CC0) vs data.gov.in (gap-free, GODL). Decision lands after first-snapshot recon comparing actual citizen-visible quality.
- **Phase C upstream gap**: HP / J&K / Sikkim / ML / MZ / MN / NL / AR are not in `LGD_Villages`. Acceptable as "no village layer for state X today", or pull `bhuvan_villages` as fall-back? Defer to first concrete consumer.
- **Phase D first-snapshot recon outcome**: whether `LGD_Assembly_Constituencies` carries 2023 Assam delim + 2022 J&K delim. Cannot answer without running the snapshot.
- **Phase D parity threshold**: name-match coverage ≥ 95% is a placeholder; the actual threshold lands after the first state's recon report shows what diacritic noise the LGD file carries.
- **Phase E trigger**: which Census-2011 indicator ships first? Out of scope of this plan to predict; the trigger is "first Census-derived choropleth consumer surface".

---

## Not in this plan (descoped)

- **GADM as a source**: hard NO. Disputed-territory polygons (5 of 41 features carry China/Pakistan-claimed slice IDs), non-commercial license blocking static-bundle redistribution, uses HASC codes not LGD/ECI, and is stale (no Ladakh split). Documented in [`boundary-data-sources.md` §"Why not GADM"](../docs/reference/boundary-data-sources.md) — do not re-litigate.
- **Bulk swap of all 28 HTL states onto ramSeraph in one PR**: violates the gap-fill-not-bulk-swap policy. Phase D.2 promotes only those states where the parity-check authorises it; the rest stay on HTL until they need refresh.
- **DIGIPIN (4 m × 4 m grid)**: not a polygon family; needs a separate point/grid handler. Not on the boundary-coverage roadmap.
- **Topographic raster basemaps** (`ramSeraph/india_topo_maps`): out of scope for the choropleth-rendering frontend per [`boundary-data-sources.md`](../docs/reference/boundary-data-sources.md).
- **Historical district decadal series** (`ramSeraph/indian_admin_boundaries#historical`): high-value catalogue (1941 → 2001 polygons + `District_Timeseries_1951-2024.csv` change-log + name-change / split / carve-out CSVs). Adopt when a methodology-break-aware trend visualisation ships per [`boundaries.md` §"Methodology breaks"](../docs/architecture/data/boundaries.md#methodology-breaks). Out of scope for this plan.
