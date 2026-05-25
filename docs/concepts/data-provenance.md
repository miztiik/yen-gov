# Data Provenance

**Last Updated**: 2026-05-26

> Every observation yen-gov publishes carries a `source_id` foreign key to one row in `datasets/taxonomy/sources.parquet`. This is non-negotiable (CLAUDE.md Holy Law #9, §12). The mechanism is the canonical sources table — a **citation ledger** keyed on `(producer, title, vintage)`, adopted from OWID `origin.*` (CLAUDE.md §0a "The One Rule") plus four yen-gov extensions for confidence + verifiability. Schema is at v3.0 per [ADR-0042](../architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) (2026-05-26).

## The contract

`datasets/taxonomy/sources.parquet` is the **one** sources table for the whole repo. Every observation row in every Parquet family — `elections/`, `energy/`, `demography/`, `fiscal/`, `education/`, `health/`, … — carries a `source_id` that points at exactly one row in that table.

There is no per-shard sources array. There is no embedded URL on an observation row. There is no second provenance table for a particular family. **One table, one FK, one shape.**

This is enforced at the writer (UPSERT into DuckDB with deterministic source_id derivation) and at the consumer (frontend contract tests reject any observation with NULL or dangling `source_id`).

## The shape: citation, not fetch

Each row in `sources.parquet` represents **one citation** — one publisher × one report × one vintage — not one fetch event. The natural key is the triple `(producer, title, vintage)`. The `source_id` is a deterministic 12-character hash of that triple:

```python
source_id = "src-" + sha256(f"{producer}|{title}|{vintage}".encode("utf-8")).hexdigest()[:12]
```

The same triple yields the same `source_id` anywhere in the codebase — across cold starts, across machines, across ingest paths. When the live HTTP fetcher and the hand-imported transcription path both populate observations for the same ECI Statistical Report, they BOTH derive the same `source_id` and collapse to one citation row.

This is the v2.0 shape, established in [ADR-0032](../architecture/decisions/0032-sources-citation-ledger.md) (2026-05-20) and sharpened on `vintage` semantics by [ADR-0042](../architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) (2026-05-26, schema v3.0). v1.0 was a fetch ledger keyed on `(url, content_hash)`; that shape conflated citations with fetch events and is removed from the contract.

### What `vintage` means (v3.0)

`vintage` is the **strongest period anchor available** for the citation:

- **Publisher edition when the upstream publishes one.** RBI Handbook of Statistics on Indian States ships an edition tag `"2024-25"`; CEA Monthly Executive Reports ship `"2026-03"`; NFHS ships `"NFHS-5"`. Use the publisher's verbatim string.
- **Operator snapshot window when the publisher publishes no edition tag.** NITI Aayog ICED APIs are continuously-updated and carry no edition tag; the operator records `"2024-25"` to mean "snapshotted in FY 2024-25." The snapshot window matches the meadow-tier path (`datasets/<family>/_meadow/<source>/<vintage>/`) per [ADR-0041](../architecture/decisions/0041-meadow-tier.md) §non-negotiable #4.

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

Control-plane artifacts (`datasets/manifest.json`, run logs under `.runtime/logs/`) are operator state, not citizen-facing data. They MAY stamp `generated_at` with wall-clock; they do NOT participate in the `sources.parquet` FK contract (CLAUDE.md §10 carve-out).

## Idempotency and fetch telemetry — what changed at v2.0

v1.0 carried `content_hash`, `first_fetched_at`, `last_seen_at` on the citation row as idempotency / freshness anchors. v2.0 **removes** these fields from the contract. The reasoning is structural:

- A citation is publisher × report × vintage — properties of the published document. They don't change when the pipeline polls more often.
- Fetch telemetry is pipeline-operator state — properties of how often / how recently the pipeline ran. They change every run.

Mixing the two on one row caused the **fetched_at smear** lesson (/memories/lessons.md 2026-05-16): re-running an ingest pipeline rewrote N artifacts' `fetched_at` even when upstream bytes were byte-identical. The v1.0 attempt to mitigate (SHA-gating, sidecars, `write_text_if_changed`) addressed the symptom; v2.0 addresses the cause by removing the smearable fields from the contract.

Adapters that still need byte-change detection write `.runtime/<adapter>/<source_id>.json` sidecars. These are ephemeral by CLAUDE.md §2 — never referenced from any committed artifact, never citizen-facing.

The CLAUDE.md §10 anti-pattern still holds: **`datetime.now()` is forbidden as input to observation content**. The way to satisfy the rule is to keep wall-clock OUT of the citizen-facing row entirely, which v2.0 does by construction.

## What does NOT live in `sources.parquet`

- **Fetch timestamps** (`first_fetched_at`, `last_seen_at`, `date_accessed`) — removed at v2.0 per above.
- **`content_hash`** — removed at v2.0 per above; lives in `.runtime/` sidecars if any adapter wants it.
- **Intermediate downloaded files** under `.runtime/raw/` (per [ADR-0003](../architecture/decisions/0003-no-fetch-cache.md)). Throwaway debug artifacts; no `source_id`, no schema, no place in `datasets/`.
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

## See also

- `CLAUDE.md` Holy Law #9, §12 — authoritative statement.
- [`docs/architecture/data/canonical-store.md` §5](../architecture/data/canonical-store.md#5-sources-schema-d5) — full sources schema with column-by-column rationale.
- [ADR-0032 — Sources table v2.0: citation ledger keyed on (producer, title, vintage)](../architecture/decisions/0032-sources-citation-ledger.md) — the design decision that established this contract; includes the four rejected designs. Superseded on `vintage` semantics by ADR-0042.
- [ADR-0042 — Sources schema v3.0: `vintage` as strongest period anchor available](../architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) — sharpens `vintage` to enable meadow-tier path enforcement; identity contract unchanged.
- [ADR-0041 — Meadow tier (`datasets/<family>/_meadow/<source>/<vintage>/`)](../architecture/decisions/0041-meadow-tier.md) — the canonical-input contract whose §non-negotiable #4 is now structurally enforceable thanks to ADR-0042.
- [ADR-0030 — Canonical store on Hive-partitioned Parquet read by DuckDB-WASM](../architecture/decisions/0030-canonical-store-duckdb-wasm.md) — established the canonical store + sources.parquet table; v1.0 of this schema lived there.
- [ADR-0003 — No HTTP cache layer; intermediates live in `.runtime/raw/`](../architecture/decisions/0003-no-fetch-cache.md) — why intermediates are excluded.
- [`docs/concepts/owid-alignment.md`](owid-alignment.md) — OWID is the canonical reference (§0a).
- [`docs/reference/identifiers.md`](../reference/identifiers.md) — code conventions for entities inside payloads (separate from the provenance of the payload itself).
- [ADR-0002 — Provenance as a list of `{url, fetched_at}` entries](../architecture/decisions/0002-provenance-as-sources-list.md) — **superseded** by ADR-0030 + ADR-0032; retained for historical context.

