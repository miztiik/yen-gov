# LGD canonical keys: state/district/AC join contract

**Last Updated**: 2026-06-01

## Audience

Engineers wiring a new indicator into yen-gov who need to know:

- Which column do I join on?
- Which authority issues that column?
- How do I translate from a non-LGD upstream key (ECI, Census, state-portal id) to the canonical LGD id?

For the doctrine that drives this contract, see [docs/concepts/lgd-authority.md](../../concepts/lgd-authority.md) and [ADR-0050](../decisions/0050-folder-naming-lgd-slug.md).

## The contract in one paragraph

Every row in every canonical Parquet under `datasets/` that names a geographic entity carries an LGD id at the relevant level: `lgd_state_id` (smallint), `lgd_district_id` (int), `lgd_ac_id` (int). These are the ONLY join keys consumers should write joins against. Display-friendly columns (`state_code = "S07"`, `ac_no = 42`, `pc_no = 9`) survive for citizen-readable UI but are NEVER the join key. The authority for each id is the Ministry of Panchayati Raj's [Local Government Directory](https://lgdirectory.gov.in/); the authority list in-repo is `datasets/taxonomy/lgd_<level>.json` per level.

## Levels and authority files

| Level | Column | Authority file | Schema | Row count |
| --- | --- | --- | --- | --- |
| State / UT | `lgd_state_id` | `datasets/taxonomy/lgd_states.json` | [lgd-states.schema.json](../../../datasets/schemas/lgd-states.schema.json) | 36 |
| District | `lgd_district_id` | `datasets/taxonomy/lgd_districts.json` | [lgd-districts.schema.json](../../../datasets/schemas/lgd-districts.schema.json) | 784 |
| Assembly Constituency | `lgd_ac_id` | `datasets/taxonomy/lgd_acs.json` (pending PR L1c) | `lgd-acs.schema.json` (pending) | ~4123 |
| Parliamentary Constituency | `lgd_pc_id` | `datasets/taxonomy/lgd_pcs.json` (future) | `lgd-pcs.schema.json` (future) | 543 |
| Sub-district / Block | `lgd_subdistrict_id` | `datasets/taxonomy/lgd_subdistricts.json` (future) | (future) | ~7000 |
| Panchayat / ULB / Ward | `lgd_panchayat_id` / `lgd_ulb_id` / `lgd_ward_id` | (future) | (future) | varies |

State + district are seeded (PRs L1a #555 + L1b #556). AC seed (L1c) is blocked on LGD AC-directory snapshot; see the [execution handover](../../../TODO/20260601-lgd-execution-handover.md) for the source plan.

## Join recipes

### Pattern 1: state-level indicator (most common)

Upstream gives you a state name or an ECI code. Resolve to `lgd_state_id` via `lgd_states.json`:

```python
# In a backend adapter, e.g. backend/yen_gov/sources/nfhs/loader.py
states = json.loads(Path("datasets/taxonomy/lgd_states.json").read_text())["states"]
by_eci = {s["eci_st_code"]: s["lgd_state_id"] for s in states}
by_name = {s["lgd_name"].lower(): s["lgd_state_id"] for s in states}

def to_lgd_state(row: dict) -> int:
    if "st_code" in row:
        return by_eci[row["st_code"]]
    if "state_name" in row:
        return by_name[row["state_name"].strip().lower()]
    raise ValueError(f"no state key in row: {row}")
```

The canonical row written to `datasets/indicators/in/<topic>/...` carries `lgd_state_id` as the join key. The original `st_code` may also be carried as a display column; readers MUST NOT depend on it for joins.

### Pattern 2: district-level indicator

Upstream gives a district name within a state. Resolve via the composite `(lgd_state_id, district_name)`:

```python
districts = json.loads(Path("datasets/taxonomy/lgd_districts.json").read_text())["districts"]
by_state_name = {(d["lgd_state_id"], d["lgd_name"].lower()): d["lgd_district_id"] for d in districts}

def to_lgd_district(lgd_state_id: int, district_name: str) -> int:
    return by_state_name[(lgd_state_id, district_name.strip().lower())]
```

Name collisions across states (Hamirpur in HP and UP, Aurangabad in Maharashtra and Bihar) are not collisions in the lookup because the state-id is part of the composite key. The salted-slug rule (see [lgd-districts.schema.json](../../../datasets/schemas/lgd-districts.schema.json)) addresses the display-slug level, not the id-resolution level.

### Pattern 3: AC-level (election + non-election)

Election results today key on ECI `(state_code, ac_no)`. Per [ADR-0049](../decisions/0049-canonical-ac-join-key.md), the canonical INTERNAL join is `lgd_ac_id` via `datasets/taxonomy/ac_crosswalk.parquet`. The crosswalk is the dispatched authority during the migration; once L1c lands, `lgd_acs.json` becomes the single AC register and the crosswalk becomes a thin lookup layer.

### Pattern 4: folder-partition lookups

After the partition rename (waves M2-M4 per execution handover), every dataset reads from `state=<slug>/...`:

```python
slug = next(s["slug"] for s in states if s["lgd_state_id"] == lgd_state_id)
path = REPO / f"datasets/boundaries/in/ac/state={slug}/all.geojson"
```

Frontend Vite middleware `serveDatasets()` exposes the same partition shape under `/data/` (per [docs/architecture/frontend/data-loading.md](../frontend/data-loading.md)).

## What columns NEVER to join on

| Column | Why not |
| --- | --- |
| `state_code` (`"S07"`) | Per-state ECI form. Display-only since ADR-0049. Re-issued each delim. |
| `ac_no` / `eci_no` | Per-state ballot enumeration. Not globally unique. Ballot number can shift in a re-delim. |
| `state_name_en` raw string | Whitespace / casing / punctuation drift across upstream sources. Resolve to id at the boundary. |
| `iso_alpha` (`"IN-HR"`) | Display-only; used by cross-country tools (OWID-style); never a yen-gov join key. |
| `census_2001_code` / `census_2011_code` | Vintage-specific; use only for cross-census joins where you EXPLICITLY want a vintage axis. |
| `in_s07` legacy folder labels | Retired per ADR-0050. If you see this in code, it is a migration backlog item. |

## Writer-side discipline

When emitting a new row into the canonical store:

1. Resolve the upstream key to `lgd_<level>_id` at the boundary (in the adapter, not downstream).
2. Carry the `lgd_<level>_id` as the primary join column.
3. Keep the original upstream key (e.g. `st_code`, `ac_no`) as a nullable display column.
4. Cite the LGD source row in `sources.parquet` for the entity identity AND the upstream source for the observed value (these are two distinct citations).

Fail fast at the boundary if the upstream key does not resolve. NEVER guess or coerce. A missing LGD mapping is a real data event - log it, raise it, or mark the row with `match_method = "unmapped"` per ADR-0049 pattern.

## Reader-side discipline

When joining two datasets:

1. Both sides MUST carry the LGD id at the relevant level. If one side carries only a legacy key, fail loud (do not silently translate at read time - the writer should have resolved).
2. For frontend Svelte / DuckDB-WASM joins, the partition slug must match `lgd_states.json:slug`. The lookup tables ship as JSON next to the data.
3. For cross-level joins (e.g. AC -> district -> state), use the FK chain: `lgd_ac_id -> lgd_district_id -> lgd_state_id` via `lgd_acs.json` and `lgd_districts.json`. No name-string joins at read time.

## What changed (vs the prior order)

Pre-LGD-canonical, yen-gov used `state_code` (ECI form) as the de-facto join key for everything that wasn't an election. That worked because the codebase started in election work; it stops working the moment a health / fiscal / agriculture indicator joins on district. ADR-0049 + ADR-0050 + the L1 seed PRs make the new contract explicit and machine-checkable.

## See also

- [docs/concepts/lgd-authority.md](../../concepts/lgd-authority.md) - WHY LGD is canonical
- [ADR-0050](../decisions/0050-folder-naming-lgd-slug.md) - folder-naming convention `state=<lgd-name-slug>`
- [ADR-0049](../decisions/0049-canonical-ac-join-key.md) - `lgd_ac_id` as canonical internal AC key
- [ADR-0044](../decisions/0044-grain-over-entity.md) - entity_id shape (unchanged by LGD-canonical)
- [docs/architecture/data/canonical-store.md](canonical-store.md) - the canonical store layout that consumes these keys
- [docs/concepts/admin-level-sourcing.md](../../concepts/admin-level-sourcing.md) - the LGD-golden doctrine predating these PRs
- [TODO/20260601-lgd-canonical-plan.md](../../../TODO/20260601-lgd-canonical-plan.md) - parent strategic plan
- [TODO/20260601-lgd-execution-handover.md](../../../TODO/20260601-lgd-execution-handover.md) - per-row execution split
