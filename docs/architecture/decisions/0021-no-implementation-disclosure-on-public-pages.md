# ADR-0021: No implementation or security-boundary disclosure on public pages

**Last Updated**: 2026-05-11
**Status**: accepted

## Context

The first version of the `/explore` (Data Explorer) page proudly described
its own plumbing to every visitor:

> "Browser SQL via `sql.js` over `results.sqlite` for event AcGenMay2026."
> "Loading SQLite database…"
> "Safety: Read-only mode is enforced — only one `SELECT`/`WITH` statement per
> run; `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, `PRAGMA` etc.
> are blocked client-side. Even without that, the database is an in-memory copy
> in your tab — there is no server-side database to corrupt."

Two distinct mistakes are bundled in there:

1. **Implementation tour.** Naming `sql.js`, `wasm`, `results.sqlite`,
   `lib/explore/sqlGuard.ts`, the (since-retired) doc path `docs/reference/sqlite-schema.md`,
   and the exact set of blocked keywords tells a casual visitor things they
   neither asked for nor benefit from.
2. **Security-boundary disclosure.** Stating *what is enforced and where it
   is enforced* is, in security terms, free reconnaissance for anyone who
   wants to probe the boundary. It also frames the product around what it
   refuses to do, not what it does.

Neither addition makes the system more secure. The `sqlGuard` keyword check,
the in-memory database, and the absence of a backend are all true and they
all stand on their own. Saying so on the page does not strengthen them; it
only narrates them. If the implementation later changes (e.g. we move from
`sql.js` to another engine, or we add a server-side endpoint for federated
queries), every public page that mentioned the old shape becomes a lie that
must be hunted down and rewritten.

## Decision

**Public-facing UI must not disclose the system's implementation choices,
internal file paths, or the shape of its security boundary.**

Concretely, the following do not appear in any user-visible string in
`frontend/src/routes/**` or any rendered content the deployed site shows:

- Library / runtime names: `sql.js`, `sqlite-wasm`, `wasm`, `WASM`,
  `SQLite` (as a brand the user is told about), `d3`, `maplibre`,
  framework names beyond what's in the page chrome / About credits.
- Internal file paths: anything under `lib/`, `docs/`, `datasets/`,
  `backend/`, schema filenames, etc.
- Enumerations of blocked / allowed operations framed as a security control
  ("Read-only mode is enforced — `INSERT`, `UPDATE`, … are blocked").
- Statements about what cannot be attacked, corrupted, or written to.
- Statements about *where* a check runs (client-side vs. server-side).

What replaces them is a plain description of what the surface **does** for
the user. For the Data Explorer:

> "Ad-hoc queries against this state's results."
> "Only `SELECT` / `WITH` queries are supported."

The first sentence is the value. The second is functional guidance the user
needs to write a working query — it is not framed as a security stance and
does not enumerate the rejected operations.

Error messages follow the same rule. The `sqlGuard.validateSql` rejection
reason is `` `INSERT` is not supported here. `` rather than
`` Read-only mode: `INSERT` is not allowed. ``.

This is not security-through-obscurity dressed up as policy. The actual
controls (no backend, no shared state, in-memory per-tab database, keyword
guard, single-statement guard) remain exactly as before. We just stop
narrating them on the public surface.

## Where the documentation *does* live

Internally — and only internally — we are explicit:

- **What is supported / not supported** in the Data Explorer:
  documented in [docs/architecture/data/canonical-store.md](../data/canonical-store.md)
  (the Parquet + DuckDB-WASM store that replaced the per-state SQLite shards) and in source comments in
  [`frontend/src/lib/explore/sqlGuard.ts`](../../../frontend/src/lib/explore/sqlGuard.ts)
  and [ADR-0017](0017-explore-page-uses-sql-js.md) (engine choice; superseded by ADR-0030).
- **Why the keyword guard exists** (typo defence, not a hardened
  sandbox) is in the source comment at the top of `sqlGuard.ts`.
- **The static-bundle / no-production-backend stance** is the first Holy
  Law in [`CLAUDE.md`](../../../CLAUDE.md#1-holy-laws-read-first-every-session)
  and is captured in [docs/architecture/deployment.md](../deployment.md).

These are operator/contributor concerns. The visitor reading
`/tn/explore` does not need them.

## Scope and what is *not* changed by this ADR

Two adjacent things are explicitly **not** in scope:

1. **Privacy promises to the user.** The About page says "no advertising,
   no analytics, no user accounts, and no data collected from you. The
   whole site is a static bundle served from GitHub Pages." That is a
   commitment to the user about *their* data, not a description of our
   security posture. It stays.
2. **Source code comments and internal docs.** Comments in
   `frontend/src/**`, `backend/yen_gov/**`, `docs/**`, and
   `tools/**` are written for contributors. They should be as candid and
   detailed as ever.

## Consequences

**Good**

- Public pages survive implementation changes without rewrites.
- The product reads as what it does, not as a list of what it forbids.
- Less material for a hostile reader to map the system from.

**Bad / costs**

- Slightly more discipline at PR review: any user-visible string that
  names a library, internal path, or "X is blocked" formulation must be
  flagged. A grep for `sql.js|wasm|sqlite|read-only|client-side|in-memory`
  under `frontend/src/routes/**` and any Svelte template content is the
  cheap recurring check.
- Contributors must remember the rule applies to **rendered** content and
  user-visible error messages, not to source comments — which historically
  is where the same wording came from.

## Alternatives considered

- **Keep the disclosures, on transparency grounds.** Rejected: transparency
  to a curious citizen is well-served by the public GitHub repo and the
  About page. The `/explore` header is not the right surface for it.
- **Move the disclosures to a dedicated /security or /how-it-works page.**
  Rejected for now: it would just relocate the same boundary-mapping
  content. If we ever want a public engineering write-up, it lives in the
  repo's docs, not in the deployed app.

## See also

- [ADR-0017](0017-explore-page-uses-sql-js.md) — engine choice for the
  Data Explorer (the internal "what / why").
- [`CLAUDE.md`](../../../CLAUDE.md) Holy Law #1 — static-first production.
- [`frontend/src/lib/explore/sqlGuard.ts`](../../../frontend/src/lib/explore/sqlGuard.ts)
  — the actual guard, with its rationale in the file header.
