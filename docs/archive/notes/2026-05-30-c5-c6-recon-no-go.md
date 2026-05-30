# C.5 LGD PC v2 + C.6 Susewind 2014 AP overlay — recon verdict (both NO-GO; closed without implementation)

**Date**: 2026-05-30
**Plan-doc rows**: C.5 + C.6 of [TODO/20260529-boundary-rip-and-replace-plan.md](../TODO/20260529-boundary-rip-and-replace-plan.md)
**Verdict**: BOTH NO-GO. C.5 reaffirms the prior D.6 NO-GO from 2026-05-25 (upstream byte-identical, all 4 structural findings still in force). C.6's stated precondition (B.1 confirms Susewind 2014 ships a 175-feature post-bifurcation AP-only shape) has been REFUTED by the 2026-05-29 B.1 verdict correction (Susewind 2014 actually ships 292 pre-bifurcation features at unified AP+TG numbering). Neither row warrants an implementation PR; both are closed via this recon.

## TL;DR

**C.5 (LGD PC v2 swap)**: REAFFIRM D.6 NO-GO. Today's probe of `LGD_Parliament_Constituencies.geojsonl.7z` returns 543 features (504 active + 39 pre-delim), byte-identical to D.6's 2026-05-25 verification (the upstream release date is `2023-12-12`; no commits since). All 4 D.6 NO-GO findings persist:
1. 6 entire states have ZERO active PC features (J&K=6/6, Arunachal=2/2, Nagaland=1/1, Manipur=2/2, Assam=14/14, Jharkhand=14/14 — total 39 pre-delim features that would silently drop from active coverage if adopted).
2. No LGD-grade PC identifier (only `pc_id`, which is unstable).
3. `pc_id` is a legacy frozen pre-2014 key (44 mismatches — Telangana 17 PCs use `28xx` AP prefix; Andhra Pradesh 25 PCs use `37xx`; Daman & Diu + Dadra & Nagar Haveli use `39xx` against st_code 38). A join keyed on `pc_id` would silently mis-attribute Telangana election results to Andhra Pradesh.
4. Feature count 543 vs the plan-doc's documented 545-precondition (rooted in shijithpk's 545-feature file which adds 2 J&K-territory placeholders with `ls_seat_code=999`). The shortfall is constitutional (104th Amendment abolished 2 Anglo-Indian seats), but combined with findings 1-3 the NO-GO holds.

The C.5 plan-doc row was authored on 2026-05-29 without awareness that D.6 ran this exact recon 4 days earlier. The row is a duplicate-of-D.6.

**C.6 (Susewind 2014 AP overlay)**: NO-GO on precondition failure. The C.6 row's gate text reads "if B.1 verdict confirms Susewind 2014 ships post-2014 175-feature AP-only shape AND ramSeraph LGD has cleaner coverage". The 2026-05-29 B.1 verdict correction ([notes/2026-05-29-phase-b-verdict-correction.md](2026-05-29-phase-b-verdict-correction.md)) REFUTES the first condition: Susewind 2014 ships 292 features under `state=='Andhra Pradesh'` at LEGACY PRE-bifurcation unified AP+TG numbering (`ac` field 1-294, first AC = "Sirpur" in Adilabad district which is Telangana side of the 2014 split). It is NOT a clean 175-feature post-bifurcation AP slice; never was. Without a Susewind 2014 AP-clean baseline, there is nothing for the overlay to cross-verify against. C.6 is closed without action; the Susewind 2014 file remains a known artefact in upstream but is NOT adopted.

## C.5 — full probe transcript

### Today's probe (re-run of D.6's recon driver shape)

Same upstream artefact D.6 verified:
- URL: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Parliament_Constituencies.geojsonl.7z`
- Upstream release date: 2023-12-12 (commit `ac724c2` on `constituencies` tag; no commits since)
- Archive `fetched_at`: 2026-05-30T02:45:17Z
- Feature count: 543

**Status distribution by state** (filtering on `status=" "` for active vs `status="Pre delimitation"` for legacy):

| State_LGD | st_name | total | active | pre_delim | Zero-active? |
|---:|---|---:|---:|---:|---|
| 1 | JAMMU & KASHMIR | 6 | **0** | 6 | YES |
| 2 | HIMACHAL PRADESH | 4 | 4 | 0 | - |
| 3 | PUNJAB | 13 | 13 | 0 | - |
| 4 | CHANDIGARH | 1 | 1 | 0 | - |
| 5 | UTTARAKHAND | 5 | 5 | 0 | - |
| 6 | HARYANA | 10 | 10 | 0 | - |
| 7 | DELHI | 7 | 7 | 0 | - |
| 8 | RAJASTHAN | 25 | 25 | 0 | - |
| 9 | UTTAR PRADESH | 80 | 80 | 0 | - |
| 10 | BIHAR | 40 | 40 | 0 | - |
| 11 | SIKKIM | 1 | 1 | 0 | - |
| 12 | ARUNACHAL PRADESH | 2 | **0** | 2 | YES |
| 13 | NAGALAND | 1 | **0** | 1 | YES |
| 14 | MANIPUR | 2 | **0** | 2 | YES |
| 15 | MIZORAM | 1 | 1 | 0 | - |
| 16 | TRIPURA | 2 | 2 | 0 | - |
| 17 | MEGHALAYA | 2 | 2 | 0 | - |
| 18 | ASSAM | 14 | **0** | 14 | YES |
| 19 | WEST BENGAL | 42 | 42 | 0 | - |
| 20 | JHARKHAND | 14 | **0** | 14 | YES |
| 21 | ORISSA | 21 | 21 | 0 | - |
| 22 | CHHATTISGARH | 11 | 11 | 0 | - |
| 23 | MADHYA PRADESH | 29 | 29 | 0 | - |
| 24 | GUJARAT | 26 | 26 | 0 | - |
| 27 | MAHARASHTRA | 48 | 48 | 0 | - |
| 28 | ANDHRA PRADESH | 25 | 25 | 0 | - |
| 29 | KARNATAKA | 28 | 28 | 0 | - |
| 30 | GOA | 2 | 2 | 0 | - |
| 31 | LAKSHADWEEP | 1 | 1 | 0 | - |
| 32 | KERALA | 20 | 20 | 0 | - |
| 33 | TAMIL NADU | 39 | 39 | 0 | - |
| 34 | PUDUCHERRY | 1 | 1 | 0 | - |
| 35 | ANDAMAN & NICOBAR | 1 | 1 | 0 | - |
| 36 | TELANGANA | 17 | 17 | 0 | - |
| 38 | DAMAN & DIU | 1 | 1 | 0 | - |
| 38 | DADRA & NAGAR HAVELI | 1 | 1 | 0 | - |
| **TOTAL** | | **543** | **504** | **39** | **6 zero-active states** |

D.6 reported `active=504 pre_delim=39 total=543` and identified the same 6 zero-active states (J&K=6, Arunachal=2, Nagaland=1, Manipur=2, Assam=14, Jharkhand=14 = 39). **Byte-identical reproduction confirmed.**

### `pc_id` legacy-prefix mismatch breakdown

`pc_id == st_code * 100 + pc_no`? **44 mismatches**:

| st_code | st_name | mismatched pc_ids |
|---|---|---:|
| 37 | ANDHRA PRADESH | 25 |
| 36 | TELANGANA | 17 |
| 39 | DAMAN & DIU | 1 |
| 39 | DADRA & NAGAR HAVELI | 1 |

(D.6 reported 44 mismatches via Telangana drift; today's breakdown adds AP, Daman & Diu, and D&NH drift detail. All represent legacy frozen pre-bifurcation / pre-merger codes that would mis-key joins.)

### Property keys (full set, 12 keys)

`OBJECTID`, `Shape_Area`, `Shape_Length`, `State_LGD`, `pc_id`, `pc_name`, `pc_no`, `st_area_sh`, `st_code`, `st_length_`, `st_name`, `status`

No `lgd_pc_code` / `pc_lgd` / `pclgd` / any LGD-grade PC identifier. D.6's finding 3 confirmed.

### Re-evaluation triggers (unchanged from D.6)

Re-open C.5 when ANY of these flips upstream:
- ramSeraph publishes a release where the 6 structural-gap states (J&K, Arunachal, Nagaland, Manipur, Assam, Jharkhand) all have `status=" "` (active) features.
- An LGD-grade PC identifier (`lgd_pc_code` or equivalent stable code) is added.
- The Telangana / AP / Daman & Diu / D&NH `pc_id` drift is rewritten to use state-correct prefixes.
- A new upstream maintainer publishes an LGD-keyed PC release with `delim=2024` and 543 active features.

The D.6 recon driver script `tools/boundaries/recon_d6_pc.py` is kept in-tree as the re-evaluation trigger; re-run it when any of the above flips.

## C.6 — precondition failed per B.1 correction

The C.6 row's gate language:

> if B.1 verdict confirms Susewind 2014 ships post-2014 175-feature AP-only shape AND ramSeraph LGD has cleaner coverage, Susewind 2014 lives at `boundaries/in/ac/state=in_s01/_susewind2014/all.geojson` as a v2 cross-verification source

Per [notes/2026-05-29-phase-b-verdict-correction.md](2026-05-29-phase-b-verdict-correction.md), the actual Susewind 2014 AP slice contains:
- **292 features** under `state=='Andhra Pradesh'` (NOT 175)
- numbered `ac` 1-294 in LEGACY PRE-bifurcation unified AP+TG scheme (Sirpur is `ac=1` and lives in Adilabad district which is Telangana side of the 2014 split)
- property keys `state` / `pc` / `pc_name` / `ac` / `ac_name` (all lowercase)
- delimitation vintage = 2008 Delimitation Commission Order with 2014 bifurcation NOT applied to the geometry/numbering

Susewind 2014's AP slice is therefore a PRE-bifurcation snapshot, not a clean post-bifurcation 175-AP-only overlay. There is no transformation in the Susewind 2014 release that yields the 175-feature shape — the geometry was authored before the 2014 bifurcation as a single unified AP+TG canvas; carving out the 175 modern AP polygons would require boundary surgery against the Adilabad / Nizamabad / Karimnagar / Warangal / Khammam / Mahbubnagar / Nalgonda / Hyderabad / Ranga Reddy / Medak district lines that became the Telangana state — work that is structurally outside Susewind 2014's authoring scope.

**Net**: C.6's first condition is unsatisfiable on the existing Susewind 2014 file. The second condition ("ramSeraph LGD has cleaner coverage") was answered TRUE by B.1's correction (LGD's 178-feature AP slice via `State_LGD=28 AND st_name='ANDHRA PRADESH'` filter + name-rewrite produces a clean 175-AP modern shape — this IS the source for A.1.a). But "cleaner" is comparative — there is no Susewind 2014 175-feature baseline to compare against, so the whole overlay premise dissolves.

The Susewind 2014 file is NOT adopted at any path under `datasets/boundaries/in/ac/state=in_s01/_susewind2014/`. If a future re-evaluation surfaces the need for a pre-bifurcation unified AP+TG cross-verification source (e.g. for a 2009 GE choropleth), it would be sourced separately and probably under a different partition (e.g. `_pre2014_unified_ap/`); this is not in any current plan-doc row.

## What this PR ships

1. **This recon note** — single consolidated verdict closing both C.5 and C.6.
2. **Plan-doc C.5 row update**: status `Closed (REAFFIRMS D.6 NO-GO)`, link here, link back to D.6 recon note.
3. **Plan-doc C.6 row update**: status `Closed (PRECONDITION FAILED per B.1 correction)`, link here, link back to B.1 correction note.
4. **No pipeline.json change** (no source adopted in either case; existing shijithpk PC stanza unchanged).
5. **No datasets change** (no boundaries snapshot run; no parquet update).
6. **No frontend change** (no STATE_AC entry, no GeoLevel extension; PC layer has no frontend consumer today).
7. **No test change** (no contract test affected; no new source row in sources.parquet).

## Why bundle C.5 + C.6 into one PR

Both rows close as recon-only NO-GOs from already-known upstream findings (D.6 for C.5; B.1 correction for C.6). Each independently warrants a thin closure PR; bundling halves merge ceremony cost without conflating doctrine (both are "Phase C upstream-not-fit-for-purpose" closures). Pattern lineage: PR #290 (Phase D.7 R1 single-PR-with-20-state-decisions) + PR #296 (single-PR-with-3-subagent-verdicts) — same-doctrine multi-row closures merge cleanly when each closure's reasoning is independently legible.

## Out of scope

- Re-running D.6's `recon_d6_pc.py` (today's probe is functionally equivalent; D.6 driver still in-tree as the re-evaluation trigger).
- Removing the C.5 / C.6 rows from the plan-doc (closed-with-status is the more durable record than row deletion; future readers can see WHY each row closed without git-spelunking).
- Re-evaluating shijithpk's stability (no signal from upstream; the existing layer at `datasets/ephemeral/india_ls_seats_545.geojson` remains the working source).
- Pursuing alternative LGD-grade PC sources (no Tier-1 candidate currently exists; the BharatMaps `AC_PC/MapServer/1` direct API requires LGD govt-portal access and would not be a stable mirror).
- Pursuing a pre-bifurcation unified AP+TG layer (Susewind 2014 IS that layer, but there is no current citizen need for that vintage; deferred indefinitely).

## References

- D.6 PC recon (2026-05-25, the prior NO-GO that C.5 reaffirms): [notes/2026-05-25-d6-pc-recon.md](2026-05-25-d6-pc-recon.md)
- B.1 + B.2 verdict correction (2026-05-29, the source for C.6's precondition refutation): [notes/2026-05-29-phase-b-verdict-correction.md](2026-05-29-phase-b-verdict-correction.md)
- Plan-doc rows being closed: [TODO/20260529-boundary-rip-and-replace-plan.md](../TODO/20260529-boundary-rip-and-replace-plan.md) §C.5 + §C.6
- ramSeraph constituencies release tag: https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/constituencies
- Current shijithpk PC stanza (UNCHANGED by this PR): `tools/boundaries/pipeline.json` lines 1111-1138
- ADR-0031 (records the D.6 PC vintage-gate decision; not amended in this PR — D.6's amendment stands)
