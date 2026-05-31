# Schema Version Magic Test Cleanup Plan

**Last Updated**: 2026-05-31
**Status**: ACTIVE - Row A plan-doc PR #501 merged; Row B doctrine PR #503 merged; Row C split by source-contract blocker; C1 source-surface unblock in progress.
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
- [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md) - citation-ledger provenance; no fetch telemetry in `taxonomy.sources`.
- [docs/architecture/frontend/charts/source-list-v2.md](../docs/architecture/frontend/charts/source-list-v2.md) - frontend render surface for citation-ledger sources.
- [docs/architecture/decisions/0032-sources-citation-ledger.md](../docs/architecture/decisions/0032-sources-citation-ledger.md) and [docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md](../docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) - source rows are citation identity, not fetch events.
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
| Frontend production stale emission | [frontend/src/lib/canonical/indicator-from-canonical.ts](../frontend/src/lib/canonical/indicator-from-canonical.ts), [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts) | Do not just change `4.4` to current. First move canonical-backed provenance to the SourceListV2 citation-ledger surface, then remove render-hint carryover, then stamp the current indicator schema from a single tested frontend policy. |
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
| A | #501 | Merged | `feat/schema-version-magic-plan` | Fowler | Add this TODO plan only. No runtime behavior. | File exists under `TODO/`; plan names subagent use, branch discipline, classification table, exclusions, and row gates; `git diff --check` clean. | Stop if another active plan already supersedes this exact scope on `main`. |
| B | #503 | Merged | `feat/schema-version-testing-doctrine` | Fowler + Gregor | Durable docs: update [docs/architecture/testing.md](../docs/architecture/testing.md), [docs/architecture/backend/validator.md](../docs/architecture/backend/validator.md), and a narrow [CLAUDE.md](../CLAUDE.md) section 11 clarification if needed. | Docs define forbidden current-version literals, allowed historical/backcompat exceptions, backend registry pattern, tools-local schema JSON pattern, frontend policy-constant pattern; docs have Last Updated and See also where required. | Stop if docs would change schema compatibility policy owned by [TODO/20260530-schema-version-compatibility-plan.md](20260530-schema-version-compatibility-plan.md). |
| C0 | #506 | Merged | `feat/schema-magic-row-c-unblock` | Fowler + Gregor | Plan amendment only: split Row C because canonical source provenance is citation-ledger v3, not legacy fetch-ledger `sources[]`. | Plan names the source-contract prerequisite, rejected fake telemetry, and the C1/C2/C3 sequence; `git diff --check` clean. | Stop if this turns into runtime/schema edits. |
| C1 | #507 | Merged | `feat/frontend-indicator-sources-v2` | Fowler + Gregor, Jony if visible behavior changes | Source-surface contract unblock for canonical-backed indicator routes: render citation-ledger provenance through SourceListV2 instead of fake legacy `fetched_at`. | Canonical-backed source rows contain no fetch telemetry; tests prove SourceListV2 receives citation-ledger rows; legacy artifacts still render legacy `sources[]`; browser smoke covers one canonical-backed and one legacy indicator route. | Stop if the only path is to invent `fetched_at`, `date_accessed`, `first_fetched_at`, or `last_seen_at`. Escalate if `indicator.schema.json` must change. |
| C2 | #509 | In review | `feat/frontend-indicator-render-hints` | Fowler + Gregor, Jony if visible behavior changes | Render-hint cleanup: remove canonical translator carryover of v6-deleted fields only after renderer behavior is preserved via grapher policy. | `indicator-from-canonical` tests prove no `renderer_rules`, `default_mode`, or `facet_labels` are emitted; rank/render behavior remains covered. | Stop if removing `renderer_rules` would change citizen-visible rank suppression before grapher lookup is wired. |
| C3 | _pending_ | Not started | `feat/frontend-indicator-v6-artifact` | Fowler + Gregor | Version-policy cleanup: centralize emitted indicator schema version policy and remove `4.4` stamps only after C1/C2 make the emitted artifact current-shape honest. | Policy test proves frontend emitted current equals `indicator.schema.json` x-version; translator uses policy, not hand-typed literals; targeted/full frontend tests as feasible. | Stop if emitted populated artifacts are not valid for the stamped schema. |
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

### Row C0 - Frontend indicator source-contract split

This row records the blocker found while preflighting the original Row C.
[frontend/src/lib/canonical/indicator-from-canonical.ts](../frontend/src/lib/canonical/indicator-from-canonical.ts) currently degrades `taxonomy.sources.parquet` citation-ledger rows into legacy `IndicatorSource` rows with `fetched_at: ""`. That is not an honest route to current `indicator.schema.json`: canonical source rows intentionally do not carry fetch telemetry per [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md), [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md), and [ADR-0042](../docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md).

Gregor + Fowler verdict, 2026-05-31:

- Reject fake telemetry. Do not invent `fetched_at`, `date_accessed`, `first_fetched_at`, or `last_seen_at`.
- Do not stamp the current indicator schema while populated canonical-backed sources remain invalid for that schema.
- Split the original Row C into C1 source-surface unblock, C2 render-hint cleanup, and C3 version-policy stamp.
- Prefer frontend/runtime branching to a schema change unless C1 proves `indicator.schema.json` must grow a `sources_v2` field. If a schema bump is needed, that is a dedicated contract PR with validation and artifact migration gates, not a hidden Row C edit.

### Row C1 - Canonical indicator SourceListV2 unblock

- **Files likely touched**:
  - [frontend/src/lib/canonical/indicator-from-canonical.ts](../frontend/src/lib/canonical/indicator-from-canonical.ts)
  - [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts)
  - [frontend/src/lib/indicators.ts](../frontend/src/lib/indicators.ts), only if a typed wrapper/optional `sources_v2` is needed.
  - [frontend/src/lib/AboutThisData.svelte](../frontend/src/lib/AboutThisData.svelte) and the indicator render component(s), only if rendering needs to branch between legacy `SourceList` and `SourceListV2`.
  - [docs/architecture/frontend/charts/source-list-v2.md](../docs/architecture/frontend/charts/source-list-v2.md), if canonical indicators become a SourceListV2 adopter.
- **Required checks**:
  - Canonical-backed provenance is projected as citation-ledger rows compatible with `SourceListV2`.
  - No canonical-backed source projection contains fetch telemetry fields.
  - Legacy JSON indicator artifacts keep the old `sources[]` render path.
- **DoD gates**: targeted vitest for canonical indicator/source-list paths; `bun run check`; browser smoke for one canonical-backed indicator route and one legacy indicator route.

### Row C2 - Frontend indicator render-hint cleanup

- **Files likely touched**:
  - [frontend/src/lib/canonical/indicator-from-canonical.ts](../frontend/src/lib/canonical/indicator-from-canonical.ts)
  - [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts)
  - [frontend/src/lib/grapher/catalogue.ts](../frontend/src/lib/grapher/catalogue.ts) and grapher tests only if rank/render hints must move for canonical-backed indicators.
- **Required checks**:
  - Artifact builder does not emit indicator v6-removed fields: `renderer_rules`, `default_mode`, `facet_labels`.
  - Any renderer behavior previously driven by `renderer_rules` still comes from an allowed frontend/grapher surface.
- **DoD gates**: targeted vitest for canonical indicator tests and any grapher/indicator-card tests; `bun run check` if TypeScript surfaces changed; browser smoke only if route behavior changes.

### Row C3 - Frontend indicator artifact version-policy cleanup

- **Files likely touched**:
  - [frontend/src/lib/canonical/types.ts](../frontend/src/lib/canonical/types.ts)
  - [frontend/src/lib/canonical/indicator-from-canonical.ts](../frontend/src/lib/canonical/indicator-from-canonical.ts)
  - [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts)
- **Required checks**:
  - Artifact builder no longer emits `$schema_version: "4.4"`.
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
