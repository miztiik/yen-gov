# CLAUDE.md - yen-gov Engineering Contract

**Last Updated**: 2026-06-04

Non-negotiable contract for any human or AI agent working in this repo. Derived standard: [docs/reference/documentation-structure.md](docs/reference/documentation-structure.md). When the two disagree, this file wins for yen-gov.

> Indian socio-economic + election data. Schema-first ingestion, processing, static visualization. Canonical store is long-format CSV under `datasets/data/` read by DuckDB-WASM in the browser. All indicator families (elections, fiscal, health, energy, demography, ...) are equally important; whichever family is being worked on, go depth-first before breadth.

> **DOCTRINE IN MIGRATION (2026-06-04).** The repo is executing [TODO/20260603-data-and-charting-platform-reset-plan.md](TODO/20260603-data-and-charting-platform-reset-plan.md) (Level-5, user-ratified): a rip-and-replace from Hive-partitioned Parquet to ONE format - long-format CSV under `datasets/data/` (OWID-grapher-shaped), read in-browser by DuckDB-WASM `read_csv(columns=...)`. Until that plan's chunks land, parts of THIS file still describe the old world. Reconciliation follows the plan's two-phase rule (plan section 22.7): an assertion is rewritten here once its new truth is binding regardless of code state, and carries an inline `MIGRATING (plan <chunk>)` marker where the fact only becomes true mid-rip. The binding new direction, in force for any NEW work from now:
>
> - **One format: long-format CSV.** No Parquet for tabular data. The schema contract moves to a per-file CSV column validator (name + dtype + nullability) + a typed `read_csv(columns=...)` boundary; it is NOT the storage format and it did NOT disappear (Holy Law #3 preserved). Geometry stays `.topojson` / `.geojson`.
> - **Provenance FK target is `datasets/data/entities/source.csv`** (was `datasets/taxonomy/sources.parquet`); the citation-ledger rule (one row per producer/title/vintage) is unchanged (Holy Law #9, section 12).
> - **Elections are per-election self-contained CSV** under `datasets/elections/{assembly,parliament}/...`; aggregate electoral indicators are long-format under `datasets/data/datapoints/electoral/`.
> - **The DDF brand is dropped** and `__` is banned in filenames/ids (plan 21.6 / 21.12).
> - **Glyph SVGs live in `frontend/public/icons/`** (plan 21.10).
> - **ADRs retire into their subsystem/concept docs (keep-receipts)**; no new numbered ADR files (section 9 below + plan section 9).
> - **Network-fetch code is deleted; ingest reads local TCPD / source CSV** (plan 21.4).
>
> Where this file still says Parquet, DDF, `sources.parquet`, the meadow tier, JSON-Schema-on-Parquet validators, or "frontend reads Parquet only", read it as MIGRATING per the chunk that deletes it (writers B3 PARTIAL on 2026-06-06 - 10 dead canonical seed writers + the shared writer.py path retired for the 14 X1b-deleted parquets + 9 dead per-parquet schemas + 2 dead CLI commands [s1-persons-fork + ingest-people-panel]; the legacy ECI Fetcher-using ingest stack RETIRED in B4-pt2 (2026-06-06): pt2.1 #824 stripped IcedClient + Fetcher network paths from 10 mixed iced + rbi_xlsx ingest modules; pt2.2 #826 deleted 11 network CLI commands + `pipeline/run.py` + `pipeline/reference.py`; pt2.3 #827 deleted 6 orphan source modules (`sources/eci/{statistical_report,static_catalog,urls}.py` + `sources/wikipedia/urls.py` + `sources/iced_common/client.py` + `sources/iced_power/fetch_pipeline.py`) + stripped `sources/india_geodata/power_plants.py`; pt2.4 (this PR) deleted `core/http.py` + `test_core_http.py` + `datasets/_ops/range-mime-probe.parquet` + removed `tenacity` from pyproject. The residual parquet emit paths for the surviving `election_results` / `dim_party_alliances` / `entities` / `indicators` / `boundary_layers` parquets stay until those tables retire too; reader-flip X1a / X1a-followup / YA-apply, Parquet-delete X1b - X1b retired 14 zero-reader parquets on 2026-06-06: `dim_parties` / `dim_pcs` / `dim_persons` / `dim_acs` / `elections_candidacies` + `taxonomy/ac_crosswalk` / `taxonomy/persons` / `taxonomy/sources` + 6 small taxonomy orphans `election_events` / `facet-axes` / `indicator_topic_tags` / `methodology_breaks` / `state_tiers` / `topics`; the dim_acs + elections_candidacies pair was added after YA-apply #813 flipped semantic-catalogue.ts to CSV mid-PR; residual parquets `election_results` + `dim_party_alliances` + `entities` + `indicators` + `boundary_layers` retire via a later partial-X1b pass. The `legacy/folded_indicator_writer.py` module + `core/io.write_artifact` + the `core/io.Source` dataclass + the entire `backend/yen_gov/legacy/` namespace RETIRED in B4-pt3 (2026-06-07): the 3 legacy JSON writes in `eci-statreport-emit-local` were deleted (results.csv survives as the only artifact), `canonical/adapters/eci_ae_panel.py.upsert_inventory_entries` switched to a direct `json.dumps + write_text` mirroring `eci_ls.py._upsert_inventory`, and the 6 cache-only ingest orchestrators (`cea_installed_capacity` / `datagovin_ogd` / `rbi_appendix_deficits` / `rbi_appendix_national` / `rbi_hbs_ie_centre_deficits` / `rbi_hbs_ie_state_sdp`) were narrowed to canonical CSV emit only - their `_build_*_payload` + `_write_indicator` + `_source_entries` + `_common_indicator_fields` helpers were stubbed (`raise RuntimeError(...)` markers) and their `IndicatorIngestResult.artifact_path` field renamed `csv_path` to match the new contract; tests `test_core_io.py` + `test_sources_rbi_hbs_ie_state_sdp.py` + `test_sources_rbi_hbs_ie_centre_deficits.py` deleted; `test_core_models._round_trip` rewired to in-memory `Draft202012Validator` (no disk write); 3 dead `test_ingest_<pollutant>_emits_artifact` tests in `test_sources_iced_air_quality_markers.py` marked SKIP since the `_build_<pollutant>_payload` builders they exercised are now orphan production code awaiting a follow-on cleanup commit. Net -1676 LOC.). NO agent may reintroduce a Parquet writer, a network fetcher, the DDF grammar, or a JSON projection of canonical data. Agent memory (`/memories/`) is derived, not authoritative (section 5) and self-corrects.

## 0a. The One Rule

**OWID is the canonical reference for socio-economic data modelling.** Check OWID first; adopt verbatim; document deviations in [docs/architecture/data/canonical-store.md](docs/architecture/data/canonical-store.md) signed off by Hans + Max. See [docs/concepts/owid-alignment.md](docs/concepts/owid-alignment.md).

**Doctrinal spine.** The One Rule sits inside the broader [data-spine doctrine](docs/concepts/data-spine.md) - five non-negotiables (question-first, LGD-joinable, methodology-stable, source-cited, static-served) that REPLACE the off-the-cuff "DATA - SCHEMA - SCALE - ENRICHMENT" slogan. The spine names WHY OWID is the reference (FAIR-grade comparability + cite-ability at scale); this rule names HOW to invoke it. Every new family of indicators MUST honour all five non-negotiables; see the spine doc for the pipeline-of-responsibility breakdown (acquire -> define -> shape -> store -> serve -> render).

**Authority assignment** (resolves stalled agent debates):

| Decision class | Authority |
| --- | --- |
| Data shape - column types, enums, period axis, entity IDs, indicator metadata, source schema, taxonomy | **Hans + Max** |
| Contract / integration - schema versioning, write seams, layer boundaries, pipes-and-filters topology | **Gregor** |
| Engineering craft - refactor safety, test tiers, module structure, deletion discipline | **Fowler** |
| UX - URL grammar, visual bounds, copy, gestures, citizen-readable framing | **Jony + Citizen** |
| AI / LLM app design - model selection, prompts, RAG, agent topology, evals, tokenizer/context | **Andre** |

**User approval supersedes every agent and every rule in this file.** Amend conflicting rules in the same commit.

## 0. Non-Goals

- **Accessibility (a11y / ARIA / WCAG / axe-core).** Descoped 2026-05-12. No a11y deps, assertions, agent doctrine, or `aria-*` enforcement at project level. Re-scope by editing this entry.
- **Production backend.** See Holy Law #1.

## 1. Holy Laws (Read First, Every Session)

1. **Static-first production.** Deployed app is a static bundle on GitHub Pages. No production backend. Anything the UI needs at runtime ships in the bundle.
2. **Backend = local pipeline only.** `backend/` generates datasets; MUST NOT be assumed to exist at production runtime.
3. **Contracts before logic.** Every cross-boundary payload gets a typed schema before logic is written. For tabular canonical data the contract surface is the per-file CSV column schema (name + dtype + nullability) consumed by a typed `read_csv(columns=...)` boundary. The 9 per-parquet JSON Schemas for the X1b-retired tables (`dim-acs` / `dim-pcs` / `dim-parties` / `dim-persons` / `elections-candidacies` / `ac-crosswalk` / `persons` / `person-aliases` / `source`) were deleted in B3 (2026-06-06); the surviving JSON Schemas validate either surviving parquet row shapes (`dim-party-alliances` / `entity` / `indicator-catalogue` / `observation` / `boundary-layers` / `manifest`) or surviving JSON inputs (`state-tiers` / `election-events` / `methodology-break` / `concepts` / `topic-catalogue` / etc.). MIGRATING marker for the rest of the parquet-shape schemas tracks the residual parquets (`election_results` / `dim_party_alliances` / `entities` / `indicators` / `boundary_layers`) retiring in a later partial-X1b pass.
4. **Docs = agent memory.** Every design decision, however granular, is documented in the same commit as the code. Default home: relevant subsystem doc under `docs/architecture/<area>/` or concept doc under `docs/concepts/`. ADRs retire into their subsystem/concept docs per [ADR-0034](docs/concepts/documentation-discipline.md#adr-0034-documentation-routing-contract) (folded into the routing-contract concept doc; the ADR tier itself retired 2026-06-05 per [TODO/20260603-data-and-charting-platform-reset-plan.md](TODO/20260603-data-and-charting-platform-reset-plan.md) chunk D-DOC3, with the redirect map at [docs/reference/decision-index.md](docs/reference/decision-index.md)).
5. **Structural fixes only.** No band-aids, no monkey patches, no "temporary" hacks. Escalate the correction level instead.
6. **No hardcoding.** Tunable knobs live in `config/`; reference data and generated artifacts live in `datasets/`. Both are schema-validated.
7. **No mocks unless asked.** Real implementations and real fixtures. Mocks only on explicit user request or for genuinely untestable external boundaries.
8. **Open source first.** Prefer mature OSS over custom builds.
9. **Provenance is mandatory.** Every observation row carries `source_id` FK to `datasets/data/entities/source.csv`. See section 12.
10. **Tests ship with the feature.** Behaviour-changing commit lands with tests at the appropriate tier (section 15). Full suite green at merge.

## 2. Path Rules

For anything leaving the process (JSON, logs, DB rows, emitted artifacts, agent memory, error messages, sources rows, ADR cross-links, dataset references):

- Relative paths only. No absolute paths. No drive letters. No `/home/...`.
- POSIX separators only (`/`). Never `\`.
- Minimal reconstructable form.

In-memory `Path` objects for local I/O may stay platform-native. Rule applies at the moment a path leaves the process.

**Ephemeral runtime.** `.runtime/` is ephemeral by definition. Agents MUST NOT reference `.runtime/` paths from any committed artifact. State that outlives a run belongs in `datasets/`, `config/`, or `docs/`.

## 3. Repository Topology

| Directory       | Status     | Purpose |
| --------------- | ---------- | ------- |
| `docs/`         | created    | Canonical knowledge (Diataxis tiers, 3-level depth) |
| `README.md`     | created    | Entry point |
| `CLAUDE.md`     | created    | This file |
| `datasets/`     | created    | Canonical store + schemas + reference data + upstream snapshots. Long-format CSV under `datasets/data/` per [docs/concepts/data-spine.md](docs/concepts/data-spine.md). B2b MERGED (per-family CSVs emitted across `data/datapoints/geo/` + `data/entities/` + `data/elections/{assembly,parliament}/.../candidacies.csv` + summary); X1b PARTIAL 2026-06-06 (14 zero-reader parquets retired: `elections/dim_parties` + `elections/dim_pcs` + `elections/dim_persons` + `elections/dim_acs` + `elections/elections_candidacies` + `taxonomy/ac_crosswalk` + `taxonomy/persons` + `taxonomy/sources` + 6 small taxonomy orphans; the dim_acs + elections_candidacies pair added after YA-apply #813 landed mid-PR); X1b-pt2 (2026-06-07, local commit `8ea74f24`) retired 9 more parquets in the energy + livestock families: `energy/{energy_installed_capacity, energy_generation, energy_demand_supply, energy_distribution_performance, energy_fuel_consumption, energy_capacity_pipeline}.parquet` + `livestock/{livestock_pashu_aadhaar, livestock_owner_registration, livestock_naip_iv}.parquet` + 57 backend-internal `_meadow/` scratch files + `datasets/livestock/AGENTS.md` family-map doc, plus the matching writer chain (`backend/yen_gov/canonical/adapters/{energy,livestock}/` packages, the reingest modules, the lift-energy + lift-livestock CLI commands, and 2 inspector tools); the FE reader for these 9 families flipped to per-indicator CSV under `datasets/data/datapoints/geo/<canonical_id>.csv` via R2 (2026-06-07, local commit `96275ab6`); the residual parquets (MIGRATING per a later partial-X1b pass) are now 5 (DOWN from 14 pre-X1b-pt2): `election_results` (sharded by state), `dim_party_alliances`, `entities`, `indicators`, `boundary_layers`. Sole writer: `backend/`. See [docs/architecture/data/canonical-store.md](docs/architecture/data/canonical-store.md). |
| `datasets/_ops/`| created    | Operator state; not citizen-facing, not inventoried. See [datasets/_ops/README.md](datasets/_ops/README.md). |
| `config/`       | created    | Human-edited tunable knobs. After G9 (2026-06-08) the only file is [config/topojson.json](config/topojson.json) (mapshaper quantization + simplification knobs read by [tools/topojson/convert_layer.py](tools/topojson/convert_layer.py)); its schema lives at [datasets/schemas/topojson-config.schema.json](datasets/schemas/topojson-config.schema.json). The 3 other configs (`eci-pins.json` + `elections.json` + `processing.json`) and their schemas were retired as orphan tunables - all readers were either dead post-B4 (`sources/eci/categories.py`, the Composer architecture) or had a single 2-knob consumer (cli `eci-statreport-emit-local`) that inlined the constants. |
| `backend/`      | created    | Local Python pipeline. FastAPI admin wrapper at `backend/yen_gov/admin/`. |
| `frontend/`     | created    | Static GitHub Pages app (Svelte 5 + Vite 6 + Tailwind + d3 + maplibre-gl). Never commits data files. |
| `admin/`        | created    | Dev-only Svelte app on port 5174. Never deployed publicly. |
| `tools/`        | created    | Standalone dev/ops tooling. No `backend/` imports. |
| `.runtime/`     | gitignored | Ephemeral run state. Never a contract surface. |
| `TODO/`         | optional   | Working scratchpads - non-authoritative. Sole working-docs home; `notes/` was retired 2026-06-08 per [TODO/20260603-data-and-charting-platform-reset-plan.md](TODO/20260603-data-and-charting-platform-reset-plan.md) override O10 (durable content lifted into `docs/`, in-flight handover folded into the relevant TODO/ sub-plan). |

Create folders only when real code is about to land. Identifier convention: use issuing-authority IDs (ISO 3166, ECI codes, LGD codes); see [docs/reference/identifiers.md](docs/reference/identifiers.md).

## 4. Layer and Dependency Rules

- `frontend/` MUST NOT import from `backend/`.
- `frontend/` MUST NOT commit data files. Dev: Vite middleware `serveDatasets()` in [frontend/vite.config.ts](frontend/vite.config.ts) serves `datasets/` under `/data/`. Deploy: workflow copies `datasets/` into `_site/data/`. See [docs/architecture/frontend/data-loading.md](docs/architecture/frontend/data-loading.md).
- `backend/` MUST NOT include UI/DOM logic.
- `backend/` is the only writer to `datasets/`; readers treat it as a contract surface.
- Cross-runtime sharing is via data contracts under `datasets/`, never code imports.
- `tools/` MUST NOT import `backend/` runtime modules.
- Domain/core code MUST NOT import adapters/infrastructure (adapters -> core, never reverse).
- `datasets/<family>/_meadow/...` is the backend-internal meadow tier. Frontend MUST NOT fetch under `_meadow/`. See [ADR-0041](docs/architecture/data/canonical-store.md#adr-0041-meadow-tier) + [docs/concepts/meadow-tier.md](docs/concepts/meadow-tier.md). (MIGRATING: the meadow tier retires as the local-CSV reingest lands per plan chunk B4.)

## 5. Documentation Discipline

- Diataxis tiers under `docs/`: `architecture/`, `how-to/`, `concepts/`, `reference/` (+ `getting-started/`, `archive/`, `research/`, `agents/`).
- Max depth: `docs/<tier>/<topic>/<file>.md`.
- Every doc: H1 title, `Last Updated: YYYY-MM-DD`, "See also" cross-links.
- One concept defined once; everywhere else links to it.
- ASCII-only in all repo text: commit messages, docs, code comments, log strings, agent markdown, CLI output (use `-`, `->`, `>=`, "section", "INR"). No curly quotes, em-dashes, or non-ASCII symbols. Applies going forward; no retroactive fixing.
- **Doc-class routing:** ADR / subsystem doc / concept doc / plan-doc - each has one valid home. See [ADR-0034](docs/concepts/documentation-discipline.md#adr-0034-documentation-routing-contract).
- **Plan-doc distillation:** When a plan-doc row closes, durable findings are lifted into the right `docs/` home per [docs/how-to/distill-a-plan.md](docs/how-to/distill-a-plan.md). The plan-doc itself stays as a thin audit ledger with back-pointers. Agent-only execution lessons (gotchas, tool quirks, recurring traps) go to `/memories/lessons.md`, not `docs/`.
- Agent memory (`AGENTS.md`, `/memories/repo/`) is derived, not authoritative; if it disagrees with `docs/`, docs win.
- Personas live under `docs/agents/`; each loads [docs/agents/bootstrap.md](docs/agents/bootstrap.md) before answering. New citizen-facing features follow [docs/how-to/distill.md](docs/how-to/distill.md). Doctrine: [docs/concepts/citizen-first.md](docs/concepts/citizen-first.md).
- Open questions live in the active plan-doc under `TODO/`, not in this file.
- Docs-only PRs are a code smell.

## 6. Correction Levels

| Level | Scope | Workflow |
| :---: | --- | --- |
|  0 | Comments, typos, log strings | Direct fix |
|  1 | 1 file, ~50 lines, isolated bug | Direct fix |
|  2 | 1-2 files, explicit behavior change | Plan -> execute once scope is clear |
|  3 | 2-3 files, cross-cutting | Plan -> phased execution |
|  4 | 4+ files, structural | Propose breakdown first |
|  5 | Core design / data model / runtime | Design consultation only - pause work |

When in doubt, choose the higher level.

## 7. Debug Logging

- Temporary logs MUST be prefixed `[DEBUG]`.
- Before finalizing: grep for `[DEBUG]` and remove every match. Re-run tests after cleanup.

## 8. Git Hygiene

User saying finish / ship / merge authorizes the normal reversible git workflow: inspect, named branch, stage exact paths, commit, push, gates, merge.

Avoid (broad / lossy / history-rewriting):

- `git stash`
- `git reset --hard`
- `git clean -fd`
- `git checkout .` / broad `git restore .`
- `git add .` / `git add -A`
- `git push --force` / `git push --force-with-lease`
- Amending pushed commits
- Leaving a merged PR's remote branch undeleted or its `: gone]` local tracking branches unpruned. Run post-merge cleanup per [docs/how-to/ship-a-pr.md](docs/how-to/ship-a-pr.md). The cosmetic `gh pr merge` error when any worktree holds `main` is expected; the manual `git push origin --delete <branch>` follow-up is mandatory, not optional.

Safe workflow: `git status --porcelain`, leave unrelated dirty files alone, stage only explicit paths, verify with `git diff --cached --name-only`, small reversible commits on a named branch, push, merge after gates pass.

Commit messages describe the change. **No AI co-author / attribution tags.**

## 9. Definition of Done

- [ ] Tests added/updated at the tier appropriate to the surface (section 15). No mocks per Holy Law #7.
- [ ] Full suite green locally before commit (`npm test` in `frontend/`, `npm run test:e2e` if frontend runtime changed, `pytest -q` in `backend/`).
- [ ] Lint, type-check, schema validation, tests all pass.
- [ ] For `frontend/` or `admin/` runtime changes: smoke-tested via integrated browser tools per section 13.
- [ ] Canonical docs updated in `docs/` (right tier).
- [ ] Schemas bumped/migrated if any persisted contract changed.
- [ ] Every new/changed observation row carries `source_id` FK (section 12).
- [ ] Module `AGENTS.md` updated if structure or invariants changed.
- [ ] No `[DEBUG]` markers left.
- [ ] No new hardcoded values.
- [ ] No source or instruction the user named explicitly was downgraded, substituted, or scope-narrowed without a Scope-change ledger row carrying a non-empty `signoff:` in the active plan-doc (section 10 STOP-AND-SURFACE).
- [ ] No new mocks unless explicitly requested.
- [ ] Lockfiles in sync with manifests. If commit touches `frontend/package.json` or `admin/package.json`, regenerate the matching `bun.lock` and stage in the SAME commit. The Pages workflow runs `bun install --frozen-lockfile` and will reject any desync.
- [ ] Post-merge cleanup run per [docs/how-to/ship-a-pr.md](docs/how-to/ship-a-pr.md) section Post-merge cleanup (merge verified, remote branch deleted, `: gone` local branches pruned, `.tmp_*` removed, durable lessons distilled per [docs/how-to/distill-a-plan.md](docs/how-to/distill-a-plan.md)).

## 10. Anti-Patterns (Do NOT)

- Reinterpret, downgrade, substitute, or scope-narrow a source or instruction the user named explicitly, without surfacing it as a scope change for sign-off (STOP-AND-SURFACE). An explicit user-named artifact may NOT be silently demoted - e.g. "ingest X" quietly becoming "X is crosswalk / fallback only" inside baked-facts or any other low-visibility ledger. Disposition of a user-named source is a contract change requiring an explicit STOP plus user sign-off (section 0a), NOT agent-internal ambiguity resolution. When you hit this: set the plan-doc row `BLOCKED-NEEDS-SIGNOFF`, write a Scope-change ledger row (verbatim instruction | proposed change | reason | `signoff:`) in the active plan-doc, and stop. See [docs/how-to/handle-scope-change.md](docs/how-to/handle-scope-change.md).
- Assume a backend exists in production.
- Hardcode taxonomy values, version numbers, magic strings.
- Store absolute / backslash paths in any persisted artifact.
- Build custom HTTP / retry / parsing / validation when an OSS library exists.
- Swallow exceptions or silently coerce invalid input - fail fast at the boundary.
- Mock in tests by default.
- Use `datetime.now()` in data-row content (observation provenance, indicator vintage, citizen-facing footers). Wall-clock at write time is operational telemetry, not provenance. Carve-out: control-plane artifacts (`datasets/manifest.json`, `.runtime/logs/`) MAY stamp `generated_at`. See [docs/concepts/data-provenance.md](docs/concepts/data-provenance.md) and [ADR-0032](docs/concepts/data-provenance.md#adr-0032-sources-citation-ledger).
- Propose `write_text_if_changed`-style byte-compare helpers at write seams. Fix non-determinism upstream of the write seam.
- Re-litigate the sources-table design (domain-as-identity, drop-the-table, add-`content_hash`-back, require-`citation_full`). See [ADR-0032](docs/concepts/data-provenance.md#adr-0032-rejected-alternatives) Rejected A/B/C/D.
- Walk the real on-disk corpus from a `pytest` test or live HTTP smoke test. That is Tier-B (section 11), local-only via `python -m yen_gov validate --root .`. Inject root via env var, use `tmp_path` fixtures in tests. See [docs/architecture/backend/validator.md](docs/architecture/backend/validator.md).
- Emit JSON projections of canonical data for the citizen frontend. Frontend reads long-format CSV via DuckDB-WASM `read_csv(columns=...)` for the X1a-flipped surfaces (dim_parties via `data/entities/parties.csv`; sources via `data/entities/source.csv`; election candidacies/summary via per-(state,year) CSV; ac_crosswalk via `data/entities/ac_crosswalk.csv` per X1a-followup #811; yenask semantic-catalogue startup via `data/entities/electoral.csv` + `taxonomy/election_events.json` per YA-apply #813) AND the X1b-retired tables (dim_persons + dim_pcs + dim_acs + elections_candidacies + taxonomy/persons + 6 small taxonomy orphans) AND the X1b-pt2-retired energy + livestock families (per-indicator CSV at `data/datapoints/geo/<canonical_id>.csv`; 127 `csv_path` declarations on `frontend/src/lib/canonical/indicator-allowlist.ts` cover 43 single + 84 facet child descriptors per R2 commit `96275ab6` 2026-06-07). Residual parquet reads pending a later partial-X1b pass: `election_results` (3 aggregators), `dim_party_alliances` (no CSV emit), `boundary_layers`, `entities`, `indicators`.
- Run CI that processes `datasets/**`. Publish is plain static-file copy; CI gates are lint, type-check, pytest, frontend build, Playwright only.
- Use broad / lossy / history-rewriting git commands (section 8).
- Let `TODO/`, chat logs, `AGENTS.md`, or `/memories/` become the source of truth for architecture.
- Pre-create empty modules "for later".
- Skip the docs update.
- Edit `package.json` without running `bun install` and staging the resulting `bun.lock` in the same commit.
- Create new files under `datasets/indicators/in/<topic>/<id>.json`. That path is retiring per [ADR-0041](docs/architecture/data/canonical-store.md#adr-0041-meadow-tier). New backend-internal parsed rows go to `datasets/<family>/_meadow/<source>/<vintage>/<file>.json`; citizen-facing canonical data goes to `datasets/<family>/<family>_<role>.parquet`. Enforced by Tier-B; see [docs/architecture/backend/validator.md](docs/architecture/backend/validator.md).
- Author `id_aliases[]` on `datasets/taxonomy/indicators.json` without a paired `deprecated_in: "YYYY-MM-DD"`. Enforced by Tier-B `tier_b_indicator_alias_window` (60-day window); see [datasets/schemas/indicator-catalogue.schema.json](datasets/schemas/indicator-catalogue.schema.json) v1.1.
- Encode topic membership as a prefix on `indicator_id`. The id is `<measure>-<unit>-<facet>` kebab-case (grain comes from the row's `entity_kind`, not the id — see [ADR-0044](docs/concepts/indicator-naming.md#adr-0044-grain-over-entity)); topic membership lives on M:N rows in `datasets/taxonomy/indicator_topic_tags.parquet`. See [docs/concepts/indicator-naming.md](docs/concepts/indicator-naming.md).
- Prefix `state-` / `district-` / `national-` on `indicator_id`. Grain lives on each observation row's `entity_kind` and is dispatched at read time. The id is `<measure>-<unit>-<facet>` only. See [ADR-0044](docs/concepts/indicator-naming.md#adr-0044-grain-over-entity). Enforced by Tier-B `tier_b_indicator_id_no_grain_prefix` (ships dark in PR-B1, enforces post-PR-B9).
- Add UI/render fields (`chart_type`, `default_mode`, `renderer_rules`, `facet_labels`, `dimension`) to `indicator-catalogue.schema.json` or `topic-catalogue.schema.json`. Render hints live in the grapher catalogue at `datasets/grapher/indicator_render.json` + `topic_render.json`, owned by the frontend per [ADR-0045](docs/architecture/data/indicator-catalogue.md#adr-0045-grapher-catalogue-split).
- Add facet/grain-fanout cards to a topic page (e.g. separate cards per species / fuel / facet for the same measure). One card per measure; the facet picker lives inside the card. Enforced by [frontend/src/contracts/topic-card-uniqueness.test.ts](frontend/src/contracts/topic-card-uniqueness.test.ts) (live as of PR #411, which collapsed `/t/agriculture` from 16 cards to 7). See [docs/concepts/schema-is-the-design-system.md](docs/concepts/schema-is-the-design-system.md) "one card per measure" rule.
- Mint a new `indicator_id` for a new vintage, new publisher, new base-year, or new sampling-frame of an existing fact. New vintage = UPSERT same id (writer PK is `(entity_id, year, period_label, indicator_id)`). New publisher of an existing fact = UPSERT or facet, never mint. Base-year rebase / definition shift = SAME id + new `methodology_breaks.parquet` row (Rosling rule). See OWID-precedent doctrine in [docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md](docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md) §0quint.
- Skip the pre-ingest overlap check before adding any new ingest. Every new-source handover-doc MUST cite `python -m yen_gov check-overlap --concept "<noun>" --unit "<u>" --entity_kind "<k>"` (ships PR-Z3). If overlap >= 70%, the action is UPSERT into the existing indicator or add a facet — NOT mint a new id.
- Land a new ingest without a green pre-flight report cited in the handover-doc. Run `python -m yen_gov pre-flight-ingest --proposal-file ./proposal.json --report ./report.json` (ADR-0046); cite both paths in the handover-doc §3. Exit code 2 = abort; no override flag (Holy Law #5). The gate batches the six mechanical checks (concept overlap, concept FK, grain prefix, update_period_days, justification, source_id derivation) so no future agent has to re-discover them PR-by-PR.
- Author a plan-doc that touches indicator ids or catalogue fields without citing [ADR-0044](docs/concepts/indicator-naming.md#adr-0044-grain-over-entity) + [ADR-0045](docs/architecture/data/indicator-catalogue.md#adr-0045-grapher-catalogue-split) in its preamble. Reviewers enforce.
- Land an indicator-catalogue row without declaring `update_period_days` (publisher refresh cadence in days: NDLM monthly = 30, RBI Handbook annual = 365, Census decennial = 3650). Staleness can only be surfaced when cadence is named. OWID precedent: every Grapher variable carries this. Enforced post-PR-Z3b by Tier-B `tier_b_indicator_freshness_declared`; see [docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md](docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md) §0quat guardrail #18.
- Mint a new `indicator_id` without an FK to a row in `datasets/taxonomy/concepts.json` declaring `(noun, unit_canonical, normalisation, entity_kinds)`. Identity is what is MEASURED, not who published it. Run `python -m yen_gov check-overlap` (ships PR-Z3b) before authoring any new catalogue row; if a concept match >=70% exists, UPSERT into the existing indicator or add a facet. Enforced post-PR-Z3b by Tier-B `tier_b_one_indicator_per_concept`; see plan-doc §0quat guardrail #13.

## 11. Schema Versioning

Every JSON Schema under `datasets/schemas/` carries:

- `$schema`: `https://json-schema.org/draft/2020-12/schema`
- `$id`: relative path (`./<name>.schema.json`). Local `$id` only.
- `title`, `description`.
- `x-version`: `"<major>.<minor>"` only.
- `x-changelog`: non-empty array, oldest first; last entry's `version` MUST equal `x-version`.

Bump rules:

- **Minor** (`1.0` -> `1.1`): purely additive, backwards-compatible.
- **Major** (`1.x` -> `2.0`): removed/renamed field, type change, narrowed constraint, semantic shift.
- Every bump adds a new `x-changelog` entry in the same commit.
- **Code never hand-types schema-version literals.** Source via `yen_gov.core.schema_registry.schema_version("<file>")` / `schema_id("<file>")`.

Every emitted data file under `datasets/` carries `"$schema"` and `"$schema_version"`. Validation has two tiers (Tier A always-on in `pytest -q`; Tier B on-demand local via `python -m yen_gov validate --root .`). See [docs/architecture/backend/validator.md](docs/architecture/backend/validator.md).

Schema-version compatibility follows [ADR-0047](docs/architecture/data/schema-evolution.md#adr-0047-schema-version-compatibility-contract) and [docs/architecture/data/schema-evolution.md](docs/architecture/data/schema-evolution.md): writers are strict, readers are compatible only by explicit contract. A writer MUST emit the current schema version. A reader or validator MAY accept an older declared version only when the compatibility contract says it can interpret that version without guessing. Old major versions require retained schemas, an explicit translator, migration, or fail-loud rejection. Until a reader/validator implements the compatibility contract, it MUST keep rejecting non-current versions.

The reader compatibility contract lives in `datasets/schema-compatibility.json`. Schema-release history and the public receipt for `schema changed, values did not` live in `datasets/schema-evolution.json`; retained historical schemas live under `datasets/schemas/archive/<schema-stem>/v<major>.<minor>/<schema-file>`. Do not overload `datasets/migration-ledger.csv` for schema-release metadata.

## 12. Data Provenance

Every observation row in every long-format CSV family under `datasets/data/` (and every `datasets/elections/**` row) carries a `source_id` FK to one row in `datasets/data/entities/source.csv`. Provenance is a **citation ledger**, one row per `(producer, title, vintage)` triple, not per fetch event. Adopts OWID `origin.*` fields verbatim plus four yen-gov extensions for confidence + verifiability.

Schema (11 columns, 8 required + 3 optional): [docs/architecture/data/canonical-store.md section 5](docs/architecture/data/canonical-store.md). Rationale + rejected designs: [ADR-0032](docs/concepts/data-provenance.md#adr-0032-sources-citation-ledger). v3.0 `vintage` sharpening (publisher edition vs operator snapshot window): [ADR-0042](docs/concepts/data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor). Concept: [docs/concepts/data-provenance.md](docs/concepts/data-provenance.md).

Build `source_id` via `backend.yen_gov.canonical.citation.derive_source_id`; never hand-author.

## 13. UI Verification (Frontend / Admin)

Any change touching `frontend/` or `admin/` runtime MUST be verified by the agent using integrated browser tools, not deferred to the human.

Minimum loop:

1. Confirm dev server up (`http://localhost:5173/` frontend, `http://localhost:5174/` admin); start if not.
2. `open_browser_page` / `navigate_page` to affected route(s) plus one cross-route smoke.
3. `read_page` and confirm: (a) new copy/structure renders, (b) no new `[error]` console events, (c) no new `404`.
4. If layout-sensitive: `screenshot_page` to confirm visual intent.
5. Only then mark done.

Does not apply to pure backend / pipeline / docs / schema-only changes.

## 14. Test Coverage Policy

Four tiers - **Unit / Contract / Integration / End-to-end**. Change without appropriate-tier test in same commit is a Definition-of-Done failure. Mock carve-outs: (a) `fetch` in loader unit tests, (b) explicit user request. No pytest test walks the real corpus; use `tmp_path` fixtures injected via env var.

Per-tier matrix, commands, fixture conventions: [docs/architecture/testing.md](docs/architecture/testing.md).
