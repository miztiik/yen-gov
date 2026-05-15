# AGENTS.md — tools/eci_recon

**Last Updated**: 2026-05-15

Canonical rationale and ingest mechanics live in [docs/architecture/backend/sources-eci.md](../../docs/architecture/backend/sources-eci.md). This file is only the module map for the recon tools.

## Invariants

- **Reconnaissance only.** This module MUST NOT write to `datasets/`. Output goes to stdout, `.runtime/`, or a deliberately archived doc; `notes/` is non-authoritative scratch per CLAUDE.md §3.
- **No backend imports.** `tools/` is self-contained per CLAUDE.md §4. If you find yourself wanting `from backend.something import ...`, the function belongs in `backend/` and is being called by recon for the wrong reason.
- **Persist permalinks, never signed URLs.** Per [backend/sources-eci.md](../../docs/architecture/backend/sources-eci.md#url-grammar--statistical-reports): `/eci-backend/public/api/download?url=<base64>` URLs are time-limited. Recon records `https://eci.gov.in/files/file/<id>-<slug>/`-style permalinks instead.
- **Honest about reachability.** When a host is unreachable, the inventory must say so per probe. Do NOT silently drop failed probes — they are findings, not noise.

## Phase boundary

- **Phase A (this module)**: discover what exists. No download, no parse, no ingest.
- **Phase B (backend adapter)**: download XLSX, parse to schemas, emit to `datasets/`. Different code path. If you are adding XLSX parsing here, stop and move the work into `backend/yen_gov/sources/eci/` with docs in `sources-eci.md`.

## Refreshing `NEW_PORTAL_SECRET`

The header value comes from ECI's public JS bundle. When ECI deploys a new bundle, refresh per the README. Not a credential — do not gate it behind config or env vars; it is a public constant we are quoting.
