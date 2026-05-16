# ADR-0003: No HTTP cache layer; intermediates live in `.runtime/raw/`

**Last Updated**: 2026-05-17
**Status**: accepted

## Context

Earlier design proposed a hash-keyed disk cache (`.runtime/cache/<sha256(url)>.{html,meta.json}`) with TTL eviction reading `cache_ttl_seconds` from `config/processing.json`. The user pushed back: "let us not complicate with too much of hashes and TTL and all those nonsense. I think they are just complicating it too much."

The realities for this project:

- ECI election results are **immutable post-declaration**. Once a result is up at `results.eci.gov.in/ResultAcGenMay2026/...`, it does not change.
- Pipeline runs are **manual** (per `CLAUDE.md` §13: "GitHub Actions cadence: manual dispatch only for now").
- Re-fetching a few hundred pages is cheap (seconds).
- The cost of cache invalidation bugs (stale data shipped as fresh) is much higher than the cost of an extra HTTP round-trip.

## Decision

There is **no caching layer** in `core/http.py`. Every `Fetcher.fetch(url)` call hits the network.

Downloaded responses (HTML, JSON, etc.) ARE persisted, but as **intermediates**, not as a cache:

- Path: `.runtime/raw/<source>/<url-derived-relative-path>` — e.g. `.runtime/raw/eci/ResultAcGenMay2026/partywiseresult-S22.htm`.
- Purpose: troubleshooting and re-parsing. If a parser bug is found, we can re-run the parser against the saved HTML without re-hitting the upstream.
- Lifetime: gitignored (`.runtime/` already is per CLAUDE.md §3). No TTL, no eviction. Operator deletes the directory if they want a fresh fetch.
- Schema: none. These files are not a contract surface.

Tenacity is still used for retry on transient HTTP failures (network blips, 5xx). Retry config (`retry_attempts`, `retry_backoff_seconds`, `timeout_seconds`) reads from `config/processing.json`. That isn't caching — it's basic resilience for an unreliable network.

The `cache_ttl_seconds` field is removed from `processing.schema.json` in the v2.0 → v3.0 schema bump (Phase 0.5B work).

## Consequences

- **Good**: no cache-invalidation class of bugs. The only state that determines what we ship is the most recent run's output.
- **Good**: simpler `core/http.py` — fewer than ~80 lines instead of a few hundred.
- **Good**: `.runtime/raw/` doubles as a debugging artifact and a "what did upstream serve us yesterday?" record. Operator can `diff` two runs.
- **Cost**: re-running the pipeline always re-fetches. Acceptable given pipeline cadence is manual and dataset size is small (TN AC = 234 constituencies).
- **Cost**: if upstream rate-limits us, we hit it on every run. Mitigated by `concurrency` cap in `processing.json`. If this becomes a problem, revisit with a deliberate cache ADR rather than retrofitting.

## Alternatives considered

- **Hash-keyed cache with TTL**. Rejected: complexity that defends against a problem we don't have. Election data doesn't change post-declaration.
- **ETag / If-Modified-Since**. Rejected: ECI HTML pages don't reliably set those headers; would be dead code in practice.
- **No persistence at all (parse-in-memory, write only the final artifact)**. Rejected: when a parser bug is found mid-development, having the original HTML on disk is invaluable. Loss of `.runtime/raw/` is annoying; loss of upstream is permanent.

## Clarifications 2026-05-17 (folded-indicator PR)

The folded-indicator + collection-inventory work
(`indicator.schema.json` v2.0, see [folded-indicator](../../concepts/folded-indicator.md))
clarified how this ADR relates to the higher-level collection model:

- **The no-cache stance stands.** `core/http.py` still has no cache
  layer; every `Fetcher.fetch(url)` still hits the network.
- **`.runtime/raw/` is throwaway debug, not a published inventory
  record.** It is gitignored, has no schema, and is not a contract
  surface. The committed indicator JSON is.
- **Collection avoidance lives one layer up.** The planner reads
  `collection_inventory.frozen`, `refetch_requested`, and
  `pending_periods` on each folded indicator and simply does not call
  the Fetcher for already-collected (state, period) cells. This is
  not caching; this is the planner not asking again. See
  [collection-inventory](../../concepts/collection-inventory.md).
- **`rm` remains the only force-recollect mechanism.** A second
  force-refetch flag was considered and rejected as duplicate state.
  See [How-to: force re-collection](../../how-to/force-recollect.md).
- **A SHA-gate at the Fetcher (and a paired `.meta.json` per URL)
  was considered and rejected.** Bytes ≠ data; the gate that matters
  is at the collect/planner layer (do we already have this cell?),
  not at the byte layer (are the bytes identical?). See CLAUDE.md
  §10 anti-patterns.
