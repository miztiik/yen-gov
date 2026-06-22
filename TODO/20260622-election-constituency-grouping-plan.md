# Election Constituency Grouping + List Redesign Plan

**Last Updated**: 2026-06-22
**Level**: 4 (multi-file, structural-additive across the elections frontend + one data backfill). No Level-5 core-data-model change. ONE Level-5-style STOP trigger lives in Row 1 (Delhi source substitution).

## Section 0 - Operating contract

### Why this plan exists

The state assembly election page (e.g. `/andhra-pradesh/elections/assembly-2024`) renders an ungrouped flat list of 175-294 constituencies. Some state LANDING pages (e.g. `/tamil-nadu`) group constituencies by district while others (e.g. `/andhra-pradesh`) show a flat list. The national/parliament pages have no constituency list at all. The user wants:

- **State assembly pages**: assembly constituencies (ACs) grouped by **District**.
- **Parliament / general pages**: full **PC -> AC -> District** hierarchy (each PC expands to its child ACs, each AC tagged with its district).
- **Both**: search by constituency name + a **Reserved filter** (All / GEN / SC / ST).
- The list UI itself rebuilt to be glanceable (proportional party strip, reservation badges, margin colour-band) instead of the current "ugly" flat table.

### Verified findings (established by diagnosis 2026-06-22 - trust these; re-verify only the one you touch)

1. The constituency-list component [frontend/src/lib/elections/StateEventConstituencyList.svelte](../frontend/src/lib/elections/StateEventConstituencyList.svelte) is ALREADY built for district grouping (collapsed-by-default folds, sticky search, party strip). Its own header comment says it shipped ready-but-dormant awaiting district data. `SeatRow.district` is an optional field that nothing populates yet.
2. The parent [frontend/src/routes/StateElection.svelte](../frontend/src/routes/StateElection.svelte) builds `seat_rows` (around L994-L1011) WITHOUT a `district` field, so every seat collapses into one "All constituencies" group. This is a WIRING gap, not a data gap.
3. The universal AC->district source is [datasets/data/entities/electoral_district_membership.csv](../datasets/data/entities/electoral_district_membership.csv) (AC `electoral_id` -> `lgd_district_id` slug, `is_primary` flag). It covers **30 of 31** applicable jurisdictions. ONLY Delhi (U05) is missing.
4. The landing page [frontend/src/routes/StateOverview.svelte](../frontend/src/routes/StateOverview.svelte) (around L643-L680) groups by an INLINE `district_id` read from `boundaries_sot/<S>/constituencies.json`, which is present in only **5 of 31** states (Assam S03, Kerala S11, Tamil Nadu S22, West Bengal S25, Puducherry U07). That is why TN groups but AP does not.
5. The AC->PC link is NATIVE in [datasets/data/entities/electoral.csv](../datasets/data/entities/electoral.csv): every `entity_kind=ac` row's `parent` is its PC `entity_id` (e.g. AC `IN-AC-2008-andhra-pradesh-3166` -> `parent IN-PC-2008-andhra-pradesh-411`). PC grouping needs ZERO new data.
6. District display NAMES come from the LGD district master under [datasets/data/entities/lgd/](../datasets/data/entities/lgd/) / [geo.csv](../datasets/data/entities/geo.csv) - resolve the slug, do NOT title-case it (it mangles "Dr B R Ambedkar Konaseema").
7. Delhi root cause: the membership builder [backend/yen_gov/canonical/seed/_run_electoral_from_snapshot.py](../backend/yen_gov/canonical/seed/_run_electoral_from_snapshot.py) is a pure LGD join (no geometry). The LGD PRI export for Delhi (state code 7) returned 0 rows in the 2026-06-05 snapshot ([datasets/_ops/lgd-parse-receipt.json](../datasets/_ops/lgd-parse-receipt.json)). Delhi's 11 districts ARE present in LGD; only the AC->district edge file is empty.

### Hard-coded scope

- IN scope: the 7 rows below, organised into 5 file-disjoint LANES that run in PARALLEL (Section 1b). Frontend grouping + list redesign + the single Delhi data backfill. Delhi backfill (Row 1) is CONFIRMED in scope.
- OUT of scope: re-delimitation refresh of the membership CSV (2008 delim is the live delim for current elections; re-delimited J&K-2022 / Assam-2023 ACs that do not join fall to the "Other constituencies" bucket - this is the user-accepted 7.2 "latest is good enough with caveats"). Do NOT re-key the membership CSV to a newer delimitation in this plan.
- OUT of scope: any new third-party library; any per-state bespoke component (schema-is-the-design-system - ONE generic list serves assembly + general + national).

### Decisions already locked by the user (do not re-litigate)

| Q | Ruling |
| --- | --- |
| 7.1 | Parliament/national = FULL PC -> AC -> District hierarchy. |
| 7.2 | Latest delimitation is good enough; unmapped ACs -> trailing "Other" bucket, never dropped. |
| 7.3 | Backfill Delhi from LGD (re-fetch); hand-authoring from ECI Delimitation Order 2008 is a STOP-AND-SURFACE fallback (Row 1). CONFIRMED in scope. |
| 7.4 | Landing-page migration to the universal membership source is in the SAME effort (Row 6). |
| Glyphs | Expand/collapse uses the icon-registry chevron GLYPH (chevron-right collapsed / chevron-down expanded), NOT a text caret; the sort control uses a sort GLYPH; search uses the magnifier GLYPH. Reuse existing icons; if a glyph is absent, add it per the icon-registry gates (Row 2). |
| Grouping dims | State assembly = AC -> District. Parliament = PC -> AC -> District. Both carry name-search + Reserved (GEN/SC/ST) filter. |

### Authority map (CLAUDE.md section 0a)

- Data shape / source (Row 1 backfill, Row 6 source-swap): **Hans + Max**.
- Read seams / SeatRow contract (Rows 4, 5): **Gregor**.
- Component craft / tests (all rows): **Fowler**.
- UX of the list, mocks, fold, filter, glyphs (Rows 2, 3, 5, 7): **Jony + Citizen**.

### ESCALATE / STOP triggers (stop ONLY here)

- **Row 1**: if the LGD re-fetch for Delhi (state code 7) STILL yields 0 AC->district rows, STOP-AND-SURFACE. Hand-authoring a lower-authority source (ECI Delimitation Order 2008) in place of the user-named LGD source is a contract change requiring user sign-off (CLAUDE.md section 10). Write the Scope-change ledger row (intent-only) and pause.
- Any row that would force a change to `datasets/data/_schema/columns.json` or the canonical CSV column contract -> Level-5, PAUSE for user sign-off (not expected; all rows consume existing columns).

## Section 1 - Status Reckoner

| Row | Lane | Wave | Title | Status | PR | Effort |
| :-: | :-: | :-: | --- | --- | :-: | :-: |
| 1 | DATA | 1 | Backfill Delhi AC->district membership (70 rows, LGD re-fetch) | [ ] PENDING | - | S |
| 2 | LIST | 1 | Component rebuild: proportional strip + leading label + SC/ST badge + margin band + chevron/sort/search glyphs + Reserved filter + count; declares full SeatRow contract | [ ] PENDING | - | M |
| 3 | LIST | 2 | Add `header_result` PC-mode rendering to the component | [ ] PENDING | - | S |
| 4 | STATE | 2 | Assembly wiring: district + reservation on seat_rows, sort by eci_no (grouping lights up) | [ ] PENDING | - | M |
| 5 | STATE | 3 | Parliament/general wiring: PC-grouped rows feeding header_result + child ACs | [ ] PENDING | - | M |
| 6 | LANDING | 3 | Landing page migrate to universal membership CSV (5 -> 31 states) | [ ] PENDING | - | M |
| 7 | NATIONAL | 4 | National page: mount grouped list State -> PC -> AC -> District | [ ] PENDING | - | M |

## Section 1b - Parallel execution topology (LANES x WAVES)

FIVE file-disjoint LANES. Rows in the SAME lane touch the SAME file and run SEQUENTIALLY; rows in DIFFERENT lanes touch DIFFERENT files and run in PARALLEL (no merge conflict by construction). The orchestrator dispatches one stateless `runSubagent` per row, runs all rows of a WAVE concurrently, waits for the wave to merge to `main`, then dispatches the next wave.

| Lane | Owns (only these files) | Rows (in order) |
| --- | --- | --- |
| DATA | `datasets/**` (membership CSV, lgd snapshot CSV, parse receipt) | 1 |
| LIST | `frontend/src/lib/elections/StateEventConstituencyList.svelte` + new shared token module (+ any new icon SVGs) | 2 -> 3 |
| STATE | `frontend/src/routes/StateElection.svelte` + new loader module | 4 -> 5 |
| LANDING | `frontend/src/routes/StateOverview.svelte` | 6 |
| NATIONAL | `frontend/src/routes/NationalElection.svelte` | 7 |

| Wave | Dispatch in parallel | Cross-lane gate (why it waits) |
| :-: | --- | --- |
| 1 | Row 1 (DATA) + Row 2 (LIST) | none - both start immediately |
| 2 | Row 3 (LIST) + Row 4 (STATE) | both consume Row 2's SeatRow contract / component shape (merged in Wave 1). Row 1 may still be finishing in parallel. |
| 3 | Row 5 (STATE) + Row 6 (LANDING) | Row 5 needs Row 3 (`header_result` prop) + Row 4 (same lane); Row 6 needs Row 2 (token) + Row 4 (loader) |
| 4 | Row 7 (NATIONAL) | needs Row 3 (`header_result`) + Row 5 (parliament rows) |

Conflict guarantee: within any wave the dispatched rows own DISJOINT files (DATA vs LIST; LIST vs STATE; STATE vs LANDING), so two subagents never edit the same file concurrently. Each subagent runs in its OWN worktree off `origin/main` (per the worktree-isolation lesson - never share a worktree). Row 1 (DATA) is independent of every frontend lane and may land in any wave; it sits in Wave 1 so Delhi coverage is complete before Rows 5/6/7 render parliament + landing, but it NEVER blocks them (Delhi degrades to the searchable flat list until Row 1 merges).

## Section 2 - Per-row specs

### Row 1 - Backfill Delhi AC->district membership

- **Scope**: add the 70 Delhi AC->district edges so Delhi groups like every other jurisdiction. NO new builder code, NO geometry, NO spatial overlay.
- **Approach**: re-fetch the LGD Constituency Coverage / PRI export for state code 7 via the existing parser at [tools/lgd/parse_lgd_export.py](../tools/lgd/parse_lgd_export.py); regenerate [datasets/data/entities/lgd/constituency_district_membership.csv](../datasets/data/entities/lgd/constituency_district_membership.csv) with the Delhi rows; re-run `python -m yen_gov.canonical.seed._run_electoral_from_snapshot` to emit the 70 rows into [datasets/data/entities/electoral_district_membership.csv](../datasets/data/entities/electoral_district_membership.csv). Update [datasets/_ops/lgd-parse-receipt.json](../datasets/_ops/lgd-parse-receipt.json).
- **Files**: the two CSVs above + the parse receipt.
- **Authority**: Hans + Max.
- **STOP trigger**: if Delhi still returns 0 rows from LGD, STOP-AND-SURFACE per Section 0 (do not hand-author silently).
- **Gates**: Tier-B `python -m yen_gov validate --root .` on the membership CSV; `pytest -q backend/tests/test_seed_electoral_district_membership_csv.py`.
- **ORACLE**: `IN-AC-2008-delhi-*` row count == 70; every Delhi `electoral_id` FK-resolves in `electoral.csv`; every `lgd_district_id` FK-resolves in `geo.csv`; exactly one `is_primary=true` district per Delhi AC.

### Row 2 - Component rebuild (LIST lane, Wave 1) - the user's quoted change + glyphs

- **Scope**: rebuild [StateEventConstituencyList.svelte](../frontend/src/lib/elections/StateEventConstituencyList.svelte): (a) replace the colour-deduped `dot_strip` with a PROPORTIONAL segmented strip - count seats per winning party, widths proportional, top-4 parties + an "other" segment - plus a leading-party label `"<SHORT> n/N"` (never colour-only); (b) `[SC]`/`[ST]` rose badge per leaf (GEN blank); (c) RdYlBu margin colour-band per leaf (reuse StateOverview bands: <5 nail-biter, <10 contestable, >=10 comfortable); (d) the expand/collapse TWISTY renders the icon-registry chevron GLYPH (chevron-right collapsed / chevron-down expanded), NOT a text caret; the search uses the magnifier glyph; (e) add a SORT control (sort glyph) toggling leaf order ballot-order (`eci_no`) <-> by-margin; (f) Reserved filter `(All) GEN SC ST` beside search + a "N constituencies in M districts" count, AND-composed with the name search; (g) drop the Share column on mobile (<640px). DECLARE the full exported `SeatRow` contract: add `reservation?: string | null` (`district?` already exists). Extract a shared `ReservationBadge` + margin-band helper (token module) for Row 6 reuse.
- **Glyph gate**: if the chevron / sort / magnifier glyphs are not already in `frontend/public/icons/`, add them per the icon-registry gates - pass the SVG allowlist (convert any `<rect>` to a rounded-rect `<path>`; ALLOWED_ATTRS excludes width/height/rx), update the EXACT sorted list in [frontend/src/lib/TopicIcon.test.ts](../frontend/src/lib/TopicIcon.test.ts), add a LICENCES.md row, bump the glyph count. `bun run build` validates the SVG bytes.
- **Files**: `StateEventConstituencyList.svelte` + shared token module (+ any new icon SVGs + `TopicIcon.test.ts` + `LICENCES.md`).
- **Authority**: Jony + Citizen.
- **Visual target**: appendix mock Mode 1 + Mode 2.
- **Gates**: vitest (strip math + filter + sort); browser-verify + screenshot; preserve all `state-event-constituency-*` testids; do NOT add a per-row corpus-scaling test (no-frontend-corpus-explosion).
- **ORACLE**: unit test - strip `{TDP:9, YSRCP:6, JSP:2}` -> 3 proportional segments summing 100%, ordered desc, label `"TDP 9/17"`; sweep `{TDP:16}` -> 1 full segment, label `"TDP 16/16"`; the Reserved=SC filter yields only SC leaves and the count text matches; the sort toggle reorders leaves by margin.

### Row 3 - Add `header_result` PC-mode to the component (LIST lane, Wave 2)

- **Scope**: add an optional `header_result?: { chip; share; margin; child_count }` prop to [StateEventConstituencyList.svelte](../frontend/src/lib/elections/StateEventConstituencyList.svelte). When PRESENT (parliament/PC mode): the GROUP HEADER renders the result (party chip + share + margin band) and the leaves render as navigation + a district label (no per-AC result chip). When ABSENT (assembly mode): existing behaviour. ONE component, behaviour switched by DATA presence (schema-is-the-design-system).
- **Files**: `StateEventConstituencyList.svelte`.
- **Authority**: Jony + Citizen (UX) + Gregor (prop contract).
- **Gates**: vitest; preserve testids; browser-verify deferred to Row 5 (needs the data feed).
- **ORACLE**: unit test - with `header_result` present, the group header shows the result and leaves show district labels (no result chip); with it absent, leaves show result chips (assembly mode unchanged).

### Row 4 - Assembly wiring: district + reservation onto seat_rows (STATE lane, Wave 2)

- **Scope**: [StateElection.svelte](../frontend/src/routes/StateElection.svelte) builds each `seat_row` with `district` (from membership `is_primary` -> LGD display name) and `reservation` (from `electoral.csv`); sort leaves by `eci_no` ascending (ballot order). Assembly grouping lights up for all states. Unmapped ACs -> `district = null` -> the component's single/"Other" path.
- **Join path**: winner `entity_id` (or `state + eci_no` via `electoral.csv`) -> `electoral_district_membership.electoral_id` (filter `is_primary=true`) -> `lgd_district_id` slug -> LGD district display name. Add a small loader under `frontend/src/lib/elections/`; reuse the existing DuckDB-WASM read seam (no JSON projection).
- **Depends on**: Row 2 (the `reservation` field on the exported `SeatRow`).
- **Files**: `StateElection.svelte` (+ one loader module).
- **Authority**: Gregor (read seam) + Fowler (craft).
- **Gates**: vitest; browser-verify `/andhra-pradesh/elections/assembly-2024` now shows district groups; preserve testids.
- **ORACLE**: contract test - for an AP fixture, every `seat_row.district` is either a real LGD district name or null; the set of distinct non-null districts equals the set of distinct `is_primary` districts for AP in the membership CSV; no AC appears in two groups.

### Row 5 - Parliament / general wiring: PC -> AC -> District (STATE lane, Wave 3)

- **Scope**: the state-scoped general page (`/<state>/elections/general-*`, handled by `StateElection.svelte`) builds PC-grouped rows: group = PC (feed Row 3's `header_result` from the PC MP result), leaves = the PC's child ACs (via `electoral.csv` `parent`) each tagged with its `is_primary` district. Assembly mode (Row 4) stays unchanged.
- **Depends on**: Row 3 (`header_result` prop) + Row 4 (same lane, the seat_rows + loader base).
- **Files**: `StateElection.svelte` (general branch) + the Row 4 loader.
- **Authority**: Jony + Citizen (UX) + Gregor (component contract).
- **Gates**: vitest; browser-verify `/andhra-pradesh/elections/general-2024`.
- **ORACLE**: contract test - for a fixture PC, the group header carries the MP winner; the leaves equal exactly the ACs whose `parent == that PC` in `electoral.csv`; each leaf shows its `is_primary` district.

### Row 6 - Landing-page migration to the universal membership source (LANDING lane, Wave 3)

- **Scope**: [StateOverview.svelte](../frontend/src/routes/StateOverview.svelte) district grouping switches from the inline `boundaries_sot` `district_id` (5 states) to the membership CSV (31 states) so AP + 25 others group on the landing page. Reuse Row 4's loader + Row 2's shared `ReservationBadge` + margin band. Keep unmapped -> trailing "Other" bucket.
- **Depends on**: Row 2 (token) + Row 4 (loader). Disjoint file from Row 5 -> runs in parallel with it.
- **Files**: `StateOverview.svelte` (+ reuse Row 4 loader, Row 2 token).
- **Authority**: Hans + Max (source swap) + Jony (UX parity).
- **Gates**: vitest ([StateOverview.test.ts](../frontend/src/routes/StateOverview.test.ts)); browser-verify `/andhra-pradesh` now grouped.
- **ORACLE**: contract test - for an AP fixture, `by_district` resolves from the membership CSV, covers all 175 ACs (mapped + Other), and yields more than one distinct district (proving AP now groups instead of one flat list).

### Row 7 - National page constituency list (NATIONAL lane, Wave 4)

- **Scope**: [NationalElection.svelte](../frontend/src/routes/NationalElection.svelte) (maps-only today) mounts the same list: outer group = state, leaf = PC, with PC expand -> AC -> district (reuse Row 3 + Row 5's PC mode). Search across state / PC / AC; Reserved filter from Row 2.
- **Depends on**: Row 3 (`header_result`) + Row 5 (parliament rows).
- **Files**: `NationalElection.svelte`.
- **Authority**: Jony + Citizen.
- **Gates**: vitest with BOUNDED fixtures (do NOT render-test all 543 PCs - no-frontend-corpus-explosion); browser-verify the national general route.
- **ORACLE**: e2e/contract - the national list renders the states as top groups; expanding one state shows its PCs; expanding one PC shows its child ACs with districts; the sampled state's PC/AC counts match `electoral.csv`.

## Parallel dispatch directive (read with Section 1b, governs the EXECUTION BLOCK below)

This plan is built to run IN PARALLEL. The orchestrator does NOT run rows one-at-a-time: it dispatches every row in the current WAVE (Section 1b) CONCURRENTLY as separate `runSubagent` briefs, each in its OWN worktree off `origin/main`, because same-wave rows own disjoint files. It waits for the whole wave's PRs to merge, advances `main`, then dispatches the next wave. The main thread holds ONLY the Status Reckoner + wave/merge state; ALL row implementation happens in subagents. Peak concurrency is Wave 2 (Row 1 finishing + Row 3 + Row 4 = up to 3 subagents). The verbatim execution contract below governs each individual row's PR lifecycle.

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

## Appendix - Visual target (ASCII mock, pure-ASCII)

```text
MODE 1  State Assembly  (AC -> District)
ANDHRA PRADESH  -  Assembly 2024                                          175 seats
+------------------------------------------------------------------------------------+
| [search] Search constituency...   Reserved: (All) GEN SC ST   Sort [updown] ballot  |
+------------------------------------------------------------------------------------+
| [+] Anantapur            14   [##############::::::]   TDP 10/14                    |
| [-] Guntur               17   [#########::::::::....]  TDP 9/17                     |
|        eci  name             resv   winner    share    margin                       |
|        163  Tadikonda        [SC]   [YSRCP]   47.2%    |R| 2.1                      |
|        164  Mangalagiri      [  ]   [TDP]     51.8%    |O| 7.4                       |
|        165  Ponnur           [  ]   [TDP]     55.0%    |B| 12.6                      |
| [+] Krishna              16   [################::::]   TDP 13/16                    |
+------------------------------------------------------------------------------------+
  [+]/[-]  = expand/collapse TWISTY. Real UI renders the icon-registry chevron GLYPH
             (chevron-right collapsed / chevron-down expanded), NOT a text caret.
  [search] = magnifier glyph.  [updown] = sort glyph -> toggles leaf order:
             ballot-order (eci_no)  <->  by-margin (nail-biters first).
  Strip    = one segment per winning party, width proportional ( # : . );
             label spells the leader "TDP 9/17".
  Resv     = [SC]/[ST] rose badge; GEN blank.  Margin band |R| <5% |O| <10% |B| >=10%

MODE 2  Parliament / General  (PC -> AC -> District, full hierarchy)
ANDHRA PRADESH  -  Lok Sabha (General) 2024                              25 PCs
+------------------------------------------------------------------------------------+
| [search] Search PC or AC...       Reserved: (All) GEN SC ST   Sort [updown] ballot  |
+------------------------------------------------------------------------------------+
| [+] Amalapuram    [SC]   [YSRCP]  51.0%  |B| 10.2          7 segments               |
| [-] Vijayawada           [TDP]    54.2%  |B| 11.0          7 segments               |
|        Vijayawada West              ->  Krishna                                     |
|        Mylavaram                    ->  NTR                                         |
|        Nandigama        [SC]        ->  NTR                                         |
+------------------------------------------------------------------------------------+
  [+]/[-] twisty = chevron glyph (as Mode 1).  PC row = the Lok Sabha (MP) result
  (chip + share + margin band).  Expand = child ACs, each tagged with its DISTRICT.
  National page wraps this with an outer State level: State -> PC -> AC -> District.
```

## See also

- [CLAUDE.md](../CLAUDE.md) - authority table (0a), correction levels (6), anti-patterns (10).
- [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) - one generic list, no per-state bespoke UI.
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - the list answers "who won where I live".
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - the PR lifecycle the EXECUTION BLOCK references.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - closure + archive ritual.
