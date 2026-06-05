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
7. **State identity = LGD spine; NO ECI state code (superseded + sharpened in round-8 section 0d).** State identity is `lgd_state_id` (PK, LGD-issued) + `lgd_name` + `iso_3166_2` (ISO-issued, transcribed) + `kind` + `slug`. There is NO authoritative ECI state/UT code registry (web-verified 2026-06-05: ECI publishes none; its result exports key on state NAME; `S22`/`U08` came from an in-repo Wikipedia join, are absent from the result files, and renumber on reorganization), so `eci_st_code` is DROPPED from the spine. The LGD State HTML/XLS export gives lgd code + name + kind; `iso_3166_2` is a tiny committed transcription seed (issuing authority = ISO). Census codes, former names, and any ECI code are carried as inline columns on `state_codes.csv` (round-8c: census as two dated columns `census_2001_code`/`census_2011_code` + a pipe `aliases` column; NO `state_aliases.csv` - see section 0d), never an exact-match key. Results join on state NAME -> LGD, never on a numeric ECI code.
8. **delim_year is the time-travel axis** (no `valid_from`/`valid_to` intervals). A state split (AP -> Telangana 2014) = a methodology-break receipt + the LGD vintage, NEVER a relabel of history. predecessor/successor lineage columns are DEFERRED (add one nullable column only if a real "what became of X" query appears - see grandparent appendix Round 7).
9. **`parties.csv`** (plural filename; user override of the singular `entities/` convention).
10. **Clean-start / rip-and-replace is MANDATORY, sourced from the fresh ephemeral LGD HTML.** SOURCE OF TRUTH = the LGD portal HTML exports the operator freshly downloaded into `datasets/ephemeral/` on 2026-06-05 (`allStateofIndia*.htm`, `allDistrictofIndia*.htm`, `allSubDistrictofIndia*.htm`, `assembly_parliament_constituency*.htm`, `parlimentConstituencyAndAssemblyConstituency*.htm`). A committed parser (B2b.5.0) converts each HTML table to CSV; the clean-start emits every `entities/*.csv` from THOSE parsed tables. DELETE every conflicting artifact (`ac_crosswalk.*`, the synthetic `dim_acs.lgd_ac_id`, the old `electoral_lgd_xwalk.csv`); treat the existing `datasets/taxonomy/*.json` as DISTRUSTED IN-REPO DERIVATIONS (the LGD portal data was never corrupt - see section 0c.2) - overridden by the new snapshot, kept only as the cross-check-diff oracle (section 0c.3), never read as live source. TCPD CSV remains the source for election RESULTS. Git is the backup.

### eci_no bind (the one curation step; Hans + Max authority)
The operator has downloaded the LGD Assembly + Parliamentary Constituency HTML exports (`assembly_parliament_constituency*.htm`) into `datasets/ephemeral/`. The bind `(state, delim_year, eci_no) -> lgd_ac_id` is built once: PREFER a direct join if that export carries BOTH the LGD constituency id AND the ECI/delimitation constituency number; ELSE name+alias match within `(state, delim_year)` using the new `aliases` column to absorb transliteration drift. Unmatched ACs (e.g. J&K U08) stay null and are listed in the B2b.5.0 PR body, never silently dropped.

New prerequisite row **B2b.5.0** below carries this; B2b.5.2..5.5 now block on B2b.5.0 (not on signoff).

---

## section 0c REFINEMENT (2026-06-05; 4-persona debate Gregor/Hans/Max/Fowler, research-only) - parser seam, diff-receipt, honest provenance

The experts pressure-tested the ephemeral-as-source-of-truth direction and converged. Binding refinements (fold into B2b.5.0):

1. **The committed PARSED CSV is the source of truth, NOT the raw HTML.** `datasets/ephemeral/*.htm` is gitignored (`*`) - local-only, throwaway. Pipeline (two filters, committed seam): `ephemeral/*.htm (gitignored)` -> **`tools/lgd/parse_lgd_html.py`** (`lxml.html`, NOT pandas - `read_html` silently strips leading zeros off authority codes; target the data `<table id="__bookmark_1">`, every cell as text) -> **committed parsed-snapshot CSV** `datasets/reference/lgd/<table>.csv` + `parse-receipt.json` (per-file sha256 of raw bytes, row count, header columns, snapshot vintage) -> **backend canonical seed** -> `datasets/data/entities/*.csv` (`columns.json`-governed). Reproducibility contract: fresh checkout + committed builder regenerates `entities/*.csv`; byte-exact HTML re-parse is NOT required (the sha256 ties the committed snapshot to the uncommitted bytes). Precedent: `datasets/taxonomy/lgd/states-latest.csv` already does committed-CSV + `.sources.json` sidecar.
2. **"Distrusted in-repo derivations", NOT "corrupted" (Hans). [SUPERSEDED by round-8 section 0d: reframed as an unattributable ECI+LGD mix -> blame-free re-baseline to the dated LGD snapshot.]** The LGD portal data was never corrupt - same issuing authority (Ministry of Panchayati Raj) we are re-pulling. What is distrusted is the in-repo DERIVATIONS: the Wikipedia-joined `eci_st_code` and the mis-keyed arithmetic AC ids (`state_code*1000+eci_no`; a `lgd_ac_id` that is actually the ECI sequence). Plan wording everywhere: "the new snapshot overrides the distrusted in-repo derivations." Never imply MoPR shipped bad data.
3. **Diff-receipt BEFORE the override label (Max + all; STOP-AND-SURFACE).** B2b.5.0 emits a diff receipt (under `datasets/_ops/`) comparing parsed-ephemeral vs `taxonomy/*.json` per grain, reporting: (1) row counts + delta; (2) id-scheme overlap ratio [the FORK-SELECTOR]; (3) name-mismatch buckets {case, old-vs-new-official, genuine}; (4) orphans both directions; (5) per-parent cardinality (districts/ACs/PCs per state); (6) cross-register coverage loss (eci/iso/census values with no LGD source). Final line = evidenced verdict {corrupted | stale-names-ids-intact | name-divergent-only}. High id-overlap -> name-refresh + alias capture (NOT wholesale override); low overlap / cardinality divergence -> clean-rip justified. The word "corrupted" may not precede this number.
4. **`state_codes.csv` is an LGD-spine entity; `iso_3166_2` is its only seeded column (round-8: ECI dropped).** The LGD snapshot gives `lgd_state_id, lgd_name, kind`; the ONE column LGD omits that belongs on the spine is `iso_3166_2` (issuing authority = ISO; yen-gov transcribes via a tiny committed `datasets/reference/state-iso-seed.csv`, ~36 rows). `eci_st_code` is NOT seeded - no authoritative ECI registry exists (section 0d), so it is dropped, not re-verified. The joined `entities/state_codes.csv` carries `lgd_state_id, lgd_name, iso_3166_2, census_2001_code, census_2011_code, kind, slug, aliases` (round-8c: census as two dated columns + pipe `aliases`; NO `state_aliases.csv` - section 0d); census / former-names ride those columns, never an exact-match key. Contract test: the ISO seed covers EXACTLY the LGD state set (a new UT fails loud). Provenance: LGD columns -> LGD snapshot source_id; `iso_3166_2` -> ISO source_id; receipts in `docs/concepts/lgd-authority.md`.
5. **vintage = `2026-06-05` (the download date) is MANDATORY for geo/electoral source rows (Hans, ADR-0042).** LGD exposes no edition, so the operator snapshot window IS the vintage. An empty vintage collapses two snapshots onto one `source_id` and silently breaks the time-versioning the user asked for. `electoral_district_membership.lgd_snapshot` == the source row's `vintage`, emitted from ONE constant so they cannot drift.
6. **Deletion is LAST + staged (Fowler).** Emit the new entities -> diff-receipt + FK validator GREEN -> THEN delete `taxonomy/*.json` + `ac_crosswalk.*` + the old xwalk in a SEPARATE commit (all reversible via git). The ONLY one-way boundary is deleting the gitignored `.htm` - record its sha256 in the parse-receipt BEFORE the operator deletes it.
7. **Sub-district = parse-and-park (Max).** v1 served entities = state + district + AC/PC + membership only (no v1 indicator consumes sub-district grain). Parse sub-district in the SAME 2026-06-05 pass (acquisition already paid), but emit it parked (non-served) with its vintage; promote into `geo.csv` (`parent = district`) when the first sub-district-grain indicator arrives.
8. **Parser test, no mocks (Fowler, Holy Law #7).** A trimmed-REAL fixture under `backend/tests/fixtures/lgd/` (the real `<table>` wrapper + header + ~3 real rows, byte-copied), golden-file assert `parse(fixture) == expected.csv`. Adversarial real rows: a leading-zero code (locks no-int-coercion), a non-ASCII local-script name (locks encoding), an AC spanning two districts (locks the 1:many `is_primary` fan-out).

Staged PR sequence inside B2b.5.0 (Fowler; one hat per PR): **0a** parser + parsed-snapshot CSV + parse-receipt (gate: html-parse-receipt + deterministic-re-run + golden fixture); **0b** `state_codes.csv` = LGD snapshot (`lgd_state_id, lgd_name, iso_3166_2, census_2001_code, census_2011_code, kind, slug, aliases`; round-8: NO ECI seed; round-8c: census as two dated COLUMNS + pipe `aliases` column, NO `state_aliases.csv`) (gate: fk-validator + iso-seed-coverage); **0c** regenerate `electoral.csv` (AC+PC, `eci_no` folded from the PRI super-file's ECI-code columns, pipe `aliases`) + `geo.csv` (district + parked subdistrict, census columns + aliases) + emit `electoral_district_membership.csv` (deduped AC<->district edges from the PRI report) + run the eci_no DIRECT JOIN for the current delimitation (`TCPD.Constituency_No = PRI.AC_ECI_Code`; historical delims name-match) + commit the diff-receipt (gate: fk-validator + eci-bind-coverage + diff-receipt); **0e** ECI + census decommission sweep across `datasets/` + `backend/` + `frontend/` + emit the sweep receipt + clean every hit (gate: eci-census-decommission-sweep - zero `eci_st_code` columns/keys, zero census-as-join-key, `eci_no` retained; see section 0d sweep block); **0d-del** DELETE old taxonomy json + `ac_crosswalk` + synthetic-id refs LAST (gate: full validator green + grep no live reader). 0c spawns its own sub-plan if eci-bind-coverage needs the multi-day ~4000-AC name-clean. (NB the PR-stage labels 0a/0b/0c/0e/0d-del are distinct from the DOCUMENT sections 0a/0b/0c/0d.)

### Open forks for the user (experts split or deferred to you)
- **Fork S1 - source envelope:** prefer the LGD CSV/XLSX export over the rendered HTML where it carries the same columns (Max: structured beats scraped) vs parse the HTML the operator already downloaded (simplest now). Lean: use the HTML on hand for v1; note the divergence.
- **Fork S2 - snapshot location:** `datasets/reference/lgd/` (Fowler; next to existing lgd snapshots) vs a new `datasets/_sources/lgd/<date>/` tier (Gregor). Either is committed + non-served; pick one naming.
- **Fork S3 - state_codes provenance:** one `source_id` for the seed file (Fowler) vs per-column re-verified editorial provenance (Hans/Max, `owner = yen-gov` + per-authority receipts). Lean: editorial.

---

## section 0d ROUND-8 (2026-06-05; user challenge + web-research + Hans) - drop ECI state code, LGD-spine state identity, validity-scoped aliases

(NB: "0d" here is a DOCUMENT section, distinct from the `0a..0d-del` PR-stage labels inside section 0c's staged sequence.)

The user challenged the `eci_st_code` requirement; a web-research pass + Hans confirm the user is right. Binding round-8 amendments to sections 0b/0c (user-ratified per CLAUDE.md section 0a; scope-change ledger below):

1. **No authoritative ECI state/UT code exists - DROP `eci_st_code` from the spine.** Web-verified 2026-06-05: ECI publishes no state-code registry (its statistical-report pages 404; results key on state NAME); the `S22`/`U08` scheme is an internal data-file artifact that renumbers on reorganization (Telangana 2014; J&K state -> UT 2019) and is ABSENT from the TCPD/ECI result files the operator downloaded. The `eci_st_code` in our repo came from `lgd_states.json`'s own `$comment`: "Joined with ECI st_code (the in-repo wikipedia.urls map)" - WE invented the join. It fails all four issuing-authority tests (not published, self-joined, absent from results, renumbers) and is DROPPED from the state spine. Re-add ONLY as a validity-scoped alias if a real ECI-numbered external dataset is ever named (residual fork R1).
2. **State identity = LGD spine.** `entities/state_codes.csv` columns become `lgd_state_id` (PK, LGD-issued) + `lgd_name` + `iso_3166_2` (ISO-issued; yen-gov transcribes; `source_id` -> ISO) + `kind(state|ut)` + `slug` (yen-gov-authored, URL/display only, NOT an identity claim) [+ `census_2001_code` + `census_2011_code` + `aliases` per round-8c below]. The state NAME is the surface results actually join on.
3. **Aliases are COLUMNS, not a table (round-8c SUPERSEDES this round-8 point).** Round-8 specified a long-format `entities/state_aliases.csv` (`lgd_state_id, alias_kind, alias_value, valid_from, valid_to, source_id`) to carry "when it was, when it is not". Round-8c (user-directed) supersedes it: census codes ship from LGD as TWO DATED COLUMNS (`census_2001_code`, `census_2011_code`) that already encode that temporality (2001 value, 2011 value, NULL = did not exist), and name synonyms ride ONE pipe `aliases` column that generalises to every grain - so NO `state_aliases.csv` is emitted. Census codes remain LABELS, NEVER exact-match keys (census 2001 vs 2011 renumber and go null for Telangana/Ladakh/DNH-DD; a naive `JOIN ON census_2011_code` drops them and renders a phantom Rosling Gap). A generic `entity_aliases.csv` (all grains, one table, with validity + `source_id`) is deferred until a real validity+source query appears. See the Round-8c section below.
4. **Reset framing replaces "distrusted derivations" (supersedes 0c.2).** We cannot attribute the identity mess produced by historically mixing LGD codes with a Wikipedia-derived ECI crosswalk - so make NO quality/blame claim. Re-baseline to a single dated LGD snapshot as the authority of record, carry every prior value forward ONLY as a validity-scoped source-stamped alias, and discard anything that does not reconcile. The keep-useful-else-discard decision is evidenced by the section-0c.3 diff receipt, not by in-the-moment judgment.
5. **XLS or HTML, operator's choice.** LGD publishes both; XLS (`openpyxl`, cells read as strings) is in fact cleaner to parse than HTML (no presentation chrome, no leading-zero coercion risk). The committed parsed CSV under `datasets/reference/lgd/` is the source of truth either way; the gitignored ephemeral file stays throwaway.

### Round-8 scope-change ledger (per [docs/how-to/handle-scope-change.md](../docs/how-to/handle-scope-change.md))

| Verbatim user instruction | Change | Reason | signoff: |
| --- | --- | --- | --- |
| "prove there is an official ECI state code ... why are we chasing something which is not maintained ... take the LGD sources from ephemeral as the source of truth ... census code also changes so it should be a column with aliases ... when it was, when it is not" | DROP `eci_st_code` from the state spine (identity = lgd + name + iso + kind + slug); move census / former-names / any-ECI-code to long-format validity-scoped `entities/state_aliases.csv`; reset framing replaces round-7b "distrusted derivations". | Web-research + Hans confirm no authoritative/stable ECI state-code registry exists; the repo's `eci_st_code` came from an in-repo Wikipedia join; census codes renumber so cannot be exact-match keys. Amends the round-7 user-ratified lock. | SIGNED 2026-06-05 (user, this message; data-shape authority with Hans + Max). |

### Round-8 residual forks - RESOLVED (2026-06-05, user)
- **R1 RESOLVED -> FULL DROP.** The user directs: fully decommission `eci_st_code` (the STATE/UT code) - it is NOT in the spine and NOT even an alias row; no `eci_st_code` `alias_kind` is emitted into `state_aliases.csv`. The mandatory decommission sweep (below) confirms no in-repo consumer needs it. If a future ECI-numbered EXTERNAL dataset ever requires it, it is re-introduced THEN - via a new scope-change ledger row - as a validity-scoped alias, never pre-emptively. (Rationale: it fails all four issuing-authority tests - not published by ECI, self-joined from Wikipedia in-repo, absent from the result files, renumbers on reorganization - so carrying it even as a dormant alias would re-seed the exact identity confusion round-8 removes.)
- **R2 RESOLVED -> Round-8 chose a long-format `entities/state_aliases.csv`; Round-8c SUPERSEDES that to inline alias COLUMNS (see Round-8c section below).** Rationale recap: census codes ship from LGD as two dated columns (`census_2001_code` + `census_2011_code`) which already encode "when it was, when it is not", and name synonyms ride one pipe `aliases` column that generalises to every grain - so no separate alias table is needed at v1. A generic `entity_aliases.csv` (all grains, one table, with validity + `source_id`) is deferred until a real validity+source query appears. OWID-faithful + simpler. (The micro-call on whether the deferred generic table is ever needed sits with Hans + Max per [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md).)

### eci_st_code vs eci_no - the disambiguation the executing agent MUST honour
- **DECOMMISSIONED: `eci_st_code`** - the `S22`/`U08` STATE/UT code. Dropped from the spine, no alias, swept out everywhere (below). It is NOT in the result files.
- **RETAINED: `eci_no`** - the per-constituency ballot/serial number (1..N WITHIN a state, per delimitation). It IS present in the ECI/TCPD result files (the "AC NO" / "PC NO" columns), is folded on `electoral.csv` (round-7), and is the natural key the candidacies resolve through. Do NOT drop `eci_no` when decommissioning `eci_st_code`. A sweep that strips `eci_no` is a regression, not a cleanup.

### Round-8c LGD source files + open enrichment corpus (2026-06-05, user-directed; refines Round-8's 7-file list and R2 after on-disk validation of the operator's ephemeral exports)

A validation pass (subagent + direct read of `datasets/ephemeral/`) produced three refinements, all user-ratified (Round-8c scope-change ledger below).

> **ROUND-8d EXECUTION-READY CORRECTIONS (2026-06-05, user; on-disk validated - these supersede the round-8c text below wherever they conflict):**
> 1. **Ephemeral is SOURCE-only, never a destination.** Every `datasets/ephemeral/*.csv` is INPUT; outputs land committed under `datasets/reference/lgd/` (parsed LGD snapshot) + `datasets/data/entities/` and `datasets/data/datapoints/` (canonical). Nothing reads `ephemeral/` after ingest (it is gitignored throwaway).
> 2. **One-time bulk load, then delta.** Load whatever is present now ONCE; record a processed-ledger under `datasets/_ops/`; on later runs ingest only NEW/CHANGED files - never re-ingest a loaded snapshot.
> 3. **Enrichment (Tier E) is OPTIONAL, NOT required.** The core elections delivery is COMPLETE with spine (Tier S) + results (Tier R) alone. Office-holders / affidavits / rolls / gender / pincodes load on demand, each independently, never as a blocker or prerequisite. They sit in the manifest so they route correctly WHEN wanted - not because they are mandatory.
> 4. **What actually landed for ALL states is the Coverage Report, not the PRI-ECI report.** `Constituency_Report_2026-06-05_11-10-33.csv` (44 MB, all states) is the structural super-file (AC + PC + AC->PC + AC->district 1:many with Fully/Partly Covered = `is_primary`, down to village/ward). It carries LGD codes, NOT ECI codes - so `eci_no` binds by NAME-MATCH `(state, delim_year, ac_name)` against the TCPD result files (whose `Constituency_No` IS `eci_no`). The PRI-with-ECI report (A&N-only on disk) is an OPTIONAL accelerator that would convert the name-match into a direct join; NOT a v1 blocker.
> 5. **Plan is EXECUTION-READY** with the files on disk; no further operator export is required for v1.

**(1) The PRI constituency export is a SUPER-FILE that collapses four of the seven Round-8 files.** `parlimentConstituencyAndAssemblyConstituencyPRI*` carries, per row: Parliament Constituency code + **Parliament Constituency ECI Code** + PC name + Assembly Constituency code + **Assembly Constituency ECI Code** + AC name + District code/name/census + Subdistrict code/name/census + Block code/name. That ONE export yields the AC register (round-8 #4, WITH the ECI AC number), the PC register (#5, WITH the ECI PC number), the AC->PC parent (#6, the PC on every AC row), AND the AC->district 1:many coverage (#7, the district on every AC row - dedupe `(ac, district)`), plus subdistrict + block for free. The spine file list therefore shrinks to THREE required + ONE parked:

| # | LGD export | Yields | Feeds | v1 |
| --- | --- | --- | --- | --- |
| 1 | All States/UTs of India | lgd_state_id, lgd_name, kind, census_2001_code, census_2011_code | `entities/state_codes.csv` | required |
| 2 | All Districts of India | lgd_district_id, lgd_name, lgd_state_id, census codes | `entities/geo.csv` district rows + district->state parent | required |
| 3 | **Constituency Coverage Report** (`Constituency_Report_*.csv`, ALL states - ON DISK 2026-06-05) | AC code + AC name + PC code + PC name (=> AC->PC) + Entity Type/Code/Name {District,SubDistrict,Localbody,Village,Ward} + Coverage Type {Fully,Partly} (=> AC->district 1:many, `is_primary` = Fully-vs-Partly) | `entities/electoral.csv` (AC+PC structure) + `entities/electoral_district_membership.csv` (`is_primary`) | required |
| 3b | PRI report (`parlimentConstituencyAndAssemblyConstituencyPRI*`, ECI-code columns) | adds **AC/PC ECI Code** => direct `eci_no` join | OPTIONAL accelerator: converts the eci_no NAME-MATCH (paragraph 2) into a direct join; A&N-only on disk; NOT a v1 blocker | optional |
| 4 | All Sub-districts of India | lgd_subdistrict_id, name, parent district | `entities/geo.csv` subdistrict rows | parked |

ON-DISK REALITY (2026-06-05, supersedes round-8c's "re-export PRI for all states"): the operator provided the **Constituency Coverage Report for ALL states** (`Constituency_Report_2026-06-05_11-10-33.csv`, 44 MB) - the structural super-file (AC + PC + AC->PC + AC->district with Fully/Partly Covered = `is_primary`, down to village/ward). It carries LGD codes (AC code e.g. 3166), NOT ECI codes, so the `eci_no` bind is by NAME-MATCH (paragraph 2 below), not a direct join. The thin `Assembly_parliament_constituency_*.csv` is SUPERSEDED by it (the coverage report is a strict superset). The standalone all-districts file (#2) is STILL required (district REGISTER: district -> state; the coverage report gives the constituency->district EDGE, not the registry). The PRI-with-ECI report (#3b) stays an OPTIONAL accelerator, NOT a v1 blocker.

**(2) `eci_no` bind = NAME-MATCH `(state, delim_year, ac_name)` by default; DIRECT JOIN only where the PRI-ECI export exists.** The TCPD result files (`All_States_AE.csv` etc.) key each row on `(State_Name, DelimID, Constituency_No, Constituency_Name)` where `Constituency_No` IS the `eci_no` (the ECI/delimitation serial 1..N per state). The on-disk Coverage Report gives the LGD structure (lgd_ac_code + ac_name + district + is_primary) but NOT the ECI serial. So the executable v1 bind is: `eci_no` comes from the TCPD result file's `Constituency_No`, joined to the LGD AC by NAME-MATCH on `(State, delim_year, ac_name)` (Constituency_Name <-> Assembly Constituency Name). This is the ~4000-AC name-normalisation pass (transliteration variants) - REAL but bounded, runs ONCE. The OPTIONAL accelerator (PRI-ECI export, table row 3b) would replace the name-match with a direct join `TCPD.Constituency_No = PRI.AC_ECI_Code`; not required for v1. Either way `eci_no` is SOURCED from the result file, so it lands on every `electoral.csv` AC row regardless of which bind is used.

**(3) Aliases are COLUMNS, not a separate table - supersedes Round-8 R2's `entities/state_aliases.csv`.** The user: "why cant aliases be another column, this will [work] for districts as well ... for other grain as well." Adopted:
- NO `state_aliases.csv`, NO per-grain alias tables.
- Census codes stay as TWO DATED COLUMNS (`census_2001_code`, `census_2011_code`) on each entity file that has them (state, district, subdistrict). These two dated columns ARE the "when it was, when it is not" the user asked for in Round-8: the 2001 column = code as of Census 2001, the 2011 column = code as of Census 2011, NULL = entity did not exist at that census. They are LABELS, never exact-match JOIN keys (codes renumber + go null for Telangana/Ladakh/DNH-DD - a `JOIN ON census_*_code` drops them and renders a phantom Rosling Gap).
- Name synonyms (transliterations, former official names) ride ONE pipe `aliases` column on EVERY entity file - state, district, AC, PC. One mechanism, all grains; powers yen-ask grounding; regenerable.
- DEFERRED escape hatch: IF a real "former name WITH a validity window AND a per-alias `source_id`" query ever appears, introduce ONE generic `entity_aliases.csv` keyed by `(entity_id, entity_kind, alias_kind, alias_value, valid_from, valid_to, source_id)` covering ALL grains in ONE table - never per-grain, never `state_aliases.csv`. Not built at v1.

### Round-8c/8d corpus routing (REQUIRED = Tier S + Tier R; OPTIONAL = Tier E; ephemeral is SOURCE-only; one-time bulk then delta)

The ephemeral folder is a SOURCE, never a destination (round-8d): every file is INPUT only; outputs land committed under `datasets/reference/lgd/` (parsed snapshot) + `datasets/data/entities/` and `datasets/data/datapoints/` (canonical); nothing reads `ephemeral/` after ingest. LOAD MODEL: a ONE-TIME bulk load of whatever is present now, then DELTA only - the agent records a processed-ledger under `datasets/_ops/` and on later runs ingests only NEW/CHANGED files, never re-ingesting a loaded snapshot. The agent enumerates `datasets/ephemeral/*.csv` and routes by the manifest below; REQUIRED tiers (S + R) MUST all be processed for the elections delivery; OPTIONAL Tier E is processed on demand and NEVER blocks; emit a skip-receipt under `datasets/_ops/` for any unrecognized file.

- **Tier S (spine) - REQUIRED:** the LGD files above -> `entities/state_codes.csv` / `geo.csv` / `electoral.csv` / `electoral_district_membership.csv`.
- **Tier R (results, core electoral facts) - REQUIRED:** TCPD `All_States_AE.csv` (assembly), `All_States_GE.csv` (parliament/LS), the per-year LS detailed-result CSVs, TCPD party + CM-id registries -> `elections/assembly/...`, `elections/parliament/...`, `entities/parties.csv`.
- **Tier E (enrichment) - OPTIONAL, load on demand, NOT required for v1:** office-holders (presidents, vice-presidents, chief ministers), candidate affidavits, electoral rolls, gender counts, pincode directory. Each is its OWN independent ingest (own concept + `source_id`), shippable whenever wanted; none blocks or is a prerequisite for the core elections delivery. The agent does NOT need these to deliver elections; it loads a Tier-E file only when that dataset is actually wanted. They are listed so that WHEN loaded they route correctly - not because they are mandatory.

Routing manifest (current ephemeral snapshot, NON-EXHAUSTIVE - extend as files arrive):

| File / glob | Tier | Routes to |
| --- | --- | --- |
| `All_Stateof_India_*.csv` | S | `entities/state_codes.csv` |
| `All_Districtof_India_*.csv` | S | `entities/geo.csv` (district) |
| `All_Sub_Districtof_India_*.csv` | S (parked) | `entities/geo.csv` (subdistrict) |
| `Constituency_Report_*.csv` (Coverage Report, ALL states - ON DISK) | S | `entities/electoral.csv` (AC+PC structure) + `entities/electoral_district_membership.csv` (Fully/Partly = is_primary) |
| `parlimentConstituencyAndAssemblyConstituencyPRI*` (ECI-code report) | S (optional) | OPTIONAL accelerator for the eci_no direct join; A&N-only on disk; NOT a v1 blocker |
| `Assembly_parliament_constituency_*.csv` (thin) | SUPERSEDED | dropped (Coverage Report is a strict superset) |
| `All_States_AE.csv` | R | `elections/assembly/state=*/election=*/...` |
| `All_States_GE.csv` | R | `elections/parliament/election=*/...` |
| `2019_*loksabha*Result.csv`, `2024_*loksabha*Result.csv` | R | `elections/parliament/...` (cross-check) |
| `TCPD-PoliticalPartiesIndia_*.csv` | R | `entities/parties.csv` |
| `TCPD-CMID_*.csv`, `CM_Final.csv` | E | chief-minister office-holder datapoints + person registry |
| `presidents_draft.csv` | E | president office-holder datapoints |
| `vice-presidents_draft.csv` | E | vice-president office-holder datapoints |
| `*_affidavits.csv` (e.g. `2014_lok_sabha_affidavits.csv`) | E | candidate-affidavit datapoints (assets/education/criminal) |
| `tn-rolls-*.csv` | E | electoral-roll datapoints |
| `tn_acwise_gendercount.csv` | E | AC-wise gender-count datapoints |
| `all_india_pincode_directory_*.csv` | E | pincode reference |

Reaffirm (round-8d): Tier E is OPTIONAL and delta-loaded - the core elections delivery is COMPLETE with Tier S + Tier R alone; Tier E adds breadth later, one independent dataset at a time, never as a blocker or prerequisite.

### Round-8c scope-change ledger (per [docs/how-to/handle-scope-change.md](../docs/how-to/handle-scope-change.md))

| Verbatim user instruction | Change | Reason | signoff: |
| --- | --- | --- | --- |
| "why cant aliasese be another column, this will for districts as well etec. for other grain as well" | Round-8 R2 `entities/state_aliases.csv` (long-format per-grain alias table) is SUPERSEDED: aliases are inline COLUMNS (census as two dated columns + one pipe `aliases` column) on every entity file; a generic `entity_aliases.csv` is deferred until a real validity+source query appears. | Census-as-two-dated-columns already encodes "when it was, when it is not" (the Round-8 requirement) and ships that way from LGD; a pipe `aliases` column generalises to all grains with no new table. Simpler + more OWID-faithful. | SIGNED 2026-06-05 (user, this message; data-shape authority with Hans + Max). |
| "Take advantage of all the CSV files ... make it clear that there will be other CSVs added ... presidents, vice presidents, chief ministers, candidate affidavits ... all for enrichment" | Add the open enrichment-corpus manifest (Tiers S/R/E) + the rule that the agent enumerates `datasets/ephemeral/*.csv` and routes by manifest (never a hardcoded closed list), with a skip-receipt for unrecognized files. | The corpus is open and growing; a fixed 7-file list would make the agent drop the office-holder / affidavit / rolls enrichment files. | SIGNED 2026-06-05 (user, this message). |
| (round-8d) "the ephemeral CSV files are just a source, not the destination ... ask why we need all that [enrichment] ... This is a one time load and after that it is only a delta load ... added PRI for rest of states and UT, make the plan ready for agent execution" | (a) state ephemeral is SOURCE-only + name committed destinations; (b) demote Tier E enrichment from "process every file" to OPTIONAL / load-on-demand / NOT-required-for-v1; (c) adopt one-time-bulk-then-delta with a processed-ledger; (d) record the Constituency Coverage Report for ALL states is on disk (structural super-file), correcting round-8c's "re-export PRI for all states" - `eci_no` binds by NAME-MATCH, PRI-ECI export is an optional accelerator; (e) mark the plan EXECUTION-READY. | User confirmation + scope reduction: enrichment is not necessary for the core delivery; the load is one-time + delta so the agent must not treat Tier E as mandatory or re-ingest loaded snapshots; on-disk validation shows the coverage report (not the PRI-ECI report) landed for all states. | SIGNED 2026-06-05 (user, this message). |

### Round-8 ECI + census decommission sweep (mandatory; PR-stage 0e, runs after 0c and before 0d-del)
Because `eci_st_code` is FULLY dropped (R1), every other consumer must be found and cleaned so nothing re-introduces it. The user's directive: "if any other indicator is using ECI, then we should clean that up as well because we are going to remove it completely." The sweep:
1. `grep -rniE 'eci_st_code|\bst_code\b|state=in_[su][0-9]{2}|\b[SU][0-9]{2}\b'` across `datasets/` (taxonomy, data, indicators, datapoints, elections, grapher), `backend/yen_gov/`, `frontend/src/` - find any column, join key, loader, SQL template, partition value, or indicator datapoint keyed on an ECI STATE code. Distinguish from `eci_no` (the constituency serial, which is RETAINED).
2. `grep -rniE 'census_20(01|11)_code'` - find any indicator/datapoint/loader that EXACT-MATCH-JOINS on a census code (vs carrying it as a label). Each such join is repointed to the LGD-id key; the census code stays a LABEL COLUMN (`census_2001_code`/`census_2011_code`) on the entity file (round-8c - NOT a `state_aliases` row; a row in the deferred generic `entity_aliases.csv` only if a real validity+source query exists), NEVER a key - census codes renumber across 2001/2011 + reorganizations and go null for post-census entities (Telangana/Ladakh/DNH-DD), so a `JOIN ON census_*_code` silently drops them (phantom Rosling Gap).
3. Emit a sweep receipt `datasets/_ops/eci-census-decommission-sweep-2026-06-05.md`: every hit (file:line), and disposition - drop-column / convert-to-validity-alias / retained-eci_no / false-positive (e.g. a `kSha` glyph or an unrelated `S01` token).
4. Clean each hit in the chunk that OWNS that surface (yenask SQL in YA; frontend loaders in F1; taxonomy/indicators in this sub-plan). Cross-surface hits get a one-line forward-pointer in the receipt so the owning chunk picks them up.

Gate `eci-census-decommission-sweep` (pass = zero): after the sweep + cleanups, the ONLY surviving `eci_st_code` tokens in the repo are its historical mentions in plan-docs + this receipt; zero `eci_st_code` columns, zero census-as-join-key, `eci_no` still present in `electoral.csv` and the result-bind.

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
| B2b.5.0 clean-start re-emit (NEW prerequisite; section 0b + REFINED section 0c into staged 0a..0e..0d-del + ROUND-8 + ROUND-8b section 0d): write `tools/lgd/parse_lgd_html.py` (lxml; or `openpyxl` for the XLS export) (ephemeral HTML/XLS -> committed parsed-snapshot CSV under `datasets/reference/lgd/` + `parse-receipt.json`); emit `entities/state_codes.csv` (LGD spine `lgd_state_id, lgd_name, iso_3166_2, census_2001_code, census_2011_code, kind, slug, aliases`; eci_st_code DROPPED - no authoritative ECI registry, section 0d; round-8c: census as two dated COLUMNS + pipe `aliases`, NO `state_aliases.csv`); regenerate `entities/electoral.csv` (AC+PC, `eci_no` folded from the PRI super-file's ECI-code columns, pipe `aliases`, LGD-native PK no arithmetic ids) + `entities/geo.csv` (district + parked subdistrict) + `entities/electoral_district_membership.csv` (`is_primary`, deduped AC<->district edges from the PRI report); run the eci_no DIRECT JOIN for the current delimitation (historical delims name-match); process the open enrichment corpus per its Tiers-S/R/E manifest (section 0d round-8c); run the ECI + census decommission sweep (PR-stage 0e - zero `eci_st_code` columns/keys, every census-as-join-key converted to a validity-scoped alias, `eci_no` RETAINED) + emit its receipt under `datasets/_ops/`; COMMIT THE DIFF-RECEIPT evidencing the override (section 0c.3) BEFORE deleting; DELETE `ac_crosswalk.*` + old xwalk + synthetic `state_code*1000+eci_no` LAST; rename `party.csv` -> `parties.csv`. Existing `taxonomy/*.json` = unattributable ECI+LGD mix; reset to the dated LGD snapshot baseline (section 0d), kept as cross-check oracle. | B2b.5.1 | html-parse-receipt + diff-receipt + fk-validator + eci-bind-coverage + eci-census-decommission-sweep | - | IN-FLIGHT (staged; see B2b.5.0 staged-PR tracker below) |

### B2b.5.0 staged-PR tracker (one PR per hat, section 0c sequence)

| Stage | Scope | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| 0a | `tools/lgd/parse_lgd_export.py` (openpyxl/CSV, NOT the plan's nominal `parse_lgd_html.py` - the operator supplied CSV + XLSX, plan 0d round-8 point 5 "XLS or HTML, operator's choice") + committed parsed snapshot `datasets/reference/lgd/{states,districts,subdistricts,constituencies,constituency_district_membership}.csv` + `parse-receipt.json` (sha256 per source + vintage) + `lgd-parse-receipt.schema.json` + golden fixtures + `backend/tests/test_lgd_parser.py` | html-parse-receipt + deterministic-re-run + golden fixture | #762 | MERGED |
| 0b | `entities/state_codes.csv` (LGD spine `lgd_state_id, lgd_name, iso_3166_2, census_2001_code, census_2011_code, kind, slug, aliases`) from the 0a snapshot + a committed ISO transcription seed `datasets/reference/state-iso-seed.csv` + columns.json file_class. Folds in a parser refinement: LGD census `0`/`000` sentinel (entity did not exist at that census) normalised to empty so census stays a LABEL never a join key (snapshot + goldens regenerated). | fk-validator + iso-seed-coverage | #763 | MERGED |
| 0c-1 | `geo.csv` +`census_2001_code` +`census_2011_code` columns (LGD-code join onto existing rows; entity_id scheme preserved) + long-name synonym alias. `eci_st_code` alias RETAINED here - stripping it breaks `test_csv_parquet_parity::test_governments` (the `load_eci_state_to_geo_entity` resolver harvests the `S<NN>`/`U<NN>` token); the full decommission is the dedicated 0e sweep. | fk-validator + governments-parity | #764 | MERGED |
| 0c-2 | regenerate `electoral.csv` (+`eci_no` folded DIRECT from the PRI super-file's ECI-code column, +`aliases`) + `electoral_district_membership.csv` (renamed from `electoral_lgd_xwalk.csv`; `is_primary`/`lgd_snapshot`/`source_id`, 4315 edges) + LGD `source.csv` row (`derive_source_id`) + diff-receipt under `datasets/_ops/` (verdict minor-membership-shift, overlap 0.98) | fk-validator + eci-bind-coverage + diff-receipt | #765 | MERGED |
| 0c-3 | rename `party.csv` -> `parties.csv`: entity file_class + 7 election/holder FK targets in `columns.json` + emitter `FILE_CLASS` + the two `_run_*` drivers + `governments_term_shape` resolver docstrings + `csv-column-contract.md` / `canonical-writer.md` spec rows. Byte-identical regen (620 rows). | fk-validator | _pending_ | IN-FLIGHT |
| 0e | ECI + census decommission sweep + receipt under `datasets/_ops/` | eci-census-decommission-sweep | - | TODO (blocks on 0c-3) |
| 0d-del | DELETE `ac_crosswalk.*` + old `electoral_lgd_xwalk.csv` + synthetic-id refs LAST | full validator green + grep no live reader | - | TODO (blocks on 0e) |

> Section 0c exceeded one reviewable PR (section 24.5: 4 emitters + 3 columns.json changes + diff-receipt + parties rename), so it shipped as three staged sub-PRs 0c-1 / 0c-2 / 0c-3, each its own reviewable diff regenerated from the committed 0a snapshot.

> Round-8d on-disk reality folded into 0a: the PRI super-file (`Parliment_..._Pri_*.xlsx`) landed for ALL 35 states/UTs, NOT A&N-only. Each per-AC-village row carries the AC LGD code + AC ECI Code + PC LGD/ECI codes + District code, so the `eci_no` bind is a DIRECT JOIN off the PRI export (not the name-match the round-8d text feared); `entity_id` stays LGD-native; AC<->district membership + plurality `is_primary` come straight off the village rows. A&N has no PRI file (no district breakdown) and therefore no AC rows - expected.

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
