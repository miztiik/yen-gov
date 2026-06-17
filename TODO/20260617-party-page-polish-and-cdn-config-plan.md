# Party-page polish + CDN/base config seam - execution plan

**Last Updated**: 2026-06-17
**Level**: 3 (cross-cutting; Row A is structural consolidation of an existing runtime seam, guarded by a contract test). No Level-5 surface (no data model, schema-major, or runtime-design change).

/ Authoring note: this plan was authored via the `prepare-plan` skill after a live
/ verification pass on https://miztiik.github.io/yen-gov/parties/cpi and a 3-persona
/ consult (Jony / Citizen / Max). It AUTHORS the work; it does not implement it.

---

## Section 0 - Operating contract

### 0.1 Why this plan exists

The per-party page `/parties/<slug>` (e.g. CPI) carries one production bug and several
citizen-polish gaps the user flagged on 2026-06-17:

1. The Wikipedia logo renders as a broken box on the deployed site.
2. The CDN/base path is resolved by 5+ scattered call sites, so a base-less asset
   string can (and did) slip through unguarded - the user wants ONE config seam every
   frontend module reads from, plus a guard so the wiki-style 404 cannot recur.
3. Five repeated "Source: ..." lines + an orphaned "About this page" footer read as
   chrome clutter.
4. The chart caption "best: 29 seats in 1962" clashes with the page's own "peak"
   vocabulary and is lower-case.
5. The two strip headings ("Where this party sits today", "Who they ride with") are
   the user's words-to-improve; Max additionally flags "sits today" as an honesty
   over-claim.
6. The "Parliament (Jun 2024)" strength line is dead text; it should link to the
   parliament election page.
7. The strongholds list is "too much text bunched up".

### 0.2 Verified facts (load-bearing; confirmed live, not assumed)

- **Wiki box = runtime base-less string.** `frontend/src/routes/Party.svelte` L633 renders
  `<img src="/brands/wikipedia.svg">`. Deploy base is `/yen-gov/`. The image resolves to
  `https://miztiik.github.io/brands/wikipedia.svg` -> **404** (`naturalWidth === 0`); the
  same asset at `https://miztiik.github.io/yen-gov/brands/wikipedia.svg` -> **200**. The
  asset EXISTS at `frontend/public/brands/wikipedia.svg` AND `frontend/public/icons/wikipedia.svg`.
- **Fonts are NOT broken (verified).** The deployed page requested
  `/yen-gov/fonts/inter-latin.woff2` -> 200 and `/yen-gov/fonts/outfit-latin.woff2` -> 200
  (`document.fonts`: Inter + Outfit both `loaded`). Vite **rewrites absolute asset URLs in
  CSS (`@font-face url("/fonts/..")` in `src/app.css`) and in `index.html`
  (`<link rel=preload href="/fonts/..">`) with the base at build time.** Do NOT "fix" those -
  they are already correct.
- **The true violation class is runtime asset strings in `.svelte`/`.ts`.** Vite does NOT
  rewrite string literals inside Svelte templates / TS, so a base-less `src="/..."` there
  breaks under the deploy base. A repo-wide grep for non-comment, non-test runtime base-less
  `src="/..."` returns exactly ONE live hit: the wiki logo. That is the only live instance;
  the seam + guard exist to stop the next one.
- **The base seam is fragmented.** `import.meta.env.BASE_URL` is read independently in
  `lib/paths.ts` (`DATA_BASE`, `SHARE_BASE`), `lib/links.ts` (`BASE` + `withBase`),
  `lib/url.ts` (`BASE` + a DUPLICATE `withBase`), `lib/boundaries/symbol-asset.ts`
  (`symbolAssetUrl`), and `lib/PartySymbolGlyph.svelte` (`glyphUrlFor`). `paths.ts` already
  documents the intent: "keep this string out of call sites so a future move (custom domain,
  CDN, S3 origin) is a one-line change here." This is the philosophical home of the seam.
- **The `link.nationalElection(event_id)` builder already exists** (`lib/links.ts`,
  `/t/elections/<event>`), and the current-strength view-model's `ParliamentLatest` already
  carries `event_id` (e.g. `general-2024`). So Row G needs no data/view-model change.
- **Enforcement precedent to mirror:** `frontend/src/contracts/in-app-hrefs-use-base.test.ts`
  walks `frontend/src`, regex-matches base-less `href` literals, skips comments + `.test.ts`
  + the self file. Row A's new contract test copies this shape for asset `src`.

### 0.3 Hard-coded scope (in / out)

IN scope (this plan): the 7 rows below, all on `/parties/<slug>` + the frontend base seam.

OUT of scope (do NOT silently expand - STOP-AND-SURFACE if tempted):
- Re-shaping the "23 of 31 states" denominator or the coverage-vs-result wording (Max flagged;
  **Hans authority**, separate data-shape PR).
- Linking the State-Assembly "Last contested" year (needs a `(state_code, event_id)` pair the
  view-model does not carry; Row G covers ONLY the Parliament line per the user's explicit ask).
- Strongholds "still holds / win-margin / streak" enrichments from Citizen's wishlist that need
  NEW mart columns (data widening is a follow-on). Strike-rate (= wins / contested) IS in scope for
  Row E because both fields are already on the row - no mart change needed.
- Any change to provenance DATA (Holy Law #9): Row C is presentation-only; every publisher that
  renders today MUST still render + stay clickable.

### 0.4 ESCALATE triggers (stop and ask)

- Row A consolidation would change the *resolved* deploy-base value or break dev (`/`) vs prod
  (`/yen-gov/`) parity -> STOP. The seam is a pure consolidation of the existing
  `import.meta.env.BASE_URL` contract; it must not introduce a hardcoded host literal (that
  would break dev and violate Holy Law #6).
- Row C would drop or de-link any publisher currently shown (Holy Law #9) -> STOP.
- Row F headings are DECIDED by the user (2026-06-17): "{party} latest scorecard" +
  "Who {party} team up with". No open decision remains; the ranked lists in Row F are retained as
  rationale only. (If a grammar-possessive variant is wanted, that is a trivial confirm, not a
  blocker.)

### 0.5 Strategy + persona ruling that set it

- **Tidy-First split (Fowler/Gregor):** Row A is structural (consolidate the seam + add the
  guard + the one base-correctness fix the guard forces on the wiki `src`). Row B is the
  behavioural wiki UX change (drop text + tooltip). They touch the same lines, so A lands first
  and B re-touches with the seam in place - structural before behavioural, never mixed in one PR.
- **Jony verdicts (UX authority):** sources -> page-foot mapped sentence (P2); "best:" -> trophy
  glyph, drop the word (P3); strongholds -> two-line hierarchy + top-5 disclosure, extracted into
  one `StrongholdList.svelte` (P1).
- **Citizen + Max (copy):** headings move off "sits today"/"ride with"; honesty (Max) + warmth
  (Citizen) both satisfied; ranked candidate sets in Row F.
- **The "config file" the user asked for** is a single TS config module that owns base
  resolution (reading the one existing env knob `import.meta.env.BASE_URL`, set from `BASE_URL`
  in the deploy workflow). A committed JSON with a hardcoded `/yen-gov/` host is REJECTED: it
  would break dev (base `/`) and hardcode an environment value (Holy Law #6). Optionally the
  prod base path may live as ONE human-edited knob consumed by `vite.config.ts` to set `base`;
  runtime continues to read it via `import.meta.env.BASE_URL` through the seam. Gregor owns the
  exact placement at execution time.

### 0.6 User refinements applied (2026-06-17)

After the first plan draft + the persona consult, the user reviewed and ruled:

- **Row F sits-today heading:** "Their latest scorecard" -> **"{party} latest scorecard"** (drop the
  3rd-person "their"; name the party).
- **Row F alliance heading:** **"Who {party} team up with"** (approved).
- **Row D "best:":** NO emoji. REUSE the trophy the app already ships (the gold Lucide trophy in
  `MarginHistogram.svelte`), do not mint a new one.
- **Row C sources:** approved as drafted (Jony P2 page-foot sentence).
- **Row E strongholds:** approved, PLUS add a **strike-rate** per stronghold, **colour-code** it by
  range, and **sort best-to-least by strike-rate**.
- Rows A, B, G: unchanged from the draft.

---

## Section 1 - Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| A | CDN/base config seam (`assetUrl`) + consolidate readers + contract test (forces wiki `src` base-fix) | [ ] PENDING | - | M |
| B | Wiki logo: drop visible "Wikipedia" text, keep logo image + tooltip | [ ] PENDING | - | S |
| C | Sources: replace 5 per-card lines + orphan footer with ONE page-foot mapped sentence (Jony P2) | [ ] PENDING | - | M |
| D | "best:" caption -> REUSE the existing trophy glyph + "N seats in YYYY" (Jony P3; resolves Max "best" ambiguity) | [ ] PENDING | - | S |
| E | Strongholds: `StrongholdList.svelte` two-line hierarchy + colour-coded strike-rate badge + strike-rate sort, top-5 + show-all | [ ] PENDING | - | M |
| F | Headings (user-decided): "{party} latest scorecard" + "Who {party} team up with" | [ ] PENDING | - | S |
| G | Parliament strength-line date -> `link.nationalElection(event_id)` link | [ ] PENDING | - | S |

Phase / dependency: **A first** (foundational seam + guard). **B depends on A** (uses the seam).
**C, D, E, F, G are independent** of A and of each other (none add base-less asset strings) and
may ship in any order / in parallel after A is in flight.

---

## Section 2 - Per-row spec

### Row A - CDN/base config seam + contract guard

**Goal.** One config seam every frontend module reads for the deploy base / asset URLs, so the
wiki-style 404 cannot recur. Consolidation of the EXISTING `import.meta.env.BASE_URL` contract -
not a new runtime design.

**Scope.**
1. Add a single config module (recommend `frontend/src/lib/config/cdn.ts`, or extend
   `lib/paths.ts` - Gregor's call) exposing: `CDN_BASE` (= `import.meta.env.BASE_URL`),
   `assetUrl(path: string): string` (base-prefix a `public/` asset path, collapsing the double
   slash), and re-export/own `withBase`, `DATA_BASE`, `SHARE_BASE`. Document that GitHub Pages
   is the only CDN and the base is env-driven (one knob).
2. Collapse the DUPLICATE `withBase` (currently in both `links.ts` and `url.ts`) to one
   definition; the other re-exports it. Point `symbolAssetUrl` + `glyphUrlFor` + `DATA_BASE` +
   `SHARE_BASE` at the seam (behaviour-preserving).
3. Route the wiki logo `src` (Party.svelte L633) through `assetUrl("/brands/wikipedia.svg")` -
   the ONE base-correctness fix the new guard forces. (Leave the text/tooltip to Row B.)
4. Add `frontend/src/contracts/cdn-assets-use-seam.test.ts` mirroring
   `in-app-hrefs-use-base.test.ts`: walk `frontend/src`, flag runtime base-less asset strings
   (`src="/..."`, `src={"/..."}`, `.src = "/..."`) in `.svelte`/`.ts`, skipping comment lines,
   `.test.ts`/`.spec.ts`, and the self file. CSS `url()` and `index.html` are out of the walk
   (Vite rewrites those - do not flag them).

**Files.** `lib/config/cdn.ts` (new) or `lib/paths.ts`; `lib/links.ts`; `lib/url.ts`;
`lib/boundaries/symbol-asset.ts`; `lib/PartySymbolGlyph.svelte`; `routes/Party.svelte` (L633);
`contracts/cdn-assets-use-seam.test.ts` (new); update existing tests that pin `withBase`/
`symbolAssetUrl`/`glyphUrlFor` shape if the import path moves.

**Acceptance gates.** `bun run test` green (incl. existing `paths.test.ts`, `links` tests,
`symbol-asset.test.ts`, `PartySymbolGlyph.test.ts`); `bun run build` clean; `tsc` clean.

**ONE oracle.** The new contract test goes **RED** when a base-less `src="/x.svg"` is planted in
any `.svelte`/`.ts` source and **GREEN** once it is routed through `assetUrl`; AND on the deployed
build the wiki logo loads (`naturalWidth > 0`) - verify in the integrated browser per CLAUDE.md
section 13.

### Row B - Wiki logo presentation (drop text, keep image + tooltip)

**Goal (user verbatim intent).** Now that the logo works, drop the visible word "Wikipedia"; the
logo image alone with a tooltip is enough.

**Scope.** In the header meta-strip (`Party.svelte`, `[data-testid="party-meta-wikipedia"]`
anchor): remove the `<span>Wikipedia</span>` text node; keep the `<img>` (via the Row-A seam) and
move the label to a `title` on the image plus an `aria-label`/`title` on the wrapping `<a>` so the
link target is still self-describing on hover (English-only chrome; a11y is a project Non-Goal but
`title` is free). Keep the external-link `target`/`rel`.

**Files.** `routes/Party.svelte` (meta-strip wiki block, ~L625-640).

**Acceptance gates.** `bun run test` green; browser smoke (CLAUDE.md section 13) shows the logo
with no adjacent "Wikipedia" text and a hover tooltip.

**ONE oracle.** Component/DOM test: the wiki anchor renders an `<img title="Wikipedia">` (or
anchor `title`/`aria-label` === "Wikipedia") and the rendered text content contains NO "Wikipedia"
string.

### Row C - Sources: one page-foot mapped sentence (Jony P2)

**Goal.** Kill the 4x "Source: ECI" + 1x "Source: Wikipedia" repetition and the orphaned "About
this page" footer; state each publisher once, preserve the ECI-vs-Wikipedia (official vs
community) distinction, keep names clickable (Holy Law #9).

**Scope.** Remove the 5 inline `<SourceList>` mounts on the party page (current_strength,
alliance_context, parliament, state_assembly, strongholds) and the standalone "About this page"
link. Add ONE page-foot block (new small `PartyProvenanceFooter.svelte`, or an inline foot
section) rendering a mapped sentence built from the per-card pill data already on
`view_model.provenance`:
`Seats, vote-share and strongholds: <ECI link>. Alliance line-ups: <Wikipedia link>.` followed by
the `About this page >` link. Publisher names stay anchored to their URLs. The mapping is derived
(which families resolved to which publisher), not hardcoded, so a party whose alliance data is
ECI-sourced reads correctly. `SourceList.svelte` itself stays (still used elsewhere); only the
party-page mounts move.

**Files.** `routes/Party.svelte` (remove 5 mounts + footer link; mount the foot block);
`lib/parties/PartyProvenanceFooter.svelte` (new) + its test; reuse `view_model.provenance`.

**Acceptance gates.** `bun run test` green; browser smoke shows ONE provenance block at the foot,
ECI + Wikipedia both present + clickable, no per-card "Source:" lines.

**ONE oracle.** Contract/component test: the rendered party page has exactly ONE provenance foot
block, zero per-card `SourceList` mounts, and BOTH the ECI and Wikipedia publisher URLs present as
anchors (Holy Law #9 preserved).

### Row D - "best:" -> REUSE the existing trophy glyph (Jony P3; user-confirmed)

**Goal.** Replace `best: N seats in YYYY` (lower-case, vocab clash with "peak", Max-flagged
seats-vs-vote-share ambiguity) with a trophy glyph + the metric-named figure. **NO emoji** - a real
SVG glyph.

**Reuse, do not re-mint (user 2026-06-17).** The app ALREADY ships a trophy: the Lucide trophy
stroke path inline in `frontend/src/lib/MarginHistogram.svelte` (the gold insight badge on the
state-election margin histogram), `viewBox="0 0 24 24"`, `stroke-width 2`, tone `text-amber-600`,
path `d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22M18 2H6v7a6 6 0 0 0 12 0V2Z"`.
Lift that SAME path into the icon registry as `frontend/public/icons/trophy.svg` so the registry +
the new caption (and optionally MarginHistogram) share ONE source. Do NOT introduce a different
trophy/medal.

**Scope.** Render the registry trophy via `<TopicIcon name="trophy" cls="w-3.5 h-3.5 ..."/>` before
`{peak} seats in {year}` in both chart captions (Party.svelte LS ~L767, VS ~L803). Tone: gold
`text-amber-600` to MATCH the established winner-trophy treatment in MarginHistogram (this overrides
the first draft's slate-500 - the user asked to reuse the existing gold trophy; a trophy is a
"winner" mark, the one sanctioned amber-as-celebration use). Drop the word "best" (resolves Max's
seats-vs-vote-share ambiguity - the figure now names its own metric).

**Files.** `public/icons/trophy.svg` (new, the SAME Lucide path as MarginHistogram);
`public/icons/LICENCES.md` (one row, Lucide ISC); `routes/Party.svelte` (2 captions). Optional DRY:
repoint MarginHistogram's inline trophy at the registry icon - only if it stays a clean lift.

**Acceptance gates.** `bun run test` green (incl. the icon-registry parse/allowlist test that walks
`public/icons/`, and `MarginHistogram` tests if repointed); `bun run build` clean; browser smoke
shows the gold trophy + figure, no "best", no emoji codepoint.

**ONE oracle.** Each chart caption renders the registry trophy glyph (an `<svg>`/`<img>`, not an
emoji char) + text matching `^\d+ seats in \d{4}$` with no literal "best"; `trophy.svg` passes the
icon allowlist parser.

### Row E - Strongholds: `StrongholdList.svelte` + colour-coded strike-rate + strike-rate sort (Jony P1 + Citizen + user)

**Goal.** End "too much text bunched up": hierarchy per row (constituency = hero / tap target;
strike-rate = colour-coded proof; state + recency = quiet context), cap to top-5 with disclosure,
drop the heavy outer box. NOT the per-election dot/square strip (user-vetoed). ADD a colour-coded
strike-rate and sort best-to-least by it (user 2026-06-17).

**Scope.**
1. Extract ONE presentational `lib/parties/StrongholdList.svelte` (props: `rows`,
   `max_visible = 5`) mounted twice in `Party.svelte` (Parliament + State Assembly), replacing the
   two inline `<ul>`s. Row layout: line 1 = constituency `text-sm font-semibold text-slate-800`
   (the `sky-700` link when `s.href` is set, plain bold when the seat is retired under current
   delimitation) + a right-flush **strike-rate badge**; line 2 = `State . last won YYYY` in
   `text-xs text-slate-500`. Top-5 per body + a "Show all N" disclosure (mirrors `SourceList`'s
   "+N more"). Replace the `border border-slate-200 rounded bg-white` box with bare
   `divide-y divide-slate-100`. Keep the click-through affordance.
2. **Strike-rate** = `Math.round(wins / contested * 100)` (psephology "strike rate"; both fields
   already on `PartyStronghold` - NO mart change). Render as a compact `tabular-nums` badge, e.g.
   `3/4 . 75%`, colour-coded by tier - MIRROR the sanctioned tier palette in
   `DataCompleteness.svelte::statusBadgeClass` (`bg-X-100 text-X-900 border-X-300`):
   - `>= 80%` -> emerald (a true fortress)
   - `50-79%` -> amber (a lean)
   - `< 50%`  -> rose (shaky - still top-N by wins but not a fortress)
   Thresholds/hues are Jony-tunable; the 3-tier emerald/amber/rose semantics are the established
   pattern (do NOT hijack the choropleth `--ramp-*` hues - those are direction-of-value, a
   different system per `colors/palettes.ts`).
3. **Sort best-to-least by strike-rate** (user): change the view-model sort in `party-detail.ts`
   (~L519, currently `wins DESC, then win-rate DESC`) to **`strike-rate DESC, then wins DESC, then
   last_won_year DESC, then entity_id`**. NOTE (flag for Jony/Max, do not silently resolve): pure
   strike-rate-primary floats a thin `1/1` (100%) above a deep `7/8` (87.5%); the `wins` second key
   keeps `8/8` above `1/1`. If the thin-sample float is unwanted, the mitigation is a
   `contested >= 2` co-weight - decide at implementation; do NOT filter rows out (that narrows what
   shows).

**Files.** `lib/parties/StrongholdList.svelte` (new) + test; `routes/Party.svelte` (replace the two
inline `<ul>` blocks ~L818-905; `formatStrongholdTally` moves into / is reused by the component);
`lib/view-models/party-detail.ts` (sort ~L519) + its sort test (currently pins wins-primary - flip
to strike-rate-primary).

**Acceptance gates.** `bun run test` green; browser smoke on CPI shows two-line rows, colour-coded
strike-rate, strike-rate-descending order, top-5 default + working "Show all", constituency as tap
target.

**ONE oracle.** Component test: given 10 rows, exactly 5 render initially and 10 after toggle; rows
are strike-rate-descending (wins tiebreak); each strike-rate badge carries the tier class matching
its band (`>=80` emerald / `50-79` amber / `<50` rose); the constituency is an `<a>` when `href` is
set.

### Row F - Headings copy ("sits today" + "ride with") - USER-DECIDED

**Decision (user 2026-06-17).** Both headings are settled; no open choice remains.
- Current-strength card heading: **"{party} latest scorecard"** (drops 3rd-person "their"; names
  the party). e.g. `CPI latest scorecard`.
- Alliance card heading: **"Who {party} team up with"**. e.g. `Who CPI team up with`.

`{party}` = the party's short abbreviation (`meta.short`, e.g. "CPI"). Keep the existing
`uppercase tracking-wide text-slate-500` heading treatment (renders "CPI LATEST SCORECARD" /
"WHO CPI TEAM UP WITH"). A grammatical possessive ("CPI's latest scorecard") is an acceptable
variant - confirm at implementation; the user's literal form has no apostrophe and Indian-English
collective-plural "team up" is intentional.

**Scope.** The two strip components do NOT currently receive the party name, so add a `party_label`
prop to each and pass `meta.short` from `Party.svelte`:
- `lib/parties/PartyCurrentStrength.svelte` (~L109 heading) -> `{party_label} latest scorecard`.
- `lib/parties/PartyAllianceContext.svelte` (~L146 heading) -> `Who {party_label} team up with`.
- `routes/Party.svelte`: pass `party_label={meta.short}` to both mounts.
Update the two `.test.ts` files that pin the old literal headings.

**Files.** `PartyCurrentStrength.svelte`, `PartyAllianceContext.svelte`, `routes/Party.svelte`
(2 prop additions), the two `.test.ts`.

**Acceptance gates.** `bun run test` green; browser smoke shows the party-named headings; neither
renders "sits today" or "ride with".

**ONE oracle.** Given a fixture party with `short = "CPI"`, `PartyCurrentStrength` renders a heading
containing "CPI latest scorecard" and `PartyAllianceContext` renders "Who CPI team up with"; the old
literals "Where this party sits today" / "Who they ride with" are absent.

**Rationale retained (the ranked candidate sets that informed the decision - superseded by the
decision above, kept for audit):**

_Where this party sits today_ (warmth x honesty): 1. "How they're doing now" - 2. "Where they stand
today" - 3. **"Their latest scorecard"** [chosen base, party-named] - 4. "Latest election scorecard"
- 5. "How strong are they now" - 6. "Where they stand after the latest vote" - 7. "Their current
strength" - 8. "How big are they today" - 9. "As last elected" (most honest, cold) - 10. "Seats they
hold now" (AVOID - Max over-claim).

_Who they ride with_: 1. **"Who they team up with"** [chosen base, party-named] - 2. "Who they join
hands with" - 3. "Their election alliances" - 4. "Recent election alliances" (most precise) - 5.
"Who they've allied with at elections" - 6. "Who's in their camp" - 7. "Who they contest alongside"
- 8. "Pre-poll alliances (last decade)".

### Row G - Parliament strength-line date -> election link

**Goal.** Make the "Parliament (Jun 2024)" date a link to the parliament election page.

**Scope.** In `PartyCurrentStrength.svelte` (parliament line, ~L120-126) wrap the month/date in an
`<a href={link.nationalElection(parliament.event_id)}>` (the view-model already carries
`event_id`, e.g. `general-2024`; the builder already exists). Use the standard in-app link styling
(`sky-700 hover:underline`). State-Assembly date is NOT linked (out of scope, 0.3).

**Files.** `lib/parties/PartyCurrentStrength.svelte`; import `link` from `lib/links`; its `.test.ts`.

**Acceptance gates.** `bun run test` green; browser smoke - clicking the date lands on
`/t/elections/general-2024`.

**ONE oracle.** Component test: the parliament line renders an `<a>` whose `href` ===
`link.nationalElection(parliament.event_id)` for the fixture (e.g. `/yen-gov/t/elections/general-2024`
under base, `/t/elections/general-2024` in dev).

---

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

---

## See also

- [CLAUDE.md](../CLAUDE.md) - authority table (section 0a), correction levels (section 6), anti-patterns (section 10), Holy Law #9 provenance.
- [docs/concepts/party-page-coverage.md](../docs/concepts/party-page-coverage.md) - the election-night-not-live-tally methodology fact behind Row F.
- [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) - colour reservation behind Row D.
- [frontend/src/contracts/in-app-hrefs-use-base.test.ts](../frontend/src/contracts/in-app-hrefs-use-base.test.ts) - the enforcement pattern Row A mirrors.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - the PR lifecycle the EXECUTION BLOCK references.
