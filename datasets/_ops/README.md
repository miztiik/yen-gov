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

| File | Purpose |
| --- | --- |
| `indicators-completeness.json` | Generated per-indicator completeness index emitted by [`tools/emit_indicators_completeness_index.py`](../../tools/emit_indicators_completeness_index.py) and consumed by the admin Indicators panel ([`admin/src/routes/Indicators.svelte`](../../admin/src/routes/Indicators.svelte)). Operator bookkeeping (status / observed counts / staleness), not citizen-facing fact data. Schema: [`indicators-completeness.schema.json`](../schemas/indicators-completeness.schema.json) v2.0. Moved here from `datasets/reference/in/` by G8 (2026-06-08) per plan-doc section 9. |
| `indicators-operator-state.json` | Hand-edited sparse overlay listing per-indicator operator flags (`frozen`, `refetch_requested`, `unavailable_periods`). The ONE writable knob for operators on the inventory pipeline. Schema: [`indicators-operator-state.schema.json`](../schemas/indicators-operator-state.schema.json) v1.0. Moved here from `datasets/reference/in/` by G8 (2026-06-08) per plan-doc section 9. |
| `meadow-shard-contract.txt` | Sorted allowlist of the legacy per-indicator JSON shards under `datasets/indicators/in/` (pre-canonical-pivot artifacts). Input to the Tier-B validator check `tier_b_meadow_shard_contract` in `backend/yen_gov/validate.py` - see `docs/architecture/backend/validator.md`. Per CLAUDE.md section 10, no new shards may be added; this file enforces the doctrine. Retires when the legacy shard tree is empty and the validator check is deleted in the same PR. |
| `unk-ledger-2026-06-12.csv` + `.md` | Per-bucket worklist of every publisher label still resolving to `parties.IN.UNK` after the PR-Q8 TCPD per-party catalogue re-run (2026-06-12). One row per `(body, state_slug, year, event_id, publisher_label)` carrying TCPD-side recognition context (`Party_Name` / `Party_Type` / start-last year window) when available + the correlator's `skip_reason` + a `next_lookup_source` hint. Emitted by [`tools/emit_unk_ledger`](../../tools/emit_unk_ledger); the `.md` companion is the doctrine + summary. No JSON Schema (operator worklist, not a contract surface). |

(`range-mime-probe.parquet` retired in B4-pt2.4 (2026-06-06) — the Pages
MIME / Range contract is now smoke-tested via `election_results.parquet`
in `.github/workflows/deploy-site.yml`; the dedicated probe asset had
zero workflow consumers.)

History: relocated here from the previous `datasets/_test/` subtree, which was
renamed and re-scoped. Use `git log -- datasets/_ops/` for the migration
receipt.

The two `indicators-*.json` files moved in by G8 (2026-06-08) as part of
the mechanical `datasets/reference/` reshape (the
reference tier folds into `data/entities/` for citizen-facing reference
data + `_ops/` for operator bookkeeping). The 31 hand-authored
`datasets/reference/in/states/S##/constituencies.json` curator inputs
were moved to `datasets/data/entities/boundaries_sot/<S##>/constituencies.json`
on 2026-06-08 (Option D - citizen-facing per CLAUDE.md §3), closing the
`reference/` tier retire arc. See `datasets/data/entities/boundaries_sot/README.md`
for the per-state SoT operator notes.
