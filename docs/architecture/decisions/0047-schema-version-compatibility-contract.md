# ADR-0047: Schema Version Compatibility Contract

**Last Updated**: 2026-05-30
**Status**: accepted
**Deciders**: Gregor (contract), Fowler (rollout), Hans + Max (public-data semantics)

## Context

JSON schemas under `datasets/schemas/` already carry `x-version` and `x-changelog`. JSON artifacts under `datasets/` and `config/` declare `$schema` and `$schema_version`. Before this ADR, backend Tier B and the frontend corpus contract treated any artifact whose declared version did not equal the current schema `x-version` as invalid.

That current-only rule is useful at the writer boundary, but it conflates two different events:

- The artifact's envelope changed: schema shape, validation metadata, manifest shape, or footer metadata changed.
- The facts changed: values, entity identity, period axis, denominator, indicator identity, methodology, provenance, or row inclusion changed.

The canonical Parquet reader already has a compatibility idea through `SUPPORTED_SCHEMA_VERSIONS`, but that idea is local to the frontend. The JSON validator and frontend JSON corpus test have no shared compatibility contract yet. Additive schema changes therefore risk forcing restamps or rebuilds whose only observable effect is a version string changing.

## Decision

Adopt a writer-strict, reader-compatible schema-version contract.

1. Writers emit only the current schema version. A backend writer must continue to reject stale caller-supplied schema metadata.
2. Readers and validators may accept older artifact versions only through an explicit compatibility contract.
3. Reader support ships before producer output. A writer must not emit a new version until every intended reader can accept it or fail loud with a documented reason.
4. Additive minor changes may be compatible without rebuilding unchanged artifacts when absent fields have honest null/absent semantics.
5. Breaking major changes require migration, retained historical schemas, an explicit translator, or fail-loud rejection.
6. No reader may accept an old major version by best-effort coercion.
7. Schema-only changes must not churn `source_id`, source vintage, row counts, methodology-break rows, or observation values.
8. Future implementation work must converge backend and frontend on one machine-readable compatibility contract. Temporary Python or TypeScript mirrors are acceptable only with drift tests and a removal path.

## Consequences

- Additive metadata can be introduced without pretending that every historical artifact was newly produced.
- Researchers must not infer a factual revision from `$schema_version` alone. Release metadata must eventually distinguish `schema changed, values did not` from real data revisions.
- The current strict validator remains valid until compatibility rows implement the contract. A reader that has not implemented compatibility must reject non-current versions.
- Old-major acceptance is deliberately hard. It is a translator or retained-schema problem, not a tolerant-reader guess.
- The compatibility registry row in the schema-version plan becomes the single Canonical Data Model for supported versions across backend and frontend.

## Alternatives considered

### A. Current-only equality forever

Rejected. It keeps validation simple, but it turns every additive schema bump into potential data churn. That is bad public-data hygiene because a changed artifact timestamp or version string can look like a factual update when no value changed.

### B. Accept any older version with the same major

Rejected. Semver-like ranges are too loose for public data. A minor bump can be technically additive while still requiring reader knowledge to interpret a new enum value, table footer, or manifest field.

### C. Producer-before-reader rollout

Rejected. The deployed frontend is static. If data is emitted before the shipped reader knows the version, citizens see avoidable failure states.

### D. Runtime migration service

Rejected. Production is a static GitHub Pages bundle. Runtime migration belongs either at local write time or inside a retained-schema/translator path in the static reader.

### E. Silent defaulting for old fields

Rejected. Guessing a missing historical value hides uncertainty. Missing fields are compatible only when absence is semantically honest.

### F. Permanent Python and TypeScript compatibility constants

Rejected. Duplicate local constants drift. A temporary mirror may exist only with a drift test and a row that removes or regenerates it from the shared contract.

## See also

- [docs/architecture/data/schema-evolution.md](../data/schema-evolution.md)
- [docs/reference/schemas.md](../../reference/schemas.md)
- [docs/architecture/backend/validator.md](../backend/validator.md)
- [docs/architecture/data/canonical-store.md](../data/canonical-store.md)
- [docs/architecture/testing.md](../testing.md)
- [docs/concepts/data-provenance.md](../../concepts/data-provenance.md)
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md)
