# 2026-05-21 — handover: states.json port blocked by entities.json UT coverage gap

> **Phase A: ✅ COMPLETE** — PR `feat/canonical-pivot-t0c-ii-phase-a-entities-ut-gap` (branch off `66ca264b`), 2026-05-21.
>
> The 7-UT gap in `datasets/taxonomy/entities.json` was filled (U01, U02, U03, U04, U05, U07, U08, U09 + U03-OLD + U06 historical predecessors). `entities.parquet` regenerated (185 rows, byte-stable post-emit because the JSON rows were already authored prior to this PR). New parity oracle `backend/tests/test_states_parity.py` (4 tests, 0.16s) wired in as the back-stop for Phase B + Phase C. One legitimate name deviation documented via `ALLOWED_NAME_DEVIATIONS` frozenset: `U08` carries the `"(UT)"` suffix in `entities.json` (`"Jammu and Kashmir (UT)"`) to disambiguate from the pre-2019 historical state `IN-S09`. Backend pytest: 775 passed / 41 skipped. Tier-B validator: 0 issues. Frontend vitest: 16,059 passed / 6 skipped (unchanged).
>
> **Phase A.5 (deferred)** — schema bump `entity.schema.json` v1.1 → v1.2 to add per-row `source_id` referencing `sources.parquet` (the citation ledger). The 8 UT rows authored in Phase A do not currently carry §12 envelope (entity rows have been genuinely exempt from §12 to date; CLAUDE.md §12 references "observation rows", and dim/taxonomy rows have ridden file-level conventions). Decision to ship this as Phase A was **Path B** (data-fill only, no schema change) per orchestrator guidance, because Path A would have required schema bump + Pydantic model widening + 8 MoHA-notification source rows with URL verification on `indiacode.nic.in`, ballooning the PR. Phase A.5 lifts the deferred work into its own PR with full schema-bump discipline. See Phase A.5 entry below.
>
> **Phase B: ✅ COMPLETE** — branch `feat/states-json-port-phase-b-backend-consumers`, 2026-05-22.
>
> All 4 backend consumers repointed from `datasets/reference/in/states.json` to `datasets/taxonomy/entities.json` with filter `entity_type IN ('state', 'ut') AND entity_valid_to IS NULL`. Mapping: `entity_code → eci_code`, `display_name → name`, `entity_type → kind` (translated `ut → union_territory` to preserve downstream UT-without-assembly filter in `coverage.py:287` and `core/models.py StateEntry.kind` Literal). Files touched: `backend/yen_gov/coverage.py` (wrapper helper `_load_states_from_entities`), `tools/lgd/backfill_lgd_codes.py` (inline projection via new `_iter_states_from_entities`), `backend/yen_gov/sources/india_geodata/power_plants.py` (`_state_eci_lookup` rewritten; J&K normaliser values updated to `"Jammu and Kashmir (UT)"` to match the post-Phase-A canonical `display_name` so J&K plants keep resolving to U08), `backend/tests/test_datasets_integrity.py` (`_known_state_codes` re-projection). Two test-fixture updates also shipped in this PR because their writers fed the changed code paths: `backend/tests/test_coverage.py` (4 `_write` fixtures: 3 `Tamil Nadu`/`Assam` rows + 1 empty case re-shaped to entities.json envelope) and `backend/tests/test_lgd_backfill.py` (1 fixture renaming `S99 Phantomstan` to the entities.json shape). Holy Law #4 coverage CLI smoke-tested with `--root . --no-write` (exit 0, 88KB inventory markdown). Backend pytest: **775 passed / 41 skipped (93.65s)**. Tier-B validator: **0 issues**. The legacy `datasets/reference/in/states.json` file is **NOT** deleted in Phase B — that lands in Phase C alongside the frontend port + §13 browser smoke. Both files coexist on disk and stay byte-identical for the duration of Phase B (parity oracle `test_states_parity.py` re-confirms on every PR).
>
> **Phase C (frontend port + states.json deletion + §13 browser smoke)** remains NOT started.

---

> **Status:** AUTONOMOUS-UNSAFE BLOCKER. Surfaced 2026-05-21 during T.0c-ii consumer-port arc (PR #73 closeout). Branch `feat/canonical-pivot-T0c-ii-states-json-port` was opened, the parity audit ran, the blocker was identified, the branch was abandoned. **No code shipped from the port itself; this handover doc is the only artifact.**

## TL;DR

`datasets/reference/in/states.json` (36 entries: 28 states + 8 UTs) cannot be retired in favour of `datasets/taxonomy/entities.json` (29 entries: 28 states + 1 UT) because **7 UT entries are missing from the canonical taxonomy**. The Phase-0 closeout plan §0e (TODO/20260517-canonical-long-format-pivot.md row 312) expected this port to be a trivial KEEP-AND-DELETE; the audit revealed entities.json was seeded with only Delhi for UTs. Adding the remaining 7 UTs requires hand-authored entries with authoritative MoHA-notification provenance for `entity_valid_from` and (where relevant) `entity_valid_to`, which is data-authorship that CLAUDE.md §3 ("never invent IDs", and by extension never invent constitutional dates without sourcing) puts out of bounds for autonomous work.

## Parity audit (run 2026-05-21)

`tools/inspect_states_parity.py` (scratch, deleted after the audit):

```
states.json: 36 entries
entities.json state+UT: 29 entries
missing from entities: ['U01', 'U02', 'U03', 'U04', 'U05', 'U07', 'U08', 'U09']
name mismatch: []
kind mismatch: []
extra in entities (not in states.json): ['S09']
```

The `S09` extra is correct — it's pre-2019 J&K-as-state with `entity_valid_to` set (entities.json is temporal-aware; states.json is current-only). That's not the gap; the gap is the 7 missing current UT codes.

## Missing UT entries (what needs hand-authoring)

Each row below collapses what `states.json` already carries (current-only metadata) + what `entities.json` adds (temporal metadata + LGD code). The MoHA-notification reference is the **authoritative provenance source** the next session must cite in `taxonomy/entities.json.sources[]` when adding these rows.

| `entity_code` | `display_name` (from states.json) | `iso_3166_2` (from states.json) | `lgd_code` (from `taxonomy/lgd/states-latest.csv`) | `entity_valid_from` | `entity_valid_to` | Notes / authority |
| --- | --- | --- | --- | --- | --- | --- |
| `U01` | Andaman & Nicobar Islands | `IN-AN` | look up in LGD CSV | 1956 | null | UT re-established under States Reorganisation Act 1956 (Schedule I Part C); previously administered directly by GoI. |
| `U02` | Chandigarh | `IN-CH` | look up | 1966 | null | UT created on 1 Nov 1966 under Punjab Reorganisation Act 1966 (Section 4); serves as joint capital of Punjab + Haryana. |
| `U03` | Dadra and Nagar Haveli and Daman and Diu | `IN-DH` | look up | 2020 | null | UT created by merger 26 Jan 2020 under Dadra and Nagar Haveli and Daman and Diu (Merger of Union Territories) Act 2019. **Predecessors** (DNH separate UT 1961–2020 + DD separate UT 1987–2020) MAY warrant separate historical rows with `entity_valid_to=2020`. |
| `U04` | NCT of Delhi | `IN-DL` | look up | 1991 | null | NCT status under Constitution (Sixty-ninth Amendment) Act 1991 + Government of NCT Delhi Act 1991, granting Article 239AA Legislative Assembly. Was UT 1956–1991. |
| `U05` | Jammu & Kashmir (UT) | `IN-JK` | look up | 2019 | null | UT carved from former state of J&K on 31 Oct 2019 under Jammu and Kashmir Reorganisation Act 2019. Paired with `S09` historical state row (entity_valid_to=2019). |
| `U07` | Puducherry | `IN-PY` | look up | 1962 | null | UT formed 16 Aug 1962 under Constitution (Fourteenth Amendment) Act 1962 from former French territories. Has Article 239A Legislative Assembly. Code U06 is intentionally vacant per states.json notes ("live portal serves under U07"). |
| `U08` | Ladakh | `IN-LA` | look up | 2019 | null | UT carved from former state of J&K on 31 Oct 2019 under Jammu and Kashmir Reorganisation Act 2019. No Legislative Assembly (Article 239 governance only). |
| `U09` | (verify code) | (verify) | look up | (verify) | (verify) | **U09 needs verification** — check `states.json` for what code U09 represents; the parity audit listed it as missing but I did not cross-verify the underlying entry. Could be Lakshadweep (often listed before Ladakh in older ECI numbering) — needs the same MoHA/States-Reorganisation-Act treatment. |

> **Recommended sourcing pattern for `taxonomy/entities.json.sources[]` when adding these:** cite the **specific Act + section/article** plus a URL to indiacode.nic.in or PRSIndia.org for the canonical legal text. **Do NOT cite Wikipedia for `entity_valid_from`** — that's the kind of derivative source that has bitten us before (per `/memories/lessons.md` 2026-05-19 schema-changelog discipline). MoHA notifications are the registry-of-record.

## Why this was not done autonomously

1. **CLAUDE.md §3** — never invent IDs, and by extension never assert constitutional dates without authoritative provenance. The 7 UT rows above need MoHA citations, not "well-known facts".
2. **`lgd_code` field on each row** must be cross-verified against `datasets/taxonomy/lgd/states-latest.csv`. The LGD CSV uses its own numeric scheme; the bridge is hand-authored. Risk of off-by-one or wrong-code is real if I rush.
3. The whole point of the canonical taxonomy is that it carries **provenance-bearing rows** (`sources[]` on the artifact). Adding 7 rows means amending `taxonomy/entities.json.sources[]` to enumerate the 8 MoHA notifications I cited above — that source-list amendment must be a curator action with the responsible-engineer/citizen byline visible in git blame.

## What WAS verified (safe to act on next session)

- **No name or kind mismatch** between the 28 state entries that exist on both sides. So once UTs are added, the per-state name+kind projection is byte-clean.
- **No code drift.** Every `eci_code` in states.json matches an `entity_code` in entities.json for the 28 states already present.
- **`capital` and `verification_status` fields on states.json have ZERO downstream code consumers** — searched all of backend/yen_gov/, frontend/src/, tools/. They appear only in:
  - `datasets/schemas/state.schema.json` v3.1+ (declares them)
  - `backend/yen_gov/core/models.py StateEntry` (Pydantic Literal)
  - `datasets/reference/in/states.json` itself (data)
  - documentation referring to the 5C expansion history
  
  They can be dropped on the eventual state.schema retirement without code impact. The `capital` strings (`"Amaravati"`, `"Itanagar"`, ...) are pure citizen-display chrome that nothing renders today; if a future StateOverview wants them, lift to `taxonomy/entities` as `capital` field with proper sourcing.
- **`tier` field** is NOT in states.json (it's in `taxonomy/state_tiers.json`). The `core/models.py StateEntry.tier` Literal is a vestigial declaration that pydantic ignores when absent; safe to remove with `StatesCollection`.

## Plan for the next session

**Phase A — fill the UT gap in taxonomy/entities.json (data-authorship PR). ✅ COMPLETE.** See top-of-doc status block; Phase A shipped via the `feat/canonical-pivot-t0c-ii-phase-a-entities-ut-gap` branch. The §12 envelope addition (per-row `source_id` referencing the citation ledger) was descoped from this PR and lifted into Phase A.5 (see below).

**Phase A.5 — provenance-additive entity.schema.json bump v1.1 → v1.2 (deferred from Phase A).**

1. Schema additive bump v1.1 → v1.2 adding optional `source_id` per-row, matching the `^src-[0-9a-f]{12}$` pattern used by §12 v2.0 citation ledger (ADR-0032).
2. Pydantic model in `backend/yen_gov/core/models.py` (`EntityRow` or equivalent) widens to accept the new field.
3. Emit 8 `sources.parquet` rows for the MoHA notifications cited in the Phase A authoring (States Reorganisation Act 1956, Punjab Reorganisation Act 1966, DNH-DD Merger Act 2019, Constitution 69th Amendment 1991, Constitution 14th Amendment 1962, J&K Reorganisation Act 2019, etc.) — each row built via `backend/yen_gov/canonical/citation.derive_source_id` with `(producer="Government of India / Ministry of Home Affairs", title=<Act long title>, vintage=<year>)`. URL verification on `https://www.indiacode.nic.in/` before adding (do NOT cite Wikipedia — same discipline as §12 v2.0).
4. Stamp the new optional `source_id` field on each of the 8 UT rows + 2 historic predecessor rows authored in Phase A.
5. Regenerate `entities.parquet` + `sources.parquet`, regen `manifest.json` row counts.
6. ADR-0033 (or next free) recording the schema bump rationale + the OWID-source-row precedent.
7. Tier-A pytest + Tier-B validator + frontend vitest gates.
8. Update lessons.md if anything new is learned in the source-row authoring loop.

The deferral is justified because: (a) Path A would have stalled the Phase B + Phase C unblock waiting on source authoring (Phase A's mandate was "unblock the port"); (b) Phase A.5 is a focused-scope schema-bump PR that can be reviewed with full Hans-Governance attention on sourcing rigour; (c) the existing v1.1 schema already permits `additionalProperties: true` for forward compatibility, so the Phase A rows are not invalid against v1.1 today — adding `source_id` later is genuinely additive.

**Phase B — port the 4 backend consumers (mechanical repoint). ✅ COMPLETE.** See top-of-doc status block. The handover's original filter pseudo-code (`entity_type IN ('state','union_territory')`) was a typo discovered during Phase B execution: `entities.json` actually uses `"ut"` (not `"union_territory"`) for the `entity_type` enum. The implemented wrapper applies `entity_type IN ('state','ut') AND entity_valid_to IS NULL` and translates `ut → union_territory` only where the downstream consumer (e.g. `coverage.py`'s UT-without-assembly filter, `core/models.py StateEntry.kind` Literal) requires the legacy string for behavioural parity.

Original step list, preserved for reference:

1. `backend/yen_gov/coverage.py::STATES_REL` switch to `datasets/taxonomy/entities.json` + add filter `entity_type IN ('state','union_territory') AND entity_valid_to IS NULL`.
2. `tools/lgd/backfill_lgd_codes.py::STATES_JSON` same switch.
3. `backend/yen_gov/sources/india_geodata/power_plants.py` same switch (and update the name→ECI map loader).
4. `backend/tests/test_datasets_integrity.py::STATES_REGISTRY_PATH` same switch.
5. New `backend/tests/test_states_parity.py` (real-data, not mocked, per `/memories/lessons.md` 2026-05-19 parity-oracle pattern): asserts every `(eci_code, name)` pair in legacy states.json matches the projection from `taxonomy/entities.json`. Acts as a guard that any future taxonomy edit doesn't drift the citizen-shown name.

**Phase C — frontend port + legacy file delete (browser-smoke MANDATORY).**

1. New `frontend/src/lib/view-models/states.ts::loadStates()` mirroring `loadDistricts` shape; DuckDB-WASM query `WHERE entity_type IN ('state','union_territory') AND entity_valid_to IS NULL`.
2. Delete `frontend/src/lib/data.ts::fetchStates`, `StatesCollection`, `StateEntry` exports. Update `data.test.ts` (skip retired tests).
3. Update consumers: `frontend/src/routes/Home.svelte`, `StateTopic.svelte`, `frontend/src/lib/states.svelte.ts`.
4. Browser smoke: `/india`, `/india/<state>` for each of 5 sampled states (TN, KL, BR, DL, JK-UT) + 1 UT to verify UT chrome.
5. `git rm datasets/reference/in/states.json datasets/schemas/state.schema.json`.
6. Remove `StatesCollection` + `StateEntry` from `backend/yen_gov/core/models.py`.
7. Ledger row recording the migrate.

**Phase D — closeout & memory bump.**

1. Update `/memories/repo/yen-gov-architecture.md` T.0c-ii series with the final SHA.
2. Delete this handover doc (work complete).

## Audit-script (re-creatable if needed)

```python
# tools/inspect_states_parity.py — DELETED 2026-05-21. Re-create when needed:
import json, pathlib
repo = pathlib.Path(".")
states = json.loads((repo / "datasets/reference/in/states.json").read_text(encoding="utf-8"))
entities = json.loads((repo / "datasets/taxonomy/entities.json").read_text(encoding="utf-8"))
ent_by_code = {e["entity_code"]: e for e in entities["entities"] if e["entity_type"] in ("state", "union_territory")}
missing = [s["eci_code"] for s in states["states"] if s["eci_code"] not in ent_by_code]
extra = [c for c in ent_by_code if c not in {s["eci_code"] for s in states["states"]}]
print(f"states.json: {len(states['states'])} entries; entities state+UT: {len(ent_by_code)}; missing: {missing}; extra: {extra}")
```

## Cross-references

- Plan: TODO/20260517-canonical-long-format-pivot.md §0e row 312 (states.json: DELETE → subsumed by entity_type='state'/'union_territory' in taxonomy/entities.parquet).
- Lessons: `/memories/lessons.md` 2026-05-19 (parity-oracle pattern), 2026-05-16 (provenance-is-data), 2026-05-17 (folded-indicator pattern — same instinct applies to taxonomy rows).
- Prior PRs in this arc: #69 (T.0c-ii-A orphan sweep), #70 (B.1 unmapped_regions), #71 (B.2 districts view-model), #72 (iced-chart-titles), #73 (lgd-csv-repoint).
- Constitution / legal sources to cite (do NOT cite Wikipedia):
  - https://www.indiacode.nic.in/ — for State Reorganisation Act 1956, Punjab Reorganisation Act 1966, Constitution (Fourteenth Amendment) 1962, Constitution (Sixty-ninth Amendment) 1991, J&K Reorganisation Act 2019, DNH-DD Merger Act 2019.
  - https://prsindia.org/billtrack — for legislation summaries with bill-text URLs.

---

**Disposition:** This doc is the handover. No code shipped. Branch `feat/canonical-pivot-T0c-ii-states-json-port` was deleted (it had no commits). The autonomous session ends here; PR 4 (constituencies D1 widen) also hit autonomous-unsafe limits (browser smoke MANDATORY per repo memory) and was not attempted.
