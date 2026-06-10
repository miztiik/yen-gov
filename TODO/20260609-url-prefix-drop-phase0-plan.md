# URL Prefix Drop — Phase 0 execution plan (ADR-0037 Phases 2-4)

**Last Updated**: 2026-06-10
**Status**: ACTIVE PHASES (PR-P1 / PR-P2 / PR-P3) **SHIPPED** in PRs [#867](https://github.com/miztiik/yen-gov/pull/867) + [#868](https://github.com/miztiik/yen-gov/pull/868) + [#869](https://github.com/miztiik/yen-gov/pull/869). PR-P4 (redirect-tombstone delete) DEFERRED indefinitely; user-triggered after one-cycle soak + zero redirect-hit telemetry. **Grammar A is the live URL grammar; Grammar B `/s/<state>/...` URLs redirect via `RedirectLegacyUrl.svelte`.**
**Level**: 3 (cross-cutting; 4 PRs; URL grammar = citizen contract).
**Strategy**: execute ADR-0037 Phases 2-4 (already-locked decision; not a new debate). Drop the `/s/` prefix so every URL reads as bare `/<state>/...`. Prerequisite for the [election experience overhaul plan](20260609-election-experience-overhaul-plan.md).

> This plan is NOT a new design decision. The decision is locked in [ADR-0037](../docs/architecture/frontend/url-grammar.md#adr-0037-url-grammar-drop-india-prefix). Phase 1 of ADR-0037 shipped in PR #173 (2026-05-25): `frontend/src/lib/links.ts` Grammar A builders + 3 Tier-A contract tests, zero call-sites. Phases 2-4 are mechanical execution against an existing contract.

> **Why now:** the election experience overhaul plan would mint 16 new URLs on the legacy `/s/<state>/...` grammar today. Per Gregor + Jony + Fowler unanimous verdict (2026-06-09), dropping `/s/` AFTER those URLs ship would force a second citizen-bookmark migration. Doing Phase 0 first gives the election plan a clean URL surface from day one.

---

## Section 0 — Operating contract

### 0.1 What this plan does

Today the app routes Grammar B (`/s/<state>/...`). ADR-0037 specifies Grammar A (bare `/<state>/...`):

| Surface | Today (Grammar B) | After this plan (Grammar A) |
| --- | --- | --- |
| State hub | `/s/tamil-nadu` | `/tamil-nadu` |
| State topic | `/s/tamil-nadu/t/elections` | `/tamil-nadu/t/elections` |
| State indicator | `/s/tamil-nadu/installed-capacity` | `/tamil-nadu/installed-capacity` |
| AC drill | `/s/tamil-nadu/elections/<event>/ac/167-mylapore` | `/tamil-nadu/elections/<event>/ac/mylapore` (number prefix dropped per ADR-0037 AC-slug section) |
| Party page | `/s/tamil-nadu/party/<slug>` | `/tamil-nadu/party/<slug>` |
| State explore | `/s/tamil-nadu/explore` | `/tamil-nadu/explore` |
| State district | `/s/tamil-nadu/d/chennai` | `/tamil-nadu/chennai` (positional, no `/d/` marker — per ADR-0037 routing.md) |
| Election compare | `/compare/<state>/<event>` | unchanged (Grammar A AC slug shape only) |
| Election lab | `/lab/<state>/<event>` | unchanged |
| Chrome | `/about`, `/t`, `/compare`, `/settings`, `/disclaimer` | unchanged (these never had `/s/`) |

**One operational scope-cut** for THIS plan: the AC slug shape change (`167-mylapore` → `mylapore`) ships with the AC route migration. The district resolver (positional `/<state>/<district>` vs `/s/<state>/d/<district>`) is in ADR-0037 Phase 2 scope and ships here too.

### 0.2 What this plan does NOT do

- Election URL grammar (16 election-plan PRs handle that).
- Hindi-token scrub, event-id rename, scatter chart, etc. (election plan).
- Any data store changes.
- Any socio-econ component rebuilds. Routes are renamed; component behaviour is preserved.

### 0.3 ESCALATE triggers

The orchestrator stops ONLY at:

1. **A reader-compatibility break.** PR-P2's mechanical caller-migration sweep MUST keep every internal anchor + every test + every doc cross-link working. If a sweep replaces a builder with a Grammar A builder that doesn't yet exist on `links.ts`, STOP-AND-SURFACE.
2. **The 42-test PR #172 Grammar B contract.** PR-P3 deletes it. If a test fails for reasons OTHER than "the contract is now stale" (e.g. a real regression in the Svelte component itself), STOP-AND-SURFACE — don't blindly delete a green test that's catching a real bug.
3. **`url.ts` has consumers outside `frontend/src/`.** If `tools/` or `docs/` example code imports from `url.ts` (unlikely; CLAUDE.md s4 forbids cross-tree imports), surface before deleting.

### 0.4 Baked facts (verified 2026-06-09; do not re-derive)

| Fact | Value |
| --- | --- |
| ADR | [ADR-0037 url-grammar-drop-india-prefix](../docs/architecture/frontend/url-grammar.md#adr-0037-url-grammar-drop-india-prefix) (LOCKED 2026-05-25) |
| Phase 1 shipped | PR #173 — `frontend/src/lib/links.ts` Grammar A builders + 3 Tier-A tests, zero call-sites |
| Grammar A builders | [frontend/src/lib/links.ts](../frontend/src/lib/links.ts) — `links.state(slug)`, `links.stateTopic(slug, topic)`, `links.indicator(slug)`, `links.stateIndicator(state, slug)`, `links.acIndicator(state, ac, slug)`, `links.party(state, slug)`, `links.district(state, slug)`, `links.explore(state)` |
| Grammar B builders (to retire) | [frontend/src/lib/url.ts](../frontend/src/lib/url.ts) — `url.state(slug)`, `url.stateTopic(...)`, `url.ac(state, ac, event?)`, `url.acByNo(state, eciNo, event?)`, `url.stateElection(state, event)`, `url.party(state, slug)`, `url.district(state, slug)` |
| Live route table | [frontend/src/main.ts](../frontend/src/main.ts) lines 58-160 — 20+ `/s/:state/...` route entries |
| 42-test Grammar B contract | [frontend/src/lib/links.test.ts](../frontend/src/lib/links.test.ts) (per ADR-0037 Phase 4 spec — "delete `/s/*` routes, `url.ts` legacy builders, PR #172's 42-test contract") |
| Reserved-paths invariant | [frontend/src/contracts/url-namespace-disjointness.test.ts](../frontend/src/contracts/url-namespace-disjointness.test.ts) — already asserts 3-way disjointness; Phase 2 extends to 4-way (adds `acSlugsAcrossAllStates`); Phase 3 extends to 5-way (adds `urlIndicatorSlugs`) |
| Full-name state slug invariant | [frontend/src/contracts/state-slugs-full-name.test.ts](../frontend/src/contracts/state-slugs-full-name.test.ts) — ALREADY GREEN |
| `RedirectLegacyUrl.svelte` | DOES NOT EXIST today (Fowler v3's claim was wrong; verified by `git grep`). ADR-0037 Phase 3 spec LANDS this component — PR-P1 of this plan. |
| Doc | [frontend/src/lib/links.ts](../frontend/src/lib/links.ts) module docstring lines 200-210 — names `s`, `ac`, `party` as legacy redirect anchors "through Phase 4b" |

### 0.5 Per-PR workflow

Same as election plan section 0.6:

1. Branch off `main`.
2. Implement scope. Tests ship with the row.
3. Local gates GREEN (pytest if backend touched, vitest, svelte-check, integrated-browser smoke per CLAUDE.md s13 for any route change).
4. Commit + push + `gh pr merge --squash --admin --delete-branch`. Don't wait for remote CI.
5. Pull main. Start next row.

### 0.6 Closure

Plan complete when PR-P3 ships (Grammar B fully retired except for `RedirectLegacyUrl.svelte`). PR-P4 (delete the redirect) is deferred to a follow-up release after one-cycle soak + zero redirect-hit telemetry (user-triggered, not date-gated).

---

## Section 1 — Status Reckoner

| Row | Title | Depends on | Status | PR | Effort |
| --- | --- | --- | --- | --- | --- |
| PR-P1 | Add Grammar A routes alongside `/s/*` in `main.ts` + land `RedirectLegacyUrl.svelte` for `/s/<state>*` -> `/<state>*` 301. Both grammars work simultaneously. | none | [x] MERGED + PUSHED | [#867](https://github.com/miztiik/yen-gov/pull/867) | M |
| PR-P2 | Mechanical caller-migration sweep: replace `url.*(...)` Grammar B builders with `links.*(...)` Grammar A builders across `frontend/src/**`. AC slug shape change (`167-mylapore` -> `mylapore`) ships here. AC namespace + indicator slugs join the disjointness contract. | PR-P1 | [x] MERGED + PUSHED | [#868](https://github.com/miztiik/yen-gov/pull/868) | L |
| PR-P3 | Delete Grammar B from `main.ts` routes + delete `url.ts` legacy builders + delete the 42-test PR #172 Grammar B contract + reverse the dependency in any test that still references `/s/<state>`. `RedirectLegacyUrl.svelte` STAYS for one release. | PR-P2 | [x] MERGED + PUSHED | [#869](https://github.com/miztiik/yen-gov/pull/869) | M |
| PR-P4 | Delete `RedirectLegacyUrl.svelte` after one-release soak + zero redirect-hit telemetry. **User-triggered, not date-gated.** | PR-P3 + soak | [ ] PENDING (deferred) | — | XS |

**Effort key**: XS = <1h • S = 1-3h • M = half-day • L = full-day.

**Critical path:** PR-P1 -> PR-P2 -> PR-P3. PR-P4 deferred indefinitely until user trigger. **Total active work: 3 sequential PRs.**

---

## Section 2 — Per-row specifications

### PR-P1 — Add Grammar A routes + `RedirectLegacyUrl.svelte`

**Scope.** Both Grammar A AND Grammar B routes work simultaneously after this PR. Citizens visiting `/s/tamil-nadu` get `replaceState`-redirected to `/tamil-nadu`. Citizens visiting `/tamil-nadu` directly get rendered.

**Files:**
- NEW `frontend/src/routes/RedirectLegacyUrl.svelte` — client-side route handler. On mount: parse `window.location.pathname`; rewrite `/s/<state>/...` to `/<state>/...`; `history.replaceState(null, '', newPath)` + dispatch to the matching Grammar A route.
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — add Grammar A route entries ABOVE the existing `/s/*` entries (route order matters):
  - `pattern: "/:state", component: StateOverview, crumbs(p) { ... }`
  - `pattern: "/:state/t/:topic", component: StateTopic, ...`
  - `pattern: "/:state/elections/:event", component: StateElection, ...`
  - `pattern: "/:state/elections/:event/ac/:ac", component: Constituency, ...`
  - `pattern: "/:state/elections/:event/pc/:pc", component: Constituency, ...` (if PC route exists)
  - `pattern: "/:state/party/:party", component: Party, ...`
  - `pattern: "/:state/explore", component: Explore, ...`
  - `pattern: "/:state/:district", component: District, ...` (positional — depth-2 dispatch via district registry; per ADR-0037 routing.md)
  - `pattern: "/:state/:indicator", component: IndicatorPage, ...` (if shipped; depth-2 dispatch via indicator registry — fallback to district resolver if not an indicator)
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — add `pattern: "/s/:state/*", component: RedirectLegacyUrl` as the catch-all for Grammar B. MUST be LAST in route order (so specific routes match first).
- NEW `frontend/src/lib/RedirectLegacyUrl.test.ts` — vitest: 5 known Grammar B URLs (`/s/tamil-nadu`, `/s/tamil-nadu/t/elections`, `/s/karnataka/elections/AcGenMay2023`, `/s/chhattisgarh/elections/<event>/ac/1-bastar`, `/s/karnataka/party/inc-742`) each rewrite to the Grammar A equivalent.
- NEW `frontend/e2e/url-prefix-drop.spec.ts` — Playwright: navigate `/s/tamil-nadu` -> assert URL bar becomes `/tamil-nadu` AND `StateOverview` renders. Navigate `/tamil-nadu` directly -> assert same rendering, no redirect.

**Acceptance gates:**

- [ ] G1 — vitest GREEN on `RedirectLegacyUrl.test.ts`; full suite GREEN.
- [ ] G2 — svelte-check + tsc CLEAN.
- [ ] G3 — Playwright `url-prefix-drop.spec.ts` GREEN.
- [ ] G4 — integrated browser smoke (CLAUDE.md s13): open `/s/tamil-nadu/t/elections` in browser; confirm URL bar flips to `/tamil-nadu/t/elections`; confirm page renders identically. Screenshot.
- [ ] G5 — Grammar B URLs still render (via redirect); Grammar A URLs render directly. Both work.

**Oracle:** `/s/tamil-nadu` -> URL becomes `/tamil-nadu` AND `StateOverview` renders. One spec proves the redirect + the Grammar A route both work.

**Escalation:** if the Svelte router doesn't support catch-all wildcards (`/s/:state/*`), STOP-AND-SURFACE — Fowler likely needs to verify the wildcard syntax against the project's router (`frontend/src/lib/router.svelte.ts`).

---

### PR-P2 — Mechanical caller-migration sweep + AC slug shape change

**Scope.** Sweep all internal anchors + tests + docs from Grammar B builders (`url.*`) to Grammar A builders (`links.*`). AC slug shape change (`167-mylapore` -> `mylapore`) ships in the same sweep. AC namespace + indicator slugs join the disjointness contract (extends Phase 1's 3-way to 5-way).

**Files (grep-driven; executor runs the grep):**
- `git grep -E "url\.(state|stateTopic|district|ac|acByNo|stateElection|party|explore)\(" frontend/src/` — every match becomes a `links.*` call site.
- All `<a href={url.state(...)}>` -> `<a href={links.state(...)}>`.
- Tests + Playwright specs that hard-code `/s/tamil-nadu/...` get rewritten to `/tamil-nadu/...`.
- Docs that cite Grammar B URLs (`docs/architecture/frontend/indicators.md`, etc.) get updated.
- AC slug shape change: anywhere a constituency URL is built, the slug becomes name-only (no `167-` prefix). Where the ECI code is needed for collision disambiguation (rare), the `<name>-2` fallback shape kicks in per ADR-0037 AC-slug rule.
- EXTEND [frontend/src/contracts/url-namespace-disjointness.test.ts](../frontend/src/contracts/url-namespace-disjointness.test.ts) to assert 5-way disjointness:
  - `urlIndicatorSlugs` (from `datasets/taxonomy/indicators.parquet` `url_slug` field — load it; if the field doesn't exist yet, this is Phase 3 of ADR-0037 territory; if it ISN'T live yet, ship the 4-way disjointness here and add the 5th in a follow-up)
  - `stateSlugs` (existing)
  - `topicSlugs` (existing)
  - `acSlugsAcrossAllStates` (~4,123 slugs) — NEW; loaded from `datasets/data/entities/electoral.csv` AC rows
  - `RESERVED` (existing)

**Acceptance gates:**

- [ ] G1 — `git grep -E "url\.(state|stateTopic|district|ac|acByNo|stateElection|party|explore)\(" frontend/src/` returns ZERO matches (sweep complete).
- [ ] G2 — vitest GREEN; svelte-check + tsc CLEAN.
- [ ] G3 — extended `url-namespace-disjointness.test.ts` GREEN (4-way OR 5-way depending on whether `url_slug` is available).
- [ ] G4 — Playwright: every existing E2E spec passes (URLs flipped from `/s/<state>` to `/<state>` where applicable).
- [ ] G5 — integrated browser smoke: navigate ALL the canonical citizen paths (Home -> state -> state topic -> AC drill -> party page); confirm each renders Grammar A URL; confirm breadcrumb shows correct cascade.

**Oracle:** grep gate G1 — zero remaining `url.*(...)` Grammar B builder call-sites.

**Escalation:** if the `url_slug` field isn't yet on `datasets/taxonomy/indicators.parquet`, ship the 4-way disjointness here and document the 5th as a follow-up gate. Do NOT block on the missing field.

---

### PR-P3 — Delete Grammar B routes + `url.ts` builders + 42-test contract

**Scope.** Final delete. `RedirectLegacyUrl.svelte` STAYS for one release; everything else Grammar-B-shaped gets removed.

**Files (DELETE):**
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — remove every `/s/:state/...` route entry. KEEP the `pattern: "/s/:state/*", component: RedirectLegacyUrl` entry.
- DELETE [frontend/src/lib/url.ts](../frontend/src/lib/url.ts) Grammar B builders (`state`, `stateTopic`, `ac`, `acByNo`, `stateElection`, `party`, `district`). If `url.ts` has only these + the legacy redirect-anchor exports, DELETE the file. If it has other live exports, narrow the file.
- DELETE [frontend/src/lib/links.test.ts](../frontend/src/lib/links.test.ts) Phase-4b legacy-redirect-anchor test (`it("retains the Phase-4b legacy redirect anchors (s, ac, party)", ...)`). The Phase 4b mention is the soak window; we're past it for the route table.
- DELETE the 42-test PR #172 Grammar B contract (if it's a separate file; if it lives INSIDE `links.test.ts`, remove those specific tests).
- EDIT [docs/architecture/frontend/routing.md](../docs/architecture/frontend/routing.md) — remove "Grammar A end-state documented but not wired" disclaimer. ADR-0037 Phase 1-3 status update.
- EDIT [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) — Phase 4 status update in ADR-0037.

**Acceptance gates:**

- [ ] G1 — `git grep "/s/:state" frontend/src/main.ts` returns ONLY the `RedirectLegacyUrl` entry.
- [ ] G2 — vitest GREEN; svelte-check + tsc CLEAN; full suite GREEN.
- [ ] G3 — Playwright: every E2E spec passes; navigate one legacy Grammar B URL `/s/tamil-nadu/t/elections` -> assert redirect to `/tamil-nadu/t/elections`.
- [ ] G4 — bundle size: assert post-PR bundle is SMALLER than pre-PR (`du -b frontend/dist/`).
- [ ] G5 — integrated browser smoke: visit `/s/karnataka/t/elections` (legacy) AND `/karnataka/t/elections` (current); confirm both land on the same rendered page with the URL bar showing `/karnataka/t/elections`.

**Oracle:** `git grep "/s/:state" frontend/src/main.ts | grep -v RedirectLegacyUrl` returns ZERO matches AND a legacy Grammar B URL still routes correctly via the redirect.

**Escalation:** Trigger #2 from section 0.3 — if a 42-test failure is catching a real Svelte component bug rather than just a stale Grammar B assertion, STOP-AND-SURFACE.

---

### PR-P4 — Delete `RedirectLegacyUrl.svelte` (deferred, user-triggered)

**Scope.** Tombstone. After PR-P3 ships + one-cycle soak + zero redirect-hit telemetry, delete the redirect.

**Files:**
- DELETE `frontend/src/routes/RedirectLegacyUrl.svelte`.
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — remove the `/s/:state/*` redirect route entry.
- DELETE `frontend/src/lib/RedirectLegacyUrl.test.ts`.

**Acceptance gates:**

- [ ] G1 — vitest GREEN; svelte-check + tsc CLEAN.
- [ ] G2 — `git grep "/s/:state" frontend/src/main.ts` returns ZERO matches.
- [ ] G3 — bundle size SMALLER again.

**Oracle:** zero importers of `RedirectLegacyUrl.svelte`.

**Escalation:** if any external citation is known to still hit `/s/<state>` (Twitter, press, citizen bookmark), DEFER. User decides.

---

## Section 3 — Final acceptance (whole plan)

**The migration is COMPLETE when PR-P3 ships.** The acceptance walkthrough:

1. Navigate `/tamil-nadu`. Confirm state hub renders. URL bar shows `/tamil-nadu`.
2. Navigate `/tamil-nadu/t/elections`. Confirm state-elections topic page renders.
3. Navigate `/tamil-nadu/installed-capacity`. Confirm indicator renders.
4. Navigate `/s/tamil-nadu` (legacy). Confirm URL bar flips to `/tamil-nadu`; same rendering.
5. Navigate `/s/tamil-nadu/t/elections` (legacy). Confirm URL bar flips; same rendering.
6. Verify breadcrumb on every page renders Grammar A URLs in its `<a href>`s.
7. `git grep -E "url\.(state|stateTopic|district|ac|acByNo|stateElection|party|explore)\(" frontend/src/` returns ZERO.
8. `git grep "/s/:state" frontend/src/main.ts | grep -v RedirectLegacyUrl` returns ZERO.

After PR-P3 ships, the election experience overhaul plan (the dependent plan) starts on a clean Grammar A surface.

---

## Execution contract (autonomous; follow blindly, do not re-plan)

Same as election plan's execution contract:

1. Each PR row dispatched as a stateless `runSubagent` brief with scope + files + gates + oracle.
2. Branch off `main`. Test locally. Commit. Push. `gh pr merge --squash --admin --delete-branch`. Don't wait for remote CI. Pull main. Next row.
3. Use Playwright + integrated browser (CLAUDE.md s13) for every frontend route change.
4. Sequential within this plan (P1 -> P2 -> P3); PR-P4 deferred indefinitely.
5. Stop only at section 0.3 ESCALATE triggers OR an audit depth >3.
6. Closure: archive per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).

---

## See also

- [ADR-0037 — drop /india/ prefix](../docs/architecture/frontend/url-grammar.md#adr-0037-url-grammar-drop-india-prefix) — the binding decision THIS plan executes.
- [docs/architecture/frontend/routing.md](../docs/architecture/frontend/routing.md) — operational route resolver.
- [frontend/src/lib/links.ts](../frontend/src/lib/links.ts) — Grammar A builders (Phase 1 of ADR-0037, shipped).
- [frontend/src/lib/url.ts](../frontend/src/lib/url.ts) — Grammar B builders (to retire in PR-P3).
- [TODO/20260609-election-experience-overhaul-plan.md](20260609-election-experience-overhaul-plan.md) — the DEPENDENT plan; ships AFTER PR-P3.
- [CLAUDE.md](../CLAUDE.md) — engineering contract; authority table; Holy Laws.
