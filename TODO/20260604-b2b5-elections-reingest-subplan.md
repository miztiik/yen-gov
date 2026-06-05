# B2b.5 sub-sub-plan - elections-from-local-TCPD per-election CSV reingest

**Last Updated**: 2026-06-04
**Parent**: [TODO/20260604-b2b-reingest-subplan.md](20260604-b2b-reingest-subplan.md) row B2b.5
**Grandparent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk B2b
**Status**: UNBLOCKED 2026-06-05 (user-ratified resolution in section 0b; LGD-native PK kept, `eci_no` folded as a column, clean-start rip-and-replace). NEW prerequisite row B2b.5.0 (clean-start re-emit) added; B2b.5.2..B2b.5.5 flip from `BLOCKED-NEEDS-SIGNOFF` to `TODO (blocks on B2b.5.0)`. B2b.5.1 MERGED (#711); B2b.5.Z TODO. Resolution + signed scope-change ledger in section 0b.
**Authority**: Hans + Max (per-election shape, identity, candidacy vs summary columns) / Gregor (FK contract, per-election self-containment, parity gate, parliament `state` mandatory column per 23.4) per CLAUDE.md section 0a

---

## section 0a Data-audit finding (2026-06-04; PR #713) - STOP-AND-SURFACE

Pre-flight audit of the TN slice before emitting B2b.5.2 found a structural FK rot: the `entity_id` the emitter would derive from the parquet does not resolve in the canonical `datasets/data/entities/electoral.csv` it must FK to. This is the same class of bug surfaced by the 2026-06-03 audit chain (`/memories/lessons.md`: "Field name parity does not imply scheme parity") and by the B2b.4.7 person reingest blocker (`/memories/session/b2b-4-7-blocker.md`).

### What I measured

Reproducible via `mcp_provides_tool_pylanceRunCodeSnippet` against the on-disk corpus on 2026-06-04:

- `datasets/elections/dim_acs.parquet.lgd_ac_id` for `state_code='S22' AND delim_year=2008`: range `33001..33234`, 234 rows (233 distinct populated). Encoding: `state_code * 1000 + eci_no`.
- `datasets/data/entities/electoral.csv` trailing-int suffix of `entity_id` for `state='tamil-nadu' AND entity_kind='ac'`: range `3857..4090`, 232 rows. Encoding: `lgd_acs.json.lgd_ac_id` (LGD constituency-register sequential-per-state id).
- **Overlap of the two sets: 0** (verified `SELECT ... INTERSECT ...` returns zero rows).
- Andhra Pradesh (S01): parquet `28120..28294` vs csv `3166..3438`. Same disjoint shape (175 rows each side, 0 overlap).
- Parliament has the equivalent collision: parquet `dim_pcs.pc_no` for TN is per-state-restart (`1..39`), `entities/electoral.csv` PC suffix for `tamil-nadu` is sequential-national (`503..541`).

### Root cause

The repo holds TWO numbering schemes both labelled "LGD AC id":

1. **`state_code * 1000 + eci_no`** (synthetic, ECI-derived): used by `datasets/taxonomy/ac_crosswalk.parquet.lgd_ac_id`, `datasets/elections/dim_acs.parquet.lgd_ac_id`, and the AC boundary feature `AC_ID` property. Harvested by `tools/migrate/build_ac_crosswalk.py` (EciToAcid migration Row A2; see [TODO/20260530-eci-to-lgd-acid-migration-plan.md](20260530-eci-to-lgd-acid-migration-plan.md)). The `match_method='lgd_direct'` label on those rows is misleading - the value is synthetic, not a real LGD register id.
2. **LGD constituency-register sequential-per-state** (authoritative, LGD-derived): only in `datasets/taxonomy/lgd_acs.json.lgd_ac_id` (TN 3857..4090, AP 3166..3438). Lifted verbatim into `entities/electoral.csv` by B2a.6 (`backend/yen_gov/canonical/seed/electoral_csv.py`) per the seed's docstring: `IN-AC-<delim_year>-<state-slug>-<lgd_ac_id>`.

There is no existing ECI-no -> LGD-register crosswalk on disk. `ac_crosswalk.parquet` is named promisingly but only binds `(state_code, eci_no) -> synthetic state*1000+eci_no` - it does NOT bind to the LGD-register sequential id. A real bind would need name-cleaning across ~4000 ACs (the parquet has `GUMMIDIPUNDI` at S22 eci_no=1; lgd_acs.json has `Gummidipoondi` at lgd_ac_id=4062 - same constituency, transliteration drift).

### Why this blocks B2b.5.2 / 5.3 / 5.4 / 5.5

The candidacies file class declares `entity_id` as non-nullable FK to `entities/electoral.csv.entity_id` (see `datasets/data/_schema/columns.json` lines 140-159). `backend/yen_gov/canonical/csv_validator.py._check_fks` enforces this strictly: every non-null value must exist in the target file. There is no soft-FK option (correctly so per CLAUDE.md Holy Law #9). If B2b.5.2 emits using the parquet's `lgd_ac_id`, 100% of TN rows fail FK validation. Re-keying onto `(state_code, eci_no)` does not help either - `entities/electoral.csv` carries neither column. The same blocker propagates to B2b.5.3 (assembly fan-out across the other 35 states), B2b.5.4 (parliament; PC has the same collision), and B2b.5.5 (source-ledger backfill rides the emit rows that surface gaps).

### Four resolution paths (Hans + Max authority per CLAUDE.md section 0a)

- **A) Build a real ECI-no -> LGD-register crosswalk** by name-clean + position match + delim-2008 anchor, lift into a new `entities/electoral_eci_xwalk.csv`. Multi-day operator project across ~4000 ACs (transliteration ambiguity, J&K U08 already known-unmapped per EciToAcid Row C1's 253 still-`unmapped` count). Becomes a new sub-plan blocking B2b.5.x. Preserves the LGD-native entity_id shape `entities/electoral.csv` already commits to.
- **B) Re-key `entities/electoral.csv` to the ECI-native scheme** (`IN-AC-2008-S22-1`), re-emit via a B2a.6 successor. Breaks every existing consumer of the LGD-native id (frontend SQL, `entities/electoral_lgd_xwalk.csv` PK at 253 rows, boundary join). Directly contradicts B2a.6's rationale which cites `lgd_acs.json`'s `$comment` that "ECI ac_no is NOT carried here" and chose the LGD-native shape deliberately.
- **C) Extend `entities/electoral.csv` to carry BOTH schemes** (or partition by delim_year and accept pre-2008 = ECI-only). Schema change to the canonical entity catalogue. Doubles the row count and complicates downstream consumers that today assume one row per (state, delim, ac).
- **D) Scope-fence B2b.5.x to DEFERRED-NEEDS-CROSSWALK** until the EciToAcid migration plan ships the real-LGD bind (D1 row in [TODO/20260530-eci-to-lgd-acid-migration-plan.md](20260530-eci-to-lgd-acid-migration-plan.md), currently DEFERRED per the same blocker surfaced this audit). The rest of the grandparent reset plan (D-DOC1/2/3, U1..U5, F2*..F4, YA, E1..E6 except E5 which blocks on X1b) is unblocked.

Recommendation (NOT a decision): D. The EciToAcid migration plan already owns this problem; B2b.5 should wait on it rather than re-litigate the LGD-numbering choice inside the elections sub-sub-plan. The agent will NOT autonomously pick a path - this requires Hans + Max sign-off (CLAUDE.md section 0a).

### Scope-change ledger (per [docs/how-to/handle-scope-change.md](../docs/how-to/handle-scope-change.md))

| Verbatim user instruction | Proposed change | Reason | `signoff:` |
| --- | --- | --- | --- |
| "Take B2b.5.2 (TN assembly pilot): emit `datasets/elections/assembly/state=tamil-nadu/election=YYYY/candidacies.csv` + `summary.csv` from existing TN parquet partition." | Flip B2b.5.2 / B2b.5.3 / B2b.5.4 / B2b.5.5 row Status to `BLOCKED-NEEDS-SIGNOFF` until the user picks A / B / C / D in section 0a above. B2b.5.1 stays MERGED. B2b.5.Z stays TODO. | Pre-flight audit found 100% FK rot between parquet's `lgd_ac_id` and `entities/electoral.csv.entity_id` suffix (TN: 233 vs 232, overlap 0; AP: 175 vs 175, overlap 0; PC same shape). FK is non-negotiable per Holy Law #9. The LGD-numbering choice is a Hans + Max decision per CLAUDE.md section 0a, not an executor decision. | SIGNED 2026-06-05 (user, data-shape authority with Hans + Max): resolve via section 0b below - keep LGD-native PK, fold `eci_no` as a column, add `aliases`, clean-start rip-and-replace, emit `state_codes.csv`, rename to `electoral_district_membership.csv` + `parties.csv`. Overrides the section-0a recommendation D. |

---

## section 0b RESOLUTION (2026-06-05; user-ratified per CLAUDE.md section 0a) - LGD-native, fold eci_no, clean-start

The user (data-shape authority with Hans + Max) ran the Jony/Max/Hans/Fowler debate and RATIFIED the consensus, overriding the section-0a recommendation D (defer). This UNBLOCKS B2b.5. Binding decisions:

1. **LGD is the canonical spine.** `entities/geo.csv` (LGD admin ladder) binds every indicator and entity. Electoral entities KEEP their LGD-register-native `entity_id` (the `lgd_ac_id`/`lgd_pc_id` B2a.6 already emits, e.g. TN AC suffix 3857..4090) so they join the LGD spine. Path B (re-key to ECI-native) is REJECTED.
2. **No arithmetic surrogate ids, anywhere.** The `state_code*1000+eci_no` scheme (synthetic `lgd_ac_id` 33001.., 28120..) is the bug, not a key - it is DELETED, not carried. Ids are natural authority-issued numbers (LGD register id, ECI ballot serial) joined by `-`, never computed.
3. **Fold `eci_no` as a column on `entities/electoral.csv`; DELETE `ac_crosswalk`.** `eci_no` is the natural ECI ballot serial (1..N per state per delim) that candidacies carry; it is 1:1 with the AC so it folds (Fowler cardinality rule). `datasets/data/entities/ac_crosswalk.csv` + the `datasets/taxonomy/ac_crosswalk.parquet` synthetic bridge are ripped.
4. **Add an `aliases` column** (pipe-delimited) to `entities/electoral.csv` AND `entities/geo.csv` for name/transliteration/old-name variants (`Gummidipoondi|GUMMIDIPUNDI`). Powers the eci_no bind AND yen-ask grounding (grandparent section 20.10).
5. **Candidacies resolve `entity_id` at emit time** via `(state, delim_year, eci_no) -> entity_id` lookup into `entities/electoral.csv`. The validator stays single-column FK (Holy Law #9); resolution happens in the emitter, not the validator.
6. **Re-source + rename the AC/PC -> district 1:many.** LGD itself asserts an AC can span districts (the LGD Constituency-Coverage HTML exports `parlimentConstituencyAndAssemblyConstituency*.htm` + `assembly_parliament_constituency*.htm` carry the AC<->district coverage edges), so the relation is LGD-canonical, NOT a geometry artifact. Parse those exports to `entities/electoral_district_membership.csv` (renamed from `electoral_lgd_xwalk.csv`), columns `electoral_id, lgd_district_id, is_primary, lgd_snapshot, source_id`. This RESOLVES the enum drift (drops the fuzzy `{primary|partial}` vs on-disk `{wholly_inside|partial}`; replaced by a clean `is_primary` boolean + row-existence membership).
7. **One-place state-code map.** Parse `entities/state_codes.csv` from the ephemeral `allStateofIndia*.htm` (LGD state code + name + census code). The ECI `st_code` (S22/U08) + ISO 3166-2 are NOT in the LGD export - carry them as a small committed, re-verified ECI/ISO mapping (NOT the corrupted `lgd_states.json`); flag for Hans + Max. This is the single LGD<->ECI<->ISO<->census lookup the bind, the results emit, and yen-ask all read.
8. **delim_year is the time-travel axis** (no `valid_from`/`valid_to` intervals). A state split (AP -> Telangana 2014) = a methodology-break receipt + the LGD vintage, NEVER a relabel of history. predecessor/successor lineage columns are DEFERRED (add one nullable column only if a real "what became of X" query appears - see grandparent appendix Round 7).
9. **`parties.csv`** (plural filename; user override of the singular `entities/` convention).
10. **Clean-start / rip-and-replace is MANDATORY, sourced from the fresh ephemeral LGD HTML.** SOURCE OF TRUTH = the LGD portal HTML exports the operator freshly downloaded into `datasets/ephemeral/` on 2026-06-05 (`allStateofIndia*.htm`, `allDistrictofIndia*.htm`, `allSubDistrictofIndia*.htm`, `assembly_parliament_constituency*.htm`, `parlimentConstituencyAndAssemblyConstituency*.htm`). A committed parser (B2b.5.0) converts each HTML table to CSV; the clean-start emits every `entities/*.csv` from THOSE parsed tables. DELETE every conflicting artifact (`ac_crosswalk.*`, the synthetic `dim_acs.lgd_ac_id`, the old `electoral_lgd_xwalk.csv`); treat the existing `datasets/taxonomy/*.json` as DERIVED/CORRUPTED - overridden, never read as source (kept at most for an optional cross-check diff). TCPD CSV remains the source for election RESULTS. Git is the backup.

### eci_no bind (the one curation step; Hans + Max authority)
The operator has downloaded the LGD Assembly + Parliamentary Constituency HTML exports (`assembly_parliament_constituency*.htm`) into `datasets/ephemeral/`. The bind `(state, delim_year, eci_no) -> lgd_ac_id` is built once: PREFER a direct join if that export carries BOTH the LGD constituency id AND the ECI/delimitation constituency number; ELSE name+alias match within `(state, delim_year)` using the new `aliases` column to absorb transliteration drift. Unmatched ACs (e.g. J&K U08) stay null and are listed in the B2b.5.0 PR body, never silently dropped.

New prerequisite row **B2b.5.0** below carries this; B2b.5.2..5.5 now block on B2b.5.0 (not on signoff).

---

## Why this exists

Parent sub-plan row B2b.5 reads as one line but expands into a per-election reingest across the full corpus the surviving parquet family currently holds, plus a separate parliament axis. Per CLAUDE.md correction-level discipline (>=4 files structural -> propose breakdown first) and parent plan section 24.5, this becomes a sub-sub-plan rather than one mega-PR. The spawn pattern mirrors B2a + B2b.4.

The parent B2b sub-plan's B2b.5 row stays `DEFERRED-TO-SUBPLAN` with a forward-pointer to this file until B2b.5.Z (closure) merges, at which point B2b.5 flips to `MERGED` with the closure PR# stamped.

## Corpus audit (2026-06-04, on-disk)

- `datasets/elections/state=<lgd-slug>/election_results.parquet` x 36 state directories (one file per state, aggregates all years for that state; sample TN = 10.35 MB).
- `datasets/elections/elections_candidacies.parquet` (root; all states + all years + parliament + assembly mixed; 14.9 MB).
- Root dimensions (B2a-style; entity-mirrored already): `dim_acs`, `dim_parties`, `dim_party_alliances`, `dim_pcs`, `dim_persons` (12.7 MB).
- Total: 42 parquet files, ~161.6 MB.
- Parliament partition: NOT a separate directory; PC rows are mixed inside `elections_candidacies.parquet`, discriminated by `entity_id` prefix (`IN-PC-...` vs `IN-AC-...`).
- 36 state dirs (35 states + UTs incl. Lakshadweep) MATCHES the LGD slug set; one `state=<slug>` directory per polity that has held an assembly election.
- Local TCPD inputs survive at the pure-parser layer: `backend/yen_gov/sources/eci/{constituencywise,partywise,people_panel,ls_constituencywise,ls_ge_tcpd,statistical_report,statistical_report_detailed,section3}.py`. The URL-builder layer (`urls.py`) is deleted under chunk B4 per plan section 21.4; B2b.5 emitters MUST NOT import `urls.py` or `core/http.Fetcher` (any reference is a B4-blocking regression).

## Target layout (mandatory, per plan sections 21.3 + 23.4)

```
datasets/elections/
  assembly/state=<lgd-slug>/election=<year>/
    candidacies.csv   # candidate-grain
    summary.csv       # constituency-grain; DERIVED projection of candidacies (F7)
  parliament/election=<year>/
    candidacies.csv   # country-wide; MUST carry `state` column (23.4)
    summary.csv       # one row per PC; entity_id = IN-PC-<delim>-<state>-<pc_no>
```

Per-election self-contained: no across-years AC file. Cross-year reads glob `assembly/state=<slug>/election=*/summary.csv` at read time (F1's job).

## Scope

In scope: per-election emitter that reads the surviving parquet (or, equivalently, re-parses the local TCPD CSV behind it - decision per family per row) and writes the four target CSV file classes (`assembly_candidacies`, `assembly_summary`, `parliament_candidacies`, `parliament_summary`) against the column contracts declared in `datasets/data/_schema/columns.json` (extended in B2b.5.1). Every emitted row carries `source_id` resolvable in `entities/source.csv` (Holy Law #9; for any TCPD release vintage missing a source row, append via the same SAME-PR rule used by B2a.1 - mint via `derive_source_id`, do not hand-author).

Cross-format parity gate runs per family. Parity oracle subset (`canonical_winners_2026_05_19.json` + `summary == recompute(candidacies)`) runs per row that emits parliament or assembly summary files. The full F1 rewrite of `test_canonical_parity_oracle.py` does not block here; this sub-sub-plan only needs the winner+margin invariants asserted from the new CSV path per the rows that touch them.

Out of scope (other rows / chunks):

- B2a entity / catalogue emits (dim_*): MERGED in #688 (B2a.5/B2a.6/B2a.8 covered persons, parties, electoral entities). Dim parquets stay on disk until X1b deletes them; this row does NOT re-emit them.
- Reader flip (X1a) + parquet delete (X1b): writer-only here; parquet survives until X1b.
- F1 oracle full rewrite (the 4 hardcoded parquet paths -> CSV with glob): a separate chunk on the parent ledger; this sub-sub-plan only ships the per-row parity subset.
- Network-fetch deletion + `core/http.Fetcher` removal + `cli.py` `with Fetcher(...)` rewrite: chunk B4 territory per plan section 23.1.

## EL7 - coverage.py disposition (resolved here, per plan section 23.4)

`backend/yen_gov/coverage.py` is assembly-only today. Per plan section 23.4, this sub-sub-plan MUST resolve the AC-vs-PC disposition before parliament data emits in B2b.5.4. Decision recorded in row B2b.5.4's PR body: EITHER extend `coverage.py` to discriminate (extra row class + per-class aggregations) OR scope-fence it to assembly with a doc note + a tracking row on a follow-up chunk. The PR that emits parliament CSV cannot land without this decision noted in its body; reviewers enforce. An aggregator silently blind to a whole election class is a latent reporting bug.

## Sub-sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| B2b.5.1 column contract: extend `datasets/data/_schema/columns.json` with four new file_class entries (`elections/assembly/state=*/election=*/candidacies.csv`, `.../summary.csv`, `elections/parliament/election=*/candidacies.csv`, `.../summary.csv`) + write-time validator passthrough (FK targets: `entity_id` -> `entities/electoral.csv` projection; `party_id` -> `dim_parties`-mirrored future `entities/party.csv` or current ledger row; `source_id` -> `entities/source.csv`); update `backend/yen_gov/canonical/reingest/` scaffolding. Audit-finding: the four file_class entries landed in PR #629 (B1.1) ahead of schedule, so the columns.json delta in this row is zero; the in-scope delta is (a) per-file-class writer + validator roundtrip unit tests proving passthrough for all four globs, and (b) shared scaffolding module `backend/yen_gov/canonical/reingest/elections.py` exposing the FILE_CLASS constants + path-builder helpers that B2b.5.2..5.4 emitters import. | - | docs-review + fk-validator-dry-run | #711 | MERGED |
| B2b.5.0 clean-start re-emit (NEW prerequisite; section 0b): FIRST write a committed HTML->CSV parser (`tools/` or `backend/yen_gov/ingest/`) that converts the ephemeral LGD HTML exports (`datasets/ephemeral/all{State,District,SubDistrict}ofIndia*.htm`, `assembly_parliament_constituency*.htm`, `parlimentConstituencyAndAssemblyConstituency*.htm`) to CSV - these are the SOURCE OF TRUTH (existing `taxonomy/*.json` treated as corrupted/overridden). THEN emit `entities/electoral.csv` with `eci_no` + `aliases` (LGD-native PK, no arithmetic ids); `entities/state_codes.csv` (LGD<->ECI<->ISO<->census; ECI/ISO from the re-verified mapping, not the corrupted json); `entities/electoral_district_membership.csv` (`is_primary` bool - resolves enum drift); DELETE `ac_crosswalk.csv` + the synthetic `state_code*1000+eci_no` scheme; rename `party.csv` -> `parties.csv`. eci_no bind = curation step (Hans+Max; prefer direct join if the LGD AC export carries the ECI no, else name+alias match within (state, delim)). | B2b.5.1 | fk-validator + eci-bind-coverage + html-parse-receipt | - | TODO |
| B2b.5.2 assembly per-state pilot: emit `assembly/state=tamil-nadu/election=<yr>/{candidacies,summary}.csv` for ALL TN years held in `state=tamil-nadu/election_results.parquet` + `elections_candidacies.parquet` (TN-scoped slice); cross-format-parity + parity-oracle-CSV (winner+margin invariants only) on this slice | B2b.5.0 | cross-format-parity + parity-oracle-CSV | - | TODO (blocks on B2b.5.0; resolved section 0b) |
| B2b.5.3 assembly fan-out: replay the B2b.5.2 emitter across the remaining 35 `state=<slug>/` directories; one PR per parallel-safe wave (~6-10 states per wave by file-size; orchestrator picks wave membership; each wave is ITSELF a sub-sub-sub-row that may spawn its own plan if a wave exceeds one PR's reviewable surface) | B2b.5.2 | cross-format-parity per state | - | TODO (blocks on B2b.5.2; resolved section 0b) |
| B2b.5.4 parliament: emit `parliament/election=<year>/{candidacies,summary}.csv` for every LS cycle held in `elections_candidacies.parquet` (1957..2024, ~18 cycles; PC rows discriminated by `entity_id` prefix). MANDATORY `state` column on the parliament file per plan section 23.4. EL7 `coverage.py` disposition resolved in this PR's body | B2b.5.0 | cross-format-parity + parity-oracle-CSV | - | TODO (blocks on B2b.5.0; resolved section 0b) |
| B2b.5.5 source ledger backfill (only if B2b.5.2 / B2b.5.3 / B2b.5.4 surface any TCPD release vintage absent from `entities/source.csv`): append rows via `derive_source_id`; SAME-PR with the emit row that surfaced the gap (do NOT defer; per B2a.1 precedent) | (folded inline into the emit row that triggers it) | fk-validator | - | TODO (folds inline into B2b.5.2 / .3 / .4; resolved section 0b) |
| B2b.5.Z close sub-sub-plan: flip parent B2b.5 row to MERGED + stamp closure PR + distil per-row emit map into [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md) "Datapoint reingest" section "Elections" subsection + archive this file to `docs/archive/plans/` | B2b.5.1..B2b.5.4 | docs-review | - | TODO |

Parallel-safe groups:

- Wave 0 (single, ships first): B2b.5.1 (column contract is FK target for every subsequent row).
- Wave 1 (after Wave 0): B2b.5.2 (TN pilot establishes assembly emitter shape).
- Wave 2 (after Wave 1; parallel-safe across states because each `state=<slug>/` writes a disjoint sub-tree): B2b.5.3 fan-out. B2b.5.4 parliament MAY also start at Wave 2 (no shared write target with assembly).
- Wave 3 closure: B2b.5.Z.

If any single wave inside B2b.5.3 exceeds one reviewable PR (>~10 states or >~500 changed lines outside the CSV emits themselves), that wave spawns its OWN sub-plan per parent 24.5 and the parent row here flips to `DEFERRED-TO-SUBPLAN`. The orchestrator decides at audit-time; the spawn shape MUST mirror this file's structure.

## Contract invariants (inherited from parent 22.4 + sub-plan invariants)

1. Provenance FK mandatory: every emitted candidacy / summary row carries `source_id` resolvable in `entities/source.csv` (Holy Law #9). For TCPD-sourced rows, `source_id` derives from the TCPD release vintage via `derive_source_id`; backfill rows ship in the SAME PR as the emit that surfaced the gap (B2b.5.5).
2. Per-election self-contained: every `assembly/state=<slug>/election=<year>/` and `parliament/election=<year>/` directory is independently readable; no across-years AC file (per plan section 21.3).
3. Parliament rows carry `state` as a MANDATORY column (per plan section 23.4; without it, `constituency_no` is non-unique within the file since it restarts per state).
4. `summary == recompute(candidacies)` per directory (F7-computed: winner = argmax votes ex-NOTA, margin = winner - runner-up, turnout if present). Asserted by parity-oracle-CSV subset on B2b.5.2 / B2b.5.3 / B2b.5.4.
5. No `__` in any emitted filename or directory (per plan section 21.6).
6. No `datetime.now` in content columns (CLAUDE.md anti-pattern). Wall-clock at write time is operational telemetry only.
7. Deterministic sort + stable CSV serialisation: same input -> identical bytes.
8. No network: emitters import ONLY the local-parser layer of `backend/yen_gov/sources/eci/` (the 8 pure-parser modules listed in the audit above) OR re-read the surviving parquet directly via DuckDB. Any import of `urls.py` / `core/http.Fetcher` is a B4-blocking regression - reviewers enforce.
9. No mocks: parity tests read REAL parquet + REAL CSV from disk (Holy Law #7); the gate skips cleanly only if a family is absent on this machine.

## Tracking

The parent B2b sub-plan's Execution Ledger row B2b.5 is `DEFERRED-TO-SUBPLAN -> TODO/20260604-b2b5-elections-reingest-subplan.md` in the SAME PR that lands this sub-sub-plan. Sub-sub-row status updates land inside each B2b.5.x PR per parent 24.3.

## See also

- Parent sub-plan: [TODO/20260604-b2b-reingest-subplan.md](20260604-b2b-reingest-subplan.md) row B2b.5.
- Grandparent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) (sections 21.3, 21.4, 21.6, 22.4, 22.5, 22.6, 23.1, 23.3, 23.4, 23.7, 24.5).
- B2b.4 sub-sub-plan precedent (taxonomy datapoint reingest): [TODO/20260604-b2b4-taxonomy-subplan.md](20260604-b2b4-taxonomy-subplan.md).
- B2a sub-plan precedent: [docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md](../docs/archive/plans/20260604-b2a-csv-catalogue-subplan.md).
- B1 sub-plan precedent: [docs/archive/plans/20260604-b1-csv-writer-subplan.md](../docs/archive/plans/20260604-b1-csv-writer-subplan.md).
- Canonical writer doc: [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md).
- Sub-plan spawning rule: grandparent section 24.5.
