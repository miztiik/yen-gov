# Boundary Follow-ups Execution Plan

**Last Updated**: 2026-05-30

**Predecessor**: [docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md](../docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md) (CLOSED via PRs #434-#456) and [TODO/20260529-boundary-rip-and-replace-plan.md](20260529-boundary-rip-and-replace-plan.md).

**Inventory**: [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md) (30 items; per-row rationale + trigger lookup).

**Operating doctrine**: AUTO per [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) "Autonomous plan execution - AUTO is the default".

> **Note on row IDs**: Row numbers `5.x` are historical (originally "Phase 5"). The `5.` prefix is now a stable ID used by inventory + CLAUDE.md memory references; do not renumber.

---

## section 0. Operating contract

### 0.1 Default stance

- **AUTO every row**: execute work, run 5-gate DoD per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md), `gh pr merge --squash --delete-branch`, advance to next row.
- **Personas as scouts, not gates**: dispatch as Explore subagents for facts; verdicts inform action, never request approval.
- **User unavailable mid-execution**: stay in scope, finish in-flight row, do not invent or contract scope.

### 0.2 Baked facts

| Fact | Value |
| --- | --- |
| F1 | Branch naming: `feat/p5-<short-id>`. |
| F2 | Pre-existing pytest failures = 12 (livestock NAIP IV + owner_reg, indicator-catalogue v21, schema_v5 x_version, energy build envelopes, concept-resolve). Gate 2 passes iff `passed >= 1449` AND `failed <= 12`. |
| F3 | Vitest baseline = 0 failures / 113 files / 2730 passed / 21 skipped. Gate 4 passes iff `failed = 0` AND test-files >= 113. |
| F4 | svelte-check baseline = 0 errors / 7 warnings in 6 files. Gate 3 passes iff `errors = 0` AND `warnings <= 7`. |
| F5 | `gh pr merge --squash --delete-branch` is clean IFF no worktree owns `main` at merge time. Check via `git worktree list` pre-merge; if a worktree holds `[main]`, expect cosmetic `failed to run git: fatal: 'main' is already used by worktree` AFTER server-side merge succeeds; verify via `gh pr view <#> --json state,mergedAt,mergeCommit`, then manually `git push origin --delete <branch>`. |
| F6 | Worker Python venv: `..\yen-gov\.venv\Scripts\python.exe`. Has duckdb + lxml. No shapely, pyproj, geopandas, numpy. Use stdlib + duckdb + lxml; if numpy needed, add to backend `pyproject.toml`. |
| F7 | NEVER concurrent vitest + pytest. Sequence sole-tenant: pytest -> svelte-check -> vitest. |
| F8 | Boundary attribution chip = icon-only U+24D8 glyph, full label "Boundary sources & licensing" on `title` attribute, links to `/about?section=maps`. Implemented in [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) `boundaryFooterHtml()`. |
| F9 | ASCII rule: NEW Markdown files use plain ASCII only (`-` not em-dash, `->` not arrow). Existing files grandfathered. Never bulk-substitute ASCII into existing prose (truncates files); re-author from scratch. |

### 0.3 ESCALATE triggers

Stop, post a message, wait for user. Do NOT escalate for anything else.

1. Schema major bump (e.g. indicator schema 5.x -> 6.x).
2. New ADR proposal required to unblock a row (existing ADR amendment is in-scope).
3. Election-results data deletion request.
4. Persona-conflict-unresolved after 1 round of cross-persona dispatch.
5. 3x cost overrun on a row's estimated effort tier (S/M/L/XL).
6. Any row in [TODO/20260530-eci-to-lgd-acid-migration-plan.md](20260530-eci-to-lgd-acid-migration-plan.md) beyond R1 (Level-5 per CLAUDE.md §6).
7. Re-scoping any Category 4 explicit non-goal (historical districts, Census 2011, slums, polling stations, etc.) without a citizen-indicator trigger.

### 0.4 Per-row execution contract

1. Read row's "Steps" + "Acceptance" blocks.
2. 5-gate DoD on worker branch. Gates 2 + 3 + 4 sole-tenant per F7.
3. ASCII-only `.tmp_*` files via `create_file` (not bulk-substitute).
4. `git push -u origin <branch>`; `gh pr create --base main --head <branch> --title ... --body-file .tmp_pr_body.md`.
5. Replace `_pending_` with `#NNN`, commit 2, push.
6. `gh pr merge <#> --squash --delete-branch`. Verify via `gh pr view`. Per F5, manually `git push origin --delete <branch>` if cosmetic error fired.
7. Update Status Reckoner row + PR#.
8. Post-merge cleanup per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md).

### 0.5 Plan closure

When all rows reach `[x] DONE` / `[-] COLLAPSED` / `[!] ESCALATED-and-resolved`, run 6-step distillation per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) and `git mv` this file to `docs/archive/plans/`. Do NOT archive while any executable row remains.

---

## section 1. Status Reckoner

Total: 37 rows. 16 DONE + 1 COLLAPSED + 1 PENDING-actionable + 19 BLOCKED-on-trigger.

| Row | Title | Status | PR | Trigger / Notes |
| --- | --- | --- | --- | --- |
| 1.1 | Icon-only attribution chip | `[x] DONE` | #460 | |
| 1.2 | e2e assertion swap + skip-trap guard | `[x] DONE` | #460 | |
| 1.3 | Predecessor archive + autonomy stanza + this plan-doc | `[x] DONE` | #460 | |
| 2.1 | C.2 panchayats verdict distillation | `[x] DONE` | #462 | |
| 2.2 | C.3 ULB wards verdict distillation | `[x] DONE` | #462 | |
| 2.3 | C.4 villages verdict distillation | `[x] DONE` | #462 | |
| 2.4 | T3 PDF vectorization how-to | `[x] DONE` | #462 | S03-specific framing SUPERSEDED by 5.1 (SVG pipeline); how-to kept for future delim-PDF states. |
| 2.5 | ADR-0029 retirement backlink | `[x] DONE` | #462 | |
| 3.1 | Vitest U08/U09 villages orphan | `[-] COLLAPSED` | n/a | Resolved upstream by PR #457. |
| 4.1 | Code-marker TODO annotations | `[x] DONE` | #464 | |
| 4.2 | Premature plan-doc archive | `[x] DONE` | #465 | REVERTED by 4.3. |
| 4.3 | Un-archive + SVG pivot + restructure (PR #468) | `[x] DONE` | #468 | |
| 4.4 | Open Level-5 successor plan-doc for eci_no -> AC_ID | `[x] DONE` | #469 | Was 5.2; renamed to 4.4 since done. |
| 4.5 | This plan-doc cleanup (single-hierarchy restructure + 5.22 reframe + concrete 5.1/5.5/5.7 steps) | `[x] DONE` | #471 | |
| 4.6 | S03 Furfur SVG structure probe + verdict | `[x] DONE` | #472 | Probe finding supersedes 5.1's optimistic 10-11h estimate. |
| 4.7 | S01 Susewind 2014 probe + verdict | `[x] DONE` | #474 | Susewind 2014 confirmed NOT viable (292 features pre-bifurcation; CC-BY-SA-NC license); only Path B remains. |
| 4.8 | Promote `verify_ac_parity` to pytest gate (was Row 5.22) | `[x] DONE` | #475 | 12 new tests across 10 D.2 states. |
| 4.9 | U09 Ladakh villages source probe + verdict | `[ ] PENDING` | _pending_ | This PR. No viable polygon source today; recommend Path D (defer + document). |
| 5.1 | S03 Assam Furfur SVG -> GeoJSON pipeline | `[ ] BLOCKED` | - | Probe (4.6) found only 20 paths / 25 subpaths / 132 numeric labels - NOT 126 per-AC polygons. Unblock: Path B (Furfur outreach) succeeds OR user accepts Path A (Voronoi approximation) with citizen caveat. |
| 5.7 | S01 AP residue: Path B in-repo surgery | `[ ] BLOCKED` | - | BLOCKED on user decision Path B (drop HTL touchpoint via remap; 3-4h) vs Path D (accept HTL indefinitely; COLLAPSE row). Per probe verdict (4.7), Path A Susewind is NOT viable. |
| **5.5** | **U09 Ladakh villages source probe** | **`[ ] BLOCKED`** | - | Per probe verdict (4.9), no viable polygon source today. Unblock now requires BOTH upstream-quality source AND village-grain citizen indicator for Ladakh. |
| ~~5.22~~ | ~~Promote `verify_ac_parity` to pytest gate~~ | `[x] DONE` (as 4.8) | #475 | Shipped as Row 4.8. |
| 5.3 | C.2.d Bhuvan panchayat gap-fill (9 states/UTs) | `[ ] BLOCKED` | - | Trigger: PRR / MGNREGS / PRI-funds indicator at panchayat grain. |
| 5.4 | C.3.d Urban ward gap-fill (WB-AMRUT / Shillong / LivingAtlas) | `[ ] BLOCKED` | - | Trigger: urban-governance / Swachh-Survekshan / AMRUT indicator at ward grain. |
| 5.6 | C.4 other 7-state villages gap-fill | `[ ] BLOCKED` | - | Per-state upstream + village-grain citizen indicator. |
| 5.8 | C.2.c Panchayat district-picker UI component | `[ ] BLOCKED` | - | Measured panchayat data + first panchayat-grain indicator. |
| 5.9 | C.3.c ULB ward-picker UI component | `[ ] BLOCKED` | - | Measured data + first ward-grain indicator. |
| 5.10 | Frontend villages registry + picker | `[ ] BLOCKED` | - | First village-grain citizen indicator. |
| 5.11 | Historical districts (1941-2001) | `[ ] BLOCKED` | - | Citizen-trigger: explicit historical-district indicator. |
| 5.12 | Census 2011 polygon snapshot | `[ ] BLOCKED` | - | Citizen-trigger: Census-grain historical indicator. |
| 5.13 | SHRUG Census 2011 harmonized variant | `[ ] BLOCKED` | - | Same as 5.12. |
| 5.14 | Habitations / sub-village granularity | `[ ] BLOCKED` | - | Citizen-trigger: sub-village indicator (unlikely). |
| 5.15 | Polling stations (7 ramSeraph sources) | `[ ] BLOCKED` | - | `/e/` event-page polling-station drill-down. |
| 5.16 | Slums (8 sources) | `[ ] BLOCKED` | - | Slum-welfare / urban-health indicator. |
| 5.17 | ULB cadastrals (52 ramSeraph sources) | `[ ] BLOCKED` | - | Property-tax / municipal-revenue indicator. |
| 5.18 | Post Offices / PostalGIS | `[ ] BLOCKED` | - | Postal-service indicator. |
| 5.19 | Cadastrals / water / transport / power / etc. | `[ ] BLOCKED` | - | Per ADR-0041 indicator-family `_meadow/` ingest. |
| 5.20 | Multi-source villages consolidation refactor | `[ ] BLOCKED` | - | 2nd non-J&K state villages gap-fill. |
| 5.21 | Sub-panchayat / GP Ward layer | `[ ] BLOCKED` | - | Upstream + GP-ward grain citizen indicator. |

Legend: `[x] DONE` / `[ ] PENDING` / `[!] ESCALATED` / `[-] COLLAPSED` / `[ ] BLOCKED`.

---

## section 2. Active rows (full detail)

### Row 4.5 - This plan-doc cleanup (this PR)

**Status**: PENDING this PR.

**Problem**: Plan-doc previously had two parallel hierarchies (`Phase 1..5` labels + `section 1..7` numbering); 4.3 was described in two places; Row 5.22 carried meaningless "pixel comparison" framing; 5.1 / 5.5 / 5.7 had no concrete tool stacks.

**This PR**:
1. Restructure plan-doc to single hierarchy (sections 0-5; no Phase labels).
2. Single Status Reckoner table covering all 33 rows.
3. Bake concrete steps + tool stacks into 5.1 / 5.5 / 5.7.
4. Reframe 5.22 to option beta (promote `verify_ac_parity.py` to pytest gate).
5. Move done Row 5.2 -> Row 4.4 (was research-PR-shipped via #469, no longer "active follow-up").

**Gates**: 1 + 2 only (docs-only; no frontend, no Python code, no schema).

---

### Row 4.6 - S03 Furfur SVG structure probe + verdict (this PR)

**Status**: PENDING this PR.

**Output**: NEW [notes/2026-05-30-s03-furfur-svg-structure-probe-verdict.md](../notes/2026-05-30-s03-furfur-svg-structure-probe-verdict.md) documenting that the Furfur SVG has only 20 `<path>` elements / 25 subpath-starts / 132 numeric labels — NOT 126 per-AC polygons. Path geometry represents district-fill groups; AC identity lives only in numeric `<text>` labels at centroids. Supersedes Row 5.1's optimistic 10-11h estimate.

**Gates**: 1 only (research-only PR; notes + plan-doc updates).

---

### Row 5.1 - S03 Assam Furfur SVG -> GeoJSON pipeline

**Status**: BLOCKED on Row 4.6 probe finding.

**Source**: [File:Wahlkreise zur Vidhan Sabha von Assam (2023-).svg](https://commons.wikimedia.org/wiki/File:Wahlkreise_zur_Vidhan_Sabha_von_Assam_(2023-).svg) by Furfur, CC-BY-SA 4.0, 6.14 MB, 1326x919 viewBox.

**Row 4.6 probe finding** (see [notes/2026-05-30-s03-furfur-svg-structure-probe-verdict.md](../notes/2026-05-30-s03-furfur-svg-structure-probe-verdict.md)): SVG has only **20 `<path>` elements with 25 subpath-starts** + **132 numeric `<text>` labels** at AC centroids. NOT 126 per-AC polygons. AC names appear only in the Wikimedia description, not in the SVG.

**Three revised paths**:

- **Path A - Voronoi tessellation around 126 numeric label centroids** (L-XL, ~20-40h): clip Voronoi cells to the union of district-fill polygons; affine-warp to lat/lon. Produces 126 polygons that **approximate** AC boundaries. Requires `shapely` + `scipy.spatial.Voronoi` + `numpy` (none currently in venv). Risk: shipping approximated boundaries labeled as "post-2023 delimitation" is misleading without a prominent caveat.

- **Path B - Contact Furfur for source files** (S, unknown timeline): open a discussion on https://commons.wikimedia.org/wiki/User_talk:Furfur asking for the source data (Adobe Illustrator native file, georeferenced shapefile). If Furfur shares the source, full pipeline becomes trivial.

- **Path C - Keep T4 district fallback** (S, ~0.5h): current S03 state-page renders district outlines with "boundaries pending post-2023 delimitation" tooltip. Honest about the gap. Cost: zero engineering. Trade-off: S03 stays only-state without per-AC granularity until a real source ships.

**Recommended unblock**: Path B (cheap, unbounded payoff) -> if Furfur unresponsive within 4-6 weeks, ask user to authorise Path A with a citizen-visible caveat ribbon. Until then keep Path C as the shipped experience.

**Effort**: BLOCKED until Path B verdict or user authorises Path A.
**Branch**: TBD when unblocked.

---

### Row 4.7 - S01 Susewind 2014 probe + verdict (this PR)

**Status**: PENDING this PR.

**Output**: NEW [notes/2026-05-30-s01-susewind-probe-verdict.md](../notes/2026-05-30-s01-susewind-probe-verdict.md) documenting that the Susewind 2014 release (ramSeraph mirror) ships 292 features for "Andhra Pradesh" at PRE-bifurcation unified AP+TG numbering (first AC = "Sirpur" in TG-side Adilabad), AND carries CC-BY-SA-NC license (non-commercial). NOT viable for S01 post-2014 175-feature target. Reaffirms prior PR #454 §C.6 finding. Path B (in-repo surgery on existing LGD source) is the only remaining structural path; Path D (keep HTL S01 indefinitely) is the zero-effort alternative.

**Gates**: 1 only (research-only PR).

---

### Row 5.7 - S01 AP pre-bifurcation residue cleanup

**Status**: PENDING.

**Current state** (per [notes/2026-05-29-ap-assam-ac-source-hunt-handover.md](../notes/2026-05-29-ap-assam-ac-source-hunt-handover.md) section 0):
- HTL S01 currently ships 177 features (post-2014 AP-only), NOT 294 as some older notes claim.
- ramSeraph LGD S01 ships 294 features (pre-2014 unified AP+TG numbering).
- ECI SoT = 175 features (post-2014 AP-only).
- Current frontend uses HTL with ~100% name parity to ECI post-2014.

**Three paths**:

**Path A - Susewind 2014 probe (recommended first, ~1-2h research-only)**:
- Check https://github.com/ramSeraph/indian_admin_boundaries releases/tags for Susewind 2014 academic source.
- Confirm feature count = 175 + post-2014 AC names present.
- If available: adopt as `ramseraph_susewind_2014_ac_s01`; drop HTL S01.

**Path B - In-repo surgery (fallback, ~3-4h)**:
- Filter ramSeraph LGD S01 by `state_lgd == 1` (175 features after dropping TG).
- Hand-curate `datasets/reference/in/states/S01/ac_no_remap.json` mapping pre-2014 LGD numbering -> post-2014 ECI numbering via centroid or name lookup.
- Replace HTL with filtered+remapped output.
- `verify_ac_parity --state S01` expect >=95%.

**Path C - Wait for community (DO NOT block)**.

**Acceptance**:
- HTL touchpoint count drops 4 -> 3 (S01 dropped; S03 + U07 + U10 remain).
- [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) S01 entry swapped from HTL.
- `verify_ac_parity --state S01` exit 0.

**Effort**: S (Path A) -> M (Path B fallback).
**Branch**: `feat/p5-s01-ap-residue-cleanup`.

---

### Row 5.22 - Promote `verify_ac_parity` to pytest gate (option beta)

**Status**: PENDING.

**Problem**: Original A.4 row was "AC coverage >= 90% threshold (pixel comparison)" - "pixel comparison" is meaningless (canvas fill is data-driven, not boundary-driven).

**Reframe**: The actual coverage gate already exists at [tools/boundaries/verify_ac_parity.py](../tools/boundaries/verify_ac_parity.py) (`NAME_PARITY_THRESHOLD: float = 0.95`). It's currently invoked manually per state. Promote to pytest gate so every PR enforces it across all states.

**Steps**:
1. NEW `backend/tests/test_ac_parity_per_state.py` that imports `verify_ac_parity.main()` (or its public function), invokes it with no `--state` argument (defaults to DEFAULT_STATES tuple of 10 D.2 promotion states), asserts exit 0.
2. Confirm Tier of test: keep Tier-A (always-on in `pytest -q`) since `verify_ac_parity` reads `datasets/reference/in/states/<eci>/constituencies.json` (real fixture, no real-corpus walk; D.2 states have stable fixtures).
3. Document in [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md) under a new "AC parity gate" sub-section.

**Acceptance**:
- `pytest backend/tests/test_ac_parity_per_state.py -q` exit 0.
- `pytest -q` baseline F2 unchanged (12 failed / 1449 passed minimum) OR moves to 1450 passed (one new test).
- Any future PR that breaks per-state name parity below 0.95 fails Gate 2.

**Effort**: S (~1-2h).
**Branch**: `feat/p5-ac-parity-pytest-gate`.

**Rejected alternatives**:
- Option alpha (geometry-coverage validator `sum(polygon_area)/state_area >= 0.90`): meaningful but new code; defer.
- Option gamma (drop row): rejected; the existing tool deserves a CI seat.

---

### Row 5.5 - U09 Ladakh villages source probe

**Status**: PENDING (research-only PR; ship Path D if no source found).

**Problem**: `Bhuvan_JK_Villages` covers U08 only; U09 Ladakh deferred indefinitely. No source confirmed today.

**Paths**:

**Path A - Bhuvan/NRSC probe (~2-4h research-only)**:
- Probe https://bhuvan.nrsc.gov.in/ for Ladakh village layer; check ramSeraph mirror at https://indianopenmaps.com/api/routes for `/ladakh/villages/` namespace; check https://github.com/ramSeraph/indian_admin_boundaries for "ladakh" + "villages" releases.
- If found: mirror [tools/boundaries/lift_villages_jk_bhuvan.py](../tools/boundaries/lift_villages_jk_bhuvan.py) (PR #453) pattern as `lift_villages_u09_bhuvan.py`. Ship in separate PR.

**Path B - SVAMITVA portal (~2h)**:
- Probe https://svamitva.nic.in/ for Ladakh village property boundaries.
- Risk: SVAMITVA is property-centroid, not polygons; likely unsuitable.

**Path C - Census 2011 + manual mapping (~4-6h)**: rejected upstream; introduces unmaintainable curation burden.

**Path D - Defer + document (~0.5h)**:
- Add U09 to coverage gaps list in [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) (or `docs/concepts/boundary-data-philosophy.md` if it exists).
- Reclassify Row 5.5 from "BLOCKED on upstream" to "BLOCKED on citizen-trigger".

**Acceptance** (research-only PR):
- Either NEW `notes/<date>-u09-ladakh-villages-source-probe.md` documenting Path A/B/C/D verdict + concrete candidate URL if found.
- OR if Path A succeeds: ship as separate lift PR (do not bundle).

**Effort**: S (probe) or M (if Path A lift ships).
**Branch**: `feat/p5-u09-ladakh-villages-probe`.

---

## section 3. ESCALATE-only items

These items REQUIRE user authorisation to start (cross-cutting / Level-5 / re-scope):

- **Rows R2+ of [TODO/20260530-eci-to-lgd-acid-migration-plan.md](20260530-eci-to-lgd-acid-migration-plan.md)** (the eci_no -> AC_ID migration arc): all ESCALATE per CLAUDE.md §6 Level-5. R1 audit research-PR ships independently; user reads + picks strategy before R2 unblocks.
- **Re-scoping any row 5.11-5.19** (Category 4 explicit non-goals from inventory): requires citizen-indicator trigger + user re-scoping.

---

## section 4. Closed rows archive

Distillation routing per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md). All shipped via PRs #460 / #462 / #464 / #465 / #468 / #469.

| Row | PR | Distilled-to |
| --- | --- | --- |
| 1.1 | #460 | `boundaryFooterHtml()` in [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts); rule baked into F8 above. |
| 1.2 | #460 | [frontend/e2e/state-ac-coverage.spec.ts](../frontend/e2e/state-ac-coverage.spec.ts). |
| 1.3 | #460 | Autonomy stanza in [docs/agents/bootstrap.md](../docs/agents/bootstrap.md); inventory at [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md); predecessor at `docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md`. |
| 2.1 | #462 | NEW [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) (3-convention rule + Bhuvan/LGD/ramSeraph lineage). |
| 2.2 | #462 | APPENDED to [docs/how-to/add-new-boundary-layer.md](../docs/how-to/add-new-boundary-layer.md) (ULB-keyed shards). |
| 2.3 | #462 | [docs/how-to/add-new-boundary-layer.md](../docs/how-to/add-new-boundary-layer.md) (when-to-fork-vs-consolidate). |
| 2.4 | #462 | NEW [docs/how-to/digitize-ac-from-pdf.md](../docs/how-to/digitize-ac-from-pdf.md) (4-tier ladder + QGIS workflow). KEPT durable for future delim-PDF states; S03-specifically SUPERSEDED by Row 5.1. |
| 2.5 | #462 | [docs/architecture/decisions/0029-unmapped-region-chips.md](../docs/architecture/decisions/0029-unmapped-region-chips.md) (D.1.A user-mandate backlinks). |
| 3.1 | n/a | COLLAPSED upstream by PR #457 (boundaries-conform regex widened). |
| 4.1 | #464 | TODO blocks in [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) + [frontend/src/lib/boundaries.ts](../frontend/src/lib/boundaries.ts). |
| 4.2 | #465 | REVERTED by 4.3. Lesson: don't distill-on-complete while inventory rows remain LIVE. |
| 4.3 | #468 | Un-archived this plan-doc + baked SVG pivot for S03 + restructured to active follow-ups. |
| 4.4 | #469 | NEW [TODO/20260530-eci-to-lgd-acid-migration-plan.md](20260530-eci-to-lgd-acid-migration-plan.md) (Level-5 successor; R1 PENDING + R2+ ESCALATED). |

---

## See also

- [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md) - 30-item inventory (per-row rationale).
- [TODO/20260530-eci-to-lgd-acid-migration-plan.md](20260530-eci-to-lgd-acid-migration-plan.md) - Level-5 successor for eci_no -> AC_ID migration.
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) - autonomy stance.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - 5-gate DoD + post-merge cleanup.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - 6-step distillation at plan close.
- [docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md](../docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md) - predecessor (CLOSED).
