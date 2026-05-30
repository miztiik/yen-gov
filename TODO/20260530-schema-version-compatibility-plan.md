# Schema Version Compatibility Plan

**Last Updated**: 2026-05-30
**Status**: In review - PR-A is open as #459.
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
| A | #459 | In review | Gregor + Fowler + Hans + Max | Create this plan-doc. No runtime behavior. | File exists under `TODO/`; status ledger and PR DAG are clear; `git diff --check` clean. | Stop if unrelated dirty worktree changes would need staging. |
| B | _pending_ | Not started | Gregor + Fowler + Hans + Max | Durable policy docs: create an ADR for the compatibility decision and a living subsystem doc at `docs/architecture/data/schema-evolution.md`; amend `docs/reference/schemas.md`, `docs/architecture/backend/validator.md`, `docs/architecture/data/canonical-store.md`, `docs/architecture/testing.md`, and `CLAUDE.md` section 11 if the strict JSON rule changes. | ADR records rejected alternatives; subsystem docs define writer-strict vs reader-compatible semantics; reader-before-producer rollout order is resolved once; changed docs have H1, Last Updated, See also; `git diff --check` clean; no runtime, schema, registry, or data behavior changes. | Stop if policy would allow old major versions without retained schemas / translator. |
| C | _pending_ | Not started | Gregor + Fowler | Compatibility contract surface. Preferred target: a single data-owned registry such as `datasets/schema-compatibility.json` plus `datasets/schemas/schema-compatibility.schema.json`, seeded current-only except for already-supported canonical reader versions. The registry is the single compatibility contract consumed by backend and frontend; any temporary Python/TS mirror must have a drift test and a removal row. | Registry validates; tests prove schema format and no Python/TS shadow constants drift; no validator behavior change yet. | Stop if a simpler schema-embedded field is proven better by Gregor + Fowler. |
| D | _pending_ | Not started | Fowler | Structural test cleanup in tests only. Replace current-version magic literals with registry/schema lookups where tests are about current writer behavior. Keep literal version strings only in named historical-compatibility fixtures, with the test name or assertion making that purpose explicit. | Targeted pytest for schema registry / validator / affected seed tests; grep confirms no unannotated current-version literals remain in touched tests; no production logic, validator behavior, schema, registry, or data files changed. | Stop if a test is the only guard for a real historical fixture. |
| E | _pending_ | Not started | Gregor + Fowler | Backend Tier-B compatibility. Keep `core/io.py` writer-strict, but let validator accept versions allowed by the compatibility contract. Before Row H, accepted old JSON versions must be additive minors that still validate against the current schema; declared-version schema resolution waits for retained schemas. Add fixture tests for supported old additive minor, unsupported future/major, writer stale-version rejection, and accepted-version-but-incompatible-current-schema rejection. | `pytest -q backend/tests/test_validate.py backend/tests/test_core_io.py`; full backend pytest per repo baseline; `python -m yen_gov validate --root .`. | Stop if implementation needs real-corpus pytest walking or accepting an old version requires a historical schema not yet retained. |
| F | _pending_ | Not started | Gregor + Fowler | Frontend JSON corpus contract. Make `frontend/src/contracts/datasets-conform.test.ts` use the same compatibility contract instead of current-only equality. Ajv validation stays fail-loud. | Targeted vitest for `datasets-conform`; full `bun run test` in `frontend`. | Stop if contract needs a runtime network dependency or stale copied compatibility constants. |
| G1 | _pending_ | Not started | Gregor + Fowler | Structural frontend compatibility cleanup. Make the canonical runtime compatibility set derive from the Row C contract, or from a generated module whose source is that contract; retire the shadow `SUPPORTED_SCHEMA_VERSIONS` constant as an authority. No runtime behavior change. | Targeted vitest for `frontend/src/lib/canonical/manifest.test.ts`; a drift test proves the frontend runtime set and Row C contract cannot disagree; full `bun run test` in `frontend`. | Stop if the frontend would need a runtime network fetch before `manifest.json`. |
| G2 | _pending_ | Not started | Gregor + Jony if copy changes | Runtime manifest / Parquet reader behavior. Enforce supported table versions consistently at manifest lookup / registration and keep unsupported versions fail-loud. Do not design mixed-schema projection in this row. | Frontend unit tests for supported old minor and unsupported future/major; browser smoke on one canonical-backed route if runtime behavior changes; unsupported version still fails loud. | Stop if mixed Parquet schemas require `union_by_name` or projection defaults not yet designed. |
| H | _pending_ | Not started | Hans + Max + Gregor + Fowler | Schema-evolution release metadata contract. Define how historical snapshots validate by declared version, how old schemas are retained, and which durable public surface records `schema changed, values did not`: either a documented extension of `datasets/migration-ledger.csv` or a separate schema-evolution ledger with its own schema. No pilot schema bump in this row. | Chosen path, columns/fields, and ownership are named in docs; parser/schema tests cover `values_changed=true`, `values_changed=false`, and missing old-schema references; existing canonical-pivot ledger semantics are not silently repurposed. | Stop if old schemas are not recoverable by version or if the ledger surface would overload an existing artifact without a documented migration. |
| I | _pending_ | Not started | Fowler + Hans + Max | Additive no-mechanical-rebuild row, executed only when there is a named near-term metadata need. Do not invent an optional field just to prove the mechanism; if no real candidate exists after Row H, close this row as N/A and rely on fixture tests from Rows E/F/H. When executed, name the schema candidate in this row before editing and keep unchanged artifact bytes unchanged. | Diff shows schema/docs/tests/ledger only unless the named need requires more; no observation/source FK churn; targeted validator + frontend contract tests pass; Row H metadata records `values_changed=false`; old artifact validates through the compatibility contract. | Stop if the candidate touches observation Parquet, provenance, `source_id`, or citizen-visible semantics. |
| J | _pending_ | Not started | Gregor + Fowler + Hans + Max | Breaking-change trigger row. Do not create a breaking schema change solely as a pilot. Execute only when an actual schema contraction, rename, removal, or semantic shift is needed; otherwise close as Deferred after Rows E/H prove old-major rejection with fixtures. | If executed, major bump has expand -> migrate -> contract or explicit rejection tests, ledger row, rollback note, consumer inventory, and docs. | Stop if consumers cannot be enumerated. |
| K | _pending_ | Not started | Fowler | Plan distillation and closure. Lift durable rules from this TODO into `docs/`; archive or slim this plan; update status table to closed. | Durable doctrine lives in `docs/`; TODO says where it moved; no stale TODO-only architecture remains. | Stop if docs disagree after distillation. |

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
- **Schema/data row**: validator, migration ledger entry, no unexpected row-count/value/source FK churn.

## 10. Open questions resolved by the row owners

- **Compatibility registry home**: Row C starts with a data-owned registry as the preferred design. Gregor + Fowler may choose schema-embedded accepted-version metadata only if it reduces drift without scattering policy.
- **Historical schema storage**: Row H decides whether old schemas live as archived files, release assets, or entries in the compatibility registry. No old-major acceptance before this is resolved.
- **Parquet mixed-schema reads**: Row G2 decides whether to require homogeneous table versions per manifest entry or to implement explicit projection/`union_by_name` behavior.
- **Public release metadata**: Row H decides how a researcher sees `schema changed, values did not` without reading git history.

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
