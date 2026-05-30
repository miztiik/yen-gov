# Boundary rip-and-replace plan — session handover (2026-05-29 evening)

Companion to [TODO/20260529-boundary-rip-and-replace-plan.md](../TODO/20260529-boundary-rip-and-replace-plan.md).

Hands the boundary rip-and-replace plan off cleanly to the next session.

## Where the plan is RIGHT NOW

**Phase A: 100% DONE.**

| Row | What shipped | PR | SHA |
| --- | --- | --- | --- |
| A.1.a | S01 AP HTL→LGD swap with property rewrite (per-entity surgical fix) | #434 | `b5b6ce94` |
| A.1.b | S03 Assam Tier-4 district fallback (A.1.b ladder rung 2) | #435 | `d191638c` |
| A.3 | Centralised boundary-attribution component + `/about?section=maps` route | #436 | `6262eb22` |
| A.2 | 24-state STATE_AC registry sync via `sources.ts` | #437 | `3aea515b` |
| A.4 | 31-state Playwright per-state AC coverage e2e (`state-ac-coverage.spec.ts`) | #438 | `da04ab31` |

Net delivered: every state in scope has an AC drilldown page that renders the SoT name as H1, fetches the correct shard from the centralised registry, displays the centralised attribution footer link, and is regression-guarded by a 31-state Playwright matrix that runs in 3.4m on chromium.

**Phase C: 1 of 6 rows in flight.**

| Row | What shipped | PR | SHA |
| --- | --- | --- | --- |
| C.1 recon | Verdict file for LGD Blocks (Tier-1 found: ramSeraph LGD_Blocks.geojsonl.7z, 7323 features, CC0 1.0) | #439 | `9b3d886f` |

## What's queued for the NEXT session

### C.1 implementation (HIGH PRIORITY — verdict already done)

The recon verdict file at [notes/2026-05-29-c1-blocks-source-hunt-verdict.md](2026-05-29-c1-blocks-source-hunt-verdict.md) contains a 6-step execute-ready plan:

1. Add `pipeline.json` entry: `kind: "blocks"`, source.urls download/blocks/LGD_Blocks.geojsonl.7z, format `geojsonl_7z`, coord_precision 2, `id_property: "block_lgd"`, `name_property: "block_name"` (with first-snapshot confirmation note), tippecanoe minzoom 6 maxzoom 12.
2. Bump `datasets/schemas/boundary-layers.schema.json` (and any adjacent schemas) to add `"block"` to the `level` enum; bump `$id` minor version.
3. Run `python -m yen_gov.tools.boundaries.snapshot --layer blocks` (or the orchestrator analogous to `lift_subdistricts_national.py`) to produce ~33 per-state shards under `datasets/boundaries/in/blocks/state=in_<lc>/all.geojson` + sidecars.
4. First-snapshot inspection: confirm actual property names; update pipeline.json + registry if they differ from the assumed `block_lgd` / `block_name`.
5. Add `BLOCK_BOUNDARY` registry to `frontend/src/lib/maplibre/sources.ts` mirroring the `STATE_AC` shape.
6. Add `frontend/src/contracts/state-blocks-registry-coverage.test.ts` analogous to A.2's contract test (`discoverShards()` + `it.each(Object.entries(BLOCK_BOUNDARY))`).

**Citizen surface for blocks**: deferred to Phase C+1. Gate 5 for the C.1 implementation PR is the contract test passing + a browser smoke fetching 1 state's block shard successfully (no rendered page needed since blocks are not yet mounted on any topic page).

Estimated PR size: ~30-40 files (1 pipeline + 1-2 schema + 1 orchestrator + ~33 shards + 1 registry + 1 contract test + 1 plan-doc).

### C.2 — LGD Panchayats recon

ramSeraph has a `panchayats` release tag (mentioned in the C.1 verdict's investigation log). Dispatch a thorough Explore subagent: "verify Tier-1 LGD_Panchayats availability + lineage + property schema + feature count + license + naming distinction from any existing panchayat shipping in yen-gov". Ship as recon-only PR analogous to C.1 recon.

### C.3 — ULB Wards recon

ramSeraph has an `urban` release tag (mentioned in the C.1 verdict). Dispatch a thorough Explore subagent. Ship as recon-only PR.

### C.4 — Bhuvan J&K Villages recon

Bhuvan WMS / GeoServer probe needed. Higher risk of "no Tier-1 path found" — the plan-doc anticipates this might need a Tier-2 fallback to ramSeraph villages (which already ships J&K under partial coverage). Dispatch subagent with explicit instruction to probe Bhuvan first + report Tier-1 found / not-found / Tier-2 fallback.

### C.5 — LGD PC v2 recon (replace shijithpk for J&K)

Per the plan-doc, J&K is currently using shijithpk seat_id binding for PC boundaries; LGD has a PC v2 release that may be the durable replacement. Dispatch subagent + ship recon.

### C.6 — Susewind 2014 AP overlay (gated on B.1 verdict)

Per the plan-doc, this is gated on B.1's verdict (the AP 2014-vintage source-hunt PR). B.1 should already be merged; cross-reference its verdict file to determine whether C.6 is needed at all.

### D.1.A — retire per-entity side-fixes

The plan-doc's Phase D row D.1.A enumerates per-entity side-fixes to retire (Lakshadweep extractor + chip-strip + coverage exclusion + ADR-0029). This is a cleanup row that depends on Phase A + Phase C being stable. Likely a multi-file deletion + ADR-amendment PR; estimate ~10-15 files.

## Working agreements (carried forward from this session)

- **Recon-impl split is the right shape for ANY new-admin-level PR** (lesson from C.1). Don't ship a "blocks" implementation PR without a recon PR landed first.
- **2-commit-then-squash with `_pending_` -> PR# stamp** is the standard pattern; shipped clean on PR #439.
- **Cosmetic gh-merge error is expected** while master worktree holds `[main]` at stale `71cb4a59`. Pre-merge `git worktree list` predicts; manual `git push origin --delete <branch>` is mandatory; verify via `gh pr view NNN --json state,mergedAt,mergeCommit`. 19 confirmations in this codebase to date.
- **Worker worktree**: `C:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-gov-r0-d7-recon` currently at `9b3d886f` (= main HEAD); ready to branch off for next PR.
- **CLAUDE.md §8** explicit-path `git add` + column-1 `M ` / `A ` verification is non-negotiable. No `git add -A` / `git add .`.
- **Vitest + pytest** never run concurrent (worker-pool socket contention). Always queue vitest after pytest finishes.
- **`run_in_terminal` cd-stripping**: use `&{ Set-Location <abs>; <cmd> }` block-scoping for any cd-then-command sequence.

## Pre-flight checklist for the next session

1. `cd C:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-gov-r0-d7-recon` (worker).
2. `git fetch origin main; git reset --hard origin/main` (sync to latest).
3. `git log -1 --oneline` (expect `9b3d886f docs(boundaries): C.1 LGD Blocks upstream recon verdict (#439)` OR later).
4. `git worktree list` (verify master still holds `[main]` -> expect cosmetic merge error pattern).
5. Read [TODO/20260529-boundary-rip-and-replace-plan.md](../TODO/20260529-boundary-rip-and-replace-plan.md) (especially rows C.1-C.6 + D.1.A).
6. Read [notes/2026-05-29-c1-blocks-source-hunt-verdict.md](2026-05-29-c1-blocks-source-hunt-verdict.md) (6-step C.1 implementation plan + RECOMMENDED-PATH pipeline.json snippet).
7. Pick up at C.1 implementation OR C.2 recon depending on session budget.

## Session metrics (this session)

- 7 PRs shipped: #434 / #435 / #436 / #437 / #438 / #439 (1 of these — #439 — was this session; the others were carried in from prior compaction summary).
- Phase A: 5 PRs (#434-#438) completed across multiple sessions; Phase A 100% DONE as of #438.
- Phase C: 1 recon PR (#439) shipped this session; verdict file + 6-step plan ready for C.1 implementation.
- 1 lessons.md entry added (C.1 recon + Phase A close-out summary).
- 0 rollbacks; 0 post-hoc fixes; 0 dropped gates.

Phase A is done. Phase C is opened. The plan has clean forward momentum.
