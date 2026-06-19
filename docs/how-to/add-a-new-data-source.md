# Add a new data source

Last Updated: 2026-06-19

Cookbook for adding a new upstream data source (REST endpoint, XLSX workbook,
PDF, web scrape) to yen-gov via the `ingest` pipeline. The pipeline is
addressed by INDICATOR; a source adapter feeds it. Terse by design:
cross-links over duplication. The subsystem design is
[docs/architecture/ingest/pipeline.md](../architecture/ingest/pipeline.md); the
three-stage doctrine is
[docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md);
the CLI reference is [docs/reference/cli-ingest.md](../reference/cli-ingest.md).

The worked example throughout is `niti_sdg_index` (the NITI Aayog SDG India
Index) - the gold single-series greenfield adapter at
[backend/yen_gov/canonical/adapters/niti_sdg_index/](../../backend/yen_gov/canonical/adapters/niti_sdg_index/).

## 1. When to use this guide

- You want to ingest a NEW upstream data source -- one REST endpoint OR one
  XLSX workbook OR one scrape target -- as a new adapter feeding one or more
  indicators.
- Adding a new fuel / facet / publisher to an EXISTING indicator is NOT this
  guide -- that is an UPSERT into the existing series (see
  [docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md)
  "Enrich INTO the existing dataset").
- Schema work (bumping `datasets/schemas/*.schema.json` versions) is separate;
  rationale + rejected alternatives live as `## Design rationale` /
  `## Rejected alternatives` sections inside subsystem and concept docs (see
  [docs/reference/decision-index.md](../reference/decision-index.md)).

## 2. Prerequisites

1. Read the three-stage doctrine
   [docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md)
   (Fetch -> Enrich -> Publish + the run-preamble).
2. Read [docs/agents/ingest-checklist.md](../agents/ingest-checklist.md) (the
   author-time agent checklist).
3. Know the upstream cadence (for `update_period_days`) and have one sample
   raw response or workbook for shape recon.
4. Decide the SHAPE: single-series (one value per `(entity, time)` - most
   sources) goes through the shared `run_pipeline`; faceted (per-fuel /
   per-sector dimension columns) is the separate
   `yen_gov.sources.iced_power.ingest_pipeline` strategy.

## 3. Step 1 -- Design the indicator + clear the gates

Identity is what is MEASURED. Before any code, prove the fact is not already in
canonical and that the proposed id is well formed.

```powershell
# Focused overlap probe (does an existing concept already measure this?)
python -m yen_gov check-overlap --concept "SDG India Index score" --unit "score" --entity_kind "state"

# The full author-time gate (batches the six mechanical checks)
python -m yen_gov pre-flight-ingest `
  --proposal-file TODO/<slug>/proposal.json `
  --report TODO/<slug>/report.json
```

Decision tree on `verdict` (see
[docs/concepts/pre-flight-ingest.md](../concepts/pre-flight-ingest.md) and
[ADR-0046](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)):

- `mint_new` -- proceed; register a new concept + indicator (step 2).
- `upsert` / `add_facet` -- STOP this guide; UPSERT into the existing indicator.
- `abort` -- exit code 2, no override flag (Holy Law #5). Fix the proposal.

Commit the `proposal.json` + `report.json` into the PR.

## 4. Step 2 -- Register the identity (catalogue SOT)

The pipeline READS identity and never mints it, so the indicator + concept must
exist in the catalogue SOT before an orchestrated run will pass the
registration FK. The chain is `concepts.json -> indicators.json ->
variables.csv`:

- `datasets/taxonomy/concepts.json` -- the concept row: `(noun, unit_canonical,
  normalisation, entity_kinds)`, plus `price_basis` (current/constant + base
  year) for monetary concepts and `sampling_frame` for frame-bounded surveys.
- `datasets/taxonomy/indicators.json` -- the indicator row: `indicator_id`
  (`<measure>-<unit>-<facet>` kebab-case, NO grain prefix), `concept_id` FK,
  `update_period_days`, `source_id`.
- `datasets/data/variables.csv` + `datasets/data/concepts.csv` -- the compiled
  catalogue rows the frontend + validator read.

A single-series adapter does not hand-author these: `run_pipeline` UPSERTs the
`variables.csv` + `concepts.csv` rows for you from a `variable_row_builder`
callback + a `concept_row` dict (see `niti_sdg_index/ingest.py`
`_variable_row_builder` / `_concept_row`). You author the `concepts.json` +
`indicators.json` rows once, then `python -m yen_gov emit-taxonomy` compiles
them.

## 5. Step 3 -- Author the typed specs

A `SourceSpec` is the PARENT (the adapter + the provenance quartet); its
children are `IndicatorSpec` rows (the measurement tuple). No field repeats
across the two levels. `source_id` is DERIVED from `(producer, title,
vintage)`, never stored.

```python
from yen_gov.canonical.ingest.spec import IndicatorSpec, SourceSpec

SourceSpec(
    adapter_slug="niti-sdg-index",
    producer="NITI Aayog",          # the issuing authority that MEASURED it
    title="SDG India Index and Dashboard",
    vintage="2020-21",
    url="https://sdgindiaindex.niti.gov.in",
    indicators=(
        IndicatorSpec(
            indicator_id="sdg-india-index-score",
            unit="score",            # the CANONICAL unit (matched vs the concept)
            normalisation="index",
            price_basis=None,        # set for monetary concepts only
            sampling_frame=None,     # set for frame-bounded surveys only
        ),
    ),
)
```

Provenance doctrine (Holy Law #9): `producer` is the organisation that MEASURED
the fact. NITI Aayog ORIGINATES the SDG India Index, so the producer is
`"NITI Aayog"`. Where a source is a pure passthrough of an upstream authority
(the ICED case), the producer is that upstream and the re-publisher moves into
`title` -- decided per endpoint on cited evidence (D2; see
[docs/architecture/ingest/pipeline.md](../architecture/ingest/pipeline.md)).

## 6. Step 4 -- Implement the adapter

### Single-series (most sources) -- via `run_pipeline`

Thin: parse the staged/fetched payload, resolve labels to `entity_id`, hand the
long-format observations to `run_pipeline`. Pattern from `niti_sdg_index/ingest.py`:

```python
from yen_gov.canonical.ingest.run_pipeline import Citation, run_pipeline

observations = parse_sdg_index_csv(staged.read_bytes(), spec, resolver)
outcome = run_pipeline(
    repo_root=repo_root,
    indicator_id=spec.indicator_id,
    observations=observations,                # list[Observation(entity_id, time, value)]
    citation=Citation(producer=..., title=..., vintage=..., url=...),
    datapoints_mode="replace",                # "replace" (full series) or "upsert" (per-year)
    variable_row_builder=_variable_row_builder(spec),
    concept_row=_concept_row(spec),
)
```

`run_pipeline` derives the `source_id`, emits the long-format
`datapoints/geo/<id>.csv`, upserts the `source.csv` citation row, and upserts
the catalogue rows. `datapoints_mode="replace"` for a full-workbook caller that
owns every year; `"upsert"` for a per-year caller that emits one year and must
leave the others intact (the `rbi_hbs_health` cohort).

### Faceted (per-fuel / per-sector) -- separate strategy

A source whose values carry a dimension column (fuel, sector) does NOT go
through `run_pipeline`; it uses the faceted
`yen_gov.sources.iced_power.ingest_pipeline`. Folding faceted into the
single-series pipeline is explicit YAGNI (the two shapes are genuinely
different).

### Wire the adapter into the registry

Implement the `Adapter` protocol (`adapter_slug`, `source_specs()`,
`run_indicator(indicator_id, *, repo_root, config)`) and add the instance to
`default_registry()` in
[backend/yen_gov/canonical/ingest/registry.py](../../backend/yen_gov/canonical/ingest/registry.py).
Add the three `Fetchable` members (`cache_units_for`, `spec_version`,
`process_year`) ONLY if the source supports automated network fetch; an
operator-staged source (RBI Handbook, SDG India Index) stays a plain `Adapter`.
The orchestrator dispatches polymorphically and never branches on
`adapter_slug`.

## 7. Step 5 -- The honesty gates (what Enrich + Publish enforce)

Your adapter's Enrich + Publish must satisfy the fail-loud preconditions (the
engine raises if they are violated; do NOT silence them):

- **Six India-discontinuity ENRICH gates** -- bifurcation / state-lifespan,
  code-authority (LGD/Census/ECI), fiscal-vs-calendar year, provisional-vs-
  revised, price-basis, publisher-bounded-universe.
- **Divergence gate (Publish)** -- a second `source_id` overwriting a cell
  beyond the concept tolerance fails loud; record a `DivergenceResolution` to
  override.
- **Splice break-row gate (Publish)** -- a mid-series `source_id` change refuses
  to publish without a `methodology_breaks` row at the seam year.

See [docs/architecture/ingest/pipeline.md](../architecture/ingest/pipeline.md)
"The honesty doctrine" for the full rules.

## 8. Step 6 -- Run the lifecycle locally + ship

```powershell
# Gate (re-run against the committed proposal)
python -m yen_gov pre-flight-ingest --proposal-file TODO/<slug>/proposal.json --report TODO/<slug>/report.json

# Drive the indicator through the orchestrator (operator-staged sources need --staging-dir)
python -m yen_gov ingest run --indicator <indicator-id> --staging-dir ./.staging/<slug> --root .

# Coverage + per-source year spans + staleness
python -m yen_gov ingest status --indicator <indicator-id> --root .

# Taxonomy compile + validator (Tier-A in pytest; Tier-B on demand)
python -m yen_gov emit-taxonomy --root .
python -m yen_gov validate --root .
```

Ship per [docs/how-to/ship-a-pr.md](ship-a-pr.md): tests at the appropriate
tier, full suite green, `gh pr create` then `gh pr merge <#> --squash
--delete-branch`.

## 9. Anti-patterns (Holy Law #5)

- Do NOT hand-type a `source_id` -- it is DERIVED from `(producer, title,
  vintage)` by `derive_source_id` / `run_pipeline`.
- Do NOT use `datetime.now()` in an observation row (CLAUDE.md section 10;
  [docs/concepts/data-provenance.md](../concepts/data-provenance.md)).
- Do NOT prefix `state-` / `district-` / `national-` / `country-` on a new
  `indicator_id` ([ADR-0044](../concepts/indicator-naming.md#adr-0044-grain-over-entity));
  grain lives on `entity_kind`.
- Do NOT mint a new `indicator_id` for a new vintage / publisher / base-year --
  UPSERT into the existing series.
- Do NOT skip `pre-flight-ingest` (the gate IS the protocol; ADR-0046).
- Do NOT silence a gate by editing `validate.py` / the enrich gates -- fix the
  data or the proposal.
- Do NOT fold a faceted source into `run_pipeline`, and do NOT reintroduce a
  network fetcher in production -- automated fetch is the LOCAL pipeline only.

## 10. Worked examples

- Single-series greenfield (operator-staged CSV -> `run_pipeline`):
  [backend/yen_gov/canonical/adapters/niti_sdg_index/](../../backend/yen_gov/canonical/adapters/niti_sdg_index/)
  (`ingest.py` parse + `run_pipeline`; `NitiSdgIndexAdapter` registry wiring).
- Single-series XLSX (operator-staged workbook, multi-indicator source):
  `backend/yen_gov/canonical/adapters/rbi_handbook/` plus
  [docs/architecture/backend/sources-rbi-handbook.md](../architecture/backend/sources-rbi-handbook.md).
- Faceted (per-fuel dimension columns): `yen_gov.sources.iced_power.ingest_pipeline`.

## 11. See also

- [docs/architecture/ingest/pipeline.md](../architecture/ingest/pipeline.md)
- [docs/reference/cli-ingest.md](../reference/cli-ingest.md)
- [docs/concepts/ingest-fetch-enrich-separation.md](../concepts/ingest-fetch-enrich-separation.md)
- [docs/agents/ingest-checklist.md](../agents/ingest-checklist.md)
- [docs/concepts/pre-flight-ingest.md](../concepts/pre-flight-ingest.md)
- [docs/architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract](../architecture/backend/preflight.md#adr-0046-pre-flight-ingest-gate-contract)
- [docs/concepts/data-provenance.md](../concepts/data-provenance.md)
- [docs/concepts/indicator-naming.md](../concepts/indicator-naming.md)
- [TODO/_TEMPLATE-ingest-handover.md](../../TODO/_TEMPLATE-ingest-handover.md)
- [CLAUDE.md](../../CLAUDE.md) sections 5, 10, 12
