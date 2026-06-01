# Plan: LGD-canonical execution handover (parallel-agent PR split)

**Status:** ACTIVE
**Last Updated:** 2026-06-01
**Level:** 5 (cross-cutting)
**Parent plan:** [`TODO/20260601-lgd-canonical-plan.md`](20260601-lgd-canonical-plan.md) (decisions locked; PR #544 + #546)
**Standing mandate:** continue till end of plan; ship one PR per row; dispatch custom agents where domain expertise applies; parallel-friendly rows have no shared file surface.

## Source-of-truth doctrine (locked 2026-06-01)

**Single canonical source = GoI.** Specifically:

- **LGD portal** (`https://lgdirectory.gov.in/`) for every state/district/sub-district/panchayat/ULB/ward/AC code + name + parent.
- **ECI** (`https://eci.gov.in/`) only for election artefacts (events, results, candidates) where it IS the issuing authority.
- **Survey of India** (`https://surveyofindia.gov.in/`) for geometry where it publishes; otherwise **Bhuvan/NRSC** (`https://bhuvan.nrsc.gov.in/`); otherwise **Census of India** vintage.
- **Retire:** shijithpk, Garuda, ramSeraph LGD mirror, OpenStreetMap polygons (where GoI publishes equivalent), Wikimedia overlays. They stay as VERIFICATION-only references in source-hunt notes; never written into `datasets/taxonomy/sources.parquet`.
- **Exception:** if GoI has not published a layer (e.g. J&K post-2022 AC geometry), use the best Tier-2 source AND open a follow-up ticket to ingest the GoI artefact when it appears.

Rationale (user, 2026-06-01): "consolidate all sources to refer to GoI no need to maintain multiple sources." Multi-source proliferation = recurring methodology-break risk; GoI single-source = stable join keys + clear chain-of-custody for citizen verifiability.

## Sikkim verification (commissioned by user 2026-06-01)

- **Existing** `datasets/boundaries/in/ac/state=in_s21/all.geojson`: **38 AC features** (expected: **32** per 2008 delim). Overcount source unknown; likely older vintage with reserved-seat duplication or stale upstream. 4 districts referenced (`Dist_LGD` 225, 226, 227, 228) - **pre-2021 4-district Sikkim**. Sikkim was reorganised into **6 districts** in late 2021 (added Pakyong + Soreng).
- **shijithpk candidate:** 31 features (undercount of 1).
- **Verdict:** existing data is stale on BOTH AC count AND district count. **Row AC1 (Sikkim slice) blocked on GoI source.** Need LGD AC directory + LGD district directory current snapshot; shijithpk is now a Tier-3 verification overlay only.

## PR split (parallel-agent friendly)

Independence is encoded in the **Touches** column. Rows with disjoint Touches sets can run in parallel agents. Rows with shared Touches must serialise.

| # | Row | Agent | Touches | Depends on | Risk | Parallel? |
| :-: | --- | --- | --- | --- | :-: | :-: |
| **L1a** | Seed `datasets/taxonomy/lgd_states.json` (37 states/UTs from LGD portal: `lgd_state_id`, `lgd_name`, `lgd_name_short`, `iso_alpha`, `slug`, `eci_st_code`) + schema | Default | `datasets/taxonomy/lgd_states.json`, `datasets/schemas/lgd-states.schema.json` | none | M | YES |
| **L1b** | Seed `datasets/taxonomy/lgd_districts.json` (~780 districts; `lgd_district_id`, `lgd_state_id`, `lgd_name`, `slug`, `created_on`, `parent_district_lgd` for splits) + schema | **Hans** (district-name + bifurcation lineage rigour) | `datasets/taxonomy/lgd_districts.json`, schema | L1a | M | NO (FK to L1a) |
| **L1c** | Seed `datasets/taxonomy/lgd_acs.json` (~4123 ACs; `lgd_ac_id`, `lgd_district_id`, `lgd_state_id`, `ac_name`, `reservation`, `eci_ac_no`) + schema | **Hans** | `datasets/taxonomy/lgd_acs.json`, schema | L1a | M | NO (FK to L1a/L1b) |
| **L1d** | Verification tests: every `lgd_district_id` FKs to L1a; every `lgd_ac_id` FKs to L1b; `eci_*` columns are nullable display-only | Default | `backend/tests/test_lgd_taxonomy.py` | L1a + L1b + L1c | L | NO |
| **A1** | New ADR-0050 "Folder-naming convention: `state=<lgd_name_slug>`" + `docs/architecture/decisions/0050-folder-naming.md` | **Gregor** | new ADR file only | none | L | YES (independent of L1) |
| **A2** | New `docs/concepts/lgd-authority.md` (LGD-as-canonical doctrine; why ECI is display-only; how to translate; OWID-aligned narrative) | **Hans** + **Andre** (citizen-reader voice) | new concept doc only | none | L | YES |
| **A3** | New `docs/architecture/data/lgd-canonical-keys.md` (state/district/AC code policy + join contract + reader-side translation patterns) | **Gregor** | new arch doc only | A1 | L | YES (after A1) |
| **M1** | Rename `tools/migrate/rename_partition_keys.py`: rewrites `state=in_s07` -> `state=haryana` across `datasets/boundaries/**`, `datasets/elections/**`, `datasets/indicators/**`, every Parquet partition. Dry-run mode + manifest output | **Fowler** (refactor safety + reversibility) | new tool + tests | L1a (needs slug map) | L | YES |
| **M2** | EXECUTE M1 against `datasets/boundaries/**` only (smaller blast radius first). Update conform tests | **Fowler** | `datasets/boundaries/**`, conform tests, contracts | M1 | XL | NO |
| **M3** | EXECUTE M1 against `datasets/elections/**`. Update snapshot directives in `config/elections.json` | **Fowler** | `datasets/elections/**`, `config/elections.json`, `tools/boundaries/snapshot.py` | M2 | XL | NO |
| **M4** | EXECUTE M1 against `datasets/indicators/**` + every remaining partition | **Fowler** | residual datasets/** + Tier-A validators | M3 | XL | NO |
| **F1** | Frontend route migration: build `redirect_map.ts` (old slug -> new lgd-name slug); ship 6-month 301 redirect layer in [`frontend/src/lib/routes.ts`](../frontend/src/lib/routes.ts); golden-path e2e covers both shapes | **Jony** (URL grammar) + **Citizen** (no-broken-bookmarks check) | `frontend/src/lib/routes.ts`, golden-path.spec.ts, redirect_map.ts | M2 | M | YES (no overlap with M3/M4) |
| **AC1a** | Per-state AC geometry from **Survey of India** OR **Bhuvan** (whichever publishes AC layer). FALLBACK Tier-2 with explicit `notes/<state>-source-verdict.md` if no GoI artefact. Each state = one PR. **Sikkim FIRST** as canary (4 -> 6 district reorg + 32 AC verify) | **Max** (source-hunt) + Default (ingest) | per-state slice of `datasets/boundaries/in/ac/state=<slug>/all.geojson` | L1a + L1c | M | **YES, per-state parallel** (no file overlap across state slices) |
| **AC1b** | Stamp `lgd_ac_id` on every AC feature via name-key join from L1c. Add Tier-B test `tier_b_ac_lgd_id_present` | Default | `tools/boundaries/stamp_lgd_ac_id.py`, Tier-B predicate | L1c + AC1a (any) | M | YES (per-state after its AC1a) |
| **D1'** | Delete `apply_ac_no_rewrite_by_name` + wiring + tests; S01/AP frontend rework off `ac_no == eci_no` assumption; parity-oracle regen | **Fowler** | `tools/boundaries/snapshot.py`, `config/elections.json`, `frontend/src/lib/elections/**`, S01 boundary file | AC1b for S01 | M | NO (last) |
| **CLOSE** | Distill + archive parent plan-doc per [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md). Update [`docs/concepts/lgd-authority.md`](../docs/concepts/lgd-authority.md) with retrospective. Re-run coverage matrix script and bake final matrix into [`docs/architecture/data/boundary-coverage-matrix.md`](../docs/architecture/data/boundary-coverage-matrix.md). | Default | docs/archive/, plan-doc, coverage matrix | all above | L | NO |

## Parallel execution waves

```
Wave 1 (4 parallel):  L1a    A1     A2     M1-design
                       |      |      |       |
Wave 2 (3 parallel):  L1b    A3 (after A1)  M1-tests
                      L1c
                       |
Wave 3:               L1d
                       |
Wave 4:               M2  ----------------> AC1a (Sikkim canary)
                       |                     |
Wave 5:               M3                    AC1a (other states, parallel pool of 5+)
                       |                     |
Wave 6:               M4    F1              AC1b (per-state, parallel)
                       |     |               |
Wave 7:               D1' (depends on M4 + AC1b-S01 + F1)
                       |
Wave 8:               CLOSE
```

## Per-state AC1a parallelism budget

- **Source-hunt cohort (Max-subagent driven):** group states by source family (Survey of India bulk download / Bhuvan tile-by-tile / state-government portal one-offs). Run source-hunt for entire cohort in one Max dispatch; then per-state ingest agents run in parallel.
- **Concurrency cap:** 5 parallel ingest agents (file IO contention on `datasets/boundaries/` git index).
- **Canary first:** Sikkim (S21 -> `state=sikkim`) before fanning out. Validates both M2's slug rename AND the new AC1a pattern in one shot.

## Custom-agent assignment rationale

- **Hans (governance):** L1b, L1c — district bifurcation lineage + AC reservation conventions need public-administration depth.
- **Gregor (architecture):** A1, A3 — folder-convention ADR + canonical-keys contract are integration-pattern decisions.
- **Andre (LLM/AI app):** A2 co-author — the lgd-authority concept doc will be read by future LLM agents (citizen explainer + RAG); citizen-readable framing matters.
- **Fowler (engineering craft):** M1-M4 + D1' — large refactor surface; reversible-commit discipline + delete-first instinct critical.
- **Jony (UX):** F1 — URL grammar + redirect-map citizen-bookmark protection.
- **Citizen (sanity check):** F1 — verify no broken-bookmark scenarios from a non-technical citizen mental model.
- **Max (indicator scout):** AC1a source-hunt cohort — Survey of India / Bhuvan / state portal triage is OWID-style provenance work.

## Acceptance gates per PR (standard 5-gate DoD)

1. `python -m yen_gov.validate` EXIT=0
2. `pytest backend/tests -q` baseline maintained (no NEW failures)
3. `bun run check` (svelte-check) 0 errors
4. `bun run test` (vitest) baseline maintained
5. For frontend-touching PRs: browser smoke per CLAUDE.md §13

## Anti-patterns specific to this execution

- **Do NOT** create per-state agents that touch shared files (`tools/`, `backend/yen_gov/canonical/**`, `config/elections.json`). Per-state work is ONLY allowed inside `datasets/boundaries/in/ac/state=<one>/**`.
- **Do NOT** parallelise M2/M3/M4 — they MUST serialise (each rewrites partition keys; concurrent execution = git conflict storm).
- **Do NOT** mint a non-GoI source row in `datasets/taxonomy/sources.parquet`. If a state's GoI AC layer doesn't exist, ship that state's AC1a as BLOCKED with a verdict note citing the Tier-2 candidate as verification-only.
- **Do NOT** carry shijithpk / Garuda / Wikimedia URLs into shipped data files. They live in source-hunt notes only.
- **Do NOT** ship D1' before AC1b for S01 lands.

## Handover state for next agent

- Parent plan decisions baked: PR #544 (`a5907840`) + PR #546 (`82913d79`).
- Origin/main current head: `82913d79`.
- All 3 open questions answered: slug=name (`state=haryana`), no delim versioning, J&K LGD codes from `globalviewstateforcitizen.do`.
- **Sikkim discrepancy logged** (4 districts existing / 6 actual; 38 AC existing / 32 actual; 31 shijithpk / 32 actual). AC1a for S21 is the canary.
- Source-of-truth doctrine: **GoI only.** shijithpk + Garuda demoted to Tier-3 verification-only.
- **Next ship:** L1a (this row has no dependencies; default-agent friendly).

## See also

- **Coverage inventory:** [`docs/architecture/data/boundary-coverage-matrix.md`](../docs/architecture/data/boundary-coverage-matrix.md) - per-state x per-layer matrix; refreshed whenever a layer/state ships.
- Parent plan: [`TODO/20260601-lgd-canonical-plan.md`](20260601-lgd-canonical-plan.md)
- Superseded coverage plan: [`TODO/20260601-ac-coverage-to-100-plan.md`](20260601-ac-coverage-to-100-plan.md) (PR #541)
- [ADR-0049](../docs/architecture/decisions/0049-lgd-ac-id-internal-key.md) (lgd_ac_id internal key)
- [Distill ceremony](../docs/how-to/distill-a-plan.md)
- [PR ship workflow](../docs/how-to/ship-a-pr.md)
