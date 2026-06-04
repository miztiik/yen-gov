# B2b.5 sub-sub-plan - elections-from-local-TCPD per-election CSV reingest

**Last Updated**: 2026-06-04
**Parent**: [TODO/20260604-b2b-reingest-subplan.md](20260604-b2b-reingest-subplan.md) row B2b.5
**Grandparent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk B2b
**Status**: IN-FLIGHT (spawned 2026-06-04)
**Authority**: Hans + Max (per-election shape, identity, candidacy vs summary columns) / Gregor (FK contract, per-election self-containment, parity gate, parliament `state` mandatory column per 23.4) per CLAUDE.md section 0a

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
| B2b.5.2 assembly per-state pilot: emit `assembly/state=tamil-nadu/election=<yr>/{candidacies,summary}.csv` for ALL TN years held in `state=tamil-nadu/election_results.parquet` + `elections_candidacies.parquet` (TN-scoped slice); cross-format-parity + parity-oracle-CSV (winner+margin invariants only) on this slice | B2b.5.1 | cross-format-parity + parity-oracle-CSV | - | TODO |
| B2b.5.3 assembly fan-out: replay the B2b.5.2 emitter across the remaining 35 `state=<slug>/` directories; one PR per parallel-safe wave (~6-10 states per wave by file-size; orchestrator picks wave membership; each wave is ITSELF a sub-sub-sub-row that may spawn its own plan if a wave exceeds one PR's reviewable surface) | B2b.5.2 | cross-format-parity per state | - | TODO |
| B2b.5.4 parliament: emit `parliament/election=<year>/{candidacies,summary}.csv` for every LS cycle held in `elections_candidacies.parquet` (1957..2024, ~18 cycles; PC rows discriminated by `entity_id` prefix). MANDATORY `state` column on the parliament file per plan section 23.4. EL7 `coverage.py` disposition resolved in this PR's body | B2b.5.1 | cross-format-parity + parity-oracle-CSV | - | TODO |
| B2b.5.5 source ledger backfill (only if B2b.5.2 / B2b.5.3 / B2b.5.4 surface any TCPD release vintage absent from `entities/source.csv`): append rows via `derive_source_id`; SAME-PR with the emit row that surfaced the gap (do NOT defer; per B2a.1 precedent) | (folded inline into the emit row that triggers it) | fk-validator | - | TODO |
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
