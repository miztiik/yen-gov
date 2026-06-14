# Party-page reimagination (`/parties/<slug>`)

**Last Updated**: 2026-06-14

**Level**: 4 (4+ files, structural; spans citizen-chrome vocabulary + visual reshape + 3 new view-model surfaces + per-card source provenance + a doc-rename sweep; ~10-11 PRs in 4 waves).

**Scope.** Reimagine the per-party page at `/parties/<slug>` (e.g. `/parties/bjp`, `/parties/dmk`) per the 2026-06-14 user direction. The current page (shipped via [docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md](../docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md) PR-4 and the [docs/archive/plans/20260613-party-deferred-followups-plan.md](../docs/archive/plans/20260613-party-deferred-followups-plan.md) sprint, all rows now merged on `main` as of `d09f8827c`) ships with seven concrete defects flagged by the user:

1. Citizen-chrome leaks transliterated South Asian language nouns (`Lok Sabha`, `Vidhan Sabha`) across the latest-of one-liners, KPI tile labels, chart H2s, stronghold subheaders, and the recognition-strip wording. The url-grammar policy already locks `Parliament` / `Assembly` as the chrome forms on the elections surface; the party page never applied it.
2. Strongholds rows render as text + Unicode block glyphs (`won 7 of 10 (70%) ▮▮▮▮▮▮▮▯▯▯`), which the user calls ugly. Jony never blessed this; it shipped as the v1 honest-degradation.
3. Stronghold rows show only the constituency name with no state context. A citizen reading "BAREILLY CITY" cannot tell which state it sits in. Constituency-name collisions across states ("Kalyan" in Maharashtra and Karnataka) make this load-bearing, not cosmetic.
4. The header avatar is a brand-colour SQUARE with the party short token written inside. When `parties.csv.symbol_asset` exists (e.g. `party-symbols/lotus.svg` for BJP) the symbol image is never rendered. When no asset exists, the geometry should be a CIRCLE, not a square.
5. The metadata footer (founded year, recognition, home states, wiki, native-script) is a horizontal row of text + icon pairs the user calls text-heavy. The native-script field (e.g. `भारतीय जनता पार्टी`) violates the same English-only chrome policy.
6. Both Parliament + state Assembly DualAxisBarLine charts read ugly. The dual-Y-axis encoding (bars = seats, line = vote-share %) forces the citizen to track two grids, two unit-formats, two ramps. The methodology-break tooltip leaks internal operator state (`lspc-delim-1976` subtitle + repo-path / `PR-N` references in the `note` body), violating the no-implementation-disclosure rule in [docs/concepts/citizen-first.md ADR-0021](../docs/concepts/citizen-first.md#adr-0021-no-implementation-disclosure-on-public-pages).
7. The page answers ONE citizen question well ("how did this party do over time?") but never answers "where does this party sit RIGHT NOW?", "who do they ride with?", "where are they fighting next?". Holy Law #9 (provenance) is also unsatisfied: the page carries no per-card source-pill back to `datasets/data/entities/source.csv`.

## 0. Operating contract

### Why this plan exists

The user direction was: "reimagine this page; Jony + Max + Hans". The three personas were dispatched in parallel as research-only subagents on 2026-06-14 and their written verdicts converged into the doctrine locks below. The user explicitly named "skill make a plan", so this is an execution-ready plan-doc (per `.claude/skills/prepare-plan/SKILL.md`) ready to run with "implement it".

### Personas consulted (verdict-source receipts)

| Persona | Items | Verdict role |
| --- | --- | --- |
| Jony (UI/UX) | J1-J8 | Visual reshape (avatar geometry, stronghold row, footer card, chart structural call, tooltip leak) |
| Max (Indicator Scout) | M1-M9 | New surface picks from canonical store (current-strength, head-to-head, alliance context, coverage badges, source-pills) |
| Hans (Governance) | H1-H8 | Citizen-vocabulary verdicts (per-surface chrome term), state-prefix semantics, recognition-scope nouns, doc-rename list |

All three ran in parallel as Explore subagents (no edits). Verdict files are session-cached:

- Jony: `toolu_vrtx_01Sx31jFShH1kc8ctVnn61eB__vscode-1781390311900`
- Max: `toolu_vrtx_019FRAwZUr75UuCEURwA6Cv9__vscode-1781390311904`
- Hans: `toolu_vrtx_01YYFBs4f2cKgwdk8ygqSukA__vscode-1781390311907`

Where personas diverged, the doctrine-lock table below records the orchestrator-resolved verdict per the CLAUDE.md section 0a authority table.

### ESCALATE triggers (Level-5 - pause for sign-off)

None expected on the happy path. Two real Level-5 triggers if they fire:

- **E1**: PR-10 (chart structural change) qualifies as a NEW renderer per the [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) closed-renderer-set discipline. Default disposition: add a `mode: "composite"` prop to the existing `DualAxisBarLine` (additive extension to the closed-renderer extension log already present in that doc) NOT mint a new `CompositeShareBar` primitive. If implementation reveals the additive extension is insufficient (e.g. the composite-bar encoding fundamentally differs from the dual-axis encoding), STOP and re-debate Gregor + Jony before minting a new primitive.
- **E2**: Any of the M3 head-to-head queries surface a derivation footgun (e.g. the rival is sentinel `parties.IN.IND` because the constituency's runner-up is always an Independent). Default disposition: filter sentinels out of rival-eligibility; cap the v1 to parties with `>=3 LS cycles AND recognition_scope IN ('national', 'state')`. If filtering still produces an offensive rival pick, STOP and consult Max + Hans.

### Doctrine locks (do NOT re-litigate during execution)

These are the orchestrator-resolved verdicts where personas disagreed or where a v1 simplification was chosen over a richer v2.

| Decision | Resolved verdict | Authority |
| --- | --- | --- |
| Per-surface citizen-chrome vocabulary | Hans H1 verbatim table. `Lok Sabha` -> `Parliament`; `Vidhan Sabha` -> `State Assembly`. Applied to every chrome surface (latest-of one-liners, KPI tile labels, chart H2s, stronghold subheaders, recognition-strip labels, sentence rewrites). | Hans (UX-Jony+Citizen alignment) |
| Stronghold row geometry | Jony J1 - 10-cell SVG dot strip (6px diameter, 4px gap). Wins = brand-colour fill; loss = paper fill + 1px slate-300 ring; did-not-contest = diagonal-hatch (reuse `party-stronghold-hatch` pattern from `PartyStrongholdMap.svelte`). Cap at 10 cells; pad shorter histories with did-not-contest. Drop the Unicode-block glyphs entirely. | Jony |
| Stronghold state-context | Jony J2 (inline state name prefix with middle-dot separator) - OVERRIDES Hans H3 (group-by-state subheader). Format: `Uttar Pradesh \u00b7 BAREILLY CITY` (state name slate-500; constituency name slate-800; middle-dot separator; constituency truncates before state). State name from `states.name(state_code)` already in scope. Reason: the section's load-bearing signal is the lifetime ranking, which group-subheaders destroy. Hans's state-collision concern (Kalyan-MH-vs-KA) is satisfied by the inline prefix; the grouping was the form, not the floor. CLAUDE.md section 0a UX authority is Jony+Citizen. | Jony (UX) overrides Hans (governance form) |
| Header avatar shape | Jony J4 - CIRCLE in all cases (with symbol, without symbol, sentinel). With symbol: 80px circle, paper-white fill, 3px brand-colour ring, symbol image 48x48 centred (16px padding). Without symbol: 80px circle, paper-white fill, 3px brand-colour ring, party short token 20px bold slate-900 centred. Sentinel (IND, NOTA): 80px circle, slate-200 fill, NO ring, slate-600 token. | Jony |
| Native-script field (`name_native_script`) rendering | DROP from the citizen surface entirely. Column stays on `parties.csv` (Holy Law #9 provenance). No Glossary-line carve-out on this page; the H1 already carries the English form. Mirror the drop in [PartyTooltip.svelte](../frontend/src/lib/party-pill/PartyTooltip.svelte). | Hans H4 + Jony J5 |
| Footer reshape | Jony J5 - desktop (>=1024px) side-rail "About this party" card (240px right rail); mobile (<1024px) labelled `<dl>` definition list under strongholds. Rows: Founded -> Recognition -> Home states -> Wikipedia -> Aliases -> Lineage. No native-script. No "Native script" icon. | Jony |
| Founding-year framing | Hans H6 - "Active since 1980" (live parties) / "Active 1925-1991" (defunct). Drop the bare "Founded 1980" / "Dissolved 1991" pair. Years-active counter is implicit; do not add it. | Hans |
| Recognition-scope citizen vocabulary | Hans H7 - `national` -> "Nationally recognised party"; `state` -> "State-recognised party"; `unrecognised_registered` -> "Registered party (unrecognised)"; `defunct` -> "Defunct"; `sentinel` -> "Special category". | Hans |
| Methodology-break tooltip + caption | Jony J7 - drop `methodology_version` subtitle entirely; rewrite title from `1) <year> methodology break` to `Boundaries changed in <at_year>` (for `kind=frame_change`); body = cleaned `note` (view-model helper strips `TODO/`, `PR-N`, `lspc-delim-N`, `methodology_version` substrings); footer = `Source: <publisher_url hostname>` when present. Caption under the chart rewrites to citizen-readable form, no operator jargon. The `methodology_breaks.json` note text ALSO gets scrubbed of operator narrative at the writer side (in the SAME PR) so the citizen never sees `PR-N` / repo-path content under any tooltip. | Jony |
| Section glyphs | Jony J3g - Parliament chart + KPI + stronghold subheader gets `landmark.svg` (already in `frontend/public/icons/`). State Assembly equivalents get `flag.svg` (already in `frontend/public/icons/`). No new icon assets; no new dep. | Jony |
| Chart structural call (PR-10) | Add `mode: "composite"` prop to existing `DualAxisBarLine` (NOT a new primitive). Composite mode: bar height = vote-share %; bar darkness ratio from the bottom = `seats_won / seats_contested`. Single Y-axis (vote-share, 0-100). Methodology-break markers + caption stay anchored to the X band. Both Parliament + State Assembly charts flip to composite mode. Default `mode` prop value remains "dual-axis" so the 0 other callers in the codebase break. | Jony J6 + Gregor authority (extension-log additive bump) |
| Three new surfaces in scope for this plan | PR-7 "Current strength" strip + PR-8 "Who they ride with" alliance strip + PR-9 per-card source-pill strip. PR-7 corroborated by Jony J8 #1 + Max M2; PR-8 by Max M5; PR-9 by Max M7+M8 + Holy Law #9. M3 head-to-head card is OUT-OF-SCOPE for this plan (deferred to a follow-on plan because rival-derivation depth + sentinel-handling complexity warrants its own PR-arc). | Orchestrator + Max + Jony |
| Documentation rename (language-name scrub) | The existing citizen-chrome policy in [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) is currently labelled by the name of one specific South Asian language; the user mandate is to rephrase to a language-neutral framing ("English-only citizen-chrome policy") WHILE keeping the policy in force. The rename also covers 4 sibling docs + CLAUDE.md line 86. Scrub is doc-only; the grep gate `git grep -iE "lok.sabha\|vidhan.sabha"` stays in force, naming the specific tokens not the policy. KEEP unchanged: `design-system.md` script-name + font-shaping content (script-name is not the language-name and is load-bearing technical context); archived plan-doc receipts (historical, not the policy surface). | Hans H5 |
| Coverage of `name_native_script` data | The column remains on `parties.csv`. Future operator-only diagnostics surfaces (if ever shipped) MAY render it; the citizen surface MUST NOT. The catalogue line in [docs/concepts/party-identity.md](../docs/concepts/party-identity.md) updates to "per the English-only citizen-chrome policy". | Hans H4 |

### Deferred citizen-asks (logged for future plans; NOT in scope here)

These were named in personas' M3+M9 + the prior plan-doc section 0 but are deferred to keep this plan to a tight 4-wave shape:

- **Head-to-head card** (Max M3) - rival-derivation from `_election_results.csv` runner-up tables. Deferred because sentinel + defunct + split-child edge-cases need their own PR-arc and the doctrine lock above caps PR-12 risk.
- **Symbol-history strip** (Jony J8 #3) - timeline of `(from_year, to_year, symbol_asset)` tuples. Needs a new `party_symbol_history.csv` sibling table; out-of-scope ingest.
- **Wikidata leadership snapshot + tooltip leader rendering** (Max M2 follow-on, PR-9 + PR-11 of the prior plan-doc) - operator-blocked on SPARQL endpoint pull. Already deferred upstream.
- **Recognition-flip history visual** (Max M6) - 2-event horizontal strip + future `recognition_scope_history` schema bump. Defer.
- **Geographical-reach mini-grid** (Max M4) - 28-state + 8-UT presence grid. Defer; the existing home-states pill row in the side-rail covers v1.
- **Electoral bonds donor card** (Max M9 #a) - ADR/SBI re-published corpus. Operator-blocked.
- **Manifesto links strip** (Max M9 #b) - ECI archive ingest. Operator-blocked.
- **ECI candidate-affidavits** (Max M9 #d) - OCR pipeline; operator effort. Defer.

These get filed into a follow-on plan-doc only when the user prioritises them; this plan does NOT bake them in as commitments.

## 1. Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| PR-1 | Citizen-chrome vocabulary scrub on `/parties/<slug>` - chart H2s, KPI tile labels, latest-of one-liners, stronghold subheaders, sentence rewrites (Hans H1 verbatim) | [ ] PENDING | - | ~2h |
| PR-2 | Methodology-break tooltip + caption + writer-side note scrub (Jony J7; cleans `methodology_breaks.json` of operator narrative; view-model `cleanNote()` helper as belt-and-braces) | [ ] PENDING | - | ~2h |
| PR-3 | Documentation rename - language-name scrub in url-grammar.md + electoral-hierarchy.md + party-identity.md + indicator-naming.md + CLAUDE.md (Hans H5; replacement label "English-only citizen-chrome policy") | [ ] PENDING | - | ~1h |
| PR-4 | Header avatar circle + symbol-image + sentinel treatment (Jony J4); also rewires `getAvatarStyle()` helper signature and updates tests | [ ] PENDING | - | ~3h |
| PR-5 | Stronghold row redesign - 10-cell SVG dot strip + inline state-name prefix (Jony J1 + J2); drops Unicode-block sparkline | [ ] PENDING | - | ~3h |
| PR-6 | Side-rail "About this party" card + Hans H6 founding framing + Hans H7 recognition vocabulary + drop `name_native_script` rendering (Jony J5 + Hans H4 + H6 + H7) | [ ] PENDING | - | ~3h |
| PR-7 | "Where this party sits today" current-strength strip (Max M2; new view-model + new component; reads `marts/party_pages/history.csv` filtered to MAX(year) per body + optional `office_holdings.csv` for chief-executive count) | [ ] PENDING | - | ~5h |
| PR-8 | "Who they ride with" alliance context strip (Max M5; new view-model + new component; reads `party_alliances.csv` filtered to latest event per body) | [ ] PENDING | - | ~4h |
| PR-9 | Per-card coverage badges + bottom-of-page source-pill strip (Max M7 + M8; satisfies Holy Law #9); new helper + footer strip | [ ] PENDING | - | ~3h |
| PR-10 | `DualAxisBarLine` composite mode + section-glyph wiring (Jony J6 + J3g; additive `mode: "composite"` prop; closed-renderer extension-log bump) | [ ] PENDING | - | ~4h |
| PR-11 | Closure - archive plan-doc to `docs/archive/plans/` + Section 6 closure ledger + durable distillation per `docs/how-to/distill-a-plan.md` | [ ] PENDING | - | ~30min |

**Total**: 11 PRs / 4 waves / ~30h wall-clock if parallelised correctly.

## 2. Wave + dependency graph

```
Wave 1 (parallel, file-disjoint, 3 subagents):
  PR-1  (frontend Party.svelte vocabulary scrub - touches H2 strings + KPI labels + latest-of one-liner args + stronghold subheaders + recognition-strip labels)
  PR-2  (frontend methodology-break tooltip cleanup + datasets/taxonomy/methodology_breaks.json note scrub)
  PR-3  (docs-only rename of language-name across 5 files)
        |
        v
Wave 2 (parallel, file-disjoint, 3 subagents):
  PR-4  (Party.svelte avatar block + getAvatarStyle helper + tests)
  PR-5  (Party.svelte stronghold list block + state-name derivation + SVG dot-strip component + tests)
  PR-6  (Party.svelte metadata footer block becomes side-rail AboutThisParty card + recognition vocabulary + drop native-script)
        |
        v
Wave 3 (parallel, file-disjoint, 3 subagents):
  PR-7  (new PartyCurrentStrength.svelte + view-model)
  PR-8  (new PartyAllianceContext.svelte + view-model)
  PR-9  (new PartySourcesStrip.svelte + view-model + per-card CoverageBadge)
        |
        v
Wave 4 (sequential):
  PR-10 (DualAxisBarLine composite mode - schema-is-the-design-system extension log bump + Party.svelte wiring + section glyphs)
        depends on: PR-7 + PR-8 in scope (they consume the chart slot ordering)
        |
        v
  PR-11 (Plan-doc archive + distillation)
        depends on: all 10 previous rows DONE
```

**Critical path**: Wave 1 (~3h parallel) -> Wave 2 (~3h parallel) -> Wave 3 (~5h parallel) -> PR-10 (~4h) -> PR-11 (~30min) = ~15h wall-clock optimal with 3-subagent parallelism per wave.

## 3. PR-1 - Citizen-chrome vocabulary scrub on `/parties/<slug>`

**Scope**. Apply Hans's H1 verdict table to every chrome surface on the party page. The page is the ONLY consumer of these strings; no shared label-registry refactor is needed.

### Exact rewrites (Hans H1 verbatim)

| Surface | Today | Verdict |
| --- | --- | --- |
| `formatLatestSentence` body-label arg, Parliament call site | `"Lok Sabha"` | `"Parliament"` |
| `formatLatestSentence` body-label arg, state-Assembly call site | `"Vidhan Sabha"` | `"State Assembly"` |
| KPI tile label, Parliament | `"Lok Sabha seats won"` | `"Parliament seats won"` |
| KPI tile label, state-Assembly | `"Vidhan Sabha seats won"` | `"State Assembly seats won"` |
| Chart H2, Parliament | `"Lok Sabha &mdash; every election contested"` | `"Parliament - every general election contested"` |
| Chart H2, state-Assembly | `"Vidhan Sabha &mdash; every state assembly election contested"` | `"State Assembly - every election contested"` |
| Stronghold subheader, Parliament | `"Lok Sabha"` | `"Parliament strongholds"` |
| Stronghold subheader, state-Assembly | `"Vidhan Sabha"` | `"State Assembly strongholds"` |
| Stronghold coverage caption | `"Strongholds computed over 1999&ndash;2024 LS / 2008&ndash;2026 AE; pre-coverage history not yet ingested."` | `"Strongholds computed from Parliament elections 1999-2024 and State Assembly elections 2008-2026. Earlier history not yet ingested."` |
| PartyStrongholdMap title (LS body) | `"Lok Sabha strongholds map"` | `"Parliament strongholds map"` |
| `formatLatestSentence` peak/low framing - the literal ` . v from peak X in Y.` shape | unchanged shape | Drop the `.` opening + `v` glyph in favour of a citizen-readable rewrite per Hans's VS sentence rewrite: `"Parliament (2024): 211 of 543 seats won, 36.5% of votes - down from the party's peak of 303 seats in 2019."` (live parties) / `"... - up from the party's earlier low of N in Y."` (Re-spell out v / ^; named verbs; comma separators; the latest-of helper test re-pins) |

### Recognition-strip labels (PR-2 of the closed deferred-followups plan, currently live on `main` as commit `d89f158a5` PR #992)

The `recognition-strip.ts` helper (`frontend/src/lib/parties/recognition-strip.ts`) carries body-label strings as part of strip text composition. Audit ALL strings in that file plus its sibling `RecognitionStrip.svelte` and re-pin every `Lok Sabha` to `Parliament`, `Vidhan Sabha` to `State Assembly`. Strip-text tests in `recognition-strip.test.ts` get re-pinned.

### Files touched

- MOD `frontend/src/routes/Party.svelte` - 9 string replacements per the table above; `formatLatestSentence(_, _, "Lok Sabha")` -> `..."Parliament"` and likewise for state Assembly.
- MOD `frontend/src/routes/Party.test.ts` - all `Lok Sabha` / `Vidhan Sabha` test assertions re-pinned (8+ assertion sites).
- MOD `frontend/src/lib/parties/recognition-strip.ts` - body-label strings re-pinned.
- MOD `frontend/src/lib/parties/recognition-strip.test.ts` - test assertions re-pinned.
- MOD `frontend/src/lib/parties/RecognitionStrip.svelte` - any chrome strings re-pinned.
- MOD `frontend/src/lib/parties/PartyStrongholdMap.svelte` - title / caption strings re-pinned.

### Acceptance gates

1. svelte-check 0 errors delta (baseline must be cited from `main` HEAD before edit).
2. vitest party-detail + recognition-strip focused: all pre-existing tests pass with the re-pinned assertions.
3. `git grep -E "Lok Sabha|Vidhan Sabha" frontend/src/routes/Party.svelte frontend/src/lib/parties/` MUST return zero matches after the PR (the existing url-grammar grep gate already names `lok.sabha|vidhan.sabha` lowercase; this PR extends the discipline to the title-case forms on the party page).
4. Section 13 browser smoke at `http://localhost:5173/parties/bjp` AND `/parties/dmk` AND `/parties/aap`: chart H2s + KPI labels + latest-of one-liners + stronghold subheaders + recognition-strip text all match Hans's verdict table; the `v` glyph and `.` opening on the framing line are gone.

### Load-bearing oracle

After the edit, run the contract probe:

```pwsh
$hits = git grep -E "Lok Sabha|Vidhan Sabha" frontend/src/ | Where-Object { $_ -notmatch "test\." -and $_ -notmatch "// MIGRATING" }
if ($hits) { Write-Error "Vocabulary scrub incomplete: $($hits | Out-String)"; exit 1 } else { "ok" }
```

Zero hits in frontend non-test code post-PR is the binary signal. Tests carry the strings inside `describe()` headers as historical receipts and are exempt.

## 4. PR-2 - Methodology-break tooltip + caption + writer-side note scrub

**Scope**. Two seams in ONE PR (the scrubbed `note` text and the renderer cleanup are tightly coupled; splitting risks a half-state):

1. **Writer side**: rewrite the `note` text on the 3 `lspc-delim-*` rows of `datasets/taxonomy/methodology_breaks.json` to drop the operator narrative (the literal substrings `PR-4 of TODO/20260613-party-deferred-followups-plan.md (Max Q1.1d).`, `PR-10 will render the marker on DualAxisBarLine.`, and similar repo-path / PR-id leaks). The cleaned `note` carries ONLY the citizen-relevant text: what changed, what citizens should not compare across the break.
2. **Renderer side**: drop the `methodology_version` subtitle from `DualAxisBarLine.svelte` line 359; rewrite the marker title from `1) <at_year> methodology break` to a `kind`-dispatched verb (`Boundaries changed in <at_year>` for `kind=frame_change`; `Definition changed in <at_year>` for `kind=definition_change`; `Source changed in <at_year>` for `kind=source`); add a `cleanNote()` view-model helper in `frontend/src/lib/view-models/party-detail.ts` as belt-and-braces (strips any leftover `TODO/[\w-]+\.md`, `PR-\d+`, `lspc-delim-\d+`, `methodology_version[:=]\s*\S+` substrings even if the writer-side scrub regresses); render `Source: <hostname>` as a clickable link in the tooltip footer when `publisher_url` is non-null. Rewrite the chart caption (currently `"1) delim 1967 (Parliament constituency boundaries shifted ...); 2) delim 1976 (boundaries shifted ...)."`) to a citizen-readable form: `"1) 1967: Parliament constituency boundaries changed. 2) 1976: boundaries changed again, then frozen until 2008. Why this matters: per-constituency win counts before and after a break refer to different geographic units."`

### Cleaned `note` text (writer side)

Three rows of `methodology_breaks.json` get `note` rewritten in this PR:

- **`lspc-delim-1967`**: from `"Parliament constituency boundaries shifted from the 1951-Order delimitation (used 1952-1962) to the 1962 Delimitation Commission output (used 1967 and 1971). Per-constituency comparisons across this year are not valid; per-state aggregates are. PR-4 of TODO/20260613-party-deferred-followups-plan.md (Max Q1.1d). PR-10 will render the marker on DualAxisBarLine."` -> `"Parliament constituency boundaries shifted from the 1951-Order delimitation (used 1952-1962) to the 1962 Delimitation Commission output (used 1967 and 1971). Per-constituency comparisons across this break are not valid; per-state aggregates are."`
- **`lspc-delim-1976`**: drop the final two sentences (`PR-4 of ...` and `PR-10 will render ...`); keep the substantive body.
- **`lspc-delim-2008`**: drop the operator narrative; keep the substantive body.

The 5 non-LS-delim rows in the same file ALREADY carry clean note text; do not touch them.

### Files touched

- MOD `datasets/taxonomy/methodology_breaks.json` - 3 `note` fields rewritten. No schema bump (additive scrub of free-form prose; `x-version` stays at 1.0).
- MOD `frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte` - line 359 `subtitle: m.row.methodology_version` -> `subtitle: ""` (or remove the field from the tooltip-row builder); line 358-ish title rewrite to `kind`-dispatched verb; tooltip-footer `Source:` link addition.
- MOD `frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.test.ts` - re-pin marker subtitle assertions to empty / dropped; add a new test that asserts no `lspc-delim-` substring leaks anywhere into the rendered tooltip data shape.
- MOD `frontend/src/lib/view-models/party-detail.ts` - new `cleanNote(raw: string): string` helper exported alongside existing `MethodologyBreakRow`; wired into the `ls_methodology_breaks` builder so the rows reaching the chart carry pre-cleaned text.
- MOD `frontend/src/lib/view-models/party-detail.test.ts` - new tests for `cleanNote()` covering: TODO/ path stripped, PR-N stripped, lspc-delim-N stripped, methodology_version=X stripped, well-formed citizen prose preserved verbatim.
- MOD `frontend/src/routes/Party.svelte` - chart caption rewrite per the verdict above (lines 581-587-ish, the `"1) delim 1967 ..."` paragraph).
- MOD `frontend/src/routes/Party.test.ts` - re-pin caption assertion.

### Acceptance gates

1. svelte-check delta 0.
2. vitest delta 0 with re-pinned assertions.
3. `python -m yen_gov validate --root .` (Tier-B) MUST stay green - the methodology-breaks schema validator passes with the new `note` text (still a string).
4. New contract test: `frontend/src/contracts/methodology-tooltip-no-leaks.test.ts` (NEW) - iterates every row in `methodology_breaks.json`, asserts the `note` field matches `/^[^\.]*\.(\s[^\.]*\.)*\s*$/` shape (sentences only, no parenthetical `(PR-N)` or repo-path leaks). Lives in `frontend/src/contracts/` for Tier-A discoverability.
5. Section 13 browser smoke at `/parties/dmk` (the screenshot subject): hover the methodology-break marker on the Parliament chart; tooltip MUST show `Boundaries changed in 1977` (title) + clean note text (body) + `Source: eci.gov.in` (footer link). No `lspc-delim-1976`. No `TODO/...`. No `PR-N`. The caption below the chart MUST match the citizen-readable rewrite verbatim.

### Load-bearing oracle

After the edit:

```pwsh
$leaks = Select-String -Path datasets/taxonomy/methodology_breaks.json -Pattern "PR-\d+|TODO/\w+|lspc-delim" -AllMatches
if ($leaks) { Write-Error "Writer-side scrub incomplete"; exit 1 }
cd frontend
$out = (./node_modules/.bin/vitest run --pool=forks --poolOptions.forks.singleFork=true frontend/src/contracts/methodology-tooltip-no-leaks.test.ts)
if ($LASTEXITCODE -ne 0) { Write-Error "Contract test failed"; exit 1 }
"ok"
```

## 5. PR-3 - Documentation rename (language-name scrub)

**Scope**. Pure-docs PR. Renames the existing citizen-chrome English-only policy from its current language-named label to a language-neutral label, across the 6 doc surfaces Hans H5 enumerated. The policy itself does NOT change; only its label and the body paragraphs that name a specific South Asian language. The mechanical `git grep -iE "lok.sabha|vidhan.sabha"` grep gate stays in force (it names the specific tokens, not the policy).

### Replacement label (Hans H5)

**"English-only citizen-chrome policy"** - preferred over alternatives ("Latin-script-only", "No-translit", etc.) because:

- "English-only" is the affirmative form of what the policy enforces.
- "Citizen-chrome" preserves the scope-limit (the policy never bound the CSV column names, the font subsets, or contributor docs - only the citizen surface).
- It reads naturally in cross-doc references ("per the English-only citizen-chrome policy").

### Files touched (Hans H5 list, redacted shape)

The BEFORE strings are not enumerated in this plan-doc per the user mandate (the literal language-name must not appear in committed prompts / docs). The executing subagent resolves the BEFORE text by reading each file directly; the rewrite rule is uniform across the 5 docs:

> **Rewrite rule**: wherever a doc names one specific South Asian language as part of the citizen-chrome policy label or body, replace the language-name with a language-neutral framing. The replacement label for the policy is **"English-only citizen-chrome policy"**. Body-paragraph phrases that name the same language as a citizen-vocabulary anchor (e.g. patterns like "learned the [lang] term first", "[lang] tokens in URLs", "No [lang]/English mixing") rewrite to language-neutral equivalents ("learned the local-language term first", "transliterated tokens in URLs", "Single-script titles, no transliteration").

1. **MOD [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md)** - rewrite the policy section heading at line 244 (a `### <prior-label> (PR-0 2026-06-09)` heading whose label names the language) to `### English-only citizen-chrome policy (PR-0 2026-06-09)`. Apply the rewrite rule to the body paragraphs at lines 246 (Context), 255 (Carve-outs), 257 (Mechanical scrub gate). The grep-gate regex `git grep -iE "lok.sabha|vidhan.sabha"` STAYS in force - it names the specific tokens, not the policy. The "PR-W1a" historical receipt stays.
2. **MOD [docs/concepts/electoral-hierarchy.md](../docs/concepts/electoral-hierarchy.md)** - apply the rewrite rule to line 53 (the URL-tokens line) and any adjacent body sentence that names the language as a citizen-vocabulary anchor.
3. **MOD [docs/concepts/party-identity.md](../docs/concepts/party-identity.md)** - apply the rewrite rule to line 100 (the `name_native_script` table row referencing the prior policy label by name). The replacement text scope-widens from "elections surface" to "citizen surface" because the policy now applies to the party page per PR-1 of this plan: the row becomes `"UI policy filters it OUT on the citizen surface per the English-only citizen-chrome policy."`
4. **MOD [docs/concepts/indicator-naming.md](../docs/concepts/indicator-naming.md)** - apply the rewrite rule to line 114 (the title-mixing rule); replacement text is `"English only. Single-script titles, no transliteration."`
5. **MOD [CLAUDE.md](../CLAUDE.md)** - apply the rewrite rule to line 86 (the URL-grammar pin citing the prior policy label by name). Drop the "elections surface" qualifier (policy now applies to the party page too); replacement text is `"... + English-only citizen-chrome policy, 2026-06-09)."`

### KEEP UNCHANGED

- [docs/architecture/frontend/design-system.md](../docs/architecture/frontend/design-system.md) lines 74, 91, 93 - the font-shaping content names a SCRIPT (not the citizen-chrome language) and is load-bearing technical context for the GSUB / conjunct shaping discussion. The English-only policy never bound the font subset; only the chrome. Per Hans H5 verbatim.
- Archived plan-docs under `docs/archive/plans/` carrying receipts of the OLD policy name (e.g. `20260609-election-experience-overhaul-plan.md` line 155, `20260610-electoral-data-quality-and-party-catalogue-plan.md` line 132, `20260613-party-deferred-followups-plan.md`). Archives are historical receipts, not the policy surface; touching them rewrites history.
- The grep-gate regex `git grep -iE "lok.sabha|vidhan.sabha"` STAYS in force at its current location in url-grammar.md.

### Acceptance gates

The subagent composes the verification regex at execution time by reading the BEFORE strings from each file - the literal language-name patterns are not enumerated in this plan-doc per the user mandate.

1. After the rewrite, `git grep -inE "<prior-policy-label-regex>" -- "docs/architecture/" "docs/concepts/" "CLAUDE.md"` MUST return zero matches (where `<prior-policy-label-regex>` is the regex matching the prior label as the subagent observes it before edit; archive matches are out of scope - the grep restricts to live doc roots).
2. The font-shaping content in [docs/architecture/frontend/design-system.md](../docs/architecture/frontend/design-system.md) MUST still contain its existing script-name references (proves we did not over-scrub).
3. Markdownlint / repo doc-style check stays green.
4. The CLAUDE.md cross-link to url-grammar.md still resolves (the heading-anchor for the renamed section becomes `#english-only-citizen-chrome-policy-pr-0-2026-06-09`; bump the link in CLAUDE.md in the SAME PR).

### Load-bearing oracle

Before the rewrite, the subagent captures `$before_regex` by reading the section heading at url-grammar.md line 244 (and the body-paragraph patterns that name the same language). After the rewrite:

```pwsh
$leaks = git grep -nE $before_regex -- "docs/architecture/" "docs/concepts/" "CLAUDE.md"
if ($leaks) { Write-Error "Scrub incomplete: $leaks"; exit 1 }
$keeps = Select-String -Path docs/architecture/frontend/design-system.md -Pattern "font-subset|font-shaping|script-name" -SimpleMatch
if (-not $keeps) { Write-Error "Over-scrub - font-shaping content was deleted"; exit 1 }
"ok"
```

If the subagent needs to bake the `$before_regex` value into a committed test or grep, capture it as a doc-internal constant in url-grammar.md's own renamed section (the policy SOURCE doc is the right home for the historical-label-redirect anchor) and reference the constant by anchor, never spelling the literal in any other doc, prompt, or test.

## 6. PR-4 - Header avatar (circle + symbol-image + sentinel)

**Scope**. Rewire `getAvatarStyle()` in `frontend/src/routes/Party.svelte` and the avatar markup block (lines ~439-463) to ship Jony J4's circle-with-ring-and-symbol-or-token treatment.

### Visual contract (Jony J4 verbatim)

- **With `meta.symbol_asset` populated** (e.g. BJP `party-symbols/lotus.svg`): 80px circle, paper-white fill (`var(--surface)`), 3px brand-colour ring, symbol image 48x48 centred (16px padding all sides). The brand colour sits on the RING; never behind the symbol (ECI symbols are authored for high contrast on white - putting the lotus on a saffron square is the current page's worst signal-to-noise).
- **Without `symbol_asset` (live parties)**: 80px circle, paper-white fill, 3px brand-colour ring, party short token (`meta.short`) in 20px bold slate-900 centred.
- **Sentinel parties (IND, NOTA)**: 80px circle, slate-200 fill (`#e2e8f0`), NO ring, slate-600 token (`#475569`). The absent ring is the visual signal "not a party in the same sense" - matches the recognition-strip's verbal cue.

### Helper signature change

The existing `getAvatarStyle(party_id, row, is_sentinel)` returns `AvatarStyle { kind, fill, ring, ink, swatch }`. Rewrite to return a richer shape:

```ts
export type AvatarKind = "symbol" | "token" | "sentinel";

export interface AvatarStyle {
  kind: AvatarKind;
  /** Background fill for the circle (always set). */
  fill: string;
  /** Ring colour - null for sentinel; brand colour otherwise. */
  ring: string | null;
  /** Token ink colour - used only when kind="token" or kind="sentinel". */
  ink: string;
  /** Symbol asset URL (resolved via glyphUrlFor) - non-null when kind="symbol". */
  symbol_url: string | null;
}
```

The 3-tier party-colour resolver branch (`anchor` / `brand` / `fallback`) collapses into the SHAPE decision (symbol present vs absent) because the avatar is now uniformly a circle. The brand colour comes from the resolver but only paints the ring; the fill is always `var(--surface)` (or slate-200 for sentinel). The old `swatch` corner-dot affordance is removed (the ring carries the brand-colour signal at higher legibility).

### Tests

- MOD `frontend/src/routes/Party.test.ts` - `getAvatarStyle` tests get re-pinned to the new shape:
  - BJP (anchor + symbol_asset): `kind: "symbol"`, `symbol_url: "/party-symbols/lotus.svg"`, `ring: "#FF9933"`, `fill: var(--surface)`.
  - INC (anchor + symbol_asset): `kind: "symbol"`, `symbol_url: "/party-symbols/hand.svg"`, `ring: <INC anchor colour>`.
  - DMK (brand + symbol_asset): `kind: "symbol"`, `symbol_url: "/party-symbols/rising-sun.svg"`, ring = brand colour.
  - Some party with NO symbol_asset: `kind: "token"`, `symbol_url: null`, ring = brand colour, ink = slate-900.
  - IND (sentinel): `kind: "sentinel"`, `symbol_url: null`, ring = null, fill = `#e2e8f0`, ink = `#475569`.
  - NOTA (sentinel): same as IND.
- The avatar block markup also gets a new contract test in `frontend/src/contracts/party-avatar-shape.test.ts` (NEW) that mounts the page for 3 representative slugs (`bjp`, `aap`, `nota`) and asserts the rendered DOM:
  - `<div data-testid="party-avatar">` has class `rounded-full` (circle, not `rounded-md`).
  - For `bjp`: contains a child `<img>` with src ending `lotus.svg`.
  - For `nota`: contains no `<img>`; contains the token text "NOTA".

### Files touched

- MOD `frontend/src/routes/Party.svelte` - avatar markup block (lines ~439-463); `getAvatarStyle()` helper (lines ~135-175); `partyRowFromMeta()` unchanged.
- MOD `frontend/src/routes/Party.test.ts` - `getAvatarStyle` tests + new render-shape tests.
- NEW `frontend/src/contracts/party-avatar-shape.test.ts` - the DOM-level contract test.

### Acceptance gates

1. svelte-check delta 0.
2. vitest delta 0 with re-pinned + new tests passing.
3. Section 13 browser smoke at `/parties/bjp` (anchor + symbol), `/parties/aap` (anchor + symbol), `/parties/dmk` (brand + symbol), some no-symbol party (e.g. `/parties/abnp`), `/parties/nota` (sentinel), `/parties/independent` (sentinel). Avatar geometry MUST be a circle in all six cases. Symbol image renders for the first 3; token for the 4th; slate-200-no-ring for the 5th + 6th.

### Load-bearing oracle

After the edit, the DOM contract test:

```pwsh
cd frontend
./node_modules/.bin/vitest run frontend/src/contracts/party-avatar-shape.test.ts
```

Must pass. The test directly asserts the geometry (circle) + symbol-image presence per slug.

## 7. PR-5 - Stronghold row redesign (SVG dot strip + inline state-name prefix)

**Scope**. Two coordinated changes to the strongholds section (Party.svelte lines ~650-700):

1. **Row geometry change**: replace the `won {wins} of {contested} ({winRate}%) [unicode-block-glyphs]` shape with `[State name] \u00b7 [Constituency name] [right-flush] [10-cell SVG dot strip] [win count text]`. New component `StrongholdDotStrip.svelte` does the SVG.
2. **State-name derivation**: each stronghold row gets the state name from the `entity_id`. For PCs (`IN-PC-2008-S22-167`): extract the `state_ut_code` (`S22`) and resolve via the existing `states.name(state_code)` accessor. For ACs (`IN-AC-2008-S22-167`): same extraction shape. Where the state-name resolver returns null (unknown code), render the state code as a degraded fallback (slate-400).

### Component contract (NEW `frontend/src/lib/parties/StrongholdDotStrip.svelte`)

```svelte
<script lang="ts">
  interface Props {
    results: readonly ("W" | "L")[];  // chronological oldest-first
    brand_colour: string;             // the party's fill colour for wins
    cell_count?: number;              // default 10
  }
  let { results, brand_colour, cell_count = 10 }: Props = $props();
  
  // Pad results array to cell_count with "did-not-contest" markers
  const padded = $derived.by(() => {
    const out = [...results];
    while (out.length < cell_count) out.push("DNC" as any);
    return out.slice(-cell_count);  // most recent N if longer
  });
</script>

<svg width="124" height="10" viewBox="0 0 124 10" aria-hidden="true">
  {#each padded as r, i}
    <circle cx={6 + i * 12} cy="5" r="3" 
      fill={r === "W" ? brand_colour : r === "L" ? "var(--surface)" : "url(#stronghold-dnc-hatch)"}
      stroke={r === "L" ? "#cbd5e1" : "none"}
      stroke-width="1"
    />
  {/each}
  <defs>
    <pattern id="stronghold-dnc-hatch" patternUnits="userSpaceOnUse" width="4" height="4" patternTransform="rotate(45)">
      <rect width="4" height="4" fill="var(--surface)" />
      <line x1="0" y1="0" x2="0" y2="4" stroke="#cbd5e1" stroke-width="1" />
    </pattern>
  </defs>
</svg>
```

The hatch pattern reuses the visual idiom from `PartyStrongholdMap.svelte` (already in the codebase from PR-12 of the prior plan). Total width 124px = 10 cells * 12px stride + 4px right pad.

### Row markup (Party.svelte stronghold list block, both LS and VS)

```svelte
<li class="flex items-center gap-3 px-3 py-2 text-sm" data-testid="party-stronghold-ls" data-state={state_code}>
  <span class="flex-1 min-w-0 flex items-baseline gap-1.5">
    <span class="text-slate-500 truncate">{state_name}</span>
    <span class="text-slate-400">\u00b7</span>
    <span class="font-medium text-slate-800 truncate">{s.constituency_name || s.entity_id}</span>
  </span>
  <span class="shrink-0 text-xs text-slate-500 tabular-nums">
    won {s.wins} of {s.contested}
  </span>
  <StrongholdDotStrip results={s.results} brand_colour={bar_color} />
</li>
```

The percent (e.g. `(70%)`) is dropped from the count text per Jony's "the dot strip carries the trajectory; the count carries the absolute" framing - showing wins / contested + a 10-cell strip is sufficient. The middle-dot `\u00b7` is a literal Unicode character (not an HTML entity); the file is UTF-8 already.

### State-name derivation helper

Extract a pure helper `stateNameFromEntityId(entity_id: string): { state_code: string | null; state_name: string }` into `frontend/src/lib/parties/party-detail-utils.ts` (NEW file). Logic: split on `-`; entity_ids of shape `IN-PC-YYYY-Sxx-N` or `IN-AC-YYYY-Sxx-N` have `state_code = parts[3]`; fall back to empty string when the pattern does not match. The component then calls `states.name(state_code) || state_code` for the citizen-readable string.

### Files touched

- NEW `frontend/src/lib/parties/StrongholdDotStrip.svelte` - the SVG component.
- NEW `frontend/src/lib/parties/StrongholdDotStrip.test.ts` - pure-helper tests for padding behaviour (results.length < cell_count -> pad with DNC; > cell_count -> take most recent).
- NEW `frontend/src/lib/parties/party-detail-utils.ts` - `stateNameFromEntityId` helper.
- NEW `frontend/src/lib/parties/party-detail-utils.test.ts` - tests for the helper on PC + AC + malformed ids.
- MOD `frontend/src/routes/Party.svelte` - remove the existing `sparkline()` helper export and its tests; remove the `winRate` calc; remove the `<span class="font-mono text-xs ...">` block; insert `<StrongholdDotStrip>` + state-name prefix per the markup above. BOTH LS and VS stronghold lists get the same shape.
- MOD `frontend/src/routes/Party.test.ts` - remove the `sparkline` tests; add minimal smoke that the rendered row carries the state name prefix.

### Acceptance gates

1. svelte-check delta 0.
2. vitest delta 0; the deleted `sparkline()` tests no longer exist.
3. Section 13 browser smoke at `/parties/bjp` (national party, mixed state strongholds in the top 10) AND `/parties/dmk` (state party, expect Tamil Nadu strongholds clustered). Each row MUST show: state name in slate-500, middle-dot, constituency name in slate-800, "won X of Y" count, 10-cell dot strip with brand-colour wins / hollow-ring losses / hatch DNC. No Unicode block glyphs anywhere. State names render for known codes; degraded slate-400 state code for unknown.
4. The DMK page screenshotted by the user (where every BAREILLY CITY-style row lacks state context) MUST now render `Uttar Pradesh \u00b7 BAREILLY CITY`-style prefixes.

### Load-bearing oracle

After the edit:

```pwsh
$leaks = Select-String -Path frontend/src/routes/Party.svelte -Pattern "sparkline|\\u25AE|\\u25AF|winRate" -AllMatches
if ($leaks) { Write-Error "Old sparkline residue: $leaks"; exit 1 }
```

Plus the browser-smoke render-shape assertion: every `[data-testid="party-stronghold-ls"]` element has BOTH a state-name child AND a 10-circle SVG.

## 8. PR-6 - Side-rail About card + recognition vocabulary + drop native-script

**Scope**. Three coordinated changes to the metadata footer (Party.svelte lines ~705-763):

1. **Layout reshape**: desktop (>=1024px) renders the metadata as a 240px right-rail card titled "About this party" with labelled rows (Founded -> Recognition -> Home states -> Wikipedia -> Aliases -> Lineage). Mobile (<1024px) renders as a `<dl>` definition list below the strongholds section. Wire via a `lg:grid lg:grid-cols-[1fr_240px]` outer layout on the main content block; the side-rail is `lg:row-span-N` so it floats next to the page content from the header downward.
2. **Founding-year framing rewrite** (Hans H6): the existing "Founded 1980" label becomes "Active since 1980" for live parties; "Active 1925-1991" for defunct parties (`meta.dissolved_year != null`). Drop the bare `meta.founded_year` + `meta.dissolved_year` pair-of-pills shape.
3. **Recognition-scope vocabulary rewrite** (Hans H7): rewrite the existing `recognitionLabel()` helper in Party.svelte:
   - `"national"` -> `"Nationally recognised party"`
   - `"state"` -> `"State-recognised party"`
   - `"unrecognised_registered"` -> `"Registered party (unrecognised)"`
   - `"defunct"` -> `"Defunct"`
   - `"sentinel"` -> `"Special category"`
4. **Drop `name_native_script` rendering entirely** (Hans H4 + Jony J5). The `<TopicIcon name="languages" />` block at lines 741-748 is deleted. Also drop the parallel block in `frontend/src/lib/party-pill/PartyTooltip.svelte` and its associated test fixtures.

### Side-rail content (NEW `frontend/src/lib/parties/PartyAboutCard.svelte`)

```
[Card header]   About this party
                
Active since    1980
Recognition     Nationally recognised party
Home states     (only renders for state-recognised)
Wikipedia       Bharatiya Janata Party (link)
Aliases         BHARATIYA JANATA PARTY, BHARTIYA JANTA PARTY
Lineage         Successor of Janata Party (link to /parties/jp)
```

The Aliases + Lineage rows are NEW (the existing footer never surfaces them); they read from `parties.csv.aliases` and `parties.csv.predecessor_party_ids` / `successor_party_ids` respectively. These columns exist; the view-model just needs to expose them.

### View-model additions

`PartyMeta` already carries the relevant raw columns. Augment `frontend/src/lib/view-models/parties.ts`:

- Expose `aliases: string[]` (split the existing pipe-delimited `aliases` column).
- Expose `predecessor_party_ids: string[]` and `successor_party_ids: string[]` (same split).
- Expose `dissolved_year: number | null` (already on the type).

`PartyAboutCard.svelte` consumes these directly.

### Tests

- NEW `frontend/src/lib/parties/PartyAboutCard.test.ts` - pure helper tests for: founding-year-framing for live vs defunct; recognition-label dispatch; aliases-split with empty / single / multi; lineage-link rendering.
- MOD `frontend/src/lib/view-models/parties.test.ts` - new tests for `aliases` / `predecessor_party_ids` / `successor_party_ids` exposure.
- MOD `frontend/src/routes/Party.test.ts` - remove `name_native_script` test assertions; add side-rail vs mobile-dl shape assertions.
- MOD `frontend/src/lib/party-pill/PartyTooltip.test.ts` - remove `name_native_script` assertions.

### Files touched

- NEW `frontend/src/lib/parties/PartyAboutCard.svelte` - the side-rail component.
- NEW `frontend/src/lib/parties/PartyAboutCard.test.ts` - pure-helper tests.
- MOD `frontend/src/lib/view-models/parties.ts` - expose 3 new fields.
- MOD `frontend/src/lib/view-models/parties.test.ts` - new field tests.
- MOD `frontend/src/routes/Party.svelte` - delete footer block lines 705-763; rewire main layout into `lg:grid lg:grid-cols-[1fr_240px]`; wire `<PartyAboutCard />` into the right column; mobile `<dl>` fallback below strongholds; `recognitionLabel()` helper rewrites.
- MOD `frontend/src/routes/Party.test.ts` - drop deleted-block assertions; add new shape assertions.
- MOD `frontend/src/lib/party-pill/PartyTooltip.svelte` - drop `name_native_script` rendering block.
- MOD `frontend/src/lib/party-pill/PartyTooltip.test.ts` - drop `name_native_script` assertions.

### Acceptance gates

1. svelte-check delta 0.
2. vitest delta 0.
3. Section 13 browser smoke at `/parties/bjp` (live + recognised + with predecessors), `/parties/jp` (defunct + with successors), `/parties/aap` (live + recognised + with home-states list), `/parties/nota` (sentinel + Special category recognition). On a desktop viewport (>=1024px wide) the About card MUST render as a 240px right rail. On mobile (<640px viewport) it MUST collapse to a `<dl>` under strongholds. The native-script `\u092d\u093e\u0930\u0924\u0940\u092f \u091c\u0928\u0924\u093e \u092a\u093e\u0930\u094d\u091f\u0940` text from the BJP screenshot MUST be absent.

### Load-bearing oracle

```pwsh
$nativeScript = Select-String -Path frontend/src/routes/Party.svelte frontend/src/lib/party-pill/PartyTooltip.svelte -Pattern "name_native_script" -SimpleMatch
if ($nativeScript) { Write-Error "name_native_script render path still alive"; exit 1 }
```

Plus the side-rail-vs-mobile-dl render shape verified via the new Party.test.ts assertions.

## 9. PR-7 - Current strength strip ("Where this party sits today")

**Scope**. New strip rendered DIRECTLY UNDER the header card and ABOVE the latest-of one-liners. Answers the citizen question "how big is this party right now?" using the canonical store's MAX(year) row per body (Max M2).

### Strip content (Max M2b verbatim shape, 2-3 sentences)

```
Parliament (Jun 2024): 211 of 543 seats - 36.5% vote share - the largest party.
State Assemblies (latest cycles): 1,469 seats across 14 states out of 4,123 total.
Last contested any election: Maharashtra State Assembly, Nov 2024.
```

The third line is rendered ONLY when a most-recent-event timestamp exists; the second line ONLY when at least 1 state assembly cycle is in the canonical store.

### View-model contract (NEW shape on `PartyDetailViewModel`)

Augment `frontend/src/lib/view-models/party-detail.ts` `PartyDetailViewModel` interface:

```ts
export interface PartyCurrentStrength {
  /** Latest Parliament (LS) cycle the party contested. Null when no LS history. */
  parliament_latest: {
    year: number;
    event_id: string;       // e.g. "general-2024"
    month_label: string;    // e.g. "Jun 2024"
    seats_won: number;      // e.g. 211
    seats_total: number;    // 543
    vote_share_pct: number;
    rank_label: string;     // "the largest party" | "second largest" | "third largest" | null
  } | null;
  /** Aggregated across the LATEST state Assembly cycle in each state with coverage. */
  state_assemblies_latest: {
    seats_won: number;        // sum across all latest-cycle state events
    seats_total: number;      // sum of the chamber sizes for those states
    state_count: number;      // how many states contributed
    latest_event_label: string; // e.g. "Maharashtra State Assembly, Nov 2024" - the single most recent state event the party contested
  } | null;
}
```

The SQL: for `parliament_latest`, take `marts/party_pages/history.csv` filtered to `(party_id, body=LS)` and pick the row with MAX(year). For `state_assemblies_latest`, group `(party_id, body=VS, state)` rows from the same mart, pick MAX(year) per state, sum the seats and contested counts; the latest_event_label comes from `MAX(period_label)` across all the per-state latest rows.

The `rank_label` derivation is OPTIONAL for v1 (requires a JOIN against the cycle's all-parties rollup to know whether this party was largest / 2nd / 3rd). v1 ships `rank_label = null` and a follow-on PR enriches.

### Component contract (NEW `frontend/src/lib/parties/PartyCurrentStrength.svelte`)

Pure presentational: renders the 2-3 lines per the shape above, with:

- Parliament line in slate-800 16px, with a `landmark.svg` glyph at the start (16px).
- State Assemblies line in slate-700 14px, with a `flag.svg` glyph at the start.
- Last contested line in slate-500 12px italic, no glyph.

Each numeric token (seats, vote-share, count) is `tabular-nums`. Sentinel parties (IND, NOTA): the strip RENDERS for IND showing aggregate numbers honestly (Independent IS counted in election results); HIDES entirely for NOTA + UNK (the aggregate is structurally meaningless).

### Coverage caveats (Max M2c+M2d)

The strip is followed by a slate-400 italic one-liner caption:

```
Election-night results - does not track post-election defections, resignations, or bye-elections later than the latest cycle.
```

This caption is REQUIRED per Max M2d (citizen-honest framing of "the canonical store records election outcomes, not current floor strength").

### Files touched

- NEW `frontend/src/lib/parties/PartyCurrentStrength.svelte`.
- NEW `frontend/src/lib/parties/PartyCurrentStrength.test.ts`.
- NEW `frontend/src/lib/view-models/party-current-strength.ts` (pure SQL builders + projection from raw mart rows).
- NEW `frontend/src/lib/view-models/party-current-strength.test.ts`.
- MOD `frontend/src/lib/view-models/party-detail.ts` - add `current_strength: PartyCurrentStrength | null` field to `PartyDetailViewModel`; populate via the new builder in `loadPartyDetail`.
- MOD `frontend/src/lib/view-models/party-detail.test.ts` - new tests covering the populated field for representative parties.
- MOD `frontend/src/routes/Party.svelte` - wire `<PartyCurrentStrength />` directly under the header card.
- MOD `frontend/src/routes/Party.test.ts` - smoke that the strip renders for BJP and is hidden for NOTA.

### Acceptance gates

1. svelte-check + vitest delta 0.
2. New tests for the view-model: BJP latest LS = 2024 row from history.csv; AAP latest LS = 2024; defunct party (JP) returns null `parliament_latest` (no recent contests).
3. Section 13 browser smoke at `/parties/bjp` (largest party, full strip lights up), `/parties/aap` (partial strip - has LS but state assemblies summed across 2 states), `/parties/dmk` (state party - LS line shows Tamil Nadu-only contest), `/parties/nota` (entire strip hidden), `/parties/independent` (strip renders aggregate honestly with the "Independent isn't one party" sentinel framing already present).

### Load-bearing oracle

```pwsh
cd frontend
./node_modules/.bin/vitest run frontend/src/lib/view-models/party-current-strength.test.ts
```

Plus the browser-smoke per-slug shape assertion above.

## 10. PR-8 - Alliance context strip ("Who they ride with")

**Scope**. New strip rendered DIRECTLY UNDER the Current Strength strip (so the citizen reads: party-now -> alliance-now -> historical charts). Reads `datasets/data/entities/party_alliances.csv` filtered to the LATEST event per body for the focal party (Max M5).

### Strip content (Max M5b verbatim shape, 2 sub-rows)

```
Parliament 2024 - led NDA (294 seats with 12 partners: JD(U), TDP, ShS, LJPRV, JD(S), ...)
State Assemblies - alliance per state where contested:
  Maharashtra (2024): led Mahayuti with ShS + NCP
  Bihar (2020): NDA junior with JD(U) + LJP
  Karnataka (2023): contested alone
  Tamil Nadu (2021): AIADMK-led junior partner
```

The "led / junior partner / contested alone" classification comes from the focal party's seat count vs partner counts within the (event, state) tuple - "led" when the focal has the largest seat count in the alliance, "junior partner" when not, "contested alone" when no alliance row exists for that (event, state).

### View-model contract

NEW `frontend/src/lib/view-models/party-alliance-context.ts`:

```ts
export interface PartyAllianceContext {
  parliament: {
    event_label: string;       // "Parliament 2024"
    alliance: string;           // "NDA"
    role: "led" | "junior" | "alone";
    partner_count: number;       // 12
    partner_names_top: string[]; // top-N partners by seats (truncate at 5 with "..." caption)
    total_alliance_seats: number;
  } | null;
  state_assemblies: {
    state_name: string;         // "Maharashtra"
    event_label: string;         // "Maharashtra (2024)"
    alliance: string | null;     // "Mahayuti" or null when no alliance row
    role: "led" | "junior" | "alone";
    partner_names_top: string[];
  }[];
}
```

SQL: `SELECT event_id, state, alliance FROM party_alliances WHERE party_id = ?` then group by `(event_id, state)` and pick the MAX event per body. Cross-reference for partners: `JOIN party_alliances pa2 ON pa2.event_id = pa.event_id AND pa2.state = pa.state AND pa2.alliance = pa.alliance AND pa2.party_id != ?`.

Per the user-memory note 2026-06-14 "Alliance rows ship independent of candidacies CSV": when alliance data exists but per-state candidacies are not in the per-state `_election_results.csv` (e.g. some forward-looking events), surface as `role: "alone"` with no partner names - the alliance is recorded but the seat-count derivation is impossible. Surface this honestly with the slate-400 caption.

### Component contract (NEW `frontend/src/lib/parties/PartyAllianceContext.svelte`)

Pure presentational; one header line + an unordered list of per-state lines. Sentinel parties (IND, NOTA, UNK): strip HIDDEN entirely (sentinels do not form alliances). State-only parties (single home_state, e.g. BJD in Odisha): the strip shows only the state Assembly section, no Parliament section (when they did contest LS, the Parliament line renders honestly).

### Coverage caveats (Max M5c)

Bottom slate-400 italic one-liner:

```
Alliance ties recorded only for the cycles already ingested; older arrangements may exist in publisher records not yet on file.
```

### Files touched

- NEW `frontend/src/lib/parties/PartyAllianceContext.svelte`.
- NEW `frontend/src/lib/parties/PartyAllianceContext.test.ts`.
- NEW `frontend/src/lib/view-models/party-alliance-context.ts`.
- NEW `frontend/src/lib/view-models/party-alliance-context.test.ts`.
- MOD `frontend/src/lib/view-models/party-detail.ts` - add `alliance_context: PartyAllianceContext | null`; populate via the new builder.
- MOD `frontend/src/lib/view-models/party-detail.test.ts` - new tests.
- MOD `frontend/src/routes/Party.svelte` - wire `<PartyAllianceContext />` under `<PartyCurrentStrength />`.

### Acceptance gates

1. svelte-check + vitest delta 0.
2. New view-model tests: BJP general-2024 = "led NDA"; INC general-2024 = "led INDIA"; AAP general-2024 = "INDIA junior"; some state party general-2024 = "alone" or "junior partner".
3. Section 13 browser smoke at `/parties/bjp` (Parliament line + 3-5 state lines), `/parties/inc` (parallel shape), `/parties/aap` (Delhi alone, INDIA junior nationally), `/parties/bjd` (Odisha-only state Assembly line, alone in Parliament when contested), `/parties/nota` (strip hidden).

### Load-bearing oracle

```pwsh
cd frontend
./node_modules/.bin/vitest run frontend/src/lib/view-models/party-alliance-context.test.ts
```

Per-slug renders verified via browser smoke.

## 11. PR-9 - Per-card coverage badges + bottom-of-page source-pill strip

**Scope**. Two coordinated additions to satisfy Holy Law #9 (provenance is mandatory):

1. **Per-card coverage badge**: small slate-400 italic one-liner at the bottom of each major section (Current Strength, Alliance Context, Parliament chart, State Assembly chart, Strongholds) declaring the event-set spanned + the publisher + the vintage (Max M7). Reuses the badge pattern from `IndicatorCoverageBadge.svelte` (lookup the existing pattern; if unsuitable, ship a new `PartyCoverageBadge.svelte`).
2. **Bottom-of-page source-pill strip**: a collapsible "Sources for this page" strip at the very bottom. Default collapsed: `Computed from 32 source files across TCPD and ECI - click to see all`. Expanded: a 4-column table (Producer / Title / Vintage / Cards using it). Reads from `marts/party_pages/history.csv` and `strongholds.csv` `source_ids` columns and JOINs to `entities/source.csv` for the producer/title/vintage triple (Max M8a).

### Coverage badge shape (Max M7 examples)

- LS chart: `Parliament 1962-2024 - 16 cycles - TCPD Panel + ECI Form-20 - last refresh src vintage 2024-06-04`
- VS chart: `State Assembly 2008-2026 - <N> cycles across <S> states - TCPD + ECI - last refresh src vintage 2024-XX-XX`
- Strongholds: `Computed from Parliament 1999-2024 and State Assembly 2008-2026 - <N> cycles - earlier history not yet ingested`
- Current Strength: `Latest cycle per body - Parliament 2024 - state Assemblies span 2018-2026 - data current as of <vintage>`
- Alliance Context: `Recorded for <Y> cycles - <N> of 36 jurisdictions covered - older arrangements not yet on file`

The badge text MUST come from the view-model (computed from the actual source_ids and event_ids in scope), NEVER hand-typed.

### Source-pill strip shape (Max M8b)

Bottom of page, before the right-rail About card on desktop:

```
[v Sources for this page]   (collapsed by default)
```

Expanded:

```
| Producer | Title | Vintage | Used in |
| Trivedi Centre for Political Data | Lok Sabha Constituency Panel 1962-2019 | 2024-06-04 | Parliament chart, Strongholds |
| Election Commission of India | Form-20 - Parliament General 2024 | 2024-06-15 | Parliament chart, Current Strength, Strongholds |
| Trivedi Centre for Political Data | All States GE 1962-1998 | 2024-06-04 | Parliament chart |
| ... |
```

The Vintage column links to `source.url` when set; the Title carries no link.

### View-model additions

NEW `frontend/src/lib/view-models/party-sources.ts`:

```ts
export interface PartyPageSource {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  url: string | null;
  /** Which cards on the page consume this source. */
  used_in: string[];
}

export interface PartySourcesStrip {
  total_count: number;
  by_card: Map<string, PartyPageSource[]>;  // card_id -> sources
  all: PartyPageSource[];                    // deduped, sorted by producer then vintage desc
}
```

Plus per-card coverage badge builders in the same file (`buildLsCoverageBadge`, `buildVsCoverageBadge`, etc.) returning the citizen-readable strings.

### Files touched

- NEW `frontend/src/lib/parties/PartyCoverageBadge.svelte` (small badge component; if the existing `IndicatorCoverageBadge.svelte` works, reuse instead - file_search before deciding).
- NEW `frontend/src/lib/parties/PartySourcesStrip.svelte` (collapsible strip).
- NEW `frontend/src/lib/parties/PartySourcesStrip.test.ts`.
- NEW `frontend/src/lib/view-models/party-sources.ts`.
- NEW `frontend/src/lib/view-models/party-sources.test.ts`.
- MOD `frontend/src/lib/view-models/party-detail.ts` - add `sources_strip: PartySourcesStrip` to `PartyDetailViewModel`; populate.
- MOD `frontend/src/lib/view-models/party-detail.test.ts` - new tests.
- MOD `frontend/src/routes/Party.svelte` - wire `<PartyCoverageBadge>` under each major section + `<PartySourcesStrip>` at the bottom of `<main>`.

### Acceptance gates

1. svelte-check + vitest delta 0.
2. NEW Tier-A contract test `frontend/src/contracts/party-page-provenance.test.ts`: for any populated `PartyDetailViewModel`, EVERY card MUST have a non-empty `used_in` source list AND `sources_strip.all.length > 0`. This enforces Holy Law #9 mechanically.
3. Section 13 browser smoke at `/parties/bjp`: each section has a coverage badge; the source strip at the bottom shows ~30+ sources collapsed; expanding shows the 4-column table; producer + title + vintage all non-empty for each row.

### Load-bearing oracle

```pwsh
cd frontend
./node_modules/.bin/vitest run frontend/src/contracts/party-page-provenance.test.ts
```

Per Holy Law #9, any card without a source attribution is a ship-block. The contract test fails if any card returns an empty `used_in`.

## 12. PR-10 - DualAxisBarLine composite mode + section glyph wiring

**Scope**. Two coordinated changes to make both Parliament + state Assembly charts citizen-readable (Jony J6 + J3g):

1. **Composite-bar mode on `DualAxisBarLine`**: additive `mode: "composite" | "dual-axis"` prop with default `"dual-axis"` (existing behaviour preserved for 0 other call sites - all 2 existing call sites are the LS + VS charts on the party page, both flipped to `"composite"` in the same PR). In composite mode: bar height = vote-share % (single Y-axis 0-100); bar darkness ratio from the bottom = `seats_won / seats_contested` painted as a darker shade of the brand colour. The methodology-break markers + caption stay anchored to the X band.
2. **Section glyph wiring**: prepend `<TopicIcon name="landmark" />` to the Parliament chart H2 + KPI tile + stronghold subheader; prepend `<TopicIcon name="flag" />` to the state Assembly equivalents (Jony J3g). Both icons already in `frontend/public/icons/` (verified 2026-06-14).

### Composite-bar encoding (Jony J6)

Per cycle (bar):
- X position: cycle year
- Bar height: `vote_share_pct` (0-100 scale, single Y-axis labelled "Vote share %")
- Bar fill: from the bottom up to `bar_height * (seats_won / seats_contested)`, the brand colour at full saturation; from there to the top, the brand colour at 40% opacity (the "didn't convert" upper portion)
- Bar width: per the existing band scale
- Tooltip on hover: `Year: 2024 - vote share 36.5% - seats 211 of 543 contested (seat conversion 38.9%)`

This single composite bar carries TWO indicators (vote-share + seat-conversion) in one geometry. The citizen reads ONE axis. The seat-conversion story is the darker-bottom fill ratio.

### Schema-is-the-design-system extension log

Per [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) the closed-renderer extension log already contains a `DualAxisBarLine` entry with 4 qualifying indicators. Adding the `mode: "composite"` prop is an ADDITIVE extension of the SAME primitive (not a new primitive); update the extension-log entry to name the new mode + its qualifying indicators:

- Parliament: vote-share + seat-conversion - the citizen-facing primary view post-redesign.
- State Assembly: parallel.
- Future: per-event vote-share + winner-margin.
- Future: per-state turnout + valid-vote-share.

This is an ADDITIVE update; no new ADR file, no schema bump.

### Files touched

- MOD `frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte` - add `mode` prop with default `"dual-axis"`; branch the bar-fill renderer + Y-axis renderer on mode; the line series is hidden in composite mode (or repurposed as the tooltip-only series).
- MOD `frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.test.ts` - new tests for composite mode (bar geometry, tooltip shape, no line rendered).
- MOD `frontend/src/routes/Party.svelte` - both `<DualAxisBarLine>` call sites add `mode="composite"`; the line + bar data semantics flip (bars become vote-share, the seat-conversion is computed in the helper); chart H2 + KPI labels + stronghold subheaders get `<TopicIcon>` prefix.
- MOD `frontend/src/routes/Party.test.ts` - re-pin assertions to match composite mode.
- MOD `docs/concepts/schema-is-the-design-system.md` - the `DualAxisBarLine` extension-log entry gains a "Mode: composite (added 2026-06-XX)" sub-section with the 2+ qualifying indicators.

### Acceptance gates

1. svelte-check + vitest delta 0.
2. The DualAxisBarLine composite-mode test in `DualAxisBarLine.test.ts` covers: single Y-axis labelled "Vote share %"; no line series in DOM when `mode="composite"`; bar fill is split into two opacity bands per cycle.
3. Section 13 browser smoke at `/parties/bjp`, `/parties/dmk`, `/parties/aap`: both charts MUST render in composite mode; bar HEIGHT visibly tracks vote-share trajectory (not seats); bar DARKER PORTION tracks the seats-won subset; methodology-break markers + caption still anchored (already cleaned by PR-2). Section glyphs (`landmark.svg` + `flag.svg`) appear next to the chart H2s, KPI labels, and stronghold subheaders.

### Load-bearing oracle

```pwsh
cd frontend
./node_modules/.bin/vitest run frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.test.ts
```

Plus the browser-smoke geometry assertion: ` <rect data-mode="composite" data-overlay="seats-fill">` elements exist on the chart SVG for each cycle.

## 13. PR-11 - Plan-doc archive + distillation

**Scope**. Close the plan and distill durable learnings per `docs/how-to/distill-a-plan.md`.

### Steps

1. Verify all 10 implementation rows are `[x] DONE` in the Reckoner (Section 1).
2. Author Section 14 closure stanza here: per-PR ledger (PR # + SHA + 1-line "what shipped"); persona-debate distillation pointer (Jony / Max / Hans verdict files cited); 3 durable lessons for `/memories/lessons.md` (e.g. "doctrine-lock the chrome vocabulary in a per-page closed-list before adding view-models that re-author the strings"; "writer-side scrub of operator narrative beats renderer-side guards alone"; "side-rail layout flip needs the `lg:grid-cols-[1fr_240px]` shell at the route-level, not inside the side-rail component").
3. Lift any durable doctrinal additions into the right `docs/` home (specifically: if PR-10's composite-mode shape generalises, fold it into [docs/architecture/frontend/charts/dual-axis-bar-line.md](../docs/architecture/frontend/charts/dual-axis-bar-line.md) with the new shape spec; if PR-3's rename produces a doctrinal phrase the codebase will lean on, ensure the url-grammar.md section is the authoritative anchor).
4. `git mv TODO/20260614-party-page-reimagination-plan.md docs/archive/plans/20260614-party-page-reimagination-plan.md` and update any cross-links.
5. Open the closure PR with title `docs(plans): archive 20260614 party-page-reimagination plan (PR-11 closure)`.

### Acceptance gates

1. Test path GONE: `git ls-files TODO/20260614-party-page-reimagination-plan.md` returns empty.
2. Archive path EXISTS: `Test-Path docs/archive/plans/20260614-party-page-reimagination-plan.md`.
3. Closure stanza heading EXISTS: `Select-String -Path docs/archive/plans/20260614-party-page-reimagination-plan.md -Pattern "## 14. Plan complete"`.
4. No broken relative links to the old TODO/ path remain in the repo.

### Load-bearing oracle

```pwsh
$gone = git ls-files TODO/20260614-party-page-reimagination-plan.md
if ($gone) { Write-Error "Old plan path still tracked"; exit 1 }
Test-Path docs/archive/plans/20260614-party-page-reimagination-plan.md
$broken = git grep -l "TODO/20260614-party-page-reimagination" -- "*.md"
if ($broken) { Write-Error "Broken cross-links: $broken"; exit 1 }
"ok"
```

## 14. Plan complete

This section is filled at PR-11 close. Per-row PR ledger + persona-debate distillation pointer + 3 durable lessons land here.

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

## See also

- [CLAUDE.md](../CLAUDE.md) - section 0a authority table (Hans+Max data shape; Jony+Citizen UX; Gregor contracts), section 10 anti-patterns, Holy Law #9 provenance, Holy Law #4 docs.
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) - the 8-step persona startup ritual.
- [docs/agents/guardrails.md](../docs/agents/guardrails.md) - what every persona must honour.
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - the 7-step question-first pipeline + ADR-0021 no-implementation-disclosure rule that informs PR-2's tooltip scrub.
- [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) - the closed-renderer extension log that PR-10 amends.
- [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) - the existing citizen-chrome policy whose label PR-3 renames (policy unchanged).
- [docs/concepts/party-identity.md](../docs/concepts/party-identity.md) - the `name_native_script` column whose rendering PR-6 drops.
- [docs/concepts/electoral-hierarchy.md](../docs/concepts/electoral-hierarchy.md) - the chrome-vocabulary line PR-3 rewrites.
- [docs/concepts/indicator-naming.md](../docs/concepts/indicator-naming.md) - the title-mixing rule PR-3 rewrites.
- [docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md](../docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md) - the original PR-4 that shipped the page now being reimagined.
- [docs/archive/plans/20260613-party-deferred-followups-plan.md](../docs/archive/plans/20260613-party-deferred-followups-plan.md) - the closed sprint that landed methodology-break markers (PR-10) + stronghold choropleth (PR-12); commit `d09f8827c`.
- [frontend/src/routes/Party.svelte](../frontend/src/routes/Party.svelte) - the page being reimagined.
- [frontend/src/lib/view-models/party-detail.ts](../frontend/src/lib/view-models/party-detail.ts) - the view-model that PRs 7/8/9 extend.
- [frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte](../frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte) - the primitive PR-10 extends with composite mode.
- [datasets/data/entities/parties.csv](../datasets/data/entities/parties.csv) - source of `symbol_asset`, `brand_colour`, `name_native_script` (column stays; render drops).
- [datasets/data/entities/source.csv](../datasets/data/entities/source.csv) - the citation ledger PR-9 wires per Holy Law #9.
- [datasets/data/entities/party_alliances.csv](../datasets/data/entities/party_alliances.csv) - the source PR-8 reads.
- [datasets/data/marts/party_pages/history.csv](../datasets/data/marts/party_pages/history.csv) + [strongholds.csv](../datasets/data/marts/party_pages/strongholds.csv) - the marts PR-7 + PR-9 read.
- [datasets/taxonomy/methodology_breaks.json](../datasets/taxonomy/methodology_breaks.json) - the file whose `note` text PR-2 scrubs.
- [frontend/public/icons/landmark.svg](../frontend/public/icons/landmark.svg) + [flag.svg](../frontend/public/icons/flag.svg) - the section glyphs PR-10 wires.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - the PR lifecycle the Execution contract references.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - the closure ritual PR-11 follows.
