# ADR-0040: YENASK brand mark refresh (Yen-Ask) + lab route placement (/lab/yenask) — Accepted

**Last Updated**: 2026-05-26
**Status**: accepted
**Supersedes**: none (narrowly amends [ADR-0039 §D-33](0039-yenask-retrieval-augmented-intent-extraction.md#yen-ask-brand-mark-standard-d-33) and the `/dev/yenask` route choice locked in [ADR-0039](0039-yenask-retrieval-augmented-intent-extraction.md) §"Yen-Ask brand-mark standard (D-33)")
**Amends**: ADR-0039 (visible brand standard only: Yen-Ask; route URL only: `/dev/yenask` → `/lab/yenask`)
**Related**: [yenask subsystem doc](../frontend/yenask.md), [ADR-0039](0039-yenask-retrieval-augmented-intent-extraction.md), [ADR-0038](0038-yenask-two-stage-llm-pipeline-rejected.md), [ADR-0028](0028-routing-and-state-permalinks.md) (URL grammar)

## Context

ADR-0039 (Accepted 2026-05-24) made two micro-decisions inside its larger Slice-E architecture commit:

1. **Brand mark**: standardize the on-screen logo + page title as `Yen-Ask`.
2. **Route URL**: keep the lab mounted at `/dev/yenask` — same namespace as the runtime-failure harnesses (`/dev/duckdb-harness`, `/dev/charts-sandbox`).

Same-day user direction (2026-05-24, after PR #240 / Slice E.2 merged):

> "The display name should be Yen-Ask. Why are we not mounting /lab and using /dev — there are charts hosted on /lab/, wouldn't that be a natural home?"

This ADR records the resolution. Both micro-decisions in ADR-0039 §D-33 are now superseded by what's recorded here. ADR-0039's substantive content — the LLM-OS pipeline shape (MiniLM-L6-v2 retrieval + SmolLM2-360M extraction + deterministic compile + execute), the cosine-threshold fallback (Gregor's lock), the eval-set-as-contract condition (Andre + Hamel + Fowler lock), Slice E.1/E.2/E.3 slicing — remains in force.

## Decision

### 1. Brand mark: **Yen-Ask** (with hyphen)

The on-screen logo on the dev-only lab route uses **`Yen-Ask`** in two places:

- The `<title>` element of `frontend/src/routes/Yenask.svelte` (browser tab + history label).
- The `<h1>` mark in the same route's header.

Everywhere else the identifier `yenask` is preserved verbatim — see "Brand vs identifier separation" below.

### 2. Route placement: **`/lab/yenask`**

The lab moves from `/dev/yenask` to **`/lab/yenask`**. The reason `/lab/` is the right namespace:

- The `/lab/` namespace already houses the analyst surface (`/lab/:state/:event` = Psephlab, the per-cohort psephology workbench with charts + tables for an analyst audience). The yen-ask assistant is the **same audience** (analyst / curious citizen / researcher) hitting the **same canonical Parquet store** through a **different question shape** (free-text NL instead of pre-built panels). Same room, different chair.
- The `/dev/` namespace is reserved for runtime-failure / development harnesses (`/dev/duckdb-harness` proves DuckDB-WASM cold-start failure UX; `/dev/charts-sandbox` is a generic-renderer regression bed). These are operator-facing diagnostic surfaces, not "things that compute insights from canonical data". `/lab/yenask` describes what the page IS; `/dev/yenask` described where it WAS in the project lifecycle.
- Pattern collision check: `/lab/yenask` (2 segments) is disjoint from `/lab/:state/:event` (3 segments) under svelte-spa-router's exact-segment matcher. Route order in `frontend/src/main.ts` is not load-bearing.
- Removal contract unchanged: deleting the lab is still `git rm` of `frontend/src/routes/Yenask.svelte` + `frontend/src/lib/yenask/` + the single route entry in `frontend/src/main.ts`. The new namespace doesn't add any coupling to other `/lab/` routes (they neither import nor are imported by `lib/yenask/`).

### 3. Brand vs identifier separation (unchanged from ADR-0039 §D-33; restated for completeness)

CHANGED (citizen-facing affordances):

- `<title>` and `<h1>` strings in `frontend/src/routes/Yenask.svelte` use Yen-Ask.
- Route URL the citizen types or bookmarks (`/dev/yenask` → `/lab/yenask`).

UNCHANGED (engineering affordances):

- Library / module path: `frontend/src/lib/yenask/...`
- Svelte file name: `Yenask.svelte`
- URL slug inside the route: `/lab/yenask` keeps `yenask` as the slug
- LocalStorage keys: `yenask.model.id.v1`, `yenask.last_model.v1`, etc.
- DOM attributes: `data-route="yenask"`, all `data-testid="yenask-*"` selectors
- ADR titles ("ADR-0038: YENASK two-stage LLM pipeline — Rejected"; this ADR; etc.)
- Plan-doc filename + § titles, subsystem doc filename + headings
- Code comments and citation strings inside the codebase
- Agent persona files, commit subjects, PR titles (those carry "YENASK" as the proper noun)

The reason for the split: the brand mark is what a citizen reads on the page; the identifier is what an engineer reads in the editor. They are separately tunable. A brand rename that ripples through ~200 file paths + a localStorage migration + a redirect chain is a coordination tax with no operational benefit.

## Consequences

**Positive**:

- The lab name a citizen sees (`Yen-Ask`) matches the brand pattern they're already familiar with (`yen-gov`, the parent project).
- The route URL (`/lab/yenask`) describes WHAT THE PAGE IS, not where it is in the project lifecycle.
- `/lab/` becomes the predictable canonical namespace for "analyst surfaces that compute against the canonical store" — Psephlab, yen-ask, and any future research-grade routes (election-margins explorer, indicator-correlations workbench, etc.).
- `/dev/` cleans up to its true meaning: runtime-failure / regression harnesses for operators, never linked from the left rail.

**Negative**:

- Any existing bookmark / shared link to `/dev/yenask` 404s after this change. **Mitigation declined**: the route is dev-only, was never citizen-discoverable, was never linked from the left rail. The audience that knows the URL existed (engineers + the author) is the same audience that reads this ADR. A 301 redirect from `/dev/yenask` → `/lab/yenask` would be defensible but adds router complexity for a ~5-person audience; opt for the simple cut.
- The plan-doc `TODO/20260518-browser-governance-insight-assistant-plan.md` carried stale route and brand-standard references. **Mitigation**: handled by the same-day plan-doc surgery PR (separate commit) — the plan-doc was already due for a hard-cleanup pass per the user's direction.

**Trade-off accepted**: documentation churn (subsystem doc + AGENTS.md + size-tier.ts comment + plan-doc + ADR-0039 status line + this new ADR) in exchange for a route URL that matches what the page IS. Net positive — future agents reading `/lab/yenask` will not have to ask "why is this under /dev/?".

## Alternatives considered

### A — Keep `/dev/yenask`, rename brand only

Rejected. The user's question (*"why are we not mounting /lab — there are charts hosted on /lab/, wouldn't that be a natural home?"*) is correct and unanswered. `/dev/` was a Phase-1 placeholder when the lab's audience was "the one engineer building it"; the audience is now "analyst + curious citizen" same as Psephlab. The namespace should reflect the audience, not the build phase.

### B — Promote to a top-level `/ask` or `/yenask` route (no namespace prefix)

Rejected on two grounds. (i) Premature elevation — the lab is still dev-only, not citizen-discoverable from the left rail, and Slice E.3 (the deterministic intent-router) is parked pending evidence. Top-level routes carry a quality contract (Citizen + Hans review the answer copy, the renderer hits 6 routes for §13 smoke). The lab isn't there yet. (ii) Naming budget — top-level slugs are scarce. Reserve them for citizen-facing destinations. `/ask` is a recognisable verb and should stay free for the eventual citizen-facing version of this lab (if any).

### C — Add a `/dev/yenask` → `/lab/yenask` 301 redirect

Rejected per the "Negative" mitigation note above. Dev-only audience; not worth the router complexity. A future PR can add the redirect on ~3 lines if a real user reports a broken bookmark.

### D — Brand-rename more aggressively (e.g. lib/`yen-ask/`, file `YenAsk.svelte`, slug `/lab/yen-ask`)

Rejected on ADR-0039's identifier-separation rationale, which this ADR explicitly preserves. The brand label is for the citizen's eye; the identifier is for the engineer's editor. Conflating them creates a coordination tax (file rename → import rewrite → test selector update → localStorage migration → redirect chain) for zero operational benefit. The user's direction is specifically scoped: *"the display name should be Yen-Ask"*. Display only.

### E — `Yen-Ask` vs `YenAsk` vs `yen-ask` vs `Yen Ask`

`Yen-Ask` chosen (matches `yen-gov` parent project's kebab-style + initial-capital convention used on the citizen home page). Rejected: `YenAsk` (loses the visual mirror of `yen-gov`), `yen-ask` (lowercase reads as a code identifier), `Yen Ask` (space is a worse separator on narrow screens). `Yen-Ask` is the single in-style choice.

## Reversal cost

**Low**. Revising this ADR is two narrow grep-and-replace passes (the visible brand label and the route namespace) across the same 7 files this ADR's PR touched. The Cache Storage URL keys for downloaded models are unaffected (they encode the HuggingFace repo, not the route). localStorage keys are unaffected (none encode the route). No data migration, no schema bump, no consumer-side change beyond the bookmark-link 404 mentioned above.

If a future ADR wants to flip the brand to `YENASK` (uppercase, as the original brand) or move the route to `/ask`, this ADR is the right one to cite as the predecessor.

## Implementation slicing

This ADR ships in a single PR (the brand + route are coupled by the same user direction and have the same blast radius). The PR is ~7 file edits plus this ADR + the ADR-0039 status amendment line. No new tests required beyond updating the existing Playwright route coverage to `goto("/lab/yenask")` and `getByRole("heading", { name: /Yen-Ask/i })`.

Plan-doc cleanup (separate concern raised in the same user message) is a follow-up PR — see the post-merge plan-doc surgery PR for the prune from ~913 lines to a lean handoff stub.
