# Level-5 plan: `eci_no` -> LGD `AC_ID` corpus migration

**Last Updated**: 2026-05-30

**Predecessor plan-doc**: [docs/archive/plans/20260530-boundary-followups-execution-plan.md](../docs/archive/plans/20260530-boundary-followups-execution-plan.md) Row 4.4 (was Row 5.2 pre-PR #471 cleanup; this plan-doc opens that row's research-only first PR).

**Status**: MIGRATION AUTHORIZED. R1 audit complete ([notes/20260601-eci-to-acid-migration-surface-audit.md](../notes/20260601-eci-to-acid-migration-surface-audit.md)). User granted explicit big-bang sign-off 2026-06-01 (see section 0.4), which per CLAUDE.md section 0a ("user approval supersedes every agent and every rule") unblocks the Level-5 pause. Chosen strategy = Strategy-D-hardened (section 0.5). Execution proceeds autonomously via the A1->D1 PR breakdown (section 3).

---

## section 0. Operating contract

### 0.1 Why this plan-doc exists

The "LGD-golden" doctrine (per [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) + Phase A.1 of the 20260530 plan-doc) made LGD the authoritative spine for Assembly Constituency identity. Boundary shards now key on `lgd_ac_id` (numeric LGD identifier) while election-results parquets + indicator-family tables + SoT files + frontend join logic still key on `eci_no` (ECI's per-state 1-to-N enumeration). The two-spine state is workable for the current citizen surfaces but creates ongoing translation cost on every cross-cut and blocks any future "national AC-level indicator" that needs a single primary key.

This plan-doc opens the migration arc. It does NOT start migrating; it commissions the audit that tells the user how big the rewrite is + which surfaces would have to change + what the user-experience-visible risk is for each surface.

### 0.2 Hard-coded scope of the FIRST PR (this PR via _pending_)

ONLY R1 - write a research-note auditing all `eci_no` read + write sites. No data rewrite. No frontend join changes. No schema changes. No code execution beyond the audit walk.

### 0.3 ESCALATE triggers (everything beyond R1)

The migration rows (R2 onwards: data rewrite, schema changes, join-key refactor, frontend join logic, contract-test updates, distillation) ALL ESCALATE. Agent does NOT execute any of them without:

1. User reading the R1 research-note + explicitly approving migration strategy
2. This plan-doc amended with the chosen strategy + per-row acceptance gates IN THE SAME COMMIT as the approval

This is the CLAUDE.md section 6 Level-5 contract verbatim: "Core design / data model / runtime - Design consultation only - pause work".

### 0.4 User sign-off (2026-06-01) - RECORDED

User granted explicit big-bang authorization (verbatim intent): "YOU HAVE PERMISSION TO RIP AND REPLACE - NO PRISONERS - NO STRANGLER FIG - GIT IS THE BACKUP TO REVERT UPON FAILURE. GO BIG BANG RE WRITE - break it into small manageable PR, merge to main then start next PR ... all surfaces change - big-bang ... all citizen facing routes should change ... ultimately the url is human friendly correct? /s/tamil-nadu". This satisfies the section 0.3 trigger #1 (user approval) and trigger #2 (this same edit amends the plan-doc with the chosen strategy + per-row gates). CLAUDE.md section 0a applies: user approval supersedes the Level-5 pause.

### 0.5 Chosen strategy - Strategy-D-hardened (Gregor conference verdict, 2026-06-01)

`lgd_ac_id` becomes the canonical INTERNAL join key; `eci_no` is DEMOTED from identity to citizen-facing display/URL label (the ballot number citizens recognize). `entity_id` remains the PK (ADR-0044 untouched); `lgd_ac_id` is a nullable join attribute. The crosswalk is ONE Canonical Data Model table harvested from existing boundary provenance, filled per-state for the long tail.

**Coverage correction (verified 2026-06-01 against `datasets/boundaries/in/ac/state=*/all.topojson`):** the earlier audit framing of "only ~10 states have LGD / 18 states need external sourcing" was WRONG. **30 of 31 AC partitions already carry the LGD AC code** in boundary features as `AC_ID` (= 2-digit `State_LGD` + 3-digit `ac_no`, e.g. S02 `12032`, S24 `09175`; S01 additionally has explicit `lgd_ac_id`+`lgd_legacy_ac_no`). **Only U08 (J&K) genuinely lacks it** (uses `seat_id`, post-2022 delimitation source). The 0% figure is true only of the SoT `constituencies.json` files; the LGD data lives in the boundary shards. The real gap is the **crosswalk binding** `eci_no <-> lgd_ac_id` lifted to a canonical table (today only S01 has its `ac_no` rewritten to ECI numbering; the other 29 carry the LGD code but the `eci_no` join must be derived: `ac_no` where ECI/LGD numbering coincides, name+reservation where it diverges, e.g. `"status":"Pre delimitation"` rows). So the crosswalk is HARVESTABLE for ~30 states with no external sourcing; only U08 needs special handling.

**URL grammar decision (user, 2026-06-01):** AC route becomes `/s/<state-slug>/ac/<eci_no>-<name-slug>` (e.g. `/s/tamil-nadu/ac/42-tekkali`). `eci_no` stays the leading human-recognizable token; the name slug is appended for readability; `lgd_ac_id` is INTERNAL-ONLY and never appears in any URL. State route `/s/<state-slug>` unchanged. This revises Gregor's original "no URL-rename PR" to "AC slug gains a name suffix; the spine stays `eci_no`" - handled by PR-URL below.

---

## section 1. Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| R1 | Audit all `eci_no` read + write sites; produce research-note + migration-surface map | [x] NOTE AUTHORED - [notes/20260601-eci-to-acid-migration-surface-audit.md](../notes/20260601-eci-to-acid-migration-surface-audit.md) | #469 (docket) + _pending_ (note) | S |
| R2 | Migration strategy chosen + plan-doc amended | [x] DONE - Strategy-D-hardened, signed off 2026-06-01 (section 0.4/0.5) | _this edit_ | S |
| A1 | Crosswalk contract + scaffolding (schema + helper, no data, no readers) | [x] DONE | #530 | M |
| A2 | Materialize crosswalk by harvesting ~30 covered states from boundary `AC_ID` | [x] DONE - 4113 rows / 3860 lgd_direct / 253 unmapped (93.8% mapped); bijection+cover oracle green | #533 | M |
| A3 | Lift `lgd_ac_id` nullable attribute onto `dim_acs` | [x] DONE | #534 | M |
| B1 | Boundary snapshot emits `lgd_ac_id` as parallel top-level join property | [x] DONE - 29/31 AC shards stamped (3860 distinct = crosswalk-covered); S03+U08 exempt (no AC_ID); S01 string->int normalised | #535 | M |
| B2 | Frontend canonical join via crosswalk (Message Translator), output-pinned | [x] DONE | #536 | L |
| B3 | Flip boundary default `join_property` to `lgd_ac_id` for covered states | [x] DONE | #537 | M |
| URL | AC URL slug gains name suffix `/s/<state>/ac/<eci_no>-<name-slug>` | [x] DONE | #538 | M |
| C1 | Fill crosswalk for U08 (J&K) + any uncovered AC (repeatable per N states) | [ ] PENDING | _pending_ | L |
| D1 | Rip out legacy name-based `ac_no<->eci_no` translation seams | [ ] PENDING | _pending_ | M |

---

## section 2. Row R1 - Audit + research-note (THIS PR's deliverable)

### R1 acceptance

This PR (#469) ships:

1. THIS plan-doc with the operating contract + Row R1 spec.
2. R1 acceptance is bounded - actual research-note authoring happens in a future PR; this PR opens the docket.

The research-note (separate PR) will be at `notes/<YYYYMMDD>-eci-to-acid-migration-surface-audit.md` and MUST list, exhaustively:

- **Read sites** in `frontend/`: every `.ts` / `.svelte` file that reads `eci_no` from any data source (parquet via DuckDB, JSON sidecar, URL parameter, contract test fixture). For each site: file:line, what it reads `eci_no` FOR, what it would key on POST-migration.
- **Read sites** in `backend/`: every Python module that reads `eci_no` from any source.
- **Write sites** in `backend/`: every parquet / JSON emit that carries `eci_no` as a column or key.
- **SoT files**: every `datasets/reference/in/states/<state>/constituencies.json` that lists `eci_no` as the citizen-recognizable enumeration.
- **Election-results parquets**: per-election manifests that key results to `eci_no`.
- **Indicator-family tables**: any AC-grain indicator parquet that uses `eci_no` as the grain dimension.
- **Frontend join logic**: every `maplibre` boundary -> data join that does `properties.eci_no === row.eci_no`.
- **Contract tests**: every `frontend/src/contracts/*.test.ts` + `backend/tests/test_*.py` that asserts on `eci_no` as the key.

### R1 deliverable structure (for the future PR)

The research-note will tabulate sites in 8 sections (one per surface above) + a "migration-surface map" diagram showing the dependency order (which sites are downstream of which) + 3-5 candidate migration strategies (e.g. (a) big-bang corpus rewrite, (b) dual-key co-existence with adapter layer, (c) read-side translation table + lazy migration, (d) keep ECI as citizen-display + LGD as internal-only, (e) just-the-bits-that-need-national-spine).

R1 explicitly does NOT recommend a strategy. The user picks from the 3-5 options + the agent's R1 estimated effort/risk per option.

### R1 NOT-in-scope

- Implementing any of the migration strategies
- Modifying any data file
- Modifying any frontend / backend code (except possibly adding a `// TODO: migration audit captured in <note>` marker, which is itself ESCALATE-able)
- Touching schemas
- Touching contract tests

---

## section 3. Migration PR breakdown (A1 -> D1)

Phases: A (structural, ships NOW without external sourcing), B (reader cutover, behavioural but output-pinned), URL (citizen-facing slug), C (data-fill, repeatable), D (cleanup). Each row builds on the prior; each is independently `git revert`-able by construction.

**The single load-bearing safety net** is ONE contract test introduced in A2 and extended every phase: the crosswalk bijection-and-completeness oracle. It asserts (1) every SoT `(state_code, eci_no)` has exactly one crosswalk row; (2) `lgd_ac_id` is globally unique where non-null; (3) on the covered subset `(eci_no, lgd_ac_id)` is a strict bijection; (4) covered-row count equals the boundary-provenance `lgd_ac_id` count (no silent drops from the lossy name-join). Behavioural cutover rows (B2/B3) additionally carry a result-parity oracle pinning byte-identical result rows pre/post.

### Row A1 - Crosswalk contract + scaffolding (structural, ships NOW)

- Surfaces: new `datasets/schemas/ac-crosswalk.schema.json`; new pure helper `backend/yen_gov/canonical/ac_crosswalk.py` (lookup + bijection-assert; no data).
- `ac_crosswalk` columns: `state_code TEXT`, `eci_no INT`, `lgd_ac_id INT NULL`, `entity_id TEXT`, `ac_name TEXT`, `delim_year INT`, `match_method TEXT` enum `{lgd_direct, name_reservation_join, unmapped}`, `source_id TEXT` FK to `datasets/taxonomy/sources.parquet`. PK `(state_code, eci_no)`, total over every SoT AC.
- Gates: Contract (schema validates) + Unit (helper round-trip). No data, no readers.
- New ADR-0049 "Canonical AC join key = lgd_ac_id; eci_no demoted to display label; crosswalk as Canonical Data Model" ships with this row (cites ADR-0044 + admin-level-sourcing.md).

### Row A2 - Materialize crosswalk by harvest (structural, ships NOW)

- Surfaces: new `tools/migrate/build_ac_crosswalk.py`; new `datasets/taxonomy/ac_crosswalk.parquet`; `datasets/manifest.json`.
- Reads boundary-shard `AC_ID`/`lgd_ac_id` + `ac_no` + SoT `eci_no`; emits one row per SoT AC. ~30 states resolve via `AC_ID` (`lgd_direct` where `ac_no`==`eci_no`, else `name_reservation_join`). U08 + any unresolved get `lgd_ac_id=null, match_method=unmapped`.
- Gate: the bijection + completeness oracle (THE safety net). Structural - nobody reads it yet.
- DONE (PR #533): harvester `tools/migrate/build_ac_crosswalk.py` emits 4113 rows (one per SoT AC), 3860 `lgd_direct` + 253 `unmapped` (93.8% mapped), zero global `lgd_ac_id` collisions. `ac_id`/`ac_name`/`delim_year` read from `dim_acs(2008)` (SoT is a strict subset, verified). `lgd_ac_id` harvested from HTL `AC_ID` after dropping cross-state spillover via modal `st_code`. Whole-state `unmapped`: S03/Assam (126, boundary has no `AC_ID`) + U08/J&K (90, no `AC_ID`) - deferred to Row C1. Registered in `manifest.json` via `_taxonomy_schema_file` mapping. Oracle (`backend/tests/test_build_ac_crosswalk.py::test_shipped_crosswalk_passes_oracle`) runs `assert_bijection` with exact cover over the real SoT universe and passes (4113 == 4113).

### Row A3 - Lift `lgd_ac_id` onto `dim_acs` (structural, ships NOW)

- Surfaces: `envelope.py` (`DimensionAc`), `rollups.py`, `writer.py` (additive `dim_acs` column), `canonical_eci_backfill.py`. `entity_id` PK + `eci_no` FK unchanged; `lgd_ac_id` added as nullable attribute joined from the crosswalk.
- Gate: Contract (`dim_acs.lgd_ac_id` == crosswalk for covered states, null elsewhere).
- DONE (PR #534): `dim-acs.schema.json` bumped 1.0 -> 1.1 (additive nullable `lgd_ac_id`); `schema-compatibility.json` accepts `[1.0, 1.1]`. `AcDimRow` (envelope) + `_DIM_SPECS["ac"]` (writer) carry the column. New one-shot `backend/yen_gov/pipeline/dim_acs_lgd_lift.py` re-emits `dim_acs.parquet` through `_emit_table` (KV metadata + manifest advance to 1.1) joining `lgd_ac_id` from the crosswalk for `delim_year=2008` rows only. Future-correctness: `build_slice_envelope`/`_process_slice`/`backfill_elections` + `run.py` thread an optional `lgd_lookup` so re-runs never null the column. Shipped distribution: 8055 rows, 3860 covered (2008 `lgd_direct`); 1976 (3932) + uncovered 2008 (263) NULL. Oracle `test_dim_acs_lgd_lift.py::test_shipped_dim_acs_matches_crosswalk` asserts every 2008 row == crosswalk and every non-2008 row NULL. Gates: validate EXIT=0; A3 test 4/4; writer+partition+backfill 45/45.

### Row B1 - Boundary snapshot emits `lgd_ac_id` join property (structural-leaning)

- Surfaces: `tools/boundaries/snapshot.py` (promote provenance `lgd_ac_id` to first-class feature property for all ~30 covered states, not just S01), pipeline config, `frontend/src/lib/maplibre/sources.ts` (add `join_property_lgd` beside existing `ac_no`). Keep `ac_no`.
- Gate: Contract (boundary `lgd_ac_id` subset-of crosswalk covered).

**DONE (PR #535):** New `tools/boundaries/lift_boundary_lgd_ac_id.py` (pure duckdb+stdlib) stamps `lgd_ac_id = int(AC_ID)` onto every crosswalk-covered AC feature; `snapshot.py` calls it at end-of-run for future-correctness. `sources.ts` `BoundaryEntry` gains optional `join_property_lgd: "lgd_ac_id"` on all 29 covered states (S03 + U08 exempt - no `AC_ID`). 29/31 shards stamped; 3860 distinct `lgd_ac_id` = exactly crosswalk-covered (subset gate green). S01 `lgd_ac_id` normalised string->int. Gates: validate EXIT=0; `test_lift_boundary_lgd_ac_id.py` 7/7; `state-ac-registry-coverage.test.ts` 67/67; svelte-check 0e/7w.

### Row B2 - Frontend canonical join via crosswalk (behavioural, output-pinned)

- Surfaces: `duckdb-views.ts`, `presets.ts`, `view-models/constituency.ts`, `maplibre/MapChoropleth.svelte`. Resolve boundary<->results through crosswalk `lgd_ac_id` where present, fall back to `eci_no`/`ac_no` where `unmapped`.
- Gate: Integration parity oracle pinning byte-identical result rows pre/post (THE behavioural net).

**DONE (PR #536):** New `frontend/src/lib/view-models/ac-crosswalk.ts` (`loadAcLgdLookup(state) -> Map<eci_no, lgd_ac_id>` reading `taxonomy.ac_crosswalk` covered rows - the Message Translator). New pure `mirrorLgdKeys(base, lookup)` in `election-map-coloring.ts` dual-keys an eci_no-keyed fills/opacities map under each AC's `lgd_ac_id` (>=1000, never collides with eci_no 1..~403). `MapChoropleth.svelte` gains optional `canonical_join` prop: when true + entry carries `join_property_lgd`, the fill/opacity/hatch join `coalesce`s raw `lgd_ac_id` before `ac_no` (coalesce on RAW values before `to-number`, since `to-number(null)=0` defeats fallback); selection/hover/highlight keep the eci_no label join (click-to-navigate unchanged). `StateAcMap.svelte` loads the per-state lookup, dual-keys fills+opacities, and flips `canonical_join` atomically when the lookup resolves (no flash). SEAM NOTE: plan named `duckdb-views.ts`/`presets.ts`/`constituency.ts` but those overlap an in-flight winners-query refactor; join resolved in the boundary layer via the crosswalk instead - same outcome, no WIP contention. Gates: parity oracle (`election-map-coloring.test.ts` +6 tests) 21/21; svelte-check 0e/7w; validate EXIT=0. `entity_id` PK + ADR-0044 untouched; `lgd_ac_id` INTERNAL-only.

### Row B3 - Flip boundary default `join_property` to `lgd_ac_id` (behavioural)

- Surfaces: `sources.ts` `join_property`, contract tests `state-ac-registry-coverage.test.ts` + `election-tile-layout-coverage.test.ts`. Covered states only; `unmapped` states still ride `ac_no`.
- Gate: Contract (updated parity oracles green).

**DONE (PR #537):** 29 covered `STATE_AC` entries in `sources.ts` flip `join_property: "ac_no"` -> `join_property: "lgd_ac_id"` and gain a new optional `join_property_label: "ac_no"` (eci_no-valued); S03 Assam (`ac_no` Tier-4 district fallback) + U08 J&K (`seat_id`) stay exempt. `MapChoropleth.svelte` `get_fill_join_value` keys the COLOUR fill on `join_property_label ?? join_property` so covered polygons never flash blank pre-lookup; selection/highlight stay on the canonical `join_property` (lgd_ac_id). `StateAcMap.svelte` inverts the crosswalk lookup (`reverse_lookup` lgd_ac_id -> eci_no) so click-to-navigate recovers the citizen-facing eci_no (URL never carries lgd_ac_id), with `ac_no`-feature + raw-key fallbacks; the highlight key is mapped eci_no -> lgd_ac_id (`highlight_lgd`). DEVIATION from the one-line spec: added `join_property_label` + the reverse-map - necessary to keep eci_no in the URL (citizen invariant) and keep the fill flash-free; also makes Row D1 a near-pure deletion (selection recovers eci_no without the legacy name-join). `election-tile-layout-coverage.test.ts` needed no edit (it reads `f.properties.ac_no` feature data, not the registry). Gates: svelte-check 0e/7w; vitest `state-ac-registry-coverage` 68 + `election-tile-layout-coverage` 9 + maplibre/elections 35 green; validate EXIT=0.

### Row URL - AC URL slug gains name suffix (citizen-facing)

- Surfaces: AC route + slug builder/parser (`acSlug`/`parseAcSlug`), route param, title. New grammar `/s/<state-slug>/ac/<eci_no>-<name-slug>` (e.g. `/s/tamil-nadu/ac/42-tekkali`). `eci_no` stays the leading token + parse key; name slug is decorative + parsed-tolerant. `constituencywise_url` (ECI-portal-semantic) stays on `eci_no`. `lgd_ac_id` never in URL.
- Gate: Unit (slug round-trip: parse(build(eci_no, name)) == eci_no) + a redirect/tolerance check for the old bare-number form. Browser smoke per CLAUDE.md section 13.

**DONE (PR #538):** The grammar was ALREADY in place - `url.ac(state, eci_no, name)` + `acSlug(eci_no, name)` build the name-suffixed slug, `parseAcSlug` already accepts both `/ac/42` and `/ac/42-tekkali`, and `StateOverview` already emitted it. This row converged the three remaining citizen-facing emitters that still produced bare-number links: `RacesBoard.svelte` (`url.acByNo` -> `url.ac` with `r.name`), `ElectionMap.svelte` (hex/tile map click maps eci_no -> AC name via new `name_by_eci` lookup over `rows`), `StateAcMap.svelte` (choropleth select same, layered on the Row B3 reverse-map). `url.acByNo` retained as the no-name fallback API; absent name falls back to bare eci_no (parse-tolerant). Gates: svelte-check 0e/7w; vitest `slug.test.ts` 14 (round-trip + bare-number tolerance) + `url.test.ts` 44 green; validate EXIT=0.

### Row C1 - Fill crosswalk for U08 + uncovered (behavioural, REPEATABLE)

- Surfaces: SoT `constituencies.json` real `lgd_ac_id` (with `constituency.schema.json` 4.1 -> 4.2 additive bump + restamp of every touched SoT file's `$schema_version` + a `datasets/schema-compatibility.json` entry, all in this same change per ADR-0047), recompile `ac_crosswalk.parquet`, flip `match_method` `unmapped` -> `lgd_direct`. U08 (J&K seat_id<->eci_no) is the known hard case - research via integrated browser / LGD portal if needed; stays `unmapped` (rides `ac_no`/`seat_id`) until resolved.
- Gate: bijection oracle extended to newly-filled states + explicit "no regression to already-covered states" assertion.

### Row D1 - Rip out legacy name-based translation seams (structural cleanup)

- Surfaces: reduce/retire `apply_ac_no_rewrite_by_name`; delete scattered `ac_no<->eci_no` name joins.
- Gate: green parity oracle proving deletion changed nothing. Ships only after coverage is effectively 100% `lgd_direct`.

### Per-row execution rules

1. 2-commit-then-squash (structural commit + `_pending_` -> real-PR# stamp); merge to main; start next row.
2. Minimal necessary tests only (the oracles above are load-bearing; do not over-test).
3. Parallelize independent rows via subagents; do not block on slow e2e.
4. Stamp this Status Reckoner with the real PR# as each row merges.

---

## See also

- [docs/archive/plans/20260530-boundary-followups-execution-plan.md](../docs/archive/plans/20260530-boundary-followups-execution-plan.md) Row 4.4 (was Row 5.2; this plan-doc opens that row)
- [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) (LGD-golden doctrine + 3-convention rule)
- [docs/architecture/decisions/0029-unmapped-region-chips.md](../docs/architecture/decisions/0029-unmapped-region-chips.md) (D.1.A user-mandate + retirement context)
- [CLAUDE.md](../CLAUDE.md) section 6 Level-5 ("Core design / data model / runtime - Design consultation only - pause work")
