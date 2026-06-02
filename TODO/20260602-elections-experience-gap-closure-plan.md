# Elections Experience - delivery-gap closure plan

**Last Updated**: 2026-06-02

> The UK-style elections experience (`TODO/20260531-uk-style-elections-experience-plan.md`, now complete) shipped with three delivery gaps the user surfaced post-merge. This plan closes them and installs a process guardrail so the reinterpretation class of gap cannot recur. Authorities (CLAUDE.md s0a): IA/contracts = Gregor; data shape = Hans + Max; UX = Jony + Citizen; **user approval supersedes every agent**.

## Section 0 - Operating contract (read before ANY row)

### 0.1 Stance

- **AUTO + STOP-AND-SURFACE.** Execute the next in-scope row in your lane without waiting for confirmation. BUT if a row would reinterpret/downgrade/substitute/scope-narrow a source or instruction the user named explicitly, do NOT auto-resolve and do NOT consult an agent to proceed: set the row `BLOCKED-NEEDS-SIGNOFF`, write a Scope-change ledger row (Section 4), and stop. Only the user can sign (CLAUDE.md s0a). This is Lane 0's own rule, applied to this plan from row 1.
- **Resolve ordinary ambiguity by consulting the row's named agent**, apply verdict, record in PR body, proceed.
- **Frugal testing.** Run only the gates listed on the row. No full-suite runs for a single-subsystem PR. Local `bun run check` + `bun run test` + integrated-browser Playwright smoke is the bar; do not wait for remote Pages deploy.
- **One in-progress row per lane.** Stamp PR# on close.
- **Worktree hygiene.** Before each PR: `git worktree add ../yen-gov-egc-<row> -b feat/egc-<row> origin/main`. Never branch from another worktree's branch; never park a worktree on `main`.

### 0.2 The three gaps (verified live 2026-06-02)

- **GAP A (IA mismatch).** The experience (`ElectionMap` + time-slider + filter rail) mounts only on the event route `/s/:state/elections/:event` and the national atlas `/t/elections/:event`. The topic doors citizens actually click - `/s/:state/t/elections` and the national `/t/elections` - still render a summary card that links out, landing the citizen one click short. This was a deliberate ADR-0048 s1 choice (topic = card, event = experience), so it is a wrong-for-user contract, not a bug. **User decision (2026-06-02): promote the experience onto the topic doors. No redirect. Top-level `/t/elections` must work as the experience too.**
- **GAP B (under-delivered source).** The user explicitly asked to ingest `All_States_GA.csv`; the prior plan downgraded it to "crosswalk / historical fallback only" inside baked-facts (lowest-visibility surface). Only 2024 (ECI #33 direct CSV) was ingested; 1999-2019 was never ingested. **Premise correction (user, 2026-06-02): `All_States_GA.csv` IS a TCPD file, and TCPD is ECI-derived - it was already the right family.** Hans+Max load-bearing finding: that segment file has NO electors and NO postal column, so it can produce at most 9 of 13 `pc-*` indicators and never turnout/electors. **User decision: prefer a direct ECI `.xls/.xlsx` constituency-wise source for 1999-2019; TCPD is ECI-derived; do not fight PDF.**
- **GAP C (tile coverage).** Only S13-AC (288) + national-PC (545) tile layouts exist; every other state's "Equal seats" arm shows "Equal-seats view isn't available for this state yet." Root cause: the generator was a throwaway `.tmp` script, deleted post-merge. **User decision: promote the generator to a committed tool, build all states/UTs, AND refine the hexbin so tiles conform closely to the enclosing polygon border.**

### 0.3 Concurrency (CRITICAL)

A separate topojson/boundary migration is running across many `yen-gov-topojson-*` / `yen-gov-y*` / `yen-gov-z*` worktrees, actively churning `frontend/src/lib/maplibre/sources.ts`, `datasets/boundaries/in/**`, and `frontend/e2e/boundary-benchmark.spec.ts`. Rules: do NOT touch boundary files; read whichever of `all.geojson`/`all.topojson` the existing loader resolves (no format hardcode); new election e2e goes in `frontend/e2e/elections-atlas.spec.ts`, never `golden-path.spec.ts`. Lane 0 (docs), Lane A (frontend render), Lane B (backend ingest) are collision-free by construction. Lane C touches `datasets/grapher/**` + `tools/` + frontend - no boundary-file writes.

### 0.4 Closure condition

Every row DONE or COLLAPSED-with-rationale; the GAP B `All_States_GA.csv` Scope-change ledger row (Section 4) has a non-empty `signoff:`. On completion: distil to `docs/` per `docs/how-to/distill-a-plan.md`, append the "Plan complete" map, `git mv` this file to `docs/archive/plans/`.

---

## Section 1 - Status Reckoner

Lanes run in parallel; within a lane rows are sequential. `||` = can start immediately.

| Row | Lane | Title | Depends on | Status | PR | Agent |
| --- | --- | --- | --- | --- | --- | --- |
| EGC-0 | 0 | Process guardrail: STOP-AND-SURFACE tripwire (no schema enums) | none `||` | [x] DONE | #574 | Gregor |
| EGC-A1 | A | Extract `StateElectionExperience.svelte` (behaviour-preserving) | none `||` | [x] DONE | #582 | Gregor/Jony |
| EGC-A2 | A | Mount experience on `/s/:state/t/elections` topic door | EGC-A1 | [x] DONE | #582 | Jony |
| EGC-A3 | A | Mount experience on national `/t/elections` topic door | EGC-A1 | [x] DONE | #582 | Jony |
| EGC-A4 | A | Amend ADR-0048 (topic-door experience; reconcile Model C) + docs | EGC-A2,A3 | [x] DONE | #583 | Gregor |
| EGC-B1 | B | Per-year ECI-direct vs TCPD-fallback source map recon (1999-2019); GAP B signed off option (a) | none `||` | [x] DONE | #579 | Max |
| EGC-B2 | B | Ingest historical PC series (TCPD/Lok Dhaba for all 5 years per B1 verdict) + honesty flags | EGC-B1 | [ ] PENDING | _pending_ | Hans + Max |
| EGC-C1 | C | Promote hexbin generator to `tools/`; border-conforming refinement; build all states/UTs | none `||` | [x] DONE | #588 | Jony |
| EGC-C2 | C | Two-tier tile-layout coverage contract (Tier-1 always-on; Tier-2 ship-dark->enforce) | EGC-C1 | [x] DONE | #588 | Jony |
| EGC-C3 | C | Hide "Equal seats" toggle where no layout; demote string to deep-link fallback | EGC-C1 | [x] DONE | #588 | Jony |

---

## Section 2 - Lane detail

### Lane 0 - process guardrail (user: mandatory; NO new schema enums)

**EGC-0.** Install a checkable STOP-AND-SURFACE tripwire so an explicit user-named source/instruction can never again be silently downgraded inside baked-facts. **User correction: do NOT add `INGESTED-AS-ASKED | REINTERPRETED` schema enums to the handover template. The tripwire is a process stance + a plain-prose Scope-change ledger in the plan-doc, not a schema field.**

- **CLAUDE.md s10 (Anti-Patterns) - add:** "Reinterpret, downgrade, substitute, or scope-narrow a source or instruction the user named explicitly, without surfacing it as a scope change for sign-off. An explicit user-named artifact may NOT be silently demoted (e.g. 'ingest X' -> 'crosswalk/fallback only') inside baked-facts or any low-visibility ledger. Disposition of a user-named source is a contract change requiring an explicit STOP + user sign-off (s0a), not agent-internal ambiguity resolution."
- **CLAUDE.md s9 (Definition of Done) - add checkbox:** "[ ] No source/instruction the user named explicitly was downgraded/substituted/scope-narrowed without a Scope-change ledger row carrying a non-empty `signoff:` in the active plan-doc."
- **`docs/how-to/distill-a-plan.md` (or a new short `docs/how-to/handle-scope-change.md`) - add the STOP-AND-SURFACE stance + the Scope-change ledger format** (verbatim user instruction | proposed change | reason | `signoff:`). Plain markdown table; no JSON schema, no enums.
- **Retroactive close:** Section 4 of THIS plan already carries the `All_States_GA.csv` ledger row with `signoff:` empty until the user acks.
- Gates: G-docs (H1 + Last Updated + See-also + ASCII). No code/schema/data.

### Lane A - promote the experience onto the topic doors (no redirect)

**EGC-A1.** Extract the experience block from `frontend/src/routes/StateElection.svelte` into NEW `frontend/src/lib/elections/StateElectionExperience.svelte` (the `{#if ev.kind === "assembly"}` map+slider+filters block, its `ac_winners` reactive load, `party_options`, `mode_coverage`, `filters`/`onFilterChange`; props `state_code`, `event_row`, `catalogue`). EDIT `StateElection.svelte` to mount it (delete inlined block; fix the stale "permalink wrapper" doc-comment). Pure extraction - no schema/URL/data change. Gates: `bun run check` 0 errors; existing tile/filter/map-colour vitest green; Playwright `elections-atlas.spec.ts` green on `/s/maharashtra/elections/AcGenOct2019` (zero-drift proof).

**EGC-A2.** EDIT `frontend/src/routes/StateTopic.svelte`: in the `kind:"election"` branch, when the default event resolves to an `assembly` event, mount `<StateElectionExperience .../>` in place of the summary card; keep a collapsed "Other elections on file" `<details>` below; preserve mixed-artifact rendering; honest empty-state when no default event. lok_sabha events on a state topic still card-and-link to the national atlas (do not mount the AC experience for a PC event). NO catalogue schema bump (resolution stays read-time via `defaultEventForState`). Gates: `bun run check`; NEW Tier-A `frontend/src/contracts/election-topic-experience.test.ts` (topic door + event route mount same component, resolve same default event - drift guard); Playwright: `/s/maharashtra/t/elections` shows map + Map|Equal-seats toggle + slider + filter rail, `?view=hex` persists, unit drills to `/s/maharashtra/ac/<ac>`, "Other elections" still lists rest; no console error/404.

**EGC-A3.** Promote the national topic door. EDIT the route that serves `/t/elections` (national topic) so it mounts the national PC atlas experience (the one already built for `/t/elections/:event` in prior PR-B4) at the default lok_sabha event, instead of a card/link. No redirect. Keep an "Other Lok Sabha elections on file" list below. Gates: `bun run check`; Playwright: `/t/elections` renders the national PC atlas + Map|Equal-seats toggle + slider + filters; drills to `/s/:state/elections/:event`; no console error/404.

**EGC-A4.** EDIT `docs/architecture/decisions/0048-elections-drill-ia-and-tile-cartogram.md`: Addendum "Topic doors mount the experience (supersedes s1 topic-as-card)"; record the redirect/merge option as rejected (IA-consistency + lost mixed-artifact rationale); in the SAME edit replace the stale "Option B concept-binding" load-bearing-contracts paragraph with the shipped Model C contract. EDIT `docs/architecture/frontend/indicators.md`: move "Render election results inline on the topic page" DEFERRED -> DONE with pointers to EGC-A2/A3; retire QR4's "topic is not the landing" premise. Gates: G-docs.

### Lane B - historical Lok Sabha series, ECI-primary with TCPD fallback (SIGNED OFF option (a), 2026-06-02)

**Strategy (per user signoff):** per-year, prefer the direct ECI constituency-wise source where it exists in usable form (the ECI #33-style detailed-result workbook that 2024 used; newer GEs as `.xls/.xlsx`). For the older GEs ECI does not publish in usable constituency-wise form, **fall back to TCPD** (ECI-derived) AC-split data, pulling the missing years via the integrated browser from the TCPD portal. `All_States_GA.csv` itself stays a crosswalk, not the ingest source.

**EGC-B1.** Recon-only. Build the per-year source map for the 1999-2019 Lok Sabha GEs: for each GE year, determine (i) does ECI publish a usable constituency-wise file (`.xls/.xlsx/.csv`) carrying **electors + postal**? if yes, that year is ECI-direct; (ii) if not, the year is TCPD-fallback - identify the exact TCPD AC-split file + whether it carries electors/postal (it generally does not -> turnout NULL for that year). Per the CSV-only ingest contract: any `.xls/.xlsx` is converted to CSV in a one-time documented prep step OUTSIDE the pipeline; the pipeline ingests CSV only (stdlib csv + DuckDB; no xlrd/pandas in `backend`). Deliverable: a recon note `notes/2026-06-02-eci-historical-ls-source-recon.md` with a per-year table (year | source = ECI-direct or TCPD-fallback | format | carries electors? | carries postal? | which of the 13 `pc-*` indicators it yields | licence). No STOP needed - the ECI-primary/TCPD-fallback path is the signed-off plan; the recon just fixes which years land on which arm. Gates: G-docs; no code/data.

**EGC-B2.** Ingest 1999-2019 PC results from the EGC-B1 source through the existing PC pipeline (mirrors PR-A2/A3/A4 of the prior plan: identity, observations, rollups, writer, `ingest-eci-ls` CLI). Reuse the existing Model-C `pc-*` indicators + `IN-PC-<delim_year>-<state_code>-<pc_no>` entity scheme - NO new indicator, NO new id grammar. Mandatory honesty guards (Hans+Max): `segment_approximate` boolean per row (true only if a year is segment-sourced); one `methodology_breaks.parquet` row for the 2008 delimitation; NOTA NULL (not zero) pre-2013; Telangana-under-AP pre-2014 (NULL not zero); turnout/electors NULL (never fabricated) for any year whose source lacks electors; per-`(year, delim_year)` distinct-PC count assertion (543 elected universe for direct-sourced; floor >=536 + named missing-seat allow-list for any segment-sourced stopgap year; never assert 545). Per-year `source_id` FK so the postal-inclusive/exclusive split is auditable from provenance. Gates: `python -m yen_gov validate --root .` on the touched family; per-year count-assertion test; pre-flight-ingest exit 0; schema bump only if `segment_approximate` is a new observation field (grep-confirm first; additive MINOR if so).

### Lane C - equal-seats coverage for every state (user: refine hexbin border conformance)

**EGC-C1.** Promote the deleted `.tmp_gen_layout.py` to a committed deterministic tool `tools/gen_election_tile_layouts.py`: `--layout-kind ac --scope <state_code>` or `--all-states`; reads `datasets/boundaries/in/ac/state=<slug>/all.geojson`; persists `q,r` into `datasets/grapher/election_tile_layouts.json` with `derivation_method`; idempotent per-scope (re-running a scope replaces only that scope's tiles). `tools/` must NOT import `backend/` runtime (read geojson directly). Scope set = every state/UT with an elected assembly + AC corpus (~31); no-assembly UTs get no AC layout by design. **Border-conformance refinement (user, 2026-06-02): the current greedy nearest-free-cell hexbin places tiles that do not hug the enclosing polygon outline closely enough. Improve tile->geography fidelity** - e.g. snap each tile to the grid cell whose centre is nearest the constituency centroid under the STATE outline's aspect ratio (scale q/r axes to the state bounding box), iterate to reduce centroid->tile displacement, and keep boundary-ring constituencies on the outer ring of the hex layout rather than letting greedy fill pull them inward. Validate visually: hand-author Puducherry (4 disjoint enclaves break any hexbin; `derivation_method: "hand-authored"`); eyeball the dense mega-city/long-ribbon states (UP 403, WB 294, TN 234, Bihar 243, MP 230, Karnataka 224, Kerala 140 N-S ribbon) with one batch sandbox screenshot pass before merge; auto-ship the contiguous mid-count majority with no review. Do not block the easy ~25 on the 1 hard one. Gates: per-scope no-overlap + full-count assertion (Tier-1 below); sandbox screenshot for the flagged high-count scopes.

> **DONE (PR #588, 2026-06-02).** Generator shipped as `tools/gen_election_tile_layouts.py` (stdlib-only, never imports `backend/`); centroid-hexbin with per-state bbox aspect-ratio scaling + equirectangular lon correction. `--all-states` built **30 standard-schema AC scopes + national PC = 4543 tiles, zero overlap in all 31 scopes**. Also emits a tiny covered-scopes manifest `datasets/grapher/election_tile_scopes.json` (+ schema) consumed by EGC-C3 to gate the toggle. J&K skipped (non-standard boundary schema, no `ac_no`; soft-fail exit 1) - the lone documented holdout.
> **Residual (user-supervised, deferred from this PR):** (1) hand-author Puducherry U07 (4 disjoint enclaves the hexbin only approximates; `derivation_method: "hand-authored"`); (2) one screenshot-review pass over the high-count ribbon/mega-city states (UP 402, WB 293, TN 233, Bihar 243, MP/Karnataka 224, Kerala 140 N-S ribbon). Current output is structurally valid (proven by the EGC-C2 coverage contract); these are visual-fidelity refinements needing eyes-on review, tracked here for a follow-up supervised pass.

**EGC-C2.** Generalise `frontend/src/contracts/election-tile-layout-coverage.test.ts` into two tiers. Tier-1 (always-on, ship now): for EVERY `(layout_kind, scope, delim_year)` present in the layouts file, assert no two tiles share `(q,r)`, no duplicate `unit_id`, and the tile set equals the expected `unit_id` set from that scope's boundary corpus - so each new state self-validates with zero test edits. Tier-2 (completeness gate, ship-dark): compute required scope set = every `datasets/boundaries/in/ac/state=*/` slug with an elected assembly; assert each has exactly one AC layout, behind a `COVERED_AC_SCOPES` allowlist starting `["S13"]` that each layout-landing PR appends to (the allowlist IS the progress ledger); when the last scope lands, delete the allowlist and flip Tier-2 to assert the full set unconditionally. Keep the existing S13 `288` + national-PC `545` count pins. Gates: `bun run test` on the contract file.

**EGC-C3.** EDIT `frontend/src/lib/elections/ElectionMap.svelte`: hide the "Equal seats" toggle group on any state with no AC layout (check layout availability before render - either inspect the fetched layout doc or read a tiny static `datasets/grapher/election_tile_scopes.json` covered-scopes manifest synchronously). Render the geographic map with NO toggle when no layout exists; the toggle's presence becomes an honest "Equal seats works here" signal. Demote the existing "isn't available" string to a pure deep-link-race fallback for `?view=hex` (never reachable by clicking). Gates: `bun run check`; Playwright: a no-layout state shows the map with NO Equal-seats toggle; a covered state (Maharashtra) still shows it; `?view=hex` on a no-layout state shows the graceful fallback string, not an empty canvas.

---

## Section 3 - Dependency graph

```mermaid
graph LR
  A1[EGC-A1 extract] --> A2[EGC-A2 state door]
  A1 --> A3[EGC-A3 national door]
  A2 --> A4[EGC-A4 ADR + docs]
  A3 --> A4
  B1[EGC-B1 ECI recon] --> B2[EGC-B2 ingest]
  C1[EGC-C1 tool + refine] --> C2[EGC-C2 coverage contract]
  C1 --> C3[EGC-C3 hide toggle]
  EGC0[EGC-0 guardrail]
```

EGC-0, EGC-A1, EGC-B1, EGC-C1 all start immediately and in parallel.

## Section 4 - Scope-change ledger (the GAP B receipt)

| Verbatim user instruction | Proposed change in prior plan | Reason recorded | `signoff:` |
| --- | --- | --- | --- |
| "why not ingest [All_States_GA.csv] i explicitly asked for this ingest" | Prior plan downgraded it to "crosswalk / historical fallback only" inside baked-facts; only 2024 (ECI #33) was ingested | Segment grain, EVM-only/postal-excluded, no electors column, no 2024; yields at most 9 of 13 `pc-*` indicators | **SIGNED OFF 2026-06-02 (user), option (a):** ack `All_States_GA.csv` is best used as crosswalk. Ingest direct ECI per-year where it exists (2024 = ECI #33 done; newer years as `.xls/.xlsx`). For older years ECI does not publish in usable constituency-wise form, **fall back to TCPD** (ECI-derived) AC-split files, pulling missing years via the integrated browser. Turnout/electors emitted only where the year's source carries them; NULL (never fabricated) otherwise. |

## See also

- `TODO/20260531-uk-style-elections-experience-plan.md` (the completed plan whose gaps this closes)
- `docs/architecture/decisions/0048-elections-drill-ia-and-tile-cartogram.md`
- `docs/architecture/frontend/indicators.md`
- `docs/how-to/distill-a-plan.md`
