# Topic taxonomy

**Last Updated**: 2026-05-22

> **See also**:
>
> - [Canonical store §2a](../architecture/data/canonical-store.md) — naming convention for families and roles
> - [ADR-0030](../architecture/decisions/0030-canonical-store-duckdb-wasm.md) — D26 (facet-explode) and D29 (catalogue columns) including `topic_tags[]`
> - [ADR-0034](../architecture/decisions/0034-documentation-routing-contract.md) — doc-class routing rule under which this concept doc exists
> - [OWID alignment](owid-alignment.md) — the "One Rule" for socio-economic modelling
> - [Indicator naming](indicator-naming.md) — citizen URL slug rules (no topic prefix)

The **topic taxonomy** is yen-gov's flat catalogue of governance subject areas. Topics are tags on indicators, NOT a hierarchical directory structure. Each indicator carries a multi-valued `topic_tags[]` array (M:N relationship); each topic carries a stable machine slug plus a citizen-readable title.

## Why flat, not hierarchical

OWID's `topics.csv` is flat-with-multi-tag for a non-arbitrary reason: hierarchical taxonomies become contested politics. "Is GST devolution under *Money* or *Centre–state relations*?" has no right answer, and a tree forces one. Flat-with-multi-tag honestly carries both.

Hierarchy of citizen interest belongs to **indicator parents** (per ADR-0030 §D26, `parent_indicator_id`) — `installed-capacity-by-fuel-mw` is a child of `installed-capacity-total-mw` because the citizen's question "how much power capacity" cleanly decomposes into "by what fuel". Hierarchy at the topic level — "is electricity a sub-topic of energy or of infrastructure?" — is editorial weather, not invariant.

Therefore: `taxonomy/topics.parquet` is flat. `parent_topic_id` is rejected (per ADR-0030 §D-implied; locked at 2026-05-20 four-way concurrence in §0e.10.2.D of the canonical-pivot plan).

## Storage shape

| Layer | Path | Role |
| --- | --- | --- |
| Authored | `datasets/taxonomy/topics.json` | Hand-edited text source-of-truth per ADR-0030 D18 |
| Compiled | `datasets/taxonomy/topics.parquet` | Writer-emitted columnar form for DuckDB-WASM |
| Join table | `datasets/taxonomy/indicator_topic_tags.parquet` | M:N edges between indicators and topics |
| Projection | `topic_tags[]` column on `datasets/taxonomy/indicators.parquet` | Denormalised for fast catalogue browse |

The hand-authored JSON has two citizen-facing columns plus FK metadata:

```json
{
  "topic_id": "energy",
  "title": "Power & fuel",
  "description_short": "Electricity capacity, generation, consumption, losses; coal, oil, renewables.",
  "ordering": 4,
  "source_id": "src-..."
}
```

Renames touch the `title` column only; the slug (`topic_id`) is stable identity and never changes without a deprecation cycle.

## Citizen URL slugs do NOT carry topic prefix

Per ADR-0030 §D30 (indicator naming) and §0e.3 of the canonical-pivot plan, citizen URLs are `/indicator/<slug>` with no `/indicator/<topic>/<slug>`. Reason: topics are M:N. A single-parent slug is a lie about whichever parent loses ("installed-capacity-coal-mw" tags both `energy` and `environment`; the URL cannot say both). OWID is the precedent — its slugs are flat: `/grapher/gdp-per-capita-worldbank` not `/grapher/economy/gdp-per-capita-worldbank`.

## The 17 locked topic slugs

The slugs below were locked 2026-05-19 (3-agent debate: Hans + Max + Gregor) and amended 2026-05-19 via user override (`accountability` → `governance`). The first seven (`fiscal`, `energy`, `elections`, `economy`, `demography`, `human_development`, `environment`) are the live-on-disk set as of 2026-05-22; the remaining ten are scheduled to come online as Phase 2 P.\* per-family ingestions land.

### Live (Phase 0 / Phase 1 era)

| Slug | Citizen title | Hosts |
| --- | --- | --- |
| `fiscal` | Money & debt | State budgets; CAG state accounts; finance commission devolution; outstanding debt; market borrowings |
| `energy` | Power & fuel | Electricity capacity / generation / consumption / losses; coal & oil products; renewables; DISCOM finance |
| `elections` | Elections | Per-AC + per-PC results; turnout; party share; candidate counts; postal ballots |
| `economy` | Economy | GSDP / NSDP; sectoral output; CPI / WPI / IIP; per-capita income; industry & trade |
| `demography` | People | Census; SRS; CRS; population projections; sex ratio; density; urbanisation |
| `human_development` | Human development indices | HDI; MPI; HCI (composite indices only — `health` / `education` / `amenities` split out per Phase 2) |
| `environment` | Environment | Air quality; forest cover; carbon; protected areas; river quality; climate observations |

### Scheduled (Phase 2 P.\* / Phase 3)

| Slug | Citizen title | Hosts | Comes online with |
| --- | --- | --- | --- |
| `governance` | Measuring the government | CAG state-audit findings + performance audits; PRS bill tracker; RTI compliance (CIC); Lokpal / CVC; PHC vacancy %; teacher absenteeism; NJDG pendency; FIR-to-chargesheet ratio | Phase 2 CAG + governance ingest |
| `schemes` | Where the money goes | MGNREGA; PMAY-G/U; PM-KISAN; ICDS; PM-POSHAN; NFSA; CSS + CS scheme delivery | Phase 2 e-GramSwaraj / PFMS ingest |
| `local_govt_finance` | Panchayats & local bodies | e-GramSwaraj; 15th Finance Commission grant flows; State Finance Commission transfers; ULB own revenue; ZP/BP receipts-payments; CAG Local Bodies Audit | Phase 2 e-GramSwaraj ingest |
| `work` | Work & jobs | PLFS (quarterly + annual); NSS-EUS (with methodology break vs PLFS); wages; female LFPR; self-employment; work-related migration | Phase 2 PLFS ingest |
| `judiciary` | Courts | NJDG pendency + disposal; eCourts metrics | Phase 2 NJDG ingest |
| `crime` | Crime | NCRB Crime in India (IPC + SLL); Prison Statistics India; FIR-to-chargesheet ratio | Phase 2 NCRB ingest |
| `health` | Health | NFHS-5 (and successors); HMIS monthly; SRS annual; CRS births/deaths; public health expenditure | Phase 2 NFHS-5 ingest |
| `education` | Education | UDISE+ school metrics; AISHE higher-ed; ASER learning outcomes; literacy | Phase 2 UDISE+ ingest |
| `amenities` | Household amenities | NFHS HH module (water, sanitation, electricity, cooking fuel); JJM; SBM; PMAY-U/G housing | Phase 2 NFHS-5 ingest (HH module) |
| `technology` | Telecom & internet | TRAI quarterly performance; broadband penetration; mobile subscribers; NFHS ICT module | Phase 2 TRAI ingest |

When `health`, `education`, and `amenities` ingestions land, `human_development` retains only the composite indices (HDI / MPI / HCI). The decomposition is deliberate: a citizen comparing infant mortality across states should land on `/topic/health`, not `/topic/human_development`.

## Cross-cutting tags that are NOT top-level topics

`nutrition` and `gender` were considered as top-level slugs and rejected (2026-05-19, Max). Reason: both genuinely cross-cut multiple families.

- **`nutrition`** spans `health` (anaemia, stunting, wasting from NFHS) + `schemes` (PM-POSHAN, ICDS take-home rations) + `demography` (food security from HCES).
- **`gender`** spans `health` (MMR, ANC visits) + `education` (female literacy, GER) + `work` (female LFPR, gender wage gap) + `crime` (offences against women) + `governance` (women in local-government office).

Both ship as values inside `topic_tags[]` on individual indicator rows — the M:N model handles cross-cutting honestly without forcing a single-parent home.

## Adding a new topic

A new top-level topic requires:

1. **Max sign-off** — the topic must point at concrete indicators, not be aspirational.
2. **An issuing-authority data source** for at least three citizen-meaningful indicators in that topic.
3. **A row added to `datasets/taxonomy/topics.json`** with stable slug + citizen title + `source_id` for the topic's primary publisher.
4. **The compile step** (`backend/yen_gov/canonical/topics_seed.py`, per ADR-0030 §D18) regenerates `topics.parquet` from the JSON in the same commit.
5. **The frontend topic landing page** at `frontend/src/routes/topic/<slug>/+page.svelte` exists (or is explicitly deferred with a TODO row); a topic without a landing page is a 404 hazard for citizens following a tagged-indicator chip.

Removing a topic is harder: every indicator carrying that tag must lose it (M:N edge update) and the citizen URL `/topic/<slug>` must 301 to a successor for one release before going 404. See [migration handbook](../how-to/canonical-migration.md) for the standard deprecation cycle.

## What this concept is NOT

- **Not a directory.** `datasets/indicators/<topic>/` no longer exists (retired in Phase 1 per `TODO/20260517-canonical-long-format-pivot.md` §7 rows 1.8a–1.8f). All indicators live under `datasets/<family>/` keyed by the publisher's natural family, not by topic.
- **Not the citizen URL grammar.** URLs are `/indicator/<slug>` and `/topic/<slug>`; a topic does NOT appear inside an indicator URL.
- **Not exhaustive.** Indicators may have one, two, or three topic tags. Mean is ~1.4 tags per indicator at the current corpus.
