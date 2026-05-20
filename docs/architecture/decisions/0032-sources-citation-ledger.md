# ADR-0032: Sources table v2.0 — citation ledger keyed on (producer, title, vintage)

**Last Updated**: 2026-05-20
**Status**: Accepted
**Deciders**: User; Hans (Governance) + Max (Indicator Scout) parallel concurrence 2026-05-20 (CLAUDE.md §0a authority assignment for source schema)
**Supersedes**: `datasets/schemas/source.schema.json` v1.0 (the fetch-ledger shape established in [ADR-0030](0030-canonical-store-duckdb-wasm.md) §Group 4)
**Plan reference**: P.0e brief in conversation transcript 2026-05-20; partial cross-references in [`docs/architecture/data/canonical-store.md` §5](../data/canonical-store.md#5-sources-schema-d5)

## Context

[ADR-0030](0030-canonical-store-duckdb-wasm.md) established `datasets/taxonomy/sources.parquet` as the one provenance table for the whole repo: every observation row in every Parquet family carries a `source_id` FK pointing at exactly one row in that table. v1.0 of the schema shipped the table as a **fetch ledger** keyed on `(url, content_hash)`, with `source_id = sha256(url)[:12]`, alongside fields `first_fetched_at`, `last_seen_at`, `date_accessed`, `url_download`. The intent was OWID-aligned provenance plus idempotency anchors so a re-fetch with byte-identical bytes would be a no-op.

Two weeks of real use revealed four structural problems:

### 1. Identity collision with citation

The same Statistical Report from the Election Commission of India (ECI) — one report, one citation a citizen would write — was represented by N source rows whenever the live-fetched path produced one URL per AC and the hand-imported path produced N synthetic `local://<event>/<state>/eci-section-10` URLs. The v1.0 sources.parquet on disk held **84 rows** to cover **55 distinct citations** (53 states × events plus duplicates from path-divergence). When the citizen page on `/lab/S22/AcGenMay2026` rendered "Source: ECI, Statistical Report ... (May 2026)" 234 times for 234 AC results, the rendering layer had to collapse them by string-equality anyway because the FK pointed at 30 distinct source rows for the same citation.

The fix was not "deduplicate at render" — the contract itself was wrong. A citation is one publisher × one report × one vintage. The fetch URL is plumbing.

### 2. Fetch telemetry vs publication facts

`first_fetched_at`, `last_seen_at`, `date_accessed`, `content_hash` are pipeline-operator state: when did the bytes arrive, how do we know they have not changed. Bundling them into the citizen-facing provenance row mixed two lifecycles:

- **Operator lifecycle** (changes every run): `last_seen_at` advances; `content_hash` may rotate.
- **Citation lifecycle** (immutable per report): publisher published this report on this date with this title under this license.

The /memories/lessons.md 2026-05-16 "fetched_at smear" entry already documented the harm of mixing these: any re-run of an ingest pipeline rewrote N artifacts' `fetched_at` even when bytes were byte-identical. v1.0 partly mitigated this with content-hash-keyed sidecars, but the citizen-facing row STILL carried `first_fetched_at` and `last_seen_at`, and the fetcher STILL updated `last_seen_at` on every poll. The leak was structural: as long as fetch telemetry lived on the citation row, every poll wrote bytes.

### 3. URL change rotates the FK

`source_id = sha256(url)[:12]` means: ECI changes the URL of one Statistical Report (which it does, frequently — they rename directories every election cycle) and every observation that cited that report has a dangling FK. The citation itself didn't change — same producer, same report, same vintage — but the v1.0 contract said the source_id was the URL's identity, not the report's.

### 4. Copy-paste / hand-imported is second-class

When an operator transcribes a number from a PDF the live fetcher could not parse, v1.0 required a URL. Operators minted `local://AcGen.../eci-section-10` as a sentinel, and the confidence_tier silently dropped from "gold" to "silver" because the URL "wasn't real". Both of those were workarounds for the fetch-ledger shape: the synthetic URL was a lie (no bytes were fetched from it), and the confidence-tier downgrade was on the wrong axis (the issuing authority status was unchanged; only the verification chain was different). Hans flagged this as a citation-honesty failure: the citizen should not see different confidence tiers for the same ECI report just because two different ingest paths populated different ACs.

### "The One Rule" (CLAUDE.md §0a)

OWID is the canonical reference for data-shape questions. OWID's `origin.*` schema treats provenance as a citation: `producer`, `title`, `vintage`, `license`, `url_main`, `citation_full` are first-class; `date_accessed` is on the row but treated as a polled-on date (not an immutable citation field). yen-gov adopts the OWID shape verbatim and replaces the v1.0 fetch-ledger extensions with citation-friendly ones.

## Decision

`datasets/taxonomy/sources.parquet` v2.0 is a **citation ledger**. One row per `(producer, title, vintage)` triple. `source_id` is deterministic: `"src-" + sha256(f"{producer}|{title}|{vintage}").hexdigest()[:12]`. Field count: **11 (8 required + 3 optional)**.

### Schema (full 11 columns)

| # | Field | JSON Schema type | Required | Origin | Meaning |
|---|---|---|---|---|---|
| 1 | `source_id` | `string` matching `^src-[a-z0-9]{12}$` | yes | yen-gov | deterministic 12-char hash of the citation triple; FK target on every observation |
| 2 | `producer` | `string` minLength 1 | yes | OWID `origin.producer` | publisher organisation; verbatim from the source ("Election Commission of India", "Reserve Bank of India", "yen-gov" for editorial rows) |
| 3 | `title` | `string` minLength 1 | yes | OWID `origin.title` | citizen-readable report name; verbatim |
| 4 | `vintage` | `string` (empty `""` allowed) | yes | OWID `origin.vintage` | source's own period label ("2021", "FY 2024-25", "Aug 2025 issue"); empty when source has no vintage |
| 5 | `license` | `string` enum-6 | yes | OWID `origin.license` | `OGL-IN-1.0` / `CC-BY-4.0` / `CC0-1.0` / `public-domain` / `unknown-public` / `internal` |
| 6 | `confidence_tier` | `string` enum-3 | yes | yen-gov | `gold` (issuing authority) / `silver` (reputable republisher) / `bronze` (single-paper / activist) |
| 7 | `is_issuing_authority` | `boolean` | yes | yen-gov | true iff producer is the issuing authority for this data (ECI on votes = true; a research aggregator republishing ECI numbers = false) |
| 8 | `verification_method` | `string` enum-4 | yes | yen-gov (Hans amendment) | `live-fetch` (adapter polls upstream HTTP each run) / `archived-snapshot` (local copy preserved, any format) / `transcribed` (operator typed from web view, no archive) / `editorial` (yen-gov editorial framing, no external source). **Array order = canonical rank (4→1).** |
| 9 | `url_main` | `["string", "null"]` | no | OWID | landing-page URL; may 404; citizen click-through |
| 10 | `citation_full` | `["string", "null"]` | no | OWID | adapter override; when null, renderer composes `f"{producer}, {title}" + (f" ({vintage})" if vintage else "")` |
| 11 | `notes` | `["string", "null"]` | no | yen-gov | operator scratchpad |

### Removed (breaking) from v1.0 — 6 fields

`url`, `url_download`, `content_hash`, `first_fetched_at`, `last_seen_at`, `date_accessed`. All gone from the contract. Live-fetch adapters that genuinely need this telemetry (cache invalidation, byte-change detection) write `.runtime/<adapter>/<source_id>.json` sidecars — ephemeral, never a contract surface per CLAUDE.md §2.

### Rename

`authored` → `editorial` in the `verification_method` enum. "Editorial" is the citizen-honest label for "yen-gov is the source of this framing"; "authored" was a developer-internal term.

### 8-layer enforcement (ships in one fused commit)

1. JSON Schema v2.0 strict (`additionalProperties: false`, required[8], enums locked) — [`datasets/schemas/source.schema.json`](../../../datasets/schemas/source.schema.json).
2. Pydantic `SourceRow` rewrite (`ConfigDict(extra="forbid", frozen=True)`, `Literal` types) — [`backend/yen_gov/canonical/envelope.py`](../../../backend/yen_gov/canonical/envelope.py).
3. DuckDB `_SRC_DDL` rewrite (11 columns) + `INSERT BY NAME` for additive-bump coexistence — [`backend/yen_gov/canonical/writer.py`](../../../backend/yen_gov/canonical/writer.py).
4. `canonical_eci_backfill` rewrite (two `SourceRow(...)` sites collapsed to one citation-triple builder) — [`backend/yen_gov/pipeline/canonical_eci_backfill.py`](../../../backend/yen_gov/pipeline/canonical_eci_backfill.py).
5. Citation helper module `derive_source_id` / `render_citation` / `verification_method_rank` + enum-mirror constants — [`backend/yen_gov/canonical/citation.py`](../../../backend/yen_gov/canonical/citation.py).
6. Regenerated `datasets/taxonomy/sources.parquet` (55 rows × 11 cols) + rewritten `source_id` column on all 31 state-shard `election_results.parquet` files via [`tools/migrate_sources_v1_to_v2.py`](../../../tools/migrate_sources_v1_to_v2.py).
7. CLAUDE.md §10 + §12 doctrine update.
8. `docs/concepts/data-provenance.md` rewrite + `docs/architecture/data/canonical-store.md` §5 rewrite + this ADR.

The migration tool is intentionally a one-shot under `tools/`, not part of the `backend/yen_gov` package — once the corpus is in v2.0 shape, the canonical-backfill pipeline produces v2.0 source rows directly.

## Consequences

### Wins

- **Citizen-honest attribution.** The chip "Source: ECI, Statistical Report Section 10 (Detailed Results) — S22 AcGenMay2026" appears ONCE per citation across all consumers, not 30 times across 30 path-divergent fetch rows.
- **Smaller adapter code.** Adapters no longer carry SHA-gating logic at the source-row construction site; identity is the citation triple, deduplication is a `dict[source_id, SourceRow]` setdefault in the envelope builder.
- **Smaller sources.parquet.** 84 v1.0 rows → 55 v2.0 rows (35% reduction) for the same observation footprint; future families will see larger collapse ratios because socio-economic indicators reference the same RBI Handbook / NSS report from 50+ indicators each.
- **No more fetched_at smear.** The lesson recurred at every layer; v2.0 removes the smearable fields from the contract entirely. Adapters that still need cache-invalidation state write `.runtime/` sidecars that have no place in the citizen-facing data and no opinion on what the row "means".
- **URL rotation no longer breaks FKs.** ECI renames a Statistical Report URL → `url_main` updates in place; `source_id` is unchanged because `(producer, title, vintage)` is unchanged. All observation FKs remain stable.
- **Hand-imported and live-fetched paths are first-class peers.** Both write `verification_method="archived-snapshot"` and `confidence_tier="gold"` for ECI data; `url_main` is the only field that differs (None for hand-imported, the real URL for live-fetched).

### Losses (and mitigations)

- **Lost: cross-fetch byte-change detection on the citizen row.** Mitigated by the `.runtime/<adapter>/<source_id>.json` sidecar pattern for live-fetch adapters (when v3.x adapters land).
- **Lost: ability to ask "when did we last see this URL" via SQL on sources.parquet.** Same mitigation; the question is operator-state and now lives in operator-state files.
- **Migration cost: 31 state-shard Parquets had to be rewritten** to point at new v2.0 source_ids. Mitigated by [`tools/migrate_sources_v1_to_v2.py`](../../../tools/migrate_sources_v1_to_v2.py) — a 200-line one-shot that reads existing rows, derives new triples, rewrites the FK column in place, and verifies FK closure. Total time: ~5s on a 201,292-row corpus.
- **Migration cost: the v1.0 `local://` synthetic URLs for hand-imported ACs are dropped.** Mitigated: the citation row itself still carries the producer / title / vintage; the citizen still sees "Source: ECI, ...". The only loss is the `url_main` click-through link, which was never a real URL anyway.

### Forward compatibility

The schema is `x-version: "2.0"`; further additive bumps (e.g. v2.1 adds an optional `subtitle`) follow the established `x-changelog` rules in CLAUDE.md §11. Breaking changes (v2.x → v3.0) require a new ADR.

## Rejected Alternatives

### Rejected A: Domain-as-identity (`source_id = sha256(domain)`)

Collapse all ECI sources to one row by hashing only the domain. **Rejected**: `eci.gov.in` publishes 200+ distinct reports (state assembly elections, general elections, byelections, ECI orders, ECI press notes); collapsing them loses citation precision. The citizen seeing "Source: ECI" for a S22 AcGenApr2021 result and "Source: ECI" for a U05 PCGen2019 result wants to be able to distinguish them; the domain is a breadcrumb, not an identity. Hans flagged this as the citation-precision failure mode.

### Rejected B: Drop sources.parquet entirely; use git-commit citations

Recognise the canonical store is in git, and let the commit message be the provenance. **Rejected**: re-creates the per-shard smear we already eliminated in ADR-0030. The same RBI Handbook cited by 50 indicators would generate 50 commit messages with no shared identity; the citizen has no FK to dedupe against; cross-indicator queries ("show me everything we cite from the 2024-25 Handbook") become git-log archaeology. Violates Holy Law #9 — provenance is data, not commentary on data. Gregor flagged.

### Rejected C: `content_hash` back as nullable for "adapters that earn it"

Keep `content_hash` as an optional column so live-fetch adapters can populate it; hand-imported rows set it to NULL. **Rejected**: re-introduces the fetched_at-smear class one layer up. The moment the column exists on the citizen-facing row, some adapter will start updating it on every poll. The /memories/lessons.md 2026-05-16 lesson was: bytes ≠ data. Adapters that need fetch telemetry write `.runtime/` sidecars where the smear stays isolated from the citizen surface. Fowler flagged.

### Rejected D: `citation_full` REQUIRED with adapter-mandatory templating

Make the rendered citation a stored field, computed by the adapter. **Rejected**: dies the moment citation style evolves (e.g. APA vs Chicago vs in-line). A read-time renderer reads the structured (producer, title, vintage) triple and composes the citation in whichever style the consumer wants. Storing the rendered string locks the schema to one display convention. Jony flagged the typography-coupling failure mode.

## Concurrence

Per CLAUDE.md §0a authority assignment, sources schema is owned by Hans (Governance) + Max (Indicator Scout). Both agents ran in parallel on 2026-05-20 against the v1.0 pain analysis above. Hans concurred on the citation-vs-fetch framing and proposed the `verification_method` enum (4 values, descending verifiability) as a yen-gov extension to OWID. Max concurred on the OWID alignment and confirmed the 11-field shape covers every non-elections family already on disk (RBI Handbook, NSS rounds, NFHS, ICMR, MoSPI, CAG, AISHE) without further extension.

User approval logged in conversation transcript at line 404 (2026-05-20 ~18:56 UTC), with explicit go-ahead: "execute end-to-end without confirmation loops".

## See also

- [CLAUDE.md §12 (provenance contract)](../../../CLAUDE.md) — the doctrine entry this ADR rewrote.
- [CLAUDE.md §10 (anti-patterns)](../../../CLAUDE.md) — the four rejected designs are archived there as do-not bullets.
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md) — citizen-facing concept doc.
- [`docs/architecture/data/canonical-store.md` §5](../data/canonical-store.md#5-sources-schema-d5) — full schema reference with column-by-column rationale.
- [ADR-0030](0030-canonical-store-duckdb-wasm.md) — established the canonical store + sources.parquet table; v1.0 of this schema lived there.
- [`backend/yen_gov/canonical/citation.py`](../../../backend/yen_gov/canonical/citation.py) — `derive_source_id` / `render_citation` / `verification_method_rank` + enum-mirror constants.
- [`tools/migrate_sources_v1_to_v2.py`](../../../tools/migrate_sources_v1_to_v2.py) — one-shot migration that produced the v2.0 sources.parquet + rewrote 31 state-shard FKs.
- /memories/lessons.md 2026-05-16 "fetched_at smear" entry — the prior lesson that motivated removing fetch telemetry from the citizen-facing row.
- /memories/lessons.md 2026-05-19 "schema-paired-TS-union" lesson — applied here: schema bump + 6 frontend view-model files (`constituency.{ts,test.ts}`, `election-seats-trend.{ts,test.ts}`, `state-overview.{ts,test.ts}`) updated in the same commit.
