# Frontend Corpus Test Tier Reset Plan

**Last Updated**: 2026-06-14
**Level**: 4 - structural, cross-cutting test/validator/docs change

## 0. Operating contract

### Why this plan exists

The frontend default Vitest suite currently contains high-cardinality corpus validation that scales with `datasets/**` size rather than frontend behavior. The acute blocker is the generated boundary test case for `datasets/boundaries/in/villages/state=maharashtra/district=466/all.geojson`, but that file is only a symptom: the suite is creating thousands of generated checks by walking boundary and dataset files from frontend tests.

Verified local counts on 2026-06-14 from the main worktree:

| Surface | Current shape | Approx default frontend cost |
| --- | --- | ---: |
| `frontend/src/contracts/boundaries-conform.test.ts` | one generated feature-count parity test per TopoJSON sibling | 4,711 tests |
| `frontend/src/lib/boundaries.contract.test.ts` | one generated join-key sample test per classified boundary shard | 683 tests |
| `frontend/src/contracts/datasets-conform.test.ts` | one generated schema-conformance test per shipped dataset JSON | 271 tests |
| Panchayat + ward shard/registry tests | walks 663 panchayat shards + 3,300 ward shards | dozens of tests, large I/O |
| **Direct default frontend reduction target** | remove corpus-cardinality work from default Vitest | **>= 5,300 tests** |

Expected result after this plan:

| Metric | Before | After |
| --- | ---: | ---: |
| Static frontend `it/test` declarations | 3,008 | about 3,000 |
| Expanded default frontend practical count | about 8,600-9,000 | about 3,000-3,400 |
| Default frontend tests that open every boundary/JSON file | yes | no |
| Exhaustive corpus contract | scattered frontend loops | producer receipt + Tier-B validator |

### Strategy

The ruling from Fowler + Gregor (2026-06-14 research pass) is binding for this plan:

- The contract commitment is correct.
- The test placement is wrong.
- Frontend tests prove consumer behavior with fixtures and representative canaries.
- Producer/Tier-B validation proves exhaustive corpus conformance.
- High-cardinality inventory belongs in one contract artifact, not as thousands of frontend-generated test cases.

This plan therefore does **not** weaken schema or boundary contracts. It moves exhaustive proof to the producer side and keeps frontend Vitest constant-size.

### Hard scope

In scope:

- Move full boundary and JSON corpus checks out of default frontend Vitest.
- Add or extend Tier-B validator checks in `backend/yen_gov/validate.py` using the existing fixture-test pattern in `backend/tests/test_validate.py`.
- Add a committed boundary encoding receipt for TopoJSON/GeoJSON sibling and feature-count facts.
- Replace hand-maintained high-cardinality frontend boundary registries with generated or ledger-derived surfaces.
- Add a guardrail that prevents future default frontend tests from scaling with corpus cardinality.
- Update docs that currently say frontend conformance is the upstream gap detector.

Out of scope:

- No boundary geometry regeneration except the minimal receipt generation needed by a row.
- No change to map rendering behavior.
- No production backend.
- No higher test timeouts.
- No mere aggregation of thousands of file checks into one frontend assertion.
- No new dataset-processing GitHub Action in this plan. CLAUDE.md section 10 currently rejects CI that processes `datasets/**`; adding a path-filtered/nightly corpus workflow is an ESCALATE trigger requiring user sign-off.

### Doctrine / guardrail to land

The durable rule must land in `docs/architecture/testing.md`, `docs/architecture/backend/validator.md`, `docs/architecture/frontend/topojson-loader.md`, `docs/architecture/data/boundaries.md`, and `CLAUDE.md` if the executing agent touches that contract file:

> Default frontend tests must not scale with corpus cardinality. No default frontend Vitest may create one test per dataset file, shard, row, district, village, ward, panchayat, constituency, party, indicator, path, or schema artifact. Frontend tests prove consumer behavior with fixtures and representative canaries. Exhaustive corpus validation belongs to producer receipts plus backend Tier-B validation.

Review rule:

> If a default frontend test uses broad `globSync`, recursive `readdirSync`, or loops over `datasets/**` to generate test cases, it is presumed wrong unless bounded by a small explicit canary list.

### ESCALATE triggers

Stop and ask the user before proceeding if any row requires:

- A major schema bump.
- A new dataset-processing GitHub Action or any CI job that walks `datasets/**`.
- Deleting GeoJSON or TopoJSON siblings from disk.
- Removing exhaustive validation entirely instead of moving it to Tier-B.
- A runtime frontend reader that fetches the full boundary inventory for ordinary page load.
- Replacing LGD or ECI identity surfaces.
- Scope-narrowing any explicit user requirement recorded in this plan.

### Load-bearing docs and code already verified

- `docs/architecture/testing.md` - current test-tier doctrine, including no real-corpus pytest walks and e2e canary precedent.
- `docs/architecture/backend/validator.md` - existing Tier-A/Tier-B split and forbidden-path check pattern.
- `backend/yen_gov/validate.py` - `run()` chains named Tier-B checks; new checks must follow this pattern.
- `backend/tests/test_validate.py` - fixture-based tests and `run(tmp_path)` regression guards are the required style.
- `frontend/src/contracts/boundaries-conform.test.ts` - current source of the ~4,711 TopoJSON generated cases.
- `frontend/src/lib/boundaries.contract.test.ts` - current source of the ~683 generated boundary shard cases.
- `frontend/src/contracts/datasets-conform.test.ts` - current source of the ~271 generated JSON artifact cases.
- `datasets/data/_schema/columns.json` - existing `boundary_layer.csv` contract has GeoJSON ledger fields but no TopoJSON sibling/hash receipt fields.
- `tools/topojson/convert_layer.py` - already computes input SHA and writes ignored `.topojson.meta.json` sidecars; row B promotes the durable subset into a committed CSV receipt.
- `frontend/src/lib/boundaries/sources.ts` - current hand-maintained high-cardinality registry home.

## 1. Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| A | Move corpus proof to Tier-B and cut frontend to canaries | [x] DONE | - | L |
| B | Add committed boundary encoding receipt | [x] DONE | - | M |
| C | Generate high-cardinality boundary registries from the ledger | [ ] PENDING | - | L |
| D | Land doctrine guardrail against future frontend corpus explosion | [ ] PENDING | - | M |

## 2. Row A - Move corpus proof to Tier-B and cut frontend to canaries

### Row A scope

This row removes the current 5k-test blocker from default frontend Vitest while preserving exhaustive validation in Tier-B.

Add backend validator functions for the corpus facts currently enforced by frontend:

- `tier_b_boundary_hive_path_shape(root)` - every boundary `.geojson` and `.topojson` under `datasets/boundaries/in/` maps to a known Hive path family.
- `tier_b_boundary_topo_sibling_pairs(root)` - every `.topojson` has a sibling `.geojson`; the sibling policy follows the current durable topo-first/geo-fallback design without requiring every legacy GeoJSON to already have TopoJSON if current corpus does not.
- `tier_b_boundary_topo_feature_count_parity(root)` - for each `.topojson`/`.geojson` pair, TopoJSON object geometry count equals GeoJSON `features.length`. Implement the count structurally from TopoJSON `objects[object].geometries.length` where possible; do not add a browser/frontend dependency to the backend validator.
- Keep existing `tier_b_legacy_boundary_sidecars(root)` as the sidecar gate; move the frontend duplicate to canary-only.
- Treat full JSON schema corpus conformance as already owned by `tier_b(schemas, root)`; reduce the frontend duplicate.

Shrink frontend tests:

- `frontend/src/contracts/boundaries-conform.test.ts`: delete the `for (const topoRel of ALL_TOPOJSON)` generated loop. Keep small tests for known Hive path regex, sidecar absence smoke, ledger presence, states join-key canary, and a fixed explicit TopoJSON decode canary set.
- `frontend/src/lib/boundaries.contract.test.ts`: delete `for (const relPath of ALL_SHARDS)` generated join-key tests. Keep `boundaryRelPath` resolver cases and explicit canaries: country, states, districts, one subdistrict, one village large-shard canary, one missing/404 case through loader tests.
- `frontend/src/contracts/datasets-conform.test.ts`: keep schema registry sanity and schema-compatibility algorithm tests; replace one-test-per-data-JSON with 3-5 representative artifact canaries. Full JSON corpus validation stays in `python -m yen_gov validate --root .`.

### Row A files likely touched

- `backend/yen_gov/validate.py`
- `backend/tests/test_validate.py`
- `frontend/src/contracts/boundaries-conform.test.ts`
- `frontend/src/lib/boundaries.contract.test.ts`
- `frontend/src/contracts/datasets-conform.test.ts`
- `docs/architecture/backend/validator.md`
- `docs/architecture/testing.md`
- `docs/architecture/frontend/topojson-loader.md`
- `docs/architecture/data/boundaries.md`

### Row A acceptance gates

- `pytest -q backend/tests/test_validate.py`
- `cd frontend && bunx vitest run src/contracts/boundaries-conform.test.ts src/lib/boundaries.contract.test.ts src/contracts/datasets-conform.test.ts --pool=forks --poolOptions.forks.singleFork=true`
- `python -m yen_gov validate --root .` from repo root, or documented baseline if unrelated chronic failures exist.
- Default frontend tests no longer open the Maharashtra village shard as part of generated corpus loops.

### Row A load-bearing oracle

Run this static oracle from repo root after the row:

```powershell
rg "for \(const .* of ALL_TOPOJSON|for \(const .* of ALL_SHARDS|DATA_FILE_REFS\) \{|globSync\(\"\*\*/\*\.(geojson|topojson|json)\"" frontend/src/contracts frontend/src/lib/boundaries.contract.test.ts
```

Expected: no match that generates one default frontend test per corpus file. Bounded explicit canary arrays are allowed and must carry a comment naming each risk class.

## 3. Row B - Add committed boundary encoding receipt

### Row B scope

This row makes the producer-side contract explicit so Tier-B validates a receipt, not scattered rediscovery logic.

Add a new CSV file class under `datasets/data/entities/`:

`datasets/data/entities/boundary_encoding.csv`

Proposed columns:

| Column | Meaning |
| --- | --- |
| `topojson_path` | PK, POSIX repo-relative path under `datasets/` to the TopoJSON sibling. |
| `geojson_path` | POSIX repo-relative path under `datasets/` to the source/sibling GeoJSON. |
| `layer_id` | Best-effort FK-like join to `boundary_layer.csv.layer_id` where resolvable. |
| `level` | Boundary family level, matching `boundary_layer.csv.level` where possible. |
| `topojson_object` | Object key used inside the TopoJSON topology. |
| `geojson_feature_count` | Number of GeoJSON features at receipt time. |
| `topojson_feature_count` | Number of TopoJSON geometries at receipt time. |
| `geojson_sha256` | SHA-256 of the GeoJSON file bytes. |
| `topojson_sha256` | SHA-256 of the TopoJSON file bytes. |
| `mapshaper_version` | Version from `tools/topojson/.mapshaper-version`. |
| `topojson_config_hash` | SHA-256 of the effective `config/topojson.json` payload or per-layer effective settings. |
| `generated_by` | Tool id, e.g. `tools.topojson.convert_layer`. |

Implementation shape:

- Add the file class to `datasets/data/_schema/columns.json`.
- Add a producer command, either inside `tools/topojson/convert_layer.py` batch mode or as a sibling command `python -m tools.topojson.emit_receipt`, that writes `boundary_encoding.csv` from the current boundary corpus.
- Add Tier-B receipt validation:
  - every receipt row's paths exist;
  - hashes match disk;
  - feature counts match disk;
  - `geojson_feature_count == topojson_feature_count`;
  - every `.topojson` under `datasets/boundaries/in/` has exactly one receipt row;
  - orphan receipt rows fail loudly.
- Keep `.topojson.meta.json` sidecars ignored and local-only; the committed receipt is the contract surface.

### Row B files likely touched

- `datasets/data/_schema/columns.json`
- `datasets/data/entities/boundary_encoding.csv` (new generated artifact)
- `tools/topojson/convert_layer.py` or new `tools/topojson/emit_receipt.py`
- `tools/topojson/README.md`
- `backend/yen_gov/validate.py`
- `backend/tests/test_validate.py`
- `docs/architecture/data/csv-column-contract.md`
- `docs/architecture/frontend/topojson-loader.md`
- `docs/architecture/data/boundaries.md`

### Row B acceptance gates

- `pytest -q backend/tests/test_validate.py`
- Receipt generation is byte-stable on a second run.
- `python -m yen_gov validate --root .` validates the receipt against disk.
- `git diff --stat datasets/data/entities/boundary_encoding.csv` is explainable and does not rewrite unrelated data files.

### Row B load-bearing oracle

Fixture test in `backend/tests/test_validate.py` must mutate one receipt hash or one feature count in a `tmp_path` corpus and prove `run(tmp_path)` returns exactly the new boundary receipt failure. The regression guard must fail if the new Tier-B receipt check is not chained into `run()`.

## 4. Row C - Generate high-cardinality boundary registries from the ledger

### Row C scope

This row removes duplicate inventory truth from `frontend/src/lib/boundaries/sources.ts` for high-cardinality boundary families.

The current frontend registry file hand-maintains maps such as:

- `STATE_AC`
- `BLOCK_BOUNDARY`
- `PANCHAYAT_BOUNDARY_BY_DISTRICT`
- `PANCHAYAT_DISTRICTS_BY_STATE`
- `WARD_BOUNDARY_BY_ULB`
- `WARDS_BY_STATE`

The panchayat and ward tests currently walk 663 and 3,300 shards to prove those maps match disk. The durable fix is to make those maps derivative of the boundary ledger/receipt.

Implementation shape:

- Add a generator, e.g. `tools/boundaries/generate_frontend_registry.py`, that reads `datasets/data/entities/boundary_layer.csv` plus `datasets/data/entities/boundary_encoding.csv` and emits a generated TS module.
- Prefer a generated file such as `frontend/src/lib/boundaries/generated-sources.ts` with a header naming input signature. Keep hand-authored labels/caveats only where they are editorial, not inventory.
- `frontend/src/lib/boundaries/sources.ts` imports generated high-cardinality maps and retains only low-cardinality hand-authored constants, helper functions, and editorial caveats.
- Add a Tier-B or frontend constant-size freshness test that recomputes the generator input signature and fails when the generated TS is stale.
- Replace panchayat/ward/block/AC registry coverage tests with:
  - generated-registry shape tests;
  - a few sentinel keys;
  - input-signature freshness;
  - no recursive directory walk.

### Row C files likely touched

- `tools/boundaries/generate_frontend_registry.py` (new)
- `frontend/src/lib/boundaries/generated-sources.ts` (new generated file)
- `frontend/src/lib/boundaries/sources.ts`
- `frontend/src/contracts/state-panchayats-shards-coverage.test.ts`
- `frontend/src/contracts/state-panchayats-registry-coverage.test.ts`
- `frontend/src/contracts/state-wards-shards-coverage.test.ts`
- `frontend/src/contracts/state-wards-registry-coverage.test.ts`
- `frontend/src/contracts/state-blocks-registry-coverage.test.ts`
- `frontend/src/contracts/state-ac-registry-coverage.test.ts`
- `backend/yen_gov/validate.py` if freshness is Tier-B-owned
- `backend/tests/test_validate.py` if freshness is Tier-B-owned
- `docs/architecture/data/boundaries.md`
- `docs/architecture/frontend/map.md` if the registry contract is documented there

### Row C acceptance gates

- `python tools/boundaries/generate_frontend_registry.py --check` exits 0 after generation.
- `cd frontend && bunx vitest run src/contracts/state-panchayats-registry-coverage.test.ts src/contracts/state-wards-registry-coverage.test.ts src/contracts/state-blocks-registry-coverage.test.ts src/contracts/state-ac-registry-coverage.test.ts --pool=forks --poolOptions.forks.singleFork=true`
- `cd frontend && bun run check` if generated TS affects type surfaces.
- No default frontend test recursively walks `datasets/boundaries/in/panchayats` or `datasets/boundaries/in/wards`.

### Row C load-bearing oracle

Modify a generated registry file in a `tmp_path` or test fixture without changing the ledger signature; the freshness test must fail. Then regenerate and prove it passes. The default frontend tests must not use `readdirSync` over panchayat/ward corpus directories.

## 5. Row D - Land doctrine guardrail against future frontend corpus explosion

### Row D scope

This row prevents the same pattern from returning for the next high-cardinality dataset.

Add a constant-size guard test that scans frontend test source files, not `datasets/**`, for default-corpus explosion patterns. The scan is allowed because it walks about 200 source files, not thousands of generated artifacts.

Suggested test file:

- `frontend/src/contracts/no-frontend-corpus-explosion.test.ts`

It should reject new default frontend tests that:

- use broad `globSync("**/*.geojson")`, `globSync("**/*.topojson")`, or `globSync("**/*.json")` under `datasets/`;
- recursively `readdirSync` under `datasets/boundaries` or `datasets/data`;
- generate `it()`/`test()` blocks from unbounded dataset file lists;
- assert exact corpus cardinality unless the input is a bounded explicit canary list.

Allowed shapes:

- explicit canary arrays with a comment naming the risk class;
- fixture tests under `frontend/src/**` that do not read the real corpus;
- tests that scan frontend source files for guardrail enforcement;
- loader tests that mock fetch or load a single named canary artifact.

Update docs:

- `docs/architecture/testing.md` - default frontend contract tests are consumer canaries, not full corpus walks.
- `docs/architecture/backend/validator.md` - Tier-B owns exhaustive boundary/json corpus validation and receipts.
- `docs/architecture/frontend/topojson-loader.md` - replace the claim that frontend conformance is the upstream gap-detector with producer receipt + Tier-B.
- `docs/architecture/data/boundaries.md` - document boundary encoding receipt and registry generation.
- `CLAUDE.md` section 10 - add the anti-pattern if this row touches the contract file; otherwise leave a TODO row for a later CLAUDE sync.

### Row D files likely touched

- `frontend/src/contracts/no-frontend-corpus-explosion.test.ts` (new)
- `docs/architecture/testing.md`
- `docs/architecture/backend/validator.md`
- `docs/architecture/frontend/topojson-loader.md`
- `docs/architecture/data/boundaries.md`
- `CLAUDE.md` if contract sync is included

### Row D acceptance gates

- `cd frontend && bunx vitest run src/contracts/no-frontend-corpus-explosion.test.ts --pool=forks --poolOptions.forks.singleFork=true`
- `rg "frontend conformance test is the upstream gap-detector|one test per dataset file|every shipped .* validates" docs/architecture/frontend/topojson-loader.md docs/architecture/testing.md docs/architecture/backend/validator.md docs/architecture/data/boundaries.md` returns no stale doctrine except historical quoted text clearly marked as retired.
- The guard test includes a fixture or synthetic source snippet proving it catches an unbounded `globSync` + generated `it()` pattern.

### Row D load-bearing oracle

Add a synthetic bad-test snippet fixture inside the guard test and assert it is rejected. Add a synthetic explicit canary-list snippet and assert it is accepted. This proves the guard enforces the doctrine without banning legitimate canaries.

## 6. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Contract gets weakened during the frontend cutover | Row A adds Tier-B checks before deleting frontend loops. No row may remove exhaustive validation without a replacement owner. |
| New receipt becomes another stale artifact | Row B adds hash/freshness validation and byte-stable generation. |
| Generated frontend registry loses editorial caveats | Row C separates generated inventory from hand-authored labels/caveats. Editorial caveats stay hand-authored and low-cardinality. |
| Guard test blocks legitimate small canaries | Row D allows explicit canary arrays with comments naming the risk class. |
| Execution agent tries to add a dataset-processing CI workflow | ESCALATE trigger; current CLAUDE.md rejects CI that processes `datasets/**`. |
| Backend validator becomes too slow | Tier-B is local-only by existing doctrine. If runtime exceeds acceptable local use, optimize validator implementation or receipt hashes before adding knobs. |

## 7. Definition of Done for the whole plan

- Default frontend Vitest no longer creates one test per boundary shard or dataset JSON file.
- Expanded default frontend test count drops by at least 5,300 cases versus the 2026-06-14 baseline.
- `python -m yen_gov validate --root .` owns the full boundary/json corpus contract.
- Boundary encoding facts have a committed receipt validated against disk.
- Panchayat/ward high-cardinality registries are generated or ledger-derived, not hand-maintained as a second inventory.
- A guard test or equivalent default gate prevents future high-cardinality frontend corpus walks.
- Docs name the new tier boundary unambiguously.

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.
