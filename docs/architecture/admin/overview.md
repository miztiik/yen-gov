# Admin app — overview

**Last Updated**: 2026-05-09 (status: walking skeleton + Inventory panel shipped — Phase 4 v0)

> **Status note.** Phase 4 v0 has landed: `admin/` Svelte app, `backend/yen_gov/admin/` FastAPI module, and the **Inventory** panel are live. **Schemas, Pipeline, and Patches panels are still design-only.** When those land, promote their subsections in this doc into sibling files (`admin/patches.md`, etc.).

The admin app is a **separate, dev-only Svelte application** that lives alongside the public frontend but ships in its own bundle, talks to a local **FastAPI** wrapper around the existing pipeline, and is **never deployed to GitHub Pages**. It is the operator's cockpit: dataset inventory, schema health, pipeline status, and a patch-file editor for data corrections.

This page covers why the admin is separated, the stack, the panels, and the patch-file model used for data corrections. It does not cover the Python pipeline itself (see [backend overview](../backend/overview.md)).

## Why a separate app

CLAUDE.md Holy Law #1 says "static-first production" and Holy Law #2 says "backend = local pipeline only". The public bundle on GitHub Pages MUST function with no backend. Embedding admin features behind a feature flag in the public bundle creates two persistent risks:

1. Dead code in the production bundle (admin routes/components that no public user can reach).
2. Tempting future regressions (a "small" admin endpoint hosted somewhere "just for now").

A separate app makes the boundary physical. The public Pages deploy never sees admin code; the admin deploy never happens at all (it runs locally).

### Separation rationale (summary)

| Property | Public frontend | Admin app |
| --- | --- | --- |
| Where it runs | GitHub Pages | Operator's localhost |
| Backend | None | FastAPI on `localhost:8000` |
| Read scope | `datasets/` (committed JSON/SQLite/PMTiles) | `datasets/`, `.runtime/`, schemas, git status |
| Write scope | None | Patch files under `datasets/patches/`, optionally trigger pipeline runs |
| Bundle | `frontend/dist/` → Pages | `admin/dist/` → never deployed |
| Authentication | None | Localhost-bound; no auth (single-user developer tool) |

### Separation — alternatives considered

- **Embed admin in the public bundle behind a build flag.** Rejected: leaks dead code, tempts future hosting, and means every Pages deploy needs the flag verified.
- **CLI-only admin (no UI).** Considered. Workable for power users; rejected because the inventory and patch-file editor are genuinely interactive (filters, side-by-side diff). CLI commands still exist (`yen-gov inventory`, `yen-gov validate`) — the admin UI calls the same code.
- **Streamlit.** Lower-effort, but ties UI choices to Python's render model and produces a feel inconsistent with the Svelte public app. Rejected on consistency.
- **Tauri / Electron desktop app.** Adds packaging complexity for zero benefit over a localhost web app.

## Stack

| Concern | Choice |
| --- | --- |
| Frontend framework | Svelte 5 + Vite 6 (mirrors public frontend for skill reuse) |
| Styling | Tailwind 3 + a darker default theme to visually distinguish from public app |
| API | FastAPI under `backend/yen_gov/admin/` (new module, sibling of `cli.py`) |
| API server | `uvicorn yen_gov.admin:app --reload --port 8000` |
| API contract | OpenAPI (FastAPI auto-emits at `/docs` and `/openapi.json`); admin frontend types generated via `openapi-typescript` |
| Auth | None — `uvicorn` binds to `127.0.0.1` only |

## Repository placement

```
admin/                          ← new top-level directory (sibling of frontend/)
├── package.json
├── vite.config.ts              ← proxy /api → http://127.0.0.1:8000
├── src/
│   ├── main.ts
│   ├── routes/
│   │   ├── Inventory.svelte
│   │   ├── Schemas.svelte
│   │   ├── Pipeline.svelte
│   │   └── Patches.svelte
│   └── lib/
│       └── api.ts              ← generated OpenAPI client

backend/yen_gov/admin/           ← new Python module
├── __init__.py                  ← FastAPI app
├── inventory.py                 ← list datasets, freshness, provenance
├── schemas.py                   ← schema-health checks (Tier A + B per CLAUDE.md §11)
├── pipeline.py                  ← read .runtime/logs/, trigger runs (subprocess)
└── patches.py                   ← read/write datasets/patches/

datasets/patches/                ← new (created lazily on first patch)
└── <election>/
    └── YYYYMMDDHHMMSS_kind.json ← user-preferred timestamp format
```

The public `frontend/` is untouched. CLAUDE.md §3's "create folders only when real code is about to land" — these are created in Phase 4.

## Running locally

```powershell
# terminal 1 — FastAPI (admin extras: pip install -e backend[admin])
python -m uvicorn yen_gov.admin:app --port 8000 --app-dir backend

# terminal 2 — Svelte dev server (proxies /api → 127.0.0.1:8000)
cd admin; bun install; bunx vite
# http://localhost:5174
```

A convenience `npm run admin` script that runs both with `concurrently` is **not yet wired** (single-line ask deferred until a second panel makes it worth the dependency). For now, two terminals.

The admin Vite config proxies `/api/*` to `127.0.0.1:8000` so the bundle has no hardcoded host.

## Panels (v1)

### Inventory ✅ shipped (2026-05-09)

Implemented in [`backend/yen_gov/admin/inventory.py`](../../../backend/yen_gov/admin/inventory.py) (endpoint `GET /api/inventory`) and [`admin/src/routes/Inventory.svelte`](../../../admin/src/routes/Inventory.svelte) (UI).

The backend walks `datasets/elections/<event>/<state>/`, and for every cell reports:
- `summary.schema_version`, `summary.sources[]` (provenance), `summary.path`, `summary.mtime` from `result.summary.json`.
- `ac_results.found` (count of files in `results/*.json`) vs `ac_results.expected` (length of the matching `datasets/reference/in/states/<state>/constituencies.json`); `missing` if any.
- Whether `parties.json` and `results.sqlite` exist alongside.

UI is a single dark-themed table sorted by event, then state, with completeness coloured (emerald 100% / amber partial / rose 0%). State codes are joined to display names from `datasets/reference/in/states.json` so the table reads "S22 Tamil Nadu", not just "S22" — same fix as the public app.

A real bug was caught during the first browser walkthrough: WB renders `293 / 294 ACs` but `Math.round` was rounding to 100%; the UI now uses `Math.floor` so any missing AC drops below 100. Lesson: completeness UIs must round *down*, never up.

Drives a coverage table: rows are (event, state) pairs; aggregating into a state × election matrix is deferred until a second event lands (today only one event exists; a 1-column matrix would just be the list).

### Schemas (planned)

Runs the two-tier validator from CLAUDE.md §11:
- **Tier A** — every `*.schema.json` validates against JSON Schema 2020-12 meta-schema; `$ref`s resolve; `x-version`/`x-changelog` invariants hold.
- **Tier B** — every `*.json` under `datasets/` validates against its declared `$schema`.

Failures link to the offending file with the validator's error path highlighted. This is a UI for what CI already does on PR; the value is the *interactive* diff during data wrangling.

### Pipeline (planned)

- **Last runs** — table of recent `.runtime/logs/<run-id>/` directories, with status, duration, source, and log links.
- **Trigger** — buttons to run sources (e.g. `yen-gov pipeline run --source eci --election AcGenMay2026 --state S22`). Streams the run's stdout/stderr to the page via Server-Sent Events from the FastAPI handler.
- Read-only panel by default; the trigger buttons are gated by a `ADMIN_ALLOW_RUN=1` env var on the uvicorn process to avoid accidental scrapes during exploration.

### Patches (planned)

Editor for the patch-file model (below). Loads a dataset, lets the operator edit specific fields, emits a structured patch under `datasets/patches/`, shows the diff, and offers a "stage in git" button.

## Patch-file model for data massaging

Direct edits to `datasets/` would lose the audit trail and conflate "the upstream said this" with "we corrected it to this". The patch-file model keeps both visible.

### Shape

Every patch is a JSON file under `datasets/patches/<election>/<timestamp>_<kind>.json`:

```json
{
  "$schema": "https://yen-gov.in/schemas/patch.schema.json",
  "$schema_version": "1.0",
  "applies_to": {
    "election": "AcGenMay2026",
    "state": "S22",
    "ac": "167"
  },
  "kind": "rename_party",
  "rationale": "ECI portal lists the same party under two spellings on different pages; canonicalising to the form used in datasets/reference/in/parties.json",
  "operations": [
    { "op": "replace", "path": "/results/167/candidates/3/party_eci_code", "from": "AIDMK", "to": "AIADMK" }
  ],
  "sources": []
}
```

- `$schema` / `$schema_version` — patches are themselves a versioned contract surface (CLAUDE.md §11).
- `applies_to` — scope; the apply step only loads the named files.
- `kind` — one of `rename_party`, `merge_candidates`, `fix_typo`, `correct_vote`, etc. Drives validation rules (e.g. `correct_vote` MUST cite a `sources` URL; `fix_typo` MAY be empty).
- `rationale` — human prose required by CLAUDE.md Holy Law #4 (rationale ships with the change).
- `operations` — RFC 6902 JSON Patch operations. Choosing a standard means the apply step is a one-liner (`fast-json-patch` or `jsonpatch` in Python).
- `sources` — provenance for the patch itself per CLAUDE.md §12. Empty array = hand-correction; the rationale field carries the why.

### Apply step

The pipeline's emit phase applies all patches under `datasets/patches/<election>/` in timestamp order to the canonical artifact, *after* the upstream parse and *before* the schema validation. Result: the on-disk artifact is always consistent with `(upstream + patches)`. The patch files themselves stay in git, so anyone reading the repo sees both the upstream-faithful version (in `.runtime/raw/`) and the corrections (in `datasets/patches/`).

### Why patches, not direct edits

- **Auditable.** Each correction is a discrete file with rationale and (where required) a citation. Git diff alone shows what *changed* but not *why*.
- **Reversible.** Delete the patch file → next pipeline run produces the upstream-faithful artifact. No git revert archaeology.
- **Cumulative.** Multiple corrections to the same file compose without merge conflicts (they're separate files).
- **Honest.** The published artifact's `sources[]` still cites the upstream URL; readers who care can diff against `.runtime/raw/` to see exactly what we changed.

### Patch model — alternatives considered

- **Direct edits to `datasets/` JSON, git diff as audit trail.** Rejected: loses the upstream-faithful version, makes "rerun the pipeline" destructive, hides rationale.
- **A single patches.json per election with all corrections.** Rejected: turns into a merge-conflict magnet; hard to attribute rationale per correction.
- **Database of corrections + emit on build.** Adds a backend, violates Holy Law #2.

## Provenance and the admin app

The admin **never** strips or weakens provenance. Patch files have their own `sources[]` (per CLAUDE.md §12). When patches are applied to a downstream artifact, the resulting artifact's `sources[]` is the union of (upstream + patch) provenance. The admin panel surfaces both halves so the operator sees what they're about to publish.

## Phase plan

Admin lands in **Phase 4** of the [frontend phasing](../frontend/overview.md#phasing). Phases 1–3 (public Explore, Psephlab, Compare) are higher priority because they are user-facing; the admin shortens *our own* loop and is built once we have enough data variety to need it.

## See also

- [Backend overview](../backend/overview.md) — the pipeline the admin wraps.
- [Frontend overview](../frontend/overview.md) — public app, separate bundle.
- [Schemas reference](../../reference/schemas.md) — what the schema-health panel validates against.
- [Data provenance](../../concepts/data-provenance.md) — applies to patches too.
- CLAUDE.md §1 (Holy Laws), §11 (schema versioning), §12 (provenance).
