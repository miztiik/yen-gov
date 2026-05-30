# Boundary Follow-ups Execution Plan (autonomous)

**Last Updated**: 2026-05-30

**Predecessor**: [docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md](../docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md) (CLOSED via PRs #434-#456) and [TODO/20260529-boundary-rip-and-replace-plan.md](../TODO/20260529-boundary-rip-and-replace-plan.md).

**Followups inventory**: [TODO/20260530-boundary-plan-followups.md](../TODO/20260530-boundary-plan-followups.md) (30 items across 8 categories).

**Operating doctrine**: This plan executes under the autonomy stance documented in [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) section "Autonomous plan execution - AUTO is the default". Read that section before starting any row.

---

## section 0. Operating contract (read once, act every row)

### 0.1 Default stance

- **AUTO every row**: execute work, run 5-gate DoD per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md), `gh pr merge --squash --delete-branch`, advance to next row.
- **Personas as scouts, not gates**: Citizen / Hans / Max / Gregor / Fowler / Jony / Andre may be dispatched as Explore subagents for facts; their verdicts inform action, never request approval.
- **User unavailable mid-execution**: stay in scope, finish the in-flight row, do not invent or contract scope.

### 0.2 Baked facts (no decision points within these)

| Fact | Value | Source |
| --- | --- | --- |
| F1 | Branch naming: `feat/<phase>-<short-id>` (Phase 1 = `feat/p1-bundle-chip-and-distillations`). | docs/how-to/ship-a-pr.md |
| F2 | Pre-existing pytest failures = 12 (livestock NAIP IV + owner_reg schema_version 4.4 vs 6.0, indicator-catalogue v21 update_period_days, schema_v5 x_version, energy build envelopes, concept-resolve C2-C6). Not introduced by this plan. Gate 2 passes iff `passed` count >= 1449 AND `failed` count <= 12. | backend/.tmp_pytest2.log on `aad024a9` |
| F3 | Vitest baseline = 0 failures / 113 files / 2730 passed / 21 skipped on `aad024a9` (the U08/U09 orphan failure tracked in inventory Category 6 is already CLOSED by PR #457 widening the villages regex). Gate 4 passes iff failed = 0 AND test-file count >= 113. | this session vitest run |
| F4 | Pre-existing svelte-check baseline: 0 errors / 7 warnings in 6 files. Gate 3 passes iff errors = 0 AND warnings <= 7. | frontend bun run check on `aad024a9` |
| F5 | Master worktree currently holds `[main]` lock at `71cb4a59`. `gh pr merge --squash --delete-branch` from worker WILL emit cosmetic `failed to run git: fatal: 'main' is already used by worktree` AFTER server-side merge succeeds. Verify via `gh pr view <#> --json state,mergedAt,mergeCommit`, then manually `git push origin --delete <branch>`. | git worktree list (this session) |
| F6 | Worker Python venv: `..\yen-gov\.venv\Scripts\python.exe`. Has duckdb. No pyarrow, no numpy. Use duckdb for parquet inspection; never import pyarrow / pandas. | This session |
| F7 | `bun run dev` cd-stripping rule: ALWAYS use `send_to_terminal` for dev-server start commands; `run_in_terminal` will strip the cd preamble. | Recurring lesson (4 sessions) |
| F8 | Boundary attribution chip on maps = icon-only glyph U+24D8 (rendered as `&#9432;`), with full label "Boundary sources &amp; licensing" on the `title` attribute, linking to `/about?section=maps`. Implemented in `frontend/src/lib/maplibre/sources.ts` `boundaryFooterHtml()`. | This PR |
| F9 | NEVER concurrent vitest + pytest. Vitest worker pool crashes on socket contention with pytest. Sequence: pytest sync (sole tenant) -> svelte-check sync (sole tenant) -> vitest sync (sole tenant). | Recurring lesson |
| F10 | ASCII rule: NEW Markdown / agent-customization files use plain ASCII only. Use `-` not em-dash, `->` not arrow, `[x]/[ ]/[!]/[-]` not emoji status. Existing files grandfathered. NEVER bulk-substitute ASCII into existing prose - re-author from scratch instead (one bulk-substitute truncated this plan-doc to 0 bytes this session). | This session lesson |
| F11 | Browser smoke (Gate 5) for any frontend change touching map registry / attribution: `/s/tamil-nadu` + `/s/tamil-nadu/ac/1` cover both choropleth + AC-mode paths. Tooltip presence verified via `page.locator('.maplibregl-ctrl-attrib-inner a').first().getAttribute('title')`. | This PR |

### 0.3 ESCALATE triggers (and ONLY these)

ESCALATE means: stop, post a message summarising the trigger, wait for user. Do NOT escalate for anything else.

1. **Schema major bump** (e.g. indicator schema 5.x -> 6.x, or descriptor schema 1.x -> 2.x).
2. **New ADR proposal** required to unblock a row (existing ADR amendment is in-scope).
3. **Election-results data deletion** request (any DROP / DELETE against `datasets/elections/`).
4. **Persona-conflict-unresolved** after 1 round of cross-persona dispatch (e.g. Jony says ship, Citizen says block, Hans abstains).
5. **3x cost overrun** on a row's estimated effort tier (S / M / L / XL).

### 0.4 Per-row execution contract

1. Read the row's "Steps" block in order; do not skip steps.
2. Run the 5-gate DoD on the worker branch. Gates 2 + 3 + 4 are sole-tenant per F9.
3. Author commit msg + PR body as ASCII-only `.tmp_*` files via `create_file` (not bulk-substitute).
4. `git push -u origin <branch>` then `gh pr create --base main --head <branch> --title ... --body-file .tmp_pr_body.md`.
5. Replace `_pending_` in any in-PR doc references with the freshly-allocated `#NNN`, commit as commit 2, push.
6. `gh pr merge <#> --squash --delete-branch`. Verify via `gh pr view <#> --json state,mergedAt,mergeCommit`. Per F5, manually `git push origin --delete <branch>` if needed.
7. Update the Status Reckoner row's status marker + PR# in this file.
8. Run post-merge cleanup per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) section "Post-merge cleanup".

### 0.5 Distill-on-complete

When all rows reach `[x] DONE` or `[-] COLLAPSED`, run the 6-step distillation per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) and `git mv` this file to `docs/archive/plans/`.

---

## section 1. Status Reckoner (UPDATE AFTER EVERY ROW)

> **Plan-doc state**: ACTIVE. The 10 execution rows (Phases 1-4) merged 2026-05-30. The 22 follow-up rows (Phase 5, derived from inventory [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md)) remain LIVE. Plan closes when all 32 rows reach `[x] DONE` / `[-] COLLAPSED` / `[!] ESCALATED-and-resolved`. This file moves to `docs/archive/plans/` only at that point.

### Execution rows (merged)

| Row | Phase | Title | Status | PR |
| --- | --- | --- | --- | --- |
| 1.1 | P1 Bundle | Icon-only attribution chip on map footer | [x] DONE | #460 |
| 1.2 | P1 Bundle | e2e assertion swap (`toHaveText` -> `toHaveAttribute('title', ...)`) + skip-trap guard | [x] DONE | #460 |
| 1.3 | P1 Bundle | Predecessor plan-doc archive + bootstrap.md autonomy stanza + inventory + this plan-doc | [x] DONE | #460 |
| 2.1 | P2 Distill | C.2 panchayats verdict distillation -> docs/concepts + docs/architecture | [x] DONE | #462 |
| 2.2 | P2 Distill | C.3 ULB wards verdict distillation -> docs/architecture | [x] DONE | #462 |
| 2.3 | P2 Distill | C.4 villages verdict distillation -> docs/how-to/add-new-boundary-layer.md | [x] DONE | #462 |
| 2.4 | P2 Distill | A.1.b T3 PDF vectorization workflow -> docs/how-to/digitize-ac-from-pdf.md (see SVG-pivot correction in section 3 Row 2.4) | [x] DONE | #462 |
| 2.5 | P2 Distill | ADR-0029 retirement backlink to D.1.A user mandate | [x] DONE | #462 |
| 3.1 | P3 Cleanup | Vitest U08/U09 villages orphan: delete OR allow-list the 14 entries | [-] COLLAPSED | n/a |
| 4.1 | P4 Optional | Code-marker TODO annotations in sources.ts + boundaries.ts (Category 8) | [x] DONE | #464 |
| 4.2 | P4 Distill | Premature distill-on-complete archive of this plan-doc | [x] DONE | #465 |
| 4.3 | P4 Correction | Un-archive this plan-doc + bake SVG pivot for S03 + restructure §6 to active follow-ups | [ ] PENDING | _pending_ |

### Active follow-up rows (Phase 5; from inventory)

| Row | Source (inventory category) | Title | Effort | Value | Status | Trigger / unblock |
| --- | --- | --- | --- | --- | --- | --- |
| 5.1 | Cat 2 #2 (A.1.b) | S03 Assam Furfur SVG -> GeoJSON pipeline (supersedes T3 PDF for S03) | L (~10-20h auto) | HIGH | [ ] PENDING | User-authorized 2026-05-30 (this PR) |
| 5.2 | Cat 5 #1 | Open Level-5 successor plan-doc for `eci_no` -> `AC_ID` corpus migration (research-only first row) | S (this PR) + XL (multi-PR migration) | HIGH | [ ] PENDING | User-authorized 2026-05-30 (this PR opens the design-research plan-doc; migration rows pause for user) |
| 5.3 | Cat 1 #1 | C.2.d Bhuvan panchayat gap-fill (9 states/UTs) | M | MED | [ ] BLOCKED | Citizen-trigger: PRR / MGNREGS / PRI-funds indicator at panchayat grain in target state |
| 5.4 | Cat 1 #2 | C.3.d Urban ward gap-fill (WB-AMRUT / Shillong / LivingAtlas; 7 states) | M | MED | [ ] BLOCKED | Citizen-trigger: urban-governance / Swachh-Survekshan / AMRUT indicator at ward grain |
| 5.5 | Cat 1 #3 | C.4 Ladakh villages (U09) gap-fill | S | LOW | [ ] BLOCKED | Upstream: ramSeraph OR LGD releases Ladakh village geometry |
| 5.6 | Cat 1 #4 | C.4 other 7-state villages gap-fill | S per state | LOW | [ ] BLOCKED | Per-state upstream + village-grain citizen indicator |
| 5.7 | Cat 2 #1 (A.1.a) | S01 AP pre-bifurcation residue cleanup (no-fill TG polygons) | L | MED | [ ] BLOCKED | Upstream: ramSeraph LGD v2 with post-bifurcation AP-only geometry |
| 5.8 | Cat 3 #1 | C.2.c Panchayat district-picker UI component | M | MED | [ ] BLOCKED | Measured data + first citizen indicator at panchayat grain |
| 5.9 | Cat 3 #2 | C.3.c ULB ward-picker UI component | M | MED | [ ] BLOCKED | Measured data + first citizen indicator at ward grain |
| 5.10 | Cat 3 #3 | Frontend villages registry (sources.ts + contract test + picker) | M | BLOCKED | [ ] BLOCKED | Citizen-trigger: first village-grain indicator (MGNREGA person-days, micro-watershed, PMGSY) |
| 5.11 | Cat 4 #1 | Historical districts (1941-2001) | L | LOW | [ ] BLOCKED | Citizen-trigger: explicit historical-district indicator demand |
| 5.12 | Cat 4 #2 | Census 2011 polygon snapshot | M | LOW | [ ] BLOCKED | Citizen-trigger: Census-grain historical indicator |
| 5.13 | Cat 4 #3 | SHRUG Census 2011 harmonized variant | M | LOW | [ ] BLOCKED | Same as 5.12 |
| 5.14 | Cat 4 #4 | Habitations / sub-village granularity | XL | LOW | [ ] BLOCKED | Citizen-trigger: sub-village indicator (unlikely) |
| 5.15 | Cat 4 #5 | Polling stations (7 ramSeraph sources) | L | MED | [ ] BLOCKED | Citizen-trigger: `/e/` event-page polling-station drill-down |
| 5.16 | Cat 4 #6 | Slums (8 sources) | L per source | MED | [ ] BLOCKED | Citizen-trigger: slum-welfare / urban-health indicator |
| 5.17 | Cat 4 #7 | ULB cadastrals (52 ramSeraph sources) | XL | LOW | [ ] BLOCKED | Citizen-trigger: property-tax / municipal-revenue indicator |
| 5.18 | Cat 4 #8 | Post Offices / PostalGIS (point layer) | S | LOW | [ ] BLOCKED | Citizen-trigger: postal-service indicator |
| 5.19 | Cat 4 #9 | Cadastrals / water / transport / power / buildings / industries / floods / DEM / lithology / SOI topo / lineament | M per layer | family-dependent | [ ] BLOCKED | Per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md): family-specific `_meadow/` ingest when family-indicator adopts |
| 5.20 | Cat 5 #2 | Multi-source villages consolidation (per-state -> `--source` flag refactor) | M | LOW | [ ] BLOCKED | 2nd non-J&K state villages gap-fill lands |
| 5.21 | Cat 5 #3 | Sub-panchayat / GP Ward layer | M | LOW | [ ] BLOCKED | Upstream + citizen-trigger at GP-ward grain |
| 5.22 | Cat 6 #1 | A.4 AC coverage >= 90% threshold re-introduction (pixel comparison) | S | MED | [ ] BLOCKED | Election-results ingest completion |

Legend: `[x] DONE` / `[ ] PENDING` (executable) / `[!] ESCALATED` / `[-] COLLAPSED` / `[ ] BLOCKED` (executable only when trigger fires).

Total: 32 rows. 11 DONE + 1 COLLAPSED + 2 PENDING-and-executable (4.3 this PR, 5.1 next; 5.2 also next) + 1 PENDING-but-paused-for-design (5.2 migration rows after research) + 17 BLOCKED-on-trigger. Plan-doc closes when all 32 resolve.

---

## section 2. Phase 1 - Polish bundle PR (1 PR, this branch)

Single PR `feat/p1-bundle-chip-and-distillations` covering all 3 Row-1 items. Already in flight on this branch.

### Row 1.1 - Icon-only attribution chip

**File**: [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) `boundaryFooterHtml()`.

**Behaviour**: Visible glyph `&#9432;` (U+24D8 INFORMATION SOURCE); label "Boundary sources &amp; licensing" moves to the `title` attribute; one click navigates to `/about?section=maps`.

**Steps**:
1. Apply the icon-only chip + title-attribute in `boundaryFooterHtml()`.
2. Update the function-level comment to explain icon-only refinement + the `title` semantic.
3. Verify the link still works under `BASE_URL = "/"` (dev) and a `BASE_URL = "/yen-gov"` simulation.

### Row 1.2 - e2e assertion swap + skip-trap guard

**Files**: [frontend/e2e/state-ac-coverage.spec.ts](../frontend/e2e/state-ac-coverage.spec.ts).

**Behaviour**:
- Assertion at line ~150 changes from `.toHaveText(/Boundary sources & licensing/)` to `.toHaveAttribute('title', /Boundary sources & licensing/)`.
- Comment at line ~28 updated to reflect icon-only chip render.
- `afterEach` guards against `trap` being undefined when `mobile-pixel-5` project skips in `beforeEach`. Already shipped in commit `aad024a9` on this branch.

### Row 1.3 - Plan-docs + bootstrap autonomy stanza

**Files**:
- `git mv TODO/20260527-state-ac-map-universal-coverage-plan.md docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md` (predecessor archive)
- `docs/agents/bootstrap.md`: add "Autonomous plan execution - AUTO is the default" stanza
- `TODO/20260530-boundary-plan-followups.md`: 30-item residual inventory (already authored)
- `TODO/20260530-boundary-followups-execution-plan.md`: this file (ACTIVE; un-archived in Row 4.3 after the premature Row 4.2 archive)

**Acceptance**: Phase-1 bundle PR ships green on 5 gates per `docs/how-to/ship-a-pr.md`. After merge, all 3 rows flip to `[x] DONE` with PR# stamped.

---

## section 3. Phase 2 - Docs distillation quick-wins (1 PR, ~1 day)

Single Level-2 docs PR bundling 5 distillations. Effort: 5xS. Value: HIGH (saves future agents from re-discovering source-hunt findings).

### Row 2.1 - C.2 panchayats verdict distillation

**Source**: [notes/2026-05-30-c2-panchayats-source-hunt-verdict.md](../notes/2026-05-30-c2-panchayats-source-hunt-verdict.md).

**Output**:
- NEW: `docs/concepts/admin-level-sourcing.md` (3-convention rule + Bhuvan / LGD / ramSeraph lineage).
- APPEND: "Panchayats partition strategy" section to `docs/architecture/boundaries/README.md` (or create if absent).

### Row 2.2 - C.3 ULB wards verdict distillation

**Source**: [notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md](../notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md).

**Output**: APPEND "ULB Wards partition strategy" section to `docs/architecture/boundaries/README.md`.

### Row 2.3 - C.4 villages verdict distillation

**Source**: [notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md](../notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md).

**Output**: NEW `docs/how-to/add-new-boundary-layer.md` covering "when to fork vs consolidate orchestrators".

### Row 2.4 - A.1.b T3 PDF vectorization workflow

**Source**: plan-doc row A.1.b narrative + [notes/2026-05-29-phase-b-verdict-correction.md](../notes/2026-05-29-phase-b-verdict-correction.md).

**Output**: NEW `docs/how-to/digitize-ac-from-pdf.md` covering the 4-tier fallback ladder + T3 QGIS workflow (text-only; screenshots deferred).

> **SVG-pivot correction (2026-05-30)**: Mid-conversation between Row 2.4 distillation and Row 4.2 archive, the user pointed at https://commons.wikimedia.org/wiki/File:2026_Assam_Legislative_Assembly_Election_ASM_Seat_Sharing_Map.svg and the agent confirmed the base layer (`Wahlkreise zur Vidhan Sabha von Assam (2023-).svg` by Furfur, CC-BY-4.0, 6.52 MB, georeferenced post-2023 delim with all 126 ACs) is a viable Tier-1 source for S03. The SVG-to-GeoJSON pipeline is ~10-20h autonomous, NOT the 40-60h QGIS PDF tracing estimated by `docs/how-to/digitize-ac-from-pdf.md`. The agent failed to bake this pivot into the plan-doc / inventory / distillation-doc / supersede the S03 verdict notes; that correction lands in Row 4.3 + Row 5.1 of this plan-doc + the SUPERSEDED header on [notes/2026-05-29-s03-pdf-probe-verdict.md](../notes/2026-05-29-s03-pdf-probe-verdict.md) + [notes/2026-05-29-phase-b-verdict-correction.md](../notes/2026-05-29-phase-b-verdict-correction.md). The `digitize-ac-from-pdf.md` how-to is KEPT intact because the 4-tier ladder + QGIS workflow remains durable knowledge for any future state shipping a delim order WITHOUT a Furfur-style cartographer; only the S03-specific framing is superseded.

### Row 2.5 - ADR-0029 retirement backlink

**File**: `docs/architecture/decisions/0029-*.md` (verify exact filename).

**Output**: Embed verbatim user mandate quote from 2026-05-30 D.1.A retirement; backlink to predecessor plan row D.1.A.

**Acceptance for Phase 2**: 5 distillations land in 1 docs PR. Gate 1 (validate) + Gate 4 (vitest baseline) only; Gates 2, 3, 5 trivially pass (no Python, no Svelte, no map render touched).

---

## section 4. Phase 3 - Test cleanup

### Row 3.1 - Vitest U08/U09 villages orphan [COLLAPSED]

**Status**: COLLAPSED. Resolved upstream of this plan by PR #457 (`fix(contracts): widen boundaries-conform villages regex to accept slug district segments`). Vitest now shows 113 files / 2730 passed / 0 failed on `aad024a9`. The inventory entry (`TODO/20260530-boundary-plan-followups.md` Category 6) remains for archaeological context but no action needed.

---

## section 5. Phase 4 - Optional polish (deferred unless triggered)

### Row 4.1 - Code-marker TODO annotations [DONE PR #464]

Per inventory Category 8: forward-looking `// TODO:` markers added above
`PANCHAYAT_BOUNDARY_BY_DISTRICT` + `WARD_BOUNDARY_BY_ULB` in
[frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) (flag the deferred C.2.c + C.3.c
picker UI shims) and above the `JOIN_KEYS` table in
[frontend/src/lib/boundaries.ts](../frontend/src/lib/boundaries.ts) (flag the absent VILLAGE_BOUNDARY_BY_DISTRICT
registry, blocked on first village-grain citizen indicator). Markers
backlink each follow-up to inventory Category 3.

Originally tagged "bundle-with-nearby-edit, not standalone" (Value=LOW).
Shipped standalone on user override 2026-05-30; cost was ~3 lines of
diff per file with zero behaviour change so the bundle-only heuristic
did not apply.

---

## section 6. Phase 5 - Active follow-up rows (un-archived 2026-05-30)

Rows 5.1 + 5.2 are unblocked-and-actionable per user mandate 2026-05-30 ("WE NEED TO WORK ON THE 22 AND THE BELOW"). Rows 5.3-5.22 are blocked-on-upstream-or-citizen-trigger per inventory categorisation; each will execute as a standalone PR ONLY when its named trigger fires.

### Row 4.3 - Un-archive this plan-doc + bake SVG pivot + restructure to active follow-ups

**Trigger**: User correction 2026-05-30 calling out (a) plan-doc was archived prematurely with 22 inventory items still live; (b) Row 2.4 + Section 6 + inventory + 2 verdict notes still carried stale PDF-vectorization framing for S03 despite mid-conversation Furfur SVG verdict that was never baked in; (c) the plan-doc moved off `TODO/` while its inventory still lives there.

**Files**:
- `git mv docs/archive/plans/20260530-boundary-followups-execution-plan.md TODO/20260530-boundary-followups-execution-plan.md` (un-archive)
- This plan-doc: path-depth fix `]( ../../X)` -> `]( ../X)`; restructured Status Reckoner (execution rows + Phase 5 rows); SVG correction inline in Row 2.4; new sections 5 / 6 / 7; "Plan complete" block deleted
- `TODO/20260530-boundary-plan-followups.md`: Cat 2 #2 (A.1.b) + Cat 7 #4 (A.1.b ladder) entries rewritten - PDF-only estimate superseded by Furfur SVG pivot
- `docs/agents/bootstrap.md` L44: backlink reverted to `../../TODO/20260530-boundary-followups-execution-plan.md`
- `docs/architecture/decisions/0029-unmapped-region-chips.md` L101: backlink reverted to `../../../TODO/20260530-boundary-followups-execution-plan.md`; drop "(CLOSED 2026-05-30)" parenthetical
- `frontend/src/lib/maplibre/sources.ts` L49: comment backlink reverted to `TODO/20260530-boundary-followups-execution-plan.md`
- `notes/2026-05-29-s03-pdf-probe-verdict.md`: SUPERSEDED-2026-05-30 correction header (same pattern as `notes/2026-05-29-s03-assam-source-hunt-verdict.md`)
- `notes/2026-05-29-phase-b-verdict-correction.md`: S03 section SUPERSEDED-2026-05-30 correction header

**Gates**: 1 + 3 + 4 only (docs PR + 1 comment-line change in `.ts` - no pytest impact; no map render impact since only a comment changed).

**Steps**: 2-commit-then-squash (commit 1 = the work with `_pending_` for PR#; `gh pr create`; commit 2 = stamp `_pending_` -> `#NNN`; squash-merge).

### Row 5.1 - A.1.b S03 Assam Furfur SVG -> GeoJSON pipeline

**Status**: PENDING (user-authorized 2026-05-30; deferred to next session per residual capacity).

**Trigger**: User pointed at https://commons.wikimedia.org/wiki/File:2026_Assam_Legislative_Assembly_Election_ASM_Seat_Sharing_Map.svg on 2026-05-30. Agent confirmed base = `Wahlkreise zur Vidhan Sabha von Assam (2023-).svg` by Furfur (CC-BY-4.0, 6.52 MB / 1326x919, georeferenced post-2023 delim, all 126 ACs present). This supersedes the T3 PDF estimate of 40-60h for S03 specifically.

**Acceptance**:
- New `datasets/boundaries/in/ac/state=in_s03/all.geojson` with 126 features (was 33 districts) carrying `ac_no` (1-126) + `ac_name` (post-2023 SoT names) + `state_lgd=18` + Furfur source-attribution properties.
- `verify_ac_parity --state S03` returns 126/126 name parity to SoT.
- `STATE_AC.S03` in [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) switched from `district` to `ac` shard; `join_property: "ac_no"`; T4 interim tooltip removed.
- `verify_ac_parity --state S03` exit-0.
- Gate 5: `/s/assam/ac/1` renders "Gossaigaon" AC polygon (NOT Kokrajhar district).
- `notes/2026-05-29-s03-pdf-probe-verdict.md` SUPERSEDED header points at the resulting `feat(boundaries): A.1.b - S03 Assam Furfur SVG -> GeoJSON` PR for traceability.

**Source plan**:
1. Fetch SVG (CC-BY-4.0 attribution baked into `datasets/taxonomy/sources.parquet` via `derive_source_id("Wikimedia Commons", "Wahlkreise zur Vidhan Sabha von Assam (2023-).svg", "2023-")`).
2. Audit SVG structure: `<g>` groupings, `<path d="...">` elements per AC, viewBox bounds, layer-name conventions (Furfur uses German class names typically).
3. Georeference: solve the affine transform that maps SVG viewBox (1326x919 px) to Assam lat/lon bbox (~89.7E-96.0E, ~24.1N-28.2N). Use 3-4 known landmark points (e.g. Guwahati centroid, Silchar centroid, Tinsukia centroid) as control points; least-squares fit; verify residuals <100m for QA points.
4. Path extraction: per path, parse `d=` attribute via existing `svgpath` Python library OR custom mini-parser; convert to GeoJSON `Polygon` / `MultiPolygon` after applying the affine transform.
5. Property assignment: cross-reference Furfur layer label (German constituency name) to post-2023 SoT `eci_no` via `datasets/reference/in/states/S03/constituencies.json` name lookup; emit `ac_no` + `ac_name`.
6. Topology cleanup: dissolve adjacent-AC slivers; ensure 126 features with no overlaps + gaps <0.001 sq.km.
7. Pipeline.json entry: new S03 source = SVG with georeferencing-control-points + affine-transform; documented vintage `2023-08-11` (Delim Order date).
8. `verify_ac_parity --state S03` + Gate 5.

**Effort**: L (~10-20h autonomous; the georeferencing + path-extraction is the bulk; topology cleanup likely 2-4h).

**Branch**: `feat/p5-s03-furfur-svg-ac-geometry`.

**Why deferred to next session**: This session is long post-compaction; the SVG pipeline is non-trivial and warrants a fresh session with full context for the georeferencing math + 126-polygon QA loop.

### Row 5.2 - Open Level-5 successor plan-doc for `eci_no` -> `AC_ID` corpus migration

**Status**: PENDING (user-authorized 2026-05-30 for the research-only first PR; subsequent migration rows pause per CLAUDE.md §6 Level-5 "Design consultation only").

**Trigger**: User said "work on it" 2026-05-30. Predecessor inventory entry: Cat 5 #1.

**This PR's scope (research-only)**:
- NEW: `TODO/<YYYYMMDD>-eci-to-lgd-acid-migration-plan.md` with research-only first row.
- Section 1 Status Reckoner with one row: "R1 Audit all `eci_no` usages across election-results parquets + indicator-family tables + SoT files + frontend join logic".
- Section 2 ESCALATE triggers: ALL migration rows (data rewrite, schema change, join-key refactor) ESCALATE per CLAUDE.md §6 Level-5; agent does NOT execute beyond R1 without user design consultation.
- Section 3 R1 deliverable: write a research-note `notes/<date>-eci-to-acid-migration-surface-audit.md` listing every place `eci_no` is read or written.

**Effort**: S (this PR is the plan-doc skeleton + R1 audit; ~2-4h).

**Branch**: `feat/p5-level5-eci-to-acid-research-plan`.

**Why deferred to next session**: Same as 5.1 — fresh session for clean audit-trail authoring.

### Rows 5.3-5.22 - Blocked on upstream / citizen-trigger

See Status Reckoner section 1 for the full row list with per-row trigger conditions. Each row will execute as a standalone PR ONLY when its named trigger fires. No agent should pre-create blocked rows; the inventory + Status Reckoner is the durable lookup.

---

## section 7. ESCALATE triggers + closed-execution distillation routing (Phases 1-4)

### ESCALATE triggers (preserved from section 0.3)

These items REQUIRE user authorisation to start (effort >= L OR architectural scope):

- ~~**A.1.b S03 Assam T3 PDF vectorization sprint** (40-60h QGIS work; Value HIGH but cost L)~~ - SUPERSEDED by Row 5.1 Furfur SVG pivot (auto-able; user-authorized).
- ~~**Full `eci_no` -> LGD `AC_ID` corpus migration** (Level-5 multi-PR rewrite; XL)~~ - SUPERSEDED by Row 5.2 (research-only first PR user-authorized; migration rows still ESCALATE).
- **Re-scope any Category 4 explicit non-goal** (historical districts, Census 2011, slums, polling stations, etc.). All require citizen-indicator trigger + user re-scoping. Per Status Reckoner rows 5.11-5.19.

### Closed-execution distillation routing (Phases 1-4)

The 10 execution rows shipped via PRs #460 / #462 / #464 / #465. Distillation routing per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md):

| Row | PR | Distilled output (durable home) |
| --- | --- | --- |
| 1.1 Icon-only attribution chip | #460 | `boundaryFooterHtml()` in [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) (code is its own home); rule baked into plan section 0.2 F8 |
| 1.2 e2e assertion swap + skip-trap guard | #460 | [frontend/e2e/state-ac-coverage.spec.ts](../frontend/e2e/state-ac-coverage.spec.ts) (test is its own home) |
| 1.3 Predecessor archive + autonomy stanza + inventory + this plan-doc | #460 | "Autonomous plan execution - AUTO is the default" stanza in [docs/agents/bootstrap.md](../docs/agents/bootstrap.md); 30-item inventory in [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md); predecessor at `docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md` |
| 2.1 C.2 panchayats verdict | #462 | NEW [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) (3-convention rule + Bhuvan / LGD / ramSeraph lineage) |
| 2.2 C.3 ULB wards verdict | #462 | APPENDED to [docs/how-to/add-new-boundary-layer.md](../docs/how-to/add-new-boundary-layer.md) (ULB-keyed shards section) |
| 2.3 C.4 villages verdict | #462 | NEW [docs/how-to/add-new-boundary-layer.md](../docs/how-to/add-new-boundary-layer.md) (when-to-fork-vs-consolidate orchestrators) |
| 2.4 T3 PDF vectorisation workflow | #462 | NEW [docs/how-to/digitize-ac-from-pdf.md](../docs/how-to/digitize-ac-from-pdf.md) (4-tier fallback ladder + QGIS workflow) - KEPT durable for future delim-PDF states; S03 specifically SUPERSEDED by Row 5.1 SVG pipeline |
| 2.5 ADR-0029 retirement backlink | #462 | [docs/architecture/decisions/0029-unmapped-region-chips.md](../docs/architecture/decisions/0029-unmapped-region-chips.md) (5 explicit D.1.A user-mandate backlinks) |
| 3.1 Vitest U08/U09 villages orphan | n/a | COLLAPSED upstream by PR #457 (boundaries-conform regex widened) |
| 4.1 Code-marker TODO annotations | #464 | TODO blocks in [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) (PANCHAYAT_BOUNDARY_BY_DISTRICT + WARD_BOUNDARY_BY_ULB) + [frontend/src/lib/boundaries.ts](../frontend/src/lib/boundaries.ts) (JOIN_KEYS), each backlinked to [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md) Category 3 |
| 4.2 Premature distill-on-complete archive | #465 | REVERTED by Row 4.3 (this PR). Lesson: don't distill-on-complete while inventory rows remain LIVE; the 30-item inventory IS plan scope, not separate. |

Plan-doc REMAINS ACTIVE. Closes only when all Phase 5 rows reach `[x] DONE` / `[-] COLLAPSED` / `[!] ESCALATED-and-resolved`.

---

## See also

- [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md) - full 30-item inventory (Cat 7 + Cat 8 CLOSED; Cat 1-6 mapped to Phase 5 rows 5.3-5.22 above).
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) - autonomy stance + persona loading ritual.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - 5-gate DoD + post-merge cleanup.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - 6-step distillation to run when this plan closes.
- [docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md](../docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md) - predecessor plan (CLOSED via PR #460).
