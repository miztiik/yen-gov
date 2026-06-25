# Standard map hover card - one card across PC / AC / equal-seats hex (execution plan)

**Last Updated**: 2026-06-25
**Level**: 4 (4+ files, structural; frontend-only - no schema / data-model / canonical change)

> Authored via the `prepare-plan` skill. This doc AUTHORS the work; it is not yet executed. When it is in context and the instruction is "implement it", follow the EXECUTION BLOCK (section 4) blindly.

---

## Section 0 - Operating contract

**Why.** Four election-map surfaces draw a hover card from TWO divergent builders that have drifted:

- The 3 d3 maps - per-state PC ([frontend/src/lib/charts/StatePcMapD3.svelte](../frontend/src/lib/charts/StatePcMapD3.svelte)), per-state AC ([frontend/src/lib/charts/StateAcMapD3.svelte](../frontend/src/lib/charts/StateAcMapD3.svelte)), national PC ([frontend/src/lib/charts/IndiaPcMapD3.svelte](../frontend/src/lib/charts/IndiaPcMapD3.svelte)) - share the pure `renderTooltipCard` HTML-string in [frontend/src/lib/boundaries/tooltip-card.ts](../frontend/src/lib/boundaries/tooltip-card.ts).
- The equal-seats hex cartogram ([frontend/src/lib/charts/TileCartogram.svelte](../frontend/src/lib/charts/TileCartogram.svelte)) hand-rolls a DIFFERENT `tooltip_html` ("Winner:/Margin:", no party symbol) in [frontend/src/lib/view-models/election-tile-layout.ts](../frontend/src/lib/view-models/election-tile-layout.ts).

Observed defects (user, 2026-06-25): the card is visually crude; the symbol slot renders a broken BOX when a party has no asset; the box RESIZES as the cursor moves (jarring); the hex 2-letter labels carry a heavy double-stroke halo; the hex tooltip looks nothing like the constituency tooltip. This plan collapses all four onto ONE fixed-size card + ONE positioned shell, fixes the box bug, and cleans the hex font/size - fenced by a non-drift contract test so it cannot re-diverge. This is the "one card, not per-surface bespoke markup" rule (Holy Law #4 doc-as-memory; [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md)) applied to tooltips.

**In scope (frontend render only).**
- [frontend/src/lib/boundaries/tooltip-card.ts](../frontend/src/lib/boundaries/tooltip-card.ts) (+ its test)
- new `frontend/src/lib/charts/HoverCardShell.svelte` + `frontend/src/lib/charts/hover-card-position.ts` (+ test)
- the 3 d3 map components (adopt shell, drop number, pass grain + parent + accent)
- [frontend/src/lib/view-models/election-tile-layout.ts](../frontend/src/lib/view-models/election-tile-layout.ts) (+ tile-cartogram test) and [frontend/src/lib/charts/TileCartogram.svelte](../frontend/src/lib/charts/TileCartogram.svelte)
- new `frontend/src/contracts/tooltip-card-single-source.contract.test.ts`

**Out of scope (do NOT touch).**
- Map polygon FILL coloring - already `marginShade` (within-party saturation) in [frontend/src/lib/elections/election-map-coloring.ts](../frontend/src/lib/elections/election-map-coloring.ts). The tooltip text gets its own margin treatment (R-C); the fill encoding is untouched.
- The indicator / election data model, canonical CSV, or any `datasets/` schema. No data change.
- The mobile tap-vs-hover interaction model (Hans flagged that a mid-tier Android has no hover, so this is really a tap-readout). Tracked as a follow-up below; NOT this plan.
- a11y / ARIA (CLAUDE.md section 0 non-goal).

**ESCALATE triggers (STOP for user sign-off ONLY here; otherwise AUTO).**
- A row discovers it needs a canonical / election-results schema bump or a data-row change. None expected (frontend render only). -> STOP, Level-5.
- A NEW persona conflict the plan did not pre-resolve. All known conflicts are resolved in section 0.1.
- An explicit user-named source/instruction would be scope-narrowed (CLAUDE.md section 10 STOP-AND-SURFACE).

**Strategy + the convergence that set it.** EXTEND, do not fork (Fowler, craft authority). Keep the pure `renderTooltipCard(model) -> string` (string-level security suite intact) as the single content+visual authority emitting the WHOLE fixed-size card incl. the left bar; add ONE thin `<HoverCardShell>` Svelte wrapper + a pure node-testable `hover-card-position.ts` for placement + viewport edge-flip; migrate all 4 surfaces; retire the hex's bespoke builder LAST so the security tests AND the tile-cartogram "Winner: INC" assertions never break mid-stream (reader-before-writer). Jony owns card anatomy, Hans owns content meaning, Fowler owns the row split - all three converged in section 0.1.

---

## Section 0.1 - Design rulings (converged, baked - do NOT relitigate)

Persona debate (Jony UI/UX, Hans Governance, Fowler Engineering) per the CLAUDE.md section 0a authority table, 2026-06-25. Single verdicts:

### R-A. The ONE fixed card (Jony, UX deciding authority)

Same **256 x 140 px** box for PC, AC, and the hex cartogram. As the cursor moves only the text / bar-color / symbol / margin-color change; nothing resizes or moves (this is the user's primary constraint - "constant div size so the mind focuses only on changing elements"). radius 14px, `overflow:hidden`, white surface, 1px slate-200 border, shadow --e2, `pointer-events:none`, `box-sizing:border-box`. Internal layout is a CSS grid of FIXED px rows so positions never shift; every text cell is `white-space:nowrap; overflow:hidden; text-overflow:ellipsis`; the margin cell is `font-variant-numeric:tabular-nums` so digits never change width.

```
PC hover                                AC hover
+------------------------------+        +------------------------------+
|| Uttar Pradesh               |        || Tamil Nadu                  |
|| [PC] Bhiwani-Mahendragarh   |        || [AC] Tindivanam        [ST] |
|| --------------------------- |        || --------------------------- |
|| (o) BJP             +12.4%  |        || (o) DMK              +6.1%  |
||     Dharambir Singh         |        ||     M. Karunanidhi          |
|| Click to view               |        || Click to view               |
+------------------------------+        +------------------------------+
 ^ 4px party-color bar, full height, flush left, clipped by the 14px radius
   (o) = 18px party symbol glyph (or party-hued disc when no asset; never a broken <img>)
```

Rows (fixed px, content padding `14px 14px 14px 18px`; left 18 = 4px bar + 14; rows + padding + border sum to 140):

| # | Line | PC shows | AC shows | Font px / weight / color |
| - | - | - | - | - |
| 1 | Parent state | "Uttar Pradesh" | "Tamil Nadu" | 11 / 500 / slate-500 |
| 2 | grain chip + name + reservation | `[PC]` + name | `[AC]` + name + `[ST]` | name 14 / 600 / slate-900 |
| 3 | divider | 1px full-width slate-200 | same | - |
| 4 | symbol + party + margin | `(o)` + "BJP" + "+12.4%" | `(o)` + "DMK" + "+6.1%" | party 13 / 600 / slate-900; margin 13 / see R-C |
| 5 | candidate (the 1 extra, R-F) | "Dharambir Singh" | "M. Karunanidhi" | 12 / 400 / slate-500 |
| 6 | affordance | "Click to view" | "Click to view" | 11 / 500 / slate-400 |

Row 2 = 3-col flex: chip (fixed) - name (`flex:1`, ellipsis) - reservation (fixed, right). Row 4 = symbol 18x18 (fixed) - party (`flex:1`, ellipsis) - margin (fixed, right). The hex cartogram passes the IDENTICAL model into the IDENTICAL renderer - same box, no variant.

### R-B. Left party-color accent bar (Jony; precedent [frontend/src/lib/WinnerBadge.svelte](../frontend/src/lib/WinnerBadge.svelte))

YES. 4px wide, full height, flush left, fill = winner party hex (the same 3-tier resolved color that fills the seat, via `getPartyColor` / the `party_colors.get(...)` map each surface already holds). `position:absolute; left:0; top:0; bottom:0`; the card's `overflow:hidden` + 14px radius clip it so it follows the rounded corner (no square poke-out). Pending / no-winner -> --party-neutral #cbd5e1.

### R-C. Margin colored by split (Jony UX authority; Hans meaning-constraints baked)

YES - color the margin VALUE text on a **party-INDEPENDENT** 3-band scale (party color is already carried by the bar + symbol; coloring the margin by party duplicates that signal AND a pale "+2.1%" in a party hue is illegible at 13px). Bands by `abs(margin_pct)`, **COLOR ONLY - NO rendered "safe"/"marginal" word-label** (Hans over-claim guard), with a leading "+" SIGN (a sign, not an arrow):

| Internal band const | Threshold | Color | Weight |
| - | - | - | - |
| `MARGIN_CLOSE_PP = 5` | abs < 5pp | amber-700 #b45309 | 600 |
| (mid) | 5 to < 15pp | slate-500 #64748b | 600 |
| `MARGIN_DECISIVE_PP = 15` | abs >= 15pp | slate-900 #0f172a | 700 |

Thresholds are named consts in `tooltip-card.ts` (no magic numbers); names avoid prediction language. Framing is value-only + this-election: margin% is NOT cross-seat comparable in multi-corner Indian races (Hans), so the color flags "this result was close" for THIS seat - it implies NO ranking and NO future prediction. The within-party saturation encoding (`marginShade`) stays on the map polygon FILL, never duplicated in the tooltip text.

### R-D. Grain signifier (Jony) - this is how "PC and AC info" survives the number-drop

A leading chip `[PC]` or `[AC]` immediately left of the constituency name on row 2 (10px, weight 700, uppercase, slate-600 on slate-100, radius 4px, fixed width; the cartogram derives it from `layout_kind`). REJECTED: "PC . name" prefix (the dot is ambiguous) and overloading the parent-state line (row 1 is the STATE - a different fact, and it would break for the national PC map where state IS the parent line). The grain chip (left, slate) and the reservation tag (right, rose) are positionally distinct so "what kind of seat" and "reserved category" never blur.

### R-E. Parent-PC on an AC hover -> EXCLUDED (Hans, meaning deciding authority)

Even though `AcRow.parent_pc_id` + a cached `pcIdToName` map make it cheap (research confirmed it is available client-side in [frontend/src/lib/elections/constituency-district-loader.ts](../frontend/src/lib/elections/constituency-district-loader.ts)), an AC and its parent PC are TWO different elections (split-ticket voting is normal); showing the PC next to the AC invites reading one verdict as the other. Parent PC belongs on the click-through detail page, not the hover. Row 1 carries the parent STATE, never the parent PC.

### R-F. The one extra field = winning candidate name (Jony + Hans agree)

Row 5, muted slate-500 sub-line. It turns an abstract seat into a person ("who is my MLA / MP now?") and matches the India reference the user liked. The map view-models already carry `winner_candidate_name`. Winner vote-share % is REJECTED by both: it answers the same "how decisive" question the margin already owns; a redundant second number is exactly what slows the read. Turnout, alliance-vs-party label, and raw vote counts are EXCLUDED (Hans). Reservation SC/ST stays as the small right-side badge (existing), lowest priority - drop first only if a card ever exceeds its line budget.

### R-G. No arrows; the party glyph is the only icon (user constraint)

"Click to view" is TEXT only - no "->" / chevron. The only iconography is the 18px party symbol glyph.

### R-H. Placeholder box bug fix (Jony + Fowler) - the root cause

When a party has no symbol asset, `symbolMedallion` currently emits a bare-relative `<img src="party-symbols/placeholder.svg">` with NO base-url prefix and NO `onerror`; on a deep route (e.g. `/meghalaya/elections/assembly-2018`) the browser resolves it against the route dir -> 404 -> broken-image BOX. Fix: when the asset is empty/garbage, emit a party-hued DISC token (the resolved party hex, 1px slate-200 ring) - a neutral token that still carries identity, never a missing `<img>`. Real assets reach the card already base-resolved via `symbolAssetUrl(...)` at the call sites (research 6a/6b); keep that, keep `safeAssetPath` (a malicious path still degrades to the disc, never markup). Delete the `placeholder.svg` / `unverified.svg` `<img>` fallback branch from the pure fn.

### R-I. Hex cartogram cleanup (separate risk profile -> its own row)

1. **Font.** Remove the SVG `<text>` double-stroke halo (`paint-order="stroke"` + dark `stroke`/`stroke-width`/`stroke-opacity`) on the 2-letter codes; set `fill` to a per-hex readable color (white on saturated party fills, slate-900 on pale / pending) via the existing luma helper (`readableText` in tooltip-card.ts).
2. **Size.** Promote hex size to a knob. On-screen size is governed by the container `height` (default 520px), NOT the `S=10` radius constant (the SVG viewBox auto-fits, and the national grid is height-constrained). So expose `S` + `height` as props and RAISE the default `height` (~960px) so the hexes render roughly 2x larger by default - the answer to "can we double it / is it customizable" is YES via `height`.

### R-J. Topology (Fowler, craft deciding authority)

Pure `renderTooltipCard(model) -> string` emits the COMPLETE fixed-size card (incl. the left bar; the party hex is `safeHexColor`-sanitized in-string, so the hex cartogram gets the identical card for free via `{@html}`). `hover-card-position.ts` (pure, node-testable) computes placement + edge-flip from the cursor + the fixed 256x140 size. `<HoverCardShell>` is the thin positioned wrapper reused by all 4 surfaces. A full Svelte-component rewrite is REJECTED: it would relocate the proven string-level security suite (escape + hex/path allowlist) into templating = maximum blast radius, exactly what reader-before-writer forbids. The accent bar lives in the card STRING (not a shell prop) because (a) the hex is already sanitized in-string, (b) the hex cartogram then reuses the bar for free, (c) it keeps "the card is one string any surface can render" true. Do NOT add a second allowlist for the margin/bar color - reuse `safeHexColor`.

**Open follow-ups (NOT this plan; for `docs/research/` or a later plan):**
- Mobile tap-readout: a mid-tier Android has no hover; spec "Click to view" + dismissal as a tap interaction (Jony + Citizen handoff). Governs the one-second budget the rulings assume.
- Pin the precise definition "won by N points" = winner vote-share minus runner-up vote-share in pp, so map + hover + detail agree.

---

## Section 1 - Status Reckoner

Rows are PRs. Status starts `[ ] PENDING`, flips to `[x] DONE` with the merged PR number.

| Row | Title | Status | PR | Effort |
| - | - | - | - | - |
| 1 | Fixed card: rewrite `renderTooltipCard` (bar, grain, margin bands, candidate, click-to-view, disc fallback) | [x] DONE | #1244 | M |
| 2 | `HoverCardShell` + pure `hover-card-position` helper (fixed size + viewport edge-flip) | [x] DONE | #1243 | M |
| 3 | Adopt shell in the 3 d3 maps; drop number; pass grain + parentLabel + accent | [x] DONE | #1246 | M |
| 4 | Adopt shell in `TileCartogram` chrome only (buildTileRows untouched) | [x] DONE | #1245 | S |
| 5 | Switch `buildTileRows` -> `renderTooltipCard`; retire "Winner:/Margin:" asserts | [x] DONE | #1248 | M |
| 6 | Hex SVG: remove label halo + promote `S` / `height` to knobs | [x] DONE | #1247 | S |
| 7 | Non-drift guard contract test | [x] DONE | #1249 | S |

### Section 1.1 - Parallel wave schedule (dependency DAG)

Deps: `1:[]  2:[]  3:[1,2]  4:[2]  5:[1,4]  6:[4]  7:[5]`

- **Wave 1 (parallel):** Row 1, Row 2
- **Wave 2 (parallel):** Row 3, Row 4
- **Wave 3 (parallel):** Row 5, Row 6  (disjoint files: `election-tile-layout.ts` + its test vs `TileCartogram.svelte`)
- **Wave 4:** Row 7

The orchestrator dispatches each wave's rows as concurrent `runSubagent` PR-briefs, merges each row as its gates go green, and never idles between waves. Row 6 follows Row 4 because both edit `TileCartogram.svelte` (file-ordering, not a logical dep).

---

## Section 2 - Per-row specs

Each row: ONE PR = ONE branch = ONE reviewable unit. Gates = the 5-gate Definition-of-Done (CLAUDE.md section 9) + browser-verify (section 13) for any runtime change.

### Row 1 - Fixed card (rewrite `renderTooltipCard`)

- **Scope.** Rewrite `renderTooltipCard` to emit the R-A 256x140 card: left party bar (R-B), parent-state row, grain chip + name + reservation row (R-D), divider, symbol (disc fallback R-H) + party + 3-band margin (R-C) row, candidate row (R-F), "Click to view" text (R-G). Add additive model fields `grain?: "PC" | "AC"`, `parentLabel?: string | null`, `pending?: boolean` (absent `grain` omits the chip so un-migrated callers stay valid until Row 3). Keep ALL sanitization (`escapeHtml`, `safeHexColor`, `safeAssetPath`). Export `MARGIN_CLOSE_PP` / `MARGIN_DECISIVE_PP`. Replace the empty-asset `<img>` placeholder with the party-hued disc.
- **Files.** [frontend/src/lib/boundaries/tooltip-card.ts](../frontend/src/lib/boundaries/tooltip-card.ts), [frontend/src/lib/boundaries/tooltip-card.test.ts](../frontend/src/lib/boundaries/tooltip-card.test.ts)
- **Dep.** none.
- **Oracle.** `tooltip-card.test.ts`: ALL existing security asserts STILL pass AND new asserts pass - grain chip text present; each of the 3 margin bands resolves to its color by `abs(margin)`; the pending branch emits no margin + a neutral bar; an empty/garbage `symbolAsset` emits NO `<img>` and NO bare `party-symbols/...` string (the disc instead).

### Row 2 - `HoverCardShell` + pure position helper

- **Scope.** New pure `hover-card-position.ts`: `computeHoverCardPosition({ cursorX, cursorY, containerW, containerH, cardW = 256, cardH = 140, offset = 12 })` -> `{ left, top }` that flips LEFT when the cursor is near the right edge, UP when near the bottom, else anchors bottom-right of the cursor, and clamps within `[0, containerW - cardW] x [0, containerH - cardH]` so the FIXED box never clips/squeezes. New `HoverCardShell.svelte`: thin positioned wrapper, props `(x, y, html, containerW, containerH)`, renders `<div class="pointer-events-none absolute" style:left style:top>{@html html}</div>`, forwards `data-testid`.
- **Files.** new `frontend/src/lib/charts/HoverCardShell.svelte`, new `frontend/src/lib/charts/hover-card-position.ts`, new `frontend/src/lib/charts/__tests__/hover-card-position.test.ts`
- **Dep.** none.
- **Oracle.** `hover-card-position.test.ts`: right-edge cursor flips left; bottom-edge flips up; interior anchors bottom-right; the result is always within the clamp box.

### Row 3 - Adopt shell in the 3 d3 maps

- **Scope.** In `StatePcMapD3`, `StateAcMapD3`, `IndiaPcMapD3`: (a) drop the leading number from `title` (pass `name`, not `${eci_no}. ${name}`); (b) set `grain` ("PC"/"AC") and `parentLabel` (national PC: `state_ut_name` from props; per-state maps: the page state); (c) wrap the existing `{@html}` tooltip in `<HoverCardShell>` (replacing the ad-hoc absolute div). Preserve every existing `data-testid`.
- **Files.** [frontend/src/lib/charts/StatePcMapD3.svelte](../frontend/src/lib/charts/StatePcMapD3.svelte), [frontend/src/lib/charts/StateAcMapD3.svelte](../frontend/src/lib/charts/StateAcMapD3.svelte), [frontend/src/lib/charts/IndiaPcMapD3.svelte](../frontend/src/lib/charts/IndiaPcMapD3.svelte)
- **Dep.** Row 1, Row 2.
- **Oracle.** The 3 `@elections` Playwright specs pass with testids preserved AND the rendered card shows the name with NO leading "<n>. " prefix. Browser-verify (section 13): hover a PC seat, an AC seat, a pending seat - the box never resizes as the cursor moves.

### Row 4 - Adopt shell in `TileCartogram` chrome (content-neutral)

- **Scope.** Replace the ad-hoc `{@html tip.html}` div in `TileCartogram` with `<HoverCardShell>`. `buildTileRows` and its `tooltip_html` string are UNTOUCHED (still the old "Winner:/Margin:" content) - this row only swaps the chrome, proving the shell is content-neutral.
- **Files.** [frontend/src/lib/charts/TileCartogram.svelte](../frontend/src/lib/charts/TileCartogram.svelte)
- **Dep.** Row 2.
- **Oracle.** `tile-cartogram.test.ts` passes UNCHANGED (the "Winner: INC" assertions still hold - the chrome swap changed nothing in the content string). Browser-verify one cartogram tile.

### Row 5 - Switch the hex builder to the shared card

- **Scope.** Rewrite `buildTileRows` to populate a `TooltipCardModel` (grain from `layout_kind`; `parentLabel` from `stateCodeFromUnitId` + state-name lookup; candidate/party/margin from the winner row; pending branch) and call `renderTooltipCard` - so the hex card is byte-identical to the map card. Delete the private `escapeHtml` in `election-tile-layout.ts`. Retire the "Winner: INC" / "Margin:" / "Results pending" assertions in `tile-cartogram.test.ts` and replace with card-shaped asserts (grain chip, party pill text, "+25.0%", pending card) IN THE SAME ROW.
- **Files.** [frontend/src/lib/view-models/election-tile-layout.ts](../frontend/src/lib/view-models/election-tile-layout.ts), [frontend/src/lib/charts/__tests__/tile-cartogram.test.ts](../frontend/src/lib/charts/__tests__/tile-cartogram.test.ts)
- **Dep.** Row 1, Row 4.
- **Oracle.** `tile-cartogram.test.ts` (rewritten) asserts the hex `tooltip_html` now contains the grain chip + party short + "+25.0%" (and the pending tile -> pending card), and contains NO "Winner:" / "Margin:" literals.

### Row 6 - Hex SVG cleanup

- **Scope.** (1) Remove `paint-order="stroke"` + the dark `stroke`/`stroke-width`/`stroke-opacity` halo from the hex `<text>`; set `fill` to a per-hex readable color via `readableText`. (2) Promote `S` (hex radius) and the container `height` to props with defaults; raise the default `height` so hexes render ~2x larger. Keep the viewBox auto-fit.
- **Files.** [frontend/src/lib/charts/TileCartogram.svelte](../frontend/src/lib/charts/TileCartogram.svelte) (+ a small render/unit test)
- **Dep.** Row 4 (same file - sequence after).
- **Oracle.** A cartogram test asserts the `<text>` has NO `stroke` / `paint-order` attribute AND the `S` / `height` knobs change the emitted geometry / viewBox. Browser-verify the national hex map (labels crisp, hexes larger).

### Row 7 - Non-drift guard contract test

- **Scope.** New `tooltip-card-single-source.contract.test.ts` (node-env source-scan, matching the house pattern of [frontend/src/contracts/topic-card-uniqueness.test.ts](../frontend/src/contracts/topic-card-uniqueness.test.ts)). Asserts: the card-structural literals (the left-bar span, the grain-chip markup, "Click to view", "party-symbols/placeholder.svg") appear in NO frontend file except `tooltip-card.ts`; `election-tile-layout.ts` declares no private `escapeHtml(`; each of the 4 surfaces imports `renderTooltipCard` (content) AND mounts `HoverCardShell` (chrome).
- **Files.** new `frontend/src/contracts/tooltip-card-single-source.contract.test.ts`
- **Dep.** Row 5.
- **Oracle.** The guard test itself - it goes red if any surface re-rolls bespoke tooltip markup.

---

## Section 3 - Test churn summary (per Fowler)

- **Row 1** CHANGE `tooltip-card.test.ts`: keep all security asserts; add grain chip, 3 margin bands by color, pending branch, disc fallback (no `<img>` for empty/malicious asset).
- **Row 2** NEW `hover-card-position.test.ts`.
- **Row 3** No unit churn; update the 3 `@elections` Playwright specs only if they assert the old leading number. Testids preserved.
- **Row 4** No churn - `tile-cartogram.test.ts` stays green (proves chrome swap is content-neutral).
- **Row 5** CHANGE `tile-cartogram.test.ts`: retire `Winner: INC` / `Margin:` / `Results pending`; replace with card-shaped asserts.
- **Row 6** NEW/CHANGE one cartogram render test (no `paint-order`; `S` knob).
- **Row 7** NEW guard contract test.

Smell watch (Fowler): do NOT grow a second `marginColorHex` allowlist - reuse `safeHexColor`. Do NOT bundle Row 6 into the tooltip rows (couples SVG-paint regression to injection review). Do NOT pre-build `unverified`/`placeholder` fallback ceremony in the pure fn - that duplicated-policy split IS the original bug.

---

## Section 4 - Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md): 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).

### Wave dispatch for this plan (parallel)

Per section 1.1: dispatch Wave 1 {Row 1, Row 2} concurrently; on both merged, dispatch Wave 2 {Row 3, Row 4}; then Wave 3 {Row 5, Row 6}; then Wave 4 {Row 7}. Within a wave the rows touch disjoint files, so concurrent subagent PRs do not conflict. Rebase each next-wave branch onto the advancing `main` before its gates.

---

## Plan complete

Closed 2026-06-25. All 7 rows merged to `main` via the parallel wave schedule (4 waves, worktree-per-subagent, auto-merge). Distillation map:

- Row 1 (fixed card renderer) -> PR #1244. The design contract (R-A..R-J, section 0.1) + the renderer `frontend/src/lib/boundaries/tooltip-card.ts` are the live source of truth.
- Row 2 (HoverCardShell + pure position helper) -> PR #1243.
- Row 3 (3 d3 maps adopt the shell; leading number dropped; grain chip) -> PR #1246.
- Row 4 (TileCartogram chrome swap, content-neutral) -> PR #1245.
- Row 5 (hex tooltip -> shared card) -> PR #1248. FOLLOW-UP: `parentLabel` is omitted on the hex card (optional field renders a blank parent-state line); wiring a sync state-code->name lookup is a future minor row.
- Row 6 (hex labels halo-free + size knob) -> PR #1247. Default cartogram `height` 520->960; `NationalElection.svelte` mount bumped to 960.
- Row 7 (non-drift single-source guard) -> PR #1249. `frontend/src/contracts/tooltip-card-single-source.contract.test.ts` fences the card to one renderer + one chrome.

Agent-craft lessons (parallel bun-cache contention; subagent stall on slow bun install/build; `bun x vitest` cwd mis-resolution; worktree-per-subagent isolation) distilled to `/memories/`. The hover-card design contract (section 0.1) remains here as the audit ledger.

Plan-doc remains as the audit ledger; do not edit further. New work starts a new plan-doc.

---

## See also

- [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) - the "one card, not per-surface bespoke markup" doctrine this plan applies to tooltips.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - the PR lifecycle the EXECUTION BLOCK references.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - closure + archive ritual.
- [frontend/src/lib/boundaries/tooltip-card.ts](../frontend/src/lib/boundaries/tooltip-card.ts) - the single content authority being extended.
- [frontend/src/lib/elections/election-map-coloring.ts](../frontend/src/lib/elections/election-map-coloring.ts) - `marginShade` (map FILL margin depth; out of scope, do not duplicate in the tooltip).
- [CLAUDE.md](../CLAUDE.md) - authority table (section 0a), correction levels (section 6), anti-patterns (section 10).
