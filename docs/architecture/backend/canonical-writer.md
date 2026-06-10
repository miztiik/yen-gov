# Canonical CSV writer + validator (`yen_gov.canonical.csv_writer` + `csv_validator`)

**Last Updated**: 2026-06-06

The canonical CSV writer is the sole entry point that persists observation rows into the long-format CSV store under `datasets/data/` (and `datasets/elections/**`). It is the write seam referenced by Holy Law #2 ("backend is the only writer to `datasets/`") and the contract surface every re-pointed ingest (B1.4-B1.6 waves) funnels through, replacing the historical `core/io.write_artifact` meadow-tier path.

Distilled from sub-plan B1 (sub-rows B1.1..B1.7, PRs #629-B1.7-closure) on 2026-06-04.

> The legacy Parquet writer at `backend/yen_gov/canonical/writer.py` (see [writer.md](writer.md)) survives in-tree until grandparent chunk B3 deletes it. Until then both writers coexist; new ingest re-points emit CSV via `csv_writer.write_csv`, never via the legacy `core/io.write_artifact` path.

## Purpose

- Emit one row per observation into the canonical long-format CSV files under `datasets/data/datapoints/<class>/<variable_id>.csv` and per-election `datasets/elections/{assembly,parliament}/state=<key>/election=<id>/{candidacies,summary}.csv` per [csv-column-contract.md](../data/csv-column-contract.md).
- Enforce the per-file-class column contract (`datasets/data/_schema/columns.json`) at write time: header order, dtype, nullability, deterministic sort, `__` ban, UTF-8 + LF + trailing newline + no BOM.
- Enforce cross-file integrity at read time: FK existence (`source_id` to `entities/source.csv` per Holy Law #9; `concept_id` to `concepts.csv` per ADR-0044 one-indicator-per-concept; `entity_id` to declared entity file), closed-enum membership, datapoint-filename equals `<variable_id>.csv`.
- Preserve the skip-write-if-equal optimisation from `core/io.write_artifact` (value-level row-list compare) so re-running ingest leaves a clean `git status`.

## Three-module surface

| Module | Role | Public API |
| --- | --- | --- |
| `yen_gov.canonical.csv_columns` (B1.1, PR #629) | Loads + caches the column contract from `datasets/data/_schema/columns.json`; validates the contract itself against `_schema/columns.schema.json` (D6 escape-hatch retained per the column contract escape-hatch rule). | `load_columns()`, `file_class_for(path)` |
| `yen_gov.canonical.csv_writer` (B1.2, PR #631) | Sole CSV emission point. Strict on shape (header, dtype, nullability, sort, filename `__` ban). | `write_csv(*, path, file_class, rows) -> Path` |
| `yen_gov.canonical.csv_validator` (B1.3, PR #633) | Read-time cross-file integrity check. Strict on FK + closed-enum + sort + filename-equals-variable_id. No mocks (Holy Law #7); caller owns `repo_root` so fixtures stage under `tmp_path` (CLAUDE.md anti-pattern: validators MUST NOT walk the real on-disk corpus from pytest). | `validate_csv(*, path, file_class, repo_root) -> None` |

Division of labour: the writer is strict on per-row shape; the validator is strict on cross-file integrity. Anything that needs sibling-file presence (FK targets, datapoint-filename-equals-id) lives in the validator because the writer cannot assume sibling files exist yet during a partial re-ingest.

## Contract invariants enforced

Inherited from CLAUDE.md Holy Laws #3, #6, #9:

1. **Provenance FK mandatory.** Every datapoint + candidacy row carries `source_id` -> `datasets/data/entities/source.csv` (validator-enforced).
2. **One-indicator-per-concept.** Each `variable_id` in `variables.csv` binds to one `concept_id` -> `concepts.csv` (validator-enforced FK).
3. **LGD/ECI key separation preserved.** The writer never invents a shared parent; election rows key on ECI codes per existing parser output, observation rows key on LGD ids per the entity file declared by the file class.
4. **Schema-per-file typed.** Callers pass `file_class` explicitly; there is no `read_csv_auto` round-trip. The writer is the strict half of the same typed-read contract F1 codegen will materialise on the frontend.
5. **Static-first deterministic read.** Rows sorted by the file class's PK columns in declaration order; no `datetime.now` in content columns; UTF-8 + LF + trailing newline + no BOM.
6. **Double-underscore ban.** Filenames containing `__` are rejected at write time (CLAUDE.md section 10 anti-pattern).

## Re-point pattern for ingest callers

The B1.4-B1.6 waves re-pointed ~17 surviving `core/io.write_artifact` call-sites onto `csv_writer.write_csv`. The uniform shape for any future re-point:

1. Identify the canonical CSV file class the meadow JSON corresponds to (see [csv-column-contract.md section 3](../data/csv-column-contract.md)).
2. Build rows as `list[dict]` keyed by the declared columns; derive `source_id` via `backend.yen_gov.canonical.citation.derive_source_id` (never hand-author).
3. Call `write_csv(path=datapoints/<class>/<variable_id>.csv, file_class=..., rows=...)`.
4. During the B1 window the legacy `write_artifact` call MAY stay in place alongside the new CSV emit (whichever keeps the per-family gate green); deletion is deferred to grandparent chunk B3. Record the alongside choice in the sub-row's PR body.

**Alongside-NEITHER carve-out.** When a `write_artifact` site emits operator state (e.g. `datasets/elections/_inventory.json`) or a per-election shape that is one of N inputs to a downstream aggregator (B2a-owned: `entities/*.csv`, per-election `candidacies.csv` / `summary.csv`), no canonical CSV file class fits. Leave the legacy call in place, record the rationale in the sub-row PR body + sub-plan addendum, and pass `docs-review` instead of `writer-unit` + `suite-green`. Precedents: B1.6.4 (#664), B1.6.5 (#666), B1.6.6 (#668), B1.6.7 (#669) - all four alongside-NEITHER under sub-plan B1.6, all emit operator inventory or downstream-aggregator shapes.

## Seed emitters (B2a, PRs #673-#688)

Sub-plan B2a (PRs #673-#688) delivered eight one-shot emitters under `backend/yen_gov/canonical/seed/` that lift the existing taxonomy artifacts under `datasets/taxonomy/` into the canonical CSV catalogue rows every downstream reader (B2b datapoint reingest, F1 frontend loaders, YA yen-ask grounding) joins against. Each emitter reads ONE taxonomy artifact and writes ONE CSV file class via `csv_writer.write_csv`; the validator (`csv_validator.validate_csv`) enforces FK + enum + sort across the emitted files.

| Emitter module | Reads | Emits | File class | PR |
| --- | --- | --- | --- | --- |
| `seed/source_csv.py` | `datasets/taxonomy/sources.parquet` | `datasets/data/entities/source.csv` | `entities/source.csv` (5 cols; 6 legacy cols dropped per plan section 7) | #673 |
| `seed/topics_csv.py` | `datasets/taxonomy/topics.json` | `datasets/data/topics.csv` | `topics.csv` (parent-pointer tree; pillars are roots) | #675 |
| `seed/concepts_csv.py` | `datasets/taxonomy/concepts.json` | `datasets/data/concepts.csv` | `concepts.csv` (F6 one-per-concept identity) | #677 |
| `seed/variables_csv.py` | `datasets/taxonomy/indicators.json` | `datasets/data/variables.csv` | `variables.csv` (FKs to source + topics + concepts; 11 cols incl. 3 yen-ask grounding columns nullable in B2a) | #680 |
| `seed/geo_csv.py` | `datasets/taxonomy/lgd_states.json` + `lgd_districts.json` | `datasets/data/entities/geo.csv` | `entities/geo.csv` (country -> state -> district ladder; `aliases` pipe-delimited) | #678 |
| `seed/electoral_csv.py` | `datasets/taxonomy/lgd_acs.json` + `lgd_pcs.json` | `datasets/data/entities/electoral.csv` | `entities/electoral.csv` (FK `state` -> geo; AC parent is PC of same `delim_year`) | #682 |
| `seed/electoral_lgd_xwalk_csv.py` | `datasets/taxonomy/lgd_ac_pc_district_map.json` | `datasets/data/entities/electoral_lgd_xwalk.csv` | `entities/electoral_lgd_xwalk.csv` (composite PK; `boundary_snapshot` carries the decay receipt per plan section 20.5) | #684 |
| `seed/party_csv.py` | `datasets/taxonomy/parties.json` | `datasets/data/entities/parties.csv` | `entities/parties.csv` (`party_id` sole canonical key per plan section 20.3; `eci_codes` is descriptive, not a join key) | #686 |

Each emitter is paired with `backend/tests/test_seed_<name>_csv.py` covering: deterministic sort, FK existence under the file class's predecessor (geo before electoral, source + topics + concepts before variables), enum membership, and `__` ban. A sibling `_run_<name>_csv.py` shim per emitter is the operator-facing runner invoked when refreshing the catalogue.

### Identity-derivation forks resolved

- **`source_id`** is re-derived inside `seed/source_csv.py` via `canonical.citation.derive_source_id` (chicken-and-egg seed path); downstream callers (B2b reingest) MUST use `citation.lookup_source_id` against the emitted CSV, never re-derive.
- **`topic.parent`** is a self-FK; emit order sorts parents-before-children so the validator passes without a deferred-FK pass.
- **`variables.concept_id`** binds to `concepts.csv` per ADR-0044 one-indicator-per-concept; `check-overlap` may be re-run as a post-emit audit (see canonical-writer `## Re-point pattern` for the binding rule on B2b ingest).
- **`variables.time_min` / `time_max` / `entity_kinds`** are nullable at B2a (no datapoints yet) and back-filled by B2b reingest.
- **`electoral.parent`** uses AC -> PC-of-same-delim_year, PC -> state; the LGD/ECI key separation invariant (#3 above) means `entities/electoral.csv` carries NO district FK - the only meeting point is `entities/electoral_lgd_xwalk.csv`.

### Parquet sibling lifecycle

Each emitter targets a CSV under `datasets/data/`; the legacy parquet sibling under `datasets/taxonomy/` survives until grandparent chunk X1b deletes it. During the B2a -> X1a -> X1b window both formats coexist; new readers MUST consume the CSV, never the parquet.

## Taxonomy datapoint reingest (B2b.4, PRs #698-#708 + DROP #774)

Sub-plan B2b.4 (PRs #698-#708 + DROP #774) delivered six emitters lifting the datapoint-shape parquets B2a left behind (election_events, facet_axes, state_tiers, indicator_topic_tags, methodology_breaks, ac_crosswalk) into long-format CSV siblings under `datasets/data/`. The seventh planned row (`entities/person.csv` from `persons.parquet`) was DROPPED per converged Fowler+Hans persona-debate verdict (PR #774): the audit-only parquet has zero frontend consumers, biographic `dim_persons` cols migrate inline via B2b.5.x candidacies, and the cross-format-parity gate is N/A for an unconsumed parquet. Per-row emit map:

| Source parquet | Emitter | Writes | PR | Notes |
| --- | --- | --- | --- | --- |
| `taxonomy/methodology_breaks.parquet` | `reingest/methodology_breaks.py` | `datasets/data/methodology_breaks.csv` | #698 | 5 rows; F6 reference; verbatim project (PK `methodology_version + at_year + at_period_seq`) |
| `taxonomy/facet-axes.parquet` | `reingest/facet_axes.py` | `datasets/data/facet_axes.csv` | #700 | 127 rows; reference; filename loses hyphen per plan 21.6 |
| `taxonomy/state_tiers.parquet` | `reingest/state_tiers.py` | `datasets/data/state_tiers.csv` | #702 | 104 rows; ECI `state_code` -> LGD state_entity_id re-key; FK -> `entities/geo.csv` |
| `taxonomy/election_events.parquet` | `reingest/election_events.py` | `datasets/data/election_events.csv` | #704 | 339 rows; ECI `state_code` -> LGD re-key as state_tiers |
| `taxonomy/indicator_topic_tags.parquet` | `reingest/indicator_topic_tags.py` | `datasets/data/indicator_topic_tags.csv` | #706 | 45 rows; M:N; FK `topic_id` -> `topics.csv`; FK `artifact_id` -> `variables.csv` when `artifact_kind='indicator'` |
| `taxonomy/ac_crosswalk.parquet` | `reingest/ac_crosswalk.py` | `datasets/data/entities/ac_crosswalk.csv` | #708 | 4113 rows; ECI no -> LGD AC id mapping; FK `state_entity_id` + `source_id` |
| `taxonomy/persons.parquet` | DROPPED via PR #774 | n/a | #774 | Audit-only registry (7 cols: `person_id, display_name, source_id, confidence_tier, evidence_note_md, cluster_id, merged_candidacy_count`); zero frontend consumers verified via grep; biographic `dim_persons` cols (`sex, age, education, profession`) live on a SEPARATE parquet under `datasets/elections/dim_persons.parquet` and migrate INLINE to per-election `candidacies.csv` via B2b.5.x #768-#772; cross-format-parity N/A for unconsumed parquet; X1b deletion-safety statement = this audit trail + sub-plan section 0 + grep receipt |

Binding doctrine (shared by all six emitted CSVs): each emitter projects the parquet verbatim where possible; the only re-keys are `state_code` (ECI S/U code) -> LGD `state_entity_id` (for state_tiers, election_events, ac_crosswalk via `lgd_states.json`); `source_id` rows already exist in `entities/source.csv` for rows that carry it (lifted by B2a); no `datetime.now` in content columns. Each parity gate `backend/tests/test_csv_parquet_parity.py::test_<name>` reads BOTH real on-disk parquet + new CSV, asserts identical row count + typed per-cell equality, skips cleanly if either absent (Holy Law #7). The DROP of persons.parquet is recorded in section 0 of the archived sub-plan with the converged Fowler+Hans verdict and a Scope-change ledger row carrying user-kickoff signoff.

## Elections datapoint reingest (B2b.5, PRs #762-772)

Sub-plan B2b.5 (PRs #762-772) delivered the elections clean-start: an LGD-spine reset (PR-stages 0a-0e) plus the two Tier-R result axes (assembly + parliament). The spine is sourced from a committed LGD parsed snapshot under `datasets/data/entities/lgd/` (relocated from `datasets/reference/lgd/` by G8-finish 2026-06-08, plan section 9); the results are re-parsed from the local TCPD compilations in `datasets/ephemeral/` (never the surviving parquet). Per-row emit map:

| Source (ephemeral, INPUT-only) | Emitter | Writes | Key shape |
| --- | --- | --- | --- |
| `All_Stateof_India_*.csv` (LGD) | `seed/state_codes_csv.py` (0b) | `entities/state_codes.csv` | `lgd_state_id` PK; `iso_3166_2` seeded; `eci_st_code` DROPPED; census as two dated LABEL columns |
| LGD snapshot `constituencies.csv` | `seed/electoral_csv_from_snapshot.py` (0c-2) | `entities/electoral.csv` | `IN-{AC,PC}-2008-<state-slug>-<lgd_code>`; `eci_no` folded DIRECT from the PRI ECI-code column |
| LGD snapshot `constituency_district_membership.csv` | `seed/electoral_district_membership_csv.py` (0c-2) | `entities/electoral_district_membership.csv` | `(electoral_id, lgd_district_id)`; `is_primary` = plurality district |
| `datasets/taxonomy/parties.json` | `seed/party_csv.py` (0c-3 rename) | `entities/parties.csv` | `party_id` PK (renamed from `party.csv`) |
| `All_States_AE.csv` (TCPD assembly) | `reingest/assembly_results.py` (5.2 pilot + 5.3 fan-out) | `elections/assembly/state=<slug>/election=<yr>/{candidacies,summary}.csv` | candidate-grain; `entity_id` binds AC on `(state, eci_no)`; `summary == recompute(candidacies)` |
| `All_States_GE.csv` (TCPD parliament) | `reingest/parliament_results.py` (5.4) | `elections/parliament/election=<yr>/{candidacies,summary}.csv` | country-wide; MANDATORY `state` column (pc_no restarts per state); PC bind |

Binding doctrine (shared by both result axes): only the in-force 2008 delimitation (TCPD `DelimID` 4) is emitted, because its `Constituency_No` numbering is the one bound to `electoral.csv`; NOTA is excluded from candidacies (a ballot option, not a candidate, but its votes stay in the AC/PC-level turnout); `party_id` is null at v1 (the TCPD-internal `Party_ID` has no crosswalk into `parties.csv`); an unbindable constituency (state-reorganisation artefact or the small LGD-spine gap, e.g. Delhi which has no `electoral.csv` constituencies) is SKIPPED and surfaced in a per-stage coverage receipt under `datasets/_ops/`, never fabricated. The summary's `winner_share_pct` + runner-up + margin columns are nullable to admit an uncontested (single-candidate, unopposed) seat. `recompute_summary_row` is shared (imported by the parliament emitter) so the parity oracle `summary == recompute(candidacies)` holds identically on both axes. Each TCPD endpoint mints ONE `source_id` via `derive_source_id` (scalar per producer+endpoint+snapshot per ADR-0042 / OWID one-origin-per-snapshot), not one per year. Coverage reconciliation of the new CSV tree (`coverage.py`) is deferred to the F1 reader-flip (it is assembly/AC + legacy-parquet today); see [coverage.md](coverage.md).

## Parity oracle (F1.1 - 2026-06-06, distilled in F1.4)

`backend/tests/test_canonical_parity_oracle.py` is the post-CSV-cutover gate that pins per-AC FPTP winner against the frozen ground truth in `backend/tests/fixtures/canonical_winners_2026_05_19.json`. F1.1 (PR #791) flipped the SQL from a 4-way `read_parquet(...)` JOIN (`election_results.parquet` x `elections_candidacies.parquet` x `dim_persons.parquet` x `dim_acs.parquet`) to a per-(state, year) scan against:

```text
datasets/elections/assembly/state=<lgd-slug>/election=<yyyy>/candidacies.csv
```

The reader is a typed `read_csv(columns={...})` matching the `candidacies.csv` header shipped by B2b.5.x (17 columns including `entity_id`, `state`, `election_year`, `constituency_no`, `candidate_name`, `party_id`, `votes`, `vote_share_pct`, `position`, `result`, biographics, `candidate_type`, `source_id`). Sub-plan F1 (PR #791, distilled in F1.4).

### Path A backfill (mash from TCPD + parquet + LGD-spine)

The user verdict on the fixture-vs-CSV drift surfaced by the initial rewrite was **A: backfill**, not relax the assertion. `tools/elections/backfill_from_legacy.py` extends `datasets/data/entities/electoral.csv` with synthetic gap-fill rows (entity_id pattern `IN-AC-2008-<state-slug>-eci<N>`; name lifted from `dim_acs.parquet`; reservation lifted from TCPD `Constituency_Type`) and then re-runs `assembly_results.emit_state_assembly()` per affected state. The previously-unbindable ACs bind via the now-complete electoral.csv FK lookup and ship as full candidacies + summary rows. The mashed CSV is the canonical source of truth from PR #791 onward; the fixture was re-anchored on TCPD-derived winners and re-keyed from `<event_id>/<eci_state_code>` (e.g. `AcGenApr2016/S03`) to `<event_id>/<lgd_state_slug>` (`AcGenApr2016/assam`) so the 22-entry ECI st_code map dropped out of the test entirely.

### Fixture invariants

- **Fixture key shape**: `<event_id>/<lgd_state_slug>` (e.g. `AcGenApr2016/assam`); winners is `{ac_eci_no: {name, party_short, votes}}`.
- **Per-AC assertion**: ZERO tolerance. Max-votes candidate's `candidate_name` + `votes` + derived `party_short` must match the fixture byte-exact. NOTA is excluded by construction because `candidacies.csv` carries only registered candidates (NOTA totals live in `summary.csv`).
- **Floor 34 -> 35** (`MIN_SLICES_FOR_NON_SKIP`): the post-Path-A corpus has 35 of the 41 fixture slices on disk; the floor rose from 34 once the Delhi 2020 slice was recovered via the LGD-spine extension.
- **6 residue slices** in `_KNOWN_ABSENT_SLICES`: 5 AcGenMay2026/* (assam, kerala, tamil-nadu, west-bengal, puducherry - TCPD AE compilation vintage 2026-06-05 does not yet carry the 2026 assembly cycle) + 1 AcGenNov2023/rajasthan (TCPD AE compilation stops at 2021 for Rajasthan). These are documented genuine upstream gaps, not regressions.

### Gates

- `test_oracle_non_skip_gate` (CLAUDE.md section 22.6 `oracle-non-skip`): hard FAILS if the per-slice run-set drops below 35. This is the false-green guard for the post-X1b world - a blanket `skipif csv absent` skip would mask a real deletion regression.
- 35 `test_per_ac_fptp_winner_matches_fixture[<event_id>-<state_slug>]` parametrize cases: one per on-disk slice; together with the gate this is 36/36 pass byte-exact.

Holy Law #7: the oracle reads the REAL on-disk CSV + a checked-in real-data fixture - no mocks. The Path A backfill tool (`tools/elections/backfill_from_legacy.py`) is committed for provenance + reproducibility per the `tools/` convention.

## Test surfaces

| Test | What it pins |
| --- | --- |
| `backend/tests/test_csv_writer.py` | Happy-path emit, dtype coercion, sort determinism, `__` rejection, null vs empty-string distinction, skip-write-if-equal. |
| `backend/tests/test_csv_validator.py` | FK miss, enum miss, sort drift, `__` rejection, missing `source_id`. `tmp_path` fixtures only - never walks the real corpus. |
| Per-family `test_<source>_csv_repoint.py` (one per B1.4-B1.6 wave PR) | Row-builder helper + `write_csv` round-trip for that source's file class. |
| `backend/tests/test_seed_<name>_csv.py` (one per B2a emitter) | Deterministic sort, FK existence under predecessor file class, enum membership, `__` ban. |

## Known follow-ups deliberately deferred

These surfaced during B1 execution and are recorded here so future agents do not re-discover them:

- **Per-indicator facet columns** (column contract, CLAUDE.md section 10). Writer + validator both reject undeclared columns today. Both surfaces will relax together when the first facet ingest needs it.
- **Wall-clock-in-content-columns detector** (CLAUDE.md section 10 anti-pattern). A defensible detector needs a content-column taxonomy that `columns.json` does not yet carry. Land alongside the first ingest that would benefit.
- **Null-vs-empty-string distinction for string columns** (writer module docstring notes this). B1.2 emits `None` as the empty CSV field uniformly; a richer encoding will land if a downstream consumer needs to distinguish.
- **Parquet writer + `core/io.write_artifact` deletion.** Both survive in-tree until grandparent chunk B3. New code MUST NOT call either; the import-allowlist pattern from PR-SYM-6f is the model for B3's enforcement test.

## See also

- [../data/csv-column-contract.md](../data/csv-column-contract.md) - the binding column spec (D-DOC0, PR #627).
- Sub-plan B1 (PRs #629-B1.7-closure) delivered this writer + validator.
- Sub-plan B1.4 (PRs #634-#644) - wave 1 (iced_*) per-family re-point precedent.
- Sub-plan B1.5 (PRs #645-#656) - wave 2 (rbi_*) precedent.
- Sub-plan B1.6 (PRs #657-#669) - wave 3 (misc) including four alongside-NEITHER carve-outs.
- Sub-plan B2a (PRs #673-#686) - the eight seed emitters.
- Sub-plan B2b.5 (PRs #762-#772) - elections clean-start.
- [writer.md](writer.md) - legacy Parquet writer (survives until grandparent chunk B3).
- [ADR-0032](../decisions/0032-sources-citation-ledger.md) - `source_id` FK requirement.
- [ADR-0042](../decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) - `vintage` semantics for `derive_source_id`.
- [ADR-0044](../decisions/0044-grain-over-entity.md) - one-indicator-per-concept, no grain prefix on `variable_id`.
- [CLAUDE.md](../../../CLAUDE.md) Holy Laws #3, #6, #7, #9; sections 9 (DoD), 12 (provenance).
