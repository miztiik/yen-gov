# Plan: LGD-canonical alignment (state/district/AC keys end-to-end)

**Status:** PROPOSED
**Author:** GitHub Copilot (orchestrator)
**Last Updated:** 2026-06-01
**Level:** 5 (cross-cutting; structural; touches partition layout, URLs, contracts, every indicator join)
**Supersedes:** `TODO/20260601-ac-coverage-to-100-plan.md` (which inherited ECI-keying assumptions; deferred Rows I2/I3/D1' fold into this plan)

## Mandate (rephrased from user, 2026-06-01)

> "When data.gov.in provides a dataset keyed to district id, that is most probably referenced by LGD data... if we use ECI state id then we are chasing tails for every indicator. This whole plan was eci-to-lgd to avoid that. I wanted to use garuda to fill our gaps and NOT inherit ECI as reference. If our filenaming s22/s11/s01 is wrong, lets fix that - perhaps state names or lgd identifiers. But we cant have piece meal of both."

## The strategic call (locked)

**LGD is the canonical internal join key for every geographic entity** (state, district, sub-district, panchayat, ULB, ULB ward, AC, PC).

- `lgd_state_id`, `lgd_district_id`, `lgd_ac_id`, `lgd_panchayat_id`, etc. are the only keys allowed on canonical-store rows.
- `eci_*` codes (ECI st_code, ECI ac_no, ECI pc_no) survive ONLY as election-domain display labels (URLs, badges) and as join-attributes on election artefacts.
- Garuda is **carrier of ECI-keyed AC geometry** (clean, complete except U08). Per AC feature it carries `st_name`, `ac_name`, ECI `st_code`, ECI `ac_no`, ECI-derived `ac_id`. **It does NOT carry LGD codes.** We use Garuda for geometry + ECI verification; LGD codes are stamped on top via a separate join.
- Folder labels (`in_s01`, `in_s12`, `in_u07`, ...) are an internal yen-gov invention that aligns with neither ECI nor LGD. They are retired in this plan.

## Why this is non-negotiable

Every non-electoral GoI indicator (data.gov.in, MoSPI NSO, NFHS, Census, NDLM AQ, RBI Handbook fiscal, Bhuvan landcover, etc.) keys on LGD identifiers via the LGD portal `https://lgdirectory.gov.in/`. Verified in-repo: `datasets/taxonomy/sources.parquet`, every existing `parent_district_lgd` / `State_LGD` / `lgd_ac_id` field, ADR-0049, and the existing `eci_no -> lgd_ac_id` migration arc PRs #530-#540 are all LGD-canonical by design.

If yen-gov adopts ECI as the canonical join key (the trap of PR #542's enrich-only approach), every future health/fiscal/agriculture/education indicator needs a per-indicator ECI<->LGD translation. That is the "chasing tails" tax the user named. We refuse it here.

## Status reckoner

| # | Description | Status | PR | Risk |
| :-: | --- | --- | --- | :-: |
| L0 | This plan-doc + sign-off | [ ] PENDING | _pending_ | L |
| L1 | Author `datasets/taxonomy/lgd_states.json` (37 states/UTs: lgd_state_id + lgd_name + slug). Author `datasets/taxonomy/lgd_districts.json` (~780 districts: lgd_district_id + lgd_state_id + lgd_name). Author `datasets/taxonomy/lgd_eci_state_map.json` (lgd_state_id <-> eci_st_code lookup). | [ ] PENDING | _pending_ | M |
| L2 | Decide folder-name convention. Two candidates: (a) `state=lgd06` (LGD ID, machine-stable); (b) `state=haryana` (LGD-name slug, human-readable). Plan-doc gate; non-PR. | [ ] PENDING (needs user pick) | _pending_ | L |
| L3 | Rename rip across `datasets/boundaries/in/{ac,pc,country,states,districts,...}` AND `datasets/elections/state=*` AND every Parquet partition key carrying `state_code`. Single big-bang script + recompile every artefact. Test contract for the new convention. | [ ] BLOCKED-on-L2 | _pending_ | XL |
| L4 | Frontend route migration: `/s/<old-slug>` -> `/s/<lgd-slug>` with redirect map for 6 months (saves citizen bookmarks). Update `StateAcMap`, `frontend/src/lib/routes.ts`, `golden-path.spec.ts`. | [ ] BLOCKED-on-L3 | _pending_ | L |
| AC1 | Replace boundary AC geometry from Garuda for all 30 covered states (single big-bang). Stamp `lgd_ac_id` per feature via LGD AC directory lookup (29 states' AC LGD codes are publicly listed; J&K post-2022 needs hand-stamp from delim notification annex). U08 from shijithpk file (90 ACs post-2022, `state_id="U08"` already aligns). | [ ] BLOCKED-on-L1 (needs lgd_states ready) | _pending_ | M |
| LGD-STAMP | Author `datasets/taxonomy/lgd_acs.json` (~4123 ACs across India: lgd_ac_id + lgd_district_id + ac_name + reservation + eci_st_code + eci_ac_no). Source: LGD portal scrape (one-shot, fact-stable per delim cycle) or hand-compilation. Becomes the join authority for everything AC-level. | [ ] BLOCKED-on-L1 | _pending_ | M |
| RETIRE-D1 | After AC1 + LGD-STAMP land: rip `apply_ac_no_rewrite_by_name` + the name-translation seam. S01/AP frontend rework (replace `ac_no==eci_no` assumption with crosswalk reverse-map). | [ ] BLOCKED-on-AC1 | _pending_ | M |

## Sources (verified 2026-06-01)

| Layer | Source | Provides | License |
| --- | --- | --- | --- |
| State LGD codes | `https://lgdirectory.gov.in/states.do` | 37 states/UTs, lgd_state_id + name | public-domain (GoI) |
| District LGD codes | `https://lgdirectory.gov.in/listOfDistrictsForCensus2011.do` | ~780 districts | public-domain (GoI) |
| AC LGD codes (29 states) | LGD AC directory (per state) | lgd_ac_id + lgd_district_id + name + reservation | public-domain (GoI) |
| AC geometry (30 states, ECI-keyed) | `https://github.com/GarudadevDataServices/indian_mlas/raw_data/india_asm.geojson` | 4164 AC polygons, st_code + ac_no + ac_id (ECI) | public-domain mirror (ECI works) |
| U08 J&K AC geometry post-2022 | `https://github.com/shijithpk/2024_maps_supplement/blob/main/j_and_k_assembly_new_borders.geojson` | 91 features (90 ACs + 1 POK ref), `state_id="U08"`, `seat_id` 1-90, `seat_name_en`, `seat_district_en` | per shijithpk repo (verify CC/MIT on commit) |
| U08 J&K verification overlay | Wikimedia Furfur SVG "Wahlkreise zur Vidhan Sabha von J&K (2022)" | visual cross-check post-delim boundaries | CC-BY-4.0 |

## Anti-patterns (do NOT)

- Adopt ECI st_code as canonical for non-electoral indicators - the very trap this plan exists to escape.
- Ship piece-meal renames (one folder at a time) - the convention split is worse than either pure convention.
- Skip LGD-STAMP and let crosswalk show "lgd_direct" without actual lgd_ac_id values (PR #542's residual smell - acceptable as transition, NOT acceptable as end-state).
- Mint a fresh `slug` per state from boundary file name strings - use LGD canonical state name only.
- Build a `lgd_to_eci` translator inside every indicator adapter - centralise it in `lgd_eci_state_map.json` (state level) + `lgd_acs.json` (AC level).

## Distillation routes (per `docs/how-to/distill-a-plan.md`)

| Row | Distill to |
| --- | --- |
| L0 | NEW `docs/architecture/data/lgd-canonical-keys.md` (LGD-as-canonical doctrine, state/district/AC code policy) |
| L1 | `docs/architecture/data/canonical-store.md` (taxonomy seed contract for lgd_states / lgd_districts / lgd_eci_state_map) |
| L2 | `docs/architecture/decisions/0050-folder-naming-convention.md` NEW ADR |
| L3 | `docs/how-to/migrate-partition-keys.md` NEW (rip+recompile recipe) |
| L4 | `docs/architecture/frontend/data-loading.md` (URL slug migration + redirect map) |
| AC1 | `docs/how-to/add-new-boundary-layer.md` (Garuda-geometry + LGD-stamp pattern) |
| LGD-STAMP | `docs/concepts/lgd-authority.md` NEW (why LGD is the indicator-join centre, how it differs from ECI) |
| RETIRE-D1 | Append to ADR-0029 retirement section; archive parent migration plan-doc |

At plan close, archive `TODO/20260601-lgd-canonical-plan.md` to `docs/archive/plans/` with per-row PR + distillation map per the standard distill ceremony.

## Open questions (need user answer before L3 starts)

1. **L2 convention pick:** `state=lgd06` (machine ID, language-neutral, stable across renames like Orissa->Odisha) OR `state=haryana` (slug, human-readable, but a name change forces a rip). **My lean: `state=lgd06`** with a separate `lgd_name` field for display. Machines key on IDs; names drift.
2. **AC LGD source confidence:** for the 29 covered states, do we trust LGD portal AC listings as authoritative-as-of-current-delim, or do we need a delim-cycle versioning concept (`lgd_ac_id_2008delim` vs `lgd_ac_id_2022delim`)? **My lean: trust LGD as canonical-as-of-current; versioning is a separate plan if a state re-delims.**
3. **U08 J&K LGD codes:** shijithpk's `seat_id` 1-90 matches ECI ac_no. LGD doesn't publish AC codes for J&K post-2022 (delim too recent). **Options:** (a) compute synthetic `lgd_ac_id = lgd_state_id * 1000 + seat_id` until LGD catches up; (b) leave J&K `lgd_ac_id` null and revisit when LGD publishes. **My lean: (b)** - synthetic codes are tech debt that will be wrong when LGD publishes real ones.

## See also

- `TODO/20260601-ac-coverage-to-100-plan.md` (superseded; PR #542 enrich shipped as ECI-keyed transitional state; PR #541 plan-doc folded here)
- `docs/architecture/decisions/0049-lgd-ac-id-internal-key.md` (LGD-canonical for AC level; this plan generalises to state/district)
- PR #542 `feat/i1-garuda-ac-id-enrich` (merged; adds AC_ID to Assam features; transitional, NOT canonical end-state)
- Garuda mirror: `https://github.com/GarudadevDataServices/indian_mlas`
- shijithpk J&K: `https://github.com/shijithpk/2024_maps_supplement`
- Wikimedia Furfur J&K SVG: `https://en.wikipedia.org/wiki/File:Wahlkreise_zur_Vidhan_Sabha_von_Jammu_%26_Kashmir_(2022).svg`
