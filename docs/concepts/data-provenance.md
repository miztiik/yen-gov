# Data Provenance

**Last Updated**: 2026-06-11

> Every observation yen-gov publishes carries a `source_id` foreign key to one row in `datasets/data/entities/source.csv`. This is non-negotiable (CLAUDE.md Holy Law #9, §12). The mechanism is the canonical sources table — a **citation ledger** keyed on `(producer, title, vintage)`, adopted from OWID `origin.*` (CLAUDE.md §0a "The One Rule") plus four yen-gov extensions for confidence + verifiability. Schema is at v3.0 per [ADR-0042](data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor) (2026-05-26).

## The contract

`datasets/data/entities/source.csv` is the **one** sources table for the whole repo. Every observation row in every long-format CSV family — `data/datapoints/electoral/`, `data/datapoints/geo/`, elections family, office-holders, etc. — carries a `source_id` that points at exactly one row in that table.

There is no per-shard sources array. There is no embedded URL on an observation row. There is no second provenance table for a particular family. **One table, one FK, one shape.**

This is enforced at the writer (UPSERT into DuckDB with deterministic source_id derivation) and at the consumer (frontend contract tests reject any observation with NULL or dangling `source_id`).

## The shape: citation, not fetch

Each row in `source.csv` represents **one citation** — one publisher × one report × one vintage — not one fetch event. The natural key is the triple `(producer, title, vintage)`. The `source_id` is a deterministic 12-character hash of that triple:

```python
source_id = "src-" + sha256(f"{producer}|{title}|{vintage}".encode("utf-8")).hexdigest()[:12]
```

The same triple yields the same `source_id` anywhere in the codebase — across cold starts, across machines, across ingest paths. When the live HTTP fetcher and the hand-imported transcription path both populate observations for the same ECI Statistical Report, they BOTH derive the same `source_id` and collapse to one citation row.

This is the v2.0 shape, established in [ADR-0032](data-provenance.md#adr-0032-sources-citation-ledger) (2026-05-20) and sharpened on `vintage` semantics by [ADR-0042](data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor) (2026-05-26, schema v3.0). v1.0 was a fetch ledger keyed on `(url, content_hash)`; that shape conflated citations with fetch events and is removed from the contract.

### What `vintage` means (v3.0)

`vintage` is the **strongest period anchor available** for the citation:

- **Publisher edition when the upstream publishes one.** RBI Handbook of Statistics on Indian States ships an edition tag `"2024-25"`; CEA Monthly Executive Reports ship `"2026-03"`; NFHS ships `"NFHS-5"`. Use the publisher's verbatim string.
- **Operator snapshot window when the publisher publishes no edition tag.** NITI Aayog ICED APIs are continuously-updated and carry no edition tag; the operator records `"2024-25"` to mean "snapshotted in FY 2024-25." The snapshot window matches the meadow-tier path (`datasets/<family>/_meadow/<source>/<vintage>/`) per [ADR-0041](../architecture/data/canonical-store.md#adr-0041-meadow-tier) §non-negotiable #4.

`vintage` is required and non-empty (v3.0 schema sets `minLength: 1`). v2.0 permitted `""` when the publisher published no tag; v3.0 retires that loophole because the meadow path always encodes an operator-chosen vintage and the citation row must anchor to it. The 3-arg hash signature `(producer, title, vintage)` is unchanged — only the field MEANING is sharpened.

## The 11 columns

Full schema lives in [`docs/architecture/data/canonical-store.md` §5](../architecture/data/canonical-store.md#5-sources-schema-d5). Quick reference:

**OWID `origin.*` (verbatim, 5 columns) — `producer`, `title`, `vintage`, `license`, `url_main`, `citation_full`** (the last two optional). These are the citizen-facing facts the reader would write if they were citing the source themselves.

**yen-gov extensions (5 columns) — `source_id` (PK), `confidence_tier`, `is_issuing_authority`, `verification_method`, `notes`** (the last optional). These add the trust signal the citizen needs to weigh the number.

Total: 8 required + 3 optional = 11 fields. Schema-locked, additive bumps only without a new ADR.

## Four lifecycles, one table

Every observation row's provenance is one of four shapes. All four collapse to the same `(producer, title, vintage)` identity:

1. **Live-fetched (most rows).** Pipeline pulled bytes from a URL. The citation row carries `producer + title + vintage + url_main + license + verification_method="live-fetch"`.
2. **Archived-snapshot.** Pipeline holds a local copy of the bytes (e.g. a downloaded PDF or HTML page that no longer renders cleanly). Same citation row shape with `verification_method="archived-snapshot"`. The local archive lives outside the canonical store; the row attests we can re-verify against bytes we hold.
3. **Transcribed.** Operator typed numbers from a web view or scanned report that adapters cannot parse. Same citation row shape with `verification_method="transcribed"`, `url_main` optional. The same publisher / report / vintage yields the same `source_id` as a live-fetched copy would.
4. **Editorial.** yen-gov is the source of the framing (e.g. a derived rollup, an analytical category). `producer = "yen-gov"`, `license = "internal"`, `is_issuing_authority = false`, `confidence_tier = "gold"`, `verification_method = "editorial"`, `url_main = null`.

Control-plane artifacts (`datasets/manifest.json`, run logs under `.runtime/logs/`) are operator state, not citizen-facing data. They MAY stamp `generated_at` with wall-clock; they do NOT participate in the `source.csv` FK contract (CLAUDE.md §10 carve-out).

## Idempotency and fetch telemetry — what changed at v2.0

v1.0 carried `content_hash`, `first_fetched_at`, `last_seen_at` on the citation row as idempotency / freshness anchors. v2.0 **removes** these fields from the contract. The reasoning is structural:

- A citation is publisher × report × vintage — properties of the published document. They don't change when the pipeline polls more often.
- Fetch telemetry is pipeline-operator state — properties of how often / how recently the pipeline ran. They change every run.

Mixing the two on one row caused the **fetched_at smear** lesson (/memories/lessons.md 2026-05-16): re-running an ingest pipeline rewrote N artifacts' `fetched_at` even when upstream bytes were byte-identical. The v1.0 attempt to mitigate (SHA-gating, sidecars, `write_text_if_changed`) addressed the symptom; v2.0 addresses the cause by removing the smearable fields from the contract.

Adapters that still need byte-change detection write `.runtime/<adapter>/<source_id>.json` sidecars. These are ephemeral by CLAUDE.md §2 — never referenced from any committed artifact, never citizen-facing.

The CLAUDE.md §10 anti-pattern still holds: **`datetime.now()` is forbidden as input to observation content**. The way to satisfy the rule is to keep wall-clock OUT of the citizen-facing row entirely, which v2.0 does by construction.

## What does NOT live in `source.csv`

- **Fetch timestamps** (`first_fetched_at`, `last_seen_at`, `date_accessed`) — removed at v2.0 per above.
- **`content_hash`** — removed at v2.0 per above; lives in `.runtime/` sidecars if any adapter wants it.
- **Intermediate downloaded files** under `.runtime/raw/` (per [ADR-0003](../architecture/backend/core.md#adr-0003-no-fetch-cache)). Throwaway debug artifacts; no `source_id`, no schema, no place in `datasets/`.
- **Reference materials a human consulted** to write a hand-authored entity. Those go in commit messages, not as sources rows. A sources row records what the *pipeline* fetched OR what the operator *transcribed* OR what yen-gov is *editorially* asserting — not what a maintainer happened to read.
- **Identifier conventions** — "S22 is the ECI code for Tamil Nadu" is documented in [`identifiers.md`](../reference/identifiers.md), not as a per-row source.
- **Editorial notes about an indicator** — these are typed fields on `taxonomy/indicators.json` (`description_short`, `description_long`, `excluded_notes`, methodology break narratives), not provenance.

## Why this is mandatory

Civic data without provenance is anti-data. A reader cannot:

- assess whether the upstream has been updated since,
- reproduce the result by re-fetching or by re-reading the cited report,
- argue with the source if a number looks wrong,
- trust the publisher.

Treating provenance as a hard contract — enforced by the writer, surfaced in `CLAUDE.md` Holy Laws, captured in every Definition of Done — is what separates a publishing pipeline from a data-laundering one. Treating the citation (not the fetch event) as the unit of provenance is what makes the contract honest to the citizen, who cites reports, not URLs.

## Design rationale

This section consolidates the rationale (Context + Decision + key Consequences, condensed) of the ADRs that define the provenance contract. Each ADR's full body lives EITHER as the receipts folded below + verbatim under [Rejected alternatives](#rejected-alternatives), OR in `docs/archive/decisions/` (superseded). The originating `docs/architecture/decisions/` files were deleted in D-DOC3.10 closure; the redirect map lives at [`docs/reference/decision-index.md`](../reference/decision-index.md).

### ADR-0032: sources-citation-ledger

Status: accepted 2026-05-20; superseded on `vintage` semantics by [ADR-0042](#adr-0042-sources-schema-v3-vintage-as-period-anchor). Authority: Hans + Max (sources schema, parallel concurrence 2026-05-20). Supersedes the v1.0 fetch-ledger shape established in [ADR-0030](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) section Group 4.

**Context.** [ADR-0030](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) established a single sources table as the one provenance table for the whole repo: every observation row carries a `source_id` FK pointing at exactly one row in that table. v1.0 shipped the table as a fetch ledger keyed on `(url, content_hash)`, with `source_id = sha256(url)[:12]`, alongside fields `first_fetched_at`, `last_seen_at`, `date_accessed`, `url_download`. The intent was OWID-aligned provenance plus idempotency anchors so a re-fetch with byte-identical bytes would be a no-op. Two weeks of real use revealed four structural problems:

1. **Identity collision with citation.** The same Statistical Report from ECI - one report, one citation a citizen would write - was represented by N source rows whenever the live-fetched path produced one URL per AC and the hand-imported path produced N synthetic `local://<event>/<state>/eci-section-10` URLs. The v1.0 sources.parquet on disk held 84 rows to cover 55 distinct citations. The rendering layer had to collapse them by string-equality anyway because the FK pointed at 30 distinct source rows for the same citation. The fix was not "deduplicate at render" - the contract itself was wrong. A citation is one publisher x one report x one vintage. The fetch URL is plumbing.
2. **Fetch telemetry vs publication facts.** `first_fetched_at`, `last_seen_at`, `date_accessed`, `content_hash` are pipeline-operator state. Bundling them into the citizen-facing provenance row mixed two lifecycles: operator lifecycle (changes every run) and citation lifecycle (immutable per report). The /memories/lessons.md 2026-05-16 "fetched_at smear" entry already documented the harm; v1.0 partly mitigated with content-hash-keyed sidecars but the citizen-facing row STILL carried `first_fetched_at` and `last_seen_at`. As long as fetch telemetry lived on the citation row, every poll wrote bytes.
3. **URL change rotates the FK.** `source_id = sha256(url)[:12]` means: ECI changes the URL of one Statistical Report (which it does, frequently) and every observation that cited that report has a dangling FK. The citation itself didn't change - same producer, same report, same vintage - but the v1.0 contract said the source_id was the URL's identity, not the report's.
4. **Copy-paste / hand-imported is second-class.** When an operator transcribed a number from a PDF the live fetcher could not parse, v1.0 required a URL. Operators minted `local://...` sentinels and the confidence_tier silently dropped from "gold" to "silver" because the URL "wasn't real". Both were workarounds for the fetch-ledger shape: the synthetic URL was a lie, and the confidence-tier downgrade was on the wrong axis. Hans flagged this as a citation-honesty failure.

Per CLAUDE.md section 0a "The One Rule" - OWID's `origin.*` schema treats provenance as a citation: `producer`, `title`, `vintage`, `license`, `url_main`, `citation_full` are first-class; `date_accessed` is on the row but treated as a polled-on date (not an immutable citation field). yen-gov adopts the OWID shape verbatim and replaces the v1.0 fetch-ledger extensions with citation-friendly ones.

**Decision.** The sources table v2.0 (`datasets/data/entities/source.csv`) is a **citation ledger**. One row per `(producer, title, vintage)` triple. `source_id` is deterministic: `"src-" + sha256(f"{producer}|{title}|{vintage}").hexdigest()[:12]`. Field count: 11 (8 required + 3 optional). Required (8): `source_id` (PK), `producer`, `title`, `vintage`, `license`, `confidence_tier`, `is_issuing_authority`, `verification_method`. Optional (3): `url_main`, `citation_full`, `notes`. Removed (breaking) from v1.0 (6 fields): `url`, `url_download`, `content_hash`, `first_fetched_at`, `last_seen_at`, `date_accessed`. Rename: `authored` -> `editorial` in the `verification_method` enum. 8-layer enforcement ships in one fused commit (JSON Schema v2.0 strict; Pydantic `SourceRow` rewrite with `extra="forbid"`, `frozen=True`, `Literal` types; DuckDB `_SRC_DDL` rewrite + `INSERT BY NAME` for additive-bump coexistence; `canonical_eci_backfill` rewrite collapsing two `SourceRow(...)` sites to one citation-triple builder; citation helper module `derive_source_id`/`render_citation`/`verification_method_rank` + enum-mirror constants; regenerated `sources.parquet` + rewritten `source_id` column on all 31 state-shard `election_results.parquet` files via one-shot migration tool; CLAUDE.md section 10 + section 12 doctrine update; concept doc + canonical-store.md rewrite + this ADR).

**Consequences.** Wins: citizen-honest attribution (the chip "Source: ECI, Statistical Report Section 10..." appears ONCE per citation across all consumers, not 30 times across 30 path-divergent fetch rows); smaller adapter code (identity is the citation triple, dedup is a `dict[source_id, SourceRow]` setdefault); smaller source table (84 v1.0 rows -> 55 v2.0 rows, 35% reduction); no more fetched_at smear (v2.0 removes the smearable fields from the contract entirely); URL rotation no longer breaks FKs (`source_id` is unchanged because `(producer, title, vintage)` is unchanged); hand-imported and live-fetched paths are first-class peers. Losses: lost cross-fetch byte-change detection on the citizen row (mitigated by the `.runtime/<adapter>/<source_id>.json` sidecar pattern); v1.0 `local://` synthetic URLs for hand-imported ACs are dropped (mitigated: the citation row itself still carries the producer/title/vintage; the only loss is the click-through link which was never real anyway). Forward compatibility: schema is `x-version: "2.0"`; further additive bumps follow the established `x-changelog` rules in CLAUDE.md section 11. Breaking changes (v2.x -> v3.0) require a new ADR (delivered as ADR-0042).

### ADR-0042: sources-schema-v3-vintage-as-period-anchor

Status: accepted 2026-05-26. Authority: User (autonomous mandate) + Gregor (architect) + Fowler (engineering) - parallel custom-agent consult 2026-05-26, both converged. Supersedes ADR-0032 on vintage semantics only (ADR-0032's body remains in force for the citation-ledger pivot, 11-column shape, identity-as-citation-triple rationale). Refines ADR-0041 section non-negotiable #4 (meadow path vintage MUST equal citation row vintage); the invariant text in ADR-0041 stays as-is, this ADR resolves the semantic ambiguity that previously made #4 structurally unenforceable for unvintaged publishers.

**Context.** [ADR-0032](#adr-0032-sources-citation-ledger) defined `vintage` as "OWID origin.vintage verbatim - source's OWN period / revision / edition label" and permitted empty string when the source publishes no vintage. The energy sources seed file ratified that interpretation: 5 NITI ICED rows ship with `vintage = ""` because the ICED APIs are continuously-updated and carry no publisher edition tag; 7 RBI/CEA rows ship with `vintage = "2024-25"` (or `"2026-03"`) because those upstreams DO publish edition tags. [ADR-0041](../architecture/data/canonical-store.md#adr-0041-meadow-tier) then established `datasets/<family>/_meadow/<source>/<vintage>/<file>.json` as the canonical-input contract path. The `<vintage>` segment is operator-chosen and encodes "when did we snapshot this." For ICED meadow files it is `2024-25` (the FY in which the operator ingested). For RBI/CEA meadow files it is `2024-25` / `2026-03` (which happens to equal the publisher tag). ADR-0041 section non-negotiable #4 says: "Vintage in meadow path MUST match `vintage` field of citation row the `source_id` FK resolves to." With ICED rows carrying `vintage = ""` in the citation ledger but `_meadow/iced/2024-25/` on disk, the invariant is structurally unsatisfiable - `"" != "2024-25"`. Any Tier-B validator implementing #4 strictly would fail-closed on every ICED meadow file.

Three options surfaced: alpha (redefine `vintage` as "operator snapshot window" everywhere; hash signature unchanged 3-arg; 5 ICED rows' `vintage` flips `""` -> `"2024-25"`; 5 source_ids re-hash; observation FKs re-emit); beta (relax non-negotiable #4 with a wildcard - rejected because "A rule with a wildcard escape is no rule"; the Tier-B fence becomes ceremony); gamma (schema split adding new field `snapshot_vintage` extrinsic + rename existing `vintage` to `publisher_vintage` intrinsic - rejected because duplicates filesystem state into the citation ledger, and collapses on re-snapshot of unvintaged sources via identity hash collision). Per CLAUDE.md section 0a "The One Rule" - OWID's `origin.vintage` is documented as "the year, month, or other label representing the version of the data." OWID does NOT prescribe what to do when the publisher publishes no vintage; in practice OWID curators fill it with the operator's best guess at a period anchor.

**Decision.** `datasets/schemas/source.schema.json` ships as v3.0. The `vintage` field's description is rewritten to "strongest period anchor available - publisher edition when the upstream publishes one; operator snapshot window when not." `minLength: 1` is added. The 5 NITI ICED rows flip vintage `""` -> `"2024-25"`. The 7 RBI/CEA rows are unchanged. `derive_source_id` keeps its 3-arg signature. Three commits: structural (schema bump + docstring updates + status pointer on ADR-0032 + new ADR-0042 + concept-doc update); behavioural atomic (5 ICED `_TRIPLES` entries flip; baked-id constants + tests updated; sources.parquet regenerated; indicators.json baked source-id strings search-replaced; energy `.parquet` files re-emitted via canonical writer); structural (new Tier-B rule `tier_b_meadow_vintage_matches_source_id` with positive + negative tests).

**Consequences.** Wins: ADR-0041 section non-negotiable #4 becomes structurally enforceable as a strict equality check with zero wildcards; Tier-B rule ships as a regression guard, not a runtime fix; 3-arg identity contract preserved (Holy Law #9 surface untouched); schema stays 11 columns (no `snapshot_vintage` duplication of filesystem state); citation ledger stays free of operator-mutability; re-snapshot of ICED next FY produces NEW source rows with `vintage = "2025-26"` and NEW source_ids (no collision with FY24-25 rows); 5 publisher-edition rows (RBI/CEA) byte-identical pre/post. Costs: 5 NITI ICED source_ids re-hash; ~70 observation FK rows re-emit; ~28 baked-hash references in `indicators.json` search-replace; 4 backend test files updated (mitigated by the canonical writer's existing UPSERT determinism + `emit-taxonomy`'s hash-regen path); PR-B is 3 commits instead of the planned 1 (mitigated by Tidy-First decomposition - Commit 1 and Commit 3 are gating-green-out-of-box); ADR-0032 section vintage description is now historically inaccurate without the supersession pointer read first (mitigated by the Status pointer + `Last Updated` discipline). Forward compatibility: future schema bumps to v3.x add fields per the established `x-changelog` rules in CLAUDE.md section 11; breaking changes (v3.x -> v4.0) require a new ADR; Phase 2 P.2+ families authoring NEW sources MUST follow this rule (publisher edition tag if one exists; otherwise operator snapshot window matching the meadow path).

---

## Rejected alternatives

This section preserves the rejected-alternatives receipts from the ADRs whose rationale is folded above. Each subsection is anchored as `#adr-NNNN-rejected-alternatives` for the redirect index.

### ADR-0032 rejected alternatives

**Rejected A: Domain-as-identity (`source_id = sha256(domain)`).** Collapse all ECI sources to one row by hashing only the domain. Rejected: `eci.gov.in` publishes 200+ distinct reports (state assembly elections, general elections, byelections, ECI orders, ECI press notes); collapsing them loses citation precision. The citizen seeing "Source: ECI" for a S22 AcGenApr2021 result and "Source: ECI" for a U05 PCGen2019 result wants to be able to distinguish them; the domain is a breadcrumb, not an identity. Hans flagged this as the citation-precision failure mode.

**Rejected B: Drop source.csv entirely; use git-commit citations.** Recognise the canonical store is in git, and let the commit message be the provenance. Rejected: re-creates the per-shard smear we already eliminated in ADR-0030. The same RBI Handbook cited by 50 indicators would generate 50 commit messages with no shared identity; the citizen has no FK to dedupe against; cross-indicator queries ("show me everything we cite from the 2024-25 Handbook") become git-log archaeology. Violates Holy Law #9 - provenance is data, not commentary on data. Gregor flagged.

**Rejected C: `content_hash` back as nullable for "adapters that earn it".** Keep `content_hash` as an optional column so live-fetch adapters can populate it; hand-imported rows set it to NULL. Rejected: re-introduces the fetched_at-smear class one layer up. The moment the column exists on the citizen-facing row, some adapter will start updating it on every poll. The /memories/lessons.md 2026-05-16 lesson was: bytes != data. Adapters that need fetch telemetry write `.runtime/` sidecars where the smear stays isolated from the citizen surface. Fowler flagged.

**Rejected D: `citation_full` REQUIRED with adapter-mandatory templating.** Make the rendered citation a stored field, computed by the adapter. Rejected: dies the moment citation style evolves (e.g. APA vs Chicago vs in-line). A read-time renderer reads the structured (producer, title, vintage) triple and composes the citation in whichever style the consumer wants. Storing the rendered string locks the schema to one display convention. Jony flagged the typography-coupling failure mode.

### ADR-0042 rejected alternatives

**Rejected alpha-as-stated (Fowler's plain phrasing): `vintage` = "operator snapshot window" always.** Fowler's initial framing dropped the publisher-edition concept entirely. Rejected because RBI Handbook genuinely DOES publish a "2024-25" edition tag and that's a different epistemic fact from "we snapshotted in 2024-25." For the current dataset both phrasings produce the same string values, but the accepted framing preserves the OWID semantic (publisher tag when published) and scales to families where the publisher edition matters for citation precision (NFHS-5 vs NFHS-4 is a publisher-edition distinction; if it ever flipped to operator-snapshot semantics, two NFHS-5 snapshots in different operator-FYs would collide on the same source_id - wrong).

**Rejected beta: wildcard relaxation of ADR-0041 section non-negotiable #4.** A Tier-B rule with a wildcard escape is computationally tautological. The fence's existence requires uniform enforcement. Fowler-tagged this as "empty-string-as-magic-value band-aid"; Gregor-tagged it as "Holy Law #5 violation - when the rule says NEVER, it must mean never."

**Rejected gamma: `publisher_vintage` + `snapshot_vintage` schema split.** Duplicates filesystem state into the citation ledger; collapses on re-snapshot of unvintaged sources. `snapshot_vintage` exists only because filesystem layout exists. The meadow path component IS the snapshot vintage. Putting it on the citation row duplicates filesystem state into the citation ledger - a control-plane concern leaking into the citizen-facing data contract. When ICED is re-snapshotted next FY (paths become `_meadow/iced/2025-26/`), gamma requires the operator to author NEW source rows with NEW `snapshot_vintage` AND `publisher_vintage = ""` (still empty). Both rows have the same `publisher_vintage = ""` -> identity hash collision on `(producer, title, publisher_vintage)`. The 4-arg hash fix-up Gregor surfaced (`(producer, title, publisher_vintage, snapshot_vintage)`) ripples the identity contract change across every Phase 2 source and re-introduces the very migration cost gamma was supposed to avoid. Gregor-tagged this as "speculative generality wearing architectural-purity clothing."

**Rejected delta-prime: 4-arg hash `(producer, title, publisher_vintage, snapshot_vintage)`.** Considered as a fix-up for gamma's identity collision. Rejected because it ripples the identity contract change across every Phase 2 source (not just energy ICED), making PR-B blast-radius cover the entire citation ledger. The 3-arg hash is part of the Holy Law #9 surface; changing the arity is a Level-5 contract change with cross-family implications. The accepted decision achieves the same outcome with the 3-arg hash intact.

**Rejected epsilon: defer the entire question; ship Tier-B rule WITHOUT addressing the ICED case.** Mark ICED meadow files exempt from Tier-B; ship the rule for CEA/RBI only. Rejected because the exemption list becomes a soft allowlist that grows - every future continuously-updated source asks "can I be exempt too?" The exception eats the rule.

### ADR-0002 rejected alternatives

Archived 2026-05-19 (superseded by ADR-0030 and refined by ADR-0032). Body preserved verbatim at [`docs/archive/decisions/0002-provenance-as-sources-list.md`](../archive/decisions/0002-provenance-as-sources-list.md). Trace: domain-as-identity per-shard `sources[]` array (per archived ADR-0002); rejected alternatives in that ADR included keeping sentinel strings + adding a `sources` array alongside, a single `source` URL + separate `derivations: []` array, and requiring non-empty `sources` always with an explicit `hand_authored: true` flag. ADR-0030 retired the per-shard array entirely in favour of a `source_id` FK to a single table; ADR-0032 then re-shaped that table from a fetch ledger to a citation ledger.

## See also

- `CLAUDE.md` Holy Law #9, §12 — authoritative statement.
- [`docs/architecture/data/canonical-store.md` §5](../architecture/data/canonical-store.md#5-sources-schema-d5) — full sources schema with column-by-column rationale.
- [ADR-0032 — Sources table v2.0: citation ledger keyed on (producer, title, vintage)](data-provenance.md#adr-0032-sources-citation-ledger) — the design decision that established this contract; includes the four rejected designs. Superseded on `vintage` semantics by ADR-0042.
- [ADR-0042 — Sources schema v3.0: `vintage` as strongest period anchor available](data-provenance.md#adr-0042-sources-schema-v3-vintage-as-period-anchor) — sharpens `vintage` to enable meadow-tier path enforcement; identity contract unchanged.
- [ADR-0041 — Meadow tier (`datasets/<family>/_meadow/<source>/<vintage>/`)](../architecture/data/canonical-store.md#adr-0041-meadow-tier) — the canonical-input contract whose §non-negotiable #4 is now structurally enforceable thanks to ADR-0042.
- [ADR-0030 — Canonical store on long-format CSV read by DuckDB-WASM](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) — established the canonical store and citation-ledger contract; v1.0 of this schema lived there.
- [ADR-0003 — No HTTP cache layer; intermediates live in `.runtime/raw/`](../architecture/backend/core.md#adr-0003-no-fetch-cache) — why intermediates are excluded.
- [`docs/concepts/owid-alignment.md`](owid-alignment.md) — OWID is the canonical reference (§0a).
- [`docs/reference/identifiers.md`](../reference/identifiers.md) — code conventions for entities inside payloads (separate from the provenance of the payload itself).
- [archived ADR-0002 — Provenance as a list of `{url, fetched_at}` entries](../archive/decisions/0002-provenance-as-sources-list.md) — **superseded** by ADR-0030 + ADR-0032; retained for historical context.

