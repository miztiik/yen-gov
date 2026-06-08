# Backend `core/` — Reusable Infrastructure

**Last Updated**: 2026-06-08

`backend/yen_gov/core/` is the upstream-agnostic foundation of the backend. It contains the pydantic models that mirror published schemas, the schema registry + evolution helpers, the event types emitted at each pipeline stage, and the structured logger. Nothing in `core/` knows that ECI or Wikipedia exist.

This page covers two load-bearing decisions: pydantic models mirror schemas 1:1, and pipeline events are frozen dataclasses (not pydantic). The legacy `http.py` (httpx + tenacity Fetcher) and `io.py` (`write_artifact` chokepoint) modules were retired in B4-pt2.4 / B4-pt3 (2026-06-06 / 2026-06-07) per [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) section 21.4: production runtime no longer fetches over the network, and canonical long-format CSV is emitted via `yen_gov.canonical.csv_writer.write_csv` against the per-file column contract under `datasets/data/_schema/columns.json`.

## Modules

| File | Responsibility |
| ---- | -------------- |
| [`models.py`](../../../backend/yen_gov/core/models.py) | Pydantic v2 `BaseModel` per `*.schema.json`. |
| [`schema_registry.py`](../../../backend/yen_gov/core/schema_registry.py) | Reads `x-version` / `$id` from `datasets/schemas/*.schema.json` once at import; provides `schema_id(name)` + `schema_version(name)` so models and composers never hand-type schema metadata (CLAUDE.md section 11). |
| [`schema_evolution.py`](../../../backend/yen_gov/core/schema_evolution.py) | Release-ledger helpers backing `datasets/schema-evolution.json` so validators can resolve an artifact by its declared schema version without guessing from git history (CLAUDE.md section 11). |
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

## See also

- [Backend overview](overview.md)
- [Pipeline orchestration](pipeline.md)
- CLAUDE.md §2 (path rules), §4 (layer rules), §11 (schema versioning), §12 (provenance)
