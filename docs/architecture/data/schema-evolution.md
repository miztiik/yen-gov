# Schema Evolution

**Last Updated**: 2026-06-12

This document is the operational policy for evolving yen-gov schema contracts without unnecessary data rebuilds. [ADR-0047](../../reference/decision-index.md) records the decision; this page records the working rules.

> **Status note (2026-06-12).** A pending [OWID-conformance pivot](#pending-owid-conformance-pivot-stop-stamping-schema_version-onto-data-emit-files) reframes the `$schema_version` field as a yen-gov-specific extension that OWID does not carry on its data emit files. The current writer-strict / reader-compatible policy below stays in force until the pivot ships; the open question is whether the field should exist on data files at all, not whether the field is well-stamped today. Tracked in [TODO/20260612-schema-version-field-refactor-plan.md](../../../TODO/20260612-schema-version-field-refactor-plan.md).

## Scope

Applies to:

- JSON Schemas under `datasets/schemas/`.
- JSON artifacts under `datasets/` and `config/`.
- `datasets/manifest.json`.
- Parquet row schemas and Parquet footer metadata.
- Backend validator and frontend reader compatibility checks.

Out of scope:

- Production backend migrations. Production is static.
- Silent defaulting or lossy coercion of old artifacts.
- Methodology-break policy except where a schema change also changes data meaning.

## Policy Summary

- **Writers are strict**: a writer emits the current schema version and rejects stale schema metadata.
- **Readers are compatible by contract**: a reader may accept an older version only when the compatibility contract says it can.
- **Reader before producer**: reader support lands before a writer emits a new version.
- **Fail loud**: unsupported, unknown, or incompatible versions fail rather than being coerced.
- **No mechanical restamp**: additive minor changes do not require rewriting unchanged artifacts solely to update `$schema_version`.

## Contract Surfaces

| Surface | Responsibility |
| --- | --- |
| JSON Schema `x-version` + `x-changelog` | Names the current contract and records schema evolution. |
| Backend writers, including `canonical.csv_writer.write_csv` (post-B4-pt3) | Emit current schema metadata only. |
| Backend Tier B validator | Validates corpus artifacts against current or explicitly compatible contracts by consuming `datasets/schema-compatibility.json` for `json-corpus`. |
| Frontend JSON corpus contract | Defends the static corpus the frontend consumes by using the same `json-corpus` compatibility contract as backend Tier B. |
| Canonical manifest reader | Checks manifest/table versions before registering Parquet files. |
| `datasets/schema-compatibility.json` | Single machine-readable source for supported reader versions across runtimes. Its schema lives at `datasets/schemas/schema-compatibility.schema.json`. |
| `datasets/schema-evolution.json` | Public release ledger for schema changes: which schema moved, whether values/provenance/methodology changed, and which historical schema file validates old declared versions. Its schema lives at `datasets/schemas/schema-evolution.schema.json`. |
| `datasets/schemas/archive/<schema>/v<version>/<schema-file>` | Retained historical JSON Schema documents used for declared-version validation when the current schema cannot honestly validate old artifacts. |

## Compatibility Registry

`datasets/schema-compatibility.json` is the data-owned compatibility contract introduced by PR #463. It is a contract surface, not a generated data snapshot, and it answers only one question: which schema versions a reader surface may accept.

The registry has two policy layers:

- **Defaults** name each reader surface's baseline behavior. The JSON corpus surface is current-schema only by default; backend Tier B and the frontend corpus contract consume overrides from this registry. The canonical manifest reader is unsupported unless an override lists the schema/version pair.
- **Overrides** name explicitly accepted versions for a surface and schema. Row C seeded additive minor versions that the current schema can still validate: `manifest.schema.json` v1.0-v1.3 and `observation.schema.json` v1.0-v1.1. Row G2 extends the `canonical-manifest-reader` surface with current-only entries for every non-observation table schema the runtime can register.

The registry deliberately does not copy old-major frontend constants whose current schemas have since moved to a higher major. Old majors need retained schemas, a translator, migration, or fail-loud rejection. Rows G1/G2 retire local frontend constants as an authority and wire runtime canonical manifest/table registration to the shared contract; Rows E and F wired backend and frontend JSON corpus consumption. Row H adds the separate release ledger; do not stuff release history, value-change assertions, or retained-schema paths into the compatibility registry.

## Version Change Taxonomy

| Change class | Version bump | Rebuild duty | Reader duty |
| --- | --- | --- | --- |
| Documentation or description only | None | Do not rebuild artifacts. | None. |
| Optional metadata field | Minor | New writers emit the new version; unchanged old artifacts may remain if absence is honest. | Accept old minor only through compatibility contract. |
| Optional enum widening | Minor | Rebuild only artifacts that use the new value. | Support the widened value before data ships. |
| Required field after backfill | Minor or major by review | Backfill affected artifacts before tightening. | Reject missing field after contract phase. |
| Rename, removal, or type narrowing | Major | Migrate, translate, or retain old schemas. | Reject unless translator or retained schema exists. |
| Semantic meaning change | Major plus Hans + Max review | Migrate with methodology notes or reject. | Never smooth old and new meanings together. |
| Parquet physical layout change | Minor or major by reader impact | Rewrite affected table/partition only. | Check manifest and footer versions before query. |

## Envelope vs Fact

A schema version is an envelope label. It says how to parse and validate an artifact; it does not itself mean the facts changed.

An **envelope-only change** affects schema shape, validation metadata, manifest metadata, Parquet footer metadata, path inventory, or table naming while preserving values, logical keys, entity identity, period semantics, methodology, source identity, and row inclusion.

A **factual revision** changes what the data asserts: value, entity identity, period axis, denominator, indicator concept, methodology, source citation identity, or row inclusion/exclusion.

A **provenance-only revision** changes citation metadata without changing values. It is not envelope-only. If `(producer, title, vintage)` changes, derive a new `source_id` and update affected foreign keys.

`datasets/schema-evolution.json` records these distinctions durably. PR bodies may summarize them, but the durable public receipt lives in the ledger.

## Release Metadata Ledger

`datasets/schema-evolution.json` is append-only release metadata for schema changes. It is deliberately separate from `datasets/migration-ledger.csv`: the migration ledger tracks canonical-pivot disposition of legacy data artifacts, while the schema-evolution ledger tracks schema-release history and declared-version validation.

Each non-empty ledger entry names:

- `schema_file`, `schema_id`, `from_version`, and `to_version`.
- `change_class`, `compatibility_status`, and `validation_strategy`.
- `values_changed` plus `value_change_summary` when values did change. `values_changed=false` means published values, logical keys, entity identity, periods, row inclusion, and methodology are unchanged; it does not hide provenance changes.
- `provenance_changed`, `methodology_changed`, and `methodology_break_refs`.
- `affected_artifacts` with path patterns and the action taken (`unchanged`, `metadata_rewritten`, `values_rewritten`, and so on).
- `retained_schema` when `validation_strategy=declared_schema`, including the retained schema path, version, and SHA-256.
- `pr`, `commit`, and human-readable `notes`.

The ledger may be empty when no schema-release event has shipped yet. Adding the ledger contract does not create a pilot schema bump, rewrite data, or widen any reader by itself.

Do not create additive or breaking pilot schema releases solely to prove the compatibility mechanism. Fixture tests are the proof surface until a real schema-release event exists. The first real additive or breaking candidate must name the field or contract change, the consumer, the honest absent/null or migration semantics, and the matching ledger entry before editing producer outputs.

## Minor Versions

Minor versions are compatible only when all of these hold:

1. The change is additive or looser.
2. Missing old fields have honest absent/null semantics.
3. Existing values and logical keys do not change.
4. The intended readers have explicit support for the older declared version.
5. Validation still fails when the artifact shape is invalid for the schema the reader uses.

Do not infer compatibility from the version number alone.

## Major Versions

Major versions are incompatible by default. Supporting an old major version requires at least one of:

- A retained historical schema and declared-version validation.
- An explicit translator from old shape to new reader shape.
- A migration that rewrites affected artifacts.

If none exists, reject the artifact loudly. Do not fill missing fields with guessed defaults.

## Retained Historical Schemas

Historical schemas are retained as files in the repository, not inferred from git history or release downloads. The path convention is:

```text
datasets/schemas/archive/<schema-stem>/v<major>.<minor>/<schema-file>
```

Example: `datasets/schemas/archive/indicator/v1.2/indicator.schema.json`.

The retained file should be the exact historical JSON Schema document needed to validate artifacts that declare that version. `backend.yen_gov.core.schema_evolution.resolve_schema_for_declared_version()` uses this order:

1. If the top-level current schema's `x-version` equals the artifact's declared version, use the current schema.
2. Otherwise load `datasets/schema-evolution.json`, find a release for `(schema_file, declared_version)`, verify the retained schema path and SHA-256, and validate against that retained schema.
3. If no retained schema exists, fail loudly. No git-history lookup, no guessed defaults, no old-major best effort.

## Rollout Order

Normal rollout is reader before producer:

1. Update policy/docs when the contract changes.
2. Add or update `datasets/schema-compatibility.json`.
3. Ship reader support and tests for old supported, unsupported future, unsupported major, and incompatible-shape cases.
4. Only then emit artifacts with the new schema version.

This order matters because the production frontend is static. A new data version can reach GitHub Pages before a citizen has reloaded a new bundle unless the old bundle fails loud or already supports it.

## Testing Policy

Test cases should prove behavior, not literal version strings.

- Writer tests assert newly emitted artifacts use the current schema version from the registry.
- Validator tests use `tmp_path` fixture corpora; pytest must not walk the real corpus.
- Compatibility tests cover supported old additive minor versions, unsupported future versions, unsupported major versions, stale writer metadata, and accepted-version-but-invalid-shape rejection.
- Schema-evolution tests cover valid `values_changed=false`, valid `values_changed=true`, missing retained-schema references, and retained-schema hash/version mismatches using `tmp_path` fixture ledgers.
- Frontend JSON corpus contract tests use the same compatibility contract as backend validation. Canonical DuckDB-WASM reader tests use the `canonical-manifest-reader` surface for manifest/table registration compatibility.
- Literal version strings are acceptable in named historical fixtures; otherwise use schema-registry lookups.

## Pending OWID-conformance pivot: stop stamping `$schema_version` onto data emit files

**Status (2026-06-12, PR-0 ratified).** Scope narrowed from "wide pivot" (8-15 PRs, ~50 schemas + 120 artifacts + new `origin.date_accessed` / `dataset.*` fields) to **"scoped retirement"** (~5-7 PRs, $schema_version stamp dropped from citizen-facing data files only, `datasets/manifest.json` carved out, no new fields). Doctrine is in transition; the policy above stays in force until later PRs ship. Tracked in [TODO/20260612-schema-version-field-refactor-plan.md](../../../TODO/20260612-schema-version-field-refactor-plan.md). User mandate: "no more calling it schema version" + "OWID conformance style" (2026-06-12). PR-0 closed section 0.7 of the plan-doc via 4-persona debate (Gregor + Hans + Max + Fowler); awaiting user verdict on Path A (close as permanent named divergence; ship 1-PR drift-hazard fix only) vs Path B (proceed with scoped 5-7 PR sequence) per plan-doc section 5.

### Why this is a divergence from OWID, not an alignment

yen-gov currently stamps a `$schema_version` field at the top of every JSON artifact in `datasets/` (one or two siblings: `$schema` carries the schema URL; `$schema_version` carries the semver of that schema). The field is well-stamped today — populated by writers from the schema's own `x-version` and validated by per-file JSON Schema rules with `pattern: "^\\d+\\.\\d+$"` (see e.g. [`datasets/schemas/indicator.schema.json`](../../../datasets/schemas/indicator.schema.json), [`datasets/schemas/manifest.schema.json`](../../../datasets/schemas/manifest.schema.json), [`datasets/schemas/indicators-completeness.schema.json`](../../../datasets/schemas/indicators-completeness.schema.json)).

The question is whether the field should exist on citizen-facing data files **at all**. The PR-0 verdict separates manifest (control-plane bootstrap, KEPT) from citizen-facing data files (retiring).

OWID's answer for the citizen-facing tier is **no**. Per [OWID's metadata reference](https://docs.owid.io/projects/etl/architecture/metadata/reference/) and [`docs/concepts/owid-alignment.md`](../../concepts/owid-alignment.md), OWID separates four semantic concerns that yen-gov currently maps as follows (PR-0 ratified column added):

| Concern | OWID field | What it means | yen-gov current surface | After scoped pivot |
| --- | --- | --- | --- | --- |
| Schema shape identity | (none on data file) | "Which version of the schema validates this artifact?" | `.schema.json` `x-version` + duplicated `$schema_version` stamp on every data file | `.schema.json` `x-version` only on citizen-facing artifacts; manifest keeps both per carve-out |
| Data freshness pointer | `origin.date_accessed` | "When did we pull these bytes?" | `_meadow/<source>/<vintage>/` snapshot directories + `.runtime/<adapter>/<source_id>.json` sidecars + `_ops/indicators-completeness.json` overlays | unchanged — already at OWID parity in spirit (the snapshot directory IS the OWID `date_accessed`). Not added as a 6th column on source.csv (would re-open the 5-col binding contract ratified 2026-06-11; re-introduces the `fetched_at smear` from /memories/lessons.md 2026-05-16). |
| Publisher's edition tag | `origin.version_producer` | "Which release of the upstream report?" | `source.csv.vintage` per [ADR-0042](../../concepts/data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor) — covers vintaged AND operator-snapshot-anchored sources | unchanged — yen-gov local name kept (semantic stronger than OWID's `version_producer`; ADR-0042 receipt) |
| Expected refresh cadence | `dataset.update_period_days` | "How often does the upstream change?" | already on every indicator catalogue row per [ADR-0046](canonical-store.md) + CLAUDE.md section 10; sampled 100+ rows, zero nulls | tighten to `required` in the indicator catalogue schema (doctrinal ratification of on-disk reality) |

yen-gov's `$schema_version` field collapses (1) into the data file itself, where it serves no validator the validator doesn't already know. Concerns (2)/(3)/(4) are already covered under yen-gov-native names; the scoped pivot does NOT introduce new fields. Per CLAUDE.md §0a "The One Rule" (OWID is the canonical reference) and the OWID-alignment doctrine, this is a named divergence retiring on citizen-facing surfaces; manifest stays as a documented carve-out.

### What is actually on disk today (audit snapshot, 2026-06-12)

- **~50 `.schema.json` files** in `datasets/schemas/` declare `$schema_version` as a required string field with `pattern: "^\\d+\\.\\d+$"` (semver-2-position).
- **120+ JSON artifacts** in `datasets/` carry the stamp (boundary SoT files at `4.1`, manifest at `1.4`, indicators-completeness at `2.0`, taxonomy/parties at `2.3`, etc.).
- **5 tool sites stamp a hardcoded literal** (`tools/gen_election_tile_layouts.py` x2, `tools/lgd/parse_lgd_export.py`, `tools/lgd/snapshot.py`, `tools/boundaries/enrich_census_code_2011.py` x2): `"$schema_version": "1.0"`. These DO NOT auto-track schema bumps — when the schema moves to `1.1`, the tool keeps emitting `1.0` and writer-strict validation fails. This is the **drift hazard** the pivot fixes incidentally; the underlying question is whether the field should exist at all.
- **1 tool site stamps from the schema** (`tools/emit_indicators_completeness_index.py:180`): `"$schema_version": schema["x-version"]`. This is the well-behaved pattern; it would still be retired by the pivot.

### Why this needs a multi-PR sequence (PR-0 ratified scope)

Downstream impact under the scoped pivot:

- Every citizen-facing JSON artifact's writer needs a coordinated retire of the field (manifest writer keeps the stamp per carve-out).
- Every reader / consumer / contract test that checks for the field's presence on a citizen-facing artifact needs to be updated. Manifest reader ([`frontend/src/lib/canonical/manifest.ts`](../../../frontend/src/lib/canonical/manifest.ts) + [`frontend/src/lib/duckdb.ts`](../../../frontend/src/lib/duckdb.ts)) is the carve-out and stays live.
- Every `.schema.json` file's `required: [..., "$schema_version", ...]` declaration needs to drop the field EXCEPT `manifest.schema.json`.
- The 120+ on-disk artifacts need a per-family migration to drop the field. Manifest stays at `$schema_version: "1.4"`.
- **No replacement fields.** The OWID-shape concerns (`origin.date_accessed`, `origin.version_producer`, `dataset.update_period_days`) are already covered by yen-gov-native surfaces: `_meadow/<source>/<vintage>/` snapshot directories + `_ops/`/`.runtime/` overlays for freshness; `source.csv.vintage` for publisher edition (per ADR-0042); `indicators.json.update_period_days` for cadence (per ADR-0046). The 4-persona debate (Gregor + Hans + Max + Fowler, 2026-06-12) rejected adding `origin.date_accessed` as a 6th column on `source.csv` because it would re-open the 5-col binding contract ratified 2026-06-11 and re-introduce the `fetched_at smear` class.
- Tier-B validator dispatch swap is dead-code deletion: the retained-schema dispatcher in [`backend/yen_gov/core/schema_evolution.py`](../../../backend/yen_gov/core/schema_evolution.py) `resolve_schema_for_declared_version()` is not in the live `tier_b()` hot path (archive has 1 entry).

This is a Level-3 contract change under the narrowed scope (was Level-4 under the original wide framing). It is planned, debated across 4 personas (Gregor / Hans / Max / Fowler) in PR-0, and ships as a 5-7 PR sequence with reader-before-producer rollout per the operational policy above. The plan-doc is [TODO/20260612-schema-version-field-refactor-plan.md](../../../TODO/20260612-schema-version-field-refactor-plan.md).

### What the operational policy means during the transition

Until the pivot lands:

1. **Writers continue to stamp `$schema_version`** with the schema's `x-version`. The writer-strict rule (Policy Summary item 1) stays in force; do not start emitting artifacts that omit the field — readers expect it.
2. **The 5 hardcoded `"1.0"` tool sites are a known drift hazard** but DO NOT band-aid them by rewiring to `schema["x-version"]` if the broader pivot would retire the field anyway. Such a rewire is wasted motion. They retire by DELETION when the writer stops stamping the field. EXCEPTION: if the user picks Path A (close as permanent named divergence per plan-doc section 5), the in-place rewire SHIPS as the only 1-PR fix.
3. **New schemas added during the transition** carry `$schema_version` per the existing template — to keep the contract uniform until the pivot retires it everywhere at once.
4. **No new replacement fields land on citizen-facing artifacts.** Do not start emitting `origin.date_accessed` / `origin.version_producer` / `dataset.update_period_days` as one-off additions to individual artifacts. The PR-0 verdict is that these OWID concerns are already covered by yen-gov-native surfaces (`vintage`, `_meadow/.../<vintage>/`, `update_period_days` on the indicator catalogue); no new namespace lands as part of the pivot. The plan ships the schema-version retirement atomically per artifact family.
5. **`datasets/manifest.json` keeps `$schema_version`** per the CLAUDE.md section 10 control-plane carve-out (documented alongside `generated_at`). Manifest is bootstrap; the deployed static bundle reads it via `isCompatibleSchemaVersion()` and would fail-loud if the field disappeared. This is not a half-migration; it is a named carve-out with a load-bearing reader.

### Cross-links

- [`docs/concepts/owid-alignment.md`](../../concepts/owid-alignment.md) — names this as a divergence; PR-0 verdict narrows the scope and documents manifest as a permanent named carve-out.
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md) — the citation ledger 5-col binding contract (2026-06-11) stays unchanged; PR-0 rejected adding `origin.date_accessed` as a 6th column.
- [`CLAUDE.md` section 10](../../../CLAUDE.md) — manifest control-plane carve-out for `$schema_version` lives here (alongside the `generated_at` carve-out).
- [TODO/20260612-schema-version-field-refactor-plan.md](../../../TODO/20260612-schema-version-field-refactor-plan.md) — the execution plan with PR-0 ratified verdicts in section 0.7.

## Stop Conditions

Stop and escalate if a proposed compatibility path would:

- Change the meaning of a number.
- Weaken provenance or churn `source_id` without a citation-identity change.
- Hide or smooth over a methodology break.
- Accept old major versions without retained schemas, translators, or migrations.
- Assert `values_changed=false` without deterministic evidence that values, keys, periods, row inclusion, and methodology are unchanged.
- Require guessing, silent defaulting, or lossy coercion.
- Leave durable policy only in a TODO plan.

---

## Design rationale

This section consolidates the rationale (Context + Decision + Consequences, condensed) of the originating ADR that pinned the cross-cutting choice for this subsystem (the schema-version compatibility contract). The redirect lives in [decision-index.md](../../reference/decision-index.md).

### ADR-0047: schema-version-compatibility-contract

Status: accepted 2026-05-30. Deciders: Gregor (contract), Fowler (rollout), Hans + Max (public-data semantics).

**Context.** JSON schemas under `datasets/schemas/` already carry `x-version` and `x-changelog`. JSON artifacts under `datasets/` and `config/` declare `$schema` and `$schema_version`. Before this ADR, backend Tier B and the frontend corpus contract treated any artifact whose declared version did not equal the current schema `x-version` as invalid. That current-only rule is useful at the writer boundary, but it conflates two different events: the artifact's envelope changed (schema shape, validation metadata, manifest shape, or footer metadata) vs the facts changed (values, entity identity, period axis, denominator, indicator identity, methodology, provenance, or row inclusion). At ADR acceptance time, the canonical Parquet reader had a frontend-local compatibility idea through `SUPPORTED_SCHEMA_VERSIONS`. Row G1 of the schema-version plan made that export a registry-derived alias instead of an authority. Before this ADR, the JSON validator and frontend JSON corpus test had no shared compatibility contract. Additive schema changes therefore risked forcing restamps or rebuilds whose only observable effect was a version string changing.

**Decision.** Adopt a writer-strict, reader-compatible schema-version contract:

1. Writers emit only the current schema version. A backend writer must continue to reject stale caller-supplied schema metadata.
2. Readers and validators may accept older artifact versions only through an explicit compatibility contract.
3. Reader support ships before producer output. A writer must not emit a new version until every intended reader can accept it or fail loud with a documented reason.
4. Additive minor changes may be compatible without rebuilding unchanged artifacts when absent fields have honest null / absent semantics.
5. Breaking major changes require migration, retained historical schemas, an explicit translator, or fail-loud rejection.
6. No reader may accept an old major version by best-effort coercion.
7. Schema-only changes must not churn `source_id`, source vintage, row counts, methodology-break rows, or observation values.
8. Future implementation work must converge backend and frontend on one machine-readable compatibility contract. Temporary Python or TypeScript mirrors are acceptable only with drift tests and a removal path.

The operational rules (writers strict, readers compatible by contract, reader-before-producer, fail loud, no mechanical restamp) plus the supporting contract surfaces (`x-version`, `canonical.csv_writer.write_csv` (post-B4-pt3, the retired predecessor was `core.io.write_artifact`), backend Tier B, frontend JSON corpus contract, canonical manifest reader, `datasets/schema-compatibility.json`, `datasets/schema-evolution.json`, retained historical schemas under `datasets/schemas/archive/...`) are formalised above in [Policy Summary](#policy-summary) + [Contract Surfaces](#contract-surfaces) + [Compatibility Registry](#compatibility-registry).

**Consequences.** Additive metadata can be introduced without pretending that every historical artifact was newly produced. Researchers must not infer a factual revision from `$schema_version` alone - release metadata must distinguish "schema changed, values did not" from real data revisions (this is the `datasets/schema-evolution.json` ledger's job, separate from `datasets/migration-ledger.csv`). The current strict validator remains valid until compatibility rows implement the contract (a reader that has not implemented compatibility must reject non-current versions). Old-major acceptance is deliberately hard - it is a translator or retained-schema problem, not a tolerant-reader guess. The compatibility registry row in the schema-version plan becomes the single Canonical Data Model for supported versions across backend and frontend.

> **DOCTRINE NOTE (2026-06-04, plan section 22.7).** ADR-0047's writer-strict / reader-compatible contract survives the data-platform reset verbatim. The compatibility registry (`datasets/schema-compatibility.json`) and the release ledger (`datasets/schema-evolution.json`) both apply to long-format-CSV writers and readers (plan chunks B2b / X1a) the same way they applied to Parquet writers and readers. The `json-corpus` surface generalises to CSV: per-file CSV column validation (name + dtype + nullability) consumed by a typed `read_csv(columns=...)` boundary IS the schema contract for the CSV era (per CLAUDE.md DOCTRINE IN MIGRATION header, "The schema contract moves to a per-file CSV column validator (name + dtype + nullability) + a typed `read_csv(columns=...)` boundary; it is NOT the storage format and it did NOT disappear (Holy Law #3 preserved)").

---

## Rejected alternatives

This section preserves the rejected-alternatives receipts from the ADR whose rationale is folded above, verbatim and append-only per the ADR retirement contract ([decision-index.md](../../reference/decision-index.md)). Each subsection is anchored as `#adr-NNNN-rejected-alternatives` for the redirect index.

### ADR-0047 rejected alternatives

Verbatim from the originating ADR. Append-only per ADR retirement contract.

- **A. Current-only equality forever.** Rejected. It keeps validation simple, but it turns every additive schema bump into potential data churn. That is bad public-data hygiene because a changed artifact timestamp or version string can look like a factual update when no value changed.
- **B. Accept any older version with the same major.** Rejected. Semver-like ranges are too loose for public data. A minor bump can be technically additive while still requiring reader knowledge to interpret a new enum value, table footer, or manifest field.
- **C. Producer-before-reader rollout.** Rejected. The deployed frontend is static. If data is emitted before the shipped reader knows the version, citizens see avoidable failure states.
- **D. Runtime migration service.** Rejected. Production is a static GitHub Pages bundle. Runtime migration belongs either at local write time or inside a retained-schema / translator path in the static reader.
- **E. Silent defaulting for old fields.** Rejected. Guessing a missing historical value hides uncertainty. Missing fields are compatible only when absence is semantically honest.
- **F. Permanent Python and TypeScript compatibility constants.** Rejected. Duplicate local constants drift. A temporary mirror may exist only with a drift test and a row that removes or regenerates it from the shared contract.

---

## See also

- [ADR-0047](../../reference/decision-index.md)
- [docs/reference/schemas.md](../../reference/schemas.md)
- [docs/architecture/backend/validator.md](../backend/validator.md)
- [docs/architecture/data/canonical-store.md](canonical-store.md)
- [docs/architecture/testing.md](../testing.md)
- [docs/concepts/data-provenance.md](../../concepts/data-provenance.md)
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md)
