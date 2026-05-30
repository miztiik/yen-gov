# Schema Evolution

**Last Updated**: 2026-05-30

This document is the operational policy for evolving yen-gov schema contracts without unnecessary data rebuilds. [ADR-0047](../decisions/0047-schema-version-compatibility-contract.md) records the decision; this page records the working rules.

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
| Backend writers, including `core.io.write_artifact` | Emit current schema metadata only. |
| Backend Tier B validator | Validates corpus artifacts against current or explicitly compatible contracts by consuming `datasets/schema-compatibility.json` for `json-corpus`. |
| Frontend JSON corpus contract | Defends the static corpus the frontend consumes by using the same `json-corpus` compatibility contract as backend Tier B. |
| Canonical manifest reader | Checks manifest/table versions before registering Parquet files. |
| `datasets/schema-compatibility.json` | Single machine-readable source for supported reader versions across runtimes. Its schema lives at `datasets/schemas/schema-compatibility.schema.json`. |
| `datasets/schema-evolution.json` | Public release ledger for schema changes: which schema moved, whether values/provenance/methodology changed, and which historical schema file validates old declared versions. Its schema lives at `datasets/schemas/schema-evolution.schema.json`. |
| `datasets/schemas/archive/<schema>/v<version>/<schema-file>` | Retained historical JSON Schema documents used for declared-version validation when the current schema cannot honestly validate old artifacts. |

## Compatibility Registry

`datasets/schema-compatibility.json` is the data-owned compatibility contract introduced by Row C of the schema-version compatibility plan. It is a contract surface, not a generated data snapshot, and it answers only one question: which schema versions a reader surface may accept.

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

## Stop Conditions

Stop and escalate if a proposed compatibility path would:

- Change the meaning of a number.
- Weaken provenance or churn `source_id` without a citation-identity change.
- Hide or smooth over a methodology break.
- Accept old major versions without retained schemas, translators, or migrations.
- Assert `values_changed=false` without deterministic evidence that values, keys, periods, row inclusion, and methodology are unchanged.
- Require guessing, silent defaulting, or lossy coercion.
- Leave durable policy only in a TODO plan.

## See also

- [ADR-0047](../decisions/0047-schema-version-compatibility-contract.md)
- [docs/reference/schemas.md](../../reference/schemas.md)
- [docs/architecture/backend/validator.md](../backend/validator.md)
- [docs/architecture/data/canonical-store.md](canonical-store.md)
- [docs/architecture/testing.md](../testing.md)
- [docs/concepts/data-provenance.md](../../concepts/data-provenance.md)
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md)
