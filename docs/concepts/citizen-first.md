# Citizen-First: We Work Question-First, Not Data-First

**Last Updated**: 2026-05-15

This is the doctrine that decides the order in which yen-gov's six personas (Citizen, Hans, Max, Gregor, Fowler, Jony) collaborate on any new citizen-facing feature. The procedural form lives in [`../how-to/distill.md`](../how-to/distill.md); this doc is the *why* behind that order.

## The principle

A feature begins with a citizen's question, not with a dataset that happens to be available. The pipeline starts with **Citizen** (what is being asked?) and ends with **Citizen** (did we actually answer it?). Citizen bookends the work; everything in between is in service of that question.

This inverts the historical default of "ingest dataset → figure out who cares." That default produces beautiful charts that nobody came looking for. yen-gov is a governance-transparency product for Indian citizens — its load-bearing input is an actual citizen's question, surfaced from civic curiosity ("is my state doing better than the one next door on health?"), not from data-supply.

## Why Hans precedes Max

In the older mental model, Max (Indicator Scout) went first — scout the data, then frame it. We invert that: **Hans (Governance) frames the question first, then Max scouts the source that honestly answers the framed question.** The reason is that the framing decides what would *count* as an answer. Without Hans's framing pass, Max can scout a perfectly authoritative dataset that answers the wrong question — e.g. "GST collected by state" looks like a state-performance metric but is actually a measure of where consumption was billed (Roy's standing rule). Framing first protects against authoritative-but-misleading acquisition.

Max remains *upstream* of the engineering personas (Gregor, Fowler) — he still answers "what indicator should we acquire and from where?" — but he is now downstream of Hans, not upstream.

## The full order

1. **Citizen** — *what question is being asked? what decision does it inform?* Problem definition in plain language.
2. **Hans** — *given that question, what indicator(s) in the Indian fiscal-federal context would honestly answer it? what's the framing trap?* Framing memo.
3. **Max** — *which upstream sources can support that framing? are they comparable across years and states?* Source memo with acquisition recommendation.
4. **Gregor** — *schema and contract for the chosen indicator(s).* Contract proposal.
5. **Fowler** — *ingest adapter, fixtures, tests, small commits.* Implementation.
6. **Jony** — *how it surfaces in the UI (legend, color ramp, comparison view).* UI spec.
7. **Citizen** *(again)* — *does the page actually answer the question from step 1?* Comprehension check.

The Citizen step is intentionally repeated. The opening Citizen pass is the *brief*; the closing Citizen pass is the *audit*. Skipping either is a doctrinal violation.

## What failure looks like when this is violated

- **Skip step 1 (Citizen at start).** "We have NCRB data, what should we do with it?" → produces a crime-by-state choropleth that no citizen came looking for, with framing traps Hans would have caught (population denominator? reporting-rate confound? state-police-data discretion?).
- **Run Max before Hans.** Max scouts an authoritative source; Hans is then asked to frame what was already acquired and either has to defend a poor framing or send Max back to re-scout. Wasted acquisition cycle.
- **Skip step 7 (Citizen at end).** Page ships, builds clean, schema validates, tests pass — and the citizen who clicked the WhatsApp link still can't figure out whether their state is doing well. The *engineering* loop closed; the *product* loop didn't.

## What's not in scope for this doctrine

- Internal pipeline / infrastructure / schema-only / tooling changes. These don't have a citizen-question shape and don't need to run the full loop. They still honour `CLAUDE.md` Holy Laws and the rest of the engineering contract.
- Bug fixes inside an existing citizen feature. Those need step 7 (does the fix actually fix the citizen-visible problem?) but rarely the full loop.

> **Doctrine note.** Citizen-first ordering and the no-implementation-disclosure rule survive storage changes. Public copy stops naming storage formats, query engines, internal paths, or boundary-check mechanisms; the rule is independent of the current data-store implementation.

## Design rationale

This section folds in the receipt from the originating ADR that pinned the no-implementation-disclosure rule for this concept. The redirect map lives in [decision-index.md](../reference/decision-index.md). The verbatim rejected alternatives live under [Rejected alternatives](#rejected-alternatives).

### ADR-0021: no-implementation-disclosure-on-public-pages

**Context.** The first version of the `/explore` (Data Explorer) page proudly described its own plumbing to every visitor: "Browser SQL via `sql.js` over `results.sqlite` for event AcGenMay2026"; "Loading SQLite database..."; "Safety: Read-only mode is enforced - only one `SELECT`/`WITH` statement per run; `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, `PRAGMA` etc. are blocked client-side. Even without that, the database is an in-memory copy in your tab - there is no server-side database to corrupt." Two distinct mistakes are bundled in there: (1) implementation tour - naming `sql.js`, `wasm`, `results.sqlite`, `lib/explore/sqlGuard.ts`, the (since-retired) doc path `docs/reference/sqlite-schema.md`, and the exact set of blocked keywords tells a casual visitor things they neither asked for nor benefit from; (2) security-boundary disclosure - stating what is enforced and where it is enforced is, in security terms, free reconnaissance for anyone who wants to probe the boundary. It also frames the product around what it refuses to do, not what it does. Neither addition makes the system more secure. The sqlGuard keyword check, the in-memory database, and the absence of a backend are all true and they all stand on their own. Saying so on the page does not strengthen them; it only narrates them. If the implementation later changes, every public page that mentioned the old shape becomes a lie that must be hunted down and rewritten.

**Decision.** Public-facing UI must not disclose the system's implementation choices, internal file paths, or the shape of its security boundary. Concretely, the following do not appear in any user-visible string in `frontend/src/routes/**` or any rendered content the deployed site shows: library / runtime names (`sql.js`, `sqlite-wasm`, `wasm`, `WASM`, `SQLite` as a brand the user is told about, `d3`, `maplibre`, framework names beyond what's in the page chrome / About credits); internal file paths (anything under `lib/`, `docs/`, `datasets/`, `backend/`, schema filenames, etc.); enumerations of blocked / allowed operations framed as a security control ("Read-only mode is enforced - `INSERT`, `UPDATE`, ... are blocked"); statements about what cannot be attacked, corrupted, or written to; statements about where a check runs (client-side vs. server-side). What replaces them is a plain description of what the surface does for the user. For the Data Explorer: "Ad-hoc queries against this state's results." "Only `SELECT` / `WITH` queries are supported." The first sentence is the value. The second is functional guidance the user needs to write a working query - it is not framed as a security stance and does not enumerate the rejected operations. Error messages follow the same rule. The `sqlGuard.validateSql` rejection reason is "`INSERT` is not supported here." rather than "Read-only mode: `INSERT` is not allowed." This is not security-through-obscurity dressed up as policy. The actual controls (no backend, no shared state, in-memory per-tab database, keyword guard, single-statement guard) remain exactly as before. We just stop narrating them on the public surface.

**Where the documentation does live.** Internally - and only internally - we are explicit: what is supported / not supported in the Data Explorer is documented in [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) (the canonical store that replaced the per-state SQLite shards) and in source comments; why the keyword guard exists (typo defence, not a hardened sandbox) is in the source comment at the top of `sqlGuard.ts`; the static-bundle / no-production-backend stance is the first Holy Law in [CLAUDE.md](../../CLAUDE.md) and is captured in the deployment architecture doc. These are operator / contributor concerns. The visitor reading `/<state>/explore` does not need them.

**Scope and what is NOT changed.** Two adjacent things are explicitly not in scope: (1) Privacy promises to the user - the About page says "no advertising, no analytics, no user accounts, and no data collected from you. The whole site is a static bundle served from GitHub Pages." That is a commitment to the user about their data, not a description of our security posture. It stays. (2) Source code comments and internal docs - comments in `frontend/src/**`, `backend/yen_gov/**`, `docs/**`, and `tools/**` are written for contributors. They should be as candid and detailed as ever.

**Consequences (good).** Public pages survive implementation changes without rewrites. The product reads as what it does, not as a list of what it forbids. Less material for a hostile reader to map the system from. **Consequences (bad / costs).** Slightly more discipline at PR review: any user-visible string that names a library, internal path, or "X is blocked" formulation must be flagged. A grep for `sql.js|wasm|sqlite|read-only|client-side|in-memory` (and any new storage-format names the project adopts) under `frontend/src/routes/**` and any Svelte template content is the cheap recurring check. Contributors must remember the rule applies to rendered content and user-visible error messages, not to source comments - which historically is where the same wording came from.

## Rejected alternatives

This section preserves the rejected-alternatives receipts for the ADR whose rationale is folded above. The subsection is anchored as `#adr-NNNN-rejected-alternatives` for the redirect index.

### ADR-0021 rejected alternatives

Verbatim from the originating ADR. Append-only receipt.

- **Keep the disclosures, on transparency grounds.** Rejected: transparency to a curious citizen is well-served by the public GitHub repo and the About page. The `/explore` header is not the right surface for it.
- **Move the disclosures to a dedicated /security or /how-it-works page.** Rejected for now: it would just relocate the same boundary-mapping content. If we ever want a public engineering write-up, it lives in the repo's docs, not in the deployed app.

## See also

- [`../how-to/distill.md`](../how-to/distill.md) — the seven-step procedure with artifact per step.
- [`../agents/bootstrap.md`](../agents/bootstrap.md) — what each persona loads before contributing to the loop.
- [`../agents/guardrails.md`](../agents/guardrails.md) — the rules that constrain every step.
- [`../../CLAUDE.md`](../../CLAUDE.md) — the engineering contract.
