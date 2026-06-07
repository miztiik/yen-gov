# Backend `core/` — Reusable Infrastructure

**Last Updated**: 2026-05-09

`backend/yen_gov/core/` is the upstream-agnostic foundation of the backend. It contains the HTTP fetcher, the JSON artifact writer, the pydantic models that mirror published schemas, the event types emitted at each pipeline stage, and the structured logger. Nothing in `core/` knows that ECI or Wikipedia exist.

This page covers three load-bearing decisions: pydantic models mirror schemas 1:1, pipeline events are frozen dataclasses (not pydantic), and the on-disk path for fetched intermediates is derived from the URL deterministically.

## Modules

| File | Responsibility |
| ---- | -------------- |
| [`http.py`](../../../backend/yen_gov/core/http.py) | `Fetcher` (httpx + tenacity); reads timeout/retry/UA from `config/processing.json`; writes intermediates under `.runtime/raw/<source>/<derived-path>` (see also: [no fetch cache](../decisions/0003-no-fetch-cache.md)). |
| [`io.py`](../../../backend/yen_gov/core/io.py) | `write_artifact` chokepoint: stamps `$schema`, `$schema_version`, and `sources` (per [provenance contract](../decisions/0002-provenance-as-sources-list.md)); runs Tier-B validation before emit; uses POSIX paths. |
| [`models.py`](../../../backend/yen_gov/core/models.py) | Pydantic v2 `BaseModel` per `*.schema.json`. |
| [`events.py`](../../../backend/yen_gov/core/events.py) | Frozen `@dataclass` events for the structured log + future monitoring layer. |
| [`logging.py`](../../../backend/yen_gov/core/logging.py) | Structured logger writing JSON-lines to `.runtime/logs/<run-id>/`. |

## Pydantic models mirror JSON Schemas 1:1

The contract surface for yen-gov is `datasets/schemas/*.schema.json`. The runtime backend manipulates the same data in-process where we want type safety, IDE autocomplete, and method-call APIs.

We hand-maintain both, with a strict 1:1 invariant enforced by per-model round-trip tests:

- `core/models.py` defines one pydantic v2 `BaseModel` per `*.schema.json` file. Naming follows readability over schema-filename mechanical mapping (`result.constituency.schema.json` → `ConstituencyResult`), since some files *contain* a collection. The historical `state.schema.json` → `StatesCollection` mirror was retired in Phase C of the strangler-fig closeout (the state + UT roster now lives on `datasets/taxonomy/entities.json` and backend consumers read the JSON directly via `_load_states_from_entities`). Similarly the `district.schema.json` → `DistrictsCollection` mirror was retired in T.0c-iii Phase D.1 — see [ADR-0033](../decisions/0033-retire-wikipedia-districts-adapter.md).
- The schema remains the **publication contract** (what external consumers and the validator use). The pydantic model is the **internal contract**.
- Each top-level model carries its own `sources: list[SourceRef]` and exposes `.body_payload()` + `.sources_payload()` (the latter returns JSON-ready `list[dict[str, str]]` since B4-pt3 retired the `core.io.write_artifact` chokepoint). Models never write their own files; callers either stamp `$schema` / `$schema_version` / `sources` around the body themselves or - for canonical long-format data - emit via `yen_gov.canonical.csv_writer.write_csv` per the per-file CSV column contract under `datasets/data/_schema/columns.json`.
- Tests in [`backend/tests/test_core_models.py`](../../../backend/tests/test_core_models.py) round-trip every model through in-memory `Draft202012Validator` against the actual schema file under `datasets/schemas/`. Drift fails CI.
- One asymmetry deserves a name: schemas can mark a field both **required and nullable** (e.g. `result.constituency.others`). `_Artifact.body_payload` uses `exclude_none=True` by default; subclasses with required-and-nullable fields override and re-inject the explicit `null`. Today only `ConstituencyResult` does this.

### Design rationale

Two ways to bridge JSON Schema and Python: generate one from the other, or hand-maintain both with a drift test. Hand-maintenance won because:

- Backend code uses real Python objects (`result.candidates[0].votes`) instead of dict access. Type errors are caught at write time.
- Pydantic v2's validation is faster than jsonschema for the in-process path. We keep jsonschema for the published validator (Tier B) because the schema is the authoritative artifact for outside consumers.
- Refactoring the schema forces an explicit pydantic update — drift is loud, not silent.
- Magnitude is small (≤8 schemas); the round-trip test makes the invariant cheap.

Pydantic models can technically express things JSON Schema can't (custom validators, computed fields). We forbid this in `core/models.py` — anything pydantic-specific lives in `core/events.py` or higher layers.

### Alternatives considered

- **Generate pydantic from JSON Schema (`datamodel-code-generator`)**. Rejected for now: generated code is less ergonomic, harder to grep, and the schemas are small enough that hand-maintenance is cheap. Revisit if we exceed ~20 schemas.
- **Generate JSON Schema from pydantic (`model.model_json_schema()`)**. Rejected: pydantic-generated schemas drift from JSON Schema 2020-12 idioms (extra `definitions`, `anyOf` for nullables instead of `type: ["string", "null"]`). The published schema would become an awkward auto-emit.
- **Skip pydantic, use TypedDict**. Rejected: no runtime validation, no parsing of dates/timestamps, no nested model recursion ergonomics.

## Pipeline events are frozen dataclasses, not pydantic

Pipeline stages (fetch, parse, validate, emit) announce what they're doing for the structured JSON-lines log under `.runtime/logs/` and (eventually) for a FastAPI monitoring wrapper. We feed them through typed event classes, not free-form `logger.info("fetch.started", ...)` calls.

- Each event class is a `@dataclass(frozen=True)` subclass of an internal `_Event` base in `core/events.py`.
- It declares `event_name: ClassVar[str]` (the stable string a log-tailing UI greps on) and `level: ClassVar[str]` (`INFO` / `WARN` / `ERROR`).
- `_Event.to_extra()` flattens fields into JSON-safe scalars: `Path → POSIX string` (CLAUDE.md §2), `datetime → RFC 3339 with Z`, primitives passthrough, anything else `repr()`'d.
- A module-level `emit(logger, event)` helper routes to the right level method.
- `ALL_EVENT_NAMES` pins the public surface; a test asserts it stays in sync with declared classes so renames are caught in CI.

### Design rationale

Events are ephemeral, never serialised as artifacts, never schema-validated. Pydantic's parsing/coercion is dead weight. Adding an `Event` schema under `datasets/schemas/` would conflate "data we publish" with "instrumentation we emit." Frozen dataclasses cost ~100 lines of scaffolding and pay for themselves the first time we rename an event.

The cost is two "typed object" idioms in one codebase (Pydantic for artifacts, dataclass for events). They have different lifetimes and different consumers; mixing them deliberately keeps the right tool in the right place.

### Alternatives considered

- **Pydantic events.** Rejected: dead-weight validation; conflates publication and instrumentation surfaces.
- **Free-form `logger.info("fetch.started", ...)` everywhere.** Rejected: no compile-time check that `fetch.started` is spelled the same in 12 call sites; no enforced field shape.
- **`enum.Enum` of event names + free-form kwargs.** Rejected: pins names but not field shapes; still allows `bytes_downloaded` in one site and `bytes` in another.
- **OpenTelemetry.** Out of scope for a local pipeline writing to a single log file. Revisit if the FastAPI monitoring layer ever needs distributed tracing.

## Intermediate raw-file path derivation

`Fetcher.fetch(url)` writes its response to:

```
.runtime/raw/<source>/<host-stripped-path>
```

Rules:

- **`<source>`** is the logical source name passed by the caller, NOT inferred from the URL. Callers in `sources/eci/` pass `"eci"`; callers in `sources/wikipedia/` pass `"wikipedia"`. Keeps the directory aligned with our adapter naming, even when one upstream serves several hostnames.
- **`<host-stripped-path>`** is the URL's path component (everything after the host), with leading `/` stripped. The query string is appended as `?key=val&...` only when present; URLs without queries get a clean filename. Fragments (`#…`) are dropped.
- POSIX separators throughout, even on Windows. The `Path` is constructed via `pathlib.PurePosixPath`.
- Reserved characters on Windows (`:`, `*`, `?`, `"`, `<`, `>`, `|`) inside the path or query are percent-encoded using `urllib.parse.quote(safe="/")`.
- Path traversal attempts (`..`, leading `/` after stripping) are rejected with `ValueError` rather than written.
- File extension is taken from the URL's path component if present; otherwise no extension is added. We do NOT sniff Content-Type to add an extension.

| URL                                                                                | Source       | On-disk path                                                                                |
| ---------------------------------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------- |
| `https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm`            | `eci`        | `.runtime/raw/eci/ResultAcGenMay2026/partywiseresult-S22.htm`                              |
| `https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22001.htm`         | `eci`        | `.runtime/raw/eci/ResultAcGenMay2026/ConstituencywiseS22001.htm`                           |
| `https://en.wikipedia.org/wiki/Tamil_Nadu_Legislative_Assembly`                    | `wikipedia`  | `.runtime/raw/wikipedia/wiki/Tamil_Nadu_Legislative_Assembly`                              |
| `https://en.wikipedia.org/w/index.php?title=Foo&oldid=123`                         | `wikipedia`  | `.runtime/raw/wikipedia/w/index.php?title=Foo&oldid=123` (Linux/Mac) or percent-encoded (Windows) |

Re-fetches **overwrite** — see also [no fetch cache](../decisions/0003-no-fetch-cache.md): this directory is debug, not history. Operators wanting to compare two runs save off `.runtime/raw/` between runs themselves.

### Design rationale

Filenames are human-readable. An operator can `ls .runtime/raw/eci/ResultAcGenMay2026/` and immediately see what's been pulled. The directory mirrors upstream URL structure, so re-running a parser against a saved file is `python -m yen_gov.sources.eci parse .runtime/raw/eci/ResultAcGenMay2026/ConstituencywiseS22001.htm`. Collision-free as long as upstream URLs are unique (they are).

Acknowledged costs: not a content-addressable store (older bytes lost on overwrite — fine because election results don't change post-declaration); long URLs can in theory hit Windows MAX_PATH (260 chars), but in practice ECI URLs are short.

### Alternatives considered

- **`<sha256(url)>.html`** — collision-free and trivial, but unreadable. Rejected: defeats the debugging purpose.
- **Content-Type-derived extension** (`.html` / `.json` / `.pdf`). Rejected: introduces a fork between "what the URL said" and "what we saved as", complicating re-fetch logic.
- **`<host>/<path>` instead of `<source>/<path>`** — automatic, but ties on-disk shape to upstream hostname changes (ECI redirected from `eciresults.nic.in` historically) and forces special cases for adapters spanning multiple hostnames. Rejected: the logical-source name is more stable.
- **Atomic rename via temp file** — would prevent half-written files on crash. Worth adding inside `Fetcher.fetch` later (it's an implementation detail, not a contract); not codified here.

---

## Design rationale

This section consolidates the rationale (Context + Decision + Consequences, condensed) of the originating ADR that pinned a cross-cutting choice for this subsystem (the no-HTTP-cache rule); the originating ADR file under `docs/architecture/decisions/` was deleted in [docs/archive/plans/20260604-d-doc3-adr-retire-subplan.md](../../archive/plans/20260604-d-doc3-adr-retire-subplan.md) D-DOC3.10 closure. The redirect map lives at [decision-index.md](../../reference/decision-index.md). Folded into this doc per D-DOC3.8 (2026-06-04).

### ADR-0003: no-fetch-cache

Status: accepted 2026-05-17 (Clarifications 2026-05-17 folded-indicator PR).

**Context.** Earlier design proposed a hash-keyed disk cache (`.runtime/cache/<sha256(url)>.{html,meta.json}`) with TTL eviction reading `cache_ttl_seconds` from `config/processing.json`. The user pushed back: "let us not complicate with too much of hashes and TTL and all those nonsense. I think they are just complicating it too much." The realities for this project: ECI election results are immutable post-declaration (once a result is up at `results.eci.gov.in/ResultAcGenMay2026/...`, it does not change); pipeline runs are manual per [CLAUDE.md section 13](../../../CLAUDE.md); re-fetching a few hundred pages is cheap (seconds); and the cost of cache-invalidation bugs (stale data shipped as fresh) is much higher than the cost of an extra HTTP round-trip.

**Decision.** There is no caching layer in `core/http.py`. Every `Fetcher.fetch(url)` call hits the network. Downloaded responses (HTML, JSON, etc.) ARE persisted, but as **intermediates**, not as a cache: path `.runtime/raw/<source>/<url-derived-relative-path>` (see [Intermediate raw-file path derivation](#intermediate-raw-file-path-derivation) above); purpose is troubleshooting and re-parsing (if a parser bug is found, we can re-run the parser against the saved HTML without re-hitting the upstream); lifetime is gitignored (`.runtime/` already is per [CLAUDE.md section 3](../../../CLAUDE.md)), no TTL, no eviction (operator deletes the directory if they want a fresh fetch); schema is none (these files are not a contract surface). Tenacity is still used for retry on transient HTTP failures - that isn't caching, it's basic resilience. The `cache_ttl_seconds` field was removed from `processing.schema.json` in the v2.0 -> v3.0 schema bump.

**Clarifications 2026-05-17 (folded-indicator PR).** The no-cache stance stands; `core/http.py` still has no cache layer. `.runtime/raw/` is throwaway debug, not a published inventory record (gitignored, no schema, no contract surface; the committed indicator JSON is). Collection avoidance lives one layer up - the planner reads `collection_inventory.frozen`, `refetch_requested`, and `pending_periods` on each folded indicator and simply does not call the Fetcher for already-collected `(state, period)` cells. That is not caching; it is the planner not asking again (see [docs/concepts/collection-inventory.md](../../concepts/collection-inventory.md)). `rm` remains the only force-recollect mechanism (a second force-refetch flag was considered and rejected as duplicate state - see [docs/how-to/force-recollect.md](../../how-to/force-recollect.md)). A SHA-gate at the Fetcher (and a paired `.meta.json` per URL) was considered and rejected: bytes != data; the gate that matters is at the collect / planner layer (do we already have this cell?), not at the byte layer (are the bytes identical?). See [CLAUDE.md section 10](../../../CLAUDE.md) anti-patterns.

**Consequences.** No cache-invalidation class of bugs (the only state that determines what we ship is the most recent run's output); simpler `core/http.py` (under ~80 lines instead of a few hundred); `.runtime/raw/` doubles as a debugging artifact and a "what did upstream serve us yesterday?" record (operator can `diff` two runs). Costs: re-running the pipeline always re-fetches (acceptable given pipeline cadence is manual and dataset size is small); if upstream rate-limits us, we hit it on every run (mitigated by `concurrency` cap in `processing.json`; if this becomes a problem, revisit with a deliberate cache ADR rather than retrofitting).

> **DOCTRINE NOTE (2026-06-04, plan section 22.7).** `backend/yen_gov/core/http.py` itself MIGRATES per [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) chunk B4 (network-fetch code is deleted; elections backend = ingest-only against local source CSV; see plan section 21.4). The no-cache rule survives the rip verbatim - it just narrows scope: when there is no fetcher in production runtime, there is by construction no cache. The `.runtime/raw/` debug-snapshot convention stays in force for any operator-tier tooling under [tools/](../../../tools/) that still touches the network for a one-shot asset population (e.g. font builds; see operator-tooling carve-out in `/memories/lessons.md`).

---

## Rejected alternatives

This section preserves the rejected-alternatives receipts from the ADR whose rationale is folded above, verbatim and append-only per [docs/archive/plans/20260604-d-doc3-adr-retire-subplan.md](../../archive/plans/20260604-d-doc3-adr-retire-subplan.md) D-DOC3.8 (2026-06-04). Each subsection is anchored as `#adr-NNNN-rejected-alternatives` for the redirect index.

### ADR-0003 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **Hash-keyed cache with TTL.** Rejected: complexity that defends against a problem we don't have. Election data doesn't change post-declaration.
- **ETag / If-Modified-Since.** Rejected: ECI HTML pages don't reliably set those headers; would be dead code in practice.
- **No persistence at all (parse-in-memory, write only the final artifact).** Rejected: when a parser bug is found mid-development, having the original HTML on disk is invaluable. Loss of `.runtime/raw/` is annoying; loss of upstream is permanent.
- **`write_text_if_changed`-style byte-compare helper at the Fetcher write seam.** Rejected per [CLAUDE.md section 10](../../../CLAUDE.md) anti-pattern: fix non-determinism upstream of the write seam rather than gating bytes at the seam.
- **SHA-gate at the Fetcher with a paired `.meta.json` per URL.** Rejected per 2026-05-17 clarification: bytes != data; the gate that matters is at the collect / planner layer (do we already have this cell?), not at the byte layer (are the bytes identical?).
- **A second force-refetch flag in addition to `rm`.** Rejected per 2026-05-17 clarification: duplicate state; `rm` of the planner's collected-cell record IS the force-recollect mechanism (see [docs/how-to/force-recollect.md](../../how-to/force-recollect.md)).

---

## See also

- [Backend overview](overview.md)
- [Pipeline orchestration](pipeline.md)
- [ADR-0002 — Provenance as a list of `{url, fetched_at}` entries](../decisions/0002-provenance-as-sources-list.md)
- [ADR-0003 — No HTTP cache; intermediates live in `.runtime/raw/`](../decisions/0003-no-fetch-cache.md)
- CLAUDE.md §2 (path rules), §4 (layer rules), §11 (schema versioning), §12 (provenance)
