# boundaries_sot/

Per-state AC-name source-of-truth (SoT) files consumed by:

- `tools/boundaries/snapshot.py::apply_ac_no_rewrite_by_name` (reads via the
  `sot_ref` field in `tools/boundaries/pipeline.json`; one production
  `sot_ref` for S01 today, with `delimitation_warning` strings naming S03).
- `tools/boundaries/verify_ac_parity.py::load_sot` (the Tier-A `verify_state`
  parity gate, run for 10 D.2-promotion states via
  `backend/tests/test_ac_parity_per_state.py`).
- `frontend/src/lib/data.ts::fetchConstituencies` (renders the per-state AC
  list on `/s/<state>` via `StateOverview.svelte`).

## Provenance

Moved here from `datasets/reference/in/states/<S>/constituencies.json` on
2026-06-08 when the `datasets/reference/` tier was fully retired (plan
[TODO/20260603-data-and-charting-platform-reset-plan.md](../../../../TODO/20260603-data-and-charting-platform-reset-plan.md)
section 9). Option D (move to `data/entities/`) was chosen over Option C
(`_ops/`) because the data has a citizen-facing consumer (`fetchConstituencies`
above) and per CLAUDE.md section 3 `_ops/` is operator-only / not citizen-facing
\u2014 citizen-facing data lives under `data/`.

This mirrors the G8-finish (2026-06-08) precedent that moved the LGD-snapshot
masters from `datasets/reference/lgd/*.csv` into `datasets/data/entities/lgd/`.

## Schema

Each file declares `$schema = "https://yen-gov.github.io/schemas/constituency.schema.json"`
and `$schema_version` against
[`datasets/schemas/constituency.schema.json`](../../../schemas/constituency.schema.json)
(currently v4.2; files emit v4.1 per the json-corpus compatibility window in
[`datasets/schema-compatibility.json`](../../../schema-compatibility.json)).

The contract test
[`frontend/src/contracts/datasets-conform.test.ts`](../../../../frontend/src/contracts/datasets-conform.test.ts)
resolves the `$schema` URL by basename against the loaded schema registry, so
the move did not require any rewrites inside the 31 JSON bodies; the `git mv`
preserved them byte-identical.

## Deferred work: fold into canonical `electoral.csv`

The canonical entity catalogue at `datasets/data/entities/electoral.csv` is
the long-term home for AC identity (`entity_kind in {ac, pc}`, `delim_year`,
`state` FK, `reservation`). The deferred audit (recorded in the plan-doc and
in [CLAUDE.md section 3](../../../../CLAUDE.md)) found that as of 2026-06-08:

- ONLY S08 Himachal Pradesh has a perfect `(eci_no, name)` match for 68/68
  ACs between `constituencies.json` and `electoral.csv`.
- 30 of 31 states have name-set mismatches against `electoral.csv` because
  the canonical store currently keys on `delim_year=2008` only (the post-2014
  AP+TG bifurcation, the post-2023 Assam re-delim, etc. are not yet modelled).
- The `reservation` column is `None` for ALL 4189 AC rows in `electoral.csv`
  because the LGD-snapshot writer left it `None` in v1.

Folding `constituencies.json` data into `electoral.csv` therefore requires
(a) extending the schema to model multiple delimitation cycles, (b) back-filling
`reservation`, and (c) repointing the 3 SoT-consumer call sites (snapshot.py,
verify_ac_parity.py, fetchConstituencies). That is structural work owned by
Hans + Max per [CLAUDE.md section 0a](../../../../CLAUDE.md) and is intentionally
deferred to a future PR; until then, this subdirectory is the SoT.
