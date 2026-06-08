# E6 user-override + PL2/PL3 execution sub-plan

**Date**: 2026-06-08
**Status**: IN-FLIGHT (single branch `fix/pl2-pl3-dim-parties-schema-drift-plus-e6-e7`)
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) - ledger rows `PL2`, `PL3`, `E6 alternate counting methods (25.6b)`
**Supersedes**: [TODO/20260607-e6-alternate-counting-methods-subplan.md](20260607-e6-alternate-counting-methods-subplan.md) for the E6 row (the prior DEFERRED triple-verdict stands as documented Citizen+Hans+OWID concerns this sub-plan honours via the banner + sandbox-fenced execution)

## 0. User override (verbatim, per CLAUDE.md section 0a)

> "currently the semicircle is broken - use integrated browser and playwright to test you code.
> there were other system then FPTP planned in the plan /subplan/sub-sub plan - can you deliver that as well.
> 'runSubagent'
> can you fix the above
> do not wait for remote PR merge.
> do the work , test, commit, push your branch for merge dont wait for CI merge -in remote, localy testing success is good enough.
> most of this should be backend work,
> use subagents for main work - the main thread remains a orchestrator - no deferals unless explicity authorized by me.
> parellelize as much as possible. use as many subagents as possible. clean if all items are done."

Per CLAUDE.md section 0a: "User approval supersedes every agent and every rule in this file."

This authorisation explicitly OVERRIDES the prior E6 DEFER verdict (Citizen + Hans + OWID-no-precedent). The DEFERRED sub-plan's "Follow-up if user overrides" section names the path; this sub-plan executes it.

## 1. Scope (this branch carries all of it - bundle-related-work-in-same-PR)

PL2 + PL3 + E6 + E7 are shipped together because (a) they share the Psephlab surface, (b) the PL2 fix is a precondition for any meaningful E6/E7 §13 smoke, and (c) the user's "no deferrals" rule + "parallelize as much as possible" + "ship local, don't wait for CI" directives collapse the artificial PR-by-PR ceremony.

| Row | What | Status |
| --- | --- | --- |
| **PL2** | parties.csv 7->8 column drift (G1 added `aliases`) broke every `registerCsvAsTable("elections.dim_parties")` consumer (StateOverview, Psephlab, Compare, Constituency) with the DuckDB sniffer error "7 columns in dict but 8 in file". | **DONE** - `frontend/src/lib/duckdb.ts` reads the columns dict from `csvColumnsClause(...)` (schema-as-single-source-of-truth per CLAUDE.md Holy Law #6) instead of hand-typing it inline. §13 verified: `/lab/tamil-nadu/AcGenApr2021` renders 234 dots, party totals sum to 234 (E5 invariant green), zero console errors. |
| **PL3** | In-browser smoke for `/lab/:state/:event` per CLAUDE.md section 13 + Playwright spec. | **IN-FLIGHT** - smoke screenshot captured manually; Playwright spec dispatched to subagent D. |
| **E7 Gallagher** (the honest carve-out per parent plan section 25.6b "Hans's carve-out") | Gallagher disproportionality chart on Psephlab: two stacked bars (vote share vs seat share per party) with the index value labelled. Measurement of the existing FPTP system; no banner needed. | Dispatched to subagent B. |
| **E6** | Three alternate counting methods (proportional / ranked-choice / approval) behind the existing `countSeats()` seam at `frontend/src/lib/charts/count-seats.ts`. Each method MUST surface a loud "HYPOTHETICAL RECOUNT - NOT THE OFFICIAL RESULT" banner the citizen cannot scroll past. | Dispatched to subagents A (banner) + C (rules). |

## 2. Honest-design contract (binds every method)

Per the prior sub-plan's Hans/Citizen analysis, the architecture MUST honour:

1. **Banner is mandatory + structural, not decorative.** A new `HypotheticalRecountBanner.svelte` is the load-bearing safety component. Rule picker switches show the banner inside the result panel; rule = FPTP hides it. Banner copy is asked-for-explicitly verbatim per Hans's "fabricated-input" primitive (sub-plan §"Follow-up").
2. **Per-method `caveat: string` is required on every non-FPTP rule.** Surfaced beside the banner; tells the citizen exactly what the simulator ASSUMES (e.g. IRV: "Indian EVMs do not record ranked ballots. This simulator assumes voters' second preferences transfer proportionally across the surviving candidates' current shares. The recount is illustrative, not predictive.").
3. **Method names are descriptive, not euphemistic.** No "alternative voting" or "modern method" framing. Citizens see the algorithm: "Proportional (Sainte-Lague)", "Ranked-choice (IRV, uniform transfer)", "Approval (cast = approval)".
4. **Rosling Class D guard.** Non-FPTP outputs MUST NOT participate in any cross-state ranking or any "winner predicted" widget. The Psephlab path is the only host surface in this PR; nothing on `/s/<state>` or `/` reads alternate-method tallies.
5. **No bookmark of "BJP got 145 seats under PR" link to other pages.** Scenarios encode `{rule, mutations}` in the URL fragment (`?s=`) per existing convention; the URL never claims a non-FPTP tally as a citizen-share-friendly fact.
6. **Sandbox fence.** Psephlab is the ONLY route that mounts non-FPTP rules. The `countSeats()` seam still throws for non-FPTP from any other caller. (The `psephlab/rules/` registry is the local-only opt-in.)

## 3. Files in scope (subagent boundaries)

Designed so subagents work on non-overlapping files; orchestrator wires up Psephlab.svelte at the end.

**Subagent A - Banner primitive**
- NEW `frontend/src/lib/HypotheticalRecountBanner.svelte`
- NEW `frontend/src/lib/HypotheticalRecountBanner.test.ts`

**Subagent B - Gallagher chart (E7)**
- NEW `frontend/src/lib/charts/GallagherDisproportionality.svelte`
- NEW `frontend/src/lib/charts/GallagherDisproportionality.test.ts`
- (pure component; consumes `SeatAllocation` shape from `psephlab/types.ts`)

**Subagent C - Alternate counting rules + countSeats seam**
- NEW `frontend/src/lib/psephlab/rules/sainteLague.ts` (proportional, Sainte-Lague divisor; state-wide)
- NEW `frontend/src/lib/psephlab/rules/sainteLague.test.ts`
- NEW `frontend/src/lib/psephlab/rules/instantRunoff.ts` (ranked-choice IRV; per-AC; uniform-transfer assumption)
- NEW `frontend/src/lib/psephlab/rules/instantRunoff.test.ts`
- NEW `frontend/src/lib/psephlab/rules/approval.ts` (approval-as-cast; per-AC; FPTP-equivalent by construction, shipped as the citizen-honest "no separate approval data" baseline)
- NEW `frontend/src/lib/psephlab/rules/approval.test.ts`
- EDIT `frontend/src/lib/psephlab/rules/index.ts` (register the new rules)
- EDIT `frontend/src/lib/psephlab/types.ts` (add optional `caveat?: string` + `assumptions?: string[]` to `CountingRule` so the UI can surface them)
- EDIT `frontend/src/lib/charts/count-seats.ts` (broaden non-FPTP throw to accept method names registered in the psephlab rules registry; throw stays for *unknown* methods)
- EDIT `frontend/src/lib/charts/count-seats.test.ts` (update tests to reflect the broadened gate)

**Subagent D - PL3 Playwright smoke**
- NEW `frontend/e2e/psephlab-smoke.spec.ts` (loads `/lab/tamil-nadu/AcGenApr2021`, asserts 234 dots, asserts party-tally sum = total_seats invariant, asserts zero console errors)

**Orchestrator wiring (this thread, after subagents return)**
- EDIT `frontend/src/routes/Psephlab.svelte`:
  - Mount `HypotheticalRecountBanner` above the seat-tally panel when `scenario.rule !== "fptp"`.
  - Mount `GallagherDisproportionality` chart in a new section below the existing seat board.
  - Add a rule-picker `<select>` driven from the `RULES` registry. Already present via `scenario.rule` + `ruleById` - just surface a `<select>` next to the existing "Counting rule:" header line.

## 4. Gates (essential-tests-only per parent plan section 22.3)

| Gate | What it asserts | Owner |
| --- | --- | --- |
| `vitest run frontend/src/lib/psephlab/rules/` | New rule files + invariant assertions (seat-sum, no-negative-seats, allocation determinism). | Subagent C |
| `vitest run frontend/src/lib/HypotheticalRecountBanner.test.ts` | Banner component renders with role=alert + ASCII-only copy + the words "HYPOTHETICAL RECOUNT". | Subagent A |
| `vitest run frontend/src/lib/charts/GallagherDisproportionality.test.ts` | Index = sqrt((1/2) * SUM((vote% - seat%)^2)); 0 when perfectly proportional; ~equals known TN-2021 value within rounding. | Subagent B |
| `bunx svelte-check --threshold error` | Zero new svelte-check errors. | Orchestrator after wiring. |
| `bunx vite build` | Production build green. | Orchestrator after wiring. |
| `bunx playwright test frontend/e2e/psephlab-smoke.spec.ts` | Smoke + PL3 receipt; pins the E5 invariant (234 dots, 234 legend total) AND each non-FPTP rule renders the banner. | Subagent D + orchestrator. |
| `pytest backend/tests/` | Net-zero new failures vs origin/main baseline (PL2 + E6/E7 are frontend-only). | Orchestrator. |

## 5. Subagent return contract

Each subagent returns a single message with:
- List of files created/modified
- Summary of tests added (count, what they pin)
- Local gate result for its scope (e.g. `vitest run <file>` PASS)
- Any STOP-AND-SURFACE issue encountered

Orchestrator merges work into the single branch (no rebase needed since files are non-overlapping) and runs the remaining gates.

## 6. Out of scope for THIS PR

- Re-routing alternate-method tallies onto any other surface (`/s/<state>`, `/`, /compare).
- The "ship Hans's Option C carve-out (Gallagher) first as the precedent" sequencing - we ship both E7 and E6 together because the user directive collapses the gating ceremony.
- Yenask query support for alternate methods (would re-litigate Andre 20.10 grounding surface; preserve `concepts.ts` FPTP-only SQL).
- Cross-state Gallagher chart (state-wise comparison would invite Rosling Type 2 misreading; ship per-state only).

## 7. Plan-ledger update

After merge, the parent ledger row updates:

- `PL2 Pilot-state canonical shards + loader returns rows`: PARTIAL -> **MERGED** (PR for this sub-plan); root cause + structural fix narrated.
- `PL3 In-browser verify per CLAUDE.md section 13`: NOT STARTED -> **MERGED**; Playwright spec at `frontend/e2e/psephlab-smoke.spec.ts`.
- `E6 alternate counting methods (25.6b)`: DEFERRED -> **MERGED (user override 2026-06-08)** with link to this sub-plan; the prior DEFERRED sub-plan stays archived as the documented Citizen+Hans concern record that this design honours via the banner.
- NEW row `E7 Gallagher disproportionality chart`: **MERGED** with this sub-plan.
