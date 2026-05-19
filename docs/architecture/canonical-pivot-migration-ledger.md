# Canonical-pivot migration ledger

**Last Updated**: 2026-05-18
**Status**: Phase 0 step 0.5 deliverable. **Read alongside the [deletion manifest](canonical-pivot-deletion-manifest.md).** This doc covers data artifacts (110 socio-economic indicators + 27 elections); the deletion manifest covers files, modules, and concepts.
**Owner**: Max (indicator decisions); Hans (governance framing).
**THE PLAN**: [`TODO/20260517-canonical-long-format-pivot.md`](../../TODO/20260517-canonical-long-format-pivot.md). On conflict, THE PLAN wins; update this ledger.
**Data file**: [`canonical-pivot-migration-ledger.csv`](canonical-pivot-migration-ledger.csv) — the actual ledger; this doc is its explainer.

---

## §0. Why this exists

Per D24 in THE PLAN: every pre-pivot artifact gets an up-front decision before `_old/` can be deleted (D14 checklist gate). Silent catalogue loss is not acceptable — rip-and-replace (D13) only works if "what we are replacing it with" is recorded for every existing thing.

This ledger is the contract for Phase 1.8 deletion. Empty `target_phase` or unresolved `queue` rows BLOCK deletion. Discovery → Decision → Deletion, in that order.

---

## §1. Scope

| Family | Count | Source |
| --- | --- | --- |
| Elections (election_id directories) | 27 | `datasets/elections/AcGen*/` |
| Indicators (per-shard JSON) | 110 | `datasets/indicators/in/<topic>/*.json` |
| **Total ledger rows** | **137** | |

Topic breakdown of the 110 indicators: demography 3, economy 20, energy 41, environment 8, fiscal 22, health 6, human_development 1, prices 7, transport 2.

Out of scope (per R25 + §0c):
- `datasets/boundaries/` — sibling family, never moves.
- `datasets/taxonomy/` — canonical store itself.
- `datasets/schemas/` — schemas, including legacy.
- `datasets/manifest.json` — control plane.
- `datasets/people/`, `datasets/governments/`, `datasets/events/`, `datasets/features/`, `datasets/reference/` — separate ledger entries when those families are scheduled.

---

## §2. Ledger format

The CSV uses `#`-prefixed comment lines (skip when parsing). Columns:

| Column | Meaning |
| --- | --- |
| `legacy_path` | Current path under `datasets/` (pre-pivot). |
| `topic_or_family` | Destination canonical family. |
| `status` | `migrate` / `consolidate` / `drop` / `queue` (see §3). |
| `target_phase` | Phase in which the migrate/consolidate ingest lands. `queue` rows carry the phase before which Max + Hans must revisit. |
| `replacement_indicator_id` | Canonical id per [D30 naming convention](data/canonical-store.md#7-indicator-naming-convention-d30). Empty for `drop` / `queue`. |
| `replacement_facet_values` | JSON literal of `dimension_values` when `status=consolidate`. Empty otherwise. |
| `notes` | Rationale; Hans / Max question flags; consolidation pass markers. |

---

## §3. Status semantics

- **`migrate`** — port the legacy artifact verbatim into the canonical store with the named `replacement_indicator_id`. The legacy shape becomes a single parent indicator; logical key (D7) is preserved across the port.
- **`consolidate`** — merge the legacy artifact into a **parent** indicator via facet-explode (D26). The parent already has another row (or is the `migrate` row of a sibling); this row becomes a child with populated `dimension_values`.
- **`drop`** — retire the legacy artifact with a recorded reason. Gets a row in `datasets/_old/DELETED.md` (D36) at actual deletion time in Phase 1.8 / 2 / 3. Common drop reasons: duplicate of another artifact (different unit, different source vintage — reconcile via UPSERT logical key), `*_long` intermediate that is not authoritative, total that is compute-on-read (D33.8).
- **`queue`** — legitimate but deferred. `target_phase` is the phase before which Max + Hans must revisit and promote the row to `migrate` or `consolidate`. Unresolved `queue` rows at Phase 1.8 BLOCK `_old/` deletion (D14 checklist).

---

## §4. Headline numbers (current pass)

Approximate; live counts come from grepping the CSV.

| Status | Approx count | Where |
| --- | --- | --- |
| `migrate` | ~75 | Elections (27) + ~48 indicators landing as their own parent |
| `consolidate` | ~25 | Heavy in energy (fuel_type), fiscal (transfer_type), economy (prices_basis), demography (residence / gender) |
| `drop` | ~13 | Unit-conversion duplicates, `_long` intermediates, computable totals (D33.8) |
| `queue` | ~17 | environment (7), prices (7), human_development (1), transport (2) |

Net effect: ~110 legacy socio-economic indicators collapse to **~50 canonical parents + facet-explode children**, with another ~17 queued for Phase 3.5 / Phase 4 promotion. Consistent with THE PLAN's "60 parents → 80–120 ids" R11 ballpark — and well clear of the §0b 500–1,000+ growth target.

---

## §5. Open consolidation questions (Max + Hans pre-Phase-2 sweep)

Tagged in the `notes` column of the CSV; restated here for visibility:

1. **`allocation_basis` facet axis** (geographical vs contractual for installed capacity) — **REGISTERED 2026-05-19 (PR-Q.2)**. Now lives as a `FacetAxis` literal inside `FACET_AXES` in `backend/yen_gov/canonical/facet_axes_seed.py` (per canonical-store.md §8.3 — the Python-compiles-to-parquet pattern that replaced the legacy `facet-axes.json` registry). Open downstream choice for Phase 2 Energy: whether CEA installed capacity ships as one parent indicator faceted by `allocation_basis` ∈ {`geographical`, `contractual`}, or as two distinct parent indicators. Decision owned by Max + Hans at Phase 2 kickoff.
2. **Renewable `fuel_type` sub-split** — solar utility / solar rooftop / wind / biomass / SHP — pre-declare or let MNRE adapter drive?
3. **National-level entity convention** — confirm `entity_type=country` for `india-*` indicator rows in `entities.json`.
4. **`national_renewable_potential_vs_installed_mw`** — explode into two parents (potential, installed) or one parent with measure facet?
5. **`india-macro-aggregates` explosion** — Max to enumerate constituent series before Phase 3 ingest.
6. **CPI `combined_yoy`** — facet value alongside food/fuel/housing/general per D33.7, or first-class indicator? Confirm at Phase 3.5 kickoff.

Each gets a follow-up commit when answered (in the same PR as the answer if the answer triggers a CSV edit).

---

## §6. Update protocol

- New legacy artifacts discovered during a phase → append to CSV in the same commit that discovers them.
- A `queue` row gets promoted to `migrate` / `consolidate` → edit in place, do NOT delete the row (preserves audit trail).
- A `drop` row gets actually deleted in `_old/` → that event lands a row in [`_old/DELETED.md`](../../datasets/_old/DELETED.md) (created on first deletion per D36); this ledger stays as the planning record.

---

## See also

- [Canonical-pivot deletion manifest](canonical-pivot-deletion-manifest.md) — files / modules / concepts retired (companion to this data-artifact ledger).
- [`canonical-pivot-migration-ledger.csv`](canonical-pivot-migration-ledger.csv) — the ledger itself.
- [ADR-0030 — canonical store on Parquet + DuckDB-WASM](decisions/0030-canonical-store-duckdb-wasm.md) — D13 rip-and-replace, D14 deletion checklist, D24 migration ledger, D26 facet-explode.
- [`data/canonical-store.md`](data/canonical-store.md) — D30 naming convention used by `replacement_indicator_id`.
- [THE PLAN §6 step 0.5 + §7 step 1.8](../../TODO/20260517-canonical-long-format-pivot.md) — ledger / deletion gating.
