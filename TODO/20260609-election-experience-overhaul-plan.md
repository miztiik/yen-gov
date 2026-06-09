# Election Experience Overhaul — execution plan

**Last Updated**: 2026-06-09
**Level**: 4 (cross-cutting; 16 PRs in 5 waves; URL grammar = citizen contract; English-only nouns).
**Strategy**: rip-and-replace per user mandate ("we can break the app temporarily to achieve our goals"). Atomic per-row PRs; redirects only where citizen consumers are real; ephemeral state where they are not.

> Reference: live walk of [indiavotes.com](https://www.indiavotes.com/) (national + state + constituency + scatter + compare cascades), on-disk inventory of yen-gov's election surfaces, persona verdicts converged from Jony (UX) + Hans (governance + English nouns) + Fowler (engineering) + Max (chart dimensions).

> User-mandated binding constraints (baked into every row):
>
> 1. **No Hindi tokens** in URLs, page chrome, code identifiers, or event-id literals. Use English (`general-2024`, `assembly-2023`, `general-bye-2024-<state>-<seat>`).
> 2. **Plain old routing.** No query params. No `#` fragments. Pure path cascades under Grammar A (`/<state>/...` after the Phase 0 plan ships).
> 3. **Repurpose** today's state-elections topic page ("horrible page" with bare "List: N/A" badge) and the Home elections rail ("almost useless, hangs without context").
> 4. **Must-feature: scatter chart** (turnout x margin x party-colour x electors-size) on both national + per-state surfaces, with 6 filters.
> 5. **Drop the body-root pages.** No `/parliament/`, no `/assembly/`. Body distinction lives ONLY in the event-slug prefix (`general-` / `assembly-`).
> 6. **Drop the `/pc/` and `/ac/` literals.** The event-slug body prefix already implies constituency type. New URLs are `/<state>/elections/<event>/<constituency-slug>`.
> 7. **Body-tag the compare route.** `/compare/elections/<state>/<from-event>/<to-event>` (disambiguates from socio-econ compare).
> 8. **Ephemeral scenarios.** No `?s=<b64>` URL. No localStorage. Refresh = fresh start. Add persistence only when a real citizen complaint surfaces.
> 9. **No legacy-URL absorber.** Old bookmarks lose work; that is acceptable today.

> **PREREQUISITE: [URL Prefix Drop Phase 0 plan](20260609-url-prefix-drop-phase0-plan.md) must ship PR-P3 before this plan's PR-0 starts.** Phase 0 drops the `/s/` prefix across the whole app (executing ADR-0037 Phases 2-4 — a locked decision, not a new debate). This plan's URLs assume Grammar A (`/<state>/elections/<event>/...`) from day one. Per Gregor + Jony + Fowler unanimous verdict (2026-06-09): minting 16 new election URLs on the legacy `/s/<state>/...` grammar would force a second citizen-bookmark migration when Phase 0 finally lands.

> Authorities per [CLAUDE.md section 0a](../CLAUDE.md): URL grammar + IA + UX = Jony + Citizen; data shape + English nouns + governance framing = Hans + Max; URL-as-contract + write-seam + refactor + PR decomposition = Gregor + Fowler; chart-dimension design = Max + Jony. **User approval supersedes every agent.**

---

## Section 0 — Operating contract

### 0.1 Default stance

- **AUTO** every row per [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) autonomous-execution stanza. Each row dispatches a stateless `runSubagent` brief with: scope + files + acceptance gates + the one oracle. Subagent ships the PR; orchestrator merges and starts the next without waiting for remote CI.
- **No mid-row CONSULT pause.** Persona verdicts are baked into the rows. If a NEW persona-class decision surfaces, run the personas in DEBATE (never parallel review), bake ONE verdict, proceed.

### 0.2 ESCALATE triggers (the ONLY stop points)

The orchestrator stops ONLY at these triggers. Otherwise AUTO.

1. **State-formation re-partition write (PR-W1b)** — Hans's verdict sanctions moving pre-formation election rows OUT of current-day state CSVs into historical-state CSVs (OWID USSR precedent). The WRITE is Hans+Max + user territory and touches data store contract ([CLAUDE.md](../CLAUDE.md) Holy Law #3). PR-W1b emits a DRY-RUN proposal CSV under `datasets/_ops/state-formation-repartition-proposal.csv` and STOPS for user sign-off before any move.
2. **Schema MAJOR bump anywhere.** Per [CLAUDE.md section 11](../CLAUDE.md) MAJOR is a user sign-off gate. PR-W2a's MINOR bump on `election-events.schema.json` (adding `general_bye` + `assembly_bye` kinds + `event_id_aliases[]`) does NOT trigger this.
3. **Persona verdict contradicts on-disk truth.** If any claim in this plan diverges from on-disk reality, surface and re-debate; do NOT silently re-author scope.
4. **Phase 0 plan PR-P3 has not yet shipped.** This plan's URLs assume Grammar A. If an executing agent starts a row before PR-P3 lands, STOP-AND-SURFACE — the URL grammar will collide.

### 0.3 Baked facts (verified 2026-06-09; do not re-derive)

| Fact | Value |
| --- | --- |
| Election routes today | [NationalElectionsAtlas](../frontend/src/routes/NationalElectionsAtlas.svelte), [StateElection](../frontend/src/routes/StateElection.svelte), [Constituency](../frontend/src/routes/Constituency.svelte), [Compare](../frontend/src/routes/Compare.svelte), [CompareIndicator](../frontend/src/routes/CompareIndicator.svelte), [Psephlab](../frontend/src/routes/Psephlab.svelte), [Party](../frontend/src/routes/Party.svelte) |
| Shipped URL grammar | `/t/elections/:event`, `/s/:state/elections/:event`, `/s/:state/elections/:event/ac/:eci_no-slug`, `/lab/:state/:event[?s=<b64>]`, `/compare/:state/:event[?a=&b=&mode=]`, `/s/:state/party/:party`, `/s/:state/t/elections` (the "horrible page") |
| Election CSVs on disk | 36 per-state files at [datasets/data/datapoints/electoral/](../datasets/data/datapoints/electoral/), shape `entity_id, year, period_label, period_seq, indicator_id, value_numeric, value_text, source_id, derivation` |
| Electoral entities | [datasets/data/entities/electoral.csv](../datasets/data/entities/electoral.csv) — `entity_id, name, aliases, entity_kind(ac\|pc), delim_year, state, parent, eci_no, reservation, source_id` |
| Parties + alliances | [parties.csv](../datasets/data/entities/parties.csv), [party_alliances.csv](../datasets/data/entities/party_alliances.csv) (per-event snapshot keyed by `period_label`) |
| Event registry | [datasets/taxonomy/election_events.json](../datasets/taxonomy/election_events.json) — `kind:"lok_sabha"\|"assembly"`, event_id (today: `LsGenJun2024`), delim_year, dates, state |
| Psephlab engine | [frontend/src/lib/psephlab/](../frontend/src/lib/psephlab/) — 10+ counting rules + 4 mutation kinds; today uses `?s=<b64>` URL encoding (to be dropped) |
| Breadcrumb today | [GeoBreadcrumb.svelte](../frontend/src/lib/GeoBreadcrumb.svelte) — place-first only |
| Party colour resolver | [resolver.ts](../frontend/src/lib/colors/resolver.ts) — anchor / brand / algorithmic OkLCh keyed on `party_id` + ECI code |
| Time slider | [ElectionTimeSlider.svelte](../frontend/src/lib/elections/ElectionTimeSlider.svelte) (election-domain only) |
| Reserved-paths test | [frontend/src/contracts/url-namespace-disjointness.test.ts](../frontend/src/contracts/url-namespace-disjointness.test.ts) — ADR-0037 Phase 1 invariant (states + topics + RESERVED pairwise disjoint); EXTENDED in PR-0 |
| Router | [frontend/src/main.ts](../frontend/src/main.ts) + [frontend/src/lib/router.svelte.ts](../frontend/src/lib/router.svelte.ts) |

### 0.4 New URL grammar (binding contract after PR-0; assumes Phase 0 plan PR-P3 shipped)

```
/                                                              -> Home (welfare-led; 3-card election rail)
/t/elections                                                   -> firehose (every event ever, sortable)
/t/elections/<event-slug>                                      -> national event view
/<state>                                                       -> state hub (unchanged shape; Phase 0 dropped /s/)
/<state>/t/elections                                           -> state-elections hub (REBUILT in PR-W3a)
/<state>/elections/<event-slug>                                -> state slice of one event
/<state>/elections/<event-slug>/<constituency-slug>            -> constituency drill (no /pc/, no /ac/)
/compare/elections/<state>/<from-event-slug>/<to-event-slug>   -> event-vs-event compare
/lab/<state>/<event-slug>                                      -> psephlab analyst surface (scenarios ephemeral)
/<state>/party/<party-slug>                                    -> party page (unchanged shape; Phase 0 dropped /s/)
```

Event-slug grammar:

```
general-<YYYY>                                  e.g. general-2024
assembly-<YYYY>                                 e.g. assembly-2023
general-bye-<YYYY>-<state-slug>-<seat-slug>     e.g. general-bye-2024-bihar-bastar
assembly-bye-<YYYY>-<seat-slug>                 e.g. assembly-bye-2024-tarikere  (state already in path)
```

Regex pin (Tier-A contract test in PR-0): `^(general|assembly)(-bye-[a-z0-9-]+|-\d{4})$` and a parallel disjointness assertion: `stateSlugs`, `topicSlugs`, `indicatorSlugs` each disjoint from the literal set `{"general", "assembly", "elections"}`.

### 0.5 Elections-vs-socio-econ boundary (anti-leakage)

This plan changes ONLY the elections surface. Socio-econ is untouched.

| Concern | Elections (this plan) | Socio-econ (UNCHANGED) |
| --- | --- | --- |
| URL grammar | Place-first under Grammar A `/<state>/elections/<event-slug>/<constituency-slug>` + firehose `/t/elections` + compare `/compare/elections/<state>/<from>/<to>`. No body-roots. No params. No fragments. Phase 0 plan ships Grammar A; this plan ships on top. | Place-first flat indicator slug: `/<state>/<indicator>` (shipped after Phase 0). Unchanged by this plan. |
| Time nav | `YearPillStrip` (discrete tap-to-jump) in `frontend/src/lib/elections/`. Election-domain only. | Time slider in chart shell (continuous). NO pills. |
| Year token | Inside event-slug (`general-2024`); never standalone. | Not in URL; chart shows all years via slider. |
| Components dir | `frontend/src/lib/elections/` | `frontend/src/lib/charts/` (only PR-W4c's scatter primitive adds a NEW file here) |
| Shared seams | `Breadcrumb` component (renamed from `GeoBreadcrumb`); `getPartyColor`; chart-shell composition by scatter. | same |
| Mashed pages (Home, state hub) | Small summary CARDS linking INTO the cascade. NEVER inline pills, swing, or election chrome. | Indicator cards. NEVER election chrome. |

**Anti-leakage rule for the executing agent:** if a PR touches `frontend/src/lib/charts/` (except PR-W4c's scatter), `frontend/src/lib/IndicatorChoropleth.svelte`, `frontend/src/routes/TopicLanding.svelte`, or `frontend/src/routes/StateOverview.svelte` (except to add the small state-level elections summary card), STOP-AND-SURFACE.

### 0.6 Per-PR workflow (every row follows this)

1. Branch off `main`: `git switch -c <feat-branch> origin/main`.
2. Implement the row scope. Tests ship with the row.
3. Local gates GREEN: pytest (backend), vitest (frontend), svelte-check, `python -m yen_gov validate --root .`.
4. **Integrated browser + Playwright verification** per [CLAUDE.md section 13](../CLAUDE.md) for any frontend route change: navigate to the affected URL(s), read_page, screenshot, assert 0 console errors + 0 failed requests. Screenshots in PR body.
5. Commit (single squash-able commit). Push to origin.
6. Open PR. Run `gh pr merge --squash --admin --delete-branch` once local gates are green. **Do NOT wait for remote CI.**
7. Pull `main`. Start the next row.

### 0.7 Closure

Plan complete when every row is DONE or COLLAPSED-with-cited-rationale. Distill durable findings to [docs/architecture/frontend/](../docs/architecture/frontend/) per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md); `git mv` this file to `docs/archive/plans/`.

---

## Section 1 — Status Reckoner (waves for max parallelism)

WAVE 0 ships first and gates everything. WAVE 1+ rows within a wave are PARALLEL (touch disjoint files). Across waves: each WAVE N+1 row depends on at least one WAVE N row.

| Row | Wave | Title | Depends on | Status | PR | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| PR-0 | 0 | Doctrine: URL grammar contract + Hindi-scrub policy + bye-slug locked + reserved-paths test extension | none | [ ] PENDING | — | S |
| PR-W1a | 1 | Hindi-token scrub (TS enums + Svelte chrome + Python labels + comments). Pure rename. | PR-0 | [ ] PENDING | — | M |
| PR-W1b | 1 | State-formation events table + historical-state slug crosswalk + re-partition DRY-RUN (ESCALATE-gated) | PR-0 | [ ] PENDING | — | M (ESCALATE) |
| PR-W1c | 1 | IndiaVotes parity oracle CLI under `tools/elections_parity_indiavotes/` (one-shot offline, never CI) | PR-0 | [ ] PENDING | — | S |
| PR-W1d | 1 | Rename `GeoBreadcrumb` -> `Breadcrumb` + per-route `crumbs(params)` field on route table | PR-0 | [ ] PENDING | — | S |
| PR-W2a | 2 | Event-id rename in `taxonomy/election_events.json` + `event_id_aliases[]` strangler + add `general_bye` + `assembly_bye` kinds (MINOR schema bump) + one bye fixture row | PR-W1a | [ ] PENDING | — | M |
| PR-W2b | 2 | Generic `loadElectionResults(scope)` view-model alongside the 4 bespoke ones (golden-row equality oracle) | PR-W1a | [ ] PENDING | — | M |
| PR-W3a | 3 | Repurpose `/<state>/t/elections` ("horrible page") into state-elections hub: chronological timeline + body filter chip | PR-W2b | [ ] PENDING | — | M |
| PR-W3b | 3 | Rebuild state event view `/<state>/elections/<event-slug>`: KPIs + state choropleth + top-parties + constituency table + inline swing + alliance-first + add `<constituency-slug>` leaf (no `/pc/`, no `/ac/`); strip `?s=<b64>` URL handling | PR-W2a, PR-W2b | [ ] PENDING | — | L |
| PR-W3c | 3 | Rebuild national event view `/t/elections/<event-slug>`: rename `NationalElectionsAtlas` -> `NationalElection`; KPIs + India choropleth + top-parties | PR-W2a, PR-W2b | [ ] PENDING | — | M |
| PR-W3d | 3 | New `/t/elections` firehose: table of every event ever (year + body + leading party + seats + turnout + runners-up) | PR-W2b | [ ] PENDING | — | M |
| PR-W4a | 4 | `YearPillStrip` + `ConstituencyHistoryBar` in `frontend/src/lib/elections/`; mount on `Constituency.svelte` (the constituency drill) | PR-W3b | [ ] PENDING | — | M |
| PR-W4b | 4 | Path-form compare cascade `/compare/elections/<state>/<from-event>/<to-event>` + winner-change table (drop `?a=&b=&mode=` query handling) | PR-W3b, PR-W3c | [ ] PENDING | — | M |
| PR-W4c | 4 | Scatter chart at `frontend/src/lib/charts/Scatter.svelte` (turnout x margin x party-colour x electors-size sqrt; 6 filters); mounted on PR-W3b + PR-W3c | PR-W3b, PR-W3c | [ ] PENDING | — | L |
| PR-W4d | 4 | Home elections rail redesign: 3-card strip (anchor + hook + door) | PR-W3d | [ ] PENDING | — | S |
| PR-W5a | 5 | Strip remaining `?s=<b64>` parsing from `/lab/` route + cleanup; delete 4 bespoke election view-models replaced by PR-W2b | PR-W3b, PR-W4b | [ ] PENDING | — | S |

**Effort key**: XS = <1h • S = 1-3h • M = half-day • L = full-day. Estimates, not commitments.

**Critical path:** PR-0 -> PR-W1a -> PR-W2a -> PR-W3b -> PR-W4c -> PR-W5a (6 sequential PRs minimum). Everything else parallelizes.

---

## Section 2 — Per-row specifications

> Every row carries: **Scope**, **Files**, **Acceptance gates**, **Load-bearing oracle**, **Escalation**.

### PR-0 — Doctrine + URL grammar contract + bye-slug locked

**Scope.** Pure docs + one test extension. Locks the contracts the other 15 rows execute against.

**Files:**
- EDIT [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) — append two named-divergence sections: (a) "Event-grain URLs (elections-only exception)" — ADR-0028 rejected vintage, not year-as-event-identity; (b) "No-Hindi policy" — English-only across URLs / chrome / code; cite Hans English-noun rulings.
- EDIT [docs/concepts/electoral-hierarchy.md](../docs/concepts/electoral-hierarchy.md) — add "URL grammar (binding)" section with the full cascade + event-slug grammar + bye-slug format from section 0.4 of THIS plan.
- EDIT [frontend/src/contracts/url-namespace-disjointness.test.ts](../frontend/src/contracts/url-namespace-disjointness.test.ts) — add the event-slug regex assertion + 3 disjointness assertions (`stateSlugs`, `topicSlugs`, `indicatorSlugs` each disjoint from `{"general", "assembly", "elections"}`). NO new TOP_LEVEL reserved tokens (firehose stays at the existing `/t/elections`).
- EDIT [CLAUDE.md](../CLAUDE.md) section 3 (topology) — one-line pointer to the updated url-grammar doc.

**Acceptance gates:**

- [ ] G1 — `npx vitest run frontend/src/contracts/url-namespace-disjointness.test.ts` GREEN.
- [ ] G2 — no new top-level RESERVED token added (grep gate).
- [ ] G3 — every edited doc has H1 + `Last Updated: 2026-06-09` + "See also"; ASCII-only.

**Oracle:** the extended contract test GREEN with the event-slug regex + 3 disjointness assertions enforced.

**Escalation:** none.

---

### PR-W1a — Hindi-token scrub (pure rename, zero behaviour change)

**Scope.** Replace every Hindi token (`lok_sabha`, `vidhan_sabha`, `Lok Sabha`, `Vidhan Sabha`) with the English equivalent (`parliament`, `assembly`, `Parliament`, `Assembly`) across the whole repo. Tidy First; zero behaviour change.

**Files (grep-driven; executor runs the grep):**
- TypeScript: enum literals + union types + comments under `frontend/src/lib/` and `frontend/src/routes/`.
- Svelte: page chrome strings — Hans Q5 wording: "General Election YYYY", "Karnataka Assembly Election YYYY".
- Python: `backend/yen_gov/canonical/` labels + docstrings + comments.
- JSON schemas: `kind` enum in [election-events.schema.json](../datasets/schemas/election-events.schema.json) — MINOR bump + `x-changelog` SAME COMMIT.

**Acceptance gates:**

- [ ] G1 — `git grep -iE "lok.sabha|vidhan.sabha"` returns ZERO matches across the repo.
- [ ] G2 — pytest GREEN; svelte-check + tsc CLEAN; vitest GREEN.
- [ ] G3 — `python -m yen_gov validate --root .` OK.
- [ ] G4 — integrated browser smoke: navigate one existing election URL, confirm rendering is byte-equivalent except for the chrome-string rename.

**Oracle:** grep gate G1 — zero Hindi tokens repo-wide.

**Escalation:** if a chrome string has Hindi where the English replacement loses meaning (rare — e.g. an attribution credit naming a Hindi-language source), STOP-AND-SURFACE.

---

### PR-W1b — State-formation events + historical-state slug + re-partition DRY-RUN (ESCALATE-gated)

**Scope.** Make state-formation events first-class. Author the table; build the slug crosswalk; emit a DRY-RUN of pre-formation row re-partitioning; STOP for user sign-off before any write.

**Files:**
- NEW [datasets/taxonomy/state_formation_events.json](../datasets/taxonomy/state_formation_events.json). 5-column shape: `event_id, parent_state_ids[], successor_state_ids[], event_date, source_id`. Seed the 5 known events: MP/CG (2000-11-01), UP/UK (2000-11-09), Bihar/Jharkhand (2000-11-15), AP/Telangana (2014-06-02), Goa/Daman+Diu split (1987).
- NEW `datasets/schemas/state-formation-events.schema.json` v1.0 + `x-changelog`.
- NEW `backend/yen_gov/canonical/historical_state_slug.py` — pure function `historical_state_slug(constituency_entity_id, event_year) -> str`. Unit-tested with the 5 formation events.
- NEW `tools/elections_state_formation/repartition_dry_run.py` — emits `datasets/_ops/state-formation-repartition-proposal.csv` (columns: `entity_id, year, current_file, proposed_file, formation_event_id`). NO writes.
- EDIT [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) — add "State-formation events" subsection.

**Acceptance gates:**

- [ ] G1 — `python -m yen_gov validate --root .` OK.
- [ ] G2 — pytest GREEN on the 5+ unit tests for `historical_state_slug`.
- [ ] G3 — `repartition_dry_run.py` emits a non-empty proposal CSV with the expected columns.
- [ ] G4 — **STOP-AND-SURFACE** with the proposal CSV path. Wait for user sign-off OR a defer verdict (Path-B: leave current-day partitioning, resolve historical state only in URL routing).

**Oracle:** `historical_state_slug("IN-PC-2008-S26-1", 1952) == "madhya-pradesh-1947-1999"` AND `historical_state_slug("IN-PC-2008-S26-1", 2024) == "chhattisgarh"`. One test proves the temporal crosswalk works.

**Escalation:** Gate G4 is THE escalate point (section 0.2 trigger #1).

---

### PR-W1c — IndiaVotes parity oracle CLI (one-shot offline, never CI)

**Scope.** Build a parity-check CLI per Max verdict. Sole consumer = the engineer running the gate; output to `datasets/_ops/`.

**Files:**
- NEW `tools/elections_parity_indiavotes/pyproject.toml` — pinned `httpx + beautifulsoup4`. Does NOT import `backend/`.
- NEW `tools/elections_parity_indiavotes/__main__.py` — CLI: `python -m tools.elections_parity_indiavotes --event general-2024 --state chhattisgarh --output datasets/_ops/elections-parity-vs-indiavotes-2026-06-09.csv`.
- NEW `tools/elections_parity_indiavotes/scrape.py` — pulls IndiaVotes HTML; caches under `datasets/ephemeral/indiavotes-snapshots/<date>/<event>/<state>/<page>.html`. Honours `robots.txt`. 1 req/sec single-threaded.
- NEW `tools/elections_parity_indiavotes/diff.py` — joins scraped winners against yen-gov's per-state CSV; emits delta rows.
- NEW `tools/elections_parity_indiavotes/README.md` — usage + politeness rules + "never CI" doctrine.
- EDIT [docs/how-to/](../docs/how-to/) — new `validate-elections-vs-indiavotes.md`.

**Acceptance gates:**

- [ ] G1 — CLI runs end-to-end against live site for general-2024 Chhattisgarh; emits non-empty CSV.
- [ ] G2 — agreement >= 99% on 11 PC winners.
- [ ] G3 — `datasets/ephemeral/indiavotes-snapshots/` is gitignored.
- [ ] G4 — `tools/elections_parity_indiavotes/` has no imports from `backend/`.

**Oracle:** for general-2024 Chhattisgarh, the CSV records 11 PC winner agreements (or names exact deltas). Holy Law #5: parity miss = fix the ingest, not stash IndiaVotes rows.

**Escalation:** none.

---

### PR-W1d — Rename `GeoBreadcrumb` -> `Breadcrumb` + route-driven `crumbs(params)`

**Scope.** ONE breadcrumb engine that consumes a per-route `crumbs(params)` function. Election-cascade crumbs and socio-econ-cascade crumbs share one component.

**Files:**
- RENAME (`git mv`) [frontend/src/lib/GeoBreadcrumb.svelte](../frontend/src/lib/GeoBreadcrumb.svelte) -> `frontend/src/lib/Breadcrumb.svelte`. Drop place-first assumption; consume `crumbs: Crumb[]` prop directly.
- NEW `frontend/src/lib/breadcrumb-types.ts` — `interface Crumb { label: string; href?: string; isLeaf?: boolean }`.
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — add `crumbs(params): Crumb[]` to each route entry.
- EDIT every consumer (`StateOverview`, `StateTopic`, `Constituency`, `District`, `Home`) — `<GeoBreadcrumb ... />` -> `<Breadcrumb crumbs={crumbs} />`.
- NEW `frontend/src/lib/Breadcrumb.test.ts` — snapshot test for 6 canonical URLs (mix election + socio-econ).

**Acceptance gates:**

- [ ] G1 — vitest GREEN on snapshot test; full suite GREEN.
- [ ] G2 — svelte-check + tsc CLEAN.
- [ ] G3 — `git grep GeoBreadcrumb` returns ZERO matches.
- [ ] G4 — integrated browser smoke: navigate one election URL + one socio-econ URL; breadcrumb visible + clickable in both.

**Oracle:** the 6-URL snapshot test — ONE component renders both cascades from the matched route's `crumbs(params)` output.

**Escalation:** none.

---

### PR-W2a — Event-id rename + bye event kinds + alias strangler

**Scope.** Atomically rename event-ids on disk from internal codes (`LsGenJun2024`) to citizen-readable slugs (`general-2024`). Add the two bye event kinds. Add `event_id_aliases[]` to the schema for one-release readability of legacy values.

**Files:**
- EDIT [datasets/schemas/election-events.schema.json](../datasets/schemas/election-events.schema.json) — MINOR bump: add `general_bye` + `assembly_bye` to `kind` enum; add `event_id_aliases: string[]` (optional); `x-changelog` row SAME COMMIT.
- EDIT [datasets/taxonomy/election_events.json](../datasets/taxonomy/election_events.json) — mechanical rename every `event_id`: `LsGenJun2024` -> `general-2024`, `AcGenMay2023` -> `assembly-2023`, etc. Populate `event_id_aliases: ["<old-id>"]` on each row.
- EDIT every consumer that types the literal event-id (frontend view-models, Python adapters, tests). The pattern is mechanical.
- ADD one bye-event fixture row exercising the bye-slug format from PR-0 (`assembly-bye-2024-tarikere` style).
- EDIT `frontend/src/lib/canonical/event-kind.ts` (or equivalent) — add the two new variants.

**Acceptance gates:**

- [ ] G1 — vitest GREEN; pytest GREEN; svelte-check CLEAN.
- [ ] G2 — `python -m yen_gov validate --root .` OK; events table re-validates with `event_id_aliases[]`.
- [ ] G3 — every `period_label` in `datasets/data/datapoints/electoral/*.csv` resolves via the alias table (one Python test walks the CSVs).
- [ ] G4 — bye fixture row resolves: `loadEventsByKind('assembly_bye').length >= 1`.

**Oracle:** for an old-id URL like `/<state>/elections/LsGenJun2024` AND a new-id URL like `/<state>/elections/general-2024`, BOTH resolve via the alias table to the same canonical event row.

**Escalation:** if PR-0 has not landed Hans's bye-slug verdict, the executing agent CANNOT proceed (PR-W2a needs the bye-slug format to rename event ids without guessing a forever URL contract). The status reckoner's `Depends on: PR-W1a` chain already enforces this; no special status name needed. Surface to user if PR-0 is in flight but stalled.

---

### PR-W2b — Generic `loadElectionResults(scope)` view-model

**Scope.** Collapse the 4 election view-models (`loadNationalPcWinners`, `loadStateAcWinners`, `loadConstituencyResult`, `loadIndiaLeadingParties`) into ONE generic loader. Bespoke loaders STAY LIVE in this PR; replaced one-by-one as call-sites flip; deleted in PR-W5a.

**Files:**
- NEW `frontend/src/lib/view-models/election-results.ts` — exports `loadElectionResults(scope: ElectionScope): Promise<ElectionResultRow[]>`. Two projection helpers: `projectAsConstituencyRanks(rows)` + `projectAsWinnersByEntity(rows)`.
- NEW `frontend/src/lib/view-models/election-results.test.ts` — GOLDEN-ROW EQUALITY against each bespoke loader for 3 scopes:
  - `{event: 'general-2024'}` (national winners)
  - `{event: 'assembly-2023', state: 'karnataka'}` (state AC winners)
  - `{event: 'general-2024', state: 'chhattisgarh', constituency: 'bastar'}` (single constituency)
- EDIT `frontend/src/AGENTS.md` — append "view-model collapse: `loadElectionResults(scope)` is the canonical loader; bespoke ones retired by PR-W5a."

**Acceptance gates:**

- [ ] G1 — vitest GREEN on golden-row equality test.
- [ ] G2 — no callers of the new loader yet (library-only).
- [ ] G3 — svelte-check + tsc CLEAN; full vitest GREEN.

**Oracle:** golden-row equality — for each of the 3 scopes, `loadElectionResults(scope)` returns a row-set BYTE-EQUAL to the bespoke loader's output (sorted by entity_id + period_label).

**Escalation:** if a projection-loss is real, surface as TWO projection helpers rather than collapsing.

---

### PR-W3a — Repurpose `/<state>/t/elections` ("horrible page") into state-elections hub

**Scope.** URL unchanged; content rewritten. Replaces today's "List: N/A" + "How X compares" framing with a chronological event timeline.

**New layout (per Jony Q3):**
- Header: `<state-name>` + "Election history".
- Body filter chip: `[All] [Parliament] [Assembly]`. One filter only.
- Chronological event timeline, newest first. One row per event: year + body chip + winning party/alliance pill + seat count + swing vs previous same-body event. Click -> `/<state>/elections/<event-slug>`.

**Files:**
- EDIT [frontend/src/routes/StateTopic.svelte](../frontend/src/routes/StateTopic.svelte) topic=elections branch (or extract to NEW `frontend/src/routes/StateElectionsHub.svelte` if cleaner).
- NEW `frontend/src/lib/elections/StateEventTimeline.svelte` — pure component, props `{ events: ElectionEvent[], onSelect }`.
- NEW `frontend/e2e/state-elections-hub.spec.ts` — Playwright: navigate `/karnataka/t/elections`, assert >= 10 event rows + body filter chip + click-through to one event lands on `/karnataka/elections/<slug>`. 0 console errors.

**Acceptance gates:**

- [ ] G1 — Playwright spec GREEN.
- [ ] G2 — svelte-check + tsc CLEAN; vitest GREEN.
- [ ] G3 — integrated browser smoke on the user-named horrible page: navigate `/arunachal-pradesh/t/elections`, screenshot. Before/after comparison in PR body.
- [ ] G4 — anti-leakage: other topic branches of `StateTopic.svelte` (`t/economy`, `t/power-energy`, etc.) unchanged.

**Oracle:** Playwright — `/karnataka/t/elections` renders all 11 Karnataka assembly events as clickable timeline rows.

**Escalation:** none.

---

### PR-W3b — Rebuild state event view + inline swing + alliance + add constituency leaf

**Scope.** Rebuild `StateElection.svelte` (URL `/<state>/elections/<event-slug>` after Phase 0) into the new IndiaVotes-style state event experience. Add the `<constituency-slug>` route literal (no `/pc/`, no `/ac/`). Strip `?s=<b64>` URL handling from the inline swing.

**New layout:**
- KPIs strip: seats / voters / polled / turnout.
- State choropleth via `ElectionMap.svelte` with `Winner | Margin` toggle.
- Top-parties bar (Hans Q6: filter to "parties that contested this event").
- Constituency table: name + winner-party-pill + vote-share % + margin-over-runner-up.
- Inline counterfactual swing (2 dropdowns + 0-30% slider + "seats under this swing" card; ephemeral state, no URL).
- Alliance-first display ("NDA 11 / INDIA 0 / Others 0"; one-click expand to party breakdown; caption "alliance as of polling date <date>").
- "Compare with previous same-body event ->" CTA -> `/compare/elections/<state>/<from-event>/<to-event>` (PR-W4b target).

**Files:**
- EDIT [frontend/src/routes/StateElection.svelte](../frontend/src/routes/StateElection.svelte) — full rebuild.
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — add `pattern: "/:state/elections/:event/:constituency"` (NO `/pc/` or `/ac/` literal; Phase 0 plan dropped the `/s/` namespace marker). Same `Constituency.svelte` component handles both AC and PC; dispatch on event-slug prefix (`general-` -> PC; `assembly-` -> AC).
- EDIT [frontend/src/routes/Constituency.svelte](../frontend/src/routes/Constituency.svelte) — adapt to read constituency type from event-slug prefix.
- NEW `frontend/src/lib/elections/InlineCounterfactualSwing.svelte` — 2 dropdowns + slider + seats card. Composes `statewideSwing` mutation + `fptp` rule. Component state only (no URL).
- NEW `frontend/src/lib/elections/AllianceTotals.svelte` — joins `party_alliances.csv` by `period_label` + `party_id`.
- NEW `*.test.ts` for both panels — vitest fixtures.
- NEW `frontend/e2e/state-event-view.spec.ts` — Playwright: navigate `/chhattisgarh/elections/general-2024`, assert KPIs + map + swing slider works + alliance totals show + drill into one constituency via `/chhattisgarh/elections/general-2024/bastar`.

**Acceptance gates:**

- [ ] G1 — vitest + pytest GREEN; svelte-check + tsc CLEAN; Playwright GREEN.
- [ ] G2 — integrated browser walkthrough: state event view -> change swing slider -> seat counts update -> drill into Bastar (PC inferred from `general-` prefix). Screenshot.
- [ ] G3 — anti-leakage: socio-econ surfaces untouched (grep gate).
- [ ] G4 — slug-collision validator extended: constituency slug must NOT match event-slug regex.

**Oracle:** inline-swing fixture — `statewideSwing(allocation, {from: 'BJP', to: 'INC', pct: 5})` produces a NEW allocation differing from baseline.

**Escalation:** if alliance data is missing for the test event, the AllianceTotals panel renders "alliance data pending" (does not block the rest).

---

### PR-W3c — Rebuild national event view + rename component

**Scope.** Rebuild `NationalElectionsAtlas.svelte`; rename to `NationalElection.svelte`. URL `/t/elections/:event` unchanged (event-slug renamed by PR-W2a).

**Files:**
- RENAME (`git mv`) `frontend/src/routes/NationalElectionsAtlas.svelte` -> `frontend/src/routes/NationalElection.svelte`.
- EDIT the renamed file — replace atlas-only layout with: KPIs (total seats / voters / polled / turnout) + India choropleth + top-parties horizontal bar + click-state-to-drill.
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — update import + `pattern: "/t/elections/:event"` component reference.
- NEW `frontend/e2e/national-event-view.spec.ts` — Playwright: `/t/elections/general-2024` renders KPIs + India map + top-parties bar. 0 console errors.

**Acceptance gates:**

- [ ] G1 — Playwright spec GREEN; vitest GREEN.
- [ ] G2 — svelte-check + tsc CLEAN.
- [ ] G3 — integrated browser smoke: navigate `/t/elections/general-2024`, screenshot.

**Oracle:** for `/t/elections/general-2024`, the India choropleth renders >= 35 coloured polygons AND the top-parties bar shows BJP first (240 seats in 2024).

**Escalation:** none.

---

### PR-W3d — New `/t/elections` firehose

**Scope.** New top-level firehose page mirroring `/t/<topic>` pattern. Lists every election event ever (year + body + leading party + seats + turnout + runners-up).

**Files:**
- NEW `frontend/src/routes/ElectionsFirehose.svelte` — URL `/t/elections` (no second segment). Table layout matching IndiaVotes's index visual style.
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — add `pattern: "/t/elections"` route entry BEFORE `pattern: "/t/elections/:event"` (route order matters).
- NEW `frontend/e2e/elections-firehose.spec.ts` — Playwright: navigate `/t/elections`, assert >= 18 event rows (18 LS events 1952-2024) + state-assembly events present + click-through routes correctly.

**Acceptance gates:**

- [ ] G1 — Playwright spec GREEN.
- [ ] G2 — svelte-check + tsc CLEAN; vitest GREEN.
- [ ] G3 — `url-namespace-disjointness.test.ts` STILL GREEN.
- [ ] G4 — integrated browser smoke: navigate `/t/elections`, screenshot.

**Oracle:** Playwright — the firehose table shows >= 18 LS general elections AND row-clicks resolve to the matching `/t/elections/<event-slug>` view.

**Escalation:** none.

---

### PR-W4a — `YearPillStrip` + `ConstituencyHistoryBar`

**Scope.** Two election-domain components per Jony verdict. Live in `frontend/src/lib/elections/`. Mount on `Constituency.svelte`.

**Files:**
- NEW `frontend/src/lib/elections/YearPillStrip.svelte` — props `{ events: ElectionEvent[], active: EventId, onSelect }`. Discrete tap-to-jump pills.
- NEW `frontend/src/lib/elections/ConstituencyHistoryBar.svelte` — props `{ entity_id, body, results }`. One row per election: bar width = winner vote share; party-pill + margin at right.
- NEW `*.test.ts` for both — fixture-driven.
- EDIT [frontend/src/routes/Constituency.svelte](../frontend/src/routes/Constituency.svelte) — mount both components below the candidates table.

**Acceptance gates:**

- [ ] G1 — vitest GREEN on both component tests.
- [ ] G2 — svelte-check + tsc CLEAN.
- [ ] G3 — integrated browser smoke: `/chhattisgarh/elections/general-2024/bastar`; assert year-pills (18 pills for Bastar's full history) + history bars (18 rows). Screenshot.

**Oracle:** constituency-history fixture — 18 general elections for Bastar produce 18 history-bar rows with correct party colours (BJP saffron, INC blue, IND grey).

**Escalation:** none.

---

### PR-W4b — Path-form compare cascade `/compare/elections/<state>/<from>/<to>`

**Scope.** Body-tagged compare path per user verdict. Drop the old `?a=&b=&mode=` query form.

**Files:**
- NEW `frontend/src/routes/CompareElections.svelte` — URL `/compare/elections/:state/:fromEvent/:toEvent`. Loads both events via `loadElectionResults`; joins by constituency id; renders IndiaVotes-style winner-change table.
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — register `/compare/elections/:state/:fromEvent/:toEvent`. The old `/compare/:state/:event` stays live for PR-W5a to clean.
- EDIT existing `Compare.svelte` — keep route alive but add a deep-link `<a href={newCompareUrl}>Open new compare ->` (user accepts loss of `?a=&b=` URL bookmarks per binding constraint #9).
- NEW `frontend/e2e/compare-elections.spec.ts` — Playwright: `/compare/elections/tamil-nadu/general-2014/general-2019` renders >= 30 rows + >= 20 flips. 0 console errors.

**Acceptance gates:**

- [ ] G1 — Playwright spec GREEN; vitest GREEN.
- [ ] G2 — svelte-check + tsc CLEAN.
- [ ] G3 — integrated browser smoke: open the new compare URL, screenshot.

**Oracle:** for `/compare/elections/tamil-nadu/general-2014/general-2019`, change-table renders >= 30 rows + >= 20 flips (the ADMK -> DMK swing).

**Escalation:** none.

---

### PR-W4c — Scatter chart (must-feature)

**Scope.** New chart primitive per Max verdict. Lives at `frontend/src/lib/charts/Scatter.svelte`. Mounted on `NationalElection.svelte` AND `StateElection.svelte`. The scatter is the ONE permitted new file under `frontend/src/lib/charts/` per anti-leakage rule.

**Chart spec (Max verdict baked):**
- X: voter turnout %; Y: winning margin %; colour: winning party (via `getPartyColor`); **size: total electors, sqrt-scaled** (visual area scales with value — OWID Rosling precedent).
- 6 filters: event + state + highlight-party + reservation (GEN/SC/ST) + body (parliament/assembly) + margin-band (`<2%` / `2-5%` / `5-10%` / `>10%`).
- Click-dot -> `/<state>/elections/<event-slug>/<constituency-slug>`.
- Honesty caption (Max Q8): "Plotting N constituency-elections across <event-set>. 2008 delimitation break + AP/Telangana 2014 + Assam/J&K post-2022 redelim mean pre-2009 PC seats are not 1:1 comparable. [Methodology]".

**Files:**
- NEW `frontend/src/lib/charts/Scatter.svelte` — pure component, props `{ data, filters, onDotClick }`. Reuses existing chart-shell.
- NEW `frontend/src/lib/charts/Scatter.test.ts` — fixture: 50 rows -> 50 dots; size sqrt-correct; click handler fires with correct entity_id.
- NEW `frontend/src/lib/charts/scatter-fixtures.ts`.
- EDIT `NationalElection.svelte` (PR-W3c) — mount `<Scatter />` with national default (event=general-2024, state=All, highlight=none per Max Q3).
- EDIT `StateElection.svelte` (PR-W3b) — mount `<Scatter />` with state filter pre-applied.
- NEW `frontend/e2e/elections-scatter.spec.ts` — Playwright: navigate `/t/elections/general-2024`, scroll to scatter, change reservation filter to ST, assert dots reduce to ST seats; click one dot, assert routes to constituency drill.

**Acceptance gates:**

- [ ] G1 — vitest GREEN on Scatter tests.
- [ ] G2 — Playwright spec GREEN.
- [ ] G3 — svelte-check + tsc CLEAN; full vitest GREEN.
- [ ] G4 — integrated browser smoke: navigate `/t/elections/general-2024`, screenshot scatter with all filters open. Toggle reservation=ST; screenshot. Open `/karnataka/elections/assembly-2023`; confirm scatter restricts to Karnataka ACs.
- [ ] G5 — anti-leakage: Scatter is the ONLY new file under `frontend/src/lib/charts/`. All other socio-econ chart files unchanged.

**Oracle:** for `/t/elections/general-2024`, the scatter renders >= 540 dots (one per Parliament seat in 2024) AND size differentiates Bangalore-South (large) from Lakshadweep (small).

**Escalation:** if the scatter needs a generic chart-shell tweak (e.g. axis label rendering), the tweak ships in this PR but socio-econ chart files MUST stay unchanged. Otherwise STOP-AND-SURFACE.

---

### PR-W4d — Home elections rail redesign (3-card strip)

**Scope.** Replace the "almost useless, hangs without context" Home elections section per Jony Q4 verdict.

**Layout:**
1. **Anchor card** — most-recent-finished event ("Parliament 2024 — national results" -> `/t/elections/general-2024`).
2. **Hook card** — closest race in latest OR next-upcoming event ("2024's closest seat: Mumbai South, margin 12k votes" -> drill route).
3. **Door card** — "All elections ->" -> `/t/elections` firehose.

**Files:**
- EDIT [frontend/src/routes/Home.svelte](../frontend/src/routes/Home.svelte) — replace the current elections section with the 3-card strip.
- NEW `frontend/src/lib/elections/HomeElectionsRail.svelte` — pure component, props `{ anchor, hook, door }`.
- NEW `frontend/src/lib/view-models/home-elections-rail.ts` — composes the 3 card payloads.
- NEW `*.test.ts` — fixture.
- NEW `frontend/e2e/home-elections-rail.spec.ts` — Playwright: navigate `/`, assert 3 cards render + each is clickable + each routes correctly.

**Acceptance gates:**

- [ ] G1 — vitest GREEN; svelte-check + tsc CLEAN; Playwright GREEN.
- [ ] G2 — integrated browser smoke: open Home, screenshot the rail. Before/after in PR body. The "hangs without context" state MUST visually clear.
- [ ] G3 — anti-leakage: rest of Home.svelte (welfare-led theme, socio-econ rails) unchanged.

**Oracle:** Home renders 3 cards, each with non-empty content + working link.

**Escalation:** none.

---

### PR-W5a — Final cleanup: drop `?s=<b64>` URL parsing + delete bespoke view-models

**Scope.** Last cleanup row. Strip remaining `?s=<b64>` parsing from `/lab/` route (scenarios are now ephemeral). Delete the 4 bespoke election view-models replaced by PR-W2b's `loadElectionResults(scope)`. Remove the legacy `/compare/:state/:event` route after PR-W4b's replacement ships.

**Files (DELETE):**
- DELETE `frontend/src/lib/view-models/national-elections.ts`
- DELETE `frontend/src/lib/view-models/state-overview.ts` (READ FIRST — if it has non-election consumers, narrow rather than delete)
- DELETE `frontend/src/lib/view-models/constituency.ts`
- DELETE `frontend/src/lib/view-models/india-leading-parties.ts`
- DELETE `frontend/src/routes/Compare.svelte` (replaced by `CompareElections.svelte`; `CompareIndicator.svelte` UNCHANGED — socio-econ)
- EDIT [frontend/src/routes/Psephlab.svelte](../frontend/src/routes/Psephlab.svelte) — strip all `?s=<b64>` URL parsing + URL-building code. Scenarios are now ephemeral component state.
- EDIT [frontend/src/main.ts](../frontend/src/main.ts) — remove the `/compare/:state/:event` route entries; remove import of deleted view-models + `Compare.svelte`.

**Acceptance gates:**

- [ ] G1 — vitest GREEN; full suite GREEN.
- [ ] G2 — svelte-check + tsc CLEAN (no dangling imports).
- [ ] G3 — `git grep "[?]s="` returns ZERO matches in `frontend/src/routes/` or `frontend/src/lib/psephlab/` (URL-encoded scenario fully retired).
- [ ] G4 — bundle size SMALLER than pre-rip (`du -b frontend/dist/` comparison in PR body).
- [ ] G5 — integrated browser walkthrough — section 3 final-acceptance citizen path GREEN.

**Oracle:** `git grep "[?]s=<b64>" -- frontend/src/` returns ZERO matches AND the four bespoke view-model files don't exist.

**Escalation:** if `state-overview.ts` is consumed by non-election routes, narrow (delete only election-specific functions) instead of full-file delete.

---

## Section 3 — Final acceptance (whole plan)

**The rip is COMPLETE when** the [CLAUDE.md section 9](../CLAUDE.md) 5-gate Definition of Done passes for every row AND a manual citizen walkthrough succeeds end-to-end with 0 console errors:

1. Open `/t/elections` (firehose). Confirm event table renders.
2. Click a national event view: `/t/elections/general-2024`. Confirm KPIs + India choropleth + top-parties bar + scatter chart.
3. From the national choropleth, click Chhattisgarh -> `/chhattisgarh/elections/general-2024`. Confirm KPIs + state map + inline counterfactual swing + alliance-first totals + constituency table + scatter chart.
4. Trigger the inline swing (BJP -> INC 5%); see seats recompute live.
5. From the constituency table, click Bastar -> `/chhattisgarh/elections/general-2024/bastar` (no `/pc/` literal). Confirm candidate list + year-pills strip + "across elections" history bars.
6. Use year-pills to jump to Bastar 2019 -> URL becomes `/chhattisgarh/elections/general-2019/bastar`. Same shape.
7. From state event view click "Compare with previous ->" -> `/compare/elections/chhattisgarh/general-2019/general-2024`. Confirm winner-change table.
8. Manually navigate to `/compare/elections/tamil-nadu/general-2014/general-2019`. Confirm >= 30 rows + >= 20 flips.
9. Open state-elections hub `/arunachal-pradesh/t/elections` (the user-named horrible page). Confirm timeline + body filter chip. Clearly NOT the old "List: N/A" surface.
10. Open Home `/`. Confirm 3-card elections rail. Clearly NOT the old "hanging" state.
11. Verify breadcrumb on every page (one `Breadcrumb` component, body-aware vs place-first crumbs from per-route `crumbs(params)`).
12. Verify alliance-first display on state event pages.
13. Run `git grep -iE "lok.sabha|vidhan.sabha"` — ZERO matches.

Screenshot every step into the final PR body.

---

## Execution contract (autonomous; follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger.

1. **Orchestrator + subagent topology.** Main agent owns the Status Reckoner; never lets context overflow. Each row dispatched as a stateless `runSubagent` brief with scope + files + gates + oracle.
2. **One row = one PR = one branch** off `main`. Per-PR workflow per section 0.6 (test locally, commit, push, `gh pr merge --squash --admin --delete-branch`, **don't wait for remote CI**, pull main, next row).
3. **Wave-parallelism.** Within a wave, dispatch all rows in parallel (each in its own worktree via `git worktree add` to avoid master-worktree collisions per lessons.md 2026-06-09 G29). Across waves, sequential.
4. **Tests ship with the row.** Use Playwright + integrated browser (`open_browser_page`, `read_page`, `screenshot_page`) for every frontend route change per [CLAUDE.md section 13](../CLAUDE.md).
5. **Persona debate converges to ONE ruling.** When a row hits a contested call, run authority personas in debate (never parallel review); bake one verdict; proceed.
6. **Context offload.** Push breadth-y reads + audits into subagents so the orchestrator window stays lean.
7. **Post-merge hygiene every time.** Prune `: gone` local branches, delete `.tmp_*`, distil lessons.
8. **Stop only at a real boundary** (section 0.2 ESCALATE triggers OR audit depth >3). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every row is DONE or COLLAPSED-with-cited-rationale. Archive per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).

---

## Appendix — Persona verdict convergence (baked; do not re-debate)

**Jony (UX + URL).** Place-first cascade on Grammar A (`/<state>/...` after Phase 0 plan ships). Year inside event-slug (`general-2024`); event is one atomic identity. Year-pills strip for ELECTIONS only; socio-econ keeps slider. ONE breadcrumb engine, URL-derived. Inline counterfactual swing on state event page + `/lab/` for power users. No `/pc/` or `/ac/` literals (body prefix implies type). Keep `/t/elections` firehose. Compare URL body-tagged. Repurpose `/<state>/t/elections` into chronological timeline. Home rail = 3-card strip.

**Hans (English nouns + governance).** Event slug `general-<YYYY>` / `assembly-<YYYY>`. Bye slug uses `bye-` per ECI/Hindu/IE/ToI usage: `general-bye-<YYYY>-<state>-<seat>` / `assembly-bye-<YYYY>-<seat>`. Constituency-unit nouns "Parliament constituency" / "Assembly constituency" in chrome; "PC" / "AC" survive in URL slugs + chart axes. Hindi Glossary line allowed in page body ONLY (one line, never slug/heading/code). State-formation events first-class (5-column JSON). Bye-elections as new event kinds (`general_bye` / `assembly_bye`). Top-parties widget filtered to "parties that contested this event". Alliance display alliance-first, party-breakdown one-click expand. V1 KPI lead: seats won. IndiaVotes parity oracle one-shot offline never CI.

**Fowler (engineering).** Atomic rip with no legacy-URL absorber (user verdict drops the strangler). Generic `loadElectionResults(scope)` collapses 4 bespoke loaders; golden-row equality oracle. Breadcrumb rename + per-route `crumbs(params)`. NO localStorage for scenarios (ephemeral; revisit when citizen complaint surfaces). NO new TOP_LEVEL reserved tokens (firehose stays at `/t/elections`). Scatter as `frontend/src/lib/charts/Scatter.svelte`. Bye-slug locked in PR-0 BEFORE PR-W2a; the status-reckoner dependency chain (`PR-W2a depends on PR-W1a depends on PR-0`) enforces the sequence \u2014 no special "BLOCKED" status terminology needed.

**Max (scatter dimensions).** Size = total electors (sqrt-scaled; Rosling precedent). 6 filters (event + state + highlight-party + reservation + body + margin-band). National + per-state surfaces. Click-dot -> constituency drill. Honesty caption naming the 2008 delimitation break + AP/Telangana 2014 + Assam/J&K post-2022 redelim.

---

## See also

- [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) — receives event-grain + No-Hindi divergences (PR-0).
- [docs/concepts/electoral-hierarchy.md](../docs/concepts/electoral-hierarchy.md) — receives the binding cascade + bye-slug format (PR-0).
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md) — existing geography divergence; new event-grain divergence parallels it.
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) — autonomous-execution stanza.
- [docs/agents/guardrails.md](../docs/agents/guardrails.md) — anti-patterns the executing agent must respect.
- [TODO/20260531-uk-style-elections-experience-plan.md](20260531-uk-style-elections-experience-plan.md) — prior elections-IA plan; THIS plan replaces its URL grammar.
- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) — long-format CSV foundation under which this plan ships.
- [CLAUDE.md](../CLAUDE.md) — engineering contract; authority table (section 0a); Holy Laws.
