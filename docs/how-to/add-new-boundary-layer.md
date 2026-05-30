# How to add a new boundary layer (orchestrator authoring)

**Last Updated**: 2026-05-30

Adding a new admin-level boundary layer (or a gap-fill source for an
existing level) follows a stable 7-step pattern proved across blocks
(C.1), panchayats (C.2), ULB wards (C.3), and J&K villages (C.4).
This doc captures the durable structural decisions, especially the
"fork a parallel orchestrator vs consolidate the existing one"
question that recurs whenever a 2nd source enters an established level.

For the upstream-pick decision tree (LGD vs BharatMaps vs Bhuvan vs
LivingAtlas), see [`docs/concepts/admin-level-sourcing.md`](../concepts/admin-level-sourcing.md).
For the architectural decision (one-source-per-level + per-state hive
partition), see [ADR-0031](../architecture/decisions/0031-boundary-geometry-strategy.md).

## When to fork a NEW orchestrator vs augment the existing one

This is the most common question on the 2nd source for an established
level. The rule, derived from C.4 (Bhuvan-JK villages, parallel to
LGD national villages):

- **FORK a parallel orchestrator** when the new source covers a
  SUBSET of the existing source's coverage gap (overlap < 5% by
  feature count). Example: C.4 adds J&K villages where LGD has zero;
  zero overlap with `lift_villages_national.py`. Fork is cleaner.
- **AUGMENT the existing orchestrator** when the new source covers
  the SAME territory with refresh / quality / vintage improvement.
  Example: would apply if ramSeraph one day publishes LGD-vintage
  v2 with post-2014 AP geometry that supersedes the current S01
  vintage. Augment via a `--source {v1 | v2}` flag + per-source
  property constants.

The fork-vs-augment threshold is **5% feature-count overlap**. Below
that, fork (no risk to existing behaviour, no parametrisation
overhead). Above that, augment (avoids two-script drift on the same
territory).

When forking, the new orchestrator follows the naming convention
`tools/boundaries/lift_<level>_<source>_<scope>.py`:

- `lift_villages_jk_bhuvan.py` for C.4 (single-state, Bhuvan source)
- `lift_villages_hp_bhuvan.py` would be the future HP gap-fill
- `lift_villages_national.py` stays as the LGD-national umbrella

## The 7-step authoring pattern

### Step 1: Recon the upstream and pick the source

See [`docs/concepts/admin-level-sourcing.md`](../concepts/admin-level-sourcing.md)
for the LGD/BharatMaps/Bhuvan/LivingAtlas pick rule. Output: one
verdict note under `notes/<date>-<level>-source-hunt-verdict.md`
covering TL;DR + Tier-1 URL + alternatives + coverage gaps + chosen
partition shape. Recon-only PRs are encouraged when scope is unclear
(no implementation, just the verdict note).

### Step 2: First-snapshot probe for property names (3-CONVENTION RULE)

NEVER assume property names match the level's predecessor. Author a
one-shot probe script (or interactive REPL session) that:

1. Downloads the upstream artefact (`.geojsonl.7z` from ramSeraph).
2. Extracts and reads the first 5 features.
3. Prints `features[0]["properties"].keys()` and 3 sample values.
4. Confirms the LGD code field, the parent FK field, and the name
   field.

Lock the observed names into module-level constants at the top of the
orchestrator:

```python
STATE_PROPERTY = "st_lgd"       # observed from probe, not assumed
DISTRICT_PROPERTY = "dt_lgd"
ID_PROPERTY = "gp_code"
NAME_PROPERTY = "gp_name"
```

This pattern was introduced after C.1.b / C.2.b / C.3.b each surfaced
a different naming convention. The probe takes ~5 minutes; skipping it
has cost ~half a day per level so far.

### Step 3: Schema enum addition (one-line change)

Add the new level to the `level` enum in
`datasets/schemas/boundaries.schema.json`. Singular non-prefixed name
(`panchayat` not `gram_panchayat`, `ward` not `ulb_ward`). The
disambiguation between similar entities (ULB ward vs GP ward) is
carried by the partition key (`ulb=` vs `district=`) and by
`entity_kind` in the parquet ledger, not by the level name.

### Step 4: Orchestrator (modelled on the closest precedent)

Pick the precedent that matches the partition shape:

| New level partition shape | Closest precedent |
| --- | --- |
| `state=in_<lc>/all.geojson` | `lift_districts.py` |
| `state=in_<lc>/district=<lgd>/all.geojson` | `lift_villages_national.py` |
| `state=in_<lc>/ulb=<lgd>/all.geojson` | `lift_wards_national.py` (post-C.3.b) |

Copy the precedent, replace the property constants (Step 2), update
the URL + partition key + level enum, and run.

Inherit the C.1.c auto-fallback pattern (PR #443) for byte-budget
breaches: emit at `coord_precision=5`, fall back to `4` then `3`,
SKIP if still over budget. Record `simplification_tolerance_deg` per
shard in the parquet ledger.

### Step 5: Per-shard contract tests

Add a vitest entry to the conformance test family (currently
`frontend/src/contracts/__tests__/boundaries-conform.test.ts`). The
regex needs to recognise the new partition shape. Example for ward:

```typescript
const WARD_PATH = /^boundaries\/in\/wards\/state=in_[a-z]{1,3}[0-9]?\/ulb=\d+\/all\.geojson$/;
```

Run `bun run test` and confirm zero new failures. If the new layer
introduces orphans (files on disk but not matched by any regex), fix
the regex BEFORE merging -- orphan failures cascade across every
subsequent run.

### Step 6: Sources parquet row + lift ledger entry

Add a row to `datasets/_sources/sources.parquet` for the new upstream:

- `source_id`: stable nickname (e.g. `ramseraph_lgd_panchayats`,
  `ramseraph_bhuvan_jk_villages`).
- `url`: the exact `.7z` URL.
- `license`: `CC0-1.0` for the current cohort.
- `lineage_chain`: human-readable (e.g.
  "LGD -> BharatMaps -> ramSeraph", or
  "J&K Revenue Dept -> Bhuvan/NRSC -> ramSeraph").
- `vintage`: ramSeraph release tag date.

The lift orchestrator writes per-shard ledger entries to
`datasets/_sources/boundaries_lift_ledger.parquet` with `feature_count`,
`coord_precision_used`, `simplification_tolerance_deg`, `shard_bytes`.

### Step 7: Frontend registry (only if a citizen surface needs it)

NOT every new boundary layer needs frontend exposure. Villages have
existed on disk since pre-C.4 with no frontend registry entry; the
gating condition is whether a CITIZEN INDICATOR consumes the layer.

If yes, add a registry entry to
`frontend/src/lib/maplibre/sources.ts`:

```typescript
export const PANCHAYAT_BOUNDARY_BY_DISTRICT: Record<string, () => Promise<string>> = {
  "in_s33_576": () => fetch("/data/.../state=in_s33/district=576/all.geojson")
    .then(r => r.text()),
  // ...
};
```

Plus a contract test mirroring `state-ac-coverage.spec.ts` for the
new level. The picker UI (district-picker for panchayats, ULB-picker
for wards) is a separate Level-3 component, typically scoped as a
follow-up PR after disk + registry land.

If NO surface is needed, document the deferred status in
`TODO/<latest>-boundary-plan-followups.md` Category 3 (Renderer /
UX follow-ups) and link the inventory entry from the source's verdict
note.

## What NOT to do

- **Do NOT add a new boundary level to satisfy a hypothetical future
  indicator.** The decision filter in `admin-level-sourcing.md` Step
  "When to adopt a new admin level" requires existing or imminent
  demand. Hypothetical demand triggers verdict-only recon, not
  adoption.
- **Do NOT skip the property-name probe** (3-convention rule). It
  ALWAYS surfaces a surprise.
- **Do NOT augment an existing orchestrator below the 5% feature-count
  overlap threshold** with the new source. The augmentation cost
  exceeds the parallel-script cost at that scale.
- **Do NOT bundle the disk layer + frontend registry + picker UI in
  one PR.** Slice into infrastructure + lift + frontend + picker per
  the C.2 / C.3 sub-row pattern (`.a` infra, `.b` lift, `.c`
  frontend, `.d` optional gap-fill). The picker UI in particular
  benefits from waiting on measured data (typical density, name
  lengths) before tuning.

## See also

- [`docs/concepts/admin-level-sourcing.md`](../concepts/admin-level-sourcing.md) -- upstream-pick rules + 3-convention rule
- [`docs/concepts/boundary-data-philosophy.md`](../concepts/boundary-data-philosophy.md) -- WHY polygons over rasters, LGD-golden doctrine
- [ADR-0031](../architecture/decisions/0031-boundary-geometry-strategy.md) -- architectural decision (one-source-per-level)
- [`tools/boundaries/README.md`](../../tools/boundaries/README.md) -- pipeline ops + per-orchestrator usage
- [`docs/how-to/digitize-ac-from-pdf.md`](digitize-ac-from-pdf.md) -- T3 PDF fallback workflow for delim-AC layers
