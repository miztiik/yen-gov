# ADR-0019: Dataset topology — per-state, per-topic SQLite + canonical column names

**Last Updated**: 2026-05-15
**Status**: accepted (amended 2026-05-15 — see §Amendments)

## Context

The election slice ships one `results.sqlite` per `(event, state)` per [ADR-0014](0014-sqlite-emitter.md). The roadmap anticipates additional domains beyond elections — socio-economic indicators (state GDP, electricity consumption, child welfare, healthcare/hospitals), district-level project tracking, and similar metadata, often year-on-year over decades.

Three concrete questions surfaced before any of that code is written:

1. **One database for all of India + all domains, one per state, or one per (state, topic)?** A monolith makes cross-cuts trivial in SQL but is hostile to browsers and to pipelines whose inputs update on different cadences. Many small files keep each artifact small and independently regenerable but push join orchestration to the consumer.
2. **How do consumers join across files later?** SQLite supports `ATTACH DATABASE`, so cross-file joins are possible — but only if the joined columns line up. Without a canonical naming rule, every new emitter invents its own (`state`, `state_id`, `state_code`, `tn_state_code` …) and joins become alias salad.
3. **What does the frontend see?** [TODO/PLAN.md](../../../TODO/PLAN.md) already commits to a future `/explore` page that lazy-loads `sqlite-wasm` for ad-hoc queries. The granularity question is therefore downstream of "what gets fetched per user query?" — not "what gets stored on disk?".

ADR-0014 settled the elections case ("one DB per `(event, state)`; path encodes the state, no `state` column"). This ADR generalises the rule to all future domains and locks the column-naming discipline that makes cross-file joins viable.

## Decision

### 1. Granularity: per-state, per-topic SQLite

Every domain follows the same shape as elections:

```
datasets/<domain>/<state>/<topic>.sqlite          # socio-econ etc.
datasets/elections/<event>/<state>/results.sqlite # already shipped (ADR-0014)
```

Concrete future examples:

```
datasets/socioecon/S22/economy.sqlite        # GDP, sectoral output, …
datasets/socioecon/S22/electricity.sqlite    # consumption, generation, …
datasets/socioecon/S22/welfare.sqlite        # pensions, child welfare, …
datasets/socioecon/S22/healthcare.sqlite     # hospitals, beds, …
datasets/socioecon/S29/economy.sqlite        # Karnataka, same shape
```

The unit of granularity is **the smallest set of tables that (a) regenerates from a single coherent upstream pipeline and (b) shares a single change cadence**. Election results are frozen post-declaration; GDP revises quarterly; hospital counts update yearly. Different cadences never share a deterministic artifact (this is the rule that protects the byte-stable-rebuild property documented in [canonical-store.md](../data/canonical-store.md)).

A topic file may contain several related tables; the test is "do they regenerate together from the same upstream sources?", not "are they conceptually similar?".

### 2. Path encodes state and event; columns encode within-file dimensions

State (and, for elections, event) live in the **file path**, not as columns. This continues ADR-0014's rule. Within a file, dimensions that vary across rows (district, AC, year, quarter, party, candidate rank, …) are columns and follow the canonical names below.

Cross-state queries are the consumer's job: ATTACH the per-state files and `UNION ALL` with the state code injected as a literal (`SELECT 'S22' AS state_eci_code, * FROM economy.gdp_yearly`), or precompute an aggregate offline. The frontend's `/explore` page does the ATTACH for the small set of files relevant to the active query.

### 3. Canonical column names (locked)

Every SQLite emitter — elections, socio-econ, boundaries, anything future — uses these exact column names whenever the underlying concept is present. Adding new canonical names is allowed (additive); renaming an existing one requires another ADR.

| Column                | Type      | Meaning                                                                 |
| --------------------- | --------- | ----------------------------------------------------------------------- |
| `state_eci_code`      | `TEXT`    | ECI state code (`S22`, `U07`, …). Injected at query time when state is path-encoded; persisted as a column only in cross-state aggregates. |
| `district_lgd_code`   | `INTEGER` | LGD numeric district code. Falls back to `district_id` (`TEXT`) with `id_source` column when LGD unavailable, per [identifiers.md](../../reference/identifiers.md). |
| `subdistrict_lgd_code`| `INTEGER` | LGD numeric subdistrict (taluk / tehsil / mandal) code. Promoted to first-class 2026-05-15 by amendment for the TN granular-geo pipeline (`backend/yen_gov/pipelines/boundaries_tn/`). Join key against `<S>-subdistricts.geojson` feature property `subdist_lgd`. |
| `village_lgd_code`    | `INTEGER` | LGD numeric village code. Promoted to first-class 2026-05-15 by amendment for the TN granular-geo pipeline. Join key against `<S>-villages-<dist_lgd>.geojson` feature property `village_lgd`. |
| `ac_eci_no`           | `INTEGER` | ECI Assembly Constituency number, scoped by state.                      |
| `year`                | `INTEGER` | Calendar year, four digits.                                             |

Authoritative definitions live in [docs/reference/identifiers.md](../../reference/identifiers.md). Future additions (`pc_eci_no`, `block_lgd_code`, `gender`, `age_band`, `year_quarter`, …) are added to the table as the first emitter that needs them lands, in the same commit.

### 4. No socio-econ schemas land before the elections slice closes

Holy Law #4 (CLAUDE.md §1) plus Hohpe's "sell options, don't burn them": shipping new domain schemas while the elections slice still has open contracts couples two things that should evolve independently. Socio-econ ingestion starts only after elections is at "full state regenerates deterministically; reconciler agrees with partywise; both JSON outputs validate" (the Phase 4 definition-of-done in [TODO/PLAN.md](../../../TODO/PLAN.md#L101)).

## Consequences

- **Disk and network stay browser-friendly.** Each file is bounded by one state × one topic × its time series. The browser only fetches files the current query touches.
- **Pipeline parallelism is preserved.** Adding Karnataka means writing files under `datasets/<domain>/S29/`; no schema migration, no rewrite of existing state files.
- **Byte-deterministic rebuild stays intact.** Refreshing one topic does not rewrite bytes belonging to another topic or another state. Git diffs on `.sqlite` continue to mean "real data changed".
- **Cross-cuts have a known path.** ATTACH + canonical column names + literal-injected `state_eci_code` covers every cross-state and cross-domain join. The `/explore` page is the surface that does this.
- **Column naming is a one-way door.** Renaming a canonical column later breaks every emitter and every saved query. The four names above are committed; new ones are added only.
- **The naming convention is itself a contract.** Once a path like `datasets/socioecon/S22/economy.sqlite` is written into an ADR and consumed by the frontend, moving it is a coordinated migration. Future emitters MUST follow the `<domain>/<state>/<topic>.sqlite` shape.

## Alternatives considered

- **National monolith (`india.sqlite`)**: rejected. Forces every consumer to download all domains for all states to query one cell. Bundles unrelated change cadences (frozen election bytes get rewritten when GDP refreshes). Destroys the byte-stable-rebuild property. The "easier cross-cuts" benefit is recoverable on demand: a 50-line offline aggregator can ATTACH every per-state file and `CREATE TABLE AS SELECT` a one-off `india.sqlite` for an analyst, without making the browser pay that cost daily.
- **State monolith (`states/<state>/yen.sqlite`, all domains inside)**: rejected. Solves the cross-domain join for one state but reintroduces the cadence-coupling problem within the state — a welfare refresh rewrites the elections bytes. Splitting it back out later is mechanical but requires touching every consumer that learned the monolith's table layout.
- **Persist `state_eci_code` as a column in single-state files**: rejected. Violates DRY (the value is already in the path), and ADR-0014 already established the no-redundant-state-column rule for elections. The literal-injection-at-query-time pattern is one line of SQL and avoids the redundancy.
- **Defer the column-naming decision until socio-econ code lands**: rejected. This is the one irreversible decision in the bundle (a one-way door in Hohpe's terms): every later emitter and every saved `/explore` query bakes in whatever names the first emitter happened to pick. Locking the names today, while no socio-econ code exists, costs nothing and prevents an alias-salad cleanup later.
- **Define a SQL-level `views.sql` macro that joins all per-state files automatically**: rejected for now. Premature — no consumer needs it yet, and the `/explore` page can ATTACH on demand. Revisit if the pattern repeats.

## See also

- [ADR-0014: SQLite emitter](0014-sqlite-emitter.md) — the per-state, per-event rule this ADR generalises. (Superseded 2026-05-19 by ADR-0030; the topology + column discipline below survives unchanged.)
- [ADR-0017: `/explore` page uses sql.js](0017-explore-page-uses-sql-js.md) — historical consumer. (Superseded 2026-05-19 by ADR-0030; `/explore` now uses DuckDB-WASM.)
- [docs/reference/identifiers.md](../../reference/identifiers.md) — authoritative table of canonical IDs and (now) column names.
- [docs/architecture/data/canonical-store.md](../data/canonical-store.md) — current authoritative store layout (Parquet + DuckDB-WASM); replaces the retired `docs/reference/sqlite-schema.md`.
- [TODO/PLAN.md](../../../TODO/PLAN.md) — phasing that defers socio-econ until elections closes.

## Amendments

### 2026-05-15 — `subdistrict_lgd_code` and `village_lgd_code` promoted to first-class

The TN granular-geography pipeline (TODO/TN-GRANULAR-GEO-PLAN.md) is the first emitter that needs sub-district and village identifiers. Per the original §3 rule ("Future additions are added to the table as the first emitter that needs them lands, in the same commit"), both columns are promoted from the prose footnote to first-class rows in the canonical-column table:

- `subdistrict_lgd_code` (`INTEGER`) — LGD numeric subdistrict code; join key against `<S>-subdistricts.geojson` feature property `subdist_lgd`.
- `village_lgd_code` (`INTEGER`) — LGD numeric village code; join key against `<S>-villages-<dist_lgd>.geojson` feature property `village_lgd`.

`block_lgd_code` remains a deferred future addition (no emitter yet). The footnote is updated accordingly. No type or semantic change for any existing column. No migration required for any existing artifact.
