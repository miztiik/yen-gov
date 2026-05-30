# Boundary Follow-ups Execution Plan (autonomous)

**Last Updated**: 2026-05-30

**Predecessor**: [docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md](../docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md) (CLOSED via PRs #434-#456) and [TODO/20260529-boundary-rip-and-replace-plan.md](20260529-boundary-rip-and-replace-plan.md).

**Followups inventory**: [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md) (30 items across 8 categories).

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

| Row | Phase | Title | Status | PR |
| --- | --- | --- | --- | --- |
| 1.1 | P1 Bundle | Icon-only attribution chip on map footer | [x] DONE | #460 |
| 1.2 | P1 Bundle | e2e assertion swap (`toHaveText` -> `toHaveAttribute('title', ...)`) + skip-trap guard | [x] DONE | #460 |
| 1.3 | P1 Bundle | Predecessor plan-doc archive + bootstrap.md autonomy stanza + inventory + this plan-doc | [x] DONE | #460 |
| 2.1 | P2 Distill | C.2 panchayats verdict distillation -> docs/concepts + docs/architecture | [x] DONE | #462 |
| 2.2 | P2 Distill | C.3 ULB wards verdict distillation -> docs/architecture | [x] DONE | #462 |
| 2.3 | P2 Distill | C.4 villages verdict distillation -> docs/how-to/add-new-boundary-layer.md | [x] DONE | #462 |
| 2.4 | P2 Distill | A.1.b T3 PDF vectorization workflow -> docs/how-to/digitize-ac-from-pdf.md | [x] DONE | #462 |
| 2.5 | P2 Distill | ADR-0029 retirement backlink to D.1.A user mandate | [x] DONE | #462 |
| 3.1 | P3 Cleanup | Vitest U08/U09 villages orphan: delete OR allow-list the 14 entries | [-] COLLAPSED | n/a |
| 4.1 | P4 Optional | Code-marker TODO annotations in sources.ts + boundaries.ts (Category 8) | [x] DONE | #464 |

Legend: `[x] DONE` / `[ ] PENDING` / `[!] ESCALATED` / `[-] COLLAPSED`.

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
- `TODO/20260530-boundary-followups-execution-plan.md`: this file

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

## section 6. Out of scope (do not start without ESCALATE)

These items are tracked in the inventory but require user authorisation to start (effort >= L OR architectural scope):

- **A.1.b S03 Assam T3 PDF vectorization sprint** (40-60h QGIS work; Value HIGH but cost L). User-led scoping needed.
- **Full `eci_no` -> LGD `AC_ID` corpus migration** (Level-5 multi-PR rewrite; XL). Successor plan-doc required.
- **Re-scope any Category 4 explicit non-goal** (historical districts, Census 2011, slums, polling stations, etc.). All require citizen-indicator trigger + user re-scoping.

---

## See also

- [TODO/20260530-boundary-plan-followups.md](20260530-boundary-plan-followups.md) - full 30-item inventory.
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) - autonomy stance + persona loading ritual.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - 5-gate DoD + post-merge cleanup.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - 6-step distillation to run when this plan closes.
- [TODO/20260529-boundary-rip-and-replace-plan.md](20260529-boundary-rip-and-replace-plan.md) - predecessor plan (CLOSED).
