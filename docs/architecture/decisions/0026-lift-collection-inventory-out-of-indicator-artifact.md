# ADR-0026 — Lift `collection_inventory` and `series_spec.expected_*` out of the indicator artifact

**Status**: Accepted
**Superseded by**: [ADR-0030](0030-canonical-store-duckdb-wasm.md) (2026-05-17). The collection-inventory-as-overlay concept is replaced by `datasets/manifest.json` (D21) plus denormalised `coverage_*` columns on `taxonomy/indicators.parquet` (D15).
**Date**: 2026-05-17
**Deciders**: User; agent-deliberation included Gregor (Architect), Fowler (Engineering), Hans (Governance)
**Supersedes / supersedes**: builds on ADR-0020 (indicator artifact as data contract); related to lesson-2026-05-16 (fetched_at smear)

## Context

Indicator schema v3.0 required a `collection_inventory` block on every artifact:

```json
"collection_inventory": {
  "status": "complete | partial | empty",
  "frozen": false,
  "refetch_requested": false,
  "last_collected_at": "2026-05-16T08:31:12+00:00",
  "observed_periods": [ {key, label, frequency}, … ],
  "pending_periods":  [ {key, label, frequency}, … ],
  "unavailable_periods": [ {period, geographies?, reason}, … ]
}
```

…and a sibling `series_spec.expected_geographies` / `series_spec.expected_periods` / `series_spec.expected_periods_inference` describing the *promised* shape.

That one block was carrying **three unrelated jobs**:

1. **Publisher promise** — what RBI/CEA/MoSPI says it will publish for this series. Slow-changing, hand-authored or derived from the series's own metadata.
2. **Operator scoreboard** — what yen-gov has actually pulled, what is still pending, what is operator-frozen, and what is acknowledged-unavailable. Wall-clock heavy, hand-curated overlay, *not citizen data.*
3. **Citizen completeness banner** — the small "we have N of M periods; last fetched X" hint shown on every indicator card.

Stuffing three jobs onto one block produced four concrete defects:

- **Re-derive smear.** `inventory.last_collected_at` was computed as `max(sources[].fetched_at)`. Every Fetcher re-stamp (lesson-2026-05-16 fetched_at smear, *one layer up*) leaked into the artifact even when rows were byte-identical. Commit 1d2983c added a dict-equal write-skip gate that masked the symptom, but the *contract* was still asking the artifact to carry operator wall-clock telemetry.
- **Hans/nuclear-in-Goa false-pending.** `pending_periods = expected_periods − observed_periods` was a cross-product blowup. If `expected_geographies = ALL_STATES` and `expected_periods = [FY24]` and Goa had no nuclear capacity, the cross-product pretended Goa-FY24 was "pending collection" — a row that *will never exist* and that no operator should chase. The framework was inventing work for itself.
- **Operator-set fields buried in a citizen artifact.** `frozen` and `refetch_requested` are operations primitives ("don't refresh this" / "do refresh this on the next pass"). Citizens don't see them. Operators want to edit them in bulk across many indicators, not 110 separate files. They also have no place being content-hashed.
- **Schema bloat amplifies all four.** Every artifact carried a `collection_inventory` block whether or not it had any operator state at all. The default-empty case (frozen=false, refetch=false, unavailable=[]) was duplicated 110 times in the contract.

The 1-thing-per-field rule (lesson-2026-05-16) makes the diagnosis surgical: a field that means three things means none of them.

## Decision

Lift `collection_inventory` and `series_spec.expected_*` **out** of the indicator artifact entirely (schema v3.0 → v4.0). Spread the three jobs across three surfaces, each with one job:

| Job | New surface | Schema |
| --- | --- | --- |
| Publisher promise (expected periods + geographies) | absorbed by the completeness index (planned §16 #11 follow-up — see *Open questions* below) | `datasets/schemas/indicators-completeness.schema.json` |
| Operator scoreboard (frozen / refetch / unavailable / first-collected) | sparse hand-edited overlay `datasets/reference/in/indicators-operator-state.json` | `datasets/schemas/indicators-operator-state.schema.json` v1.0 |
| Citizen completeness banner (status, observed count, last-collected-at) | derived index `datasets/reference/in/indicators-completeness.json` | `datasets/schemas/indicators-completeness.schema.json` (v1.0 today; v2.0 in follow-up) |

Concretely:

- `indicator.schema.json` v4.0: remove `collection_inventory` (required + properties). Shrink `series_spec` to `{description}` only. Bump version.
- `indicators-operator-state.json` (NEW): envelope `{$schema, $schema_version: "1.0", indicators: {<id>: {frozen?, refetch_requested?, unavailable_periods?}}}`. Sparse — only indicators with non-default flags appear. Hand-edited.
- `indicators-completeness.json`: regenerated from `rows[].time` (observed_count), `sources[].fetched_at` (last_collected_at), and the operator-state overlay (frozen, unavailable_count). Status is "complete" iff rows are present, else "empty"; the pre-v4 three-valued enum becomes two-valued in practice (a follow-up may shrink the schema enum to match).
- `tools/rip_to_v4.py` (NEW): idempotent migration that walked 110 indicators, stripped the blocks, bumped the version, and seeded the operator-state overlay from any pre-existing values. Ships in the repo for archaeology.
- Frontend `IndicatorArtifact` type loses `collection_inventory?`; `SeriesSpec` shrinks to `{description}`. `AboutThisData.svelte` drops the per-indicator Coverage block — citizens now see completeness on `/data-completeness` (which already exists and reads the index).

## Rejected alternatives

### Alternative A — keep the block, just stop re-stamping

Was: leave the schema at v3.0, fix only the smear by content-hash gating writes (which we did anyway in commit 1d2983c) and forbid re-deriving `last_collected_at`. Rejected because it left the three-jobs-one-field defect intact; the Hans/nuclear-in-Goa false-pending bug would have stayed; operator state would still have been buried in 110 separate citizen artifacts.

### Alternative B — split `collection_inventory` into three siblings INSIDE the artifact

Was: add `publisher_promise`, `operator_state`, `derived_coverage` as three top-level blocks under `IndicatorArtifact`. Rejected because operator state still doesn't belong in citizen-facing data, and the operator UX is "edit many indicators at once" not "open 110 files." Splitting fields without moving surfaces would have failed both the contract clarity and the operator workflow tests.

### Alternative C — move only `collection_inventory`, keep `expected_*` in `series_spec`

Was: lift the derived/operational block, leave the publisher-promise fields where they were. Rejected because `expected_periods` is the **input** to the false-pending bug; without expected, there is no false-pending. Also: the publisher promise is *not* per-indicator authored data today (it was synthesized from observed rows during the v1.6 fold), so leaving it in the artifact would have left a field that the framework had no honest way to populate.

## Consequences

**Bug-fix consequences.**

- The Hans/nuclear-in-Goa cross-product is structurally impossible: there is no `expected_periods × expected_geographies` to take a difference against.
- The `last_collected_at` smear cannot leak into the citizen artifact: the field is no longer in the artifact. It lives in the completeness index, which is derived from `sources[].fetched_at` (still operator wall-clock today; tracked separately under §16 #13 Option B Last-Modified derivation).
- Operator state is editable as a single small file (`indicators-operator-state.json`) rather than 110 file-touches.

**Contract consequences.**

- Schema v4.0 is a MAJOR bump (per CLAUDE.md §11: removing a required field is breaking). All 110 artifacts were rewritten by `tools/rip_to_v4.py` in the same commit (7239c65) — there is no half-migrated intermediate state. Any external consumer that read `collection_inventory.*` or `series_spec.expected_*` will fail loud (key missing) rather than silent-default-to-empty.
- The `indicators-completeness.json` schema stays at v1.0 for this commit. Follow-up §16 #11 will either (a) shrink the `inventory_status` enum from 3 values to 2 (`complete | empty`) since `partial` is no longer derivable, or (b) move the expected-periods surface into the index and restore three-valued completeness. The decision between (a) and (b) is deferred until at least one indicator authors a real expected-periods promise.

**Operator workflow consequences.**

- Setting an indicator frozen now requires editing `indicators-operator-state.json` (one file) and re-running the completeness emitter. The previous workflow (edit one of 110 artifact files, re-run validate) is gone.
- Hand-authored `unavailable_periods` move from the artifact to the overlay. The shape is unchanged (`{period, geographies?, reason}` array per indicator id).
- `refetch_requested` is currently un-wired (no adapter reads it yet — §16 #12 follow-up). It exists in the overlay schema so the operator UX can land before the adapter wiring.

**Citizen-facing consequences.**

- `AboutThisData` panels no longer carry the small Coverage block. The /data-completeness route remains the single citizen surface that answers "how complete is this dataset?" — which is honest, since per-indicator coverage was always an approximation anyway.
- The Scope sub-section no longer says "Tracked for N geographies." If a future commit reinstates a geography count, it should source it from the *observed* rows, not from a publisher-promise field.

**Test consequences.**

- 502/502 backend tests pass. `test_core_io.py` was updated for v4.0 (`test_write_artifact_v4_strips_no_inventory_carried_in_caller_payload` replaces the prior operator-set-fields preservation test). `test_migrate_indicators_v15_to_v20.py` no longer validates the migration tool's output against the live schema (the live schema is now v4.0; the migration tool produces v1.6 — that's intentional historical archaeology).
- `npm run check` reports 0 errors on the frontend.

## Migration record

| Commit | What it did |
| --- | --- |
| `1d2983c` | core(io): dict-equal write-skip gate at write_artifact — masks the smear at the write seam |
| `7239c65` | schema(indicator) v3.0 → v4.0; ripped 110 artifacts; new operator-state schema + empty overlay; simplified io.py folded-blocks derivation |
| `79011c5` | tools+data(completeness): rewrote `emit_indicators_completeness_index.py` to derive from rows + sources + operator-state overlay; regenerated `indicators-completeness.json` |
| `925a70e` | frontend(types+about): dropped `CollectionInventory` type, shrunk `SeriesSpec`, removed Coverage block from `AboutThisData.svelte` |
