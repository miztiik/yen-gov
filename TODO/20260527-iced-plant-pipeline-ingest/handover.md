# 2026-05-27 ICED plantPipelineInfo ingest handover

**Last Updated**: 2026-05-27

> First ICED ingest through the four-layer doctrine ([docs/concepts/ingest-fetch-enrich-separation.md](../../docs/concepts/ingest-fetch-enrich-separation.md)) and the [ADR-0046](../../docs/architecture/decisions/0046-pre-flight-ingest-gate-contract.md) pre-flight gate. PR: #_pending_ — ships layers **1 (Fetch) + 2 (Parse)** end-to-end, plus the proposal + report that pin the `mint_new` verdict. Layers 3 (Enrich) + 4 (Emit) are deferred to a follow-up PR with structural pre-conditions documented in §5.

## 1. Source

- **Publisher**: NITI Aayog — India Climate & Energy Dashboard (ICED), `https://iced.niti.gov.in/energy/electricity/capacity/upcoming` (API: `https://icedapi.niti.gov.in/v1/plantPipelineInfo`)
- **Vintage / cadence**: monthly refresh (publisher heuristic — set `update_period_days=30`)
- **License**: [Government of India Open Data License](https://www.data.gov.in/government-open-data-license-india)
- **Sampling frame / methodology**: under-construction generation capacity (thermal pipeline) by expected commissioning calendar-year. AES-encrypted envelope (`U2FsdGVkX1…` salted-base64); `IcedClient.get(..., decrypt=True)` returns the plaintext payload. Prior session memory stated "plaintext JSON (no crypto envelope)" — VERIFIED INCORRECT 2026-05-27; the endpoint IS encrypted.

## 2. Scope

- **Concept measured**: under-construction generation capacity (pipeline)
- **Unit canonical**: `GW` (raw value magnitudes 0.45 to 8.52 match GW for India-wide annual additions)
- **Normalisation**: `absolute`
- **Entity grain**: `country` (single `entity_id="IN"`; no per-state breakdown)
- **Time range**: 2011-2031 calendar-year (publisher skips 2022 — gap preserved verbatim)
- **Facet axis**: status, two values verbatim
  - `"Under Construction and likely to be commissioned"`
  - `"Under Construction but on Hold"`
- **Row count (live recon)**: 20 years × 2 status = 40 rows

## 3. Concept overlap audit

- **Proposal**: [proposal.json](./proposal.json)
- **Report**: [report.json](./report.json)
- **Verdict**: `mint_new`
- **Exit code**: 1 (soft-warn on `concept_fk` — expected for mint_new; will be cleared when the follow-up PR adds the row in `datasets/taxonomy/concepts.json`)

The six-check breakdown landed in `report.json`:

| # | check | status | note |
|---|---|---|---|
| 1 | `concept_overlap` | pass | no existing concept scores >= 0.70 |
| 2 | `concept_fk` | warn | proposal has no `concept_id` yet; mint_new requires a new row in concepts.json in the same PR (deferred to follow-up — see §5) |
| 3 | `grain_prefix` | pass | `under-construction-capacity-gw` carries no `state-/district-/national-` prefix |
| 4 | `update_period_days` | pass | 30 (monthly cadence) |
| 5 | `justification` | pass | length 427 |
| 6 | `source_id_derivation` | pass | proposal omits hand-typed `source_id` (correct — adapter will derive via `derive_source_id`) |

## 4. Identifiers (planned for follow-up PR)

- **`indicator_id`**: `under-construction-capacity-gw` (kebab-case; no grain prefix per [ADR-0044](../../docs/architecture/decisions/0044-grain-over-entity.md); country grain lives on each row's `entity_id="IN"`)
- **`concept_id`** (to be added): `under-construction-capacity`
  - `noun`: "Under-construction generation capacity"
  - `unit_canonical`: `GW`
  - `normalisation`: `absolute`
  - `entity_kinds`: `["country"]`
- **`source_id`**: derived via `backend.yen_gov.canonical.citation.derive_source_id("iced", "plantPipelineInfo", "2026-05-27")`
- **`update_period_days`**: 30

## 5. Pipeline plan + this-PR scope

This PR ships **layers 1 + 2 + the pre-flight gate run**. Layers 3 + 4 are deferred because the canonical writer for the energy family is gated to five existing envelope stems and adding a sixth is structural work beyond this PR's budget.

### Shipped in this PR

- **Layer 1 (Fetch)** — [backend/yen_gov/sources/iced_power/fetch_pipeline.py](../../backend/yen_gov/sources/iced_power/fetch_pipeline.py): thin live-fetch helper. Persists to `datasets/energy/_meadow/iced/<vintage>/plant_pipeline_info.json` where `<vintage>` is the upstream `Last-Modified` (ADR-0041 grammar). Verified live 2026-05-27 (vintage `2026-05-27`, 20-year × 2-status payload, ~480 bytes decrypted). The meadow snapshot is NOT committed in this PR because the meadow tier validator requires a matching `(producer, vintage)` row in `datasets/taxonomy/sources.parquet`, which is part of the follow-up PR's citation work (§5 item 4); committing the snapshot here would land a Tier-B failure. The follow-up PR will run the helper to produce the snapshot in the same commit as the citation row.
- **Layer 2 (Parse)** — `parse_plant_pipeline_info(decrypted)` appended to [backend/yen_gov/sources/iced_power/parsers.py](../../backend/yen_gov/sources/iced_power/parsers.py). Pure function over the decrypted dict; returns `list[dict]` of `(entity_id, time, value, facet)` rows with `entity_id="IN"`, calendar-year `time`, status facet. 5 unit tests in [backend/tests/test_sources_iced_power.py](../../backend/tests/test_sources_iced_power.py) cover the happy path, publisher year-gap preservation (2022 skip), non-dict / missing-keys errors, malformed series-entry skip.
- **Pre-flight gate** — proposal + report committed adjacent to this handover. `mint_new` verdict pinned.

### Deferred to follow-up PR (layers 3 + 4)

Structural pre-conditions (Level-4 per CLAUDE.md §6) that must land together:

1. **New concept row** in `datasets/taxonomy/concepts.json` with `concept_id: "under-construction-capacity"` (clears the §3 `concept_fk` warn).
2. **New indicator row** in `datasets/taxonomy/indicators.json` with `indicator_id: "under-construction-capacity-gw"`, `concept_id` FK, `update_period_days: 30`, source pointer.
3. **New canonical-store envelope** in `backend/yen_gov/canonical/adapters/energy/` (new module `capacity_pipeline.py`) registered in `__init__.py:build_envelopes`. The existing five envelope modules range 6-18 KB each; this sixth follows the same shape.
4. **New canonical parquet stem** `datasets/energy/energy_capacity_pipeline.parquet` — added to the canonical-allowlist and the writer's stem registry. `lift-energy --table energy_capacity_pipeline` will produce it.
5. **Enrich layer** — `backend/yen_gov/sources/iced_power/ingest.py` extension or a new `ingest_pipeline.py`: call `fetch_plant_pipeline_info()` → `parse_plant_pipeline_info()` → derive `source_id` via `lookup_source_id` (never hand-type per CLAUDE.md §12) → write via canonical writer.
6. **Tier-B gates** — all 5 LIVE tier-B checks (concept FK, grain prefix, update_period_days, justification, one-indicator-per-concept) re-run on the new row.
7. **Integration test** — idempotency proof: run `lift-energy --table energy_capacity_pipeline` twice; assert the second run is a no-op.
8. **`datasets/_ops/meadow-shard-contract.txt`** — add the new meadow file path.
9. **Optional frontend allowlist** — defer unless a topic page surfaces the indicator.

### Why split here

- The fetch + parse layers are GENUINELY independent of layers 3 + 4 per the [4-layer doctrine](../../docs/concepts/ingest-fetch-enrich-separation.md) — they can land alone, be tested alone, and unblock the follow-up.
- The structural work to add a sixth canonical envelope + parquet stem to `lift-energy` is Level-4 and warrants a dedicated PR with explicit Hans + Gregor sign-off on the new stem (one-concept-per-parquet vs UPSERT-into-`energy_installed_capacity.parquet` is a load-bearing design call).
- The pre-flight verdict is pinned in this PR and survives unchanged into the follow-up (`generated_at` is a deterministic hash of `input_echo` per ADR-0046).

## 6. Acceptance gates (this PR)

- [x] G1 `python -m yen_gov validate --root .` OK
- [x] G2 targeted pytest: `test_sources_iced_power.py` (13 passed: 8 pre-existing + 5 new) + `test_preflight_*.py` + parser_kit
- [x] G4 pre-flight re-run against committed `proposal.json`: verdict `mint_new`, exit 1 (soft-warn `concept_fk` — expected)
- N/A G3 / G5 — no frontend changes

## 7. Open questions for the follow-up PR

- Should the new stem be `energy_capacity_pipeline` (standalone) or a UPSERT into `energy_installed_capacity.parquet` with a `status` facet column? Recommend STANDALONE (under-construction is a fundamentally different physical state from commissioned per [ADR-0044](../../docs/architecture/decisions/0044-grain-over-entity.md) concept-identity doctrine).
- Confirm unit is `GW` not `MW` (current evidence: values 0.45-8.52 match GW for India-wide annual additions; the dashboard page would settle it definitively).
- Should the publisher's `2022` year-gap be filled with `null` rows or left absent? Recommend ABSENT (current parser behavior) — schema readers should treat missing years as missing data, not zero.

## 8. References

- [docs/concepts/ingest-fetch-enrich-separation.md](../../docs/concepts/ingest-fetch-enrich-separation.md) — 4-layer doctrine
- [docs/concepts/pre-flight-ingest.md](../../docs/concepts/pre-flight-ingest.md) — gate concept
- [ADR-0046](../../docs/architecture/decisions/0046-pre-flight-ingest-gate-contract.md) — gate contract
- [ADR-0044](../../docs/architecture/decisions/0044-grain-over-entity.md) — grain on row, not id
- [ADR-0041](../../docs/architecture/decisions/0041-meadow-tier.md) — meadow tier
- [docs/agents/ingest-checklist.md](../../docs/agents/ingest-checklist.md)
- [backend/yen_gov/sources/iced_common/endpoints.py](../../backend/yen_gov/sources/iced_common/endpoints.py) line 180 — endpoint catalogue entry
