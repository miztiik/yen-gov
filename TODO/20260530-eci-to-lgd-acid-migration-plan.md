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
| A2 | Materialize crosswalk by harvesting ~30 covered states from boundary `AC_ID` | [ ] PENDING | _pending_ | M |
| A3 | Lift `lgd_ac_id` nullable attribute onto `dim_acs` | [ ] PENDING | _pending_ | M |
| B1 | Boundary snapshot emits `lgd_ac_id` as parallel top-level join property | [ ] PENDING | _pending_ | M |
| B2 | Frontend canonical join via crosswalk (Message Translator), output-pinned | [ ] PENDING | _pending_ | L |
| B3 | Flip boundary default `join_property` to `lgd_ac_id` for covered states | [ ] PENDING | _pending_ | M |
| URL | AC URL slug gains name suffix `/s/<state>/ac/<eci_no>-<name-slug>` | [ ] PENDING | _pending_ | M |
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

### Row A3 - Lift `lgd_ac_id` onto `dim_acs` (structural, ships NOW)

- Surfaces: `envelope.py` (`DimensionAc`), `rollups.py`, `writer.py` (additive `dim_acs` column), `canonical_eci_backfill.py`. `entity_id` PK + `eci_no` FK unchanged; `lgd_ac_id` added as nullable attribute joined from the crosswalk.
- Gate: Contract (`dim_acs.lgd_ac_id` == crosswalk for covered states, null elsewhere).

### Row B1 - Boundary snapshot emits `lgd_ac_id` join property (structural-leaning)

- Surfaces: `tools/boundaries/snapshot.py` (promote provenance `lgd_ac_id` to first-class feature property for all ~30 covered states, not just S01), pipeline config, `frontend/src/lib/maplibre/sources.ts` (add `join_property_lgd` beside existing `ac_no`). Keep `ac_no`.
- Gate: Contract (boundary `lgd_ac_id` subset-of crosswalk covered).

### Row B2 - Frontend canonical join via crosswalk (behavioural, output-pinned)

- Surfaces: `duckdb-views.ts`, `presets.ts`, `view-models/constituency.ts`, `maplibre/MapChoropleth.svelte`. Resolve boundary<->results through crosswalk `lgd_ac_id` where present, fall back to `eci_no`/`ac_no` where `unmapped`.
- Gate: Integration parity oracle pinning byte-identical result rows pre/post (THE behavioural net).

### Row B3 - Flip boundary default `join_property` to `lgd_ac_id` (behavioural)

- Surfaces: `sources.ts` `join_property`, contract tests `state-ac-registry-coverage.test.ts` + `election-tile-layout-coverage.test.ts`. Covered states only; `unmapped` states still ride `ac_no`.
- Gate: Contract (updated parity oracles green).

### Row URL - AC URL slug gains name suffix (citizen-facing)

- Surfaces: AC route + slug builder/parser (`acSlug`/`parseAcSlug`), route param, title. New grammar `/s/<state-slug>/ac/<eci_no>-<name-slug>` (e.g. `/s/tamil-nadu/ac/42-tekkali`). `eci_no` stays the leading token + parse key; name slug is decorative + parsed-tolerant. `constituencywise_url` (ECI-portal-semantic) stays on `eci_no`. `lgd_ac_id` never in URL.
- Gate: Unit (slug round-trip: parse(build(eci_no, name)) == eci_no) + a redirect/tolerance check for the old bare-number form. Browser smoke per CLAUDE.md section 13.

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
