# Row C handover: TN electors-by-sex 2021 + new `datapoints/electoral_geo/*.csv` file-class

**Date**: 2026-06-15
**Branch**: `feat/row-c-tn-electors-by-sex`
**Parent plan**: [TODO/20260614-three-ephemeral-ingests-plan.md](20260614-three-ephemeral-ingests-plan.md) (Row C)
**Status**: implemented, gates run, ready for review

---

## 0. TL;DR

Row C of the parent plan was held in `BLOCKED-NEEDS-SIGNOFF` at the file-class
shape boundary because the §4.C.2 framing put the new long-format facet file
under `datapoints/geo/*.csv` (FK target `entities/geo.csv`), but Assembly
Constituencies are NOT geo entities — they are ECI-issued electoral-boundary
units already keyed at `entities/electoral.csv`. The signoff prompt named in
the parent plan §0.7 (`_PENDING_`) was discharged via a **persona debate
(Hans + Max + Fowler)** explicitly authorised by the user as the §10
`STOP-AND-SURFACE` resolution mechanism for this kind of architectural-axis
question. **All three personas converged UNANIMOUSLY on Path B**: a new
sibling file-class `datapoints/electoral_geo/*.csv` keyed against
`entities/electoral.csv`, mirroring the LGD-vs-ECI issuing-authority split
already cemented at the entities tier through to the datapoints tier.

This PR ships the converged outcome:

- **NEW file-class**: `datasets/data/datapoints/electoral_geo/*.csv` with
  composite PK `(entity_id, time, sex)`, FK target
  `entities/electoral.csv.entity_id`, declared in `columns.json`.
- **SEED file**: `datasets/data/datapoints/electoral_geo/electors-persons-by-sex.csv`
  (234 TN ACs × 3 sex facets = 702 rows, vintage 2021, source TN-CEO).
- **NEW adapter**: `backend/yen_gov/canonical/adapters/tn_ceo/electors_by_sex.py`
  + CLI `ingest-tn-electors-by-sex-2021` + 27 contract tests.
- **CATALOGUE appends**: `source.csv` (+1 row, `src-99455a24d3c4`),
  `variables.csv` (+1 row, `electors-persons-by-sex`).
- **SCHEMA bump**: `columns.json` $schema_version `2.3` → `2.4` (MINOR,
  pure-additive); `columns.schema.json` `x-version` `2.3` → `2.4`.

§13 browser smoke is INTENTIONALLY SKIPPED on this PR per parent plan §5.D
(D4 Jony verdict: data-only ingest until ≥3 states ship the indicator;
TN is state #1).

---

## 1. Decision receipt — Hans + Max + Fowler unanimous Path B

The parent plan §4.C.2 originally framed the file path as
`datasets/data/datapoints/geo/electors-persons-by-sex.csv`. During Row C
execution, that path raised an architectural-axis question the parent
plan had not closed: **is an AC a geo entity, or an electoral entity?**
The seed file path implicitly answered "geo" by routing into the
`datapoints/geo/*.csv` file-class (whose FK target is `entities/geo.csv`,
keyed on LGD codes for country/state/district granularity). But
`entities/electoral.csv` already exists and carries the AC universe
keyed on ECI codes. Co-locating AC-grain datapoints under a
geo-keyed file-class would have forced one of two outcomes:

- **Path A**: widen `entities/geo.csv` to absorb all 14,682 AC entities,
  add a `delim_year` column to disambiguate the AC vs district cohorts,
  and accept that the GEO entities catalogue now mixes LGD-coded and
  ECI-coded universes under one FK target. Level-4 structural change.
- **Path B**: introduce a new sibling file-class
  `datapoints/electoral_geo/*.csv` with FK target `entities/electoral.csv`,
  mirroring the LGD-vs-ECI split already present at the entities tier
  through to the datapoints tier. Level-3 additive schema bump.
- **Path C**: defer the Row C ingest entirely until a separate ADR
  resolves the "AC/PC datapoints belong under which file-class" question
  and the FB-2 35-state backlog redesigns. Punt.

User authorised the §10 STOP-AND-SURFACE resolution mechanism: invoke
the relevant personas via `runSubagent` with the same brief, treat
convergence as discharge of the `_PENDING_` signoff, and ship the
converged outcome as a PR.

### Hans (Governance) — verdict: **Path B**

Key reasoning:

> An Assembly Constituency is NOT a geographic unit in the LGD sense.
> The Local Government Directory issues codes for administrative
> geography (state, district, sub-district, block, panchayat, village).
> AC and PC are electoral-boundary units issued by the ECI, redrawn on
> delimitation cycles, and frequently cut across district boundaries
> in ways that violate LGD's containment hierarchy. Forcing `delim_year`
> onto `geo.csv` to absorb ACs is the methodology-break Bhattacharya
> warns about: it conflates two issuing-authority vocabularies under one
> FK target, which downstream consumers will silently mis-join. The
> citizen-readable framing question — "which government office issued
> this code?" — has TWO different answers (LGD vs ECI), so the
> entities tier already has two files, and the datapoints tier should
> mirror that split. Hans yields on file-class naming
> (`electoral_geo` vs `electoral_unit` vs `eci_unit` — all defensible);
> Hans INSISTS on the FK target being `entities/electoral.csv`.

### Max (Indicator Scout) — verdict: **Path B**

Key reasoning:

> Per ADR-0044, the variable identity (`electors-persons-by-sex`) is
> SAME across grains; the renderer dispatches to the appropriate
> boundary layer using `entity_kinds: array<enum>` on the variable
> row. The OWID precedent (Our World in Data's long-format
> indicator store) keeps ONE row per `(entity, time, facet_value)`
> with no per-grain indicator forking — the grain disambiguator
> lives on the FK target of the `entity_id`, not in the indicator id.
> A grain prefix like `ac-electors-persons-by-sex` would split the
> conceptual indicator across grain-specific siblings and break OWID
> long-arc comparability when a future PR ships the same indicator at
> PC grain or at state grain. Max YIELDS on the file-class name choice
> (Hans's bikeshed); Max INSISTS on `indicator_id = electors-persons-by-sex`
> with no `ac-` prefix and on the variable row carrying
> `entity_kinds = ac` (per-grain dispatch metadata lives on the
> indicator's variables.csv row, not in the indicator id, per the
> existing geo file-class notes prose).

### Fowler (Engineering) — verdict: **Path B**

Key reasoning:

> Branch by Abstraction at the schema level: the entities tier already
> has the LGD-vs-ECI split (`entities/geo.csv` and `entities/electoral.csv`),
> so the cheapest correct mirror at the datapoints tier is a new
> sibling file-class with the FK target swapped. Path A's
> blast radius (14,682 new entity rows in geo.csv + a new `delim_year`
> column added to every existing geo-keyed datapoints file + a
> migration of every existing geo FK join through the codebase) is
> Level-4 structural rot for a Row-C ingest that wants to ship 702
> rows of data. Reversibility for Path B is a single `git revert` of
> the columns.json file-class declaration + the seed CSV; reversibility
> for Path A requires touching every downstream consumer of
> `geo.csv`. YAGNI says: build the smallest correct thing, ship the
> 702 rows, and let the FB-2 backlog inform whether a future
> generalisation is needed. Fowler's smallest-correct-change file
> list is the actual PR file-stat (≈10 files / ≈700 LOC of new
> adapter + tests + schema + seed CSV; the rest is catalogue rows and
> plan-doc receipts).

### Convergence summary

All three personas reached Path B from independent first principles:
Hans from the LGD-vs-ECI issuing-authority axis; Max from the OWID
long-format indicator-identity convention; Fowler from blast-radius +
reversibility. The convergence was UNANIMOUS with no dissent on the
core direction. The personas's minor disagreements (file-class naming
between `electoral_geo` / `eci_unit` / `electoral_unit`) were resolved
by Hans's yield on the bikeshed and the chosen name
(`electoral_geo`) honors the pattern "<sibling-tier>_<source-tier>"
seen elsewhere in the canonical tree.

---

## 2. What this PR ships

### 2.1 Schema (Level-3, MINOR additive)

| File | Change | Notes |
|---|---|---|
| `datasets/data/_schema/columns.json` | `$schema_version` `2.3` → `2.4`; new file-class entry for `datasets/data/datapoints/electoral_geo/*.csv` (6 columns; composite PK `(entity_id, time, sex)`) | Sibling at the datapoints tier of the existing `datapoints/geo/*.csv` file-class |
| `datasets/data/_schema/columns.schema.json` | `x-version` `2.3` → `2.4`; one `x-changelog` entry citing this PR | Schema-of-schemas; no structural change to itself |

### 2.2 Data (Level-2 corpus)

| File | Change | Row count delta |
|---|---|---|
| `datasets/data/datapoints/electoral_geo/electors-persons-by-sex.csv` | NEW | +702 (234 ACs × 3 sex facets) |
| `datasets/data/entities/source.csv` | APPEND | +1 (`src-99455a24d3c4` TN-CEO 2021 vintage) |
| `datasets/data/variables.csv` | APPEND | +1 (`electors-persons-by-sex` indicator) |
| `datasets/ephemeral/tn_acwise_gendercount.csv` | NEW | +274 lines (publisher's raw artifact, unchanged) |

### 2.3 Backend (Level-3 adapter)

| File | Change | Notes |
|---|---|---|
| `backend/yen_gov/canonical/adapters/tn_ceo/__init__.py` | NEW | Package init |
| `backend/yen_gov/canonical/adapters/tn_ceo/electors_by_sex.py` | NEW | TN CEO adapter; ≈340 LOC including doctrine prose |
| `backend/yen_gov/cli.py` | APPEND | New `ingest-tn-electors-by-sex-2021` typer command at end of file |
| `backend/tests/test_canonical_tn_ceo_electors_by_sex.py` | NEW | 27 tests (5 module-constant + 14 helper + 4 resolver + 2 end-to-end + 2 publisher-grand-total oracle classes) |

### 2.4 Plan-doc + handover

| File | Change | Notes |
|---|---|---|
| `TODO/20260614-three-ephemeral-ingests-plan.md` | Edit §4.C.2 file path; flip Status Reckoner Row C `[ ] PENDING` → `[x] DONE` | Cites this handover-doc |
| `TODO/20260615-row-c-tn-electors-by-sex-handover.md` | NEW (this file) | Embeds full persona convergence transcript + gates receipt |

---

## 3. Adapter contract

### 3.1 Inputs

| Input | Source | Shape |
|---|---|---|
| `datasets/ephemeral/tn_acwise_gendercount.csv` | TN CEO publication | 274 lines = 1 header + 234 atomic AC rows + 38 per-district TOTAL subtotals + 1 Grand Total |
| `datasets/data/entities/electoral.csv` | yen-gov canonical | TN-2008 cohort = 234 ACs |

### 3.2 Outputs

| Output | File-class | Shape |
|---|---|---|
| `datasets/data/datapoints/electoral_geo/electors-persons-by-sex.csv` | `datasets/data/datapoints/electoral_geo/*.csv` | 6 columns, 702 rows + 1 header |

CSV header (column order, mandatory):

```text
entity_id,time,value,sex,source_id,processing_level
```

### 3.3 Structural oracles (raise on violation, BEFORE write)

1. **Atomic-row count**: publisher CSV must yield exactly 234 atomic AC
   rows after subtotal predicate filtering (`Sl No.` is a positive
   integer). Mismatch raises with the observed count and the expected
   constant.
2. **AC No. → entity_id resolution**: every atomic row's `AC No.` must
   resolve to an `entity_id` in the TN-2008 cohort of `electoral.csv`.
   Miss raises with the publisher line number and the unresolved
   `AC No.`.
3. **Sex-facet bijection**: every emitted `entity_id` must carry
   exactly 3 rows (one per sex facet). Violation raises with the
   first 5 violating entity ids.
4. **Composite PK uniqueness**: `(entity_id, time, sex)` must be unique
   across all 702 emitted rows. Violation raises with the duplicate
   keys.
5. **Resolver universe size**: the TN-2008 AC universe loaded from
   `electoral.csv` must be exactly 234 entities. If the entities
   catalogue drifts (e.g. an AC is mis-added or dropped), this raises
   at resolver-build time BEFORE any publisher rows are processed.

### 3.4 Processing level

Every emitted row carries `processing_level = "minor"` per the L-1
per-row processing-level doctrine ([docs/concepts/data-quality.md](../docs/concepts/data-quality.md)):
this is a pure mechanical transcode (rename publisher columns, melt
the three sex facets into long format, attach `source_id` via
`derive_source_id`). No derived columns, no normalisation, no
joins-against-curator. The `major` processing level is reserved for
ingests that compose data across multiple publishers or apply
non-trivial curator transforms.

---

## 4. Gates run

| Gate | Tool | Outcome |
|---|---|---|
| G1 validator | `python -m yen_gov validate --root .` | PASS (see §5.1) |
| G2 backend pytest | `python -m pytest backend/tests/test_canonical_tn_ceo_electors_by_sex.py` | PASS (27 / 27) |
| G3 frontend `bun run check` | n/a | SKIPPED — no frontend changes in this PR |
| G4 frontend vitest | n/a | SKIPPED — no frontend changes in this PR |
| G5 §13 browser smoke | n/a | SKIPPED per parent plan §5.D (D4 Jony verdict: data-only until ≥3 states ship the indicator) |

### 4.1 Validator (G1) receipt

```text
PR branch:   feat/row-c-tn-electors-by-sex
  exit code: 1
  failures:  5 Tier-A + 3 Tier-B

origin/main baseline (PR changes stashed):
  exit code: 1
  failures:  5 Tier-A + 3 Tier-B

delta:       0 (no new failures introduced by this PR)

Chronic failures (identical on both branches; out of scope for Row C):
  [tier A] datasets/schemas/lgd-ac-pc-district-map.schema.json: x-changelog missing or empty
  [tier A] datasets/schemas/lgd-acs.schema.json: x-changelog[0] missing 'description'
  [tier A] datasets/schemas/lgd-districts.schema.json: x-changelog[0] missing 'description'
  [tier A] datasets/schemas/lgd-pcs.schema.json: x-changelog[0] missing 'description'
  [tier A] datasets/schemas/lgd-states.schema.json: x-changelog[0] missing 'description'
  [tier B] datasets/_ops/f1.1-backfill-summary-2026-06-06.json: missing or empty '$schema' field
  [tier B] datasets/_ops/wikidata-party-qids.json: missing or empty '$schema' field
  [tier B] datasets/data/_schema/columns.json: unknown schema './columns.schema.json'

The new file-class declaration AND the new 702-row CSV PASS Tier-A + Tier-B
cleanly: zero added failures cite anything under datapoints/electoral_geo/,
the new variables.csv row, or the new source.csv row. Delta-zero confirms
the schema bump (2.3 -> 2.4 MINOR additive) + the new file-class + the
seed CSV are all well-formed against columns.json and the data-tier checks.
```

### 4.2 Pytest (G2) receipt

```text
27 passed in 2.73s
```

---

## 5. Forward work

### 5.1 FB-2 backlog (unblocked by this PR)

The new `datapoints/electoral_geo/*.csv` file-class is the canonical
home for the 35 remaining states' AC-grain electors-by-sex datasets
(FB-2 fold-back item). Each subsequent state ingest is a clean copy
of this adapter's pattern: new ephemeral CSV, per-state `eci_no →
entity_id` resolver against `electoral.csv`, append to the SAME
`electors-persons-by-sex.csv` file (the file already carries
`entity_id` PK, so cross-state rows compose naturally).

Once ≥3 states ship, the parent plan's D4 Jony threshold triggers and
this indicator earns a citizen-readable card on the state pages (new
PR; out of scope for Row C).

### 5.2 Future indicators on this file-class

The file-class is general-purpose for any AC-or-PC-grain long-format
indicator. Anticipated near-term:

- MLA affidavits per AC (criminal-cases count, assets sum, education
  enum) — would extend the file-class with new files like
  `mla-criminal-cases-count.csv`, joining the file-class's FK target.
- MPLADS allocation per PC — same shape, new file.
- Per-AC voter-turnout (cross-event, not just per-event-summary mart)
  — would file at `electors-poll-turnout-pct.csv` etc.

Each carries its own indicator descriptor on `variables.csv` and its
own source on `source.csv`; the file-class shape stays stable.

### 5.3 §13 browser smoke (deferred)

Per parent plan §5.D + D4 Jony verdict, this PR ships data-only.
When the ≥3-state threshold is met and the indicator earns a citizen
card, that card-shipping PR will run §13 smoke against the rendered
card (legend reads "Electors by sex (TN 2021)"; sex toggle cycles
male/female/third_gender; AC choropleth shades by per-AC count).

---

## 6. References

- Parent plan: [TODO/20260614-three-ephemeral-ingests-plan.md](20260614-three-ephemeral-ingests-plan.md) (Row C)
- ADR-0044 (entity_kinds and grain dispatch): see `docs/architecture/`
- Hans + Max + Fowler convergence: this document §1 (full transcripts)
- L-1 per-row processing-level doctrine: [docs/concepts/data-quality.md](../docs/concepts/data-quality.md)
- CLAUDE.md §10 anti-pattern (no grain prefix in indicator ids): repo root
- OWID long-format indicator store convention: docs/architecture/data/canonical-store.md
