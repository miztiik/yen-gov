# Data Flow

**Last Updated**: 2026-06-10

This document describes how data moves through the yen-gov system, from upstream sources to the static GitHub Pages bundle.

## Three actors, one direction

```
  ECI / Wikipedia / LGD / TCPD      (upstream sources; read locally, no network fetch)
            |
            v  parse + validate + schema-check
  +-------------------------+
  |  backend/yen_gov/       |   (local Python pipeline; never deployed)
  +-------------------------+
            |
            v  emit (schema-validated long-format CSV)
  +-------------------------+
  |  datasets/              |   (CONTRACT SURFACE; owned by neither runtime)
  +-------------------------+
            |
            v  dev: Vite middleware streams from ../datasets at /data
            v  prod: deploy step places datasets/ alongside dist/
  +-------------------------+
  |  frontend bundle + data |   (static; deployed to GitHub Pages)
  +-------------------------+
```

Data flows in one direction only: **upstream -> backend -> datasets -> frontend bundle**. Nothing flows back.

Details per stage:

- Backend layering: [backend/overview](backend/overview.md).
- Per-source adapters: [ECI](backend/sources-eci.md), [Wikipedia](backend/sources-wikipedia.md).
- Dev-time data access + prod placement: [frontend/data-loading](frontend/data-loading.md).

## Why `datasets/` is its own tier

CLAUDE.md §3 introduces `datasets/` as a top-level tier owned by neither `backend/` nor `frontend/`. Two reasons:

1. **Decoupling.** The backend should not know about Vite's `public/` convention. The frontend should not know about the pipeline's emit machinery. Both treat `datasets/` as a contract: schema-validated CSV files at known paths.
2. **Holy Law #1 alignment.** Production has no backend. Whatever the frontend needs at runtime must be in the bundle. `datasets/` is what gets copied in. Keeping it outside `frontend/src/` makes the boundary explicit — `frontend/` is *code*, `datasets/` is *data*.

The frontend's `vite.config.ts` registers a small `serveDatasets()` middleware that streams `../datasets/` under `/data/` during `vite dev`. The deploy step then places the same `datasets/` tree alongside `dist/` on the Pages origin so production URLs resolve at the same `/data/` prefix — see [frontend/data-loading > production placement](frontend/data-loading.md#production-placement). The frontend bundle never copies or commits data files (CLAUDE.md §4).

## Read/write rules

| Path                    | Backend writes? | Backend reads? | Frontend reads? |
| ----------------------- | --------------- | -------------- | --------------- |
| `datasets/schemas/`     | no (hand-authored) | yes (validation) | no |
| `datasets/data/`        | yes             | yes            | yes (DuckDB-WASM `read_csv(columns=...)`) |
| `datasets/elections/`   | yes             | yes            | yes (per-state/election CSV shards) |
| `datasets/boundaries/`  | no (`tools/boundaries/` writes locally) | no | yes (TopoJSON/GeoJSON via boundaries.ts; PMTiles for future village tier) |
| `datasets/taxonomy/`    | no (hand-authored JSON; parquets retired) | yes | no (consumers use `datasets/data/entities/*.csv` instead) |
| `.runtime/raw/`         | yes (debug only, gitignored) | yes | no |

The backend is the **only writer** to `datasets/`. Any future tool that wants to mutate `datasets/` must do so through the backend's emit layer so two-tier validation (CLAUDE.md §11) runs first.

## Why no runtime backend

GitHub Pages serves a static bundle. There is no server-side process, no database, no API. Every byte the UI needs at runtime lives inside `frontend/dist/`. This is not a limitation we work around — it is a chosen constraint that:

- removes a class of operational concerns (no uptime, no cost, no auth),
- makes results auditable and forkable (the bundle *is* the data), and
- forces clean schema design (if it can't be precomputed, it can't ship).

If a feature ever needs server-side compute, the answer is to precompute it into a long-format CSV artifact under `datasets/data/`, not to introduce a runtime backend.

## See also

- [`docs/architecture/data-model.md`](data-model.md) — the entities that live in `datasets/`.
- [`docs/reference/schemas.md`](../reference/schemas.md) — current schema list and versions.
- [`docs/reference/identifiers.md`](../reference/identifiers.md) — ID conventions used in paths and payloads.
- `CLAUDE.md` §3, §4, §11 — authoritative contracts.
