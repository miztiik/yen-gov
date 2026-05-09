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

- `core/models.py` defines one pydantic v2 `BaseModel` per `*.schema.json` file. Naming follows readability over schema-filename mechanical mapping (`result.constituency.schema.json` → `ConstituencyResult`, `state.schema.json` → `StatesCollection`), since the file *contains* a collection.
- The schema remains the **publication contract** (what external consumers and the validator use). The pydantic model is the **internal contract**.
- Each top-level model carries its own `sources: list[SourceRef]` and exposes `.body_payload()` + `.sources_payload()` so `core.io.write_artifact` stays the single chokepoint that stamps `$schema` / `$schema_version` and runs Tier-B validation. Models never write their own files.
- Tests in [`backend/tests/test_core_models.py`](../../../backend/tests/test_core_models.py) round-trip every model through `write_artifact` against the actual schema file under `datasets/schemas/`. Drift fails CI.
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

## See also

- [Backend overview](overview.md)
- [Pipeline orchestration](pipeline.md)
- [ADR-0002 — Provenance as a list of `{url, fetched_at}` entries](../decisions/0002-provenance-as-sources-list.md)
- [ADR-0003 — No HTTP cache; intermediates live in `.runtime/raw/`](../decisions/0003-no-fetch-cache.md)
- CLAUDE.md §2 (path rules), §4 (layer rules), §11 (schema versioning), §12 (provenance)
