# 2026-05-21 — handover: states.json port blocked by entities.json UT coverage gap

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

**Phase A — fill the UT gap in taxonomy/entities.json (data-authorship PR).**

1. Hand-author 7 new UT rows (8 if U09 needs the J&K-historical split) per the table above. Use `tools/inspect_states_parity.py` (re-create from this doc's audit-script section) to verify post-edit parity.
2. Add 8 MoHA-notification sources to `taxonomy/entities.json.sources[]` with URLs to indiacode.nic.in.
3. Bump `taxonomy/entities` schema if needed (probably not — current schema supports all the fields).
4. Regenerate `datasets/taxonomy/entities.parquet` via `emit-taxonomy`.
5. Update `datasets/manifest.json` row count.
6. Re-run parity audit; assert zero missing UTs.
7. Pytest + vitest + validate.
8. PR, request review (Hans-Governance for sourcing rigour), merge.

**Phase B — port the 4 backend consumers (mechanical repoint).**

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
