# yen-gov

**A free website that shows how every Indian state is doing — money, schools, hospitals, electricity, elections — on a map, with the source for every number.**

> **Live site:** [miztiik.github.io/yen-gov](https://miztiik.github.io/yen-gov/)
>
> Works on a phone. No login. No ads. Every chart tells you where the data came from and when it was fetched.

---

## What you can actually do here

Pick a topic. Pick a state. Compare it to the others. Read the source.

Some questions the site is built to answer today:

- How much money does my state get from the Centre — and is it more or less than other states?
- Which states are borrowing the most, relative to the size of their economy?
- Where does my state stand on installed power capacity, and how much of it is renewable?
- Did the party I voted for actually win the seats it contested? By how much?
- Which state is ahead on a given indicator right now — and which way is it moving?

Every page shows:

- **One indicator at a time**, on a map of India, with a ranked table beside it.
- **The source URL and the date we fetched it** — RBI, Election Commission, Ministry data portals. No anonymous numbers.
- **Honest caveats on the page, not in a footnote** — when a methodology changed (GST, base-year revisions, PLFS replacing the old NSS surveys), the page says so before you read the number.
- **Who is constitutionally accountable** — every topic is tagged State List, Union List, or Concurrent List, so you know which government to ask.
- **What we have and what's missing** — the [`/data-completeness`](https://yen-gov.github.io/data-completeness) view lists every indicator with its editorial documentation status (stub / partial / authored) and collection status (empty / partial / complete). We are loud about gaps. See [folded-indicator](docs/concepts/folded-indicator.md) and [data-quality](docs/concepts/data-quality.md).

## What this is *not*

- **Not a "best state" league table.** No single 0–100 score that hides trade-offs. You compare on one indicator at a time, with the right denominator (per person, per household, per beneficiary).
- **Not a live tracker.** It's a snapshot, rebuilt when new data is ingested. Every page shows when its data was fetched. For today's number, follow the source link to the original portal.
- **Not a replacement for the primary source.** It's a comparability layer with its assumptions visible. RBI, ECI, MoSPI remain the primary sources — we just make their numbers easier to compare and harder to misread.
- **Not an elections-only site, despite the name.** Elections is one topic among several. The home page leads with a fiscal or welfare indicator because what the government does between elections matters more than who won the last one.

## Topics live today

Fiscal capacity (RBI), Energy (installed capacity), Economy, Demography, Elections (Tamil Nadu Assembly May 2026, with more cycles being added).

More topics — education, health, livelihood, infrastructure — are being ingested in priority order. See [`datasets/reference/in/topic-catalogue.json`](datasets/reference/in/topic-catalogue.json) for the current catalogue.

## Why it exists

The Indian civic-data landscape is split between three places that don't talk to each other: government portals (RBI, ECI, MoSPI) that publish the raw numbers but don't compare across states; news dashboards that compare but rarely show provenance; and composite-index reports that rank states with one number but hide the trade-offs. yen-gov is the missing middle — comparable cross-state series with the source URL, fetch timestamp, methodology vintage, and the relevant constitutional list visible on every page.

If you're a researcher, journalist, teacher, student, or just a citizen who wants to know what their state is actually doing — this site is for you.

---

## For developers and contributors

The rest of this file is for people who want to run, modify, or contribute to the project.

### Architecture in one paragraph

Static-first. The deployed site is a build-time bundle on GitHub Pages — there is **no production server**. A local Python pipeline under `backend/` fetches data from official sources, validates every artifact against a JSON Schema, writes the result into `datasets/`, and the Vite frontend copies `datasets/` into the deployed bundle. Every observation row carries a `source_id` foreign key to `datasets/taxonomy/sources.parquet` — a single sources table that adopts OWID's `origin.*` field shape (CLAUDE.md §12). Every schema is versioned with a changelog. The engineering contract that makes this all non-negotiable lives in [CLAUDE.md](CLAUDE.md).

### Repository layout

```
docs/                # Canonical knowledge (Diataxis: architecture / how-to / concepts / reference)
datasets/            # Schemas, reference data, generated artifacts
  schemas/           #   JSON Schemas (draft 2020-12), versioned per CLAUDE.md §11
  reference/         #   Slowly-changing reference data (states, parties, topic catalogue)
  indicators/        #   Generated indicator artifacts (fiscal, energy, economy, ...)
  elections/         #   Per-event/per-state election outputs
config/              # Tunable knobs (e.g. processing.json)
backend/             # Python pipeline + tests + FastAPI dev admin
  yen_gov/           #   Package: validate.py, cli.py, adapters, ...
  tests/             #   pytest
frontend/            # Static GitHub Pages app (Svelte 5 + Vite 6 + Tailwind + d3 + maplibre-gl)
admin/               # Dev-only operator console (separate Vite app, port 5174)
tools/               # Standalone dev/ops tooling (recon scripts, downloaders)
.runtime/            # Ephemeral run state, cached HTML, logs           [gitignored]
TODO/                # Working scratchpads (non-authoritative)
```

### Quick start

Validate the repository (two-tier: schema sanity + data conformance):

```sh
PYTHONPATH=backend python -m yen_gov validate
```

Run the test suites:

```sh
PYTHONPATH=backend python -m pytest backend/tests -q
cd frontend && npm test
```

Run the frontend dev server:

```sh
cd frontend && npm run dev          # http://localhost:5173/
```

Run the admin dev server:

```sh
cd admin && npm run dev              # http://localhost:5174/
```

Re-render the data inventory after each ingest:

```sh
PYTHONPATH=backend python -m yen_gov coverage
```

Writes [`docs/reference/data-inventory.md`](docs/reference/data-inventory.md) — the auto-generated checkpoint of which (state, topic, event) slices have been ingested.

### Documentation

Canonical docs live under [`docs/`](docs/) and follow the Diataxis tiers (architecture / how-to / concepts / reference) with a 3-level depth cap.

Start here:

- [CLAUDE.md](CLAUDE.md) — engineering contract. Read first, every session.
- [`docs/architecture/data-flow.md`](docs/architecture/data-flow.md) — how data moves through the system.
- [`docs/architecture/data-model.md`](docs/architecture/data-model.md) — entities and relationships.
- [`docs/concepts/data-provenance.md`](docs/concepts/data-provenance.md) — every observation carries a `source_id` FK to `datasets/taxonomy/sources.parquet`.
- [`docs/concepts/cross-state-comparison.md`](docs/concepts/cross-state-comparison.md) — why ranked tables, not composite indices.
- [`docs/concepts/schema-is-the-design-system.md`](docs/concepts/schema-is-the-design-system.md) — closed renderer set, schema-driven UI.
- [`docs/reference/schemas.md`](docs/reference/schemas.md) — current schemas with versions.
- [`docs/reference/data-inventory.md`](docs/reference/data-inventory.md) — auto-generated coverage checkpoint.
- [`docs/reference/identifiers.md`](docs/reference/identifiers.md) — ECI / ISO / LGD code conventions.

### Contributing

Read [CLAUDE.md](CLAUDE.md) first. Highlights:

- Contracts before logic — every cross-boundary payload gets a typed schema first.
- Every observation carries a `source_id` FK to `datasets/taxonomy/sources.parquet` (Holy Law #9).
- Schemas are versioned with a changelog (CLAUDE.md §11).
- Tests ship with the feature (§15) — unit, contract, integration, end-to-end as appropriate.
- No band-aids, no mocks (unless explicitly asked), no hardcoded magic values.
- For UI changes: smoke-test via the agent's browser tools against a running dev server (§13).
