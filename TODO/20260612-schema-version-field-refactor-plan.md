# Schema-version field refactor — OWID-conformance pivot plan

**Last Updated**: 2026-06-12
**Status**: Authored. Not started. Awaiting orchestrator + multi-persona debate (Gregor / Fowler / Hans / Max / Jony) before PR-0.
**Level**: 4 (cross-cutting contract change; touches ~50 schemas, ~120 on-disk artifacts, 6+ writer modules, every consumer that asserts on the field's presence; reversible only via full rollback because reader-before-producer rollout makes the swap atomic at the family level).
**Strategy**: drop the `$schema_version` field from every JSON data emit file. Schema-shape identity moves to the `.schema.json` file's own `x-version` (where it already lives); data-freshness, publisher edition, and refresh cadence move to OWID-shape semantic siblings on a new metadata block. Multi-PR rollout per the writer-strict / reader-compatible policy in [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md).

> User mandate, 2026-06-12: "agreed on option 2 OWID conformance style no more calling it schema version" + "what does OWID use - long format json like us?" + "the downstream impact on updating all indicators and datasets might be hugh ... ok update doc and add todo plan, will pick it up later." This plan-doc is the carry-over.

> **This plan is open work. It does NOT modify the existing writer-strict / reader-compatible policy.** Until the pivot ships, every new artifact still stamps `$schema_version` per the current contract. The pivot atomically retires the field per artifact family with reader-before-producer rollout; partial / per-artifact retirement is forbidden because it creates a half-migrated surface where some artifacts use OWID grammar and others do not.

---

## Section 0 — Operating contract

### 0.1 Goal

Bring yen-gov's schema-versioning grammar into OWID-conformance: stop stamping a top-level `$schema_version` semver on every JSON data emit file; let schema-shape identity live ONLY in the `.schema.json` file's own `x-version`; expose data-freshness / publisher-edition / refresh-cadence as separate semantic fields on the citation ledger and on a new per-dataset metadata block. This closes [Named divergence #5](../docs/concepts/owid-alignment.md#named-divergences-from-owid-with-reasons) and aligns the data emit grammar with the [OWID metadata reference](https://docs.owid.io/projects/etl/architecture/metadata/reference/).

### 0.2 What this plan does

| Surface | Today | After this plan |
|---|---|---|
| Top-level field on every JSON data emit file | `$schema_version: "<semver>"` (stamped by writer from schema's `x-version`) | (deleted) |
| Schema-shape identity | Two places — `.schema.json` file's `x-version` AND the data file's `$schema_version` sibling (duplicated) | One place — `.schema.json` file's `x-version` only |
| Data-freshness pointer | implicit in `_ops/` operator state, scattered or absent on citizen artifacts | explicit `origin.date_accessed` field on the citation ledger row (one per source citation, NOT per data row) |
| Publisher edition tag | implicit in `source.csv.vintage` (already OWID-conformant via [ADR-0042](../docs/concepts/data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor)) | unchanged — `vintage` already serves the `version_producer` role |
| Refresh cadence | not surfaced (some indicators carry `update_period_days` per [ADR-0046](../docs/architecture/data/canonical-store.md), but inconsistently) | uniform `update_period_days` on the per-indicator catalogue row |
| Schema-required declaration | ~50 `.schema.json` files list `$schema_version` in `required: [...]` | Field removed from `required[]` in every schema; field removed from `properties` block in every schema; one shared `$defs/version` ref (in `columns.schema.json`, `schema-evolution.schema.json`) deleted |
| Writer behaviour | every emit site adds the `$schema_version: schema["x-version"]` line | every emit site omits the line; lint test enforces absence |
| Reader behaviour | most consumers IGNORE the field (the schema validator just validates against `.schema.json`); a few contract tests (e.g. `frontend/src/contracts/sources-v2-shape.test.ts` pre-simplification) DID assert on the literal | reader/test sweep drops every presence-of-`$schema_version` assertion |
| Hardcoded `"1.0"` tool sites | 5 places (see audit below) — drift hazard | retired in same sweep |

### 0.3 What this plan does NOT do

- Touch the existing `.schema.json` files' `x-version` declarations. Schema-shape identity continues to live there; this plan only stops DUPLICATING it onto every data file.
- Touch the `x-changelog` blocks. Per-schema evolution history continues exactly as today.
- Touch the writer-strict / reader-compatible operational policy in [schema-evolution.md](../docs/architecture/data/schema-evolution.md). That policy survives verbatim; only the on-disk field disappears.
- Touch the `derive_source_id` 3-arg hash or the `(producer, title, vintage)` citation-ledger identity. ADR-0032 + ADR-0042 + ADR-NNNN (citation-ledger-5col) all survive unchanged.
- Touch the 5-col `source.csv` shape. The new `origin.date_accessed` semantic is appended on a SIBLING block (see §1.4 target shape) — the 5-col citation ledger stays exactly 5 cols.
- Touch the canonical long-format CSV observation rows (the `data/datapoints/**` tier). Observations carry `source_id` FKs; no `$schema_version` field exists at the observation-row grain today, and none will after.
- Touch `datasets/manifest.json`'s structural role. The manifest file itself drops its own top-level `$schema_version` but its semantic content (the list of tables + their schemas) is unchanged.
- Replace the field with a renamed equivalent. The user mandate is "no more calling it schema version"; the pivot DELETES, not RENAMES.

### 0.4 OWID precedent

[OWID's metadata reference](https://docs.owid.io/projects/etl/architecture/metadata/reference/) treats the four concerns as distinct:

| Concern | OWID field | yen-gov target |
|---|---|---|
| Schema-shape identity | (none on data file; lives in the `.schema.json` file's `x-version`) | Same — drop the data-file stamp |
| Data freshness pointer | `origin.date_accessed` (when WE pulled the bytes) | `origin.date_accessed` on the source.csv row (one timestamp per citation; mutable on re-fetch) |
| Publisher edition tag | `origin.version_producer` (e.g. "NFHS-5", "RBI Handbook 2024-25") | already lives in `source.csv.vintage` per [ADR-0042](../docs/concepts/data-provenance.md#adr-0042) |
| Expected refresh cadence | `dataset.update_period_days` (e.g. 365 for annual, 30 for monthly) | already conceptually exists on the indicator catalogue per [ADR-0046](../docs/architecture/data/canonical-store.md); make it uniform across the catalogue |

The lift is mostly NAMING + CONSOLIDATION rather than NEW FIELDS. The semantic content is mostly already in place. The pivot's value is in subtraction (drop the duplicated identity stamp) + grammar conformance (use OWID's field names so a citizen / researcher familiar with OWID can read yen-gov metadata at a glance).

### 0.5 Audit — what's on disk today (2026-06-12)

**Schemas declaring `$schema_version` as required**: ~50 `.schema.json` files in `datasets/schemas/`. Pattern is uniformly `{ "type": "string", "pattern": "^\\d+\\.\\d+$" }` (semver-2-position). Sample:

- `indicator.schema.json` (required for indicator artifacts)
- `manifest.schema.json` (required for `datasets/manifest.json`)
- `indicators-completeness.schema.json` (required for `datasets/_ops/indicators-completeness.json`)
- `constituency.schema.json`, `election.schema.json`, `party.schema.json` (electoral artifacts)
- `taxonomy-parties.schema.json`, `topic-catalogue.schema.json`, `methodology-break.schema.json` (taxonomy)
- `feature_collection.metadata.schema.json` (geo features)
- `lgd-*.schema.json` (LGD lookups)
- `result.constituency.schema.json`, `result.summary.schema.json` (election results)
- ... and ~35 more.

**Artifacts on disk carrying the stamp**: 120+ (grep cap was hit at 200; estimated true count 500-2000 once boundary partition shards + per-state election shards are counted). Sample:

- All boundary SoT (`datasets/data/entities/boundaries_sot/SXX/constituencies.json`) at `4.1` — 28 files
- All taxonomy files (`datasets/taxonomy/*.json`) at `1.0`-`3.0` — ~14 files
- All grapher files (`datasets/grapher/*.json`) at `1.0`-`1.1` — ~5 files
- All `_ops/` files at `1.0`-`2.0` — ~5 files
- All election event/result/inventory files — count TBD by audit subagent
- `datasets/manifest.json` at `1.4`
- `datasets/data/_schema/columns.json` at `2.0`

**Writer sites**:

- 1 well-behaved (reads from schema): `tools/emit_indicators_completeness_index.py:180` — `"$schema_version": schema["x-version"]`
- 5 hardcoded literal (drift hazard): `tools/gen_election_tile_layouts.py:326,375`, `tools/lgd/parse_lgd_export.py:582`, `tools/lgd/snapshot.py:132`, `tools/boundaries/enrich_census_code_2011.py:456,483` — `"$schema_version": "1.0"`
- N more writer sites in `backend/yen_gov/canonical/` and `backend/yen_gov/pipeline/` that stamp via `core/schema_registry.py:schema_version()` — count TBD by audit subagent

**Consumers asserting on the field**:

- The Tier-B validator (`backend/yen_gov/validate.py`) consumes `$schema_version` to dispatch to retained historical schemas per [schema-evolution.md §Retained Historical Schemas](../docs/architecture/data/schema-evolution.md#retained-historical-schemas). This is the load-bearing consumer; the pivot needs a replacement dispatch story.
- Frontend canonical-store reader (`frontend/src/lib/duckdb.ts` + `frontend/src/lib/canonical/`) projects `$schema_version` through DuckDB SELECT clauses on some tables — count TBD by audit subagent.
- Per-shard contract tests (e.g. `frontend/src/contracts/sources-v2-shape.test.ts` pre-PR-#963) historically asserted on the literal value — sweep needed.

### 0.6 ESCALATE triggers

The orchestrator stops ONLY at:

1. **The Tier-B validator's retained-schema dispatch breaks at the seam.** Today `validate.py` reads `$schema_version` to pick which `datasets/schemas/archive/<schema>/v<ver>/<file>` to validate against. The pivot has to choose: (a) drop retained-schema validation entirely (semver-2 archive is small; we accept "validate against current schema only" and migrate all on-disk artifacts to current); (b) use a different dispatch key (e.g. the artifact's `$schema` URL with version embedded); (c) keep `$schema_version` as a Tier-B-only operator-tier field that doesn't ship on citizen-facing artifacts. PR-0 of this plan MUST resolve this before any writer changes; STOP-AND-SURFACE if the chosen option breaks a consumer not enumerated in the audit.

2. **A consumer of the field is discovered that asserts on its VALUE (not just presence).** Audit subagent grep must catch every consumer; if PR-1+ discovers a 7th class of consumer (e.g. some adapter branches on `if doc["$schema_version"] >= "2.0":`), STOP-AND-SURFACE — the pivot may need a translator at the reader for that consumer.

3. **A schema's `x-changelog` predicts a future version bump that depends on `$schema_version` being readable at the artifact level.** Audit needs to read every `x-changelog` block; if any change description includes "readers may dispatch on `$schema_version` to handle the new shape", STOP-AND-SURFACE — that change has to land BEFORE the pivot, or the pivot has to design around it.

4. **The replacement `origin.date_accessed` field cannot be populated without a fetched-at smear.** The yen-gov lesson from /memories/lessons.md 2026-05-16 + ADR-0032 is: do not stamp pipeline wall-clock onto citizen-facing rows. If the OWID-shape `origin.date_accessed` semantic forces re-emission of every observation on every fetch, the pivot has to use sidecar telemetry (already the canonical pattern) instead of citizen-row stamping. STOP-AND-SURFACE if the audit reveals no clean separation.

### 0.7 Decisions to ratify BEFORE PR-0

These need multi-persona debate (Gregor + Fowler + Hans + Max + Jony) and a written verdict in this plan-doc:

| Open question | Personas to weigh in | Default if unresolved |
|---|---|---|
| Tier-B retained-schema dispatch — option (a) / (b) / (c) above | Gregor (architect), Fowler (rollout) | Default (a): drop retained-schema validation; migrate all on-disk artifacts to current schema. Reason: retained-schema archive is tiny (1 entry today at `datasets/schemas/archive/elections-inventory/v1.0/`); the cost of carrying the dispatch infrastructure outweighs the benefit. |
| Should `origin.date_accessed` live on the `source.csv` row or on a sibling `.metadata.json` per data file? | Gregor (data model), Hans (citizen meaning), Max (researcher use-case) | Default: on `source.csv` row, BUT only if the row's identity is unchanged by re-fetch. If `date_accessed` is mutable per-fetch, it does NOT participate in the `derive_source_id` hash (3-arg `(producer, title, vintage)` survives unchanged); it's a mutable column on the existing row, populated on first fetch and updated on subsequent fetches via UPSERT. |
| Should `dataset.update_period_days` be uniform across the indicator catalogue, or per-source? | Hans (publisher semantics), Max (cross-source comparability) | Default: per-indicator. The cadence is a property of the upstream's publication schedule, which is per-indicator. Some indicators have multiple sources at different cadences; the indicator's effective cadence is the union (refresh-needed = ANY source has new data). |
| Migration of the 120+ on-disk artifacts — one-shot sweep PR or per-family sweep? | Fowler (rollout safety) | Default: one-shot SWEEP per artifact family (e.g. all boundary SoT in one PR, all taxonomy in another). Per-family is small enough to review; one-shot all-artifacts is 200-2000-file diff per PR which violates reviewer comfort. |
| Should `manifest.json` retain `$schema_version` because it's the bootstrap file the reader needs to discover schemas? | Gregor | Default: NO. The manifest's own schema URL (`$schema`) is sufficient to bootstrap. If the reader needs schema version awareness for manifest, it lives in the schema URL itself (e.g. `https://yen-gov.github.io/schemas/manifest.v2.schema.json` — versioned schema files instead of versioned data stamps). |

### 0.8 Per-PR workflow

Standard:
1. Branch off `origin/main`.
2. Implement scope. Tests ship with the row.
3. Local gates GREEN (pytest, vitest, svelte-check, browser smoke per CLAUDE.md §13).
4. Commit + push + `gh pr merge --squash --admin --delete-branch`.
5. Pull main. Start next row.

---

## Section 1 — PR sequence

Reader-before-producer (per [schema-evolution.md §Rollout Order](../docs/architecture/data/schema-evolution.md#rollout-order)). Each PR ships AS A WHOLE; no partial / per-artifact rollout.

### PR-0 — Audit + doctrine consolidation + decision ratification

**Scope**: this plan-doc closure (fill in §0.7 with ratified verdicts after persona debate). Add an ADR-NNNN entry in [schema-evolution.md](../docs/architecture/data/schema-evolution.md) titled `schema-version-field-retirement` recording the decision. Update CLAUDE.md §11 to flag the field as "in retirement; do not stamp on new schemas." Update the `prepare-plan` skill if it references the field.

**No code changes.** Doc-only PR, ~5 files, reversible at any time.

**Acceptance**: all §0.7 questions have a verdict in the plan-doc. ADR-NNNN exists. Doc-only diff.

### PR-1 — Audit subagent grep + populate this plan-doc's §0.5 with the FULL list

**Scope**: exhaustive grep for every consumer / writer / reader / contract test referencing `$schema_version`. Audit subagent ships back a report; orchestrator pastes the full list into §0.5 of this plan and commits. **No code changes**; the report drives the per-family PR sequence.

**Acceptance**: this plan-doc's §0.5 has a complete enumeration (no "TBD by audit subagent" markers remaining).

### PR-2 — Tier-B validator dispatch swap (reader-before-producer)

**Scope**: rewrite `backend/yen_gov/validate.py` (or wherever Tier-B dispatch lives) per the §0.7 verdict on retained-schema dispatch. Add a regression test that the new dispatch validates every artifact family identically to the old `$schema_version`-keyed dispatch. **Reader-first**: writers continue to stamp `$schema_version` for now; the validator just doesn't depend on it anymore.

**Acceptance**: pytest green. Every artifact family validates identically pre/post.

### PR-3 — Replacement-field landing (also reader-before-producer)

**Scope**: introduce `origin.date_accessed` on `source.csv` per §0.7 verdict (likely a new optional 6th column on the citation ledger — note this technically expands the 5-col contract from PR-#963's [ADR-NNNN citation-ledger-5col](../docs/concepts/data-provenance.md#adr-nnnn-citation-ledger-5col); the user verdict may instead place it on a sibling metadata block to preserve the 5-col binding). Introduce `dataset.update_period_days` as uniform across `datasets/taxonomy/indicators.json` rows. **Readers learn to use these fields**; writers do not yet populate them (one indicator family pilot, then sweep in PR-5+).

**Acceptance**: reader code paths exercise the new fields with synthetic fixtures; no on-disk artifact has the new fields yet.

### PR-4 — Writer pivot for one artifact family (pilot)

**Scope**: pick ONE artifact family (e.g. `datasets/_ops/indicators-completeness.json` — smallest, single-file, well-isolated). Rewrite its writer (`tools/emit_indicators_completeness_index.py`) to OMIT `$schema_version`. Rewrite its `.schema.json` to remove the field from `required[]` + `properties`. Re-emit the artifact. Verify Tier-B validator (post-PR-2 swap) still validates. Verify no consumer breaks.

**Acceptance**: one artifact on disk no longer carries `$schema_version`; validator + consumers + tests all green.

### PR-5+ — Per-family writer-pivot sweeps

**Scope**: one PR per artifact family per §0.7 verdict on rollout granularity. Each PR:
1. Rewrites the family's writer to omit the field.
2. Removes the field from the family's `.schema.json`.
3. Re-emits the family's artifacts (drop the line on disk).
4. Sweeps any contract test that asserted on the field's presence.

Estimated 8-15 PRs depending on family granularity. The 5 hardcoded `"1.0"` tool sites land in the LAST PR (they're tools, not adapters; deleting them last simplifies the audit by ensuring no in-flight tool run emits a stale stamp during the migration).

**Acceptance** (final PR): zero `.json` files in `datasets/` carry `$schema_version`. Zero writer sites stamp it. Zero `.schema.json` files declare it. Tier-B validator and frontend reader both work. PR-0 ADR-NNNN status flips from "in progress" to "complete".

### PR-FINAL — Doctrine cleanup

**Scope**: delete this plan-doc's §0.4 / §0.5 audit blocks (they're now historical). Move this plan-doc to `docs/archive/plans/` per the [distill-a-plan](../docs/how-to/distill-a-plan.md) flow. Update [schema-evolution.md](../docs/architecture/data/schema-evolution.md) — replace the "Pending OWID-conformance pivot" section with an "ADR-NNNN: schema-version field retirement" stanza in Design rationale. Remove the open divergence #5 from [owid-alignment.md](../docs/concepts/owid-alignment.md). Update CLAUDE.md §11 to reflect the final shape.

---

## Section 2 — Acceptance criteria (whole-plan)

When the last PR merges:

- **Zero data emit files in `datasets/`** carry `$schema_version`.
- **Zero writer sites** stamp `$schema_version` (the 6 producer sites + any auxiliary `core/schema_registry.py:schema_version()` callers are all retired).
- **Zero `.schema.json` files** declare `$schema_version` in `required[]` or `properties[]`.
- **Tier-B validator** dispatches on the new key (per §0.7 option); regression test proves identical validation pre/post.
- **Frontend reader / contract tests** do not reference `$schema_version`.
- **`origin.date_accessed`** populated on every source.csv row (or sibling metadata block per §0.7 verdict).
- **`dataset.update_period_days`** populated on every indicator catalogue row.
- **CLAUDE.md §11** rewritten to reflect the new OWID-conformance grammar; the writer-strict / reader-compatible operational policy in [schema-evolution.md](../docs/architecture/data/schema-evolution.md) survives because it's about WRITERS emitting current versions, not about the `$schema_version` STAMP itself.
- **[owid-alignment.md](../docs/concepts/owid-alignment.md)** no longer carries the divergence #5 row.

---

## Section 3 — Open questions (carry into PR-0 debate)

- **Migration cost vs deletion benefit**: is the citizen-facing value of OWID grammar conformance worth N PRs of churn across the corpus? Hans/Citizen verdict matters most here. The honest counter-position is: the field is correctly populated today and consumers mostly ignore it; the duplication is grammatical, not functional. If the persona debate rules "leave it as-is and document the divergence permanently," that's a legitimate outcome — the plan would close with no code changes and just a permanent named divergence in [owid-alignment.md](../docs/concepts/owid-alignment.md).
- **Schema-shape evolution dispatch**: if the pivot drops retained-schema validation (PR-2 option (a)), is there a use case we lose? The current archive has ONE entry (`elections-inventory/v1.0/`); pre-canonical-store-pivot history is largely uncoupled from this contract. But the loss is reversible-only-with-effort: once we delete the archive infrastructure, restoring it costs more than originally building it.
- **`update_period_days` enforcement**: the current indicator catalogue does not enforce uniform population of this field. Should the pivot make it `required` for every indicator? Hans + Max verdict.
- **OWID's actual conformance**: OWID has its own dialects (YAML vs JSON, ETL vs grapher). Are we adopting OWID's `origin.date_accessed` literal field name, or yen-gov's own equivalent (`fetched_at`, `last_polled_at`, etc.)? Default is to use OWID's literal names because the user mandate is "OWID conformance style"; but if grep finds 50 references to `fetched_at` in the codebase already, the cost of renaming may exceed the conformance benefit. Audit subagent verdict.
- **Versioned schema URLs as an alternative**: instead of stamping the version on each artifact, embed it in the schema URL (`https://yen-gov.github.io/schemas/manifest.v2.schema.json`). This is HALF of the OWID approach (OWID's `$id` URLs are versioned). yen-gov already does this partially. Should the pivot complete it? Gregor verdict.
- **Boundary SoT shards at `4.1`**: 28 per-state files all carry the stamp. If the pivot removes the stamp but the boundary schema itself bumps to `5.0` for a real shape change later, do we lose the ability to discriminate which on-disk shards are pre-bump? (Yes, but Tier-B validation against current schema catches the discrepancy. The discriminator IS the schema validator's verdict, not a per-file stamp.) Confirm with Fowler.

---

## Section 4 — Stop conditions (whole-plan)

Halt the plan and surface to user if:

- Any §0.7 question's persona debate fails to converge after one round.
- The Tier-B validator dispatch swap (PR-2) reveals a class of consumer the audit missed.
- The OWID-conformance grammar conflicts with an existing yen-gov hard contract (e.g. `derive_source_id`'s 3-arg signature being affected by adding `date_accessed` to the source row identity — must NOT happen).
- The migration cost estimate in PR-1's audit comes back at >10 PRs and the user wants to reconsider whether the divergence is worth retaining (return to the §0.4 "default if unresolved" verdict: accept the divergence as permanent, document it in [owid-alignment.md](../docs/concepts/owid-alignment.md)).

---

## See also

- [docs/architecture/data/schema-evolution.md §Pending OWID-conformance pivot](../docs/architecture/data/schema-evolution.md#pending-owid-conformance-pivot-stop-stamping-schema_version-onto-data-emit-files) — the operational-policy note that points here.
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md) — fallback doctrine; this plan closes Named divergence #5.
- [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md) — citation-ledger contract; the natural home for `origin.date_accessed`.
- [OWID metadata reference](https://docs.owid.io/projects/etl/architecture/metadata/reference/) — canonical source for OWID grammar.
- [TODO/20260611-sources-simplification-plan.md](20260611-sources-simplification-plan.md) — precedent for "extraordinary cleanup" plan shape; this plan follows its operating-contract grammar.
