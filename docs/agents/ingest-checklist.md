# Ingest checklist (agent-followable)

**Last Updated**: 2026-05-27

> **Pipeline name**: This checklist gates entry to the **ingest** pipeline (Fetch -> Enrich -> Publish). When an agent is asked to add a new data source, run `python -m yen_gov pre-flight-ingest` first, then follow [docs/how-to/add-a-new-data-source.md](../how-to/add-a-new-data-source.md).

> Mechanical checklist for any agent shipping a new ingest. Replaces the bare `check-overlap` invocation in [TODO/_TEMPLATE-ingest-handover.md](../../TODO/_TEMPLATE-ingest-handover.md) §3 with a single batched pre-flight gate. Defined by [ADR-0046](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract).

## Step 1 -- author a proposal file

Drop a JSON file next to your handover-doc:

```
TODO/<YYYYMMDD>-<source>-ingest/
  proposal.json        # the input to the gate
  report.json          # the output (committed alongside)
  handover.md          # the human-readable handover
```

`proposal.json` shape (all 11 fields REQUIRED):

```json
{
  "proposed_id": "livestock-pashu-aadhaar-count",
  "family": "livestock",
  "concept": "pashu aadhaar tag count",
  "unit": "count",
  "normalisation": "absolute",
  "entity_kind": "district",
  "source_producer": "NDLM",
  "source_title": "Pashu Aadhaar registry",
  "source_vintage": "2024-25",
  "update_period_days": 30,
  "justification": "per-animal UID coverage at district grain; not a head-count rollup"
}
```

Optional fields: `concept_id` (FK to `concepts.json` if the verdict will be `upsert` / `add_facet`), `source_id` (only if you want the gate to verify it matches `derive_source_id` exactly).

## Step 2 -- run the gate

```bash
python -m yen_gov pre-flight-ingest \
  --proposal-file TODO/<YYYYMMDD>-<source>-ingest/proposal.json \
  --report        TODO/<YYYYMMDD>-<source>-ingest/report.json
```

Read the exit code:

| code | meaning | next step |
|---|---|---|
| 0 | pass | proceed to step 3 |
| 1 | soft warn | proceed; document the warning in the handover §3 |
| 2 | hard fail | STOP; correct the proposal and re-run |

There is no override flag. Per CLAUDE.md Holy Law #5, if the gate fails the proposal is wrong, not the gate.

## Step 3 -- act on the verdict

```
mermaid
flowchart TD
  A[report.verdict] --> B{which?}
  B -- mint_new --> C[author new row in indicators.json<br/>+ new row in concepts.json in SAME PR]
  B -- upsert --> D[UPSERT new vintage / publisher<br/>into existing indicator_id]
  B -- add_facet --> E[add facet axis on existing<br/>indicator_id; do NOT mint a new id]
  B -- abort --> F[STOP -- correct proposal, re-run]
```

The report's `recommended_action.target_indicator_id` names the existing id you must UPSERT or facet into when the verdict is not `mint_new`.

## Step 4 -- cite the report in the handover

In [TODO/_TEMPLATE-ingest-handover.md](../../TODO/_TEMPLATE-ingest-handover.md) §3 paste:

```markdown
**Pre-flight report**: [report.json](./report.json)
**Verdict**: <mint_new|upsert|add_facet>
**Target indicator_id** (if not mint_new): `<id>`
```

The CI `indicator-add-gate` workflow checks any `proposal.json` shipped under `TODO/` and rejects the PR if its `report.json` carries verdict `abort`.

## What the six checks ask

| # | check | meaning |
|---|---|---|
| 1 | `concept_overlap` | does an existing concept score >= 0.70 against your proposal? |
| 2 | `concept_fk` | if you supplied `concept_id`, does it resolve in `concepts.json`? |
| 3 | `grain_prefix` | does `proposed_id` carry a `state-/district-/national-` prefix? (must not — ADR-0044) |
| 4 | `update_period_days` | did you declare cadence as a positive integer? (per guardrail #18) |
| 5 | `justification` | is `justification` >=20 chars naming the distinguishing dimension? |
| 6 | `source_id_derivation` | if you supplied `source_id`, does it match `derive_source_id(producer, title, vintage)`? |

See [docs/concepts/pre-flight-ingest.md](../concepts/pre-flight-ingest.md) for the full semantics.

## See also

- [docs/concepts/pre-flight-ingest.md](../concepts/pre-flight-ingest.md)
- [docs/architecture/backend/preflight.md](../architecture/backend/preflight.md)
- [ADR-0046](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)
- [docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md)
