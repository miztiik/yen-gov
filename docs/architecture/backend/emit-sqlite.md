# Backend `emit/` — SQLite Emitter

**Last Updated**: 2026-05-10

`backend/yen_gov/emit/` writes the per-state `results.sqlite` artifact next to each `result.summary.json`. SQLite is a **derived secondary artifact** built from the same validated JSON records, intended for cross-cutting queries on the [`/explore`](../frontend/data-loading.md#the-explore-page-uses-sqljs) page. It is **not a contract surface** — no JSON Schema, no `x-version`/`x-changelog`. The layout is documented in [`docs/reference/sqlite-schema.md`](../../reference/sqlite-schema.md) and versioned via `PRAGMA user_version`. Column names follow [ADR-0019](../decisions/0019-dataset-topology-and-column-discipline.md) (canonical: `ac_eci_no`, `state_eci_code`, `district_lgd_code`, `year`).

## Decisions in one screen

1. **One `.sqlite` per event/state.** Path: `datasets/elections/<event>/<state>/results.sqlite`. Mirrors the JSON layout exactly.
2. **Derived, not a contract.** No JSON Schema; layout versioned via `PRAGMA user_version` (integer; bumped on any layout change). The Tier-B validator ignores `.sqlite` files.
3. **Committed to git.** Reasons:
   - Symmetric to the JSON: both ship together, both are byte-for-byte reproducible from upstream.
   - The deploy step ([prod data placement](../frontend/data-loading.md#production-placement)) already does `cp -r datasets _site/data`. Adding a regeneration step in `site.yml` would couple deploy to a Python install.
   - A 234-row state DB is ~200 kB; even the full 36-state corpus is a few MB.
   - Reviewers see the JSON diff next to the opaque `.sqlite` diff in the maintainer's data-refresh PR. Combined, the PR is auditable.
4. **New subpackage `backend/yen_gov/emit/`.** Reads validated JSON from `datasets/elections/<event>/<state>/`, writes the `.sqlite` next to it. Does NOT import from `pipeline/` — the emitter is a *projection* of the canonical JSON, not a step in the fetch/parse/validate chain. A failure in the emitter must not block JSON emission.
5. **Auto-emit by default; `--no-sqlite` to skip.** Consistent with the principle that the canonical artifacts are produced by one command.

## Layout (informative; canonical doc is [`docs/reference/sqlite-schema.md`](../../reference/sqlite-schema.md))

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

## Design rationale

- **Per-state, byte-stable.** The `.sqlite` is byte-stable across runs of the same JSON inputs. Tests assert this so PR diffs only appear when JSON changed.
- **No new dependency.** `sqlite3` is stdlib.
- **Lazy-loaded by the frontend.** `frontend/` gains an option to `fetch('/data/elections/<event>/<state>/results.sqlite')` and load it via `sql.js` ([see frontend/data-loading.md](../frontend/data-loading.md#the-explore-page-uses-sqljs)). The current State Overview page does NOT use the SQLite path; only the future `/explore` page will.
- **Layout changes are explicit.** Bumping `PRAGMA user_version` and updating `docs/reference/sqlite-schema.md` go in the same commit. Consumers (the `/explore` page) check `user_version` on load and refuse to render older layouts.
- **Opaque diffs are tolerable.** PR reviewers rely on the side-by-side JSON diff for audit.

## Alternatives considered

- **Single `all.sqlite` covering every event/state.** Rejected: forces all consumers to download the full corpus to query one state, contradicts the per-state lazy-load story for `/explore`. Cross-state aggregation can `ATTACH` multiple DBs.
- **Treat SQLite as a contract surface (JSON Schema + `x-version`).** Rejected: JSON Schema doesn't describe SQL — the natural versioning surface is `PRAGMA user_version`. A duplicate "schema-of-the-schema" adds maintenance with no consumer benefit.
- **Regenerate `.sqlite` in `site.yml` from committed JSON.** Rejected: couples deploy to a Python install, makes the deploy artifact non-reproducible from a checkout, and slows the deploy. Marginal disk savings (a few MB) don't justify it.
- **Emitter as a step in `pipeline/run.py`.** Rejected: the emitter is a projection of validated JSON, not part of the fetch/parse/compose chain. Keeping it in a sibling `emit/` subpackage means a parser regression doesn't break the SQLite path and vice versa.

## See also

- [Backend overview](overview.md), [Pipeline orchestration](pipeline.md)
- [`docs/reference/sqlite-schema.md`](../../reference/sqlite-schema.md) — canonical layout.
- [Frontend data loading](../frontend/data-loading.md) — `/explore` page consumes this artifact.
