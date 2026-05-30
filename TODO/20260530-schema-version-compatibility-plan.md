# Schema Version Compatibility Plan

**Last Updated**: 2026-05-31
**Status**: Closing - PR-A merged as #459; Row B merged as #461; Row C merged as #463; Row D merged as #466; Row E merged as #467; Row F merged as #470; Row G1 merged as #473; Row G2 merged as #477; Row H merged as #480 (`87d108b0`); Row I closed N/A as #482 (`fa873294`); Row J deferred as #483 (`bdcd0f96`); Row K closing as #484.
**Correction level**: 5 - core data contract / validator / runtime-reader semantics. Design rows first; code rows execute only after the policy row lands.
**Doc-class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). Durable doctrine must be distilled into `docs/` before this plan closes.
**Authority**: Gregor owns contract / integration; Fowler owns engineering slicing and test cleanup; Hans + Max own data-shape / public-data semantics; user mandate authorizes autonomous execution except for major unresolved decisions.

## 0. Mandate

User, 2026-05-30, paraphrased from chat:

> Make a TODO plan for the schema-version compatibility work. Use subagents and custom agents to resolve ambiguity. Break it into logical sequential PRs for a multi-agent system. Decompose durable decisions into `/docs` memory when done. Run autonomously; no human intervention unless a major change is unresolvable by custom agents. Merge each PR to main and continue to the next step autonomously.

## 1. Load-bearing context

- [CLAUDE.md](../CLAUDE.md) Holy Laws #1, #2, #3, #4, #6, #9, and #10.
- [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md) - current Tier A / Tier B split.
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) - Parquet manifest and reader compatibility doctrine.
- [docs/reference/schemas.md](../docs/reference/schemas.md) - current strict JSON `$schema_version == x-version` rule.
- [docs/architecture/testing.md](../docs/architecture/testing.md) - test-tier policy and no-pytest-real-corpus rule.
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md) - OWID as fallback doctrine for socio-economic data modelling.
- [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md) and [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) - source identity and provenance trust floor.

## 2. Current finding

The repo currently has two different version policies:

1. **JSON artifacts and config** use latest-only equality. `backend/yen_gov/validate.py` Tier B rejects any file whose `$schema_version` does not equal the current schema `x-version`. The frontend `datasets-conform` contract repeats that rule.
2. **Canonical Parquet / manifest loading** already uses a reader compatibility set through `SUPPORTED_SCHEMA_VERSIONS`, but not every runtime path is guaranteed to route through it.

This means an additive schema change can trigger version-only rewrites of unchanged JSON artifacts. That protects current-corpus hygiene, but it is not a good long-term public-data archival policy. A citizen or researcher needs to know whether numbers changed, not just whether the envelope was restamped.

## 3. Resolved doctrine

The custom-agent panel converged on this split:

- **Writer strictness stays**: current writers emit the current schema version and reject stale hand-typed schema metadata.
- **Reader / corpus compatibility becomes explicit**: readers and validators may accept older versions only when a compatibility contract says they are supported.
- **Additive minor changes should not force mechanical data rebuilds** when the artifact shape and values do not change.
- **Breaking major changes require migration, archival validation, or fail-loud rejection**. No best-effort coercion.
- **Historical/public snapshots validate against their declared contract** once versioned schema resolution exists.
- **No provenance weakening**: `source_id`, source vintage, methodology breaks, row counts, and value-change status must remain auditable.

## 4. Non-goals

- No production backend or runtime migration service.
- No silent defaults for missing historical fields.
- No acceptance of old major versions without retained schemas or an explicit translator.
- No broad corpus rewrite just to update `$schema_version` strings.
- No one-shot mega-PR touching backend validator, frontend runtime, docs, tests, and data in one move.

## 5. Subagent responsibilities

| Agent | Responsibility in this plan | When to dispatch |
| --- | --- | --- |
| Gregor Hohpe (Architect) | Compatibility contract, registry home, write/read boundary, migration topology. | Every policy or cross-runtime contract PR. |
| Fowler (Engineering) | PR slicing, test refactor safety, behavior-vs-structure separation. | Before any test cleanup or validator behavior PR. |
| Hans (Governance) | Public-data trust, historical snapshot semantics, provenance and methodology-break visibility. | Before archival validation, migration ledger, or no-rebuild gates. |
| Max (Indicator Scout) | OWID / public-data practice, indicator catalogue implications, additive-vs-breaking doctrine. | Before schema policy docs and indicator-catalogue pilot rows. |
| Jony + Citizen | Citizen-facing copy if runtime failure states or source chips change. | Only if UI copy or visible route behavior changes. |

Subagent verdicts are advisory. If they conflict, apply [CLAUDE.md](../CLAUDE.md) section 0a authority assignment; if still unresolved, stop and ask the user.

## 6. PR ledger

Update this table in every PR. Do not skip rows. Each PR should be small enough for another agent to own without reading the whole history.

| Row | PR | Status | Owner agents | Scope | Acceptance gates | Stop conditions |
| --- | :---: | --- | --- | --- | --- | --- |
| A | #459 | Merged (`fd9c3376`) | Gregor + Fowler + Hans + Max | Create this plan-doc. No runtime behavior. | File exists under `TODO/`; status ledger and PR DAG are clear; `git diff --check` clean. | Stop if unrelated dirty worktree changes would need staging. |
| B | #461 | Merged (`e7afe058`) | Gregor + Fowler + Hans + Max | Durable policy docs: create an ADR for the compatibility decision and a living subsystem doc at `docs/architecture/data/schema-evolution.md`; amend `docs/reference/schemas.md`, `docs/architecture/backend/validator.md`, `docs/architecture/data/canonical-store.md`, `docs/architecture/testing.md`, and `CLAUDE.md` section 11 if the strict JSON rule changes. | ADR records rejected alternatives; subsystem docs define writer-strict vs reader-compatible semantics; reader-before-producer rollout order is resolved once; changed docs have H1, Last Updated, See also; `git diff --check` clean; no runtime, schema, registry, or data behavior changes. | Stop if policy would allow old major versions without retained schemas / translator. |
| C | #463 | Merged (`099a7890`) | Gregor + Fowler | Compatibility contract surface. Preferred target: a single data-owned registry such as `datasets/schema-compatibility.json` plus `datasets/schemas/schema-compatibility.schema.json`, seeded current-only except for already-supported canonical reader versions. The registry is the single compatibility contract consumed by backend and frontend; any temporary Python/TS mirror must have a drift test and a removal row. | Registry validates; tests prove schema format and that registry overrides do not outrun the current TS reader constant; Row G retires stale local constants as an authority. No validator behavior change yet. | Stop if a simpler schema-embedded field is proven better by Gregor + Fowler. |
| D | #466 | Merged (`b9d5cd93`) | Fowler | Structural test cleanup in tests only. Replace current-version magic literals with registry/schema lookups where tests are about current writer behavior. Keep literal version strings only in named historical-compatibility fixtures, with the test name or assertion making that purpose explicit. | Targeted pytest for schema registry / validator / affected seed tests; grep confirms no unannotated current-version literals remain in touched tests; no production logic, validator behavior, schema, registry, or data files changed. | Stop if a test is the only guard for a real historical fixture. |
| E | #467 | Merged (`24083707`) | Gregor + Fowler | Backend Tier-B compatibility. Keep `core/io.py` writer-strict, but let validator accept versions allowed by the compatibility contract. Before Row H, accepted old JSON versions must be additive minors that still validate against the current schema; declared-version schema resolution waits for retained schemas. Add fixture tests for supported old additive minor, unsupported future/major, writer stale-version rejection, and accepted-version-but-incompatible-current-schema rejection. | `pytest -q backend/tests/test_validate.py backend/tests/test_core_io.py`; full backend pytest per repo baseline; `python -m yen_gov validate --root .`. | Stop if implementation needs real-corpus pytest walking or accepting an old version requires a historical schema not yet retained. |
| F | #470 | Merged (`54ffba8e`) | Gregor + Fowler | Frontend JSON corpus contract. Make `frontend/src/contracts/datasets-conform.test.ts` use the same compatibility contract instead of current-only equality. Ajv validation stays fail-loud. | Targeted vitest for `datasets-conform`; full `bun run test` in `frontend`. | Stop if contract needs a runtime network dependency or stale copied compatibility constants. |
| G1 | #473 | Merged (`bc3cebd2`) | Gregor + Fowler | Structural frontend compatibility cleanup. Make the canonical runtime compatibility set derive from the Row C contract, or from a generated module whose source is that contract; retire the shadow `SUPPORTED_SCHEMA_VERSIONS` constant as an authority. No runtime behavior change. | Targeted vitest for `frontend/src/lib/canonical/manifest.test.ts`; a drift test proves the frontend runtime set and Row C contract cannot disagree; full `bun run test` in `frontend`. | Stop if the frontend would need a runtime network fetch before `manifest.json`. |
| G2 | #477 | Merged (`9a774431`) | Gregor + Jony if copy changes | Runtime manifest / Parquet reader behavior. Enforce supported table versions consistently at manifest lookup / registration and keep unsupported versions fail-loud. Do not design mixed-schema projection in this row. | Frontend unit tests for supported old minor and unsupported future/major; browser smoke on one canonical-backed route if runtime behavior changes; unsupported version still fails loud. | Stop if mixed Parquet schemas require `union_by_name` or projection defaults not yet designed. |
| H | #480 | Merged (`87d108b0`) | Hans + Max + Gregor + Fowler | Schema-evolution release metadata contract. Define how historical snapshots validate by declared version, how old schemas are retained, and which durable public surface records `schema changed, values did not`: separate `datasets/schema-evolution.json` ledger with `datasets/schemas/schema-evolution.schema.json`. No pilot schema bump in this row. | Chosen path, columns/fields, and ownership are named in docs; parser/schema tests cover `values_changed=true`, `values_changed=false`, and missing old-schema references; existing canonical-pivot ledger semantics are not silently repurposed. | Stop if old schemas are not recoverable by version or if the ledger surface would overload an existing artifact without a documented migration. |
| I | #482 | N/A - no named near-term metadata candidate after Row H | Fowler + Hans + Max | Assessed after Row H (#480 / `87d108b0`). Do not invent an optional field to prove the mechanism: Rows E/F/H already cover backend compatibility, frontend corpus compatibility, retained-schema resolution, and `values_changed` ledger semantics with fixtures. Agent review found only already-shipped, obsolete, or feature-coupled/provenance/citizen-semantics items outside Row I's stop conditions. | N/A - no schema, data, ledger, or runtime change. Fixture coverage from Rows E/F/H remains the proof until a real schema-release event exists. | Reopen only when a named additive metadata need can keep unchanged artifact bytes unchanged and does not touch observation Parquet, provenance, `source_id`, or citizen-visible semantics. |
| J | #483 | Deferred - no justified breaking schema change now | Gregor + Fowler + Hans + Max | Assessed after Rows E/H and Row I (#482 / `fa873294`). Do not invent a contraction, rename, removal, type narrowing, or semantic shift to prove the mechanism. OWID/public-indicator practice favours stable contracts, additive metadata, retained historical schemas, and fail-loud old-major rejection unless the current schema is actively misleading for a real consumer. Current scan found only already-shipped breaks, compatibility aliases still serving their window, or future trigger-gated migrations. | N/A - no schema, data, ledger, or runtime change. Rows E/F/G2/H fixtures and retained-schema ledger semantics remain the proof surface for unsupported old-major rejection until a real breaking schema-release event exists. | Reopen only for a named breaking need with consumer inventory, migration or retained-schema/translator path, rollback note, schema-evolution ledger entry, and Hans + Max signoff if meanings change. |
| K | #484 | Closing | Fowler | Plan distillation and closure. Durable doctrine was already lifted into `docs/` by Rows B-H; this row adds the missing no-pilot trigger rule, refreshes validator reference docs, and marks this plan as a closed audit ledger. | Durable doctrine lives in `docs/`; this TODO contains only execution history and a distillation map; no stale TODO-only architecture remains. | Stop if docs disagree after distillation. |

## 7. Execution rules

1. Work one row per PR unless the row says otherwise.
2. Each PR updates this ledger from `_pending_` to the actual PR number and status.
3. Use subagents listed in section 5 before any row that changes policy or runtime behavior.
4. Stage exact paths only. Ignore unrelated dirty files.
5. Merge each PR to main after gates pass, then continue to the next row autonomously.
6. If `gh pr merge --squash --delete-branch` reports the known worktree-local `main` cleanup error, verify server-side merge state before manual branch cleanup.
7. After the final row, distill this plan into the canonical docs per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) if present on the current main branch.
8. Do not execute Rows I or J just to demonstrate machinery. They are trigger rows for real schema needs; fixture tests in earlier rows are enough when no real candidate exists.

## 8. Version-change taxonomy

| Change class | Version bump | Rebuild duty | Reader duty | Ledger duty |
| --- | --- | --- | --- | --- |
| Description / docs only | None | Forbidden unless emitted bytes genuinely change for another reason. | None. | None. |
| Optional metadata field | Minor | New writers emit new version; old artifacts may stay if compatible. | Accept old minor only if missing field has honest null/absent semantics. | Record values-changed = false if artifacts are intentionally not rebuilt. |
| Optional enum widening | Minor | Rebuild only affected artifacts using the new enum value. | Reader must tolerate the widened value before data ships. | Record whether values changed. |
| Required field after backfill | Minor or major by contract review | Backfill affected artifacts first; then tighten. | Reject missing field after contract phase. | Migration row required. |
| Rename / removal / type narrowing | Major | Migrate or retain old versioned schema. | Old major accepted only through explicit translator. | Migration row required. |
| Semantic meaning change | Major plus Hans + Max review | Rebuild only with a value-preserving migration or explicit methodology break. | Surface methodology break; never smooth trends across it. | Migration row plus methodology-break row where relevant. |
| Parquet physical layout change | Minor or major by reader impact | Only affected table/partition; manifest and footer metadata must agree. | Fail loud unless supported; design mixed-schema reads before allowing them. | Migration row required. |

## 9. Acceptance gates by surface

- **Docs-only row**: `git diff --check`; changed docs have H1, Last Updated, See also where applicable.
- **Backend validator row**: targeted pytest plus full backend pytest under current repo baseline; `python -m yen_gov validate --root .` when schemas/data are touched.
- **Frontend contract row**: targeted vitest plus full `bun run test` in `frontend`.
- **Runtime frontend row**: svelte-check, vitest, and browser smoke per [CLAUDE.md](../CLAUDE.md) section 13.
- **Schema/data row**: validator, schema-evolution ledger entry when a release event exists, no unexpected row-count/value/source FK churn.

## 10. Open questions resolved by the row owners

- **Compatibility registry home**: Row C starts with a data-owned registry as the preferred design. Gregor + Fowler may choose schema-embedded accepted-version metadata only if it reduces drift without scattering policy.
- **Historical schema storage**: Row H resolved this as retained repo files under `datasets/schemas/archive/<schema-stem>/v<major>.<minor>/<schema-file>`, referenced by `datasets/schema-evolution.json` with SHA-256. No old-major acceptance without one of these retained schemas, a translator, or a migration.
- **Parquet mixed-schema reads**: Row G2 requires supported homogeneous table versions at manifest lookup/registration. Explicit projection or `union_by_name` remains deferred until a real mixed-schema need exists.
- **Public release metadata**: Row H resolved this as `datasets/schema-evolution.json`; `datasets/migration-ledger.csv` remains scoped to canonical-pivot artifact disposition.

## 11. Stop conditions

- A row would change the meaning of a number: denominator, entity identity, period axis, methodology, source identity, or value semantics.
- A row would weaken provenance, hide a methodology break, or churn `source_id` without Hans + Max + Gregor signoff.
- Compatibility would require guessing or lossy coercion.
- Pytest would walk the real corpus.
- A PR needs broad staging, stash, reset, or cleanup of unrelated worktree changes.
- The plan row's durable decision has no home in `docs/` after it ships.

## 12. See also

- [CLAUDE.md](../CLAUDE.md)
- [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md)
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md)
- [docs/reference/schemas.md](../docs/reference/schemas.md)
- [docs/architecture/testing.md](../docs/architecture/testing.md)
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md)
- [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md)

## Plan complete

Closed 2026-05-31. Rows A-K are complete; this file remains as the audit ledger and should not be used as the live source of architecture doctrine.

Distillation map:

- Rows A/B -> [ADR-0047](../docs/architecture/decisions/0047-schema-version-compatibility-contract.md), [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md), and [docs/reference/schemas.md](../docs/reference/schemas.md).
- Row C -> [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md) Compatibility Registry.
- Row D -> [docs/architecture/testing.md](../docs/architecture/testing.md) and the fixture-literal policy in [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md).
- Row E -> [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md) Schema-version compatibility.
- Row F -> [docs/reference/schemas.md](../docs/reference/schemas.md) and [docs/architecture/testing.md](../docs/architecture/testing.md) frontend corpus contract policy.
- Rows G1/G2 -> [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) and [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md) canonical manifest reader policy.
- Row H -> [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md) Release Metadata Ledger and Retained Historical Schemas.
- Rows I/J -> [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md) no-pilot schema-release rule.
- Row K -> this closure block plus the reference-doc refresh in [docs/reference/schemas.md](../docs/reference/schemas.md) and [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md).

New schema-version compatibility work starts with a fresh plan-doc or a focused PR against the canonical docs above.
