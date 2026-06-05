# Add a new data source

Last Updated: 2026-05-27

> **Pipeline name**: The four-layer ingest workflow described here is called **the Lift pipeline** (the verb `lift` matches the existing `python -m yen_gov lift-<family>` CLI). When asked to "lift a new data source" or "run X through the Lift", read this cookbook first.

Cookbook for adding a new upstream data source (REST endpoint, XLSX
workbook, PDF, web scrape) to yen-gov via the 4-layer ingest doctrine.
Terse by design: cross-links over duplication.

## 1. When to use this guide

- You want to ingest a NEW upstream data source -- one REST endpoint OR
  one XLSX workbook OR one scrape target -- as its own PR.
- Each upstream artifact lands as ITS OWN PR via the 4-layer pattern in
  [docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md).

Do NOT use this guide for:

- Adding a new column / facet to an EXISTING canonical adapter -- edit
  the adapter directly; no new family folder needed.
- Schema work (bumping `datasets/schemas/*.schema.json` versions) --
  that is ADR-grade; see [docs/reference/decision-index.md](../reference/decision-index.md)
  for the full ADR redirect map (the legacy `docs/architecture/decisions/` tier was retired in D-DOC3.10 closure 2026-06-05; rationale + rejected alternatives live as `## Design rationale` + `## Rejected alternatives` sections inside subsystem and concept docs).

## 2. Prerequisites

1. Read [docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md)
   (the 4 layers: Fetch -> Parse -> Enrich -> Emit).
2. Read [docs/agents/ingest-checklist.md](../agents/ingest-checklist.md)
   (pre-flight agent checklist).
3. Run `python -m yen_gov pre-flight-ingest --help` to see the gate.
4. Check whether the source family already has an adapter under
   `backend/yen_gov/sources/<family>/`. If yes, this guide is for ADDING
   a new endpoint to that family. If no, you will create the family
   folder fresh.
5. Know the upstream cadence (for `update_period_days`) and have one
   sample raw response or workbook download for shape recon.

## 3. Step 1 -- Write `proposal.json` + run pre-flight

Place the proposal at `TODO/<YYYYMMDD>-<slug>-ingest/proposal.json`.
Use [TODO/20260527-iced-plant-pipeline-ingest/proposal.json](../../TODO/20260527-iced-plant-pipeline-ingest/proposal.json)
as a literal worked example.

Run the gate:

```powershell
$env:PYTHONPATH = "$pwd\backend"
python -m yen_gov pre-flight-ingest `
  --proposal-file TODO/<slug>/proposal.json `
  --report TODO/<slug>/report.json
```

Decision tree on `verdict` (see [docs/concepts/pre-flight-ingest.md](../concepts/pre-flight-ingest.md)
and [ADR-0046](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)
for exit-code semantics):

- `mint_new` -- proceed; create new `indicator_id`.
- `upsert` -- proceed; UPSERT rows into an existing indicator (no new id).
- `add_facet` -- proceed; add a facet axis to an existing indicator.
- `abort` -- STOP. Exit code 2. No override flag (Holy Law #5). Fix the
  failing predicate or escalate; do NOT write code yet.

Commit the proposal + report into the PR.

## 4. Step 2 -- Scaffolding

Branch on the upstream shape. The Enrich + Emit layer is shared.

### REST endpoint (new endpoint in an `iced_*` family or similar)

```
backend/yen_gov/sources/<family>/
  __init__.py
  client.py                   # may already exist; reuse iced_common.client
  fetch_<endpoint>.py         # NEW; mirror iced_power/fetch_pipeline.py
  parsers.py                  # extend with parse_<endpoint>()
backend/yen_gov/canonical/adapters/<family>/
  <topic>.py                  # NEW; enrich + emit layer
backend/tests/
  test_sources_<family>_<endpoint>.py
datasets/<family>/_meadow/<source>/<vintage>/
  <endpoint>.json             # raw meadow snapshot (layer 1 output)
```

### XLSX workbook (e.g. new RBI workbook)

```
backend/yen_gov/sources/<source>/
  urls.py                     # URL registry, env override, local cache
  parsers.py                  # XLSX cell extraction
  ingest.py                   # orchestrator
backend/yen_gov/canonical/adapters/<family>/
  <topic>.py                  # shared enrich + emit layer
backend/tests/test_sources_<source>_*.py
```

See [docs/architecture/backend/sources-rbi.md](../architecture/backend/sources-rbi.md)
for the XLSX reference; `backend/yen_gov/sources/rbi_hbs/` is the canonical
implementation.

## 5. Step 3 -- Imports to copy verbatim

Every line below was grep-verified against `backend/yen_gov/` on
2026-05-27. If you need an API not listed here, grep the codebase first;
do not invent.

Layer 1 (Fetch) -- REST:

```python
from yen_gov.sources.iced_common.client import IcedClient, API_HOST_DEFAULT
from yen_gov.core.io import Source, write_artifact
```

Layer 1 (Fetch) -- generic HTTP (XLSX, PDF, datagov):

```python
from yen_gov.core.http import Fetcher, FetchResult
from yen_gov.core.io import Source, write_artifact
```

Layer 2 (Parse) -- pure functions; no I/O imports beyond `json` /
`openpyxl`. Tested in isolation against meadow fixtures.

Layer 3 + 4 (Enrich + Emit) -- always:

```python
from yen_gov.canonical.citation import derive_source_id, lookup_source_id
from yen_gov.canonical.writer import write_batch, WriteResult
from yen_gov.canonical.state_lgd_resolver import load_state_lgd_to_eci_map
from yen_gov.canonical.concept_registry import find_overlap
```

Taxonomy seed extensions (rare -- only if your source introduces a new
source row, new concept, or new topic; otherwise the existing seeds
absorb your indicator by FK):

```python
# backend/yen_gov/canonical/<family>_sources_seed.py
from yen_gov.canonical.citation import derive_source_id
```

## 6. Step 4 -- Wire into `lift-<family>` CLI

The lift command per family dispatches on a target-table-stem registry.
See [docs/architecture/backend/lifting.md](../architecture/backend/lifting.md)
and `cli.py` `@app.command("lift-energy")` for the reference shape.

Add your new fact-table stem to the family registry (e.g.
`FAMILY_FACT_TABLE_STEMS` in `backend/yen_gov/canonical/adapters/<family>/__init__.py`)
and wire the adapter callable. PR #420 is a worked example for energy.

## 7. Step 5 -- Run the lifecycle locally

```powershell
$env:PYTHONPATH = "$pwd\backend"

# Gate
python -m yen_gov pre-flight-ingest --proposal-file TODO/<slug>/proposal.json --report TODO/<slug>/report.json

# Layer 1 + 2 (per-family ingest module; iced_power/ingest.py style)
python -m yen_gov.sources.<family>.fetch_<endpoint>     # or run the ingest module

# Layer 2 in isolation
python -m pytest backend/tests/test_sources_<family>_<endpoint>.py -q

# Layer 3 + 4 (canonical writer)
python -m yen_gov lift-<family> --table <new_stem>

# Taxonomy + completeness regen
python -m yen_gov emit-taxonomy
python tools/emit_indicators_completeness_index.py --write

# Validator (Tier-A in pytest; Tier-B on demand)
python -m yen_gov validate --root .
```

## 8. Step 6 -- Pre-flight re-run + ship

- Re-run the gate against the committed `proposal.json`; verdict + exit
  code should be clean.
- Suggested commit cadence (4 commits, squash on merge):
  1. Layer 1 (Fetch) + meadow snapshot
  2. Layer 2 (Parse) + parser tests
  3. Layer 3 + 4 (Enrich + Emit) + adapter tests + lift wiring
  4. PR# stamp (plan-doc / handover-doc replaces `#_pending_`)
- `gh pr create` then `gh pr merge <#> --squash --delete-branch`.

## 9. Anti-patterns (Holy Law #5)

- Do NOT hand-type a `source_id` -- use
  `lookup_source_id()` / `derive_source_id()`.
- Do NOT use `datetime.now()` anywhere in an observation row
  (CLAUDE.md sec 10; [docs/concepts/data-provenance.md](../concepts/data-provenance.md)).
- Do NOT prefix `state-` / `district-` / `national-` / `country-` on any
  new `indicator_id` (ADR-0044). Grain lives on `entity_kind`.
- Do NOT create a new parquet stem when the verdict is `upsert` or
  `add_facet` -- UPSERT into the existing fact table.
- Do NOT mint a new `indicator_id` when concept-overlap is >= 0.70 --
  the gate will already say `upsert` or `add_facet`.
- Do NOT skip pre-flight (the gate IS the protocol; ADR-0046).
- Do NOT edit `backend/yen_gov/validate.py` or
  `backend/yen_gov/preflight/predicates.py` to silence a failure --
  fix the data or the proposal.
- Do NOT create files under the retired
  `datasets/indicators/in/<topic>/<id>.json` path (ADR-0041); new
  meadow snapshots go to `datasets/<family>/_meadow/<source>/<vintage>/`.

## 10. Worked examples

- REST end-to-end (mint_new, country-aggregate facet):
  PR #419 (Fetch + Parse) -> PR #420 (Enrich + Emit). Files:
  `backend/yen_gov/sources/iced_power/fetch_pipeline.py`,
  `backend/yen_gov/sources/iced_power/parsers.py`,
  `backend/yen_gov/canonical/adapters/energy/capacity_pipeline.py`.
- XLSX end-to-end: `backend/yen_gov/sources/rbi_hbs/` plus
  [docs/architecture/backend/sources-rbi.md](../architecture/backend/sources-rbi.md).

## 11. See also

- [docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md)
- [docs/agents/ingest-checklist.md](../agents/ingest-checklist.md)
- [docs/concepts/pre-flight-ingest.md](../concepts/pre-flight-ingest.md)
- [docs/architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)
- [docs/architecture/backend/preflight.md](../architecture/backend/preflight.md)
- [docs/architecture/backend/overview.md](../architecture/backend/overview.md)
- [docs/architecture/backend/pipeline.md](../architecture/backend/pipeline.md)
- [docs/architecture/backend/lifting.md](../architecture/backend/lifting.md)
- [docs/architecture/backend/writer.md](../architecture/backend/writer.md)
- [docs/architecture/backend/core.md](../architecture/backend/core.md)
- [docs/architecture/backend/sources-iced-api.md](../architecture/backend/sources-iced-api.md)
- [docs/architecture/backend/sources-rbi.md](../architecture/backend/sources-rbi.md)
- [TODO/_TEMPLATE-ingest-handover.md](../../TODO/_TEMPLATE-ingest-handover.md)
- [CLAUDE.md](../../CLAUDE.md) sections 5, 10, 12
