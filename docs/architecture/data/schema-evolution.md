# Schema Evolution

**Last Updated**: 2026-06-12

This document is the operational policy for evolving yen-gov schema contracts without unnecessary data rebuilds. [ADR-0047](../../reference/decision-index.md) records the decision; this page records the working rules.

> **Status note (2026-06-12).** The OWID-conformance question ("should `$schema_version` exist on data files at all?") was debated and CLOSED on 2026-06-12 with the user verdict to keep the field as a PERMANENT NAMED DIVERGENCE from OWID. The four OWID concerns the field allegedly conflates are already covered by yen-gov-native surfaces (`x-version` on `.schema.json`; `_meadow/<source>/<vintage>/` + `_ops/` / `.runtime/` for freshness; `source.csv.vintage` per ADR-0042 for publisher edition; `indicators.json.update_period_days` per ADR-0046 for cadence). The chronic drift hazard on 5 hardcoded `"1.0"` tool sites was repaired in the same closure PR via `yen_gov.core.schema_registry.schema_version(<file>)` per CLAUDE.md section 11. The current writer-strict / reader-compatible policy below stays in force unchanged. Closure receipt is captured in [§Schema-version field stamping (permanent named divergence)](#schema-version-field-stamping-permanent-named-divergence) below; the original execution plan-doc (PR-0 ratified verdicts + 4-persona debate trail) is archived at [docs/archive/plans/20260612-schema-version-field-refactor-plan.md](../../../docs/archive/plans/20260612-schema-version-field-refactor-plan.md).

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

## Schema-version field stamping (permanent named divergence)

**Status (2026-06-12, closed via Path A).** The OWID-conformance question on whether to retire `$schema_version` from data emit files was debated on 2026-06-12 by Gregor + Hans + Max + Fowler personas and CLOSED as a **permanent named divergence** per user verdict. This section is the durable closure receipt; the original 4-persona debate trail + PR-0 ratified verdicts + scoped-pivot PR sequence + Path A vs Path B vs Path C user-decision menu are preserved in the archived plan-doc at [docs/archive/plans/20260612-schema-version-field-refactor-plan.md](../../../docs/archive/plans/20260612-schema-version-field-refactor-plan.md).

### What was decided

yen-gov continues to stamp `$schema_version` at the top of every JSON artifact in `datasets/` populated from the schema's own `x-version`. This is a documented divergence from OWID (whose data files carry no such stamp) and survives because:

1. **The citizen never sees the field.** It is operator-axis metadata not surfaced on any chart, source-pill, IndicatorDoc page, or About copy. The OWID-alignment doctrine is a fallback for citizen-surface decisions; this is not a citizen-surface decision.
2. **The four OWID-named concerns are already realised in yen-gov via four separate native surfaces.** See the table below.
3. **Adding OWID's `origin.date_accessed` as a 6th column on `source.csv` would re-open the 5-col binding contract** ratified one day earlier (2026-06-11 ADR citation-ledger-5col in [docs/concepts/data-provenance.md](../../concepts/data-provenance.md)) and re-introduce the `fetched_at smear` failure mode from /memories/lessons.md 2026-05-16. The cost of OWID grammar conformance exceeds the benefit in this specific case.
4. **The five-PR scoped pivot (Path B) was a legitimate alternative.** It was rejected on cost-benefit: 5-7 PRs of writer + schema + on-disk + browser-smoke churn against zero citizen-axis signal gain. The plan-doc's archived section 5 records Path B in full for the next time this question is re-litigated.

| OWID concern | yen-gov-native surface that already covers it |
| --- | --- |
| Schema-shape identity | `.schema.json` file's `x-version` (already canonical). The duplicated `$schema_version` stamp on the data file is documentation grade, not load-bearing for the validator (Tier-B reads `$schema` URL to resolve the schema). |
| Data freshness pointer (`origin.date_accessed`) | `datasets/<family>/_meadow/<source>/<vintage>/` operator snapshot directories + `.runtime/<adapter>/<source_id>.json` sidecars + `_ops/indicators-completeness.json` overlays. The snapshot directory IS the OWID `date_accessed` (immutable per snapshot; new fetch = new directory). |
| Publisher edition tag (`origin.version_producer`) | `source.csv.vintage` per [ADR-0042](../../concepts/data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor). Semantic STRONGER than OWID's `version_producer` because it covers vintaged AND operator-snapshot-anchored sources in one field. |
| Expected refresh cadence (`dataset.update_period_days`) | `datasets/taxonomy/indicators.json` `update_period_days` per ADR-0046. Already on every indicator catalogue row (sampled 100+ rows, zero nulls). Enforced by Tier-B `tier_b_indicator_freshness_declared`. |

### Drift hazard repair (same PR)

Five tool sites historically stamped a hardcoded `"1.0"` literal that did NOT auto-track schema bumps:

- `tools/gen_election_tile_layouts.py` (layout + scopes writers)
- `tools/lgd/parse_lgd_export.py` (parse-receipt writer)
- `tools/lgd/snapshot.py` (CSV sources sidecar writer)
- `tools/boundaries/enrich_census_code_2011.py` (sidecar + coverage writers)

All six emit sites now source `$schema_version` from `yen_gov.core.schema_registry.schema_version(<file>)` per CLAUDE.md section 11 ("Code never hand-types schema-version literals"). The helper reads `datasets/schemas/<file>.schema.json`'s `x-version` once at import time and caches; drift is impossible by construction. CLAUDE.md section 4 forbids importing backend RUNTIME modules from `tools/`; `schema_registry` is a metadata helper that reads `datasets/schemas/` directly, not a runtime module, so the import is in scope and matches the precedent in `tools/emit_indicators_completeness_index.py` (the one already-well-behaved tool that loads the schema dict to read `x-version`).

### What this means for new artifacts going forward

New schemas and new writers continue to stamp `$schema_version` per the existing template (writer-strict per [ADR-0047](#adr-0047-schema-version-compatibility-contract) survives unchanged). Code MUST source the value via `schema_registry.schema_version(<file>)` — never a hand-typed literal. The next time the OWID-conformance question is raised, point at this section + the archived plan-doc; do not re-litigate.

### Cross-links

- [`docs/concepts/owid-alignment.md`](../../concepts/owid-alignment.md) — Named divergence #5 (permanent).
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md) — 5-col `source.csv` binding contract (2026-06-11); reason this divergence survives.
- [`CLAUDE.md` section 10](../../../CLAUDE.md) — `$schema_version` is not on the anti-pattern stack; control-plane carve-out for `generated_at` survives unchanged.
- [`CLAUDE.md` section 11](../../../CLAUDE.md) — "Code never hand-types schema-version literals"; this section's drift-hazard repair enforces it.
- [docs/archive/plans/20260612-schema-version-field-refactor-plan.md](../../../docs/archive/plans/20260612-schema-version-field-refactor-plan.md) — archived execution plan-doc with full 4-persona debate trail + PR-0 ratified verdicts + Path A vs B vs C user-decision menu.

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

The operational rules (writers strict, readers compatible by contract, reader-before-producer, fail loud, no mechanical restamp) plus the supporting contract surfaces (`x-version`, `canonical.csv_writer.write_csv` (post-B4-pt3; the predecessor write path was retired in the rip), backend Tier B, frontend JSON corpus contract, canonical manifest reader, `datasets/schema-compatibility.json`, `datasets/schema-evolution.json`, retained historical schemas under `datasets/schemas/archive/...`) are formalised above in [Policy Summary](#policy-summary) + [Contract Surfaces](#contract-surfaces) + [Compatibility Registry](#compatibility-registry).

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
