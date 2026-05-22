# `datasets/_ops/` — Operator state

This directory holds operational assets that are NOT citizen-facing
fact tables and NOT contract surfaces with their own JSON Schema.

Rules:

- Files under `_ops/` are NOT inventoried by the admin Inventory panel
  (`backend/yen_gov/admin/inventory.py:_SKIP_DIR_PREFIXES`).
- JSON files under `_ops/` are NOT auto-exempt from Tier-B validator
  rules — if you add a JSON contract here it MUST carry `$schema` like
  any other contract surface. The current contents are non-JSON
  (Parquet); this rule applies only when JSON appears in the future.
- This is the home for files that genuinely live forever as part of the
  deployed canonical store but are operational rather than analytical
  (e.g. probe assets, operator overlays). Compare with `.runtime/`
  (CLAUDE.md §2), which is ephemeral and gitignored — `_ops/` is
  committed, `.runtime/` is not.

Current residents:

| File                       | Purpose                                                                                                                                                                                                                                  |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `range-mime-probe.parquet` | 363-byte Parquet operational asset used by the deploy workflow to verify GitHub Pages serves the correct MIME type and honours the HTTP `Range` header for byte-range Parquet fetches. See `docs/architecture/deployment.md` for context. |

History: relocated here by T.1 (TODO/20260517 §0e.7) from the previous
`datasets/_test/` subtree, which was renamed and re-scoped — see the
git log on this directory or the T.1 commit for the migration plan.

Future planned residents (subject to the Hans + Max + Gregor canonical
indicator-contract panel that follows T.1; see plan §0e.7 T.3):

- `indicators-operator-state.json` (currently at
  `datasets/reference/in/indicators-operator-state.json`) — the
  hand-edited sparse overlay listing `frozen` / `refetch_requested` /
  `unavailable_periods` flags per indicator. Will migrate here once
  the panel decides whether it stays JSON or moves into a Parquet
  column on `taxonomy/indicators.parquet`.
