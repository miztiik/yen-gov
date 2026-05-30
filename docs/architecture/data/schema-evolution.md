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
| Backend Tier B validator | Validates corpus artifacts against current or explicitly compatible contracts. Until compatibility code lands, it may keep latest-only equality. |
| Frontend JSON corpus contract | Defends the static corpus the frontend consumes. It must converge on the same compatibility contract as backend Tier B. |
| Canonical manifest reader | Checks manifest/table versions before registering Parquet files. |
| `datasets/schema-compatibility.json` | Single machine-readable source for supported reader versions across runtimes. Its schema lives at `datasets/schemas/schema-compatibility.schema.json`. |

## Compatibility Registry

`datasets/schema-compatibility.json` is the data-owned compatibility contract introduced by Row C of the schema-version compatibility plan. It is a contract surface, not a generated data snapshot.

The registry has two policy layers:

- **Defaults** name each reader surface's baseline behavior. The JSON corpus surface is current-schema only until backend and frontend readers consume the registry. The canonical manifest reader is unsupported unless an override lists the schema/version pair.
- **Overrides** name explicitly accepted versions for a surface and schema. Row C seeds only additive minor versions that the current schema can still validate: `manifest.schema.json` v1.0-v1.3 and `observation.schema.json` v1.0-v1.1.

The registry deliberately does not copy old-major frontend constants whose current schemas have since moved to a higher major. Old majors need retained schemas, a translator, migration, or fail-loud rejection. Row G owns retiring local frontend constants as an authority; Row E and Row F own backend and frontend JSON corpus consumption.

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

Row H of the schema-version compatibility plan owns the durable release metadata surface that records these distinctions. Until that lands, docs and PR bodies must use this language plainly.

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
- Frontend contract tests use the same compatibility contract as backend validation once Row C/F land.
- Literal version strings are acceptable in named historical fixtures; otherwise use schema-registry lookups.

## Stop Conditions

Stop and escalate if a proposed compatibility path would:

- Change the meaning of a number.
- Weaken provenance or churn `source_id` without a citation-identity change.
- Hide or smooth over a methodology break.
- Accept old major versions without retained schemas, translators, or migrations.
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
