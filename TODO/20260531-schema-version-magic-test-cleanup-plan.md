# Schema Version Magic Test Cleanup Plan

**Last Updated**: 2026-05-31
**Status**: ACTIVE - plan-doc written for execution against `main`; implementation rows not started.
**Correction level**: 4 - cross-cutting cleanup across backend tests, frontend runtime, tools emitters, and docs. Escalate to Level 5 if a row changes canonical schema semantics rather than test/emitter mechanics.
**Doc-class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). Durable doctrine must be distilled into `docs/` before this plan closes.
**Base branch discipline**: every execution PR branches from `origin/main`, not from this plan-doc branch and not from another active worktree branch.
**Fowler review**: 2026-05-31 `runSubagent` review applied. The key correction is that this is a classification-and-relationship cleanup, not a literal bump sprint.

## 0. Mandate

User request, 2026-05-31:

> Are these the only tests that test for magic string? Are we removing all point number checks like these across the app and adding documentation under `/docs` to avoid this in the future in testing strategy? Review the plan with Fowler and write the plan into TODO so another agent can pick up the work if needed. Plan the work in chunks and use `runSubagent`.

The answer from the audit is **no**: the original failing tests are not the only current-schema point pins. This plan turns the audit into PR-sized work that another agent can execute without this chat history.

## 1. Load-bearing context

- [CLAUDE.md](../CLAUDE.md) Holy Laws #3, #4, #5, #6, and #10.
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) - load before any execution turn.
- [docs/agents/guardrails.md](../docs/agents/guardrails.md) - authority, git hygiene, and stop conditions.
- [docs/architecture/testing.md](../docs/architecture/testing.md) - test-tier policy and fixture conventions.
- [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md) - validator Tier A / Tier B split.
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) - canonical store and runtime-reader contract.
- [docs/architecture/decisions/0045-grapher-catalogue-split.md](../docs/architecture/decisions/0045-grapher-catalogue-split.md) - render hints live in grapher, not canonical indicator schema.
- [TODO/20260530-schema-version-compatibility-plan.md](20260530-schema-version-compatibility-plan.md) - related compatibility policy plan. This plan is narrower: stale current-version literals and tests.

## 2. Doctrine locked by Fowler

Schema-version tests must prove a relationship or behavior, not the current point value.

**Forbidden pattern** when the literal means "current":

```python
assert schema["x-version"] == "6.0"
assert payload["$schema_version"] == "6.0"
assert schema["x-changelog"][-1]["date"] == "2026-05-26"
```

**Required replacement**:

- Backend production code/tests source current schema versions through `yen_gov.core.schema_registry.schema_version("<file>")` / `schema_id("<file>")` when backend imports are legal.
- `tools/` code does **not** import backend runtime modules. Tools that emit schema-stamped artifacts read the schema JSON file directly or use a tools-local helper with a drift test.
- Frontend code uses one named frontend policy constant/helper for emitted current versions, guarded by a test against `datasets/schemas/<file>.schema.json`.
- Tests may assert `artifact["$schema_version"] == schema["x-version"]`, `changelog[-1]["version"] == schema["x-version"]`, or behavior introduced by a schema version.
- Explicit literals are allowed only when the literal is historical input to the behavior under test: migration fixtures, backcompat cases, changelog-entry presence, intentionally bad-version rejection, or a synthetic fixture disconnected from production schemas.

**Do not bump stale literals.** Delete the assertion, replace it with a relationship, or fix the emitter.

## 3. Initial classification from audit

This table is not a substitute for the Row A grep gate. It records known surfaces so another agent starts from facts rather than chat memory.

| Class | Known files | Expected treatment |
| --- | --- | --- |
| Stale current-version tests | [backend/tests/test_indicator_schema_v5.py](../backend/tests/test_indicator_schema_v5.py), [backend/tests/test_livestock_naip_iv_meadow.py](../backend/tests/test_livestock_naip_iv_meadow.py), [backend/tests/test_livestock_owner_reg_meadow.py](../backend/tests/test_livestock_owner_reg_meadow.py) | Remove current point/date assertions. Keep behavior checks. Fix emitters where tests expose stale output. |
| Fragile current-version tests | [backend/tests/test_canonical_writer.py](../backend/tests/test_canonical_writer.py), [backend/tests/test_concepts_seed.py](../backend/tests/test_concepts_seed.py), [backend/tests/test_grapher_catalogue_schema.py](../backend/tests/test_grapher_catalogue_schema.py), [backend/tests/test_indicator_catalogue_schema_v2.py](../backend/tests/test_indicator_catalogue_schema_v2.py), [backend/tests/test_indicator_catalogue_schema_v21.py](../backend/tests/test_indicator_catalogue_schema_v21.py), [backend/tests/test_source_row_v2.py](../backend/tests/test_source_row_v2.py), [backend/tests/test_preflight_cli.py](../backend/tests/test_preflight_cli.py) | Replace current literals with schema-derived assertions or producer constants. Preserve behavior and historical changelog checks. |
| Frontend production stale emission | [frontend/src/lib/canonical/indicator-from-canonical.ts](../frontend/src/lib/canonical/indicator-from-canonical.ts), [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts) | Do not just change `4.4` to `6.0`. First make emitted artifacts clean for indicator schema v6.0: no `renderer_rules`, `default_mode`, or `facet_labels` in canonical indicator artifacts. |
| Frontend render-hint carryover | [frontend/src/lib/canonical/indicator-allowlist.ts](../frontend/src/lib/canonical/indicator-allowlist.ts), [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts) | Move/consume render hints through grapher policy if needed. Stop and split if this becomes a renderer architecture change. |
| Active tools emit stale indicator schema | [tools/livestock_meadow_naip_iv.py](../tools/livestock_meadow_naip_iv.py), [tools/livestock_meadow_owner_reg.py](../tools/livestock_meadow_owner_reg.py), [tools/livestock_meadow_pashu_aadhaar.py](../tools/livestock_meadow_pashu_aadhaar.py), [tools/rbi_hbs_ingest_state_gdp.py](../tools/rbi_hbs_ingest_state_gdp.py) | Fix active emitters. Tools must not import backend runtime; source schema version through schema JSON or a tools-local helper with tests. |
| Other production literals needing classification | [backend/yen_gov/preflight/\_\_init\_\_.py](../backend/yen_gov/preflight/__init__.py), [backend/yen_gov/sources/iced_power/fetch_pipeline.py](../backend/yen_gov/sources/iced_power/fetch_pipeline.py), [backend/yen_gov/pipeline/run.py](../backend/yen_gov/pipeline/run.py), [backend/yen_gov/pipeline/canonical_eci_backfill.py](../backend/yen_gov/pipeline/canonical_eci_backfill.py), [backend/yen_gov/canonical/adapters/eci_ae_panel.py](../backend/yen_gov/canonical/adapters/eci_ae_panel.py) | Classify as current producer stamp, row-schema constant, synthetic event version, or historical fixture before editing. |
| Explicit exclusions | [backend/tests/test_validate.py](../backend/tests/test_validate.py), [backend/tests/test_schema_registry.py](../backend/tests/test_schema_registry.py), [backend/tests/test_migrate_indicators_v15_to_v20.py](../backend/tests/test_migrate_indicators_v15_to_v20.py), [frontend/src/lib/canonical/manifest.test.ts](../frontend/src/lib/canonical/manifest.test.ts), [frontend/src/contracts/datasets-conform.test.ts](../frontend/src/contracts/datasets-conform.test.ts) | Keep bad-version fixtures, migration/backcompat literals, and relationship tests. Do not weaken them. |

Out of scope for this plan: row-count sentinels, source vintage dates, fixture business dates, API mock versions, schema changelog history in `datasets/schemas/**`, and boundary stale-shard parent-directory tests unless a row explicitly says otherwise.

## 4. Subagent responsibilities

Use `runSubagent` before each row named below. Subagent verdicts are advisory; if verdicts conflict, apply [CLAUDE.md](../CLAUDE.md) section 0a authority assignment.

| Agent | Responsibility | Required before rows |
| --- | --- | --- |
| Fowler (Engineering) | Test cleanup strategy, behavior-vs-structure split, PR slicing, deletion discipline. | All rows. |
| Gregor Hohpe (Architect) | Contract boundary when producer/consumer schema policy or frontend/backend version authority changes. | Rows B, C, D, E. |
| Jony (UI/UX) | Only if frontend render-hint migration changes citizen-visible behavior or copy. | Row C if UI behavior changes. |
| Hans + Max | Only if a change can alter data semantics, provenance, or public interpretation. | Stop-and-escalate rows only; not expected for pure schema stamp cleanup. |

Prompt shape for execution agents:

```text
runSubagent(<agent>, "Review Row <row id> of TODO/20260531-schema-version-magic-test-cleanup-plan.md. Do not edit. Return must-fix risks, exact files to touch/avoid, and gates to run.")
```

## 5. PR ledger

Update this table in every PR that executes a row. Each row branches from `origin/main` and stages explicit paths only. Leave unrelated dirty worktree files alone.

| Row | PR | Status | Branch | Owner agents | Scope | Acceptance gates | Stop conditions |
| --- | :---: | --- | --- | --- | --- | --- | --- |
| A | _pending_ | Not started | `feat/schema-version-magic-plan` | Fowler | Add this TODO plan only. No runtime behavior. | File exists under `TODO/`; plan names subagent use, branch discipline, classification table, exclusions, and row gates; `git diff --check` clean. | Stop if another active plan already supersedes this exact scope on `main`. |
| B | _pending_ | Not started | `feat/schema-version-testing-doctrine` | Fowler + Gregor | Durable docs: update [docs/architecture/testing.md](../docs/architecture/testing.md), [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md), and a narrow [CLAUDE.md](../CLAUDE.md) section 11 clarification if needed. | Docs define forbidden current-version literals, allowed historical/backcompat exceptions, backend registry pattern, tools-local schema JSON pattern, frontend policy-constant pattern; docs have Last Updated and See also where required. | Stop if docs would change schema compatibility policy owned by [TODO/20260530-schema-version-compatibility-plan.md](20260530-schema-version-compatibility-plan.md). |
| C | _pending_ | Not started | `feat/frontend-indicator-v6-artifact` | Fowler + Gregor, Jony if visible behavior changes | Frontend runtime: make canonical indicator artifacts v6-shape-clean, centralize emitted indicator schema version policy, remove `4.4` stamps, update tests. | `indicator-from-canonical` tests prove no removed v6 render fields are emitted; policy test proves frontend emitted current equals `indicator.schema.json` x-version; `bun run test` targeted/full as feasible; browser smoke only if runtime route behavior changes. | Stop if render-hint migration requires broader grapher architecture work; split before changing UI semantics. |
| D | _pending_ | Not started | `feat/tools-schema-version-emitters` | Fowler + Gregor | Active emitter cleanup in `tools/` and backend producer modules. Fix stale `4.4` indicator emitters and classify current producer constants. | Tools do not import backend runtime. Tests prove emitted `$schema_version` equals source schema x-version. Targeted pytest/tool tests pass. `python -m yen_gov validate --root .` if datasets/config/schemas are touched. | Stop if a tool emits artifacts not clean under the current schema shape; fix shape before stamping current. |
| E | _pending_ | Not started | `feat/backend-schema-version-test-cleanup` | Fowler | Backend non-indicator test cleanup: canonical writer, concepts seed, grapher catalogue, source row, preflight CLI. | Current version literals removed or replaced by relationships/constants. Bad-version and historical fixtures remain named. Targeted pytest for touched files. Grep gate confirms no unclassified current pins in touched files. | Stop if a literal is the only guard for a historical behavior; rename/comment instead of deleting. |
| F | _pending_ | Not started | `feat/indicator-schema-test-cleanup` | Fowler + Gregor | Indicator schema/catalogue tests: rename stale version-specific tests where helpful; remove current point pins; add v6 render-field absence checks; preserve historical changelog checks. | Targeted pytest for indicator schema/catalogue files; tests prove behavior and relationships, not point versions. | Stop if catalogue semantics or ADR-0045 ownership would change. |
| G | _pending_ | Trigger row | `feat/stale-shard-test-cleanup` | Fowler | Boundary stale-shard tests, only if the executor's active branch still has failures that enumerate pruned parent dirs. This is not schema-version magic. | Tests assert kept shard exists and stale shard file/path is gone; no parent-dir `iterdir()` on deleted paths. Targeted pytest for changed lift tests. | Skip if current `main` already has these tests correct. Do not bundle with schema-version rows. |
| H | _pending_ | Not started | `feat/schema-magic-plan-distill` | Fowler | Plan closure: distill durable testing doctrine into docs if not already done by Row B, then archive/slim this TODO with a plan-complete map. | Durable doctrine lives in docs; this plan records where each row landed; no TODO-only architecture remains. | Stop if any execution row is still pending/actionable. |

## 6. Row execution details

### Row A - Plan-doc PR

- **Files**: this file only.
- **DoD gates**: `git diff --check`; no tests required for TODO-only docs.
- **PR body must say**: Fowler reviewed the plan through `runSubagent`; no code/runtime behavior changed.

### Row B - Testing doctrine docs

- **Files**:
  - [docs/architecture/testing.md](../docs/architecture/testing.md)
  - [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md)
  - [CLAUDE.md](../CLAUDE.md), only if the executor decides the root contract needs the same clarification.
- **Required content**:
  - Section named `Schema Versions In Tests` or equivalent.
  - Anti-pattern examples and replacement patterns.
  - Backend `schema_registry` usage.
  - `tools/` no-backend-import rule and schema JSON helper pattern.
  - Frontend current-version policy constant/helper pattern.
  - Allowed explicit-literal exceptions.
- **DoD gates**: docs-only `git diff --check`.

### Row C - Frontend indicator artifact v6 cleanup

- **Files likely touched**:
  - [frontend/src/lib/canonical/types.ts](../frontend/src/lib/canonical/types.ts)
  - [frontend/src/lib/canonical/indicator-from-canonical.ts](../frontend/src/lib/canonical/indicator-from-canonical.ts)
  - [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts)
  - [frontend/src/lib/canonical/indicator-allowlist.ts](../frontend/src/lib/canonical/indicator-allowlist.ts), only if render hints must move out of canonical descriptor metadata.
  - Grapher catalogue files/tests only if render hints need a canonical destination; split if that grows.
- **Required checks**:
  - Artifact builder no longer emits `$schema_version: "4.4"`.
  - Artifact builder does not emit indicator v6-removed fields: `renderer_rules`, `default_mode`, `facet_labels`.
  - Version policy is centralized and tested against [datasets/schemas/indicator.schema.json](../datasets/schemas/indicator.schema.json).
- **DoD gates**: targeted vitest for canonical indicator tests; full `bun run test` if feasible; `bun run check` if TypeScript surfaces changed; browser smoke only if route behavior changes.

### Row D - Active producer and tools emitters

- **Files likely touched**:
  - [tools/livestock_meadow_naip_iv.py](../tools/livestock_meadow_naip_iv.py)
  - [tools/livestock_meadow_owner_reg.py](../tools/livestock_meadow_owner_reg.py)
  - [tools/livestock_meadow_pashu_aadhaar.py](../tools/livestock_meadow_pashu_aadhaar.py)
  - [tools/rbi_hbs_ingest_state_gdp.py](../tools/rbi_hbs_ingest_state_gdp.py)
  - [backend/yen_gov/preflight/\_\_init\_\_.py](../backend/yen_gov/preflight/__init__.py)
  - [backend/yen_gov/sources/iced_power/fetch_pipeline.py](../backend/yen_gov/sources/iced_power/fetch_pipeline.py)
  - [backend/yen_gov/pipeline/run.py](../backend/yen_gov/pipeline/run.py), [backend/yen_gov/pipeline/canonical_eci_backfill.py](../backend/yen_gov/pipeline/canonical_eci_backfill.py), [backend/yen_gov/canonical/adapters/eci_ae_panel.py](../backend/yen_gov/canonical/adapters/eci_ae_panel.py), only after classification.
- **Implementation rule**:
  - Backend modules use `schema_registry` where the schema has a registry entry.
  - Tools use schema JSON reading, because [docs/agents/guardrails.md](../docs/agents/guardrails.md) forbids `tools/` importing backend runtime modules.
- **DoD gates**: targeted pytest/tool tests; `python -m yen_gov validate --root .` if committed data/config/schema artifacts change.

### Row E - Backend non-indicator test cleanup

- **Files likely touched**:
  - [backend/tests/test_canonical_writer.py](../backend/tests/test_canonical_writer.py)
  - [backend/tests/test_concepts_seed.py](../backend/tests/test_concepts_seed.py)
  - [backend/tests/test_grapher_catalogue_schema.py](../backend/tests/test_grapher_catalogue_schema.py)
  - [backend/tests/test_source_row_v2.py](../backend/tests/test_source_row_v2.py)
  - [backend/tests/test_preflight_cli.py](../backend/tests/test_preflight_cli.py)
- **Keep**:
  - Synthetic `9.9` bad-version fixtures.
  - Historical v1/v2 example rows when the test is about rejection or migration.
  - Relationship tests such as `$schema_version == x-version`.
- **Remove or replace**:
  - Literal current `1.0`, `1.3`, `2.4`, `3.0` checks where the literal means "whatever current is today".
- **DoD gates**: targeted pytest for each changed file; grep gate for unclassified current literals in changed files.

### Row F - Indicator schema and catalogue tests

- **Files likely touched**:
  - [backend/tests/test_indicator_schema_v5.py](../backend/tests/test_indicator_schema_v5.py), likely rename to a non-versioned behavior test.
  - [backend/tests/test_indicator_catalogue_schema_v2.py](../backend/tests/test_indicator_catalogue_schema_v2.py)
  - [backend/tests/test_indicator_catalogue_schema_v21.py](../backend/tests/test_indicator_catalogue_schema_v21.py)
  - [backend/tests/test_indicator_catalogue_schema_v22.py](../backend/tests/test_indicator_catalogue_schema_v22.py), only to clarify historical-date intent if needed.
- **Required behavior coverage**:
  - Keep tests for v5-introduced fields that still define the schema: `entity_kinds`, `base_year`, `frequency`, lifted `additionalProperties`, singular `entity_kind` requirements.
  - Add tests for v6 render-hint removals: canonical indicator schema must not declare `default_mode`, `facet_labels`, or `renderer_rules` on the indicator block.
  - Keep historical changelog presence tests; rename/comment them as historical if a literal date remains.
- **DoD gates**: targeted pytest for changed indicator schema/catalogue files.

### Row G - Boundary stale-shard test cleanup trigger

This row exists because the original failure list mixed stale-shard tests with schema-version tests. It is deliberately a trigger row, not part of the schema-version cleanup.

- **Execute only if** an active branch still has tests that enumerate or read a parent directory after `remove_stale_shards()` pruned it.
- **Likely files**: `backend/tests/test_lift_*_national.py` variants.
- **Correct assertion shape**: kept shard file exists; stale shard file/path does not exist; no `iterdir()` call on a deleted parent dir.
- **DoD gates**: targeted pytest for the affected lift tests.

### Row H - Distill and close

- **Files**: this plan-doc plus docs touched by Row B if doctrine moved.
- **Required closure block**:
  - Row -> PR -> durable output map.
  - Explicit list of any skipped trigger rows and why.
  - Pointer to the docs section that now owns the schema-version-in-tests rule.
- **DoD gates**: docs-only `git diff --check`.

## 7. Acceptance grep gate

Every implementation PR after Row A must run and paste a short classification summary in the PR body. Use `rg` if available:

```powershell
rg -n 'x-version"\]\s*==\s*"[0-9]+\.[0-9]+|\$schema_version"\]\s*==\s*"[0-9]+\.[0-9]+|\$schema_version:\s*"[0-9]+\.[0-9]+|schema_version\s*=\s*"[0-9]+\.[0-9]+' backend frontend tools
```

The summary must classify remaining matches as one of:

- `fixed-in-this-PR`
- `historical/backcompat literal - keep`
- `bad-version fixture - keep`
- `synthetic fixture - keep`
- `row-schema constant - keep or scheduled`
- `producer emitter - scheduled`
- `out of scope for this plan`

If a match cannot be classified, stop and ask Fowler through `runSubagent` before editing.

## 8. Stop conditions

- A row would only bump a stale literal to the latest number without changing the test to a relationship.
- A frontend row would stamp indicator v6.0 while still emitting v6-removed canonical fields.
- A `tools/` row would import backend runtime modules.
- A test literal is historical/backcompat behavior and would be weakened by deletion.
- A row would change values, provenance, source identity, entity identity, or methodology semantics.
- A row would touch unrelated row-count sentinels, dates, or boundary geometry behavior.
- A row needs broad staging, stash, reset, or cleanup of unrelated dirty worktree changes.

## 9. See also

- [CLAUDE.md](../CLAUDE.md)
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md)
- [docs/agents/guardrails.md](../docs/agents/guardrails.md)
- [docs/architecture/testing.md](../docs/architecture/testing.md)
- [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md)
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md)
- [docs/architecture/decisions/0045-grapher-catalogue-split.md](../docs/architecture/decisions/0045-grapher-catalogue-split.md)
- [TODO/20260530-schema-version-compatibility-plan.md](20260530-schema-version-compatibility-plan.md)
