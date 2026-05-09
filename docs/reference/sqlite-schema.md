# SQLite layout: `results.sqlite`

**Last Updated**: 2026-05-09

This page is the canonical layout for the per-state `.sqlite` artifact emitted by `yen-gov run`. The design rationale (one DB per state, derived not contract, etc.) lives in [backend/emit-sqlite.md](../architecture/backend/emit-sqlite.md).

## File location

```
datasets/elections/<event>/<state>/results.sqlite
```

One file per `(event, state)` pair, written by `backend/yen_gov/emit/sqlite.py` after the JSON artifacts have been validated and persisted. Disable with `yen-gov run <event> <state> --no-sqlite`.

## Versioning

The layout is versioned via SQLite's standard `PRAGMA user_version`. The current value is **`1`**. Any change to a table, column, index, or view bumps it monotonically. The Python emitter sets the version; consumers read it on load and refuse incompatible versions.

There is **no** JSON Schema for `.sqlite` — JSON Schema doesn't describe SQL. The version → layout mapping is this document.

## Tables

### `parties`
ECI-coded parties only. Independents and NOTA never have an `eci_code` and live in `candidates` directly.

| Column       | Type    | Notes                                |
| ------------ | ------- | ------------------------------------ |
| `eci_code`   | TEXT PK | Numeric string from ECI partywise.   |
| `short_name` | TEXT NN |                                      |
| `full_name`  | TEXT    | Nullable.                            |

### `constituencies`
One row per AC.

| Column         | Type     | Notes                                  |
| -------------- | -------- | -------------------------------------- |
| `eci_no`       | INT PK   | 1-based, per-state.                    |
| `name`         | TEXT NN  | As reported by ECI; empty string if absent. |
| `votes_polled` | INTEGER  | From the per-AC totals.                |

### `candidates`
One row per candidate per AC, plus one row per AC for NOTA (`is_nota = 1`, `party_short = 'NOTA'`).

| Column                | Type     | Notes                                                              |
| --------------------- | -------- | ------------------------------------------------------------------ |
| `constituency_eci_no` | INT NN FK → `constituencies.eci_no` |                                          |
| `rank`                | INT NN   | From the JSON. NOTA gets `rank = max(candidate ranks) + 1` so the PK is unique. |
| `name`                | TEXT NN  | `"NOTA"` for NOTA rows.                                            |
| `party_eci_code`      | TEXT FK → `parties.eci_code` (nullable) | NULL for independents and NOTA.            |
| `party_short`         | TEXT NN  | For grouping in views; ECI's short label.                          |
| `votes`               | INT NN   |                                                                    |
| `vote_share_pct`      | REAL NN  | 0–100.                                                             |
| `is_winner`           | INT NN   | 1 only on the winning row per AC; 0 otherwise.                     |
| `is_nota`             | INT NN   | 1 on NOTA rows; 0 otherwise.                                       |
| **PK**                | (`constituency_eci_no`, `rank`)         |                                                |

### Indexes

- `idx_candidates_party` on `candidates(party_short)` — supports party-page queries.
- `idx_candidates_winner` on `candidates(is_winner) WHERE is_winner = 1` — partial index for "all winners" scans.

### Views

#### `party_totals`

```sql
SELECT party_short,
       COUNT(*) FILTER (WHERE is_winner = 1) AS seats_won,
       SUM(votes)                            AS votes
FROM candidates
WHERE is_nota = 0
GROUP BY party_short
ORDER BY seats_won DESC, votes DESC;
```

A test (`test_emit_party_totals_view_matches_summary`) asserts this view's seat counts match `result.summary.json` exactly. Do not "optimize" the view to use joins or filters that break that equivalence.

## What is NOT in the database

- `election` and `state` codes — encoded in the file path.
- Source provenance (URLs, fetch timestamps) — JSON-only; the SQLite file is derived.
- Top-N / "others" cutoff metadata — already applied to the JSON candidates list.
- `result.summary.json`'s alliance distributions — not yet implemented anywhere.

## Determinism

The emitter writes a fresh DB on each call, sorts all INSERTs by primary key, and uses `os.replace` for atomic publication. Two runs over identical JSON produce byte-identical `.sqlite` files; a test enforces this. PR diffs on `.sqlite` therefore signal real data changes, not emitter noise.

## See also

- [backend/emit-sqlite.md](../architecture/backend/emit-sqlite.md)
- [Reference: schemas](schemas.md) — JSON contract surfaces this file is derived from.
- [How to run the pipeline](../how-to/run-the-pipeline.md)
