# Schema-version field refactor - OWID-conformance pivot plan

**Last Updated**: 2026-06-12 (PR-0 ratification)
**Status**: PR-0 ratified. Open questions in section 0.7 closed by 4-persona debate (Gregor, Hans, Max, Fowler). Scope narrowed from "wide pivot" (8-15 PRs, ~50 schemas + 120 artifacts + new fields) to **"scoped retirement"** (~5-7 PRs, $schema_version stamp dropped from citizen-facing data files only, manifest.json carved out, no new fields). Awaiting user verdict on Path A vs Path B (see section 5) before PR-1 ships.
**Level**: 3 (was Level-4 under the original wide framing; narrowed scope reduces blast radius to a citizen-facing-data-file sweep with one explicit control-plane carve-out for manifest.json).
**Strategy**: drop the `$schema_version` field from every JSON data emit file EXCEPT `datasets/manifest.json` (control-plane carve-out per CLAUDE.md section 10). Schema-shape identity lives in the `.schema.json` file's own `x-version` (already true). No new fields added; existing OWID-shape concerns (`vintage`, `update_period_days`) already live on the right surfaces. Tier-B validator dispatch swap is dead-code deletion (the retained-schema dispatcher is not in the live hot path). Multi-PR rollout per the writer-strict / reader-compatible policy in [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md).

> User mandate, 2026-06-12: "no more calling it schema version" + "OWID conformance style" + "the downstream impact on updating all indicators and datasets might be hugh ... ok update doc and add todo plan, will pick it up later." This plan-doc is the carry-over; PR-0 ratifies the scope.

> **PR-0 does NOT modify the writer-strict / reader-compatible policy.** Until later PRs ship, every new artifact still stamps `$schema_version` per the current contract. The scoped pivot atomically retires the field per artifact family with reader-before-producer rollout; partial / per-artifact retirement is forbidden because it creates a half-migrated surface where some artifacts use OWID grammar and others do not. Manifest.json keeps the field (named carve-out, not a half-migration).

---

## Section 0 - Operating contract

### 0.1 Goal

Bring yen-gov's schema-versioning grammar into OWID-conformance on the surface that matters: stop stamping a top-level `$schema_version` semver on every citizen-facing JSON data emit file; keep the field on `datasets/manifest.json` (control-plane bootstrap surface; deployed static bundle reads it via `isCompatibleSchemaVersion()` in [`frontend/src/lib/duckdb.ts`](../frontend/src/lib/duckdb.ts) + [`frontend/src/lib/canonical/manifest.ts`](../frontend/src/lib/canonical/manifest.ts)). Schema-shape identity stays in the `.schema.json` file's `x-version` (already true). This narrows [Named divergence #5](../docs/concepts/owid-alignment.md#named-divergences-from-owid-with-reasons) from "open pivot" to "scoped pivot with documented carve-out" and aligns the citizen-facing data emit grammar with the [OWID metadata reference](https://docs.owid.io/projects/etl/architecture/metadata/reference/).

### 0.2 What this plan does

| Surface | Today | After this plan |
|---|---|---|
| Top-level field on every citizen-facing JSON data emit file | `$schema_version: "<semver>"` (stamped by writer from schema's `x-version`) | (deleted) |
| Top-level field on `datasets/manifest.json` | `$schema_version: "1.4"` | **KEPT** (CLAUDE.md section 10 control-plane carve-out; deployed bundle gates on it) |
| Schema-shape identity | Two places - `.schema.json` file's `x-version` AND the data file's `$schema_version` sibling (duplicated) | One place on citizen-facing data files - `.schema.json` file's `x-version` only. Manifest keeps both per carve-out. |
| Tier-B validator dispatch | reads `$schema_version` from artifact + checks against `_json_corpus_accepted_versions()` set built from compatibility registry | reads only `$schema` URL; validates against current schema resolved by URL (drops the version-string check + the `json-corpus` surface from `datasets/schema-compatibility.json`; the `canonical-manifest-reader` surface stays for manifest) |
| Schema-required declaration | ~50 `.schema.json` files list `$schema_version` in `required: [...]` | Field removed from `required[]` + `properties` in every schema EXCEPT `manifest.schema.json`. One shared `$defs/version` ref (in `columns.schema.json`, `schema-evolution.schema.json`) deleted. |
| Writer behaviour | every emit site adds the `$schema_version: schema["x-version"]` line | every emit site EXCEPT manifest omits the line; lint test enforces absence on citizen-facing artifacts; manifest writer keeps the stamp |
| Reader behaviour | most consumers IGNORE the field (the schema validator just validates against `.schema.json`); manifest reader dispatches on it; a few contract tests assert on the literal | reader/test sweep drops every presence-of-`$schema_version` assertion on citizen-facing artifacts; manifest reader unchanged |
| Hardcoded `"1.0"` tool sites | 5 places (see audit) - drift hazard | retired by deletion (the field vanishes when the writer stops stamping it; no rewire to `schema["x-version"]` needed) |
| Replacement fields (`origin.date_accessed`, `dataset.*` namespace) | not added | **NOT ADDED**. Semantic already covered by `source.csv.vintage` (per [ADR-0042](../docs/concepts/data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor)) + `indicators.json.update_period_days` (per CLAUDE.md section 10 anti-pattern stack + Tier-B `tier_b_indicator_freshness_declared`). |
| `update_period_days` enforcement | already on every catalogue row (100+ rows sampled, zero nulls); enforcement gate `tier_b_indicator_freshness_declared` is live | tighten to **required** in [datasets/schemas/indicator-catalogue.schema.json](../datasets/schemas/indicator-catalogue.schema.json) in the FINAL sweep; doctrinal ratification of the on-disk reality |
| `source.csv` row shape | 5-col binding contract ratified 2026-06-11 (ADR citation-ledger-5col) | **UNCHANGED**. The OWID-shape `origin.date_accessed` semantic does NOT land as a 6th column; mutable wall-clock at the citation row re-opens the `fetched_at smear` failure mode from /memories/lessons.md 2026-05-16. Operator-tier freshness stays in `_ops/` + `.runtime/` (where it already lives). |

### 0.3 What this plan does NOT do

- Touch the existing `.schema.json` files' `x-version` declarations. Schema-shape identity continues to live there; this plan only stops DUPLICATING it onto every data file.
- Touch the `x-changelog` blocks. Per-schema evolution history continues exactly as today.
- Touch the writer-strict / reader-compatible operational policy in [schema-evolution.md](../docs/architecture/data/schema-evolution.md). That policy survives verbatim; only the on-disk citizen-facing field disappears.
- Touch the `derive_source_id` 3-arg hash or the `(producer, title, vintage)` citation-ledger identity. ADR-0032 + ADR-0042 + ADR citation-ledger-5col (2026-06-11) all survive unchanged.
- Touch the 5-col `source.csv` shape. NO 6th column for `date_accessed`. The OWID concern is already covered by `vintage` (publisher-edition tag per ADR-0042) for vintaged sources, and by operator-tier `_meadow/<source>/<vintage>/` snapshot directories for non-vintaged sources.
- Touch the canonical long-format CSV observation rows (the `data/datapoints/**` tier). Observations carry `source_id` FKs; no `$schema_version` field exists at the observation-row grain today, and none will after.
- Touch `datasets/manifest.json`'s `$schema_version` stamp. Documented as a CLAUDE.md section 10 control-plane carve-out (alongside `generated_at`). Manifest is bootstrap, never citizen-rendered, gated by the live deployed static bundle.
- Rename `vintage` to `version_producer`. Max persona verdict (2026-06-12): `vintage` carries stronger semantics than OWID's `version_producer` per ADR-0042 (covers vintaged AND operator-snapshot-anchored sources in one field); renaming throws away a 17-day-old four-persona decision.
- Introduce a `dataset.*` or `origin.*` namespace. Max persona verdict: the OWID-namespaced concerns already live on the right yen-gov surfaces (vintage on source.csv, update_period_days on indicator catalogue); no new namespace needed.
- Replace the field with a renamed equivalent on citizen-facing files. The user mandate is "no more calling it schema version"; the pivot DELETES, not RENAMES.

### 0.4 OWID precedent

[OWID's metadata reference](https://docs.owid.io/projects/etl/architecture/metadata/reference/) treats four concerns as distinct:

| Concern | OWID field | yen-gov current surface | After pivot |
|---|---|---|---|
| Schema-shape identity | (none on data file; lives in `.schema.json` `x-version` / `$id` URL) | `.schema.json` `x-version` + duplicated `$schema_version` stamp on every data file | `.schema.json` `x-version` only on citizen-facing artifacts; manifest keeps the duplicated stamp per carve-out |
| Data freshness pointer | `origin.date_accessed` (when WE pulled the bytes); immutable per snapshot directory in OWID practice (`snapshots/<source>/<date>/`) | `_meadow/<source>/<vintage>/` operator snapshot directories + `.runtime/<adapter>/<source_id>.json` sidecars + `_ops/indicators-completeness.json` overlays | unchanged - already at OWID parity in spirit; the snapshot directory IS the OWID `date_accessed` |
| Publisher edition tag | `origin.version_producer` | `source.csv.vintage` per [ADR-0042](../docs/concepts/data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor) - covers publisher-vintaged AND operator-snapshot-anchored sources | unchanged - yen-gov local name kept (semantic stronger than OWID's `version_producer`; ADR-0042 receipt) |
| Expected refresh cadence | `dataset.update_period_days` (e.g. 365 for annual, 30 for monthly) | already on every indicator catalogue row per [ADR-0046](../docs/architecture/data/canonical-store.md) + CLAUDE.md section 10 anti-pattern stack; sampled 100+ rows, zero nulls | tighten to `required` in catalogue schema (doctrinal ratification of on-disk reality) |

The lift is mostly SUBTRACTION (drop the duplicated identity stamp on citizen-facing files) + DOCTRINAL RATIFICATION (`update_period_days` to `required`). The semantic content for the other three OWID concerns is already in place under yen-gov-native names. The pivot's value is in (1) removing one redundant artifact across ~120 files + ~50 schemas + 6 writer sites; (2) eliminating the 5 hardcoded `"1.0"` drift hazards by deletion; (3) closing Named divergence #5 from open to scoped-with-carve-out.

### 0.5 Audit - what's on disk today (2026-06-12; PR-1 will produce the complete list)

**Schemas declaring `$schema_version` as required**: ~50 `.schema.json` files in `datasets/schemas/`. Pattern is uniformly `{ "type": "string", "pattern": "^\\d+\\.\\d+$" }` (semver-2-position). Sample:

- `indicator.schema.json` (required for indicator artifacts)
- `manifest.schema.json` (required for `datasets/manifest.json`) - **KEPT per carve-out**
- `indicators-completeness.schema.json` (required for `datasets/_ops/indicators-completeness.json`)
- `constituency.schema.json`, `election.schema.json`, `party.schema.json` (electoral artifacts)
- `taxonomy-parties.schema.json`, `topic-catalogue.schema.json`, `methodology-break.schema.json` (taxonomy)
- `feature_collection.metadata.schema.json` (geo features)
- `lgd-*.schema.json` (LGD lookups)
- `result.constituency.schema.json`, `result.summary.schema.json` (election results)
- ... and ~35 more. PR-1 audit subagent will produce the complete list.

**Artifacts on disk carrying the stamp**: 120+ (grep cap was hit at 200; estimated true count 500-2000 once boundary partition shards + per-state election shards are counted). Sample:

- All boundary SoT (`datasets/data/entities/boundaries_sot/SXX/constituencies.json`) at `4.1` - 28 files
- All taxonomy files (`datasets/taxonomy/*.json`) at `1.0`-`3.0` - ~14 files
- All grapher files (`datasets/grapher/*.json`) at `1.0`-`1.1` - ~5 files
- All `_ops/` files at `1.0`-`2.0` - ~5 files (operator-tier; still retired per the scope)
- All election event/result/inventory files - count TBD by PR-1 audit subagent
- `datasets/manifest.json` at `1.4` - **KEPT per carve-out**
- `datasets/data/_schema/columns.json` at `2.0`

**Writer sites**:

- 1 well-behaved (reads from schema): `tools/emit_indicators_completeness_index.py:180` - `"$schema_version": schema["x-version"]`
- 5 hardcoded literal (drift hazard, retired by DELETION): `tools/gen_election_tile_layouts.py:326,375`, `tools/lgd/parse_lgd_export.py:582`, `tools/lgd/snapshot.py:132`, `tools/boundaries/enrich_census_code_2011.py:456,483` - `"$schema_version": "1.0"`. PR-1 audit confirms whether these are the only literal sites or if more surface.
- N more writer sites in `backend/yen_gov/canonical/` and `backend/yen_gov/pipeline/` that stamp via `core/schema_registry.py:schema_version()` - count TBD by PR-1 audit subagent.

**Consumers (Fowler-recommended 3-class split, to be confirmed in PR-1)**:

1. **Load-bearing dispatchers** (gate per-family ordering): `frontend/src/lib/canonical/manifest.ts:41-57` (gates `parseManifest()` on `manifest.$schema_version`), `frontend/src/lib/duckdb.ts:102-105` (calls `isCompatibleSchemaVersion()`). Both stay live because manifest is the carve-out.
2. **Cosmetic destructurers** (typed-loader interfaces that round-trip the value without branching): swept with `Remove Parameter` / `Inline Field` per Fowler in same PR as their family's schema edit.
3. **Test-fixture stampers**: 50+ (`datasets-conform.test.ts:296-301` is a hard gate; PR-1 audit enumerates all).

**Tier-B validator dispatch (the load-bearing question, resolved by Gregor + Fowler)**:

- Live path: [`backend/yen_gov/validate.py`](../backend/yen_gov/validate.py) `tier_b()` reads `data.get("$schema_version")` at line ~410 and checks against the accepted-versions set built from [`datasets/schema-compatibility.json`](../datasets/schema-compatibility.json).
- Dead path: [`backend/yen_gov/core/schema_evolution.py`](../backend/yen_gov/core/schema_evolution.py) `resolve_schema_for_declared_version()` (lines ~111-151) - **NOT called from `tier_b()` hot path**. The archive at `datasets/schemas/archive/elections-inventory/v1.0/` (1 entry) is reachable only via this dead path. PR-2 deletes the json-corpus accepted-versions check; the dead path can stay as cold storage or retire in a follow-up.

### 0.6 ESCALATE triggers (scoped to the narrowed pivot)

The orchestrator stops ONLY at:

1. **PR-1 audit surfaces a consumer that asserts on the field's VALUE (not just presence)** on a citizen-facing artifact other than manifest. A consumer that branches on `if doc["$schema_version"] >= "2.0":` needs a translator at the reader before the writer pivot; STOP-AND-SURFACE.

2. **PR-1 audit surfaces a `.schema.json` `x-changelog` that predicts a future bump depending on `$schema_version` being readable at the artifact level**. Same response - the change has to land BEFORE the pivot, or the pivot has to design around it.

3. **A consumer of `$schema_version` is discovered on the manifest carve-out side that disagrees with the documented bootstrap-only role** (e.g. a citizen-rendered chart reads `manifest.$schema_version` as a citizen-facing label). STOP-AND-SURFACE - either the carve-out is wider than expected or the citizen surface needs a rewire.

4. **The browser smoke (CLAUDE.md section 13) after PR-4 reveals a citizen surface degrades** (any 404, any console error, any failed request, any missing chart) on a route that exercises an artifact whose `$schema_version` was just retired. STOP-AND-SURFACE.

The original ESCALATE-4 (`origin.date_accessed` fetched-at smear) does NOT apply to the scoped pivot because `origin.date_accessed` is not introduced.

### 0.7 PR-0 ratified verdicts (closed by 4-persona debate 2026-06-12)

| Open question | Personas | PR-0 verdict | Reason |
|---|---|---|---|
| Tier-B retained-schema dispatch - option (a) drop / (b) versioned URL / (c) operator-tier-only | Gregor + Fowler | **(a) drop retained-schema dispatch entirely.** Drop the `json-corpus` accepted-versions check + the `_json_corpus_accepted_versions()` function + the `json-corpus` surface from `datasets/schema-compatibility.json`. KEEP the `canonical-manifest-reader` surface (manifest carve-out). | The retained-schema dispatcher is not in the live `tier_b()` hot path; the archive has 1 entry; option (a) is dead-code deletion. Options (b)/(c) are net-new infrastructure to replace infrastructure with zero live consumers. Joint Gregor + Fowler verdict. |
| `origin.date_accessed` location (source.csv 6th column / sibling .metadata.json / reject) | Gregor + Hans + Max | **REJECT.** Do not add the field. Semantic already in `source.csv.vintage` (vintaged sources) + `_meadow/<source>/<vintage>/` snapshot directories (non-vintaged sources). | Adding the field re-opens the 5-col `source.csv` contract ratified 24hr ago (2026-06-11); re-introduces the `fetched_at smear` from /memories/lessons.md 2026-05-16; produces zero citizen-axis signal (the median citizen cites publisher's edition, not our pipeline poll-time); supersedes 17-day-old ADR-0042 + 1-day-old ADR citation-ledger-5col simultaneously. 3-persona convergence. |
| `dataset.update_period_days` axis (per-indicator / per-source / hybrid) | Hans + Max | **per-indicator** (status quo; field already on every catalogue row sampled). | A single Indian publisher routinely emits multi-cadence datasets (RBI HBS-IS = annual + quarterly mix; CEA Monthly = monthly + annual mix); per-source axis under-promises on the faster series. Cross-source overlay UX needs per-line-resolution cadence chips. Hans + Max convergence with concrete cases (NDLM monthly vs annual, RBI quarterly vs annual, future Census-SECC dual-cadence). |
| Migration granularity (one-shot / per-family) | Fowler | **per-family sweep** (default). Each PR = one artifact family with TIDY-FIRST commit split (structural schema edit + behavioural writer rewrite + on-disk re-emit as separate commits in the same PR). | Reviewer-bounded diffs; clean revert surface (one git revert per family); pre-staging to `legacy/` namespace per the 2026-05-22 strangler-fig pattern does NOT apply (no shared module to pre-stage; flat literal per schema file). *Inline Field* + *Remove Setting Method* (Refactoring catalogue) fit better. |
| `manifest.json` retention | Gregor + Fowler | **KEEP** as documented CLAUDE.md section 10 control-plane carve-out (alongside `generated_at`). | Manifest is bootstrap; deployed static bundle reads it via `isCompatibleSchemaVersion()` in `frontend/src/lib/duckdb.ts` + `frontend/src/lib/canonical/manifest.ts`; dropping the field forces either a versioned-URL migration (Q6 cost, rejected) or silent-accept any shape (regression on ADR-0047's "future-version-not-supported" diagnostic). The carve-out costs one line of doctrine; the bootstrap rewire costs a multi-deploy strangler-fig PR sequence. User mandate "no more calling it schema version" applies to CITIZEN-FACING data; manifest is operator-tier bootstrap, never rendered on a citizen surface. |
| `update_period_days` enforcement (required / optional / required-with-sentinel) | Hans + Max | **required** (no carve-outs; ratify on-disk reality). Tighten in [datasets/schemas/indicator-catalogue.schema.json](../datasets/schemas/indicator-catalogue.schema.json) in the FINAL sweep. | Field already populated on every row sampled (100+ across electoral/energy/livestock/RBI/Census/NFHS); `tier_b_indicator_freshness_declared` already enforces; OWID's own enforcement is `required` per metadata reference. Max + Hans convergence. The honest-null-sentinel debate (-1 for one-shot, 0 for publisher-discretion) is deferred to the future PR that adds a Census-2011 or CAG-audit indicator with no committed next refresh; today's corpus does not have one. |
| Versioned schema URLs (Q6 follow-on) | Gregor | **REJECT as part of this pivot.** Allow a separate follow-up to consolidate `$id` URL grammar (today is mixed: 22/53 schemas use `https://yen-gov.github.io/...`, 31/53 use `./<name>.schema.json`; CLAUDE.md section 11 currently bans the URL form but reality has diverged). Adding version SEGMENTS is a separate concern from picking ONE grammar. | Pivot's value is SUBTRACTION; versioned URLs trade per-file per-bump restamp churn for per-file per-bump $schema-URL churn (a wash on cost, a regression on framing). 53 schema renames + every artifact's `$schema` URL update + validator URL-parsing rewrite = 4-6 PRs of pure churn for marginal OWID-conformance gain. |
| Boundary shard discriminator (Q11) | Gregor + Fowler | **validator-only.** No per-file fingerprint. The validator's verdict against current schema IS the per-file truth. | Per-file sha256 fingerprint is enterprise ceremony without a named beneficiary; re-introduces exactly the stamp the pivot is retiring, just renamed; adds fragility (doc-only schema edits change sha256 without changing the contract). OWID precedent matches: no per-file fingerprint. The schema-evolution ledger ([datasets/schema-evolution.json](../datasets/schema-evolution.json)) + git history of the schema file suffice for the rare archaeology case. |
| OWID literal names vs yen-gov locals (Q10) | Max | **hybrid per-field**: keep `vintage` (semantic stronger than OWID's `version_producer` per ADR-0042); keep `update_period_days` (already OWID-literal); do NOT add `date_accessed` (semantic already in `vintage` + `_meadow/.../<vintage>/`); do NOT introduce `dataset.*` or `origin.*` namespace; `owner -> producer` rename proceeds in the separate [sources simplification plan](20260611-sources-simplification-plan.md), not here. | Cost-benefit pivots per field: when local name semantically matches OWID literal, adopt OWID; when local is deliberately sharpened beyond OWID, keep local + document. Mechanical field-name substitution is conformance theatre. |

### 0.8 Per-PR workflow

Standard:
1. Branch off `origin/main` in a sub-worktree (`git worktree add ../yen-gov-<row> -b feat/schema-version-<row> origin/main`).
2. Implement scope per the row brief. Tests ship with the row.
3. Local gates GREEN (pytest, vitest, svelte-check, browser smoke per CLAUDE.md section 13 for citizen-facing surfaces).
4. Commit + push + `gh pr merge --squash --admin --delete-branch`.
5. Master worktree pulls main + tears down the sub-worktree per the per-PR cleanup ritual. Start next row.

TIDY-FIRST split for writer-pivot PRs (PR-3 onwards): one commit per structural change (schema edit, writer interface change) separate from the behavioural change (writer output / re-emit). Per Beck's *Tidy First*: each commit independently revertible.

---

## Section 1 - PR sequence (post-PR-0 narrowed scope)

Reader-before-producer (per [schema-evolution.md section Rollout Order](../docs/architecture/data/schema-evolution.md#rollout-order)). Each PR ships AS A WHOLE; no partial / per-artifact rollout. Manifest is OUT-OF-SCOPE for every PR below (documented carve-out).

### PR-0 - Doctrine ratification + plan-doc rewrite + CLAUDE.md section 10 carve-out

**Scope (this PR)**:
1. Rewrite this plan-doc with PR-0 ratified verdicts (section 0.7 closed; section 1 narrowed).
2. Add the `$schema_version` carve-out for `datasets/manifest.json` to CLAUDE.md section 10 alongside the existing `generated_at` carve-out.
3. Update [docs/architecture/data/schema-evolution.md](../docs/architecture/data/schema-evolution.md) section Pending OWID-conformance pivot to reflect the scoped pivot (manifest carve-out + no new fields).
4. Update [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md) Named divergence #5 to flag the scope narrowing (still open; will close when PR-4+ ships; PARTIAL alignment after pivot lands with manifest as remaining documented carve-out).

**No code changes.** Doc-only PR, 4 files, reversible at any time.

**Acceptance**: all section 0.7 questions have a verdict in this plan-doc. CLAUDE.md section 10 has the new carve-out. schema-evolution.md + owid-alignment.md are aligned with the narrowed scope. Doc-only diff. User picks Path A (close as permanent divergence; ship only the 5-hardcoded-tool-sites fix) or Path B (proceed with PR-1+ per the scoped sequence below) in section 5 before PR-1 dispatches.

### PR-1 - Audit subagent grep + populate this plan-doc's section 0.5 with the FULL 3-class consumer split

**Scope**: exhaustive grep for every consumer / writer / reader / contract test referencing `$schema_version`. Audit subagent ships back a report split per Fowler's 3-class taxonomy (load-bearing dispatchers / cosmetic destructurers / test-fixture stampers). Orchestrator pastes the full list into section 0.5 of this plan and commits. **No code changes**; the report drives the per-family PR sequence.

**Acceptance**: this plan-doc's section 0.5 has a complete enumeration (no "TBD by PR-1 audit subagent" markers remaining). The 3-class split lets PR-2's regression test be honestly scoped and PR-3+ family ordering be safely sequenced.

### PR-2 - Tier-B validator dispatch swap (reader-before-producer)

**Scope** (per Gregor + Fowler Q1 verdict (a)):
1. Delete `_json_corpus_accepted_versions()` from [`backend/yen_gov/validate.py`](../backend/yen_gov/validate.py).
2. Delete the `accepted_versions` check inside `tier_b()` (the `data.get("$schema_version")` read + the version-string match against the registry).
3. Delete the `json-corpus` surface from [`datasets/schema-compatibility.json`](../datasets/schema-compatibility.json). **KEEP** the `canonical-manifest-reader` surface (manifest carve-out).
4. Leave [`backend/yen_gov/core/schema_evolution.py`](../backend/yen_gov/core/schema_evolution.py) `resolve_schema_for_declared_version()` + [`datasets/schemas/archive/elections-inventory/v1.0/`](../datasets/schemas/archive/elections-inventory/v1.0/) as cold storage (not in hot path; may retire in a follow-up PR-X if no consumer surfaces).

**Regression test shape** (per Fowler):
- Golden-output diff: run `python -m yen_gov validate --root .` against the live `datasets/**` + `config/**` corpus pre-swap; capture the `[tier B] <path>: <message>` list. Apply the swap; re-run; assert the post list is the pre list MINUS exactly the `"$schema_version ... is not accepted ..."` failure class.
- One new `tmp_path` fixture per [`backend/tests/test_validate.py`](../backend/tests/test_validate.py) conventions: artifact without `$schema_version`. Post-swap MUST validate; pre-swap MUST fail.

**Acceptance**: pytest green. Every artifact family validates identically pre/post except for the deliberately-removed version-string check. ~80 LOC out, ~10 LOC in. Single revert recovers the swap.

### PR-3 - Writer pivot for `datasets/_ops/indicators-completeness.json` (pilot, single-file family)

**Scope** (TIDY-FIRST commit split per Fowler):

*Commit 1 (structural)*: edit [`datasets/schemas/indicators-completeness.schema.json`](../datasets/schemas/indicators-completeness.schema.json) - drop `$schema_version` from `required[]` + `properties`. Validator still passes existing artifacts (they still carry the field; the schema simply no longer demands it). Pure schema loosening.

*Commit 2 (behavioural)*: edit [`tools/emit_indicators_completeness_index.py:180`](../tools/emit_indicators_completeness_index.py) - rewrite writer to OMIT `$schema_version`. Re-emit `datasets/_ops/indicators-completeness.json` (drop the line on disk). Verify Tier-B (post-PR-2 swap) still validates.

**Acceptance**: one artifact on disk no longer carries `$schema_version`; validator + consumers + tests all green. Pilot proves the per-family sweep shape. Operator-tier file (`_ops/`), so no browser smoke required per CLAUDE.md section 13.

### PR-4 - Per-family writer-pivot sweep: taxonomy (datasets/taxonomy/*.json)

**Scope**: 
1. *Commit 1 (structural)*: drop `$schema_version` from `taxonomy-parties.schema.json`, `topic-catalogue.schema.json`, `methodology-break.schema.json`, `election-events.schema.json`, `indicator-catalogue.schema.json`, etc. (PR-1 audit enumerates all).
2. *Commit 2 (behavioural)*: rewrite writers (likely centralised in `backend/yen_gov/canonical/*` or `tools/emit_*.py`) to omit the field; re-emit all ~14 `datasets/taxonomy/*.json` files.
3. Sweep any contract test that asserts on the field's presence within this family.
4. Browser smoke per CLAUDE.md section 13 on at least 3 routes that read a taxonomy artifact (most do via the canonical catalogue + party tooltip + topic page).

**Acceptance**: zero `datasets/taxonomy/*.json` files carry `$schema_version`; validator + consumers + tests all green; browser smoke clean.

### PR-5 - Per-family writer-pivot sweep: grapher (datasets/grapher/*.json)

Same shape as PR-4 for the ~5 grapher catalogue files per [ADR-0045](../docs/architecture/data/indicator-catalogue.md#adr-0045-grapher-catalogue-split). Browser smoke on a chart-rendering route.

### PR-6 - Per-family writer-pivot sweep: boundary SoT (datasets/data/entities/boundaries_sot/*/constituencies.json)

Same shape for the 28 per-state boundary SoT shards at `4.1`. Browser smoke on the state choropleth + election event map routes.

### PR-7 - Per-family writer-pivot sweep: election results + inventory

Same shape for the per-state election results + the inventory artifacts. Count TBD by PR-1 audit. Browser smoke on the election-event page + state hub.

### PR-8 - Per-family writer-pivot sweep: remaining operator-tier files (_ops/, columns.json) + tighten `update_period_days` to required

**Scope**:
1. Drop `$schema_version` from any remaining `_ops/` files surfaced by PR-1 audit + from `datasets/data/_schema/columns.json`.
2. *(Doctrinal ratification)*: tighten `update_period_days` to `required` in [`datasets/schemas/indicator-catalogue.schema.json`](../datasets/schemas/indicator-catalogue.schema.json) per Hans + Max Q9 verdict. On-disk reality is already at parity (100+ rows sampled, zero nulls); this commit just locks the gate.

**Acceptance**: zero citizen-facing artifacts carry `$schema_version`; `update_period_days` enforced as `required`; validator + consumers + tests all green.

### PR-FINAL - Doctrine cleanup

**Scope**:
1. Delete this plan-doc's section 0.4 / 0.5 audit blocks (they're now historical).
2. Move this plan-doc to `docs/archive/plans/` per the [distill-a-plan](../docs/how-to/distill-a-plan.md) flow.
3. Update [schema-evolution.md](../docs/architecture/data/schema-evolution.md) - replace the "Pending OWID-conformance pivot" section with an ADR-NNNN entry in Design rationale (titled `schema-version-field-retirement` with manifest carve-out documented).
4. Update [owid-alignment.md](../docs/concepts/owid-alignment.md) Named divergence #5: was open pivot -> becomes **PARTIAL ALIGNMENT** with `manifest.json` documented as remaining named carve-out (control-plane bootstrap, not citizen-facing).
5. Update CLAUDE.md section 11 to reflect the final shape (citizen-facing data files omit; manifest stamps; control-plane carve-out cross-referenced to section 10).

---

## Section 2 - Acceptance criteria (whole-plan, post-PR-0)

When the last PR merges:

- **Zero citizen-facing data emit files in `datasets/`** carry `$schema_version`. Manifest keeps it per carve-out.
- **Zero writer sites EXCEPT the manifest writer** stamp `$schema_version` (the 5 hardcoded `"1.0"` literals retire by deletion; the 1 `emit_indicators_completeness_index.py` site + the N `core/schema_registry.py:schema_version()` callers retire per family).
- **Zero citizen-facing `.schema.json` files** declare `$schema_version` in `required[]` or `properties[]`. `manifest.schema.json` keeps the declaration.
- **Tier-B validator** dispatches purely on `$schema` URL; regression test proves identical validation pre/post (except the deliberately-removed version-string check).
- **Frontend reader / contract tests** do not reference `$schema_version` on citizen-facing artifacts. Manifest reader (`frontend/src/lib/canonical/manifest.ts` + `frontend/src/lib/duckdb.ts`) keeps the gate.
- **`update_period_days`** required on every indicator catalogue row (doctrinal ratification; corpus already at parity).
- **CLAUDE.md section 10** carries the `$schema_version` manifest carve-out alongside the `generated_at` carve-out.
- **CLAUDE.md section 11** reflects the final shape (citizen-facing data files do NOT stamp; manifest stamps per carve-out).
- **[owid-alignment.md](../docs/concepts/owid-alignment.md)** Named divergence #5 reframed from "open" to "scoped with manifest carve-out".
- **No new fields added.** `origin.date_accessed`, `origin.version_producer`, `dataset.*` namespace - none of these introduced. Existing yen-gov surfaces (`vintage`, `_meadow/.../<vintage>/`, `update_period_days`) continue to serve the OWID-named semantic concerns.
- **`source.csv` row shape unchanged** at 5 columns per 2026-06-11 binding contract.

---

## Section 3 - Open questions (deferred, NOT blocking)

Closed in PR-0 (see section 0.7 ratified verdicts):

- ~Migration cost vs deletion benefit~ -> scoped pivot (Path B) recommended; user picks A vs B in section 5.
- ~Schema-shape evolution dispatch~ -> drop entirely (Gregor + Fowler joint).
- ~`update_period_days` enforcement~ -> required (Hans + Max joint).
- ~OWID's actual conformance / literal names~ -> hybrid per-field (Max verdict).
- ~Versioned schema URLs as alternative~ -> reject as part of this pivot (Gregor verdict).
- ~Boundary SoT shards discriminator~ -> validator-only (Gregor + Fowler joint).

Still open (deferred to in-PR resolution as they arise):

- **Honest-null sentinel for `update_period_days`** on genuinely one-shot indicators (Census 2011 with deferred 2021 round; CAG audit on publisher discretion; Finance Commission award periods). PR-8 lands the `required` gate; if a future indicator surfaces that genuinely cannot declare a positive cadence, the next PR ratifies the sentinel (`-1` = one-shot, `0` = publisher-discretion per Hans). Today's corpus has zero such cases.
- **Versioned schema URL grammar consolidation** (22 of 53 schemas use `https://yen-gov.github.io/...`, 31 use `./<name>.schema.json`; CLAUDE.md section 11 bans the URL form but reality has diverged). Separate follow-up after this pivot ships; out of scope here.
- **`owner -> producer` rename on source.csv** lives in the separate [sources simplification plan](20260611-sources-simplification-plan.md). Cross-reference only; not part of this plan.

---

## Section 4 - Stop conditions (whole-plan, scoped)

Halt the plan and surface to user if:

- The Tier-B validator dispatch swap (PR-2) reveals a class of consumer the PR-1 audit missed.
- PR-1 audit returns a 4th consumer class (beyond Fowler's 3-class taxonomy) that needs special handling.
- The CLAUDE.md section 10 manifest carve-out triggers a Gregor/Fowler "wait, that's still half-migrated" objection at PR-0 review.
- The browser smoke after any per-family PR fails on a route that previously rendered.
- The user picks Path A (close as permanent divergence) instead of Path B (proceed with scoped pivot).

---

## Section 5 - User decision required (before PR-1 dispatches)

PR-0 has narrowed the scope and ratified section 0.7. Before PR-1 dispatches, the user picks:

### Path A (Hans-conservative): close as permanent named divergence; ship only the 5-hardcoded-tool-sites fix

- **1 PR** that rewires `tools/gen_election_tile_layouts.py` x2, `tools/lgd/parse_lgd_export.py`, `tools/lgd/snapshot.py`, `tools/boundaries/enrich_census_code_2011.py` x2 to `yen_gov.core.schema_registry.schema_version(...)` per CLAUDE.md section 11 ("Code never hand-types schema-version literals").
- Move this plan-doc to `docs/archive/plans/` per the [distill-a-plan](../docs/how-to/distill-a-plan.md) flow.
- Rewrite [owid-alignment.md](../docs/concepts/owid-alignment.md) Named divergence #5 to PERMANENT named divergence with the Hans verdict cited: duplication is grammatical not functional; citizen does not see the field; OWID grammar conformance is not a citizen benefit; the four OWID concerns are already realised in yen-gov via four separate channels.
- **Pros**: 1 PR; no churn; preserves the 24hr-old 5-col source.csv contract; preserves the 17-day-old vintage semantics; closes the chronic drift hazard.
- **Cons**: keeps the divergence open; citizen-facing files keep the duplicated stamp; future bumps still need writer-side discipline.
- **Hans verdict**: this is the right shape because the citizen does not see the field; the only PRs that don't ship a methodology banner or denominator picker are PRs that don't close a citizen question.

### Path B (Gregor + Max + Fowler moderate): proceed with the scoped 5-7 PR sequence (PR-1 through PR-FINAL above)

- **5-7 PRs total** (PR-1 audit + PR-2 dispatch swap + PR-3 pilot + PR-4 through PR-7 per-family + PR-8 + PR-FINAL).
- Drops `$schema_version` from every citizen-facing data emit file; keeps manifest per carve-out; tightens `update_period_days` to required.
- **Pros**: closes Named divergence #5 to scoped-with-carve-out (cleaner OWID-conformance posture); eliminates the duplicated identity stamp; the 5 hardcoded drift hazards retire by deletion (no rewire needed); ratifies on-disk `update_period_days` reality at the schema gate.
- **Cons**: 5-7 PRs of churn; reviewer attention split across families; browser smoke per family.
- **Gregor + Max + Fowler verdict**: this is the right shape if the user wants the OWID-conformance posture to be load-bearing rather than aspirational. The narrowed scope (manifest carve-out + no new fields) reduces blast radius below the original wide-pivot risk.

### Path C (defer indefinitely)

- No PRs. Plan-doc stays in `TODO/` as an open plan with the PR-0 verdicts ratified for whenever the user picks A or B.
- Cost: zero churn; benefit: zero progress; the field-vs-divergence question stays open.

**Default if user does not pick within one session**: Path B (per plan-doc section 0.7 "Default if unresolved" pattern + 3-of-4 persona convergence on "proceed-with-PR-1").

---

## See also

- [docs/architecture/data/schema-evolution.md section Schema-version field stamping (permanent named divergence)](../../architecture/data/schema-evolution.md#schema-version-field-stamping-permanent-named-divergence) - closure receipt; doctrinal home for the permanent named divergence.
- [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) - fallback doctrine; Named divergence #5 is now PERMANENT (closed via Path A).
- [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) - citation-ledger contract; 5-col source.csv shape stays unchanged (was the binding constraint that ruled out adding `origin.date_accessed` as a 6th column).
- [OWID metadata reference](https://docs.owid.io/projects/etl/architecture/metadata/reference/) - canonical source for OWID grammar.
- [TODO/20260611-sources-simplification-plan.md](../../../TODO/20260611-sources-simplification-plan.md) - precedent for "extraordinary cleanup" plan shape; this plan follows its operating-contract grammar.
- [CLAUDE.md section 10](../../../CLAUDE.md) - anti-pattern stack carries the closure note on `$schema_version` literals + `schema_registry` mandate.
- [CLAUDE.md section 11](../../../CLAUDE.md) - schema-versioning grammar; the "Code never hand-types schema-version literals" rule is now enforced at the 5 historically-hardcoded tool sites.

---

## Section 6 - Plan complete (Path A closure, 2026-06-12)

**User verdict (2026-06-12, post-PR-0 vscode_askQuestions decision point)**: Path A. Close as permanent named divergence; ship the 1-PR drift-hazard fix.

### What shipped

| PR | Title | Status |
|---|---|---|
| #973 | docs(schema): document $schema_version OWID-conformance pivot (deferred) | merged commit d444e714e |
| #972 | chore(pipeline): repoint dim_acs_lgd_lift to ac_crosswalk.csv | merged commit 569b87c5e |
| #980 | docs(schema): PR-0 ratify schema-version field retirement verdicts + scope-narrow pivot | merged commit 67350bc31 |
| **#TBD** | **chore(tools): rewire 5 schema-version literals to schema_registry + close OWID divergence #5 as permanent (Path A)** | this PR |

### What was achieved

1. **Drift hazard repair**: 5 hardcoded `"1.0"` tool sites (2 in `tools/gen_election_tile_layouts.py`, 1 in `tools/lgd/parse_lgd_export.py`, 1 in `tools/lgd/snapshot.py`, 2 in `tools/boundaries/enrich_census_code_2011.py`) rewired to source `$schema_version` from `yen_gov.core.schema_registry.schema_version(<file>)` per CLAUDE.md section 11. Next schema bump tracks automatically; writer-strict validation no longer fails on stale literal.
2. **Doctrine ratification**: Named divergence #5 in [docs/concepts/owid-alignment.md](../../concepts/owid-alignment.md) flipped from "open divergence, pending pivot" to **PERMANENT** with the closure receipt's "Why this is the right divergence to keep" reasoning baked in.
3. **Schema-evolution.md closure**: the "Pending OWID-conformance pivot" section is replaced by "Schema-version field stamping (permanent named divergence)" with the four-OWID-concerns table showing each concern's yen-gov-native surface; status note at the doc head updated to reflect closure.
4. **CLAUDE.md section 10 update**: anti-pattern bullet flipped from "Stamp `$schema_version` on a citizen-facing JSON data emit file" (retirement framing) to "Hand-type `$schema_version` literals in any writer" (drift-hazard framing); points at `schema_registry.schema_version()` as the canonical helper.
5. **Plan-doc archived** to `docs/archive/plans/` per the [distill-a-plan](../../how-to/distill-a-plan.md) flow with this closure stanza appended.

### What was deliberately NOT done (alternative paths preserved for future re-litigation)

- **Path B was not executed.** The scoped 5-7 PR sequence (PR-1 audit through PR-FINAL doctrine cleanup) lives in section 1 of this archived plan-doc with the full PR-by-PR scope + Tidy-First commit-split guidance. If a future session re-opens the OWID-conformance question with new constraints (e.g. citizen surface starts depending on the absence of the field, or a backend rewrite makes the per-family sweep cheaper), this plan-doc is the prebuilt execution scaffold.
- **`origin.date_accessed` was not introduced.** The 5-col `source.csv` binding contract (2026-06-11 ADR citation-ledger-5col) was preserved; the `fetched_at smear` failure mode from 2026-05-16 was not re-litigated.
- **`update_period_days` was not tightened to required.** On-disk reality is already at parity (100+ rows sampled, zero nulls); `tier_b_indicator_freshness_declared` already enforces. Doctrinal ratification can land in a separate small PR if a future ingest tries to skip the field; today's corpus does not need the gate to fire.

### Persona debate trail

PR-0 (#980) carries the full 4-persona debate (Gregor + Hans + Max + Fowler) in section 0.7 of this plan-doc + the persona attribution on each verdict. The Hans persona's "this is operator-axis metadata; citizen does not see it; OWID-conformance is not a citizen benefit here" verdict is the one the user picked.

### Durable lessons (distilled to user memory)

- **OWID-alignment doctrine is a FALLBACK, not a refactor mandate.** When the divergence is operator-axis and the citizen-axis benefit is zero, the right move is to close the divergence as permanent + name the reasoning verbatim in `docs/concepts/owid-alignment.md` (so the next session does not re-open the question). Cost: 1 PR + a doctrine update. Benefit: blocks N PRs of grammar-conformance churn from re-emerging.
- **Multi-persona debate via parallel read-only subagents** is the right shape for Level-3+ contract questions. 4 personas dispatched in parallel returned within one round, converged on scope-narrow, and the Hans persona's reasoning was the load-bearing one for the user's Path A pick. Subagent reports are preserved verbatim in session memory; the plan-doc's section 0.7 is the durable distillation.
- **CLAUDE.md section 4 "tools self-contained" is qualified**: the prohibition is on `backend/` RUNTIME modules. `yen_gov.core.schema_registry` is a metadata helper that reads `datasets/schemas/` directly; importing it from `tools/` is in scope and matches the precedent in `tools/emit_indicators_completeness_index.py`. The 3 over-strict docstring claims in `enrich_census_code_2011.py`, `gen_election_tile_layouts.py`, `lgd/snapshot.py` were updated to reflect the qualified rule.

**Status: COMPLETE.** The OWID-conformance question on `$schema_version` is closed for the foreseeable future. Next agent who hits this should read [docs/architecture/data/schema-evolution.md section Schema-version field stamping](../../architecture/data/schema-evolution.md#schema-version-field-stamping-permanent-named-divergence) + [Named divergence #5](../../concepts/owid-alignment.md#named-divergences-from-owid-with-reasons) before opening any related plan-doc.
