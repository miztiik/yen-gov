# Pre-flight ingest gate

**Last Updated**: 2026-05-27

> ONE command to run before any new ingest. Replaces six previously-manual checks with one batched gate that emits a typed report. Defined by [ADR-0046](../architecture/decisions/0046-pre-flight-ingest-gate-contract.md).

## When to run it

Run `python -m yen_gov pre-flight-ingest` BEFORE you author any of:

- a new row in `datasets/taxonomy/indicators.json`
- a new adapter under `backend/yen_gov/sources/<source>/`
- a new meadow tree under `datasets/<family>/_meadow/<source>/<vintage>/`

If the gate exits with code 2, the proposal is wrong — correct it and re-run. There is no override flag (CLAUDE.md Holy Law #5).

## The six checks

| # | check | what it asks |
|---|---|---|
| 1 | `concept_overlap` | does the proposed concept already exist in `datasets/taxonomy/concepts.json`? |
| 2 | `concept_fk` | if the proposal declares a `concept_id`, does it resolve in the registry? |
| 3 | `grain_prefix` | is the proposed `indicator_id` free of `state-/district-/national-` prefix (ADR-0044)? |
| 4 | `update_period_days` | does the proposal declare a positive integer refresh cadence? |
| 5 | `justification` | does `meta.justification` carry a >=20-char string naming the distinguishing dimension? |
| 6 | `source_id_derivation` | if a `source_id` is supplied, does it match `derive_source_id(producer, title, vintage)` exactly? |

The six predicates live in [backend/yen_gov/preflight/predicates.py](../../backend/yen_gov/preflight/predicates.py) and are re-used by the Tier-B validators in [backend/yen_gov/validate.py](../../backend/yen_gov/validate.py) — a parity test guarantees the two seams cannot drift.

## Exit codes

| code | meaning | agent action |
|---|---|---|
| 0 | pass | proceed; cite the report path in the handover-doc |
| 1 | soft warn | proceed with the named concern (e.g. `mint_new` without a new concepts.json row in the same PR) |
| 2 | hard fail | abort; correct proposal and re-run |

## Verdict ladder

| verdict | when | next step |
|---|---|---|
| `mint_new` | no existing concept scores >= 0.70 | author a new `indicator_id` AND a new row in `concepts.json` in the same PR |
| `upsert` | existing concept scores >= 0.85 across noun + unit + normalisation + entity_kind | UPSERT into the existing indicator (new vintage or new publisher of the same fact) |
| `add_facet` | existing concept scores >= 0.70 on noun + unit + normalisation | add a facet axis on the existing indicator instead of minting a new id |
| `abort` | any hard-fail check | correct and re-run; no override |

## Report shape

The report is JSON validated against [preflight-report.schema.json](../../datasets/schemas/preflight-report.schema.json) v1.0. Two runs against the same input produce byte-identical reports — `generated_at` is a deterministic hash of `input_echo`, NOT a wall-clock timestamp.

```json
{
  "schema_version": "1.0",
  "verdict": "mint_new",
  "recommended_action": {
    "kind": "mint_new",
    "target_indicator_id": null,
    "target_parquet_path": "datasets/livestock/livestock_<role>.parquet",
    "rationale": "no concept overlap >= 0.70; proceed with mint_new"
  },
  "checks": [
    {"name": "concept_overlap", "status": "pass", "evidence": "...", "doc_link": "docs/concepts/pre-flight-ingest.md"}
  ],
  "input_echo": {"proposed_id": "livestock-foo-count", "family": "livestock", "...": "..."},
  "generated_at": "preflight:sha256:abcdef0123456789"
}
```

## How agents cite it

Drop the proposal next to the handover-doc as `TODO/<date>-<source>-ingest/proposal.json`. Run the gate; commit the report alongside. The handover-doc §3 cites both paths. CI's `indicator-add-gate` workflow validates that any `proposal.json` shipped under `TODO/` has a report with verdict != `abort`.

## See also

- [ADR-0046](../architecture/decisions/0046-pre-flight-ingest-gate-contract.md) — the contract
- [docs/architecture/backend/preflight.md](../architecture/backend/preflight.md) — module layout
- [docs/agents/ingest-checklist.md](../agents/ingest-checklist.md) — the checklist with literal commands
- [docs/concepts/ingest-fetch-enrich-separation.md](ingest-fetch-enrich-separation.md) — the layered pipeline this gate fronts
- [docs/concepts/owid-alignment.md](owid-alignment.md) — concept identity doctrine
