# ADR-0014: SQLite emitter — derived per-state artifact

**Last Updated**: 2026-05-19
**Status**: superseded (by [ADR-0030 — canonical store on DuckDB-WASM + Parquet](0030-canonical-store-duckdb-wasm.md), 2026-05-19)

> **Superseded 2026-05-19 (PR-R.3, TODO row `1.8e`).** The per-state `datasets/elections/<event>/<state>/results.sqlite` artifact, the `backend/yen_gov/emit/sqlite.py` emitter, and the matching frontend reader (`frontend/src/lib/sql.ts` over sql.js) have all been deleted. Researcher SQL now runs against the canonical Parquet store via DuckDB-WASM on `/explore` (or against the public Parquet URLs with any DuckDB client). See [canonical-store.md \u00a71.1](../data/canonical-store.md) and the deletion manifest row 1.8e in [canonical-pivot-deletion-manifest.md](../canonical-pivot-deletion-manifest.md). The body below is preserved as the audit trail for the original 2026-05-09 decision.

## Context

The locked PLAN.md decision (2026-05-08) declared SQLite a *derived secondary artifact* built from the same validated JSON records, intended for cross-cutting queries on a future `/explore` page (lazy-loading `sqlite-wasm`). Phase 2 deferred the emitter; Phase 5 picks it up.

Open questions to settle before writing code:

1. **One DB or many?** A single `all.sqlite` covering every event/state, or one DB per `(event, state)`?
2. **Contract surface or convenience?** Does the SQLite file need a JSON Schema and `x-version`?
3. **Regenerate or commit?** Is the `.sqlite` committed to git like the JSON, or built by CI from JSON before deploy?
4. **Where does the emitter live?** A new `pipeline/` step, or its own subpackage?
5. **Auto-emit on `yen-gov run`, or a separate command?**

## Decision

1. **One `.sqlite` per event/state.** Path: `datasets/elections/<event>/<state>/results.sqlite`. Mirrors the JSON layout exactly so a downstream consumer doesn't need to know two layouts. Cross-state queries are the consumer's job (attach multiple databases or merge in a build step).

2. **Derived, not a contract.** No JSON Schema; no `x-version`/`x-changelog`. The SQLite *layout* (table names, column types, view definitions) is documented in `docs/reference/sqlite-schema.md` and versioned via `PRAGMA user_version` (integer; bumped on any layout change). The validator ignores `.sqlite` files (Tier B is JSON-only by §11).

3. **Commit the `.sqlite`.** Reasons:
   - Symmetric to the JSON: both ship together, both are byte-for-byte reproducible from upstream.
   - The deploy step (ADR-0013) already does `cp -r datasets _site/data`. Adding a regeneration step in `deploy-site.yml` would couple deploy to a Python install, defeating the simplicity of pure file staging.
   - A 234-row state DB is ~200 kB; even the full 36-state corpus would be a few MB, well within git's comfort zone.
   - Reviewers see the data diff in the maintainer's data-refresh PR; the `.sqlite` diff is opaque but the JSON diff next to it is not. Combined, the PR is auditable.

4. **New subpackage `backend/yen_gov/emit/`.** Reads validated JSON from `datasets/elections/<event>/<state>/`, writes the `.sqlite` next to it. Does NOT import from `pipeline/` — the emitter is a *projection* of the canonical JSON, not a step in the fetch/parse/validate chain. This keeps the dependency direction one-way (`pipeline` → `core`; `emit` → `core`; `emit` reads what `pipeline` wrote, via the filesystem contract). A failure in the emitter must not block JSON emission.

5. **Auto-emit by default; `--no-sqlite` to skip.** Consistent with the principle that the canonical artifacts are produced by one command. The flag exists so that JSON-only iterations during parser development don't pay the emit cost.

## Layout (informative; canonical doc is `docs/reference/sqlite-schema.md`)

> **Update 2026-05-10:** Column names were renamed to follow [ADR-0019](0019-dataset-topology-and-column-discipline.md): the per-state ECI Assembly Constituency number is now `ac_eci_no` in both tables (was `eci_no` / `constituency_eci_no`). `PRAGMA user_version` is now `2`. The DDL below reflects v2.

```sql
PRAGMA user_version = 2;

CREATE TABLE parties (
  eci_code   TEXT PRIMARY KEY,        -- nullable parties (independents) live in candidates only
  short_name TEXT NOT NULL,
  full_name  TEXT
);

CREATE TABLE constituencies (
  ac_eci_no    INTEGER PRIMARY KEY,   -- per-state AC number; canonical name (ADR-0019)
  name         TEXT NOT NULL,
  votes_polled INTEGER
);

CREATE TABLE candidates (
  ac_eci_no      INTEGER NOT NULL REFERENCES constituencies(ac_eci_no),
  rank           INTEGER NOT NULL,
  name           TEXT NOT NULL,
  party_eci_code TEXT REFERENCES parties(eci_code),  -- NULL for independents / NOTA
  party_short    TEXT NOT NULL,
  votes          INTEGER NOT NULL,
  vote_share_pct REAL    NOT NULL,
  is_winner      INTEGER NOT NULL DEFAULT 0,         -- 1 only on the winning row per AC
  is_nota        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (ac_eci_no, rank)
);

CREATE INDEX idx_candidates_party       ON candidates(party_short);
CREATE INDEX idx_candidates_winner      ON candidates(is_winner) WHERE is_winner = 1;

CREATE VIEW party_totals AS
  SELECT party_short,
         COUNT(*) FILTER (WHERE is_winner = 1) AS seats_won,
         SUM(votes)                            AS votes
  FROM candidates
  WHERE is_nota = 0
  GROUP BY party_short
  ORDER BY seats_won DESC, votes DESC;
```

The `election` and `state` codes are NOT stored as columns: the file path encodes them, and a single-state DB has only one value each. If we later move to a multi-state DB we revisit.

## Consequences

- The `.sqlite` is byte-stable across runs of the same JSON inputs. Tests assert this so PR diffs only appear when JSON changed.
- `sqlite3` is stdlib — no new dependency.
- `frontend/` gains an option to `fetch('/data/elections/<event>/<state>/results.sqlite')` and load it via `sqlite-wasm`. The current State Overview page does NOT use the SQLite path; only the future `/explore` page will.
- A schema layout change requires bumping `PRAGMA user_version` and updating `docs/reference/sqlite-schema.md` in the same commit. Consumers (the `/explore` page) check `user_version` on load and refuse to render older layouts.
- Git diffs on `.sqlite` are opaque. PR reviewers rely on the side-by-side JSON diff for audit.

## Alternatives considered

- **Single `all.sqlite` covering every event/state**: rejected. Forces all consumers to download the full corpus to query one state, contradicts the per-state lazy-load story for `/explore`. Cross-state aggregation can `ATTACH` multiple DBs.
- **Treat SQLite as a contract surface (JSON Schema + `x-version`)**: rejected. JSON Schema doesn't describe SQL — the natural versioning surface is `PRAGMA user_version`. A duplicate "schema-of-the-schema" adds maintenance with no consumer benefit.
- **Regenerate `.sqlite` in `deploy-site.yml` from committed JSON**: rejected. Couples deploy to a Python install, makes the deploy artifact non-reproducible from a checkout, and slows the deploy. Marginal disk savings (a few MB) don't justify it.
- **Emitter as a step in `pipeline/run.py`**: rejected. The emitter is a projection of validated JSON, not part of the fetch/parse/compose chain. Keeping it in a sibling `emit/` subpackage means a parser regression doesn't break the SQLite path and vice versa.

## See also

- [Phase 5 plan in TODO/PLAN.md](../../../TODO/PLAN.md)
- [docs/reference/sqlite-schema.md](../../reference/sqlite-schema.md)
- [ADR-0013: Production data placement](0013-prod-data-placement.md)
